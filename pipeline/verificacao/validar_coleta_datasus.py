"""Confere cobertura, hashes, filtros dos CSVs e reconciliação dos resumos."""
from collections import Counter
import csv
import json
from pathlib import Path
import zipfile

from pipeline.comum.epidemiologia import ano_corrente, anos_ate_corrente
from pipeline.coleta.baixar_datasus import VERSION, municipality, save_json, sha256, now


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate(base=Path('dados/datasus')):
    manifest=json.loads((base/'manifesto.json').read_text(encoding='utf-8'))
    require(not manifest['erros'], 'Manifesto contém erros de download.')
    data=[r for r in manifest['arquivos'] if r['agravo'] in ['dengue','animais']]
    expected={(a,y) for a in ['dengue','animais'] for y in anos_ate_corrente(2022)}
    # Só o ano corrente pode faltar (arquivo preliminar ainda não publicado).
    obtido={(r['agravo'],r['ano']) for r in data}
    require(obtido <= expected and all(y == ano_corrente() for _,y in expected - obtido),'Cobertura de agravos/anos incompleta.')
    for item in manifest['arquivos']:
        path=Path(item['arquivo'])
        require(path.stat().st_size==item['tamanho'],f'Tamanho incorreto: {path}')
        require(sha256(path)==item['sha256'],f'Hash incorreto: {path}')
    with zipfile.ZipFile(base/'documentacao/Docs_TAB_SINAN.zip') as z:
        require(z.testzip() is None,'Pacote de documentação corrompido.')
    reports=[]
    for item in sorted(data,key=lambda r:(r['ano'],r['agravo'])):
        a,y=item['agravo'],item['ano']
        report=json.loads((base/'qualidade'/f'{a}_{y}.json').read_text(encoding='utf-8'))
        require(report['versao']==VERSION and report['fonte_sha256']==item['sha256'],f'Processamento desatualizado: {a}/{y}')
        code=report['municipio']
        path=Path(report['csv'])
        require(sha256(path)==report['csv_sha256'],f'CSV alterado: {path}')
        refs=report['campos_referencia']
        all_counts=Counter()
        selected_counts=Counter()
        selected=0
        n=0
        with path.open(encoding='utf-8-sig',newline='') as f:
            for row in csv.DictReader(f):
                n+=1
                actual={ref:municipality(row[field])==code for ref,field in refs.items()}
                require(any(actual.values()),f'Registro fora do município: {path}/{n}')
                for ref,matched in actual.items():
                    require(row['GOIANIA_'+ref.upper()]==str(int(matched)),f'Indicador territorial incorreto: {path}/{n}')
                    all_counts[ref]+=int(matched)
                wanted=a=='dengue' or row['TP_ACIDENT']=='3'
                if wanted:
                    selected+=1
                    for ref,matched in actual.items():
                        selected_counts[ref]+=int(matched)
        require(n==report['registros_recorte'],f'Contagem CSV diverge: {path}')
        require(dict(all_counts)==report['registros_por_referencia'],f'Contagem territorial diverge: {path}')
        if a=='animais':
            spath=Path(report['csv_escorpioes'])
            require(sha256(spath)==report['csv_escorpioes_sha256'],f'CSV de escorpiões alterado: {spath}')
            sn=0
            with spath.open(encoding='utf-8-sig',newline='') as f:
                for row in csv.DictReader(f):
                    sn+=1
                    require(row['TP_ACIDENT']=='3',f'Tipo de animal indevido: {spath}')
            require(sn==selected==report['escorpioes_recorte'],f'Contagem de escorpiões diverge: {spath}')
        summary_counts=Counter()
        with (base/'resumos'/f'{a}_{y}_mensal.csv').open(encoding='utf-8-sig',newline='') as f:
            for row in csv.DictReader(f):
                summary_counts[row['referencia_geografica'],row['campo_data']]+=int(row['n_registros'])
        for ref,nref in selected_counts.items():
            for date_field in report['campos_data']:
                require(summary_counts[ref,date_field]==nref,f'Resumo mensal diverge: {a}/{y}/{ref}/{date_field}')
        result=dict(agravo=a,ano=y,situacao=item['situacao'],registros_recorte=n,
                    escorpioes=selected if a=='animais' else None,por_referencia=dict(all_counts))
        reports.append(result)
        print(result,flush=True)
    result=dict(validado_em=now(),status='aprovado',versao=VERSION,arquivos_originais=len(manifest['arquivos']),bases=len(data),resultados=reports)
    save_json(base/'validacao.json',result)
    print('OK: 10 bases, hashes, documentação ZIP, 15 CSVs e 10 resumos reconciliados.',flush=True)
    return result


if __name__=='__main__':
    validate()
