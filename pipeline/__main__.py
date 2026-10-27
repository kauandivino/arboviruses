"""Executa o pipeline completo a partir da raiz do projeto.

    .venv/Scripts/python.exe -m pipeline                 integração, verificações e painel (sem rede)
    .venv/Scripts/python.exe -m pipeline --reprocessar   refaz antes o processamento local dos originais
    .venv/Scripts/python.exe -m pipeline --coletar       baixa antes as versões publicadas pelas fontes oficiais
    .venv/Scripts/python.exe -m pipeline --semanal       atualiza só SINAN e INMET (usado pelo agendamento semanal)

Para na primeira etapa que falhar; o painel só é marcado como revisado e compilado
depois que todos os testes e validações passarem. O registro da execução fica em
dados/pipeline_ultima_execucao.json.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
NODE = ROOT / '.tools/node/node-v22.14.0-win-x64'


def competencia_cnes():
    # A competência usada é a de referência (dados/referencias.json), não a mais recente baixada.
    from pipeline.comum.referencias import CNES_COMPETENCIA
    return CNES_COMPETENCIA


def modulo(nome, *args):
    return [sys.executable, '-m', f'pipeline.{nome}', *args]


def etapas(args):
    if args.coletar:
        historicos = [str(a) for a in range(2014, 2022)]
        yield 'coleta', 'informes', modulo('coleta.baixar_informes')
        yield 'coleta', 'datasus', modulo('coleta.baixar_datasus')
        yield 'coleta', 'datasus_historico', modulo('coleta.baixar_datasus', '--anos', *historicos, '--agravos', 'dengue', '--saida', 'dados/datasus_historico')
        yield 'coleta', 'regional', modulo('coleta.extrair_regional')
        yield 'coleta', 'ibge', modulo('coleta.baixar_ibge')
        # Malha SIGGO e CNES nas versões de referência (dados/referencias.json): uma nova coleta da malha
        # ou outra competência do CNES mudariam a seleção dos territórios e são decisões explícitas.
        yield 'coleta', 'malha_municipal', modulo('coleta.baixar_malha_municipal', '--processar-local')
        yield 'coleta', 'cnes', lambda: modulo('coleta.baixar_cnes', '--competencia', competencia_cnes())
        yield 'coleta', 'inmet', modulo('coleta.baixar_inmet')
        yield 'coleta', 'inmet_historico', modulo('coleta.baixar_inmet', '--anos', *historicos, '--destino', 'dados/inmet_historico')
    elif args.semanal:
        # Só fontes que mudam toda semana. CNES, malhas e informes mudam a seleção dos territórios
        # ou exigem conferência humana, por isso ficam fora da atualização automática.
        yield 'coleta', 'datasus', modulo('coleta.baixar_datasus')
        yield 'coleta', 'inmet', modulo('coleta.baixar_inmet')
        yield 'coleta', 'regional', modulo('coleta.extrair_regional')
    elif args.reprocessar:
        yield 'processamento', 'datasus', modulo('coleta.baixar_datasus', '--processar-local')
        yield 'processamento', 'ibge', modulo('coleta.baixar_ibge', '--processar-local')
        yield 'processamento', 'malha_municipal', modulo('coleta.baixar_malha_municipal', '--processar-local')
        yield 'processamento', 'cnes', lambda: modulo('coleta.baixar_cnes', '--somente-processar', '--competencia', competencia_cnes())
        yield 'processamento', 'inmet', modulo('coleta.baixar_inmet', '--somente-processar')
        yield 'processamento', 'regional', modulo('coleta.extrair_regional')
    if args.coletar or args.reprocessar:
        yield 'processamento', 'extrair_informes', modulo('processamento.extrair_informes')
        yield 'processamento', 'revisar_territorio', modulo('processamento.revisar_territorio')
    yield 'integracao', 'integrar_bases', modulo('processamento.integrar_bases')
    yield 'integracao', 'selecionar_territorios', modulo('processamento.selecionar_territorios')
    yield 'integracao', 'preparar_mapa', modulo('processamento.preparar_mapa')
    yield 'modelagem', 'nowcast_dengue', modulo('modelagem.nowcast')
    yield 'modelagem', 'previsao_dengue', modulo('modelagem.previsao')
    yield 'modelagem', 'alerta_dengue', modulo('modelagem.alerta')
    yield 'modelagem', 'risco_dengue', modulo('modelagem.risco')
    for teste in ['cnes', 'datasus', 'download', 'extracao_informes', 'ibge', 'inmet', 'integracao',
                  'malha_municipal', 'revisao_territorial', 'selecao', 'mapa', 'acoes_campo', 'nowcast', 'previsao', 'alerta', 'referencias', 'regional']:
        yield 'verificacao', f'teste_{teste}', modulo(f'verificacao.verificar_{teste}')
    yield 'verificacao', 'validar_datasus', modulo('verificacao.validar_coleta_datasus')
    yield 'verificacao', 'validar_ibge', modulo('verificacao.validar_ibge')
    yield 'verificacao', 'validar_malha_municipal', modulo('verificacao.validar_malha_municipal')
    yield 'verificacao', 'validar_cnes', lambda: modulo('verificacao.validar_cnes', '--competencia', competencia_cnes())
    yield 'verificacao', 'validar_inmet', modulo('verificacao.validar_inmet')
    yield 'verificacao', 'validar_informes', modulo('verificacao.validar_extracao_informes')
    yield 'verificacao', 'validar_revisao_territorial', modulo('verificacao.validar_revisao_territorial')
    if not args.sem_painel:
        yield 'painel', 'snapshot', modulo('processamento.preparar_painel', '--concluir')
        yield 'painel', 'compilar', [str(NODE / 'node.exe'), str(NODE / 'node_modules/npm/bin/npm-cli.js'), 'run', 'build', '--prefix', str(ROOT / 'painel')]
        yield 'painel', 'verificar_navegador', modulo('verificacao.verificar_painel_browser')
        yield 'site', 'dados', modulo('processamento.preparar_site')
        yield 'site', 'compilar', [str(NODE / 'node.exe'), str(NODE / 'node_modules/npm/bin/npm-cli.js'), 'run', 'build', '--prefix', str(ROOT / 'site')]
        yield 'site', 'verificar_navegador', modulo('verificacao.verificar_site')


def main():
    parser = argparse.ArgumentParser(prog='python -m pipeline', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    modo = parser.add_mutually_exclusive_group()
    modo.add_argument('--coletar', action='store_true', help='baixa novamente das fontes oficiais (requer internet)')
    modo.add_argument('--reprocessar', action='store_true', help='reprocessa os originais locais, sem rede')
    modo.add_argument('--semanal', action='store_true', help='atualiza só SINAN e INMET (requer internet)')
    parser.add_argument('--sem-painel', action='store_true', help='não atualiza nem compila o painel nem o site')
    parser.add_argument('--listar', action='store_true', help='mostra as etapas sem executar')
    args = parser.parse_args()

    env = {**os.environ, 'PYTHONIOENCODING': 'utf-8', 'PATH': f'{NODE}{os.pathsep}{os.environ["PATH"]}'}
    registro = {'iniciado_em': datetime.now(timezone.utc).isoformat(), 'modo': 'coletar' if args.coletar else 'semanal' if args.semanal else 'reprocessar' if args.reprocessar else 'padrao', 'etapas': []}
    falhou = False
    for fase, nome, comando in etapas(args):
        if args.listar:
            print(f'{fase:13} {nome}')
            continue
        comando = comando() if callable(comando) else comando
        print(f'\n=== [{fase}] {nome}', flush=True)
        inicio = time.monotonic()
        codigo = subprocess.run(comando, cwd=ROOT, env=env).returncode
        registro['etapas'].append({'fase': fase, 'etapa': nome, 'codigo_saida': codigo, 'segundos': round(time.monotonic() - inicio, 1)})
        if codigo != 0:
            print(f'\nFALHA em [{fase}] {nome} (código {codigo}). Etapas seguintes não executadas.', file=sys.stderr)
            falhou = True
            break
    if args.listar:
        return
    registro['concluido_em'] = datetime.now(timezone.utc).isoformat()
    registro['status'] = 'falhou' if falhou else 'aprovado'
    (ROOT / 'dados/pipeline_ultima_execucao.json').write_text(json.dumps(registro, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'\nPipeline {registro["status"]}: {len(registro["etapas"])} etapas. Registro em dados/pipeline_ultima_execucao.json')
    sys.exit(1 if falhou else 0)


if __name__ == '__main__':
    main()
