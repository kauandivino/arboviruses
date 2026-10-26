"""Testes das regras de falhas, horários UTC e cobertura dos resumos."""
import unittest
import pandas as pd
from pipeline.processamento.processar_inmet import measurement, summarize
from pipeline.coleta.baixar_inmet import select_member


class RegrasINMET(unittest.TestCase):
    def test_versoes_acumuladas_nao_duplicam_horas(self):
        old = 'INMET_CO_GO_A002_GOIANIA_01-01-2026_A_31-08-2026.CSV'
        new = 'INMET_CO_GO_A002_GOIANIA_01-01-2026_A_30-09-2026.CSV'
        self.assertEqual(select_member([new, old], 2026), new)
        with self.assertRaises(RuntimeError):
            select_member([new, new], 2026)

    def test_sentinelas_e_dominios(self):
        for raw in ('', 'Null', '-9999', '9999'):
            self.assertTrue(pd.isna(measurement(raw, 'chuva_mm')[0]))
        self.assertEqual(measurement('0', 'chuva_mm'), (0.0, 'valido'))
        self.assertEqual(measurement('1,7', 'chuva_mm'), (1.7, 'valido'))
        self.assertEqual(measurement('101', 'umidade_pct')[1], 'fora_dominio')
        self.assertEqual(measurement('-1', 'chuva_mm')[1], 'fora_dominio')
        self.assertEqual(measurement('-1', 'temperatura_c')[0], -1)

    def test_total_incompleto_nao_vira_total_completo(self):
        frame = pd.DataFrame({'linha_presente': True, 'chuva_mm': 1.,
                              'temperatura_c': 20., 'umidade_pct': 50.},
                             index=pd.date_range('2024-02-01', periods=24, freq='h', tz='UTC'))
        complete = summarize(frame, 'dia').iloc[0]
        self.assertEqual(complete.chuva_mm_completo_valor, 24)
        frame.loc[frame.index[0], 'chuva_mm'] = float('nan')
        partial = summarize(frame, 'dia').iloc[0]
        self.assertEqual(partial.chuva_mm_observado, 23)
        self.assertTrue(pd.isna(partial.chuva_mm_completo_valor))
        self.assertEqual(summarize(frame, 'mes').iloc[0].horas_esperadas, 29 * 24)
        self.assertEqual(frame.index[0].tz_convert('America/Sao_Paulo').day, 31)


if __name__ == '__main__':
    unittest.main()
