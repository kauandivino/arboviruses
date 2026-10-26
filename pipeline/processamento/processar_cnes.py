"""Recorte municipal e diagnóstico das coordenadas sem geocodificar endereços."""
from collections import Counter
import json
from pathlib import Path
import zipfile

import geopandas as gpd
import pandas as pd
from pipeline.comum.ibge_utils import now, save_json, sha256


FIELDS = ['CO_UNIDADE', 'CO_CNES', 'NO_FANTASIA', 'NO_RAZAO_SOCIAL', 'NO_LOGRADOURO',
          'NU_ENDERECO', 'NO_COMPLEMENTO', 'NO_BAIRRO', 'CO_CEP', 'NU_TELEFONE', 'NO_EMAIL',
          'CO_MUNICIPIO_GESTOR', 'CO_ESTADO_GESTOR', 'TP_UNIDADE', 'CO_TIPO_UNIDADE',
          'CO_TIPO_ESTABELECIMENTO', 'CO_NATUREZA_JUR', 'TP_GESTAO', 'CO_MOTIVO_DESAB',
          'NU_LATITUDE', 'NU_LONGITUDE', 'ST_CONTRATO_FORMALIZADO']


def coordinate_status(latitude, longitude):
    if pd.isna(latitude) or pd.isna(longitude) or not str(latitude).strip() or not str(longitude).strip():
        return None, None, 'ausente'
    try:
        lat, lon = float(str(latitude).replace(',', '.')), float(str(longitude).replace(',', '.'))
    except ValueError:
        return None, None, 'nao_numerica'
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None, None, 'fora_dominio'
    if lat == 0 or lon == 0:
        return None, None, 'zero_suspeito'
    return lat, lon, 'dominio_valido'


def processar(base, comp):
    base = Path(base)
    out = base / 'goiania' / comp
    out.mkdir(parents=True, exist_ok=True)
    sources = []
    with zipfile.ZipFile(base / 'originais' / f'BASE_DE_DADOS_CNES_{comp}.ZIP') as archive:
        member = f'tbEstabelecimento{comp}.csv'
        chunks, count = [], 0
        with archive.open(member) as source:
            for chunk in pd.read_csv(source, sep=';', encoding='latin-1', dtype=str, keep_default_na=False, chunksize=50000):
                count += len(chunk)
                required = set(FIELDS) - set(chunk.columns)
                if required:
                    raise ValueError(f'Colunas esperadas ausentes: {required}')
                # Município de localização segundo a chave CO_UNIDADE; confirmado pelo município gestor.
                selected = chunk.CO_UNIDADE.str.startswith('520870')
                by_manager = chunk.CO_MUNICIPIO_GESTOR.eq('520870')
                if not selected.equals(by_manager):
                    raise ValueError('Município da chave diverge do município gestor; exige revisão')
                dates = [c for c in chunk.columns if c.startswith('TO_CHAR(DT_ATUALIZACAO,') or c.startswith('TO_CHAR(DT_ATU_GEO,')]
                chunks.append(chunk.loc[selected, FIELDS + dates].copy())
        data = pd.concat(chunks, ignore_index=True)
        data = data.rename(columns={c: ('data_atualizacao_cadastro' if c.startswith('TO_CHAR(DT_ATUALIZACAO,')
                                       else 'data_atualizacao_geolocalizacao')
                                    for c in data.columns if c.startswith('TO_CHAR(')})
        if data.empty or data.CO_UNIDADE.duplicated().any() or data.CO_CNES.duplicated().any():
            raise ValueError('Recorte vazio ou códigos duplicados')
        if not data.CO_CNES.str.fullmatch(r'\d{7}').all():
            raise ValueError('Código CNES fora do padrão de sete dígitos')
        for stem in ('tbTipoUnidade', 'tbTipoEstabelecimento', 'tbNaturezaJuridica', 'tbMotivoDesativacao'):
            name = f'{stem}{comp}.csv'
            raw = archive.read(name)
            doc = out / name
            doc.write_bytes(raw)
            sources.append(dict(membro_zip=name, sha256=sha256(doc)))
        for stem, key, label in [('tbTipoUnidade', 'TP_UNIDADE', 'tipo_unidade_descricao'),
                                 ('tbTipoEstabelecimento', 'CO_TIPO_ESTABELECIMENTO', 'tipo_estabelecimento_descricao'),
                                 ('tbNaturezaJuridica', 'CO_NATUREZA_JUR', 'natureza_juridica_descricao'),
                                 ('tbMotivoDesativacao', 'CO_MOTIVO_DESAB', 'motivo_desativacao_descricao')]:
            lookup = pd.read_csv(out / f'{stem}{comp}.csv', sep=';', encoding='latin-1', dtype=str, keep_default_na=False)
            # As tabelas de domínio têm código na primeira coluna e descrição na segunda.
            if lookup.iloc[:, 0].duplicated().any():
                raise ValueError(f'Chave duplicada no domínio {stem}')
            data[label] = data[key].map(dict(zip(lookup.iloc[:, 0], lookup.iloc[:, 1]))).fillna('')
    data['competencia'] = comp
    data['municipio_ibge7'] = '5208707'
    coordinates = [coordinate_status(lat, lon) for lat, lon in zip(data.NU_LATITUDE, data.NU_LONGITUDE)]
    data[['latitude', 'longitude', 'status_coordenada']] = pd.DataFrame(coordinates, index=data.index)
    data['possui_motivo_desativacao'] = data.CO_MOTIVO_DESAB.ne('')
    data['natureza_administracao_publica'] = data.CO_NATUREZA_JUR.str.startswith('1')
    valid = data.status_coordenada.eq('dominio_valido')
    points = gpd.GeoDataFrame(data.loc[valid].copy(), geometry=gpd.points_from_xy(
        data.loc[valid, 'longitude'], data.loc[valid, 'latitude']), crs='EPSG:4326')
    sectors = Path('dados/ibge/goiania/setores_goiania_2022.gpkg')
    data['checagem_municipal'] = 'sem_coordenada_valida'
    boundary_source = None
    if sectors.exists():
        boundary = gpd.read_file(sectors).to_crs(4326).geometry.union_all()
        inside = points.geometry.apply(boundary.covers)
        data.loc[points.index, 'checagem_municipal'] = inside.map({True: 'dentro_malha_2022', False: 'fora_malha_2022'})
        boundary_source = dict(arquivo=str(sectors), sha256=sha256(sectors), referencia='Censo 2022; união dos setores de Goiânia')
    else:
        data.loc[points.index, 'checagem_municipal'] = 'nao_verificada_sem_malha'
    data['coordenada_compartilhada'] = False
    data.loc[valid, 'coordenada_compartilhada'] = data.loc[valid].duplicated(['latitude', 'longitude'], keep=False)
    points = gpd.GeoDataFrame(data.loc[valid].copy(), geometry=points.geometry, crs=4326)
    # Todos os pontos numéricos permanecem no arquivo geral, inclusive os que exigem revisão.
    data.to_csv(out / 'estabelecimentos.csv', index=False, encoding='utf-8-sig')
    points.to_file(out / 'estabelecimentos.geojson', driver='GeoJSON')
    points.to_file(out / 'estabelecimentos.gpkg', layer='estabelecimentos', driver='GPKG')
    review = data.status_coordenada.ne('dominio_valido') | data.checagem_municipal.eq('fora_malha_2022')
    data.loc[review].to_csv(out / 'revisar_localizacao.csv', index=False, encoding='utf-8-sig')
    summary = data.groupby(['TP_UNIDADE', 'tipo_unidade_descricao'], dropna=False).agg(
        estabelecimentos=('CO_CNES', 'size'),
        com_motivo_desativacao=('possui_motivo_desativacao', 'sum'),
        natureza_publica=('natureza_administracao_publica', 'sum'))
    summary.to_csv(out / 'resumo_tipos.csv', encoding='utf-8-sig')
    report = dict(gerado_em=now(), competencia=comp, municipio='5208707', registros_brasil=count,
                  estabelecimentos=len(data), status_coordenada=Counter(data.status_coordenada),
                  checagem_municipal=Counter(data.checagem_municipal), malha_conferencia=boundary_source,
                  com_motivo_desativacao=int(data.possui_motivo_desativacao.sum()),
                  natureza_publica=int(data.natureza_administracao_publica.sum()),
                  coordenadas_compartilhadas=int(data.coordenada_compartilhada.sum()),
                  sem_descricao_dominio={key: int((data[key].ne('') & data[label].eq('')).sum())
                                         for key, label in [('TP_UNIDADE', 'tipo_unidade_descricao'),
                                                            ('CO_TIPO_ESTABELECIMENTO', 'tipo_estabelecimento_descricao'),
                                                            ('CO_NATUREZA_JUR', 'natureza_juridica_descricao'),
                                                            ('CO_MOTIVO_DESAB', 'motivo_desativacao_descricao')]},
                  fontes_dominios=sources, membro_estabelecimentos=member)
    save_json(out / 'qualidade.json', report)
    print(json.dumps(report, ensure_ascii=True, default=str), flush=True)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--competencia', required=True)
    args = parser.parse_args()
    processar(Path('dados/cnes'), args.competencia)
