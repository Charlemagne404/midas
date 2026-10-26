import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import { integratedIdentity } from './build-identity.mjs';
export default defineConfig({
  plugins: [react()],
  define: {
    'import.meta.env.VITE_MIDAS_INTEGRATED_BRANCH': JSON.stringify(integratedIdentity.branch),
    'import.meta.env.VITE_MIDAS_INTEGRATED_COMMIT': JSON.stringify(integratedIdentity.commit),
    'import.meta.env.VITE_MIDAS_INTEGRATED_DIRTY': JSON.stringify(integratedIdentity.dirty),
  },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.tsx'],
    setupFiles: ['./src/test-setup.ts'],
  },
});
