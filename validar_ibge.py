"""Valida originais, recortes e compatibilidade de chaves do Censo 2022 em Goiânia."""
import json
from pathlib import Path
import sqlite3
import zipfile

from ibge_utils import MUNICIPIO, now, save_json, sha256


def require(condition,message):
    if not condition:
        raise ValueError(message)


def validate(base=Path('dados/ibge')):
    import pandas as pd
    import pyogrio
    base=Path(base)
    originals=[]
    for name in ['manifesto_agregados.json','manifesto_malhas.json']:
        obj=json.loads((base/name).read_text(encoding='utf-8'))
        require(not obj['erros'],'Manifesto contém falhas: '+name)
        for record in obj['arquivos']:
            path=Path(record['arquivo'])
            require(sha256(path)==record['sha256'],'Hash do original diverge: '+str(path))
            if record.get('bytes'):
                require(path.stat().st_size==record['bytes'],'Tamanho diverge: '+str(path))
            if path.suffix in ['.xlsx','.zip']:
                with zipfile.ZipFile(path) as z:
                    require(z.testzip() is None,'ZIP corrompido: '+str(path))
            elif path.suffix=='.gpkg':
                with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True) as conn:
                    require(conn.execute('PRAGMA quick_check').fetchone()[0]=='ok','GeoPackage inconsistente.')
            originals.append(record)
    require({r['id'] for r in originals}=={'basico','domicilio1','domicilio2','domicilio3','dicionario_agregados','dicionario_malha','setores','bairros'},'Cobertura de originais incompleta.')
    ag=json.loads((base/'qualidade_agregados.json').read_text(encoding='utf-8'))
    geo=json.loads((base/'qualidade_malhas.json').read_text(encoding='utf-8'))
    source={r['id']:r for r in originals}
    frames={}
    for name,report in ag['tabelas'].items():
        require(report['fonte_sha256']==source[name]['sha256'],'Recorte de agregado desatualizado.')
        require(sha256(report['arquivo'])==report['sha256'],'CSV alterado: '+name)
        data=pd.read_csv(report['arquivo'],dtype=str,keep_default_na=False,na_filter=False)
        require(len(data)==report['linhas_municipio'],'Contagem diverge: '+name)
        require(not data['CD_SETOR'].duplicated().any(),'Setores duplicados: '+name)
        require(data['CD_SETOR'].str.fullmatch(MUNICIPIO+r'\d{8}').all(),'Setor de outro município: '+name)
        require(data['ANO_REFERENCIA'].eq('2022').all(),'Ano de referência incorreto.')
        frames[name]=data
    for kind,report in geo['malhas'].items():
        require(report['fonte_sha256']==source[kind]['sha256'],'Recorte da malha desatualizado.')
        require(sha256(report['gpkg'])==report['sha256_gpkg'],'Malha GPKG alterada.')
        require(sha256(report['geojson'])==report['sha256_geojson'],'GeoJSON alterado.')
        data=pyogrio.read_dataframe(report['gpkg'])
        require(len(data)==report['feicoes_goiania'],'Contagem da malha diverge.')
        require(data.crs is not None,'Malha sem CRS.')
        require(data.geometry.is_valid.all() and not data.geometry.is_empty.any(),'Malha contém geometria inválida/vazia.')
        key='CD_SETOR' if kind=='setores' else 'CD_BAIRRO'
        require(not data[key].duplicated().any(),'Código da malha duplicado.')
        require(data[key].astype(str).str.startswith(MUNICIPIO).all(),'Malha contém outro município.')
        reread=pyogrio.read_dataframe(report['geojson'])
        # Uma FeatureCollection vazia não carrega esquema de propriedades.
        if len(data):
            require(set(reread[key])==set(data[key]),'GeoJSON e GPKG têm chaves diferentes.')
            require(reread.crs.to_epsg()==4326,'GeoJSON fora de WGS84.')
        else:
            require(len(reread)==0,'GeoJSON deveria estar vazio.')
        if kind=='setores':
            sectors=data
        else:
            neighborhoods=data
    coverage=pd.DataFrame({'CD_SETOR':sorted(set(sectors['CD_SETOR']).union(frames['basico']['CD_SETOR']))})
    coverage['PRESENTE_MALHA']=coverage['CD_SETOR'].isin(sectors['CD_SETOR']).astype(int)
    for name,data in frames.items():
        coverage['PRESENTE_'+name.upper()]=coverage['CD_SETOR'].isin(data['CD_SETOR']).astype(int)
    coverage=coverage.merge(frames['basico'][['CD_SETOR','V0001','V0002']],on='CD_SETOR',how='left',validate='one_to_one')
    coverage.to_csv(base/'goiania/cobertura_agregados_malha_2022.csv',index=False,encoding='utf-8-sig')
    require(set(sectors['CD_SETOR'])==set(frames['basico']['CD_SETOR']),'Agregado básico e malha incompatíveis; consulte cobertura_agregados_malha_2022.csv.')
    indicators=pd.read_csv(base/'goiania/indicadores_prioritarios_setores_2022.csv',dtype=str,keep_default_na=False)
    require(set(indicators['CD_SETOR'])==set(frames['basico']['CD_SETOR']),'Indicadores perderam/adicionaram setores.')
    require(not indicators['CD_SETOR'].duplicated().any(),'Join multiplicou setores.')
    descriptions=pd.read_csv(base/'goiania/dicionario_indicadores_prioritarios.csv',dtype=str,keep_default_na=False)
    for row in descriptions.to_dict('records'):
        original=frames[row['tabela']].set_index('CD_SETOR')[row['variavel']]
        exported=indicators.set_index('CD_SETOR')[row['coluna']]
        expected=original.reindex(exported.index).fillna('')
        require(exported.equals(expected.rename(exported.name)),f'Células modificadas no indicador {row["coluna"]}')
    correspondence=pd.read_csv(geo['correspondencia']['arquivo'],dtype=str,keep_default_na=False)
    require(set(correspondence['CD_SETOR'])==set(sectors['CD_SETOR']),'Correspondência incompleta.')
    require(not geo['correspondencia']['agregacao_por_bairro_executada'],'Não deveria haver agregação por bairro.')
    limitations=[]
    if not len(neighborhoods):
        limitations.append('A malha de bairros do IBGE para Goiás não inclui Goiânia. A malha municipal de bairros ainda é necessária para essa agregação.')
    missing={name:len(set(frames['basico']['CD_SETOR'])-set(data['CD_SETOR'])) for name,data in frames.items()}
    without_theme=frames['basico'].loc[~frames['basico']['CD_SETOR'].isin(frames['domicilio1']['CD_SETOR']),['CD_SETOR','V0001','V0002','CD_TIPO']]
    for name,n in missing.items():
        if n:
            limitations.append(f'{name}: {n} setores do básico sem linha nessa tabela. Ausência preservada, sem preenchimento por zero.')
    result=dict(validado_em=now(),status='aprovado_com_limitacoes' if limitations else 'aprovado',ano_referencia=2022,municipio=MUNICIPIO,
                originais=len(originals),originais_bytes=sum(Path(r['arquivo']).stat().st_size for r in originals),
                setores=len(sectors),bairros_ibge=len(neighborhoods),linhas_tabelas={name:len(data) for name,data in frames.items()},
                indicadores=len(descriptions),cobertura=missing,limitacoes=limitations,
                setores_sem_linha_domicilio1=without_theme.to_dict('records'),
                verificacoes=['SHA-256 dos originais e recortes','CRC dos ZIPs/XLSX','Integridade SQLite dos GeoPackages','Geometrias, CRS e códigos municipais',
                              'Chaves do básico contra malha definitiva','Preservação célula a célula dos indicadores e marcadores','Ausência de multiplicação de linhas no join'])
    save_json(base/'validacao.json',result)
    print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
    return result


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--saida',type=Path,default=Path('dados/ibge'))
    args=parser.parse_args()
    validate(args.saida)
