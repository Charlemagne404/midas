import { defineConfig } from '@playwright/test';
import { existsSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const webRoot = dirname(fileURLToPath(import.meta.url));
const repository = resolve(webRoot, '../..');
const python =
  process.env.MIDAS_PYTHON ??
  (existsSync(join(repository, '.venv/bin/python'))
    ? join(repository, '.venv/bin/python')
    : '/home/charlie/midas/.venv/bin/python');
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
      command: `${python} -m uvicorn apps.api.main:app --host 127.0.0.1 --port 18000`,
      cwd: repository,
      url: 'http://127.0.0.1:18000/api/health',
      reuseExistingServer: false,
      env: {
        MIDAS_MODE: 'demo',
        MIDAS_DATABASE_URL: `sqlite+aiosqlite:///${database}`,
        MIDAS_ARENA_ROOT: join(dirname(database), 'arena'),
      },
    },
    {
      command: 'corepack pnpm dev --port 15173',
      cwd: webRoot,
      env: { MIDAS_API_TARGET: 'http://127.0.0.1:18000' },
      url: 'http://127.0.0.1:15173',
      reuseExistingServer: false,
    },
  ],
  reporter: 'list',
});
