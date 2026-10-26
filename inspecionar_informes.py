"""Inventário textual dos PDFs para preparar e auditar os extratores."""
from pathlib import Path
import json
import pypdfium2 as pdfium
from ibge_utils import sha256, save_json


def scan(path, base=Path('dados/informes_extraidos')):
    digest=sha256(path)
    out=Path(base)/'textos_pdfium'/(digest+'.json')
    if out.exists():
        result=json.loads(out.read_text(encoding='utf-8'))
    else:
        pages=[]
        with pdfium.PdfDocument(path) as reader:
            for i in range(len(reader)):
                page=reader[i]
                textpage=page.get_textpage()
                text=textpage.get_text_range().replace('\r','')
                textpage.close(); page.close()
                pages.append(dict(pagina=i+1,texto=text))
        result=dict(sha256=digest,arquivo=str(path),paginas=pages)
        save_json(out,result)
    candidates=[]
    for page in result['paginas']:
        text=page['texto']
        if any(w in text.lower() for w in ['bairro','escorpi','escorpiã','peçonh']):
            candidates.append(dict(pagina=page['pagina'],trecho='\n'.join(l for l in text.splitlines() if any(w in l.lower() for w in ['bairro','escorpi','peçonh']))))
    return dict(arquivo=str(path),sha256=digest,paginas=len(result['paginas']),candidatas=candidates)


if __name__=='__main__':
    files=sorted(Path('dados/informes').glob('*/*.pdf'))
    results=[]
    for i,path in enumerate(files,1):
        result=scan(path)
        results.append(result)
        if i%20==0: print(f'{i}/{len(files)} PDFs inventariados',flush=True)
    save_json(Path('dados/informes_extraidos/inventario_inspecao.json'),results)
    print('Arquivos',len(results),'com bairros',sum(bool(r['candidatas']) for r in results),flush=True)
