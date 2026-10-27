"""Contagens semanais de dengue em Goiânia, nos municípios vizinhos e no resto de Goiás.

Lê os arquivos nacionais do SINAN já baixados (2014 em diante) e grava só agregados, sem
microdados: notificações por grupo, semana de início dos sintomas e semana de digitação, com
internações e sorotipos identificados. A semana de digitação permite reconstruir o que se
sabia em cada data, como no nowcasting.

Vizinhos: municípios cujo território faz divisa com Goiânia na malha de setores do IBGE 2022.
Mesmas regras da série de Goiânia: janela do arquivo anual, sem data de digitação ou com
digitação anterior aos sintomas ficam fora (contados no manifesto).
"""
from collections import Counter
from datetime import date, datetime, timedelta, timezone
import json
import mmap
from pathlib import Path
import tempfile

import geopandas as gpd

from pipeline.coleta.baixar_datasus import dbf_schema
from pipeline.comum.epidemiologia import anos_com_arquivo, janela_arquivo
from pipeline.comum.ibge_utils import sha256

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'dados/regional'
GOIANIA_IBGE = '5208707'
CAMPOS = ['ID_MN_RESI', 'DT_SIN_PRI', 'DT_NOTIFIC', 'DT_DIGITA', 'HOSPITALIZ', 'SOROTIPO']


def original(ano):
    pasta = 'dados/datasus' if ano >= 2022 else 'dados/datasus_historico'
    return ROOT / pasta / 'originais/dengue' / f'DENGBR{ano % 100:02d}.dbc'


def municipios():
    setores = gpd.read_file(ROOT / 'dados/ibge/originais/GO_setores_CD2022.gpkg', columns=['CD_MUN', 'NM_MUN'])
    mun = setores.dissolve('CD_MUN', aggfunc='first').reset_index().to_crs(31982)
    goiania = mun[mun.CD_MUN == GOIANIA_IBGE].geometry.iloc[0]
    vizinhos = mun[mun.geometry.touches(goiania) | (mun.geometry.intersection(goiania).length > 0)]
    vizinhos = vizinhos[vizinhos.CD_MUN != GOIANIA_IBGE]
    return {'goiania': {GOIANIA_IBGE[:6]: 'Goiânia'},
            'vizinhos': {r.CD_MUN[:6]: r.NM_MUN for r in vizinhos.itertuples()},
            'todos_go': {r.CD_MUN[:6]: r.NM_MUN for r in mun.itertuples()}}


def domingo(texto):
    d = date(int(texto[:4]), int(texto[4:6]), int(texto[6:8]))
    return d - timedelta(days=(d.weekday() + 1) % 7), d


def agregar(ano, grupos):
    """Varre o DBF nacional e conta só os residentes de Goiás, por grupo e semanas."""
    from pyreaddbc import dbc2dbf
    inicio, fim = (d.date() for d in janela_arquivo(ano))
    contagem, exclusoes = Counter(), Counter()
    with tempfile.TemporaryDirectory(dir=OUT) as pasta:
        dbf = Path(pasta) / f'dengue_{ano}.dbf'
        dbc2dbf(str(original(ano)), str(dbf))
        n, cabecalho, largura, campos = dbf_schema(dbf)
        pos = {c['nome']: (c['offset'], c['tamanho']) for c in campos if c['nome'] in CAMPOS}
        faltando = set(CAMPOS) - set(pos)
        if faltando - {'SOROTIPO', 'HOSPITALIZ'}:
            raise ValueError(f'{ano}: campos ausentes {faltando}')
        with dbf.open('rb') as arquivo, mmap.mmap(arquivo.fileno(), 0, access=mmap.ACCESS_READ) as dados:
            o_mun, t_mun = pos['ID_MN_RESI']
            for i in range(n):
                base = cabecalho + i * largura
                if dados[base:base + 1] == b'*' or dados[base + o_mun:base + o_mun + 2] != b'52':
                    continue
                def campo(nome):
                    if nome not in pos:
                        return ''
                    o, t = pos[nome]
                    return dados[base + o:base + o + t].decode('cp1252').strip(' \0')
                mun = campo('ID_MN_RESI')[:6]
                grupo = 'goiania' if mun in grupos['goiania'] else 'vizinhos' if mun in grupos['vizinhos'] else 'resto_go'
                notif, sint, dig = campo('DT_NOTIFIC'), campo('DT_SIN_PRI'), campo('DT_DIGITA')
                try:
                    notificacao = date(int(notif[:4]), int(notif[4:6]), int(notif[6:8]))
                except ValueError:
                    exclusoes[(grupo, 'notificacao_invalida')] += 1
                    continue
                if not inicio <= notificacao <= fim:
                    exclusoes[(grupo, 'notificacao_fora_da_janela')] += 1
                    continue
                try:
                    (t, d_sint), (s_dig, d_dig) = domingo(sint), domingo(dig)
                except (ValueError, IndexError):
                    exclusoes[(grupo, 'data_ausente_ou_invalida')] += 1
                    continue
                if d_dig < d_sint:
                    exclusoes[(grupo, 'digitacao_antes_dos_sintomas')] += 1
                    continue
                contagem[(grupo, t.isoformat(), s_dig.isoformat(), campo('HOSPITALIZ') == '1', campo('SOROTIPO'))] += 1
    return contagem, exclusoes


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    grupos = municipios()
    (OUT / 'municipios.json').write_text(json.dumps({'criterio': 'vizinhos: divisa com Goiânia na malha IBGE 2022',
        'goiania': grupos['goiania'], 'vizinhos': grupos['vizinhos'], 'municipios_go': len(grupos['todos_go'])},
        ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    manifesto_path = OUT / 'manifesto.json'
    anterior = json.loads(manifesto_path.read_text(encoding='utf-8')) if manifesto_path.exists() else {'anos': {}}
    anos = anos_com_arquivo(2014, original)
    registros = {}
    for ano in anos:
        hash_fonte = sha256(original(ano))
        destino = OUT / f'dengue_go_{ano}.csv'
        guardado = anterior['anos'].get(str(ano))
        # Só reprocessa o ano se o arquivo nacional mudou (a varredura leva minutos por ano).
        if guardado and guardado['fonte_sha256'] == hash_fonte and destino.exists() and sha256(destino) == guardado['produto_sha256']:
            registros[str(ano)] = guardado
            print(f'{ano}: inalterado')
            continue
        contagem, exclusoes = agregar(ano, grupos)
        linhas = ['grupo,semana_inicio,semana_digitacao,internado,sorotipo,notificacoes']
        linhas += [f'{g},{t},{d},{int(h)},{s},{n}' for (g, t, d, h, s), n in sorted(contagem.items())]
        destino.write_text('\n'.join(linhas) + '\n', encoding='utf-8')
        totais = Counter()
        for (g, *_), n in contagem.items():
            totais[g] += n
        registros[str(ano)] = {'fonte': original(ano).relative_to(ROOT).as_posix(), 'fonte_sha256': hash_fonte,
                               'produto': destino.relative_to(ROOT).as_posix(), 'produto_sha256': sha256(destino),
                               'notificacoes': dict(totais), 'exclusoes': {f'{g}:{m}': n for (g, m), n in exclusoes.items()}}
        print(f'{ano}: {dict(totais)}')
    manifesto = {'gerado_em': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'metodo': 'pipeline/coleta/extrair_regional.py',
                 'vizinhos': len(grupos['vizinhos']), 'anos': registros}
    manifesto_path.write_text(json.dumps(manifesto, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
