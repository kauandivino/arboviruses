"""Previsão de 1 a 8 semanas das notificações de dengue, com avaliação contra referências simples.

Em cada data de corte A, o modelo só usa o que estava disponível em A:
  - a série semanal por início dos sintomas digitada até A, corrigida pelo nowcasting de A;
  - o clima da estação A002 até duas semanas antes de A.
Modelo: regressão ridge no logaritmo das contagens, uma por horizonte, com nível recente,
tendência, sazonalidade (seno e cosseno da semana do ano) e, opcionalmente, clima.

A previsão só é exibida se superar, na avaliação retrospectiva e em todos os horizontes, as duas
referências: repetir o nível recente e repetir a mesma semana do ano anterior.
"""
from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline.comum.epidemiologia import inicio_semana
from pipeline.comum.ibge_utils import sha256
from pipeline.modelagem import nowcast as nc

ROOT = nc.ROOT
OUT = nc.OUT
S = nc.SEMANA
HORIZONTES = range(1, 9)
NIVEL = 4                 # semanas no nível recente
JANELA_CLIMA = (9, 2)     # clima das semanas A-9 a A-2
COBERTURA_MINIMA = 0.6
RIDGE = 1.0
MIN_TREINO = 52
CLIMA = ROOT / 'dados/inmet/goiania/horario.csv'


def clima_semanal():
    h = pd.read_csv(CLIMA, usecols=['data_hora_brasilia', 'chuva_mm', 'chuva_mm_status', 'temperatura_c', 'temperatura_c_status', 'umidade_pct', 'umidade_pct_status'])
    data = pd.to_datetime(h.data_hora_brasilia.str[:10])
    h['semana'] = inicio_semana(data)
    linhas = []
    for semana, g in h.groupby('semana'):
        linha = {'semana': semana, 'horas': 168}
        for v in ['chuva_mm', 'temperatura_c', 'umidade_pct']:
            validos = g.loc[g[f'{v}_status'] == 'valido', v]
            linha[f'{v}_soma_valida'] = validos.sum()
            linha[f'{v}_horas_validas'] = len(validos)
        linhas.append(linha)
    return pd.DataFrame(linhas).set_index('semana')


def atributos_clima(clima, origem):
    """Médias por hora válida na janela; ausente se a cobertura for insuficiente (sem preencher horas)."""
    janela = clima.loc[origem - JANELA_CLIMA[0] * S: origem - JANELA_CLIMA[1] * S]
    esperado = (JANELA_CLIMA[0] - JANELA_CLIMA[1] + 1) * 168
    saida = {}
    for v in ['chuva_mm', 'temperatura_c', 'umidade_pct']:
        horas = janela[f'{v}_horas_validas'].sum()
        saida[v] = janela[f'{v}_soma_valida'].sum() / horas if horas >= COBERTURA_MINIMA * esperado else np.nan
    return saida


def serie_corrigida(reg, corte):
    """Série semanal conhecida em `corte`, com as semanas recentes corrigidas pelos fatores de atraso daquele momento."""
    acumulado = nc.triangulo(reg, corte)
    f = nc.fatores(acumulado)
    cauda = np.concatenate([np.cumprod(f[::-1])[::-1], [1.0]])
    defasagem = np.minimum(((corte - acumulado.index) / S).astype(int), nc.MATURACAO)
    observado = acumulado.to_numpy()[np.arange(len(acumulado)), defasagem]
    return pd.Series(observado * cauda[defasagem], index=acumulado.index)


def atributos(serie, origem, clima):
    nivel = serie.loc[origem - (NIVEL - 1) * S: origem]
    anterior = serie.loc[origem - (2 * NIVEL - 1) * S: origem - NIVEL * S]
    if len(nivel) < NIVEL or len(anterior) < NIVEL:
        return None
    x = {'nivel': np.log1p(nivel.mean()), 'tendencia': np.log1p(nivel.mean()) - np.log1p(anterior.mean())}
    if clima is not None:
        c = atributos_clima(clima, origem)
        if any(np.isnan(v) for v in c.values()):
            return None
        x.update(c)
    return x


def sazonal(semana):
    angulo = 2 * np.pi * semana.dayofyear / 365.25
    return {'sen': np.sin(angulo), 'cos': np.cos(angulo)}


def ajustar_prever(serie, origem, feats, h):
    """Ajusta no histórico conhecido em `origem` (pares com alvo até origem - 4 semanas) e prevê origem + h."""
    xs, ys = [], []
    for o, x in feats.items():
        alvo = o + h * S
        if alvo > origem - 4 * S:
            break
        if x is not None:
            xs.append({**x, **sazonal(alvo)})
            ys.append(np.log1p(serie[alvo]))
    x_novo = feats.get(origem)
    if len(xs) < MIN_TREINO or x_novo is None:
        return np.nan
    X = pd.DataFrame(xs)
    media, desvio = X.mean(), X.std().replace(0, 1)
    Z = ((X - media) / desvio).to_numpy()
    Z = np.column_stack([np.ones(len(Z)), Z])
    penal = RIDGE * np.eye(Z.shape[1])
    penal[0, 0] = 0
    beta = np.linalg.solve(Z.T @ Z + penal, Z.T @ np.array(ys))
    z = ((pd.DataFrame([{**x_novo, **sazonal(origem + h * S)}])[X.columns] - media) / desvio).to_numpy()
    return float(np.expm1(np.column_stack([np.ones(1), z]) @ beta)[0])


def prever(reg, origem, clima_semanas, cache_clima):
    serie = serie_corrigida(reg, origem)
    nivel = serie.loc[origem - (NIVEL - 1) * S: origem].mean()
    origens = serie.index[2 * NIVEL:]
    sem_clima = {o: atributos(serie, o, None) for o in origens}
    com_clima = {}
    for o, x in sem_clima.items():
        if o not in cache_clima:
            cache_clima[o] = atributos_clima(clima_semanas, o)
        c = cache_clima[o]
        com_clima[o] = None if x is None or any(np.isnan(v) for v in c.values()) else {**x, **c}
    linhas = []
    for h in HORIZONTES:
        alvo = origem + h * S
        linhas.append({'origem': origem, 'horizonte': h, 'semana': alvo,
                       'persistencia': nivel, 'sazonal_ingenuo': serie.get(alvo - 52 * S, np.nan),
                       'modelo_sem_clima': ajustar_prever(serie, origem, sem_clima, h),
                       'modelo_com_clima': ajustar_prever(serie, origem, com_clima, h)})
    return linhas


METODOS = ['persistencia', 'sazonal_ingenuo', 'modelo_sem_clima', 'modelo_com_clima']


def main():
    reg, _, arquivos = nc.carregar('dengue')
    corte = reg.dig.max() - S
    reg = reg[reg.dig <= corte]
    clima = clima_semanal()
    verdade = nc.verdade(reg, corte)
    origens = pd.date_range(pd.Timestamp('2023-07-02'), verdade.index.max() - max(HORIZONTES) * S, freq='7D')
    cache = {}
    avaliacao = pd.DataFrame([l for o in origens for l in prever(reg, o, clima, cache)])
    avaliacao['verdade'] = avaliacao.semana.map(verdade)
    comparaveis = avaliacao.dropna(subset=METODOS + ['verdade'])

    resumo = []
    for h, g in comparaveis.groupby('horizonte'):
        linha = {'horizonte': h, 'avaliacoes': len(g)}
        for m in METODOS:
            linha[f'erro_abs_medio_{m}'] = (g[m] - g.verdade).abs().mean()
            linha[f'erro_rel_mediano_{m}_pct'] = ((g[m] - g.verdade).abs() / g.verdade).median() * 100
        linha['melhor_referencia'] = min(['persistencia', 'sazonal_ingenuo'], key=lambda m: linha[f'erro_abs_medio_{m}'])
        linha['modelo_supera_referencias'] = linha['erro_abs_medio_modelo_com_clima'] < linha[f"erro_abs_medio_{linha['melhor_referencia']}"]
        linha['clima_melhora_modelo'] = linha['erro_abs_medio_modelo_com_clima'] < linha['erro_abs_medio_modelo_sem_clima']
        resumo.append(linha)
    resumo = pd.DataFrame(resumo)

    # Faixas: quantis da razão verdade/previsão por horizonte, só de origens cuja verdade era conhecida na origem avaliada.
    comparaveis = comparaveis.assign(razao=comparaveis.verdade / comparaveis.modelo_com_clima)
    def faixa(ate, h):
        conhecidos = comparaveis[(comparaveis.horizonte == h) & (comparaveis.semana + nc.MATURACAO * S <= ate)]
        return (np.nan, np.nan) if len(conhecidos) < 20 else tuple(conhecidos.razao.quantile(list(nc.QUANTIS)))
    cobertura = []
    for _, r in comparaveis.iterrows():
        q = faixa(r.origem, r.horizonte)
        if not np.isnan(q[0]):
            cobertura.append({'horizonte': r.horizonte, 'dentro': q[0] * r.modelo_com_clima <= r.verdade <= q[1] * r.modelo_com_clima})
    cobertura = pd.DataFrame(cobertura).groupby('horizonte').dentro.agg(['mean', 'size'])
    resumo['cobertura_faixa_pct'] = resumo.horizonte.map(cobertura['mean'] * 100)
    resumo['avaliacoes_com_faixa'] = resumo.horizonte.map(cobertura['size']).fillna(0).astype(int)

    atual = pd.DataFrame(prever(reg, corte, clima, cache))
    # Exibe só se o modelo superar as referências em todos os horizontes; horizontes isolados podem ser acaso.
    exibir = bool(resumo.modelo_supera_referencias.all())
    atual['exibir'] = exibir
    q = {h: faixa(corte, h) for h in HORIZONTES}
    atual['previsto'] = atual.modelo_com_clima
    atual['inferior'] = [q[h][0] * p for h, p in zip(atual.horizonte, atual.previsto)]
    atual['superior'] = [q[h][1] * p for h, p in zip(atual.horizonte, atual.previsto)]
    atual['semana_fim'] = atual.semana + pd.Timedelta(days=6)
    for c in ['persistencia', 'sazonal_ingenuo', 'modelo_sem_clima', 'modelo_com_clima', 'previsto', 'inferior', 'superior']:
        atual[c] = atual[c].round(0)

    OUT.mkdir(parents=True, exist_ok=True)
    produtos = {
        'previsao_dengue.csv': atual.assign(origem=atual.origem.dt.date, semana=atual.semana.dt.date, semana_fim=atual.semana_fim.dt.date),
        'previsao_dengue_avaliacao.csv': resumo.round(2),
        'previsao_dengue_retrospectiva.csv': avaliacao.assign(origem=avaliacao.origem.dt.date, semana=avaliacao.semana.dt.date).round(1),
    }
    for nome, tabela in produtos.items():
        tabela.to_csv(OUT / nome, index=False, encoding='utf-8')
    manifesto = {
        'gerado_em': datetime.now(timezone.utc).isoformat(), 'metodo': 'pipeline/modelagem/previsao.py',
        'descricao': 'Previsão de 1 a 8 semanas das notificações de dengue de residentes em Goiânia, por semana de início dos sintomas, todas as classificações',
        'origem_atual': corte.date().isoformat(),
        'parametros': {'horizontes': list(HORIZONTES), 'nivel_semanas': NIVEL, 'janela_clima_semanas_antes': JANELA_CLIMA,
                       'cobertura_minima_clima': COBERTURA_MINIMA, 'ridge': RIDGE, 'minimo_pares_treino': MIN_TREINO, 'quantis_faixa': nc.QUANTIS},
        'avaliacao': {'origens': len(origens), 'primeira_origem': origens[0].date().isoformat(), 'ultima_origem': origens[-1].date().isoformat(),
                      'exibida': exibir,
                      'regra': 'exibir somente se o modelo com clima tiver erro absoluto médio menor que o da melhor referência em todos os horizontes'},
        'fontes': [{'arquivo': a.relative_to(ROOT).as_posix(), 'sha256': sha256(a)} for a in [*arquivos, CLIMA]],
        'produtos': [{'arquivo': (OUT / n).relative_to(ROOT).as_posix(), 'sha256': sha256(OUT / n)} for n in produtos],
        'limitacoes': [
            'Avaliada em poucas temporadas (2023 a 2025); um ano epidêmico atípico pode fugir do padrão aprendido.',
            'Usa uma única estação meteorológica para a cidade inteira; não descreve diferenças entre bairros.',
            'Associação estatística com o clima não demonstra causa.',
            'Conta notificações de todas as classificações, não casos confirmados.'],
    }
    (OUT / 'previsao_dengue_manifesto.json').write_text(json.dumps(manifesto, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    colunas = ['horizonte', 'avaliacoes'] + [f'erro_rel_mediano_{m}_pct' for m in METODOS] + ['modelo_supera_referencias', 'clima_melhora_modelo', 'cobertura_faixa_pct']
    print(resumo[colunas].round(1).to_string(index=False))


if __name__ == '__main__':
    main()
