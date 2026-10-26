import { useEffect, useRef, useState } from 'react';

const inteiro = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 0 });
export const numero = (v: number | null | undefined) => (v == null ? '—' : inteiro.format(v));
export const decimal = (v: number | null | undefined, casas = 1) =>
  v == null ? '—' : new Intl.NumberFormat('pt-BR', { maximumFractionDigits: casas, minimumFractionDigits: casas }).format(v);

const MESES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];
const MESES_LONGOS = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro'];
export const mesCurto = (mes: string) => MESES[Number(mes.slice(5, 7)) - 1];
export const mesLongo = (mes: string) => MESES_LONGOS[Number(mes.slice(5, 7)) - 1];
export const dataLonga = (iso: string) => {
  const [a, m, d] = iso.split('-').map(Number);
  return `${d} de ${MESES_LONGOS[m - 1]} de ${a}`;
};
export const dataCurta = (iso: string) => {
  const [, m, d] = iso.split('-').map(Number);
  return `${d} ${MESES[m - 1]}`;
};

/** Semana epidemiológica aproximada no calendário: mês em que a semana cai, para eixos legíveis. */
export function mesDaSemana(ano: number, se: number) {
  const primeiro = new Date(Date.UTC(ano, 0, 1));
  const dia = primeiro.getUTCDay();
  const inicio = new Date(primeiro.getTime() - dia * 864e5 + (dia > 3 ? 7 * 864e5 : 0));
  return new Date(inicio.getTime() + ((se - 1) * 7 + 3) * 864e5).getUTCMonth();
}
export const MESES_ABREV = MESES;

/** Largura real de um elemento, para desenhar gráficos SVG sem distorção. */
export function useLargura<T extends HTMLElement>(padrao = 800) {
  const ref = useRef<T>(null);
  const [largura, setLargura] = useState(padrao);
  useEffect(() => {
    if (!ref.current) return;
    const obs = new ResizeObserver(([e]) => setLargura(Math.max(280, Math.round(e.contentRect.width))));
    obs.observe(ref.current);
    return () => obs.disconnect();
  }, []);
  return [ref, largura] as const;
}

/** Torna-se verdadeiro quando o elemento entra na tela (para animar e carregar o mapa sob demanda). */
export function useVisivel<T extends HTMLElement>(margem = '200px') {
  const ref = useRef<T>(null);
  const [visivel, setVisivel] = useState(false);
  useEffect(() => {
    if (!ref.current || visivel) return;
    const obs = new IntersectionObserver(([e]) => e.isIntersecting && setVisivel(true), { rootMargin: margem });
    obs.observe(ref.current);
    return () => obs.disconnect();
  }, [margem, visivel]);
  return [ref, visivel] as const;
}
