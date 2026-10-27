"""Verifica o site público no navegador (Edge/Playwright): conteúdo, interações, mapa e celular."""
import json
from pathlib import Path
import threading

from playwright.sync_api import sync_playwright

from pipeline.servidor import criar_servidor

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'dados/verificacao_site'
DADOS = json.loads((ROOT / 'site/public/dados/site.json').read_text(encoding='utf-8'))
TITULOS = {'abaixo': 'Abaixo do habitual', 'habitual': 'Dentro do habitual', 'pouco_acima': 'Um pouco acima do habitual',
           'acima': 'Acima do habitual', 'alerta': 'Alerta', 'em_atualizacao': 'Em atualização'}


def numero(v):
    return f'{v:,}'.replace(',', '.')


def abrir(pagina, base, aba):
    pagina.goto(f'{base}#/{aba}', wait_until='networkidle')
    pagina.wait_for_selector(f".abas a[href='#/{aba}'][aria-current='page']", state='attached')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    servidor = criar_servidor(0)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{servidor.server_port}/'
    verificacoes = []
    with sync_playwright() as p:
        navegador = p.chromium.launch(channel='msedge', headless=True)
        for nome, tela in [('desktop', {'width': 1440, 'height': 900}), ('celular', {'width': 390, 'height': 844})]:
            pagina = navegador.new_page(viewport=tela)
            erros = []
            pagina.on('pageerror', lambda e: erros.append(str(e)))

            # Painel: seis indicadores, gráfico integrado, achados e mapa resumido.
            pagina.goto(base, wait_until='networkidle')
            status = pagina.locator('.status')
            assert status.count() == 6, 'seis indicadores no painel'
            dengue = status.first.inner_text()
            assert TITULOS[DADOS['dengue']['situacao']['zona']].upper() in dengue.upper()
            assert numero(DADOS['dengue']['situacao']['ultimas_4_semanas']) in dengue
            assert pagina.locator('.integrado path.linha-atual').count() == 1
            assert pagina.locator('.achado').count() == 4
            pagina.locator('.mapa-compacto').scroll_into_view_if_needed()
            pagina.wait_for_selector('.mapa-compacto .grafico-area svg path', state='attached')
            assert pagina.locator('.ranking-bairros li:not(.ranking-cabeca)').count() == 8
            pagina.evaluate('window.scrollTo(0, 0)')
            pagina.screenshot(path=str(OUT / f'{nome}_painel.png'), full_page=True)

            # Navegação: o indicador leva à aba; no celular, pelo menu.
            status.first.click()
            pagina.wait_for_url('**/#/dengue')
            if nome == 'celular':
                pagina.locator('.menu-botao').click()
            pagina.locator('.abas a', has_text='Chikungunya').click()
            pagina.wait_for_url('**/#/arboviroses')
            assert pagina.locator('.outra').count() == 2, 'chikungunya e zika'

            abrir(pagina, base, 'dengue')
            assert pagina.locator('.grafico-temporada path.linha-atual').count() == 1
            pagina.locator('.grafico-temporada .chip').first.click()
            assert pagina.locator('.grafico-temporada path.linha-ano').count() == 1, 'comparação com ano anterior'
            assert pagina.locator('rect.barra').count() == len(DADOS['dengue']['anual'])
            if DADOS['sorotipos']['dominante']:
                assert f"TIPO {DADOS['sorotipos']['dominante']}" in pagina.locator('.sorotipos').inner_text().upper()

            abrir(pagina, base, 'mosquito')
            assert pagina.locator('.grafico-cartao.mosquito').count() == 2, 'LIRAa e Rt'
            pagina.get_by_role('button', name='Umidade').click()

            abrir(pagina, base, 'escorpioes')
            assert pagina.locator('.emergencia').count() == 1
            assert pagina.locator('.barra-escorpiao').count() > 12

            abrir(pagina, base, 'bairro')
            pagina.wait_for_selector('.mapa-canvas canvas', timeout=30000)
            pagina.wait_for_function("!document.querySelector('.mapa-carregando')", timeout=30000)
            territorio = DADOS['territorios'][0]['nome']
            pagina.fill('.busca input', territorio[-8:])
            pagina.locator('.sugestoes button', has_text=territorio).first.click()
            ficha = pagina.locator('.ficha')
            ficha.get_by_text('Território do projeto').wait_for()
            assert ficha.locator('.lista-unidades li').count() == 3
            assert pagina.locator('.marcador-territorio').count() == len(DADOS['territorios'])
            pagina.wait_for_timeout(1500)
            pagina.locator('#mapa').screenshot(path=str(OUT / f'{nome}_mapa.png'))

            abrir(pagina, base, 'prevencao')
            pagina.get_by_role('tab', name='Escorpiões').click()
            assert 'Sacuda antes de usar' in pagina.locator('#prevencao').inner_text()

            abrir(pagina, base, 'sobre')
            assert pagina.locator('.modelo').count() == len(DADOS['modelos'])
            assert pagina.locator('.modelo.em_uso').count() == sum(m['status'] == 'em_uso' for m in DADOS['modelos'])

            assert not pagina.evaluate('document.documentElement.scrollWidth > innerWidth + 2'), 'rolagem horizontal'
            assert not erros, erros
            verificacoes.append(nome)
        navegador.close()
    servidor.shutdown()
    resultado = {'telas': verificacoes, 'situacao': DADOS['dengue']['situacao']['zona'],
                 'verificacoes': ['painel: indicadores, gráfico integrado, achados e mapa resumido', 'navegação pelas abas e pelo menu do celular',
                                  'gráfico do ano e comparação', 'gráfico anual e sorotipos', 'LIRAa, Rt e correlação com o clima', 'escorpiões',
                                  'busca de bairro, ficha e três unidades', 'marcadores dos territórios', 'abas de prevenção', 'modelos testados',
                                  'sem rolagem horizontal', 'sem erros de página']}
    (OUT / 'resultado.json').write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Verificação do site concluída.')


if __name__ == '__main__':
    main()
