"""Pacote dos arquivos originais que não podem ser baixados de novo da mesma forma.

    python -m pipeline.comum.pacote_originais criar
    python -m pipeline.comum.pacote_originais restaurar caminho/do/pacote.zip

Inclui os PDFs dos informes da Prefeitura (a revisão territorial confere o hash de cada um e
a Prefeitura pode trocar ou retirar boletins) e a coleta da malha SIGGO de referência (cada
nova coleta gera outra versão). As demais fontes (SINAN, INMET, IBGE, CNES) são baixadas de
novo pelos scripts de coleta; seus manifestos registram os hashes usados.

O inventário com o hash de cada arquivo (dados/pacote_originais.json) fica no git; o ZIP vai
como anexo de uma release no GitHub.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import zipfile

from pipeline.comum.ibge_utils import sha256
from pipeline.comum.referencias import ROOT, SIGGO_COLETA

INVENTARIO = ROOT / 'dados/pacote_originais.json'
SAIDA = ROOT / 'pacotes'


def arquivos():
    pdfs = sorted((ROOT / 'dados/informes').glob('*/*.pdf'))
    malha = sorted(p for p in (ROOT / 'dados/malha_municipal/originais' / SIGGO_COLETA).rglob('*') if p.is_file())
    if not pdfs or not malha:
        raise SystemExit('Originais ausentes: os PDFs dos informes e a coleta SIGGO de referência precisam estar presentes.')
    return pdfs + malha


def criar():
    lista = arquivos()
    SAIDA.mkdir(exist_ok=True)
    data = datetime.now(timezone.utc)
    destino = SAIDA / f'originais_insubstituiveis_{data:%Y%m%d}.zip'
    inventario = []
    with zipfile.ZipFile(destino, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for arquivo in lista:
            relativo = arquivo.relative_to(ROOT).as_posix()
            zf.write(arquivo, relativo)
            inventario.append({'arquivo': relativo, 'bytes': arquivo.stat().st_size, 'sha256': sha256(arquivo)})
    registro = {'criado_em': data.isoformat(timespec='seconds'), 'pacote': destino.name, 'pacote_sha256': sha256(destino),
                'pacote_bytes': destino.stat().st_size, 'siggo_coleta': SIGGO_COLETA, 'arquivos': inventario}
    INVENTARIO.write_text(json.dumps(registro, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'{destino} · {len(inventario)} arquivos · {destino.stat().st_size / 2**20:.0f} MiB')
    print(f'Inventário em {INVENTARIO.relative_to(ROOT)}. Anexe o ZIP a uma release do GitHub.')


def restaurar(pacote):
    registro = json.loads(INVENTARIO.read_text(encoding='utf-8'))
    pacote = Path(pacote)
    if sha256(pacote) != registro['pacote_sha256']:
        raise SystemExit(f'O pacote {pacote.name} não corresponde ao inventário (hash diferente).')
    esperados = {a['arquivo']: a['sha256'] for a in registro['arquivos']}
    restaurados = existentes = 0
    with zipfile.ZipFile(pacote) as zf:
        for nome in zf.namelist():
            if nome not in esperados or '..' in Path(nome).parts:
                raise SystemExit(f'Arquivo inesperado no pacote: {nome}')
            destino = ROOT / nome
            if destino.exists():
                if sha256(destino) != esperados[nome]:
                    raise SystemExit(f'{nome} já existe com conteúdo diferente; nada foi sobrescrito.')
                existentes += 1
                continue
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(zf.read(nome))
            if sha256(destino) != esperados[nome]:
                destino.unlink()
                raise SystemExit(f'Hash incorreto ao restaurar {nome}.')
            restaurados += 1
    print(f'{restaurados} arquivos restaurados, {existentes} já existentes e conferidos.')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='comando', required=True)
    sub.add_parser('criar')
    r = sub.add_parser('restaurar')
    r.add_argument('pacote')
    args = parser.parse_args()
    criar() if args.comando == 'criar' else restaurar(args.pacote)


if __name__ == '__main__':
    sys.exit(main())
