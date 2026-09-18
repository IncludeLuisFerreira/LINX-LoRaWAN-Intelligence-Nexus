import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import './index.css';

async function prepareApp() {
  // Permite ativar o MSW se estiver em DEV ou se a flag VITE_ENABLE_MOCKS for 'true'
  const shouldEnableMocks =
    import.meta.env.DEV || import.meta.env.VITE_ENABLE_MOCKS === 'true';

  if (shouldEnableMocks) {
    const { worker } = await import('./mocks/browser');
    return worker.start({ onUnhandledRequest: 'bypass' });
  }
}

prepareApp().then(() => {
  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </React.StrictMode>,
  );
});
