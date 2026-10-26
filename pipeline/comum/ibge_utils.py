"""Funções compartilhadas para obter arquivos oficiais do IBGE com proveniência."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.parse import unquote, urljoin, urlsplit
import urllib.request

AGREGADOS = 'https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022/Agregados_por_Setores_Censitarios/'
MALHAS = 'https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_de_setores_censitarios__divisoes_intramunicipais/censo_2022/'
MUNICIPIO = '5208707'


def now():
    return datetime.now(timezone.utc).isoformat()


def save_json(path, obj):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.part')
    temp.write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    temp.replace(path)


def sha256(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''):
            h.update(block)
    return h.hexdigest()


def request(url, method='GET', headers=None):
    if urlsplit(url).hostname not in ['ftp.ibge.gov.br','geoftp.ibge.gov.br']:
        raise ValueError('A coleta admite apenas os dois repositórios oficiais do IBGE.')
    return urllib.request.urlopen(urllib.request.Request(url,method=method,headers={'User-Agent':'Cidadania-IBGE/1.0 (public-data-download)', **(headers or {})}),timeout=60)


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls=[]
    def handle_starttag(self, tag, attrs):
        if tag=='a' and dict(attrs).get('href'):
            self.urls.append(dict(attrs)['href'])


def index(url):
    with request(url) as r:
        data=r.read()
    try:
        text=data.decode('utf-8')
    except UnicodeDecodeError:
        text=data.decode('latin-1')
    p=Links(); p.feed(text)
    return sorted({urljoin(url,u) for u in p.urls if urljoin(url,u).startswith(url) and not u.startswith('?') and urljoin(url,u)!=url})


def latest(urls, stem, extension):
    matches=[u for u in urls if unquote(urlsplit(u).path).split('/')[-1].lower().startswith(stem.lower()) and u.lower().endswith(extension)]
    if not matches:
        raise RuntimeError(f'Arquivo oficial não localizado: {stem}{extension}')
    def rank(url):
        dates=re.findall(r'(?<!\d)(20\d{6})(?!\d)',urlsplit(url).path)
        return max(dates,default='00000000')
    best=max(rank(u) for u in matches)
    finalists=[u for u in matches if rank(u)==best]
    if len(finalists)!=1:
        raise RuntimeError(f'Versões ambíguas para {stem}: {finalists}')
    return finalists[0]


def download(item, base, force=False):
    url=item['url']
    folder='documentacao' if item['tipo']=='documentacao' else 'originais'
    target=Path(base)/folder/unquote(urlsplit(url).path).split('/')[-1]
    target.parent.mkdir(parents=True,exist_ok=True)
    receipt=target.with_suffix(target.suffix+'.json')
    with request(url,method='HEAD') as r:
        remote={'etag':r.headers.get('ETag'), 'ultima_modificacao':r.headers.get('Last-Modified'), 'bytes':int(r.headers['Content-Length']) if r.headers.get('Content-Length') else None}
    identity={'url':url,**remote}
    if target.exists() and receipt.exists() and not force:
        old=json.loads(receipt.read_text(encoding='utf-8'))
        if (remote['etag'] or remote['ultima_modificacao']) and all(old.get(k)==v for k,v in identity.items()) and (not remote['bytes'] or target.stat().st_size==remote['bytes']) and sha256(target)==old.get('sha256'):
            print('  Existente validado: '+target.name,flush=True)
            return dict(old,status='existente',verificado_em=now())
    part=target.with_suffix(target.suffix+'.part')
    partial_receipt=target.with_suffix(target.suffix+'.part.json')
    same=partial_receipt.exists() and json.loads(partial_receipt.read_text(encoding='utf-8'))==identity
    if not (same and part.exists() and (remote['etag'] or remote['ultima_modificacao'])):
        with part.open('wb'):
            pass
    save_json(partial_receipt,identity)
    for attempt in range(3):
        try:
            start=part.stat().st_size
            hdr={}
            if start:
                hdr={'Range':f'bytes={start}-','If-Range':remote['etag'] or remote['ultima_modificacao']}
            if not (start and remote['bytes']==start):
                with request(url,headers=hdr) as r:
                    append=bool(start and r.status==206)
                    if append and not r.headers.get('Content-Range','').startswith(f'bytes {start}-'):
                        raise RuntimeError('Servidor retornou intervalo inesperado.')
                    for key,header in [('etag','ETag'),('ultima_modificacao','Last-Modified')]:
                        if remote[key] and r.headers.get(header) and r.headers[header]!=remote[key]:
                            raise RuntimeError('A versão remota mudou durante o download; execute novamente.')
                    with part.open('ab' if append else 'wb') as f:
                        last=time.monotonic()
                        while block:=r.read(1024*1024):
                            f.write(block)
                            if time.monotonic()-last>=20:
                                print(f'  {target.name}: {f.tell()/1024**2:.1f} MB',flush=True)
                                last=time.monotonic()
            if remote['bytes'] and part.stat().st_size!=remote['bytes']:
                raise RuntimeError('Tamanho transferido difere do publicado.')
            with part.open('rb') as f:
                signature=f.read(16)
            if target.suffix in ['.zip','.xlsx'] and not signature.startswith(b'PK'):
                raise RuntimeError('Resposta não é ZIP/XLSX; pode ser página de erro.')
            if target.suffix=='.gpkg' and not signature.startswith(b'SQLite format 3'):
                raise RuntimeError('Resposta não é GeoPackage.')
            part.replace(target)
            record=dict(item,**remote,arquivo=str(target),sha256=sha256(target),obtido_em=now(),status='baixado')
            save_json(receipt,record)
            print(f'  Salvo: {target.name} ({target.stat().st_size/1024**2:.1f} MB)',flush=True)
            return record
        except Exception:
            if attempt==2:
                raise
            time.sleep(2**attempt)


def obtain(items, base, manifest_name, force=False):
    records=[]; errors=[]
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs={pool.submit(download,item,base,force):item for item in items}
        for job in as_completed(jobs):
            item=jobs[job]
            try:
                records.append(job.result())
            except Exception as exc:
                errors.append(f"{item['id']}: {exc}")
                records.append(dict(item,status='erro',erro=str(exc)))
                print(errors[-1],flush=True)
            save_json(Path(base)/manifest_name,dict(consultado_em=now(),ano_referencia=2022,arquivos=records,erros=errors))
    if errors:
        raise RuntimeError('; '.join(errors))
    return records


def local_records(base, manifest):
    obj=json.loads((Path(base)/manifest).read_text(encoding='utf-8'))
    if obj.get('erros'):
        raise RuntimeError('Manifesto contém downloads com erro; complete a coleta primeiro.')
    for record in obj['arquivos']:
        if sha256(record['arquivo'])!=record['sha256']:
            raise RuntimeError('Original alterado: '+record['arquivo'])
    return obj['arquivos']
