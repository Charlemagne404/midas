import { test, expect } from '@playwright/test';

test('native Reality exposes genuine evidence and frozen replay without synthetic labeling', async ({
  page,
}) => {
  // Keep this browser pass isolated from source payloads and service controls.
  await page.route('**/api/reality/records/**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        record: {
          ordinal: 1,
          kind: 'frame',
          schema_version: 1,
          payload: { fixture: 'isolated browser source record' },
        },
        payload_truncated: false,
        segment: '00000000000000000001-00000000000000000000000000000000.seg',
        offset: 8,
        canonical_record_sha256: '0'.repeat(64),
        compressed_record_sha256: '0'.repeat(64),
      }),
    });
  });
  await page.route('**/api/reality/operations', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        services: [
          {
            unit: 'midas-reality.service',
            available: true,
            properties: {
              ActiveState: 'active',
              SubState: 'running',
              MainPID: '12345',
              NRestarts: '0',
              MemoryCurrent: '16777216',
            },
          },
        ],
        configuration: {},
        storage_policy: {},
        controls: ['check-capacity'],
        collector_deployment: 'isolated browser fixture',
      }),
    });
  });
  await page.route('**/api/reality/operations/**', async (route) => {
    if (route.request().method() !== 'POST') {
      await route.continue();
      return;
    }
    const action = new URL(route.request().url()).pathname.split('/').at(-1);
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        action,
        accepted: action === 'check-capacity',
        detail: 'isolated fixture',
      }),
    });
  });
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await expect
    .poll(
      async () => {
        const r = await page.request.get('/api/health');
        return r.ok() ? (await r.json()).startup_status : 'WAITING';
      },
      { timeout: 20000 },
    )
    .toBe('READY');
  await page.goto('/');
  await page.getByRole('button', { name: 'Reality', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'The observation panel', exact: true }),
  ).toBeVisible();
  await expect(page.getByText('DEMO · SYNTHETIC', { exact: true })).toHaveCount(0);
  await expect(page.getByText('REALITY · PUBLIC OBSERVATIONS', { exact: true })).toBeVisible();
  await expect(page.getByText('No scientific champion', { exact: true })).toBeVisible();
  const nav = page.getByRole('navigation', { name: 'Reality research areas' });
  const boxes = await nav
    .getByRole('button')
    .evaluateAll((nodes) => nodes.map((n) => n.getBoundingClientRect().top));
  expect(new Set(boxes).size).toBe(1);
  await page.screenshot({ path: test.info().outputPath('reality-overview.png'), fullPage: true });
  await nav.getByRole('button', { name: 'Live explorer', exact: false }).click();
  await expect(page.getByLabel('Search Reality markets')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Yes', exact: true })).toBeVisible();
  await page.getByLabel('Hypothetical share quantity').fill('100000');
  await expect(page.getByText(/Before fees/).first()).toBeVisible();
  await expect(page.getByLabel('Replay historical observations')).toBeVisible();
  await page.getByLabel('Historical metric').selectOption('spread');
  await page.screenshot({ path: test.info().outputPath('reality-explorer.png'), fullPage: true });
  await nav.getByRole('button', { name: 'Historical', exact: false }).click();
  await expect(page.getByLabel('Historical interval end UTC')).toBeVisible();
  await nav.getByRole('button', { name: 'Opportunities', exact: false }).click();
  await expect(page.getByRole('checkbox')).toBeChecked();
  await page.getByRole('checkbox').uncheck();
  await expect(page.getByRole('button', { name: 'Inspect', exact: true }).first()).toBeVisible();
  await page.getByRole('button', { name: 'Inspect', exact: true }).first().click();
  await expect(page.getByRole('dialog', { name: 'Frozen decision replay' })).toBeVisible();
  await expect(
    page.getByRole('heading', { name: 'Later observations, kept separate' }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Verify exact input source record' }).click();
  await expect(page.getByText('Checksum-verified raw input record', { exact: true })).toBeVisible();
  await page.screenshot({ path: test.info().outputPath('reality-replay.png'), fullPage: true });
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  for (const name of ['Calibration', 'Models', 'Shadow', 'Forward', 'Operations']) {
    await nav.getByRole('button', { name, exact: false }).click();
    await expect(
      page.locator('.r-empty').filter({ hasText: 'Loading versioned research evidence…' }),
    ).toHaveCount(0);
    await page.screenshot({
      path: test.info().outputPath(`reality-${name.toLowerCase()}.png`),
      fullPage: true,
    });
  }
  await expect(page.getByText('midas-reality.service', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Check capacity', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Check capacity', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('check-capacity: accepted by systemd');
  // The capacity check is read-only; scheduling and recorder state remain unchanged.
  await page.setViewportSize({ width: 390, height: 844 });
  await nav.getByRole('button', { name: 'Overview', exact: false }).click();
  await expect(
    page.getByRole('heading', { name: 'The observation panel', exact: true }),
  ).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
  await page.screenshot({ path: test.info().outputPath('reality-mobile.png'), fullPage: true });
  expect(errors).toEqual([]);
});
