import { useState } from 'react';
import { scaleBand, scaleLinear } from 'd3-scale';
import { max } from 'd3-array';
import { motion } from 'motion/react';
import { Dna } from 'lucide-react';
import type { DadosSite } from '../lib/dados';
import { mesCurto, mesLongo, numero, useLargura } from '../lib/formato';

const TIPOS = [
  { chave: 'denv1', rotulo: 'Tipo 1', cor: '#9aa6ab' },
  { chave: 'denv2', rotulo: 'Tipo 2', cor: '#5b8fd6' },
  { chave: 'denv3', rotulo: 'Tipo 3', cor: '#e2553f' },
  { chave: 'denv4', rotulo: 'Tipo 4', cor: '#7a4fa3' },
] as const;

export function Sorotipos({ dados }: { dados: DadosSite }) {
  const s = dados.sorotipos;
  const [ref, largura] = useLargura<HTMLDivElement>();
  const [foco, setFoco] = useState<string | null>(null);
  const altura = 230, m = { topo: 12, base: 28, esquerda: 6, direita: 6 };
  const total = (d: (typeof s.meses)[number]) => TIPOS.reduce((acc, t) => acc + d[t.chave], 0);
  const x = scaleBand<string>().domain(s.meses.map(d => d.mes)).range([m.esquerda, largura - m.direita]).padding(0.22);
  const y = scaleLinear().domain([0, (max(s.meses, total) ?? 1) * 1.08]).range([altura - m.base, m.topo]);
  const dom = s.dominante ? TIPOS[Number(s.dominante) - 1] : null;
  const recente = s.primeiro_ano_relevante != null && s.primeiro_ano_relevante >= dados.dengue.ano - 1;
  const f = foco ? s.meses.find(d => d.mes === foco) : null;
  return (
    <div className="grafico-cartao cartao sorotipos">
      <div className="sorotipos-texto">
        <p className="rotulo-pequeno"><Dna size={14} aria-hidden="true" /> Qual vírus está circulando</p>
        {dom ? (
          <>
            <h3 className="titulo-cartao grande" style={{ color: dom.cor }}>Dengue {dom.rotulo.toLowerCase()}</h3>
            <p>
              É o tipo em <strong>{numero(Math.round((s.parcela_dominante ?? 0) * 100))}%</strong> das {numero(s.amostras_12_semanas)} amostras analisadas
              nas últimas 12 semanas.{recente && <> Desde {s.desde}, ele quase não aparecia em Goiânia e voltou a circular em {s.primeiro_ano_relevante}.</>}
            </p>
            <p className="aviso-curto">Existem quatro tipos de vírus da dengue. Quem já teve dengue pode pegar de novo com outro tipo, e a segunda infecção tem mais risco de ser grave.</p>
          </>
        ) : <p>Poucas amostras analisadas nas últimas semanas para saber qual tipo predomina.</p>}
        <p className="nota">Só uma parte dos casos passa por exame que identifica o tipo do vírus.</p>
      </div>
      <div ref={ref} className="grafico-area">
        <div className="legenda">{TIPOS.map(t => <span key={t.chave}><i className="leg-quadrado" style={{ background: t.cor }} />{t.rotulo}</span>)}</div>
        <svg width={largura} height={altura} role="img" aria-label="Amostras com tipo de vírus identificado, por mês, nos últimos dois anos" onPointerLeave={() => setFoco(null)}>
          {s.meses.map((d, i) => {
            let base = y(0);
            return (
              <g key={d.mes} onPointerEnter={() => setFoco(d.mes)}>
                <rect x={x(d.mes)! - 2} y={m.topo} width={x.bandwidth() + 4} height={altura - m.base - m.topo} fill="transparent" />
                {TIPOS.map(t => {
                  const h = base - y(d[t.chave]);
                  base -= h;
                  return h > 0 && <motion.rect key={t.chave} x={x(d.mes)} y={base} width={x.bandwidth()} height={h} fill={t.cor} rx={1.5}
                    opacity={foco && foco !== d.mes ? 0.45 : 1} initial={{ scaleY: 0 }} whileInView={{ scaleY: 1 }} viewport={{ once: true }}
                    style={{ transformOrigin: `0 ${y(0)}px` }} transition={{ duration: 0.5, delay: i * 0.02 }} />;
                })}
                {(d.mes.endsWith('-01') || i === 0) && <text x={x(d.mes)! + x.bandwidth() / 2} y={altura - 8} textAnchor="middle" className="eixo forte">{d.mes.slice(0, 4)}</text>}
                {largura > 600 && !d.mes.endsWith('-01') && i > 0 && <text x={x(d.mes)! + x.bandwidth() / 2} y={altura - 8} textAnchor="middle" className="eixo mini">{mesCurto(d.mes)[0].toUpperCase()}</text>}
              </g>
            );
          })}
        </svg>
        {f && (
          <div className="dica" style={{ left: Math.min(x(f.mes)! + x.bandwidth() + 8, largura - 200), top: 30 }} role="status">
            <strong>{mesLongo(f.mes)} de {f.mes.slice(0, 4)}</strong>
            {TIPOS.filter(t => f[t.chave] > 0).map(t => <span key={t.chave}><i className="leg-quadrado" style={{ background: t.cor }} />{t.rotulo}: <b>{numero(f[t.chave])}</b></span>)}
            {total(f) === 0 && <span>Nenhuma amostra tipada</span>}
          </div>
        )}
      </div>
    </div>
  );
}
