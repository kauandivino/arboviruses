"""Inspeção do painel local com Edge/Playwright; sem chamadas a fontes remotas."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import re
import threading
from playwright.sync_api import sync_playwright

OUT = Path('dados/verificacao_painel')
OUT.mkdir(parents=True, exist_ok=True)
# Serve o build atual em uma porta livre, apenas no próprio computador.
class Silencioso(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass
servidor = ThreadingHTTPServer(('127.0.0.1', 0), partial(Silencioso, directory='painel/dist'))
threading.Thread(target=servidor.serve_forever, daemon=True).start()
with sync_playwright() as p:
    browser = p.chromium.launch(channel='msedge', headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
    erros = []
    page.on('pageerror', lambda error: erros.append(str(error)))
    page.goto(f'http://127.0.0.1:{servidor.server_port}/', wait_until='networkidle')
    page.screenshot(path=str(OUT / 'municipal_desktop.png'), full_page=True)
    def capture(nome):
        page.wait_for_timeout(400)
        page.screenshot(path=str(OUT / f'{nome}.png'), full_page=True)
    def tab(nome):
        page.get_by_role('tab', name=nome, exact=True).click()
        page.wait_for_timeout(300)
    def choose(nome, valor):
        page.locator('button.filter-trigger').filter(has_text=nome).click()
        page.get_by_text(valor, exact=True).last.click()
        page.wait_for_timeout(200)
    page.get_by_role('button', name=re.compile('Ano')).click()
    page.get_by_text('2022',exact=True).last.click()
    assert '2022-01' in page.locator('body').inner_text()
    capture('municipal_2022')
    choose('Ano','All')
    assert '114 results' in page.locator('body').inner_text()
    choose('Ano','2026')
    tab('Bairros nos informes')
    capture('territorios_desktop')
    assert page.locator('[data-component-id="bairros-publicacao"] svg').count()>0
    assert len(page.get_by_role('link',name='Abrir PDF').all())>0
    choose('Publicação','2026/SE35')
    assert 'pendência' in page.locator('body').inner_text()
    capture('territorios_alerta')
    choose('Agravo','chikungunya')
    assert 'Nenhuma observação' in page.locator('body').inner_text()
    choose('Publicação','2024/SE10')
    capture('territorios_2024')
    tab('Clima')
    capture('clima_desktop')
    assert page.locator('[data-component-id="chuva-observada"] svg').count()>0
    tab('Unidades de saúde')
    capture('unidades_desktop')
    search=page.get_by_placeholder('Search data')
    search.fill('zzzz-inexistente')
    capture('unidades_sem_resultados')
    search.fill('')
    assert '200 results' in page.locator('body').inner_text()
    page.set_viewport_size({'width':390,'height':844})
    capture('unidades_mobile')
    tab('Evolução municipal')
    capture('municipal_mobile')
    overflow=page.evaluate('document.documentElement.scrollWidth > innerWidth + 2')
    assert not overflow, 'Página com overflow horizontal em tela estreita'
    page.set_viewport_size({'width':1440,'height':1000})
    tab('Plano de atuação')
    assert 'Prq Atheneu' in page.locator('body').inner_text()
    assert 'Jd Nova Esperança' in page.locator('body').inner_text()
    assert '8 results' in page.locator('body').inner_text()
    capture('selecao_desktop')
    page.set_viewport_size({'width':390,'height':844})
    capture('selecao_mobile')
    assert not page.evaluate('document.documentElement.scrollWidth > innerWidth + 2')
    assert not erros, erros
    (OUT / 'validacao_browser.json').write_text(json.dumps({'erros':erros,'overflow_mobile':overflow,'verificacoes':['cinco abas','ano 2022, todos e 2026','edição SE35 e alerta','combinação territorial vazia','edição 2024 chikungunya','busca vazia e restauração das 200 unidades','oito territórios e justificativas','desktop e mobile']},ensure_ascii=False,indent=2),encoding='utf-8')
    print('Verificação do navegador concluída.')
    browser.close()
servidor.shutdown()
