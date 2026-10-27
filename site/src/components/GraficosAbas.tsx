import { useState } from 'react';
import { scaleBand, scaleLinear } from 'd3-scale';
import { area, curveMonotoneX, line } from 'd3-shape';
import { max } from 'd3-array';
import { motion } from 'motion/react';
import type { DadosSite } from '../lib/dados';
import { MESES_ABREV, dataCurta, decimal, mesLongo, numero, useLargura } from '../lib/formato';

type Semana = DadosSite['semanal'][number];
type Serie = { chave: keyof Semana; rotulo: string; cor: string };

/** Várias séries semanais na mesma escala relativa (cada uma dividida pelo próprio pico), para comparar o formato. */
export function LinhasRelativas({ semanal, series, titulo, nota }: { semanal: Semana[]; series: Serie[]; titulo: string; nota: string }) {
  const [ref, largura] = useLargura<HTMLDivElement>();
  const [foco, setFoco] = useState<number | null>(null);
  const altura = 260, m = { topo: 14, base: 26, lado: 10 };
  const picos = Object.fromEntries(series.map(s => [s.chave, max(semanal.filter(p => !p.incompleta), p => p[s.chave] as number) || 1]));
  const x = scaleLinear().domain([0, semanal.length - 1]).range([m.lado, largura - m.lado]);
  const y = scaleLinear().domain([0, 1.15]).range([altura - m.base, m.topo]);
  const iIncompleta = semanal.findIndex(p => p.incompleta);
  const f = foco == null ? null : semanal[foco];
  return (
    <div className="cartao grafico-cartao">
      <div className="grafico-topo">
        <h3 className="titulo-cartao">{titulo}</h3>
        <div className="legenda">{series.map(s => <span key={String(s.chave)}><i className="leg-linha" style={{ background: s.cor }} />{s.rotulo}</span>)}</div>
      </div>
      <div ref={ref} className="grafico-area">
        <svg width={largura} height={altura} role="img" aria-label={titulo}
          onPointerMove={e => { const r = e.currentTarget.getBoundingClientRect(); const i = Math.round(x.invert(e.clientX - r.left)); setFoco(i >= 0 && i < semanal.length ? i : null); }}
          onPointerLeave={() => setFoco(null)}>
          {iIncompleta > 0 && <rect x={x(iIncompleta)} width={largura - m.lado - x(iIncompleta)} y={m.topo} height={altura - m.base - m.topo} className="zona-incompleta" />}
          {series.map(s => <path key={String(s.chave)} d={line<Semana>().x((_, i) => x(i)).y(p => y((p[s.chave] as number) / picos[s.chave as string])).curve(curveMonotoneX)(semanal) ?? ''}
            fill="none" stroke={s.cor} strokeWidth={2.2} strokeLinejoin="round" />)}
          {semanal.map((p, i) => p.semana.endsWith('-01-') || (i > 0 && p.semana.slice(0, 4) !== semanal[i - 1].semana.slice(0, 4))
            ? <text key={p.semana} x={x(i)} y={altura - 8} textAnchor="middle" className="eixo forte">{p.semana.slice(0, 4)}</text> : null)}
          {f && <line x1={x(foco!)} x2={x(foco!)} y1={m.topo} y2={altura - m.base} className="guia" />}
        </svg>
        {f && <div className="dica" style={{ left: Math.min(x(foco!) + 12, largura - 220) }} role="status">
          <strong>Semana de {dataCurta(f.semana)} de {f.semana.slice(0, 4)}</strong>
          {series.map(s => <span key={String(s.chave)}><i className="leg-quadrado" style={{ background: s.cor }} />{s.rotulo}: <b>{numero(f[s.chave] as number)}</b></span>)}
          {f.incompleta && <small>Registros ainda chegando</small>}
        </div>}
      </div>
      <p className="nota">{nota}</p>
    </div>
  );
}

export function Internacoes({ dados }: { dados: DadosSite }) {
  const [ref, largura] = useLargura<HTMLDivElement>();
  const anos = dados.internacoes_anual;
  const altura = 220, m = { topo: 22, base: 22, lado: 6 };
  const x = scaleBand<number>().domain(anos.map(a => a.ano)).range([m.lado, largura - m.lado]).padding(0.25);
  const y = scaleLinear().domain([0, (max(anos, a => a.internacoes) ?? 1) * 1.12]).range([altura - m.base, m.topo]);
  const atual = anos.at(-1)!;
  const total = dados.dengue.anual.find(a => a.ano === atual.ano)?.notificacoes;
  return (
    <div className="cartao grafico-cartao">
      <div className="grafico-topo">
        <h3 className="titulo-cartao">Internações por dengue</h3>
        <p className="nota">{numero(atual.internacoes)} em {atual.ano}{total ? ` · ${decimal(atual.internacoes / total * 100)}% dos casos notificados` : ''}</p>
      </div>
      <div ref={ref} className="grafico-area">
        <svg width={largura} height={altura} role="img" aria-label="Internações por dengue por ano em Goiânia">
          {anos.map((a, i) => <g key={a.ano}>
            <motion.rect x={x(a.ano)} width={x.bandwidth()} rx={3} fill="var(--zona-alerta)" opacity={a.ano === atual.ano ? 1 : 0.55}
              initial={{ y: y(0), height: 0 }} whileInView={{ y: y(a.internacoes), height: y(0) - y(a.internacoes) }} viewport={{ once: true }} transition={{ duration: 0.6, delay: i * 0.03 }} />
            {largura > 520 && <text x={x(a.ano)! + x.bandwidth() / 2} y={y(a.internacoes) - 6} textAnchor="middle" className="valor-barra">{numero(a.internacoes)}</text>}
            <text x={x(a.ano)! + x.bandwidth() / 2} y={altura - 6} textAnchor="middle" className="eixo">{largura < 520 ? `'${String(a.ano).slice(2)}` : a.ano}</text>
          </g>)}
        </svg>
      </div>
      <p className="nota">Notificações com registro de internação, por ano de início dos sintomas (SINAN). Não há previsão de internações: o modelo testado empatou com repetir as últimas semanas.</p>
    </div>
  );
}

const VARIAVEIS = { chuva_mm: { rotulo: 'Chuva', cor: 'var(--chuva)' }, umidade_pct: { rotulo: 'Umidade', cor: '#5aa0a8' }, temperatura_c: { rotulo: 'Temperatura', cor: 'var(--zona-alerta)' } } as const;

/** Correlação entre clima de semanas anteriores e dengue: bruta (inclui a época do ano) e sem sazonalidade. */
export function CorrelacaoClima({ c }: { c: DadosSite['correlacoes']['clima_dengue'] }) {
  const [ref, largura] = useLargura<HTMLDivElement>();
  const [variavel, setVariavel] = useState<keyof typeof VARIAVEIS>('chuva_mm');
  const d = c[variavel], v = VARIAVEIS[variavel];
  const altura = 230, m = { topo: 14, base: 30, esquerda: 40, direita: 10 };
  const x = scaleBand<number>().domain(d.lags).range([m.esquerda, largura - m.direita]).padding(0.2);
  const y = scaleLinear().domain([-0.4, 0.8]).range([altura - m.base, m.topo]);
  return (
    <div className="cartao grafico-cartao">
      <div className="grafico-topo">
        <h3 className="titulo-cartao">Clima das semanas anteriores e dengue</h3>
        <div className="chips" role="group">{(Object.keys(VARIAVEIS) as (keyof typeof VARIAVEIS)[]).map(k =>
          <button key={k} className="chip" aria-pressed={k === variavel} onClick={() => setVariavel(k)}>{VARIAVEIS[k].rotulo}</button>)}</div>
      </div>
      <div ref={ref} className="grafico-area">
        <svg width={largura} height={altura} role="img" aria-label={`Correlação entre ${v.rotulo.toLowerCase()} e dengue por semanas de atraso`}>
          {[-0.4, 0, 0.4, 0.8].map(t => <g key={t}><line x1={m.esquerda} x2={largura - m.direita} y1={y(t)} y2={y(t)} className={t === 0 ? 'base' : 'grade'} />
            <text x={m.esquerda - 8} y={y(t)} dy="0.32em" textAnchor="end" className="eixo">{decimal(t)}</text></g>)}
          {d.lags.map((l, i) => <g key={l}>
            <rect x={x(l)} width={x.bandwidth()} y={Math.min(y(d.r_bruta[i]), y(0))} height={Math.abs(y(d.r_bruta[i]) - y(0))} fill={v.cor} opacity={0.35} rx={2} />
            <rect x={x(l)! + x.bandwidth() * 0.25} width={x.bandwidth() * 0.5} y={Math.min(y(d.r_sem_sazonalidade[i]), y(0))} height={Math.max(1.5, Math.abs(y(d.r_sem_sazonalidade[i]) - y(0)))} fill="var(--tinta)" rx={1} />
            {(l % 2 === 0) && <text x={x(l)! + x.bandwidth() / 2} y={altura - 12} textAnchor="middle" className="eixo">{l}</text>}
          </g>)}
          <text x={(m.esquerda + largura) / 2} y={altura - 0} textAnchor="middle" className="eixo">semanas entre o clima e os casos</text>
        </svg>
      </div>
      <div className="legenda"><span><i className="leg-quadrado" style={{ background: v.cor, opacity: 0.45 }} />Junto com a época do ano</span><span><i className="leg-quadrado" style={{ background: 'var(--tinta)' }} />Além da época do ano</span></div>
      <p className="nota">Correlação de 0 (nenhuma) a 1 (total). {v.rotulo} acompanha a dengue {d.melhor_lag} semanas depois na época do ano ({decimal(d.r_bruta_no_melhor_lag, 2)}), mas, descontada a sazonalidade, a relação é {d.forca} ({decimal(d.r_melhor, 2)}).</p>
    </div>
  );
}

/** Acidentes com escorpião por mês desde 2014, com a previsão dos próximos meses. */
export function EscorpioesHistorico({ m: modelo }: { m: DadosSite['escorpioes_modelo'] }) {
  const [ref, largura] = useLargura<HTMLDivElement>();
  const [foco, setFoco] = useState<number | null>(null);
  const serie = modelo.serie;
  const prev = modelo.previsao;
  const n = serie.length + prev.length;
  const altura = 270, mm = { topo: 14, base: 26, esquerda: 36, direita: 10 };
  const x = scaleLinear().domain([0, n - 1]).range([mm.esquerda, largura - mm.direita]);
  const y = scaleLinear().domain([0, (max([...serie.map(s => s.acidentes), ...prev.map(p => p.faixa_80pct[1])]) ?? 1) * 1.08]).nice().range([altura - mm.base, mm.topo]);
  const ultimo = serie.length - 1;
  const pontosPrev = [{ i: ultimo, v: serie[ultimo].acidentes, lo: serie[ultimo].acidentes, hi: serie[ultimo].acidentes }, ...prev.map((p, k) => ({ i: ultimo + 1 + k, v: p.previsto, lo: p.faixa_80pct[0], hi: p.faixa_80pct[1] }))];
  const f = foco == null ? null : foco <= ultimo ? { mes: serie[foco].mes, v: serie[foco].acidentes, p: null } : { mes: prev[foco - ultimo - 1].mes, v: null, p: prev[foco - ultimo - 1] };
  return (
    <div className="cartao grafico-cartao">
      <div className="grafico-topo">
        <h3 className="titulo-cartao">Acidentes por mês desde 2014</h3>
        <div className="legenda"><span><i className="leg-linha" style={{ background: 'var(--escorpiao)' }} />Acidentes</span>{prev.length > 0 && <span><i className="leg-linha projecao" />Previsão</span>}</div>
      </div>
      <div ref={ref} className="grafico-area">
        <svg width={largura} height={altura} role="img" aria-label="Acidentes com escorpião por mês em Goiânia, com previsão"
          onPointerMove={e => { const r = e.currentTarget.getBoundingClientRect(); const i = Math.round(x.invert(e.clientX - r.left)); setFoco(i >= 0 && i < n ? i : null); }}
          onPointerLeave={() => setFoco(null)}>
          {y.ticks(4).map(t => <g key={t}><line x1={mm.esquerda} x2={largura - mm.direita} y1={y(t)} y2={y(t)} className="grade" />
            <text x={mm.esquerda - 8} y={y(t)} dy="0.32em" textAnchor="end" className="eixo">{t}</text></g>)}
          <path d={line<typeof serie[number]>().x((_, i) => x(i)).y(s => y(s.acidentes))(serie) ?? ''} fill="none" stroke="var(--escorpiao)" strokeWidth={1.8} />
          {prev.length > 0 && <>
            <path d={area<typeof pontosPrev[number]>().x(p => x(p.i)).y0(p => y(p.lo)).y1(p => y(p.hi))(pontosPrev) ?? ''} fill="var(--escorpiao)" opacity={0.15} />
            <path d={line<typeof pontosPrev[number]>().x(p => x(p.i)).y(p => y(p.v))(pontosPrev) ?? ''} className="linha-projecao" style={{ stroke: 'var(--escorpiao)' }} />
          </>}
          {serie.map((s, i) => s.mes.endsWith('-01') && Number(s.mes.slice(0, 4)) % 2 === 0 ? <text key={s.mes} x={x(i)} y={altura - 8} textAnchor="middle" className="eixo">{s.mes.slice(0, 4)}</text> : null)}
          {f && <line x1={x(foco!)} x2={x(foco!)} y1={mm.topo} y2={altura - mm.base} className="guia" />}
        </svg>
        {f && <div className="dica" style={{ left: Math.min(x(foco!) + 12, largura - 220) }} role="status">
          <strong>{mesLongo(f.mes)} de {f.mes.slice(0, 4)}</strong>
          {f.v != null && <span>Acidentes: <b>{numero(f.v)}</b></span>}
          {f.p && <span>Previsão: <b>{numero(f.p.previsto)}</b> <small>(entre {numero(f.p.faixa_80pct[0])} e {numero(f.p.faixa_80pct[1])})</small></span>}
        </div>}
      </div>
      <p className="nota">{prev.length > 0 ? `Previsão para os próximos 3 meses, por modelo que acertou um pouco mais que repetir o mesmo mês do ano anterior no teste de 2021 em diante. A faixa indica onde o valor real ficou em 8 de cada 10 meses testados.` : 'A previsão não superou as referências simples no teste e não é exibida.'}</p>
    </div>
  );
}

export function EpocaEscorpioes({ perfil }: { perfil: DadosSite['correlacoes']['escorpioes']['perfil_mensal'] }) {
  const [ref, largura] = useLargura<HTMLDivElement>();
  const altura = 230, m = { topo: 14, base: 26, lado: 36 };
  const x = scaleBand<number>().domain(perfil.map(p => p.mes)).range([m.lado, largura - m.lado]).padding(0.25);
  const y = scaleLinear().domain([0, (max(perfil, p => p.acidentes) ?? 1) * 1.15]).range([altura - m.base, m.topo]);
  const yt = scaleLinear().domain([16, 30]).range([altura - m.base, m.topo]);
  return (
    <div className="cartao grafico-cartao">
      <div className="grafico-topo">
        <h3 className="titulo-cartao">Época do ano</h3>
        <div className="legenda"><span><i className="leg-quadrado escorpiao" />Acidentes (média por mês)</span><span><i className="leg-linha" style={{ background: 'var(--zona-alerta)' }} />Temperatura média</span></div>
      </div>
      <div ref={ref} className="grafico-area">
        <svg width={largura} height={altura} role="img" aria-label="Média de acidentes com escorpião e temperatura por mês do ano">
          {perfil.map(p => <rect key={p.mes} x={x(p.mes)} width={x.bandwidth()} y={y(p.acidentes)} height={y(0) - y(p.acidentes)} rx={3} className="barra-escorpiao" />)}
          <path d={line<typeof perfil[number]>().x(p => x(p.mes)! + x.bandwidth() / 2).y(p => yt(p.temperatura_c)).curve(curveMonotoneX)(perfil) ?? ''} fill="none" stroke="var(--zona-alerta)" strokeWidth={2.2} />
          {perfil.map(p => <g key={`t${p.mes}`}>
            <circle cx={x(p.mes)! + x.bandwidth() / 2} cy={yt(p.temperatura_c)} r={3} fill="var(--zona-alerta)" />
            <text x={x(p.mes)! + x.bandwidth() / 2} y={altura - 8} textAnchor="middle" className="eixo">{MESES_ABREV[p.mes - 1]}</text>
          </g>)}
          <text x={largura - m.lado + 6} y={yt(30)} dy="0.7em" className="eixo">30°</text>
          <text x={largura - m.lado + 6} y={yt(16)} className="eixo">16°</text>
        </svg>
      </div>
    </div>
  );
}
