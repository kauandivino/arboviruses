import React from 'react';
import { DataComponent, DataTable } from '../../data-app-public.jsx';

const fmt = v => v == null ? '—' : new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 0 }).format(v);
const dataCurta = iso => new Date(`${iso}T12:00:00`).toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' });
const ZONAS = { sucesso: 'Abaixo do 1º quartil', seguranca: 'Entre 1º quartil e mediana', alerta: 'Entre mediana e 3º quartil', epidemica: 'Acima do 3º quartil (epidêmica)' };
const INDETERMINADA = 'Indeterminada na época: correção de atraso fora das condições testadas';
const M = { topo: 14, direita: 12, base: 30, esquerda: 52 };

function Diagrama({ rows }) {
  const ref = React.useRef(null);
  const [largura, setLargura] = React.useState(900);
  const [foco, setFoco] = React.useState(null);
  React.useEffect(() => {
    const obs = new ResizeObserver(([e]) => setLargura(e.contentRect.width || 900));
    obs.observe(ref.current);
    return () => obs.disconnect();
  }, []);
  const altura = 300, w = largura - M.esquerda - M.direita, h = altura - M.topo - M.base;
  const visto = r => r.zona_tempo_real === 'indeterminada' ? null : r.tempo_real;
  const maximo = Math.max(...rows.map(r => Math.max(r.q3, r.final, visto(r) ?? 0))) * 1.08;
  const ordem = 10 ** Math.floor(Math.log10(maximo / 4));
  const passo = [1, 2, 2.5, 5, 10].map(m => m * ordem).find(p => p >= maximo / 4);
  const topo = Math.ceil(maximo / passo) * passo;
  const x = se => M.esquerda + (se - 1) / 52 * w;
  const y = v => M.topo + h - v / topo * h;
  const area = (inferior, superior) => rows.map((r, i) => `${i ? 'L' : 'M'}${x(r.se)},${y(superior(r))}`).join('') +
    [...rows].reverse().map(r => `L${x(r.se)},${y(inferior(r))}`).join('') + 'Z';
  // Semanas sem valor válido interrompem a linha em vez de ligar os pontos vizinhos.
  const linha = valor => rows.map((r, i) => valor(r) == null ? '' : `${i && valor(rows[i - 1]) != null ? 'L' : 'M'}${x(r.se)},${y(valor(r))}`).join('');
  const r = foco == null ? null : rows[foco];

  return <div className="st-nowcast" ref={ref}>
    <svg width={largura} height={altura} role="img" aria-label="Diagrama de controle da dengue no ano epidemiológico atual, com zonas definidas pelos cinco anos anteriores"
      onPointerMove={e => { const bx = e.currentTarget.getBoundingClientRect().left; const se = Math.round((e.clientX - bx - M.esquerda) / w * 52) + 1; const i = rows.findIndex(d => d.se === se); setFoco(i >= 0 ? i : null); }}
      onPointerLeave={() => setFoco(null)}>
      <path d={area(() => 0, d => d.q1)} className="st-zona sucesso" />
      <path d={area(d => d.q1, d => d.mediana)} className="st-zona seguranca" />
      <path d={area(d => d.mediana, d => d.q3)} className="st-zona alerta" />
      <path d={area(d => d.q3, () => topo)} className="st-zona epidemica" />
      {Array.from({ length: topo / passo + 1 }, (_, i) => i * passo).map(v => <g key={v}>
        <line x1={M.esquerda} x2={largura - M.direita} y1={y(v)} y2={y(v)} className="st-nowcast-grade" />
        <text x={M.esquerda - 8} y={y(v)} dy="0.32em" textAnchor="end" className="st-nowcast-eixo">{fmt(v)}</text>
      </g>)}
      {[1, 10, 20, 30, 40, 52].map(se => <text key={se} x={x(se)} y={altura - 10} textAnchor="middle" className="st-nowcast-eixo">SE {se}</text>)}
      <path d={linha(visto)} className="st-diagrama-linha tempo-real" />
      <path d={linha(r => r.final)} className="st-diagrama-linha" />
      {rows.filter(d => d.alerta).map(d => <circle key={d.se} cx={x(d.se)} cy={y(d.tempo_real)} r={4.5} className="st-diagrama-alerta" />)}
      {r && <line x1={x(r.se)} x2={x(r.se)} y1={M.topo} y2={M.topo + h} className="st-diagrama-cursor" />}
    </svg>
    {r && <div className="st-mapa-tooltip st-nowcast-tooltip" style={{ left: Math.min(x(r.se) + 10, largura - 240), top: 12 }} role="status">
      <strong>SE {r.se}/{r.ano} · {dataCurta(r.semana)}</strong>
      <span>Notificações (dados atuais): {fmt(r.final)}</span>
      <span>{r.zona_tempo_real === 'indeterminada' ? INDETERMINADA : `Visto em tempo real: ${fmt(r.tempo_real)}`}</span>
      <span>Mediana: {fmt(r.mediana)} · 3º quartil: {fmt(r.q3)}</span>
      <span>{ZONAS[r.zona_final]}{r.alerta ? ' · alerta disparado' : ''}</span>
    </div>}
    <div className="st-mapa-legenda">
      {Object.entries(ZONAS).map(([k, v]) => <span key={k}><b className={`st-leg-zona ${k}`} /> {v}</span>)}
      <span><b className="st-leg-linha" /> Notificações (dados atuais)</span>
      <span><b className="st-leg-linha tempo-real" /> Como era visto em cada semana</span>
      <span><b className="st-leg-alerta" /> Alerta (2 semanas seguidas na zona epidêmica, como vistas na época)</span>
    </div>
  </div>;
}

export function DiagramaControle({ rows, avaliacao }) {
  if (!rows.length) return null;
  const anoAtual = Math.max(...rows.map(r => r.ano));
  const atual = rows.filter(r => r.ano === anoAtual);
  const ultima = atual.at(-1);
  const passadas = avaliacao.filter(a => a.temporada_completa).map(a => ({ ...a, antecedencia: a.semanas_antes_do_pico == null ? 'Sem alerta' : a.semanas_antes_do_pico >= 0 ? `${a.semanas_antes_do_pico} semanas antes` : `${-a.semanas_antes_do_pico} semanas depois` }));
  return <>
    <DataComponent id="diagrama-controle" queryId="alerta" title={`Diagrama de controle da dengue · ${anoAtual}`} kind="custom" variant="card" sourceRows={atual} displayRows={atual} data-reviewed-rows
      description={`Zonas pelos quartis das mesmas semanas (±1) nos cinco anos anteriores. Situação na SE ${ultima.se}: ${ZONAS[ultima.zona_tempo_real].toLowerCase()}${ultima.alerta ? ', com alerta ativo' : ''}. Contagens de notificações, não incidência.`}>
      <Diagrama rows={atual} />
    </DataComponent>
    <div className="st-nowcast-tabelas st-previsao">
      <DataComponent id="alerta-avaliacao" queryId="alerta_avaliacao" title="Como o alerta teria funcionado nas temporadas passadas" kind="table" variant="card" sourceRows={passadas} displayRows={passadas}
        description="Simulação semana a semana com os dados disponíveis em cada data. Alertas confirmados: fração das semanas em alerta que estavam de fato na zona epidêmica com os dados finais. Semanas indeterminadas: a correção de atraso daquele momento passou do maior fator visto na avaliação do nowcasting (por exemplo, na pausa de digitação da virada do ano ou na digitação lenta de 2019), e a semana não conta para o alerta.">
        <DataTable rows={passadas} searchable={false} caption="Avaliação do alerta por temporada" columns={[
          { field: 'ano', label: 'Temporada' }, { field: 'notificacoes', label: 'Notificações' },
          { field: 'pico_se', label: 'SE do pico' }, { field: 'antecedencia', label: 'Primeiro alerta' },
          { field: 'semanas_em_alerta', label: 'Semanas em alerta' }, { field: 'alertas_confirmados_pct', label: 'Alertas confirmados (%)' },
          { field: 'semanas_indeterminadas', label: 'Semanas indeterminadas' }]} />
      </DataComponent>
    </div>
  </>;
}
