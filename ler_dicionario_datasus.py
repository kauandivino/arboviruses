import sys
from pathlib import Path
sys.path.insert(0,str(Path('.tmp_pdf_reader').resolve()))
from pypdf import PdfReader

for name in ['ANIMPN_DIC_DADOS.pdf','DENGON_DIC_DADOS.pdf']:
    p=Path('dados/datasus/documentacao/dicionarios')/name
    text='\n'.join(page.extract_text() for page in PdfReader(p).pages)
    p.with_suffix('.txt').write_text(text,encoding='utf-8')
    if name.startswith('ANIM'):
        for term in ['ANT_DT_ACI','ANT_MUNIC','TP_ACIDENT','Escorpi']:
            start=text.lower().find(term.lower())
            print(term,start,text[max(0,start-250):start+1000])
