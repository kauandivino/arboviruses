"""Indicadores de saneamento do Censo 2022 por bairro (malha SIGGO), ligados a criadouros do Aedes.

Método (sem ratear por área):
  - cada setor censitário é atribuído inteiro ao bairro que contém a maior parte da sua área;
  - setores com menos de 80% da área dentro desse bairro ficam fora (estão divididos entre bairros);
  - células sob sigilo do IBGE ("X") ficam sem valor; o setor não entra no indicador afetado;
  - um indicador só é publicado se os setores usados cobrirem ao menos 70% dos domicílios dos
    setores atribuídos ao bairro e somarem 50 domicílios ou mais.
Indicadores (% dos domicílios particulares permanentes ocupados):
  sem_rede_agua: não usam a rede geral de distribuição;
  agua_fora_de_casa: água não chega encanada até dentro da casa (só ao terreno ou não chega);
  lixo_nao_coletado: lixo queimado, enterrado, jogado em terreno baldio ou outro destino;
  esgoto_inadequado: fossa rudimentar, vala, rio/córrego, outra forma ou sem banheiro.
"""
from datetime import datetime, timezone
import json
from pathlib import Path

import geopandas as gpd
import pandas as pd

from pipeline.comum.ibge_utils import sha256

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'dados/saneamento'
FONTES = {
    'indicadores': ROOT / 'dados/ibge/goiania/indicadores_prioritarios_setores_2022.csv',
    'setores': ROOT / 'dados/ibge/goiania/setores_goiania_2022.gpkg',
    'bairros': ROOT / 'dados/malha_municipal/goiania/bairros_municipais_analise.gpkg',
}
FRACAO_MINIMA = 0.8
COBERTURA_MINIMA = 0.7
DOMICILIOS_MINIMOS = 50
TOTAL = 'domicilio1_V00001'
INDICADORES = {
    'sem_rede_agua': (['domicilio2_V00112', 'domicilio2_V00113', 'domicilio2_V00114', 'domicilio2_V00115',
                       'domicilio2_V00116', 'domicilio2_V00117', 'domicilio2_V00118'], 'Não usam a rede geral de água'),
    'agua_fora_de_casa': (['domicilio2_V00200', 'domicilio2_V00201'], 'Água não chega encanada dentro de casa'),
    'lixo_nao_coletado': (['domicilio2_V00399', 'domicilio2_V00400', 'domicilio2_V00401', 'domicilio2_V00402'], 'Lixo não coletado pelo serviço de limpeza'),
    'esgoto_inadequado': (['domicilio2_V00312', 'domicilio2_V00313', 'domicilio2_V00314', 'domicilio2_V00315', 'domicilio2_V00316'],
                          'Esgoto em fossa rudimentar, vala, córrego ou sem banheiro'),
}


def main():
    valores = pd.read_csv(FONTES['indicadores'], dtype=str)
    setores = gpd.read_file(FONTES['setores'])[['CD_SETOR', 'geometry']].to_crs(31982)
    bairros = gpd.read_file(FONTES['bairros'])[['OID_SIGGO', 'geometry']].to_crs(31982)
    setores['area'] = setores.geometry.area
    partes = gpd.overlay(setores, bairros, how='intersection', keep_geom_type=True)
    partes['fracao'] = partes.geometry.area / partes.area
    principal = partes.sort_values('fracao', ascending=False).drop_duplicates('CD_SETOR')[['CD_SETOR', 'OID_SIGGO', 'fracao']]
    tabela = principal.merge(valores, on='CD_SETOR', how='left')
    numerico = lambda s: pd.to_numeric(s, errors='coerce')  # "X" (sigilo) vira ausente, nunca zero
    tabela['total'] = numerico(tabela[TOTAL])
    contido = tabela.fracao >= FRACAO_MINIMA

    linhas = []
    for oid, g in tabela.groupby('OID_SIGGO'):
        linha = {'OID_SIGGO': int(oid), 'setores_atribuidos': len(g), 'setores_contidos': int(contido[g.index].sum()),
                 'domicilios_atribuidos': float(g.total.sum())}
        for nome, (colunas, _) in INDICADORES.items():
            usados = g[contido[g.index] & g.total.notna() & g[colunas].apply(numerico).notna().all(axis=1)]
            dom = usados.total.sum()
            cobertura = dom / linha['domicilios_atribuidos'] if linha['domicilios_atribuidos'] else 0
            publicavel = cobertura >= COBERTURA_MINIMA and dom >= DOMICILIOS_MINIMOS
            linha[f'{nome}_pct'] = round(float(usados[colunas].apply(numerico).sum().sum() / dom * 100), 1) if publicavel else None
            linha[f'{nome}_cobertura_pct'] = round(float(cobertura * 100), 1)
        linhas.append(linha)
    resultado = pd.DataFrame(linhas)
    OUT.mkdir(parents=True, exist_ok=True)
    destino = OUT / 'bairros_saneamento.csv'
    resultado.to_csv(destino, index=False, encoding='utf-8')
    total_bairros = len(bairros)
    resumo = {n: int(resultado[f'{n}_pct'].notna().sum()) for n in INDICADORES}
    manifesto = {'gerado_em': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'metodo': 'pipeline/processamento/saneamento_bairros.py',
                 'ano_referencia': 2022, 'parametros': {'fracao_minima_setor': FRACAO_MINIMA, 'cobertura_minima': COBERTURA_MINIMA, 'domicilios_minimos': DOMICILIOS_MINIMOS},
                 'indicadores': {n: d for n, (_, d) in INDICADORES.items()}, 'bairros_malha': total_bairros,
                 'bairros_com_setor': len(resultado), 'bairros_com_indicador': resumo,
                 'fontes': [{'arquivo': f.relative_to(ROOT).as_posix(), 'sha256': sha256(f)} for f in FONTES.values()],
                 'produto': {'arquivo': destino.relative_to(ROOT).as_posix(), 'sha256': sha256(destino)}}
    (OUT / 'manifesto.json').write_text(json.dumps(manifesto, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'{len(resultado)} bairros com setor atribuído de {total_bairros}; com indicador: {resumo}')
    print(resultado[[f'{n}_pct' for n in INDICADORES]].describe().round(1).to_string())


if __name__ == '__main__':
    main()
