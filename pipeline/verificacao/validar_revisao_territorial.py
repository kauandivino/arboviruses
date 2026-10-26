"""Valida linhagem, cardinalidade, transcrições e conservação das pendências."""
from collections import Counter
import json
from pathlib import Path
import pandas as pd
from pipeline.comum.ibge_utils import sha256, save_json, now
from pipeline.processamento.revisar_territorio import ROOT, ANNOTATIONS, MESH


def main():
    manifest=json.loads((ROOT/'manifesto.json').read_text(encoding='utf-8'))
    for row in manifest['fontes']+manifest['produtos']:
        assert sha256(row['arquivo'])==row['sha256'],row['arquivo']
    base=pd.read_csv(ROOT/'base_territorial_revisada.csv',dtype=str,keep_default_na=False)
    correspondence=pd.read_csv(ROOT/'correspondencia_bairros.csv',dtype=str,keep_default_na=False)
    choices=pd.read_csv(ROOT/'candidatos_siggo.csv',dtype=str,keep_default_na=False)
    mesh=pd.read_csv(MESH,dtype=str,keep_default_na=False).set_index('OID_SIGGO')
    annotations=json.loads(ANNOTATIONS.read_text(encoding='utf-8'))
    assert len(base)==360 and base.revisao_id.is_unique
    assert correspondence.bairro_rotulo_revisado.is_unique
    assert set(base.bairro_rotulo_revisado)==set(correspondence.bairro_rotulo_revisado)
    assert len(base.merge(correspondence[['bairro_rotulo_revisado']],on='bairro_rotulo_revisado',validate='many_to_one'))==360
    assert base.apto_ranking_completo_ou_taxa.eq('False').all()
    assert base.limites_homologados_pela_saude.eq('False').all()
    assert base.pode_somar_entre_boletins.eq('False').all()
    exact=correspondence.status_correspondencia.eq('nominal_unico_nao_homologado')
    assert correspondence.loc[~exact,'OID_SIGGO_candidato'].eq('').all()
    for row in correspondence.loc[exact].itertuples():
        assert row.OID_SIGGO_candidato in mesh.index
        assert mesh.loc[row.OID_SIGGO_candidato,'ID_SIGGO']==row.ID_SIGGO_candidato
        assert int(row.numero_candidatos)==1
    for row in correspondence.itertuples():
        candidates=choices[choices.bairro_rotulo_revisado.eq(row.bairro_rotulo_revisado)]
        assert len(candidates)==int(row.numero_candidatos)
        assert set(candidates.OID_SIGGO)<=set(mesh.index)
    for se,review in annotations['graficos_2026'].items():
        source=review['fonte']
        assert sha256(source['arquivo_pdf'])==source['sha256']
        assert sha256(source['recorte'])==source['sha256_recorte']
        rows=base[base.elemento_id.eq(source['elemento_id'])].copy()
        rows['pos']=rows.posicao_linha_barra.astype(int); rows=rows.sort_values('pos')
        assert rows.bairro_rotulo_revisado.to_list()==review['bairros']
        assert rows.valor_revisado.astype(int).to_list()==review['valores']
    for review in annotations['tabelas_2024'].values():
        rows=base[base.elemento_id.eq(review['fonte']['elemento_id'])]
        assert len(rows)==30
        for line in review['linhas']:
            actual=rows[rows.bairro_rotulo_revisado.eq(line[0])]
            assert dict(zip(actual.indicador,actual.valor_revisado.astype(int)))==dict(zip(review['indicadores'],line[1:]))
    assert len(base[base.ano_boletim.eq('2026')&base.se_boletim.eq('26')])==10
    assert len(base[base.ano_boletim.eq('2026')&base.se_boletim.eq('35')&base.status_periodo.eq('divergencia_na_legenda')])==10
    anomalies=pd.read_csv(ROOT/'inconsistencias_fonte.csv',dtype=str)
    assert anomalies.tipo.eq('coerencia_entre_indicadores').sum()==7
    audit=pd.read_csv(ROOT/'auditoria_revisao.csv')
    assert audit.registros_antes.sum()==308 and audit.registros_revisados.sum()==360
    assert audit.registros_recuperados.sum()==52
    workbook=pd.read_excel(ROOT/'revisao_territorial.xlsx',sheet_name=None,dtype=str,keep_default_na=False)
    for name,frame in workbook.items():
        csv=pd.read_csv(ROOT/(name+'.csv'),dtype=str,keep_default_na=False) if (ROOT/(name+'.csv')).exists() else None
        if csv is not None:
            pd.testing.assert_frame_equal(frame,csv,check_dtype=False)
    result=dict(validado_em=now(),status='aprovado_com_pendencias_de_fonte_e_homologacao',
                registros=len(base),fontes_visuais_conferidas=28,registros_recuperados=52,
                correspondencias_nominais=int(exact.sum()),pendencias_nominais=int((~exact).sum()),
                dados_nao_autorizam_taxas_ou_ranking_completo=True)
    save_json(ROOT/'validacao.json',result)
    print(json.dumps(result,ensure_ascii=True))


if __name__=='__main__':
    main()
