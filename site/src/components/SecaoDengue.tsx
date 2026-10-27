import { useMemo, useState } from 'react';
import { scaleBand, scaleLinear } from 'd3-scale';
import { area, curveMonotoneX, line } from 'd3-shape';
import { max } from 'd3-array';
import { motion } from 'motion/react';
import type { DadosSite } from '../lib/dados';
import { MESES_ABREV, mesDaSemana, numero, useLargura } from '../lib/formato';
import { Revelar } from './Revelar';
import { Sorotipos } from './Sorotipos';
import { MosquitoTransmissao } from './MosquitoTransmissao';

const CORES_ANOS = ['#9aa6ab', '#b98a5e', '#7b8fc4', '#c27a9b'];
type Ponto = { se: number; valor: number };

function GraficoTemporada({ dados }: { dados: DadosSite }) {
  const [ref, largura] = useLargura<HTMLDivElement>();
  const ano = dados.dengue.ano;
  const anteriores = Object.keys(dados.dengue.temporadas).map(Number).filter(a => a < ano).sort((a, b) => b - a);
  const [visiveis, setVisiveis] = useState<number[]>([]);
  const [foco, setFoco] = useState<number | null>(null);
  const altura = largura < 560 ? 300 : 380;
  const m = { topo: 24, direita: 16, base: 34, esquerda: largura < 560 ? 40 : 52 };
  const faixa = dados.dengue.faixa_habitual;
  const atual = (dados.dengue.temporadas[String(ano)] ?? []).filter((p): p is Ponto => p.valor != null);
  const projecao = dados.dengue.projecao.filter(p => p.ano === ano);
  const series = visiveis.map(a => ({ ano: a, pontos: dados.dengue.temporadas[String(a)].filter((p): p is Ponto => p.valor != null) }));

  const x = scaleLinear().domain([1, 53]).range([m.esquerda, largura - m.direita]);
  const topo = max([...faixa.map(f => f.q3), ...atual.map(p => p.valor), ...projecao.map(p => p.superior * 0.75), ...series.flatMap(s => s.pontos.map(p => p.valor))]) ?? 100;
  const y = scaleLinear().domain([0, topo * 1.08]).nice().range([altura - m.base, m.topo]);
  const banda = area<{ se: number; q1: number; q3: number }>().x(d => x(d.se)).y0(d => y(d.q1)).y1(d => y(d.q3)).curve(curveMonotoneX);
  const mediana = line<{ se: number; mediana: number }>().x(d => x(d.se)).y(d => y(d.mediana)).curve(curveMonotoneX);
  const linhaPts = line<Ponto>().x(d => x(d.se)).y(d => y(d.valor)).curve(curveMonotoneX);
  const ultimo = atual.at(-1);
  const proj = ultimo ? [{ se: ultimo.se, valor: ultimo.valor, inferior: ultimo.valor, superior: ultimo.valor }, ...projecao.map(p => ({ se: p.se, valor: p.previsto, inferior: p.inferior, superior: Math.min(p.superior, topo * 1.08) }))] : [];
  const meses = useMemo(() => Array.from({ length: 53 }, (_, i) => i + 1).filter((se, i, arr) => i === 0 || mesDaSemana(ano, se) !== mesDaSemana(ano, arr[i - 1])), [ano]);

  const f = foco == null ? null : {
    se: foco, faixa: faixa.find(d => d.se === foco), atual: atual.find(d => d.se === foco),
    proj: projecao.find(d => d.se === foco), outros: series.map(s => ({ ano: s.ano, valor: s.pontos.find(p => p.se === foco)?.valor })),
  };
  const aoMover = (e: React.PointerEvent<SVGSVGElement>) => {
    const caixa = e.currentTarget.getBoundingClientRect();
    const se = Math.round(x.invert(e.clientX - caixa.left));
    setFoco(se >= 1 && se <= 53 ? se : null);
  };

  return (
    <div className="grafico-cartao cartao grafico-temporada">
      <div className="grafico-topo">
        <div className="legenda">
          <span><i className="leg-linha atual" /> {ano}</span>
          <span><i className="leg-faixa" /> Faixa habitual para a época</span>
          <span><i className="leg-linha mediana" /> Média dos anos anteriores</span>
          {projecao.length > 0 && <span><i className="leg-linha projecao" /> Projeção das próximas semanas</span>}
        </div>
        <div className="chips" role="group" aria-label="Comparar com anos anteriores">
          <span className="rotulo-pequeno">Comparar</span>
          {anteriores.map((a, i) => (
            <button key={a} className="chip" aria-pressed={visiveis.includes(a)} onClick={() => setVisiveis(v => v.includes(a) ? v.filter(x => x !== a) : [...v, a])}>
              <span className="marca" style={{ background: CORES_ANOS[i % CORES_ANOS.length] }} />{a}
            </button>
          ))}
        </div>
      </div>
      <div ref={ref} className="grafico-area">
        <svg width={largura} height={altura} role="img" onPointerMove={aoMover} onPointerLeave={() => setFoco(null)}
          aria-label={`Casos de dengue notificados por semana em ${ano}, comparados com a faixa habitual dos cinco anos anteriores`}>
          {y.ticks(5).map(t => (
            <g key={t}>
              <line x1={m.esquerda} x2={largura - m.direita} y1={y(t)} y2={y(t)} className="grade" />
              <text x={m.esquerda - 10} y={y(t)} dy="0.32em" textAnchor="end" className="eixo">{numero(t)}</text>
            </g>
          ))}
          {meses.filter((se, i) => se <= 50 && (largura >= 640 || i % 2 === 0)).map(se => <text key={se} x={x(se + 1.5)} y={altura - 10} textAnchor="middle" className="eixo">{MESES_ABREV[mesDaSemana(ano, se)]}</text>)}
          <path d={banda(faixa) ?? ''} className="faixa-habitual" />
          <path d={mediana(faixa) ?? ''} className="mediana" />
          {series.map((s, i) => <path key={s.ano} d={linhaPts(s.pontos) ?? ''} className="linha-ano" style={{ stroke: CORES_ANOS[anteriores.indexOf(s.ano) % CORES_ANOS.length] }} data-i={i} />)}
          <motion.path d={linhaPts(atual) ?? ''} className="linha-atual" initial={{ pathLength: 0 }} whileInView={{ pathLength: 1 }} viewport={{ once: true }} transition={{ duration: 1.6, ease: 'easeInOut' }} />
          <defs>
            {/* A faixa da projeção desaparece para cima: quanto mais alto, menos provável. */}
            <linearGradient id="g-proj" x1="0" y1="1" x2="0" y2="0">
              <stop offset="0" stopColor="var(--acento)" stopOpacity="0.22" />
              <stop offset="0.55" stopColor="var(--acento)" stopOpacity="0.1" />
              <stop offset="1" stopColor="var(--acento)" stopOpacity="0" />
            </linearGradient>
          </defs>
          {proj.length > 1 && <>
            <path d={area<typeof proj[number]>().x(d => x(d.se)).y0(d => y(d.inferior)).y1(d => y(d.superior)).curve(curveMonotoneX)(proj) ?? ''} className="faixa-projecao" />
            <path d={line<typeof proj[number]>().x(d => x(d.se)).y(d => y(d.valor)).curve(curveMonotoneX)(proj) ?? ''} className="linha-projecao" />
          </>}
          {ultimo && <g transform={`translate(${x(ultimo.se)},${y(ultimo.valor)})`}>
            <circle r="9" className="hoje-halo" /><circle r="4.5" className="hoje" />
            <text y={-16} textAnchor="middle" className="hoje-rotulo">Agora</text>
          </g>}
          {f && <line x1={x(f.se)} x2={x(f.se)} y1={m.topo} y2={altura - m.base} className="guia" />}
        </svg>
        {f && (f.atual || f.proj || f.faixa) && (
          <div className="dica" style={{ left: Math.min(Math.max(x(f.se) + 14, 0), largura - 230) }} role="status">
            <strong>Semana {f.se} · {MESES_ABREV[mesDaSemana(ano, f.se)]}</strong>
            {f.atual && <span><i className="leg-linha atual" /> {ano}: <b>{numero(f.atual.valor)}</b> casos</span>}
            {f.proj && <span><i className="leg-linha projecao" /> Projeção: <b>{numero(f.proj.previsto)}</b> <small>(entre {numero(f.proj.inferior)} e {numero(f.proj.superior)})</small></span>}
            {f.faixa && <span><i className="leg-faixa" /> Habitual: {numero(f.faixa.q1)} a {numero(f.faixa.q3)}</span>}
            {f.outros.filter(o => o.valor != null).map(o => <span key={o.ano}>{o.ano}: {numero(o.valor)}</span>)}
          </div>
        )}
      </div>
      <p className="nota">A faixa habitual mostra o que costuma acontecer em cada semana do ano, com base nos cinco anos anteriores (metade dos anos fica dentro dela). A projeção é uma estimativa estatística e pode variar bastante.</p>
    </div>
  );
}

function GraficoAnual({ dados }: { dados: DadosSite }) {
  const [ref, largura] = useLargura<HTMLDivElement>();
  const [foco, setFoco] = useState<number | null>(null);
  const anos = dados.dengue.anual;
  const altura = 260, m = { topo: 28, direita: 8, base: 30, esquerda: 8 };
  const x = scaleBand<number>().domain(anos.map(a => a.ano)).range([m.esquerda, largura - m.direita]).padding(0.28);
  const y = scaleLinear().domain([0, (max(anos, a => a.notificacoes) ?? 1) * 1.1]).range([altura - m.base, m.topo]);
  const maior = anos.reduce((a, b) => (b.notificacoes > a.notificacoes ? b : a));
  return (
    <div className="grafico-cartao cartao">
      <div className="grafico-topo">
        <h3 className="titulo-cartao">Ano a ano</h3>
        <p className="nota">Casos notificados por ano epidemiológico. {anos.at(-1)?.parcial ? `${anos.at(-1)!.ano} ainda está em andamento.` : ''}</p>
      </div>
      <div ref={ref} className="grafico-area">
        <svg width={largura} height={altura} role="img" aria-label="Casos de dengue notificados por ano em Goiânia" onPointerLeave={() => setFoco(null)}>
          <defs>
            <pattern id="hachura" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <rect width="6" height="6" fill="var(--acento-claro)" /><line x1="0" y1="0" x2="0" y2="6" stroke="var(--acento)" strokeWidth="2.4" />
            </pattern>
          </defs>
          {anos.map((a, i) => {
            const destaque = a.ano === maior.ano || a.parcial || foco === a.ano;
            return (
              <g key={a.ano} onPointerEnter={() => setFoco(a.ano)}>
                <rect x={x(a.ano)! - 4} y={m.topo} width={x.bandwidth() + 8} height={altura - m.base - m.topo} fill="transparent" />
                <motion.rect x={x(a.ano)} width={x.bandwidth()} rx={4} className={a.parcial ? 'barra parcial' : a.ano === maior.ano ? 'barra maior' : 'barra'}
                  initial={{ y: y(0), height: 0 }} whileInView={{ y: y(a.notificacoes), height: y(0) - y(a.notificacoes) }} viewport={{ once: true }}
                  transition={{ duration: 0.7, delay: i * 0.04 }} />
                {(destaque || largura > 700) && (
                  <text x={x(a.ano)! + x.bandwidth() / 2} y={y(a.notificacoes) - 8} textAnchor="middle" className={`valor-barra${destaque ? ' forte' : ''}`}>
                    {a.notificacoes >= 1000 ? `${numero(Math.round(a.notificacoes / 1000))} mil` : numero(a.notificacoes)}
                  </text>
                )}
                <text x={x(a.ano)! + x.bandwidth() / 2} y={altura - 10} textAnchor="middle" className="eixo">{largura < 520 ? `'${String(a.ano).slice(2)}` : a.ano}</text>
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}

export function SecaoDengue({ dados }: { dados: DadosSite }) {
  return (
    <section id="dengue" className="secao">
      <div className="conteudo">
        <Revelar className="cabeca-secao">
          <p className="sobretitulo">Dengue</p>
          <h2 className="titulo-secao">Como a dengue está neste ano</h2>
          <p className="lead">A linha mostra os casos de cada semana. Quando ela passa da faixa clara, há mais dengue do que o normal para a época.</p>
        </Revelar>
        <Revelar><GraficoTemporada dados={dados} /></Revelar>
        <Revelar atraso={0.1}><MosquitoTransmissao dados={dados} /></Revelar>
        <Revelar atraso={0.1}><Sorotipos dados={dados} /></Revelar>
        <Revelar atraso={0.1}><GraficoAnual dados={dados} /></Revelar>
      </div>
    </section>
  );
}
