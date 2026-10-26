import { useState } from 'react';
import { AlertTriangle, Bug, Droplets, Footprints, Home, Package, Phone, Pill, Shirt, Thermometer, Trash2, Wind } from 'lucide-react';
import { Revelar } from './Revelar';

// Orientações do Ministério da Saúde para dengue e escorpiões, em linguagem simples.
const DICAS = {
  dengue: {
    titulo: 'Dengue',
    itens: [
      { Icone: Droplets, titulo: 'Sem água parada', texto: 'Vire garrafas, baldes e pneus. Coloque areia nos pratinhos de plantas.' },
      { Icone: Package, titulo: 'Caixa d’água tampada', texto: 'Mantenha caixas d’água, tonéis e cisternas sempre bem fechados.' },
      { Icone: Home, titulo: 'Calhas e ralos limpos', texto: 'Folhas acumuladas seguram água. Limpe calhas e mantenha ralos fechados.' },
      { Icone: Trash2, titulo: 'Lixo no lugar certo', texto: 'Feche os sacos de lixo e não deixe recipientes jogados no quintal.' },
    ],
    alerta: { titulo: 'Teve febre alta com dor no corpo, atrás dos olhos ou manchas na pele?', texto: 'Procure um posto de saúde e beba bastante líquido. Não tome remédio por conta própria, principalmente AAS e anti-inflamatórios.', urgente: 'Dor forte na barriga, vômitos que não param, sangramento ou tontura: vá a um pronto atendimento imediatamente.' },
  },
  escorpioes: {
    titulo: 'Escorpiões',
    itens: [
      { Icone: Trash2, titulo: 'Quintal sem entulho', texto: 'Tijolos, telhas e madeira empilhados viram esconderijo. Mantenha o quintal limpo.' },
      { Icone: Wind, titulo: 'Ralos e frestas vedados', texto: 'Use ralos com tampa e vede frestas em paredes, portas e rodapés.' },
      { Icone: Shirt, titulo: 'Sacuda antes de usar', texto: 'Roupas, toalhas e roupas de cama podem esconder escorpiões.' },
      { Icone: Footprints, titulo: 'Confira os calçados', texto: 'Bata os sapatos antes de calçar, principalmente os que ficam no chão.' },
    ],
    alerta: { titulo: 'Foi picado por escorpião?', texto: 'Lave o local com água e sabão e procure atendimento imediatamente, sobretudo se for criança ou idoso.', urgente: 'Não corte, não aperte, não amarre e não passe nada no local da picada.' },
  },
} as const;

export function SecaoPrevencao() {
  const [aba, setAba] = useState<keyof typeof DICAS>('dengue');
  const d = DICAS[aba];
  return (
    <section id="prevencao" className="secao prevencao">
      <div className="conteudo">
        <Revelar className="cabeca-secao">
          <p className="sobretitulo">Prevenção</p>
          <h2 className="titulo-secao centro">Como se proteger</h2>
          <div className="seletor" role="tablist" aria-label="Escolha o tema">
            {(Object.keys(DICAS) as (keyof typeof DICAS)[]).map(k => (
              <button key={k} role="tab" aria-selected={aba === k} onClick={() => setAba(k)}>
                {k === 'dengue' ? <Thermometer size={17} /> : <Bug size={17} />}{DICAS[k].titulo}
              </button>
            ))}
          </div>
        </Revelar>
        <div className="dicas-grade" role="tabpanel">
          {d.itens.map((it, i) => (
            <Revelar key={`${aba}-${it.titulo}`} atraso={i * 0.06} className="dica-cartao">
              <span className="dica-icone"><it.Icone size={24} aria-hidden="true" /></span>
              <h3>{it.titulo}</h3>
              <p>{it.texto}</p>
            </Revelar>
          ))}
        </div>
        <Revelar className="aviso-saude">
          <AlertTriangle size={26} aria-hidden="true" />
          <div>
            <h3>{d.alerta.titulo}</h3>
            <p>{d.alerta.texto}</p>
            <p className="urgente"><Pill size={16} aria-hidden="true" /> {d.alerta.urgente}</p>
          </div>
          <div className="aviso-telefones">
            <a href="tel:192"><Phone size={16} /> <b>192</b> SAMU</a>
            <a href="tel:136"><Phone size={16} /> <b>136</b> Disque Saúde</a>
          </div>
        </Revelar>
        <p className="nota centro">Orientações baseadas nas recomendações do Ministério da Saúde. Em caso de dúvida, procure a unidade de saúde mais próxima.</p>
      </div>
    </section>
  );
}
