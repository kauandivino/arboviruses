import { useEffect, useState } from 'react';
import { Menu, X } from 'lucide-react';
import { ABAS, linkAba, type Aba } from '../lib/abas';

export function Marca({ claro = false }: { claro?: boolean }) {
  return (
    <a href={linkAba('painel')} className={`marca${claro ? ' clara' : ''}`} aria-label="Saúde no Território, painel">
      <span className="marca-simbolo" aria-hidden="true">
        <svg viewBox="0 0 40 40"><rect x="1" y="1" width="38" height="38" rx="3" /><path d="M9 11h22L20 31z" /></svg>
      </span>
      <span className="marca-texto">Saúde no Território<small>Goiânia</small></span>
    </a>
  );
}

export function Cabecalho({ aba }: { aba: Aba }) {
  const [rolou, setRolou] = useState(false);
  const [aberto, setAberto] = useState(false);
  useEffect(() => {
    const aoRolar = () => setRolou(window.scrollY > 8);
    aoRolar();
    window.addEventListener('scroll', aoRolar, { passive: true });
    return () => window.removeEventListener('scroll', aoRolar);
  }, []);
  useEffect(() => setAberto(false), [aba]);
  const atual = ABAS.find(a => a.id === aba)!;
  return (
    <header className={`cabecalho${rolou ? ' rolou' : ''}`}>
      <div className="conteudo cabecalho-linha">
        <Marca />
        <button className="menu-botao" aria-label={aberto ? 'Fechar menu' : 'Abrir menu'} aria-expanded={aberto} onClick={() => setAberto(a => !a)}>
          <span className="menu-atual">{atual.rotulo}</span>{aberto ? <X size={22} /> : <Menu size={22} />}
        </button>
      </div>
      <nav aria-label="Abas" className={`abas${aberto ? ' aberto' : ''}`}>
        <div className="conteudo abas-linha">
          {ABAS.map(a => <a key={a.id} href={linkAba(a.id)} aria-current={a.id === aba ? 'page' : undefined}>{a.rotulo}</a>)}
        </div>
      </nav>
    </header>
  );
}
