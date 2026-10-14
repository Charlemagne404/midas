import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './e2e',
  testMatch: 'reality.spec.ts',
  workers: 1,
  use: {
    baseURL: 'http://127.0.0.1:5180',
    headless: true,
    viewport: { width: 1600, height: 1100 },
  },
  outputDir: 'test-results/reality',
  reporter: 'list',
});
