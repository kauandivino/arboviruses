import concurrent.futures
import urllib.request
from pathlib import Path

URLS = {
    'api_schema': 'https://apidadosabertos.saude.gov.br/static/swagger.json',
    'ftp_finais_http': 'http://ftp.datasus.gov.br/dissemin/publicos/SINAN/DADOS/FINAIS/',
    'ftp_prelim_http': 'http://ftp.datasus.gov.br/dissemin/publicos/SINAN/DADOS/PRELIM/',
}

def run(item):
    name, url = item
    try:
        request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(request, timeout=40) as r:
            data = r.read()
            Path('dados/datasus/inspecao').mkdir(parents=True, exist_ok=True)
            Path(f'dados/datasus/inspecao/{name}.txt').write_bytes(data)
            return name, r.status, len(data)
    except Exception as exc:
        return name, str(exc)

if __name__ == '__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for result in pool.map(run, URLS.items()):
            print(result, flush=True)
