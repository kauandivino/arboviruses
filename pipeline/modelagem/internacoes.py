"""Previsão das internações por dengue de residentes em Goiânia nas próximas 4 semanas.

Regra definida antes da avaliação:
  Alvo: soma das internações com início dos sintomas nas 4 semanas seguintes ao corte (dados finais).
  Atributos, como conhecidos no corte (séries corrigidas pelo nowcasting do corte):
    internações e notificações das últimas 4 semanas (log) e suas tendências,
    proporção de internados nas últimas 8 semanas, internações nos vizinhos (log), sazonalidade.
  Referências: repetir a soma das últimas 4 semanas; mesmas 4 semanas do ano anterior.
  Candidatos: ridge e gradient boosting no log da soma.
  Escolha pelo erro absoluto médio na validação (origens 2016–2020); exibição só se o escolhido
  superar as duas referências no teste (origens 2021 em diante).

Limitação: o campo de internação é o do estado final do registro; não é possível saber se a
internação já estava anotada em cada data passada, o que deixa a avaliação um pouco otimista.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import warnings

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from pipeline.comum.ibge_utils import sha256
from pipeline.modelagem import nowcast as nc
from pipeline.modelagem import risco as rc

OUT = nc.OUT
S = nc.SEMANA
H = 4
VALIDACAO = (pd.Timestamp('2016-01-03'), pd.Timestamp('2020-12-27'))
MIN_TREINO = 80
GBM = {'max_iter': 200, 'learning_rate': 0.05, 'max_depth': 3, 'min_samples_leaf': 15, 'random_state': 0}
ATRIBUTOS = ['int_nivel', 'int_tendencia', 'not_nivel', 'not_tendencia', 'proporcao', 'viz_int', 'sen', 'cos']
REFERENCIAS = ['persistencia', 'sazonal']
CANDIDATOS = ['ridge', 'gbm']


def soma(serie, fim, semanas):
    return float(serie.loc[fim - (semanas - 1) * S: fim].sum())


def montar(regional):
    grupos = {'int': rc.Grupo(regional[(regional.grupo == 'goiania') & (regional.internado == 1)]),
              'not': rc.Grupo(regional[regional.grupo == 'goiania']),
              'viz': rc.Grupo(regional[(regional.grupo == 'vizinhos') & (regional.internado == 1)])}
    corte_final = regional.semana_digitacao.max() - S
    final = grupos['int'].serie(corte_final)
    linhas = []
    for corte in pd.date_range(VALIDACAO[0] - 104 * S, corte_final, freq='7D'):
        si, sn, sv = (grupos[k].serie(corte) for k in ['int', 'not', 'viz'])
        i4, i8 = soma(si, corte, 4), soma(si, corte - 4 * S, 4)
        n4, n8 = soma(sn, corte, 4), soma(sn, corte - 4 * S, 4)
        alvos = [corte + h * S for h in range(1, H + 1)]
        angulo = 2 * np.pi * alvos[1].dayofyear / 365.25
        maduro = alvos[-1] + nc.MATURACAO * S <= corte_final
        linhas.append({'corte': corte, 'int_nivel': np.log1p(i4), 'int_tendencia': np.log1p(i4) - np.log1p(i8),
                       'not_nivel': np.log1p(n4), 'not_tendencia': np.log1p(n4) - np.log1p(n8),
                       'proporcao': (i4 + i8) / (n4 + n8) if n4 + n8 else 0.0, 'viz_int': np.log1p(soma(sv, corte, 4)),
                       'sen': np.sin(angulo), 'cos': np.cos(angulo),
                       'persistencia': i4, 'sazonal': soma(si, corte + H * S - 52 * S, 4),
                       'verdade': float(final.reindex(alvos).sum()) if maduro else np.nan})
    return pd.DataFrame(linhas), grupos, corte_final


def alvo_conhecido(tabela, grupo, corte):
    """Soma das 4 semanas seguintes de cada origem, como conhecida no corte (sem olhar o futuro)."""
    serie = grupo.serie(corte)
    futuras = serie.rolling(H).sum().shift(-H)
    return tabela.corte.map(futuras)


def ajustar_prever(tabela, corte, tipo):
    treino = tabela[tabela.corte + (H + 4) * S <= corte].dropna(subset=['alvo_em_corte'])
    alvo = tabela[tabela.corte == corte]
    if len(treino) < MIN_TREINO or alvo.empty:
        return np.nan
    modelo = (HistGradientBoostingRegressor(**GBM) if tipo == 'gbm'
              else make_pipeline(StandardScaler(), Ridge(alpha=1.0)))
    modelo.fit(treino[ATRIBUTOS], np.log1p(treino.alvo_em_corte))
    return float(np.expm1(modelo.predict(alvo[ATRIBUTOS])[0]))


def main():
    regional = rc.carregar_regional()
    entradas = sorted(rc.REGIONAL.glob('dengue_go_*.csv')) + [Path(__file__), Path(rc.__file__), Path(nc.__file__)]
    chave = hashlib.sha256(json.dumps([sha256(f) for f in entradas]).encode()).hexdigest()
    anterior = OUT / 'internacoes_dengue_manifesto.json'
    if anterior.exists() and json.loads(anterior.read_text(encoding='utf-8')).get('chave') == chave:
        print('Avaliação reaproveitada: dados, parâmetros e código inalterados.')
        return
    tabela, grupos, corte_final = montar(regional)
    origens = tabela[(tabela.corte >= VALIDACAO[0]) & tabela.verdade.notna()].corte
    resultados = []
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        for corte in origens:
            tabela['alvo_em_corte'] = alvo_conhecido(tabela, grupos['int'], corte)
            r = tabela[tabela.corte == corte].iloc[0]
            resultados.append({'corte': corte, 'verdade': r.verdade, 'persistencia': r.persistencia, 'sazonal': r.sazonal,
                               **{c: ajustar_prever(tabela, corte, c) for c in CANDIDATOS}})
    r = pd.DataFrame(resultados).dropna()
    r['periodo'] = np.where(r.corte <= VALIDACAO[1], 'validacao', 'teste')
    metodos = REFERENCIAS + CANDIDATOS
    resumo = r.groupby('periodo').apply(lambda g: pd.Series({
        **{f'erro_abs_medio_{m}': (g[m] - g.verdade).abs().mean() for m in metodos},
        **{f'erro_rel_mediano_{m}_pct': ((g[m] - g.verdade).abs() / g.verdade.clip(lower=1)).median() * 100 for m in metodos},
        'origens': len(g), 'media_verdade': g.verdade.mean()}), include_groups=False)
    escolhido = min(CANDIDATOS, key=lambda m: resumo.loc['validacao', f'erro_abs_medio_{m}'])
    exibir = bool(all(resumo.loc['teste', f'erro_abs_medio_{escolhido}'] < resumo.loc['teste', f'erro_abs_medio_{ref}'] for ref in REFERENCIAS))

    # Previsão atual e faixa pelos erros do teste (razão verdade/previsto, quantis 10% e 90%).
    tabela['alvo_em_corte'] = alvo_conhecido(tabela, grupos['int'], corte_final)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        atual = ajustar_prever(tabela, corte_final, escolhido)
    teste = r[r.periodo == 'teste']
    razao = (teste.verdade / teste[escolhido].clip(lower=1)).quantile([0.1, 0.9])
    ultima = tabela[tabela.corte == corte_final].iloc[0]
    por_ano = teste.assign(ano=pd.to_datetime(teste.corte).dt.year).groupby('ano').apply(lambda g: pd.Series({
        'erro_modelo': (g[escolhido] - g.verdade).abs().mean(),
        'erro_melhor_referencia': min((g[ref] - g.verdade).abs().mean() for ref in REFERENCIAS)}), include_groups=False).round(1)

    OUT.mkdir(parents=True, exist_ok=True)
    r.assign(corte=r.corte.dt.date).round(2).to_csv(OUT / 'internacoes_dengue_retrospectiva.csv', index=False, encoding='utf-8')
    resumo.round(2).to_csv(OUT / 'internacoes_dengue_avaliacao.csv', encoding='utf-8')
    manifesto = {
        'gerado_em': datetime.now(timezone.utc).isoformat(), 'metodo': 'pipeline/modelagem/internacoes.py', 'chave': chave,
        'alvo': 'internações por dengue de residentes em Goiânia com início dos sintomas nas 4 semanas seguintes ao corte',
        'corte': corte_final.date().isoformat(), 'modelo_escolhido_na_validacao': escolhido, 'exibida': exibir,
        'previsao_atual': None if np.isnan(atual) else round(atual), 'faixa_80pct': [round(atual * razao.iloc[0]), round(atual * razao.iloc[1])],
        'ultimas_4_semanas_corrigidas': round(float(ultima.persistencia)),
        'erro_por_ano_teste': por_ano.reset_index().to_dict('records'),
        'avaliacao': {p: {k: round(float(v), 2) for k, v in resumo.loc[p].items()} for p in resumo.index},
        'regra': 'escolher na validação o candidato de menor erro absoluto médio; exibir só se, no teste, superar as duas referências',
        'limitacoes': ['O campo de internação é o do estado final do registro; a avaliação fica um pouco otimista.',
                       'Internações por início dos sintomas, não por data de internação.'],
    }
    (OUT / 'internacoes_dengue_manifesto.json').write_text(json.dumps(manifesto, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(resumo.round(1).T.to_string())
    print(por_ano.to_string())
    print(f'Escolhido: {escolhido}; exibido: {exibir}; previsão atual: {atual:.0f} (faixa {manifesto["faixa_80pct"]})')


if __name__ == '__main__':
    main()
