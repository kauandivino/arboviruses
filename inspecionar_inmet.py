"""Inspeção dos links anuais e catálogo público do INMET."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from html.parser import HTMLParser
import json
import urllib.request
from urllib.parse import urljoin

PAGE='https://portal.inmet.gov.br/dadoshistoricos'

class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.href=None; self.label=''; self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag=='a':
            self.href=dict(attrs).get('href'); self.label=''
    def handle_data(self,data):
        if self.href: self.label+=data
    def handle_endtag(self,tag):
        if tag=='a' and self.href:
            self.links.append((urljoin(PAGE,self.href),self.label.strip())); self.href=None

def fetch(item):
    name,url=item
    try:
        with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=40) as r:
            raw=r.read()
        out=Path('dados/inmet/inspecao'); out.mkdir(parents=True,exist_ok=True)
        (out/(name+'.txt')).write_bytes(raw)
        if name=='pagina':
            p=Links(); p.feed(raw.decode('utf-8'))
            for u,label in p.links:
                if '.zip' in u and any(str(y) in (u+label) for y in range(2022,2027)):
                    try:
                        with urllib.request.urlopen(urllib.request.Request(u,method='HEAD'),timeout=30) as r:
                            print(label,u,dict(r.headers),flush=True)
                    except Exception as exc: print(u,str(exc),flush=True)
        else:
            data=json.loads(raw)
            print('Catálogo',len(data),flush=True)
            for row in data:
                if 'GOIANIA' in str(row).upper(): print(row,flush=True)
    except Exception as exc:
        print(name,str(exc),flush=True)

if __name__=='__main__':
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(fetch,[('pagina',PAGE),('catalogo','https://apitempo.inmet.gov.br/estacoes/T')]))
