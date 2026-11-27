#!/usr/bin/env python3
"""Small technique vocabulary pilot. Search associations only; no clinical approvals."""
import argparse, collections, json, time, urllib.error
from pathlib import Path
import mass_media_discovery as search
import collect_first_aid_review as collector
from scale_media import load,write
ROOT=Path(__file__).resolve().parents[1]
search.MIMES["video"]={"video/webm","video/ogg","application/ogg","video/mp4"}
search.MAX_ORIGINAL=50_000_000
def queries(rows):
    return [(r,k) for r in rows for k in ("video","photo")]
def run(shard,shards):
    plan=load(ROOT/"step-plan/plan.json")
    known=set(plan["seen"]);seen=set(known)
    rows=load(ROOT/"technique-search-20261127.json")["queries"]
    tasks=queries(rows)[shard::shards]
    out=ROOT/"technique-review"/f"shard-{shard:02d}";files=out/"files";files.mkdir(parents=True,exist_ok=True);collector.OUT=files
    records=[];results=[];failed=[];used=collections.Counter();counts=collections.Counter()
    for row,kind in tasks:
        q=row["term"]+" filetype:"+("video" if kind=="video" else "bitmap")
        found=0;old=0;accepted=0;errors=[]
        try:
            pages=search.api({"generator":"search","gsrnamespace":6,"gsrlimit":30,"gsrsearch":q,"prop":"imageinfo","iiprop":"url|mime|size|sha1|extmetadata"})
            for page in sorted(pages,key=lambda x:x.get("index",999)):
                try:r=search.candidate(page,{"id":row["target"],"kind":"guide","en":row["term"]},kind,q)
                except (ValueError,KeyError,TypeError,IndexError):continue
                accepted+=1
                key=r["original_sha1"]
                if key in seen:old+=1;continue
                if found>=2 or counts[kind]>=(20 if kind=="video" else 30) or used[kind]+r["original_bytes"]>(160_000_000 if kind=="video" else 50_000_000):continue
                seen.add(key);used[kind]+=r["original_bytes"];counts[kind]+=1
                try:
                    record=collector.collect({"id":"media-"+key,"file":r["file"],"license":r["license"],"reviewed_original_sha1":key,"max_bytes":r["original_bytes"]})
                    record.update(matches=[{"target":row["target"],"kind":kind,"query":q}],clinical_approval=False,rights_review="pending",visual_review="pending",publication="blocked; review only")
                    records.append(record);found+=1
                    print("DOWNLOADED",row["target"],kind,key,flush=True)
                except Exception as e:
                    failed.append({"target":row["target"],"kind":kind,"sha1":key,"error":str(e)[:180]})
                    for ext in (".jpg",".mp4"):(files/("media-"+key+ext)).unlink(missing_ok=True)
                    if isinstance(e,urllib.error.HTTPError) and e.code in (429,503):time.sleep(30)
                time.sleep(2)
        except Exception as e:
            errors.append(str(e)[:180])
            if isinstance(e,urllib.error.HTTPError) and e.code in (429,503):time.sleep(30)
        results.append({"query":q,"target":row["target"],"kind":kind,"accepted_metadata":accepted,"known_matches":old,"new_files":found,"search_errors":errors})
        write(out/"download-report.json",{"review_only":records,"failed":failed,"queries":results})
        time.sleep(1.5)
    print("PILOT",len(records),len(failed),len(results),flush=True)
def summary():
    rows={};queries=[];failed=0
    for p in (ROOT/"technique-results").rglob("download-report.json"):
        data=load(p);queries+=data["queries"];failed+=len(data["failed"])
        for r in data["review_only"]:rows.setdefault(r["original_sha1"],r)
    report={"new_unique":len(rows),"formats":dict(collections.Counter("video" if r["file"].endswith(".mp4") else "photo" for r in rows.values())),"queries":len(queries),"accepted_metadata":sum(q["accepted_metadata"] for q in queries),"known_matches":sum(q["known_matches"] for q in queries),"search_errors":sum(bool(q["search_errors"]) for q in queries),"failed_downloads":failed,"approved":0}
    write(ROOT/"technique-summary/summary.json",report);print(json.dumps(report),flush=True)
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("mode",choices=["download","summary"]);p.add_argument("--shard",type=int,default=0);p.add_argument("--shards",type=int,default=4);a=p.parse_args()
    if a.mode=="summary":summary()
    else:
        if not 0<=a.shard<a.shards<=8:raise ValueError("bad shard")
        run(a.shard,a.shards)
