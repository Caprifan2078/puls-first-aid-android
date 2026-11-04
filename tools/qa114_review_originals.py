import json, urllib.request, urllib.parse, hashlib, pathlib, re, html
entries=json.loads(pathlib.Path('qa114-media-candidates.json').read_text())
out=pathlib.Path('review')
out.mkdir(exist_ok=True)
result=[]
headers={'User-Agent':'PULS-QA114-SourceAudit/1.0 (licensed first aid media review)'}
for e in entries:
    row=dict(e)
    try:
        q=urllib.parse.urlencode({'action':'query','format':'json','formatversion':2,'prop':'imageinfo','titles':'File:'+e['file'],'iiprop':'url|mime|size|sha1|extmetadata'})
        req=urllib.request.Request('https://commons.wikimedia.org/w/api.php?'+q,headers=headers)
        with urllib.request.urlopen(req,timeout=45) as r:
            info=json.load(r)['query']['pages'][0]['imageinfo'][0]
        md=info.get('extmetadata',{})
        clean=lambda x:' '.join(html.unescape(re.sub('<[^>]*>','',x or '')).lower().split())
        label=clean(md.get('LicenseShortName',{}).get('value',''))
        link=md.get('LicenseUrl',{}).get('value','').lower()
        want=e['license'].lower()
        if want.startswith('cc by-sa '):
            ver=want.split()[-1]
            ok=(not label or ('by-sa' in label and ver in label)) and (not link or 'by-sa/'+ver in link) and bool(label or link)
        elif want.startswith('cc0 '):
            ok=(not label or 'cc0' in label) and (not link or 'publicdomain/zero/1.0' in link) and bool(label or link)
        else:
            ok=('public domain' in label or label.startswith('pd-') or 'publicdomain' in link) and 'by-sa' not in link
        if not ok: raise ValueError('license mismatch: '+label+' '+link)
        if not 1024<=info['size']<=25000000: raise ValueError('size limit')
        u=urllib.parse.urlparse(info['url'])
        if u.scheme!='https' or u.hostname!='upload.wikimedia.org': raise ValueError('unexpected source')
        with urllib.request.urlopen(urllib.request.Request(info['url'],headers=headers),timeout=90) as r:
            if urllib.parse.urlparse(r.url).hostname!='upload.wikimedia.org': raise ValueError('unexpected redirect')
            data=r.read(25000001)
        sha=hashlib.sha1(data).hexdigest()
        remote=info['sha1'].lower()
        if not re.fullmatch('[0-9a-f]{40}',remote): remote=format(int(remote,36),'040x')
        if len(data)!=info['size'] or sha!=remote: raise ValueError('source checksum/size mismatch')
        if e.get('reviewed_original_sha1') and sha!=e['reviewed_original_sha1']: raise ValueError('original differs from reviewed version')
        suffix={'video/webm':'.webm','image/jpeg':'.jpg'}.get(info['mime'])
        if not suffix: raise ValueError('unexpected MIME '+info['mime'])
        (out/(e['id']+suffix)).write_bytes(data)
        row.update(status='downloaded_for_review',sha1=sha,sha256=hashlib.sha256(data).hexdigest(),mime=info['mime'],license_label=label,license_url=link,author_html=md.get('Artist',{}).get('value',''),source='https://commons.wikimedia.org/wiki/File:'+e['file'].replace(' ','_'))
    except Exception as exc:
        row.update(status='failed',error=str(exc))
    result.append(row)
    print(e['id'],row['status'],row.get('error',''),flush=True)
(out/'audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
