"""Extrai os ciclos do LIRAa (Levantamento Rápido de Índices para Aedes aegypti) dos informes da Prefeitura.

Os informes trazem só o resultado municipal de cada ciclo: período, índice de infestação predial
(IIP) e índice de Breteau (IB) para Aedes aegypti e Aedes albopictus, número de estratos em risco
baixo, médio e alto e a situação geral. Não há a geografia dos estratos, então não há dado por bairro.

Cada ciclo guarda o PDF, a página e o hash de onde saiu. Quando vários informes repetem o mesmo
ciclo, os valores precisam coincidir; divergências ficam registradas e o ciclo não é usado.
"""
from datetime import date, datetime, timezone
import json
from pathlib import Path
import re

import pandas as pd

from pipeline.comum.ibge_utils import sha256

ROOT = Path(__file__).resolve().parents[2]
TEXTOS = ROOT / 'dados/informes_extraidos/textos_pdfium'
OUT = ROOT / 'dados/liraa'
NUM = r'(\d+(?:,\d+)?)'

INICIO_QUADRO = re.compile(r'LIRA[as]?\s*\(Levantamento de [ÍI]ndice r[áa]pido[^)]*\),\s*Goi[âa]nia,\s*'
                           r'(\d{1,2})(?:/(\d{2}))?\s*a\s*(\d{1,2})/(\d{2})/(\d{4})', re.I)


def numero(texto):
    return float(texto.replace(',', '.'))


def texto_paginas(arquivo):
    d = json.loads(arquivo.read_text(encoding='utf-8'))
    for i, p in enumerate(d['paginas']):
        yield d, i + 1, p if isinstance(p, str) else (p.get('texto') or p.get('text') or '')


def ler_quadro(bloco):
    """Valores de um quadro do LIRAa; None se algum campo essencial não for reconhecido."""
    plano = re.sub(r'\s+', ' ', bloco)
    # IIP e IB vêm como "0,4 / 0,4" (às vezes "0.8/0,9" ou "3 / 3,8"); exigir a barra e no máximo dois
    # dígitos inteiros evita capturar anos e datas.
    dec = r'(\d{1,2}(?:[,.]\d{1,2})?)'
    aegypti = re.search(dec + r'\s*/\s*' + dec + r'(?![\d/])', plano)
    resto = plano[aegypti.end():] if aegypti else ''
    albo = re.search(r'albopictus[^0-9]*' + dec + r'(?:\s*/\s*' + dec + r')?', resto, re.I)
    def estratos(rotulos):
        m = re.search(r'(?:' + rotulos + r')[^)]*?\)\s*(\d+)', plano, re.I)
        return int(m.group(1)) if m else None
    baixo = estratos(r'baixo risco|satisfat[óo]rios')
    medio = estratos(r'm[ée]dio risco|em alerta')
    alto = estratos(r'alto risco|estratos de risco')
    situacao = re.search(r'SITUA[ÇC][ÃA]O (?:GERAL )?DO MUNIC[ÍI]PIO\s*(BAIXO RISCO|M[ÉE]DIO RISCO|ALTO RISCO|ALERTA|SATISFAT[ÓO]RIO|RISCO)', plano, re.I)
    if not (aegypti and baixo is not None and medio is not None and alto is not None and situacao):
        return None
    normal = {'ALERTA': 'medio', 'SATISFATORIO': 'baixo', 'SATISFATÓRIO': 'baixo', 'RISCO': 'alto'}
    s = situacao.group(1).upper().replace('MÉDIO', 'MEDIO')
    return {'iip_aegypti': numero(aegypti.group(1)), 'ib_aegypti': numero(aegypti.group(2)),
            'iip_albopictus': numero(albo.group(1)) if albo else None,
            'ib_albopictus': numero(albo.group(2)) if albo and albo.group(2) else None,
            'estratos_baixo': baixo, 'estratos_medio': medio, 'estratos_alto': alto,
            'situacao': normal.get(s, s.split()[0].lower())}


def main():
    candidatos = []
    for arquivo in sorted(TEXTOS.glob('*.json')):
        for doc, pagina, texto in texto_paginas(arquivo):
            for m in INICIO_QUADRO.finditer(texto):
                d1, m1, d2, m2, ano = m.groups()
                fim = date(int(ano), int(m2), int(d2))
                inicio = date(int(ano) if not m1 or int(m1) <= int(m2) else int(ano) - 1, int(m1 or m2), int(d1))
                valores = ler_quadro(texto[m.end():m.end() + 1400])
                candidatos.append({'inicio': inicio.isoformat(), 'fim': fim.isoformat(), 'arquivo_pdf': doc['arquivo'],
                                   'sha256_pdf': doc['sha256'], 'pagina': pagina, 'lido': valores is not None, **(valores or {})})
    tabela = pd.DataFrame(candidatos)
    campos = ['iip_aegypti', 'ib_aegypti', 'estratos_baixo', 'estratos_medio', 'estratos_alto', 'situacao']
    ciclos, divergencias = [], []
    for (inicio, fim), g in tabela.groupby(['inicio', 'fim']):
        lidos = g[g.lido]
        if lidos.empty:
            divergencias.append({'fim': fim, 'motivo': 'quadro não reconhecido', 'fontes': len(g)})
            continue
        distintos = lidos[campos].astype(str).drop_duplicates()
        if len(distintos) > 1:
            divergencias.append({'fim': fim, 'motivo': 'valores diferentes entre informes', 'fontes': len(lidos)})
            continue
        r = lidos.iloc[0]
        total = int(r.estratos_baixo + r.estratos_medio + r.estratos_alto)
        ciclos.append({'inicio': inicio, 'fim': fim, **{c: r[c] for c in campos},
                       'iip_albopictus': r.iip_albopictus, 'ib_albopictus': r.ib_albopictus, 'estratos_total': total,
                       'informes_concordantes': len(lidos), 'arquivo_pdf': r.arquivo_pdf, 'sha256_pdf': r.sha256_pdf, 'pagina': int(r.pagina)})
    ciclos = pd.DataFrame(ciclos).sort_values('fim')
    # Ciclos com problema na própria fonte, conferidos na imagem da página (dados/liraa/revisao_visual.json).
    revisao = json.loads((OUT / 'revisao_visual.json').read_text(encoding='utf-8'))['ciclos']
    ciclos['nota_fonte'] = ciclos.fim.map(lambda f: revisao.get(f, {}).get('nota_fonte'))
    for fim, r in revisao.items():
        for campo in r['sem_valor']:
            ciclos.loc[ciclos.fim == fim, campo] = None
    OUT.mkdir(parents=True, exist_ok=True)
    ciclos.to_csv(OUT / 'ciclos.csv', index=False, encoding='utf-8')
    manifesto = {'gerado_em': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'metodo': 'pipeline/processamento/extrair_liraa.py',
                 'ciclos': len(ciclos), 'ocorrencias_nos_informes': len(tabela), 'divergencias': divergencias,
                 'referencia_ms': 'IIP < 1% baixo risco; 1 a 3,9% médio; > 3,9% alto',
                 'revisao_visual': {'arquivo': 'dados/liraa/revisao_visual.json', 'sha256': sha256(OUT / 'revisao_visual.json')},
                 'produto': {'arquivo': 'dados/liraa/ciclos.csv', 'sha256': sha256(OUT / 'ciclos.csv')}}
    (OUT / 'manifesto.json').write_text(json.dumps(manifesto, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(ciclos[['inicio', 'fim', 'iip_aegypti', 'ib_aegypti', 'estratos_baixo', 'estratos_medio', 'estratos_alto', 'estratos_total', 'situacao', 'informes_concordantes']].to_string(index=False))
    print('divergências:', divergencias)


if __name__ == '__main__':
    main()
