import { useEffect, useState } from 'react';
import { Menu, X } from 'lucide-react';

export const SECOES = [
  { id: 'dengue', rotulo: 'Dengue' },
  { id: 'escorpioes', rotulo: 'Escorpiões' },
  { id: 'mapa', rotulo: 'Seu bairro' },
  { id: 'prevencao', rotulo: 'Prevenção' },
  { id: 'sobre', rotulo: 'Sobre os dados' },
];

export function Marca({ claro = false }: { claro?: boolean }) {
  return (
    <a href="#inicio" className={`marca${claro ? ' clara' : ''}`} aria-label="Saúde no Território, início">
      <span className="marca-simbolo" aria-hidden="true">
        <svg viewBox="0 0 40 40"><rect x="1" y="1" width="38" height="38" rx="3" /><path d="M9 11h22L20 31z" /></svg>
      </span>
      <span className="marca-texto">Saúde no Território<small>Goiânia</small></span>
    </a>
  );
}

export function Cabecalho() {
  const [ativo, setAtivo] = useState('');
  const [rolou, setRolou] = useState(false);
  const [aberto, setAberto] = useState(false);
  useEffect(() => {
    const aoRolar = () => setRolou(window.scrollY > 24);
    aoRolar();
    window.addEventListener('scroll', aoRolar, { passive: true });
    const obs = new IntersectionObserver(
      entradas => entradas.forEach(e => e.isIntersecting && setAtivo(e.target.id)),
      { rootMargin: '-45% 0px -50% 0px' },
    );
    SECOES.forEach(s => { const el = document.getElementById(s.id); if (el) obs.observe(el); });
    return () => { window.removeEventListener('scroll', aoRolar); obs.disconnect(); };
  }, []);
  return (
    <header className={`cabecalho${rolou ? ' rolou' : ''}`}>
      <div className="conteudo cabecalho-linha">
        <Marca />
        <nav aria-label="Seções" className={aberto ? 'aberto' : ''}>
          {SECOES.map(s => (
            <a key={s.id} href={`#${s.id}`} aria-current={ativo === s.id ? 'true' : undefined} onClick={() => setAberto(false)}>{s.rotulo}</a>
          ))}
        </nav>
        <button className="menu-botao" aria-label={aberto ? 'Fechar menu' : 'Abrir menu'} aria-expanded={aberto} onClick={() => setAberto(a => !a)}>
          {aberto ? <X size={22} /> : <Menu size={22} />}
        </button>
      </div>
    </header>
  );
}
