"""Prepara os dados do site público (site/public/dados) a partir dos produtos do pipeline.

Tudo vem de dados reais já processados e verificados; aqui só se resume, traduz para
linguagem simples e converte as geometrias para latitude/longitude (EPSG:4326).
"""
from datetime import datetime, timezone
import json
import re

import geopandas as gpd
import numpy as np
import pandas as pd

from pipeline.comum.referencias import CNES_ESTABELECIMENTOS
from pipeline import acoes_campo
from pipeline.comum.epidemiologia import inicio_ano_epidemiologico
from pipeline.comum.ibge_utils import sha256
from pipeline.modelagem.alerta import semana_epidemiologica

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'site/public/dados'
MOD = ROOT / 'dados/modelagem'
TIPOS_BAIRRO = {'Res': 'Residencial', 'Vl': 'Vila', 'Jd': 'Jardim', 'S': 'Setor', 'Prq': 'Parque', 'Ch': 'Chácara',
                'Bro': 'Bairro', 'Con': 'Condomínio', 'Cj': 'Conjunto', 'Cjr': 'Conjunto Residencial', 'Vlg': 'Village',
                'Lot': 'Loteamento', 'Sir': 'Sítio de Recreio', 'Faz': 'Fazenda', 'Grj': 'Granja', 'Dis': 'Distrito',
                'Col': 'Colônia', 'Zon': 'Zona', 'Sit': 'Sítio'}
# Tipos de unidade que a população procura; centrais administrativas, ambulâncias e laboratórios ficam de fora.
CATEGORIAS_UNIDADE = {'CENTRO DE SAUDE/UNIDADE BASICA': 'posto', 'POLICLINICA': 'policlinica',
                      'PRONTO ATENDIMENTO': 'urgencia', 'HOSPITAL GERAL': 'hospital'}
SIGLAS = {'USF', 'CS', 'UPA', 'CAIS', 'CIAMS', 'UBS', 'UABSF', 'CRDT', 'HC', 'HGG', 'HUGO', 'HDT', 'HMI', 'SUS', 'UFG', 'II', 'III', 'IV'}
MINUSCULAS = {'DE', 'DA', 'DO', 'DAS', 'DOS', 'E'}


def nome_legivel(texto):
    """Títulos em caixa alta do CNES para forma legível, mantendo siglas."""
    palavras = str(texto).split()
    saida = []
    for i, p in enumerate(palavras):
        if p in SIGLAS:
            saida.append(p)
        elif i and p in MINUSCULAS:
            saida.append(p.lower())
        else:
            saida.append(p.capitalize())
    return ' '.join(saida)


def nome_bairro(linha):
    base = str(linha.nm_bai or '').strip()
    if base and base.lower() not in ('nan', 'gleba') and linha.tp_bai in TIPOS_BAIRRO:
        return f'{TIPOS_BAIRRO[linha.tp_bai]} {base}'
    return str(linha.NOME_SIGGO)


def telefone(texto):
    digitos = re.sub(r'\D', '', str(texto or ''))
    if len(digitos) == 10:
        return f'({digitos[:2]}) {digitos[2:6]}-{digitos[6:]}'
    if len(digitos) == 8:
        return f'(62) {digitos[:4]}-{digitos[4:]}'
    return None


def arredondar(geom, casas=5):
    return json.loads(json.dumps(geom.__geo_interface__), parse_float=lambda v: round(float(v), casas))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    fontes = []

    def ler(caminho, **kw):
        caminho = ROOT / caminho
        fontes.append({'arquivo': caminho.relative_to(ROOT).as_posix(), 'sha256': sha256(caminho)})
        return pd.read_csv(caminho, **kw)

    # Dengue: semanas do ano epidemiológico atual com a faixa habitual (5 anos anteriores) e anos anteriores para comparar.
    alerta = ler('dados/modelagem/alerta_dengue_semanas.csv', parse_dates=['semana'])
    ano = int(alerta.ano.max())
    semanas = alerta[alerta.ano >= ano - 4]
    temporadas = {int(a): [{'se': int(r.se), 'valor': None if pd.isna(r.final) else int(r.final)} for _, r in g.iterrows()]
                  for a, g in semanas.groupby('ano')}
    atual = alerta[alerta.ano == ano]
    faixa = [{'se': int(r.se), 'q1': int(r.q1), 'mediana': int(r.mediana), 'q3': int(r.q3)} for _, r in atual.iterrows()]
    # A faixa habitual vale para o ano inteiro: completa as semanas ainda não ocorridas com os mesmos quartis.
    from pipeline.modelagem.alerta import canal
    from pipeline.modelagem.previsao import serie_corrigida
    from pipeline.modelagem import nowcast as nc
    reg, _, _ = nc.carregar('dengue')
    corte = reg.dig.max() - nc.SEMANA
    reg = reg[reg.dig <= corte]
    limites = canal(serie_corrigida(reg, inicio_ano_epidemiologico(ano) - nc.SEMANA), ano)
    faixa = [{'se': int(se), 'q1': int(r.q1), 'mediana': int(r.mediana), 'q3': int(r.q3)} for se, r in limites.iterrows()]

    nowcast = ler('dados/modelagem/nowcast_dengue.csv', parse_dates=['semana'])
    nowcast['valor'] = nowcast.estimado.fillna(nowcast.observado)
    ultimas, anteriores = nowcast.valor.iloc[-4:].sum(), nowcast.valor.iloc[-8:-4].sum()
    variacao = (ultimas - anteriores) / anteriores * 100 if anteriores else None
    tendencia = 'estavel' if variacao is None or abs(variacao) < 10 else ('subindo' if variacao > 0 else 'caindo')
    ultima = alerta.iloc[-1]
    # Vocabulário para a população; 'alerta' aqui é o alerta disparado (2 semanas seguidas acima do habitual).
    situacao = 'alerta' if ultima.alerta else {'sucesso': 'abaixo', 'seguranca': 'habitual', 'alerta': 'pouco_acima',
                                               'epidemica': 'acima', 'indeterminada': 'em_atualizacao'}[ultima.zona_tempo_real]

    previsao_meta = json.loads((MOD / 'previsao_dengue_manifesto.json').read_text(encoding='utf-8'))
    previsao = ler('dados/modelagem/previsao_dengue.csv', parse_dates=['semana'])
    projecao = []
    if previsao_meta['avaliacao']['exibida']:
        for _, r in previsao.iterrows():
            a, se = semana_epidemiologica(r.semana)
            projecao.append({'ano': a, 'se': se, 'semana': r.semana.date().isoformat(), 'previsto': int(r.previsto),
                             'inferior': int(r.inferior), 'superior': int(r.superior)})

    # Dengue ano a ano (anos epidemiológicos completos e o atual, parcial), da série corrigida.
    serie = serie_corrigida(reg, corte)
    por_ano = pd.Series(serie.values, index=[semana_epidemiologica(s)[0] for s in serie.index]).groupby(level=0).sum()
    anual = [{'ano': int(a), 'notificacoes': int(round(v)), 'parcial': bool(a == ano)} for a, v in por_ano.items() if a >= 2014]

    # Escorpiões e chuva por mês (base integrada).
    mensal = ler('dados/base_integrada/municipal_mensal_clima.csv', dtype={'mes': str})
    esc = mensal[mensal.agravo == 'escorpioes'][['mes', 'n_registros']]
    escorpioes = [{'mes': r.mes, 'acidentes': int(r.n_registros)} for _, r in esc.iterrows()]
    clima = ler('dados/base_integrada/clima_mensal.csv', dtype={'periodo_utc': str})
    chuva = [{'mes': r.periodo_utc, 'chuva_mm': None if pd.isna(r.chuva_mm_observado) else round(float(r.chuva_mm_observado), 1),
              'cobertura_pct': round(float(r.chuva_mm_cobertura_pct), 1),
              'temperatura_c': None if pd.isna(r.temperatura_c_observado) else round(float(r.temperatura_c_observado), 1)}
             for _, r in clima.iterrows()]
    dengue_mensal = [{'mes': r.mes, 'notificacoes': int(r.n_registros)} for _, r in mensal[mensal.agravo == 'dengue'].iterrows()]

    # Bairros: nome por extenso, citações nos boletins de dengue do ano e territórios do projeto.
    bairros = gpd.read_file(ROOT / 'dados/malha_municipal/goiania/bairros_municipais_analise.gpkg')
    fontes.append({'arquivo': 'dados/malha_municipal/goiania/bairros_municipais_analise.gpkg', 'sha256': sha256(ROOT / 'dados/malha_municipal/goiania/bairros_municipais_analise.gpkg')})
    boletins = ler('dados/base_integrada/bairros_publicados.csv', dtype=str)
    ano_boletim = boletins[boletins.agravo == 'dengue'].ano_boletim.max()
    citados = boletins[(boletins.agravo == 'dengue') & (boletins.ano_boletim == ano_boletim) &
                       (boletins.status_correspondencia == 'nominal_unico_nao_homologado')]
    citacoes = citados.groupby('OID_SIGGO_candidato').se_boletim.agg(lambda s: sorted({int(x) for x in s}))
    edicoes = sorted({int(x) for x in boletins[(boletins.agravo == 'dengue') & (boletins.ano_boletim == ano_boletim)].se_boletim})
    selecao = ler('dados/selecao_territorios/oito_territorios.csv', dtype={'CO_CNES': str})
    ordem = dict(zip(selecao.OID_SIGGO.astype(int), selecao.ordem_articulacao.astype(int)))
    realizadas = [a for a in acoes_campo.atuais() if a['situacao'] == 'realizada']

    bairros = bairros[bairros.geometry.area >= 1].to_crs(31982)
    bairros['geometry'] = bairros.geometry.simplify(6, preserve_topology=True)
    bairros = bairros.to_crs(4326)
    feicoes = []
    for _, b in bairros.iterrows():
        oid = int(b.OID_SIGGO)
        lista = citacoes.get(str(oid), [])
        centro = b.geometry.representative_point()
        feicoes.append({'type': 'Feature', 'id': oid, 'geometry': arredondar(b.geometry), 'properties': {
            'oid': oid, 'nome': nome_bairro(b), 'citacoes': len(lista), 'edicoes': lista,
            'territorio': ordem.get(oid), 'lon': round(centro.x, 5), 'lat': round(centro.y, 5)}})
    (OUT / 'bairros.geojson').write_text(json.dumps({'type': 'FeatureCollection', 'features': feicoes}, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')

    # Unidades de saúde públicas que atendem a população, com endereço e telefone do cadastro.
    cnes = ler(CNES_ESTABELECIMENTOS, dtype=str)
    publicas = cnes[(cnes.natureza_administracao_publica == 'True') & (cnes.possui_motivo_desativacao == 'False') &
                    (cnes.checagem_municipal == 'dentro_malha_2022') & cnes.tipo_unidade_descricao.isin(CATEGORIAS_UNIDADE)]
    unidades = []
    for _, u in publicas.iterrows():
        endereco = ', '.join(p for p in [nome_legivel(u.NO_LOGRADOURO), str(u.NU_ENDERECO or '').strip(), nome_legivel(u.NO_BAIRRO)] if p and p.lower() not in ('nan', 's/n'))
        unidades.append({'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [round(float(u.longitude), 6), round(float(u.latitude), 6)]},
                         'properties': {'cnes': u.CO_CNES, 'nome': nome_legivel(u.NO_FANTASIA), 'categoria': CATEGORIAS_UNIDADE[u.tipo_unidade_descricao],
                                        'endereco': endereco, 'telefone': telefone(u.NU_TELEFONE)}})
    (OUT / 'unidades.geojson').write_text(json.dumps({'type': 'FeatureCollection', 'features': unidades}, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')

    nomes = {f['properties']['oid']: f['properties']['nome'] for f in feicoes}
    territorios = [{'ordem': int(s.ordem_articulacao), 'oid': int(s.OID_SIGGO), 'nome': nomes.get(int(s.OID_SIGGO), s.territorio),
                    'parceiro': nome_legivel(s.unidade), 'citacoes': int(s.janelas_com_citacao), 'listas': int(s.janelas_observadas),
                    'acoes_realizadas': sum(1 for a in realizadas if a['OID_SIGGO'] == int(s.OID_SIGGO))}
                   for _, s in selecao.sort_values('ordem_articulacao').iterrows()]

    # Sorotipos identificados em Goiânia (amostras tipadas, pela semana de início dos sintomas).
    regional = pd.concat([pd.read_csv(f, parse_dates=['semana_inicio'], dtype={'sorotipo': str})
                          for f in sorted((ROOT / 'dados/regional').glob('dengue_go_*.csv'))], ignore_index=True)
    fontes.append({'arquivo': 'dados/regional/manifesto.json', 'sha256': sha256(ROOT / 'dados/regional/manifesto.json')})
    tipados = regional[(regional.grupo == 'goiania') & regional.sorotipo.isin(['1', '2', '3', '4'])].copy()
    tipados['mes'] = tipados.semana_inicio.dt.strftime('%Y-%m')
    tipados['ano'] = tipados.semana_inicio.dt.year
    por_mes = tipados.groupby(['mes', 'sorotipo']).notificacoes.sum().unstack(fill_value=0)
    por_mes = por_mes.reindex(columns=['1', '2', '3', '4'], fill_value=0).iloc[-24:]
    recentes = tipados[tipados.semana_inicio > tipados.semana_inicio.max() - pd.Timedelta(weeks=12)].groupby('sorotipo').notificacoes.sum()
    dominante = recentes.idxmax() if recentes.sum() >= 20 else None
    por_ano = tipados.groupby(['ano', 'sorotipo']).notificacoes.sum().unstack(fill_value=0)
    parcela_ano = por_ano.div(por_ano.sum(axis=1), axis=0)
    sorotipos = {
        'meses': [{'mes': m, **{f'denv{s}': int(r[s]) for s in ['1', '2', '3', '4']}} for m, r in por_mes.iterrows()],
        'dominante': dominante, 'amostras_12_semanas': int(recentes.sum()),
        'parcela_dominante': None if dominante is None else round(float(recentes[dominante] / recentes.sum()), 3),
        # Primeiro ano (desde 2014) em que o dominante passou de 5% das amostras: indica retorno recente.
        'primeiro_ano_relevante': None if dominante is None else int(parcela_ano.index[parcela_ano[dominante].fillna(0) >= 0.05][0]),
        'desde': int(parcela_ano.index.min()),
    }

    nowcast_meta = json.loads((MOD / 'nowcast_dengue_manifesto.json').read_text(encoding='utf-8'))
    ultima_semana = pd.Timestamp(nowcast_meta['data_corte_semana_digitacao'])
    site = {
        'gerado_em': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'dados_ate': (ultima_semana + pd.Timedelta(days=6)).date().isoformat(),
        'dengue': {
            'ano': ano,
            'situacao': {'zona': situacao, 'se': int(ultima.se), 'semana': ultima.semana.date().isoformat(),
                         'ultimas_4_semanas': int(round(ultimas)), 'quatro_anteriores': int(round(anteriores)),
                         'variacao_pct': None if variacao is None else round(float(variacao), 1), 'tendencia': tendencia},
            'faixa_habitual': faixa, 'temporadas': temporadas, 'projecao': projecao, 'anual': anual, 'mensal': dengue_mensal,
        },
        'sorotipos': sorotipos,
        'escorpioes': escorpioes,
        'clima': chuva,
        'boletins': {'ano': int(ano_boletim), 'edicoes': edicoes},
        'territorios': territorios,
        'acoes': {'realizadas': len(realizadas), 'participantes': sum(a['participantes'] for a in realizadas),
                  'territorios': len({a['OID_SIGGO'] for a in realizadas}),
                  'lista': [{'data': a['data'], 'territorio': a['territorio'], 'tipo': acoes_campo.TIPOS[a['tipo']], 'participantes': a['participantes']} for a in realizadas]},
        'contagens': {'unidades': len(unidades), 'bairros': len(feicoes)},
    }
    (OUT / 'site.json').write_text(json.dumps(site, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    manifesto = {'gerado_em': site['gerado_em'], 'metodo': 'pipeline/processamento/preparar_site.py', 'fontes': fontes,
                 'produtos': [{'arquivo': p.relative_to(ROOT).as_posix(), 'sha256': sha256(p)} for p in sorted(OUT.glob('*')) if p.name != 'manifesto.json']}
    (OUT / 'manifesto.json').write_text(json.dumps(manifesto, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print({p.name: f'{p.stat().st_size / 1024:.0f} KiB' for p in OUT.glob('*')})
    print('situação:', site['dengue']['situacao'])


if __name__ == '__main__':
    main()
