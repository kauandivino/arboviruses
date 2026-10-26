"""Nowcasting das notificações recentes: estima quantas ainda serão digitadas por semana de início dos sintomas.

Método (chain-ladder em tempo reverso, sem parâmetros inventados):
  - cada notificação tem semana de início dos sintomas (t) e semana de digitação no SINAN;
  - na data de corte A, só existem as notificações digitadas até A, então as semanas
    recentes estão incompletas;
  - fatores de desenvolvimento f_k = soma N(t, <=k+1) / soma N(t, <=k), estimados nas
    coortes mais recentes que já atingiram k+1 semanas de atraso;
  - estimativa(t) = observado(t) x produto dos fatores ainda não atingidos.

Avaliação retrospectiva: para cada data de corte passada, reconstrói-se o que estava
digitado naquele momento e compara-se a estimativa com o total que chegou depois.
As faixas de incerteza vêm dos erros dessas avaliações anteriores, por atraso.
"""
from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline.comum.epidemiologia import inicio_semana, janela_arquivo
from pipeline.comum.ibge_utils import sha256

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'dados/modelagem'
GOIANIA = '520870'
SEMANA = pd.Timedelta(weeks=1)
MATURACAO = 52      # semanas após as quais a coorte é tratada como completa
JANELA = 20         # coortes recentes usadas em cada fator de desenvolvimento
DEFASAGENS = 12     # semanas recentes que recebem estimativa
QUANTIS = (0.025, 0.975)
AGRAVOS = {
    'dengue': {'arquivos': 'dados/datasus/goiania/dengue_{ano}.csv', 'municipio': 'ID_MN_RESI',
               'inicio': 'DT_SIN_PRI', 'semana_fonte': 'SEM_PRI', 'filtro': None,
               'descricao': 'Notificações de dengue de residentes em Goiânia, todas as classificações, por semana de início dos sintomas'},
}


def carregar(agravo='dengue', anos=range(2022, 2027)):
    cfg = AGRAVOS[agravo]
    partes, exclusoes, fora_janela = [], [], []
    for ano in anos:
        arquivo = ROOT / cfg['arquivos'].format(ano=ano)
        d = pd.read_csv(arquivo, dtype=str, usecols=lambda c: c in {cfg['municipio'], cfg['inicio'], cfg['semana_fonte'], 'DT_NOTIFIC', 'DT_DIGITA'})
        d = d[d[cfg['municipio']] == GOIANIA]
        # Mesma regra da base integrada: notificações dentro da janela do arquivo (ano civil e epidemiológico).
        fora = ~pd.to_datetime(d.DT_NOTIFIC, errors='coerce').between(*janela_arquivo(ano))
        sem_digitacao = d.DT_DIGITA.isna()
        exclusoes.append({'arquivo': arquivo.relative_to(ROOT).as_posix(), 'ano': ano, 'registros': int(len(d)),
                          'excluidos_notificacao_fora_da_janela': int(fora.sum()), 'excluidos_sem_data_digitacao': int((~fora & sem_digitacao).sum())})
        partes.append((d[~fora & ~sem_digitacao], arquivo))
        fora_janela.append(inicio_semana(d.loc[fora, cfg['inicio']]))
    d = pd.concat([p for p, _ in partes], ignore_index=True)
    reg = pd.DataFrame({'t': inicio_semana(d[cfg['inicio']]), 'dig': inicio_semana(d.DT_DIGITA), 'se_fonte': d[cfg['semana_fonte']]})
    reg['atraso'] = ((reg.dig - reg.t) / SEMANA).astype(int)
    if (reg.atraso < 0).any():
        raise ValueError('digitação anterior ao início dos sintomas')
    reg.attrs['fora_janela_por_semana'] = pd.concat(fora_janela).value_counts()
    return reg, exclusoes, [a for _, a in partes]


def triangulo(reg, corte):
    """Contagens por semana de início (linhas) e atraso em semanas (colunas), conhecidas na data de corte."""
    v = reg[reg.dig <= corte]
    semanas = pd.date_range(v.t.min(), corte, freq='7D')
    tab = pd.crosstab(v.t, v.atraso.clip(upper=MATURACAO)).reindex(index=semanas, columns=range(MATURACAO + 1), fill_value=0)
    acumulado = tab.cumsum(axis=1)
    # Células ainda não observáveis na data de corte ficam ausentes, não zero.
    atraso_max = ((corte - acumulado.index) / SEMANA).astype(int)
    acumulado = acumulado.where(np.arange(MATURACAO + 1)[None, :] <= atraso_max.to_numpy()[:, None])
    return acumulado


def fatores(acumulado):
    f = np.ones(MATURACAO)
    for k in range(MATURACAO):
        pares = acumulado[[k, k + 1]].dropna().tail(JANELA)
        base = pares[k].sum()
        if base > 0:
            f[k] = pares[k + 1].sum() / base
    return f


def estimar(reg, corte):
    acumulado = triangulo(reg, corte)
    f = fatores(acumulado)
    cauda = np.concatenate([np.cumprod(f[::-1])[::-1], [1.0]])  # fator total a partir de cada atraso
    linhas = []
    for t in acumulado.index[-DEFASAGENS:]:
        defasagem = int((corte - t) / SEMANA)
        observado = float(acumulado.loc[t, defasagem])
        linhas.append({'semana': t, 'defasagem': defasagem, 'observado': observado, 'estimado': observado * cauda[defasagem]})
    return pd.DataFrame(linhas)


def verdade(reg, corte_final):
    """Total por semana na base mais recente, só para semanas já maduras."""
    maduras = reg[reg.t <= corte_final - MATURACAO * SEMANA]
    return maduras.groupby('t').size()


def avaliar(reg, cortes, corte_final):
    total = verdade(reg, corte_final)
    linhas = []
    for corte in cortes:
        e = estimar(reg, corte)
        e = e[e.semana.isin(total.index)]
        e['corte'] = corte
        e['verdade'] = e.semana.map(total).astype(float)
        linhas.append(e)
    return pd.concat(linhas, ignore_index=True)


def faixas(erros, ate_corte):
    """Quantis do erro relativo (verdade/estimado) por defasagem, usando só avaliações já conhecidas em ate_corte."""
    conhecidos = erros[(erros.semana + MATURACAO * SEMANA <= ate_corte) & (erros.estimado > 0)]
    razao = conhecidos.verdade / conhecidos.estimado
    q = razao.groupby(conhecidos.defasagem).quantile(list(QUANTIS)).unstack().reindex(columns=list(QUANTIS))
    n = conhecidos.groupby('defasagem').size()
    return q.assign(n=n).reindex(range(DEFASAGENS))


def metricas(erros):
    """Compara a estimativa com o número bruto (o que o painel mostraria sem modelo)."""
    def resumo(g):
        return pd.Series({
            'avaliacoes': len(g),
            'erro_abs_medio_bruto': (g.verdade - g.observado).abs().mean(),
            'erro_abs_medio_estimado': (g.verdade - g.estimado).abs().mean(),
            'erro_rel_mediano_bruto_pct': ((g.verdade - g.observado).abs() / g.verdade).median() * 100,
            'erro_rel_mediano_estimado_pct': ((g.verdade - g.estimado).abs() / g.verdade).median() * 100,
            'cobertura_faixa_pct': g.dentro.mean() * 100 if g.dentro.notna().any() else None,
            'avaliacoes_com_faixa': int(g.dentro.notna().sum()),
        })
    return erros.groupby('defasagem').apply(resumo, include_groups=False).reset_index()


def main(agravo='dengue'):
    reg, exclusoes, arquivos = carregar(agravo)
    corte = reg.dig.max() - SEMANA  # última semana de digitação completa; a semana corrente fica de fora
    reg = reg[reg.dig <= corte]
    cortes = pd.date_range(pd.Timestamp('2023-01-01'), corte - MATURACAO * SEMANA, freq='7D')
    erros = avaliar(reg, cortes, corte)

    # Faixas de cada avaliação usam só erros cuja verdade já era conhecida naquela data (sem olhar o futuro).
    erros['inferior'] = np.nan
    erros['superior'] = np.nan
    for c in erros.corte.unique():
        q = faixas(erros, c)
        idx = erros.corte == c
        validos = q[q.n >= 20]
        erros.loc[idx, 'inferior'] = erros.loc[idx].estimado * erros.loc[idx].defasagem.map(validos[QUANTIS[0]])
        erros.loc[idx, 'superior'] = erros.loc[idx].estimado * erros.loc[idx].defasagem.map(validos[QUANTIS[1]])
    erros['dentro'] = np.where(erros.inferior.notna(), (erros.verdade >= erros.inferior) & (erros.verdade <= erros.superior), np.nan)
    resumo = metricas(erros)
    melhora = bool((resumo.erro_abs_medio_estimado < resumo.erro_abs_medio_bruto).all())

    atual = estimar(reg, corte)
    q = faixas(erros, corte)
    atual['inferior'] = atual.estimado * atual.defasagem.map(q[QUANTIS[0]])
    atual['superior'] = atual.estimado * atual.defasagem.map(q[QUANTIS[1]])
    # Faixa nunca abaixo do que já foi digitado.
    atual['inferior'] = np.maximum(atual.inferior, atual.observado)
    historico = reg.groupby('t').size().rename('observado').reset_index().rename(columns={'t': 'semana'})
    historico = historico[historico.semana > corte - 52 * SEMANA]
    serie = historico.merge(atual.drop(columns='observado'), on='semana', how='left')
    se = reg.groupby('t').se_fonte.agg(lambda s: s.mode().iat[0]).rename('se')
    serie['se'] = serie.semana.map(se)
    serie['se_rotulo'] = serie.se.astype(str).str[4:] + '/' + serie.se.astype(str).str[:4]
    # Notificações do período que ficaram fora pela regra da janela dos arquivos (auditadas, não estimadas).
    serie['excluidas_fora_janela'] = serie.semana.map(reg.attrs['fora_janela_por_semana']).fillna(0).astype(int)
    serie['semana_fim'] = serie.semana + pd.Timedelta(days=6)
    serie['exibir_estimativa'] = melhora
    for c in ['estimado', 'inferior', 'superior']:
        serie[c] = serie[c].round(0)

    OUT.mkdir(parents=True, exist_ok=True)
    serie_csv = OUT / f'nowcast_{agravo}.csv'
    serie.assign(semana=serie.semana.dt.date, semana_fim=serie.semana_fim.dt.date).to_csv(serie_csv, index=False, encoding='utf-8')
    avaliacao_csv = OUT / f'nowcast_{agravo}_avaliacao.csv'
    resumo.round(2).to_csv(avaliacao_csv, index=False, encoding='utf-8')
    erros_csv = OUT / f'nowcast_{agravo}_retrospectiva.csv'
    erros.assign(semana=erros.semana.dt.date, corte=erros.corte.dt.date).round(2).to_csv(erros_csv, index=False, encoding='utf-8')
    manifesto = {
        'gerado_em': datetime.now(timezone.utc).isoformat(), 'metodo': 'pipeline/modelagem/nowcast.py',
        'agravo': agravo, 'descricao': AGRAVOS[agravo]['descricao'],
        'data_corte_semana_digitacao': corte.date().isoformat(),
        'parametros': {'maturacao_semanas': MATURACAO, 'janela_coortes': JANELA, 'defasagens_estimadas': DEFASAGENS, 'quantis_faixa': QUANTIS},
        'avaliacao': {'cortes': len(cortes), 'primeiro_corte': cortes[0].date().isoformat(), 'ultimo_corte': cortes[-1].date().isoformat(),
                      'estimativa_supera_numero_bruto_em_todas_as_defasagens': melhora},
        'exclusoes': exclusoes,
        'fontes': [{'arquivo': a.relative_to(ROOT).as_posix(), 'sha256': sha256(a)} for a in arquivos],
        'produtos': [{'arquivo': p.relative_to(ROOT).as_posix(), 'sha256': sha256(p)} for p in (serie_csv, avaliacao_csv, erros_csv)],
        'limitacoes': [
            'A reconstrução do passado usa a base atual: notificações removidas depois (por exemplo, duplicidades) não aparecem nos cortes antigos.',
            'Conta notificações de todas as classificações, não casos confirmados; a classificação final não é conhecida na data de corte.',
            'Semanas com mais de 52 semanas de atraso são tratadas como completas.',
            'As faixas refletem os erros de 2023 a 2025; uma mudança brusca na rotina de digitação pode deixá-las estreitas demais.'],
    }
    (OUT / f'nowcast_{agravo}_manifesto.json').write_text(json.dumps(manifesto, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(resumo.round(1).to_string(index=False))
    print('Estimativa supera o número bruto em todas as defasagens:', melhora)


if __name__ == '__main__':
    main()
