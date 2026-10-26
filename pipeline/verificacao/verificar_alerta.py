"""Testa o diagrama de controle: semanas epidemiológicas, quartis sem olhar o ano avaliado e zonas."""
import json
import unittest

import numpy as np
import pandas as pd

from pipeline.comum.ibge_utils import sha256
from pipeline.modelagem import alerta as al
from pipeline.modelagem import nowcast as nc


class AlertaTest(unittest.TestCase):
    def test_semana_epidemiologica_confere_com_a_fonte(self):
        reg, _, _ = nc.carregar('dengue')
        amostra = reg.drop_duplicates('t')
        calculado = [f'{a}{s:02d}' for a, s in (al.semana_epidemiologica(t) for t in amostra.t)]
        divergentes = (pd.Series(calculado, index=amostra.index) != amostra.se_fonte).sum()
        self.assertEqual(divergentes, 0)

    def test_canal_usa_so_os_cinco_anos_anteriores(self):
        semanas = pd.date_range(nc.inicio_semana(pd.Series([pd.Timestamp('2015-01-04')]))[0], '2021-12-26', freq='7D')
        serie = pd.Series(10.0, index=semanas)
        serie[serie.index.year == 2020] = 1000.0  # ano avaliado: não pode influenciar o próprio canal
        limites = al.canal(serie[serie.index < pd.Timestamp('2020-01-01')], 2020)
        self.assertTrue((limites.q3 == 10).all())
        self.assertIsNone(al.canal(serie, 2017), 'menos de cinco anos de referência')

    def test_zonas(self):
        limites = pd.Series({'q1': 10, 'mediana': 20, 'q3': 30})
        self.assertEqual([al.zona(v, limites) for v in (5, 15, 25, 31)], ['sucesso', 'seguranca', 'alerta', 'epidemica'])


class ProdutosTest(unittest.TestCase):
    def test_hashes_e_coerencia(self):
        manifesto = json.loads((al.OUT / 'alerta_dengue_manifesto.json').read_text(encoding='utf-8'))
        for item in manifesto['fontes'] + manifesto['produtos']:
            self.assertEqual(sha256(al.ROOT / item['arquivo']), item['sha256'], item['arquivo'])
        semanas = pd.read_csv(al.OUT / 'alerta_dengue_semanas.csv')
        self.assertTrue((semanas.q1 <= semanas.mediana).all() and (semanas.mediana <= semanas.q3).all())
        self.assertTrue((semanas.valores_referencia >= 10).all())
        # Caso real que motivou a proteção: em 08/02/2026 o fator de correção passou do testado.
        limite = json.loads((al.OUT / 'nowcast_dengue_manifesto.json').read_text(encoding='utf-8'))['limite_fator_por_defasagem']['0']
        reg, _, _ = nc.carregar('dengue')
        semana = pd.Timestamp('2026-02-08')
        self.assertGreater(al.fator_atual(reg[(reg.t >= semana - 80 * nc.SEMANA) & (reg.dig <= semana)], semana), limite)
        self.assertEqual(semanas.set_index('semana').loc['2026-02-08', 'zona_tempo_real'], 'indeterminada')
        # Alerta só depois de duas semanas seguidas na zona epidêmica em tempo real.
        for _, g in semanas.groupby('ano'):
            epid = (g.zona_tempo_real == 'epidemica').to_numpy()
            esperado = np.array([i >= 1 and epid[i] and epid[i - 1] for i in range(len(epid))])
            self.assertTrue((g.alerta.to_numpy() == esperado).all())


if __name__ == '__main__':
    unittest.main()
