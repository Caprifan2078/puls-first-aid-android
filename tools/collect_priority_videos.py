#!/usr/bin/env python3
"""Bounded video-only candidate acquisition; never publish to assets."""
import argparse,json,time,urllib.parse,re,hashlib
from pathlib import Path
from collect_ui_medicine_photos import get,plain,normalize_license
from audit_media_rights import validate_license_metadata
import collect_first_aid_review as collector
ROOT=Path(__file__).resolve().parents[1]
MAX=50_000_000
BUDGET=120_000_000
MIMES={"video/webm","video/ogg","application/ogg","video/mp4"}
def metadata(row):
    query=urllib.parse.urlencode({"action":"query","format":"json","formatversion":2,"titles":"File:"+row["file"],"prop":"imageinfo","iiprop":"url|mime|size|sha1|extmetadata","maxlag":5})
    info=json.loads(get("https://commons.wikimedia.org/w/api.php?"+query,2_000_000))["query"]["pages"][0]["imageinfo"][0]
    meta=info["extmetadata"]
    field=lambda k:plain(meta.get(k,{}).get("value",""))
    license=normalize_license(field("LicenseShortName"))
    if license.lower()=="cc by-sa 3.0 fr":license="CC BY-SA 3.0 FR"
    validate_license_metadata(license,field("LicenseUrl"),row.get("expected_license",license))
    url=urllib.parse.urlsplit(info["url"])
    if url.scheme!="https" or url.hostname!="upload.wikimedia.org" or info["mime"] not in MIMES or not 1024<=info["size"]<=MAX or not (field("Attribution") or field("Artist")):
        raise ValueError("source, author, type or size rejected")
    sha=info["sha1"].lower()
    if not re.fullmatch("[0-9a-f]{40}",sha):sha=format(int(sha,36),"040x")
    if not re.fullmatch("[0-9a-f]{40}",sha):raise ValueError("invalid digest")
    return license,sha,info["size"]
def main():
    p=argparse.ArgumentParser();p.add_argument("--shard",type=int,required=True);a=p.parse_args()
    if not 0<=a.shard<4:raise ValueError("invalid shard")
    rows=json.loads((ROOT/"research/video-download-priority-20261127.json").read_text(encoding="utf-8"))["records"]
    if len(rows)>48 or len({r["id"] for r in rows})!=len(rows):raise ValueError("bad inventory")
    out=ROOT/"video-review"/str(a.shard);out.mkdir(parents=True,exist_ok=True);collector.OUT=out
    report=[];seen=set();used=0
    for row in rows[a.shard::4]:
        entry={"id":row["id"],"source":row["source"],"topic_hint":row["topic_hint"],"publication":"blocked"}
        try:
            lic,sha,size=metadata(row)
            if sha in seen:raise ValueError("duplicate original")
            if used+size>BUDGET:raise ValueError("shard byte budget")
            used+=size;seen.add(sha)
            record=collector.collect({"id":row["id"],"file":row["file"],"license":lic,"reviewed_original_sha1":sha,"max_bytes":size})
            if not record["file"].endswith(".mp4"):raise ValueError("not converted video")
            entry.update(record,status="downloaded_and_decoded",topic_hint=row["topic_hint"])
        except Exception as exc:
            for suffix in (".mp4",".jpg"):(out/(row["id"]+suffix)).unlink(missing_ok=True)
            entry.update(status="rejected_or_unavailable",error=str(exc)[:240])
        report.append(entry)
        print(entry["id"],entry["status"],flush=True)
        (out/"report.json").write_text(json.dumps({"review_only":report,"attempted_bytes":used},ensure_ascii=False,indent=2),encoding="utf-8")
        time.sleep(2)
    if not any(r["status"]=="downloaded_and_decoded" for r in report):raise SystemExit("No usable video downloaded in shard")
if __name__=="__main__":main()
