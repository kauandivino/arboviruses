"""OCR local dos nomes desenhados como contornos; valores vêm do texto do PDF."""
from collections import defaultdict
import json
import math
from pathlib import Path
import re

import cv2
import numpy as np
from rapidocr_onnxruntime import RapidOCR
from pipeline.comum.ibge_utils import save_json, sha256
from pipeline.comum.informes_pdf import lines_and_words

_ENGINE=None


def ocr_chart(page, folder):
    global _ENGINE
    folder=Path(folder); folder.mkdir(parents=True,exist_ok=True)
    cache=folder/'resultado.json'
    if cache.exists():
        return json.loads(cache.read_text(encoding='utf-8'))['registros']
    lines,words=lines_and_words(page)
    title=next(line for line in lines if 'bairro' in line['text'].lower())
    upper=title['bbox'][1]-22
    lower_candidates=[line['bbox'][3]+12 for line in lines if re.match(r'Quadro\s+\d',line['text']) and line['bbox'][3]<upper]
    lower=max(lower_candidates,default=page.get_height()*.07)
    scale=3.
    bitmap=page.render(scale=scale)
    image=bitmap.to_pil().copy(); bitmap.close()
    offset_y=int((page.get_height()-upper)*scale)
    chart=image.crop((0,offset_y,image.width,int((page.get_height()-lower)*scale)))
    chart.save(folder/'grafico.png')
    rgb=np.asarray(chart.convert('RGB')).astype(np.int16)
    mask=((rgb.max(axis=2)-rgb.min(axis=2)>35)&(rgb.min(axis=2)<230)&(rgb.max(axis=2)>70)).astype(np.uint8)
    count,labels,stats,centroids=cv2.connectedComponentsWithStats(mask,8)
    groups=defaultdict(list)
    for x,y,w,h,area in stats[1:]:
        if 8<w<110 and h>20 and area>w*h*.8:
            groups[round((y+h)/4)].append((int(x),int(y),int(w),int(h)))
    bars=max(groups.values(),key=len,default=[])
    if not 3<=len(bars)<=30:
        raise ValueError(f'OCR: barras com base comum não reconhecidas ({len(bars)})')
    bars=sorted(bars)
    centers=[x+w/2 for x,y,w,h in bars]
    tolerance=min(b-a for a,b in zip(centers,centers[1:]))*.4
    baseline=max(y+h for x,y,w,h in bars)
    band_offset=baseline+3
    band=chart.crop((0,band_offset,chart.width,chart.height))
    rotated=band.rotate(-45,expand=True,fillcolor='white')
    rotated.save(folder/'nomes_rotacionados.png')
    raw_cache=folder/'ocr_bruto.json'
    if raw_cache.exists():
        results=json.loads(raw_cache.read_text(encoding='utf-8'))['resultados']
    else:
        if _ENGINE is None:
            _ENGINE=RapidOCR(intra_op_num_threads=2,inter_op_num_threads=2)
        results,elapsed=_ENGINE(np.asarray(rotated),use_cls=False)
        save_json(raw_cache,dict(resultados=results,tempos=elapsed))
    names=[]
    c=math.sqrt(.5)
    for polygon,text,score in results or []:
        if not re.search(r'[A-Za-z]{3}',text):
            continue
        if abs(polygon[1][1]-polygon[0][1])>max(5,abs(polygon[1][0]-polygon[0][0])*.2):
            continue
        original=[]
        for x,y in polygon:
            dx,dy=x-rotated.width/2,y-rotated.height/2
            original.append([c*dx+c*dy+band.width/2,-c*dx+c*dy+band.height/2+band_offset])
        names.append(dict(text=text,score=score,polygon=original,anchor=max(x for x,y in original)))
    records=[]; used=set()
    for x,y,w,h in bars:
        matches=[(i,n) for i,n in enumerate(names) if abs(n['anchor']-(x+w/2))<tolerance]
        if len(matches)!=1 or matches[0][0] in used:
            raise ValueError(f'OCR: associação bairro/barra ambígua em x={x} ({len(matches)})')
        i,name=matches[0]; used.add(i)
        px=(x+w/2)/scale
        py=page.get_height()-(offset_y+y)/scale
        # Apenas números já existentes no texto vetorial; não usar OCR para adivinhar valores.
        numbers=[n for n in words if re.fullmatch(r'\d+(?:\.\d{3})*',n['text'])
                 and abs((n['bbox'][0]+n['bbox'][2])/2-px)<max(5,w/scale)
                 and 0 < (n['bbox'][1]+n['bbox'][3])/2-py < 20]
        if len(numbers)!=1:
            half_width=min(12.,tolerance/scale)
            box=[px-half_width,py+.2,px+half_width,py+20]
            textpage=page.get_textpage()
            try:
                raw=textpage.get_text_bounded(left=box[0],bottom=box[1],right=box[2],top=box[3])
            finally:
                textpage.close()
            raw=re.sub(r'\s','',raw)
            if not re.fullmatch(r'\d+(?:\.\d{3})*',raw):
                raise ValueError(f'OCR: número vetorial não unívoco acima da barra x={x}: {raw!r}')
            number=dict(text=raw,bbox=box)
        else:
            number=numbers[0]
        xs=[v[0]/scale for v in name['polygon']]
        ys=[page.get_height()-(offset_y+v[1])/scale for v in name['polygon']]
        records.append(dict(bairro=name['text'],valor_original=number['text'],valor=int(number['text'].replace('.','')),
                            bbox_bairro=[min(xs),min(ys),max(xs),max(ys)],bbox_valor=number['bbox'],
                            confianca_ocr_bairro=float(name['score']),imagem_conferencia=str(folder/'grafico.png'),
                            origem_nome='ocr_local_pendente_revisao',origem_valor='texto_vetorial_pdf'))
    save_json(cache,dict(registros=records,sha256_imagem=sha256(folder/'grafico.png'),escala_renderizacao=scale,
                         aviso='Confiança do OCR não é probabilidade de correção; todos os nomes exigem revisão.'))
    return records
