"""Avaliação prospectiva, registrada antes dos dados: chance de a dengue ficar acima do habitual.

A regra abaixo foi registrada no git em 27/10/2026, antes de qualquer previsão desta série.
Não pode ser alterada; uma regra nova exige outro registro, com outra data de início.

  Modelo: regressão logística (C=1) com um único atributo, a razão (log) entre o nível das
  últimas 4 semanas de Goiânia e o 3º quartil do diagrama de controle na semana do corte, com
  séries corrigidas pelo nowcasting do corte. Treino: todas as origens desde 2019 cujo evento
  já era conhecido no corte (mesma montagem de pipeline/modelagem/risco.py).
  Evento: média das 4 semanas seguintes ao corte acima do 3º quartil daquelas semanas.
  Referência: frequência do evento nas mesmas origens de treino.
  Previsões: uma por semana de corte a partir de INICIO, gravadas uma única vez em
  dados/modelagem/registro_prospectivo.csv (nunca reescritas).
  Conferência: o evento é medido com os dados disponíveis 12 semanas depois da última semana
  da janela (o nowcasting erra cerca de 7% nessa idade).
  Exibição: só depois de 26 previsões conferidas, se o Brier do modelo for menor que o da
  referência e menor que 0,25 (o de quem sempre diz 50%).
"""
from datetime import datetime, timezone
import json

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from pipeline.modelagem import risco as rc
from pipeline.modelagem.alerta import semana_epidemiologica

INICIO = pd.Timestamp('2026-11-01')
CONFERENCIA_SEMANAS = 12
MINIMO_CONFERIDAS = 26
BRIER_MAXIMO = 0.25
REGISTRO = rc.OUT / 'registro_prospectivo.csv'
COLUNAS = ['corte', 'registrado_em', 'probabilidade', 'referencia', 'razao_q3', 'treino_origens', 'treino_eventos']
S = rc.S


def tabela_goiania(grupo, ate):
    """Origens desde 2019 com razão nível/3º quartil e 3º quartil médio das semanas-alvo."""
    canais, linhas = {}, []
    def q3(semana):
        ano, se = semana_epidemiologica(semana)
        if ano not in canais:
            canais[ano] = rc.canal_ano(grupo.serie(pd.Timestamp(f'{ano}-01-01') - S), ano)
        return canais[ano][se] if canais[ano] else np.nan
    for corte in pd.date_range(rc.VALIDACAO[0], ate, freq='7D'):
        serie = grupo.serie(corte)
        nivel = np.log1p(serie.loc[corte - (rc.NIVEL - 1) * S: corte].mean())
        linhas.append({'corte': corte, 'razao_q3': nivel - np.log1p(q3(corte)),
                       'q3_alvo': float(np.mean([q3(corte + h * S) for h in range(1, rc.HORIZONTE + 1)]))})
    return pd.DataFrame(linhas)


def prever(grupo, tabela, corte):
    tabela = tabela.assign(evento_em_corte=rc.evento_conhecido(tabela, {'goiania': grupo}, corte))
    treino = tabela[tabela.corte + (rc.HORIZONTE + 4) * S <= corte].dropna(subset=['evento_em_corte'])
    alvo = tabela[tabela.corte == corte].iloc[0]
    modelo = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=2000))
    modelo.fit(treino[['razao_q3']], treino.evento_em_corte)
    p = float(modelo.predict_proba(pd.DataFrame({'razao_q3': [alvo.razao_q3]}))[0, 1])
    return p, float(treino.evento_em_corte.mean()), float(alvo.razao_q3), len(treino), int(treino.evento_em_corte.sum())


def conferir(registro, grupo, tabela, corte_dados):
    """Evento observado para as previsões cuja janela de conferência já passou."""
    serie = grupo.serie(corte_dados)
    q3 = tabela.set_index('corte').q3_alvo
    saida = []
    for _, r in registro.iterrows():
        c = pd.Timestamp(r.corte)
        pronto = c + (rc.HORIZONTE + CONFERENCIA_SEMANAS) * S <= corte_dados
        media = serie.reindex([c + h * S for h in range(1, rc.HORIZONTE + 1)]).mean() if pronto else np.nan
        saida.append(np.nan if not pronto or c not in q3.index else float(media > q3[c]))
    return registro.assign(evento=saida)


def main():
    regional = rc.carregar_regional()
    grupo = rc.Grupo(regional[regional.grupo == 'goiania'])
    corte = regional.semana_digitacao.max() - S
    registro = pd.read_csv(REGISTRO) if REGISTRO.exists() else pd.DataFrame(columns=COLUNAS)
    tabela = tabela_goiania(grupo, corte)
    novos = []
    # Uma previsão por semana a partir do início registrado; semanas já gravadas não são refeitas.
    for c in pd.date_range(INICIO, corte, freq='7D'):
        if c.date().isoformat() in set(registro.corte.astype(str)):
            continue
        if c != corte:
            continue  # previsões só no próprio corte; semanas perdidas ficam ausentes, não reconstruídas
        p, ref, razao, n, ev = prever(grupo, tabela, c)
        novos.append({'corte': c.date().isoformat(), 'registrado_em': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                      'probabilidade': round(p, 4), 'referencia': round(ref, 4), 'razao_q3': round(razao, 4),
                      'treino_origens': n, 'treino_eventos': ev})
    if novos:
        registro = pd.concat([registro, pd.DataFrame(novos)], ignore_index=True)
        registro[COLUNAS].to_csv(REGISTRO, index=False, encoding='utf-8')
    conferido = conferir(registro, grupo, tabela, corte).dropna(subset=['evento']) if len(registro) else pd.DataFrame()
    n = len(conferido)
    brier_modelo = float(np.mean((conferido.probabilidade - conferido.evento) ** 2)) if n else None
    brier_ref = float(np.mean((conferido.referencia - conferido.evento) ** 2)) if n else None
    exibir = bool(n >= MINIMO_CONFERIDAS and brier_modelo < brier_ref and brier_modelo < BRIER_MAXIMO)
    resumo = {'gerado_em': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'registrado_em': '2026-10-27',
              'inicio': INICIO.date().isoformat(), 'corte_atual': corte.date().isoformat(),
              'previsoes': len(registro), 'conferidas': n, 'brier_modelo': brier_modelo, 'brier_referencia': brier_ref,
              'exibir': exibir, 'ultima_probabilidade': None if not len(registro) else float(registro.probabilidade.iloc[-1]),
              'criterio': f'exibir após {MINIMO_CONFERIDAS} previsões conferidas, se Brier < referência e < {BRIER_MAXIMO}'}
    (rc.OUT / 'registro_prospectivo_resumo.json').write_text(json.dumps(resumo, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(resumo, ensure_ascii=False))


if __name__ == '__main__':
    main()
