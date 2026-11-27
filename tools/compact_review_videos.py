#!/usr/bin/env python3
"""Compact QA derivatives without deleting files or changing clinical approval."""
import hashlib,json,math,subprocess,tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
def run(args,timeout=600):
    return subprocess.run(args,check=True,capture_output=True,timeout=timeout)
def digest(path):
    with path.open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()
def probe(path):
    info=json.loads(run(["ffprobe","-v","error","-show_streams","-show_format","-of","json",str(path)]).stdout)
    duration=float(info["format"]["duration"])
    if not math.isfinite(duration) or duration<=0:raise ValueError("invalid duration")
    video=next(s for s in info["streams"] if s["codec_type"]=="video")
    return duration,any(s["codec_type"]=="audio" for s in info["streams"]),int(video["width"]),int(video["height"])
def compact_one(path,row,target):
    old=path.stat().st_size
    if old<=target or not path.suffix==".mp4":return None
    duration,audio,width,height=probe(path)
    # Never truncate. Prefer the original size when a useful bitrate cannot fit.
    rate=int(target*8/duration*.94)-(64_000 if audio else 0)
    if rate<160_000:return None
    with tempfile.TemporaryDirectory(dir=path.parent) as d:
        tmp=Path(d)/"compact.mp4"
        cmd=["ffmpeg","-nostdin","-v","error","-y","-threads","1","-i",str(path),"-map","0:v:0","-map","0:a?","-map_metadata","-1","-map_chapters","-1"]
        if max(width,height)>960 or min(width,height)>540:
            cmd+=["-vf","scale=960:960:force_original_aspect_ratio=decrease:force_divisible_by=2"]
        cmd+=["-c:v","libx264","-preset","fast","-threads","2","-pix_fmt","yuv420p","-b:v",str(rate),"-maxrate",str(rate),"-bufsize",str(rate*2),"-c:a","aac","-b:a","64k","-movflags","+faststart",str(tmp)]
        run(cmd)
        after,after_audio,w,h=probe(tmp)
        if abs(after-duration)>max(0.6,duration*.01) or after_audio!=audio:
            raise ValueError("duration/audio mismatch")
        if tmp.stat().st_size>=old:return None
        run(["ffmpeg","-nostdin","-v","error","-xerror","-threads","1","-i",str(tmp),"-f","null","-"])
        before_hash=row["sha256"];after_hash=digest(tmp);size=tmp.stat().st_size
        tmp.replace(path)
        row.update(sha256=after_hash,bytes=size,modifications=row["modifications"]+"; QA offline copy additionally bitrate/resolution optimized; full duration retained",compacted_from_sha256=before_hash)
        return {"file":path.name,"before_bytes":old,"after_bytes":size,"before_sha256":before_hash,"after_sha256":after_hash,"duration":duration,"width":w,"height":h}
def compact_to_budget(rows,dest,budget):
    before=sum(r["bytes"] for r in rows);result=[]
    if before<=budget:return {"before_bytes":before,"after_bytes":before,"changes":[]}
    # Two bounded passes, no dropping, never modify the input source reports.
    for passno in range(2):
        total=sum(r["bytes"] for r in rows)
        if total<=budget:break
        images=sum(r["bytes"] for r in rows if r["file"].endswith(".jpg"))
        videos=[r for r in rows if r["file"].endswith(".mp4")]
        if not videos or images>=budget:raise ValueError("photos alone exceed budget")
        factor=max(.2,min(.94,(budget-images)/(total-images)*.91))
        tasks=[(dest/r["file"],r,max(1,int(r["bytes"]*factor))) for r in videos if r["bytes"]>700_000]
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(compact_one,*t) for t in tasks]
            for f in futures:
                r=f.result()
                if r:result.append(r)
    after=sum(r["bytes"] for r in rows)
    if len({r["sha256"] for r in rows})!=len(rows):raise ValueError("compaction created duplicate derivatives")
    return {"before_bytes":before,"after_bytes":after,"changes":result}
