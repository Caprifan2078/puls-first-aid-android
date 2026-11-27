#!/usr/bin/env python3
"""Build an isolated debug-only review library; never approve clinical material."""
import argparse, hashlib, json, re, shutil
from pathlib import Path
from audit_media_rights import validate_record, require

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/"app/src/debug/assets/media/review"
INPUT=ROOT/"review-input"
MAX_BYTES=1_600_000_000
MAX_FILES=1200

def sha(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f,"sha256").hexdigest()

def validate(row,source):
    require(row.get("clinical_approval") is False and row.get("visual_review")=="pending" and row.get("rights_review")=="pending","not quarantined")
    validate_record(row,"review","qa")
    require(re.fullmatch(r"[a-z0-9-]+\.(jpg|mp4)",row.get("file","")),"bad filename")
    require(source.is_file() and not source.is_symlink(),"missing file")
    require(type(row.get("bytes")) is int and 0<row["bytes"]<=35_000_000 and source.stat().st_size==row["bytes"],"size mismatch")
    require(sha(source)==row["sha256"],"hash mismatch")
    with source.open("rb") as f: head=f.read(16)
    require(head[:3]==b"\xff\xd8\xff" if source.suffix==".jpg" else head[4:8]==b"ftyp","unexpected media format")

def read_targets():
    result={}
    for path in (ROOT/"media-inventory-20261126.json",ROOT/"media-inventory-expansion-20261126.json",ROOT/"media-inventory-new-medicines-20261127.json"):
        if path.exists():
            for t in json.loads(path.read_text(encoding="utf-8"))["targets"]:
                result[t["id"]]=t
    return result

def package(root,dest,targets):
    if dest.exists():shutil.rmtree(dest)
    dest.mkdir(parents=True)
    records={}; hashes={}; rejected=[]; used=0; duplicates=0
    for report in sorted(root.rglob("*.json"),key=lambda p:("scale" in p.relative_to(root).parts,str(p))):
        if report.name not in ("download-report.json","report.json","manifest.json"):continue
        payload=json.loads(report.read_text(encoding="utf-8"))
        if not isinstance(payload,dict):continue
        for row in payload.get("review_only",[]):
            if not isinstance(row,dict):continue
            if row.get("status") and row["status"]!="downloaded_and_decoded":continue
            name=row.get("file","")
            try:
                require(isinstance(name,str) and re.fullmatch(r"[a-z0-9-]+\.(jpg|mp4)",name),"bad filename")
                source=report.parent/"files"/name
                if not source.is_file():source=report.parent/name
                validate(row,source)
                key=row["original_sha1"]
                labels=[]
                for m in row.get("matches",[]):
                    target=m.get("target","")
                    if not isinstance(target,str):continue
                    t=targets.get(target,{})
                    group=target.split(":")[0]
                    if group not in ("guide","medicine","kit","equipment"):continue
                    labels.append({"id":target,"group":group,"ru":t.get("ru",target),"en":t.get("en",target)})
                hint=row.get("topic_hint") or row.get("topic")
                if isinstance(hint,str) and hint:
                    target=targets.get("guide:"+hint,{})
                    labels.append({"id":"guide:"+hint,"group":"equipment" if hint=="equipment" else "guide","ru":target.get("ru",hint),"en":target.get("en",hint)})
                existing=key if key in records else hashes.get(row["sha256"])
                if existing:
                    duplicates+=1
                    for label in labels:
                        if label not in records[existing]["labels"]:records[existing]["labels"].append(label)
                    continue
                require(len(records)<MAX_FILES and used+row["bytes"]<=MAX_BYTES,"budget exceeded")
                output=key+source.suffix
                shutil.copyfile(source,dest/output)
                records[key]={**row,"file":output,"labels":labels,"clinical_approval":False,"rights_review":"pending","visual_review":"pending","publication":"debug-review-only"}
                hashes[row["sha256"]]=key;used+=row["bytes"]
            except (ValueError,TypeError,KeyError,OSError) as exc:
                rejected.append({"file":str(name)[:150],"reason":str(exc)[:180]})
    rows=list(records.values())
    coverage={}
    for target,t in targets.items():
        group=t["kind"];coverage.setdefault(group,{"targets":0,"photo_targets":0,"video_targets":0,"any_targets":0});coverage[group]["targets"]+=1
    by_target={}
    for row in rows:
        for label in row["labels"]:
            if label.get("id") in targets:by_target.setdefault(label["id"],set()).add("video" if row["file"].endswith(".mp4") else "photo")
    for target,kinds in by_target.items():
        stats=coverage[targets[target]["kind"]];stats["any_targets"]+=1;stats["photo_targets"]+=("photo" in kinds);stats["video_targets"]+=("video" in kinds)
    summary={"coverage":coverage,"photos":sum(r["file"].endswith(".jpg") for r in rows),"videos":sum(r["file"].endswith(".mp4") for r in rows),"bytes":used,"duplicates":duplicates,"rejected":rejected,"approved":0}
    require(not any(r["reason"]=="budget exceeded" for r in rejected),"media pack exceeds budget: do not silently discard files")
    require(summary["photos"]>=630 and summary["videos"]>=115 and len(rows)>=800,"expanded review pack incomplete")
    (dest/"manifest.json").write_text(json.dumps({"schema":1,"review_only":rows,"summary":summary},ensure_ascii=False),encoding="utf-8")
    print(json.dumps({k:v for k,v in summary.items() if k!="rejected"},ensure_ascii=False))
    return summary

def verify(root):
    manifest=root/"manifest.json"
    payload=json.loads(manifest.read_text(encoding="utf-8"))
    rows=payload["review_only"];expected={}
    originals=set(); hashes=set()
    for row in rows:
        name=row["file"];require(isinstance(name,str) and re.fullmatch(r"[a-f0-9]{40}\.(jpg|mp4)",name),"invalid packed name")
        require(name.split(".")[0]==row["original_sha1"] and row["original_sha1"] not in originals and row["sha256"] not in hashes,"duplicate media")
        validate(row,root/name)
        originals.add(row["original_sha1"]);hashes.add(row["sha256"])
        expected["assets/media/review/"+name]=row["sha256"]
    summary=payload["summary"]
    require(summary["photos"]==sum(n.endswith(".jpg") for n in expected) and summary["videos"]==sum(n.endswith(".mp4") for n in expected) and summary["approved"]==0,"incorrect coverage")
    require(summary["photos"]>=630 and summary["videos"]>=115 and len(rows)>=800,"expanded review pack incomplete")
    require({p.name for p in root.iterdir()}=={r["file"] for r in rows}|{"manifest.json"},"unexpected review files")
    expected["assets/media/review/manifest.json"]=sha(manifest)
    return expected

if __name__=="__main__":
    package(INPUT,DEST,read_targets())
    verify(DEST)
