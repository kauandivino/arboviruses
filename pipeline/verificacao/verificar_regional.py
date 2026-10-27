"""Testa a extração regional e o modelo de risco: coerência com o nowcasting e ausência de olhar o futuro."""
import json
import unittest

import numpy as np
import pandas as pd

from pipeline.comum.ibge_utils import sha256
from pipeline.modelagem import nowcast as nc
from pipeline.modelagem import risco as rc

REGIONAL = rc.carregar_regional()


class RegionalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reg, _, _ = nc.carregar('dengue')

    def test_goiania_regional_igual_a_serie_do_nowcasting(self):
        regional = REGIONAL[REGIONAL.grupo == 'goiania'].groupby('semana_inicio').notificacoes.sum()
        serie = self.reg.groupby('t').size()
        pd.testing.assert_series_equal(regional.sort_index(), serie.sort_index(), check_names=False, check_index_type=False, check_dtype=False)

    def test_correcao_rapida_igual_ao_nowcasting(self):
        grupo = rc.Grupo(REGIONAL[REGIONAL.grupo == 'goiania'])
        for corte in [pd.Timestamp('2022-03-06'), pd.Timestamp('2024-02-11'), pd.Timestamp('2025-08-17')]:
            esperado = nc.estimar(self.reg[self.reg.dig <= corte], corte).set_index('semana').estimado
            np.testing.assert_allclose(grupo.serie(corte).loc[esperado.index], esperado, rtol=1e-9)

    def test_vizinhos_definidos_pela_malha(self):
        municipios = json.loads((rc.REGIONAL / 'municipios.json').read_text(encoding='utf-8'))
        self.assertIn('520140', municipios['vizinhos'])  # Aparecida de Goiânia
        self.assertNotIn('520870', municipios['vizinhos'])

    def test_hashes_da_extracao(self):
        manifesto = json.loads((rc.REGIONAL / 'manifesto.json').read_text(encoding='utf-8'))
        for ano in manifesto['anos'].values():
            self.assertEqual(sha256(rc.ROOT / ano['produto']), ano['produto_sha256'])


class RiscoTest(unittest.TestCase):
    def test_evento_do_treino_nao_usa_dados_posteriores(self):
        grupos = {'goiania': rc.Grupo(REGIONAL[REGIONAL.grupo == 'goiania'])}
        corte = pd.Timestamp('2023-06-04')
        tabela = pd.DataFrame({'corte': pd.date_range('2023-01-01', '2023-06-04', freq='7D'), 'q3_alvo': 100.0})
        eventos = rc.evento_conhecido(tabela, grupos, corte)
        serie = grupos['goiania'].serie(corte)
        for o, e in zip(tabela.corte, eventos):
            alvos = [o + h * rc.S for h in range(1, rc.HORIZONTE + 1)]
            if alvos[-1] > corte:
                self.assertTrue(np.isnan(e), 'evento com semanas posteriores ao corte deve ficar ausente')
            else:
                self.assertEqual(e, float(serie.reindex(alvos).mean() > 100))

    def test_brier(self):
        self.assertAlmostEqual(rc.brier(np.array([0.2, 0.9]), np.array([0, 1])), (0.04 + 0.01) / 2)

    def test_produtos_e_regra(self):
        manifesto = json.loads((rc.OUT / 'risco_dengue_manifesto.json').read_text(encoding='utf-8'))
        b = manifesto['brier']
        escolhido = min(rc.CANDIDATOS, key=lambda m: b['validacao'][m])
        self.assertEqual(manifesto['modelo_escolhido_na_validacao'], escolhido)
        self.assertEqual(manifesto['exibida'], all(b['teste'][escolhido] < b['teste'][r] for r in rc.REFERENCIAS))
        p = manifesto['probabilidade_atual']
        self.assertTrue(p is None or 0 <= p <= 1)


if __name__ == '__main__':
    unittest.main()
