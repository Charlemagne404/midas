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
import { basename, delimiter, dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const webRoot = dirname(fileURLToPath(import.meta.url));
const repository = resolve(webRoot, '../..');
const python =
  process.env.MIDAS_PYTHON ??
  (existsSync(join(repository, '.venv/bin/python'))
    ? join(repository, '.venv/bin/python')
    : (process.env.PYTHON ?? 'python3'));
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
const runtimeRoot = join(browserRoot, 'runtime');
const recordingRoot = join(browserRoot, 'recordings');
const laboratoryRoot = join(browserRoot, 'laboratory');
const realityRoot = join(browserRoot, 'reality');
const homeRoot = join(browserRoot, 'home');
const xdgCacheRoot = join(browserRoot, 'xdg-cache');
const xdgConfigRoot = join(browserRoot, 'xdg-config');
const xdgStateRoot = join(browserRoot, 'xdg-state');
const xdgRuntimeRoot = join(browserRoot, 'xdg-runtime');
for (const path of [homeRoot, xdgCacheRoot, xdgConfigRoot, xdgStateRoot, xdgRuntimeRoot]) {
  mkdirSync(path, { recursive: true, mode: 0o700 });
}
const seededArenaJob = join(arenaRoot, 'jobs', 'job-e2e0123456789abcdef01234', 'job.json');
const seedSyntheticFrontier = process.env.MIDAS_SEED_FRONTIER_E2E === '1';
const seedCapturedFrontier = process.env.MIDAS_FRONTIER_E2E_CAPTURED === '1';
const phase5TestSupportRoot = process.env.MIDAS_PHASE5_TEST_SUPPORT_ROOT;
const phase5TestSupportBin = phase5TestSupportRoot
  ? join(phase5TestSupportRoot, 'bin')
  : undefined;
const useSyntheticResourceAdmission =
  process.env.MIDAS_PHASE5_SYNTHETIC_USER_PSI === '1' && Boolean(phase5TestSupportRoot);
if (phase5TestSupportRoot && !existsSync(join(phase5TestSupportRoot, 'sitecustomize.py'))) {
  throw new Error('Phase 5 test support root is missing its isolation shim');
}
if (
  useSyntheticResourceAdmission &&
  ['systemctl', 'systemd-run', 'busctl', 'dbus-send', 'gdbus', 'sudo'].some(
    (command) => !existsSync(join(phase5TestSupportBin!, command)),
  )
) {
  throw new Error('Phase 5 test support root is missing its service-command blockers');
}
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
  outputDir: join(browserRoot, 'test-results'),
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
        MIDAS_RUNTIME_ROOT: runtimeRoot,
        MIDAS_DATABASE_URL: `sqlite+aiosqlite:///${database}`,
        MIDAS_RECORDING_ROOT: recordingRoot,
        MIDAS_LABORATORY_ROOT: laboratoryRoot,
        MIDAS_ARENA_ROOT: arenaRoot,
        MIDAS_FRONTIER_ROOT: frontierRoot,
        MIDAS_REALITY_WORKSPACE: realityRoot,
        MIDAS_VERITAS_WORKSPACE: process.env.MIDAS_VERITAS_WORKSPACE ?? repository,
        HOME: homeRoot,
        XDG_CACHE_HOME: xdgCacheRoot,
        XDG_CONFIG_HOME: xdgConfigRoot,
        XDG_STATE_HOME: xdgStateRoot,
        XDG_RUNTIME_DIR: xdgRuntimeRoot,
        DBUS_SESSION_BUS_ADDRESS: `unix:path=${join(browserRoot, 'no-user-bus')}`,
        DBUS_SYSTEM_BUS_ADDRESS: `unix:path=${join(browserRoot, 'no-system-bus')}`,
        SYSTEMD_BUS_ADDRESS: `unix:path=${join(browserRoot, 'no-system-bus')}`,
        MIDAS_FRONTIER_POLYMARKET_PUBLIC_PROBE_ENABLED: 'false',
        MIDAS_FRONTIER_KALSHI_PUBLIC_PROBE_ENABLED: 'false',
        MIDAS_FRONTIER_KRAKEN_PUBLIC_PROBE_ENABLED: 'false',
        MIDAS_FRONTIER_COINBASE_PUBLIC_PROBE_ENABLED: 'false',
        ...(useSyntheticResourceAdmission
          ? {
              MIDAS_PHASE5_SYNTHETIC_USER_PSI: '1',
              MIDAS_PHASE5_ISOLATED_API: '1',
              MIDAS_BLOCKED_COMMAND_LOG: join(browserRoot, 'blocked-commands.log'),
              PATH: `${phase5TestSupportBin!}${delimiter}${process.env.PATH ?? ''}`,
            }
          : {}),
        PYTHONPATH: [
          ...(useSyntheticResourceAdmission ? [phase5TestSupportRoot!] : []),
          join(repository, 'packages'),
        ].join(delimiter),
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
