import { useEffect, useState } from 'react';

export type Situacao = 'abaixo' | 'habitual' | 'pouco_acima' | 'acima' | 'alerta' | 'em_atualizacao';

export interface DadosSite {
  gerado_em: string;
  dados_ate: string;
  dengue: {
    ano: number;
    situacao: {
      zona: Situacao; se: number; semana: string; ultimas_4_semanas: number; quatro_anteriores: number;
      variacao_pct: number | null; tendencia: 'subindo' | 'estavel' | 'caindo';
    };
    faixa_habitual: { se: number; q1: number; mediana: number; q3: number }[];
    temporadas: Record<string, { se: number; valor: number | null }[]>;
    projecao: { ano: number; se: number; semana: string; previsto: number; inferior: number; superior: number }[];
    anual: { ano: number; notificacoes: number; parcial: boolean }[];
    mensal: { mes: string; notificacoes: number }[];
  };
  sorotipos: {
    meses: { mes: string; denv1: number; denv2: number; denv3: number; denv4: number }[];
    dominante: string | null; amostras_12_semanas: number; parcela_dominante: number | null;
    primeiro_ano_relevante: number | null; desde: number;
  };
  outras_arboviroses: Record<'chikungunya' | 'zika', { anual: { ano: number; notificacoes: number }[]; mensal: { mes: string; notificacoes: number }[] }>;
  liraa: { inicio: string; fim: string; iip: number; situacao: string; estratos_alto: number; estratos_total: number; nota: string | null }[];
  transmissao: { fonte: string; consultado_em: string; versao_modelo: string; semanas: { semana: string; se: number; rt: number; p_rt1: number }[] };
  escorpioes: { mes: string; acidentes: number }[];
  clima: { mes: string; chuva_mm: number | null; cobertura_pct: number; temperatura_c: number | null }[];
  boletins: { ano: number; edicoes: number[] };
  territorios: { ordem: number; oid: number; nome: string; parceiro: string; citacoes: number; listas: number; acoes_realizadas: number }[];
  acoes: { realizadas: number; participantes: number; territorios: number; lista: { data: string; territorio: string; tipo: string; participantes: number }[] };
  contagens: { unidades: number; bairros: number };
}

export function useDados() {
  const [dados, setDados] = useState<DadosSite | null>(null);
  const [erro, setErro] = useState(false);
  useEffect(() => {
    fetch('dados/site.json', { cache: 'no-cache' })
      .then(r => (r.ok ? r.json() : Promise.reject(r.status)))
      .then(setDados)
      .catch(() => setErro(true));
  }, []);
  return { dados, erro };
}
