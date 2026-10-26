"""Verificações das fronteiras temporais e da integração gravada."""
import unittest
import pandas as pd
from pipeline.processamento.integrar_bases import construir_serie, OUT


class IntegracaoTest(unittest.TestCase):
    def test_nao_mistura_geografia_data_ou_ano(self):
        df = pd.DataFrame([
            ['residencia', 'DT_NOTIFIC', '2026-01', '2'],
            ['residencia', 'DT_NOTIFIC', '2026-01', '3'],
            ['notificacao', 'DT_NOTIFIC', '2026-01', '100'],
            ['residencia', 'DT_SIN_PRI', '2026-01', '200'],
            ['residencia', 'DT_NOTIFIC', '2025-12', '7'],
            ['residencia', 'DT_NOTIFIC', 'SEM_DATA_VALIDA', '11'],
        ], columns=['referencia_geografica', 'campo_data', 'mes', 'n_registros'])
        serie, excluidos = construir_serie(df, 2026, 'residencia', 'DT_NOTIFIC')
        self.assertEqual(serie.to_dict('records'), [{'mes': '2026-01', 'n_registros': 5}])
        self.assertEqual(int(excluidos.n_registros.sum()), 18)

    def test_sem_observacoes_nao_inventa_zero(self):
        df = pd.DataFrame([['residencia', 'DT_NOTIFIC', 'SEM_DATA_VALIDA', '4']],
                          columns=['referencia_geografica', 'campo_data', 'mes', 'n_registros'])
        serie, _ = construir_serie(df, 2026, 'residencia', 'DT_NOTIFIC')
        self.assertTrue(serie.empty)

    def test_artefatos_sem_multiplicacao(self):
        mensal = pd.read_csv(OUT / 'municipal_mensal_clima.csv')
        self.assertFalse(mensal.duplicated(['agravo', 'mes']).any())
        clima = pd.read_csv(OUT / 'clima_mensal.csv')
        self.assertTrue(clima.periodo_utc.is_unique)
        bairros = pd.read_csv(OUT / 'bairros_publicados.csv')
        self.assertTrue(bairros.revisao_id.is_unique)
        self.assertFalse(bairros.pode_somar_entre_boletins.any())
        self.assertFalse(bairros.apto_ranking_completo_ou_taxa.any())
        parceiros = pd.read_csv(OUT / 'parceiros_candidatos.csv')
        self.assertTrue(parceiros.natureza_administracao_publica.all())
        self.assertFalse(parceiros.possui_motivo_desativacao.any())
        self.assertEqual(set(parceiros.checagem_municipal), {'dentro_malha_2022'})


if __name__ == '__main__':
    unittest.main()
