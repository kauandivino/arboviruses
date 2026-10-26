"""Testa as regras que evitam trocar indicadores, períodos e ausências por zeros."""
from pathlib import Path
import unittest
import pypdfium2 as pdfium
from pipeline.processamento.extrair_informes import bulletin_metadata, municipal_annual, municipal_comparison, neighborhood_table, periodo, title_of
from pipeline.comum.informes_pdf import chart_values


class RegrasInformes(unittest.TestCase):
    def test_janela_movel(self):
        row=periodo('Gráfico 4 – Casos por bairro nas últimas 4 semanas (SE 35 a 38), Goiânia, 2026.')
        self.assertEqual((row['ano_referencia'],row['se_inicio'],row['se_fim'],row['natureza_temporal']),
                         (2026,35,38,'janela_movel'))
        self.assertEqual(row['alerta_periodo'],'')

    def test_inconsistencia_publicada_preservada(self):
        row=periodo('Últimas 4 semanas (SE 32 a 36), Goiânia, 2026.')
        self.assertEqual((row['se_inicio'],row['se_fim']),(32,36))
        self.assertTrue(row['alerta_periodo'])

    def test_ano_ou_edicao_nao_e_ocorrencia_semanal(self):
        self.assertEqual(periodo('Casos por bairros, Goiânia, 2024.')['natureza_temporal'],'nao_explicita')
        self.assertEqual(periodo('Até SE 9, Goiânia, 2024.')['natureza_temporal'],'acumulado_ate_se')
        self.assertEqual(bulletin_metadata('DENGUE - SITUAÇÃO EPIDEMIOLÓGICA - SE 52/2023')['ano_boletim'],2023)

    def test_titulo_intervalo_historico_nao_truncado(self):
        self.assertEqual(title_of('Quadro 1: Demonstrativo. Goiânia, 2015 a 2025*.\nAno Casos'),
                         'Quadro 1: Demonstrativo. Goiânia, 2015 a 2025*.')

    def test_ordem_variavel_das_colunas(self):
        table='Bairros de residência Casos Notificados Casos confirmados Casos Prováveis\nBAIRRO A 10 6 9\nFonte: SMS'
        rows=neighborhood_table(table)
        self.assertEqual({r['indicador']:r['valor'] for r in rows},
                         {'casos_notificados':10,'casos_confirmados':6,'casos_provaveis':9})

    def test_ausencia_nao_e_zero_e_milhar_nao_e_decimal(self):
        rows=neighborhood_table('Bairros de Residência Casos Notificados Casos Prováveis Casos Confirmados\nBAIRRO A 1.234 - 0\nFonte: SMS')
        self.assertEqual([r['valor'] for r in rows],[1234,None,0])

    def test_historico_so_tres_contagens(self):
        text='Quadro 1: Demonstrativo da situação epidemiológica de dengue. Goiânia, 2015 a 2022*.\nAno Casos Notificados Casos confirmados Casos Prováveis\n2022* 50469 26927 48388 3150,1 109 2,3 773,3'
        self.assertEqual([r['valor'] for r in municipal_annual(text)],[50469,26927,48388])
        self.assertEqual(municipal_annual('Quadro 1: Níveis de resposta e critérios de dengue'),[])

    def test_grafico_real_conferido_visualmente(self):
        path=next(Path('dados/informes/2026').glob('*38-2026*'))
        with pdfium.PdfDocument(path) as pdf:
            page=pdf[2]
            try:
                rows=chart_values(page)
            finally:
                page.close()
        self.assertEqual([(r['bairro'],r['valor']) for r in rows],
                         [('PRQ ATHENEU',31),('SET URIAS MAGALHAES',25),('SET PEDRO LUDOVICO',24),
                          ('JD NOVO MUNDO',24),('SET CAMPINAS',20),('BRO JARDIM AMERICA',19),
                          ('JD CURITIBA I',19),('JD BALNEARIO MEIA PONTE',18),('SET CENTRAL',17),('PRQ SANTA CRUZ',16)])

    def test_comparacao_acumulada_municipal(self):
        title='Quadro 1: Distribuição dos casos notificados e confirmados de dengue e chikungunya, por ano até SE 38, Goiânia, 2025* e 2026*.'
        rows=municipal_comparison(title,'Dengue 32159 27615 38985 33364 20,8\nChikungunya 264 166 903 763 359,6')
        self.assertEqual(len(rows),8)
        self.assertEqual([(r['ano_referencia'],r['agravo'],r['indicador'],r['valor']) for r in rows[:4]],
                         [(2025,'dengue','casos_notificados',32159),(2025,'dengue','casos_confirmados',27615),
                          (2026,'dengue','casos_notificados',38985),(2026,'dengue','casos_confirmados',33364)])
        self.assertEqual(periodo(title)['se_fim'],38)


if __name__=='__main__':
    unittest.main()
