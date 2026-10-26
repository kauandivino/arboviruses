"""Coleta SINAN/DATASUS e exporta recortes municipais sem carregar o Brasil em RAM.

Python 3.10–3.13 + pyreaddbc para processamento. Download usa apenas biblioteca padrão.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from datetime import datetime, timezone
import ftplib
import hashlib
import json
import mmap
from pathlib import Path
import re
import shutil
import struct
import sys
import time

HOST = 'ftp.datasus.gov.br'
ROOT = '/dissemin/publicos/SINAN'
DOCS = ['Docs_TAB_SINAN.zip', 'POP_I_Acesso_a_Microdados_5.pdf', 'POP_II_Descompactacao_expansao_conversao_3.pdf']
VERSION = 3
SCORPION_CODE = '3'  # ANIMPN_DIC_DADOS.pdf, campo 45: 2=aranha; 3=escorpião.


def now():
    return datetime.now(timezone.utc).isoformat()


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.part')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    tmp.replace(path)


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def connect():
    ftp = ftplib.FTP(HOST, timeout=90)
    ftp.login()
    return ftp


def inventory(years, agravos):
    result = []
    with connect() as ftp:
        for status in ['FINAIS', 'PRELIM']:
            folder = f'{ROOT}/DADOS/{status}'
            names = {n.upper(): n for n in ftp.nlst(folder)}
            ftp.voidcmd('TYPE I')
            for agravo in agravos:
                prefix = {'dengue': 'DENGBR', 'animais': 'ANIMBR'}[agravo]
                for year in years:
                    name = f'{prefix}{year % 100:02}.dbc'
                    matches = [n for n in names.values() if n.split('/')[-1].upper() == name.upper()]
                    if not matches:
                        continue
                    remote = folder + '/' + matches[0].split('/')[-1]
                    result.append(dict(agravo=agravo, ano=year, situacao=status, remoto=remote,
                                       url=f'ftp://{HOST}{remote}', tamanho=ftp.size(remote),
                                       modificado=ftp.sendcmd('MDTM ' + remote)[4:], nome=name))
    # Prefere FINAIS se o mesmo agravo/ano existir nos dois diretórios.
    unique = {}
    for item in result:
        unique.setdefault((item['agravo'], item['ano']), item)
    return list(unique.values())


def fetch(item, base, refresh=False):
    target = base / 'originais' / item['agravo'] / item['nome']
    if item['agravo'] == 'documentacao':
        target = base / 'documentacao' / item['nome']
    target.parent.mkdir(parents=True, exist_ok=True)
    receipt = target.with_suffix(target.suffix + '.json')
    if target.exists() and receipt.exists() and not refresh:
        old = json.loads(receipt.read_text(encoding='utf-8'))
        if (old.get('modificado') == item['modificado'] and target.stat().st_size == item['tamanho']
                and sha256(target) == old.get('sha256')):
            return dict(old, status='existente', arquivo=str(target), verificado_em=now())
    part = target.with_suffix(target.suffix + '.part')
    part_meta = target.with_suffix(target.suffix + '.part.json')
    identity = {k: item[k] for k in ['url', 'tamanho', 'modificado']}
    old_identity = json.loads(part_meta.read_text()) if part_meta.exists() else None
    resume = part.exists() and old_identity == identity and part.stat().st_size <= item['tamanho']
    if not resume:
        with part.open('wb'):
            pass
    save_json(part_meta, identity)
    for attempt in range(3):
        try:
            with connect() as ftp:
                start = part.stat().st_size
                last_print = time.monotonic()
                def progress(block):
                    nonlocal last_print
                    output.write(block)
                    if time.monotonic() - last_print >= 20:
                        print(f"  {item['nome']}: {output.tell() / item['tamanho']:.0%}", flush=True)
                        last_print = time.monotonic()
                if start < item['tamanho']:
                    with part.open('ab') as output:
                        ftp.retrbinary('RETR ' + item['remoto'], progress, blocksize=262144, rest=start or None)
                ftp.voidcmd('TYPE I')
                if ftp.size(item['remoto']) != item['tamanho'] or ftp.sendcmd('MDTM ' + item['remoto'])[4:] != item['modificado']:
                    raise RuntimeError('Fonte mudou durante o download; execute novamente para atualizar o inventário.')
            if part.stat().st_size != item['tamanho']:
                raise RuntimeError('Tamanho recebido diverge do FTP.')
            digest = sha256(part)
            part.replace(target)
            result = dict(item, arquivo=str(target), sha256=digest, status='baixado', obtido_em=now())
            save_json(receipt, result)
            print(f"  Salvo: {item['nome']} ({item['tamanho']/1024**2:.1f} MB)", flush=True)
            return result
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def municipality(value):
    text = str(value).strip()
    if text.endswith('.0'):
        text = text[:-2]
    return text[:6] if text.isdigit() and len(text) in (6, 7) else text


def dbf_schema(path):
    with path.open('rb') as f:
        head = f.read(32)
        if len(head) != 32:
            raise ValueError('Cabeçalho DBF incompleto.')
        count, header, width = struct.unpack_from('<IHH', head, 4)
        fields, offset = [], 1
        while f.tell() < header:
            raw = f.read(32)
            if raw[:1] == b'\r':
                break
            if len(raw) < 32:
                raise ValueError('Descritor DBF incompleto.')
            name = raw[:11].split(b'\0')[0].decode('ascii').upper()
            fields.append(dict(nome=name, tipo=chr(raw[11]), tamanho=raw[16], decimais=raw[17], offset=offset))
            offset += raw[16]
        if offset != width or path.stat().st_size < header + count * width:
            raise ValueError('DBF truncado ou tamanho de registro inconsistente.')
        return count, header, width, fields


def cell(raw, field):
    text = raw.decode('cp1252').strip(' \0')
    if field['tipo'] == 'D' and len(text) == 8 and text.isdigit():
        if text == '00000000':
            return ''
        return f'{text[:4]}-{text[4:6]}-{text[6:]}'
    return text


def export_dbf(dbf, target, item, code):
    count, header, width, fields = dbf_schema(dbf)
    names = [f['nome'] for f in fields]
    by_name = {f['nome']: f for f in fields}
    occurrence = next((name for name in ['ANT_MUNIC_', 'ID_MUN_OCOR'] if name in names), None)
    accident_date = next((name for name in ['ANT_DT_ACI', 'DT_ACID'] if name in names), None)
    refs = {'residencia': 'ID_MN_RESI', 'notificacao': 'ID_MUNICIP', 'ocorrencia': occurrence}
    refs = {label: name for label, name in refs.items() if name in names}
    if 'residencia' not in refs or (item['agravo'] == 'animais' and 'TP_ACIDENT' not in names):
        raise ValueError('Campos essenciais ausentes; esquema precisa ser revisado.')
    if item['agravo'] == 'animais' and (not occurrence or not accident_date):
        raise ValueError('Município ou data do acidente não reconhecidos; revise o dicionário do esquema.')
    date_fields = ['DT_NOTIFIC', 'DT_SIN_PRI'] if item['agravo'] == 'dengue' else ['DT_NOTIFIC', accident_date]
    if any(field not in names for field in date_fields):
        raise ValueError('Campo de data essencial ausente; revise o esquema.')
    if any(f['tipo'] not in ['C','N','D','F','L'] for f in fields):
        raise ValueError('DBF contém tipo de campo não suportado; revise o esquema.')
    extra = ['FONTE_ARQUIVO', 'FONTE_ANO', 'FONTE_SITUACAO', 'GOIANIA_RESIDENCIA', 'GOIANIA_NOTIFICACAO', 'GOIANIA_OCORRENCIA']
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix('.csv.part')
    scorpion = target.with_name(target.stem.replace('animais', 'escorpioes') + '.csv')
    scorpion_temp = scorpion.with_suffix('.csv.part')
    summary = Counter()
    selected, deleted, scorpions = 0, 0, 0
    ref_counts, missing_dates = Counter(), Counter()
    animal_counts = Counter()
    with dbf.open('rb') as inp, mmap.mmap(inp.fileno(), 0, access=mmap.ACCESS_READ) as data, temp.open('w', newline='', encoding='utf-8-sig') as out:
        writer = csv.DictWriter(out, fieldnames=names + extra)
        writer.writeheader()
        sout = scorpion_temp.open('w', newline='', encoding='utf-8-sig') if item['agravo'] == 'animais' else None
        try:
            swriter = csv.DictWriter(sout, fieldnames=names + extra) if sout else None
            if swriter:
                swriter.writeheader()
            for index in range(count):
                start = header + index * width
                if data[start:start+1] == b'*':
                    deleted += 1
                    continue
                flags = {}
                for label, name in refs.items():
                    field = by_name[name]
                    value = data[start+field['offset']:start+field['offset']+field['tamanho']].decode('ascii').strip()
                    flags[label] = municipality(value) == code
                if not any(flags.values()):
                    continue
                raw = data[start:start+width]
                row = {f['nome']:cell(raw[f['offset']:f['offset']+f['tamanho']], f) for f in fields}
                row.update(FONTE_ARQUIVO=item['nome'], FONTE_ANO=item['ano'], FONTE_SITUACAO=item['situacao'],
                           GOIANIA_RESIDENCIA=int(flags.get('residencia', False)), GOIANIA_NOTIFICACAO=int(flags.get('notificacao', False)),
                           GOIANIA_OCORRENCIA=int(flags.get('ocorrencia', False)))
                writer.writerow(row)
                selected += 1
                is_scorpion = row.get('TP_ACIDENT', '').strip() == SCORPION_CODE
                if item['agravo'] == 'animais':
                    animal_counts[row.get('TP_ACIDENT', '') or 'SEM_INFORMACAO'] += 1
                    if is_scorpion:
                        swriter.writerow(row)
                        scorpions += 1
                for ref, matched in flags.items():
                    if not matched:
                        continue
                    ref_counts[ref] += 1
                    if item['agravo'] == 'animais' and not is_scorpion:
                        continue
                    for date_field in date_fields:
                        value = row.get(date_field, '')
                        try:
                            month = datetime.strptime(value, '%Y-%m-%d').strftime('%Y-%m')
                        except ValueError:
                            month = 'SEM_DATA_VALIDA'
                            missing_dates[f'{ref}/{date_field}'] += 1
                        summary[(item['agravo'] if item['agravo']=='dengue' else 'escorpioes', item['ano'], ref,
                                 date_field, month, row.get('CLASSI_FIN', ''), row.get('CRITERIO', ''), row.get('EVOLUCAO', ''))] += 1
        finally:
            if sout:
                sout.close()
    temp.replace(target)
    if item['agravo'] == 'animais':
        scorpion_temp.replace(scorpion)
    report = dict(arquivo=item['nome'], ano=item['ano'], situacao=item['situacao'], municipio=code,
                  registros_brasil=count, registros_excluidos_dbf=deleted, registros_recorte=selected,
                  registros_por_referencia=dict(ref_counts), escorpioes_recorte=scorpions if item['agravo']=='animais' else None,
                  tipos_animais=dict(animal_counts), datas_ausentes_invalidas=dict(missing_dates), campos=fields,
                  campos_referencia=refs, campos_data=date_fields,
                  csv=str(target), csv_sha256=sha256(target), processado_em=now(), versao=VERSION, fonte_sha256=item['sha256'])
    if item['agravo'] == 'animais':
        report.update(csv_escorpioes=str(scorpion), csv_escorpioes_sha256=sha256(scorpion))
    return report, summary


def process(item, base, code, keep_dbf=False):
    from pyreaddbc import dbc2dbf
    raw = Path(item['arquivo'])
    if sha256(raw) != item['sha256']:
        raise RuntimeError('Hash do arquivo original diverge do manifesto; obtenha novamente a fonte.')
    out = base / 'goiania' / f"{item['agravo']}_{item['ano']}.csv"
    report_file = base / 'qualidade' / f"{item['agravo']}_{item['ano']}.json"
    summary_file = base / 'resumos' / f"{item['agravo']}_{item['ano']}_mensal.csv"
    if report_file.exists() and summary_file.exists() and out.exists():
        old = json.loads(report_file.read_text(encoding='utf-8'))
        extra_ok = item['agravo'] != 'animais' or (Path(old.get('csv_escorpioes', '')).is_file() and sha256(Path(old['csv_escorpioes'])) == old.get('csv_escorpioes_sha256'))
        if old.get('fonte_sha256') == item['sha256'] and old.get('versao') == VERSION and old.get('municipio') == code and sha256(out) == old.get('csv_sha256') and extra_ok:
            print(f"  Recorte existente validado: {out.name}", flush=True)
            return old
    dbf = base / 'temporarios' / (raw.stem + '.dbf')
    dbf.parent.mkdir(parents=True, exist_ok=True)
    # O cabeçalho DBF permanece no DBC, permitindo estimar espaço antes de expandir.
    with raw.open('rb') as f:
        header = f.read(32)
    n, h, w = struct.unpack_from('<IHH', header, 4)
    needed = n*w+h
    if shutil.disk_usage(base).free < needed * 1.2:
        raise RuntimeError(f'Espaço livre insuficiente para expandir {needed/1024**3:.1f} GB.')
    print(f"  Expandindo {raw.name}: ~{needed/1024**3:.2f} GB temporários", flush=True)
    dbc2dbf(str(raw), str(dbf))
    report, summary = export_dbf(dbf, out, item, code)
    summary_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = summary_file.with_suffix('.csv.part')
    with tmp.open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['agravo', 'ano_arquivo', 'referencia_geografica', 'campo_data', 'mes', 'classi_fin_codigo', 'criterio_codigo', 'evolucao_codigo', 'n_registros'])
        for key, value in sorted(summary.items()):
            writer.writerow([*key, value])
    tmp.replace(summary_file)
    save_json(report_file, report)
    if not keep_dbf:
        dbf.unlink()  # somente o DBF intermediário criado por esta execução
    print(f"  {out.name}: {report['registros_recorte']} registros selecionados", flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--anos', nargs='+', type=int, default=list(range(2022,2027)))
    parser.add_argument('--agravos', nargs='+', choices=['dengue', 'animais'], default=['dengue','animais'])
    parser.add_argument('--saida', type=Path, default=Path('dados/datasus'))
    parser.add_argument('--municipio', default='520870', help='Código SINAN de seis dígitos; padrão Goiânia.')
    parser.add_argument('--somente-baixar', action='store_true')
    parser.add_argument('--processar-local', action='store_true', help='Processa o último manifesto sem acessar a rede.')
    parser.add_argument('--atualizar', action='store_true', help='Força novo download; alterações de tamanho/data já são detectadas automaticamente.')
    parser.add_argument('--manter-dbf', action='store_true')
    args=parser.parse_args()
    if not re.fullmatch(r'\d{6}', args.municipio):
        parser.error('Informe município com seis dígitos.')
    base=args.saida
    base.mkdir(parents=True, exist_ok=True)
    errors=[]
    manifest=base/'manifesto.json'
    if args.processar_local:
        data=json.loads(manifest.read_text(encoding='utf-8'))
        results=[r for r in data['arquivos'] if r.get('ano') in args.anos and r['agravo'] in args.agravos and r.get('status') != 'erro']
        for agravo in args.agravos:
            for year in args.anos:
                if not any(r['agravo']==agravo and r['ano']==year for r in results):
                    errors.append(f'Fonte local ausente: {agravo}/{year}')
    else:
        print('Consultando inventário oficial SINAN via FTP...',flush=True)
        items=inventory(sorted(set(args.anos)), args.agravos)
        missing=[(a,y) for a in args.agravos for y in args.anos if not any(i['agravo']==a and i['ano']==y for i in items)]
        errors += [f'Arquivo não publicado no índice consultado: {a}/{y}' for a,y in missing]
        save_json(base/'inventario.json',dict(consultado_em=now(),host=HOST,arquivos=items,ausentes=missing))
        with connect() as ftp:
            ftp.voidcmd('TYPE I')
            for name in DOCS:
                remote=f'{ROOT}/DOCS/{name}'
                items.append(dict(agravo='documentacao',nome=name,remoto=remote,url=f'ftp://{HOST}{remote}', tamanho=ftp.size(remote),modificado=ftp.sendcmd('MDTM '+remote)[4:]))
        results=[]
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs={pool.submit(fetch,i,base,args.atualizar):i for i in items}
            for job in as_completed(jobs):
                item=jobs[job]
                try:
                    results.append(job.result())
                except Exception as exc:
                    errors.append(f"{item['nome']}: {exc}")
                    results.append(dict(item,status='erro',erro=str(exc)))
                    print(errors[-1],file=sys.stderr,flush=True)
                save_json(manifest,dict(executado_em=now(),arquivos=results,erros=errors))
    if not args.somente_baixar:
        for item in sorted(results,key=lambda i:(i['agravo'],i.get('ano',0))):
            if item['agravo']=='documentacao' or item.get('status')=='erro':
                continue
            try:
                process(item,base,args.municipio,args.manter_dbf)
            except Exception as exc:
                errors.append(f"Processamento {item['nome']}: {exc}")
                print(errors[-1],file=sys.stderr,flush=True)
    save_json(base/'ultima_execucao.json',dict(finalizado_em=now(),anos=args.anos,municipio=args.municipio, somente_baixar=args.somente_baixar,erros=errors))
    print(f'Concluído; {len(errors)} erros. Pasta: {base.resolve()}',flush=True)
    return 1 if errors else 0


if __name__=='__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as exc:
        print(f'ERRO: {exc}',file=sys.stderr)
        sys.exit(1)
