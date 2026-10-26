import React from 'react';
import { DataComponent, DataTable } from '../../data-app-public.jsx';

const fmt = v => v == null ? '—' : new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 0 }).format(v);
const dataCurta = iso => new Date(`${iso}T12:00:00`).toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' });
const MARGEM = { topo: 16, direita: 12, base: 34, esquerda: 52 };

function passoEixo(maximo) {
  const bruto = maximo / 4, ordem = 10 ** Math.floor(Math.log10(bruto));
  return [1, 2, 2.5, 5, 10].map(m => m * ordem).find(p => p >= bruto);
}

function Grafico({ rows }) {
  const ref = React.useRef(null);
  const [largura, setLargura] = React.useState(900);
  const [foco, setFoco] = React.useState(null);
  React.useEffect(() => {
    const obs = new ResizeObserver(([e]) => setLargura(e.contentRect.width || 900));
    obs.observe(ref.current);
    return () => obs.disconnect();
  }, []);
  const exibir = rows.some(r => r.exibir_estimativa);
  const altura = 300;
  const maximo = Math.max(...rows.map(r => exibir ? (r.superior ?? r.observado) : r.observado));
  const passo = passoEixo(maximo), topo = Math.ceil(maximo / passo) * passo;
  const w = largura - MARGEM.esquerda - MARGEM.direita, h = altura - MARGEM.topo - MARGEM.base;
  const banda = w / rows.length, barra = Math.max(banda * 0.72, 2);
  const y = v => MARGEM.topo + h - v / topo * h;
  const x = i => MARGEM.esquerda + i * banda + (banda - barra) / 2;
  const rotulos = rows.map((r, i) => i).filter(i => i % Math.ceil(rows.length / Math.max(2, Math.floor(w / 70))) === 0);
  const r = foco == null ? null : rows[foco];

  return <div className="st-nowcast" ref={ref}>
    <svg width={largura} height={altura} role="img" aria-label="Notificações de dengue por semana de início dos sintomas nas últimas 52 semanas, com estimativa das digitações pendentes nas 12 mais recentes"
      onPointerLeave={() => setFoco(null)}>
      {Array.from({ length: topo / passo + 1 }, (_, i) => i * passo).map(v => <g key={v}>
        <line x1={MARGEM.esquerda} x2={largura - MARGEM.direita} y1={y(v)} y2={y(v)} className="st-nowcast-grade" />
        <text x={MARGEM.esquerda - 8} y={y(v)} dy="0.32em" textAnchor="end" className="st-nowcast-eixo">{fmt(v)}</text>
      </g>)}
      {rows.map((d, i) => <g key={d.semana} onPointerEnter={() => setFoco(i)} onFocus={() => setFoco(i)} tabIndex={d.estimado != null ? 0 : -1}
        aria-label={`Semana de ${dataCurta(d.semana)} (SE ${d.se_rotulo}): ${fmt(d.observado)} digitadas${exibir && d.estimado != null ? `, estimativa ${fmt(d.estimado)}, faixa ${fmt(d.inferior)} a ${fmt(d.superior)}` : ''}`}>
        <rect x={MARGEM.esquerda + i * banda} y={MARGEM.topo} width={banda} height={h} className={`st-nowcast-alvo${foco === i ? ' ativo' : ''}`} />
        <rect x={x(i)} y={y(d.observado)} width={barra} height={y(0) - y(d.observado)} className="st-nowcast-observado" />
        {exibir && d.estimado != null && <>
          <rect x={x(i)} y={y(d.estimado)} width={barra} height={y(d.observado) - y(d.estimado)} className="st-nowcast-pendente" />
          <line x1={x(i) + barra / 2} x2={x(i) + barra / 2} y1={y(d.superior)} y2={y(d.inferior)} className="st-nowcast-faixa" />
          <line x1={x(i) + barra * 0.2} x2={x(i) + barra * 0.8} y1={y(d.superior)} y2={y(d.superior)} className="st-nowcast-faixa" />
        </>}
      </g>)}
      <line x1={MARGEM.esquerda} x2={largura - MARGEM.direita} y1={y(0)} y2={y(0)} className="st-nowcast-base" />
      {rotulos.map(i => <text key={i} x={x(i) + barra / 2} y={altura - 12} textAnchor="middle" className="st-nowcast-eixo">{dataCurta(rows[i].semana)}</text>)}
    </svg>
    {r && <div className="st-mapa-tooltip st-nowcast-tooltip" style={{ left: Math.min(x(foco) + barra + 8, largura - 230), top: 12 }} role="status">
      <strong>SE {r.se_rotulo} · {dataCurta(r.semana)} a {dataCurta(r.semana_fim)}</strong>
      <span>Digitadas até o corte: {fmt(r.observado)}</span>
      {exibir && r.estimado != null && <><span>Estimativa final: {fmt(r.estimado)}</span><span>Faixa: {fmt(r.inferior)} a {fmt(r.superior)}</span></>}
      {r.suspensa && <span>Estimativa suspensa: correção de atraso fora das condições testadas</span>}
      {r.excluidas_fora_janela > 0 && <span>Mais {fmt(r.excluidas_fora_janela)} notificações fora da janela do arquivo anual, excluídas para evitar dupla contagem</span>}
    </div>}
    <div className="st-mapa-legenda">
      <span><b className="st-leg-barra" /> Notificações já digitadas</span>
      {exibir && <><span><b className="st-leg-barra pendente" /> Digitações ainda esperadas (estimativa)</span><span><b className="st-leg-faixa" /> Faixa de incerteza</span></>}
    </div>
  </div>;
}

export function NowcastDengue({ rows, avaliacao }) {
  if (!rows.length) return null;
  const exibir = rows.some(r => r.exibir_estimativa);
  const recentes = rows.filter(r => r.defasagem != null).reverse();
  const cobertura = avaliacao.filter(a => a.cobertura_faixa_pct != null).map(a => a.cobertura_faixa_pct);
  return <>
    <DataComponent id="nowcast-dengue" queryId="nowcast" title="Dengue · notificações por semana de início dos sintomas" kind="custom" variant="card"
      sourceRows={rows} displayRows={rows} data-reviewed-rows
      description={exibir ? `As semanas recentes ainda recebem digitações atrasadas. A parte clara é a estimativa do que falta chegar, calculada pelo histórico de atrasos; não é previsão de semanas futuras. No teste retrospectivo, a faixa conteve o total final em ${fmt(Math.min(...cobertura))}% a ${fmt(Math.max(...cobertura))}% das vezes, conforme a semana.` : 'A estimativa de atraso não superou o número bruto no teste retrospectivo e por isso não é exibida.'}>
      <Grafico rows={rows} />
    </DataComponent>
    {exibir && <div className="st-nowcast-tabelas">
      <DataComponent id="nowcast-semanas" queryId="nowcast" title="Semanas recentes: digitado e estimado" kind="table" variant="card" sourceRows={recentes} displayRows={recentes}>
        <DataTable rows={recentes} searchable={false} caption="Semanas recentes" columns={[
          { field: 'se_rotulo', label: 'SE' }, { field: 'semana', label: 'Início', renderCell: v => dataCurta(v) },
          { field: 'observado', label: 'Digitadas' }, { field: 'estimado', label: 'Estimativa' },
          { field: 'inferior', label: 'Faixa inferior' }, { field: 'superior', label: 'Faixa superior' }]} />
      </DataComponent>
      <DataComponent id="nowcast-avaliacao" queryId="nowcast_avaliacao" title="Avaliação retrospectiva (2023–2025)" kind="table" variant="card" sourceRows={avaliacao} displayRows={avaliacao}>
        <DataTable rows={avaliacao} searchable={false} caption="Erro por semanas desde o início" columns={[
          { field: 'defasagem', label: 'Semanas desde o início' },
          { field: 'erro_rel_mediano_bruto_pct', label: 'Erro mediano sem modelo (%)' },
          { field: 'erro_rel_mediano_estimado_pct', label: 'Erro mediano com estimativa (%)' },
          { field: 'cobertura_faixa_pct', label: 'Acerto da faixa (%)' },
          { field: 'avaliacoes', label: 'Datas de corte' }]} />
      </DataComponent>
    </div>}
  </>;
}

const pct = v => v == null ? '—' : `${new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1 }).format(v)}%`;

const NOMES = { ridge_sem_clima: 'ridge sem clima', ridge_com_clima: 'ridge com clima', gbm_com_clima: 'gradient boosting com clima' };

export function PrevisaoDengue({ rows, avaliacao, temporadas }) {
  const teste = avaliacao.filter(a => a.periodo === 'teste');
  if (!teste.length) return null;
  const escolhido = teste[0].modelo_escolhido;
  const exibir = rows.length > 0 && rows.every(r => r.exibir);
  const linhas = teste.map(a => ({ ...a, erro_modelo: a[`erro_abs_medio_${escolhido}`], erro_ref: Math.min(a.erro_abs_medio_persistencia, a.erro_abs_medio_sazonal_ingenuo),
    resultado: a.modelo_supera_referencias ? 'Modelo melhor' : 'Referência melhor' }));
  const melhores = temporadas.filter(s => s.erro_modelo < s.erro_referencia).length;
  const ressalva = temporadas.length ? ` Por temporada, o modelo errou menos que a referência em ${melhores} de ${temporadas.length} (${temporadas.map(s => `${s.ano}: ${fmt(s.erro_modelo)} × ${fmt(s.erro_referencia)}`).join('; ')}).` : '';
  return <div className="st-nowcast-tabelas st-previsao">
    {exibir && <DataComponent id="previsao-semanas" queryId="previsao" title="Previsão das próximas 8 semanas" kind="table" variant="card" sourceRows={rows} displayRows={rows}
      description={`Modelo ${NOMES[escolhido]}, escolhido em 2016–2020 e testado em 2021–2025. Útil sobretudo para perceber subidas fortes; a faixa é larga e deve ser lida junto com o valor previsto.`}>
      <DataTable rows={rows} searchable={false} caption="Previsão" columns={[
        { field: 'horizonte', label: 'Semanas à frente' }, { field: 'semana', label: 'Início', renderCell: v => dataCurta(v) },
        { field: 'previsto', label: 'Previsto' }, { field: 'inferior', label: 'Faixa inferior' }, { field: 'superior', label: 'Faixa superior' },
        { field: 'persistencia', label: 'Referência' }]} />
    </DataComponent>}
    <DataComponent id="previsao-avaliacao" queryId="previsao_avaliacao" title={exibir ? 'Previsão: teste em 2021–2025' : 'Previsão de 1 a 8 semanas: não exibida'} kind="table" variant="card"
      sourceRows={linhas} displayRows={linhas}
      description={(exibir ? 'No período de teste, nunca usado na escolha do modelo, o erro médio ficou abaixo da melhor referência simples em todos os horizontes.' : 'O modelo escolhido na validação não superou a melhor referência simples em todos os horizontes do teste, então nenhum valor previsto é mostrado.') + ressalva + ' A avaliação é refeita quando os dados mudam.'}>
      <DataTable rows={linhas} searchable={false} caption="Erro absoluto médio por horizonte no teste" columns={[
        { field: 'horizonte', label: 'Semanas à frente' },
        { field: 'erro_ref', label: 'Erro: melhor referência', renderCell: v => fmt(v) },
        { field: 'erro_modelo', label: 'Erro: modelo', renderCell: v => fmt(v) },
        { field: 'resultado', label: 'Resultado' },
        { field: 'cobertura_faixa_pct', label: 'Acerto da faixa', renderCell: v => pct(v) }]} />
    </DataComponent>
  </div>;
}
