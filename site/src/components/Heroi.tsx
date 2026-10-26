import { motion } from 'motion/react';
import { ArrowDownRight, ArrowRight, ArrowUpRight, MapPin, ShieldCheck } from 'lucide-react';
import type { DadosSite, Situacao } from '../lib/dados';
import { dataLonga, numero } from '../lib/formato';

export const SITUACOES: Record<Situacao, { titulo: string; frase: string; cor: string; nivel: number }> = {
  abaixo: { titulo: 'Abaixo do habitual', frase: 'Menos casos do que costuma haver nesta época do ano.', cor: 'var(--zona-abaixo)', nivel: 0 },
  habitual: { titulo: 'Dentro do habitual', frase: 'Número de casos parecido com o dos últimos anos nesta época.', cor: 'var(--zona-habitual)', nivel: 1 },
  pouco_acima: { titulo: 'Um pouco acima do habitual', frase: 'Mais casos do que a média dos últimos anos nesta época.', cor: 'var(--zona-acima)', nivel: 2 },
  acima: { titulo: 'Acima do habitual', frase: 'Mais casos do que em quase todos os últimos anos nesta época.', cor: 'var(--zona-alerta)', nivel: 3 },
  alerta: { titulo: 'Alerta', frase: 'Há pelo menos duas semanas os casos estão acima do habitual para esta época do ano.', cor: 'var(--zona-alerta)', nivel: 3 },
  em_atualizacao: { titulo: 'Em atualização', frase: 'Os registros desta semana ainda estão chegando. Volte em alguns dias.', cor: 'var(--linha-forte)', nivel: -1 },
};

function Triangulos() {
  return (
    <svg className="heroi-geometria" viewBox="0 0 800 700" aria-hidden="true" preserveAspectRatio="xMidYMid slice">
      <defs>
        <linearGradient id="g-tri" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#20a597" stopOpacity="0.95" />
          <stop offset="1" stopColor="#5fd0c3" stopOpacity="0.75" />
        </linearGradient>
        <pattern id="p-grade" width="40" height="40" patternUnits="userSpaceOnUse"><path d="M40 0H0V40" fill="none" stroke="#13191c" strokeOpacity="0.05" /></pattern>
      </defs>
      <rect width="800" height="700" fill="url(#p-grade)" />
      <motion.path d="M140 40 L760 40 L450 620 Z" fill="none" stroke="#20a597" strokeWidth="1.5" strokeOpacity="0.5"
        initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 1.6, ease: 'easeInOut' }} />
      <motion.path d="M250 120 L680 120 L465 520 Z" fill="url(#g-tri)"
        initial={{ opacity: 0, y: -30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 1, delay: 0.3 }} />
      <motion.path d="M520 470 L620 470 L570 560 Z" fill="#13191c" fillOpacity="0.85"
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 1 }} />
      <motion.path d="M90 380 L170 380 L130 450 Z" fill="none" stroke="#13191c" strokeOpacity="0.35" strokeWidth="1.5"
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 1.2 }} />
    </svg>
  );
}

function Mini({ serie }: { serie: number[] }) {
  const max = Math.max(...serie), w = 220, h = 54;
  const pts = serie.map((v, i) => [i / (serie.length - 1) * w, h - 4 - v / max * (h - 10)]);
  const linha = pts.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join('');
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="mini" aria-hidden="true">
      <path d={`${linha}L${w},${h}L0,${h}Z`} fill="var(--acento-claro)" />
      <path d={linha} fill="none" stroke="var(--acento-forte)" strokeWidth="2" strokeLinejoin="round" />
      <circle cx={pts.at(-1)![0]} cy={pts.at(-1)![1]} r="3.5" fill="var(--acento-forte)" />
    </svg>
  );
}

export function Heroi({ dados }: { dados: DadosSite }) {
  const s = dados.dengue.situacao;
  const info = SITUACOES[s.zona];
  const atual = dados.dengue.temporadas[String(dados.dengue.ano)] ?? [];
  const recentes = atual.filter(p => p.valor != null).slice(-12).map(p => p.valor as number);
  const Seta = s.tendencia === 'subindo' ? ArrowUpRight : s.tendencia === 'caindo' ? ArrowDownRight : ArrowRight;
  return (
    <section id="inicio" className="heroi">
      <Triangulos />
      <div className="conteudo heroi-grade">
        <motion.div className="heroi-texto" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7 }}>
          <p className="sobretitulo">Goiânia · dados até {dataLonga(dados.dados_ate)}</p>
          <h1>Dengue e escorpiões<span>no seu bairro</span></h1>
          <p className="heroi-lead">Como está a cidade nesta semana, onde ficam as unidades de saúde e o que fazer para se proteger. Informação oficial, atualizada toda semana.</p>
          <div className="heroi-acoes">
            <a className="botao primario" href="#mapa"><MapPin size={17} /> Ver meu bairro</a>
            <a className="botao" href="#prevencao"><ShieldCheck size={17} /> Como se proteger</a>
          </div>
        </motion.div>
        <motion.aside className="cartao situacao" aria-label="Situação da dengue nesta semana"
          initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, delay: 0.25 }}>
          <p className="rotulo-pequeno">Dengue em Goiânia agora</p>
          <div className="situacao-selo" style={{ ['--cor' as string]: info.cor }}>
            <span className="situacao-ponto" aria-hidden="true" />
            <strong>{info.titulo}</strong>
          </div>
          <p className="situacao-frase">{info.frase}</p>
          <div className="termometro" aria-hidden="true">
            {['Abaixo', 'Habitual', 'Pouco acima', 'Acima'].map((r, i) => (
              <span key={r} className={i === info.nivel ? 'ativo' : ''}><i />{r}</span>
            ))}
          </div>
          <div className="situacao-numeros">
            <div>
              <span className="numero grande">{numero(s.ultimas_4_semanas)}</span>
              <span className="nota">casos notificados nas últimas 4 semanas</span>
            </div>
            {s.variacao_pct != null && (
              <div className={`tendencia ${s.tendencia}`}>
                <Seta size={20} />
                <span><strong>{s.variacao_pct > 0 ? '+' : ''}{numero(s.variacao_pct)}%</strong> em relação às 4 semanas anteriores</span>
              </div>
            )}
          </div>
          {recentes.length > 2 && <Mini serie={recentes} />}
          <p className="nota">Casos notificados são suspeitas registradas pelos serviços de saúde. Nas semanas mais recentes, o número inclui uma estimativa dos registros que ainda vão chegar.</p>
        </motion.aside>
      </div>
    </section>
  );
}
