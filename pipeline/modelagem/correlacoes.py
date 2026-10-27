"""Correlações entre dengue, clima, municípios vizinhos, chikungunya e escorpiões (2014 em diante).

Cada relação é medida de duas formas:
  bruta — as duas séries como são (inclui o fato de ambas subirem na mesma época do ano);
  sem sazonalidade — desvio de cada semana (ou mês) em relação à média daquela semana nos anos
  disponíveis; só esta indica relação além do calendário.
Clima: semanas com menos de 90% (chuva) ou 60% (temperatura, umidade) das horas medidas ficam
sem valor. Séries de casos: contagens por início dos sintomas, só semanas com 12 ou mais semanas
de idade (registros quase completos). Picos: semana de maior contagem em cada temporada (julho a
junho), comparada entre Goiânia, vizinhos e chikungunya.
"""
from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline.comum.epidemiologia import janela_arquivo
from pipeline.modelagem.previsao import clima_semanal
from pipeline.modelagem import nowcast as nc

ROOT = nc.ROOT
OUT = nc.OUT
REGIONAL = ROOT / 'dados/regional'
S = nc.SEMANA
LAGS = range(0, 17)


def forca(r):
    a = abs(r)
    return 'forte' if a >= 0.5 else 'moderada' if a >= 0.3 else 'fraca' if a >= 0.15 else 'muito fraca'


def serie(agravo, grupo):
    arquivos = sorted(REGIONAL.glob(f'{agravo}_go_*.csv'))
    d = pd.concat([pd.read_csv(f, parse_dates=['semana_inicio', 'semana_digitacao']) for f in arquivos], ignore_index=True)
    d = d[d.grupo == grupo]
    s = d.groupby('semana_inicio').notificacoes.sum()
    limite = d.semana_digitacao.max() - 12 * S
    s = s.reindex(pd.date_range(s.index.min(), limite, freq='7D'), fill_value=0)
    return s


def anomalia(s):
    """Desvio em relação à média da mesma semana do ano (semana ISO aproximada pelo dia do ano)."""
    semana_ano = np.minimum((s.index.dayofyear - 1) // 7, 51)
    return s - s.groupby(semana_ano).transform('mean')


def clima():
    c = clima_semanal()
    out = pd.DataFrame(index=c.index)
    out['chuva_mm'] = np.where(c.chuva_mm_horas_validas >= 0.9 * 168, c.chuva_mm_soma_valida, np.nan)
    for v in ['temperatura_c', 'umidade_pct']:
        out[v] = np.where(c[f'{v}_horas_validas'] >= 0.6 * 168, c[f'{v}_soma_valida'] / c[f'{v}_horas_validas'].replace(0, np.nan), np.nan)
    return out


def correlacao_defasada(y, x, lags):
    bruta, anom = [], []
    ya, xa = anomalia(y), anomalia(x)
    for lag in lags:
        par = pd.concat([y, x.shift(lag, freq='7D')], axis=1, join='inner').dropna()
        par_a = pd.concat([ya, xa.shift(lag, freq='7D')], axis=1, join='inner').dropna()
        bruta.append(round(float(par.corr().iloc[0, 1]), 3))
        anom.append(round(float(par_a.corr().iloc[0, 1]), 3))
    return bruta, anom


def picos(s, inicio=2015):
    """Semana de pico de cada temporada (julho a junho)."""
    saida = {}
    for ano in range(inicio, s.index.max().year + 1):
        janela = s[(s.index >= pd.Timestamp(f'{ano - 1}-07-01')) & (s.index < pd.Timestamp(f'{ano}-07-01'))]
        if len(janela) >= 40 and janela.max() > 0:
            saida[ano] = janela.idxmax()
    return saida


def diferenca_picos(a, b, minimo_b=None, s_b=None):
    pa, pb = picos(a), picos(b)
    difs = {}
    for ano in sorted(set(pa) & set(pb)):
        if minimo_b and s_b is not None:
            janela = s_b[(s_b.index >= pd.Timestamp(f'{ano - 1}-07-01')) & (s_b.index < pd.Timestamp(f'{ano}-07-01'))]
            if janela.sum() < minimo_b:
                continue
        difs[ano] = int((pb[ano] - pa[ano]) / S)
    return difs


def mensal_escorpioes():
    pastas = [ROOT / 'dados/datasus_historico_animais/goiania', ROOT / 'dados/datasus/goiania']
    partes = []
    for pasta in pastas:
        for f in sorted(pasta.glob('escorpioes_*.csv')):
            d = pd.read_csv(f, dtype=str, usecols=['ANT_MUNIC_', 'ANT_DT_ACI', 'DT_NOTIFIC'])
            ano = int(f.stem[-4:])
            notif = pd.to_datetime(d.DT_NOTIFIC, errors='coerce')
            d = d[(d.ANT_MUNIC_ == '520870') & notif.between(*janela_arquivo(ano))]
            partes.append(pd.to_datetime(d.ANT_DT_ACI, errors='coerce').dropna())
    datas = pd.concat(partes)
    datas = datas[datas >= '2014-01-01']
    return datas.dt.to_period('M').value_counts().sort_index()


def main():
    dengue = serie('dengue', 'goiania')
    vizinhos = serie('dengue', 'vizinhos')
    chik = serie('chikungunya', 'goiania')
    c = clima()
    y = np.log1p(dengue)
    resultado = {'gerado_em': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'metodo': 'pipeline/modelagem/correlacoes.py',
                 'periodo': [dengue.index.min().date().isoformat(), dengue.index.max().date().isoformat()], 'clima_dengue': {}}
    for v in ['chuva_mm', 'temperatura_c', 'umidade_pct']:
        bruta, anom = correlacao_defasada(y, c[v], LAGS)
        i = int(np.argmax(anom)) if v != 'temperatura_c' or max(anom) >= abs(min(anom)) else int(np.argmin(anom))
        resultado['clima_dengue'][v] = {'lags': list(LAGS), 'r_bruta': bruta, 'r_sem_sazonalidade': anom,
                                        'melhor_lag': list(LAGS)[i], 'r_melhor': anom[i], 'forca': forca(anom[i]),
                                        'r_bruta_no_melhor_lag': bruta[i]}

    # Vizinhos e chikungunya: diferença de semanas entre os picos de cada temporada.
    dif_viz = diferenca_picos(dengue, vizinhos)
    dif_chik = diferenca_picos(dengue, chik, minimo_b=100, s_b=chik)
    def resumo_picos(d):
        v = list(d.values())
        return {'por_temporada': {str(k): x for k, x in d.items()}, 'mediana_semanas': float(np.median(v)) if v else None,
                'antes': sum(x < -1 for x in v), 'juntos': sum(abs(x) <= 1 for x in v), 'depois': sum(x > 1 for x in v), 'temporadas': len(v)}
    resultado['vizinhos'] = resumo_picos(dif_viz)
    corr_viz = pd.concat([np.log1p(dengue), np.log1p(vizinhos)], axis=1).dropna().corr().iloc[0, 1]
    resultado['vizinhos']['correlacao_semanal'] = round(float(corr_viz), 3)
    resultado['chikungunya'] = resumo_picos(dif_chik)

    # Escorpiões e temperatura por mês.
    esc = mensal_escorpioes()
    c_mes = c.groupby(c.index.to_period('M')).agg({'temperatura_c': 'mean', 'chuva_mm': lambda s: s.sum(min_count=1)})
    tab = pd.concat([esc.rename('acidentes'), c_mes], axis=1, join='inner').dropna(subset=['acidentes', 'temperatura_c'])
    tab = tab[tab.index < esc.index.max()]  # último mês pode estar incompleto
    mes = tab.index.month
    anom = tab - tab.groupby(mes).transform('mean')
    perfil = tab.groupby(mes).mean()
    resultado['escorpioes'] = {
        'meses': len(tab), 'r_temperatura_bruta': round(float(tab.corr().loc['acidentes', 'temperatura_c']), 3),
        'r_temperatura_sem_sazonalidade': round(float(anom.corr().loc['acidentes', 'temperatura_c']), 3),
        'r_chuva_bruta': round(float(tab.corr().loc['acidentes', 'chuva_mm']), 3),
        'perfil_mensal': [{'mes': int(m), 'acidentes': round(float(r.acidentes), 1), 'temperatura_c': round(float(r.temperatura_c), 1)} for m, r in perfil.iterrows()],
    }
    resultado['escorpioes']['forca_temperatura'] = forca(resultado['escorpioes']['r_temperatura_bruta'])

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'correlacoes.json').write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    for v, r in resultado['clima_dengue'].items():
        print(f"{v}: melhor defasagem {r['melhor_lag']} sem; r sem sazonalidade {r['r_melhor']} ({r['forca']}); bruta {r['r_bruta_no_melhor_lag']}")
    print('vizinhos:', {k: v for k, v in resultado['vizinhos'].items() if k != 'por_temporada'}, resultado['vizinhos']['por_temporada'])
    print('chik:', {k: v for k, v in resultado['chikungunya'].items() if k != 'por_temporada'}, resultado['chikungunya']['por_temporada'])
    print('escorpioes:', {k: v for k, v in resultado['escorpioes'].items() if k != 'perfil_mensal'})


if __name__ == '__main__':
    main()
