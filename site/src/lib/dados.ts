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
  nowcast: { semana: string; se: number; observado: number; estimado: number | null; inferior: number | null; superior: number | null }[];
  semanal: { semana: string; ano: number; se: number; goiania: number; vizinhos: number; resto_go: number; internacoes: number; chikungunya: number; chuva_mm: number | null; incompleta: boolean }[];
  internacoes_anual: { ano: number; internacoes: number }[];
  correlacoes: {
    clima_dengue: Record<'chuva_mm' | 'temperatura_c' | 'umidade_pct', { lags: number[]; r_bruta: number[]; r_sem_sazonalidade: number[]; melhor_lag: number; r_melhor: number; forca: string; r_bruta_no_melhor_lag: number }>;
    vizinhos: { por_temporada: Record<string, number>; mediana_semanas: number; antes: number; juntos: number; depois: number; temporadas: number; correlacao_semanal: number };
    chikungunya: { por_temporada: Record<string, number>; mediana_semanas: number; antes: number; juntos: number; depois: number; temporadas: number };
    escorpioes: { meses: number; r_temperatura_bruta: number; r_temperatura_sem_sazonalidade: number; perfil_mensal: { mes: number; acidentes: number; temperatura_c: number }[] };
  };
  escorpioes_modelo: { exibida: boolean; previsao: { mes: string; horizonte: number; previsto: number; faixa_80pct: [number, number] }[]; serie: { mes: string; acidentes: number }[]; ultimo_mes: string; erro_teste: Record<string, { modelo: number; referencia: number }> };
  modelos: { nome: string; pergunta: string; status: 'em_uso' | 'nao_passou'; resultado: string }[];
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
