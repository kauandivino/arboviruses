"""Previsão de 1 a 8 semanas das notificações de dengue, com seleção e teste separados no tempo.

Em cada data de corte A, os modelos só usam o que estava disponível em A:
  - a série semanal por início dos sintomas digitada até A, corrigida pelo nowcasting de A;
  - o clima da estação A002 até duas semanas antes de A.

Candidatos definidos antes da avaliação, um ajuste por horizonte, no logaritmo das contagens:
  - ridge_sem_clima: nível e tendência recentes e sazonalidade;
  - ridge_com_clima: o mesmo, mais chuva, temperatura e umidade;
  - gbm_com_clima: gradient boosting com os mesmos atributos.
Referências: repetir o nível das últimas 4 semanas e repetir a mesma semana do ano anterior.

Regra: o candidato com menor erro absoluto médio nas origens de validação (2016–2020) é
escolhido; ele só é exibido se, nas origens de teste (2021 em diante, nunca usadas na escolha),
tiver erro menor que a melhor referência em todos os horizontes.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import warnings

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

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
CLIMA = [ROOT / 'dados/inmet_historico/goiania/horario.csv', ROOT / 'dados/inmet/goiania/horario.csv']
VALIDACAO = (pd.Timestamp('2016-01-03'), pd.Timestamp('2020-12-27'))
TESTE_INICIO = pd.Timestamp('2021-01-03')
REFERENCIAS = ['persistencia', 'sazonal_ingenuo']
CANDIDATOS = ['ridge_sem_clima', 'ridge_com_clima', 'gbm_com_clima']
METODOS = REFERENCIAS + CANDIDATOS
GBM = {'max_iter': 150, 'learning_rate': 0.05, 'max_depth': 3, 'min_samples_leaf': 10, 'random_state': 0}
PARAMETROS = {'horizontes': list(HORIZONTES), 'nivel_semanas': NIVEL, 'janela_clima_semanas_antes': JANELA_CLIMA,
              'cobertura_minima_clima': COBERTURA_MINIMA, 'ridge': RIDGE, 'minimo_pares_treino': MIN_TREINO,
              'quantis_faixa': nc.QUANTIS, 'gbm': GBM, 'validacao': [str(VALIDACAO[0].date()), str(VALIDACAO[1].date())]}
NOMES = {'persistencia': 'Repetir as últimas 4 semanas', 'sazonal_ingenuo': 'Mesma semana do ano anterior',
         'ridge_sem_clima': 'Ridge sem clima', 'ridge_com_clima': 'Ridge com clima', 'gbm_com_clima': 'Gradient boosting com clima'}


def clima_semanal():
    colunas = ['data_hora_brasilia', 'chuva_mm', 'chuva_mm_status', 'temperatura_c', 'temperatura_c_status', 'umidade_pct', 'umidade_pct_status']
    h = pd.concat([pd.read_csv(c, usecols=colunas) for c in CLIMA if c.exists()], ignore_index=True)
    h['semana'] = inicio_semana(pd.to_datetime(h.data_hora_brasilia.str[:10]))
    linhas = []
    for semana, g in h.groupby('semana'):
        linha = {'semana': semana}
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


def pares_treino(serie, origem, feats, h):
    """Pares (atributos em o, contagem em o + h) com alvo até origem - 4 semanas: nada posterior entra no ajuste."""
    xs, ys = [], []
    for o, x in feats.items():
        alvo = o + h * S
        if alvo > origem - 4 * S:
            break
        if x is not None:
            xs.append({**x, **sazonal(alvo)})
            ys.append(np.log1p(serie[alvo]))
    return xs, ys


def ajustar_prever(serie, origem, feats, h, tipo='ridge'):
    xs, ys = pares_treino(serie, origem, feats, h)
    x_novo = feats.get(origem)
    if len(xs) < MIN_TREINO or x_novo is None:
        return np.nan
    X = pd.DataFrame(xs)
    novo = pd.DataFrame([{**x_novo, **sazonal(origem + h * S)}])[X.columns]
    if tipo == 'gbm':
        modelo = HistGradientBoostingRegressor(**GBM)
        modelo.fit(X, ys)
        return float(np.expm1(modelo.predict(novo)[0]))
    media, desvio = X.mean(), X.std().replace(0, 1)
    Z = np.column_stack([np.ones(len(X)), ((X - media) / desvio).to_numpy()])
    penal = RIDGE * np.eye(Z.shape[1])
    penal[0, 0] = 0
    beta = np.linalg.solve(Z.T @ Z + penal, Z.T @ np.array(ys))
    z = np.column_stack([np.ones(1), ((novo - media) / desvio).to_numpy()])
    return float(np.expm1(z @ beta)[0])


def prever(reg, origem, clima_semanas, cache_clima):
    serie = serie_corrigida(reg, origem)
    nivel = serie.loc[origem - (NIVEL - 1) * S: origem].mean()
    sem_clima = {o: atributos(serie, o, None) for o in serie.index[2 * NIVEL:]}
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
                       'ridge_sem_clima': ajustar_prever(serie, origem, sem_clima, h),
                       'ridge_com_clima': ajustar_prever(serie, origem, com_clima, h),
                       'gbm_com_clima': ajustar_prever(serie, origem, com_clima, h, 'gbm')})
    return linhas


def erros_por_horizonte(tabela):
    linhas = []
    for h, g in tabela.groupby('horizonte'):
        linha = {'horizonte': h, 'avaliacoes': len(g)}
        for m in METODOS:
            linha[f'erro_abs_medio_{m}'] = (g[m] - g.verdade).abs().mean()
            linha[f'erro_rel_mediano_{m}_pct'] = ((g[m] - g.verdade).abs() / g.verdade).median() * 100
        linhas.append(linha)
    return pd.DataFrame(linhas)


def main():
    reg, _, arquivos = nc.carregar('dengue')
    corte = reg.dig.max() - S
    reg = reg[reg.dig <= corte]
    clima = clima_semanal()
    verdade = nc.verdade(reg, corte)
    origens = pd.date_range(VALIDACAO[0], verdade.index.max() - max(HORIZONTES) * S, freq='7D')
    cache = {}
    # A avaliação retrospectiva leva cerca de 25 minutos; só é refeita se dados, parâmetros ou código mudarem.
    fontes = [*arquivos, *[c for c in CLIMA if c.exists()], Path(__file__), Path(nc.__file__)]
    chave = hashlib.sha256(json.dumps([sha256(f) for f in fontes] + [str(PARAMETROS)]).encode()).hexdigest()
    anterior = OUT / 'previsao_dengue_manifesto.json'
    retrospectiva = OUT / 'previsao_dengue_retrospectiva.csv'
    if anterior.exists() and retrospectiva.exists() and json.loads(anterior.read_text(encoding='utf-8')).get('chave_avaliacao') == chave:
        print('Avaliação retrospectiva reaproveitada: dados, parâmetros e código inalterados.')
        avaliacao = pd.read_csv(retrospectiva, parse_dates=['origem', 'semana']).drop(columns=['verdade', 'periodo'])
    else:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            avaliacao = pd.DataFrame([l for o in origens for l in prever(reg, o, clima, cache)])
    avaliacao['verdade'] = avaliacao.semana.map(verdade)
    avaliacao['periodo'] = np.where(avaliacao.origem <= VALIDACAO[1], 'validacao', 'teste')
    comparaveis = avaliacao.dropna(subset=METODOS + ['verdade'])

    validacao = erros_por_horizonte(comparaveis[comparaveis.periodo == 'validacao']).assign(periodo='validacao')
    teste = erros_por_horizonte(comparaveis[comparaveis.periodo == 'teste']).assign(periodo='teste')
    escolhido = min(CANDIDATOS, key=lambda m: validacao[f'erro_abs_medio_{m}'].mean())
    melhor_ref = teste[[f'erro_abs_medio_{m}' for m in REFERENCIAS]].min(axis=1)
    teste['modelo_escolhido'] = escolhido
    teste['modelo_supera_referencias'] = teste[f'erro_abs_medio_{escolhido}'] < melhor_ref
    teste['melhor_referencia'] = teste[[f'erro_abs_medio_{m}' for m in REFERENCIAS]].idxmin(axis=1).str.removeprefix('erro_abs_medio_')
    exibir = bool(teste.modelo_supera_referencias.all())

    # Faixas do modelo escolhido: quantis da razão verdade/previsão de origens cuja verdade já era conhecida.
    comparaveis = comparaveis.assign(razao=comparaveis.verdade / comparaveis[escolhido])
    def faixa(ate, h):
        conhecidos = comparaveis[(comparaveis.horizonte == h) & (comparaveis.semana + nc.MATURACAO * S <= ate)]
        return (np.nan, np.nan) if len(conhecidos) < 20 else tuple(conhecidos.razao.quantile(list(nc.QUANTIS)))
    dentro = []
    for _, r in comparaveis[comparaveis.periodo == 'teste'].iterrows():
        q = faixa(r.origem, r.horizonte)
        if not np.isnan(q[0]):
            dentro.append({'horizonte': r.horizonte, 'dentro': q[0] * r[escolhido] <= r.verdade <= q[1] * r[escolhido]})
    cobertura = pd.DataFrame(dentro).groupby('horizonte').dentro.agg(['mean', 'size'])
    teste['cobertura_faixa_pct'] = teste.horizonte.map(cobertura['mean'] * 100)
    teste['avaliacoes_com_faixa'] = teste.horizonte.map(cobertura['size']).fillna(0).astype(int)
    resumo = pd.concat([validacao, teste], ignore_index=True)

    atual = pd.DataFrame(prever(reg, corte, clima, cache))
    atual['modelo'] = escolhido
    atual['exibir'] = exibir
    atual['previsto'] = atual[escolhido]
    q = {h: faixa(corte, h) for h in HORIZONTES}
    atual['inferior'] = [q[h][0] * p for h, p in zip(atual.horizonte, atual.previsto)]
    atual['superior'] = [q[h][1] * p for h, p in zip(atual.horizonte, atual.previsto)]
    atual['semana_fim'] = atual.semana + pd.Timedelta(days=6)
    for c in METODOS + ['previsto', 'inferior', 'superior']:
        atual[c] = atual[c].round(0)

    OUT.mkdir(parents=True, exist_ok=True)
    produtos = {
        'previsao_dengue.csv': atual.assign(origem=atual.origem.dt.date, semana=atual.semana.dt.date, semana_fim=atual.semana_fim.dt.date),
        'previsao_dengue_avaliacao.csv': resumo.round(2),
        'previsao_dengue_retrospectiva.csv': avaliacao.assign(origem=avaliacao.origem.dt.date, semana=avaliacao.semana.dt.date).round(1),
    }
    for nome, tabela in produtos.items():
        tabela.to_csv(OUT / nome, index=False, encoding='utf-8')
    origens_teste = comparaveis[comparaveis.periodo == 'teste'].origem
    manifesto = {
        'gerado_em': datetime.now(timezone.utc).isoformat(), 'metodo': 'pipeline/modelagem/previsao.py',
        'descricao': 'Previsão de 1 a 8 semanas das notificações de dengue de residentes em Goiânia, por semana de início dos sintomas, todas as classificações',
        'origem_atual': corte.date().isoformat(),
        'parametros': PARAMETROS, 'chave_avaliacao': chave,
        'avaliacao': {'validacao': [VALIDACAO[0].date().isoformat(), VALIDACAO[1].date().isoformat()],
                      'teste': [origens_teste.min().date().isoformat(), origens_teste.max().date().isoformat()],
                      'candidatos': CANDIDATOS, 'modelo_escolhido_na_validacao': escolhido, 'exibida': exibir,
                      'regra': 'escolher na validação o candidato de menor erro absoluto médio; exibir somente se, no teste, superar a melhor referência em todos os horizontes'},
        'fontes': [{'arquivo': a.relative_to(ROOT).as_posix(), 'sha256': sha256(a)} for a in [*arquivos, *[c for c in CLIMA if c.exists()]]],
        'produtos': [{'arquivo': (OUT / n).relative_to(ROOT).as_posix(), 'sha256': sha256(OUT / n)} for n in produtos],
        'limitacoes': [
            'Uma temporada epidêmica atípica pode fugir do padrão aprendido nas anteriores.',
            'Usa uma única estação meteorológica para a cidade inteira; não descreve diferenças entre bairros.',
            'Associação estatística com o clima não demonstra causa.',
            'Conta notificações de todas as classificações, não casos confirmados.'],
    }
    (OUT / 'previsao_dengue_manifesto.json').write_text(json.dumps(manifesto, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    for nome, tabela in [('VALIDAÇÃO', validacao), ('TESTE', teste)]:
        print(f'\n{nome}  (erro absoluto médio)')
        print(tabela[['horizonte'] + [f'erro_abs_medio_{m}' for m in METODOS]].round(0).to_string(index=False))
    print(f'\nEscolhido na validação: {escolhido}; exibido: {exibir}')


if __name__ == '__main__':
    main()
