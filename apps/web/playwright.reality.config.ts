import { defineConfig } from '@playwright/test';
import { existsSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const webRoot = dirname(fileURLToPath(import.meta.url));
const repository = resolve(webRoot, '../..');
const isolatedData = mkdtempSync(join(tmpdir(), 'midas-reality-browser-'));
const runtimeRoot = join(isolatedData, 'runtime');
const recordingRoot = join(isolatedData, 'recordings');
const laboratoryRoot = join(isolatedData, 'laboratory');
const arenaRoot = join(isolatedData, 'arena');
const frontierRoot = join(isolatedData, 'frontier');
const realityRoot = join(isolatedData, 'reality');
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
  outputDir: join(isolatedData, 'test-results'),
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
        MIDAS_RUNTIME_ROOT: runtimeRoot,
        MIDAS_DATABASE_URL: `sqlite+aiosqlite:///${join(isolatedData, 'paper.db')}`,
        MIDAS_RECORDING_ROOT: recordingRoot,
        MIDAS_LABORATORY_ROOT: laboratoryRoot,
        MIDAS_ARENA_ROOT: arenaRoot,
        MIDAS_FRONTIER_ROOT: frontierRoot,
        MIDAS_REALITY_WORKSPACE: realityRoot,
        MIDAS_VERITAS_WORKSPACE: repository,
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
