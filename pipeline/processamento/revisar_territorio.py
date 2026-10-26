"""Aplica conferências visuais e produz correspondências nominais auditáveis ao SIGGO."""
from collections import Counter
from difflib import SequenceMatcher
import json
from pathlib import Path
import re
import unicodedata

import pandas as pd
from pipeline.comum.ibge_utils import now, save_json, sha256
from pipeline.processamento.extrair_informes import periodo

ROOT=Path('dados/revisao_territorial')
ANNOTATIONS=Path('dados/revisao_territorial/revisoes_visuais_informes.json')
MESH=Path('dados/malha_municipal/goiania/bairros_municipais_analise.csv')
TYPES={'S':'SETOR','SET':'SETOR','ST':'SETOR','JD':'JARDIM','PRQ':'PARQUE','PQ':'PARQUE','PARQ':'PARQUE',
       'VL':'VILA','VI':'VILA','BRO':'BAIRRO','RES':'RESIDENCIAL','CJ':'CONJUNTO','CONJ':'CONJUNTO'}
HINTS={
    'D NOVO MUNDO':('JD NOVO MUNDO','abreviacao_ou_erro_impresso_D_nao_e_JD'),
    'TS URIAS MAGALHAES':('SET URIAS MAGALHAES','prefixo_TS_nao_identificado'),
    'ST VILA NOVA':('SET LESTE VILA NOVA','termo_LESTE_ausente_no_rotulo'),
    'ST JD AMERICA':('BRO JARDIM AMERICA','tipo_SETOR_diverge_de_BAIRRO'),
    'JD N MUNDO':('JD NOVO MUNDO','abreviacao_N_requer_confirmacao'),
    'SET U MAGALHAES':('SET URIAS MAGALHAES','abreviacao_U_requer_confirmacao'),
    'SET L VILA NOVA':('SET LESTE VILA NOVA','abreviacao_L_requer_confirmacao'),
    'SET L UNIVERSITARIO':('SET LESTE UNIVERSITARIO','abreviacao_L_requer_confirmacao'),
    'PARQUE AMAZONAS':('PARQUE AMAZONIA','toponimos_AMAZONAS_e_AMAZONIA_diferentes'),
    'PQ TREMENDAO':('SET PARQUE TREMENDAO','prefixo_SETOR_ausente_no_rotulo'),
    'SITIO REC MORADA DO SOL':('SETOR MORADA DO SOL','tipo_SITIO_RECREIO_diverge_de_SETOR')}


def key(value):
    text=''.join(c for c in unicodedata.normalize('NFKD',str(value).upper()) if not unicodedata.combining(c))
    text=re.sub(r"D[’']ALVA",'DALVA',text)
    text=re.sub(r'[^A-Z0-9 ]',' ',text)
    words=text.split()
    if words:
        words[0]=TYPES.get(words[0],words[0])
    if len(words)>1 and words[0] in ('BAIRRO','SETOR'):
        words[1]=TYPES.get(words[1],words[1])
    if len(words)>1 and words[0]=='SITIO' and words[1]=='REC':
        words[1]='RECREIO'
    return ' '.join(words)


def mesh_keys(row):
    names=[row[c] for c in ['NOME_SIGGO','nm','nm1','nm3'] if row[c]]
    if row['tp_bai'] and row['nm_bai']:
        names.append(row['tp_bai']+' '+row['nm_bai'])
    return {key(name) for name in names if name.strip()}


def match_name(name,mesh):
    normalized=key(name)
    candidates=[]; method=''; hint=''
    if '...' in name or '…' in name:
        candidates=[r for r in mesh if any(k.startswith(normalized) for k in r['_keys'])]
        method='prefixo_truncado_na_propria_fonte'
    else:
        candidates=[r for r in mesh if normalized in r['_keys']]
        if candidates:
            method='nome_normalizado_exato'
        elif name in HINTS:
            proposed,hint=HINTS[name]
            proposed_key=key(proposed)
            candidates=[r for r in mesh if proposed_key in r['_keys']]
            method='hipotese_contextual_nao_confirmada'
        elif re.search(r'\s(?:I|II|III|IV|V|[1-9])$',normalized):
            parent=re.sub(r'\s(?:I|II|III|IV|V|[1-9])$','',normalized)
            candidates=[r for r in mesh if parent in r['_keys']]
            method='etapa_nao_identificada_na_malha'
            hint='Não eliminar o indicador de etapa para forçar equivalência.'
        else:
            candidates=[r for r in mesh if any(k.startswith(normalized+' ') for k in r['_keys'])]
            if candidates:
                method='complementos_ou_subdivisoes_sem_equivalencia_confirmada'
    ranked=[]
    if not candidates:
        for r in mesh:
            score=max(SequenceMatcher(None,normalized,k).ratio() for k in r['_keys'])
            ranked.append((score,r))
        ranked=sorted(ranked,key=lambda pair:pair[0],reverse=True)[:5]
        candidates=[r for score,r in ranked if score>=.5]
        method='somente_sugestao_textual_sem_vinculo'
    exact=method=='nome_normalizado_exato'
    status=('nominal_unico_nao_homologado' if len(candidates)==1 else 'nome_exato_multiplos_poligonos') if exact else (
            'rotulo_truncado_na_fonte' if 'truncado' in method else 'pendente_identificacao_territorial')
    selected=candidates[0] if exact and len(candidates)==1 else None
    return dict(bairro_rotulo_revisado=name,bairro_chave=normalized,status_correspondencia=status,
                metodo_correspondencia=method,nota_correspondencia=hint,
                numero_candidatos=len(candidates),
                OID_SIGGO_candidato=selected['OID_SIGGO'] if selected else '',
                ID_SIGGO_candidato=selected['ID_SIGGO'] if selected else '',
                nome_siggo_candidato=selected['NOME_SIGGO'] if selected else '',
                candidatos_oids=json.dumps([r['OID_SIGGO'] for r in candidates],ensure_ascii=False),
                candidatos_nomes=json.dumps([r['NOME_SIGGO'] for r in candidates],ensure_ascii=False),
                limites_homologados_pela_saude=False,
                pode_agregar_populacao_ou_calcular_taxa=False),[
                    dict(bairro_chave=normalized,bairro_rotulo_revisado=name,OID_SIGGO=r['OID_SIGGO'],
                         ID_SIGGO=r['ID_SIGGO'],nome_siggo=r['NOME_SIGGO'],tipo_siggo=r['tp_bai'],
                         nome_base_siggo=r['nm_bai'],metodo=method,
                         qualificacao_siggo=r['ql_bai'],geometria_original_valida=r['GEOMETRIA_ORIGINAL_VALIDA'],
                         similaridade_textual=next((score for score,item in ranked if item['OID_SIGGO']==r['OID_SIGGO']),''),
                         equivalencia_territorial_confirmada=False) for r in candidates]


def verify_source(source):
    if sha256(source['arquivo_pdf'])!=source['sha256']:
        raise ValueError('A fonte revisada foi alterada: '+source['arquivo_pdf'])
    if sha256(source['recorte'])!=source['sha256_recorte']:
        raise ValueError('O recorte revisado foi alterado: '+source['recorte'])


def main():
    ROOT.mkdir(parents=True,exist_ok=True)
    annotations=json.loads(ANNOTATIONS.read_text(encoding='utf-8'))
    previous=pd.read_csv('dados/informes_extraidos/bairros.csv',dtype=str,keep_default_na=False)
    previous_elements=pd.read_csv('dados/informes_extraidos/elementos.csv',dtype=str,keep_default_na=False)
    records=[]; audit=[]
    def make_record(source,name,value,indicator,agravo,position,note):
        record={k:source[k] for k in ['arquivo_pdf','sha256','pagina','elemento_id','titulo_original','url_pdf','url_pagina','ano_boletim','se_boletim']}
        record.update(periodo(source['titulo_original']))
        record.update(bairro_rotulo_revisado=name,valor_revisado=int(value),indicador=indicator,agravo=agravo,
                      posicao_linha_barra=position,unidade='casos',municipio_ibge='5208707',
                      revisao_leitura='conferencia_visual_assistente',revisor='assistente',
                      recorte_conferencia=source['recorte'],sha256_recorte=source['sha256_recorte'],
                      nota_conferencia=note,
                      revisao_id=f"REV:{source['elemento_id']}:{position}:{indicator}",
                      abrangencia='lista_publicada_nao_comprova_todos_os_bairros',
                      pode_somar_entre_boletins=False,apto_ranking_completo_ou_taxa=False)
        record['status_periodo']='a_confirmar' if record['natureza_temporal']=='nao_explicita' else (
                                   'divergencia_na_legenda' if record['alerta_periodo'] else 'janela_declarada_na_fonte')
        record['alertas_fonte']='rotulo_truncado_na_fonte' if '...' in name else ''
        records.append(record)
    for se,review in annotations['graficos_2026'].items():
        source=review['fonte']; verify_source(source)
        assert len(review['bairros'])==len(review['valores'])==10
        for position,(name,value) in enumerate(zip(review['bairros'],review['valores']),1):
            make_record(source,name,value,'casos_notificados','dengue',position,review.get('nota',''))
        old=previous[previous.elemento_id.eq(source['elemento_id'])].copy()
        if len(old):
            old['_x']=old.bbox_valor.map(lambda value:json.loads(value)[0])
            old=old.sort_values('_x')
        status=previous_elements.loc[previous_elements.elemento_id.eq(source['elemento_id']),'status'].iloc[0]
        audit.append(dict(elemento_id=source['elemento_id'],ano=2026,edicao=int(se),pagina=3,agravo='dengue',
                          registros_antes=len(old),registros_revisados=10,registros_recuperados=10-len(old),
                          situacao_extracao_anterior=status,
                          grafias_corrigidas_com_ordem_verificavel=sum(a!=b for a,b in zip(old.bairro,review['bairros'])) if len(old)==10 else '',
                          sequencia_valores_antes=json.dumps(old.valor.astype(int).to_list()),
                          sequencia_valores_conferida=json.dumps(review['valores']),recorte=source['recorte']))
    for name,review in annotations['tabelas_2024'].items():
        se,agravo=name.split('_'); source=review['fonte']; verify_source(source)
        old=previous[previous.elemento_id.eq(source['elemento_id'])]
        for position,line in enumerate(review['linhas'],1):
            for indicator,value in zip(review['indicadores'],line[1:]):
                matches=old[old.bairro.eq(line[0])&old.indicador.eq(indicator)]
                if len(matches)!=1 or int(matches.iloc[0].valor)!=value:
                    raise ValueError(f'Divergência entre transcrição visual e tabela extraída: {name}, {line[0]}, {indicator}')
                make_record(source,line[0],value,indicator,agravo,position,review.get('nota',''))
        audit.append(dict(elemento_id=source['elemento_id'],ano=2024,edicao=int(se),pagina=review['pagina'],agravo=agravo,
                          registros_antes=len(old),registros_revisados=30,registros_recuperados=0,
                          situacao_extracao_anterior='tabela_bairros_extraida',grafias_corrigidas_com_ordem_verificavel=0,
                          sequencia_valores_antes='',sequencia_valores_conferida='',recorte=source['recorte']))
    base=pd.DataFrame(records)
    for column in ['ano_referencia','se_inicio','se_fim','posicao_linha_barra','valor_revisado']:
        base[column]=pd.to_numeric(base[column],errors='raise').astype('Int64')
    # Coerência entre indicadores do mesmo território, publicação e critério apresentado.
    anomalies=[]
    for (element,name),group in base.groupby(['elemento_id','bairro_rotulo_revisado']):
        values={indicator:int(value) for indicator,value in zip(group.indicador,group.valor_revisado)}
        if 'casos_confirmados' in values and values['casos_confirmados']>values.get('casos_provaveis',float('inf')):
            mask=base.elemento_id.eq(element)&base.bairro_rotulo_revisado.eq(name)
            base.loc[mask,'alertas_fonte']='confirmados_maiores_que_provaveis_no_quadro_publicado'
            anomalies.append(dict(tipo='coerencia_entre_indicadores',elemento_id=element,bairro=name,
                                  evidencia=json.dumps(values,ensure_ascii=False),providencia='Confirmar definição e ordem dos campos; não inverter colunas.'))
    for se,flag in [(19,'confirmar_criterio_edicao19'),(37,'mesma_sequencia_valores_com_rotulos_diferentes_37_38'),(38,'mesma_sequencia_valores_com_rotulos_diferentes_37_38')]:
        mask=base.ano_boletim.eq('2026')&base.se_boletim.eq(str(se))
        base.loc[mask,'alertas_fonte']=base.loc[mask,'alertas_fonte'].apply(lambda value:';'.join(filter(None,[value,flag])))
    for se in [19,35,37]:
        source=annotations['graficos_2026'][str(se)]['fonte']
        anomalies.append(dict(tipo='esclarecimento_de_fonte',elemento_id=source['elemento_id'],bairro='',
                              evidencia=annotations['graficos_2026'][str(se)].get('nota',''),
                              providencia='Solicitar esclarecimento/correção à Saúde sem substituir os dados publicados.'))
    mesh=pd.read_csv(MESH,dtype=str,keep_default_na=False).to_dict('records')
    for row in mesh:
        row['_keys']=mesh_keys(row)
    correspondences=[]; candidates=[]
    for name,count in base.bairro_rotulo_revisado.value_counts().items():
        match,choices=match_name(name,mesh)
        match['numero_observacoes']=int(count)
        refs=base.loc[base.bairro_rotulo_revisado.eq(name),['ano_boletim','se_boletim','pagina']].drop_duplicates()
        match['publicacoes']=json.dumps([f'{r.ano_boletim}/SE{r.se_boletim}/p{r.pagina}' for r in refs.itertuples()],ensure_ascii=False)
        match['pergunta_para_saude']=('Confirmar se o rótulo corresponde integralmente ao polígono SIGGO candidato, indicando código/vigência.'
                                      if match['status_correspondencia']=='nominal_unico_nao_homologado' else
                                      'Informar nome completo, código territorial e limites do rótulo publicado; esclarecer candidatos e etapas.')
        correspondences.append(match); candidates.extend(choices)
    correspondence=pd.DataFrame(correspondences).sort_values('bairro_rotulo_revisado')
    # Um registro por rótulo na tabela principal; as alternativas permanecem em tabela separada.
    base=base.merge(correspondence,on='bairro_rotulo_revisado',how='left',validate='many_to_one')
    assert len(base)==360 and base.revisao_id.is_unique
    unresolved=(base.status_correspondencia.ne('nominal_unico_nao_homologado')|
                base.status_periodo.ne('janela_declarada_na_fonte')|base.alertas_fonte.ne(''))
    outputs={
        'base_territorial_revisada.csv':base,
        'correspondencia_bairros.csv':correspondence,
        'candidatos_siggo.csv':pd.DataFrame(candidates),
        'pendencias_territoriais.csv':correspondence[correspondence.status_correspondencia.ne('nominal_unico_nao_homologado')],
        'observacoes_com_pendencias.csv':base[unresolved],
        'auditoria_revisao.csv':pd.DataFrame(audit),
        'inconsistencias_fonte.csv':pd.DataFrame(anomalies)}
    from pipeline.processamento.lacunas_saude import lacunas
    outputs['lista_lacunas_para_sms.csv']=lacunas()
    for filename,frame in outputs.items():
        frame.to_csv(ROOT/filename,index=False,encoding='utf-8-sig')
    report=dict(gerado_em=now(),observacoes_antes=len(previous),observacoes_revisadas=len(base),
                registros_recuperados=len(base)-len(previous),graficos_conferidos=24,tabelas_conferidas=4,
                rotulos_distintos=len(correspondence),status_correspondencia=Counter(correspondence.status_correspondencia),
                poligonos_com_candidato_nominal_unico=correspondence.loc[correspondence.OID_SIGGO_candidato.ne(''),'OID_SIGGO_candidato'].nunique(),
                observacoes_por_status_correspondencia=Counter(base.status_correspondencia),
                status_periodo=Counter(base.status_periodo),
                rotulos_truncados_na_fonte=sorted(set(base.loc[base.bairro_rotulo_revisado.str.contains('...',regex=False),'bairro_rotulo_revisado'])),
                linhas_tabela_com_confirmados_maiores_provaveis=sum(a['tipo']=='coerencia_entre_indicadores' for a in anomalies),
                observacoes_com_pendencias=int(unresolved.sum()),
                limites_homologados_pela_saude=0,aptos_ranking_completo_ou_taxas=0,
                regra='Correspondência nominal não comprova equivalência territorial; não ratear população nem duplicar observações.')
    save_json(ROOT/'qualidade.json',report)
    with pd.ExcelWriter(ROOT/'revisao_territorial.xlsx',engine='openpyxl') as writer:
        for filename,frame in outputs.items():
            sheet=filename.replace('.csv','')[:31]
            frame.to_excel(writer,sheet_name=sheet,index=False)
        from openpyxl.styles import Font, PatternFill
        for sheet in writer.book.worksheets:
            sheet.freeze_panes='A2'; sheet.auto_filter.ref=sheet.dimensions
            for cell in sheet[1]:
                cell.font=Font(bold=True,color='FFFFFF'); cell.fill=PatternFill('solid',fgColor='244B61')
            for column in sheet.columns:
                letter=column[0].column_letter
                sheet.column_dimensions[letter].width=min(52,max(15,max(len(str(c.value or '')) for c in list(column)[:60])+2))
    save_json(ROOT/'manifesto.json',dict(gerado_em=now(),fontes=[dict(arquivo=str(path),sha256=sha256(path)) for path in
               [ANNOTATIONS,MESH,Path('dados/informes_extraidos/bairros.csv'),Path('dados/informes_extraidos/elementos.csv')]],
               produtos=[dict(arquivo=str(path),sha256=sha256(path)) for path in sorted(ROOT.glob('*.csv'))]+[
                   dict(arquivo=str(ROOT/'revisao_territorial.xlsx'),sha256=sha256(ROOT/'revisao_territorial.xlsx'))]))
    print(json.dumps(report,ensure_ascii=True),flush=True)


if __name__=='__main__':
    main()
