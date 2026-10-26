"""Extrai contagens reconhecidas dos informes, preservando fontes e ambiguidades."""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import re
import unicodedata

import pypdfium2 as pdfium
from pipeline.comum.epidemiologia import anos_ate_corrente
from pipeline.comum.ibge_utils import now, save_json, sha256
from pipeline.comum.informes_pdf import chart_values
from pipeline.processamento.inspecionar_informes import scan

VERSION = 1
HEADING = re.compile(r'(?im)^\s*(?:Quadro|Tabela|Gr[áa]fico|Figura)\s+\d+\s*[:–—-]')
COUNT = r'(?:\d{1,3}(?:\.\d{3})+|\d+)'


def norm(text):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFKD', text)
                           if not unicodedata.combining(c)).lower().split())


def identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def periodo(title):
    text=norm(title)
    years=re.findall(r'\b20\d{2}\b',text)
    result=dict(ano_referencia=int(years[-1]) if years else None, se_inicio=None, se_fim=None,
                natureza_temporal='nao_explicita', periodo_original=title, alerta_periodo='')
    interval=re.search(r'\bse\s*(\d{1,2})\s*(?:a|ate|[-–])\s*(\d{1,2})\b',text)
    if interval:
        start,end=map(int,interval.groups())
        result.update(se_inicio=start,se_fim=end,natureza_temporal='janela_movel' if 'ultima' in text else 'periodo_delimitado')
        if not 1<=start<=end<=53:
            result['alerta_periodo']='intervalo_se_invalido_ou_cruza_ano_sem_definicao'
        announced=re.search(r'ultimas?\s+(\d+)\s+semanas?',text)
        if announced and end-start+1!=int(announced[1]):
            result['alerta_periodo']='quantidade_semanas_diverge_intervalo_informado'
        if start==1 and ('acumul' in text or 'ano' in text):
            result['natureza_temporal']='acumulado'
    elif match:=re.search(r'ate\s+(?:a\s+)?se\s*(\d{1,2})',text):
        result.update(se_fim=int(match[1]),natureza_temporal='acumulado_ate_se',
                      alerta_periodo='inicio_do_acumulo_nao_explicito')
    return result


def bulletin_metadata(text):
    plain=norm(text)
    match=re.search(r'situacao epidemiologica\s*[-–:]?\s*(?:ate\s*)?se\s*(\d{1,2})\s*/\s*(20\d{2}|\d{2})\b',plain)
    if match:
        return dict(se_boletim=int(match[1]),ano_boletim=int(match[2]) if len(match[2])==4 else 2000+int(match[2]))
    match=re.search(r'\b(\d{1,2})\s*/\s*(20\d{2})\b',plain[:800])
    return dict(se_boletim=int(match[1]) if match else None,ano_boletim=int(match[2]) if match else None)


def title_of(block):
    # A legenda geralmente termina no ano de referência; não absorver o corpo numérico.
    title=[]
    for line in block.splitlines()[:3]:
        title.append(line)
        if re.search(r'\b20\d{2}\s*[*.,]*\s*$',line):
            break
    return ' '.join(' '.join(title).split())


def blocks(text):
    matches=list(HEADING.finditer(text))
    for i,match in enumerate(matches):
        block=text[match.start():matches[i+1].start() if i+1<len(matches) else len(text)].strip()
        yield title_of(block),block


def number(raw):
    return int(raw.replace('.','')) if re.fullmatch(COUNT,raw) else None


def neighborhood_table(block):
    header=re.search(r'bairros? de resid[eê]ncia\s+((?:casos\s+(?:notificados|prov[áa]veis|confirmados)\s*){3})',block,re.I)
    if not header:
        raise ValueError('Cabeçalho e ordem das três colunas não reconhecidos')
    indicators=[norm(v) for v in re.findall(r'casos\s+(notificados|prov[áa]veis|confirmados)',header[1],re.I)]
    rows=[]
    for line in block[header.end():].splitlines():
        if re.match(r'\s*fonte\s*:',line,re.I):
            break
        match=re.fullmatch(r'\s*(.+?)\s+('+COUNT+r'|[-–Xx])\s+('+COUNT+r'|[-–Xx])\s+('+COUNT+r'|[-–Xx])\s*',line)
        if match and re.search('[A-Za-zÀ-ÿ]',match[1]):
            for indicator,raw in zip(indicators,match.groups()[1:]):
                rows.append(dict(bairro=match[1].strip(),indicador='casos_'+indicator,
                                 valor_original=raw,valor=number(raw),linha_original=line.strip()))
    if not rows or len(rows)%3:
        raise ValueError('Nenhuma linha reconhecida na tabela territorial')
    return rows


def municipal_annual(block):
    """Somente as três colunas iniciais de quadros históricos de dengue reconhecidos."""
    text=norm(block)
    required=['demonstrativo da situacao epidemiologica de dengue','casos notificados','casos confirmados','casos provaveis']
    if not all(item in text for item in required):
        return []
    rows=[]
    for line in block.splitlines():
        match=re.match(r'^\s*(20\d{2})\*?\s+('+COUNT+r')\s+('+COUNT+r')\s+('+COUNT+r')\s+[-\d]',line)
        if match:
            for indicator,raw in zip(['casos_notificados','casos_confirmados','casos_provaveis'],match.groups()[1:]):
                rows.append(dict(ano_referencia=int(match[1]),bairro='',indicador=indicator,
                                 valor_original=raw,valor=number(raw),linha_original=line.strip()))
    return rows


def municipal_comparison(title, block):
    plain=norm(title)
    if not all(word in plain for word in ['distribuicao','notificados','confirmados','dengue','chikungunya']):
        return []
    years=list(dict.fromkeys(int(y) for y in re.findall(r'\b20\d{2}\b',title)))
    if len(years)!=2:
        return []
    rows=[]
    pattern=r'^\s*(Dengue|Chikungunya)\s+('+COUNT+r')\s+('+COUNT+r')\s+('+COUNT+r')\s+('+COUNT+r')(?:\s+[-\d,.]+)?\s*$'
    for line in block.splitlines():
        match=re.fullmatch(pattern,line,re.I)
        if match:
            for year,values in zip(years,[match.groups()[1:3],match.groups()[3:5]]):
                for indicator,raw in zip(['casos_notificados','casos_confirmados'],values):
                    rows.append(dict(ano_referencia=year,bairro='',agravo=match[1].lower(),indicador=indicator,
                                     valor_original=raw,valor=number(raw),linha_original=line.strip()))
    return rows


def write_csv(path, rows, fields=None):
    fields=fields or list(dict.fromkeys(k for row in rows for k in row)) or ['status']
    with Path(path).open('w',encoding='utf-8-sig',newline='') as output:
        writer=csv.DictWriter(output,fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in row.items()})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--entrada',type=Path,default=Path('dados/informes'))
    parser.add_argument('--destino',type=Path,default=Path('dados/informes_extraidos'))
    parser.add_argument('--anos',nargs='+',type=int,default=anos_ate_corrente(2022))
    parser.add_argument('--sem-ocr',action='store_true',help='Não executar OCR de nomes desenhados como contornos')
    args=parser.parse_args()
    out=args.destino; out.mkdir(parents=True,exist_ok=True)
    sources=defaultdict(list)
    with (args.entrada/'manifesto.csv').open(encoding='utf-8-sig',newline='') as source:
        for row in csv.DictReader(source):
            sources[row['arquivo'].replace('\\','/')].append(row)
    observations,elements,documents,aliases,issues=[],[],[],[],[]
    seen={}
    files=sorted(p for p in args.entrada.glob('*/*.pdf') if p.parent.name in {str(y) for y in args.anos})
    if not files:
        raise RuntimeError('Nenhum PDF local encontrado')
    rawpath=out/'elementos_brutos.jsonl'
    with rawpath.open('w',encoding='utf-8') as raw_output:
        for index,path in enumerate(files,1):
            relative=path.relative_to(args.entrada).as_posix()
            digest=sha256(path)
            source_rows=sources.get(relative,[])
            for source in source_rows:
                if source['sha256'] and source['sha256']!=digest:
                    raise RuntimeError(f'Hash diverge do manifesto de download: {path}')
            urls=sorted({r['url'] for r in source_rows})
            aliases.append(dict(arquivo_pdf=str(path),sha256=digest,ano_pasta=path.parent.name,urls=urls))
            if digest in seen:
                continue
            seen[digest]=str(path)
            try:
                scanned=scan(path,out)
                doc=json.loads((out/'textos_pdfium'/f'{digest}.json').read_text(encoding='utf-8'))
                meta=bulletin_metadata(doc['paginas'][0]['texto'])
                page_text='\n'.join(p['texto'] for p in doc['paginas'])
                arbovirus='arbovirose' in norm(page_text[:6000])
                documents.append(dict(arquivo_pdf=str(path),sha256=digest,ano_pasta=path.parent.name,
                                      paginas=len(doc['paginas']),**meta,
                                      classificacao='informe_arboviroses' if arbovirus else 'outro_documento',
                                      paginas_pouco_texto=sum(len(norm(p['texto']))<80 for p in doc['paginas']),
                                      menciona_escorpioes='escorpi' in norm(page_text)))
                pdf=None
                try:
                    for page in doc['paginas']:
                        page_blocks=list(blocks(page['texto']))
                        if 'bairro' in norm(page['texto']) and not any('bairro' in norm(title) for title,block in page_blocks):
                            issues.append(dict(arquivo_pdf=str(path),sha256=digest,pagina=page['pagina'],
                                               motivo='mencao_bairro_sem_tabela_ou_grafico_territorial',trecho=page['texto'][:400]))
                        if len(norm(page['texto']))<80:
                            issues.append(dict(arquivo_pdf=str(path),sha256=digest,pagina=page['pagina'],
                                               motivo='pouco_texto_possivel_imagem_ou_pagina_vazia',trecho=page['texto']))
                        for element_index,(title,block) in enumerate(page_blocks,1):
                            element_id=f'{digest}:{page["pagina"]}:{element_index}'
                            base=dict(arquivo_pdf=str(path),sha256=digest,pagina=page['pagina'],elemento_id=element_id,
                                      texto_pagina_arquivo=str(out/'textos_pdfium'/f'{digest}.json'),
                                      url_pdf=urls[0] if urls else '',url_pagina=(urls[0]+f'#page={page["pagina"]}') if urls else '',
                                      titulo_original=title,**meta)
                            raw_output.write(json.dumps(dict(**base,texto_bloco=block),ensure_ascii=False)+'\n')
                            plain=norm(title)
                            territorial='bairro' in plain
                            disease='dengue' if 'dengue' in plain else 'chikungunya' if 'chikungunya' in plain else ''
                            rows=[]; status='preservado_sem_interpretacao'; error=''
                            period=periodo(title)
                            try:
                                if territorial and disease and plain.startswith(('quadro','tabela')):
                                    rows=neighborhood_table(block)
                                    status='tabela_bairros_extraida'
                                    method='texto_tabela_cabecalho_explicito'
                                elif territorial and disease and plain.startswith(('grafico','figura')):
                                    if 'notificad' not in plain:
                                        raise ValueError('Indicador do gráfico não reconhecido')
                                    if pdf is None:
                                        pdf=pdfium.PdfDocument(path)
                                    pdfpage=pdf[page['pagina']-1]
                                    try:
                                        try:
                                            rows=chart_values(pdfpage)
                                        except ValueError:
                                            if args.sem_ocr:
                                                raise
                                            from pipeline.comum.informes_ocr import ocr_chart
                                            print(f'OCR local: {path.name}, página {page["pagina"]}',flush=True)
                                            rows=ocr_chart(pdfpage,out/'ocr'/digest/f'pagina_{page["pagina"]}')
                                    finally:
                                        pdfpage.close()
                                    for row in rows:
                                        row['indicador']='casos_notificados'
                                    status='grafico_bairros_extraido'
                                    method='ocr_nomes_valores_vetoriais' if any('origem_nome' in r for r in rows) else 'rotulos_e_numeros_impressos_por_posicao'
                                elif 'demonstrativo da situacao epidemiologica de dengue' in plain and (rows:=municipal_annual(page['texto'])):
                                    status='tabela_municipal_contagens_extraidas'
                                    method='tres_colunas_iniciais_quadro_historico_dengue'
                                    disease='dengue'
                                elif rows:=municipal_comparison(title,page['texto']):
                                    status='tabela_municipal_comparacao_extraida'
                                    method='quatro_contagens_dois_anos_cabecalho_explicito'
                                elif territorial:
                                    status='territorial_outro_agravo_sem_interpretacao'
                            except Exception as exc:
                                status='revisar_extracao'; error=str(exc)
                                rows=[]
                            for row_index,row in enumerate(rows,1):
                                local_period=period.copy()
                                row_disease=row.pop('agravo',disease)
                                if method=='quatro_contagens_dois_anos_cabecalho_explicito':
                                    local_period['ano_referencia']=row.pop('ano_referencia')
                                elif not territorial:
                                    local_period.update(ano_referencia=row.pop('ano_referencia'),
                                                        natureza_temporal='acumulado_anual_corte_nao_explicito',
                                                        se_inicio=None,se_fim=None,
                                                        alerta_periodo='coluna_ano_nao_informa_corte_se_especifico')
                                flags=[]
                                if method=='ocr_nomes_valores_vetoriais':
                                    flags.append('nome_ocr_exige_conferencia_visual')
                                if local_period['natureza_temporal']=='nao_explicita':
                                    flags.append('natureza_temporal_nao_explicita')
                                if local_period['alerta_periodo']:
                                    flags.append(local_period['alerta_periodo'])
                                if row['valor'] is None:
                                    flags.append('valor_ausente_ou_suprimido')
                                record=dict(**base,**local_period,**row,agravo=row_disease,
                                            nivel_territorial='bairro' if territorial else 'municipio',
                                            municipio_ibge='5208707',unidade='casos',metodo=method,
                                            abrangencia='somente_bairros_exibidos_exaustividade_nao_comprovada' if territorial else 'municipio',
                                            pode_somar_entre_boletins=False,
                                            status_revisao='pendente' if flags else 'checagens_automaticas_aprovadas',
                                            alertas=';'.join(flags))
                                record['observacao_id']=f'{element_id}:{row_index}'
                                record['grupo_observacao']=identity({k:record[k] for k in ['agravo','nivel_territorial','bairro','indicador','ano_referencia','se_inicio','se_fim','natureza_temporal']})
                                observations.append(record)
                            elements.append(dict(**base,status=status,registros=len(rows),erro=error))
                            if error:
                                issues.append(dict(arquivo_pdf=str(path),sha256=digest,pagina=page['pagina'],
                                                   motivo='elemento_nao_extraido',trecho=title+' | '+error))
                finally:
                    if pdf is not None: pdf.close()
            except Exception as exc:
                issues.append(dict(arquivo_pdf=str(path),sha256=digest,pagina='',motivo='erro_documento',trecho=str(exc)))
            if index%25==0:
                print(f'{index}/{len(files)} arquivos; {len(observations)} observações',flush=True)
    fields=list(dict.fromkeys(k for row in observations for k in row))
    write_csv(out/'observacoes.csv',observations,fields)
    write_csv(out/'bairros.csv',[r for r in observations if r['nivel_territorial']=='bairro'],fields)
    write_csv(out/'municipio.csv',[r for r in observations if r['nivel_territorial']=='municipio'],fields)
    write_csv(out/'bairros_revisar.csv',[r for r in observations if r['nivel_territorial']=='bairro' and r['status_revisao']=='pendente'],fields)
    write_csv(out/'elementos.csv',elements)
    write_csv(out/'documentos.csv',documents)
    write_csv(out/'arquivos_origem.csv',aliases)
    write_csv(out/'revisar.csv',issues)
    groups=Counter(r['grupo_observacao'] for r in observations)
    coverage=[]
    for year in args.anos:
        year_docs=[d for d in documents if int(d['ano_pasta'])==year]
        doc_hashes={d['sha256'] for d in year_docs}
        rows=[r for r in observations if r['sha256'] in doc_hashes and r['nivel_territorial']=='bairro']
        coverage.append(dict(ano_pasta=year,documentos=len(year_docs),
                             documentos_com_contagens_bairro=len({r['sha256'] for r in rows}),
                             observacoes_bairro=len(rows),bairros_grafias_distintas=len({r['bairro'] for r in rows}),
                             elementos_prioritarios_bairro_detectados=sum(e['sha256'] in doc_hashes and 'bairro' in norm(e['titulo_original']) and any(a in norm(e['titulo_original']) for a in ['dengue','escorpi']) for e in elements),
                             elementos_prioritarios_bairro_nao_extraidos=sum(e['sha256'] in doc_hashes and e['status']=='revisar_extracao' for e in elements),
                             nao_comprova_cobertura_completa=True))
    write_csv(out/'cobertura_por_ano.csv',coverage)
    report=dict(gerado_em=now(),versao_extrator=VERSION,arquivos=len(files),conteudos_unicos=len(seen),
                duplicatas_binarias=len(files)-len(seen),documentos_processados=len(documents),
                elementos=Counter(e['status'] for e in elements),observacoes=len(observations),
                observacoes_bairro=sum(r['nivel_territorial']=='bairro' for r in observations),
                natureza_temporal=Counter(r['natureza_temporal'] for r in observations),
                registros_pendentes=sum(r['status_revisao']=='pendente' for r in observations),
                grupos_com_mais_de_uma_publicacao=sum(n>1 for n in groups.values()),
                documentos_mencionam_escorpioes=sum(d['menciona_escorpioes'] for d in documents),
                cobertura=coverage,problemas=Counter(r['motivo'] for r in issues))
    save_json(out/'qualidade.json',report)
    save_json(out/'manifesto_extracao.json',dict(gerado_em=now(),versao=VERSION,fontes=aliases,
               bibliotecas={name:version(name) for name in ['pypdfium2','rapidocr-onnxruntime','onnxruntime','opencv-python','Pillow']},
               produtos=[dict(arquivo=str(p),sha256=sha256(p)) for p in sorted(out.glob('*.csv'))]+[
                   dict(arquivo=str(rawpath),sha256=sha256(rawpath))]))
    diagnostic=['# Cobertura dos informes extraídos','',
                'Escopo: PDFs já baixados de 2022–2026. As contagens abaixo são observações publicadas, não pessoas distintas.',
                '', '| Pasta | PDFs de conteúdo único | PDFs com contagens por bairro extraídas | Observações por bairro | Elementos prioritários pendentes |',
                '| --- | ---: | ---: | ---: | ---: |']
    for row in coverage:
        diagnostic.append(f'| {row["ano_pasta"]} | {row["documentos"]} | {row["documentos_com_contagens_bairro"]} | {row["observacoes_bairro"]} | {row["elementos_prioritarios_bairro_nao_extraidos"]} |')
    diagnostic.extend(['', 'Os valores vêm de tabelas ou gráficos selecionados pelo editor. A ausência de bairro ou de dado extraído não equivale a zero casos.',
                       '', 'As observações de 2024 com título apenas anual têm natureza temporal não explícita. As de 2026 usam janelas móveis; não devem ser somadas entre boletins.',
                       '', 'Nomes de OCR permanecem pendentes de revisão em `bairros_revisar.csv`. Consulte `elementos.csv` para os formatos preservados sem interpretação e as falhas de extração.',
                       '', 'Não foram identificadas contagens de acidentes com escorpiões por bairro nesta extração. Os boletins de arboviroses não suprem essa necessidade.',
                       '', 'Para selecionar oito bairros de forma comparável, ainda são necessários dados agregados de dengue e acidentes com escorpiões por bairro, período e critério de caso, abrangendo todos os bairros e com a definição territorial da Saúde.',
                       '', 'A ausência de série completa deve ser resolvida com uma fonte municipal adequada ou solicitação de dados agregados à Secretaria de Saúde. A validação técnica não elimina essas lacunas.'])
    (out/'diagnostico_cobertura.md').write_text('\n'.join(diagnostic)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True),flush=True)
    if any(r['motivo']=='erro_documento' for r in issues):
        raise SystemExit('Há PDFs com erro; confira revisar.csv')


if __name__=='__main__':
    main()
