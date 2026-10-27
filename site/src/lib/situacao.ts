import type { Situacao } from './dados';

export const SITUACOES: Record<Situacao, { titulo: string; frase: string; cor: string; nivel: number }> = {
  abaixo: { titulo: 'Abaixo do habitual', frase: 'Menos casos do que costuma haver nesta época do ano.', cor: 'var(--zona-abaixo)', nivel: 0 },
  habitual: { titulo: 'Dentro do habitual', frase: 'Número de casos parecido com o dos últimos anos nesta época.', cor: 'var(--zona-habitual)', nivel: 1 },
  pouco_acima: { titulo: 'Um pouco acima do habitual', frase: 'Mais casos do que a média dos últimos anos nesta época.', cor: 'var(--zona-acima)', nivel: 2 },
  acima: { titulo: 'Acima do habitual', frase: 'Mais casos do que em quase todos os últimos anos nesta época.', cor: 'var(--zona-alerta)', nivel: 3 },
  alerta: { titulo: 'Alerta', frase: 'Há pelo menos duas semanas os casos estão acima do habitual para esta época do ano.', cor: 'var(--zona-alerta)', nivel: 3 },
  em_atualizacao: { titulo: 'Em atualização', frase: 'Os registros desta semana ainda estão chegando. Volte em alguns dias.', cor: 'var(--linha-forte)', nivel: -1 },
};
