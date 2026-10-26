"""Verifica que as camadas do mapa conservam os registros, as posições e as ausências das fontes."""
import json
from pathlib import Path
import unittest

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from pipeline.comum.ibge_utils import sha256
from pipeline.processamento.preparar_mapa import FONTES, OUT, ROOT, caminho_svg

CAMADAS = json.loads((OUT / 'camadas.json').read_text(encoding='utf-8'))
MANIFESTO = json.loads((OUT / 'manifesto.json').read_text(encoding='utf-8'))


def camada(nome):
    return [r for r in CAMADAS if r['camada'] == nome]


class MapaTest(unittest.TestCase):
    def test_fontes_e_produto_conferem_com_manifesto(self):
        for fonte in MANIFESTO['fontes'] + [MANIFESTO['produto']]:
            self.assertEqual(sha256(ROOT / fonte['arquivo']), fonte['sha256'], fonte['arquivo'])

    def test_conserva_todas_as_feicoes(self):
        self.assertEqual(len(camada('limite')), 1)
        self.assertEqual(len(camada('bairro')), len(gpd.read_file(FONTES['bairros'])))
        self.assertEqual(len(camada('unidade')), len(pd.read_csv(FONTES['unidades'])))
        self.assertTrue(camada('limite')[0]['d'])
        sem_contorno = [r for r in camada('bairro') if not r['d']]
        self.assertTrue(all(r['area_fonte_m2'] < 1 for r in sem_contorno), 'só feições degeneradas na fonte podem ficar sem contorno')
        self.assertTrue(all(r['situacao'] == 'contexto' for r in sem_contorno))

    def test_selecao_e_candidatos_sem_valores_inventados(self):
        bairros = {r['OID_SIGGO']: r for r in camada('bairro')}
        selecionados = pd.read_csv(FONTES['selecionados'])
        candidatos = pd.read_csv(FONTES['candidatos'])
        for _, s in selecionados.iterrows():
            b = bairros[int(s.OID_SIGGO)]
            self.assertEqual(b['situacao'], 'selecionado')
            self.assertEqual(b['ordem_articulacao'], int(s.ordem_articulacao))
            self.assertEqual(b['parceiro_cnes'], str(s.CO_CNES))
        for _, c in candidatos.iterrows():
            self.assertEqual(bairros[int(c.OID_SIGGO)]['janelas_com_citacao'], int(c.janelas_com_citacao))
        contexto = [b for b in bairros.values() if b['situacao'] == 'contexto']
        self.assertEqual(len(contexto), len(bairros) - len(candidatos))
        self.assertTrue(all(b['janelas_com_citacao'] is None for b in contexto), 'ausência não pode virar zero')

    def test_unidades_na_posicao_cadastrada_e_dentro_do_municipio(self):
        x0, y1 = MANIFESTO['origem_svg_m']['x_min'], MANIFESTO['origem_svg_m']['y_max']
        limite = gpd.read_file(FONTES['setores']).to_crs(MANIFESTO['crs']).union_all()
        for u in camada('unidade'):
            esperado = gpd.GeoSeries([Point(u['longitude'], u['latitude'])], crs='EPSG:4326').to_crs(MANIFESTO['crs'])[0]
            self.assertLessEqual(abs(esperado.x - x0 - u['x']), 1, u['CO_CNES'])
            self.assertLessEqual(abs(y1 - esperado.y - u['y']), 1, u['CO_CNES'])
            self.assertTrue(limite.buffer(250).contains(esperado), u['CO_CNES'])
        parceiros = {str(c) for c in pd.read_csv(FONTES['selecionados'], dtype={'CO_CNES': str}).CO_CNES}
        self.assertEqual({u['CO_CNES'] for u in camada('unidade') if u['situacao'] == 'parceiro_selecionado'}, parceiros)

    def test_caminho_svg_preserva_vertices(self):
        from shapely.geometry import Polygon
        quadrado = Polygon([(100, 200), (300, 200), (300, 50), (100, 50)])
        self.assertEqual(caminho_svg(quadrado, (100, 200)), 'M0 0l200 0l0 150l-200 0z')


if __name__ == '__main__':
    unittest.main()
