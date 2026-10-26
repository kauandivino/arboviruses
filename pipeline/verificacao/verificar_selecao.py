"""Verifica restrições que tornam a seleção territorial interpretável."""
import json
import unittest
import pandas as pd
from pipeline.processamento.selecionar_territorios import OUT, contagens


class SelecaoTest(unittest.TestCase):
    def test_rejeita_janelas_sobrepostas(self):
        b=pd.DataFrame({'se_boletim':[20,22], 'elemento_id':['a','b'],
                        'se_inicio':[17,19], 'se_fim':[20,22]})
        with self.assertRaises(AssertionError):
            contagens(b,[20,22])

    def test_oito_unicos_com_evidencias_e_parceiros(self):
        s=pd.read_csv(OUT/'oito_territorios.csv',dtype={'OID_SIGGO':str,'CO_CNES':str})
        e=pd.read_csv(OUT/'evidencias_janelas.csv',dtype={'OID_SIGGO_candidato':str})
        a=pd.read_csv(OUT/'auditoria_geolocalizacao.csv',dtype={'CO_CNES':str})
        self.assertEqual(len(s),8)
        self.assertTrue(s.OID_SIGGO.is_unique)
        self.assertTrue(s.distancia_minima_poligono_m.le(3000).all())
        for _,row in s.iterrows():
            rows=e.loc[(e.OID_SIGGO_candidato==row.OID_SIGGO)&
                       (e.status_correspondencia=='nominal_unico_nao_homologado')]
            self.assertEqual(rows.se_boletim.nunique(),row.janelas_com_citacao)
            audit=a.loc[a.CO_CNES==row.CO_CNES]
            self.assertEqual(len(audit),1)
            self.assertEqual(audit.status_checagem.iloc[0],'compatibilidade_exploratoria')
            self.assertLessEqual(audit.distancia_ao_bairro_cadastrado_m.iloc[0],250)
        self.assertTrue(s.data_acao.isna().all())
        self.assertTrue(s.custo_estimado.isna().all())
        self.assertEqual(set(s.status_parceria),{'nao_contatada'})
        self.assertEqual(set(s.area_abrangencia),{'nao_verificada'})

    def test_estabilidade_e_exclusoes(self):
        m=json.loads((OUT/'manifesto.json').read_text(encoding='utf-8'))
        self.assertTrue(m['mesmos_oito_na_alternativa'])
        e=pd.read_csv(OUT/'evidencias_janelas.csv')
        self.assertEqual(set(e.se_boletim),{16,20,24,28,32,36})
        self.assertEqual(set(e.status_periodo),{'janela_declarada_na_fonte'})
        self.assertEqual(len(e),60)
        self.assertFalse(e.pode_somar_entre_boletins.any())


if __name__=='__main__':
    unittest.main()
