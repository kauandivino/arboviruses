"""Registro local das ações de campo, com histórico de versões que só cresce.

Cada criação, edição ou cancelamento grava uma linha completa em registros.jsonl;
o estado atual é a última versão de cada id. Nada é apagado nem pré-preenchido.
Participantes são registrados apenas como contagem, sem dados pessoais.
"""
from datetime import date, datetime, timezone
import csv
import json
from pathlib import Path
import threading
import uuid

ROOT = Path(__file__).resolve().parents[1]
PASTA = ROOT / 'dados/acoes_campo'
MAPA = ROOT / 'dados/mapa/camadas.json'
UNIDADES = ROOT / 'dados/base_integrada/parceiros_candidatos.csv'

TIPOS = {
    'encontro_educativo': 'Encontro educativo e escuta comunitária',
    'observacao_ambiental': 'Observação ambiental',
    'distribuicao_material': 'Distribuição de material educativo',
    'articulacao_parceiro': 'Reunião de articulação com parceiro',
    'outra': 'Outra atividade',
}
SITUACOES = {'planejada': 'Planejada', 'realizada': 'Realizada', 'cancelada': 'Cancelada'}
CAMPOS = ['id', 'versao', 'situacao', 'data', 'tipo', 'OID_SIGGO', 'territorio', 'local',
          'CO_CNES', 'parceiro', 'participantes', 'materiais_descricao', 'materiais_quantidade',
          'responsavel', 'observacoes', 'motivo_alteracao', 'registrado_em']
LIMITES_TEXTO = {'local': 200, 'materiais_descricao': 300, 'responsavel': 120, 'observacoes': 1000, 'motivo_alteracao': 300}
_trava = threading.Lock()


class ErroValidacao(ValueError):
    def __init__(self, erros):
        super().__init__('; '.join(f'{k}: {v}' for k, v in erros.items()))
        self.erros = erros


def referencias():
    """Territórios (malha SIGGO) e unidades (CNES candidatas) aceitos no formulário."""
    bairros = {r['OID_SIGGO']: r['nome'] for r in json.loads(MAPA.read_text(encoding='utf-8')) if r['camada'] == 'bairro'}
    with UNIDADES.open(encoding='utf-8-sig', newline='') as f:
        unidades = {r['CO_CNES']: r['NO_FANTASIA'] for r in csv.DictReader(f)}
    return bairros, unidades


def _texto(valor, campo, erros, obrigatorio=False):
    texto = ' '.join(str(valor or '').split())
    if obrigatorio and not texto:
        erros[campo] = 'obrigatório'
    elif len(texto) > LIMITES_TEXTO[campo]:
        erros[campo] = f'máximo de {LIMITES_TEXTO[campo]} caracteres'
    return texto or None


def _inteiro(valor, campo, erros):
    if valor in (None, ''):
        return None
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        erros[campo] = 'deve ser um número inteiro'
        return None
    if numero < 0 or numero > 100000:
        erros[campo] = 'fora do intervalo aceito (0 a 100000)'
    return numero


def validar(dados, refs=None, hoje=None):
    """Normaliza os campos enviados pelo formulário ou levanta ErroValidacao."""
    bairros, unidades = refs or referencias()
    hoje = hoje or date.today()
    erros = {}
    situacao = dados.get('situacao')
    if situacao not in SITUACOES:
        erros['situacao'] = 'escolha planejada, realizada ou cancelada'
    tipo = dados.get('tipo')
    if tipo not in TIPOS:
        erros['tipo'] = 'tipo de atividade inválido'
    try:
        dia = date.fromisoformat(str(dados.get('data') or ''))
        if situacao == 'realizada' and dia > hoje:
            erros['data'] = 'uma ação realizada não pode ter data futura'
    except ValueError:
        dia = None
        erros['data'] = 'data obrigatória no formato AAAA-MM-DD'
    try:
        oid = int(dados.get('OID_SIGGO'))
    except (TypeError, ValueError):
        oid = None
    if oid not in bairros:
        erros['OID_SIGGO'] = 'escolha um território da malha municipal'
    cnes = str(dados.get('CO_CNES') or '') or None
    if cnes is not None and cnes not in unidades:
        erros['CO_CNES'] = 'unidade não encontrada entre as candidatas do CNES'
    participantes = _inteiro(dados.get('participantes'), 'participantes', erros)
    quantidade = _inteiro(dados.get('materiais_quantidade'), 'materiais_quantidade', erros)
    if situacao == 'realizada' and participantes is None and 'participantes' not in erros:
        erros['participantes'] = 'informe a contagem de participantes da ação realizada'
    if situacao != 'realizada' and (participantes is not None or quantidade is not None):
        erros['participantes'] = 'contagens só podem ser registradas em ações realizadas'
    registro = {
        'situacao': situacao, 'data': dia.isoformat() if dia else None, 'tipo': tipo,
        'OID_SIGGO': oid, 'territorio': bairros.get(oid),
        'local': _texto(dados.get('local'), 'local', erros, obrigatorio=True),
        'CO_CNES': cnes, 'parceiro': unidades.get(cnes),
        'participantes': participantes,
        'materiais_descricao': _texto(dados.get('materiais_descricao'), 'materiais_descricao', erros),
        'materiais_quantidade': quantidade,
        'responsavel': _texto(dados.get('responsavel'), 'responsavel', erros, obrigatorio=True),
        'observacoes': _texto(dados.get('observacoes'), 'observacoes', erros),
        'motivo_alteracao': _texto(dados.get('motivo_alteracao'), 'motivo_alteracao', erros),
    }
    if erros:
        raise ErroValidacao(erros)
    return registro


def historico(pasta=PASTA):
    arquivo = pasta / 'registros.jsonl'
    if not arquivo.exists():
        return []
    return [json.loads(linha) for linha in arquivo.read_text(encoding='utf-8').splitlines() if linha.strip()]


def atuais(pasta=PASTA):
    ultimo = {}
    for registro in historico(pasta):
        ultimo[registro['id']] = registro
    return sorted(ultimo.values(), key=lambda r: (r['data'], r['registrado_em']), reverse=True)


def gravar(dados, id_existente=None, pasta=PASTA, refs=None, hoje=None):
    """Valida e acrescenta uma versão; edição exige motivo. Retorna o registro gravado."""
    registro = validar(dados, refs, hoje)
    with _trava:
        estado = {r['id']: r for r in atuais(pasta)}
        if id_existente is not None:
            if id_existente not in estado:
                raise ErroValidacao({'id': 'registro inexistente'})
            if not registro['motivo_alteracao']:
                raise ErroValidacao({'motivo_alteracao': 'informe o motivo da alteração'})
            registro = {'id': id_existente, 'versao': estado[id_existente]['versao'] + 1, **registro}
        else:
            registro = {'id': uuid.uuid4().hex[:12], 'versao': 1, **registro}
        registro['registrado_em'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
        registro = {campo: registro.get(campo) for campo in CAMPOS}
        pasta.mkdir(parents=True, exist_ok=True)
        with (pasta / 'registros.jsonl').open('a', encoding='utf-8', newline='\n') as f:
            f.write(json.dumps(registro, ensure_ascii=False) + '\n')
        exportar_csv(pasta)
    return registro


def exportar_csv(pasta=PASTA):
    """Estado atual em CSV para planilhas; regenerado a cada gravação."""
    linhas = atuais(pasta)
    with (pasta / 'acoes.csv').open('w', encoding='utf-8-sig', newline='') as f:
        escritor = csv.DictWriter(f, fieldnames=CAMPOS + ['tipo_legivel', 'situacao_legivel'])
        escritor.writeheader()
        for r in linhas:
            escritor.writerow({**r, 'tipo_legivel': TIPOS[r['tipo']], 'situacao_legivel': SITUACOES[r['situacao']]})
