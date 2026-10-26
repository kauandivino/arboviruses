"""Prepara as camadas do mapa do painel a partir das malhas e cadastros oficiais já processados.

Geometrias reais em SIRGAS 2000 / UTM 22S (EPSG:31982), simplificadas para exibição
e convertidas em caminhos SVG com coordenadas inteiras em metros. Nada é interpolado:
bairros sem citação ou sem correspondência única ficam sem valor, não com zero.
"""
from datetime import datetime, timezone
import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
import shapely
from shapely.geometry import MultiPolygon, Polygon

from pipeline.comum.ibge_utils import sha256

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'dados/mapa'
CRS = 'EPSG:31982'
TOLERANCIA_BAIRROS_M = 8
TOLERANCIA_LIMITE_M = 15
FONTES = {
    'bairros': ROOT / 'dados/malha_municipal/goiania/bairros_municipais_analise.gpkg',
    'setores': ROOT / 'dados/ibge/goiania/setores_goiania_2022.gpkg',
    'unidades': ROOT / 'dados/base_integrada/parceiros_candidatos.csv',
    'candidatos': ROOT / 'dados/selecao_territorios/candidatos_e_reservas.csv',
    'selecionados': ROOT / 'dados/selecao_territorios/oito_territorios.csv',
    'parceiros_territorio': ROOT / 'dados/selecao_territorios/parceiros_candidatos.csv',
}


def caminho_svg(geom, origem):
    """Converte (Multi)Polygon em caminho SVG relativo; y cresce para o sul."""
    x0, y1 = origem
    partes = []
    poligonos = geom.geoms if isinstance(geom, MultiPolygon) else [geom]
    for poligono in poligonos:
        for anel in [poligono.exterior, *poligono.interiors]:
            pontos = [(round(x - x0), round(y1 - y)) for x, y in anel.coords[:-1]]
            pontos = [p for i, p in enumerate(pontos) if i == 0 or p != pontos[i - 1]]
            if len(pontos) < 3:
                continue
            texto = [f'M{pontos[0][0]} {pontos[0][1]}']
            for (ax, ay), (bx, by) in zip(pontos, pontos[1:]):
                texto.append(f'l{bx - ax} {by - ay}')
            partes.append(''.join(texto) + 'z')
    return ''.join(partes)


def poligonal(geom):
    geom = shapely.make_valid(geom)
    if isinstance(geom, (Polygon, MultiPolygon)):
        return geom
    return MultiPolygon([g for g in getattr(geom, 'geoms', []) if isinstance(g, Polygon)])


def main():
    bairros = gpd.read_file(FONTES['bairros']).to_crs(CRS)
    limite = poligonal(gpd.read_file(FONTES['setores']).to_crs(CRS).union_all())
    xmin, ymin, xmax, ymax = limite.bounds
    origem = (xmin, ymax)

    candidatos = pd.read_csv(FONTES['candidatos'], dtype={'OID_SIGGO': int})
    selecionados = pd.read_csv(FONTES['selecionados'], dtype={'OID_SIGGO': int, 'CO_CNES': str})
    parceiros = pd.read_csv(FONTES['parceiros_territorio'], dtype={'OID_SIGGO': int, 'CO_CNES': str})
    unidades = pd.read_csv(FONTES['unidades'], dtype={'CO_CNES': str})

    linhas = [{'camada': 'limite', 'id': 'limite-goiania', 'nome': 'Goiânia (malha de setores IBGE 2022)',
               'd': caminho_svg(poligonal(limite.simplify(TOLERANCIA_LIMITE_M)), origem),
               'largura_m': round(xmax - xmin), 'altura_m': round(ymax - ymin)}]

    cand = candidatos.set_index('OID_SIGGO')
    sel = selecionados.set_index('OID_SIGGO')
    for _, b in bairros.sort_values('OID_SIGGO').iterrows():
        oid = int(b.OID_SIGGO)
        geom = poligonal(b.geometry.simplify(TOLERANCIA_BAIRROS_M, preserve_topology=True))
        if geom.is_empty:
            geom = poligonal(b.geometry)
        c = cand.loc[oid] if oid in cand.index else None
        s = sel.loc[oid] if oid in sel.index else None
        centro = b.geometry.representative_point()
        linhas.append({
            'camada': 'bairro', 'id': f'bairro-{oid}', 'OID_SIGGO': oid, 'nome': b.NOME_SIGGO,
            'd': caminho_svg(geom, origem),
            # Feições degeneradas na fonte (área abaixo de 1 m²) ficam na camada, mas sem contorno.
            'area_fonte_m2': round(b.geometry.area, 1),
            'cx': round(centro.x - xmin), 'cy': round(ymax - centro.y),
            'situacao': 'selecionado' if s is not None else 'candidato' if c is not None else 'contexto',
            'janelas_com_citacao': None if c is None else int(c.janelas_com_citacao),
            'janelas_observadas': None if c is None else int(c.janelas_observadas),
            'edicoes_citadas': None if c is None else str(c.edicoes_citadas),
            'motivo_decisao': None if c is None else str(c.motivo_decisao),
            'ordem_articulacao': None if s is None else int(s.ordem_articulacao),
            'parceiro_cnes': None if s is None else s.CO_CNES,
            'parceiro_nome': None if s is None else s.unidade,
            'distancia_parceiro_m': None if s is None else float(s.distancia_minima_poligono_m),
        })

    pontos = gpd.GeoSeries(gpd.points_from_xy(unidades.longitude, unidades.latitude), crs='EPSG:4326').to_crs(CRS)
    parceiro_de = selecionados.groupby('CO_CNES').territorio.apply(lambda t: '; '.join(t)).to_dict()
    proximo_de = parceiros.groupby('CO_CNES').territorio.apply(lambda t: '; '.join(sorted(set(t)))).to_dict()
    for (_, u), p in zip(unidades.iterrows(), pontos):
        linhas.append({
            'camada': 'unidade', 'id': f'cnes-{u.CO_CNES}', 'CO_CNES': u.CO_CNES, 'nome': u.NO_FANTASIA,
            'tipo': u.tipo_unidade_descricao, 'bairro_cadastrado': u.NO_BAIRRO,
            'x': round(p.x - xmin), 'y': round(ymax - p.y),
            'latitude': float(u.latitude), 'longitude': float(u.longitude),
            'situacao': 'parceiro_selecionado' if u.CO_CNES in parceiro_de else 'candidato',
            'parceiro_de': parceiro_de.get(u.CO_CNES), 'ate_3km_de': proximo_de.get(u.CO_CNES),
        })

    OUT.mkdir(parents=True, exist_ok=True)
    destino = OUT / 'camadas.json'
    destino.write_text(json.dumps(linhas, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    contagem = pd.Series([l['camada'] for l in linhas]).value_counts().to_dict()
    manifesto = {
        'gerado_em': datetime.now(timezone.utc).isoformat(), 'metodo': 'pipeline/processamento/preparar_mapa.py',
        'crs': CRS, 'origem_svg_m': {'x_min': xmin, 'y_max': ymax},
        'simplificacao_m': {'bairros': TOLERANCIA_BAIRROS_M, 'limite': TOLERANCIA_LIMITE_M},
        'fontes': [{'arquivo': f.relative_to(ROOT).as_posix(), 'sha256': sha256(f)} for f in FONTES.values()],
        'produto': {'arquivo': destino.relative_to(ROOT).as_posix(), 'sha256': sha256(destino)},
        'feicoes': contagem,
    }
    (OUT / 'manifesto.json').write_text(json.dumps(manifesto, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(contagem, ensure_ascii=False), f'{destino.stat().st_size / 1024:.0f} KiB')


if __name__ == '__main__':
    main()
