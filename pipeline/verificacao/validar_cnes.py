"""Verifica procedência, chaves e conservação dos registros nos produtos CNES."""
import argparse
import json
from pathlib import Path
import geopandas as gpd
import pandas as pd
from pipeline.comum.ibge_utils import now, save_json, sha256
from pipeline.processamento.processar_cnes import coordinate_status


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--competencia',required=True)
    args=parser.parse_args()
    base=Path('dados/cnes'); out=base/'goiania'/args.competencia
    manifest=json.loads((base/f'manifesto_{args.competencia}.json').read_text(encoding='utf-8'))
    for record in manifest['arquivos']:
        path=base/'originais'/record['url'].rsplit('/',1)[-1]
        assert path.stat().st_size==record['bytes']
        assert sha256(path)==record['sha256']
    data=pd.read_csv(out/'estabelecimentos.csv',dtype=str,keep_default_na=False)
    assert len(data)>0 and data.CO_CNES.is_unique and data.CO_UNIDADE.is_unique
    assert data.CO_CNES.str.fullmatch(r'\d{7}').all()
    assert data.CO_UNIDADE.str.startswith('520870').all()
    assert data.CO_MUNICIPIO_GESTOR.eq('520870').all()
    assert data.competencia.eq(args.competencia).all()
    assert not any('CPF' in c or 'USUARIO' in c for c in data.columns)
    statuses=[coordinate_status(a,b)[2] for a,b in zip(data.NU_LATITUDE,data.NU_LONGITUDE)]
    assert statuses==data.status_coordenada.to_list()
    points=gpd.read_file(out/'estabelecimentos.gpkg')
    geojson=gpd.read_file(out/'estabelecimentos.geojson')
    valid=data.status_coordenada.eq('dominio_valido')
    assert set(points.CO_CNES)==set(geojson.CO_CNES)==set(data.loc[valid,'CO_CNES'])
    assert len(points)==len(geojson)==int(valid.sum())
    assert points.crs.to_epsg()==4326
    indexed=data.set_index('CO_CNES')
    for row in points.itertuples():
        original=indexed.loc[row.CO_CNES]
        assert abs(row.geometry.y-float(original.NU_LATITUDE.replace(',', '.')))<1e-10
        assert abs(row.geometry.x-float(original.NU_LONGITUDE.replace(',', '.')))<1e-10
    expected=data.status_coordenada.ne('dominio_valido')|data.checagem_municipal.eq('fora_malha_2022')
    review=pd.read_csv(out/'revisar_localizacao.csv',dtype=str)
    assert set(review.CO_CNES)==set(data.loc[expected,'CO_CNES'])
    summary=pd.read_csv(out/'resumo_tipos.csv')
    assert int(summary.estabelecimentos.sum())==len(data)
    report=dict(validado_em=now(),status='aprovado',competencia=args.competencia,
                estabelecimentos=len(data),pontos=len(points),revisar_localizacao=len(review))
    save_json(out/'validacao.json',report)
    print(report)


if __name__=='__main__':
    main()
