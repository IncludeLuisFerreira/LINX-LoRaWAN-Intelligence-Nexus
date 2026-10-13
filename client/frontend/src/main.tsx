import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import './index.css';

async function prepareApp() {
  // MSW é opt-in: ligue com VITE_ENABLE_MOCKS=true para demos sem backend.
  // Em dev, o proxy do Vite encaminha /api para o identity_api real.
  const shouldEnableMocks = import.meta.env.VITE_ENABLE_MOCKS === 'true';

  if (shouldEnableMocks) {
    const { worker } = await import('./mocks/browser');
    return worker.start({ onUnhandledRequest: 'bypass' });
  }
}

prepareApp()
  .catch((error: unknown) => {
    console.error('Falha ao inicializar os mocks:', error);
  })
  .finally(() => {
    ReactDOM.createRoot(document.getElementById('root')!).render(
      <React.StrictMode>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </React.StrictMode>,
    );
  });
