import { useDados } from './lib/dados';
import { useAba } from './lib/abas';
import { Cabecalho } from './components/Cabecalho';
import { Rodape } from './components/Rodape';
import { Painel } from './abas/Painel';
import { AbaArboviroses, AbaBairro, AbaDengue, AbaEscorpioes, AbaMosquito, AbaPrevencao, AbaSobre } from './abas/Abas';

export function App() {
  const { dados, erro } = useDados();
  const aba = useAba();
  if (erro) {
    return <main className="estado-carga"><p>Não foi possível carregar os dados agora. Tente atualizar a página em alguns instantes.</p></main>;
  }
  if (!dados) {
    return <main className="estado-carga" aria-busy="true"><span className="carregando" /><p>Carregando os dados de Goiânia…</p></main>;
  }
  return (
    <>
      <a className="pular" href="#conteudo">Pular para o conteúdo</a>
      <Cabecalho aba={aba} />
      <main id="conteudo" key={aba}>
        {aba === 'painel' && <Painel dados={dados} />}
        {aba === 'dengue' && <AbaDengue dados={dados} />}
        {aba === 'arboviroses' && <AbaArboviroses dados={dados} />}
        {aba === 'mosquito' && <AbaMosquito dados={dados} />}
        {aba === 'escorpioes' && <AbaEscorpioes dados={dados} />}
        {aba === 'bairro' && <AbaBairro dados={dados} />}
        {aba === 'prevencao' && <AbaPrevencao />}
        {aba === 'sobre' && <AbaSobre dados={dados} />}
      </main>
      <Rodape dados={dados} />
    </>
  );
}
