"""Séries UTC da estação A002, com cobertura e sem imputação de falhas."""
import csv
import io
from pathlib import Path
import unicodedata

import pandas as pd

from pipeline.comum.ibge_utils import now, save_json


def normalized(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', value.upper())
                   if not unicodedata.combining(c))


def measurement(value, kind):
    value = value.strip()
    if value.lower() in ('', 'null', 'nan', 'na'):
        return float('nan'), 'ausente'
    try:
        number = float(value.replace(',', '.'))
    except ValueError:
        raise ValueError(f'Valor numérico desconhecido: {value!r}')
    if abs(number) == 9999:
        return float('nan'), 'sentinela'
    if not pd.notna(number) or abs(number) == float('inf'):
        return float('nan'), 'ausente'
    if (kind == 'chuva_mm' and number < 0) or (kind == 'umidade_pct' and not 0 <= number <= 100):
        return float('nan'), 'fora_dominio'
    return number, 'valido'


def read_station(path, year):
    raw = Path(path).read_bytes()
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        text = raw.decode('latin-1')
    lines = text.splitlines()
    header_index = next(i for i, line in enumerate(lines) if normalized(line).startswith('DATA;'))
    metadata = dict(line.split(';', 1) for line in lines[:header_index] if ';' in line)
    if not any(v.strip() == 'A002' for v in metadata.values()):
        raise ValueError(f'Estação inesperada: {path}')
    reader = csv.DictReader(io.StringIO('\n'.join(lines[header_index:])), delimiter=';')
    columns = {}
    for field in reader.fieldnames:
        name = normalized(field)
        if name.startswith('PRECIPITACAO TOTAL, HORARIO'):
            columns['chuva_mm'] = field
        elif name.startswith('TEMPERATURA DO AR - BULBO SECO, HORARIA'):
            columns['temperatura_c'] = field
        elif name.startswith('UMIDADE RELATIVA DO AR, HORARIA'):
            columns['umidade_pct'] = field
    if len(columns) != 3:
        raise ValueError(f'Colunas meteorológicas inesperadas: {reader.fieldnames}')
    rows = []
    for source in reader:
        if not source.get(reader.fieldnames[0], '').strip():
            continue
        date = source[reader.fieldnames[0]].strip().replace('/', '-')
        hour = source[reader.fieldnames[1]].strip().split()[0].replace(':', '')
        hour = hour.zfill(4)
        if len(hour) != 4 or hour[2:] != '00':
            raise ValueError(f'Hora inesperada: {hour}')
        timestamp = pd.Timestamp(f'{date} {hour[:2]}:00:00', tz='UTC')
        if timestamp.year != year:
            raise ValueError(f'Data fora do ano: {timestamp}')
        row = dict(data_hora_utc=timestamp, linha_presente=True)
        for kind, column in columns.items():
            row[kind + '_original'] = source[column]
            row[kind], row[kind + '_status'] = measurement(source[column], kind)
        rows.append(row)
    frame = pd.DataFrame(rows).set_index('data_hora_utc').sort_index()
    if frame.empty or frame.index.has_duplicates:
        raise ValueError(f'Arquivo vazio ou horários duplicados: {path}')
    return frame, metadata


def summarize(frame, period):
    result = []
    for key, group in frame.groupby(frame.index.strftime('%Y-%m-%d' if period == 'dia' else '%Y-%m')):
        timestamp = group.index[0]
        expected = 24 if period == 'dia' else timestamp.days_in_month * 24
        row = dict(periodo_utc=key, estacao='A002', horas_esperadas=expected,
                   linhas_originais=int(group.linha_presente.sum()))
        for kind in ('chuva_mm', 'temperatura_c', 'umidade_pct'):
            count = int(group[kind].count())
            complete = count == expected
            value = (group[kind].sum(min_count=1) if kind == 'chuva_mm' else group[kind].mean())
            row[kind + '_horas_validas'] = count
            row[kind + '_cobertura_pct'] = 100 * count / expected
            row[kind + '_completo'] = complete
            row[kind + '_observado'] = value
            row[kind + '_completo_valor'] = value if complete else float('nan')
        result.append(row)
    return pd.DataFrame(result)


def processar(base, years):
    base = Path(base)
    frames, quality = [], []
    for year in sorted(set(years)):
        frame, metadata = read_station(base / 'estacao_originais' / f'{year}_A002.csv', year)
        last = frame.index.max()
        # Anos encerrados: todos os dias; ano ainda em curso: até a última data publicada.
        end = pd.Timestamp(f'{year}-12-31 23:00', tz='UTC') if year < pd.Timestamp.now(tz='UTC').year else last.normalize() + pd.Timedelta(hours=23)
        grid = pd.date_range(pd.Timestamp(f'{year}-01-01', tz='UTC'), end, freq='h', name='data_hora_utc')
        original_count = len(frame)
        frame = frame.reindex(grid)
        frame['linha_presente'] = frame['linha_presente'].fillna(False).astype(bool)
        for kind in ('chuva_mm', 'temperatura_c', 'umidade_pct'):
            frame[kind + '_status'] = frame[kind + '_status'].fillna('linha_ausente')
        quality.append(dict(ano=year, metadados_csv=metadata, linhas_originais=original_count,
                            horas_grade=len(frame), ultima_hora_original=last.isoformat(),
                            status={kind: frame[kind + '_status'].value_counts().to_dict()
                                    for kind in ('chuva_mm', 'temperatura_c', 'umidade_pct')}))
        frames.append(frame)
    hourly = pd.concat(frames).sort_index()
    if hourly.index.has_duplicates:
        raise ValueError('Sobreposição entre arquivos anuais')
    hourly['data_hora_brasilia'] = hourly.index.tz_convert('America/Sao_Paulo').astype(str)
    hourly['estacao'] = 'A002'
    out = base / 'goiania'; out.mkdir(exist_ok=True)
    hourly.to_csv(out / 'horario.csv', encoding='utf-8-sig')
    for period in ('dia', 'mes'):
        summarize(hourly, period).to_csv(out / f'{period}_utc.csv', index=False, encoding='utf-8-sig')
    save_json(out / 'qualidade.json', dict(gerado_em=now(), estacao='A002', agregacao='UTC', anos=quality))
    print(f'Concluído: {len(hourly)} horários; resultados em {out}', flush=True)
