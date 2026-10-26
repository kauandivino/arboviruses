import concurrent.futures
import ftplib
import json
import urllib.request
from pathlib import Path

def ftp_probe(host):
    try:
        with ftplib.FTP(host, timeout=20) as ftp:
            ftp.login()
            result = {}
            for sub in ['FINAIS', 'PRELIM']:
                ftp.cwd('/dissemin/publicos/SINAN/DADOS/' + sub)
                result[sub] = [x for x in ftp.nlst() if (x.upper().startswith('ANIMBR') or (x.upper().startswith('DENG') and any(x.upper().startswith(p) for p in ['DENGGO','DENGBR']))) and x.lower().endswith('.dbc')]
            Path('dados/datasus/inspecao/ftp_indice.json').write_text(json.dumps({'host':host,'arquivos':result},indent=2))
            return host, result
    except Exception as exc:
        return host, str(exc)

def api_probe():
    url='https://apidadosabertos.saude.gov.br/arboviroses/dengue?nu_ano=2022&id_municip=520870&limit=1&offset=0'
    try:
        with urllib.request.urlopen(url,timeout=40) as r:
            data=r.read()
            Path('dados/datasus/inspecao/api_amostra.json').write_bytes(data)
            return 'API', r.status, data[:800].decode()
    except Exception as exc:
        return 'API', str(exc)

if __name__=='__main__':
    obj=json.loads(Path('dados/datasus/inspecao/catalogo.json').read_text(encoding='utf-8'))['props']['pageProps']
    for r in obj['resources']:
        if any(str(y) in r.get('name','') for y in range(2022,2027)):
            print(r['name'], r['format'],r.get('size'), r['url'],flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures=[pool.submit(ftp_probe,h) for h in ['ftp.datasus.gov.br','ftp2.datasus.gov.br']]
        futures.append(pool.submit(api_probe))
        for future in concurrent.futures.as_completed(futures): print(future.result(),flush=True)
