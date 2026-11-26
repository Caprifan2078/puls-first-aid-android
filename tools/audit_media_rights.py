#!/usr/bin/env python3
"""Check media inventory and rights metadata; QA does not imply legal clearance."""
import argparse, datetime, hashlib, json, re, zipfile
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit
ASSETS=Path(__file__).resolve().parents[1]/"app/src/main/assets"
LICENSES={
 "CC0 1.0":"https://creativecommons.org/publicdomain/zero/1.0/",
 "CC BY 3.0":"https://creativecommons.org/licenses/by/3.0/",
 "CC BY 4.0":"https://creativecommons.org/licenses/by/4.0/",
 "CC BY-SA 3.0":"https://creativecommons.org/licenses/by-sa/3.0/",
 "CC BY-SA 4.0":"https://creativecommons.org/licenses/by-sa/4.0/",
 "CC BY-SA 3.0 FR":"https://creativecommons.org/licenses/by-sa/3.0/fr/",
 "Public domain":"https://creativecommons.org/publicdomain/mark/1.0/"
}
MEDIA_EXT={".jpg",".jpeg",".png",".webp",".gif",".svg",".avif",".bmp",".tiff",".mp4",".webm",".mov",".m4v",".mp3",".ogg",".wav",".aac",".m4a",".flac",".pdf",".ttf",".otf",".woff",".woff2"}
def require(ok,reason):
    if not ok: raise ValueError(reason)
def nonempty(v): return isinstance(v,str) and bool(v.strip())
def valid_source(s):
    if not nonempty(s):return False
    u=urlsplit(s)
    return u.scheme=="https" and u.netloc=="commons.wikimedia.org" and u.path.startswith("/wiki/File:") and not u.query and not u.fragment
def normalize_url(s):
    u=urlsplit(s)
    if u.scheme not in ("http","https") or u.netloc!="creativecommons.org" or u.query or u.fragment:return ""
    return "https://creativecommons.org"+u.path.rstrip("/").removesuffix("/deed").rstrip("/")+"/"
def validate_license_metadata(label,raw_url,expected):
    require(label==expected and label in LICENSES,"license label mismatch")
    if label=="Public domain":
        require(not raw_url or normalize_url(raw_url)==LICENSES[label],"public domain URL mismatch")
    else:
        require(normalize_url(raw_url)==LICENSES[label],"license URL missing or mismatched")
    return LICENSES[label]
def validate_record(a,category,mode):
    require(isinstance(a,dict),"manifest entry not an object")
    for key in ("id","title","author","source","license","license_url","source_license_url","modifications","sha256","original_sha256","original_sha1","reviewed_at","rights_review","visual_review"):
        require(nonempty(a.get(key)),"missing "+key)
    require(re.fullmatch("[a-z0-9-]+",a["id"]),"unsafe id")
    require(valid_source(a["source"]),"invalid source")
    require(a["license"] in LICENSES and a["license_url"]==LICENSES[a["license"]],"license mismatch")
    validate_license_metadata(a["license"],a["source_license_url"],a["license"])
    require(re.fullmatch("[a-f0-9]{64}",a["sha256"]) and re.fullmatch("[a-f0-9]{64}",a["original_sha256"]) and re.fullmatch("[a-f0-9]{40}",a["original_sha1"]),"invalid checksums")
    datetime.date.fromisoformat(a["reviewed_at"])
    if a["license"].startswith("CC BY-SA"):
        require(a.get("derivative_license")==a["license"],"ShareAlike derivative license missing")
    if category=="firstaid" or mode=="release":
        require(a.get("rights_review")=="approved" and a.get("visual_review")=="approved" and nonempty(a.get("review_ref")),"independent rights/visual review missing")
    if a["license"]=="Public domain" and mode=="release":
        require(nonempty(a.get("public_domain_basis")) and nonempty(a.get("jurisdictions")),"public domain review missing")
    if category=="firstaid":
        require(a.get("clinical_approval") is True,"clinical approval missing")
        if "step_index" in a:
            require(type(a["step_index"]) is int and a["step_index"]>=0 and nonempty(a.get("step_ru")) and nonempty(a.get("step_en")),"invalid step binding")
        require(re.fullmatch(r"[a-z0-9-]+\.(jpg|mp4)",a.get("file","")),"invalid firstaid file")
        return a["file"]
    return a["id"]+".jpg"
def audit(root,mode):
    seen=set();rows=[]
    by_topic=None
    for category in ("medicines","kits","firstaid"):
        folder=root/"media"/category
        manifest=folder/"manifest.json"
        if not manifest.exists():continue
        entries=json.loads(manifest.read_text(encoding="utf-8"))
        require(isinstance(entries,list),"manifest must be list")
        ids=set()
        for a in entries:
            name=validate_record(a,category,mode)
            if category=="firstaid":
                if by_topic is None:
                    text=(root/"index.html").read_text(encoding="utf-8")
                    match=re.search(r"const PAGES\s*=\s*",text)
                    require(match is not None,"guide database missing")
                    pages,_=json.JSONDecoder().raw_decode(text[match.end():])
                    by_topic={p["id"]:p for p in pages}
                topic=by_topic.get(a.get("topic"))
                require(topic is not None,"unknown first-aid topic")
                if "step_index" in a:
                    i=a["step_index"]
                    require(i<len(topic["stepsRu"]) and i<len(topic["stepsEn"]) and a["step_ru"]==topic["stepsRu"][i] and a["step_en"]==topic["stepsEn"][i],"reviewed step text changed")
            require(a["id"] not in ids,"duplicate id "+a["id"])
            ids.add(a["id"])
            path=folder/name
            require(path.is_file() and not path.is_symlink(),"missing or symlink "+str(path))
            data=path.read_bytes()
            require(hashlib.sha256(data).hexdigest()==a["sha256"] and len(data)==a.get("bytes"),"checksum/size mismatch "+str(path))
            relative=path.relative_to(root).as_posix()
            require(relative not in seen,"duplicate file")
            seen.add(relative)
            rows.append({**a,"asset":relative,"category":category})
    actual={p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and p.suffix.lower() in MEDIA_EXT}
    require(actual==seen,"unregistered assets: "+", ".join(sorted(actual-seen))+"; missing assets: "+", ".join(sorted(seen-actual)))
    return sorted(rows,key=lambda a:a["asset"])
def verify_apk(apk,root,rows):
    expected={"assets/"+a["asset"]:a["sha256"] for a in rows}
    expected["assets/media/credits.json"]=hashlib.sha256((root/"media/credits.json").read_bytes()).hexdigest()
    with zipfile.ZipFile(apk) as z:
        names=z.namelist()
        require(len(names)==len(set(names)),"duplicate APK entries")
        found={n for n in names if n.startswith("assets/") and PurePosixPath(n).suffix.lower() in MEDIA_EXT}
        require(found==set(expected)-{"assets/media/credits.json"},"APK contains unregistered media")
        for name,digest in expected.items():require(hashlib.sha256(z.read(name)).hexdigest()==digest,"APK digest mismatch "+name)
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--mode",choices=["qa","release"],required=True)
    p.add_argument("--apk",type=Path)
    args=p.parse_args()
    if args.mode=="release":
        approval=ASSETS.parents[3]/"release-review.json"
        require(approval.is_file(),"production release blocked: independent review record missing")
        review=json.loads(approval.read_text(encoding="utf-8"))
        for key in ("copyright_review_ref","medical_review_ref","trademark_privacy_review_ref"):
            require(nonempty(review.get(key)),"production release blocked: "+key)
        require(review.get("approved") is True,"production release not approved")
    rows=audit(ASSETS,args.mode)
    credits=ASSETS/"media/credits.json"
    if args.apk:verify_apk(args.apk,ASSETS,rows)
    else:
        credits.parent.mkdir(parents=True,exist_ok=True)
        credits.write_text(json.dumps({"mode":args.mode,"items":rows},ensure_ascii=False,indent=2),encoding="utf-8")
    print("PASS:",len(rows),"registered media; mode",args.mode)
if __name__=="__main__":main()
