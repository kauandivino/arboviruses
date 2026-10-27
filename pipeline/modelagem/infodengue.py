"""Comparação com o InfoDengue: consistência das séries e registro prospectivo das estimativas.

O InfoDengue usa outra alimentação do SINAN e conta de 18% a 34% mais notificações por semana que
os arquivos públicos do DATASUS, em qualquer recorte (residência, local de notificação, data de
notificação). Por isso os níveis não são comparados diretamente. Registrado em 27/10/2026:

  Consistência (retrospectiva): correlação das séries semanais (log) e razão entre as contagens,
  por ano, nas semanas com pelo menos 52 semanas de maturação.
  Registro prospectivo, a partir de 2026-11-01: a cada coleta, para as 4 semanas mais recentes de
  cada fonte, grava-se o observado e a estimativa (nossa e deles) em
  dados/infodengue/registro_estimativas.csv, que só cresce.
  Avaliação: quando a semana tiver 12 semanas de idade, o erro de cada estimativa é medido contra
  a contagem da própria fonte naquele momento (erro relativo), por idade da semana. Depois de 26
  semanas avaliadas por idade, documenta-se qual estimativa erra menos; nenhuma combinação das
  duas é usada antes disso.
"""
from datetime import datetime, timezone
import json

import numpy as np
import pandas as pd

from pipeline.modelagem import nowcast as nc

ROOT = nc.ROOT
PASTA = ROOT / 'dados/infodengue'
REGISTRO = PASTA / 'registro_estimativas.csv'
INICIO = pd.Timestamp('2026-11-01')
IDADE_CONFERENCIA = 12
COLUNAS = ['consulta', 'fonte', 'semana', 'idade_semanas', 'observado', 'estimado', 'inferior', 'superior']


def consistencia(nosso, externo):
    c = pd.concat([nosso.rename('nosso'), externo.rename('externo')], axis=1, sort=True).dropna()
    c = c[(c.nosso > 0) & (c.externo > 0)]
    por_ano = c.groupby(c.index.year).apply(lambda g: pd.Series({
        'semanas': len(g), 'razao_mediana': (g.externo / g.nosso).median(),
        'correlacao_log': np.corrcoef(np.log(g.nosso), np.log(g.externo))[0, 1] if len(g) > 2 else np.nan}), include_groups=False)
    return por_ano.round(3), float(np.corrcoef(np.log(c.nosso), np.log(c.externo))[0, 1])


def main():
    reg, _, _ = nc.carregar('dengue')
    corte = reg.dig.max() - nc.SEMANA
    final = reg[reg.dig <= corte].groupby('t').size()
    externo = pd.read_csv(PASTA / 'dengue.csv', parse_dates=['semana_inicio']).set_index('semana_inicio')
    maduro = final[final.index <= corte - nc.MATURACAO * nc.SEMANA]
    por_ano, correlacao = consistencia(maduro, externo.casos)

    # Registro prospectivo: só a partir do início registrado, e cada (consulta, fonte, semana) uma única vez.
    manifesto = json.loads((PASTA / 'manifesto.json').read_text(encoding='utf-8'))
    consulta = manifesto['coletas'][0]['consultado_em'][:10]
    registro = pd.read_csv(REGISTRO, dtype={'consulta': str, 'semana': str}) if REGISTRO.exists() else pd.DataFrame(columns=COLUNAS)
    novos = []
    if pd.Timestamp(consulta) >= INICIO and consulta not in set(registro.consulta):
        ultimo_externo = externo.index.max()
        for semana, r in externo.loc[ultimo_externo - 3 * nc.SEMANA:].iterrows():
            novos.append({'consulta': consulta, 'fonte': 'infodengue', 'semana': semana.date().isoformat(),
                          'idade_semanas': int((ultimo_externo - semana) / nc.SEMANA), 'observado': r.casos,
                          'estimado': r.casos_est, 'inferior': r.casos_est_min, 'superior': r.casos_est_max})
        nosso = pd.read_csv(nc.OUT / 'nowcast_dengue.csv', parse_dates=['semana']).dropna(subset=['defasagem']).tail(4)
        for _, r in nosso.iterrows():
            novos.append({'consulta': consulta, 'fonte': 'projeto', 'semana': r.semana.date().isoformat(),
                          'idade_semanas': int(r.defasagem), 'observado': r.observado,
                          'estimado': r.estimado, 'inferior': r.inferior, 'superior': r.superior})
    if novos:
        registro = pd.concat([registro, pd.DataFrame(novos)], ignore_index=True)
        registro[COLUNAS].to_csv(REGISTRO, index=False, encoding='utf-8')

    # Avaliação das estimativas registradas cuja semana já tem 12 semanas de idade em cada fonte.
    avaliacao = []
    for _, r in registro.iterrows():
        semana = pd.Timestamp(r.semana)
        if r.fonte == 'infodengue':
            pronto = externo.index.max() - semana >= IDADE_CONFERENCIA * nc.SEMANA
            verdade = externo.casos.get(semana) if pronto else None
        else:
            pronto = corte - semana >= IDADE_CONFERENCIA * nc.SEMANA
            verdade = final.get(semana) if pronto else None
        if verdade:
            avaliacao.append({'fonte': r.fonte, 'idade_semanas': r.idade_semanas,
                              'erro_rel_estimado': abs(r.estimado - verdade) / verdade, 'erro_rel_observado': abs(r.observado - verdade) / verdade})
    av = pd.DataFrame(avaliacao)
    resumo_av = (av.groupby(['fonte', 'idade_semanas']).agg(n=('erro_rel_estimado', 'size'), erro_rel_mediano_estimado=('erro_rel_estimado', 'median'),
                                                             erro_rel_mediano_observado=('erro_rel_observado', 'median')).round(3).reset_index().to_dict('records')
                 if len(av) else [])
    ultimo = externo.iloc[-1]
    resumo = {'gerado_em': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'metodo': 'pipeline/modelagem/infodengue.py',
              'consistencia': {'correlacao_log_semanal': round(correlacao, 3), 'por_ano': por_ano.reset_index(names='ano').to_dict('records')},
              'registro': {'inicio': INICIO.date().isoformat(), 'linhas': len(registro), 'avaliacao': resumo_av},
              'rt_atual': {'semana': externo.index.max().date().isoformat(), 'se': int(ultimo.SE), 'rt': round(float(ultimo.Rt), 3),
                           'prob_rt_maior_1': round(float(ultimo.p_rt1), 3), 'versao_modelo': str(ultimo.versao_modelo)}}
    (PASTA / 'comparacao.json').write_text(json.dumps(resumo, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'correlação log semanal: {correlacao:.3f}')
    print(por_ano.to_string())
    print('Rt atual:', resumo['rt_atual'])


if __name__ == '__main__':
    main()
