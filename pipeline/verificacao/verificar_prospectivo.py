"""Testa o registro prospectivo: previsão válida e registro que só cresce (linhas já salvas nunca mudam)."""
import io
import subprocess
import unittest

import pandas as pd

from pipeline.modelagem import prospectivo as pr
from pipeline.modelagem import risco as rc


class ProspectivoTest(unittest.TestCase):
    def test_previsao_em_data_passada_sem_gravar(self):
        regional = rc.carregar_regional()
        grupo = rc.Grupo(regional[regional.grupo == 'goiania'])
        corte = pd.Timestamp('2025-06-01')
        p, ref, _, n, eventos = pr.prever(grupo, pr.tabela_goiania(grupo, corte), corte)
        self.assertTrue(0 <= p <= 1 and 0 <= ref <= 1)
        self.assertGreater(n, 50)
        self.assertGreater(eventos, 0)

    def test_registro_so_cresce(self):
        caminho = pr.REGISTRO.relative_to(pr.rc.ROOT).as_posix()
        anterior = subprocess.run(['git', 'show', f'HEAD:{caminho}'], cwd=pr.rc.ROOT, capture_output=True, text=True)
        if anterior.returncode != 0 or not pr.REGISTRO.exists():
            self.skipTest('registro ainda sem previsões versionadas')
        antes = pd.read_csv(io.StringIO(anterior.stdout), dtype=str)
        agora = pd.read_csv(pr.REGISTRO, dtype=str)
        pd.testing.assert_frame_equal(agora.iloc[:len(antes)].reset_index(drop=True), antes)
        self.assertTrue(agora.corte.is_unique and agora.corte.is_monotonic_increasing)
        self.assertTrue((pd.to_datetime(agora.corte) >= pr.INICIO).all())


if __name__ == '__main__':
    unittest.main()
