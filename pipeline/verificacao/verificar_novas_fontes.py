"""Testa LIRAa, saneamento do Censo, InfoDengue e chikungunya/zika: coerência, sem valores inventados."""
import json
from pathlib import Path
import unittest

import pandas as pd

from pipeline.comum.ibge_utils import sha256
from pipeline.processamento import extrair_liraa as el
from pipeline.processamento import saneamento_bairros as sb

ROOT = Path(__file__).resolve().parents[2]


class LiraaTest(unittest.TestCase):
    ciclos = pd.read_csv(ROOT / 'dados/liraa/ciclos.csv')

    def test_estratos_fecham_e_situacao_coerente_com_iip(self):
        self.assertTrue((self.ciclos.estratos_total == self.ciclos[['estratos_baixo', 'estratos_medio', 'estratos_alto']].sum(axis=1)).all())
        esperado = pd.cut(self.ciclos.iip_aegypti, [-1, 0.99, 3.9, 100], labels=['baixo', 'medio', 'alto']).astype(str)
        self.assertTrue((esperado == self.ciclos.situacao).all(), self.ciclos[esperado != self.ciclos.situacao][['fim', 'iip_aegypti', 'situacao']])

    def test_revisao_visual_aplicada(self):
        revisao = json.loads((ROOT / 'dados/liraa/revisao_visual.json').read_text(encoding='utf-8'))['ciclos']
        for fim, r in revisao.items():
            linha = self.ciclos[self.ciclos.fim == fim].iloc[0]
            self.assertTrue(isinstance(linha.nota_fonte, str))
            for campo in r['sem_valor']:
                self.assertTrue(pd.isna(linha[campo]), f'{fim}: {campo} deveria ficar sem valor')

    def test_leitura_do_quadro(self):
        quadro = ('*IIP (Índice de Infestação Predial) e IB (Índice de Breteau) para Aedes aegypti 0.8/0,9 IIP e IB para Aedes albopictus '
                  '0/0 Nº de estratos com baixo risco para Aedes aegypti (IIP abaixo de 1%) 49 (66,22%) Nº de estratos com médio risco '
                  '(IIP entre 1 a 3,9%) 25 (33,78%) Nº de estratos de com alto risco (IIP acima de 3,9 %) 0 (0%) SITUAÇÃO GERAL DO MUNICÍPIO BAIXO RISCO')
        r = el.ler_quadro(quadro)
        self.assertEqual((r['iip_aegypti'], r['ib_aegypti'], r['estratos_baixo'], r['estratos_medio'], r['estratos_alto'], r['situacao']),
                         (0.8, 0.9, 49, 25, 0, 'baixo'))


class SaneamentoTest(unittest.TestCase):
    def test_percentuais_e_cobertura(self):
        s = pd.read_csv(ROOT / 'dados/saneamento/bairros_saneamento.csv')
        for nome in sb.INDICADORES:
            valores = s[f'{nome}_pct'].dropna()
            self.assertTrue(valores.between(0, 100).all())
            publicados = s[s[f'{nome}_pct'].notna()]
            self.assertTrue((publicados[f'{nome}_cobertura_pct'] >= sb.COBERTURA_MINIMA * 100).all(), 'publicado sem cobertura mínima')
        self.assertTrue(s.OID_SIGGO.is_unique)

    def test_hashes(self):
        m = json.loads((ROOT / 'dados/saneamento/manifesto.json').read_text(encoding='utf-8'))
        for f in m['fontes'] + [m['produto']]:
            self.assertEqual(sha256(ROOT / f['arquivo']), f['sha256'])


class InfoDengueTest(unittest.TestCase):
    def test_coleta_e_consistencia(self):
        m = json.loads((ROOT / 'dados/infodengue/manifesto.json').read_text(encoding='utf-8'))
        for c in m['coletas']:
            self.assertEqual(sha256(ROOT / c['original']), c['sha256_original'])
            self.assertEqual(sha256(ROOT / c['produto']), c['sha256_produto'])
        comp = json.loads((ROOT / 'dados/infodengue/comparacao.json').read_text(encoding='utf-8'))
        self.assertGreater(comp['consistencia']['correlacao_log_semanal'], 0.9, 'as séries deveriam retratar a mesma epidemia')


class OutrasArbovirosesTest(unittest.TestCase):
    def test_chikungunya_e_zika_extraidas(self):
        for agravo, inicio in [('chikungunya', 2014), ('zika', 2015)]:
            arquivos = sorted((ROOT / 'dados/regional').glob(f'{agravo}_go_*.csv'))
            self.assertEqual(int(arquivos[0].stem[-4:]), inicio)
            d = pd.concat([pd.read_csv(a) for a in arquivos])
            self.assertTrue((d.notificacoes > 0).all())
            self.assertEqual(set(d.grupo), {'goiania', 'vizinhos', 'resto_go'})


if __name__ == '__main__':
    unittest.main()
