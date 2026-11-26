#!/usr/bin/env python3
"""Mass media discovery and bounded quarantine; never write to app assets."""
import argparse, csv, hashlib, json, re, time, urllib.parse, urllib.error
from pathlib import Path
from collect_ui_medicine_photos import get, plain, normalize_license
from audit_media_rights import LICENSES, validate_license_metadata
import collect_first_aid_review as quarantine

ROOT=Path(__file__).resolve().parents[1]
INVENTORY=ROOT/"media-inventory-20261126.json"
API="https://commons.wikimedia.org/w/api.php"
MIMES={"photo":{"image/jpeg","image/png"},"video":{"video/webm"}}
MAX_ORIGINAL=25_000_000

def tasks(targets):
    return [(r,kind) for r in targets for kind in ("photo","video")]

def search_query(target,kind):
    # No medical instructions are inferred from the search result.
    name=re.sub(r'[^\w\s-]',' ',target["en"]).strip()
    if target["kind"]=="guide":
        name += " first aid"
    elif target["kind"]=="kit":
        name += " first aid supplies"
    elif target["kind"]=="equipment":
        name += " first aid"
    return " ".join(name.split())+" filetype:"+("bitmap" if kind=="photo" else "video")

def api(params):
    data=json.loads(get(API+"?"+urllib.parse.urlencode({"action":"query","format":"json","formatversion":2,"maxlag":5,**params}),3_000_000))
    if "error" in data:
        raise ValueError("API "+str(data["error"].get("code","unknown")))
    return data.get("query",{}).get("pages",[])

def candidate(page,target,kind,query):
    info=page["imageinfo"][0]
    meta=info.get("extmetadata",{})
    field=lambda k:plain(meta.get(k,{}).get("value",""))
    lic=normalize_license(field("LicenseShortName"))
    if lic.lower()=="cc by-sa 3.0 fr": lic="CC BY-SA 3.0 FR"
    if lic not in LICENSES: raise ValueError("unsupported license")
    # Strictly verify source-declared license; no guessing from search snippets.
    validate_license_metadata(lic,field("LicenseUrl"),lic)
    author=field("Attribution") or field("Artist")
    url=urllib.parse.urlsplit(info["url"])
    if not author or url.scheme!="https" or url.hostname!="upload.wikimedia.org" or info["mime"] not in MIMES[kind] or not 1024<=info["size"]<=MAX_ORIGINAL:
        raise ValueError("author, URL, MIME or size rejected")
    sha=info["sha1"].lower()
    if not re.fullmatch("[0-9a-f]{40}",sha): sha=format(int(sha,36),"040x")
    if not re.fullmatch("[0-9a-f]{40}",sha): raise ValueError("bad digest")
    title=page["title"]
    if not title.startswith("File:"): raise ValueError("not a file")
    return {"id":"media-"+sha,"file":title[5:],"license":lic,"source":"https://commons.wikimedia.org/wiki/File:"+urllib.parse.quote(title[5:].replace(" ","_"),safe=""),"author":author,"source_license_url":field("LicenseUrl"),"rights_class":"cc0-or-pd" if lic in ("CC0 1.0","Public domain") else "attribution-required","original_sha1":sha,"original_bytes":info["size"],"mime":info["mime"],"target":target["id"],"kind":kind,"query":query,"rights_review":"pending","visual_review":"pending","clinical_approval":False,"restrictions_notice":field("Restrictions"),"copyright_notice":field("CopyrightNotice")}

def discover(target,kind):
    query=search_query(target,kind)
    pages=api({"generator":"search","gsrnamespace":6,"gsrlimit":8,"gsrsearch":query,"prop":"imageinfo","iiprop":"url|mime|size|sha1|extmetadata"})
    found=[]; rejected=0
    for p in sorted(pages,key=lambda x:x.get("index",999)):
        try: found.append(candidate(p,target,kind,query))
        except (ValueError,KeyError,IndexError,TypeError): rejected+=1
    found.sort(key=lambda x:x["rights_class"]!="cc0-or-pd")
    return found[:4],rejected

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--inventory",type=Path,default=INVENTORY)
    a.add_argument("--shard",type=int,required=True)
    a.add_argument("--shards",type=int,default=12)
    a.add_argument("--download-cap",type=int,default=8)
    a.add_argument("--byte-budget",type=int,default=60_000_000)
    a.add_argument("--limit",type=int,default=0,help="Optional small smoke-test limit")
    args=a.parse_args()
    if not 0<=args.shard<args.shards<=24 or not 0<=args.download_cap<=20 or not 0<=args.byte_budget<=100_000_000: raise ValueError("invalid bounds")
    out=ROOT/"mass-media-review"/f"shard-{args.shard:02d}"
    out.mkdir(parents=True,exist_ok=True)
    files=out/"files";files.mkdir(exist_ok=True);quarantine.OUT=files
    targets=json.loads(args.inventory.read_text(encoding="utf-8"))["targets"]
    todo=tasks(targets)[args.shard::args.shards]
    if args.limit: todo=todo[:args.limit]
    report=[]; pool={}
    for target,kind in todo:
        row={"target":target["id"],"kind":kind,"query":search_query(target,kind),"status":"pending","candidate_ids":[]}
        try:
            found,rejected=discover(target,kind)
            row.update(status="found" if found else "no-compatible-result",rejected=rejected,candidate_ids=[x["id"] for x in found])
            for item in found:
                key=item["id"]
                if key not in pool: pool[key]={**item,"matches":[]}
                pool[key]["matches"].append({"target":target["id"],"kind":kind,"query":item["query"]})
        except Exception as e:
            row.update(status="error",error=str(e)[:300])
            if isinstance(e,urllib.error.HTTPError) and e.code in (429,503):time.sleep(20)
        report.append(row)
        print(row["status"],target["id"],kind,len(row["candidate_ids"]),flush=True)
        time.sleep(1.3)
    # Save metadata before optional downloads. Prioritize critical guides, then other types fairly.
    (out/"discovery.json").write_text(json.dumps({"queries":report,"candidates":list(pool.values())},ensure_ascii=False,indent=2),encoding="utf-8")
    critical={r["id"] for r in targets if r.get("critical")}
    chosen=[];failed=[];used=0;attempts=0
    def rank(x):
        return (not any(m["target"] in critical for m in x["matches"]),x["rights_class"]!="cc0-or-pd",x["original_bytes"])
    buckets={k:[] for k in ("guide","medicine","kit","equipment")}
    for x in sorted(pool.values(),key=rank):buckets[x["target"].split(":")[0]].append(x)
    ordered=[]
    while any(buckets.values()):
        for k in buckets:
            if buckets[k]:ordered.append(buckets[k].pop(0))
    for x in ordered:
        if attempts>=args.download_cap:break
        if used+x["original_bytes"]>args.byte_budget:continue
        attempts+=1;used+=x["original_bytes"]
        try:
            row=quarantine.collect({"id":x["id"],"file":x["file"],"license":x["license"],"reviewed_original_sha1":x["original_sha1"]})
            row.update(matches=x["matches"],rights_class=x["rights_class"],clinical_approval=False,visual_review="pending",rights_review="pending",publication="blocked; review only")
            chosen.append(row);print("QUARANTINED",x["id"],flush=True)
        except Exception as e:
            failed.append({"id":x["id"],"error":str(e)[:300]})
            for ext in ("jpg","mp4"):(files/(x["id"]+"."+ext)).unlink(missing_ok=True)
        time.sleep(2)
    (out/"download-report.json").write_text(json.dumps({"review_only":chosen,"failed":failed,"attempted_original_bytes":used},ensure_ascii=False,indent=2),encoding="utf-8")
    print("SUMMARY",len(report),"queries",len(pool),"unique metadata candidates",len(chosen),"downloaded review files",flush=True)
    if report and all(r["status"]=="error" for r in report):raise SystemExit("all discovery requests failed")
if __name__=="__main__":main()
