import { test, expect } from '@playwright/test';

test('renders isolated Reality evidence fixtures through explorer and replay without implying execution', async ({
  page,
}) => {
  // Route every Reality data surface to bounded local fixtures; never query machine-local archives.
  const nowNs = Date.now() * 1_000_000;
  const condition = 'e2e-fixture-condition';
  const yesAsset = 'e2e-fixture-yes-asset';
  const noAsset = 'e2e-fixture-no-asset';
  const segment = '00000000000000000001-00000000000000000000000000000000.seg';
  const overview = {
    now_ns: nowNs,
    collector_status_age_seconds: 0,
    health: 'recording',
    capture_health: 'recording',
    health_reasons: [],
    source_quality: { status: 'available', current_issues: [], observability_gaps: [] },
    collector: {
      updated_ns: nowNs,
      ordinal: 24,
      frames: 12,
      markets: 1,
      fresh_books: 2,
      expected_books: 2,
      storage_bytes: 2048,
      started_ns: nowNs - 3_600_000_000_000,
      gaps: 0,
      timing_uncertain_books: 0,
      failures: 0,
      cohort: [
        {
          condition,
          question: 'E2E fixture only: binary market for isolated UI verification',
          protocol: 'ctf',
          selection_role: 'stable_control',
          metadata_ordinal: 1,
          negative_risk: false,
          tokens: { [yesAsset]: 'Yes', [noAsset]: 'No' },
        },
      ],
      books: {
        [yesAsset]: {
          received_ns: nowNs - 1_000_000_000,
          asks: [['0.40', '100']],
          best_bid: '0.39',
          best_ask: '0.40',
          spread: '0.01',
          last: [24, 0],
          depth_truncated: false,
          issue: null,
        },
        [noAsset]: {
          received_ns: nowNs - 1_000_000_000,
          asks: [['0.55', '100']],
          best_bid: '0.54',
          best_ask: '0.55',
          spread: '0.01',
          last: [24, 1],
          depth_truncated: false,
          issue: null,
        },
      },
      observation_coverage: {
        [yesAsset]: {
          first_received_ns: nowNs - 10_000_000_000,
          last_received_ns: nowNs - 1_000_000_000,
          book_update_frames: 3,
        },
        [noAsset]: {
          first_received_ns: nowNs - 10_000_000_000,
          last_received_ns: nowNs - 1_000_000_000,
          book_update_frames: 3,
        },
      },
    },
    forward: {
      state: 'fixture_only',
      decisions: 1,
      markets: 1,
      families: 1,
      days: ['2026-10-26'],
      followups: { observed_public_measurement: 0, censored: 1 },
    },
    capacity: { estimated_storage_seconds_remaining: null },
    schedule: {},
    integrity: {},
    execution_ground_truth: 'unknown_counterfactual',
    orders_submitted: 0,
  };
  const historyRow = {
    event_seq: 1,
    ns: nowNs - 5_000_000_000,
    condition,
    legs: {
      yes: {
        best_ask: '0.40',
        best_bid: '0.39',
        spread: '0.01',
        total_ask_quantity: '100',
        last: [24, 0],
      },
      no: {
        best_ask: '0.55',
        best_bid: '0.54',
        spread: '0.01',
        total_ask_quantity: '100',
        last: [24, 1],
      },
    },
    quality_reason: null,
  };
  const decision = {
    id: 'e2e-fixture-decision',
    market_title: 'E2E fixture only: binary market for isolated UI verification',
    condition,
    decision_ns: nowNs - 2_000_000_000,
    decision_ordinal: 20,
    quality_reason: null,
    baseline: {
      opportunity: true,
      acquisition: { yes: { value: '0.40' }, no: { value: '0.55' } },
    },
    policies: [{ policy: 'fixture_policy', action: 'abstain' }],
  };
  await page.route(
    (url) => url.pathname === '/api/reality/overview',
    (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(overview),
      }),
  );
  await page.route(
    (url) => url.pathname === '/api/reality/history',
    (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ rows: [historyRow], truncated: false }),
      }),
  );
  await page.route(
    (url) => url.pathname === '/api/reality/decisions',
    (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ rows: [decision], has_more: false }),
      }),
  );
  await page.route(
    (url) => url.pathname === `/api/reality/decisions/${decision.id}`,
    (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          decision: {
            ...decision,
            reconstruction_version: 'fixture-reconstruction-v1',
            producer_implementation_sha256: '0'.repeat(64),
            source_input_lag_ns: 100,
            decision_latency_ns: 300,
            source_record_ref: { ordinal: 1, segment, offset: 8 },
            features: { fixture: true },
            predictions: { fixture: true },
            feature_sources: { fixture: 'fixture record' },
          },
          commit_ns: nowNs - 1_900_000_000,
          outcomes: [
            {
              horizon_ms: 1000,
              labels: { status: 'future_observation_not_recorded', reason: 'fixture censoring' },
              execution: [],
            },
          ],
        }),
      }),
  );
  await page.route(
    (url) => url.pathname === '/api/reality/forward',
    (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ rows: [] }),
      }),
  );
  await page.route(
    (url) => url.pathname.startsWith('/api/reality/artifacts/'),
    (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ data: {} }),
      }),
  );

  // Keep source-record lookups and service controls isolated too.
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
  await expect(
    page.getByText('PROJECT REALITY / CALIBRATION LABORATORY', { exact: true }),
  ).toBeVisible();
  await expect(page.getByText('NO ORDER EXECUTION', { exact: true })).toBeVisible();
  const nav = page.getByRole('navigation', { name: 'Reality research areas' });
  await nav.getByRole('button', { name: 'Models', exact: false }).click();
  await expect(page.getByText('No scientific champion', { exact: true })).toBeVisible();
  await nav.getByRole('button', { name: 'Overview', exact: false }).click();
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
