import type { ReactNode } from 'react';
import { CheckCircle2, CircleSlash } from 'lucide-react';
import type { DadosSite } from '../lib/dados';
import { GraficoAnual, GraficoTemporada } from '../components/SecaoDengue';
import { Sorotipos } from '../components/Sorotipos';
import { Barras } from '../components/SecaoOutras';
import { Liraa, Rt } from '../components/MosquitoTransmissao';
import { ChuvaMensal } from '../components/SecaoChuva';
import { EmergenciaEscorpiao, EscorpioesAno } from '../components/SecaoEscorpioes';
import { SecaoMapa } from '../components/SecaoMapa';
import { SecaoProjeto } from '../components/SecaoProjeto';
import { SecaoPrevencao } from '../components/SecaoPrevencao';
import { SecaoSobre } from '../components/SecaoSobre';
import { CorrelacaoClima, EpocaEscorpioes, EscorpioesHistorico, Internacoes, LinhasRelativas } from '../components/GraficosAbas';
import { Revelar } from '../components/Revelar';
import { numero } from '../lib/formato';

function CabecaAba({ sobre, titulo, lead }: { sobre: string; titulo: string; lead: string }) {
  return (
    <section className="aba-topo">
      <div className="conteudo">
        <p className="sobretitulo">{sobre}</p>
        <h1 className="aba-titulo">{titulo}</h1>
        <p className="lead">{lead}</p>
      </div>
    </section>
  );
}

function Corpo({ children }: { children: ReactNode }) {
  return <section className="secao aba-corpo"><div className="conteudo">{children}</div></section>;
}

const Dupla = ({ children }: { children: ReactNode }) => <div className="dupla">{children}</div>;

export function AbaDengue({ dados }: { dados: DadosSite }) {
  const v = dados.correlacoes.vizinhos;
  return (
    <>
      <CabecaAba sobre="Dengue" titulo="Dengue em Goiânia" lead="A temporada atual comparada com o habitual, a região, os tipos de vírus e as internações." />
      <Corpo>
        <Revelar><GraficoTemporada dados={dados} /></Revelar>
        <Revelar><LinhasRelativas semanal={dados.semanal} titulo="Goiânia e região"
          series={[{ chave: 'goiania', rotulo: 'Goiânia', cor: 'var(--acento-forte)' }, { chave: 'vizinhos', rotulo: '10 cidades vizinhas', cor: 'var(--chuva)' }, { chave: 'resto_go', rotulo: 'Resto de Goiás', cor: '#9aa6ab' }]}
          nota={`Cada linha está na proporção do próprio pico, para comparar o formato. O pico veio na mesma semana em ${v.juntos} de ${v.temporadas} temporadas desde 2015. Área cinza: semanas recentes, ainda incompletas.`} /></Revelar>
        <Dupla>
          <Revelar><Sorotipos dados={dados} /></Revelar>
        </Dupla>
        <Dupla>
          <Revelar><Internacoes dados={dados} /></Revelar>
          <Revelar><GraficoAnual dados={dados} /></Revelar>
        </Dupla>
      </Corpo>
    </>
  );
}

export function AbaArboviroses({ dados }: { dados: DadosSite }) {
  const chik = dados.correlacoes.chikungunya;
  return (
    <>
      <CabecaAba sobre="Chikungunya e Zika" titulo="Outras doenças do mosquito" lead="Transmitidas pelo mesmo Aedes aegypti. A prevenção é a mesma da dengue." />
      <Corpo>
        <Dupla>
          <Revelar><Barras agravo="chikungunya" dados={dados.outras_arboviroses.chikungunya} /></Revelar>
          <Revelar><Barras agravo="zika" dados={dados.outras_arboviroses.zika} /></Revelar>
        </Dupla>
        <p className="nota">Casos notificados de residentes em Goiânia por ano de início dos sintomas, todas as classificações (SINAN). O ano atual ainda está em andamento.</p>
        <Revelar><LinhasRelativas semanal={dados.semanal} titulo="Chikungunya e dengue nos últimos 2 anos"
          series={[{ chave: 'goiania', rotulo: 'Dengue', cor: 'var(--acento-forte)' }, { chave: 'chikungunya', rotulo: 'Chikungunya', cor: '#c27a2e' }]}
          nota={`Cada linha na proporção do próprio pico. Em ${chik.depois} das ${chik.temporadas} temporadas recentes com mais casos, a chikungunya chegou ao pico cerca de ${numero(chik.mediana_semanas)} semanas depois da dengue.`} /></Revelar>
      </Corpo>
    </>
  );
}

export function AbaMosquito({ dados }: { dados: DadosSite }) {
  return (
    <>
      <CabecaAba sobre="Mosquito e clima" titulo="O mosquito, a transmissão e o clima" lead="Onde está o Aedes, quão rápido a dengue se espalha e como a chuva, o calor e a umidade se relacionam com os casos." />
      <Corpo>
        <Dupla>
          {dados.liraa.length > 0 && <Revelar><Liraa ciclos={dados.liraa} /></Revelar>}
          {dados.transmissao.semanas.length > 0 && <Revelar><Rt t={dados.transmissao} /></Revelar>}
        </Dupla>
        <Revelar><CorrelacaoClima c={dados.correlacoes.clima_dengue} /></Revelar>
        <Revelar><ChuvaMensal dados={dados} /></Revelar>
      </Corpo>
    </>
  );
}

export function AbaEscorpioes({ dados }: { dados: DadosSite }) {
  return (
    <>
      <CabecaAba sobre="Escorpiões" titulo="Acidentes com escorpião" lead={`Quantos acontecem${dados.escorpioes_modelo.exibida ? ', em que época e quantos são esperados nos próximos meses' : ' e em que época'}. Eles se escondem em entulho, ralos e frestas.`} />
      <Corpo>
        <Revelar><EmergenciaEscorpiao /></Revelar>
        <Revelar><EscorpioesHistorico m={dados.escorpioes_modelo} /></Revelar>
        <Dupla>
          <Revelar><EscorpioesAno dados={dados} /></Revelar>
          <Revelar><EpocaEscorpioes perfil={dados.correlacoes.escorpioes.perfil_mensal} /></Revelar>
        </Dupla>
      </Corpo>
    </>
  );
}

export function AbaBairro({ dados }: { dados: DadosSite }) {
  return <><SecaoMapa dados={dados} /><SecaoProjeto dados={dados} /></>;
}

export function AbaPrevencao() {
  return <SecaoPrevencao />;
}

export function AbaSobre({ dados }: { dados: DadosSite }) {
  return (
    <>
      <SecaoSobre dados={dados} />
      <Corpo>
        <Revelar className="cabeca-secao compacta"><h2 className="titulo-secao">Modelos testados</h2>
          <p className="lead">Cada modelo foi testado em anos que ele não viu. Só aparece no site o que acertou mais que regras simples, como repetir as semanas anteriores.</p></Revelar>
        <div className="modelos-grade">
          {dados.modelos.map(m => (
            <Revelar key={m.nome} className={`cartao modelo ${m.status}`}>
              <span className="modelo-status">{m.status === 'em_uso' ? <><CheckCircle2 size={16} /> No site</> : <><CircleSlash size={16} /> Não passou no teste</>}</span>
              <h3>{m.nome}</h3>
              <p className="modelo-pergunta">{m.pergunta}</p>
              <p>{m.resultado}</p>
            </Revelar>
          ))}
        </div>
      </Corpo>
    </>
  );
}
