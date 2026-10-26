"""Baixa a base oficial mensal CNES e extrai estabelecimentos de Goiânia."""
import argparse
import ftplib
import json
from pathlib import Path
import re
import time
import zipfile
from pipeline.comum.ibge_utils import now, save_json, sha256

HOST = 'ftp.datasus.gov.br'


def connect():
    ftp = ftplib.FTP(HOST, timeout=90)
    ftp.login()
    ftp.voidcmd('TYPE I')
    return ftp


def download(remote, folder):
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / remote.rsplit('/', 1)[-1]
    receipt = target.with_suffix('.ZIP.json')
    with connect() as ftp:
        identity = dict(url=f'ftp://{HOST}{remote}', bytes=ftp.size(remote),
                        modificacao_ftp=ftp.sendcmd('MDTM ' + remote))
    if target.exists() and receipt.exists():
        old = json.loads(receipt.read_text(encoding='utf-8'))
        if all(old.get(k) == v for k, v in identity.items()) and sha256(target) == old['sha256']:
            print('Existente validado: ' + target.name, flush=True)
            return old
    part = target.with_suffix('.ZIP.part')
    state = target.with_suffix('.ZIP.part.json')
    same = state.exists() and json.loads(state.read_text(encoding='utf-8')) == identity
    if not same or not part.exists():
        part.write_bytes(b'')
    save_json(state, identity)
    for attempt in range(4):
        try:
            start = part.stat().st_size
            if start < identity['bytes']:
                last_report = time.monotonic()
                with connect() as ftp, part.open('ab') as output:
                    def write(block):
                        nonlocal last_report
                        output.write(block)
                        if time.monotonic() - last_report > 20:
                            print(f'{target.name}: {output.tell() / identity["bytes"]:.0%}', flush=True)
                            last_report = time.monotonic()
                    ftp.retrbinary('RETR ' + remote, write, blocksize=1024*1024, rest=start or None)
                    if ftp.size(remote) != identity['bytes'] or ftp.sendcmd('MDTM ' + remote) != identity['modificacao_ftp']:
                        raise RuntimeError('Arquivo remoto mudou durante a coleta; execute novamente')
            if part.stat().st_size != identity['bytes']:
                raise RuntimeError('Tamanho divergente')
            with zipfile.ZipFile(part) as archive:
                if archive.testzip():
                    raise RuntimeError('ZIP com CRC inválido')
            part.replace(target)
            result = dict(identity, sha256=sha256(target), coletado_em=now())
            save_json(receipt, result)
            return result
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--competencia', help='AAAAMM; padrão: maior competência publicada no FTP')
    parser.add_argument('--destino', type=Path, default=Path('dados/cnes'))
    parser.add_argument('--somente-processar', action='store_true')
    args = parser.parse_args()
    base = args.destino
    base.mkdir(parents=True, exist_ok=True)
    if not args.somente_processar:
        with connect() as ftp:
            names = ftp.nlst('/cnes/BASE_DE_DADOS_CNES_*.ZIP')
        available = sorted({m[1] for name in names if (m := re.search(r'BASE_DE_DADOS_CNES_(\d{6})\.ZIP$', name))})
        comp = args.competencia or max(available)
        if comp not in available:
            raise ValueError(f'Competência não publicada: {comp}')
        save_json(base / 'competencias.json', dict(consultado_em=now(), competencias=available))
        receipts = [download('/cnes/BASE_DE_DADOS_CNES_' + comp + '.ZIP', base / 'originais'),
                    download('/cnes/DICIONARIO_DE_DADOS.ZIP', base / 'originais')]
        save_json(base / f'manifesto_{comp}.json', dict(competencia=comp, arquivos=receipts))
    else:
        if not args.competencia:
            parser.error('--somente-processar exige --competencia AAAAMM')
        comp = args.competencia
    from pipeline.processamento.processar_cnes import processar
    processar(base, comp)


if __name__ == '__main__':
    main()
