"""Calendário epidemiológico (semanas de domingo a sábado) e janelas dos arquivos anuais do SINAN."""
import pandas as pd

GOIANIA = '520870'
AGRAVOS = {
    # Arquivos de dengue seguem o ano epidemiológico da notificação; os de animais peçonhentos, o ano civil.
    'dengue': {'arquivo': 'dados/datasus/goiania/dengue_{ano}.csv', 'municipio': 'ID_MN_RESI', 'referencia': 'residencia', 'data': 'DT_NOTIFIC'},
    'escorpioes': {'arquivo': 'dados/datasus/goiania/escorpioes_{ano}.csv', 'municipio': 'ANT_MUNIC_', 'referencia': 'ocorrencia', 'data': 'ANT_DT_ACI'},
}


def inicio_semana(datas):
    """Domingo que inicia a semana epidemiológica de cada data."""
    datas = pd.to_datetime(datas)
    return datas - pd.to_timedelta((datas.dt.weekday + 1) % 7, unit='D')


def inicio_ano_epidemiologico(ano):
    """SE 1 é a primeira semana (domingo a sábado) com ao menos quatro dias no ano."""
    primeiro = pd.Timestamp(f'{ano}-01-01')
    domingo = primeiro - pd.Timedelta(days=(primeiro.weekday() + 1) % 7)
    return domingo if (primeiro - domingo).days <= 3 else domingo + pd.Timedelta(days=7)


def janela_arquivo(ano):
    """Datas de notificação que um arquivo anual pode conter: ano civil e ano epidemiológico."""
    inicio = min(pd.Timestamp(f'{ano}-01-01'), inicio_ano_epidemiologico(ano))
    fim = max(pd.Timestamp(f'{ano}-12-31'), inicio_ano_epidemiologico(ano + 1) - pd.Timedelta(days=1))
    return inicio, fim


def ano_corrente():
    return pd.Timestamp.now().year


def anos_ate_corrente(inicio):
    """Anos de `inicio` até o corrente. O corrente pode ainda não ter sido publicado pela fonte."""
    return list(range(inicio, ano_corrente() + 1))


def anos_com_arquivo(inicio, caminho):
    """Anos cujo arquivo existe; só o ano corrente pode faltar, qualquer outra ausência é erro."""
    anos = [a for a in anos_ate_corrente(inicio) if caminho(a).exists()]
    faltando = [a for a in anos_ate_corrente(inicio) if a not in anos and a != ano_corrente()]
    if faltando:
        raise FileNotFoundError(f'Arquivos anuais ausentes: {faltando}')
    return anos
