import { scaleBand, scaleLinear } from 'd3-scale';
import { max } from 'd3-array';
import { motion } from 'motion/react';
import type { DadosSite } from '../lib/dados';
import { numero, useLargura } from '../lib/formato';
import { Revelar } from './Revelar';

const INFO = {
  chikungunya: { nome: 'Chikungunya', cor: '#c27a2e', texto: 'Febre alta e dor forte nas articulações, que pode durar meses.' },
  zika: { nome: 'Zika', cor: '#7a4fa3', texto: 'Manchas vermelhas na pele e coceira. Na gravidez, pode afetar o bebê: gestantes devem redobrar a proteção.' },
} as const;

function Barras({ agravo, dados }: { agravo: keyof typeof INFO; dados: DadosSite['outras_arboviroses'][keyof typeof INFO] }) {
  const [ref, largura] = useLargura<HTMLDivElement>(500);
  const info = INFO[agravo];
  const anos = dados.anual;
  const altura = 170, m = { topo: 22, base: 22, lado: 4 };
  const x = scaleBand<number>().domain(anos.map(a => a.ano)).range([m.lado, largura - m.lado]).padding(0.25);
  const y = scaleLinear().domain([0, (max(anos, a => a.notificacoes) ?? 1) * 1.12]).range([altura - m.base, m.topo]);
  const maior = anos.reduce((a, b) => (b.notificacoes > a.notificacoes ? b : a));
  const atual = anos.at(-1)!;
  return (
    <div className="cartao grafico-cartao outra">
      <h3 className="titulo-cartao" style={{ color: info.cor }}>{info.nome}</h3>
      <p><span className="numero medio">{numero(atual.notificacoes)}</span> casos notificados em {atual.ano} em Goiânia. {info.texto}</p>
      <div ref={ref} className="grafico-area">
        <svg width={largura} height={altura} role="img" aria-label={`Casos de ${info.nome} notificados por ano em Goiânia`}>
          {anos.map((a, i) => (
            <g key={a.ano}>
              <motion.rect x={x(a.ano)} width={x.bandwidth()} rx={3} fill={info.cor} opacity={a.ano === atual.ano || a.ano === maior.ano ? 1 : 0.4}
                initial={{ y: y(0), height: 0 }} whileInView={{ y: y(a.notificacoes), height: y(0) - y(a.notificacoes) }} viewport={{ once: true }} transition={{ duration: 0.6, delay: i * 0.03 }} />
              {(a.ano === maior.ano || a.ano === atual.ano) && <text x={x(a.ano)! + x.bandwidth() / 2} y={y(a.notificacoes) - 6} textAnchor="middle" className="valor-barra forte">{numero(a.notificacoes)}</text>}
              {(i % 3 === 0 || i === anos.length - 1) && <text x={x(a.ano)! + x.bandwidth() / 2} y={altura - 6} textAnchor="middle" className="eixo">{a.ano}</text>}
            </g>
          ))}
        </svg>
      </div>
    </div>
  );
}

export function SecaoOutras({ dados }: { dados: DadosSite }) {
  return (
    <section id="outras" className="secao alternada">
      <div className="conteudo">
        <Revelar className="cabeca-secao">
          <p className="sobretitulo">Outras doenças do mosquito</p>
          <h2 className="titulo-secao">Chikungunya e zika</h2>
          <p className="lead">O mesmo mosquito da dengue transmite chikungunya e zika. As medidas de prevenção são as mesmas.</p>
        </Revelar>
        <div className="outras-grade">
          {(Object.keys(INFO) as (keyof typeof INFO)[]).map((a, i) => <Revelar key={a} atraso={i * 0.08}><Barras agravo={a} dados={dados.outras_arboviroses[a]} /></Revelar>)}
        </div>
        <p className="nota">Casos notificados de residentes em Goiânia por ano de início dos sintomas, todas as classificações (SINAN). O ano atual ainda está em andamento.</p>
      </div>
    </section>
  );
}
