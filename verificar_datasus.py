"""Verifica filtros territoriais, seleção de escorpiões e integridade DBF."""
import csv
from pathlib import Path
import struct
import tempfile
import unittest

from baixar_datasus import dbf_schema, export_dbf, municipality


def make_dbf(path):
    fields = [('ID_MN_RESI', 'C', 6), ('ID_MUNICIP', 'C', 6), ('ANT_MUNIC_', 'C', 6),
              ('TP_ACIDENT', 'C', 1), ('DT_NOTIFIC', 'D', 8), ('ANT_DT_ACI', 'D', 8),
              ('CLASSI_FIN', 'C', 1), ('EVOLUCAO', 'C', 1)]
    rows = [
        ['520870', '530010', '530010', '3', '20220110', '20220109', '1', '1'],
        ['530010', '520870', '520870', '3', '20220210', '', '2', '1'],
        ['520870', '520870', '520870', '2', '20220310', '20220310', '1', '1'],
        ['530010', '530010', '530010', '3', '20220410', '20220410', '1', '1'],
    ]
    h, w = 32+32*len(fields)+1, 1+sum(f[2] for f in fields)
    header = bytearray(32)
    header[0] = 3
    struct.pack_into('<IHH', header, 4, len(rows), h, w)
    with path.open('wb') as f:
        f.write(header)
        for name, kind, length in fields:
            desc=bytearray(32)
            desc[:len(name)] = name.encode()
            desc[11], desc[16] = ord(kind), length
            f.write(desc)
        f.write(b'\r')
        for row in rows:
            f.write(b' ' + b''.join(v.encode().ljust(field[2],b' ') for v,field in zip(row,fields)))
        f.write(b'\x1a')


class DataTests(unittest.TestCase):
    def test_residence_notification_occurrence_and_animals(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            p=Path(folder)
            make_dbf(p/'fixture.dbf')
            report, summary=export_dbf(p/'fixture.dbf',p/'animais_2022.csv',
                                      dict(nome='ANIMBR22.dbc',ano=2022,situacao='FINAIS',agravo='animais',sha256='fixture'),'520870')
            self.assertEqual(report['registros_recorte'],3)
            self.assertEqual(report['escorpioes_recorte'],2)
            self.assertEqual(report['registros_por_referencia'],{'residencia':2,'notificacao':2,'ocorrencia':2})
            with (p/'escorpioes_2022.csv').open(encoding='utf-8-sig',newline='') as f:
                rows=list(csv.DictReader(f))
            self.assertEqual(len(rows),2)
            self.assertEqual(rows[0]['GOIANIA_NOTIFICACAO'],'0')
            self.assertEqual(rows[1]['GOIANIA_RESIDENCIA'],'0')
            self.assertEqual(rows[0]['ANT_DT_ACI'],'2022-01-09')
            self.assertTrue(any(key[4]=='SEM_DATA_VALIDA' for key in summary))
            self.assertFalse(any(key[4]=='2022-03' for key in summary))
            # Leitor independente confirma o esquema e a contagem da fixture.
            from dbfread import DBF
            self.assertEqual(len(list(DBF(str(p/'fixture.dbf'),encoding='cp1252'))),4)

    def test_truncated_input_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            p=Path(folder)/'broken.dbf'
            make_dbf(p)
            p.write_bytes(p.read_bytes()[:-30])
            with self.assertRaises(ValueError):
                dbf_schema(p)

    def test_ibge_and_sinan_codes(self):
        self.assertEqual(municipality('5208707'),'520870')
        self.assertEqual(municipality('520870.0'),'520870')
        self.assertNotEqual(municipality(''),'520870')


if __name__=='__main__':
    unittest.main()
