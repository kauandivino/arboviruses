import { lazy, Suspense } from 'react';
import type { DadosSite } from '../lib/dados';
import { useVisivel } from '../lib/formato';
import { Revelar } from './Revelar';

// O mapa (MapLibre) só é baixado quando a seção se aproxima da tela.
const Mapa = lazy(() => import('./Mapa'));

export function SecaoMapa({ dados }: { dados: DadosSite }) {
  const [ref, visivel] = useVisivel<HTMLDivElement>('600px');
  return (
    <section id="mapa" className="secao secao-mapa">
      <div className="conteudo">
        <Revelar className="cabeca-secao">
          <p className="sobretitulo">Seu bairro</p>
          <h2 className="titulo-secao">Encontre seu bairro no mapa</h2>
          <p className="lead">Digite o nome do seu bairro para ver as unidades de saúde mais perto e se ele aparece nos boletins de dengue da Prefeitura. Quanto mais escuro o bairro no mapa, mais vezes ele esteve entre os de mais casos em {dados.boletins.ano}.</p>
        </Revelar>
      </div>
      <div ref={ref} className="conteudo largo">
        {visivel ? <Suspense fallback={<div className="mapa-moldura"><div className="mapa-carregando"><span className="carregando" /> Carregando o mapa…</div></div>}><Mapa dados={dados} /></Suspense>
          : <div className="mapa-moldura" />}
      </div>
    </section>
  );
}
