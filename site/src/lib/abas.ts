import { useEffect, useState } from 'react';

export const ABAS = [
  { id: 'painel', rotulo: 'Painel' },
  { id: 'dengue', rotulo: 'Dengue' },
  { id: 'arboviroses', rotulo: 'Chikungunya e Zika' },
  { id: 'mosquito', rotulo: 'Mosquito e Clima' },
  { id: 'escorpioes', rotulo: 'Escorpiões' },
  { id: 'bairro', rotulo: 'Seu bairro' },
  { id: 'prevencao', rotulo: 'Prevenção' },
  { id: 'sobre', rotulo: 'Sobre' },
] as const;
export type Aba = (typeof ABAS)[number]['id'];

const ler = (): Aba => {
  const id = window.location.hash.replace(/^#\/?/, '').split('?')[0];
  return (ABAS.find(a => a.id === id)?.id ?? 'painel') as Aba;
};

/** Aba atual pelo endereço (#/dengue), para abrir e compartilhar cada aba diretamente. */
export function useAba() {
  const [aba, setAba] = useState<Aba>(ler);
  useEffect(() => {
    const mudar = () => { setAba(ler()); window.scrollTo({ top: 0 }); };
    window.addEventListener('hashchange', mudar);
    return () => window.removeEventListener('hashchange', mudar);
  }, []);
  return aba;
}

export const linkAba = (id: Aba) => `#/${id}`;
