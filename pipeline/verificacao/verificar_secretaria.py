"""Testa as regras do validador dos dados da Secretaria com tabelas mínimas montadas no teste."""
import unittest

import pandas as pd

from pipeline.coleta import receber_secretaria as rs


def contagem(**extra):
    linha = {'codigo_territorio': '01', 'nome_territorio': 'Território A', 'distrito_sanitario': 'Leste', 'ano_epidemiologico': '2026',
             'semana_epidemiologica': '14', 'agravo': 'dengue', 'indicador': 'notificacoes', 'referencia_data': 'inicio_sintomas',
             'referencia_local': 'residencia', 'valor': '7', 'situacao_valor': 'observado', 'data_extracao': '2026-11-10'}
    linha.update(extra)
    return linha


class SecretariaTest(unittest.TestCase):
    def erros(self, *linhas):
        return rs.validar_contagens(pd.DataFrame(list(linhas), columns=rs.COLUNAS_CONTAGENS), ['01'], ano_max=2026)

    def test_linha_valida(self):
        self.assertEqual(self.erros(contagem()), [])

    def test_zero_e_ausencia_sao_diferentes(self):
        self.assertEqual(self.erros(contagem(valor='0', situacao_valor='zero_confirmado')), [])
        self.assertTrue(self.erros(contagem(valor='3', situacao_valor='zero_confirmado')))
        self.assertEqual(self.erros(contagem(valor=None, situacao_valor='suprimido')), [])
        self.assertTrue(self.erros(contagem(valor='0', situacao_valor='suprimido')), 'suprimido não pode virar zero')
        self.assertTrue(self.erros(contagem(valor=None, situacao_valor='observado')))

    def test_dominios_semana_e_repeticao(self):
        self.assertTrue(self.erros(contagem(agravo='influenza')))
        self.assertTrue(self.erros(contagem(semana_epidemiologica='54')))
        self.assertTrue(self.erros(contagem(), contagem()))
        self.assertTrue(self.erros(contagem(codigo_territorio='99')))

    def test_colunas_exatas(self):
        self.assertTrue(rs.validar_contagens(pd.DataFrame([contagem()]).drop(columns='valor'), ['01']))
        self.assertTrue(rs.validar_territorios(pd.DataFrame({'codigo': ['01']})))


if __name__ == '__main__':
    unittest.main()
