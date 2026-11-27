#!/usr/bin/env python3
"""Reuse old search metadata, discover missing medicines, download only into review quarantine."""
import argparse, collections, hashlib, json, re, time, urllib.error
from pathlib import Path
from mass_media_discovery import discover, candidate, api
import collect_first_aid_review as collector
from audit_media_rights import LICENSES
ROOT=Path(__file__).resolve().parents[1]
def load(p):return json.loads(p.read_text(encoding="utf-8"))
def write(p,obj):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding="utf-8")
def prepare():
    root=ROOT/"previous"
    seen=set();covered=set();pool={}
    for path in root.rglob("*.json"):
        if path.name not in ("download-report.json","report.json","manifest.json","discovery.json"):continue
        data=load(path)
        if not isinstance(data,dict):continue
        for row in data.get("review_only",[]):
            if row.get("status") and row["status"]!="downloaded_and_decoded":continue
            key=row.get("original_sha1","")
            if not re.fullmatch("[a-f0-9]{40}",key):continue
            seen.add(key)
            for m in row.get("matches",[]):covered.add((m.get("target"),m.get("kind")))
        for row in data.get("candidates",[]):
            key=row.get("original_sha1","")
            if not re.fullmatch("[a-f0-9]{40}",key) or row.get("license") not in LICENSES:continue
            entry=pool.setdefault(key,{**row,"matches":[]})
            for m in row.get("matches",[]):
                if m not in entry["matches"]:entry["matches"].append(m)
    targets={}
    for p in (ROOT/"media-inventory-20261126.json",ROOT/"media-inventory-new-medicines-20261127.json"):
        for t in load(p)["targets"]:targets[t["id"]]=t
    remaining=[r for k,r in pool.items() if k not in seen]
    # assign each previous candidate exactly once. New search candidates may overlap between workers.
    write(ROOT/"scale-plan/plan.json",{"seen":sorted(seen),"covered":sorted([list(x) for x in covered if all(isinstance(v,str) for v in x)]),"candidates":remaining,"targets":list(targets.values())})
    print("PREPARED",len(seen),"previous originals;",len(remaining),"new metadata candidates;",len(targets),"targets")
    if not remaining or not seen:raise SystemExit("Previous artifacts not available")
def run(shard,shards):
    p=load(ROOT/"scale-plan/plan.json");seen=set(p["seen"]);covered={tuple(x) for x in p["covered"]}
    targets={t["id"]:t for t in p["targets"]}
    pool={r["original_sha1"]:r for r in p["candidates"] if int(r["original_sha1"][:8],16)%shards==shard}
    # All medicine names lacking a previous photo: broaden the query with package/tablet terms.
    fresh=[t for t in targets.values() if t["kind"]=="medicine" and (t["id"],"photo") not in covered][shard::shards]
    for t in fresh:
        try:
            query=t["en"]+" medication packaging filetype:bitmap"
            pages=api({"generator":"search","gsrnamespace":6,"gsrlimit":12,"gsrsearch":query,"prop":"imageinfo","iiprop":"url|mime|size|sha1|extmetadata"})
            found=0
            for page in sorted(pages,key=lambda v:v.get("index",999)):
                try:r=candidate(page,t,"photo",query)
                except (ValueError,KeyError,IndexError,TypeError):continue
                key=r["original_sha1"]
                if key in seen:continue
                item=pool.setdefault(key,{**r,"matches":[]})
                m={"target":t["id"],"kind":"photo","query":query}
                if m not in item["matches"]:item["matches"].append(m)
                found+=1
                if found>=5:break
            print("SEARCH",t["id"],found,flush=True)
        except Exception as e:
            print("SEARCH ERROR",t["id"],str(e)[:180],flush=True)
            if isinstance(e,urllib.error.HTTPError) and e.code in (429,503):time.sleep(30)
        time.sleep(1.5)
    out=ROOT/"scale-media-review"/f"shard-{shard:02d}";files=out/"files";files.mkdir(parents=True,exist_ok=True);collector.OUT=files
    write(out/"discovery.json",{"candidates":list(pool.values())})
    counts=collections.Counter();used=collections.Counter();attempted=collections.Counter();chosen=[];failed=[]
    def rank(r):
        m=r.get("matches",[])
        return (not any((x.get("target"),x.get("kind")) not in covered for x in m),not any(targets.get(x.get("target"),{}).get("critical") for x in m),r.get("rights_class")!="cc0-or-pd",r["original_bytes"])
    groups=collections.defaultdict(list)
    for r in sorted(pool.values(),key=rank):
        if r.get("kind") in ("photo","video"):
            groups[(r["kind"],r["target"].split(":")[0])].append(r)
    # Prefer diverse targets, then additional variants; independent caps for images/videos.
    per_target=collections.Counter()
    while any(groups.values()):
        progressed=False
        for group,rows in sorted(groups.items()):
            kind=group[0];cap=40 if kind=="photo" else 12
            budget=80_000_000 if kind=="photo" else 90_000_000
            if attempted[kind]>=cap or used[kind]>=budget:rows.clear();continue
            if not rows:continue
            idx=min(range(len(rows)),key=lambda i:(per_target[rows[i]["target"]],rank(rows[i])))
            r=rows.pop(idx);progressed=True
            key=r["original_sha1"];size=r["original_bytes"]
            if key in seen or used[kind]+size>budget:continue
            seen.add(key);attempted[kind]+=1;used[kind]+=size
            try:
                row=collector.collect({"id":"media-"+key,"file":r["file"],"license":r["license"],"reviewed_original_sha1":key})
                row.update(matches=r["matches"],rights_class=r["rights_class"],clinical_approval=False,rights_review="pending",visual_review="pending",publication="blocked; review only")
                chosen.append(row);counts[kind]+=1;per_target[r["target"]]+=1
                for m in r["matches"]:covered.add((m.get("target"),m.get("kind")))
                print("DOWNLOADED",kind,key,flush=True)
            except Exception as e:
                failed.append({"id":key,"error":str(e)[:240]})
                for ext in (".jpg",".mp4"):(files/("media-"+key+ext)).unlink(missing_ok=True)
                if isinstance(e,urllib.error.HTTPError) and e.code in (429,503):time.sleep(30)
            write(out/"download-report.json",{"review_only":chosen,"failed":failed,"attempted":dict(attempted),"downloaded":dict(counts)})
            time.sleep(2)
        if not progressed:break
    write(out/"download-report.json",{"review_only":chosen,"failed":failed,"attempted":dict(attempted),"downloaded":dict(counts)})
    print("SUMMARY",dict(counts),len(failed),flush=True)
def summarize():
    rows={};duplicates=0;failed=0
    for p in (ROOT/"scale-results").rglob("download-report.json"):
        data=load(p);failed+=len(data.get("failed",[]))
        for row in data.get("review_only",[]):
            key=row["original_sha1"]
            if key in rows:duplicates+=1
            else:rows[key]=row
    result={"unique":len(rows),"photos":sum(r["file"].endswith(".jpg") for r in rows.values()),"videos":sum(r["file"].endswith(".mp4") for r in rows.values()),"duplicates":duplicates,"failed":failed,"approved":0}
    write(ROOT/"scale-summary/summary.json",result);print(json.dumps(result))
    if not rows:raise SystemExit("No downloaded candidates")
if __name__=="__main__":
    a=argparse.ArgumentParser();a.add_argument("mode",choices=["prepare","download","summary"]);a.add_argument("--shard",type=int,default=0);a.add_argument("--shards",type=int,default=16);args=a.parse_args()
    if args.mode=="prepare":prepare()
    elif args.mode=="summary":summarize()
    else:
        if not 0<=args.shard<args.shards<=24:raise ValueError("invalid shard")
        run(args.shard,args.shards)
