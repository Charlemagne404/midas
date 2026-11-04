import { defineConfig } from '@playwright/test';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const webRoot = dirname(fileURLToPath(import.meta.url));
const repository = resolve(webRoot, '../..');
const python = process.env.MIDAS_PYTHON ?? join(repository, '.venv/bin/python');
const scratch = mkdtempSync(join(tmpdir(), 'midas-observatory-browser-'));

export default defineConfig({
  testDir: './e2e',
  testMatch: 'observatory.spec.ts',
  workers: 1,
  use: {
    baseURL: 'http://127.0.0.1:15175',
    headless: true,
    viewport: { width: 1440, height: 1000 },
  },
  webServer: [
    {
      command: `${python} -m uvicorn apps.api.main:app --host 127.0.0.1 --port 18001`,
      cwd: repository,
      url: 'http://127.0.0.1:18001/api/health',
      reuseExistingServer: false,
      env: {
        MIDAS_MODE: 'demo',
        MIDAS_DATABASE_URL: `sqlite+aiosqlite:///${join(scratch, 'paper.db')}`,
        MIDAS_LABORATORY_ROOT: join(scratch, 'laboratory'),
        MIDAS_ARENA_ROOT: join(repository, 'data/arena'),
        MIDAS_VERITAS_WORKSPACE: process.env.MIDAS_VERITAS_WORKSPACE ?? repository,
        PYTHONPATH: join(repository, 'packages'),
      },
    },
    {
      command: 'corepack pnpm dev --port 15175 --strictPort',
      cwd: webRoot,
      url: 'http://127.0.0.1:15175',
      reuseExistingServer: false,
      env: { MIDAS_API_TARGET: 'http://127.0.0.1:18001' },
    },
  ],
  reporter: 'list',
});
