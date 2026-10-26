import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Caminhos relativos: o site é servido na raiz e também pode ser aberto em subpastas.
export default defineConfig({
  base: './',
  plugins: [react()],
  build: { outDir: 'dist', emptyOutDir: true, chunkSizeWarningLimit: 1200 },
});
