#!/usr/bin/env python3
"""Produce a review queue and gap matrix from the actual packaged media.
Search matches are not a verified depiction, indication or clinical approval.
"""
import argparse,csv,json,re,unicodedata,zipfile
from collections import Counter,defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def norm(value):
    return " ".join(re.findall(r"[^\W_]+",unicodedata.normalize("NFKC",str(value or "")).casefold(),re.UNICODE))
def tokens(value):
    return {w for w in norm(value).split() if len(w)>=3 and w not in {"the","and","first","aid","step","possible","suspected","with","for","from","training","demonstration"}}
def inventory():
    targets={}
    for name in ("media-inventory-20261126.json","media-inventory-expansion-20261126.json","media-inventory-new-medicines-20261127.json","media-inventory-remaining-steps-20261127.json"):
        for t in json.loads((ROOT/name).read_text(encoding="utf-8"))["targets"]:targets[t["id"]]=t
    return targets
def group(t):return "guide_step" if t.get("step_binding") else t["kind"]
def evaluate(targets,rows):
    queue=[];mapping=defaultdict(set);stats=Counter();seen=set()
    for row in rows:
        key=row["original_sha1"];file=row["file"]
        if key in seen or not re.fullmatch(r"[a-f0-9]{40}\.(jpg|mp4)",file) or not file.startswith(key+"."):
            raise ValueError("unexpected duplicate or filename")
        if row.get("clinical_approval") is not False or row.get("rights_review")!="pending" or row.get("visual_review")!="pending":
            raise ValueError("review status inconsistent")
        seen.add(key);kind="photo" if file.endswith(".jpg") else "video"
        ids={x.get("id") for x in row.get("labels",[]) if x.get("id") in targets}
        parents={targets[t].get("step_binding",{}).get("topic",t) for t in ids}
        drug_ids={t for t in ids if targets[t]["kind"]=="medicine"}
        title=norm(row.get("title",""));title_tokens=tokens(title)
        flags=[]
        if not ids:flags.append("no-known-target")
        if len(drug_ids)>1:flags.append("multiple-drug-identities")
        if len(parents)>3:flags.append("many-topic-associations")
        if row.get("restrictions_notice"):flags.append("restrictions-notice")
        overlap=False
        for tid in sorted(ids):
            t=targets[tid];mapping[(tid,kind)].add(key)
            if tokens(t.get("en"))&title_tokens or tokens(t.get("query_hint"))&title_tokens:overlap=True
        if ids and not overlap:flags.append("no-title-token-match")
        if drug_ids:flags.append("never-identify-by-appearance")
        priority=0 if any(x in flags for x in ("multiple-drug-identities","many-topic-associations","restrictions-notice")) else 1 if any(targets[t].get("critical") for t in ids) else 2
        for flag in flags:stats[flag]+=1
        queue.append({"priority":priority,"file":file,"format":kind,"title":row.get("title",""),"author":row.get("author",""),"license":row.get("license",""),"source":row.get("source",""),"target_ids":" | ".join(sorted(ids)),"flags":" | ".join(flags),"review_status":"pending","clinical_approval":"false"})
    gaps=[]
    for tid,t in sorted(targets.items()):
        photo=len(mapping[(tid,"photo")]);video=len(mapping[(tid,"video")])
        gaps.append({"target_id":tid,"group":group(t),"ru":t["ru"],"en":t["en"],"critical":bool(t.get("critical")),"photo_candidates":photo,"video_candidates":video,"approved":0})
    queue.sort(key=lambda x:(x["priority"],x["file"]))
    gaps.sort(key=lambda x:(not x["critical"],x["photo_candidates"]+x["video_candidates"],x["target_id"]))
    counts={}
    for g in gaps:
        s=counts.setdefault(g["group"],{"targets":0,"without_photo":0,"without_video":0,"without_either":0})
        s["targets"]+=1;s["without_photo"]+=g["photo_candidates"]==0;s["without_video"]+=g["video_candidates"]==0;s["without_either"]+=g["photo_candidates"]==0 and g["video_candidates"]==0
    return queue,gaps,{"files":len(queue),"flags":dict(stats),"groups":counts,"approved":0}
def save_csv(path,rows):
    # Spreadsheet formula injection guard for Wikimedia-supplied metadata.
    def safe(value):
        if isinstance(value,str) and value.lstrip().startswith(("=","+","-","@")):return "'"+value
        return value
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        if not rows:return
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader()
        writer.writerows({k:safe(v) for k,v in r.items()} for r in rows)
def main():
    p=argparse.ArgumentParser();p.add_argument("--apk",type=Path,required=True);p.add_argument("--out",type=Path,default=Path("review-quality"));args=p.parse_args()
    with zipfile.ZipFile(args.apk) as z:rows=json.loads(z.read("assets/media/review/manifest.json"))["review_only"]
    targets=inventory()
    if sum(bool(t.get("step_binding")) for t in targets.values())!=501:raise ValueError("step inventory incomplete")
    queue,gaps,summary=evaluate(targets,rows)
    args.out.mkdir(parents=True,exist_ok=True)
    save_csv(args.out/"review-queue.csv",queue);save_csv(args.out/"missing-topics.csv",gaps)
    (args.out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False))
if __name__=="__main__":main()
