"""Produz o snapshot público do painel a partir da integração local."""
from pathlib import Path
import argparse
import json
import pandas as pd
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'dados/base_integrada'


def snapshot(concluir=False):
    queries = {}
    manifesto = json.loads((BASE / 'manifesto.json').read_text(encoding='utf-8'))
    for key, filename, definition in [
        ('municipal', 'municipal_mensal_clima', 'Registros SINAN, todas as classificações: dengue por residência e mês da notificação; escorpiões por ocorrência e mês do acidente. Não são pessoas únicas. Ausência não é zero. 2026 parcial; meses com registros podem estar incompletos. Clima A002 em UTC.'),
        ('territorios', 'bairros_publicados', 'Lista publicada por edição, agravo e indicador; janelas sobrepostas não são somadas. Não comprova todos os bairros. Correspondência SIGGO nominal, sem homologação dos limites. Não permite taxas nem ranking municipal completo.'),
        ('clima', 'clima_mensal', 'Estação A002; calendário UTC. Chuva observada pode ser parcial. Médias de temperatura e umidade são horárias, com cobertura explícita. Não atribui causalidade nem diferenças climáticas entre bairros.'),
        ('parceiros', 'parceiros_candidatos', 'Cadastros públicos sem motivo de desativação registrado e coordenadas dentro da malha municipal. Competência setembro de 2026. Funcionamento e interesse em parceria precisam ser verificados.'),
        ('censo', 'contexto_censo_2022', 'População do Censo 2022, sem estimativa para 2026 nem rateio por bairro.'),
    ]:
        path = BASE / f'{filename}.csv'
        df = pd.read_csv(path, dtype={'CO_CNES': str, 'OID_SIGGO_candidato': str})
        if key in ('municipal', 'clima'):
            df['ano'] = df['mes' if key == 'municipal' else 'periodo_utc'].str[:4]
            df['data'] = df['mes' if key == 'municipal' else 'periodo_utc'] + '-01'
        if key == 'territorios':
            df['edicao'] = df.ano_boletim.astype(str) + '/SE' + df.se_boletim.astype(str).str.zfill(2)
            df['situacao_periodo_legivel'] = df.status_periodo.map({
                'janela_declarada_na_fonte': 'Janela declarada na fonte',
                'divergencia_na_legenda': 'Divergência na legenda', 'a_confirmar': 'Período não esclarecido'})
            df['correspondencia_legivel'] = df.status_correspondencia.map({
                'nominal_unico_nao_homologado': 'Candidato nominal único',
                'pendente_identificacao_territorial': 'Identificação pendente',
                'rotulo_truncado_na_fonte': 'Nome truncado na fonte'})
        if key == 'municipal':
            df['situacao_legivel'] = df.situacao_fonte.map({'FINAIS':'Final','PRELIM':'Preliminar'})
            df['recorte_legivel'] = df.referencia_geografica.map({'residencia':'Residência','ocorrencia':'Ocorrência'})
            df['data_legivel'] = df.campo_data.map({'DT_NOTIFIC':'Notificação','ANT_DT_ACI':'Acidente'})
        if key == 'parceiros':
            # Não enviar endereços residenciais de prestadores privados: só o recorte público.
            df = df.drop(columns=['NO_LOGRADOURO', 'NU_ENDERECO'])
            df['situacao_operacional'] = 'Verificar funcionamento e parceria'
        rows = json.loads(df.to_json(orient='records', force_ascii=False))
        queries[key] = {'rows': rows, 'source': {
            'name': filename, 'provider': 'Arquivos públicos locais revisados',
            'files': [path.relative_to(ROOT).as_posix()],
            'description': definition,
            'dataPreparedAt': manifesto['gerado_em'],
            'metricDefinitions': [{'label': filename.replace('_', ' '), 'definition': definition}],
            'evidenceFlow': [{'title': 'Reprodução local', 'detail': 'Executar python -m pipeline na raiz do projeto. Insumos e hashes em dados/base_integrada/manifesto.json.'}],
            'caveats': [definition],
        }, 'methods': [{'language': 'text', 'code': 'Ler CSV integrado; preservar todas as linhas e nulos; derivar ano e data mensal para exibição. Bairros: derivar edição de ano_boletim e se_boletim. Filtrar somente na interface, sem somar publicações.'}]}
    selecao = ROOT / 'dados/selecao_territorios/oito_territorios.csv'
    if selecao.exists():
        cols = ['ordem_articulacao','territorio','janelas_com_citacao',
            'janelas_alternativas_com_citacao','unidade','CO_CNES','distancia_minima_poligono_m',
            'prioridade_articulacao','justificativa','pendencia_liberacao','parceiro_compartilhado']
        selecionados = pd.read_csv(selecao, dtype={'CO_CNES':str})[cols]
        selecionados['prioridade_legivel'] = selecionados.prioridade_articulacao.map({
            'primeira_rodada':'Primeira rodada de contatos',
            'segunda_rodada_condicional':'Segunda rodada condicionada'})
        queries['selecao'] = {'rows':json.loads(selecionados.to_json(orient='records',force_ascii=False)),
            'source':{'name':'Seleção operacional de territórios', 'provider':'Análise das bases públicas locais',
                'files':[selecao.relative_to(ROOT).as_posix(),'dados/selecao_territorios/manifesto.json'],
                'metricDefinitions':[{'label':'Presença nas listas', 'definition':'Número de listas com citação do território nas edições SE16,20,24,28,32,36 de 2026; seis janelas de quatro semanas sem sobreposição. Alternativa: SE14,18,22,26,30,34. Não mede risco nem soma casos.'},
                    {'label':'Parceiro e distância','definition':'Unidade pública candidata com compatibilidade geográfica exploratória do bairro cadastrado. Distância mínima entre ponto e polígono nominal em EPSG31982; não é trajeto nem cobertura assistencial. Funcionamento, aceite, espaço, custos e acesso não confirmados.'}],
                'evidenceFlow':[{'title':'Reprodução','detail':'Executar python -m pipeline (etapas selecionar_territorios e verificar_selecao). Fontes e hashes no manifesto de seleção. Plano e justificativa em SELECAO-TERRITORIOS.md.'}]
            }, 'methods':[{'language':'text','code':'pipeline/processamento/selecionar_territorios.py: filtrar edições e correspondências nominais; contar edições distintas; confrontar bairro CNES e coordenadas com malha SIGGO; excluir divergências; selecionar oito por presença nas listas e parceiros candidatos até 3 km do polígono. Nenhuma parceria ou agenda confirmada.'}]}
    mapa = ROOT / 'dados/mapa/camadas.json'
    if mapa.exists():
        meta = json.loads((ROOT / 'dados/mapa/manifesto.json').read_text(encoding='utf-8'))
        queries['mapa'] = {'rows': json.loads(mapa.read_text(encoding='utf-8')),
            'source': {'name': 'Mapa dos territórios', 'provider': 'Malhas IBGE 2022 e SIGGO; CNES 202609; seleção operacional',
                'files': [mapa.relative_to(ROOT).as_posix(), 'dados/mapa/manifesto.json'],
                'dataPreparedAt': meta['gerado_em'],
                'metricDefinitions': [
                    {'label': 'Geometria', 'definition': f"SIRGAS 2000 / UTM 22S (EPSG:31982), coordenadas em metros a partir do canto noroeste do limite municipal. Simplificação de exibição: {meta['simplificacao_m']['bairros']} m nos bairros e {meta['simplificacao_m']['limite']} m no limite. Distâncias e escala são reais; contornos simplificados não servem para medir área."},
                    {'label': 'Presença nas listas', 'definition': 'Somente para os 15 territórios com correspondência nominal única e elegíveis na seleção: número de listas de dengue de 2026 (SE16 a SE36, janelas sem sobreposição) que citam o território. Bairros sem cor não foram citados ou não têm correspondência única; isso não significa zero casos.'},
                    {'label': 'Unidades', 'definition': 'Cadastros CNES públicos sem motivo de desativação e com coordenadas dentro da malha. Funcionamento, abrangência e interesse em parceria não confirmados.'}],
                'evidenceFlow': [{'title': 'Reprodução', 'detail': 'Executar python -m pipeline (etapa preparar_mapa). Fontes e hashes em dados/mapa/manifesto.json.'}],
                'caveats': ['A correspondência entre os nomes dos informes e os polígonos SIGGO é nominal e não homologada pela Secretaria.', 'O mapa não representa risco, incidência nem área de abrangência das unidades.']},
            'methods': [{'language': 'text', 'code': 'pipeline/processamento/preparar_mapa.py: projetar malhas e pontos para EPSG:31982; dissolver setores IBGE no limite municipal; simplificar com preservação de topologia; converter em caminhos SVG; associar presença nas listas e parceiro candidato pelo OID SIGGO e CNES.'}]}
    nowcast = ROOT / 'dados/modelagem/nowcast_dengue.csv'
    if nowcast.exists():
        meta = json.loads((ROOT / 'dados/modelagem/nowcast_dengue_manifesto.json').read_text(encoding='utf-8'))
        fonte_nowcast = {'name': 'Nowcasting de dengue', 'provider': 'Modelo local sobre microdados SINAN',
            'files': ['dados/modelagem/nowcast_dengue.csv', 'dados/modelagem/nowcast_dengue_avaliacao.csv', 'dados/modelagem/nowcast_dengue_manifesto.json'],
            'dataPreparedAt': meta['gerado_em'],
            'metricDefinitions': [
                {'label': 'Observado', 'definition': meta['descricao'] + f", digitadas até a semana de {meta['data_corte_semana_digitacao']}."},
                {'label': 'Estimado', 'definition': 'Total esperado quando as digitações atrasadas chegarem: observado multiplicado pelos fatores de atraso das 20 coortes mais recentes (chain-ladder). Não é previsão de semanas futuras.'},
                {'label': 'Faixa', 'definition': 'Quantis 2,5% e 97,5% da razão entre o total final e a estimativa nas avaliações retrospectivas anteriores; a taxa de acerto medida aparece na tabela de avaliação.'}],
            'evidenceFlow': [{'title': 'Avaliação retrospectiva', 'detail': f"{meta['avaliacao']['cortes']} datas de corte de {meta['avaliacao']['primeiro_corte']} a {meta['avaliacao']['ultimo_corte']}, reconstruindo o que estava digitado em cada uma."}],
            'caveats': meta['limitacoes']}
        metodo = [{'language': 'text', 'code': 'pipeline/modelagem/nowcast.py: semanas epidemiológicas (domingo); triângulo início x atraso de digitação; fatores de desenvolvimento nas 20 coortes recentes; faixas pelos erros retrospectivos já conhecidos em cada data.'}]
        queries['nowcast'] = {'rows': json.loads(pd.read_csv(nowcast).to_json(orient='records', force_ascii=False)), 'source': fonte_nowcast, 'methods': metodo}
        avaliacao = pd.read_csv(ROOT / 'dados/modelagem/nowcast_dengue_avaliacao.csv')
        queries['nowcast_avaliacao'] = {'rows': json.loads(avaliacao.to_json(orient='records', force_ascii=False)), 'source': fonte_nowcast, 'methods': metodo}
    previsao = ROOT / 'dados/modelagem/previsao_dengue.csv'
    if previsao.exists():
        meta = json.loads((ROOT / 'dados/modelagem/previsao_dengue_manifesto.json').read_text(encoding='utf-8'))
        fonte_previsao = {'name': 'Previsão de dengue (1 a 8 semanas)', 'provider': 'Modelo local sobre microdados SINAN e INMET A002',
            'files': ['dados/modelagem/previsao_dengue.csv', 'dados/modelagem/previsao_dengue_avaliacao.csv', 'dados/modelagem/previsao_dengue_manifesto.json'],
            'dataPreparedAt': meta['gerado_em'],
            'metricDefinitions': [
                {'label': 'Referências', 'definition': 'Repetir a média das últimas 4 semanas (corrigidas pelo nowcasting) e repetir a mesma semana do ano anterior.'},
                {'label': 'Modelo', 'definition': 'Regressão ridge no logaritmo das contagens, por horizonte: nível e tendência recentes, sazonalidade e, na versão com clima, chuva, temperatura e umidade médias por hora válida das semanas A-9 a A-2.'},
                {'label': 'Regra de exibição', 'definition': meta['avaliacao']['regra']}],
            'evidenceFlow': [{'title': 'Avaliação retrospectiva', 'detail': f"{meta['avaliacao']['origens']} origens semanais de {meta['avaliacao']['primeira_origem']} a {meta['avaliacao']['ultima_origem']}, usando em cada uma só os dados disponíveis naquela data."}],
            'caveats': meta['limitacoes']}
        metodo_previsao = [{'language': 'text', 'code': 'pipeline/modelagem/previsao.py'}]
        atual = pd.read_csv(previsao)
        queries['previsao'] = {'rows': json.loads(atual[atual.exibir].to_json(orient='records', force_ascii=False)), 'source': fonte_previsao, 'methods': metodo_previsao}
        queries['previsao_avaliacao'] = {'rows': json.loads(pd.read_csv(ROOT / 'dados/modelagem/previsao_dengue_avaliacao.csv').to_json(orient='records', force_ascii=False)), 'source': fonte_previsao, 'methods': metodo_previsao}
    from pipeline import acoes_campo
    acoes = acoes_campo.atuais()
    queries['acoes'] = {'rows': acoes, 'source': {'name': 'Ações de campo', 'provider': 'Registro local da equipe do projeto',
        'files': ['dados/acoes_campo/registros.jsonl', 'dados/acoes_campo/acoes.csv'],
        'dataPreparedAt': max((r['registrado_em'] for r in acoes), default=None),
        'metricDefinitions': [
            {'label': 'Ações realizadas', 'definition': 'Registros cuja versão atual tem situação "realizada".'},
            {'label': 'Participantes', 'definition': 'Soma das contagens informadas nas ações realizadas; não identifica pessoas únicas.'},
            {'label': 'Materiais distribuídos', 'definition': 'Soma das quantidades informadas; ações sem contagem ficam fora da soma, sem zero.'}],
        'evidenceFlow': [{'title': 'Registro', 'detail': 'Formulário do painel servido por python -m pipeline.servidor; cada gravação acrescenta uma versão em registros.jsonl.'}],
        'caveats': ['Indicadores de execução e alcance; não demonstram efeito das ações sobre os casos.']},
        'methods': [{'language': 'text', 'code': 'pipeline/acoes_campo.py: validar campos e referências (malha SIGGO, CNES); acrescentar versão; estado atual = última versão de cada id.'}]}
    result = {'surface': 'dashboard', 'title': 'Saúde no Território · Goiânia',
        'generatedAt': datetime.now(timezone.utc).isoformat(), 'status': 'observed',
        'buildStatus': 'creating', 'filters': [
            {'id': 'ano', 'label': 'Ano', 'field': 'ano', 'defaultValue': '2026', 'queryIds': ['municipal', 'clima']},
            {'id': 'edicao', 'label': 'Publicação', 'field': 'edicao', 'defaultValue': '2026/SE38', 'queryIds': ['territorios']},
            {'id': 'agravo', 'label': 'Agravo', 'field': 'agravo', 'defaultValue': 'dengue', 'queryIds': ['territorios']},
            {'id': 'indicador', 'label': 'Indicador', 'field': 'indicador', 'defaultValue': 'casos_notificados', 'queryIds': ['territorios']},
        ], 'queries': queries}
    target = ROOT / 'dados/painel_snapshot.json'
    if (ROOT / 'painel/src/data.json').exists():
        old = json.loads((ROOT / 'painel/src/data.json').read_text(encoding='utf-8'))
        result['id'] = old['id']
        result['buildStatus'] = 'complete' if concluir else 'updating'
        target = ROOT / 'painel/src/data.json'
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(target)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--concluir', action='store_true', help='marca o snapshot como revisado (usado pelo pipeline após as verificações)')
    snapshot(parser.parse_args().concluir)
