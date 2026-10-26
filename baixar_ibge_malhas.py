"""Obtém malhas definitivas do Censo 2022 de Goiás e exporta Goiânia."""
import argparse
import json
from pathlib import Path
import re
import sys

from ibge_utils import MALHAS, MUNICIPIO, index, latest, local_records, now, obtain, save_json, sha256


def discover():
    items=[]
    for kind in ['setores','bairros']:
        folder=MALHAS+f'{kind}/gpkg/UF/GO/'
        items.append(dict(id=kind,tipo='malha',url=latest(index(folder),f'GO_{kind}_CD2022','.gpkg')))
    items.append(dict(id='dicionario_malha',tipo='documentacao',url=latest(index(MALHAS),'Dicionario_de_dados_malha_agregados','.xlsx')))
    return items


def crop(path,kind):
    import pyogrio
    info=pyogrio.read_info(path)
    names={n.upper():n for n in info['fields']}
    if 'CD_MUN' in names:
        where=f'"{names["CD_MUN"]}" = \'{MUNICIPIO}\''
    else:
        key='CD_SETOR' if kind=='setores' else 'CD_BAIRRO'
        if key not in names:
            raise RuntimeError('Código territorial não encontrado na malha.')
        where=f'substr("{names[key]}",1,7) = \'{MUNICIPIO}\''
    data=pyogrio.read_dataframe(path,where=where)
    data.columns=[c.upper() if c!='geometry' else c for c in data.columns]
    # As estatísticas vêm dos CSVs revisados, não de atributos embutidos em uma malha anterior.
    data=data.drop(columns=[c for c in data.columns if re.fullmatch(r'V\d+',c)])
    key='CD_SETOR' if kind=='setores' else 'CD_BAIRRO'
    if key not in data.columns or data.crs is None:
        raise RuntimeError('Identificador ou sistema de referência ausente na malha.')
    data[key]=data[key].astype(str)
    if data[key].duplicated().any():
        raise RuntimeError('Código territorial duplicado: '+key)
    if len(data) and not data[key].str.startswith(MUNICIPIO).all():
        raise RuntimeError('Recorte contém outro município.')
    if kind=='setores' and not len(data):
        raise RuntimeError('Nenhum setor de Goiânia foi encontrado.')
    data['ANO_REFERENCIA']=2022
    return data,dict(camada=info['layer_name'],feicoes_fonte=info['features'],feicoes_goiania=len(data),crs=str(data.crs),
                     geometrias_nulas=int(data.geometry.isna().sum()),geometrias_vazias=int(data.geometry.is_empty.sum()),
                     geometrias_invalidas=int((~data.geometry.is_valid).sum()),filtro=where)


def export(data,base,kind):
    import pyogrio
    output=Path(base)/'goiania'; output.mkdir(parents=True,exist_ok=True)
    gpkg=output/f'{kind}_goiania_2022.gpkg'
    temp=gpkg.with_name(gpkg.stem+'.part.gpkg')
    pyogrio.write_dataframe(data,temp,layer=kind,driver='GPKG')
    temp.replace(gpkg)
    geojson=gpkg.with_suffix('.geojson')
    tempjson=geojson.with_name(geojson.stem+'.part.geojson')
    pyogrio.write_dataframe(data.to_crs('EPSG:4326'),tempjson,driver='GeoJSON')
    tempjson.replace(geojson)
    data.drop(columns='geometry').to_csv(gpkg.with_suffix('.csv'),index=False,encoding='utf-8-sig')
    return dict(gpkg=str(gpkg),sha256_gpkg=sha256(gpkg),geojson=str(geojson),sha256_geojson=sha256(geojson))


def correspondence(sectors,neighborhoods,base):
    import geopandas as gpd
    import pandas as pd
    import shapely
    result=sectors[['CD_SETOR']].copy()
    if 'CD_BAIRRO' in sectors.columns:
        result['CD_BAIRRO']=sectors['CD_BAIRRO'].fillna('').astype(str)
    else:
        result['CD_BAIRRO']=''
    result['STATUS']='sem_codigo_bairro_na_malha'
    result['FRACAO_AREA_NO_BAIRRO']=pd.NA
    known=result['CD_BAIRRO'].ne('') & ~result['CD_BAIRRO'].isin(['None','nan','0'])
    if len(neighborhoods):
        matched=result['CD_BAIRRO'].isin(neighborhoods['CD_BAIRRO'])
        result.loc[known & ~matched,'STATUS']='codigo_bairro_nao_encontrado'
        result.loc[matched,'STATUS']='codigo_compativel_geometria_nao_verificada'
        if sectors.geometry.is_valid.all() and neighborhoods.geometry.is_valid.all() and not sectors.geometry.is_empty.any() and not neighborhoods.geometry.is_empty.any():
            projected=sectors.to_crs(sectors.estimate_utm_crs())
            by_code=neighborhoods.to_crs(projected.crs).set_index('CD_BAIRRO').geometry
            indices=result.index[matched]
            geom_a=projected.loc[indices].geometry.to_numpy()
            geom_b=result.loc[indices,'CD_BAIRRO'].map(by_code).to_numpy()
            area=shapely.area(geom_a)
            fraction=shapely.area(shapely.intersection(geom_a,geom_b))/area
            result.loc[indices,'FRACAO_AREA_NO_BAIRRO']=fraction
            result.loc[indices,'STATUS']=['compativel_codigo_e_geometria' if x>=0.9999 else 'divergencia_geometrica' for x in fraction]
    else:
        result.loc[known,'STATUS']='sem_bairros_do_municipio_na_fonte'
    path=Path(base)/'goiania/correspondencia_setores_bairros_2022.csv'
    result.to_csv(path,index=False,encoding='utf-8-sig')
    return dict(arquivo=str(path),sha256=sha256(path),status={k:int(v) for k,v in result['STATUS'].value_counts().items()},
                tolerancia_relativa_area=0.0001,agregacao_por_bairro_executada=False,
                observacao='Usa somente códigos de bairro do IBGE; não afirma equivalência com bairros da Saúde ou da Prefeitura.')


def process(records,base):
    sources={r['id']:r for r in records}
    if not {'setores','bairros','dicionario_malha'}.issubset(sources):
        raise RuntimeError('Manifesto incompleto para malhas.')
    tables={}; reports={}
    for kind in ['setores','bairros']:
        print('  Recortando malha de '+kind+'...',flush=True)
        data,report=crop(sources[kind]['arquivo'],kind)
        report.update(export(data,base,kind),fonte_sha256=sources[kind]['sha256'])
        tables[kind]=data; reports[kind]=report
        print(f'  {kind}: {len(data)} feições de Goiânia',flush=True)
    relation=correspondence(tables['setores'],tables['bairros'],base)
    save_json(Path(base)/'qualidade_malhas.json',dict(processado_em=now(),ano_referencia=2022,municipio=MUNICIPIO,malhas=reports,correspondencia=relation))
    return reports


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--saida',type=Path,default=Path('dados/ibge'))
    p.add_argument('--somente-baixar',action='store_true')
    p.add_argument('--processar-local',action='store_true')
    p.add_argument('--atualizar',action='store_true')
    args=p.parse_args()
    args.saida.mkdir(parents=True,exist_ok=True)
    records=local_records(args.saida,'manifesto_malhas.json') if args.processar_local else obtain(discover(),args.saida,'manifesto_malhas.json',args.atualizar)
    if not args.somente_baixar:
        process(records,args.saida)
    print('Malhas concluídas: '+str(args.saida.resolve()),flush=True)


if __name__=='__main__':
    try:
        main()
    except Exception as exc:
        print('ERRO: '+str(exc),file=sys.stderr)
        sys.exit(1)
