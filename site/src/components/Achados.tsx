import { scaleBand, scaleLinear } from 'd3-scale';
import { line, curveMonotoneX } from 'd3-shape';
import { max } from 'd3-array';
import { CloudRain, MapPinned, Bug, Activity } from 'lucide-react';
import type { DadosSite } from '../lib/dados';
import { MESES_ABREV, decimal, numero } from '../lib/formato';
import { linkAba } from '../lib/abas';

const W = 300, H = 110;

function Chuva({ c }: { c: DadosSite['correlacoes']['clima_dengue']['chuva_mm'] }) {
  const x = scaleBand<number>().domain(c.lags).range([0, W]).padding(0.25);
  const y = scaleLinear().domain([-0.2, 0.6]).range([H - 14, 4]);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="mini-grafico" aria-hidden="true">
      <line x1={0} x2={W} y1={y(0)} y2={y(0)} className="base" />
      {c.lags.map((l, i) => <g key={l}>
        <rect x={x(l)} width={x.bandwidth()} y={Math.min(y(c.r_bruta[i]), y(0))} height={Math.abs(y(c.r_bruta[i]) - y(0))} fill="var(--chuva)" opacity={l === c.melhor_lag ? 0.9 : 0.35} />
        <rect x={x(l)! + x.bandwidth() * 0.3} width={x.bandwidth() * 0.4} y={Math.min(y(c.r_sem_sazonalidade[i]), y(0))} height={Math.max(1, Math.abs(y(c.r_sem_sazonalidade[i]) - y(0)))} fill="var(--tinta)" />
      </g>)}
      {[0, 4, 8, 12, 16].map(l => <text key={l} x={x(l)! + x.bandwidth() / 2} y={H - 2} textAnchor="middle" className="eixo mini">{l}</text>)}
    </svg>
  );
}

function Vizinhos({ s }: { s: DadosSite['semanal'] }) {
  const pontos = s.filter(p => !p.incompleta);
  const mg = max(pontos, p => p.goiania) ?? 1, mv = max(pontos, p => p.vizinhos) ?? 1;
  const x = scaleLinear().domain([0, pontos.length - 1]).range([0, W]);
  const y = scaleLinear().domain([0, 1]).range([H - 6, 6]);
  const caminho = (k: 'goiania' | 'vizinhos', m: number) => line<typeof pontos[number]>().x((_, i) => x(i)).y(p => y(p[k] / m)).curve(curveMonotoneX)(pontos) ?? '';
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="mini-grafico" aria-hidden="true">
      <path d={caminho('vizinhos', mv)} fill="none" stroke="var(--chuva)" strokeWidth={2} />
      <path d={caminho('goiania', mg)} fill="none" stroke="var(--acento-forte)" strokeWidth={2} />
    </svg>
  );
}

function Picos({ p }: { p: Record<string, number> }) {
  const valores = Object.entries(p).filter(([, v]) => Math.abs(v) <= 12);
  const x = scaleLinear().domain([-6, 10]).range([16, W - 8]);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="mini-grafico" aria-hidden="true">
      <line x1={x(0)} x2={x(0)} y1={6} y2={H - 22} className="linha-um" />
      <text x={x(0)} y={H - 8} textAnchor="middle" className="eixo mini">pico da dengue</text>
      {valores.map(([ano, v], i) => <g key={ano}>
        <circle cx={x(v)} cy={16 + i * ((H - 44) / Math.max(1, valores.length - 1))} r={6} fill="#c27a2e" />
        <text x={x(v) + 10} y={16 + i * ((H - 44) / Math.max(1, valores.length - 1))} dy="0.32em" className="eixo mini">{ano}</text>
      </g>)}
    </svg>
  );
}

function Escorpioes({ perfil }: { perfil: DadosSite['correlacoes']['escorpioes']['perfil_mensal'] }) {
  const x = scaleBand<number>().domain(perfil.map(p => p.mes)).range([0, W]).padding(0.2);
  const y = scaleLinear().domain([0, (max(perfil, p => p.acidentes) ?? 1) * 1.1]).range([H - 14, 4]);
  const yt = scaleLinear().domain([18, 28]).range([H - 14, 4]);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="mini-grafico" aria-hidden="true">
      {perfil.map(p => <rect key={p.mes} x={x(p.mes)} width={x.bandwidth()} y={y(p.acidentes)} height={y(0) - y(p.acidentes)} fill="var(--escorpiao)" opacity={0.8} rx={2} />)}
      <path d={line<typeof perfil[number]>().x(p => x(p.mes)! + x.bandwidth() / 2).y(p => yt(p.temperatura_c)).curve(curveMonotoneX)(perfil) ?? ''} fill="none" stroke="var(--zona-alerta)" strokeWidth={2} />
      {perfil.filter((_, i) => i % 2 === 0).map(p => <text key={p.mes} x={x(p.mes)! + x.bandwidth() / 2} y={H - 2} textAnchor="middle" className="eixo mini">{MESES_ABREV[p.mes - 1]}</text>)}
    </svg>
  );
}

export function Achados({ dados }: { dados: DadosSite }) {
  const c = dados.correlacoes;
  const chuva = c.clima_dengue.chuva_mm;
  const ruidoClima = Math.abs(chuva.r_melhor) < 0.15;
  const viz = c.vizinhos, chik = c.chikungunya, esc = c.escorpioes;
  const chikDepois = chik.depois >= Math.ceil(chik.temporadas / 2);
  const cartoes = [
    { Icone: CloudRain, aba: 'mosquito' as const, titulo: `A dengue sobe cerca de ${chuva.melhor_lag} semanas depois das chuvas`,
      texto: ruidoClima ? 'É um padrão da época do ano. Um ano mais chuvoso que o normal não teve, por isso, mais dengue que o normal.' : `Mesmo descontada a época do ano, a relação se mantém (${decimal(chuva.r_melhor, 2)}).`,
      legenda: <><i style={{ background: 'var(--chuva)' }} /> época do ano <i style={{ background: 'var(--tinta)' }} /> além da época · semanas de atraso</>,
      grafico: <Chuva c={chuva} /> },
    { Icone: MapPinned, aba: 'dengue' as const, titulo: 'Goiânia e as cidades vizinhas sobem juntas',
      texto: `O pico veio na mesma semana em ${viz.juntos} de ${viz.temporadas} temporadas. As cidades vizinhas não avisam com antecedência.`,
      legenda: <><i style={{ background: 'var(--acento-forte)' }} /> Goiânia <i style={{ background: 'var(--chuva)' }} /> 10 cidades vizinhas · últimos 2 anos</>,
      grafico: <Vizinhos s={dados.semanal} /> },
    { Icone: Activity, aba: 'arboviroses' as const, titulo: chikDepois ? `A chikungunya chega ao pico cerca de ${numero(chik.mediana_semanas)} semanas depois da dengue` : 'Chikungunya e dengue têm picos em épocas próximas',
      texto: chikDepois ? `Aconteceu em ${chik.depois} das ${chik.temporadas} temporadas com mais casos. Quando a dengue começa a cair, a chikungunya ainda pode estar subindo.` : 'O intervalo entre os picos varia de uma temporada para outra.',
      legenda: <>semanas entre os picos, por temporada</>, grafico: <Picos p={chik.por_temporada} /> },
    { Icone: Bug, aba: 'escorpioes' as const, titulo: 'Acidentes com escorpião acontecem o ano todo',
      texto: `Ao contrário do que se pensa, quase não acompanham a temperatura em Goiânia (relação ${Math.abs(esc.r_temperatura_bruta) < 0.15 ? 'muito fraca' : 'fraca'} em ${numero(esc.meses)} meses). A prevenção vale em qualquer época.`,
      legenda: <><i style={{ background: 'var(--escorpiao)' }} /> acidentes por mês (média) <i style={{ background: 'var(--zona-alerta)' }} /> temperatura</>,
      grafico: <Escorpioes perfil={esc.perfil_mensal} /> },
  ];
  return (
    <div className="achados-grade">
      {cartoes.map(({ Icone, aba, titulo, texto, legenda, grafico }) => (
        <a key={titulo} href={linkAba(aba)} className="cartao achado">
          <Icone size={20} className="achado-icone" aria-hidden="true" />
          <h3>{titulo}</h3>
          {grafico}
          <p className="achado-legenda">{legenda}</p>
          <p>{texto}</p>
        </a>
      ))}
    </div>
  );
}

