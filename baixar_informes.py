"""Baixa os PDFs de arboviroses publicados pela SMS de Goiânia.

Instalação: py -m pip install playwright
Execução: py baixar_informes.py --anos 2026 2025 --listar
Usa o Microsoft Edge instalado, inclusive para executar o JavaScript da página.
"""

import argparse
import csv
import hashlib
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, unquote, urldefrag, urljoin, urlsplit, urlunsplit

BASE = "https://saude.goiania.go.gov.br/informe-dengue-chikungunya-zika-e-microcefalia/"


def pdf_url(url):
    return urlsplit(url).scheme in ("http", "https") and urlsplit(url).path.lower().endswith(".pdf")


def filename(url):
    stem = Path(unquote(urlsplit(url).path)).stem
    stem = re.sub(r"[^\w.-]+", "_", stem, flags=re.UNICODE).strip("._")[:120] or "informe"
    digest = hashlib.sha256(url.encode()).hexdigest()[:10]
    return f"{stem}_{digest}.pdf"


def canonical(url):
    parts = urlsplit(urldefrag(url)[0])
    return urlunsplit((parts.scheme, parts.netloc, quote(unquote(parts.path), safe="/:@!$&'()*+,;=-._~"), parts.query, ""))


def links_from_html(html, base):
    # Também captura URLs de PDFs presentes em listas JSON/JavaScript inline.
    html = html.replace("\\/", "/").replace("&amp;", "&")
    urls = re.findall(r'''(?:https?://|/)[^\s<>"'`\\]+?\.pdf(?:\?[^\s<>"'`\\]*)?''', html, re.I)
    return {urldefrag(urljoin(base, u))[0] for u in urls if pdf_url(urljoin(base, u))}


def save_manifest(path, records):
    columns = ["pagina", "ano_pagina", "url", "arquivo", "status", "bytes", "sha256", "verificado_em", "erro"]
    temp = path.with_suffix(".csv.part")
    with temp.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(records.values())
    temp.replace(path)


def collect(page, url, wait_seconds):
    response = page.goto(url, wait_until="domcontentloaded", timeout=60000)
    if response and response.status >= 400:
        raise RuntimeError(f"HTTP {response.status}: {url}")
    # networkidle não é confiável em páginas com rastreadores. Espera limitada
    # pelos PDFs e pela estabilização da lista renderizada.
    deadline = time.monotonic() + wait_seconds
    previous, stable = None, 0
    while time.monotonic() < deadline:
        current = page.locator('a[href*=".pdf" i]').count()
        stable = stable + 1 if current and current == previous else 0
        if stable >= 3:
            break
        previous = current
        page.wait_for_timeout(1000)
    html = page.content()
    anchors = page.locator("a[href]").evaluate_all(
        "nodes => nodes.map(a => ({url: a.href, texto: a.textContent.trim()}))"
    )
    urls = links_from_html(html, url)
    urls.update(urldefrag(a["url"])[0] for a in anchors if pdf_url(a["url"]))
    # A página de 2026 contém exemplos de URLs em comentários de edição.
    urls = {canonical(u) for u in urls if "..." not in u}
    return sorted(urls), anchors, html


def download(context, url, target, referer, retries):
    for attempt in range(retries):
        try:
            response = context.request.get(url, headers={"Referer": referer}, timeout=60000)
            try:
                if not response.ok:
                    raise RuntimeError(f"HTTP {response.status}")
                data = response.body()
                if not data.startswith(b"%PDF-"):
                    raise RuntimeError("Resposta não é PDF (pode ser página de erro ou bloqueio).")
                temp = target.with_suffix(".pdf.part")
                temp.write_bytes(data)
                temp.replace(target)
                return data
            finally:
                response.dispose()
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--anos", nargs="+", type=int, help="Ex.: --anos 2026 2025. Sem esta opção, descobre todos os anos no índice oficial.")
    parser.add_argument("--saida", type=Path, default=Path("dados/informes"))
    parser.add_argument("--listar", action="store_true", help="Descobre links e salva catálogo, sem baixar PDFs.")
    parser.add_argument("--limite", type=int, help="Limita downloads/verificações nesta execução, para testar.")
    parser.add_argument("--espera", type=float, default=0.8, help="Intervalo entre arquivos, em segundos.")
    parser.add_argument("--carregamento", type=int, default=25, help="Espera máxima pela lista dinâmica, em segundos.")
    parser.add_argument("--tentativas", type=int, default=3)
    parser.add_argument("--canal", default="msedge", choices=["msedge", "chrome", "chromium"])
    parser.add_argument("--visivel", action="store_true", help="Abre janela do navegador para diagnóstico.")
    args = parser.parse_args()
    if args.espera < 0 or args.carregamento < 1 or args.tentativas < 1 or (args.limite is not None and args.limite < 1):
        parser.error("Intervalo deve ser >= 0; carregamento, tentativas e limite devem ser >= 1.")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        parser.exit(2, "Instale a dependência: py -m pip install playwright\n")

    args.saida.mkdir(parents=True, exist_ok=True)
    manifest = args.saida / "manifesto.csv"
    records = {}
    if manifest.exists():
        with manifest.open(encoding="utf-8-sig", newline="") as f:
            records = {r["url"]: r for r in csv.DictReader(f)}
    errors, processed = 0, 0
    with sync_playwright() as p:
        launch = {"headless": not args.visivel}
        if args.canal != "chromium":
            launch["channel"] = args.canal
        browser = p.chromium.launch(**launch)
        context = browser.new_context()
        page = context.new_page()
        if args.anos:
            pages = {str(year): urljoin(BASE, f"informe-dengue-{year}/") for year in sorted(set(args.anos), reverse=True)}
        else:
            _, anchors, _ = collect(page, BASE, 1)
            pages = {}
            for a in anchors:
                if urlsplit(a["url"]).netloc != urlsplit(BASE).netloc:
                    continue
                if "informe-dengue" not in a["url"]:
                    continue
                years = re.findall(r"20\d{2}", urlsplit(a["url"]).path)
                if years:
                    pages["-".join(dict.fromkeys(years))] = a["url"]
            if not pages:
                raise RuntimeError("O índice oficial não retornou páginas anuais; tente --anos 2026 2025.")
        for year, url in pages.items():
            print(f"[{year}] Consultando {url}", flush=True)
            try:
                urls, _, html = collect(page, url, args.carregamento)
                (args.saida / f"pagina_{year}.html").write_text(html, encoding="utf-8")
                (args.saida / f"links_{year}.json").write_text(json.dumps(urls, ensure_ascii=False, indent=2), encoding="utf-8")
                if not urls:
                    raise RuntimeError("Nenhum PDF encontrado. Confira a página salva; a lista pode ter falhado ao carregar.")
                print(f"[{year}] {len(urls)} links de PDF encontrados.", flush=True)
            except Exception as exc:
                errors += 1
                print(f"ERRO na página {year}: {exc}", file=sys.stderr, flush=True)
                continue
            for pdf in urls:
                if args.limite is not None and processed >= args.limite:
                    break
                old = records.get(pdf, {})
                relative = old.get("arquivo") or f"{year}/{filename(pdf)}"
                target = (args.saida / relative).resolve()
                if not target.is_relative_to(args.saida.resolve()):
                    raise RuntimeError("Caminho inválido no manifesto.")
                record = {"pagina": url, "ano_pagina": year, "url": pdf, "arquivo": relative,
                          "status": "listado", "bytes": "", "sha256": "",
                          "verificado_em": datetime.now(timezone.utc).isoformat(), "erro": ""}
                try:
                    if target.exists():
                        data = target.read_bytes()
                        if not data.startswith(b"%PDF-"):
                            raise RuntimeError("Arquivo local inválido. Renomeie-o para permitir novo download.")
                        digest = hashlib.sha256(data).hexdigest()
                        if old.get("sha256") and old["sha256"] != digest:
                            raise RuntimeError("Arquivo local difere do hash registrado; verifique antes de continuar.")
                        record.update(status="existente", bytes=len(data), sha256=digest)
                    elif not args.listar:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        data = download(context, pdf, target, url, args.tentativas)
                        record.update(status="baixado", bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
                        print(f"  Baixado: {relative}", flush=True)
                        time.sleep(args.espera)
                except Exception as exc:
                    record.update(status="erro", erro=str(exc))
                    errors += 1
                    print(f"  ERRO: {pdf}: {exc}", file=sys.stderr, flush=True)
                records[pdf] = record
                save_manifest(manifest, records)
                processed += 1
            if args.limite is not None and processed >= args.limite:
                break
        browser.close()
    print(f"Concluído: {processed} links processados; {errors} erros. Pasta: {args.saida.resolve()}")
    return 1 if errors else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        sys.exit(1)
