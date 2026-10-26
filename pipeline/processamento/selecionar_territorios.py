"""Seleção operacional auditável de oito territórios com as bases disponíveis.

Sem downloads ou envio de contatos. Não estima risco nem soma casos entre edições.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import pandas as pd
import geopandas as gpd
from pipeline.processamento.revisar_territorio import key

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'dados/selecao_territorios'
JANELAS = [16, 20, 24, 28, 32, 36]
ALTERNATIVAS = [14, 18, 22, 26, 30, 34]
TOLERANCIA_M = 250
LIMITE_PARCEIRO_M = 3000


def contagens(base, semanas):
    recorte = base.loc[base.se_boletim.isin(semanas)].copy()
    assert recorte.groupby('se_boletim').elemento_id.nunique().eq(1).all()
    periodos = recorte[['se_boletim','se_inicio','se_fim']].drop_duplicates().sort_values('se_inicio')
    assert len(periodos) == len(semanas)
    assert (periodos.se_fim-periodos.se_inicio+1).eq(4).all()
    assert all(periodos.se_inicio.iloc[i] > periodos.se_fim.iloc[i-1] for i in range(1,len(periodos)))
    return recorte


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    inputs = ['dados/base_integrada/bairros_publicados.csv',
        'dados/base_integrada/parceiros_candidatos.csv',
        'dados/malha_municipal/goiania/bairros_municipais_analise.gpkg',
        'dados/cnes/goiania/202609/estabelecimentos.csv']
    b = pd.read_csv(ROOT/inputs[0],dtype={'OID_SIGGO_candidato':str})
    b = b.loc[(b.ano_boletim==2026)&(b.agravo=='dengue')&
        (b.indicador=='casos_notificados')&(b.status_periodo=='janela_declarada_na_fonte')]
    principal = contagens(b,JANELAS)
    alternativo = contagens(b,ALTERNATIVAS)
    elegiveis = principal.loc[principal.status_correspondencia=='nominal_unico_nao_homologado']
    mesh = gpd.read_file(ROOT/inputs[2]).to_crs(31982)
    mesh['oid'] = mesh.OID_SIGGO.astype(str)
    assert mesh.oid.is_unique
    geometries = mesh.set_index('oid').geometry
    names = mesh.set_index('oid').NOME_SIGGO
    index = {}
    bare = {}
    for _, row in mesh.iterrows():
        for field in ['NOME_SIGGO','nm','nm1','nm_bai']:
            index.setdefault(key(row[field]),set()).add(row.oid)
        bare.setdefault(key(row.nm_bai),set()).add(row.oid)
    c = pd.read_csv(ROOT/inputs[1],dtype={'CO_CNES':str})
    c = c.loc[c.tipo_unidade_descricao.isin(['CENTRO DE SAUDE/UNIDADE BASICA','POLICLINICA']) &
              ~c.NO_FANTASIA.str.startswith('DISTRITO SANITARIO')].copy()
    points = gpd.GeoDataFrame(c,geometry=gpd.points_from_xy(c.longitude,c.latitude),crs=4326).to_crs(31982)
    audit = []
    for _, row in points.iterrows():
        label = key(row.NO_BAIRRO)
        matches = index.get(label,set())
        metodo = 'nome_normalizado_unico'
        if not matches and label.split()[0] in ['SETOR','BAIRRO','VILA','JARDIM','PARQUE','RESIDENCIAL','CONJUNTO']:
            matches = bare.get(' '.join(label.split()[1:]),set())
            metodo = 'toponimo_sem_tipo_unico_nao_homologado'
        oid = next(iter(matches)) if len(matches)==1 else None
        distance = float(row.geometry.distance(geometries[oid])) if oid else None
        status = ('sem_correspondencia_unica' if oid is None else
                  'divergencia_espacial_a_verificar' if distance>TOLERANCIA_M else
                  'compatibilidade_exploratoria')
        audit.append({'CO_CNES':row.CO_CNES,'unidade':row.NO_FANTASIA,'bairro_cnes':row.NO_BAIRRO,
            'oid_bairro_cnes_candidato':oid,'metodo_bairro_cnes':metodo if oid else 'sem_correspondencia_unica',
            'distancia_ao_bairro_cadastrado_m':distance,'status_checagem':status})
    audit = pd.DataFrame(audit)
    points = points.merge(audit,on='CO_CNES',validate='one_to_one')
    aptos = points.loc[points.status_checagem=='compatibilidade_exploratoria'].copy()
    assert len(aptos)>0
    contatos = pd.read_csv(ROOT/inputs[3],dtype=str,keep_default_na=False).set_index('CO_CNES')
    pool, pares = [], []
    for oid, rows in elegiveis.groupby('OID_SIGGO_candidato'):
        geometry = geometries[oid]
        unidades = aptos.assign(distancia_territorio_m=aptos.geometry.distance(geometry))
        unidades['ordem_tipo'] = (unidades.tipo_unidade_descricao!='CENTRO DE SAUDE/UNIDADE BASICA').astype(int)
        unidades['dentro_tolerancia'] = unidades.distancia_territorio_m<=TOLERANCIA_M
        # Perto do polígono primeiro; tipo básico desempata, sem inferir área de cobertura.
        unidades = unidades.sort_values(['dentro_tolerancia','ordem_tipo','distancia_territorio_m','CO_CNES'],ascending=[False,True,True,True])
        unidades = unidades.loc[unidades.distancia_territorio_m<=LIMITE_PARCEIRO_M]
        for pos, (_,unit) in enumerate(unidades.iterrows(),1):
            contato = contatos.loc[unit.CO_CNES]
            pares.append({'OID_SIGGO':oid,'territorio':names[oid],'preferencia_parceiro':pos,
                'CO_CNES':unit.CO_CNES,'unidade':unit.NO_FANTASIA,'tipo_unidade':unit.tipo_unidade_descricao,
                'bairro_cnes':unit.NO_BAIRRO,'distancia_minima_poligono_m':round(float(unit.distancia_territorio_m),1),
                'metodo_checagem_bairro_cnes':unit.metodo_bairro_cnes,
                'telefone_cadastral':contato.NU_TELEFONE,'logradouro_cadastral':contato.NO_LOGRADOURO,
                'numero_cadastral':contato.NU_ENDERECO,'status_parceria':'nao_contatada',
                'funcionamento':'nao_verificado','area_abrangencia':'nao_verificada'})
        pool.append({'OID_SIGGO':oid,'territorio':names[oid],
            'janelas_com_citacao':rows.se_boletim.nunique(), 'janelas_observadas':len(JANELAS),
            'edicoes_citadas':';'.join(str(v) for v in sorted(rows.se_boletim.unique())),
            'ultima_edicao_citada':int(rows.se_boletim.max()),
            'janelas_alternativas_com_citacao':int(alternativo.loc[(alternativo.OID_SIGGO_candidato==oid)&(alternativo.status_correspondencia=='nominal_unico_nao_homologado')].se_boletim.nunique()),
            'parceiros_ate_3km_do_poligono':len(unidades),
            'menor_distancia_parceiro_m':round(float(unidades.distancia_territorio_m.min()),1) if len(unidades) else None})
    pool = pd.DataFrame(pool).sort_values(['janelas_com_citacao','ultima_edicao_citada','OID_SIGGO'],ascending=[False,False,True])
    pool['elegivel_planejamento'] = pool.parceiros_ate_3km_do_poligono>0
    selecionados = pool.loc[pool.elegivel_planejamento].head(8).copy()
    assert len(selecionados)==8
    pares = pd.DataFrame(pares)
    first = pares.loc[pares.preferencia_parceiro==1].drop(columns=['territorio'])
    selecionados = selecionados.merge(first,on='OID_SIGGO',validate='one_to_one')
    selecionados['parceiro_compartilhado'] = selecionados.CO_CNES.duplicated(keep=False)
    selecionados['prioridade_articulacao'] = selecionados.distancia_minima_poligono_m.le(TOLERANCIA_M).map({True:'primeira_rodada',False:'segunda_rodada_condicional'})
    selecionados['status_selecao'] = 'proposta_operacional_condicionada'
    selecionados['justificativa'] = selecionados.apply(lambda r:
        f'Citado em {r.janelas_com_citacao}/6 janelas não sobrepostas; em {r.janelas_alternativas_com_citacao}/6 na janela alternativa. '
        f'Candidato nominal SIGGO {r.OID_SIGGO}. Parceiro candidato: {r.unidade}; distância mínima ao polígono {r.distancia_minima_poligono_m:.0f} m. '
        'Contato, funcionamento, espaço e deslocamento não confirmados.',axis=1)
    selecionados['atividade_proposta'] = 'Encontro educativo e escuta comunitária; roteiro de observação ambiental em espaço acordado com o parceiro'
    selecionados['pendencia_liberacao'] = 'Confirmar interesse do parceiro, funcionamento, local, acessibilidade, percurso, recursos e agenda'
    selecionados['data_acao'] = ''
    selecionados['custo_estimado'] = ''
    selecionados['responsavel_confirmado'] = ''
    selecionados = selecionados.sort_values(['prioridade_articulacao','janelas_com_citacao','territorio'],ascending=[True,False,True])
    selecionados.insert(0,'ordem_articulacao',range(1,9))
    pool['selecionado'] = pool.OID_SIGGO.isin(selecionados.OID_SIGGO)
    pool['motivo_decisao'] = pool.apply(lambda r: 'selecionado' if r.selecionado else
        'sem_parceiro_no_recorte_geografico' if not r.elegivel_planejamento else 'reserva_menor_recorrencia_nas_listas',axis=1)
    evidencias = principal.copy()
    evidencias['selecionado'] = evidencias.OID_SIGGO_candidato.isin(selecionados.OID_SIGGO)
    reservas = pool.loc[~pool.selecionado].copy()
    checks = pd.DataFrame([
        ['interesse_parceiro','Não contatado; registrar aceite ou recusa sem presumir parceria.'],
        ['local_e_acessibilidade','Confirmar endereço, espaço, acessibilidade e autorização para uso.'],
        ['deslocamento','Conferir ponto de partida e rota real; distância geométrica não estima caminhada, trânsito nem custo.'],
        ['capacidade','Projeto com execução solo; uma ação por vez. Compartilhamento de unidade não comprova capacidade para vários territórios.'],
        ['recursos','Definir orçamento e materiais antes de anunciar a atividade.'],
        ['avaliacao','Registrar ações, participantes e materiais reais; não atribuir redução de casos à intervenção.'],
    ],columns=['pendencia','como_verificar'])
    tabelas={'oito_territorios':selecionados,'candidatos_e_reservas':pool,
        'parceiros_candidatos':pares,'auditoria_geolocalizacao':audit,
        'evidencias_janelas':evidencias,'liberacao_de_atividades':checks}
    for name,df in tabelas.items():
        df.to_csv(OUT/f'{name}.csv',index=False,encoding='utf-8-sig')
    with pd.ExcelWriter(OUT/'selecao_e_plano.xlsx',engine='openpyxl') as writer:
        for name,df in tabelas.items():
            df.to_excel(writer,sheet_name=name[:31],index=False)
            sheet=writer.sheets[name[:31]]
            sheet.freeze_panes='A2'
            sheet.auto_filter.ref=sheet.dimensions
            for column in sheet.columns:
                sheet.column_dimensions[column[0].column_letter].width=min(55,max(18,len(str(column[0].value))+2))
    alt_set=set(pool.sort_values(['janelas_alternativas_com_citacao','ultima_edicao_citada','OID_SIGGO'],ascending=[False,False,True]).loc[pool.elegivel_planejamento].head(8).OID_SIGGO)
    manifest={'gerado_em':datetime.now(timezone.utc).isoformat(),'metodo':'pipeline/processamento/selecionar_territorios.py',
        'janelas_principais':JANELAS,'janelas_alternativas':ALTERNATIVAS,
        'periodo_principal':'2026 SE13–36','periodo_alternativo':'2026 SE11–34',
        'tolerancia_espacial_exploratoria_m':TOLERANCIA_M,'raio_planejamento_a_partir_do_poligono_m':LIMITE_PARCEIRO_M,
        'selecionados':len(selecionados),'mesmos_oito_na_alternativa':set(selecionados.OID_SIGGO)==alt_set,
        'checagem_cnes':audit.status_checagem.value_counts().to_dict(),
        'fontes':[{'arquivo':f,'sha256':hashlib.sha256((ROOT/f).read_bytes()).hexdigest()} for f in inputs],
        'limitacoes':['Não mede risco, incidência ou cobertura assistencial.','Distâncias a polígonos nominais em EPSG31982; não são rotas.','Recorrência significa presença em listas selecionadas, nunca soma de casos.','Dados municipais de escorpiões não permitem justificar maior risco por bairro.','Viabilidade operacional, custos, recursos e aceites permanecem desconhecidos.']}
    (OUT/'manifesto.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    linhas=['# Oito territórios propostos para atuação','',
        'Seleção operacional condicionada às verificações locais. A ordem abaixo organiza os contatos; não é ranking de risco nem cronograma confirmado.','',
        '## Critérios e recorte','',
        'Dengue: seis listas de notificações dos informes de 2026, edições SE16, 20, 24, 28, 32 e 36. Cada lista descreve quatro semanas; as janelas vão de SE13 a SE36 e não se sobrepõem. Contamos em quantas listas o território aparece, sem somar seus casos. A última edição utilizável é SE36: SE37/38 repetem valores com rótulos diferentes e SE35 tem legenda temporal divergente. O ano de 2024 não entra nesta seleção porque o período das tabelas não está esclarecido.','',
        'Só entram correspondências nominais únicas, ainda sem homologação de limites. Entre os territórios com parceiros candidatos até 3 km do polígono, priorizamos maior presença nas seis listas; a última edição citada e o OID desempatam. O limite de 3 km e a tolerância cadastral de 250 m são escolhas operacionais exploratórias, sem comprovar acessibilidade ou distância entre moradores e unidades.','',
        'As janelas alternativas terminam em SE14, 18, 22, 26, 30 e 34. Os mesmos oito territórios foram selecionados: '+str(manifest['mesmos_oito_na_alternativa'])+'. Essa verificação não elimina o viés das listas publicadas.','',
        'Para os parceiros, usamos centros/unidades básicas e policlínicas públicas, sem motivo cadastral de desativação e dentro da malha municipal. Distritos sanitários classificados como unidade básica são excluídos pelo nome. A posição é confrontada com o bairro cadastrado; divergências ou nomes sem correspondência única não são usados como prova de proximidade. Correspondências sem o tipo territorial ficam identificadas como exploratórias.','',
        '## Territórios, evidências e parceiros','',
        '| Ordem de contato | Território SIGGO candidato | Listas principal / alternativa | Parceiro candidato | Distância mínima ao polígono |','|---|---|---|---|---|']
    for _,r in selecionados.iterrows():
        linhas.append(f'| {r.ordem_articulacao} | {r.territorio} | {r.janelas_com_citacao}/6 · {r.janelas_alternativas_com_citacao}/6 | {r.unidade} (CNES {r.CO_CNES}) | {r.distancia_minima_poligono_m:.0f} m |')
    linhas += ['', 'Os nomes acima seguem a malha SIGGO candidata. As grafias literais dos informes e os links de página estão na aba evidencias_janelas. Distância zero significa ponto cadastral dentro do polígono; não significa deslocamento zero. Não pressupomos que a unidade atenda aquele território.', '',
        '## Execução proposta','',
        'Começar pela primeira rodada de articulação, com os parceiros situados dentro ou até 250 m do polígono, e realizar uma atividade por vez. Após a primeira atividade, revisar esforço, participação e materiais antes de ampliar. A segunda rodada depende especialmente da confirmação do deslocamento e da abrangência das unidades externas ao território.','',
        'A atividade inicial proposta é um encontro educativo e de escuta, seguido, se houver condições e acordo local, de observação ambiental no espaço definido. Não estão previstos manejo de animais, aplicação de produtos ou coleta de dados clínicos. Materiais de prevenção devem passar pela revisão técnica do parceiro. O endereço e telefone cadastrais estão na planilha para conferência; nenhum contato foi enviado.','',
        'CS Finsocial aparece como parceira candidata de Vila Finsocial e Jardim Nova Esperança. Registrar disponibilidade por ação e manter alternativas; não reservar capacidade nem duplicar público atendido entre atividades. A data, o orçamento, os percursos e os responsáveis não foram inventados e permanecem em branco.','',
        'Se houver recusa ou inviabilidade, consultar outro parceiro da aba parceiros_candidatos; se o território continuar inviável, usar a ordem de reserva da aba candidatos_e_reservas. A ausência de um bairro nas seis listas não demonstra ausência de casos. Jardim Curitiba I permanece fora por identificação territorial ambígua, embora apareça nas listas.','',
        '## Ajuste necessário na justificativa do projeto','',
        'Substituir “8 bairros mais urgentes” por “oito territórios priorizados para um piloto, com base na presença recorrente nas listas públicas de dengue, na identificação territorial disponível e em parceiros candidatos para articulação local”. Não há evidência territorial suficiente para dizer que esses oito têm maior risco de acidentes com escorpiões. O tema pode integrar as atividades educativas, sem afirmar priorização epidemiológica por bairro.','',
        'A população do Censo 2022 e as variáveis climáticas da estação municipal não foram usadas para ordenar bairros. Não permitem inferir vulnerabilidade, saneamento ou microclima destes territórios sem outra metodologia.','',
        '## Reprodução e fontes','',
        'Executar na raiz: .venv/Scripts/python.exe -m pipeline.processamento.selecionar_territorios. Insumos, hashes e parâmetros estão em dados/selecao_territorios/manifesto.json. Fontes: dados/base_integrada/bairros_publicados.csv; parceiros_candidatos.csv; malha municipal SIGGO de análise; CNES competência 202609. Não houve nova coleta nem contato externo.']
    (ROOT/'docs/SELECAO-TERRITORIOS.md').write_text('\n'.join(linhas)+'\n',encoding='utf-8')
    print(selecionados[['ordem_articulacao','territorio','janelas_com_citacao','janelas_alternativas_com_citacao','unidade','distancia_minima_poligono_m']].to_string(index=False))
    print(json.dumps(manifest['checagem_cnes'],ensure_ascii=False))


if __name__=='__main__':
    main()
