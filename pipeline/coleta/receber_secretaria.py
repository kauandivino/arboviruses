"""Valida os arquivos por bairro enviados pela Secretaria (formato em docs/DADOS-SECRETARIA.md).

    .venv/Scripts/python.exe -m pipeline.coleta.receber_secretaria

Lê dados/secretaria/recebidos/. Sem arquivos, só registra que está aguardando. Arquivos válidos
são copiados para dados/secretaria/validados/ com hash; com erro, nada entra no pipeline.
"""
from datetime import date, datetime, timezone
import json
from pathlib import Path
import shutil
import sys

import pandas as pd

from pipeline.comum.ibge_utils import sha256

ROOT = Path(__file__).resolve().parents[2]
PASTA = ROOT / 'dados/secretaria'
COLUNAS_CONTAGENS = ['codigo_territorio', 'nome_territorio', 'distrito_sanitario', 'ano_epidemiologico', 'semana_epidemiologica',
                     'agravo', 'indicador', 'referencia_data', 'referencia_local', 'valor', 'situacao_valor', 'data_extracao']
COLUNAS_TERRITORIOS = ['codigo_territorio', 'nome_territorio', 'apelidos', 'distrito_sanitario', 'oid_siggo', 'relacao_siggo',
                       'vigencia_inicio', 'vigencia_fim']
DOMINIOS = {
    'agravo': {'dengue', 'chikungunya', 'zika', 'escorpiao'},
    'indicador': {'notificacoes', 'casos_provaveis', 'casos_confirmados', 'internacoes', 'obitos'},
    'referencia_data': {'inicio_sintomas', 'notificacao', 'acidente'},
    'referencia_local': {'residencia', 'ocorrencia', 'notificacao'},
    'situacao_valor': {'observado', 'zero_confirmado', 'suprimido', 'ignorado'},
}
CHAVE = ['codigo_territorio', 'ano_epidemiologico', 'semana_epidemiologica', 'agravo', 'indicador', 'referencia_data', 'referencia_local']


def validar_territorios(t):
    erros = []
    if list(t.columns) != COLUNAS_TERRITORIOS:
        return [f'territorios.csv: colunas esperadas {COLUNAS_TERRITORIOS}, recebidas {list(t.columns)}']
    if t.codigo_territorio.isna().any() or t.codigo_territorio.duplicated().any():
        erros.append('territorios.csv: codigo_territorio vazio ou repetido')
    invalidas = set(t.relacao_siggo.dropna()) - {'igual', 'parte_de', 'contem', 'parcial', 'sem_correspondencia'}
    if invalidas:
        erros.append(f'territorios.csv: relacao_siggo inválida {sorted(invalidas)}')
    return erros


def validar_contagens(c, codigos, ano_max=None):
    ano_max = ano_max or date.today().year
    if list(c.columns) != COLUNAS_CONTAGENS:
        return [f'contagens_bairro_semana.csv: colunas esperadas {COLUNAS_CONTAGENS}, recebidas {list(c.columns)}']
    erros = []
    for coluna, permitidos in DOMINIOS.items():
        fora = set(c[coluna].dropna()) - permitidos
        if fora or c[coluna].isna().any():
            erros.append(f'{coluna}: valores fora do domínio ou vazios {sorted(map(str, fora))[:5]}')
    ano = pd.to_numeric(c.ano_epidemiologico, errors='coerce')
    se = pd.to_numeric(c.semana_epidemiologica, errors='coerce')
    if (~ano.between(2014, ano_max)).any():
        erros.append(f'ano_epidemiologico fora de 2014–{ano_max} em {int((~ano.between(2014, ano_max)).sum())} linhas')
    if (~se.between(1, 53)).any():
        erros.append(f'semana_epidemiologica fora de 1–53 em {int((~se.between(1, 53)).sum())} linhas')
    valor = pd.to_numeric(c.valor, errors='coerce')
    texto_vazio = c.valor.isna() | (c.valor.astype(str).str.strip() == '')
    observado = c.situacao_valor == 'observado'
    if (observado & (valor.isna() | (valor < 0) | (valor % 1 != 0))).any():
        erros.append('valor: observado precisa ser inteiro ≥ 0')
    if ((c.situacao_valor == 'zero_confirmado') & (valor != 0)).any():
        erros.append('valor: zero_confirmado precisa ter valor 0')
    if (c.situacao_valor.isin(['suprimido', 'ignorado']) & ~texto_vazio).any():
        erros.append('valor: suprimido/ignorado precisa ter valor vazio (não converter ausência em número)')
    repetidas = c.duplicated(CHAVE).sum()
    if repetidas:
        erros.append(f'{repetidas} linhas repetidas para a mesma combinação {CHAVE}')
    desconhecidos = set(c.codigo_territorio.astype(str)) - set(map(str, codigos))
    if desconhecidos:
        erros.append(f'codigo_territorio ausente do cadastro: {sorted(desconhecidos)[:10]}')
    if pd.to_datetime(c.data_extracao, errors='coerce').isna().any():
        erros.append('data_extracao inválida (AAAA-MM-DD)')
    return erros


def main():
    recebidos = PASTA / 'recebidos'
    contagens, territorios = recebidos / 'contagens_bairro_semana.csv', recebidos / 'territorios.csv'
    relatorio = {'verificado_em': datetime.now(timezone.utc).isoformat(timespec='seconds')}
    if not contagens.exists() and not territorios.exists():
        relatorio['status'] = 'aguardando_envio'
        print('Nenhum arquivo da Secretaria recebido; aguardando envio (veja docs/DADOS-SECRETARIA.md).')
    else:
        erros = []
        if not contagens.exists() or not territorios.exists():
            erros.append('São necessários os dois arquivos: contagens_bairro_semana.csv e territorios.csv')
        else:
            t = pd.read_csv(territorios, dtype=str, encoding='utf-8')
            c = pd.read_csv(contagens, dtype=str, encoding='utf-8', keep_default_na=False, na_values=[])
            c = c.replace({'': None})
            erros = validar_territorios(t) + validar_contagens(c, t.codigo_territorio)
        relatorio.update({'status': 'aprovado' if not erros else 'reprovado', 'erros': erros,
                          'arquivos': [{'arquivo': p.relative_to(ROOT).as_posix(), 'sha256': sha256(p)} for p in (contagens, territorios) if p.exists()]})
        if not erros:
            destino = PASTA / 'validados'
            destino.mkdir(parents=True, exist_ok=True)
            for p in (contagens, territorios):
                shutil.copy2(p, destino / p.name)
        print(json.dumps(relatorio, ensure_ascii=False, indent=2))
    PASTA.mkdir(parents=True, exist_ok=True)
    (PASTA / 'validacao.json').write_text(json.dumps(relatorio, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return 1 if relatorio['status'] == 'reprovado' else 0


if __name__ == '__main__':
    sys.exit(main())
