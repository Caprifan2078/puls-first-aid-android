#!/usr/bin/env python3
"""Find missing medicine/equipment photo candidates with exact title matching."""
import argparse,csv,re,time,urllib.error
from pathlib import Path
import mass_media_discovery as search
import collect_first_aid_review as collector
from review_candidate_quality import inventory,norm,tokens
from scale_media import load,write
ROOT=Path(__file__).resolve().parents[1]
def medicine_match(filename,name,aliases):
    hay=" "+norm(filename)+" "
    name=norm(re.sub(r"\([^)]*\)","",name))
    variants=[name]+[norm(x) for x in re.findall(r"[A-Za-z][A-Za-z0-9-]{3,}",aliases or "")]
    qualifiers={"tablet","tablets","gel","cream","solution","injection","spray","oral","inhaler","ophthalmic","topical"}
    stem=" ".join(x for x in name.split() if x not in qualifiers)
    if stem:variants.append(stem)
    return any(len(v)>=4 and (" "+v+" ") in hay for v in variants)
def run(shard,shards):
    targets=inventory();alias=load(ROOT/"media-medicine-aliases-20261127.json")
    with (ROOT/"prior-quality/missing-topics.csv").open(encoding="utf-8-sig",newline="") as f:gaps=list(csv.DictReader(f))
    gaps=[g for g in gaps if g["group"] in ("medicine","equipment") and int(g["photo_candidates"])==0]
    seen=set(load(ROOT/"step-plan/plan.json")["seen"])
    out=ROOT/"gap-review"/f"shard-{shard:02d}";dest=out/"files";dest.mkdir(parents=True,exist_ok=True);collector.OUT=dest
    records=[];fail=[];queries=[];used=0
    for g in gaps[shard::shards]:
        t=targets[g["target_id"]];name=t["en"];al=alias.get(t["id"],{}).get("aliases","")
        clean=re.sub(r"\([^)]*\)","",name).strip()
        terms=[clean,clean+" packaging"] if t["kind"]=="medicine" else [clean,clean+" first aid"]
        found=False
        for term in dict.fromkeys(terms):
            q=term+" filetype:bitmap"
            try:
                pages=search.api({"generator":"search","gsrnamespace":6,"gsrlimit":24,"gsrsearch":q,"prop":"imageinfo","iiprop":"url|mime|size|sha1|extmetadata"})
                for page in sorted(pages,key=lambda x:x.get("index",999)):
                    try:r=search.candidate(page,t,"photo",q)
                    except (ValueError,KeyError,TypeError,IndexError):continue
                    key=r["original_sha1"]
                    if key in seen or used+r["original_bytes"]>35_000_000:continue
                    if t["kind"]=="medicine" and not medicine_match(r["file"],name,al):continue
                    if t["kind"]=="equipment" and not (tokens(r["file"])&tokens(clean)):continue
                    seen.add(key);used+=r["original_bytes"]
                    try:
                        record=collector.collect({"id":"media-"+key,"file":r["file"],"license":r["license"],"reviewed_original_sha1":key})
                        record.update(matches=[{"target":t["id"],"kind":"photo","query":q}],clinical_approval=False,rights_review="pending",visual_review="pending",publication="blocked; review only")
                        records.append(record);found=True;print("DOWNLOADED",t["id"],key,flush=True);break
                    except Exception as e:
                        fail.append({"target":t["id"],"error":str(e)[:180]})
                        (dest/("media-"+key+".jpg")).unlink(missing_ok=True)
                    time.sleep(2)
            except Exception as e:
                fail.append({"target":t["id"],"error":str(e)[:180]})
                if isinstance(e,urllib.error.HTTPError) and e.code in (429,503):time.sleep(30)
            time.sleep(1.5)
            if found:break
        queries.append({"target":t["id"],"found":found})
        write(out/"download-report.json",{"review_only":records,"failed":fail,"queries":queries})
    write(out/"download-report.json",{"review_only":records,"failed":fail,"queries":queries})
    print("GAP_RESULT",len(records),len(queries),len(fail),flush=True)
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--shard",type=int,required=True);p.add_argument("--shards",type=int,default=4);a=p.parse_args()
    if not 0<=a.shard<a.shards<=8:raise ValueError("bad shard")
    run(a.shard,a.shards)
