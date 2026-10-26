"""Verificações locais: py verificar_download.py."""
import csv
import tempfile
from pathlib import Path

from pipeline.coleta.baixar_informes import canonical, filename, links_from_html, save_manifest

html = r'''<script>const lista=["https:\/\/exemplo.gov.br\/a.pdf"];</script>
<a href="/b.pdf">PDF</a><a href="/b.pdf">Duplicado</a>'''
assert links_from_html(html, "https://exemplo.gov.br/") == {
    "https://exemplo.gov.br/a.pdf", "https://exemplo.gov.br/b.pdf"
}
assert filename("https://x.gov.br/a.pdf") != filename("https://y.gov.br/a.pdf")
assert "/" not in filename("https://x.gov.br/../../a.pdf")
assert canonical("https://x/a–b.pdf") == canonical("https://x/a%E2%80%93b.pdf")
with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
    path = Path(directory) / "manifesto.csv"
    save_manifest(path, {"https://x/a.pdf": {"url": "https://x/a.pdf", "status": "baixado"}})
    with path.open(encoding="utf-8-sig", newline="") as f:
        assert list(csv.DictReader(f))[0]["status"] == "baixado"
print("OK: links HTML/JavaScript, deduplicação, nomes e manifesto CSV.")
