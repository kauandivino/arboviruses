"""Confere se os dados locais correspondem às versões de referência (dados/referencias.json)."""
import json
from pathlib import Path
import unittest

from pipeline.comum.referencias import CNES_COMPETENCIA, CNES_ESTABELECIMENTOS, ROOT, SIGGO_COLETA


class ReferenciasTest(unittest.TestCase):
    def test_cnes_de_referencia_presente(self):
        self.assertTrue((ROOT / CNES_ESTABELECIMENTOS).exists(),
                        f'CNES {CNES_COMPETENCIA} ausente: rode a coleta do CNES com --competencia {CNES_COMPETENCIA}')

    def test_malha_siggo_e_a_de_referencia(self):
        pasta = Path(json.loads((ROOT / 'dados/malha_municipal/manifesto.json').read_text(encoding='utf-8'))['pasta'].replace('\\', '/'))
        self.assertEqual(pasta.name, SIGGO_COLETA,
                         'A malha SIGGO processada não é a de referência. Restaure o pacote de originais '
                         '(python -m pipeline.comum.pacote_originais restaurar) ou, se a mudança for intencional, '
                         'atualize dados/referencias.json e revise a seleção dos territórios.')


if __name__ == '__main__':
    unittest.main()
