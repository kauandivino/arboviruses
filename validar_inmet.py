"""Confere hashes e reconstitui os resumos a partir da série horária salva."""
import json
from pathlib import Path
import pandas as pd
from ibge_utils import sha256, save_json, now
from processar_inmet import summarize


def main():
    base = Path('dados/inmet')
    for record in json.loads((base / 'manifesto.json').read_text(encoding='utf-8')):
        path = base / 'originais' / f"{record['ano']}.zip"
        assert path.stat().st_size == record['bytes'], path
        assert sha256(path) == record['sha256'], path
    for record in json.loads((base / 'fontes_estacao.json').read_text(encoding='utf-8')):
        assert sha256(record['arquivo']) == record['sha256']
    hourly = pd.read_csv(base / 'goiania/horario.csv', index_col='data_hora_utc')
    hourly.index = pd.to_datetime(hourly.index, utc=True)
    assert hourly.index.is_unique and hourly.index.is_monotonic_increasing
    assert set(hourly.estacao) == {'A002'}
    for period in ('dia', 'mes'):
        actual = pd.read_csv(base / f'goiania/{period}_utc.csv')
        expected = summarize(hourly, period)
        pd.testing.assert_frame_equal(actual, expected, check_dtype=False, rtol=1e-10, atol=1e-10)
        for kind in ('chuva_mm', 'temperatura_c', 'umidade_pct'):
            incomplete = ~actual[kind + '_completo']
            assert actual.loc[incomplete, kind + '_completo_valor'].isna().all()
            assert actual[kind + '_cobertura_pct'].between(0, 100).all()
    report = dict(validado_em=now(), status='aprovado', horarios=len(hourly),
                  primeira_hora=str(hourly.index.min()), ultima_hora=str(hourly.index.max()))
    save_json(base / 'validacao.json', report)
    print(report)


if __name__ == '__main__':
    main()
