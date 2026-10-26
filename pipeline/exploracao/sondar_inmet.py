import concurrent.futures
import urllib.request

def probe(year):
    url=f'https://portal.inmet.gov.br/uploads/dadoshistoricos/{year}.zip'
    try:
        headers={'User-Agent':'Mozilla/5.0','Range':'bytes=0-255','Referer':'https://portal.inmet.gov.br/dadoshistoricos'}
        with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=40) as r:
            prefix=r.read(256)
            return year,r.status,dict(r.headers),repr(prefix[:20])
    except Exception as exc:
        return year,str(exc)

if __name__=='__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        for result in pool.map(probe,[2026,2022]): print(result,flush=True)
