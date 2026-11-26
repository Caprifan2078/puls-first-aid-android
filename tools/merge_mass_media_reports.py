#!/usr/bin/env python3
"""Aggregate completed shards without promoting candidates into the application."""
import csv,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
targets=json.loads((ROOT/"media-inventory-20261126.json").read_text(encoding="utf-8"))["targets"]
out=ROOT/"mass-media-summary";out.mkdir(exist_ok=True)
queries={};candidates={};downloads={}
for path in sorted((ROOT/"mass-media-input").rglob("discovery.json")):
    data=json.loads(path.read_text(encoding="utf-8"))
    for q in data["queries"]:
        queries[(q["target"],q["kind"])]=q
    for c in data["candidates"]:
        key=c["id"]
        if key not in candidates:candidates[key]={**c,"matches":[]}
        for match in c["matches"]:
            if match not in candidates[key]["matches"]:candidates[key]["matches"].append(match)
for path in sorted((ROOT/"mass-media-input").rglob("download-report.json")):
    for d in json.loads(path.read_text(encoding="utf-8"))["review_only"]:
        downloads[d["id"]]=d
rows=[]
for t in targets:
    row={k:t[k] for k in ("id","kind","ru","en")}
    row["steps"]=len(t.get("steps",[]))
    for kind in ("photo","video"):
        q=queries.get((t["id"],kind),{})
        ids=set(q.get("candidate_ids",[]))
        row[kind+"_status"]=q.get("status","not-run")
        row[kind+"_candidates"]=len(ids)
        row[kind+"_downloaded"]=len(ids&downloads.keys())
        row[kind+"_approved"]=0
    rows.append(row)
with (out/"coverage.csv").open("w",encoding="utf-8-sig",newline="") as f:
    w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
summary={"targets":len(targets),"planned_queries":len(targets)*2,"executed_queries":len(queries),"query_errors":sum(q["status"]=="error" for q in queries.values()),"unique_candidates":len(candidates),"unique_downloaded":len(downloads),"photo_targets_with_candidates":sum(r["photo_candidates"]>0 for r in rows),"video_targets_with_candidates":sum(r["video_candidates"]>0 for r in rows),"strict_cc0_pd_candidates":sum(c["rights_class"]=="cc0-or-pd" for c in candidates.values()),"approved_for_publication":0,"step_bindings_approved":0,"notice":"Review only. Coverage refers to search candidates, not relevant or approved content."}
(out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
(out/"candidate-index.json").write_text(json.dumps(list(candidates.values()),ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(summary,ensure_ascii=False))
