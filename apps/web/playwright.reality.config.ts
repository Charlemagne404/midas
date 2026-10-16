import { defineConfig } from '@playwright/test';
import { existsSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const webRoot = dirname(fileURLToPath(import.meta.url));
const repository = resolve(webRoot, '../..');
const isolatedData = mkdtempSync(join(tmpdir(), 'midas-reality-browser-'));
const python =
  process.env.MIDAS_PYTHON ??
  (existsSync(join(repository, '.venv/bin/python'))
    ? join(repository, '.venv/bin/python')
    : '/home/charlie/midas/.venv/bin/python');

export default defineConfig({
  testDir: './e2e',
  testMatch: 'reality.spec.ts',
  workers: 1,
  use: {
    baseURL: 'http://127.0.0.1:5181',
    headless: true,
    viewport: { width: 1600, height: 1100 },
  },
  outputDir: 'test-results/reality-isolated',
  reporter: 'list',
  webServer: [
    {
      command: `${python} -m uvicorn apps.api.main:app --host 127.0.0.1 --port 18001`,
      cwd: repository,
      url: 'http://127.0.0.1:18001/api/health',
      reuseExistingServer: false,
      env: {
        PYTHONPATH: join(repository, 'packages'),
        MIDAS_MODE: 'demo',
        MIDAS_DATABASE_URL: `sqlite+aiosqlite:///${join(isolatedData, 'paper.db')}`,
        MIDAS_ARENA_ROOT: join(isolatedData, 'arena'),
        MIDAS_REALITY_WORKSPACE: process.env.MIDAS_REALITY_WORKSPACE ?? repository,
      },
    },
    {
      command: 'corepack pnpm dev --port 5181',
      cwd: webRoot,
      url: 'http://127.0.0.1:5181',
      reuseExistingServer: false,
      env: { MIDAS_API_TARGET: 'http://127.0.0.1:18001' },
    },
  ],
});
