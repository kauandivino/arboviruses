import { Bug, Building2, Activity } from 'lucide-react';
import type { DadosSite } from '../lib/dados';
import { numero } from '../lib/formato';
import { Revelar } from './Revelar';

export function Numeros({ dados }: { dados: DadosSite }) {
  const ano = dados.dengue.ano;
  const dengueAno = dados.dengue.anual.find(a => a.ano === ano)?.notificacoes ?? 0;
  const anoAnterior = dados.dengue.anual.find(a => a.ano === ano - 1)?.notificacoes;
  const escorpioesAno = dados.escorpioes.filter(e => e.mes.startsWith(String(ano))).reduce((s, e) => s + e.acidentes, 0);
  const itens = [
    { icone: Activity, valor: numero(dengueAno), titulo: `Casos de dengue notificados em ${ano}`, texto: anoAnterior ? `Em todo o ano de ${ano - 1} foram ${numero(anoAnterior)}.` : '' },
    { icone: Bug, valor: numero(escorpioesAno), titulo: `Acidentes com escorpião em ${ano}`, texto: 'Picadas registradas em Goiânia, até o último mês disponível.' },
    { icone: Building2, valor: numero(dados.contagens.unidades), titulo: 'Unidades públicas de saúde no mapa', texto: 'Postos, policlínicas, pronto atendimentos e hospitais.' },
  ];
  return (
    <section className="numeros" aria-label="Números principais">
      <div className="conteudo numeros-grade">
        {itens.map((it, i) => (
          <Revelar key={it.titulo} atraso={i * 0.08} className="numero-item">
            <it.icone size={22} className="numero-icone" aria-hidden="true" />
            <span className="numero grande">{it.valor}</span>
            <h3>{it.titulo}</h3>
            <p>{it.texto}</p>
          </Revelar>
        ))}
      </div>
    </section>
  );
}
