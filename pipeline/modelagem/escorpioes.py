"""Previsão de acidentes com escorpião em Goiânia para os próximos 1 a 3 meses.

Regra definida antes da avaliação:
  Alvo: acidentes por mês de ocorrência (local do acidente em Goiânia), com os dados finais.
  Atributos no fim do mês m, só com registros digitados até então: acidentes do mês m e média dos
  meses m-1 e m-2, o mesmo mês-alvo do ano anterior, temperatura média e chuva do mês m (A002) e
  sazonalidade do mês-alvo.
  Referências: mesmo mês do ano anterior; média do mesmo mês nos três anos anteriores.
  Candidatos: ridge e gradient boosting no log da contagem, um ajuste por horizonte.
  Escolha pelo erro absoluto médio na validação (origens 2017–2020); exibição só se o escolhido
  superar as duas referências nos três horizontes no teste (origens 2021 em diante).
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

from pipeline.comum.epidemiologia import janela_arquivo
from pipeline.comum.ibge_utils import sha256
from pipeline.modelagem import nowcast as nc
from pipeline.modelagem.correlacoes import clima

ROOT = nc.ROOT
OUT = nc.OUT
PASTAS = [ROOT / 'dados/datasus_historico_animais/goiania', ROOT / 'dados/datasus/goiania']
HORIZONTES = [1, 2, 3]
VALIDACAO = (pd.Period('2017-01', 'M'), pd.Period('2020-12', 'M'))
MIN_TREINO = 30
ATRASO = 3  # meses de digitação para considerar um mês completo
GBM = {'max_iter': 150, 'learning_rate': 0.05, 'max_depth': 2, 'min_samples_leaf': 8, 'random_state': 0}
ATRIBUTOS = ['obs_m', 'obs_ant', 'mesmo_mes_ano_ant', 'temperatura_c', 'chuva_mm', 'sen', 'cos']
REFERENCIAS = ['sazonal', 'climatologia']
CANDIDATOS = ['ridge', 'gbm']


def registros():
    partes, arquivos = [], []
    for pasta in PASTAS:
        for f in sorted(pasta.glob('escorpioes_*.csv')):
            d = pd.read_csv(f, dtype=str, usecols=['ANT_MUNIC_', 'ANT_DT_ACI', 'DT_NOTIFIC', 'DT_DIGITA'])
            notif = pd.to_datetime(d.DT_NOTIFIC, errors='coerce')
            d = d[(d.ANT_MUNIC_ == '520870') & notif.between(*janela_arquivo(int(f.stem[-4:])))]
            partes.append(pd.DataFrame({'mes': pd.to_datetime(d.ANT_DT_ACI, errors='coerce').dt.to_period('M'),
                                        'dig': pd.to_datetime(d.DT_DIGITA, errors='coerce').dt.to_period('M')}).dropna())
            arquivos.append(f)
    r = pd.concat(partes, ignore_index=True)
    return r[(r.mes >= pd.Period('2014-01', 'M')) & (r.dig >= r.mes)], arquivos


def clima_mensal():
    # Cada semana entra no mês em que termina: no fim do mês m só há clima observado até m.
    c = clima()
    return c.groupby((c.index + pd.Timedelta(days=6)).to_period('M')).agg({'temperatura_c': 'mean', 'chuva_mm': lambda s: s.sum(min_count=1)})


def montar(reg, clima_mes):
    ultimo = reg.dig.max() - 1  # último mês com digitação completa
    final = reg.groupby('mes').size()
    meses = pd.period_range('2015-01', ultimo, freq='M')
    final = final.reindex(meses, fill_value=0)
    linhas = []
    for m in meses:
        conhecido = reg[reg.dig <= m].groupby('mes').size().reindex(meses, fill_value=0)
        alvo_info = {}
        for h in HORIZONTES:
            alvo = m + h
            alvo_info[f'verdade_{h}'] = float(final[alvo]) if alvo <= ultimo - ATRASO else np.nan
            alvo_info[f'mesmo_mes_ano_ant_{h}'] = float(conhecido.get(alvo - 12, np.nan))
            alvo_info[f'sazonal_{h}'] = float(conhecido.get(alvo - 12, np.nan))
            anteriores = [conhecido.get(alvo - 12 * k, np.nan) for k in (1, 2, 3)]
            alvo_info[f'climatologia_{h}'] = float(np.nanmean(anteriores)) if not all(np.isnan(anteriores)) else np.nan
            alvo_info[f'sen_{h}'] = np.sin(2 * np.pi * alvo.month / 12)
            alvo_info[f'cos_{h}'] = np.cos(2 * np.pi * alvo.month / 12)
        cm = clima_mes.loc[m] if m in clima_mes.index else pd.Series({'temperatura_c': np.nan, 'chuva_mm': np.nan})
        linhas.append({'mes': m, 'obs_m': float(conhecido[m]), 'obs_ant': float(conhecido[[m - 1, m - 2]].mean()) if m - 2 in conhecido.index else np.nan,
                       'temperatura_c': cm.temperatura_c, 'chuva_mm': cm.chuva_mm, **alvo_info})
    return pd.DataFrame(linhas), ultimo


def ajustar_prever(tabela, origem, h, tipo):
    cols = [f'{a}_{h}' if a in ('mesmo_mes_ano_ant', 'sen', 'cos') else a for a in ATRIBUTOS]
    # Só alvos com ATRASO meses de digitação até a origem, como a verdade usada na avaliação.
    treino = tabela[(tabela.mes + h <= origem - ATRASO)].dropna(subset=cols + [f'verdade_{h}'])
    alvo = tabela[tabela.mes == origem].dropna(subset=cols)
    if len(treino) < MIN_TREINO or alvo.empty:
        return np.nan
    modelo = HistGradientBoostingRegressor(**GBM) if tipo == 'gbm' else make_pipeline(StandardScaler(), Ridge(alpha=1.0))
    modelo.fit(treino[cols].to_numpy(), np.log1p(treino[f'verdade_{h}']))
    return float(np.expm1(modelo.predict(alvo[cols].to_numpy())[0]))


def main():
    reg, arquivos = registros()
    clima_mes = clima_mensal()
    entradas = arquivos + [Path(__file__)]
    chave = hashlib.sha256(json.dumps([sha256(f) for f in entradas] + [clima_mes.round(3).to_csv()]).encode()).hexdigest()
    anterior = OUT / 'escorpioes_manifesto.json'
    if anterior.exists() and json.loads(anterior.read_text(encoding='utf-8')).get('chave') == chave:
        print('Avaliação reaproveitada: dados, parâmetros e código inalterados.')
        return
    tabela, ultimo = montar(reg, clima_mes)
    linhas = []
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        for origem in tabela.mes:
            if origem < VALIDACAO[0]:
                continue
            for h in HORIZONTES:
                r = tabela[tabela.mes == origem].iloc[0]
                if np.isnan(r[f'verdade_{h}']):
                    continue
                linhas.append({'origem': origem, 'horizonte': h, 'verdade': r[f'verdade_{h}'], 'sazonal': r[f'sazonal_{h}'],
                               'climatologia': r[f'climatologia_{h}'], **{cand: ajustar_prever(tabela, origem, h, cand) for cand in CANDIDATOS}})
    av = pd.DataFrame(linhas).dropna()
    av['periodo'] = np.where(av.origem <= VALIDACAO[1], 'validacao', 'teste')
    metodos = REFERENCIAS + CANDIDATOS
    resumo = av.groupby(['periodo', 'horizonte']).apply(lambda g: pd.Series({m: (g[m] - g.verdade).abs().mean() for m in metodos} | {'n': len(g)}), include_groups=False).round(2)
    val = resumo.loc['validacao']
    escolhido = min(CANDIDATOS, key=lambda m: val[m].mean())
    teste = resumo.loc['teste']
    exibir = bool(all(teste.loc[h, escolhido] < min(teste.loc[h, r] for r in REFERENCIAS) for h in HORIZONTES))

    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        previsao = []
        for h in HORIZONTES:
            p = ajustar_prever(tabela, ultimo, h, escolhido)
            erros = av[(av.periodo == 'teste') & (av.horizonte == h)]
            razao = (erros.verdade / erros[escolhido].clip(lower=1)).quantile([0.1, 0.9])
            previsao.append({'mes': str(ultimo + h), 'horizonte': h, 'previsto': None if np.isnan(p) else round(p),
                             'faixa_80pct': None if np.isnan(p) else [round(p * razao.iloc[0]), round(p * razao.iloc[1])]})
    historico = reg.groupby('mes').size()
    manifesto = {'gerado_em': datetime.now(timezone.utc).isoformat(), 'metodo': 'pipeline/modelagem/escorpioes.py', 'chave': chave,
                 'ultimo_mes_completo': str(ultimo), 'modelo_escolhido_na_validacao': escolhido, 'exibida': exibir,
                 'previsao': previsao,
                 'avaliacao': {p: {str(h): {k: float(v) for k, v in resumo.loc[(p, h)].items()} for h in HORIZONTES} for p in ['validacao', 'teste']},
                 'serie_mensal': [{'mes': str(m), 'acidentes': int(n)} for m, n in historico.items() if m <= ultimo],
                 'regra': 'escolher na validação o candidato de menor erro médio; exibir só se, no teste, superar as duas referências nos três horizontes',
                 'fontes': [{'arquivo': f.relative_to(ROOT).as_posix(), 'sha256': sha256(f)} for f in arquivos if f.parent.name == 'goiania' and 'historico' not in str(f)]}
    (OUT / 'escorpioes_manifesto.json').write_text(json.dumps(manifesto, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    av.assign(origem=av.origem.astype(str)).round(2).to_csv(OUT / 'escorpioes_retrospectiva.csv', index=False, encoding='utf-8')
    print(resumo.to_string())
    print(f'Escolhido: {escolhido}; exibido: {exibir}; previsão: {previsao}')


if __name__ == '__main__':
    main()
