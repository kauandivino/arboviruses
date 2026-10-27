import { useDados } from './lib/dados';
import { Cabecalho } from './components/Cabecalho';
import { Heroi } from './components/Heroi';
import { Numeros } from './components/Numeros';
import { SecaoDengue } from './components/SecaoDengue';
import { SecaoChuva } from './components/SecaoChuva';
import { SecaoOutras } from './components/SecaoOutras';
import { SecaoEscorpioes } from './components/SecaoEscorpioes';
import { SecaoMapa } from './components/SecaoMapa';
import { SecaoProjeto } from './components/SecaoProjeto';
import { SecaoPrevencao } from './components/SecaoPrevencao';
import { SecaoSobre } from './components/SecaoSobre';
import { Rodape } from './components/Rodape';

export function App() {
  const { dados, erro } = useDados();
  if (erro) {
    return <main className="estado-carga"><p>Não foi possível carregar os dados agora. Tente atualizar a página em alguns instantes.</p></main>;
  }
  if (!dados) {
    return <main className="estado-carga" aria-busy="true"><span className="carregando" /><p>Carregando os dados de Goiânia…</p></main>;
  }
  return (
    <>
      <a className="pular" href="#mapa">Pular para o conteúdo</a>
      <Cabecalho />
      <main>
        <Heroi dados={dados} />
        <SecaoMapa dados={dados} />
        <Numeros dados={dados} />
        <SecaoDengue dados={dados} />
        <SecaoOutras dados={dados} />
        <SecaoChuva dados={dados} />
        <SecaoEscorpioes dados={dados} />
        <SecaoProjeto dados={dados} />
        <SecaoPrevencao />
        <SecaoSobre dados={dados} />
      </main>
      <Rodape dados={dados} />
    </>
  );
}
