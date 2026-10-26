import React from 'react';
import { DataComponent, DataTable, MetricCard, Section } from '../../data-app-public.jsx';

// Registros vêm da API local (pipeline.servidor); sem ela, o painel mostra o snapshot da última compilação, só para leitura.
const fmt = v => new Intl.NumberFormat('pt-BR').format(v);
const VAZIO = { situacao: 'realizada', data: '', tipo: 'encontro_educativo', OID_SIGGO: '', local: '', CO_CNES: '', participantes: '',
  materiais_descricao: '', materiais_quantidade: '', responsavel: '', observacoes: '', motivo_alteracao: '' };

function Campo({ id, rotulo, erro, children, largo }) {
  return <label className={`st-campo${largo ? ' largo' : ''}`} htmlFor={id}>
    <span>{rotulo}</span>{children}{erro && <em role="alert">{erro}</em>}
  </label>;
}

function Formulario({ bairros, unidades, tipos, situacoes, editando, onSalvo, onCancelar }) {
  const [valores, setValores] = React.useState(VAZIO);
  const [erros, setErros] = React.useState({});
  const [enviando, setEnviando] = React.useState(false);
  const [mensagem, setMensagem] = React.useState(null);
  React.useEffect(() => {
    // Ao sair da edição após gravar, a confirmação continua visível.
    setErros({}); if (editando) setMensagem(null);
    setValores(editando ? Object.fromEntries(Object.keys(VAZIO).map(k => [k, k === 'motivo_alteracao' ? '' : editando[k] ?? ''])) : VAZIO);
  }, [editando]);
  const mudar = campo => e => setValores(v => ({ ...v, [campo]: e.target.value }));
  const realizada = valores.situacao === 'realizada';
  const selecionados = bairros.filter(b => b.ordem_articulacao != null).sort((a, b) => a.ordem_articulacao - b.ordem_articulacao);
  const parceiros = unidades.filter(u => u.situacao === 'parceiro_selecionado');

  async function enviar(e) {
    e.preventDefault();
    setEnviando(true); setMensagem(null);
    const corpo = { ...valores, OID_SIGGO: valores.OID_SIGGO === '' ? null : Number(valores.OID_SIGGO), CO_CNES: valores.CO_CNES || null,
      participantes: realizada ? valores.participantes : null, materiais_quantidade: realizada ? valores.materiais_quantidade : null };
    try {
      const r = await fetch(editando ? `/api/acoes/${editando.id}` : '/api/acoes', {
        method: editando ? 'PUT' : 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(corpo) });
      const resposta = await r.json();
      if (r.ok) { setErros({}); setValores(VAZIO); setMensagem(editando ? 'Alteração gravada.' : 'Ação registrada.'); onSalvo(resposta.registro); }
      else { setErros(resposta.campos ?? {}); setMensagem(resposta.campos ? 'Corrija os campos indicados.' : resposta.erro); }
    } catch {
      setMensagem('Não foi possível gravar: o servidor local não respondeu.');
    } finally { setEnviando(false); }
  }

  return <form className="st-form" onSubmit={enviar} noValidate>
    <div className="st-form-titulo"><strong>{editando ? `Editar registro ${editando.id} (versão ${editando.versao})` : 'Registrar ação'}</strong>
      {editando && <button type="button" className="st-botao secundario" onClick={onCancelar}>Cancelar edição</button>}</div>
    <div className="st-form-grade">
      <Campo id="f-situacao" rotulo="Situação" erro={erros.situacao}>
        <select id="f-situacao" value={valores.situacao} onChange={mudar('situacao')}>{Object.entries(situacoes).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></Campo>
      <Campo id="f-data" rotulo="Data" erro={erros.data}><input id="f-data" type="date" value={valores.data} onChange={mudar('data')} required /></Campo>
      <Campo id="f-tipo" rotulo="Atividade" erro={erros.tipo}>
        <select id="f-tipo" value={valores.tipo} onChange={mudar('tipo')}>{Object.entries(tipos).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></Campo>
      <Campo id="f-territorio" rotulo="Território" erro={erros.OID_SIGGO}>
        <select id="f-territorio" value={valores.OID_SIGGO} onChange={mudar('OID_SIGGO')} required>
          <option value="">Selecione</option>
          <optgroup label="Oito territórios selecionados">{selecionados.map(b => <option key={b.OID_SIGGO} value={b.OID_SIGGO}>{b.ordem_articulacao}. {b.nome}</option>)}</optgroup>
          <optgroup label="Outros bairros da malha SIGGO">{bairros.filter(b => b.ordem_articulacao == null).map(b => <option key={b.OID_SIGGO} value={b.OID_SIGGO}>{b.nome}</option>)}</optgroup>
        </select></Campo>
      <Campo id="f-local" rotulo="Local (espaço onde ocorreu)" erro={erros.local}><input id="f-local" value={valores.local} onChange={mudar('local')} maxLength={200} required /></Campo>
      <Campo id="f-parceiro" rotulo="Unidade parceira (opcional)" erro={erros.CO_CNES}>
        <select id="f-parceiro" value={valores.CO_CNES} onChange={mudar('CO_CNES')}>
          <option value="">Sem unidade parceira</option>
          <optgroup label="Parceiros candidatos dos oito territórios">{parceiros.map(u => <option key={u.CO_CNES} value={u.CO_CNES}>{u.nome}</option>)}</optgroup>
          <optgroup label="Outras unidades candidatas (CNES)">{unidades.filter(u => u.situacao !== 'parceiro_selecionado').map(u => <option key={u.CO_CNES} value={u.CO_CNES}>{u.nome}</option>)}</optgroup>
        </select></Campo>
      <Campo id="f-participantes" rotulo="Participantes (contagem)" erro={erros.participantes}>
        <input id="f-participantes" type="number" min="0" step="1" inputMode="numeric" value={realizada ? valores.participantes : ''} onChange={mudar('participantes')} disabled={!realizada} placeholder={realizada ? '' : 'Só em ações realizadas'} /></Campo>
      <Campo id="f-qtd" rotulo="Materiais distribuídos (quantidade)" erro={erros.materiais_quantidade}>
        <input id="f-qtd" type="number" min="0" step="1" inputMode="numeric" value={realizada ? valores.materiais_quantidade : ''} onChange={mudar('materiais_quantidade')} disabled={!realizada} placeholder={realizada ? 'Deixe vazio se não houve contagem' : 'Só em ações realizadas'} /></Campo>
      <Campo id="f-materiais" rotulo="Materiais utilizados" erro={erros.materiais_descricao}><input id="f-materiais" value={valores.materiais_descricao} onChange={mudar('materiais_descricao')} maxLength={300} /></Campo>
      <Campo id="f-responsavel" rotulo="Responsável da equipe" erro={erros.responsavel}><input id="f-responsavel" value={valores.responsavel} onChange={mudar('responsavel')} maxLength={120} required /></Campo>
      <Campo id="f-obs" rotulo="Observações" erro={erros.observacoes} largo><textarea id="f-obs" rows={3} value={valores.observacoes} onChange={mudar('observacoes')} maxLength={1000} /></Campo>
      {editando && <Campo id="f-motivo" rotulo="Motivo da alteração" erro={erros.motivo_alteracao} largo><input id="f-motivo" value={valores.motivo_alteracao} onChange={mudar('motivo_alteracao')} maxLength={300} required /></Campo>}
    </div>
    <p className="st-form-ajuda">Não registre nomes de participantes: apenas a contagem. Campos vazios ficam sem valor; não são convertidos em zero.</p>
    <div className="st-form-acoes">
      <button type="submit" className="st-botao" disabled={enviando}>{enviando ? 'Gravando…' : editando ? 'Gravar alteração' : 'Registrar ação'}</button>
      {mensagem && <span role="status">{mensagem}</span>}
    </div>
  </form>;
}

export function AcoesCampo({ snapshotRows, bairros, unidades }) {
  const [estado, setEstado] = React.useState({ conexao: 'carregando', registros: snapshotRows, tipos: {}, situacoes: {} });
  const [editando, setEditando] = React.useState(null);
  const carregar = React.useCallback(async () => {
    try {
      const r = await fetch('/api/acoes', { cache: 'no-store' });
      if (!r.ok) throw new Error(String(r.status));
      const dados = await r.json();
      setEstado({ conexao: 'local', registros: dados.registros, tipos: dados.tipos, situacoes: dados.situacoes });
    } catch {
      setEstado(e => ({ ...e, conexao: 'somente_leitura', registros: snapshotRows }));
    }
  }, [snapshotRows]);
  React.useEffect(() => { carregar(); }, [carregar]);

  const registros = estado.registros;
  const realizadas = registros.filter(r => r.situacao === 'realizada');
  const comMateriais = realizadas.filter(r => r.materiais_quantidade != null);
  const linhas = registros.map(r => ({ ...r, tipo_legivel: estado.tipos[r.tipo] ?? r.tipo, situacao_legivel: estado.situacoes[r.situacao] ?? r.situacao }));
  const metricas = [
    ['acoes-realizadas', 'Ações realizadas', fmt(realizadas.length), `${registros.filter(r => r.situacao === 'planejada').length} planejadas e ${registros.filter(r => r.situacao === 'cancelada').length} canceladas registradas.`],
    ['pessoas-alcancadas', 'Participantes', fmt(realizadas.reduce((s, r) => s + r.participantes, 0)), 'Soma das contagens das ações realizadas. A mesma pessoa pode participar de mais de uma ação.'],
    ['territorios-com-acao', 'Territórios com ação realizada', fmt(new Set(realizadas.map(r => r.OID_SIGGO)).size), 'Bairros da malha SIGGO com ao menos uma ação realizada.'],
    ['materiais-distribuidos', 'Materiais distribuídos', comMateriais.length ? fmt(comMateriais.reduce((s, r) => s + r.materiais_quantidade, 0)) : 'Sem contagem', `Soma das ${comMateriais.length} ações realizadas que informaram quantidade.`],
  ];

  return <>
    {estado.conexao === 'somente_leitura' && <p className="st-note st-alerta" role="status">Servidor local indisponível: exibindo os registros da última compilação, sem edição. Para registrar ações, abra o painel com <code>.\abrir_painel.ps1</code>.</p>}
    <Section id="acoes:indicadores" title="Indicadores de execução" columns={4} spacing="none">
      {metricas.map(([id, titulo, valor, descricao]) => <MetricCard key={id} id={id} queryId="acoes" title={titulo} value={estado.conexao === 'carregando' ? '…' : valor} description={descricao} sourceRows={linhas} displayRows={linhas} />)}
    </Section>
    {estado.conexao === 'local' && <Section id="acoes:formulario" title={editando ? 'Editar registro' : 'Novo registro'}>
      <Formulario bairros={bairros} unidades={unidades} tipos={estado.tipos} situacoes={estado.situacoes} editando={editando}
        onSalvo={() => { setEditando(null); carregar(); }} onCancelar={() => setEditando(null)} />
    </Section>}
    <Section id="acoes:registros" title="Registros">
      <DataComponent id="acoes-registros" queryId="acoes" title="Ações registradas" kind="table" variant="card" sourceRows={linhas} displayRows={linhas}>
        {linhas.length ? <DataTable rows={linhas} caption="Ações registradas" columns={[
          { field: 'data', label: 'Data' }, { field: 'situacao_legivel', label: 'Situação' }, { field: 'tipo_legivel', label: 'Atividade' },
          { field: 'territorio', label: 'Território' }, { field: 'local', label: 'Local' }, { field: 'parceiro', label: 'Unidade parceira' },
          { field: 'participantes', label: 'Participantes' }, { field: 'materiais_quantidade', label: 'Materiais' }, { field: 'responsavel', label: 'Responsável' },
          { field: 'versao', label: 'Versão' },
          ...(estado.conexao === 'local' ? [{ field: 'id', label: 'Registro', renderCell: (_, row) => <button type="button" className="st-botao secundario" aria-label={`Editar registro ${row.id}`} onClick={() => { setEditando(row); window.scrollTo({ top: 0, behavior: 'smooth' }); }}>Editar</button> }] : []),
        ]} /> : <p className="st-empty" role="status">Nenhuma ação registrada até agora. Os indicadores serão calculados a partir dos registros reais.</p>}
      </DataComponent>
    </Section>
    <p className="st-note">Histórico completo, com todas as versões, em <code>dados/acoes_campo/registros.jsonl</code>; estado atual em <code>dados/acoes_campo/acoes.csv</code>. Estes indicadores medem execução e alcance; não permitem atribuir às ações variações nos casos de dengue ou acidentes com escorpiões.</p>
  </>;
}
