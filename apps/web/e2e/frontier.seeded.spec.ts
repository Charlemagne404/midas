import { expect, test } from '@playwright/test';

type HistoryPage = {
  items: { observation_id: string; series: { native_instrument_id: string } }[];
  returned: number;
  has_more: boolean;
};

type ReplayPage = {
  items: { run_id: string; series: { native_instrument_id: string }[] }[];
  returned: number;
  has_more: boolean;
  network_called: false;
};

test.skip(
  process.env.MIDAS_SEED_FRONTIER_E2E !== '1',
  'requires the explicit isolated deterministic Frontier store seeder',
);

test('seeded Frontier history pages and replay through the local API', async ({
  page,
  request,
}) => {
  let probeRequests = 0;
  page.on('request', (item) => {
    if (item.url().includes('/api/frontier/probe/')) probeRequests += 1;
  });

  const capturesFirstResponse = await request.get(
    'http://127.0.0.1:18000/api/frontier/price-history?venue=polymarket&limit=20&offset=0',
  );
  expect(capturesFirstResponse.status()).toBe(200);
  const capturesFirst = (await capturesFirstResponse.json()) as HistoryPage;
  expect(capturesFirst).toMatchObject({ returned: 20, has_more: true });
  expect(capturesFirst.items[0]?.series.native_instrument_id).toBe('frontier-e2e-token-20');

  const capturesSecondResponse = await request.get(
    'http://127.0.0.1:18000/api/frontier/price-history?venue=polymarket&limit=20&offset=20',
  );
  expect(capturesSecondResponse.status()).toBe(200);
  const capturesSecond = (await capturesSecondResponse.json()) as HistoryPage;
  expect(capturesSecond).toMatchObject({ returned: 1, has_more: false });
  expect(capturesSecond.items[0]?.series.native_instrument_id).toBe('frontier-e2e-token-00');

  const replayFirstResponse = await request.get(
    'http://127.0.0.1:18000/api/frontier/price-history/replays?limit=20&offset=0',
  );
  expect(replayFirstResponse.status()).toBe(200);
  const replayFirst = (await replayFirstResponse.json()) as ReplayPage;
  expect(replayFirst).toMatchObject({ returned: 20, has_more: true, network_called: false });
  expect(replayFirst.items[0]?.series[0]?.native_instrument_id).toBe('frontier-e2e-token-20');

  const replaySecondResponse = await request.get(
    'http://127.0.0.1:18000/api/frontier/price-history/replays?limit=20&offset=20',
  );
  expect(replaySecondResponse.status()).toBe(200);
  const replaySecond = (await replaySecondResponse.json()) as ReplayPage;
  expect(replaySecond).toMatchObject({ returned: 1, has_more: false, network_called: false });
  expect(replaySecond.items[0]?.series[0]?.native_instrument_id).toBe('frontier-e2e-token-00');

  await page.goto('/');
  await page.getByRole('button', { name: 'Frontier', exact: true }).click();
  await page.getByRole('button', { name: 'Replay & readiness', exact: true }).click();
  const captureList = page.getByRole('region', { name: 'Saved price-history replay inputs' });
  await expect(captureList.getByText('frontier-e2e-token-20', { exact: false })).toBeVisible();
  const checkboxes = captureList.locator('input[type="checkbox"]');
  await expect(checkboxes).toHaveCount(20);
  await checkboxes.nth(0).check();
  await checkboxes.nth(1).check();

  const replayPost = page.waitForResponse(
    (response) =>
      response.url().includes('/api/frontier/price-history/replay') &&
      response.request().method() === 'POST',
  );
  await page.getByRole('button', { name: 'Replay 2 selected series' }).click();
  const postedReplay = await replayPost;
  expect(postedReplay.status()).toBe(200);
  const postedResult = (await postedReplay.json()) as {
    run_id: string;
    manifest: { observation_ids: string[]; input_sha256: string };
    result_sha256: string;
    series: { native_instrument_id: string; raw_sha256: string }[];
  };
  expect(postedResult.manifest.observation_ids).toHaveLength(2);
  expect(postedResult.manifest.input_sha256).toMatch(/^[0-9a-f]{64}$/);
  expect(postedResult.result_sha256).toMatch(/^[0-9a-f]{64}$/);
  expect(postedResult.series.map((item) => item.native_instrument_id).sort()).toEqual([
    'frontier-e2e-token-19',
    'frontier-e2e-token-20',
  ]);

  const savedReplayResponse = await request.get(
    `http://127.0.0.1:18000/api/frontier/price-history/replays/${postedResult.run_id}`,
  );
  expect(savedReplayResponse.status()).toBe(200);
  expect(await savedReplayResponse.json()).toMatchObject({
    run_id: postedResult.run_id,
    result_sha256: postedResult.result_sha256,
  });
  await expect(page.getByText(postedResult.run_id)).toBeVisible();
  const lineage = page.getByRole('region', { name: 'Selected replay lineage' });
  await expect(
    lineage.getByRole('heading', { name: 'Polymarket · frontier-e2e-token-19' }),
  ).toBeVisible();

  await page
    .getByRole('navigation', { name: 'Saved source capture pages' })
    .getByRole('button', { name: 'Next' })
    .click();
  await expect(captureList.getByText('frontier-e2e-token-00', { exact: false })).toBeVisible();
  await expect(captureList.locator('input[type="checkbox"]')).toHaveCount(1);
  await expect(page.getByText('0 / 8 selected')).toBeVisible();

  await page
    .getByRole('navigation', { name: 'Saved replay artifact pages' })
    .getByRole('button', { name: 'Next' })
    .click();
  await expect(page.locator('.fr-history-replay-list > button')).toHaveCount(2);
  await page.locator('.fr-history-replay-list > button').nth(1).click();
  const oldestReplay = replaySecond.items[0];
  expect(oldestReplay).toBeDefined();
  await expect(lineage.getByText(oldestReplay!.run_id)).toBeVisible();
  await expect(
    lineage.getByRole('heading', { name: 'Polymarket · frontier-e2e-token-00' }),
  ).toBeVisible();
  expect(probeRequests).toBe(0);
});

test('seeded Frontier discovery artifact loads from Arena storage into Laboratory', async ({
  page,
  request,
}) => {
  let probeRequests = 0;
  let arenaMutations = 0;
  page.on('request', (item) => {
    if (item.url().includes('/api/frontier/probe/')) probeRequests += 1;
    if (item.url().includes('/api/arena/') && item.method() !== 'GET') arenaMutations += 1;
  });

  const catalogResponse = await request.get(
    'http://127.0.0.1:18000/api/arena/frontier-discovery-comparisons?limit=20',
  );
  expect(catalogResponse.status()).toBe(200);
  const catalog = (await catalogResponse.json()) as {
    items: {
      job_id: string;
      state: string;
      snapshot_id: string;
      snapshot_sha256: string;
    }[];
    research_only: true;
  };
  expect(catalog.items).toHaveLength(1);
  expect(catalog.items[0]).toMatchObject({
    job_id: 'job-e2e0123456789abcdef01234',
    state: 'COMPLETED',
  });
  expect(catalog.items[0]?.snapshot_id).toMatch(/^[0-9a-f]{64}$/);
  expect(catalog.items[0]?.snapshot_sha256).toMatch(/^[0-9a-f]{64}$/);

  const resultResponse = await request.get(
    'http://127.0.0.1:18000/api/arena/jobs/job-e2e0123456789abcdef01234/frontier-discovery',
  );
  const resultBody = await resultResponse.text();
  expect(resultResponse.status(), resultBody).toBe(200);
  const result = JSON.parse(resultBody) as {
    artifact: { result_sha256: string; comparison: { code_version: string } };
    integrity_verified: boolean;
    research_only: boolean;
    orders_submitted: boolean;
    authenticated_requests: boolean;
  };
  expect(result).toMatchObject({
    integrity_verified: true,
    research_only: true,
    orders_submitted: false,
    authenticated_requests: false,
  });
  expect(result.artifact.result_sha256).toMatch(/^[0-9a-f]{64}$/);
  expect(result.artifact.comparison.code_version).toBe('frontier-seeded-arena-browser-fixture-v1');

  await page.goto('/');
  await page.getByRole('button', { name: 'Laboratory', exact: true }).click();
  await page.getByRole('tab', { name: 'Frontier research', exact: true }).click();
  await page.getByRole('button', { name: /job-e2e0123456789abcdef01234/ }).click();
  await expect(page.getByText('INTEGRITY VERIFIED')).toBeVisible();
  await expect(page.getByText('3 paired discovery scopes')).toBeVisible();
  await page.getByText('Reproducibility identities and execution limits').click();
  await expect(page.getByText('frontier-seeded-arena-browser-fixture-v1')).toBeVisible();
  await expect(
    page.getByText('No orders were submitted, and no authenticated requests were made.'),
  ).toBeVisible();
  expect(probeRequests).toBe(0);
  expect(arenaMutations).toBe(0);
});
