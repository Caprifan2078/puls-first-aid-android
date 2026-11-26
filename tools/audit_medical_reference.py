#!/usr/bin/env python3
"""Validate offline record structure and optionally check reference reachability.
A successful HTTP response is NOT evidence of clinical accuracy or approval.
"""
import argparse
import concurrent.futures
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
INDEX=ROOT/"app/src/main/assets/index.html"
OUTPUT=ROOT/"medical-reference-audit.json"

def extract(html, name):
    match=re.search(r"(?m)^const "+re.escape(name)+r"=(.+);$",html)
    if not match:
        raise ValueError("missing data declaration "+name)
    return json.loads(match.group(1))

def allowed(url):
    if not isinstance(url,str):
        return False
    try:
        parsed=urllib.parse.urlsplit(url)
        host=parsed.hostname or ""
        return (parsed.scheme=="https" and parsed.username is None and
                parsed.password is None and parsed.port in (None,443) and
                (host=="nhs.uk" or host.endswith(".nhs.uk") or
                 host in {"www.resus.org.uk","resus.org.uk","www.sja.org.uk","sja.org.uk"}))
    except ValueError:
        return False

class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed(newurl):
            raise ValueError("redirect outside medical source allowlist")
        return super().redirect_request(req, fp, code, msg, headers, newurl)

def check(url):
    try:
        if not allowed(url):
            return {"status":"blocked"}
        opener=urllib.request.build_opener(SafeRedirect())
        req=urllib.request.Request(url,headers={"User-Agent":"PULS-Reference-QA/1.0 (+https://github.com/Caprifan2078/puls-first-aid-android)"})
        with opener.open(req,timeout=12) as resp:
            final=resp.geturl()
            if not allowed(final):
                return {"status":"blocked"}
            return {"status":"reachable","http":resp.status,"final":final,
                    "redirected":url.rstrip("/")!=final.rstrip("/")}
    except urllib.error.HTTPError as e:
        return {"status":"http-error","http":e.code}
    except (OSError,ValueError) as e:
        return {"status":"unverified","error":str(e)[:200]}

def audit(html):
    pages=extract(html,"PAGES"); meds=extract(html,"MEDICINES")
    details=extract(html,"MED_DETAILS"); refs=extract(html,"AID_REFERENCE")
    groups=extract(html,"MED_GROUPS")
    errors=[]; entries=[]
    pids=[x["id"] for x in pages]; mids=[x["id"] for x in meds]
    group_ids=[g[0] for g in groups]
    for kind,ids in (("guide",pids),("medicine",mids),("group",group_ids)):
        if len(set(ids))!=len(ids):errors.append("duplicate "+kind+" IDs")
        if any(not re.fullmatch(r"[a-z0-9-]+",i) for i in ids):errors.append("invalid "+kind+" ID")
    if set(details)!=set(mids):errors.append("medicine details coverage mismatch")
    if not set(refs)<=set(pids):errors.append("orphan guide reference")
    def add(kind,id,url,scope):
        if url and not allowed(url):
            errors.append("invalid source URL: "+kind+":"+id)
        entries.append({"kind":kind,"id":id,"url":url or None,"scope":scope,"clinical_review":"pending"})
    for p in pages:
        id=p["id"]; a=p.get("stepsRu"); b=p.get("stepsEn")
        if not (p.get("ru") and p.get("en") and p.get("avoidRu") and p.get("avoidEn") and
                isinstance(a,list) and isinstance(b,list) and a and len(a)==len(b) and
                all(isinstance(s,str) and s.strip() for s in a+b)):
            errors.append("invalid bilingual guide: "+id)
        add("guide",id,refs.get(id),"individual" if refs.get(id) else "missing")
    for m in meds:
        id=m["id"]; detail=details.get(id,{})
        if m.get("group") not in group_ids or not all((m.get("ru"),m.get("en"),detail.get("ru"),detail.get("en"))):
            errors.append("invalid medicine record: "+id)
        for field in ("caution","interaction"):
            if field in detail and not (isinstance(detail[field],list) and len(detail[field])==2 and all(isinstance(s,str) and s.strip() for s in detail[field])):
                errors.append("invalid bilingual "+field+": "+id)
        url=detail.get("source")
        scope=("missing" if not url else detail.get("sourceKind") if detail.get("sourceKind") in ("index","candidate") else "individual")
        add("medicine",id,url,scope)
        if detail.get("interaction"):
            url=detail.get("interactionSource")
            if not url:errors.append("missing interaction source: "+id)
            add("interaction",id,url,"individual" if url else "missing")
    return {"guides":len(pages),"medicines":len(meds),"groups":len(groups),
            "errors":errors,"entries":entries,"notice":"Structural and URL reachability checks only. Independent clinical review remains pending."}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--online",action="store_true")
    args=parser.parse_args()
    report=audit(INDEX.read_text(encoding="utf-8"))
    urls=sorted({e["url"] for e in report["entries"] if e["url"] and allowed(e["url"])})
    report["url_checks"]={}
    if args.online and not report["errors"]:
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            report["url_checks"]=dict(zip(urls,pool.map(check,urls)))
    report["summary"]={kind:{scope:sum(e["kind"]==kind and e["scope"]==scope for e in report["entries"]) for scope in ("individual","candidate","index","missing")} for kind in ("guide","medicine","interaction")}
    report["reachability_summary"]={status:sum(v["status"]==status for v in report["url_checks"].values()) for status in ("reachable","http-error","unverified","blocked")}
    for url,result in report["url_checks"].items():
        if result["status"]!="reachable" or result.get("redirected"):
            print("SOURCE",url,json.dumps(result,ensure_ascii=False))
    print("REACHABILITY",json.dumps(report["reachability_summary"]))
    OUTPUT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"guides":report["guides"],"medicines":report["medicines"],"summary":report["summary"],"errors":report["errors"],"unique_urls":len(urls),"online_checked":len(report["url_checks"])},ensure_ascii=False))
    if report["errors"]:raise SystemExit(1)
if __name__=="__main__":main()
