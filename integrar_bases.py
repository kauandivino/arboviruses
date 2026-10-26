"""Integra as bases locais sem depender de dados adicionais da Secretaria.

Execute com .venv-datasus/Scripts/python.exe integrar_bases.py.
Não baixa arquivos, não soma informes e não distribui população por bairro.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import pandas as pd

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'dados/base_integrada'


def construir_serie(df, ano, referencia, campo):
    """Uma dimensão geográfica e temporal por fonte anual; sem preencher zeros."""
    recorte = df.loc[(df.referencia_geografica == referencia) & (df.campo_data == campo)].copy()
    recorte['n_registros'] = pd.to_numeric(recorte.n_registros, errors='raise')
    valido = recorte.mes.str.fullmatch(fr'{ano}-\d{{2}}', na=False)
    incluidos, excluidos = recorte.loc[valido], recorte.loc[~valido]
    serie = incluidos.groupby('mes', as_index=False).n_registros.sum()
    assert int(serie.n_registros.sum()) + int(excluidos.n_registros.sum()) == int(recorte.n_registros.sum())
    return serie, excluidos


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    fontes = []

    def ler(rel):
        path = ROOT / rel
        raw = path.read_bytes()
        fontes.append({'arquivo': rel, 'sha256': hashlib.sha256(raw).hexdigest()})
        return pd.read_csv(path, dtype=str, keep_default_na=False)

    series, auditoria = [], []
    for ano in range(2022, 2027):
        for arquivo, agravo, referencia, campo in [
            ('dengue', 'dengue', 'residencia', 'DT_NOTIFIC'),
            ('animais', 'escorpioes', 'ocorrencia', 'ANT_DT_ACI'),
        ]:
            rel = f'dados/datasus/resumos/{arquivo}_{ano}_mensal.csv'
            df = ler(rel)
            assert set(df.agravo) == {agravo}, f'Agravo inesperado: {rel}'
            agregado, excluidos = construir_serie(df, ano, referencia, campo)
            qualidade = ROOT / f'dados/datasus/qualidade/{arquivo}_{ano}.json'
            metadata = json.loads(qualidade.read_text(encoding='utf-8'))
            fontes.append({'arquivo': qualidade.relative_to(ROOT).as_posix(),
                           'sha256': hashlib.sha256(qualidade.read_bytes()).hexdigest()})
            agregado = agregado.assign(agravo=agravo, ano_arquivo=ano,
                referencia_geografica=referencia, campo_data=campo,
                situacao_fonte=metadata['situacao'], arquivo_origem=rel)
            series.append(agregado)
            for mes, grupo in excluidos.groupby('mes', dropna=False):
                auditoria.append({'arquivo': rel, 'mes': mes,
                    'n_registros': int(grupo.n_registros.sum()),
                    'motivo': 'data_ausente_ou_fora_do_ano_do_arquivo',
                    'referencia_geografica': referencia, 'campo_data': campo})

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
    cnes = ler('dados/cnes/goiania/202609/estabelecimentos.csv')
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
        ['recorte_anual', 'Cada arquivo anual contribui apenas com datas do próprio ano. Datas ausentes e externas são auditadas. Isso não é uma deduplicação de microdados; não recupera notificações tardias em outros arquivos.'],
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
        'metodo': 'integrar_bases.py', 'fontes': fontes,
        'tabelas': {nome: len(tabela) for nome, tabela in tabelas.items()},
        'verificacoes': ['unicidade municipal por agravo e mês', 'unicidade dos setores e das observações revisadas',
                         'join climático many-to-one sem multiplicação', 'reconciliação de exclusões temporais']}
    (OUT / 'manifesto.json').write_text(json.dumps(manifesto, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(manifesto['tabelas'], ensure_ascii=False))


if __name__ == '__main__':
    main()
