import type { ReactNode } from 'react';
import { motion, useReducedMotion } from 'motion/react';

/** Entrada suave quando o bloco aparece na tela; respeita quem prefere menos movimento. */
export function Revelar({ children, atraso = 0, className }: { children: ReactNode; atraso?: number; className?: string }) {
  const reduzir = useReducedMotion();
  return (
    <motion.div className={className} initial={reduzir ? false : { opacity: 0, y: 22 }} whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-60px' }} transition={{ duration: 0.6, delay: atraso, ease: [0.2, 0.7, 0.2, 1] }}>
      {children}
    </motion.div>
  );
}
