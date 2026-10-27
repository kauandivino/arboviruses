"""Integra as bases locais sem depender de dados adicionais da Secretaria.

Execute na raiz: .venv/Scripts/python.exe -m pipeline.processamento.integrar_bases.
Não baixa arquivos, não soma informes e não distribui população por bairro.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import pandas as pd

from pipeline.comum.referencias import CNES_ESTABELECIMENTOS
from pipeline.comum.epidemiologia import AGRAVOS, GOIANIA, anos_com_arquivo, janela_arquivo

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'dados/base_integrada'


def construir_serie(df, ano, agravo):
    """Série mensal de um arquivo anual, a partir dos microdados; sem preencher zeros.

    Inclui as notificações de Goiânia com data de notificação na janela do arquivo
    (ano civil e ano epidemiológico) e conta pelo mês da data de referência do agravo.
    """
    cfg = AGRAVOS[agravo]
    recorte = df.loc[df[cfg['municipio']] == GOIANIA]
    inicio, fim = janela_arquivo(ano)
    notificacao = pd.to_datetime(recorte.DT_NOTIFIC, errors='coerce')
    evento = pd.to_datetime(recorte[cfg['data']], errors='coerce')
    motivo = pd.Series(None, index=recorte.index, dtype=object)
    motivo[evento.isna()] = 'data_de_referencia_ausente'
    motivo[motivo.isna() & ~notificacao.between(inicio, fim)] = 'notificacao_fora_da_janela_do_arquivo'
    motivo[motivo.isna() & (evento < pd.Timestamp('2022-01-01'))] = 'evento_anterior_a_2022'
    mes = evento.dt.strftime('%Y-%m').fillna('SEM_DATA_VALIDA')
    incluidos = mes[motivo.isna()]
    serie = incluidos.value_counts().rename_axis('mes').rename('n_registros').reset_index().sort_values('mes', ignore_index=True)
    excluidos = pd.DataFrame({'mes': mes[motivo.notna()], 'motivo': motivo[motivo.notna()]})
    excluidos = excluidos.value_counts().rename('n_registros').reset_index()
    assert int(serie.n_registros.sum()) + int(excluidos.n_registros.sum()) == len(recorte)
    return serie, excluidos


def sobreposicao_entre_arquivos(quadros):
    """Notificações idênticas em dois arquivos anuais (nas janelas sobrepostas) seriam contadas duas vezes."""
    vistos = pd.concat([q.assign(_ano=ano) for ano, q in quadros.items()], ignore_index=True)
    colunas = [c for c in vistos.columns if c != '_ano']
    repetidos = vistos[vistos.duplicated(colunas, keep=False)]
    return int((repetidos.groupby(colunas, dropna=False)._ano.nunique() > 1).sum())


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    fontes = []

    def ler(rel):
        path = ROOT / rel
        raw = path.read_bytes()
        fontes.append({'arquivo': rel, 'sha256': hashlib.sha256(raw).hexdigest()})
        return pd.read_csv(path, dtype=str, keep_default_na=False)

    series, auditoria = [], []
    for agravo, cfg in AGRAVOS.items():
        quadros = {}
        for ano in anos_com_arquivo(2022, lambda a: ROOT / cfg['arquivo'].format(ano=a)):
            rel = cfg['arquivo'].format(ano=ano)
            df = ler(rel)
            quadros[ano] = df
            agregado, excluidos = construir_serie(df, ano, agravo)
            qualidade = ROOT / f"dados/datasus/qualidade/{'dengue' if agravo == 'dengue' else 'animais'}_{ano}.json"
            metadata = json.loads(qualidade.read_text(encoding='utf-8'))
            fontes.append({'arquivo': qualidade.relative_to(ROOT).as_posix(),
                           'sha256': hashlib.sha256(qualidade.read_bytes()).hexdigest()})
            series.append(agregado.assign(ano_arquivo=str(ano), situacao_fonte=metadata['situacao'], arquivo_origem=rel))
            for _, linha in excluidos.iterrows():
                auditoria.append({'arquivo': rel, 'mes': linha.mes, 'n_registros': int(linha.n_registros), 'motivo': linha.motivo,
                                  'referencia_geografica': cfg['referencia'], 'campo_data': cfg['data']})
        repetidas = sobreposicao_entre_arquivos(quadros)
        assert repetidas == 0, f'{repetidas} notificações de {agravo} aparecem em mais de um arquivo anual'
        n = len(quadros)
        partes = pd.concat(series[-n:], ignore_index=True)
        series[-n:] = [partes.groupby('mes', as_index=False).agg(
            n_registros=('n_registros', 'sum'), ano_arquivo=('ano_arquivo', ';'.join),
            situacao_fonte=('situacao_fonte', lambda s: 'PRELIM' if 'PRELIM' in set(s) else 'FINAIS'),
            arquivo_origem=('arquivo_origem', ';'.join)).assign(
            agravo=agravo, referencia_geografica=cfg['referencia'], campo_data=cfg['data'])]

    municipal = pd.concat(series, ignore_index=True)
    assert not municipal.duplicated(['agravo', 'mes']).any()
    clima = ler('dados/inmet/goiania/mes_utc.csv')
    assert not clima.periodo_utc.duplicated().any()
    # Left join mantém a série epidemiológica; meses sem clima ficam ausentes.
    mensal = municipal.merge(clima, left_on='mes', right_on='periodo_utc',
                             how='left', validate='many_to_one')
    assert len(mensal) == len(municipal)
    bairros = ler('dados/revisao_territorial/base_territorial_revisada.csv')
    assert bairros.revisao_id.is_unique
    assert set(bairros.pode_somar_entre_boletins) == {'False'}
    setores = ler('dados/ibge/goiania/basico_setores_2022.csv')
    assert setores.CD_SETOR.is_unique
    populacao = pd.to_numeric(setores.V0001, errors='raise')
    cnes = ler(CNES_ESTABELECIMENTOS)
    parceiros = cnes.loc[(cnes.natureza_administracao_publica == 'True') &
                         (cnes.possui_motivo_desativacao == 'False') &
                         (cnes.checagem_municipal == 'dentro_malha_2022'), [
        'CO_CNES', 'NO_FANTASIA', 'tipo_unidade_descricao', 'NO_BAIRRO',
        'NO_LOGRADOURO', 'NU_ENDERECO', 'latitude', 'longitude', 'competencia',
        'natureza_administracao_publica', 'possui_motivo_desativacao',
        'checagem_municipal']].copy()
    parceiros['situacao_operacional'] = 'funcionamento_e_parceria_a_verificar'
    contexto = pd.DataFrame([{'ano_referencia': 2022, 'municipio_ibge': '5208707',
        'populacao_censo': int(populacao.sum()), 'numero_setores': len(setores),
        'uso': 'contexto_municipal_2022_sem_rateio_por_bairro'}])
    definicoes = pd.DataFrame([
        ['serie_mensal', 'Registros SINAN; dengue por residência e mês da notificação; escorpiões por ocorrência e mês do acidente. Todas as classificações. Não são pessoas únicas nem apenas casos confirmados.'],
        ['recorte_anual', 'Cada arquivo anual contribui com as notificações de Goiânia cuja data de notificação está na janela do arquivo (ano civil e ano epidemiológico: os de dengue seguem o ano epidemiológico). Um mês pode reunir registros de dois arquivos; a pipeline verifica que nenhuma notificação aparece em dois arquivos. Notificações fora da janela, sem data de referência ou com evento anterior a 2022 são auditadas em exclusoes_temporais.'],
        ['meses_ausentes', 'Ausência de linha não significa zero. Datas presentes não comprovam mês completo. Nenhum total anual de 2026 é tratado como ano completo.'],
        ['clima', 'A002; calendário UTC. Chuva observada pode ser parcial; use cobertura e valor completo. Associação temporal não estabelece causalidade nem diferenças entre bairros.'],
        ['bairros', 'Lista publicada por edição, indicador e período. Não somar edições sobrepostas, não tratar ausência como zero, não calcular taxas ou ranking completo. Correspondência SIGGO apenas nominal.'],
        ['censo', 'População medida em 2022; nenhuma estimativa populacional por bairro ou para 2026.'],
        ['parceiros', 'Candidatos públicos sem motivo cadastral de desativação e coordenadas dentro da malha. Cadastro não comprova funcionamento, adesão ao SUS ou parceria.'],
        ['integracao_futura', 'Novas fontes devem entrar com fonte, versão, granularidade e chaves próprias. Preservar a base pública e comparar definições antes de substituir valores.'],
    ], columns=['tema', 'definicao'])
    tabelas = {'municipal_mensal_clima': mensal, 'bairros_publicados': bairros,
        'clima_mensal': clima, 'parceiros_candidatos': parceiros,
        'contexto_censo_2022': contexto, 'exclusoes_temporais': pd.DataFrame(auditoria),
        'definicoes': definicoes}
    for nome, tabela in tabelas.items():
        tabela.to_csv(OUT / f'{nome}.csv', index=False, encoding='utf-8-sig')
    with pd.ExcelWriter(OUT / 'base_integrada.xlsx', engine='openpyxl') as writer:
        for nome, tabela in tabelas.items():
            tabela.to_excel(writer, sheet_name=nome[:31], index=False)
            folha = writer.sheets[nome[:31]]
            folha.freeze_panes = 'A2'
            folha.auto_filter.ref = folha.dimensions
            for coluna in folha.columns:
                letra = coluna[0].column_letter
                folha.column_dimensions[letra].width = min(55, max(16, len(str(coluna[0].value)) + 2))
    manifesto = {'gerado_em': datetime.now(timezone.utc).isoformat(),
        'depende_de_resposta_da_secretaria': False,
        'metodo': 'pipeline/processamento/integrar_bases.py', 'fontes': fontes,
        'tabelas': {nome: len(tabela) for nome, tabela in tabelas.items()},
        'verificacoes': ['unicidade municipal por agravo e mês', 'unicidade dos setores e das observações revisadas',
                         'join climático many-to-one sem multiplicação', 'reconciliação de exclusões temporais', 'ausência de notificações repetidas entre arquivos anuais']}
    (OUT / 'manifesto.json').write_text(json.dumps(manifesto, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(manifesto['tabelas'], ensure_ascii=False))


if __name__ == '__main__':
    main()
