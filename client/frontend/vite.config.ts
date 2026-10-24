import react from '@vitejs/plugin-react';
import { defineConfig, loadEnv } from 'vite';

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_');
  const allEnv = loadEnv(mode, process.cwd(), '');
  const serviceToken = allEnv.DEV_SERVICE_TOKEN ?? '';
  return {
    plugins: [react()],
    server: {
      proxy: {
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true,
          headers: {
            'X-Service-Token': serviceToken,
          },
        },
        '/ws': {
          target: env.VITE_WS_PROXY_TARGET || 'http://localhost:8000',
          changeOrigin: true,
          ws: true,
          headers: {
            'X-Service-Token': serviceToken,
          },
        },
      },
    },
  };
});
