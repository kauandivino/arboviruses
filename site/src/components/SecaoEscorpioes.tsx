import { useState } from 'react';
import { scaleBand, scaleLinear } from 'd3-scale';
import { max, mean } from 'd3-array';
import { motion } from 'motion/react';
import { Phone, Siren } from 'lucide-react';
import type { DadosSite } from '../lib/dados';
import { MESES_ABREV, numero, useLargura } from '../lib/formato';
import { Revelar } from './Revelar';

export function SecaoEscorpioes({ dados }: { dados: DadosSite }) {
  const [ref, largura] = useLargura<HTMLDivElement>();
  const [foco, setFoco] = useState<number | null>(null);
  const anoAtual = Math.max(...dados.escorpioes.map(e => Number(e.mes.slice(0, 4))));
  const anteriores = [...new Set(dados.escorpioes.map(e => Number(e.mes.slice(0, 4))))].filter(a => a < anoAtual);
  const meses = Array.from({ length: 12 }, (_, i) => {
    const mm = String(i + 1).padStart(2, '0');
    const atual = dados.escorpioes.find(e => e.mes === `${anoAtual}-${mm}`)?.acidentes ?? null;
    const valores = anteriores.map(a => dados.escorpioes.find(e => e.mes === `${a}-${mm}`)?.acidentes).filter((v): v is number => v != null);
    return { i, atual, media: valores.length ? mean(valores)! : null };
  });
  const altura = 280, m = { topo: 20, base: 30, esquerda: 36, direita: 8 };
  const x = scaleBand<number>().domain(meses.map(d => d.i)).range([m.esquerda, largura - m.direita]).padding(0.3);
  const y = scaleLinear().domain([0, (max(meses, d => Math.max(d.atual ?? 0, d.media ?? 0)) ?? 1) * 1.15]).nice().range([altura - m.base, m.topo]);
  const total = meses.reduce((s, d) => s + (d.atual ?? 0), 0);
  const f = foco == null ? null : meses[foco];
  return (
    <section id="escorpioes" className="secao">
      <div className="conteudo grade-lado invertida">
        <Revelar className="cabeca-secao">
          <p className="sobretitulo">Escorpiões</p>
          <h2 className="titulo-secao">Acidentes com escorpião</h2>
          <p className="lead">Em {anoAtual}, foram <strong>{numero(total)}</strong> picadas registradas em Goiânia até agora. Os escorpiões aparecem mais nos meses quentes e se escondem em entulho, ralos e frestas.</p>
          <div className="emergencia">
            <Siren size={22} aria-hidden="true" />
            <div>
              <strong>Foi picado? Procure atendimento imediatamente.</strong>
              <span>Lave o local com água e sabão. Não corte, não aperte e não amarre o local.</span>
              <span className="telefones"><Phone size={15} aria-hidden="true" /> SAMU <b>192</b> · Disque Saúde <b>136</b></span>
            </div>
          </div>
        </Revelar>
        <Revelar className="cartao grafico-cartao">
          <div className="grafico-topo">
            <div className="legenda">
              <span><i className="leg-quadrado escorpiao" /> {anoAtual}</span>
              <span><i className="leg-traco" /> Média de {anteriores[0]} a {anteriores.at(-1)}</span>
            </div>
          </div>
          <div ref={ref} className="grafico-area">
            <svg width={largura} height={altura} role="img" aria-label={`Acidentes com escorpião por mês em ${anoAtual}, comparados com a média dos anos anteriores`} onPointerLeave={() => setFoco(null)}>
              {y.ticks(4).map(t => (
                <g key={t}>
                  <line x1={m.esquerda} x2={largura - m.direita} y1={y(t)} y2={y(t)} className="grade" />
                  <text x={m.esquerda - 8} y={y(t)} dy="0.32em" textAnchor="end" className="eixo">{t}</text>
                </g>
              ))}
              {meses.map(d => (
                <g key={d.i} onPointerEnter={() => setFoco(d.i)}>
                  <rect x={x(d.i)! - 4} y={m.topo} width={x.bandwidth() + 8} height={altura - m.base - m.topo} fill="transparent" />
                  {d.atual != null && (
                    <motion.rect x={x(d.i)} width={x.bandwidth()} rx={4} className={`barra-escorpiao${foco === d.i ? ' foco' : ''}`}
                      initial={{ y: y(0), height: 0 }} whileInView={{ y: y(d.atual), height: y(0) - y(d.atual) }} viewport={{ once: true }} transition={{ duration: 0.6, delay: d.i * 0.04 }} />
                  )}
                  {d.media != null && <line x1={x(d.i)! - 3} x2={x(d.i)! + x.bandwidth() + 3} y1={y(d.media)} y2={y(d.media)} className="traco-media" />}
                  <text x={x(d.i)! + x.bandwidth() / 2} y={altura - 10} textAnchor="middle" className="eixo">{MESES_ABREV[d.i]}</text>
                </g>
              ))}
            </svg>
            {f && (
              <div className="dica" style={{ left: Math.min(x(f.i)! + x.bandwidth() + 10, largura - 210), top: 16 }} role="status">
                <strong>{MESES_ABREV[f.i]}</strong>
                <span>{anoAtual}: <b>{f.atual == null ? 'sem dados ainda' : `${numero(f.atual)} acidentes`}</b></span>
                {f.media != null && <span>Média anterior: {numero(Math.round(f.media))}</span>}
              </div>
            )}
          </div>
          <p className="nota">Acidentes notificados no SINAN pelo local onde aconteceram. Meses sem barra ainda não têm dados publicados.</p>
        </Revelar>
      </div>
    </section>
  );
}
