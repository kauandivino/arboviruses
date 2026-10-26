"""Testes das regras que impedem fundir etapas, nomes próximos e polígonos."""
import unittest
import pandas as pd
from pipeline.processamento.revisar_territorio import key, match_name, mesh_keys, MESH


class CorrespondenciaTerritorial(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mesh=pd.read_csv(MESH,dtype=str,keep_default_na=False).to_dict('records')
        for row in cls.mesh: row['_keys']=mesh_keys(row)

    def test_abreviacoes_controladas_sem_perder_etapa(self):
        self.assertEqual(key('JD Curitiba I'),'JARDIM CURITIBA I')
        self.assertNotEqual(key('JD Curitiba I'),key('JD Curitiba'))
        self.assertEqual(key('Set Pq Tremendão'),key('S Parque Tremendao'))
        self.assertEqual(key("Res Estrela D'alva"),key('RES ESTRELA DALVA'))

    def test_nome_completo_pode_ter_candidato_nominal_mas_sem_homologacao(self):
        row,choices=match_name('SET CAMPINAS',self.mesh)
        self.assertEqual(row['OID_SIGGO_candidato'],'1040')
        self.assertFalse(row['limites_homologados_pela_saude'])
        self.assertFalse(row['pode_agregar_populacao_ou_calcular_taxa'])

    def test_etapa_nao_e_eliminada_para_associar(self):
        row,choices=match_name('JD CURITIBA I',self.mesh)
        self.assertEqual(row['OID_SIGGO_candidato'],'')
        self.assertEqual(row['metodo_correspondencia'],'etapa_nao_identificada_na_malha')
        self.assertEqual([r['OID_SIGGO'] for r in choices],['297'])

    def test_rotulo_truncado_conserva_todas_as_opcoes(self):
        row,choices=match_name('SET LESTE...',self.mesh)
        self.assertEqual(row['status_correspondencia'],'rotulo_truncado_na_fonte')
        self.assertEqual(row['OID_SIGGO_candidato'],'')
        self.assertEqual({r['OID_SIGGO'] for r in choices},{'1109','1110'})

    def test_tipos_e_complementos_nao_sao_fundidos(self):
        row,choices=match_name('VI SAO JOSE',self.mesh)
        self.assertEqual(row['OID_SIGGO_candidato'],'')
        self.assertEqual({r['OID_SIGGO'] for r in choices},{'502','520'})
        row,choices=match_name('BRO SAO FRANCISCO',self.mesh)
        self.assertEqual(row['OID_SIGGO_candidato'],'1108')
        self.assertNotEqual(row['OID_SIGGO_candidato'],'104')

    def test_proposta_contextual_nao_vira_equivalencia(self):
        row,choices=match_name('PARQUE AMAZONAS',self.mesh)
        self.assertEqual(row['OID_SIGGO_candidato'],'')
        self.assertEqual([r['OID_SIGGO'] for r in choices],['836'])
        self.assertEqual(row['metodo_correspondencia'],'hipotese_contextual_nao_confirmada')


if __name__=='__main__':
    unittest.main()
