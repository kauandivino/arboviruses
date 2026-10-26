import { useEffect, useMemo, useRef, useState } from 'react';
import maplibregl, { type LngLatBoundsLike, type StyleSpecification } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { Building2, Cross, Hospital, MapPin, Phone, Search, Stethoscope, X } from 'lucide-react';
import type { DadosSite } from '../lib/dados';
import { numero } from '../lib/formato';

type Bairro = GeoJSON.Feature<GeoJSON.Polygon | GeoJSON.MultiPolygon, { oid: number; nome: string; citacoes: number; edicoes: number[]; territorio: number | null; lon: number; lat: number }>;
type Unidade = GeoJSON.Feature<GeoJSON.Point, { cnes: string; nome: string; categoria: Categoria; endereco: string; telefone: string | null }>;
type Categoria = 'posto' | 'policlinica' | 'urgencia' | 'hospital';

export const CATEGORIAS: Record<Categoria, { rotulo: string; cor: string; Icone: typeof Stethoscope }> = {
  posto: { rotulo: 'Posto de saúde (UBS)', cor: '#0f7168', Icone: Stethoscope },
  policlinica: { rotulo: 'Policlínica', cor: '#3f6fb5', Icone: Building2 },
  urgencia: { rotulo: 'Pronto atendimento', cor: '#d9472f', Icone: Cross },
  hospital: { rotulo: 'Hospital', cor: '#7a4fa3', Icone: Hospital },
};
const ESTILO = 'https://tiles.openfreemap.org/styles/positron';
// Sem internet para o mapa de ruas, as camadas do projeto continuam visíveis sobre um fundo neutro.
const ESTILO_RESERVA: StyleSpecification = { version: 8, sources: {}, layers: [{ id: 'fundo', type: 'background', paint: { 'background-color': '#eef1ef' } }] };

const normalizar = (t: string) => t.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
function distanciaKm(a: [number, number], b: [number, number]) {
  const r = Math.PI / 180, dLat = (b[1] - a[1]) * r, dLon = (b[0] - a[0]) * r;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a[1] * r) * Math.cos(b[1] * r) * Math.sin(dLon / 2) ** 2;
  return 12742 * Math.asin(Math.sqrt(h));
}
function limites(g: Bairro['geometry']): LngLatBoundsLike {
  const coords = (g.type === 'Polygon' ? [g.coordinates] : g.coordinates).flat(2) as number[][];
  const xs = coords.map(c => c[0]), ys = coords.map(c => c[1]);
  return [[Math.min(...xs), Math.min(...ys)], [Math.max(...xs), Math.max(...ys)]];
}

export default function Mapa({ dados }: { dados: DadosSite }) {
  const caixa = useRef<HTMLDivElement>(null);
  const mapa = useRef<maplibregl.Map | null>(null);
  const [bairros, setBairros] = useState<Bairro[]>([]);
  const [unidades, setUnidades] = useState<Unidade[]>([]);
  const [selecionado, setSelecionado] = useState<Bairro | null>(null);
  const [busca, setBusca] = useState('');
  const [camadas, setCamadas] = useState({ boletins: true, territorios: true, unidades: true });
  const [pronto, setPronto] = useState(false);
  const totalEdicoes = dados.boletins.edicoes.length;

  useEffect(() => {
    Promise.all([fetch('dados/bairros.geojson').then(r => r.json()), fetch('dados/unidades.geojson').then(r => r.json())])
      .then(([b, u]) => { setBairros(b.features); setUnidades(u.features); });
  }, []);

  useEffect(() => {
    if (!caixa.current || !bairros.length || mapa.current) return;
    let cancelado = false;
    fetch(ESTILO).then(r => (r.ok ? r.json() : Promise.reject())).catch(() => ESTILO_RESERVA).then((estilo: StyleSpecification) => {
      if (cancelado || !caixa.current) return;
      const m = new maplibregl.Map({ container: caixa.current, style: estilo, center: [-49.27, -16.68], zoom: 10.6, minZoom: 9, maxZoom: 17,
        attributionControl: { compact: true }, cooperativeGestures: window.matchMedia('(pointer: coarse)').matches });
      mapa.current = m;
      m.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'bottom-right');
      m.on('load', () => {
        m.addSource('bairros', { type: 'geojson', data: { type: 'FeatureCollection', features: bairros }, promoteId: 'oid' });
        m.addSource('unidades', { type: 'geojson', data: { type: 'FeatureCollection', features: unidades } });
        m.addLayer({ id: 'boletins', type: 'fill', source: 'bairros', filter: ['>', ['get', 'citacoes'], 0], paint: {
          'fill-color': ['interpolate', ['linear'], ['get', 'citacoes'], 1, '#bfe8e2', 6, '#5fc4b7', 14, '#20a597', 24, '#0b4f49'], 'fill-opacity': ['interpolate', ['linear'], ['zoom'], 11, 0.72, 14, 0.38] } });
        m.addLayer({ id: 'contorno', type: 'line', source: 'bairros', paint: { 'line-color': '#5c6a6e', 'line-opacity': ['interpolate', ['linear'], ['zoom'], 10, 0.12, 13, 0.4], 'line-width': 0.6 } });
        m.addLayer({ id: 'territorios', type: 'line', source: 'bairros', filter: ['!=', ['get', 'territorio'], null], paint: { 'line-color': '#13191c', 'line-width': 2.4, 'line-dasharray': [2, 1] } });
        m.addLayer({ id: 'selecionado', type: 'line', source: 'bairros', filter: ['==', ['get', 'oid'], -1], paint: { 'line-color': '#e2553f', 'line-width': 3.5 } });
        m.addLayer({ id: 'unidades', type: 'circle', source: 'unidades', paint: {
          'circle-color': ['match', ['get', 'categoria'], 'posto', CATEGORIAS.posto.cor, 'policlinica', CATEGORIAS.policlinica.cor, 'urgencia', CATEGORIAS.urgencia.cor, CATEGORIAS.hospital.cor],
          'circle-radius': ['interpolate', ['linear'], ['zoom'], 10, 3.5, 14, 7.5], 'circle-stroke-color': '#fff', 'circle-stroke-width': 1.6 } });
        // Marcadores triangulares numerados dos oito territórios do projeto.
        bairros.filter(b => b.properties.territorio).forEach(b => {
          const el = document.createElement('div');
          el.className = 'marcador-territorio';
          el.innerHTML = `<span>${b.properties.territorio}</span>`;
          el.title = `Território do projeto: ${b.properties.nome}`;
          el.addEventListener('click', ev => { ev.stopPropagation(); setSelecionado(b); });
          new maplibregl.Marker({ element: el, anchor: 'bottom' }).setLngLat([b.properties.lon, b.properties.lat]).addTo(m);
        });
        const popup = new maplibregl.Popup({ closeButton: false, offset: 10, className: 'popup-unidade' });
        m.on('mouseenter', 'unidades', e => {
          m.getCanvas().style.cursor = 'pointer';
          const u = e.features![0].properties as Unidade['properties'];
          popup.setLngLat((e.features![0].geometry as GeoJSON.Point).coordinates as [number, number])
            .setHTML(`<strong>${u.nome}</strong><span>${CATEGORIAS[u.categoria].rotulo}</span><span>${u.endereco}</span>${u.telefone ? `<span>${u.telefone}</span>` : ''}`).addTo(m);
        });
        m.on('mouseleave', 'unidades', () => { m.getCanvas().style.cursor = ''; popup.remove(); });
        m.on('click', e => {
          const [f] = m.queryRenderedFeatures(e.point, { layers: ['contorno'] });
          if (f) setSelecionado(bairros.find(b => b.properties.oid === f.properties.oid) ?? null);
        });
        setPronto(true);
      });
    });
    return () => { cancelado = true; };
  }, [bairros, unidades]);

  useEffect(() => () => { mapa.current?.remove(); mapa.current = null; }, []);

  useEffect(() => {
    const m = mapa.current;
    if (!m || !pronto) return;
    m.setFilter('selecionado', ['==', ['get', 'oid'], selecionado?.properties.oid ?? -1]);
    if (selecionado) m.fitBounds(limites(selecionado.geometry), { padding: { top: 60, bottom: 60, left: window.innerWidth > 900 ? 420 : 40, right: 60 }, maxZoom: 15, duration: 900 });
  }, [selecionado, pronto]);

  useEffect(() => {
    const m = mapa.current;
    if (!m || !pronto) return;
    m.setLayoutProperty('boletins', 'visibility', camadas.boletins ? 'visible' : 'none');
    m.setLayoutProperty('territorios', 'visibility', camadas.territorios ? 'visible' : 'none');
    m.setLayoutProperty('unidades', 'visibility', camadas.unidades ? 'visible' : 'none');
    document.querySelectorAll<HTMLElement>('.marcador-territorio').forEach(el => { el.style.display = camadas.territorios ? '' : 'none'; });
  }, [camadas, pronto]);

  const sugestoes = useMemo(() => {
    const q = normalizar(busca.trim());
    if (q.length < 2) return [];
    const nomes = new Map<string, Bairro>();
    bairros.forEach(b => { if (!nomes.has(b.properties.nome) && normalizar(b.properties.nome).includes(q)) nomes.set(b.properties.nome, b); });
    return [...nomes.values()].sort((a, b) => normalizar(a.properties.nome).indexOf(q) - normalizar(b.properties.nome).indexOf(q)).slice(0, 7);
  }, [busca, bairros]);

  const proximas = useMemo(() => {
    if (!selecionado) return [];
    const centro: [number, number] = [selecionado.properties.lon, selecionado.properties.lat];
    return unidades.map(u => ({ u, km: distanciaKm(centro, u.geometry.coordinates as [number, number]) })).sort((a, b) => a.km - b.km).slice(0, 3);
  }, [selecionado, unidades]);
  const territorio = selecionado?.properties.territorio ? dados.territorios.find(t => t.ordem === selecionado.properties.territorio) : null;

  return (
    <div className="mapa-moldura">
      <div ref={caixa} className="mapa-canvas" aria-label="Mapa de Goiânia com bairros, territórios do projeto e unidades de saúde" role="region" />
      <div className="mapa-painel">
        <div className="busca">
          <Search size={18} aria-hidden="true" />
          <input value={busca} onChange={e => setBusca(e.target.value)} placeholder="Digite o nome do seu bairro" aria-label="Buscar bairro" />
          {busca && <button aria-label="Limpar busca" onClick={() => setBusca('')}><X size={16} /></button>}
          {sugestoes.length > 0 && (
            <ul className="sugestoes" role="listbox">
              {sugestoes.map(b => <li key={b.properties.oid}><button onClick={() => { setSelecionado(b); setBusca(''); }}><MapPin size={14} aria-hidden="true" />{b.properties.nome}</button></li>)}
            </ul>
          )}
        </div>

        {selecionado ? (
          <div className="ficha" aria-live="polite">
            <div className="ficha-topo">
              <h3>{selecionado.properties.nome}</h3>
              <button className="fechar" aria-label="Fechar" onClick={() => setSelecionado(null)}><X size={18} /></button>
            </div>
            {territorio && <p className="selo-territorio"><span>{territorio.ordem}</span>Território do projeto · parceiro: {territorio.parceiro}</p>}
            <div className="ficha-boletins">
              <p className="rotulo-pequeno">Nos boletins de dengue de {dados.boletins.ano}</p>
              <div className="bolinhas" aria-hidden="true">
                {dados.boletins.edicoes.map(se => <i key={se} className={selecionado.properties.edicoes.includes(se) ? 'cheia' : ''} title={`Boletim da semana ${se}`} />)}
              </div>
              <p>{selecionado.properties.citacoes
                ? <>Apareceu em <strong>{selecionado.properties.citacoes} de {totalEdicoes}</strong> boletins entre os bairros com mais casos.</>
                : <>Não apareceu entre os bairros com mais casos. Isso não quer dizer que não há casos no bairro.</>}</p>
            </div>
            <p className="rotulo-pequeno">Unidades de saúde mais próximas</p>
            <ul className="lista-unidades">
              {proximas.map(({ u, km }) => {
                const c = CATEGORIAS[u.properties.categoria];
                return (
                  <li key={u.properties.cnes}>
                    <span className="icone-unidade" style={{ background: c.cor }}><c.Icone size={15} /></span>
                    <div>
                      <strong>{u.properties.nome}</strong>
                      <span>{c.rotulo} · {numero(Math.round(km * 10) / 10 < 1 ? Math.round(km * 1000) : Math.round(km * 10) / 10)}{km < 1 ? ' m' : ' km'} em linha reta</span>
                      <span>{u.properties.endereco}</span>
                      {u.properties.telefone && <a href={`tel:${u.properties.telefone.replace(/\D/g, '')}`}><Phone size={13} /> {u.properties.telefone}</a>}
                    </div>
                  </li>
                );
              })}
            </ul>
          </div>
        ) : (
          <div className="ficha vazia">
            <p>Busque seu bairro ou toque nele no mapa para ver se apareceu nos boletins de dengue e quais unidades de saúde ficam mais perto.</p>
          </div>
        )}

        <div className="camadas" role="group" aria-label="Camadas do mapa">
          <label><input type="checkbox" checked={camadas.boletins} onChange={e => setCamadas(c => ({ ...c, boletins: e.target.checked }))} />
            <span className="amostra gradiente" /> Bairros nos boletins de dengue</label>
          <label><input type="checkbox" checked={camadas.territorios} onChange={e => setCamadas(c => ({ ...c, territorios: e.target.checked }))} />
            <span className="amostra triangulo" /> Territórios do projeto</label>
          <label><input type="checkbox" checked={camadas.unidades} onChange={e => setCamadas(c => ({ ...c, unidades: e.target.checked }))} />
            <span className="amostra pontos">{Object.values(CATEGORIAS).map(c => <i key={c.rotulo} style={{ background: c.cor }} />)}</span> Unidades de saúde</label>
          {camadas.unidades && <div className="legenda-unidades">{Object.values(CATEGORIAS).map(c => <span key={c.rotulo}><i style={{ background: c.cor }} />{c.rotulo}</span>)}</div>}
        </div>
      </div>
      {!pronto && <div className="mapa-carregando"><span className="carregando" /> Carregando o mapa…</div>}
    </div>
  );
}

