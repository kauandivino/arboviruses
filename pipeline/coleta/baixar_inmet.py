"""Coleta reproduzível dos arquivos anuais oficiais do INMET e da estação A002."""
import argparse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import json
from html.parser import HTMLParser
from pathlib import Path
import re
import time
import urllib.request
import zipfile
from urllib.parse import urljoin

from pipeline.comum.epidemiologia import ano_corrente, anos_ate_corrente
from pipeline.comum.ibge_utils import now, save_json, sha256
PAGE = 'https://portal.inmet.gov.br/dadoshistoricos'


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.href = None
        self.label = ''
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.href = dict(attrs).get('href')
            self.label = ''

    def handle_data(self, data):
        if self.href:
            self.label += data

    def handle_endtag(self, tag):
        if tag == 'a' and self.href:
            self.links.append((urljoin(PAGE, self.href), self.label.strip()))
            self.href = None

CATALOGO = 'https://apitempo.inmet.gov.br/estacoes/T'


def select_member(names, year):
    candidates = []
    for name in names:
        match = re.search(rf'_A002_.*_01-01-{year}_A_(\d{{2}}-\d{{2}}-{year})\.CSV$', name, re.I)
        if match:
            candidates.append((datetime.strptime(match[1], '%d-%m-%Y'), name))
        else:
            raise RuntimeError(f'Nome da estação fora do padrão esperado: {name}')
    if not candidates:
        raise RuntimeError(f'CSV A002 não encontrado: {year}')
    latest = max(date for date, name in candidates)
    selected = [name for date, name in candidates if date == latest]
    if len(selected) != 1:
        raise RuntimeError(f'Versões ambíguas para a mesma data: {selected}')
    return selected[0]


def request(url, headers=None):
    return urllib.request.urlopen(urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0', 'Referer': PAGE, **(headers or {})}), timeout=90)


def download(item, base):
    year, url, label = item
    target = base / 'originais' / f'{year}.zip'
    target.parent.mkdir(parents=True, exist_ok=True)
    receipt = target.with_suffix('.zip.json')
    with request(url, {'Range': 'bytes=0-0'}) as response:
        total = int(response.headers['Content-Range'].split('/')[-1])
        identity = dict(url=url, bytes=total, etag=response.headers.get('ETag'),
                        ultima_modificacao=response.headers.get('Last-Modified'))
        response.read()
    if target.exists() and receipt.exists():
        old = json.loads(receipt.read_text(encoding='utf-8'))
        if all(old.get(k) == v for k, v in identity.items()) and sha256(target) == old.get('sha256'):
            print(f'{year}: arquivo existente validado', flush=True)
            return old
    part = target.with_suffix('.zip.part')
    state = target.with_suffix('.zip.part.json')
    same = state.exists() and json.loads(state.read_text(encoding='utf-8')) == identity
    if not same:
        part.write_bytes(b'')
    save_json(state, identity)
    # Blocos permitem retomar uma conexão interrompida sem repetir o arquivo inteiro.
    while part.stat().st_size < total:
        start = part.stat().st_size
        end = min(start + 8 * 1024 * 1024 - 1, total - 1)
        for attempt in range(4):
            try:
                headers = {'Range': f'bytes={start}-{end}'}
                if identity['etag']:
                    headers['If-Range'] = identity['etag']
                with request(url, headers) as response:
                    expected = f'bytes {start}-{end}/{total}'
                    if response.status != 206 or response.headers.get('Content-Range') != expected:
                        raise RuntimeError('Servidor não confirmou o intervalo solicitado; arquivo pode ter mudado.')
                    chunk = response.read()
                if len(chunk) != end - start + 1:
                    raise RuntimeError('Bloco incompleto')
                with part.open('ab') as output:
                    output.write(chunk)
                break
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(2 ** attempt)
        print(f'{year}: {part.stat().st_size / total:.0%}', flush=True)
    with zipfile.ZipFile(part) as archive:
        bad = archive.testzip()
        if bad:
            raise RuntimeError(f'CRC inválido: {bad}')
    part.replace(target)
    result = dict(identity, ano=year, rotulo_pagina=label, coletado_em=now(), sha256=sha256(target))
    save_json(receipt, result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--anos', nargs='+', type=int, default=anos_ate_corrente(2022))
    parser.add_argument('--destino', type=Path, default=Path('dados/inmet'))
    parser.add_argument('--somente-processar', action='store_true')
    args = parser.parse_args()
    base = args.destino
    base.mkdir(parents=True, exist_ok=True)
    if not args.somente_processar:
        with request(PAGE) as response:
            page = response.read()
        (base / 'pagina.html').write_bytes(page)
        links = Links(); links.feed(page.decode('utf-8'))
        with request(CATALOGO) as response:
            catalog = json.loads(response.read())
        save_json(base / 'catalogo_estacoes.json', catalog)
        stations = [s for s in catalog if s['CD_ESTACAO'] == 'A002']
        if len(stations) != 1 or stations[0]['DC_NOME'] != 'GOIANIA':
            raise RuntimeError('Catálogo não confirmou a estação A002 de Goiânia')
        save_json(base / 'estacao.json', stations[0])
        items = []
        for year in sorted(set(args.anos)):
            matches = [(year, u, label) for u, label in links.links
                       if u == f'https://portal.inmet.gov.br/uploads/dadoshistoricos/{year}.zip']
            if not matches and year == ano_corrente():
                print(f'Aviso: {year} ainda não publicado pelo INMET.', flush=True)
                continue
            if len(matches) != 1:
                raise RuntimeError(f'Link oficial ausente ou ambíguo: {year}')
            items.extend(matches)
        with ThreadPoolExecutor(max_workers=2) as pool:
            receipts = list(pool.map(lambda item: download(item, base), items))
        save_json(base / 'manifesto.json', receipts)
    extracted = base / 'estacao_originais'
    extracted.mkdir(exist_ok=True)
    sources = []
    anos = [y for y in sorted(set(args.anos)) if (base / 'originais' / f'{y}.zip').exists() or y != ano_corrente()]
    for year in anos:
        with zipfile.ZipFile(base / 'originais' / f'{year}.zip') as archive:
            names = [n for n in archive.namelist() if re.search(r'_A002_', n, re.I) and n.lower().endswith('.csv')]
            selected = select_member(names, year)
            target = extracted / f'{year}_A002.csv'
            target.write_bytes(archive.read(selected))
            sources.append(dict(ano=year, membro_zip=selected, candidatos=names,
                                criterio='Maior data final entre arquivos acumulados iniciados em 1 de janeiro; sem concatenar versões.',
                                arquivo=str(target), sha256=sha256(target)))
    save_json(base / 'fontes_estacao.json', sources)
    from pipeline.processamento.processar_inmet import processar
    processar(base, anos)


if __name__ == '__main__':
    main()
