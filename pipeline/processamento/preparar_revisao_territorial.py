"""Prepara recortes dos PDFs originais para conferência visual rastreável."""
from pathlib import Path
import json
import re
import pandas as pd
import pypdfium2 as pdfium
from PIL import Image, ImageDraw
from pipeline.comum.ibge_utils import sha256, save_json
from pipeline.comum.informes_pdf import lines_and_words


def main():
    root=Path('dados/revisao_territorial'); images=root/'conferencia'; images.mkdir(parents=True,exist_ok=True)
    elements=pd.read_csv('dados/informes_extraidos/elementos.csv',dtype=str,keep_default_na=False)
    selected=elements[elements.titulo_original.str.contains(r'(?i)casos.*(?:por bairro|por bairros)',regex=True)]
    index=[]
    for row in selected.to_dict('records'):
        with pdfium.PdfDocument(row['arquivo_pdf']) as pdf:
            page=pdf[int(row['pagina'])-1]
            lines,words=lines_and_words(page)
            title=next(line for line in lines if 'bairro' in line['text'].lower() and not line['rotated'])
            upper=title['bbox'][3]+12
            is_chart=row['titulo_original'].lower().startswith('gr')
            if is_chart:
                candidates=[line['bbox'][3]+5 for line in lines if re.match(r'Quadro\s+\d',line['text']) and line['bbox'][3]<title['bbox'][1]-30]
                lower=max(candidates,default=35)
            else:
                candidates=[line['bbox'][1]-10 for line in lines if re.match(r'\s*Fonte\s*:',line['text'],re.I) and line['bbox'][3]<title['bbox'][1]-20]
                lower=max(candidates,default=35)
            bitmap=page.render(scale=2.5); image=bitmap.to_pil().copy(); bitmap.close()
            crop=image.crop((0,int((page.get_height()-upper)*2.5),image.width,int((page.get_height()-lower)*2.5)))
            label=(f"SE{int(row['se_boletim']):02d}" if row['se_boletim'] else 'SE_desconhecida')+f"_{row['ano_boletim']}_p{row['pagina']}"
            path=images/(label+'.png'); crop.save(path)
            index.append(dict(**row,recorte=str(path),sha256_recorte=sha256(path),bbox_pdf=[0,lower,page.get_width(),upper]))
            page.close()
    save_json(root/'indice_conferencia.json',index)
    charts=[row for row in index if row['titulo_original'].lower().startswith('gr')]
    for start in range(0,len(charts),4):
        group=charts[start:start+4]
        sheet=Image.new('RGB',(2400,1800),'white'); draw=ImageDraw.Draw(sheet)
        for offset,row in enumerate(group):
            image=Image.open(row['recorte']).convert('RGB')
            image.thumbnail((1180,830))
            x=(offset%2)*1200; y=(offset//2)*900
            draw.text((x+15,y+10),Path(row['recorte']).stem,fill='black',font_size=25)
            sheet.paste(image,(x,y+50))
        sheet.save(images/f'prancha_{start//4+1:02d}.png')
    print('Recortes:',len(index),'gráficos:',len(charts),flush=True)


if __name__=='__main__':
    main()
