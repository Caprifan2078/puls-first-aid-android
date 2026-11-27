#!/usr/bin/env python3
"""Large, two-phase Commons discovery. Candidates only; no clinical approval."""
import argparse,collections,json,re,time,urllib.error
from pathlib import Path
import mass_media_discovery as search
import collect_first_aid_review as collector
from review_candidate_quality import inventory,norm,tokens
from targeted_gap_media import medicine_match
from scale_media import load,write
ROOT=Path(__file__).resolve().parents[1]
search.MIMES["video"]={"video/webm","video/ogg","application/ogg","video/mp4"}
search.MAX_ORIGINAL=60_000_000
def tasklist(targets,tech):
    tasks={}
    def add(t,kind,term,role):
        term=" ".join(term.split())
        if term and len(term)<=120:
            k=(t["id"],kind,term.casefold())
            tasks[k]={"target":t["id"],"kind":kind,"term":term,"role":role,"critical":bool(t.get("critical"))}
    for t in targets.values():
        if t.get("step_binding"):continue
        name=re.sub(r"\([^)]*\)","",t["en"]).strip()
        if t["kind"]=="guide":
            add(t,"photo",name+" medical illustration","illustration")
            add(t,"photo",name+" first aid training","training")
            add(t,"video",name+" demonstration","training")
        elif t["kind"]=="medicine":add(t,"photo",name+" medication","medicine")
        elif t["kind"]=="equipment":
            add(t,"photo",name,"equipment");add(t,"video",name+" demonstration","equipment")
        elif t["kind"]=="kit":add(t,"photo",name+" first aid kit","kit")
    for q in tech:
        t=targets.get(q["target"])
        if t:
            add(t,"photo",q["term"]+" illustration","illustration")
            add(t,"video",q["term"],"training")
    return sorted(tasks.values(),key=lambda r:(r["kind"]!="video",not r["critical"],r["target"],r["term"]))
def discover(shard,shards):
    targets=inventory()
    aliases=load(ROOT/"media-medicine-aliases-20261127.json")
    tasks=tasklist(targets,load(ROOT/"technique-search-20261127.json")["queries"])[shard::shards]
    pool={};reports=[]
    out=ROOT/"mega-discovery"/f"shard-{shard:02d}"
    for task in tasks:
        t=targets[task["target"]];k=task["kind"];q=task["term"]+" filetype:"+("video" if k=="video" else "bitmap")
        accepted=0;error=""
        try:
            pages=search.api({"generator":"search","gsrnamespace":6,"gsrlimit":24,"gsrsearch":q,"prop":"imageinfo","iiprop":"url|mime|size|sha1|extmetadata"})
            for page in sorted(pages,key=lambda p:p.get("index",999)):
                try:r=search.candidate(page,t,k,q)
                except (ValueError,KeyError,TypeError,IndexError):continue
                if t["kind"]=="medicine" and not medicine_match(r["file"],t["en"],aliases.get(t["id"],{}).get("aliases","")):continue
                if t["kind"]=="equipment" and not (tokens(t["en"])&tokens(r["file"])):continue
                key=r["original_sha1"]
                row=pool.setdefault(key,{**r,"matches":[]})
                m={"target":t["id"],"kind":k,"query":q,"role":task["role"],"critical":task["critical"]}
                if m not in row["matches"]:row["matches"].append(m)
                accepted+=1
        except Exception as e:
            error=str(e)[:200]
            if isinstance(e,urllib.error.HTTPError) and e.code in (429,503):time.sleep(30)
        reports.append({"target":t["id"],"kind":k,"query":q,"accepted":accepted,"error":error})
        time.sleep(1.6)
    write(out/"discovery.json",{"queries":reports,"candidates":list(pool.values())})
    print("DISCOVERY",len(reports),len(pool),sum(bool(r["error"]) for r in reports),flush=True)
    if reports and all(r["error"] for r in reports):raise ValueError("all requests failed")
def plan():
    seen=set(load(ROOT/"step-plan/plan.json")["seen"])
    for p in (ROOT/"recent").rglob("download-report.json"):
        for r in load(p).get("review_only",[]):seen.add(r["original_sha1"])
    pool={};queries=[]
    reports=list((ROOT/"mega-metadata").rglob("discovery.json"))
    if len(reports)!=16:raise ValueError("missing discovery shards")
    for p in reports:
        report=load(p);queries+=report["queries"]
        for r in report["candidates"]:
            key=r["original_sha1"]
            if key in seen:continue
            target=pool.setdefault(key,{**r,"matches":[]})
            for m in r["matches"]:
                if m not in target["matches"]:target["matches"].append(m)
    buckets=collections.defaultdict(list)
    for r in pool.values():
        m=min(r["matches"],key=lambda m:(not m["critical"],m["target"],m["role"]))
        buckets[(r["kind"],m["target"])].append(r)
    for bucket in buckets.values():
        bucket.sort(key=lambda r:(r.get("rights_class")!="cc0-or-pd",bool(r.get("restrictions_notice")),r["original_bytes"]))
    ordered=[]
    while buckets:
        for key in sorted(buckets,key=lambda x:(x[0]!="video",x[1])):
            ordered.append(buckets[key].pop(0))
            if not buckets[key]:del buckets[key]
    # Balanced deterministic allocation, with no source SHA repeated across shards.
    shards=[[] for _ in range(16)]
    counts=collections.Counter()
    for r in ordered:
        kind=r["kind"];shards[counts[kind]%16].append(r);counts[kind]+=1
    write(ROOT/"mega-plan/plan.json",{"shards":shards,"prior_count":len(seen),"queries":len(queries),"query_errors":sum(bool(x["error"]) for x in queries),"candidates":dict(counts)})
    print("PLAN",len(seen),len(queries),dict(counts),flush=True)
def download(shard):
    plan=load(ROOT/"mega-plan/plan.json");rows=plan["shards"][shard]
    out=ROOT/"mega-review"/f"shard-{shard:02d}";dest=out/"files";dest.mkdir(parents=True,exist_ok=True);collector.OUT=dest
    cap={"photo":48,"video":22};budget={"photo":90_000_000,"video":220_000_000}
    attempts=collections.Counter();used=collections.Counter();records=[];failed=[]
    for r in rows:
        k=r["kind"]
        if attempts[k]>=cap[k] or used[k]+r["original_bytes"]>budget[k]:continue
        attempts[k]+=1;used[k]+=r["original_bytes"];key=r["original_sha1"]
        try:
            row=collector.collect({"id":"media-"+key,"file":r["file"],"license":r["license"],"reviewed_original_sha1":key,"max_bytes":r["original_bytes"]})
            row.update(matches=r["matches"],clinical_approval=False,rights_review="pending",visual_review="pending",publication="blocked; review only")
            records.append(row);print("DOWNLOADED",k,key,flush=True)
        except Exception as e:
            failed.append({"sha1":key,"error":str(e)[:200]})
            for ext in (".jpg",".mp4"):(dest/("media-"+key+ext)).unlink(missing_ok=True)
            if isinstance(e,urllib.error.HTTPError) and e.code in (429,503):time.sleep(30)
        write(out/"download-report.json",{"review_only":records,"failed":failed,"attempts":dict(attempts)})
        time.sleep(2)
    write(out/"download-report.json",{"review_only":records,"failed":failed,"attempts":dict(attempts)})
    print("RESULT",len(records),len(failed),dict(attempts),flush=True)
def summary():
    reports=list((ROOT/"mega-results").rglob("download-report.json"))
    if len(reports)!=16:raise ValueError("missing download shards")
    records={};failed=0
    for p in reports:
        data=load(p);failed+=len(data["failed"])
        for r in data["review_only"]:
            key=r["original_sha1"]
            if key in records:raise ValueError("cross-shard duplicate")
            records[key]=r
    counts=collections.Counter("photo" if r["file"].endswith(".jpg") else "video" for r in records.values())
    pairs={(m["target"],m["kind"]) for r in records.values() for m in r["matches"]}
    result={"new_unique":len(records),"formats":dict(counts),"candidate_target_format_pairs":len(pairs),"failed":failed,"bytes":sum(r["bytes"] for r in records.values()),"approved":0}
    write(ROOT/"mega-summary/summary.json",result);print(json.dumps(result),flush=True)
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("mode",choices=["discover","plan","download","summary"]);p.add_argument("--shard",type=int,default=0);a=p.parse_args()
    if not 0<=a.shard<16:raise ValueError("bad shard")
    if a.mode=="discover":discover(a.shard,16)
    elif a.mode=="plan":plan()
    elif a.mode=="download":download(a.shard)
    else:summary()
