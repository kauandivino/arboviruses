"""Publica o site público (site/dist) no GitHub Pages, no ramo gh-pages do repositório `origin`.

    .venv/Scripts/python.exe -m pipeline.publicar_site

Só a pasta compilada do site vai para o ramo gh-pages; o painel da equipe e a API não são
publicados. O ramo é refeito a cada publicação (um commit), sem tocar no ramo main.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / 'site/dist'


def git(*args, cwd):
    subprocess.run(['git', *args], cwd=cwd, check=True)


def main():
    if not (DIST / 'index.html').exists() or not (DIST / 'dados/site.json').exists():
        raise SystemExit('site/dist não está compilado. Rode: .venv/Scripts/python.exe -m pipeline')
    remoto = subprocess.run(['git', 'remote', 'get-url', 'origin'], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    dados_ate = json.loads((DIST / 'dados/site.json').read_text(encoding='utf-8'))['dados_ate']
    with tempfile.TemporaryDirectory() as pasta:
        pasta = Path(pasta)
        shutil.copytree(DIST, pasta, dirs_exist_ok=True)
        (pasta / '.nojekyll').write_text('', encoding='utf-8')  # serve os arquivos como estão
        git('init', '-q', '-b', 'gh-pages', cwd=pasta)
        git('add', '-A', cwd=pasta)
        git('-c', 'user.name=Publicação automática', '-c', 'user.email=contato.omniamind@gmail.com',
            'commit', '-q', '-m', f'Site publicado em {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC · dados até {dados_ate}', cwd=pasta)
        git('push', '-q', '--force', remoto, 'gh-pages', cwd=pasta)
    print(f'Site publicado no ramo gh-pages de {remoto} (dados até {dados_ate}).')


if __name__ == '__main__':
    sys.exit(main())
