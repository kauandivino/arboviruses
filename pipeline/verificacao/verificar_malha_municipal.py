from pathlib import Path
import tempfile
import unittest

from pipeline.coleta.baixar_malha_municipal import check_batch,crosswalk,polygonal


class MunicipalTests(unittest.TestCase):
    def test_truncated_or_duplicate_page_rejected(self):
        data={'geometryType':'esriGeometryPolygon','features':[{'attributes':{'OBJECTID':1}}]}
        with self.assertRaises(RuntimeError):
            check_batch(data,[1,2],'OBJECTID')
        data['features'].append({'attributes':{'OBJECTID':1}})
        with self.assertRaises(RuntimeError):
            check_batch(data,[1,2],'OBJECTID')
        data['features'][1]['attributes']['OBJECTID']=2
        self.assertEqual(len(check_batch(data,[1,2],'OBJECTID')),2)
        data['exceededTransferLimit']=True
        with self.assertRaises(RuntimeError):
            check_batch(data,[1,2],'OBJECTID')

    def test_overlap_partial_and_uncovered_not_assigned(self):
        import geopandas as gpd
        import pandas as pd
        from shapely.geometry import box
        x,y=665000,8150000
        sectors=gpd.GeoDataFrame({'CD_SETOR':['s1','s2','s3','s4']},
            geometry=[box(x+i*10,y,x+(i+1)*10,y+10) for i in range(4)],crs='EPSG:31982')
        bairros=gpd.GeoDataFrame({'OID_SIGGO':[1,2,3,4],'ID_SIGGO':['A','A','B','D'],'NOME_SIGGO':['A1','A2','B','D']},
            geometry=[box(x,y,x+10,y+10),box(x+5,y,x+10,y+10),box(x+10,y,x+15,y+10),box(x+30,y,x+40,y+10)],crs=sectors.crs)
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            report=crosswalk(sectors,bairros,folder)
            diagnostics=pd.read_csv(Path(folder)/'diagnostico_setores_bairros.csv',keep_default_na=False).set_index('CD_SETOR')
            self.assertEqual(diagnostics.loc['s1','STATUS'],'sobreposicao_entre_poligonos')
            self.assertEqual(diagnostics.loc['s2','STATUS'],'cobertura_parcial')
            self.assertEqual(diagnostics.loc['s3','STATUS'],'sem_intersecao_acima_tolerancia')
            self.assertEqual(diagnostics.loc['s4','STATUS'],'candidato_um_poligono_99pct')
            self.assertEqual(diagnostics.loc['s1','ID_SIGGO_CANDIDATO'],'')
            self.assertEqual(diagnostics.loc['s4','ID_SIGGO_CANDIDATO'],'D')
            self.assertAlmostEqual(report['fracao_area_municipio_coberta'],.625)
            self.assertFalse(report['populacao_rateada'])
            self.assertFalse(report['agregacao_por_bairro_executada'])

    def test_geometry_repair_does_not_change_original(self):
        import shapely
        from shapely.geometry import Polygon,GeometryCollection,LineString
        original=Polygon([(0,0),(2,2),(0,2),(2,0),(0,0)])
        self.assertFalse(original.is_valid)
        repaired=polygonal(shapely.make_valid(original))
        self.assertTrue(repaired.is_valid)
        self.assertFalse(original.is_valid)
        collection=GeometryCollection([repaired,LineString([(3,3),(4,4)])])
        self.assertTrue(polygonal(collection).is_valid)
        self.assertIsNone(polygonal(LineString([(0,0),(1,1)])))


if __name__=='__main__':
    unittest.main()
