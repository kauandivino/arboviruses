"""Diagrama de controle da dengue (método dos quartis) e avaliação do alerta nas temporadas passadas.

Para cada semana epidemiológica de um ano Y, o esperado vem das contagens da mesma semana e
das vizinhas (±1) nos cinco anos anteriores, como eram conhecidas no início de Y: 15 valores.
Zonas: abaixo do 1º quartil, até a mediana, até o 3º quartil e acima do 3º quartil (epidêmica).
Alerta: duas semanas seguidas na zona epidêmica, usando em cada data só o que estava digitado,
corrigido pelo nowcasting daquele momento.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline.comum.epidemiologia import inicio_ano_epidemiologico
from pipeline.comum.ibge_utils import sha256
from pipeline.modelagem import nowcast as nc
from pipeline.modelagem import previsao
from pipeline.modelagem.previsao import serie_corrigida

ROOT = nc.ROOT
OUT = nc.OUT
S = nc.SEMANA
ANOS_REFERENCIA = 5
VIZINHAS = 1
SEMANAS_SEGUIDAS = 2


def semana_epidemiologica(semana):
    """(ano epidemiológico, número da SE) do domingo que inicia a semana."""
    ano = semana.year + 1 if semana >= inicio_ano_epidemiologico(semana.year + 1) else semana.year
    ano = ano - 1 if semana < inicio_ano_epidemiologico(ano) else ano
    return ano, int((semana - inicio_ano_epidemiologico(ano)) / S) + 1


def canal(serie_conhecida, ano):
    """Quartis por SE do ano `ano`, a partir dos cinco anos anteriores na série conhecida."""
    tabela = pd.DataFrame({'n': serie_conhecida})
    tabela[['ano', 'se']] = [semana_epidemiologica(s) for s in tabela.index]
    anteriores = tabela[tabela.ano.between(ano - ANOS_REFERENCIA, ano - 1)]
    if anteriores.ano.nunique() < ANOS_REFERENCIA:
        return None
    linhas = []
    for se in range(1, 54):
        vizinhas = {((se + d - 1) % 52) + 1 for d in range(-VIZINHAS, VIZINHAS + 1)} if se <= 52 else {51, 52, 53}
        valores = anteriores[anteriores.se.isin(vizinhas)].n
        q1, mediana, q3 = valores.quantile([0.25, 0.5, 0.75])
        linhas.append({'se': se, 'q1': q1, 'mediana': mediana, 'q3': q3, 'valores_referencia': len(valores)})
    return pd.DataFrame(linhas).set_index('se')


def zona(valor, limites):
    if valor > limites.q3:
        return 'epidemica'
    if valor > limites.mediana:
        return 'alerta'
    if valor > limites.q1:
        return 'seguranca'
    return 'sucesso'


def fator_atual(reg, semana):
    """Fator de correção aplicado à própria semana (defasagem zero) com os dados conhecidos nela."""
    f = nc.fatores(nc.triangulo(reg, semana))
    return float(np.prod(f))


def temporada(reg, ano, corte, limite_fator=np.inf):
    """Acompanha o ano epidemiológico semana a semana, como teria sido visto em tempo real."""
    inicio = inicio_ano_epidemiologico(ano)
    fim = min(inicio_ano_epidemiologico(ano + 1) - S, corte)
    limites = canal(serie_corrigida(reg, inicio - S), ano)
    if limites is None:
        return None
    linhas, seguidas = [], 0
    for semana in pd.date_range(inicio, fim, freq='7D'):
        # O valor da semana só depende das coortes recentes (fatores usam no máximo 20 + 53 semanas).
        recente = reg[reg.t >= semana - 80 * S]
        conhecida = serie_corrigida(recente, semana)
        se = semana_epidemiologica(semana)[1]
        # Fator fora do testado no nowcasting: zona indeterminada, não conta para o alerta.
        z = 'indeterminada' if fator_atual(recente, semana) > limite_fator else zona(conhecida[semana], limites.loc[se])
        seguidas = seguidas + 1 if z == 'epidemica' else 0
        linhas.append({'semana': semana, 'ano': ano, 'se': se, 'tempo_real': conhecida[semana], 'zona_tempo_real': z,
                       'alerta': seguidas >= SEMANAS_SEGUIDAS, **limites.loc[se].to_dict()})
    return pd.DataFrame(linhas)


def main():
    reg, _, arquivos = nc.carregar('dengue')
    corte = reg.dig.max() - S
    reg = reg[reg.dig <= corte]
    final = serie_corrigida(reg, corte)
    ano_atual = semana_epidemiologica(corte)[0]
    # A simulação semana a semana leva alguns minutos; só é refeita se dados, parâmetros ou código mudarem.
    entradas = [*arquivos, Path(__file__), Path(nc.__file__), Path(previsao.__file__), OUT / 'nowcast_dengue_manifesto.json']
    chave = hashlib.sha256(json.dumps([sha256(f) for f in entradas] + [ANOS_REFERENCIA, VIZINHAS, SEMANAS_SEGUIDAS]).encode()).hexdigest()
    anterior = OUT / 'alerta_dengue_manifesto.json'
    if anterior.exists() and json.loads(anterior.read_text(encoding='utf-8')).get('chave') == chave:
        print('Simulação reaproveitada: dados, parâmetros e código inalterados.')
        return
    limite_fator = json.loads((OUT / 'nowcast_dengue_manifesto.json').read_text(encoding='utf-8'))['limite_fator_por_defasagem']['0']
    temporadas = [t for ano in range(2014 + ANOS_REFERENCIA, ano_atual + 1) if (t := temporada(reg, ano, corte, limite_fator)) is not None]
    semanas = pd.concat(temporadas, ignore_index=True)
    semanas['final'] = semanas.semana.map(final)
    semanas['zona_final'] = [zona(f, r) for f, (_, r) in zip(semanas.final, semanas[['q1', 'mediana', 'q3']].iterrows())]

    avaliacao = []
    for ano, g in semanas.groupby('ano'):
        completa = ano < ano_atual
        pico = g.loc[g.final.idxmax()]
        primeiro = g[g.alerta].semana.min()
        avaliacao.append({
            'ano': ano, 'temporada_completa': completa, 'notificacoes': int(round(g.final.sum())),
            'pico_semana': pico.semana.date().isoformat(), 'pico_se': int(pico.se), 'pico_notificacoes': int(round(pico.final)),
            'primeiro_alerta': None if pd.isna(primeiro) else primeiro.date().isoformat(),
            'semanas_antes_do_pico': None if pd.isna(primeiro) else int((pico.semana - primeiro) / S),
            'semanas_em_alerta': int(g.alerta.sum()), 'semanas_indeterminadas': int((g.zona_tempo_real == 'indeterminada').sum()), 'semanas_zona_epidemica_final': int((g.zona_final == 'epidemica').sum()),
            # Fração das semanas em alerta que, com os dados finais, estavam de fato na zona epidêmica.
            'alertas_confirmados_pct': None if not g.alerta.any() else round(float((g[g.alerta].zona_final == 'epidemica').mean() * 100), 1),
        })
    avaliacao = pd.DataFrame(avaliacao)

    OUT.mkdir(parents=True, exist_ok=True)
    for c in ['tempo_real', 'final', 'q1', 'mediana', 'q3']:
        semanas[c] = semanas[c].round(0)
    produtos = {
        'alerta_dengue_semanas.csv': semanas.assign(semana=semanas.semana.dt.date),
        'alerta_dengue_avaliacao.csv': avaliacao,
    }
    for nome, tabela in produtos.items():
        tabela.to_csv(OUT / nome, index=False, encoding='utf-8')
    manifesto = {
        'gerado_em': datetime.now(timezone.utc).isoformat(), 'metodo': 'pipeline/modelagem/alerta.py',
        'descricao': 'Diagrama de controle (quartis) das notificações de dengue de residentes em Goiânia por semana de início dos sintomas',
        'data_corte': corte.date().isoformat(), 'ano_atual': ano_atual, 'chave': chave,
        'parametros': {'anos_referencia': ANOS_REFERENCIA, 'semanas_vizinhas': VIZINHAS, 'semanas_seguidas_para_alerta': SEMANAS_SEGUIDAS},
        'fontes': [{'arquivo': a.relative_to(ROOT).as_posix(), 'sha256': sha256(a)} for a in arquivos],
        'produtos': [{'arquivo': (OUT / n).relative_to(ROOT).as_posix(), 'sha256': sha256(OUT / n)} for n in produtos],
        'limitacoes': [
            'Usa contagens, não incidência: a população de Goiânia cresceu no período e não há estimativa anual oficial por semana.',
            'Os cinco anos de referência incluem anos epidêmicos; o 3º quartil fica mais alto depois deles.',
            'Na semana corrente, o valor em tempo real depende do nowcasting e tem incerteza alta.'],
    }
    (OUT / 'alerta_dengue_manifesto.json').write_text(json.dumps(manifesto, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(avaliacao.to_string(index=False))


if __name__ == '__main__':
    main()
