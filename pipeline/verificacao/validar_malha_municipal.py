"""Confere integridade e o cruzamento municipal, sem estimar população por área."""
import json
from pathlib import Path

from pipeline.comum.ibge_utils import save_json,sha256,now


def require(condition,message):
    if not condition:
        raise ValueError(message)


def validate(base=Path('dados/malha_municipal'),sectors_path=Path('dados/ibge/goiania/setores_goiania_2022.gpkg')):
    import numpy as np
    import pandas as pd
    import pyogrio
    import shapely
    from pipeline.coleta.baixar_malha_municipal import local_manifest,feature_oid,VERSION
    base=Path(base); sectors_path=Path(sectors_path)
    manifest=local_manifest(base)
    folder=Path(manifest['pasta'])
    start=json.loads((folder/'ids_inicio.json').read_text(encoding='utf-8'))
    end=json.loads((folder/'ids_fim.json').read_text(encoding='utf-8'))
    count=json.loads((folder/'contagem.json').read_text(encoding='utf-8'))
    expected=set(start['objectIds'])
    require(expected==set(end['objectIds']),'OIDs divergentes entre início e fim.')
    require(len(expected)==count['count']==manifest['feicoes'],'Contagem da fonte inconsistente.')
    features=json.loads(Path(manifest['arquivo_geometrico']).read_text(encoding='utf-8'))['features']
    actual=[feature_oid(f,manifest['oid_field']) for f in features]
    require(len(actual)==len(set(actual)) and set(actual)==expected,'Coleta com OID faltante ou duplicado.')
    quality=json.loads((base/'qualidade_malha.json').read_text(encoding='utf-8'))
    require(quality['versao']==VERSION,'Versão do processamento desatualizada.')
    for record in quality['arquivos']:
        require(sha256(record['arquivo'])==record['sha256'],'Arquivo derivado alterado: '+record['arquivo'])
    original=pyogrio.read_dataframe(base/'goiania/bairros_municipais_siggo.gpkg')
    analysis=pyogrio.read_dataframe(base/'goiania/bairros_municipais_analise.gpkg')
    require(set(original['OID_SIGGO'])==expected,'OID foi perdido na exportação.')
    require(len(original)==quality['feicoes_fonte'],'Contagem da exportação original diverge.')
    require(int((~original.geometry.is_valid).sum())==quality['geometrias_originais_invalidas'],'Validade original não corresponde ao relatório.')
    require(set(analysis['OID_SIGGO']).union(quality['oids_excluidos_analise'])==expected,'Feições excluídas não foram documentadas.')
    require(analysis.geometry.is_valid.all() and not analysis.geometry.is_empty.any() and not analysis.geometry.isna().any(),'Geometria inválida na cópia de análise.')
    require(analysis.crs.to_epsg()==31982,'CRS de análise incorreto.')
    geojson=pyogrio.read_dataframe(base/'goiania/bairros_municipais_analise.geojson')
    require(set(geojson['OID_SIGGO'])==set(analysis['OID_SIGGO']),'GeoJSON perdeu feições.')
    require(geojson.crs.to_epsg()==4326,'GeoJSON fora de WGS84.')
    audit=json.loads((base/'compatibilidade_ibge.json').read_text(encoding='utf-8'))
    require(audit['fonte_municipal_sha256']==sha256(manifest['arquivo_geometrico']),'Diagnóstico usa outra fonte municipal.')
    require(audit['setores_ibge_sha256']==sha256(sectors_path),'Diagnóstico usa outra versão dos setores.')
    require(not audit['populacao_rateada'] and not audit['agregacao_por_bairro_executada'],'Não deveria haver estimativa de população por bairro.')
    sectors=pyogrio.read_dataframe(sectors_path).to_crs('EPSG:31982').set_index('CD_SETOR')
    require(sectors.index.str.fullmatch(r'5208707\d{8}').all(),'Setores fora de Goiânia/formato inválido.')
    diagnostic_path=base/'goiania/diagnostico_setores_bairros.csv'
    pairs_path=base/'goiania/intersecoes_setores_bairros.csv'
    diagnostics=pd.read_csv(diagnostic_path,dtype={'CD_SETOR':str},keep_default_na=False)
    pairs=pd.read_csv(pairs_path,dtype={'CD_SETOR':str,'ID_SIGGO':str},keep_default_na=False)
    require(not diagnostics['CD_SETOR'].duplicated().any(),'Diagnóstico duplicou setores.')
    require(set(diagnostics['CD_SETOR'])==set(sectors.index),'Diagnóstico não cobre todos os setores.')
    require(not pairs.duplicated(['CD_SETOR','OID_SIGGO']).any(),'Par setor/feição duplicado.')
    require(set(pairs['CD_SETOR']).issubset(sectors.index),'Par com setor inexistente.')
    require(set(pairs['OID_SIGGO']).issubset(analysis['OID_SIGGO']),'Par com OID inexistente.')
    require((pairs['AREA_INTERSECAO_M2']>audit['limiar_area_m2']).all(),'Par abaixo do limiar.')
    require(pairs['FRACAO_AREA_SETOR'].between(0,1+1e-7).all(),'Fração de interseção impossível.')
    neighborhoods=analysis.set_index('OID_SIGGO')
    area=shapely.area(shapely.intersection(sectors.loc[pairs['CD_SETOR']].geometry.to_numpy(),neighborhoods.loc[pairs['OID_SIGGO']].geometry.to_numpy()))
    require(np.allclose(area,pairs['AREA_INTERSECAO_M2'],rtol=1e-8,atol=.01),'Área de pares não corresponde às geometrias.')
    require(np.allclose(area/sectors.loc[pairs['CD_SETOR']].geometry.area.to_numpy(),pairs['FRACAO_AREA_SETOR'],rtol=1e-8,atol=1e-9),'Fração de pares incorreta.')
    grouped=pairs.groupby('CD_SETOR')['FRACAO_AREA_SETOR'].sum()
    require(np.allclose(diagnostics['SOMA_FRACOES'],diagnostics['CD_SETOR'].map(grouped).fillna(0)),'Soma de interseções diverge.')
    require({k:int(v) for k,v in diagnostics['STATUS'].value_counts().items()}==audit['status'],'Contagem por status diverge.')
    candidates=diagnostics['STATUS'].eq('candidato_um_poligono_99pct')
    require((diagnostics.loc[candidates,'MAIOR_FRACAO']>=.99-1e-9).all(),'Candidato com cobertura insuficiente.')
    require((diagnostics.loc[candidates,'FRACAO_SOBREPOSICAO']<=.01+1e-9).all(),'Candidato com sobreposição excessiva.')
    require(diagnostics.loc[~candidates,'ID_SIGGO_CANDIDATO'].eq('').all(),'Setor ambíguo recebeu código candidato.')
    files=[dict(arquivo=str(path),sha256=sha256(path)) for path in [diagnostic_path,pairs_path,base/'compatibilidade_ibge.json',base/'qualidade_malha.json']]
    report=dict(validado_em=now(),status='aprovado_com_limitacoes',versao=VERSION,feicoes=len(expected),setores=len(sectors),pares=len(pairs),
                candidatos_geometricos=int(candidates.sum()),fracao_area_municipio_coberta=audit['fracao_area_municipio_coberta'],
                invalidas_originais=quality['geometrias_originais_invalidas'],ids_municipais_repetidos=quality['ids_municipais_repetidos'],arquivos=files,
                limitacoes=['A camada representa Divisas de Bairro/loteamentos do SIGGO; equivalência com bairros da Saúde ainda não validada.',
                            'Cobertura territorial parcial e setores atravessando divisas: não há agregação de população por bairro.',
                            'Cadastro consultado atualmente e setores do Censo 2022 têm referências temporais distintas.'],
                verificacoes=['Hashes dos originais e derivados','OIDs, contagens e integridade dos lotes','Geometrias reparadas só na cópia de análise',
                              'Chaves de todos os setores IBGE','Áreas de cada par recalculadas das geometrias','Reconciliação de status e ausência de candidatos em setores ambíguos'])
    save_json(base/'validacao.json',report)
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
    return report


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--saida',type=Path,default=Path('dados/malha_municipal'))
    parser.add_argument('--setores',type=Path,default=Path('dados/ibge/goiania/setores_goiania_2022.gpkg'))
    args=parser.parse_args()
    validate(args.saida,args.setores)
