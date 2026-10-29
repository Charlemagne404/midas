import { expect, test } from '@playwright/test';

test.skip(
  process.env.MIDAS_FRONTIER_E2E_CAPTURED !== '1',
  'requires the explicit isolated captured-evidence Frontier store seeder',
);

test('Frontier renders captured public market, book, provenance, and relationship evidence', async ({
  page,
}) => {
  let sourceProbes = 0;
  let apiMutations = 0;
  page.on('request', (request) => {
    const url = new URL(request.url());
    if (url.pathname.includes('/api/frontier/probe/')) sourceProbes += 1;
    if (url.pathname.startsWith('/api/') && request.method() !== 'GET') apiMutations += 1;
  });

  await page.goto('/');
  await page.getByRole('button', { name: 'Frontier', exact: true }).click();
  await page.getByRole('button', { name: 'Markets', exact: true }).click();

  const marketTitle =
    'Will the Fed decrease interest rates by 50+ bps after the October 2026 meeting?';
  const marketRow = page.getByRole('row').filter({ hasText: marketTitle });
  await expect(marketRow).toBeVisible();
  await marketRow.getByRole('button', { name: 'Inspect', exact: true }).click();

  const details = page.getByRole('region', { name: 'Market and book details' });
  await expect(details.getByRole('heading', { name: marketTitle })).toBeVisible();
  await expect(details.getByText('Not verified', { exact: true })).toBeVisible();

  const firstInstrument = details.locator('.fr-instrument-list article').first();
  await expect(firstInstrument.getByText('ASKS', { exact: true })).toBeVisible();
  await expect(firstInstrument.getByText('BIDS', { exact: true })).toBeVisible();
  await expect(firstInstrument.getByText('0.995', { exact: true })).toBeVisible();
  await firstInstrument.getByText('Inspect immutable source response').click();
  await expect(firstInstrument).toContainText('https://clob.polymarket.com/book?token_id=');

  await page.getByRole('button', { name: 'Relationship graph', exact: true }).click();
  await page.getByLabel('Relationship graph center market').selectOption('polymarket:2589810');
  const relationship = page.locator('.fr-edge').first();
  await expect(relationship).toBeVisible();
  await expect(relationship).toContainText('same event');
  await expect(relationship).toContainText('hypothesis');

  expect(sourceProbes).toBe(0);
  expect(apiMutations).toBe(0);
});

test('Frontier deterministically replays captured books in the isolated browser store', async ({
  page,
}) => {
  let sourceProbes = 0;
  const apiMutations: string[] = [];
  page.on('request', (request) => {
    const url = new URL(request.url());
    if (url.pathname.includes('/api/frontier/probe/')) sourceProbes += 1;
    if (url.pathname.startsWith('/api/') && request.method() !== 'GET') {
      apiMutations.push(`${request.method()} ${url.pathname}`);
    }
  });

  await page.goto('/');
  await page.getByRole('button', { name: 'Frontier', exact: true }).click();
  await page.getByRole('button', { name: 'Economic workbench', exact: true }).click();

  const replayButton = page.getByRole('button', {
    name: 'Run deterministic replay',
    exact: true,
  });
  const runReplay = async () => {
    const replayResponse = page.waitForResponse((response) => {
      const url = new URL(response.url());
      return url.pathname === '/api/frontier/replay' && response.request().method() === 'POST';
    });
    await replayButton.click();
    const response = await replayResponse;
    expect(response.status()).toBe(200);
    return (await response.json()) as {
      run_id: string;
      manifest: {
        market_observation_ids: string[];
        book_observation_ids: string[];
        code_version: string;
      };
      result_sha256: string;
    };
  };

  const replay = await runReplay();
  expect(replay.manifest.market_observation_ids.length).toBeGreaterThan(0);
  expect(replay.manifest.book_observation_ids.length).toBeGreaterThan(0);
  expect(replay.manifest.code_version).toMatch(/^frontier-source-sha256:/);
  expect(replay.result_sha256).toMatch(/^[0-9a-f]{64}$/);
  await expect(page.getByText(/Replay saved · \d+ candidate evaluations/)).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Replay output' })).toBeVisible();

  await expect(replayButton).toBeEnabled();
  const repeatedReplay = await runReplay();
  expect(repeatedReplay.run_id).toBe(replay.run_id);
  expect(repeatedReplay.result_sha256).toBe(replay.result_sha256);

  expect(sourceProbes).toBe(0);
  expect(apiMutations).toEqual(['POST /api/frontier/replay', 'POST /api/frontier/replay']);
});

test('Frontier primary views fit a narrow viewport without page-level horizontal overflow', async ({
  page,
}) => {
  let sourceProbes = 0;
  let apiMutations = 0;
  page.on('request', (request) => {
    const url = new URL(request.url());
    if (url.pathname.includes('/api/frontier/probe/')) sourceProbes += 1;
    if (url.pathname.startsWith('/api/') && request.method() !== 'GET') apiMutations += 1;
  });

  await page.goto('/');
  await page.getByRole('button', { name: 'Frontier', exact: true }).click();

  for (const width of [320, 390]) {
    await page.setViewportSize({ width, height: 844 });
    for (const section of [
      'Overview',
      'Coverage & quality',
      'Exchanges',
      'Markets',
      'Relationship graph',
      'Candidates',
      'Economic workbench',
      'Replay & readiness',
    ]) {
      const tab = page.getByRole('button', { name: section, exact: true });
      await tab.click();
      await expect(tab).toHaveAttribute('aria-current', 'page');
      await expect(
        page.getByRole('heading', {
          level: 1,
          name: 'Market relationships, with evidence attached.',
        }),
      ).toBeVisible();
      const dimensions = await page.evaluate(() => ({
        viewport: document.documentElement.clientWidth,
        document: document.documentElement.scrollWidth,
      }));
      expect(
        dimensions.document,
        `${section} overflows the ${dimensions.viewport}px viewport`,
      ).toBeLessThanOrEqual(dimensions.viewport);
    }
  }

  expect(sourceProbes).toBe(0);
  expect(apiMutations).toBe(0);
});
