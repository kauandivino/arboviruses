"""Testa as regras do registro de ações de campo e a proteção da API local; usa pasta temporária."""
from datetime import date
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from pipeline import acoes_campo
from pipeline.servidor import criar_servidor

REFS = acoes_campo.referencias()
OID, TERRITORIO = next(iter(REFS[0].items()))
CNES = next(iter(REFS[1]))
HOJE = date(2026, 10, 26)


def acao(**extra):
    return {'situacao': 'realizada', 'data': '2026-10-20', 'tipo': 'encontro_educativo', 'OID_SIGGO': OID,
            'local': 'Salão comunitário', 'CO_CNES': CNES, 'participantes': 23, 'responsavel': 'Equipe do projeto', **extra}


class RegrasTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.pasta = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def erros(self, dados):
        with self.assertRaises(acoes_campo.ErroValidacao) as ctx:
            acoes_campo.validar(dados, REFS, HOJE)
        return ctx.exception.erros

    def test_rejeita_referencias_desconhecidas_e_campos_obrigatorios(self):
        e = self.erros(acao(OID_SIGGO=-1, CO_CNES='0000000', local='', responsavel=' ', tipo='x', data='20/10/2026'))
        self.assertEqual(set(e), {'OID_SIGGO', 'CO_CNES', 'local', 'responsavel', 'tipo', 'data'})

    def test_contagens_so_em_acoes_realizadas_e_sem_futuro(self):
        self.assertIn('data', self.erros(acao(data='2026-12-01')))
        self.assertIn('participantes', self.erros(acao(participantes=None)))
        self.assertIn('participantes', self.erros(acao(situacao='planejada', data='2026-12-01')))
        self.assertIn('participantes', self.erros(acao(participantes=-3)))
        planejada = acoes_campo.validar(acao(situacao='planejada', data='2026-12-01', participantes=None), REFS, HOJE)
        self.assertIsNone(planejada['participantes'])

    def test_nomes_vem_das_fontes_e_ausencia_nao_vira_zero(self):
        r = acoes_campo.validar(acao(materiais_quantidade=''), REFS, HOJE)
        self.assertEqual(r['territorio'], TERRITORIO)
        self.assertEqual(r['parceiro'], REFS[1][CNES])
        self.assertIsNone(r['materiais_quantidade'])

    def test_historico_preserva_versoes_e_exige_motivo(self):
        r = acoes_campo.gravar(acao(), pasta=self.pasta, refs=REFS, hoje=HOJE)
        with self.assertRaises(acoes_campo.ErroValidacao):
            acoes_campo.gravar(acao(participantes=30), r['id'], pasta=self.pasta, refs=REFS, hoje=HOJE)
        acoes_campo.gravar(acao(participantes=30, motivo_alteracao='Contagem conferida na lista'), r['id'], pasta=self.pasta, refs=REFS, hoje=HOJE)
        self.assertEqual([h['participantes'] for h in acoes_campo.historico(self.pasta)], [23, 30])
        [atual] = acoes_campo.atuais(self.pasta)
        self.assertEqual((atual['versao'], atual['participantes']), (2, 30))
        csv = (self.pasta / 'acoes.csv').read_text(encoding='utf-8-sig').splitlines()
        self.assertEqual(len(csv), 2)

    def test_sem_registros_nao_ha_linhas(self):
        self.assertEqual(acoes_campo.atuais(self.pasta), [])


class ServidorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.servidor = criar_servidor(0, Path(cls.tmp.name))
        cls.base = f'http://127.0.0.1:{cls.servidor.server_port}'
        threading.Thread(target=cls.servidor.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.servidor.shutdown()
        cls.servidor.server_close()
        cls.tmp.cleanup()

    def pedir(self, metodo, rota, corpo=None, origem=True, tipo='application/json'):
        dados = None if corpo is None else (json.dumps(corpo) if tipo == 'application/json' else corpo).encode()
        req = urllib.request.Request(self.base + rota, data=dados, method=metodo)
        if tipo:
            req.add_header('Content-Type', tipo)
        if origem:
            req.add_header('Origin', origem if isinstance(origem, str) else self.base)
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_bloqueia_outras_origens_e_formatos(self):
        self.assertEqual(self.pedir('POST', '/api/acoes', acao(), origem='https://exemplo.com')[0], 403)
        self.assertEqual(self.pedir('POST', '/api/acoes', acao(), origem=False)[0], 403)
        self.assertEqual(self.pedir('POST', '/api/acoes', 'situacao=realizada', tipo='text/plain')[0], 415)

    def test_cria_lista_e_edita(self):
        status, corpo = self.pedir('POST', '/api/acoes', acao(data=date.today().isoformat()))
        self.assertEqual(status, 201)
        rid = corpo['registro']['id']
        status, corpo = self.pedir('POST', '/api/acoes', acao(participantes='muitos'))
        self.assertEqual((status, list(corpo['campos'])), (422, ['participantes']))
        status, corpo = self.pedir('PUT', f'/api/acoes/{rid}', acao(situacao='cancelada', participantes=None, motivo_alteracao='Chuva forte'))
        self.assertEqual((status, corpo['registro']['versao']), (200, 2))
        status, corpo = self.pedir('GET', '/api/acoes', tipo=None, origem=False)
        self.assertEqual([r['situacao'] for r in corpo['registros'] if r['id'] == rid], ['cancelada'])


if __name__ == '__main__':
    unittest.main()
