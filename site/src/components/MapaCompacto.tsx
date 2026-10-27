import { useEffect, useMemo, useState } from 'react';
import { ArrowRight } from 'lucide-react';
import { linkAba } from '../lib/abas';
import { useLargura } from '../lib/formato';

type Feicao = { geometry: { type: 'Polygon' | 'MultiPolygon'; coordinates: number[][][] | number[][][][] }; properties: { oid: number; nome: string; citacoes: number; territorio: number | null; lon: number; lat: number } };
const COR = (n: number) => (n === 0 ? '#eef1ef' : n < 6 ? '#bfe8e2' : n < 14 ? '#5fc4b7' : n < 20 ? '#20a597' : '#0b4f49');

/** Mapa leve em SVG (sem mapa de ruas): bairros pela presença nos boletins e os oito territórios. */
export function MapaCompacto({ edicoes }: { edicoes: number }) {
  const [ref, largura] = useLargura<HTMLDivElement>(500);
  const [bairros, setBairros] = useState<Feicao[]>([]);
  const [foco, setFoco] = useState<Feicao | null>(null);
  useEffect(() => { fetch('dados/bairros.geojson').then(r => r.json()).then(g => setBairros(g.features)); }, []);
  const { caminhos, altura, projetar } = useMemo(() => {
    if (!bairros.length) return { caminhos: [], altura: 300, projetar: (_: number[]) => [0, 0] };
    const anel = (g: Feicao['geometry']) => (g.type === 'Polygon' ? [g.coordinates as number[][][]] : (g.coordinates as number[][][][]));
    const pts = bairros.flatMap(b => anel(b.geometry).flat(2) as unknown as number[][]);
    const xs = pts.map(p => p[0]), ys = pts.map(p => p[1]);
    const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
    const k = Math.cos(((y0 + y1) / 2) * Math.PI / 180);
    // Altura limitada para o mapa não dominar a página; centralizado na largura disponível.
    const escala = Math.min(largura / ((x1 - x0) * k), 460 / (y1 - y0));
    const altura = (y1 - y0) * escala, dx = (largura - (x1 - x0) * k * escala) / 2;
    const projetar = (p: number[]) => [dx + (p[0] - x0) * k * escala, (y1 - p[1]) * escala];
    const caminhos = bairros.map(b => ({ b, d: anel(b.geometry).map(poli => poli.map(r => 'M' + r.map(p => projetar(p).map(v => v.toFixed(1)).join(',')).join('L') + 'Z').join('')).join('') }));
    return { caminhos, altura, projetar };
  }, [bairros, largura]);
  const ranking = [...bairros].sort((a, b) => b.properties.citacoes - a.properties.citacoes).slice(0, 8);
  return (
    <div className="cartao mapa-compacto">
      <div className="grafico-topo">
        <h3 className="titulo-cartao">Bairros nos boletins de dengue</h3>
        <a className="link-seta" href={linkAba('bairro')}>Ver no mapa completo <ArrowRight size={15} /></a>
      </div>
      <div className="mapa-compacto-corpo">
      <div ref={ref} className="grafico-area">
        {caminhos.length > 0 ? (
          <svg width={largura} height={altura} role="img" aria-label="Mapa dos bairros de Goiânia coloridos pela presença nos boletins de dengue" onPointerLeave={() => setFoco(null)}>
            {caminhos.map(({ b, d }) => <path key={b.properties.oid} d={d} fill={COR(b.properties.citacoes)} stroke="#fff" strokeWidth={0.4}
              onPointerEnter={() => setFoco(b)} className={foco === b ? 'bairro-foco' : undefined} />)}
            {caminhos.filter(({ b }) => b.properties.territorio).map(({ b }) => {
              const [x, y] = projetar([b.properties.lon, b.properties.lat]);
              return <g key={`t${b.properties.oid}`} transform={`translate(${x},${y})`} className="tri-mini"><path d="M-9,-14 L9,-14 L0,1 Z" /><text y={-7} textAnchor="middle">{b.properties.territorio}</text></g>;
            })}
          </svg>
        ) : <div className="mapa-carregando estatico"><span className="carregando" /></div>}
        {foco && <div className="dica" style={{ left: 12, top: 12 }} role="status"><strong>{foco.properties.nome}</strong>
          <span>{foco.properties.citacoes ? `Em ${foco.properties.citacoes} de ${edicoes} boletins` : 'Não apareceu entre os bairros com mais casos'}</span></div>}
      </div>
      {ranking.length > 0 && (
        <ol className="ranking-bairros" aria-label="Bairros que mais apareceram nos boletins">
          <li className="ranking-cabeca"><span>Mais citados</span><span>boletins</span></li>
          {ranking.map(b => (
            <li key={b.properties.oid} onPointerEnter={() => setFoco(b)} onPointerLeave={() => setFoco(null)} className={foco === b ? 'ativo' : undefined}>
              <span className="ranking-nome">{b.properties.nome}{b.properties.territorio ? <i className="amostra triangulo" title="Território do projeto" /> : null}</span>
              <span className="ranking-barra"><i style={{ width: `${(100 * b.properties.citacoes) / edicoes}%` }} /></span>
              <span className="numero">{b.properties.citacoes}</span>
            </li>
          ))}
        </ol>
      )}
      </div>
      <div className="legenda mapa-legenda">
        <span><i className="leg-quadrado" style={{ background: '#eef1ef', border: '1px solid var(--linha)' }} /> Não citado</span>
        <span><i className="leg-quadrado" style={{ background: '#bfe8e2' }} /> Poucas vezes</span>
        <span><i className="leg-quadrado" style={{ background: '#0b4f49' }} /> Quase todas</span>
        <span><i className="amostra triangulo" /> Território do projeto</span>
      </div>
    </div>
  );
}
