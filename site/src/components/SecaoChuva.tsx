import { useState } from 'react';
import { scaleBand, scaleLinear } from 'd3-scale';
import { area, curveMonotoneX, line } from 'd3-shape';
import { max } from 'd3-array';
import { motion } from 'motion/react';
import type { DadosSite } from '../lib/dados';
import { decimal, mesCurto, mesLongo, numero, useLargura } from '../lib/formato';

/** Chuva mensal e casos de dengue por mês nos últimos dois anos. */
export function ChuvaMensal({ dados }: { dados: DadosSite }) {
  const [ref, largura] = useLargura<HTMLDivElement>();
  const [foco, setFoco] = useState<string | null>(null);
  const dengue = new Map(dados.dengue.mensal.map(d => [d.mes, d.notificacoes]));
  // Últimos 24 meses com dados de chuva e de dengue.
  const meses = dados.clima.filter(c => dengue.has(c.mes)).slice(-24);
  const m = { esquerda: 8, direita: 8 }, hChuva = 150, hDengue = 150, vao = 36;
  const x = scaleBand<string>().domain(meses.map(c => c.mes)).range([m.esquerda, largura - m.direita]).padding(0.22);
  const yc = scaleLinear().domain([0, (max(meses, c => c.chuva_mm ?? 0) ?? 1) * 1.1]).range([hChuva, 16]);
  const yd = scaleLinear().domain([0, (max(meses, c => dengue.get(c.mes) ?? 0) ?? 1) * 1.1]).range([hChuva + vao + hDengue, hChuva + vao + 16]);
  const cx = (mes: string) => x(mes)! + x.bandwidth() / 2;
  const pontos = meses.map(c => ({ mes: c.mes, v: dengue.get(c.mes) ?? 0 }));
  const altura = hChuva + vao + hDengue + 28;
  const f = foco ? meses.find(c => c.mes === foco) : null;
  return (
        <div className="cartao grafico-cartao">
          <div className="grafico-topo"><h3 className="titulo-cartao">Chuva e dengue mês a mês</h3></div>
          <div ref={ref} className="grafico-area">
            <svg width={largura} height={altura} role="img" aria-label="Chuva mensal e casos de dengue por mês nos últimos dois anos" onPointerLeave={() => setFoco(null)}>
              <text x={m.esquerda} y={10} className="rotulo-grafico chuva">Chuva no mês (mm)</text>
              {meses.map((c, i) => (
                <g key={c.mes} onPointerEnter={() => setFoco(c.mes)}>
                  <rect x={x(c.mes)! - 3} y={0} width={x.bandwidth() + 6} height={altura} fill="transparent" />
                  {c.chuva_mm != null && (
                    <motion.rect x={x(c.mes)} width={x.bandwidth()} rx={3} className={`barra-chuva${c.cobertura_pct < 90 ? ' parcial' : ''}${foco === c.mes ? ' foco' : ''}`}
                      initial={{ y: hChuva, height: 0 }} whileInView={{ y: yc(c.chuva_mm), height: hChuva - yc(c.chuva_mm) }} viewport={{ once: true }} transition={{ duration: 0.6, delay: i * 0.02 }} />
                  )}
                </g>
              ))}
              <line x1={m.esquerda} x2={largura - m.direita} y1={hChuva} y2={hChuva} className="base" />
              <text x={m.esquerda} y={hChuva + vao + 10} className="rotulo-grafico dengue">Casos de dengue no mês</text>
              <path d={area<typeof pontos[number]>().x(d => cx(d.mes)).y0(yd(0)).y1(d => yd(d.v)).curve(curveMonotoneX)(pontos) ?? ''} className="area-atual" />
              <path d={line<typeof pontos[number]>().x(d => cx(d.mes)).y(d => yd(d.v)).curve(curveMonotoneX)(pontos) ?? ''} className="linha-atual fina" />
              <line x1={m.esquerda} x2={largura - m.direita} y1={yd(0)} y2={yd(0)} className="base" />
              {meses.filter(c => c.mes.endsWith('-01') || (c.mes === meses[0].mes && !meses.slice(1, 5).some(o => o.mes.endsWith('-01')))).map(c => (
                <text key={c.mes} x={cx(c.mes)} y={altura - 6} textAnchor="middle" className="eixo forte">{c.mes.slice(0, 4)}</text>
              ))}
              {meses.map(c => largura > 640 && <text key={`m${c.mes}`} x={cx(c.mes)} y={yd(0) + 14} textAnchor="middle" className="eixo mini">{mesCurto(c.mes)[0].toUpperCase()}</text>)}
              {f && <line x1={cx(f.mes)} x2={cx(f.mes)} y1={12} y2={yd(0)} className="guia" />}
            </svg>
            {f && (
              <div className="dica" style={{ left: Math.min(cx(f.mes) + 12, largura - 220), top: 20 }} role="status">
                <strong>{mesLongo(f.mes)} de {f.mes.slice(0, 4)}</strong>
                <span><i className="leg-quadrado chuva" /> Chuva: <b>{decimal(f.chuva_mm)} mm</b>{f.cobertura_pct < 90 ? <small> (medição parcial)</small> : null}</span>
                <span><i className="leg-quadrado dengue" /> Dengue: <b>{numero(dengue.get(f.mes))}</b> casos</span>
              </div>
            )}
          </div>
          <p className="nota">Chuva da estação do INMET em Goiânia; barras claras: meses com falhas na medição. As chuvas vão de outubro a abril, e a água parada que deixam é onde o mosquito se reproduz.</p>
        </div>
  );
}
