import { CalendarCheck, Users, MapPinned } from 'lucide-react';
import type { DadosSite } from '../lib/dados';
import { dataLonga, numero } from '../lib/formato';
import { Revelar } from './Revelar';

export function SecaoProjeto({ dados }: { dados: DadosSite }) {
  const a = dados.acoes;
  return (
    <section id="projeto" className="secao">
      <div className="conteudo">
        <Revelar className="cabeca-secao centro-mobile">
          <p className="sobretitulo">O projeto nos bairros</p>
          <h2 className="titulo-secao">Oito territórios para começar</h2>
          <p className="lead">O projeto Saúde no Território vai levar encontros educativos a oito territórios de Goiânia, junto com as unidades de saúde de cada região. Eles foram escolhidos por aparecerem com frequência nos boletins de dengue de {dados.boletins.ano}.</p>
        </Revelar>
        <div className="territorios-grade">
          {dados.territorios.map((t, i) => (
            <Revelar key={t.oid} atraso={i * 0.05} className="territorio">
              <span className="territorio-numero" aria-hidden="true">{t.ordem}</span>
              <h3>{t.nome}</h3>
              <p className="territorio-parceiro">com {t.parceiro}</p>
              <div className="territorio-barra" aria-label={`Apareceu em ${t.citacoes} de ${t.listas} listas recentes`}>
                {Array.from({ length: t.listas }, (_, k) => <i key={k} className={k < t.citacoes ? 'cheia' : ''} />)}
              </div>
              <p className="nota">Em {t.citacoes} de {t.listas} listas recentes de bairros com mais casos</p>
              <p className={`territorio-status${t.acoes_realizadas ? ' feito' : ''}`}>
                {t.acoes_realizadas ? `${t.acoes_realizadas} ${t.acoes_realizadas === 1 ? 'ação realizada' : 'ações realizadas'}` : 'Ações em preparação'}
              </p>
            </Revelar>
          ))}
        </div>
        <Revelar className="acoes-resumo cartao">
          {[
            { Icone: CalendarCheck, valor: a.realizadas, rotulo: 'ações realizadas' },
            { Icone: Users, valor: a.participantes, rotulo: 'pessoas participaram' },
            { Icone: MapPinned, valor: a.territorios, rotulo: 'territórios com ações' },
          ].map(({ Icone, valor, rotulo }) => (
            <div key={rotulo}><Icone size={22} aria-hidden="true" /><span className="numero">{numero(valor)}</span><span>{rotulo}</span></div>
          ))}
          <p className="nota">{a.realizadas ? `Última ação registrada em ${dataLonga(a.lista[0].data)}.` : 'Nenhuma ação foi realizada ainda. Os números aparecem aqui assim que a equipe registrar cada atividade.'}</p>
        </Revelar>
      </div>
    </section>
  );
}
