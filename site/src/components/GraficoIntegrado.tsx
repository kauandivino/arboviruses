import { useMemo, useState } from 'react';
import { scaleLinear } from 'd3-scale';
import { area, curveMonotoneX, line } from 'd3-shape';
import { max } from 'd3-array';
import type { DadosSite } from '../lib/dados';
import { MESES_ABREV, mesDaSemana, numero, useLargura } from '../lib/formato';

type P = { se: number; v: number };
const recentesCentro = (n: DadosSite['nowcast']) => n.map(r => r.estimado).filter((v): v is number => v != null);

/** Dengue do ano (com faixa habitual, estimativa das semanas recentes e projeção) e chuva da semana, no mesmo eixo de tempo. */
export function GraficoIntegrado({ dados }: { dados: DadosSite }) {
  const [ref, largura] = useLargura<HTMLDivElement>();
  const [foco, setFoco] = useState<number | null>(null);
  const ano = dados.dengue.ano;
  const compacto = largura < 600;
  const hDengue = compacto ? 230 : 300, hChuva = 70, vao = 18, base = 26;
  const m = { esquerda: compacto ? 38 : 50, direita: 12, topo: 18 };
  const altura = m.topo + hDengue + vao + hChuva + base;
  const faixa = dados.dengue.faixa_habitual;
  const nowcast = new Map(dados.nowcast.map(n => [n.se, n]));
  const atual: P[] = (dados.dengue.temporadas[String(ano)] ?? []).filter(p => p.valor != null).map(p => ({ se: p.se, v: p.valor as number }));
  const projecao = dados.dengue.projecao.filter(p => p.ano === ano);
  const chuva = dados.semanal.filter(s => s.ano === ano);
  const x = scaleLinear().domain([1, 53]).range([m.esquerda, largura - m.direita]);
  const topoV = max([...faixa.map(f => f.q3), ...atual.map(p => p.v), ...projecao.map(p => p.previsto), ...dados.nowcast.map(n => n.estimado ?? 0)]) ?? 100;
  const y = scaleLinear().domain([0, topoV * 1.12]).nice().range([m.topo + hDengue, m.topo]);
  const yc = scaleLinear().domain([0, Math.max(40, max(chuva, c => c.chuva_mm ?? 0) ?? 40)]).range([m.topo + hDengue + vao + hChuva, m.topo + hDengue + vao]);
  const ult = atual.at(-1);
  const recentes = dados.nowcast.filter(n => n.estimado != null && n.inferior != null && n.superior != null);
  // A faixa de incerteza esmaece para cima e é cortada no dobro do valor central; a dica mostra a faixa completa.
  const tetoFaixa = 2 * (max([...projecao.map(p => p.previsto), ...recentesCentro(dados.nowcast)]) ?? topoV);
  const proj = ult ? [{ se: ult.se, v: ult.v, lo: ult.v, hi: ult.v }, ...projecao.map(p => ({ se: p.se, v: p.previsto, lo: p.inferior, hi: Math.min(p.superior, tetoFaixa) }))] : [];
  const meses = useMemo(() => Array.from({ length: 50 }, (_, i) => i + 1).filter((se, i, a) => i === 0 || mesDaSemana(ano, se) !== mesDaSemana(ano, a[i - 1])), [ano]);
  const barra = Math.max(2, (x(2) - x(1)) * 0.7);
  const f = foco == null ? null : { se: foco, d: atual.find(p => p.se === foco), n: nowcast.get(foco), p: projecao.find(p => p.se === foco), h: faixa.find(p => p.se === foco), c: chuva.find(c => c.se === foco) };
  return (
    <div className="cartao grafico-cartao integrado">
      <div className="grafico-topo">
        <h3 className="titulo-cartao">Dengue e chuva em {ano}</h3>
        <div className="legenda">
          <span><i className="leg-linha atual" /> Casos por semana</span>
          <span><i className="leg-faixa" /> Habitual para a época</span>
          <span><i className="leg-linha projecao" /> Projeção</span>
          <span><i className="leg-quadrado chuva" /> Chuva (mm)</span>
        </div>
      </div>
      <div ref={ref} className="grafico-area">
        <svg width={largura} height={altura} role="img" aria-label={`Casos de dengue por semana em ${ano} com a faixa habitual, a projeção e a chuva semanal`}
          onPointerMove={e => { const r = e.currentTarget.getBoundingClientRect(); const se = Math.round(x.invert(e.clientX - r.left)); setFoco(se >= 1 && se <= 53 ? se : null); }}
          onPointerLeave={() => setFoco(null)}>
          <defs>
            <linearGradient id="g-proj-int" x1="0" y1="1" x2="0" y2="0">
              <stop offset="0" stopColor="var(--acento)" stopOpacity="0.2" /><stop offset="0.45" stopColor="var(--acento)" stopOpacity="0.06" /><stop offset="1" stopColor="var(--acento)" stopOpacity="0" />
            </linearGradient>
          </defs>
          {y.ticks(4).map(t => <g key={t}><line x1={m.esquerda} x2={largura - m.direita} y1={y(t)} y2={y(t)} className="grade" />
            <text x={m.esquerda - 8} y={y(t)} dy="0.32em" textAnchor="end" className="eixo">{numero(t)}</text></g>)}
          <path d={area<typeof faixa[number]>().x(d => x(d.se)).y0(d => y(d.q1)).y1(d => y(d.q3)).curve(curveMonotoneX)(faixa) ?? ''} className="faixa-habitual" />
          {recentes.length > 0 && <path d={area<typeof recentes[number]>().x(d => x(d.se)).y0(d => y(d.inferior!)).y1(d => y(Math.min(d.superior!, tetoFaixa))).curve(curveMonotoneX)(recentes) ?? ''} fill="url(#g-proj-int)" />}
          {proj.length > 1 && <path d={area<typeof proj[number]>().x(d => x(d.se)).y0(d => y(d.lo)).y1(d => y(d.hi)).curve(curveMonotoneX)(proj) ?? ''} fill="url(#g-proj-int)" />}
          <path d={line<P>().x(d => x(d.se)).y(d => y(d.v)).curve(curveMonotoneX)(atual) ?? ''} className="linha-atual" />
          {proj.length > 1 && <path d={line<typeof proj[number]>().x(d => x(d.se)).y(d => y(d.v)).curve(curveMonotoneX)(proj) ?? ''} className="linha-projecao" />}
          {ult && <g transform={`translate(${x(ult.se)},${y(ult.v)})`}><circle r="9" className="hoje-halo" /><circle r="4.5" className="hoje" /><text y={-15} textAnchor="middle" className="hoje-rotulo">Agora</text></g>}
          <text x={m.esquerda} y={m.topo + hDengue + vao - 4} className="rotulo-grafico chuva">Chuva</text>
          {chuva.map(c => c.chuva_mm != null && <rect key={c.se} x={x(c.se) - barra / 2} width={barra} y={yc(c.chuva_mm)} height={yc(0) - yc(c.chuva_mm)} rx={1.5} className="barra-chuva" />)}
          <line x1={m.esquerda} x2={largura - m.direita} y1={yc(0)} y2={yc(0)} className="base" />
          {meses.filter((_, i) => !compacto || i % 2 === 0).map(se => <text key={se} x={x(se + 1.5)} y={altura - 8} textAnchor="middle" className="eixo">{MESES_ABREV[mesDaSemana(ano, se)]}</text>)}
          {f && <line x1={x(f.se)} x2={x(f.se)} y1={m.topo} y2={yc(0)} className="guia" />}
        </svg>
        {f && (f.d || f.p) && (
          <div className="dica" style={{ left: Math.min(x(f.se) + 12, largura - 230) }} role="status">
            <strong>Semana {f.se} · {MESES_ABREV[mesDaSemana(ano, f.se)]}</strong>
            {f.d && <span>Casos: <b>{numero(f.d.v)}</b>{f.n?.estimado != null && <small> (estimado entre {numero(f.n.inferior)} e {numero(f.n.superior)}; registrados até agora: {numero(f.n.observado)})</small>}</span>}
            {f.p && <span>Projeção: <b>{numero(f.p.previsto)}</b> <small>({numero(f.p.inferior)} a {numero(f.p.superior)})</small></span>}
            {f.h && <span>Habitual: {numero(f.h.q1)} a {numero(f.h.q3)}</span>}
            {f.c?.chuva_mm != null && <span>Chuva: {numero(f.c.chuva_mm)} mm</span>}
          </div>
        )}
      </div>
    </div>
  );
}
