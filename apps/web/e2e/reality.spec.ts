import { test, expect } from '@playwright/test';

test('native Reality exposes source inspection with explicit synthetic fixture labeling', async ({
  page,
}) => {
  // Deterministic UI data is explicitly marked synthetic and stays outside research evidence.
  const nowNs = Date.now() * 1_000_000;
  const yesAsset = 'yes-asset-browser-fixture';
  const noAsset = 'no-asset-browser-fixture';
  const condition = '0x' + '1'.repeat(64);
  const segment = '00000000000000000001-00000000000000000000000000000000.seg';
  const decisionId = 'a'.repeat(64);
  const book = (bid: string, ask: string) => ({
    received_ns: nowNs,
    last: [2, 0],
    issue: null,
    best_bid: bid,
    best_ask: ask,
    spread: (Number(ask) - Number(bid)).toFixed(2),
    asks: [[ask, '100']],
    depth_truncated: false,
  });
  await page.route('**/api/reality/overview', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        now_ns: nowNs,
        collector_status_age_seconds: 0,
        health: 'recording',
        collector: {
          evidence_classification: 'SYNTHETIC_TEST_FIXTURE',
          state: 'RECORDING_UNSEQUENCED',
          markets: 1,
          expected_books: 2,
          fresh_books: 2,
          ordinal: 2,
          frames: 1,
          started_ns: nowNs - 10_000_000_000,
          sequence_verified: false,
          cohort: [
            {
              id: 'browser-fixture-market',
              condition,
              question: 'Browser fixture market',
              metadata_ordinal: 1,
              protocol: 'v1',
              selection_role: 'reference',
              negative_risk: false,
              tokens: { [yesAsset]: 'Yes', [noAsset]: 'No' },
            },
          ],
          books: { [yesAsset]: book('0.49', '0.51'), [noAsset]: book('0.48', '0.50') },
          observation_coverage: {
            [yesAsset]: {
              first_received_ns: nowNs - 1_000_000_000,
              last_received_ns: nowNs,
              book_update_frames: 2,
            },
            [noAsset]: {
              first_received_ns: nowNs - 1_000_000_000,
              last_received_ns: nowNs,
              book_update_frames: 2,
            },
          },
        },
        forward: {},
        capacity: {},
      }),
    });
  });
  await page.route('**/api/reality/history**', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        rows: [
          {
            event_seq: 2,
            ns: nowNs,
            legs: {
              yes: {
                best_ask: '0.51',
                spread: '0.02',
                total_ask_quantity: 100,
                snapshot: [1, 0],
                last: [2, 0],
              },
              no: {
                best_ask: '0.50',
                spread: '0.02',
                total_ask_quantity: 100,
                snapshot: [1, 0],
                last: [2, 0],
              },
            },
          },
        ],
        truncated: false,
      }),
    }),
  );
  await page.route(/\/api\/reality\/decisions(?:\/|\?|$)/, async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname.endsWith('/decisions')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          rows: [
            {
              id: decisionId,
              decision_ns: nowNs,
              decision_ordinal: 2,
              market_title: 'Browser fixture market',
              condition,
              baseline: {
                opportunity: false,
                acquisition: { yes: { value: '0.51' }, no: { value: '0.50' } },
              },
              policies: [{ action: 'abstain' }],
            },
          ],
          has_more: false,
        }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        commit_ns: nowNs,
        decision: {
          market_title: 'Browser fixture market',
          decision_ns: nowNs,
          source_record_ref: { ordinal: 1, segment, offset: 8 },
          policies: [{ policy: 'no_trade', action: 'abstain', reason: 'fixture_only' }],
        },
        outcomes: [{ horizon_ms: 1000, labels: { status: 'censored', reason: 'fixture_only' } }],
      }),
    });
  });
  // Keep source-record inspection and service controls inside this browser fixture.
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
  await expect(page.getByText('SYNTHETIC TEST FIXTURE · NOT MARKET EVIDENCE')).toBeVisible();
  await expect(
    page.getByText(/Synthetic test fixture · UI-only data\./, { exact: false }),
  ).toBeVisible();
  await expect(page.getByText('REALITY · RESEARCH EVIDENCE', { exact: true })).toBeVisible();
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
