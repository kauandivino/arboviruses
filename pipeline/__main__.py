"""Executa o pipeline completo a partir da raiz do projeto.

    .venv/Scripts/python.exe -m pipeline                 integração, verificações e painel (sem rede)
    .venv/Scripts/python.exe -m pipeline --reprocessar   refaz antes o processamento local dos originais
    .venv/Scripts/python.exe -m pipeline --coletar       baixa antes as versões publicadas pelas fontes oficiais

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
    manifestos = sorted((ROOT / 'dados/cnes').glob('manifesto_*.json'))
    if not manifestos:
        raise SystemExit('Nenhuma competência CNES local; execute com --coletar.')
    return manifestos[-1].stem.removeprefix('manifesto_')


def modulo(nome, *args):
    return [sys.executable, '-m', f'pipeline.{nome}', *args]


def etapas(args):
    if args.coletar:
        yield 'coleta', 'informes', modulo('coleta.baixar_informes')
        yield 'coleta', 'datasus', modulo('coleta.baixar_datasus')
        yield 'coleta', 'ibge', modulo('coleta.baixar_ibge')
        yield 'coleta', 'malha_municipal', modulo('coleta.baixar_malha_municipal')
        yield 'coleta', 'cnes', modulo('coleta.baixar_cnes')
        yield 'coleta', 'inmet', modulo('coleta.baixar_inmet')
    elif args.reprocessar:
        yield 'processamento', 'datasus', modulo('coleta.baixar_datasus', '--processar-local')
        yield 'processamento', 'ibge', modulo('coleta.baixar_ibge', '--processar-local')
        yield 'processamento', 'malha_municipal', modulo('coleta.baixar_malha_municipal', '--processar-local')
        yield 'processamento', 'cnes', lambda: modulo('coleta.baixar_cnes', '--somente-processar', '--competencia', competencia_cnes())
        yield 'processamento', 'inmet', modulo('coleta.baixar_inmet', '--somente-processar')
    if args.coletar or args.reprocessar:
        yield 'processamento', 'extrair_informes', modulo('processamento.extrair_informes')
        yield 'processamento', 'revisar_territorio', modulo('processamento.revisar_territorio')
    yield 'integracao', 'integrar_bases', modulo('processamento.integrar_bases')
    yield 'integracao', 'selecionar_territorios', modulo('processamento.selecionar_territorios')
    yield 'integracao', 'preparar_mapa', modulo('processamento.preparar_mapa')
    yield 'modelagem', 'nowcast_dengue', modulo('modelagem.nowcast')
    for teste in ['cnes', 'datasus', 'download', 'extracao_informes', 'ibge', 'inmet', 'integracao',
                  'malha_municipal', 'revisao_territorial', 'selecao', 'mapa', 'acoes_campo', 'nowcast']:
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


def main():
    parser = argparse.ArgumentParser(prog='python -m pipeline', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    modo = parser.add_mutually_exclusive_group()
    modo.add_argument('--coletar', action='store_true', help='baixa novamente das fontes oficiais (requer internet)')
    modo.add_argument('--reprocessar', action='store_true', help='reprocessa os originais locais, sem rede')
    parser.add_argument('--sem-painel', action='store_true', help='não atualiza nem compila o painel')
    parser.add_argument('--listar', action='store_true', help='mostra as etapas sem executar')
    args = parser.parse_args()

    env = {**os.environ, 'PYTHONIOENCODING': 'utf-8', 'PATH': f'{NODE}{os.pathsep}{os.environ["PATH"]}'}
    registro = {'iniciado_em': datetime.now(timezone.utc).isoformat(), 'modo': 'coletar' if args.coletar else 'reprocessar' if args.reprocessar else 'padrao', 'etapas': []}
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
