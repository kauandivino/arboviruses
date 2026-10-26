"""Verificações das fronteiras temporais e da integração gravada."""
import unittest

from pipeline.comum import epidemiologia as epi
import pandas as pd
from pipeline.processamento.integrar_bases import construir_serie, sobreposicao_entre_arquivos, OUT


class IntegracaoTest(unittest.TestCase):
    def test_janela_do_arquivo_segue_ano_civil_e_epidemiologico(self):
        df = pd.DataFrame([
            ['520870', '2026-01-02', '2026-01-02'],   # dentro do ano epidemiológico 2025
            ['520870', '2025-06-10', '2025-06-08'],
            ['520870', '2026-02-01', '2026-01-30'],   # fora da janela do arquivo 2025
            ['520140', '2025-06-10', '2025-06-08'],   # outro município de residência
            ['520870', '', '2025-06-08'],             # sem data de notificação (referência da dengue)
        ], columns=['ID_MN_RESI', 'DT_NOTIFIC', 'DT_SIN_PRI'])
        serie, excluidos = construir_serie(df, 2025, 'dengue')
        self.assertEqual(serie.to_dict('records'), [{'mes': '2025-06', 'n_registros': 1}, {'mes': '2026-01', 'n_registros': 1}])
        self.assertEqual(dict(zip(excluidos.motivo, excluidos.n_registros)),
                         {'notificacao_fora_da_janela_do_arquivo': 1, 'data_de_referencia_ausente': 1})

    def test_escorpioes_contam_pelo_mes_do_acidente(self):
        df = pd.DataFrame([['520870', '2026-01-05', '2025-12-30'], ['520870', '2026-01-05', '2021-05-01']],
                          columns=['ANT_MUNIC_', 'DT_NOTIFIC', 'ANT_DT_ACI'])
        serie, excluidos = construir_serie(df, 2026, 'escorpioes')
        self.assertEqual(serie.to_dict('records'), [{'mes': '2025-12', 'n_registros': 1}])
        self.assertEqual(list(excluidos.motivo), ['evento_anterior_a_2022'])

    def test_detecta_notificacao_em_dois_arquivos(self):
        a = pd.DataFrame({'x': ['1', '2']}); b = pd.DataFrame({'x': ['2', '3']})
        self.assertEqual(sobreposicao_entre_arquivos({2025: a, 2026: b}), 1)
        self.assertEqual(sobreposicao_entre_arquivos({2025: a, 2026: pd.DataFrame({'x': ['3']})}), 0)

    def test_anos_dinamicos_so_o_corrente_pode_faltar(self):
        corrente = epi.ano_corrente()
        existentes = {2022, 2023, corrente - 1} | set(range(2024, corrente))
        caminho = lambda a: type('Caminho', (), {'exists': lambda self: a in existentes})()
        self.assertEqual(epi.anos_com_arquivo(2022, caminho), sorted(existentes))
        existentes.discard(2023)
        with self.assertRaises(FileNotFoundError):
            epi.anos_com_arquivo(2022, caminho)

    def test_sem_observacoes_nao_inventa_zero(self):
        df = pd.DataFrame([['520870', '', '2025-06-08']], columns=['ID_MN_RESI', 'DT_NOTIFIC', 'DT_SIN_PRI'])
        serie, _ = construir_serie(df, 2025, 'dengue')
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
