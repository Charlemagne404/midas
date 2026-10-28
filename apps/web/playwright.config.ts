import { defineConfig } from '@playwright/test';
import { spawnSync } from 'node:child_process';
import { existsSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { basename, dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const webRoot = dirname(fileURLToPath(import.meta.url));
const repository = resolve(webRoot, '../..');
const python =
  process.env.MIDAS_PYTHON ??
  (existsSync(join(repository, '.venv/bin/python'))
    ? join(repository, '.venv/bin/python')
    : '/home/charlie/midas/.venv/bin/python');
const browserRoot = resolve(
  process.env.MIDAS_FRONTIER_E2E_ROOT ?? mkdtempSync(join(tmpdir(), 'midas-browser-')),
);
if (dirname(browserRoot) !== tmpdir() || !basename(browserRoot).startsWith('midas-browser-')) {
  throw new Error('Playwright browser root must be an isolated temporary directory');
}
process.env.MIDAS_FRONTIER_E2E_ROOT = browserRoot;
const database = join(browserRoot, 'paper.db');
const frontierRoot = join(browserRoot, 'frontier');
if (
  process.env.MIDAS_SEED_FRONTIER_E2E === '1' &&
  !existsSync(join(frontierRoot, 'frontier.sqlite3'))
) {
  const seed = spawnSync(python, [join(webRoot, 'e2e/seed_frontier_store.py'), frontierRoot], {
    cwd: repository,
    env: { ...process.env, PYTHONPATH: join(repository, 'packages') },
    stdio: 'inherit',
  });
  if (seed.error) throw seed.error;
  if (seed.status !== 0) throw new Error(`Frontier E2E seeder exited with ${seed.status}`);
}

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
        MIDAS_FRONTIER_ROOT: frontierRoot,
        MIDAS_VERITAS_WORKSPACE: process.env.MIDAS_VERITAS_WORKSPACE ?? repository,
        PYTHONPATH: join(repository, 'packages'),
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
