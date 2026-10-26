from pathlib import Path
import pandas as pd
import geopandas as gpd
from revisar_territorio import key

ROOT=Path(__file__).resolve().parent
b=pd.read_csv(ROOT/'dados/base_integrada/bairros_publicados.csv', dtype={'OID_SIGGO_candidato':str})
b=b[(b.ano_boletim==2026)&(b.agravo=='dengue')&(b.indicador=='casos_notificados')&b.se_boletim.isin([16,20,24,28,32,36])]
b=b[b.status_correspondencia=='nominal_unico_nao_homologado']
mesh=gpd.read_file(ROOT/'dados/malha_municipal/goiania/bairros_municipais_analise.gpkg').to_crs(31982)
mesh['oid']=mesh.OID_SIGGO.astype(str)
c=pd.read_csv(ROOT/'dados/base_integrada/parceiros_candidatos.csv', dtype={'CO_CNES':str})
c=c[c.tipo_unidade_descricao.isin(['CENTRO DE SAUDE/UNIDADE BASICA','POLICLINICA','CENTRO DE IMUNIZACAO'])]
c=c[~c.NO_FANTASIA.str.startswith('DISTRITO SANITARIO')]
points=gpd.GeoDataFrame(c,geometry=gpd.points_from_xy(c.longitude,c.latitude),crs=4326).to_crs(31982)
index={}
for _,r in mesh.iterrows():
    for column in ['NOME_SIGGO','nm','nm1','nm_bai']:
        index.setdefault(key(r[column]),set()).add(r.oid)
audit=[]
for _,row in points.iterrows():
    matches=index.get(key(row.NO_BAIRRO),set())
    distance=None
    if len(matches)==1:
        geom=mesh.loc[mesh.oid==next(iter(matches))].geometry.iloc[0]
        distance=row.geometry.distance(geom)
    audit.append({'CO_CNES':row.CO_CNES,'NO_FANTASIA':row.NO_FANTASIA,'NO_BAIRRO':row.NO_BAIRRO,
                  'distancia_bairro_cadastrado_m':distance,'coerente':distance is not None and distance<=250})
audit=pd.DataFrame(audit)
print('AUDITORIA GEOGRAFICA\n',audit.to_string(index=False))
points=points[points.CO_CNES.isin(audit.loc[audit.coerente,'CO_CNES'])]
for oid,rows in b.groupby('OID_SIGGO_candidato'):
    polygon=mesh.loc[mesh.oid==oid].geometry.iloc[0]
    distances=points.geometry.distance(polygon)
    nearby=points.assign(distancia_m=distances).sort_values(['distancia_m','CO_CNES']).head(3)
    print(rows.nome_siggo_candidato.iloc[0], rows.se_boletim.nunique(), 'janelas', str(oid))
    print(nearby[['CO_CNES','NO_FANTASIA','NO_BAIRRO','distancia_m']].to_string(index=False))
