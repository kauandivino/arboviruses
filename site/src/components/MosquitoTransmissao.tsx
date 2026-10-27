import { useState } from 'react';
import { scaleLinear, scaleTime } from 'd3-scale';
import { line, curveMonotoneX } from 'd3-shape';
import { max } from 'd3-array';
import { Activity, Bug } from 'lucide-react';
import type { DadosSite } from '../lib/dados';
import { dataCurta, dataLonga, decimal, useLargura } from '../lib/formato';

const SITUACAO = { baixo: 'Baixo risco', medio: 'Médio risco', alto: 'Alto risco' } as Record<string, string>;
const COR = { baixo: 'var(--zona-abaixo)', medio: 'var(--zona-acima)', alto: 'var(--zona-alerta)' } as Record<string, string>;

function Liraa({ ciclos }: { ciclos: DadosSite['liraa'] }) {
  const [ref, largura] = useLargura<HTMLDivElement>(500);
  const [foco, setFoco] = useState<number | null>(null);
  const altura = 200, m = { topo: 12, base: 26, esquerda: 34, direita: 10 };
  const datas = ciclos.map(c => new Date(`${c.fim}T12:00:00`));
  const x = scaleTime().domain([datas[0], datas.at(-1)!]).range([m.esquerda + 6, largura - m.direita - 6]);
  const topo = Math.max(5, (max(ciclos, c => c.iip) ?? 5) * 1.15);
  const y = scaleLinear().domain([0, topo]).range([altura - m.base, m.topo]);
  const ultimo = ciclos.at(-1)!;
  const anos = [...new Set(ciclos.map(c => Number(c.fim.slice(0, 4))))];
  const c = foco == null ? null : ciclos[foco];
  return (
    <div className="cartao grafico-cartao mosquito">
      <p className="rotulo-pequeno"><Bug size={14} aria-hidden="true" /> Onde está o mosquito (LIRAa)</p>
      <h3 className="titulo-cartao grande" style={{ color: COR[ultimo.situacao] === 'var(--zona-abaixo)' ? 'var(--acento-forte)' : COR[ultimo.situacao] }}>{SITUACAO[ultimo.situacao] ?? ultimo.situacao}</h3>
      <p>No último levantamento ({dataLonga(ultimo.fim)}), o mosquito foi encontrado em <strong>{decimal(ultimo.iip)}%</strong> dos imóveis visitados. {ultimo.estratos_alto > 0 && <>{ultimo.estratos_alto} das {ultimo.estratos_total} áreas da cidade estavam em alto risco.</>}</p>
      <div ref={ref} className="grafico-area">
        <svg width={largura} height={altura} role="img" aria-label="Índice de infestação predial do Aedes aegypti em cada levantamento LIRAa" onPointerLeave={() => setFoco(null)}>
          {[[0, 1, 'var(--zona-abaixo)'], [1, 3.9, 'var(--zona-acima)'], [3.9, topo, 'var(--zona-alerta)']].map(([a, b, cor]) => (
            <rect key={String(a)} x={m.esquerda} width={largura - m.esquerda - m.direita} y={y(Number(b))} height={y(Number(a)) - y(Number(b))} fill={String(cor)} opacity={0.18} />
          ))}
          {[1, 3.9].map(v => <text key={v} x={m.esquerda - 6} y={y(v)} dy="0.32em" textAnchor="end" className="eixo">{decimal(v)}%</text>)}
          {/* Segmentos retos: os levantamentos são espaçados por meses; uma curva sugeriria valores não medidos. */}
          <path d={line<DadosSite['liraa'][number]>().x((_, i) => x(datas[i])).y(d => y(d.iip))(ciclos) ?? ''} className="linha-liraa" />
          {ciclos.map((ci, i) => (
            <g key={ci.fim} onPointerEnter={() => setFoco(i)}>
              <circle cx={x(datas[i])} cy={y(ci.iip)} r={12} fill="transparent" />
              <circle cx={x(datas[i])} cy={y(ci.iip)} r={foco === i ? 6 : 4.5} fill={COR[ci.situacao] ?? 'var(--tinta-3)'} stroke="#fff" strokeWidth={1.5} />
            </g>
          ))}
          {anos.map(a => { const d = new Date(`${a}-07-01T12:00:00`); return d >= datas[0] && d <= datas.at(-1)! && <text key={a} x={x(d)} y={altura - 6} textAnchor="middle" className="eixo forte">{a}</text>; })}
        </svg>
        {c && (
          <div className="dica" style={{ left: Math.min(x(datas[foco!]) + 10, largura - 220), top: 8 }} role="status">
            <strong>{dataCurta(c.inicio)} a {dataCurta(c.fim)} de {c.fim.slice(0, 4)}</strong>
            <span>Imóveis com o mosquito: <b>{decimal(c.iip)}%</b></span>
            <span>{SITUACAO[c.situacao]} · {c.estratos_alto} de {c.estratos_total} áreas em alto risco</span>
            {c.nota && <small>Observação sobre a fonte: {c.nota}</small>}
          </div>
        )}
      </div>
      <p className="nota">Faixas do Ministério da Saúde: até 1% baixo risco, de 1% a 3,9% médio, acima de 3,9% alto. Fonte: informes da Secretaria Municipal de Saúde de Goiânia.</p>
    </div>
  );
}

function Rt({ t }: { t: DadosSite['transmissao'] }) {
  const [ref, largura] = useLargura<HTMLDivElement>(500);
  const s = t.semanas;
  const altura = 200, m = { topo: 12, base: 26, esquerda: 34, direita: 10 };
  const x = scaleLinear().domain([0, s.length - 1]).range([m.esquerda + 6, largura - m.direita - 6]);
  const vals = s.map(d => d.rt);
  const y = scaleLinear().domain([Math.min(0.6, ...vals) * 0.95, Math.max(1.4, ...vals) * 1.05]).range([altura - m.base, m.topo]);
  // A semana mais recente ainda está incompleta; o resumo usa a anterior e o gráfico mostra todas.
  const base = s.length > 1 ? s[s.length - 2] : s[0];
  const subindo = base.p_rt1 >= 0.5;
  return (
    <div className="cartao grafico-cartao mosquito">
      <p className="rotulo-pequeno"><Activity size={14} aria-hidden="true" /> Ritmo de transmissão (Rt)</p>
      <h3 className="titulo-cartao grande" style={{ color: subindo ? 'var(--zona-alerta)' : 'var(--acento-forte)' }}>{subindo ? 'Transmissão em alta' : 'Transmissão em queda'}</h3>
      <p>Na semana de {dataCurta(base.semana)}, cada pessoa com dengue transmitiu, em média, para <strong>{decimal(base.rt, 2)}</strong> outras. Acima de 1 a doença se espalha; abaixo de 1, perde força. Chance de estar acima de 1: <strong>{Math.round(base.p_rt1 * 100)}%</strong>.</p>
      <div ref={ref} className="grafico-area">
        <svg width={largura} height={altura} role="img" aria-label="Ritmo de transmissão da dengue nas últimas semanas">
          <line x1={m.esquerda} x2={largura - m.direita} y1={y(1)} y2={y(1)} className="linha-um" />
          <text x={m.esquerda - 6} y={y(1)} dy="0.32em" textAnchor="end" className="eixo forte">1</text>
          <path d={line<typeof s[number]>().x((_, i) => x(i)).y(d => y(d.rt)).curve(curveMonotoneX)(s) ?? ''} className="linha-atual fina" />
          {s.map((d, i) => <circle key={d.se} cx={x(i)} cy={y(d.rt)} r={i === s.length - 1 ? 3 : 4} fill={d.rt > 1 ? 'var(--zona-alerta)' : 'var(--acento-forte)'} stroke="#fff" strokeWidth={1.5} opacity={i === s.length - 1 ? 0.5 : 1} />)}
          {s.map((d, i) => (i % 3 === 0 || i === s.length - 1) && <text key={`r${d.se}`} x={x(i)} y={altura - 6} textAnchor="middle" className="eixo">{dataCurta(d.semana)}</text>)}
        </svg>
      </div>
      <p className="nota">Estimativa do InfoDengue (Fiocruz/FGV), modelo de {dataLonga(t.versao_modelo)}. O último ponto, mais claro, ainda está incompleto e costuma mudar.</p>
    </div>
  );
}

export function MosquitoTransmissao({ dados }: { dados: DadosSite }) {
  return (
    <div className="mosquito-grade">
      {dados.liraa.length > 0 && <Liraa ciclos={dados.liraa} />}
      {dados.transmissao.semanas.length > 0 && <Rt t={dados.transmissao} />}
    </div>
  );
}
