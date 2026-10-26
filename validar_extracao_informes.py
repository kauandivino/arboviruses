"""Validação técnica da extração e conferência dos números nas coordenadas do PDF."""
from collections import Counter
import csv
import json
from pathlib import Path
import re
import pypdfium2 as pdfium
from ibge_utils import now, save_json, sha256


def read(path):
    with path.open(encoding='utf-8-sig',newline='') as source:
        return list(csv.DictReader(source))


def main():
    out=Path('dados/informes_extraidos')
    manifest=json.loads((out/'manifesto_extracao.json').read_text(encoding='utf-8'))
    for row in manifest['fontes']:
        assert sha256(row['arquivo_pdf'])==row['sha256']
    for row in manifest['produtos']:
        assert sha256(row['arquivo'])==row['sha256']
    docs={r['sha256']:r for r in read(out/'documentos.csv')}
    rows=read(out/'observacoes.csv')
    assert len({r['observacao_id'] for r in rows})==len(rows)
    neighborhood=read(out/'bairros.csv'); municipal=read(out/'municipio.csv')
    assert {r['observacao_id'] for r in neighborhood+municipal}=={r['observacao_id'] for r in rows}
    assert len(neighborhood)+len(municipal)==len(rows)
    checked=0; opened={}
    try:
        for row in rows:
            doc=docs[row['sha256']]
            assert 1<=int(row['pagina'])<=int(doc['paginas'])
            assert row['municipio_ibge']=='5208707'
            assert row['pode_somar_entre_boletins']=='False'
            assert row['unidade']=='casos'
            assert row['valor']=='' or int(row['valor'])>=0
            if row['valor']:
                assert int(row['valor_original'].replace('.',''))==int(row['valor'])
            if row.get('linha_original'):
                page_text=json.loads(Path(row['texto_pagina_arquivo']).read_text(encoding='utf-8'))['paginas'][int(row['pagina'])-1]['texto']
                assert ' '.join(row['linha_original'].split()) in ' '.join(page_text.split())
            if row['natureza_temporal']=='nao_explicita' or row['alerta_periodo']:
                assert row['status_revisao']=='pendente'
            if row['metodo']=='ocr_nomes_valores_vetoriais':
                assert row['status_revisao']=='pendente'
                assert Path(row['imagem_conferencia']).exists()
                assert row['origem_valor']=='texto_vetorial_pdf'
            if row.get('bbox_valor'):
                key=row['sha256']
                if key not in opened:
                    opened[key]=pdfium.PdfDocument(row['arquivo_pdf'])
                page=opened[key][int(row['pagina'])-1]
                text=page.get_textpage()
                x0,y0,x1,y1=json.loads(row['bbox_valor'])
                source=text.get_text_bounded(left=x0-.3,bottom=y0-.3,right=x1+.3,top=y1+.3)
                text.close(); page.close()
                assert re.sub(r'\s','',source)==row['valor_original'],(row['observacao_id'],source)
                checked+=1
    finally:
        for pdf in opened.values(): pdf.close()
    raw=[json.loads(line) for line in (out/'elementos_brutos.jsonl').read_text(encoding='utf-8').splitlines()]
    raw_ids={r['elemento_id'] for r in raw}
    assert all(r['elemento_id'] in raw_ids for r in rows)
    assert len(raw)==len(read(out/'elementos.csv'))
    result=dict(validado_em=now(),status='aprovado_com_pendencias_semanticas_explicitadas',
                documentos=len(docs),observacoes=len(rows),observacoes_bairro=len(neighborhood),
                numeros_graficos_reconferidos_no_pdf=checked,
                status_revisao=Counter(r['status_revisao'] for r in rows))
    save_json(out/'validacao.json',result)
    print(json.dumps(result,ensure_ascii=True))


if __name__=='__main__':
    main()
