"""Testa as correlações e a previsão de acidentes com escorpião: métodos, regra de exibição e ausência de dados futuros."""
import json
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

from pipeline.comum.ibge_utils import sha256
from pipeline.modelagem import correlacoes as co
from pipeline.modelagem import escorpioes as es

ROOT = Path(__file__).resolve().parents[2]
MOD = ROOT / 'dados/modelagem'


class CorrelacoesTest(unittest.TestCase):
    r = json.loads((MOD / 'correlacoes.json').read_text(encoding='utf-8'))

    def test_anomalia_remove_padrao_do_ano(self):
        datas = pd.date_range('2015-01-04', '2024-12-29', freq='7D')
        sazonal = pd.Series(100 + 50 * np.sin(2 * np.pi * datas.dayofyear / 365), index=datas)
        # Resta só a variação dentro de cada semana do ano (a série tem amplitude 50).
        self.assertLess(co.anomalia(sazonal).std(), 0.05 * sazonal.std())

    def test_defasagem_recuperada_em_serie_sintetica(self):
        datas = pd.date_range('2015-01-04', '2024-12-29', freq='7D')
        x = pd.Series(np.random.default_rng(0).normal(size=len(datas)), index=datas)
        y = x.shift(5, freq='7D').reindex(datas)
        _, anom = co.correlacao_defasada(y, x, co.LAGS)
        self.assertEqual(int(np.argmax(anom)), 5)
        self.assertGreater(anom[5], 0.95)

    def test_series_sem_semanas_recentes(self):
        for agravo, grupo in [('dengue', 'goiania'), ('dengue', 'vizinhos'), ('chikungunya', 'goiania')]:
            arquivos = sorted(co.REGIONAL.glob(f'{agravo}_go_*.csv'))
            digitacao = max(pd.read_csv(f, parse_dates=['semana_digitacao']).semana_digitacao.max() for f in arquivos)
            self.assertLessEqual(co.serie(agravo, grupo).index.max(), digitacao - 12 * co.S)

    def test_regra_de_cobertura_do_clima(self):
        semanal, c = co.clima_semanal(), co.clima()
        incompletas = semanal.chuva_mm_horas_validas < 0.9 * 168
        self.assertTrue(c.chuva_mm[incompletas].isna().all())
        self.assertTrue(c.temperatura_c[semanal.temperatura_c_horas_validas < 0.6 * 168].isna().all())

    def test_resultado_coerente(self):
        for v, d in self.r['clima_dengue'].items():
            self.assertEqual(len(d['r_bruta']), len(d['lags']))
            self.assertTrue(all(-1 <= x <= 1 for x in d['r_bruta'] + d['r_sem_sazonalidade']))
            self.assertEqual(d['r_melhor'], d['r_sem_sazonalidade'][d['lags'].index(d['melhor_lag'])])
            self.assertEqual(d['forca'], co.forca(d['r_melhor']))
        for chave in ['vizinhos', 'chikungunya']:
            p = self.r[chave]
            self.assertEqual(p['antes'] + p['juntos'] + p['depois'], p['temporadas'])
            self.assertEqual(len(p['por_temporada']), p['temporadas'])
        self.assertEqual([p['mes'] for p in self.r['escorpioes']['perfil_mensal']], list(range(1, 13)))


class EscorpioesTest(unittest.TestCase):
    m = json.loads((MOD / 'escorpioes_manifesto.json').read_text(encoding='utf-8'))
    retro = pd.read_csv(MOD / 'escorpioes_retrospectiva.csv')

    @staticmethod
    def sinteticos():
        rng = np.random.default_rng(1)
        meses = pd.period_range('2015-01', '2022-06', freq='M')
        linhas = []
        for m in meses:
            for _ in range(int(rng.poisson(40 + 10 * np.sin(2 * np.pi * m.month / 12)))):
                linhas.append({'mes': m, 'dig': m + int(rng.choice([0, 1, 2], p=[0.6, 0.3, 0.1]))})
        reg = pd.DataFrame(linhas)
        return reg[reg.dig <= meses[-1] + 1]

    def test_atributos_usam_so_o_digitado_ate_a_origem(self):
        reg = self.sinteticos()
        clima_mes = pd.DataFrame({'temperatura_c': 24.0, 'chuva_mm': 100.0}, index=pd.period_range('2014-01', '2023-12', freq='M'))
        tabela, ultimo = es.montar(reg, clima_mes)
        for origem in [pd.Period('2018-03', 'M'), pd.Period('2020-11', 'M')]:
            linha = tabela[tabela.mes == origem].iloc[0]
            self.assertEqual(linha.obs_m, ((reg.mes == origem) & (reg.dig <= origem)).sum())
        self.assertTrue(tabela[tabela.mes + 1 > ultimo - es.ATRASO].verdade_1.isna().all())

    def test_previsao_nao_muda_com_registros_futuros(self):
        reg = self.sinteticos()
        clima_mes = pd.DataFrame({'temperatura_c': 24.0, 'chuva_mm': 100.0}, index=pd.period_range('2014-01', '2023-12', freq='M'))
        origem = pd.Period('2020-06', 'M')
        tabela, _ = es.montar(reg, clima_mes)
        # Registros digitados depois da origem, de meses que o treino ainda não considera completos.
        extra = pd.DataFrame({'mes': [origem - 1] * 300 + [origem] * 300, 'dig': [origem + 1] * 600})
        tabela2, _ = es.montar(pd.concat([reg, extra], ignore_index=True), clima_mes)
        for h in es.HORIZONTES:
            for tipo in es.CANDIDATOS:
                self.assertAlmostEqual(es.ajustar_prever(tabela, origem, h, tipo), es.ajustar_prever(tabela2, origem, h, tipo), places=6)

    def test_regra_de_exibicao(self):
        teste, escolhido = self.m['avaliacao']['teste'], self.m['modelo_escolhido_na_validacao']
        val = self.m['avaliacao']['validacao']
        self.assertEqual(escolhido, min(es.CANDIDATOS, key=lambda c: np.mean([val[str(h)][c] for h in es.HORIZONTES])))
        passou = all(teste[str(h)][escolhido] < min(teste[str(h)][r] for r in es.REFERENCIAS) for h in es.HORIZONTES)
        self.assertEqual(self.m['exibida'], passou)

    def test_retrospectiva_e_periodos(self):
        origens = pd.PeriodIndex(self.retro.origem, freq='M')
        self.assertTrue((origens >= es.VALIDACAO[0]).all())
        self.assertTrue(((origens <= es.VALIDACAO[1]) == (self.retro.periodo == 'validacao')).all())
        ultimo = pd.Period(self.m['ultimo_mes_completo'], 'M')
        self.assertTrue((origens + self.retro.horizonte.to_numpy() <= ultimo - es.ATRASO).all())
        for p in self.m['previsao']:
            self.assertEqual(pd.Period(p['mes'], 'M'), ultimo + p['horizonte'])

    def test_fontes(self):
        for f in self.m['fontes']:
            self.assertEqual(sha256(ROOT / f['arquivo']), f['sha256'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
