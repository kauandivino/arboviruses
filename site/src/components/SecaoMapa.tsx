import { lazy, Suspense } from 'react';
import type { DadosSite } from '../lib/dados';
import { useVisivel } from '../lib/formato';
import { Revelar } from './Revelar';

// O mapa (MapLibre) só é baixado quando a seção se aproxima da tela.
const Mapa = lazy(() => import('./Mapa'));

export function SecaoMapa({ dados }: { dados: DadosSite }) {
  const [ref, visivel] = useVisivel<HTMLDivElement>('600px');
  return (
    <section id="mapa" className="secao secao-mapa alternada">
      <div className="conteudo">
        <Revelar className="cabeca-secao">
          <p className="sobretitulo">Seu bairro</p>
          <h2 className="titulo-secao">Encontre seu bairro no mapa</h2>
          <p className="lead">Os boletins da Prefeitura listam, a cada semana, os bairros com mais casos de dengue. Quanto mais escuro o bairro, mais vezes ele apareceu nessas listas em {dados.boletins.ano}.</p>
        </Revelar>
      </div>
      <div ref={ref} className="conteudo largo">
        {visivel ? <Suspense fallback={<div className="mapa-moldura"><div className="mapa-carregando"><span className="carregando" /> Carregando o mapa…</div></div>}><Mapa dados={dados} /></Suspense>
          : <div className="mapa-moldura" />}
      </div>
    </section>
  );
}
