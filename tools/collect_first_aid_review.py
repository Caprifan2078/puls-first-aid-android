#!/usr/bin/env python3
"""Quarantine candidate first-aid media; never modify Android assets."""
import hashlib, json, re, subprocess, tempfile, time, urllib.parse
from pathlib import Path
from collect_ui_medicine_photos import get, plain, normalize_license, LICENSES
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "first-aid-review"
LIMIT = 25_000_000
ALLOWED = dict(LICENSES, **{"CC BY-SA 3.0 FR":"https://creativecommons.org/licenses/by-sa/3.0/fr/"})

def collect(row):
    slug = row["id"]
    if not re.fullmatch(r"[a-z0-9-]+", slug):
        raise ValueError("invalid identifier")
    query = urllib.parse.urlencode({"action":"query","format":"json","formatversion":2,
        "titles":"File:"+row["file"],"prop":"imageinfo","iiprop":"url|mime|size|sha1|extmetadata"})
    info = json.loads(get("https://commons.wikimedia.org/w/api.php?"+query,2_000_000))["query"]["pages"][0]["imageinfo"][0]
    meta = info["extmetadata"]
    lic = normalize_license(plain(meta["LicenseShortName"]["value"]))
    if lic.lower()=="cc by-sa 3.0 fr":
        lic="CC BY-SA 3.0 FR"
    if lic != row["license"] or lic not in ALLOWED:
        raise ValueError("license mismatch: "+lic)
    author = plain(meta.get("Artist",{}).get("value",""))
    if not author:
        raise ValueError("author missing")
    kind = {"image/jpeg":"jpg","image/png":"png","video/webm":"webm"}.get(info["mime"])
    if not kind or not 1024<=info["size"]<=LIMIT:
        raise ValueError("MIME or size rejected")
    url = urllib.parse.urlsplit(info["url"])
    if url.scheme!="https" or url.hostname!="upload.wikimedia.org":
        raise ValueError("invalid source")
    data = get(info["url"],LIMIT)
    sha = hashlib.sha1(data).hexdigest()
    upstream = info["sha1"].lower()
    if not re.fullmatch("[0-9a-f]{40}",upstream):
        upstream=format(int(upstream,36),"040x")
    if len(data)!=info["size"] or sha!=upstream or (row.get("reviewed_original_sha1") and sha!=row["reviewed_original_sha1"]):
        raise ValueError("source checksum mismatch")
    if not data.startswith({"jpg":b"\xff\xd8\xff","png":b"\x89PNG\r\n\x1a\n","webm":b"\x1a\x45\xdf\xa3"}[kind]):
        raise ValueError("invalid signature")
    ext="jpg" if kind in ("jpg","png") else "mp4"
    target=OUT/(slug+"."+ext)
    with tempfile.TemporaryDirectory() as tmp:
        original=Path(tmp)/("original."+kind)
        original.write_bytes(data)
        command=["ffmpeg","-nostdin","-v","error","-i",str(original),"-map_metadata","-1","-map_chapters","-1"]
        if kind in ("jpg","png"):
            command+=["-vf","scale=1280:1280:force_original_aspect_ratio=decrease","-frames:v","1","-q:v","3"]
        else:
            command+=["-map","0:v:0","-map","0:a?","-vf","scale=1280:720:force_original_aspect_ratio=decrease:force_divisible_by=2","-c:v","libx264","-pix_fmt","yuv420p","-crf","25","-c:a","aac","-movflags","+faststart"]
        subprocess.run(command+[str(target)],check=True,timeout=180)
    subprocess.run(["ffmpeg","-nostdin","-v","error","-i",str(target),"-f","null","-"],check=True,timeout=180)
    return {"id":slug,"file":target.name,"author":author,"license":lic,"license_url":ALLOWED[lic],
        "source":"https://commons.wikimedia.org/wiki/File:"+urllib.parse.quote(row["file"].replace(" ","_"),safe=""),
        "original_sha1":sha,"original_sha256":hashlib.sha256(data).hexdigest(),
        "derivative_sha256":hashlib.sha256(target.read_bytes()).hexdigest(),"bytes":target.stat().st_size,
        "modifications":"Resized/re-encoded; metadata removed; video converted to MP4; audio preserved where present",
        "clinical_approval":False,"visual_review":"pending","publication":"blocked; review only"}

def main():
    OUT.mkdir(exist_ok=True)
    entries=json.loads((ROOT/"media-review-20261126.json").read_text())["first_aid"]
    records=[]; failed=[]
    for row in entries:
        try:
            records.append(collect(row))
            print("REVIEW",row["id"],flush=True)
        except Exception as e:
            for ext in ("jpg","mp4"):
                (OUT/(row["id"]+"."+ext)).unlink(missing_ok=True)
            failed.append({"id":row["id"],"error":str(e)})
            print("SKIP",row["id"],str(e),flush=True)
        time.sleep(3)
    (OUT/"manifest.json").write_text(json.dumps({"review_only":records,"failed":failed,"notice":"Not clinically approved. Do not publish to users."},ensure_ascii=False,indent=2))
    print("Quarantined",len(records),"of",len(entries),flush=True)
    if not records:
        raise SystemExit("No media verified")
if __name__=="__main__":
    main()
