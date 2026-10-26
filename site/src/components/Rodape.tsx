import { Phone } from 'lucide-react';
import type { DadosSite } from '../lib/dados';
import { dataLonga } from '../lib/formato';
import { Marca, SECOES } from './Cabecalho';

export function Rodape({ dados }: { dados: DadosSite }) {
  return (
    <footer className="rodape">
      <div className="faixa-acento" aria-hidden="true" />
      <div className="conteudo rodape-grade">
        <div>
          <Marca claro />
          <p>Informação clara sobre dengue e escorpiões em Goiânia, feita a partir de dados públicos oficiais. Projeto do programa Embaixadores da Cidadania 2026.</p>
        </div>
        <nav aria-label="Seções do site">
          <h3>Seções</h3>
          {SECOES.map(s => <a key={s.id} href={`#${s.id}`}>{s.rotulo}</a>)}
          <a href="#projeto">O projeto</a>
        </nav>
        <div>
          <h3>Emergência</h3>
          <a href="tel:192"><Phone size={14} /> SAMU · 192</a>
          <a href="tel:136"><Phone size={14} /> Disque Saúde · 136</a>
          <a href="#mapa">Unidades de saúde no mapa</a>
        </div>
      </div>
      <div className="conteudo rodape-base">
        <span>Dados até {dataLonga(dados.dados_ate)}</span>
        <span>Fontes: Ministério da Saúde (SINAN/DATASUS), Prefeitura de Goiânia, INMET, CNES e IBGE</span>
      </div>
    </footer>
  );
}
