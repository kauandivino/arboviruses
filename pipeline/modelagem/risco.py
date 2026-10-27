"""Probabilidade de a dengue em Goiânia ficar acima do habitual nas próximas 4 semanas.

Evento (definido antes da avaliação): a média das 4 semanas seguintes à data de corte A,
com os dados finais, fica acima do 3º quartil do diagrama de controle daquelas semanas.

Atributos, sempre como eram conhecidos em A (séries corrigidas pelo nowcasting de A):
  Goiânia: nível e tendência das últimas 4 semanas e razão entre o nível e o 3º quartil atual;
  vizinhos (10 municípios com divisa) e resto de Goiás: nível e tendência;
  sorotipo emergente: parcela, entre as amostras tipadas nas 12 semanas anteriores, de sorotipos
  que tiveram menos de 10% das amostras nos 3 anos anteriores;
  clima A002 das semanas A-9 a A-2; sazonalidade das semanas-alvo.

Referências: frequência histórica do evento e regressão logística só com a razão nível/3º quartil.
Candidatos: regressão logística e gradient boosting com todos os atributos.
Escolha pelo Brier score na validação (origens 2019–2021); exibição só se o escolhido tiver
Brier menor que as duas referências no teste (origens 2022 em diante, nunca usadas na escolha).
O evento só existe a partir de 2019: o habitual usa os cinco anos anteriores e o histórico começa em 2014.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import warnings

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from pipeline.comum.ibge_utils import sha256
from pipeline.modelagem import nowcast as nc
from pipeline.modelagem.alerta import ANOS_REFERENCIA, semana_epidemiologica
from pipeline.modelagem.previsao import atributos_clima, clima_semanal

ROOT = nc.ROOT
OUT = nc.OUT
REGIONAL = ROOT / 'dados/regional'
S = nc.SEMANA
HORIZONTE = 4
NIVEL = 4
MATURACAO = nc.MATURACAO
VALIDACAO = (pd.Timestamp('2019-01-06'), pd.Timestamp('2021-12-26'))
TESTE_INICIO = pd.Timestamp('2022-01-02')
MIN_TREINO = 80
GBM = {'max_iter': 200, 'learning_rate': 0.05, 'max_depth': 3, 'min_samples_leaf': 15, 'random_state': 0}
REFERENCIAS = ['frequencia', 'logistica_situacao']
CANDIDATOS = ['logistica_completa', 'gbm_completo']
ATRIB_SITUACAO = ['razao_q3']
ATRIB_COMPLETOS = ['razao_q3', 'nivel', 'tendencia', 'viz_nivel', 'viz_tendencia', 'go_tendencia', 'sorotipo_emergente',
                   'chuva_mm', 'temperatura_c', 'umidade_pct', 'sen', 'cos']
ABLACOES = {'sem_vizinhos': ['viz_nivel', 'viz_tendencia', 'go_tendencia'], 'sem_sorotipo': ['sorotipo_emergente'],
            'sem_clima': ['chuva_mm', 'temperatura_c', 'umidade_pct']}


class Grupo:
    """Triângulo início × atraso de digitação de um grupo, para séries corrigidas em qualquer data de corte."""

    def __init__(self, tabela):
        tabela = tabela.groupby(['semana_inicio', 'semana_digitacao']).notificacoes.sum().reset_index()
        self.inicio = pd.Timestamp(tabela.semana_inicio.min())
        t = ((tabela.semana_inicio - self.inicio) / S).astype(int).to_numpy()
        # Atraso exato (sem agrupar): a visibilidade em cada corte depende da data real de digitação.
        atraso = ((tabela.semana_digitacao - tabela.semana_inicio) / S).astype(int).to_numpy()
        self.m = np.zeros((t.max() + 1, atraso.max() + 1))
        np.add.at(self.m, (t, atraso), tabela.notificacoes.to_numpy())

    def serie(self, corte):
        """Mesma lógica de nowcast.estimar: fatores das 20 coortes recentes, aplicados às semanas incompletas."""
        a = int((corte - self.inicio) / S)
        n = min(a + 1, self.m.shape[0])
        idade = a - np.arange(n)
        visivel = np.arange(self.m.shape[1])[None, :] <= idade[:, None]
        completo = np.cumsum(np.where(visivel, self.m[:n], 0), axis=1)
        # Como no nowcasting, o atraso 52 reúne tudo o que foi digitado com 52 semanas ou mais (até o corte).
        acum = completo[:, :MATURACAO + 1].copy()
        acum[:, MATURACAO] = completo[:, -1]
        f = np.ones(MATURACAO)
        for k in range(MATURACAO):
            coortes = np.where(idade >= k + 1)[0][-nc.JANELA:]
            base = acum[coortes, k].sum()
            if base > 0:
                f[k] = acum[coortes, k + 1].sum() / base
        cauda = np.concatenate([np.cumprod(f[::-1])[::-1], [1.0]])
        d = np.minimum(idade, MATURACAO)
        valores = acum[np.arange(n), d] * cauda[d]
        return pd.Series(valores, index=pd.date_range(self.inicio, periods=n, freq='7D'))


def carregar_regional():
    partes = [pd.read_csv(p, parse_dates=['semana_inicio', 'semana_digitacao'], dtype={'sorotipo': str})
              for p in sorted(REGIONAL.glob('dengue_go_*.csv'))]
    return pd.concat(partes, ignore_index=True)


def canal_ano(serie_final, ano):
    """3º quartil por SE do ano, com os cinco anos anteriores (mesma regra do diagrama de controle)."""
    tab = pd.DataFrame({'n': serie_final})
    tab[['ano', 'se']] = [semana_epidemiologica(s) for s in tab.index]
    ant = tab[tab.ano.between(ano - ANOS_REFERENCIA, ano - 1)]
    if ant.ano.nunique() < ANOS_REFERENCIA:
        return None
    q3 = {}
    for se in range(1, 54):
        viz = {((se + d - 1) % 52) + 1 for d in (-1, 0, 1)} if se <= 52 else {51, 52, 53}
        q3[se] = ant[ant.se.isin(viz)].n.quantile(0.75)
    return q3


def sorotipos_conhecidos(regional, corte):
    """Amostras tipadas de Goiânia digitadas até o corte, por semana de início e sorotipo."""
    s = regional[(regional.grupo == 'goiania') & regional.sorotipo.isin(['1', '2', '3', '4']) & (regional.semana_digitacao <= corte)]
    return s.groupby(['semana_inicio', 'sorotipo']).notificacoes.sum().unstack(fill_value=0)


def emergente(tipados, corte):
    recentes = tipados.loc[corte - 11 * S: corte]
    anteriores = tipados.loc[corte - 3 * 52 * S: corte - 12 * S]
    if recentes.values.sum() < 5 or anteriores.values.sum() < 10:
        return 0.0
    parcela_antes = anteriores.sum() / anteriores.values.sum()
    raros = parcela_antes[parcela_antes < 0.10].index
    return float(recentes[raros].values.sum() / recentes.values.sum()) if len(raros) else 0.0


def montar(regional, clima):
    grupos = {g: Grupo(regional[regional.grupo == g]) for g in ['goiania', 'vizinhos', 'resto_go']}
    corte_final = regional.semana_digitacao.max() - S
    final = grupos['goiania'].serie(corte_final)
    canais = {}
    linhas = []
    tipados_cache = None
    origens = pd.date_range(VALIDACAO[0], corte_final, freq='7D')
    for corte in origens:
        ano, se = semana_epidemiologica(corte)
        if ano not in canais:
            canais[ano] = canal_ano(grupos['goiania'].serie(pd.Timestamp(f'{ano}-01-01') - S), ano)
        if canais[ano] is None:
            continue
        g, v, r = (grupos[k].serie(corte) for k in ['goiania', 'vizinhos', 'resto_go'])
        def nivel_tend(s):
            u, p = s.loc[corte - (NIVEL - 1) * S: corte].mean(), s.loc[corte - (2 * NIVEL - 1) * S: corte - NIVEL * S].mean()
            return np.log1p(u), np.log1p(u) - np.log1p(p)
        gn, gt = nivel_tend(g)
        vn, vt = nivel_tend(v)
        _, rt = nivel_tend(r)
        tipados_cache = sorotipos_conhecidos(regional, corte)
        c = atributos_clima(clima, corte)
        alvos = [corte + h * S for h in range(1, HORIZONTE + 1)]
        q3_alvo = []
        for a in alvos:
            ano_a, se_a = semana_epidemiologica(a)
            if ano_a not in canais:
                canais[ano_a] = canal_ano(grupos['goiania'].serie(pd.Timestamp(f'{ano_a}-01-01') - S), ano_a)
            q3_alvo.append(canais[ano_a][se_a] if canais[ano_a] else np.nan)
        angulo = 2 * np.pi * alvos[1].dayofyear / 365.25
        maduro = alvos[-1] + MATURACAO * S <= corte_final
        linhas.append({'corte': corte, 'razao_q3': gn - np.log1p(canais[ano][se]), 'nivel': gn, 'tendencia': gt,
                       'viz_nivel': vn, 'viz_tendencia': vt, 'go_tendencia': rt, 'sorotipo_emergente': emergente(tipados_cache, corte),
                       **c, 'sen': np.sin(angulo), 'cos': np.cos(angulo),
                       'q3_alvo': float(np.mean(q3_alvo)),
                       'final_alvo': float(final.reindex(alvos).mean()) if maduro else np.nan})
    tabela = pd.DataFrame(linhas)
    tabela['evento'] = np.where(tabela.final_alvo.notna(), (tabela.final_alvo > tabela.q3_alvo).astype(float), np.nan)
    return tabela, corte_final, grupos


def ajustar_prever(tabela, corte, tipo, atributos):
    """Treina com pares cujo evento já era conhecido em `corte` e prevê a probabilidade em `corte`."""
    conhecido = tabela[(tabela.corte + (HORIZONTE + 4) * S <= corte)].dropna(subset=atributos + ['evento_em_corte'])
    alvo = tabela[tabela.corte == corte]
    if alvo.empty or alvo[atributos].isna().any(axis=None):
        return np.nan
    # O evento usado no treino é o observado com os dados de `corte` (sem olhar o futuro).
    y = conhecido.evento_em_corte
    if len(conhecido) < MIN_TREINO or y.nunique() < 2:
        return np.nan
    if tipo == 'frequencia':
        return float(y.mean())
    if tipo == 'gbm':
        modelo = HistGradientBoostingClassifier(**GBM)
    else:
        modelo = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=2000))
    modelo.fit(conhecido[atributos], y)
    return float(modelo.predict_proba(alvo[atributos])[0, 1])


def evento_conhecido(tabela, grupos, corte):
    """Evento de cada origem anterior, medido com a série corrigida conhecida em `corte`."""
    serie = grupos['goiania'].serie(corte)
    # Média das semanas o+1..o+4 para cada origem o.
    futuras = serie.rolling(HORIZONTE).mean().shift(-HORIZONTE)
    medias = tabela.corte.map(futuras)
    return np.where(medias.notna(), (medias > tabela.q3_alvo).astype(float), np.nan)


def brier(p, y):
    return float(np.mean((p - y) ** 2))


def main():
    # A avaliação leva alguns minutos; só é refeita se dados, parâmetros ou código mudarem.
    entradas = sorted(REGIONAL.glob('dengue_go_*.csv')) + [c for c in __import__('pipeline.modelagem.previsao', fromlist=['CLIMA']).CLIMA if c.exists()]
    entradas += [Path(__file__), Path(nc.__file__), Path(nc.__file__).with_name('previsao.py'), Path(nc.__file__).with_name('alerta.py')]
    chave = hashlib.sha256(json.dumps([sha256(f) for f in entradas]).encode()).hexdigest()
    anterior = OUT / 'risco_dengue_manifesto.json'
    if anterior.exists() and json.loads(anterior.read_text(encoding='utf-8')).get('chave') == chave:
        print('Avaliação reaproveitada: dados, parâmetros e código inalterados.')
        return
    regional = carregar_regional()
    clima = clima_semanal()
    tabela, corte_final, grupos = montar(regional, clima)
    origens = tabela[(tabela.corte >= VALIDACAO[0]) & tabela.evento.notna()].corte
    metodos = {'frequencia': ('frequencia', ATRIB_SITUACAO), 'logistica_situacao': ('logistica', ATRIB_SITUACAO),
               'logistica_completa': ('logistica', ATRIB_COMPLETOS), 'gbm_completo': ('gbm', ATRIB_COMPLETOS),
               **{f'gbm_{k}': ('gbm', [a for a in ATRIB_COMPLETOS if a not in v]) for k, v in ABLACOES.items()},
               **{f'logistica_{k}': ('logistica', [a for a in ATRIB_COMPLETOS if a not in v]) for k, v in ABLACOES.items()}}
    resultados = []
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        for corte in origens:
            tabela['evento_em_corte'] = evento_conhecido(tabela, grupos, corte)
            linha = {'corte': corte, 'evento': tabela.loc[tabela.corte == corte, 'evento'].iloc[0]}
            for nome, (tipo, atrib) in metodos.items():
                linha[nome] = ajustar_prever(tabela, corte, tipo, atrib)
            resultados.append(linha)
    r = pd.DataFrame(resultados).dropna(subset=list(metodos))
    r['periodo'] = np.where(r.corte <= VALIDACAO[1], 'validacao', 'teste')
    resumo = r.groupby('periodo').apply(lambda g: pd.Series({**{m: brier(g[m], g.evento) for m in metodos}, 'origens': len(g),
                                                              'frequencia_evento': g.evento.mean()}), include_groups=False)
    escolhido = min(CANDIDATOS, key=lambda m: resumo.loc['validacao', m])
    exibir = bool(all(resumo.loc['teste', escolhido] < resumo.loc['teste', ref] for ref in REFERENCIAS))

    # Probabilidade atual com o modelo escolhido, treinado com tudo o que se conhece hoje.
    tabela['evento_em_corte'] = evento_conhecido(tabela, grupos, corte_final)
    tipo, atrib = metodos[escolhido]
    atual = ajustar_prever(tabela, corte_final, tipo, atrib)
    calibracao = r[r.periodo == 'teste'].assign(faixa=lambda d: pd.cut(d[escolhido], [0, .2, .4, .6, .8, 1], include_lowest=True))
    calibracao = calibracao.groupby('faixa', observed=True).agg(previsto=(escolhido, 'mean'), observado=('evento', 'mean'), n=('evento', 'size')).reset_index()

    OUT.mkdir(parents=True, exist_ok=True)
    r.assign(corte=r.corte.dt.date).round(4).to_csv(OUT / 'risco_dengue_retrospectiva.csv', index=False, encoding='utf-8')
    resumo.round(4).to_csv(OUT / 'risco_dengue_avaliacao.csv', encoding='utf-8')
    calibracao.assign(faixa=calibracao.faixa.astype(str)).round(3).to_csv(OUT / 'risco_dengue_calibracao.csv', index=False, encoding='utf-8')
    ultima = tabela[tabela.corte == corte_final].iloc[0]
    tipados = sorotipos_conhecidos(regional, corte_final)
    manifesto = {
        'gerado_em': datetime.now(timezone.utc).isoformat(), 'metodo': 'pipeline/modelagem/risco.py',
        'evento': 'média das 4 semanas seguintes acima do 3º quartil do diagrama de controle (dados finais)',
        'chave': chave, 'corte': corte_final.date().isoformat(), 'probabilidade_atual': None if np.isnan(atual) else round(atual, 3),
        'exibida': exibir, 'modelo_escolhido_na_validacao': escolhido,
        'brier': {p: {m: round(float(resumo.loc[p, m]), 4) for m in metodos} for p in resumo.index},
        'frequencia_evento': {p: round(float(resumo.loc[p, 'frequencia_evento']), 3) for p in resumo.index},
        'origens': {p: int(resumo.loc[p, 'origens']) for p in resumo.index},
        'regra': 'escolher na validação o candidato de menor Brier; exibir só se, no teste, tiver Brier menor que as duas referências',
        'atributos_atuais': {k: (None if pd.isna(ultima[k]) else round(float(ultima[k]), 4)) for k in ATRIB_COMPLETOS},
        'sorotipos_12_semanas': {s: int(n) for s, n in tipados.loc[corte_final - 11 * S: corte_final].sum().items()},
        'fontes': [{'arquivo': p.relative_to(ROOT).as_posix(), 'sha256': sha256(p)} for p in sorted(REGIONAL.glob('dengue_go_*.csv'))],
        'limitacoes': ['Poucas temporadas para avaliar probabilidades; uma temporada atípica pode fugir do aprendido.',
                       'Sorotipo é identificado em poucas amostras (0,1% a 3% das notificações).',
                       'Vizinhos pela residência informada; não mede deslocamento de pessoas.'],
    }
    (OUT / 'risco_dengue_manifesto.json').write_text(json.dumps(manifesto, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(resumo.round(4).T.to_string())
    print(f'Escolhido: {escolhido}; exibido: {exibir}; probabilidade atual: {atual:.3f}')


if __name__ == '__main__':
    main()
