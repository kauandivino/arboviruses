import { Phone } from 'lucide-react';
import type { DadosSite } from '../lib/dados';
import { ABAS, linkAba } from '../lib/abas';
import { dataLonga } from '../lib/formato';
import { Marca } from './Cabecalho';

export function Rodape({ dados }: { dados: DadosSite }) {
  return (
    <footer className="rodape">
      <div className="faixa-acento" aria-hidden="true" />
      <div className="conteudo rodape-grade">
        <div>
          <Marca claro />
          <p>Monitoramento de dengue, chikungunya, zika e escorpiões em Goiânia com dados públicos oficiais. Projeto do programa Embaixadores da Cidadania 2026.</p>
        </div>
        <nav aria-label="Abas do site">
          <h3>Abas</h3>
          {ABAS.map(a => <a key={a.id} href={linkAba(a.id)}>{a.rotulo}</a>)}
        </nav>
        <div>
          <h3>Emergência</h3>
          <a href="tel:192"><Phone size={14} /> SAMU · 192</a>
          <a href="tel:136"><Phone size={14} /> Disque Saúde · 136</a>
          <a href={linkAba('bairro')}>Unidades de saúde no mapa</a>
        </div>
      </div>
      <div className="conteudo rodape-base">
        <span>Dados até {dataLonga(dados.dados_ate)}</span>
        <span>Fontes: Ministério da Saúde (SINAN/DATASUS), Prefeitura de Goiânia, InfoDengue, INMET, CNES e IBGE</span>
      </div>
    </footer>
  );
}
