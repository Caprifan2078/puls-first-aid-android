#!/usr/bin/env python3
"""Offline contact sheets for human QA. No approval, diagnosis or instruction generation."""
import argparse, concurrent.futures, hashlib, html, json, re, shutil, subprocess, tempfile, zipfile
from pathlib import Path
from review_candidate_quality import evaluate,inventory,save_csv
PREFIX="assets/media/review/"
def esc(value):return html.escape(str(value or ""),quote=True)
def run(args,timeout=45):
    return subprocess.run(args,check=True,capture_output=True,timeout=timeout)
def sample_times(duration):
    if not isinstance(duration,(float,int)) or not 0<duration<86400: return [0]
    return [round(duration*p,2) for p in (.1,.5,.85)]
def make_previews(apk,row,out):
    file=row["file"]
    if not re.fullmatch(r"[a-f0-9]{40}\.(jpg|mp4)",file):raise ValueError("invalid name")
    digest=hashlib.sha256();written=[]
    with tempfile.TemporaryDirectory() as tmp:
        source=Path(tmp)/file
        with zipfile.ZipFile(apk) as z,z.open(PREFIX+file) as src,source.open("wb") as dst:
            size=0
            while chunk:=src.read(1024*1024):
                size+=len(chunk)
                if size>35_000_000:raise ValueError("oversize media")
                digest.update(chunk);dst.write(chunk)
        if digest.hexdigest()!=row["sha256"] or size!=row["bytes"]:raise ValueError("source checksum mismatch")
        video=file.endswith(".mp4")
        duration=0
        if video:
            try:duration=float(run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",str(source)]).stdout.strip())
            except (ValueError,subprocess.SubprocessError):pass
        times=sample_times(duration) if video else [0]
        for i,at in enumerate(times):
            dest=out/f"{source.stem}-{i}.jpg"
            try:
                run(["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-y","-threads","1","-ss",str(at),"-i",str(source),"-frames:v","1","-vf","scale=320:240:force_original_aspect_ratio=decrease:force_divisible_by=2","-q:v","5","-threads","1",str(dest)])
                if not dest.is_file() or dest.stat().st_size==0:raise ValueError("empty preview")
                written.append({"path":"thumbs/"+dest.name,"at":at})
            except (ValueError,subprocess.SubprocessError):
                dest.unlink(missing_ok=True)
        return {"file":file,"duration":duration,"previews":written,"expected":len(times)}
def card(row,q,preview):
    labels=" · ".join(dict.fromkeys(x.get("ru") or x.get("en") or "" for x in row.get("labels",[])))
    pictures="".join('<figure><img loading="lazy" src="'+esc(x["path"])+'" alt="QA preview"><figcaption>'+esc(str(x["at"])+" s" if q["format"]=="video" else "Фото")+'</figcaption></figure>' for x in preview["previews"])
    if not pictures:pictures="<p>Не удалось получить превью / preview failed</p>"
    return ('<article><h2>'+esc(q["title"])+'</h2><p>'+esc(labels)+'</p><p class="flag">'+esc(q["flags"])+'</p><div class="pictures">'+pictures+'</div><p>'+esc(q["author"])+' · '+esc(q["license"])+'</p><p>'+esc(row.get("modifications"))+' '+esc(row.get("credit_line"))+' '+esc(row.get("copyright_notice"))+' '+esc(row.get("restrictions_notice"))+'</p><p>'+esc(row.get("license_url"))+'</p><p><a href="'+esc(q["source"])+'" rel="noreferrer">Оригинал (онлайн) / Source</a></p><code>'+esc(q["file"])+'</code><p>Проверка: ожидается / pending</p></article>')
def page(title,body):
    return '<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+esc(title)+'</title><style>body{font:16px system-ui,sans-serif;max-width:1050px;margin:auto;padding:18px;background:#f4f5f5;color:#152226}article{padding:16px;background:white;border:1px solid #d4dddd;border-radius:10px;margin:12px 0;overflow-wrap:anywhere}h2{font-size:18px}.pictures{display:flex;flex-wrap:wrap;gap:10px}figure{margin:0}img{max-width:320px;width:100%;height:auto}figcaption,code{font-size:12px}.flag{font-weight:600;color:#824b22}a{color:#135e74}header{padding:12px;background:#fff0dc;border-radius:8px}</style><body><h1>'+esc(title)+'</h1><header>Только для проверки. Не инструкция, не способ идентификации препаратов. Кадры видео не заменяют проверку полного ролика. Все материалы требуют медицинского и визуального подтверждения.</header>'+body+'</body></html>'
def main():
    p=argparse.ArgumentParser();p.add_argument("--apk",type=Path,required=True);p.add_argument("--out",type=Path,default=Path("visual-review"));p.add_argument("--workers",type=int,default=4);a=p.parse_args()
    if not 1<=a.workers<=6:raise ValueError("invalid worker count")
    with zipfile.ZipFile(a.apk) as z:rows=json.loads(z.read(PREFIX+"manifest.json"))["review_only"]
    targets=inventory();queue,gaps,quality=evaluate(targets,rows)
    out=a.out;out.mkdir(parents=True,exist_ok=True);thumbs=out/"thumbs";thumbs.mkdir(exist_ok=True)
    by_file={r["file"]:r for r in rows};previews={}
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:
        jobs={pool.submit(make_previews,a.apk,r,thumbs):r["file"] for r in rows}
        for f in concurrent.futures.as_completed(jobs):previews[jobs[f]]=f.result()
    sections=[];page_size=24
    for i in range(0,len(queue),page_size):
        name=f"page-{i//page_size+1:03d}.html";part=queue[i:i+page_size]
        body='<p><a href="index.html">← Все страницы</a></p>'+''.join(card(by_file[q["file"]],q,previews[q["file"]]) for q in part)
        (out/name).write_text(page(f"Материалы {i+1}–{i+len(part)}",body),encoding="utf-8")
        sections.append(f'<li><a href="{name}">{i+1}–{i+len(part)}</a> · приоритет {part[0]["priority"]}–{part[-1]["priority"]}</li>')
    missing=[f for f,r in previews.items() if not r["previews"]];partial=[f for f,r in previews.items() if 0<len(r["previews"])<r["expected"]]
    summary={"files":len(queue),"photos":sum(q["format"]=="photo" for q in queue),"videos":sum(q["format"]=="video" for q in queue),"preview_frames":sum(len(r["previews"]) for r in previews.values()),"missing_previews":missing,"partial_previews":partial,"pages":len(sections),"approved":0}
    (out/"index.html").write_text(page("PULS · визуальная проверка",f"<p>Файлы: {len(queue)} · страницы: {len(sections)} · без превью: {len(missing)}</p><p>Сначала спорные совпадения и ограничения, затем критические темы.</p><ul>"+''.join(sections)+"</ul><p><a href='review-queue.csv'>Очередь проверки</a> · <a href='missing-topics.csv'>Пробелы</a></p>"),encoding="utf-8")
    save_csv(out/"review-queue.csv",queue);save_csv(out/"missing-topics.csv",gaps)
    (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({**summary,"missing_previews":len(missing),"partial_previews":len(partial)},ensure_ascii=False),flush=True)
    if len(missing)>max(1,len(queue)//100):raise ValueError("too many unavailable previews")
if __name__=="__main__":main()
