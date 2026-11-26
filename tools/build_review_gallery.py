#!/usr/bin/env python3
"""Build offline review gallery from downloaded artifacts, never modify app assets."""
import hashlib,html,json,re,shutil,csv
from pathlib import Path
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parents[1]
INPUT=ROOT/"review-input"
OUT=ROOT/"review-gallery"
def e(v):return html.escape(str(v or ""),quote=True)
def valid_url(v):
    u=urlsplit(v or "")
    return u.scheme=="https" and u.netloc=="commons.wikimedia.org" and u.path.startswith("/wiki/File:")
def digest(p):
    with p.open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()
def main():
    OUT.mkdir(exist_ok=True); dest=OUT/"files";dest.mkdir(exist_ok=True)
    targets={}
    for path in (ROOT/"media-inventory-20261126.json",ROOT/"media-inventory-expansion-20261126.json"):
        for t in json.loads(path.read_text(encoding="utf-8"))["targets"]:targets[t["id"]]=t
    records={};rejected=[]
    for path in sorted(INPUT.rglob("download-report.json")):
        for row in json.loads(path.read_text(encoding="utf-8"))["review_only"]:
            name=row.get("file","");sha=row.get("sha256","");original=row.get("original_sha1","")
            try:
                if not re.fullmatch(r"[a-z0-9-]+\.(jpg|mp4)",name) or not re.fullmatch("[a-f0-9]{64}",sha) or not re.fullmatch("[a-f0-9]{40}",original):raise ValueError("invalid path or hash")
                if not valid_url(row.get("source")):raise ValueError("invalid source")
                source=path.parent/"files"/name
                if not source.is_file() or source.is_symlink() or digest(source)!=sha or source.stat().st_size!=row["bytes"]:raise ValueError("file missing or checksum mismatch")
                matches=[m for m in row.get("matches",[]) if m.get("target") in targets]
                if not matches:raise ValueError("no known targets")
                if original not in records:
                    file=original+source.suffix
                    shutil.copyfile(source,dest/file)
                    records[original]={**row,"file":file,"matches":[]}
                item=records[original]
                for m in matches:
                    if m not in item["matches"]:item["matches"].append(m)
            except (ValueError,KeyError,OSError) as exc:rejected.append({"file":name,"error":str(exc)})
    rows=list(records.values())
    cards=[]
    for row in rows:
        name=row["file"];kind="video" if name.endswith(".mp4") else "photo"
        labels=[targets[m["target"]] for m in row["matches"]]
        groups=" ".join(sorted(set(t["kind"] for t in labels)))
        display="; ".join(dict.fromkeys(t["ru"] for t in labels))
        preview='<video controls playsinline preload="none" src="files/'+e(name)+'"></video>' if kind=="video" else '<a href="files/'+e(name)+'"><img loading="lazy" src="files/'+e(name)+'" alt="Материал для проверки"></a>'
        cards.append('<article data-kind="'+kind+'" data-group="'+e(groups)+'"><h2>'+e(row["title"])+'</h2>'+preview+'<p><b>Возможные темы (не подтверждены):</b> '+e(display)+'</p><p>'+e(row["author"])+' · '+e(row["license"])+'</p><p>'+e(row.get("restrictions_notice"))+'</p><a href="'+e(row["source"])+'" rel="noreferrer">Оригинал / сведения о правах (интернет)</a><p class="pending">Не опубликовано. Нужна независимая проверка.</p><details><summary>Контрольная сумма и ID</summary><p>'+e(row["original_sha1"])+'</p><p>'+e(row["sha256"])+'</p></details></article>')
    page='''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src 'self' file:; media-src 'self' file:; style-src 'unsafe-inline'; script-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"><title>ПУЛЬС — медиапроверка</title><style>body{font:16px system-ui;background:#eef3f5;color:#172b33;margin:0;padding:20px}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,310px),1fr));gap:16px}article{background:white;border:1px solid #ccd7dc;padding:16px;border-radius:14px;overflow-wrap:anywhere}article[hidden]{display:none}h2{font-size:17px}img,video{width:100%;max-height:260px;object-fit:contain;background:#e8eef1}a{color:#145f81}input,select{font:inherit;padding:10px;max-width:100%;box-sizing:border-box}.pending{color:#8b4910}.filters{display:flex;gap:10px;flex-wrap:wrap;margin:18px 0}</style><h1>ПУЛЬС · медиапроверка</h1><p>Локальные кандидаты. Не инструкция и не каталог для самолечения. Фотографии и ролики не утверждены для приложения.</p><div class="filters"><input id="q" placeholder="Тема, препарат, автор"><select id="kind"><option value="">Все форматы</option><option value="photo">Фото</option><option value="video">Видео</option></select><select id="group"><option value="">Все разделы</option><option value="guide">Инструкции</option><option value="medicine">Лекарства</option><option value="kit">Аптечки</option><option value="equipment">Оснащение</option></select></div><p id="count" role="status"></p><main>'''+''.join(cards)+'''</main><script>const q=document.querySelector('#q'),kind=document.querySelector('#kind'),group=document.querySelector('#group'),count=document.querySelector('#count');function filter(){let n=0;document.querySelectorAll('article').forEach(a=>{a.hidden=!(a.textContent.toLowerCase().includes(q.value.toLowerCase())&&(!kind.value||a.dataset.kind===kind.value)&&(!group.value||a.dataset.group.split(' ').includes(group.value)));if(a.hidden)a.querySelector('video')?.pause();else n++});count.textContent='Показано: '+n}document.addEventListener('input',filter);document.addEventListener('change',filter);document.addEventListener('play',ev=>{document.querySelectorAll('video').forEach(v=>{if(v!==ev.target)v.pause()})},true);filter()</script></html>'''
    (OUT/"index.html").write_text(page,encoding="utf-8")
    with (OUT/"review-checklist.csv").open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,fieldnames=["original_sha1","file","candidate_target","target_ru","license","source","rights_review","visual_review","clinical_review","review_ref","notes"]);w.writeheader()
        for row in rows:
            for m in row["matches"]:
                t=targets[m["target"]]
                w.writerow({"original_sha1":row["original_sha1"],"file":row["file"],"candidate_target":t["id"],"target_ru":t["ru"],"license":row["license"],"source":row["source"],"rights_review":"pending","visual_review":"pending","clinical_review":"pending","review_ref":"","notes":""})
    summary={"unique_verified_downloads":len(rows),"photos":sum(r["file"].endswith(".jpg") for r in rows),"videos":sum(r["file"].endswith(".mp4") for r in rows),"targets_with_downloads":len({m["target"] for r in rows for m in r["matches"]}),"rejected":rejected,"approved":0}
    (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False))
    if not rows:raise SystemExit("no usable downloads")
if __name__=="__main__":main()
