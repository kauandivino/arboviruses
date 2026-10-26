"""Testa o nowcasting: contas exatas em dados sintéticos, ausência de olhar o futuro e coerência dos produtos."""
import json
import unittest

import numpy as np
import pandas as pd

from pipeline.comum.ibge_utils import sha256
from pipeline.modelagem import nowcast as nc

S = nc.SEMANA


def sintetico(semanas=60, por_semana=100, atrasos=(0, 1, 2), proporcoes=(0.5, 0.3, 0.2)):
    """Cada semana tem o mesmo total e a mesma distribuição de atraso, conhecidos de antemão."""
    inicio = pd.Timestamp('2024-01-07')
    linhas = []
    for i in range(semanas):
        t = inicio + i * S
        for atraso, p in zip(atrasos, proporcoes):
            linhas += [{'t': t, 'dig': t + atraso * S, 'atraso': atraso, 'se_fonte': ''}] * int(por_semana * p)
    return pd.DataFrame(linhas)


class NowcastTest(unittest.TestCase):
    def test_inicio_semana_epidemiologica_no_domingo(self):
        datas = pd.Series(pd.to_datetime(['2026-10-04', '2026-10-07', '2026-10-10', '2026-10-11']))
        self.assertEqual(list(nc.inicio_semana(datas).dt.date.astype(str)), ['2026-10-04', '2026-10-04', '2026-10-04', '2026-10-11'])

    def test_recupera_total_quando_atraso_e_estavel(self):
        reg = sintetico()
        corte = reg.t.max()
        e = nc.estimar(reg, corte).set_index('defasagem')
        self.assertEqual(e.loc[0, 'observado'], 50)
        self.assertAlmostEqual(e.loc[0, 'estimado'], 100)
        self.assertAlmostEqual(e.loc[1, 'estimado'], 100)
        self.assertAlmostEqual(e.loc[5, 'estimado'], 100)

    def test_triangulo_nao_inventa_celulas_futuras(self):
        reg = sintetico(semanas=10)
        corte = reg.t.max()
        acumulado = nc.triangulo(reg, corte)
        self.assertTrue(np.isnan(acumulado.loc[corte, 1]), 'célula ainda não observável deve ficar ausente')
        self.assertEqual(acumulado.loc[corte, 0], 50)
        tardias = reg[reg.dig > corte]
        self.assertTrue(tardias.empty or acumulado.loc[corte - S, 1] == 80)

    def test_faixas_usam_so_erros_ja_conhecidos(self):
        erros = pd.DataFrame({'semana': [pd.Timestamp('2025-01-05'), pd.Timestamp('2025-06-01')], 'defasagem': [0, 0],
                              'estimado': [100.0, 100.0], 'verdade': [150.0, 50.0]})
        cedo = nc.faixas(erros, pd.Timestamp('2025-01-05') + nc.MATURACAO * S)
        self.assertEqual(cedo.loc[0, 'n'], 1)
        self.assertAlmostEqual(cedo.loc[0, nc.QUANTIS[0]], 1.5)
        self.assertTrue(np.isnan(nc.faixas(erros, pd.Timestamp('2025-01-01')).loc[0, 'n']))


class ProdutosTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifesto = json.loads((nc.OUT / 'nowcast_dengue_manifesto.json').read_text(encoding='utf-8'))
        cls.serie = pd.read_csv(nc.OUT / 'nowcast_dengue.csv')

    def test_hashes_conferem(self):
        for item in self.manifesto['fontes'] + self.manifesto['produtos']:
            self.assertEqual(sha256(nc.ROOT / item['arquivo']), item['sha256'], item['arquivo'])

    def test_estimativas_coerentes(self):
        recentes = self.serie.dropna(subset=['defasagem'])
        self.assertEqual(len(recentes), nc.DEFASAGENS)
        suspensas = recentes[recentes.suspensa.astype(bool)]
        self.assertTrue(suspensas.estimado.isna().all(), 'semana suspensa não pode exibir estimativa')
        limites = {int(k): v for k, v in self.manifesto['limite_fator_por_defasagem'].items()}
        self.assertTrue(all(r.fator > limites[int(r.defasagem)] for _, r in suspensas.iterrows()))
        e = recentes.dropna(subset=['estimado'])
        self.assertTrue((e.estimado >= e.observado).all(), 'estimativa não pode ficar abaixo do já digitado')
        self.assertTrue((e.inferior >= e.observado).all() and (e.inferior <= e.estimado).all() and (e.superior >= e.estimado).all())
        self.assertTrue(recentes.se.notna().all())

    def test_serie_conserva_os_registros_observados(self):
        reg, _, _ = nc.carregar('dengue')
        corte = pd.Timestamp(self.manifesto['data_corte_semana_digitacao'])
        contagem = reg[reg.dig <= corte].groupby('t').size()
        for _, r in self.serie.iterrows():
            self.assertEqual(r.observado, contagem[pd.Timestamp(r.semana)])


if __name__ == '__main__':
    unittest.main()
