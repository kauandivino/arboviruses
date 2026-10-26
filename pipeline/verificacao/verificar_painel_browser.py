"""Inspeção do painel local com Edge/Playwright; sem chamadas a fontes remotas."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import re
import tempfile
import threading
from playwright.sync_api import sync_playwright

from pipeline import acoes_campo
from pipeline.servidor import criar_servidor

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
    assert page.locator('.st-nowcast-pendente').count() == 12, 'nowcast deve marcar as 12 semanas recentes'
    page.locator('.st-nowcast-alvo').nth(-1).hover()
    assert 'Estimativa final' in page.locator('.st-nowcast-tooltip').inner_text()
    assert 'Acerto da faixa' in page.locator('[data-component-id="nowcast-avaliacao"]').inner_text()
    exibida = json.loads(Path('dados/modelagem/previsao_dengue_manifesto.json').read_text(encoding='utf-8'))['avaliacao']['exibida']
    assert page.locator('[data-component-id="previsao-avaliacao"]').count() == 1
    assert page.locator('[data-component-id="previsao-semanas"]').count() == (1 if exibida else 0), 'regra de exibição da previsão'
    assert page.locator('[data-component-id="diagrama-controle"] .st-zona').count() == 4
    assert 'Como o alerta teria funcionado' in page.locator('[data-component-id="alerta-avaliacao"]').inner_text()
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
    tab('Mapa')
    assert page.locator('.st-mapa-territorio.selecionado').count()==8
    assert page.locator('.st-mapa-parceiro').count()>0
    page.locator('.st-mapa-foco select').select_option(label='1. Prq Atheneu')
    page.wait_for_timeout(400)
    assert 'USF PARQUE ATHENEU' in page.locator('.st-mapa-detalhe').inner_text()
    capture('mapa_desktop')
    page.get_by_role('button',name='Ver tudo').click()
    page.locator('.st-mapa-check input').uncheck()
    assert page.locator('.st-mapa-unidade').count()==0
    page.set_viewport_size({'width':390,'height':844})
    capture('mapa_mobile')
    assert not page.evaluate('document.documentElement.scrollWidth > innerWidth + 2')
    page.set_viewport_size({'width':1440,'height':1000})
    tab('Ações de campo')
    assert 'Indicadores de execução' in page.locator('body').inner_text()
    capture('acoes_desktop')
    tab('Plano de atuação')
    assert 'Prq Atheneu' in page.locator('body').inner_text()
    assert 'Jd Nova Esperança' in page.locator('body').inner_text()
    assert '8 results' in page.locator('body').inner_text()
    capture('selecao_desktop')
    page.set_viewport_size({'width':390,'height':844})
    capture('selecao_mobile')
    assert not page.evaluate('document.documentElement.scrollWidth > innerWidth + 2')
    assert not erros, erros

    # Registro de ações de ponta a ponta, com o servidor real gravando em pasta temporária.
    with tempfile.TemporaryDirectory() as pasta:
        api = criar_servidor(0, Path(pasta))
        threading.Thread(target=api.serve_forever, daemon=True).start()
        pagina = browser.new_page(viewport={'width': 1440, 'height': 1000})
        pagina.on('pageerror', lambda error: erros.append(str(error)))
        pagina.goto(f'http://127.0.0.1:{api.server_port}/equipe/', wait_until='networkidle')
        pagina.get_by_role('tab', name='Ações de campo', exact=True).click()
        pagina.get_by_text('Nenhuma ação registrada até agora.').wait_for()
        pagina.get_by_role('button', name='Registrar ação').click()
        pagina.get_by_text('Corrija os campos indicados.').wait_for()
        assert not acoes_campo.historico(Path(pasta)), 'formulário inválido não pode gravar'
        pagina.fill('#f-data', '2026-10-20')
        pagina.select_option('#f-territorio', label='1. Prq Atheneu')
        pagina.fill('#f-local', 'Teste automatizado')
        pagina.select_option('#f-parceiro', label='USF PARQUE ATHENEU')
        pagina.fill('#f-participantes', '12')
        pagina.fill('#f-responsavel', 'Verificação automática')
        pagina.get_by_role('button', name='Registrar ação').click()
        pagina.get_by_text('Ação registrada.').wait_for()
        pagina.get_by_role('cell', name='Teste automatizado').wait_for()
        capture_api = lambda nome: pagina.screenshot(path=str(OUT / f'{nome}.png'), full_page=True)
        capture_api('acoes_registrada')
        pagina.get_by_role('button', name=re.compile('^Editar registro ')).click()
        pagina.fill('#f-participantes', '14')
        pagina.get_by_role('button', name='Gravar alteração').click()
        pagina.get_by_text('Corrija os campos indicados.').wait_for()
        pagina.fill('#f-motivo', 'Contagem conferida')
        pagina.get_by_role('button', name='Gravar alteração').click()
        pagina.get_by_text('Alteração gravada.').wait_for()
        versoes = acoes_campo.historico(Path(pasta))
        assert [v['participantes'] for v in versoes] == [12, 14], versoes
        assert versoes[0]['territorio'] == 'Prq Atheneu' and versoes[0]['CO_CNES'] == '2665239'
        assert '14' in pagina.locator('[data-component-id="pessoas-alcancadas"]').inner_text()
        api.shutdown(); api.server_close()
    assert not erros, erros
    (OUT / 'validacao_browser.json').write_text(json.dumps({'erros':erros,'overflow_mobile':overflow,'verificacoes':['sete abas','ano 2022, todos e 2026','edição SE35 e alerta','combinação territorial vazia','edição 2024 chikungunya','busca vazia e restauração das 200 unidades','oito territórios e justificativas','mapa: foco, detalhe e camada de unidades','nowcast: 12 semanas estimadas, tooltip e avaliação','previsão: exibição condicionada à avaliação','diagrama de controle e avaliação do alerta','ações de campo: validação, registro, edição com motivo e versões','desktop e mobile']},ensure_ascii=False,indent=2),encoding='utf-8')
    print('Verificação do navegador concluída.')
    browser.close()
servidor.shutdown()
