"""Inspeção dos índices e do dicionário oficial; não altera bases anteriores."""
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit
import urllib.request

AGREGADOS='https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022/Agregados_por_Setores_Censitarios/'
MALHAS='https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_de_setores_censitarios__divisoes_intramunicipais/censo_2022/'

class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag=='a':
            value=dict(attrs).get('href','')
            if value: self.links.append(value)

def inspect(url):
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=60) as r:
        data=r.read()
    folder=Path('dados/ibge/inspecao')
    folder.mkdir(parents=True,exist_ok=True)
    name=urlsplit(url).path.rstrip('/').split('/')[-1]
    (folder/(name+'.html')).write_bytes(data)
    try:
        html=data.decode('utf-8')
    except UnicodeDecodeError:
        html=data.decode('latin-1')
    parser=Links(); parser.feed(html)
    urls=[urljoin(url,href) for href in parser.links if not href.startswith('?')]
    wanted=[u for u in urls if u.startswith(url) and u!=url]
    print('\n'+url+'\n'+'\n'.join(wanted),flush=True)
    if url==AGREGADOS:
        for u in wanted:
            if 'dicionario' in u.lower() and u.endswith('.xlsx'):
                with urllib.request.urlopen(u,timeout=60) as r:
                    (folder/'dicionario_agregados.xlsx').write_bytes(r.read())

if __name__=='__main__':
    urls=[MALHAS+'setores/gpkg/UF/GO/',MALHAS+'bairros/gpkg/UF/GO/']
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(inspect,urls))
