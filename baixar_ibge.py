"""Executa download, recorte e validação do IBGE/Censo 2022 para Goiânia."""
import argparse
from pathlib import Path
import subprocess
import sys


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--saida',type=Path,default=Path('dados/ibge'))
    parser.add_argument('--somente-baixar',action='store_true')
    parser.add_argument('--processar-local',action='store_true')
    parser.add_argument('--atualizar',action='store_true')
    args=parser.parse_args()
    if args.somente_baixar and args.processar_local:
        parser.error('Escolha somente download ou processamento local.')
    root=Path(__file__).resolve().parent
    options=['--saida',str(args.saida.resolve())]
    for flag in ['somente_baixar','processar_local','atualizar']:
        if getattr(args,flag):
            options.append('--'+flag.replace('_','-'))
    for script in ['baixar_ibge_agregados.py','baixar_ibge_malhas.py']:
        subprocess.run([sys.executable,str(root/script),*options],check=True)
    if not args.somente_baixar:
        subprocess.run([sys.executable,str(root/'validar_ibge.py'),'--saida',str(args.saida.resolve())],check=True)


if __name__=='__main__':
    try:
        main()
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)
