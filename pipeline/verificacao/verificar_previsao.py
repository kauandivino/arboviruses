"""Testa a previsão: sem uso do futuro, clima sem horas inventadas e regra de exibição respeitada."""
import json
import unittest

import numpy as np
import pandas as pd

from pipeline.comum.ibge_utils import sha256
from pipeline.modelagem import nowcast as nc
from pipeline.modelagem import previsao as pv

S = nc.SEMANA


class PrevisaoTest(unittest.TestCase):
    def test_clima_com_cobertura_baixa_fica_ausente(self):
        semanas = pd.date_range('2025-01-05', periods=12, freq='7D')
        clima = pd.DataFrame({'horas': 168, **{f'{v}_soma_valida': 168.0 for v in ['chuva_mm', 'temperatura_c', 'umidade_pct']},
                              **{f'{v}_horas_validas': 168 for v in ['chuva_mm', 'temperatura_c', 'umidade_pct']}}, index=semanas)
        origem = semanas[-1]
        self.assertEqual(pv.atributos_clima(clima, origem)['chuva_mm'], 1.0)
        clima.loc[semanas[:8], 'chuva_mm_horas_validas'] = 0
        self.assertTrue(np.isnan(pv.atributos_clima(clima, origem)['chuva_mm']))

    def test_clima_nao_usa_semanas_posteriores_a_origem_menos_2(self):
        semanas = pd.date_range('2025-01-05', periods=12, freq='7D')
        clima = pd.DataFrame({**{f'{v}_soma_valida': 0.0 for v in ['chuva_mm', 'temperatura_c', 'umidade_pct']},
                              **{f'{v}_horas_validas': 168 for v in ['chuva_mm', 'temperatura_c', 'umidade_pct']}}, index=semanas)
        origem = semanas[-1]
        clima.loc[semanas[-2:], 'chuva_mm_soma_valida'] = 1e9
        self.assertEqual(pv.atributos_clima(clima, origem)['chuva_mm'], 0.0)

    def test_treino_so_com_alvos_conhecidos_na_origem(self):
        indice = pd.date_range('2023-01-01', periods=200, freq='7D')
        serie = pd.Series(np.linspace(100, 300, 200), index=indice)
        feats = {o: pv.atributos(serie, o, None) for o in indice[2 * pv.NIVEL:]}
        origem = indice[150]
        base = pv.ajustar_prever(serie, origem, feats, 2)
        # Alvos depois de origem - 4 semanas não podem entrar no ajuste: alterá-los não muda a previsão.
        alterada = serie.where(serie.index <= origem - 4 * S, 1e6)
        self.assertAlmostEqual(base, pv.ajustar_prever(alterada, origem, feats, 2))

    def test_serie_corrigida_coincide_com_nowcast(self):
        reg, _, _ = nc.carregar('dengue')
        corte = pd.Timestamp(json.loads((nc.OUT / 'nowcast_dengue_manifesto.json').read_text(encoding='utf-8'))['data_corte_semana_digitacao'])
        reg = reg[reg.dig <= corte]
        serie = pv.serie_corrigida(reg, corte)
        estimado = nc.estimar(reg, corte).set_index('semana').estimado
        np.testing.assert_allclose(serie.loc[estimado.index], estimado)


class ProdutosTest(unittest.TestCase):
    def test_hashes_e_regra_de_exibicao(self):
        manifesto = json.loads((pv.OUT / 'previsao_dengue_manifesto.json').read_text(encoding='utf-8'))
        for item in manifesto['fontes'] + manifesto['produtos']:
            self.assertEqual(sha256(pv.ROOT / item['arquivo']), item['sha256'], item['arquivo'])
        resumo = pd.read_csv(pv.OUT / 'previsao_dengue_avaliacao.csv')
        atual = pd.read_csv(pv.OUT / 'previsao_dengue.csv')
        validacao, teste = resumo[resumo.periodo == 'validacao'], resumo[resumo.periodo == 'teste']
        # A escolha usa só a validação; a exibição, só o teste.
        escolhido = min(pv.CANDIDATOS, key=lambda m: validacao[f'erro_abs_medio_{m}'].mean())
        self.assertEqual(manifesto['avaliacao']['modelo_escolhido_na_validacao'], escolhido)
        self.assertTrue((atual.modelo == escolhido).all())
        melhor_ref = teste[[f'erro_abs_medio_{m}' for m in pv.REFERENCIAS]].min(axis=1)
        esperado = bool((teste[f'erro_abs_medio_{escolhido}'] < melhor_ref).all())
        self.assertEqual(manifesto['avaliacao']['exibida'], esperado)
        self.assertTrue((atual.exibir == esperado).all())
        self.assertEqual(sorted(atual.horizonte), list(pv.HORIZONTES))


if __name__ == '__main__':
    unittest.main()
