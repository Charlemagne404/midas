import { defineConfig } from '@playwright/test';
import { existsSync, mkdirSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { delimiter, dirname, join, resolve } from 'node:path';
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
const homeRoot = join(isolatedData, 'home');
const xdgCacheRoot = join(isolatedData, 'xdg-cache');
const xdgConfigRoot = join(isolatedData, 'xdg-config');
const xdgStateRoot = join(isolatedData, 'xdg-state');
const xdgRuntimeRoot = join(isolatedData, 'xdg-runtime');
for (const path of [homeRoot, xdgCacheRoot, xdgConfigRoot, xdgStateRoot, xdgRuntimeRoot]) {
  mkdirSync(path, { recursive: true, mode: 0o700 });
}
const phase5TestSupportRoot = process.env.MIDAS_PHASE5_TEST_SUPPORT_ROOT;
const phase5TestSupportBin = phase5TestSupportRoot ? join(phase5TestSupportRoot, 'bin') : undefined;
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
const python =
  process.env.MIDAS_PYTHON ??
  (existsSync(join(repository, '.venv/bin/python'))
    ? join(repository, '.venv/bin/python')
    : (process.env.PYTHON ?? 'python3'));

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
        MIDAS_MODE: 'demo',
        MIDAS_RUNTIME_ROOT: runtimeRoot,
        MIDAS_DATABASE_URL: `sqlite+aiosqlite:///${join(isolatedData, 'paper.db')}`,
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
        DBUS_SESSION_BUS_ADDRESS: `unix:path=${join(isolatedData, 'no-user-bus')}`,
        DBUS_SYSTEM_BUS_ADDRESS: `unix:path=${join(isolatedData, 'no-system-bus')}`,
        SYSTEMD_BUS_ADDRESS: `unix:path=${join(isolatedData, 'no-system-bus')}`,
        MIDAS_FRONTIER_POLYMARKET_PUBLIC_PROBE_ENABLED: 'false',
        MIDAS_FRONTIER_KALSHI_PUBLIC_PROBE_ENABLED: 'false',
        MIDAS_FRONTIER_KRAKEN_PUBLIC_PROBE_ENABLED: 'false',
        MIDAS_FRONTIER_COINBASE_PUBLIC_PROBE_ENABLED: 'false',
        ...(useSyntheticResourceAdmission
          ? {
              MIDAS_PHASE5_SYNTHETIC_USER_PSI: '1',
              MIDAS_PHASE5_ISOLATED_API: '1',
              MIDAS_BLOCKED_COMMAND_LOG: join(isolatedData, 'blocked-commands.log'),
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
      command: 'corepack pnpm dev --port 5181',
      cwd: webRoot,
      url: 'http://127.0.0.1:5181',
      reuseExistingServer: false,
      env: { MIDAS_API_TARGET: 'http://127.0.0.1:18001' },
    },
  ],
});
