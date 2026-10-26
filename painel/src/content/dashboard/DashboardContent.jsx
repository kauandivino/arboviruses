import React from 'react';
import { EvidenceChart, DataComponent, DataTable, Filters, Section, MetricCard, SortableRegion, SortableItem, useDashboardTabs, useDataApp } from '../../data-app-public.jsx';
import { CartaoMapa } from './MapaTerritorios.jsx';
import { AcoesCampo } from './AcoesCampo.jsx';
import { NowcastDengue, PrevisaoDengue } from './GraficoNowcast.jsx';
import './dashboard.css';
const tabs = [
 {id:'municipal',label:'Evolução municipal',filterIds:['ano']},
 {id:'territorios',label:'Bairros nos informes',filterIds:['edicao','agravo','indicador']},
 {id:'clima',label:'Clima',filterIds:['ano']},
 {id:'parceiros',label:'Unidades de saúde',filterIds:[]}
 ,{id:'mapa',label:'Mapa',filterIds:[]}
 ,{id:'atuacao',label:'Plano de atuação',filterIds:[]}
 ,{id:'acoes',label:'Ações de campo',filterIds:[]}
];
const number = v => v == null ? 'Sem dado' : new Intl.NumberFormat('pt-BR').format(v);
const col = (field,label) => ({field,label});
const alerts = {
 confirmar_criterio_edicao19:'A edição SE19/2026 apresenta variação acentuada; o critério da publicação precisa de esclarecimento.',
 rotulo_truncado_na_fonte:'Há nome de bairro truncado na fonte; a identificação permanece pendente.',
 mesma_sequencia_valores_com_rotulos_diferentes_37_38:'As edições SE37 e SE38/2026 repetem a sequência de valores com bairros diferentes. Os valores publicados foram preservados e a comparabilidade permanece pendente.',
 confirmados_maiores_que_provaveis_no_quadro_publicado:'O quadro publicado apresenta confirmados maiores que prováveis em algumas linhas. Cabeçalhos e valores foram preservados.'
};
const line = (y,label) => ({type:'line',x:'data',y,stackable:false,startAtZero:true,legend:{labels:{[y]:label}},valueDecimals:0});
function Chart({id,queryId,title,rows,sourceRows,spec,height=300,...rest}) {
 return <EvidenceChart id={id} queryId={queryId} title={title} variant="card" rows={rows} displayRows={rows} sourceRows={sourceRows ?? rows} spec={spec} height={height} {...rest}/>;
}
function Table({id,queryId,title,rows,columns,...rest}) {
 return <DataComponent id={id} queryId={queryId} title={title} kind="table" variant="card" sourceRows={rows} displayRows={rows} {...rest}><DataTable rows={rows} columns={columns} caption={title}/></DataComponent>;
}
function Notice({children}) {return <p className="st-note">{children}</p>;}
export function DashboardContent() {
 const {queries,snapshot,filters,setFilter} = useDataApp();
 const {activeTabId} = useDashboardTabs(tabs);
 const tab = tabs.find(t=>t.id===activeTabId) ?? tabs[0];
 const all = id => queries[id]?.rows ?? [];
 const ano = filters.ano ?? '2026';
 const mensal = all('municipal').filter(r=>ano==='all'||String(r.ano)===ano);
 const clima = all('clima').filter(r=>ano==='all'||String(r.ano)===ano);
 const censo = all('censo');
 const territorios = all('territorios').filter(r=>['edicao','agravo','indicador'].every(k=>!filters[k]||filters[k]==='all'||String(r[k])===String(filters[k])));
 const unitario = ['edicao','agravo','indicador'].every(k=>new Set(territorios.map(r=>r[k])).size===1);
 return <div className="st-page">
 <Filters sticky filters={snapshot.filters.filter(f=>tab.filterIds.includes(f.id))} queries={queries} values={filters} onChange={setFilter} clearLabel="Limpar filtros"/>
 {tab.id==='municipal' && <>
 <Notice>Registros de dengue por residência e mês da notificação; escorpiões por ocorrência e mês do acidente. Todas as classificações. Em 2026, dengue tem registros até outubro e escorpiões até agosto. Os meses recentes podem estar incompletos; uma queda no fim da série exige cautela.</Notice>
 <NowcastDengue rows={all('nowcast')} avaliacao={all('nowcast_avaliacao')}/>
 <PrevisaoDengue rows={all('previsao')} avaliacao={all('previsao_avaliacao')}/>
 <SortableRegion id="saude:municipal" variant="canvas" spacing="standard" columns={12} rows={[{id:'municipal:trends',items:['dengue-serie','escorpioes-serie']}]}>
 {['dengue','escorpioes'].map(agravo=>{const rows=mensal.filter(r=>r.agravo===agravo); return <SortableItem key={agravo} id={`${agravo}-serie`} span={6} label={agravo}>
 <Chart id={`${agravo}-serie`} queryId="municipal" title={agravo==='dengue'?'Dengue · registros mensais':'Escorpiões · registros mensais'} rows={rows} spec={line('n_registros','Registros')} description={rows.length?`Meses com registros: ${rows[0].mes} a ${rows.at(-1).mes}. Mês presente não comprova completude; ausência não é zero.`:'Nenhum mês disponível para esta seleção.'}/>
 </SortableItem>;})}
 </SortableRegion>
 <Section id="municipal:detail-title" title="Períodos e situação da fonte">
 <Table id="municipal-detalhe" queryId="municipal" title="Registros por mês e agravo" rows={mensal} columns={[col('mes','Mês'),col('agravo','Agravo'),col('n_registros','Registros'),col('recorte_legivel','Recorte geográfico'),col('data_legivel','Data de referência'),col('situacao_legivel','Situação da fonte')]}/>
 </Section>
 <Section id="censo:context-title" title="Contexto populacional"><MetricCard id="populacao-censo" queryId="censo" title="População · Censo 2022" value={number(censo[0]?.populacao_censo)} sourceRows={censo} displayRows={censo} description="População medida em 2022. Não é estimativa de 2026 nem denominador territorial por bairro."/></Section>
 </>}
 {tab.id==='territorios' && <>
 <Notice>Listas publicadas nos informes: ausência de bairro não significa zero. Valores de edições diferentes não são somados. A correspondência com a malha municipal é nominal e não permite taxas por bairro.</Notice>
 {[...new Set(territorios.flatMap(r=>(r.alertas_fonte ?? '').split(';')).filter(Boolean))].map(a=><Notice key={a}>{alerts[a] ?? a.replaceAll('_',' ')}</Notice>)}
 {!territorios.length?<p className="st-empty" role="status">Nenhuma observação para essa combinação. Selecione outra publicação, agravo ou indicador.</p>:<>
 {unitario?<><Notice>{territorios[0].titulo_original} · Página {territorios[0].pagina}. {territorios.some(r=>r.status_periodo!=='janela_declarada_na_fonte')?'O período possui pendência na fonte; consulte os alertas abaixo.':''}</Notice>
 <Chart id="bairros-publicacao" queryId="territorios" title="Valores na lista publicada" rows={territorios} spec={{type:'horizontalBar',x:'bairro_rotulo_revisado',y:'valor_revisado',startAtZero:true,stackable:false,valueDecimals:0}} height={420}/></>:<Notice>Selecione uma publicação, um agravo e um indicador para visualizar o gráfico. A tabela mantém as observações separadas.</Notice>}
 <Section id="territorios:detail-title" title="Conferência e origem"><Table id="territorios-detalhe" queryId="territorios" title="Bairros citados e correspondência territorial" rows={territorios} columns={[col('edicao','Publicação'),col('bairro_rotulo_revisado','Bairro na fonte'),col('valor_revisado','Valor'),col('situacao_periodo_legivel','Período'),col('correspondencia_legivel','Correspondência'),col('nome_siggo_candidato','Nome SIGGO candidato'),{field:'url_pagina',label:'Página de origem',renderCell:value=><a href={value} target="_blank" rel="noreferrer">Abrir PDF</a>}]}/></Section>
 </>}
 </>}
 {tab.id==='clima' && <>
 <Notice>Estação Goiânia A002 · calendário UTC. Chuva observada pode ser parcial; a cobertura acompanha cada mês. Uma estação não descreve diferenças entre bairros nem demonstra a causa dos casos.</Notice>
 <Section id="clima:rain-title" title="Chuva e disponibilidade das medições" columns={2} spacing="none">
 <Chart id="chuva-observada" queryId="clima" title="Chuva observada · mm" rows={clima} spec={{...line('chuva_mm_observado','Chuva observada (mm)'),type:'bar',valueDecimals:1}}/>
 <Chart id="cobertura-chuva" queryId="clima" title="Cobertura da chuva · % de horas válidas" rows={clima} spec={{...line('chuva_mm_cobertura_pct','Cobertura (%)'),valueDecimals:1}}/>
 </Section>
 <Section id="clima:thermal-title" title="Temperatura e umidade" columns={2}>
 <Chart id="temperatura" queryId="clima" title="Temperatura média observada · °C" rows={clima} spec={{...line('temperatura_c_observado','Temperatura (°C)'),valueDecimals:1}}/>
 <Chart id="umidade" queryId="clima" title="Umidade média observada · %" rows={clima} spec={{...line('umidade_pct_observado','Umidade (%)'),valueDecimals:1}}/>
 </Section>
 <Section id="clima:coverage-title" title="Conferência da cobertura"><Table id="clima-detalhe" queryId="clima" title="Medições e cobertura mensal" rows={clima} columns={[col('periodo_utc','Mês UTC'),col('chuva_mm_observado','Chuva observada (mm)'),col('chuva_mm_cobertura_pct','Cobertura chuva (%)'),col('chuva_mm_completo_valor','Chuva com todas as horas (mm)'),col('temperatura_c_cobertura_pct','Cobertura temperatura (%)'),col('umidade_pct_cobertura_pct','Cobertura umidade (%)')]}/></Section>
 </>}
 {tab.id==='parceiros' && <><Notice>CNES · competência setembro de 2026. Unidades públicas sem motivo cadastral de desativação, com coordenadas dentro da malha. Funcionamento e disponibilidade para parceria precisam ser verificados. Busque por nome, tipo de unidade ou bairro.</Notice>
 <Table id="unidades-parceiras" queryId="parceiros" title="Unidades candidatas a contato" rows={all('parceiros')} columns={[col('CO_CNES','CNES'),col('NO_FANTASIA','Unidade'),col('tipo_unidade_descricao','Tipo'),col('NO_BAIRRO','Bairro cadastrado'),col('latitude','Latitude'),col('longitude','Longitude'),col('situacao_operacional','Verificação em campo')]}/></>}
 {tab.id==='mapa' && <>
 <Notice>Oito territórios selecionados, os demais elegíveis e as unidades de saúde candidatas, sobre as malhas oficiais (IBGE 2022 e SIGGO). A cor indica em quantas das seis listas de dengue de 2026 o território foi citado. Não representa risco, incidência nem área de abrangência das unidades. Bairros sem cor não foram citados ou não têm correspondência única com a malha; isso não significa zero casos.</Notice>
 <CartaoMapa rows={all('mapa')}/>
 </>}
 {tab.id==='acoes' && <>
 <Notice>Registro das ações realizadas, planejadas ou canceladas nos territórios. Os indicadores são calculados apenas a partir destes registros; não há valores estimados. Cada alteração gera uma nova versão, e as anteriores continuam no histórico.</Notice>
 <AcoesCampo snapshotRows={all('acoes')} bairros={all('mapa').filter(r=>r.camada==='bairro').sort((a,b)=>a.nome.localeCompare(b.nome,'pt-BR'))} unidades={all('mapa').filter(r=>r.camada==='unidade').sort((a,b)=>a.nome.localeCompare(b.nome,'pt-BR'))}/>
 </>}
 {tab.id==='atuacao' && <>
 <Notice>Proposta para oito territórios: presença em seis listas de dengue com janelas sem sobreposição, identificação nominal e parceiros candidatos. Os mesmos oito permanecem no recorte alternativo. A ordem organiza contatos, sem representar risco epidemiológico ou cronograma confirmado.</Notice>
 <Table id="territorios-atuacao" queryId="selecao" title="Oito territórios propostos" rows={all('selecao')} columns={[col('ordem_articulacao','Ordem de contato'),col('territorio','Território candidato'),col('janelas_com_citacao','Listas principais (de 6)'),col('janelas_alternativas_com_citacao','Listas alternativas (de 6)'),col('unidade','Parceiro candidato'),col('distancia_minima_poligono_m','Distância mínima ao polígono (m)'),col('prioridade_legivel','Articulação')]}/>
 <Notice>Distância ao polígono não é percurso de moradores nem comprova abrangência da unidade. O CS Finsocial é candidato para dois territórios; sua capacidade precisa ser confirmada. Interesse dos parceiros, funcionamento, espaço, acessibilidade, deslocamento, recursos e agenda permanecem pendentes. Não há dados para afirmar maior risco de escorpiões nestes bairros.</Notice>
 <Section id="atuacao:justificativas" title="Justificativas e condições para iniciar">
 <Table id="atuacao-condicoes" queryId="selecao" title="Conferência antes de agendar" rows={all('selecao')} columns={[col('territorio','Território'),col('justificativa','Justificativa'),col('pendencia_liberacao','Condições a confirmar')]}/>
 </Section>
 </>}
 </div>;
}
