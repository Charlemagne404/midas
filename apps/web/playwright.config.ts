import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './e2e',
  use: {
    baseURL: 'http://127.0.0.1:5173',
    headless: true,
    viewport: { width: 1440, height: 1000 },
  },
  webServer: [
    {
      command: '.venv/bin/uvicorn apps.api.main:app --host 127.0.0.1 --port 8000',
      cwd: '../..',
      url: 'http://127.0.0.1:8000/api/health',
      reuseExistingServer: !process.env.CI,
      env: { MIDAS_MODE: 'demo' },
    },
    {
      command: 'corepack pnpm dev',
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: !process.env.CI,
    },
  ],
  reporter: 'list',
});
