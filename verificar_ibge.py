"""Testes dos filtros, revisões, células protegidas e correspondência espacial."""
from pathlib import Path
import tempfile
import unittest
import zipfile

from baixar_ibge_agregados import read_filtered
from baixar_ibge_malhas import correspondence
from ibge_utils import latest


class IBGETests(unittest.TestCase):
    def test_codes_suppression_and_header_alias(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            path=Path(directory)/'dados.zip'
            with zipfile.ZipFile(path,'w') as z:
                z.writestr('dados.csv','"setor";"V00111";"V00112";"V00113"\n"520870705000001";"0";"X";""\n"520110805000001";"8";"2";"3"\n')
            data,report=read_filtered(path,'5208707')
            self.assertEqual(report['linhas_fonte'],2)
            self.assertEqual(len(data),1)
            self.assertEqual(data.iloc[0]['CD_SETOR'],'520870705000001')
            self.assertEqual(data.iloc[0]['V00111'],'0')
            self.assertEqual(data.iloc[0]['V00112'],'X')
            self.assertEqual(data.iloc[0]['V00113'],'')

    def test_duplicate_sector_rejected(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            path=Path(directory)/'dados.zip'
            with zipfile.ZipFile(path,'w') as z:
                z.writestr('dados.csv','CD_SETOR;V0001\n520870705000001;1\n520870705000001;2\n')
            with self.assertRaises(RuntimeError):
                read_filtered(path,'5208707')

    def test_newest_release_and_ambiguity(self):
        urls=['https://ftp.ibge.gov.br/a/arquivo.zip','https://ftp.ibge.gov.br/a/arquivo_20260520.zip','https://ftp.ibge.gov.br/a/arquivo_20250417.zip']
        self.assertTrue(latest(urls,'arquivo','.zip').endswith('20260520.zip'))
        with self.assertRaises(RuntimeError):
            latest(['https://ftp.ibge.gov.br/a/arquivo_a.zip','https://ftp.ibge.gov.br/a/arquivo_b.zip'],'arquivo','.zip')

    def test_neighborhood_boundary_mismatch_and_missing(self):
        import geopandas as gpd
        from shapely.geometry import box
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            base=Path(directory)
            (base/'goiania').mkdir()
            sectors=gpd.GeoDataFrame({'CD_SETOR':['a','b','c'],'CD_BAIRRO':['1','1','']},
                geometry=[box(-49.30,-16.70,-49.29,-16.69),box(-49.29,-16.70,-49.27,-16.69),box(-49.27,-16.70,-49.26,-16.69)],crs='EPSG:4674')
            bairros=gpd.GeoDataFrame({'CD_BAIRRO':['1']},geometry=[box(-49.31,-16.71,-49.28,-16.68)],crs='EPSG:4674')
            result=correspondence(sectors,bairros,base)
            self.assertEqual(result['status']['compativel_codigo_e_geometria'],1)
            self.assertEqual(result['status']['divergencia_geometrica'],1)
            self.assertEqual(result['status']['sem_codigo_bairro_na_malha'],1)
            self.assertFalse(result['agregacao_por_bairro_executada'])


if __name__=='__main__':
    unittest.main()
