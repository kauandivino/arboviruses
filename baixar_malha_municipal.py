"""Baixa a camada pública Divisas de Bairro/SIGGO e audita a cobertura do IBGE."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
from urllib.parse import urlencode, urlsplit
import urllib.request
import uuid

from ibge_utils import now, save_json, sha256

LAYER='https://portalmapa.goiania.go.gov.br/servicogyn/rest/services/MapaServer/Feature_Base/MapServer/2'
HELP='https://portalmapa.goiania.go.gov.br/helpsiggo/HelpSIGGO/bai.htm'
VERSION=1
MIN_AREA=1.0  # m²: interseções inferiores a esse limiar ficam fora da tabela de pares.
FIELDS=['OBJECTID','id','tp_bai','nm_bai','nm','nm1','nm2','nm3','ql_bai','id_mun','id_re7','id_mzo','in_cond','last_edited_date']


def get(url,params=None):
    if urlsplit(url).hostname!='portalmapa.goiania.go.gov.br':
        raise ValueError('Apenas o servidor oficial portalmapa.goiania.go.gov.br é admitido.')
    full=url+('?' + urlencode(params) if params else '')
    for attempt in range(3):
        try:
            req=urllib.request.Request(full,headers={'User-Agent':'Cidadania-SIGGO/1.0 (public-map-download)'})
            with urllib.request.urlopen(req,timeout=60) as r:
                raw=r.read()
                headers={k:r.headers.get(k) for k in ['Date','Last-Modified','ETag','Content-Type']}
            return raw,dict(url=full,recebido_em=now(),headers=headers,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
        except Exception:
            if attempt==2:
                raise
            time.sleep(2**attempt)


def fetch_json(url,params,target,log):
    raw,receipt=get(url,params)
    obj=json.loads(raw)
    if obj.get('error'):
        raise RuntimeError('ArcGIS: '+json.dumps(obj['error'],ensure_ascii=False))
    target.write_bytes(raw)
    log.append(dict(receipt,arquivo=str(target)))
    return obj


def oid_name(metadata):
    names=[f['name'] for f in metadata.get('fields',[]) if f.get('type')=='esriFieldTypeOID']
    if len(names)!=1:
        raise RuntimeError('Campo OID da fonte ausente ou ambíguo.')
    return names[0]


def feature_oid(feature,field):
    props=feature.get('properties',feature.get('attributes',{}))
    lookup={k.upper():v for k,v in props.items()}
    if field.upper() not in lookup:
        raise RuntimeError('OID não retornado em uma feição.')
    return int(lookup[field.upper()])


def check_batch(obj,expected,field):
    if not (obj.get('type')=='FeatureCollection' or obj.get('geometryType')=='esriGeometryPolygon') or obj.get('exceededTransferLimit'):
        raise RuntimeError('Página truncada ou resposta geográfica não reconhecida.')
    features=obj.get('features',[])
    actual=[feature_oid(f,field) for f in features]
    if len(actual)!=len(set(actual)) or set(actual)!=set(expected):
        raise RuntimeError('A página não corresponde aos OIDs solicitados; coleta incompleta.')
    return features


def download(base,batch_size=200):
    tag=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:6]
    folder=Path(base)/'originais'/tag
    folder.mkdir(parents=True,exist_ok=False)
    log=[]
    metadata=fetch_json(LAYER,{'f':'pjson'},folder/'camada.json',log)
    if metadata.get('geometryType')!='esriGeometryPolygon':
        raise RuntimeError('A camada mudou de tipo de geometria.')
    if metadata.get('name')!='Divisas de Bairro':
        raise RuntimeError('O endereço não corresponde mais à camada Divisas de Bairro.')
    field=oid_name(metadata)
    available={f['name'] for f in metadata.get('fields',[])}
    selected_fields=[name for name in FIELDS if name in available]
    if not {field,'id','tp_bai','nm_bai'}.issubset(selected_fields):
        raise RuntimeError('Campos cartográficos essenciais ausentes.')
    ids_response=fetch_json(LAYER+'/query',{'where':'1=1','returnIdsOnly':'true','f':'json'},folder/'ids_inicio.json',log)
    ids=sorted(ids_response.get('objectIds') or [])
    if not ids or len(ids)!=len(set(ids)):
        raise RuntimeError('Lista de OIDs vazia ou duplicada.')
    count=fetch_json(LAYER+'/query',{'where':'1=1','returnCountOnly':'true','f':'json'},folder/'contagem.json',log)
    if count.get('count')!=len(ids):
        raise RuntimeError('Contagem e lista de OIDs divergem.')
    print(f'Fonte: {len(ids)} feições. Coleta em lotes de {batch_size}.',flush=True)
    features=[]
    native_header=None
    for i in range(0,len(ids),batch_size):
        batch=ids[i:i+batch_size]
        # Campos explícitos evitam depender de campos calculados e nomes duplicados do esquema.
        params={'objectIds':','.join(map(str,batch)),'outFields':','.join(selected_fields),'returnGeometry':'true','outSR':'31982','f':'json'}
        page=fetch_json(LAYER+'/query',params,folder/f'pagina_{i//batch_size+1:03}.json',log)
        if native_header is None:
            native_header={k:page[k] for k in ['geometryType','spatialReference','fields']}
        elif page.get('spatialReference')!=native_header['spatialReference'] or page.get('fields')!=native_header['fields']:
            raise RuntimeError('Esquema/CRS mudou entre páginas.')
        features.extend(check_batch(page,batch,field))
        print(f'  Recebidas {len(features)}/{len(ids)} feições',flush=True)
        time.sleep(0.3)
    after=fetch_json(LAYER+'/query',{'where':'1=1','returnIdsOnly':'true','f':'json'},folder/'ids_fim.json',log)
    if set(after.get('objectIds') or [])!=set(ids):
        raise RuntimeError('O cadastro mudou durante a coleta; execute novamente.')
    combined=folder/'bairros_siggo.esri.json'
    save_json(combined,dict(**native_header,features=features))
    log.append(dict(arquivo=str(combined),bytes=combined.stat().st_size,sha256=sha256(combined),derivado_de='paginas_esri_json'))
    try:
        raw,receipt=get(HELP)
        documentation=folder/'dicionario_siggo_bai.html'
        documentation.write_bytes(raw)
        log.append(dict(receipt,arquivo=str(documentation)))
        documentation_error=None
    except Exception as exc:
        documentation_error=str(exc)
    manifest=dict(coletado_em=now(),versao=VERSION,camada=LAYER,nome=metadata['name'],oid_field=field,feicoes=len(features),
                  crs_resposta='EPSG:31982',formato_resposta='EsriJSON',campos_solicitados=selected_fields,pasta=str(folder),arquivo_geometrico=str(combined),arquivos=log,erro_documentacao=documentation_error,
                  observacao='API pública sem snapshot transacional; OIDs conferidos antes/depois. Datas de edição não equivalem à vigência legal da malha.')
    save_json(folder/'manifesto.json',manifest)
    save_json(Path(base)/'manifesto.json',manifest)
    return manifest


def local_manifest(base):
    manifest=json.loads((Path(base)/'manifesto.json').read_text(encoding='utf-8'))
    for entry in manifest['arquivos']:
        if sha256(entry['arquivo'])!=entry['sha256']:
            raise RuntimeError('Original alterado: '+entry['arquivo'])
    return manifest


def polygonal(geometry):
    import shapely
    from shapely.geometry import MultiPolygon
    if geometry is None or geometry.is_empty:
        return None
    if geometry.geom_type in ['Polygon','MultiPolygon']:
        return geometry
    if not hasattr(geometry,'geoms'):
        return None
    parts=[]
    for part in geometry.geoms:
        cleaned=polygonal(part)
        if cleaned is not None:
            parts.extend([cleaned] if cleaned.geom_type=='Polygon' else list(cleaned.geoms))
    return shapely.union_all(parts) if parts else None


def export(data,path,layer):
    import pyogrio
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.stem+'.part.gpkg')
    pyogrio.write_dataframe(data,temp,layer=layer,driver='GPKG')
    temp.replace(path)
    geojson=path.with_suffix('.geojson')
    tmp=geojson.with_name(geojson.stem+'.part.geojson')
    pyogrio.write_dataframe(data.to_crs('EPSG:4326'),tmp,driver='GeoJSON')
    tmp.replace(geojson)
    csv=path.with_suffix('.csv')
    data.drop(columns='geometry').to_csv(csv,index=False,encoding='utf-8-sig')
    return [dict(arquivo=str(p),sha256=sha256(p),bytes=p.stat().st_size) for p in [path,geojson,csv]]


def prepare(manifest,base):
    import geopandas as gpd
    import pandas as pd
    import shapely
    import pyogrio
    data=pyogrio.read_dataframe(manifest['arquivo_geometrico'])
    if data.crs is None or data.crs.to_epsg()!=31982:
        raise RuntimeError('CRS do arquivo original diferente do solicitado.')
    oid=manifest['oid_field']
    if len(data)!=manifest['feicoes'] or data[oid].duplicated().any():
        raise RuntimeError('Contagem/OIDs inválidos no arquivo combinado.')
    data['OID_SIGGO']=data[oid].astype('int64')
    if 'id' not in data.columns or 'nm_bai' not in data.columns:
        raise RuntimeError('Esquema mudou: ID/nome municipal ausentes.')
    data['ID_SIGGO']=data['id'].fillna('').astype(str)
    fallback=data['tp_bai'].fillna('').astype(str).str.cat(data['nm_bai'].fillna('').astype(str),sep=' ').str.strip()
    data['NOME_SIGGO']=data['nm'].fillna('').astype(str).str.strip() if 'nm' in data.columns else fallback
    data.loc[data['NOME_SIGGO'].eq(''),'NOME_SIGGO']=fallback
    data['COLETADO_EM']=manifest['coletado_em']
    data['GEOMETRIA_ORIGINAL_VALIDA']=data.geometry.is_valid.astype(int)
    outputs=export(data,Path(base)/'goiania/bairros_municipais_siggo.gpkg','bairros_siggo')
    analysis=data.copy().to_crs('EPSG:31982')
    bad=~analysis.geometry.is_valid
    analysis.loc[bad,'geometry']=shapely.make_valid(analysis.loc[bad].geometry.to_numpy())
    analysis['geometry']=analysis.geometry.map(polygonal)
    usable=analysis.geometry.notna() & ~analysis.geometry.is_empty
    excluded=analysis.loc[~usable,'OID_SIGGO'].tolist()
    analysis=analysis.loc[usable].copy()
    if not len(analysis) or not analysis.geometry.is_valid.all():
        raise RuntimeError('Geometrias não puderam ser preparadas para análise.')
    outputs+=export(analysis,Path(base)/'goiania/bairros_municipais_analise.gpkg','bairros_analise')
    report=dict(preparado_em=now(),versao=VERSION,feicoes_fonte=len(data),feicoes_analise=len(analysis),
                geometrias_originais_invalidas=int((~data.geometry.is_valid).sum()),
                oids_originais_invalidos=data.loc[~data.geometry.is_valid,'OID_SIGGO'].tolist(),oids_excluidos_analise=excluded,
                ids_municipais_repetidos=int(data['ID_SIGGO'].duplicated().sum()),nomes_vazios=int(data['NOME_SIGGO'].eq('').sum()),
                ids_municipais_para_revisao=data.loc[data['ID_SIGGO'].duplicated(keep=False),['OID_SIGGO','ID_SIGGO','NOME_SIGGO']].to_dict('records'),
                id_mun_valores=sorted(data['id_mun'].dropna().astype(str).unique().tolist()) if 'id_mun' in data else [],
                fontes_estatisticas_embutidas_nao_utilizadas=['pop_total','pop_masc','pop_fem'],
                reparo='make_valid apenas na cópia de análise; componentes não poligonais descartados. Original preservado.',
                arquivos=outputs)
    save_json(Path(base)/'qualidade_malha.json',report)
    return analysis,report


def crosswalk(sectors,neighborhoods,output):
    import geopandas as gpd
    import numpy as np
    import pandas as pd
    import shapely
    if not sectors.geometry.is_valid.all() or sectors.geometry.is_empty.any() or sectors.geometry.isna().any():
        raise RuntimeError('Setores IBGE inválidos; valide a coleta IBGE primeiro.')
    if sectors['CD_SETOR'].duplicated().any():
        raise RuntimeError('Setores IBGE duplicados.')
    sectors=sectors.to_crs('EPSG:31982').reset_index(drop=True)
    neighborhoods=neighborhoods.to_crs(sectors.crs).reset_index(drop=True)
    areas=sectors.geometry.area
    if (areas<=0).any():
        raise RuntimeError('Setor com área nula.')
    pairs=gpd.sjoin(sectors[['CD_SETOR','geometry']],neighborhoods[['OID_SIGGO','ID_SIGGO','NOME_SIGGO','geometry']],how='inner',predicate='intersects')
    first=sectors.loc[pairs.index].geometry.to_numpy()
    second=neighborhoods.loc[pairs['index_right']].geometry.to_numpy()
    intersection=shapely.area(shapely.intersection(first,second))
    table=pairs.drop(columns=['geometry','index_right']).copy()
    table['AREA_INTERSECAO_M2']=intersection
    table['AREA_SETOR_M2']=areas.loc[pairs.index].to_numpy()
    table['FRACAO_AREA_SETOR']=table['AREA_INTERSECAO_M2']/table['AREA_SETOR_M2']
    ignored=table.loc[table['AREA_INTERSECAO_M2']<=MIN_AREA]
    table=table.loc[table['AREA_INTERSECAO_M2']>MIN_AREA].copy()
    table=table.sort_values(['CD_SETOR','FRACAO_AREA_SETOR','OID_SIGGO'],ascending=[True,False,True]).reset_index(drop=True)
    union=shapely.union_all(neighborhoods.geometry.to_numpy())
    coverage=shapely.area(shapely.intersection(sectors.geometry.to_numpy(),union))/areas.to_numpy()
    stats=sectors[['CD_SETOR']].copy()
    stats['AREA_SETOR_M2']=areas
    stats['FRACAO_COBERTA_UNIAO']=np.clip(coverage,0,1)
    stats['AREA_COBERTA_M2']=stats['AREA_SETOR_M2']*stats['FRACAO_COBERTA_UNIAO']
    grouped=table.groupby('CD_SETOR',sort=False)
    top=table.drop_duplicates('CD_SETOR').set_index('CD_SETOR')
    stats['N_POLIGONOS']=stats['CD_SETOR'].map(grouped.size()).fillna(0).astype(int)
    stats['SOMA_FRACOES']=stats['CD_SETOR'].map(grouped['FRACAO_AREA_SETOR'].sum()).fillna(0)
    stats['MAIOR_FRACAO']=stats['CD_SETOR'].map(top['FRACAO_AREA_SETOR']).fillna(0)
    stats['FRACAO_SOBREPOSICAO']=np.maximum(0,stats['SOMA_FRACOES']-stats['FRACAO_COBERTA_UNIAO'])
    stats['STATUS']='setor_cruza_poligonos'
    stats.loc[stats['MAIOR_FRACAO'].ge(.99),'STATUS']='candidato_um_poligono_99pct'
    stats.loc[stats['FRACAO_SOBREPOSICAO'].gt(.01),'STATUS']='sobreposicao_entre_poligonos'
    stats.loc[stats['FRACAO_COBERTA_UNIAO'].lt(.99),'STATUS']='cobertura_parcial'
    stats.loc[stats['N_POLIGONOS'].eq(0),'STATUS']='sem_intersecao_acima_tolerancia'
    eligible=stats['STATUS'].eq('candidato_um_poligono_99pct')
    stats['OID_SIGGO_CANDIDATO']=stats['CD_SETOR'].map(top['OID_SIGGO']).where(eligible).astype('Int64')
    stats['ID_SIGGO_CANDIDATO']=stats['CD_SETOR'].map(top['ID_SIGGO']).where(eligible,'')
    stats['NOME_CANDIDATO']=stats['CD_SETOR'].map(top['NOME_SIGGO']).where(eligible,'')
    if 'SITUACAO' in sectors.columns:
        stats['SITUACAO_IBGE']=sectors['SITUACAO']
        by_situation=[]
        for situation,group in stats.groupby('SITUACAO_IBGE',dropna=False):
            by_situation.append(dict(situacao=str(situation),setores=len(group),area_m2=float(group['AREA_SETOR_M2'].sum()),
                                     fracao_area_coberta=float(group['AREA_COBERTA_M2'].sum()/group['AREA_SETOR_M2'].sum())))
    else:
        by_situation=[]
    output=Path(output); output.mkdir(parents=True,exist_ok=True)
    table.to_csv(output/'intersecoes_setores_bairros.csv',index=False,encoding='utf-8-sig')
    stats.to_csv(output/'diagnostico_setores_bairros.csv',index=False,encoding='utf-8-sig')
    city=shapely.union_all(sectors.geometry.to_numpy())
    area_city=shapely.area(city)
    area_covered=shapely.area(shapely.intersection(city,union))
    return dict(setores=len(sectors),pares_intersecoes=len(table),status={k:int(v) for k,v in stats['STATUS'].value_counts().items()},por_situacao_ibge=by_situation,
                area_municipio_ibge_m2=float(area_city),area_coberta_m2=float(area_covered),fracao_area_municipio_coberta=float(area_covered/area_city),
                area_malha_fora_municipio_ibge_m2=float(shapely.area(shapely.difference(union,city))),
                intersecoes_ignoradas_ate_1m2=len(ignored),area_ignorada_m2=float(ignored['AREA_INTERSECAO_M2'].sum()),
                crs_area='EPSG:31982',limiar_area_m2=MIN_AREA,limiar_cobertura=.99,limiar_sobreposicao=.01,
                populacao_rateada=False,agregacao_por_bairro_executada=False,
                observacao='Candidatos geométricos para revisão, sem atribuição oficial de setor ou população. Cadastro atual não assegura limites de 2022 nem equivalência com bairros da Saúde.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--saida',type=Path,default=Path('dados/malha_municipal'))
    parser.add_argument('--setores',type=Path,default=Path('dados/ibge/goiania/setores_goiania_2022.gpkg'))
    parser.add_argument('--processar-local',action='store_true')
    parser.add_argument('--somente-baixar',action='store_true')
    parser.add_argument('--lote',type=int,default=200)
    args=parser.parse_args()
    if not 1<=args.lote<=500:
        parser.error('Lote deve estar entre 1 e 500.')
    args.saida.mkdir(parents=True,exist_ok=True)
    manifest=local_manifest(args.saida) if args.processar_local else download(args.saida,args.lote)
    if args.somente_baixar:
        return
    neighborhoods,quality=prepare(manifest,args.saida)
    if not args.setores.is_file():
        raise RuntimeError('Malha municipal exportada, mas setores IBGE não encontrados para conferência.')
    import pyogrio
    sectors=pyogrio.read_dataframe(args.setores)
    if not sectors['CD_SETOR'].astype(str).str.fullmatch(r'5208707\d{8}').all():
        raise RuntimeError('A malha de setores informada não é de Goiânia.')
    audit=crosswalk(sectors,neighborhoods,args.saida/'goiania')
    audit.update(executado_em=now(),fonte_municipal_sha256=sha256(manifest['arquivo_geometrico']),setores_ibge_sha256=sha256(args.setores))
    save_json(args.saida/'compatibilidade_ibge.json',audit)
    print(json.dumps(audit,ensure_ascii=False,indent=2),flush=True)
    from validar_malha_municipal import validate
    validate(args.saida,args.setores)


if __name__=='__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as exc:
        print('ERRO: '+str(exc),file=sys.stderr)
        sys.exit(1)
