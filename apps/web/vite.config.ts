import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { integratedIdentity } from './build-identity.mjs';

export default defineConfig({
  plugins: [react()],
  define: {
    'import.meta.env.VITE_MIDAS_INTEGRATED_BRANCH': JSON.stringify(integratedIdentity.branch),
    'import.meta.env.VITE_MIDAS_INTEGRATED_COMMIT': JSON.stringify(integratedIdentity.commit),
    'import.meta.env.VITE_MIDAS_INTEGRATED_DIRTY': JSON.stringify(integratedIdentity.dirty),
  },
  server: {
    proxy: {
      '/api': {
        target: process.env.MIDAS_API_TARGET ?? 'http://127.0.0.1:8000',
        changeOrigin: false,
      },
    },
  },
});
