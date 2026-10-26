import React from 'react';
import { DataComponent } from '../../data-app-public.jsx';

// Geometria em metros (EPSG:31982) com origem no canto noroeste do limite municipal; y cresce para o sul.
const ESCALAS = [100, 200, 500, 1000, 2000, 5000, 10000];
const fmt = v => v == null ? 'Sem dado' : new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 0 }).format(v);

function limites(d) {
  let x = 0, y = 0, minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const [, cmd, a, b] of d.matchAll(/([Ml])(-?\d+) (-?\d+)/g)) {
    if (cmd === 'M') { x = +a; y = +b; } else { x += +a; y += +b; }
    minX = Math.min(minX, x); minY = Math.min(minY, y); maxX = Math.max(maxX, x); maxY = Math.max(maxY, y);
  }
  return { x: minX, y: minY, w: maxX - minX, h: maxY - minY };
}

function enquadrar(caixa, margem, proporcao) {
  let w = caixa.w + 2 * margem, h = caixa.h + 2 * margem;
  if (w / h < proporcao) w = h * proporcao; else h = w / proporcao;
  return { x: caixa.x + caixa.w / 2 - w / 2, y: caixa.y + caixa.h / 2 - h / 2, w, h };
}

function Detalhe({ item, onFechar }) {
  if (!item) return <div className="st-mapa-detalhe st-mapa-detalhe-vazio">
    <p>Clique em um território destacado ou em uma unidade para ver os dados de origem.</p>
  </div>;
  const campos = item.camada === 'unidade' ? [
    ['CNES', item.CO_CNES], ['Tipo', item.tipo], ['Bairro cadastrado', item.bairro_cadastrado],
    ['Parceiro candidato de', item.parceiro_de ?? '—'], ['Até 3 km de territórios', item.ate_3km_de ?? '—'],
    ['Coordenadas', `${item.latitude.toFixed(6)}, ${item.longitude.toFixed(6)}`],
  ] : [
    ['Situação', item.situacao === 'selecionado' ? `Selecionado · ordem de contato ${item.ordem_articulacao}` : item.situacao === 'candidato' ? 'Elegível, não selecionado' : 'Sem destaque na seleção'],
    ['Listas de dengue com citação', item.janelas_com_citacao == null ? 'Sem correspondência única ou sem citação' : `${item.janelas_com_citacao} de ${item.janelas_observadas}`],
    ['Edições citadas (SE/2026)', item.edicoes_citadas?.replaceAll(';', ', ') ?? '—'],
    ['Parceiro candidato', item.parceiro_nome ? `${item.parceiro_nome} (CNES ${item.parceiro_cnes})` : '—'],
    ['Distância mínima ao polígono', item.distancia_parceiro_m == null ? '—' : `${fmt(item.distancia_parceiro_m)} m`],
    ['OID SIGGO', item.OID_SIGGO],
  ];
  return <div className="st-mapa-detalhe" aria-live="polite">
    <div className="st-mapa-detalhe-topo"><strong>{item.nome}</strong><button type="button" onClick={onFechar} aria-label="Fechar detalhes">×</button></div>
    <dl>{campos.map(([k, v]) => <React.Fragment key={k}><dt>{k}</dt><dd>{v}</dd></React.Fragment>)}</dl>
    <p className="st-mapa-ressalva">{item.camada === 'unidade' ? 'Funcionamento, abrangência e interesse em parceria não verificados.' : 'Correspondência nominal com a malha SIGGO, sem homologação dos limites usados pela vigilância.'}</p>
  </div>;
}

export function MapaTerritorios({ rows }) {
  const limite = rows.find(r => r.camada === 'limite');
  const bairros = React.useMemo(() => rows.filter(r => r.camada === 'bairro'), [rows]);
  const unidades = React.useMemo(() => rows.filter(r => r.camada === 'unidade'), [rows]);
  const destacados = React.useMemo(() => bairros.filter(b => b.situacao !== 'contexto').sort((a, b) => (a.ordem_articulacao ?? 99) - (b.ordem_articulacao ?? 99)), [bairros]);
  const selecionados = destacados.filter(b => b.situacao === 'selecionado');
  const [tamanho, setTamanho] = React.useState({ w: 800, h: 640 });
  const proporcao = tamanho.w / tamanho.h;
  const inicial = React.useMemo(() => limite && enquadrar({ x: 0, y: 0, w: limite.largura_m, h: limite.altura_m }, 400, proporcao), [limite, proporcao]);
  const [view, setView] = React.useState(inicial);
  const interagiu = React.useRef(false);
  // Até a primeira interação, o enquadramento acompanha o tamanho real do quadro.
  React.useEffect(() => { setView(v => interagiu.current && v ? { ...v, y: v.y + v.h / 2 - v.w / proporcao / 2, h: v.w / proporcao } : inicial); }, [proporcao, inicial]);
  const [selecao, setSelecao] = React.useState(null);
  const [hover, setHover] = React.useState(null);
  const [mostrarUnidades, setMostrarUnidades] = React.useState(true);
  const svgRef = React.useRef(null);
  const arrasto = React.useRef(null);
  const toques = React.useRef(new Map());

  React.useEffect(() => {
    const svg = svgRef.current; if (!svg) return;
    const obs = new ResizeObserver(([e]) => {
      const { width, height } = e.contentRect;
      if (width && height) setTamanho(t => t.w === width && t.h === height ? t : { w: width, h: height });
    });
    obs.observe(svg);
    const roda = e => {
      e.preventDefault();
      zoomEm(e.clientX, e.clientY, e.deltaY > 0 ? 1.25 : 0.8);
    };
    svg.addEventListener('wheel', roda, { passive: false });
    return () => { obs.disconnect(); svg.removeEventListener('wheel', roda); };
  });

  if (!limite) return <p className="st-empty" role="status">Camadas do mapa indisponíveis neste snapshot.</p>;

  function pontoSvg(cx, cy) {
    const r = svgRef.current.getBoundingClientRect();
    return { x: view.x + (cx - r.left) / r.width * view.w, y: view.y + (cy - r.top) / r.height * view.h };
  }
  function zoomEm(cx, cy, fator) {
    interagiu.current = true;
    setView(v => {
      const r = svgRef.current.getBoundingClientRect();
      const px = v.x + (cx - r.left) / r.width * v.w, py = v.y + (cy - r.top) / r.height * v.h;
      const w = Math.min(Math.max(v.w * fator, 600), inicial.w * 1.5), h = w / (r.width / r.height), k = w / v.w;
      return { x: px - (px - v.x) * k, y: py - (py - v.y) * k, w, h };
    });
  }
  function zoomCentro(fator) {
    const r = svgRef.current.getBoundingClientRect();
    zoomEm(r.left + r.width / 2, r.top + r.height / 2, fator);
  }
  function focar(item) {
    interagiu.current = true;
    setSelecao(item); setHover(null);
    if (item.camada === 'bairro') setView(enquadrar(limites(item.d), 1500, proporcao));
    else setView(enquadrar({ x: item.x, y: item.y, w: 0, h: 0 }, 1500, proporcao));
  }
  const inicioArrasto = e => {
    toques.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    arrasto.current = { x: e.clientX, y: e.clientY, view, moveu: false };
  };
  const moverArrasto = e => {
    if (!arrasto.current) return;
    const anterior = toques.current.get(e.pointerId);
    toques.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (toques.current.size === 2 && anterior) {
      const [a, b] = [...toques.current.values()];
      const outro = [...toques.current.entries()].find(([id]) => id !== e.pointerId)[1];
      const antes = Math.hypot(anterior.x - outro.x, anterior.y - outro.y), depois = Math.hypot(a.x - b.x, a.y - b.y);
      if (antes > 0 && depois > 0) zoomEm((a.x + b.x) / 2, (a.y + b.y) / 2, antes / depois);
      arrasto.current.moveu = true;
      return;
    }
    const r = svgRef.current.getBoundingClientRect(), d = arrasto.current;
    const dx = (e.clientX - d.x) / r.width * d.view.w, dy = (e.clientY - d.y) / r.height * d.view.h;
    if (Math.abs(e.clientX - d.x) + Math.abs(e.clientY - d.y) > 4) {
      d.moveu = true;
      if (!svgRef.current.hasPointerCapture(e.pointerId)) svgRef.current.setPointerCapture(e.pointerId);
    }
    if (d.moveu) interagiu.current = true;
    if (d.moveu) setView({ ...d.view, x: d.view.x - dx, y: d.view.y - dy });
  };
  const fimArrasto = e => {
    toques.current.delete(e.pointerId);
    if (toques.current.size === 0) setTimeout(() => { arrasto.current = null; });
  };
  const clicar = item => () => { if (!arrasto.current?.moveu) setSelecao(item); };
  const teclado = item => e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); focar(item); } };
  const sobre = item => e => setHover({ item, ...pontoSvg(e.clientX, e.clientY), cx: e.clientX, cy: e.clientY });

  const metrosPorPx = view.w / tamanho.w;
  const escala = ESCALAS.findLast(m => m / metrosPorPx <= 140) ?? ESCALAS[0];
  const raio = Math.max(metrosPorPx * 3.2, 40);
  const caixa = svgRef.current?.getBoundingClientRect();

  return <div className="st-mapa">
    <div className="st-mapa-controles">
      <label className="st-mapa-foco">Ir para
        <select value={selecao?.camada === 'bairro' ? selecao.id : ''} onChange={e => { const b = destacados.find(x => x.id === e.target.value); if (b) focar(b); else { setSelecao(null); interagiu.current = false; setView(inicial); } }}>
          <option value="">Goiânia inteira</option>
          <optgroup label="Oito territórios selecionados">{selecionados.map(b => <option key={b.id} value={b.id}>{b.ordem_articulacao}. {b.nome}</option>)}</optgroup>
          <optgroup label="Elegíveis não selecionados">{destacados.filter(b => b.situacao === 'candidato').map(b => <option key={b.id} value={b.id}>{b.nome}</option>)}</optgroup>
        </select>
      </label>
      <label className="st-mapa-check"><input type="checkbox" checked={mostrarUnidades} onChange={e => setMostrarUnidades(e.target.checked)} /> Unidades de saúde candidatas ({unidades.length})</label>
      <div className="st-mapa-zoom" role="group" aria-label="Zoom do mapa">
        <button type="button" onClick={() => zoomCentro(0.7)} aria-label="Aproximar">+</button>
        <button type="button" onClick={() => zoomCentro(1.4)} aria-label="Afastar">−</button>
        <button type="button" onClick={() => { interagiu.current = false; setView(inicial); setSelecao(null); }}>Ver tudo</button>
      </div>
    </div>
    <div className="st-mapa-corpo">
      <div className="st-mapa-quadro">
        <svg ref={svgRef} viewBox={`${view.x} ${view.y} ${view.w} ${view.h}`} role="img"
          aria-label="Mapa de Goiânia com os oito territórios selecionados, os territórios elegíveis e as unidades de saúde candidatas"
          onPointerDown={inicioArrasto} onPointerMove={moverArrasto} onPointerUp={fimArrasto} onPointerCancel={fimArrasto}
          onPointerLeave={() => setHover(null)} onDoubleClick={e => zoomEm(e.clientX, e.clientY, 0.6)}>
          <path d={limite.d} className="st-mapa-limite-fundo" />
          <g className="st-mapa-contexto">{bairros.filter(b => b.situacao === 'contexto').map(b => <path key={b.id} d={b.d} onPointerMove={sobre(b)} />)}</g>
          <g>{destacados.map(b => <path key={b.id} d={b.d} tabIndex={0} role="button" aria-label={`${b.nome}: citado em ${b.janelas_com_citacao} de ${b.janelas_observadas} listas${b.ordem_articulacao ? `, ordem de contato ${b.ordem_articulacao}` : ''}`}
            className={`st-mapa-territorio ${b.situacao}${selecao?.id === b.id ? ' ativo' : ''}`} data-presenca={b.janelas_com_citacao}
            onClick={clicar(b)} onKeyDown={teclado(b)} onPointerMove={sobre(b)} />)}</g>
          <path d={limite.d} className="st-mapa-limite" />
          {mostrarUnidades && <g>{unidades.filter(u => u.situacao !== 'parceiro_selecionado').map(u => <circle key={u.id} cx={u.x} cy={u.y} r={raio * 0.75}
            className={`st-mapa-unidade${selecao?.id === u.id ? ' ativo' : ''}`} onClick={clicar(u)} onPointerMove={sobre(u)} />)}</g>}
          <g>{unidades.filter(u => u.situacao === 'parceiro_selecionado').map(u => <rect key={u.id} x={u.x - raio} y={u.y - raio} width={raio * 2} height={raio * 2}
            transform={`rotate(45 ${u.x} ${u.y})`} tabIndex={0} role="button" aria-label={`${u.nome}, parceiro candidato de ${u.parceiro_de}`}
            className={`st-mapa-parceiro${selecao?.id === u.id ? ' ativo' : ''}`} onClick={clicar(u)} onKeyDown={teclado(u)} onPointerMove={sobre(u)} />)}</g>
          <g className="st-mapa-rotulos" aria-hidden="true">{selecionados.map(b => <g key={b.id} transform={`translate(${b.cx} ${b.cy})`}>
            <circle r={raio * 2.4} /><text dy={raio * 0.85} fontSize={raio * 2.6}>{b.ordem_articulacao}</text></g>)}</g>
        </svg>
        {hover && caixa && <div className="st-mapa-tooltip" style={{ left: Math.min(hover.cx - caixa.left + 14, caixa.width - 230), top: hover.cy - caixa.top + 14 }} role="status">
          <strong>{hover.item.nome}</strong>
          {hover.item.camada === 'unidade' ? <span>{hover.item.tipo}{hover.item.parceiro_de ? ` · parceiro candidato de ${hover.item.parceiro_de}` : ''}</span>
            : hover.item.situacao === 'contexto' ? <span>Sem destaque na seleção</span>
            : <span>Citado em {hover.item.janelas_com_citacao} de {hover.item.janelas_observadas} listas{hover.item.ordem_articulacao ? ` · ordem ${hover.item.ordem_articulacao}` : ''}</span>}
        </div>}
        <div className="st-mapa-escala" aria-hidden="true"><i style={{ width: escala / metrosPorPx }} /><span>{escala >= 1000 ? `${escala / 1000} km` : `${escala} m`}</span></div>
      </div>
      <Detalhe item={selecao} onFechar={() => setSelecao(null)} />
    </div>
    <div className="st-mapa-legenda">
      <span><b className="st-leg-area" data-presenca="5" /> Selecionado (número = ordem de contato)</span>
      <span className="st-leg-rampa">Listas com citação: {[1, 2, 3, 4, 5, 6].map(n => <b key={n} className="st-leg-area" data-presenca={n} title={`${n} de 6`}>{n}</b>)}</span>
      <span><b className="st-leg-area st-leg-candidato" /> Elegível não selecionado</span>
      <span><b className="st-leg-area st-leg-contexto" /> Sem destaque (não significa zero casos)</span>
      <span><b className="st-leg-parceiro" /> Parceiro candidato</span>
      <span><b className="st-leg-unidade" /> Outra unidade candidata</span>
    </div>
  </div>;
}

export function CartaoMapa({ rows }) {
  return <DataComponent id="mapa-territorios" queryId="mapa" title="Mapa dos territórios e unidades de saúde" kind="custom" variant="card"
    sourceRows={rows} displayRows={rows} data-reviewed-rows>
    <MapaTerritorios rows={rows} />
  </DataComponent>;
}
