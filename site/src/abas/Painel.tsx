import { ArrowDownRight, ArrowRight, ArrowUpRight, Bug, CloudRain, Activity, Thermometer, Waves, Target } from 'lucide-react';
import type { DadosSite } from '../lib/dados';
import { linkAba, type Aba } from '../lib/abas';
import { dataLonga, decimal, mesLongo, numero } from '../lib/formato';
import { SITUACOES } from '../lib/situacao';
import { GraficoIntegrado } from '../components/GraficoIntegrado';
import { Achados } from '../components/Achados';
import { MapaCompacto } from '../components/MapaCompacto';
import { Revelar } from '../components/Revelar';

type Cartao = { aba: Aba; Icone: typeof Bug; tema: string; titulo: string; cor: string; valor: string; detalhe: string; tendencia?: 'sobe' | 'desce' | null };

function cartoes(d: DadosSite): Cartao[] {
  const s = d.dengue.situacao, info = SITUACOES[s.zona];
  const chikAno = d.outras_arboviroses.chikungunya.anual;
  const chikAtual = chikAno.at(-1)!, chikAnt = chikAno.at(-2)!;
  const liraa = d.liraa.at(-1)!;
  const rt = d.transmissao.semanas.length > 1 ? d.transmissao.semanas.at(-2)! : d.transmissao.semanas[0];
  const climaRecente = [...d.clima].reverse().find(c => c.cobertura_pct >= 90 && c.chuva_mm != null)!;
  const mesmoMes = d.clima.filter(c => c.mes.slice(5) === climaRecente.mes.slice(5) && c.mes < climaRecente.mes && c.cobertura_pct >= 90 && c.chuva_mm != null);
  const mediaMes = mesmoMes.length ? mesmoMes.reduce((a, c) => a + (c.chuva_mm ?? 0), 0) / mesmoMes.length : null;
  const esc = d.escorpioes_modelo.previsao[0];
  const liraaCor = { baixo: 'var(--acento-forte)', medio: 'var(--zona-acima)', alto: 'var(--zona-alerta)' }[liraa.situacao] ?? 'var(--tinta)';
  return [
    { aba: 'dengue', Icone: Thermometer, tema: 'Dengue', titulo: info.titulo, cor: info.cor === 'var(--zona-habitual)' || info.cor === 'var(--zona-abaixo)' ? 'var(--acento-forte)' : info.cor,
      valor: numero(s.ultimas_4_semanas), detalhe: 'casos nas últimas 4 semanas', tendencia: s.tendencia === 'subindo' ? 'sobe' : s.tendencia === 'caindo' ? 'desce' : null },
    { aba: 'arboviroses', Icone: Waves, tema: 'Chikungunya', titulo: chikAtual.notificacoes > chikAnt.notificacoes ? 'Mais casos que em ' + chikAnt.ano : 'Menos casos que em ' + chikAnt.ano,
      cor: '#c27a2e', valor: numero(chikAtual.notificacoes), detalhe: `casos em ${chikAtual.ano} (${numero(chikAnt.notificacoes)} em todo ${chikAnt.ano})` },
    { aba: 'mosquito', Icone: Bug, tema: 'Mosquito', titulo: { baixo: 'Baixo risco', medio: 'Médio risco', alto: 'Alto risco' }[liraa.situacao] ?? liraa.situacao, cor: liraaCor,
      valor: `${decimal(liraa.iip)}%`, detalhe: `dos imóveis com o mosquito (${mesLongo(liraa.fim)} de ${liraa.fim.slice(0, 4)})` },
    { aba: 'mosquito', Icone: Activity, tema: 'Transmissão', titulo: rt.p_rt1 >= 0.5 ? 'Em alta' : 'Em queda', cor: rt.p_rt1 >= 0.5 ? 'var(--zona-alerta)' : 'var(--acento-forte)',
      valor: decimal(rt.rt, 2), detalhe: 'pessoas infectadas por cada caso (Rt)', tendencia: rt.p_rt1 >= 0.5 ? 'sobe' : 'desce' },
    { aba: 'mosquito', Icone: CloudRain, tema: 'Chuva', titulo: mediaMes == null ? mesLongo(climaRecente.mes) : (climaRecente.chuva_mm ?? 0) > mediaMes * 1.2 ? 'Acima da média' : (climaRecente.chuva_mm ?? 0) < mediaMes * 0.8 ? 'Abaixo da média' : 'Na média',
      cor: 'var(--chuva)', valor: `${numero(climaRecente.chuva_mm)} mm`, detalhe: `em ${mesLongo(climaRecente.mes)}${mediaMes != null ? ` (média ${numero(mediaMes)} mm)` : ''}` },
    esc ? { aba: 'escorpioes', Icone: Target, tema: 'Escorpiões', titulo: 'Previsão', cor: 'var(--escorpiao)', valor: `~${numero(esc.previsto)}`,
      detalhe: `acidentes em ${mesLongo(esc.mes)} (entre ${numero(esc.faixa_80pct[0])} e ${numero(esc.faixa_80pct[1])})` }
      : escorpioesUltimo(d),
  ];
}

function escorpioesUltimo(d: DadosSite): Cartao {
  const serie = d.escorpioes_modelo.serie, ult = serie.at(-1)!;
  const anteriores = serie.filter(s => s.mes.slice(5) === ult.mes.slice(5) && s.mes < ult.mes).slice(-3);
  const media = anteriores.length ? anteriores.reduce((a, s) => a + s.acidentes, 0) / anteriores.length : null;
  const titulo = media == null ? 'Último mês' : ult.acidentes > media * 1.15 ? 'Acima do habitual' : ult.acidentes < media * 0.85 ? 'Abaixo do habitual' : 'Dentro do habitual';
  return { aba: 'escorpioes', Icone: Target, tema: 'Escorpiões', titulo, cor: 'var(--escorpiao)', valor: numero(ult.acidentes),
    detalhe: `acidentes em ${mesLongo(ult.mes)}${media != null ? ` (média ${numero(Math.round(media))} nos 3 anos anteriores)` : ''}` };
}

export function Painel({ dados }: { dados: DadosSite }) {
  return (
    <>
      <section className="painel-topo">
        <div className="conteudo">
          <p className="sobretitulo">Goiânia · dados até {dataLonga(dados.dados_ate)}</p>
          <h1 className="painel-titulo">Painel de monitoramento</h1>
          <div className="status-grade">
            {cartoes(dados).map((c, i) => (
              <Revelar key={c.tema} atraso={i * 0.04}>
                <a href={linkAba(c.aba)} className="cartao status" style={{ ['--cor' as string]: c.cor }}>
                  <span className="status-tema"><c.Icone size={15} aria-hidden="true" />{c.tema}</span>
                  <strong className="status-titulo">{c.titulo}</strong>
                  <span className="status-valor numero">{c.valor}{c.tendencia === 'sobe' ? <ArrowUpRight size={20} /> : c.tendencia === 'desce' ? <ArrowDownRight size={20} /> : null}</span>
                  <span className="status-detalhe">{c.detalhe}</span>
                  <ArrowRight size={15} className="status-seta" aria-hidden="true" />
                </a>
              </Revelar>
            ))}
          </div>
        </div>
      </section>
      <section className="secao painel-corpo">
        <div className="conteudo">
          <Revelar><GraficoIntegrado dados={dados} /></Revelar>
          <Revelar className="cabeca-secao compacta">
            <h2 className="titulo-secao">O que os dados mostram</h2>
          </Revelar>
          <Achados dados={dados} />
          <Revelar><MapaCompacto edicoes={dados.boletins.edicoes.length} /></Revelar>
        </div>
      </section>
    </>
  );
}
