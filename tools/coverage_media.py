#!/usr/bin/env python3
"""Target uncovered topics rather than bulk repeats. All results are review-only."""
import argparse, collections, json, re, time, urllib.error
from pathlib import Path
from scale_media import load,write
import mass_media_discovery as search
import collect_first_aid_review as collector
ROOT=Path(__file__).resolve().parents[1]
search.MIMES["video"]={"video/webm","video/ogg","application/ogg","video/mp4"}
search.MAX_ORIGINAL=50_000_000
KINDS={"guide":("photo","video"),"medicine":("photo",),"kit":("photo",),"equipment":("photo","video")}
def prepare():
    seen=set();covered=set();targets={}
    for name in ("media-inventory-20261126.json","media-inventory-expansion-20261126.json","media-inventory-new-medicines-20261127.json"):
        for t in load(ROOT/name)["targets"]:targets[t["id"]]=t
    for p in (ROOT/"previous").rglob("*.json"):
        if p.name not in ("download-report.json","report.json","manifest.json"):continue
        data=load(p)
        if not isinstance(data,dict):continue
        for row in data.get("review_only",[]):
            if row.get("status") and row["status"]!="downloaded_and_decoded":continue
            key=row.get("original_sha1","")
            if not re.fullmatch("[a-f0-9]{40}",key):continue
            seen.add(key);kind="video" if row.get("file","").endswith(".mp4") else "photo"
            for m in row.get("matches",[]):covered.add((m.get("target"),kind))
            hint=row.get("topic_hint") or row.get("topic")
            if isinstance(hint,str):covered.add(("guide:"+hint,kind))
    tasks=[]
    for t in targets.values():
        for kind in KINDS.get(t["kind"],()):
            if (t["id"],kind) not in covered:
                tasks.append({"target":t,"kind":kind})
    tasks.sort(key=lambda x:(x["kind"]!="video",not x["target"].get("critical"),x["target"]["kind"],x["target"]["id"]))
    write(ROOT/"coverage-plan/plan.json",{"seen":sorted(seen),"tasks":tasks,"covered":[list(x) for x in sorted(covered) if all(isinstance(v,str) for v in x)]})
    print("PLAN",len(seen),len(tasks),dict(collections.Counter(x["kind"] for x in tasks)),flush=True)
    if len(seen)<800:raise ValueError("Prior downloads incomplete")
def queries(t,k):
    name=re.sub(r"[^\w\s-]"," ",t["en"]).strip()
    suffix=" filetype:"+("video" if k=="video" else "bitmap")
    if t["kind"]=="medicine":return [name+" tablets packaging"+suffix,name+" medication"+suffix,name+suffix]
    if t["kind"]=="equipment":return [name+" demonstration"+suffix,name+suffix]
    if t["kind"]=="kit":return [name+" first aid kit"+suffix,name+suffix]
    hint=t.get("query_hint") or name
    return list(dict.fromkeys([hint+" first aid"+suffix,hint+" demonstration"+suffix,hint+suffix]))
def run(shard,shards):
    plan=load(ROOT/"coverage-plan/plan.json");seen=set(plan["seen"])
    tasks=plan["tasks"][shard::shards];out=ROOT/"coverage-review"/f"shard-{shard:02d}"
    files=out/"files";files.mkdir(parents=True,exist_ok=True);collector.OUT=files
    records=[];fail=[];results=[];used=collections.Counter();attempt=collections.Counter()
    caps={"photo":30,"video":15};budgets={"photo":90_000_000,"video":180_000_000}
    for task in tasks:
        t,k=task["target"],task["kind"]
        if attempt[k]>=caps[k] or used[k]>=budgets[k]:continue
        found=False;errors=[]
        for q in queries(t,k):
            try:
                pages=search.api({"generator":"search","gsrnamespace":6,"gsrlimit":12,"gsrsearch":q,"prop":"imageinfo","iiprop":"url|mime|size|sha1|extmetadata"})
                candidates=[]
                for page in sorted(pages,key=lambda p:p.get("index",999)):
                    try:r=search.candidate(page,t,k,q)
                    except (ValueError,KeyError,TypeError,IndexError):continue
                    if r["original_sha1"] not in seen:candidates.append(r)
                for r in candidates[:3]:
                    key=r["original_sha1"];size=r["original_bytes"]
                    if key in seen or attempt[k]>=caps[k] or used[k]+size>budgets[k]:continue
                    seen.add(key);attempt[k]+=1;used[k]+=size
                    try:
                        row=collector.collect({"id":"media-"+key,"file":r["file"],"license":r["license"],"reviewed_original_sha1":key,"max_bytes":size})
                        m={"target":t["id"],"kind":k,"query":q}
                        if t.get("step_binding"):m["step_binding"]=t["step_binding"]
                        row.update(matches=[m],clinical_approval=False,rights_review="pending",visual_review="pending",publication="blocked; review only")
                        records.append(row);found=True;print("DOWNLOADED",t["id"],k,key,flush=True);break
                    except Exception as e:
                        fail.append({"target":t["id"],"kind":k,"sha1":key,"error":str(e)[:200]})
                        for ext in (".jpg",".mp4"):(files/("media-"+key+ext)).unlink(missing_ok=True)
                        if isinstance(e,urllib.error.HTTPError) and e.code in (429,503):time.sleep(30)
                    time.sleep(2)
            except Exception as e:
                errors.append(str(e)[:180])
                if isinstance(e,urllib.error.HTTPError) and e.code in (429,503):time.sleep(30)
            time.sleep(1.5)
            if found:break
        results.append({"target":t["id"],"kind":k,"found":found,"search_errors":errors})
        write(out/"download-report.json",{"review_only":records,"failed":fail,"queries":results})
    write(out/"download-report.json",{"review_only":records,"failed":fail,"queries":results})
    print("RESULT",len(records),len(fail),len(results),flush=True)
def summary():
    plan=load(ROOT/"coverage-plan/plan.json");seen=set(plan["seen"]);rows={};queries=[];failed=0
    for p in (ROOT/"coverage-results").rglob("download-report.json"):
        data=load(p);queries+=data["queries"];failed+=len(data["failed"])
        for r in data["review_only"]:
            key=r["original_sha1"]
            if key not in seen:rows.setdefault(key,r)
    counts=collections.Counter("video" if r["file"].endswith(".mp4") else "photo" for r in rows.values())
    covered={(m["target"],m["kind"]) for r in rows.values() for m in r["matches"]}
    report={"new_unique":len(rows),"formats":dict(counts),"new_target_format_pairs":len(covered),"queries":len(queries),"failed_downloads":failed,"approved":0}
    write(ROOT/"coverage-summary/summary.json",report);print(json.dumps(report),flush=True)
    if not rows:raise ValueError("No new downloads")
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("mode",choices=["prepare","download","summary"]);p.add_argument("--shard",type=int,default=0);p.add_argument("--shards",type=int,default=20);a=p.parse_args()
    if a.mode=="prepare":prepare()
    elif a.mode=="summary":summary()
    else:
        if not 0<=a.shard<a.shards<=24:raise ValueError("bad shard")
        run(a.shard,a.shards)
