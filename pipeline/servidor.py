"""Servidor local do painel: arquivos de painel/dist e API das ações de campo.

    .venv/Scripts/python.exe -m pipeline.servidor [--porta 4173]

Atende apenas 127.0.0.1. Gravações exigem JSON e origem igual à do próprio painel,
para que outras páginas abertas no navegador não consigam registrar ações.
"""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import urlsplit

from pipeline import acoes_campo

ROOT = Path(__file__).resolve().parents[1]
LIMITE_CORPO = 16 * 1024


class Painel(SimpleHTTPRequestHandler):
    pasta_acoes = acoes_campo.PASTA

    def log_message(self, formato, *args):
        if self.path.startswith('/api/'):
            super().log_message(formato, *args)

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        super().end_headers()

    def _json(self, status, corpo):
        dados = json.dumps(corpo, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def do_GET(self):
        if self.path.split('?')[0] == '/api/acoes':
            return self._json(200, {'registros': acoes_campo.atuais(self.pasta_acoes),
                                    'tipos': acoes_campo.TIPOS, 'situacoes': acoes_campo.SITUACOES})
        if self.path.startswith('/api/'):
            return self._json(404, {'erro': 'rota inexistente'})
        return super().do_GET()

    def _origem_valida(self):
        origem = self.headers.get('Origin')
        host = self.headers.get('Host', '')
        return origem is not None and urlsplit(origem).netloc == host and urlsplit(origem).hostname in ('127.0.0.1', 'localhost')

    def _gravar(self, id_existente=None):
        if not self._origem_valida():
            return self._json(403, {'erro': 'origem não autorizada'})
        if self.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json':
            return self._json(415, {'erro': 'envie application/json'})
        tamanho = int(self.headers.get('Content-Length') or 0)
        if tamanho <= 0 or tamanho > LIMITE_CORPO:
            return self._json(413, {'erro': 'corpo ausente ou grande demais'})
        try:
            dados = json.loads(self.rfile.read(tamanho))
            if not isinstance(dados, dict):
                raise ValueError
        except ValueError:
            return self._json(400, {'erro': 'JSON inválido'})
        try:
            registro = acoes_campo.gravar(dados, id_existente, pasta=self.pasta_acoes)
        except acoes_campo.ErroValidacao as erro:
            return self._json(422, {'erro': 'dados inválidos', 'campos': erro.erros})
        return self._json(200 if id_existente else 201, {'registro': registro})

    def do_POST(self):
        if self.path == '/api/acoes':
            return self._gravar()
        return self._json(404, {'erro': 'rota inexistente'})

    def do_PUT(self):
        partes = self.path.split('/')
        if len(partes) == 4 and partes[:3] == ['', 'api', 'acoes'] and partes[3].isalnum():
            return self._gravar(partes[3])
        return self._json(404, {'erro': 'rota inexistente'})


def criar_servidor(porta=4173, pasta_acoes=None, dist=ROOT / 'painel/dist'):
    manipulador = type('PainelConfigurado', (Painel,), {'pasta_acoes': pasta_acoes or acoes_campo.PASTA})
    return ThreadingHTTPServer(('127.0.0.1', porta), partial(manipulador, directory=str(dist)))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--porta', type=int, default=4173)
    args = parser.parse_args()
    if not (ROOT / 'painel/dist/index.html').exists():
        raise SystemExit('Painel ainda não compilado. Execute: .venv/Scripts/python.exe -m pipeline')
    servidor = criar_servidor(args.porta)
    print(f'Painel em http://127.0.0.1:{args.porta}/ — Ctrl+C encerra o servidor.', flush=True)
    print(f'Ações de campo gravadas em {acoes_campo.PASTA.relative_to(ROOT).as_posix()}/', flush=True)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
