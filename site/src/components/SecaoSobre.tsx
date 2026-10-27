import { CloudSun, Database, FileText, Map as MapaIcone, RefreshCw } from 'lucide-react';
import type { DadosSite } from '../lib/dados';
import { dataLonga } from '../lib/formato';
import { Revelar } from './Revelar';

const FONTES = [
  { Icone: Database, nome: 'Ministério da Saúde', texto: 'Casos de dengue, chikungunya, zika e acidentes com escorpião registrados no SINAN (DATASUS).' },
  { Icone: FileText, nome: 'Prefeitura de Goiânia', texto: 'Boletins semanais de dengue, levantamentos do mosquito (LIRAa) e o mapa oficial de bairros.' },
  { Icone: CloudSun, nome: 'INMET e InfoDengue', texto: 'Chuva, temperatura e umidade da estação de Goiânia; ritmo de transmissão (Fiocruz/FGV).' },
  { Icone: MapaIcone, nome: 'CNES e IBGE', texto: 'Cadastro das unidades de saúde, limites e saneamento por bairro (Censo 2022).' },
];

export function SecaoSobre({ dados }: { dados: DadosSite }) {
  return (
    <section id="sobre" className="secao sobre alternada">
      <div className="conteudo">
        <Revelar className="cabeca-secao">
          <p className="sobretitulo">Sobre os dados</p>
          <h2 className="titulo-secao">De onde vêm as informações</h2>
          <p className="lead">Tudo o que aparece aqui vem de dados públicos oficiais. Nada é inventado: quando um dado ainda não existe, o site mostra que ele está faltando.</p>
        </Revelar>
        <div className="fontes-grade">
          {FONTES.map((f, i) => (
            <Revelar key={f.nome} atraso={i * 0.06} className="fonte">
              <f.Icone size={22} aria-hidden="true" />
              <h3>{f.nome}</h3>
              <p>{f.texto}</p>
            </Revelar>
          ))}
        </div>
        <Revelar className="atualizacao">
          <RefreshCw size={20} aria-hidden="true" />
          <p>Os dados são atualizados toda semana. Esta versão usa registros até <strong>{dataLonga(dados.dados_ate)}</strong>. Os números das semanas mais recentes podem mudar, porque parte dos casos é registrada com atraso.</p>
          {/* O painel da equipe só existe no servidor local; no site publicado o link não aparece. */}
          {['localhost', '127.0.0.1'].includes(window.location.hostname) && <a className="botao" href="equipe/">Painel técnico da equipe</a>}
        </Revelar>
      </div>
    </section>
  );
}
