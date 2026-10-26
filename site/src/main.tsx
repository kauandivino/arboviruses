import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import '@fontsource/raleway/500.css';
import '@fontsource/raleway/700.css';
import '@fontsource/raleway/800.css';
import '@fontsource/raleway/900.css';
import '@fontsource-variable/inter';
import './styles/base.css';
import './styles/secoes.css';
import { App } from './App';

createRoot(document.getElementById('raiz')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
