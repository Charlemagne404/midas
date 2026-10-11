import { defineConfig } from '@playwright/test';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
const database = join(mkdtempSync(join(tmpdir(), 'midas-browser-')), 'paper.db');
export default defineConfig({
  testDir: './e2e',
  workers: 1,
  use: {
    baseURL: 'http://127.0.0.1:15173',
    headless: true,
    viewport: { width: 1440, height: 1000 },
  },
  webServer: [
    {
      command: '.venv/bin/uvicorn apps.api.main:app --host 127.0.0.1 --port 18000',
      cwd: '../..',
      url: 'http://127.0.0.1:18000/api/health',
      reuseExistingServer: false,
      env: { MIDAS_MODE: 'demo', MIDAS_DATABASE_URL: `sqlite+aiosqlite:///${database}` },
    },
    {
      command: 'corepack pnpm dev --port 15173',
      env: { MIDAS_API_TARGET: 'http://127.0.0.1:18000' },
      url: 'http://127.0.0.1:15173',
      reuseExistingServer: false,
    },
  ],
  reporter: 'list',
});
