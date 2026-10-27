"""Coleta a série semanal de Goiânia no InfoDengue (Fiocruz/FGV): casos, estimativa de atraso e Rt.

    .venv/Scripts/python.exe -m pipeline.coleta.baixar_infodengue

API pública, sem chave: https://info.dengue.mat.br/api/alertcity. Zika não está disponível
para Goiânia. A resposta original é guardada com hash a cada coleta; a série processada fica
em dados/infodengue/<agravo>.csv. A estimativa deles é refeita a cada semana, então só a
coleta guardada mostra o que eles estimavam em cada data.
"""
from datetime import date, datetime, timezone
import json
from pathlib import Path
import urllib.request

import pandas as pd

from pipeline.comum.ibge_utils import sha256

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'dados/infodengue'
API = 'https://info.dengue.mat.br/api/alertcity?geocode=5208707&disease={agravo}&format=json&ew_start=1&ew_end=53&ey_start=2014&ey_end={ano}'
AGRAVOS = ['dengue', 'chikungunya']
CAMPOS = ['SE', 'data_iniSE', 'casos', 'casos_est', 'casos_est_min', 'casos_est_max', 'Rt', 'p_rt1', 'nivel',
          'casprov', 'p_inc100k', 'pop', 'tempmed', 'umidmed', 'versao_modelo']


def main():
    agora = datetime.now(timezone.utc)
    (OUT / 'originais').mkdir(parents=True, exist_ok=True)
    registros = []
    for agravo in AGRAVOS:
        url = API.format(agravo=agravo, ano=date.today().year)
        with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'saude-no-territorio'}), timeout=180) as r:
            bruto = r.read()
        dados = json.loads(bruto)
        if not dados:
            raise RuntimeError(f'InfoDengue sem dados para {agravo}')
        original = OUT / 'originais' / f'{agravo}_{agora:%Y%m%dT%H%M%SZ}.json'
        original.write_bytes(bruto)
        serie = pd.DataFrame(dados)[CAMPOS].sort_values('SE')
        serie['semana_inicio'] = pd.to_datetime(serie.data_iniSE, unit='ms').dt.date
        serie = serie.drop(columns='data_iniSE')
        if serie.SE.duplicated().any():
            raise RuntimeError(f'Semanas repetidas na resposta do InfoDengue ({agravo})')
        destino = OUT / f'{agravo}.csv'
        serie.to_csv(destino, index=False, encoding='utf-8')
        registros.append({'agravo': agravo, 'url': url, 'consultado_em': agora.isoformat(timespec='seconds'),
                          'original': original.relative_to(ROOT).as_posix(), 'sha256_original': sha256(original),
                          'produto': destino.relative_to(ROOT).as_posix(), 'sha256_produto': sha256(destino),
                          'semanas': len(serie), 'primeira_se': int(serie.SE.min()), 'ultima_se': int(serie.SE.max()),
                          'versao_modelo': str(serie.versao_modelo.iloc[-1])})
        print(f'{agravo}: {len(serie)} semanas, até SE {serie.SE.max()} (modelo {serie.versao_modelo.iloc[-1]})')
    (OUT / 'manifesto.json').write_text(json.dumps({'fonte': 'InfoDengue (https://info.dengue.mat.br)', 'coletas': registros},
                                                    ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
