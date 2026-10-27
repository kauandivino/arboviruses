"""Versões de referência das fontes que definem a seleção dos territórios (dados/referencias.json)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_REF = json.loads((ROOT / 'dados/referencias.json').read_text(encoding='utf-8'))

CNES_COMPETENCIA = _REF['cnes_competencia']
SIGGO_COLETA = _REF['siggo_coleta']
CNES_ESTABELECIMENTOS = f'dados/cnes/goiania/{CNES_COMPETENCIA}/estabelecimentos.csv'
