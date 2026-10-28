import { defineConfig } from '@playwright/test';
import { randomUUID } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import {
  existsSync,
  lstatSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  realpathSync,
  writeFileSync,
} from 'node:fs';
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
const temporaryRoot = resolve(tmpdir());
const browserRoot = resolve(
  process.env.MIDAS_FRONTIER_E2E_ROOT ?? mkdtempSync(join(temporaryRoot, 'midas-browser-')),
);
if (dirname(browserRoot) !== temporaryRoot || !basename(browserRoot).startsWith('midas-browser-')) {
  throw new Error('Playwright browser root must be an isolated temporary directory');
}
const rootOwnerPath = join(browserRoot, '.midas-frontier-e2e-owner');
if (existsSync(browserRoot)) {
  const rootMetadata = lstatSync(browserRoot);
  if (!rootMetadata.isDirectory() || rootMetadata.isSymbolicLink()) {
    throw new Error('Playwright browser root must be a real directory');
  }
  const runId = process.env.MIDAS_FRONTIER_E2E_RUN_ID;
  if (runId) {
    if (!existsSync(rootOwnerPath)) {
      throw new Error('Playwright browser root is missing its current-run owner marker');
    }
    const ownerMetadata = lstatSync(rootOwnerPath);
    if (!ownerMetadata.isFile() || ownerMetadata.isSymbolicLink()) {
      throw new Error('Playwright browser root owner marker must be a regular file');
    }
    const expectedOwner = `${runId}\n${realpathSync(browserRoot)}\n`;
    if (readFileSync(rootOwnerPath, 'utf8') !== expectedOwner) {
      throw new Error('Playwright browser root belongs to a different run');
    }
  } else {
    if (readdirSync(browserRoot).length > 0) {
      throw new Error('Playwright browser root must be fresh and empty');
    }
    const newRunId = randomUUID();
    process.env.MIDAS_FRONTIER_E2E_RUN_ID = newRunId;
    writeFileSync(rootOwnerPath, `${newRunId}\n${realpathSync(browserRoot)}\n`, {
      flag: 'wx',
      mode: 0o600,
    });
  }
} else {
  mkdirSync(browserRoot);
  const newRunId = process.env.MIDAS_FRONTIER_E2E_RUN_ID ?? randomUUID();
  process.env.MIDAS_FRONTIER_E2E_RUN_ID = newRunId;
  writeFileSync(rootOwnerPath, `${newRunId}\n${realpathSync(browserRoot)}\n`, {
    flag: 'wx',
    mode: 0o600,
  });
}
if (dirname(realpathSync(browserRoot)) !== realpathSync(temporaryRoot)) {
  throw new Error('Playwright browser root must resolve directly inside the temporary directory');
}
process.env.MIDAS_FRONTIER_E2E_ROOT = browserRoot;
const database = join(browserRoot, 'paper.db');
const frontierRoot = join(browserRoot, 'frontier');
const arenaRoot = join(browserRoot, 'arena');
const seededArenaJob = join(arenaRoot, 'jobs', 'job-e2e0123456789abcdef01234', 'job.json');
const seedSyntheticFrontier = process.env.MIDAS_SEED_FRONTIER_E2E === '1';
const seedCapturedFrontier = process.env.MIDAS_FRONTIER_E2E_CAPTURED === '1';
if (seedSyntheticFrontier && seedCapturedFrontier) {
  throw new Error('Choose either the synthetic or captured Frontier E2E store');
}
if (seedCapturedFrontier) {
  if (existsSync(arenaRoot)) {
    throw new Error('Captured Frontier E2E must not reuse an Arena fixture root');
  }
  const seed = spawnSync(
    python,
    [join(webRoot, 'e2e/seed_captured_frontier_store.py'), frontierRoot],
    {
      cwd: repository,
      env: { ...process.env, PYTHONPATH: join(repository, 'packages') },
      stdio: 'inherit',
    },
  );
  if (seed.error) throw seed.error;
  if (seed.status !== 0) throw new Error(`Captured Frontier E2E seeder exited with ${seed.status}`);
} else if (seedSyntheticFrontier) {
  const historyStoreExists = existsSync(join(frontierRoot, 'frontier.sqlite3'));
  const arenaJobExists = existsSync(seededArenaJob);
  if (historyStoreExists !== arenaJobExists || (!historyStoreExists && existsSync(arenaRoot))) {
    throw new Error('Refusing to seed a partially populated Frontier/Arena E2E root');
  }
  if (!historyStoreExists) {
    const seed = spawnSync(python, [join(webRoot, 'e2e/seed_frontier_store.py'), frontierRoot], {
      cwd: repository,
      env: { ...process.env, PYTHONPATH: join(repository, 'packages') },
      stdio: 'inherit',
    });
    if (seed.error) throw seed.error;
    if (seed.status !== 0) throw new Error(`Frontier E2E seeder exited with ${seed.status}`);
  }
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
        MIDAS_ARENA_ROOT: arenaRoot,
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
