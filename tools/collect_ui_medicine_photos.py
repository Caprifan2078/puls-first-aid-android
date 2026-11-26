#!/usr/bin/env python3
"""QA-only acquisition of licensed original medicine photographs; no runtime network."""
import hashlib
import html
import json
import re
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "app/src/main/assets/media/medicines"
LIMIT = 8_000_000
UA = "PULS-MedicinePhotoQA/1.0 (https://github.com/Caprifan2078/puls-first-aid-android)"
LICENSES = {"CC0 1.0": "https://creativecommons.org/publicdomain/zero/1.0/",
            "CC BY-SA 4.0": "https://creativecommons.org/licenses/by-sa/4.0/",
            "CC BY-SA 3.0": "https://creativecommons.org/licenses/by-sa/3.0/"}

def normalize_license(value):
    return {"CC0": "CC0 1.0"}.get(value, value)

def plain(value):
    return html.unescape(re.sub(r"<[^>]*>", "", value)).strip()

def get(url, limit):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=35) as response:
        final = urllib.parse.urlsplit(response.geturl())
        if final.scheme != "https" or final.hostname not in {"commons.wikimedia.org", "upload.wikimedia.org"}:
            raise ValueError("unexpected redirect")
        data = response.read(limit + 1)
    if not data or len(data) > limit:
        raise ValueError("invalid size")
    return data

def collect(row):
    slug = row["id"]
    if not re.fullmatch(r"[a-z0-9-]+", slug):
        raise ValueError("bad identifier")
    query = urllib.parse.urlencode({"action":"query","format":"json","formatversion":2,
        "titles":"File:" + row["file"],"prop":"imageinfo","iiprop":"url|mime|size|sha1|extmetadata"})
    info = json.loads(get("https://commons.wikimedia.org/w/api.php?" + query, 2_000_000))["query"]["pages"][0]["imageinfo"][0]
    meta = info["extmetadata"]
    license_name = normalize_license(plain(meta["LicenseShortName"]["value"]))
    if license_name != row["license"] or license_name not in LICENSES:
        raise ValueError("license differs: " + license_name)
    author = plain(meta.get("Artist", {}).get("value", ""))
    if not author or info["mime"] != "image/jpeg" or info["size"] > LIMIT:
        raise ValueError("author, MIME or size rejected")
    url = urllib.parse.urlsplit(info["url"])
    if url.scheme != "https" or url.hostname != "upload.wikimedia.org":
        raise ValueError("unexpected media host")
    data = get(info["url"], LIMIT)
    if len(data) != info["size"] or not data.startswith(b"\xff\xd8\xff") or not data.endswith(b"\xff\xd9"):
        raise ValueError("invalid JPEG")
    digest = hashlib.sha1(data).hexdigest()
    upstream = info["sha1"]
    if digest.lower() != upstream.lower() and int(digest, 16) != int(upstream, 36):
        raise ValueError("original SHA-1 mismatch")
    # Preserve original digest, resize to a local derivative without EXIF/GPS metadata.
    with tempfile.TemporaryDirectory() as temp:
        original = Path(temp) / "original.jpg"
        original.write_bytes(data)
        target = Path(temp) / "display.jpg"
        subprocess.run(["ffmpeg","-nostdin","-v","error","-i",str(original),"-map_metadata","-1","-vf","scale=1000:1000:force_original_aspect_ratio=decrease","-frames:v","1","-q:v","3",str(target)], check=True, timeout=45)
        display = target.read_bytes()
        if not display.startswith(b"\xff\xd8\xff") or len(display)>1_000_000:
            raise ValueError("invalid derived JPEG")
        (OUT / (slug + ".jpg")).write_bytes(display)
    return {"id":slug,"source":row["source"],"author":author,"license":license_name,
        "license_url":LICENSES[license_name],"original_sha256":hashlib.sha256(data).hexdigest(), "original_sha1":digest,
        "sha256":hashlib.sha256(display).hexdigest(), "bytes":len(display),"visual_review":"pending; QA only","modifications":"Resized to fit 1000px; metadata removed; JPEG re-encoded"}

def main():
    candidates = json.loads((ROOT / "media-review-20261126.json").read_text())["medicine_photos"]
    OUT.mkdir(parents=True, exist_ok=True)
    for stale in OUT.glob("*.jpg"):
        stale.unlink()
    rows, failed = [], []
    for row in candidates:
        try:
            rows.append(collect(row))
            print("OK", row["id"], flush=True)
        except Exception as exc:
            failed.append({"id":row["id"],"error":str(exc)})
            print("SKIP", row["id"], str(exc), flush=True)
        time.sleep(2)
    (OUT / "manifest.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    (ROOT / "medicine-photo-qa-report.json").write_text(json.dumps({"retrieved":rows,"failed":failed}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Retrieved", len(rows), "of", len(candidates), "QA photos; not a release")
    collect_kits()

def collect_kits():
    global OUT
    OUT = ROOT / "app/src/main/assets/media/kits"
    OUT.mkdir(parents=True, exist_ok=True)
    for stale in OUT.glob("*.jpg"):
        stale.unlink()
    rows, failed = [], []
    for row in json.loads((ROOT / "media-review-20261126.json").read_text())["kit_photos"]:
        try:
            rows.append(collect(row))
            print("KIT OK", row["id"], flush=True)
        except Exception as exc:
            failed.append({"id":row["id"],"error":str(exc)})
            print("KIT SKIP", row["id"], str(exc), flush=True)
        time.sleep(2)
    (OUT / "manifest.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    report = ROOT / "medicine-photo-qa-report.json"
    data = json.loads(report.read_text())
    data["kits"] = {"retrieved":rows,"failed":failed}
    report.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
