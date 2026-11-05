import { test, expect } from '@playwright/test';

test('configure, launch, compare and replay a persisted laboratory experiment', async ({
  page,
}) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Laboratory', exact: true }).click();
  await page.getByRole('tab', { name: 'Experiment builder', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Experiment configuration' })).toBeVisible();
  await page.getByLabel('Number of scenarios').fill('2');
  await page.getByLabel('Scenario family').selectOption('calm');
  await page.getByLabel('Compare all execution models').check();
  await page.getByRole('button', { name: 'Launch experiment', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'Campaign execution', exact: true }),
  ).toBeVisible({ timeout: 30000 });
  await expect(page.getByText('6 / 6 runs committed', { exact: true })).toBeVisible({
    timeout: 30000,
  });
  await page.getByRole('tab', { name: 'Strategy comparison', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'Paired strategy and execution results' }),
  ).toBeVisible();
  await expect(page.getByRole('cell', { name: 'arbitrage/optimistic', exact: true })).toBeVisible();
  await page.getByRole('tab', { name: 'Campaign monitor', exact: true }).click();
  await page.getByRole('button', { name: 'Inspect run', exact: true }).first().click();
  await expect(page.getByRole('heading', { name: 'Persisted event replay' })).toBeVisible();
  await page.getByRole('button', { name: 'Next event', exact: true }).click();
  await expect(page.getByText('Event 2 /', { exact: false })).toBeVisible();
  await page.getByLabel('Replay timeline').fill('5');
  await expect(page.getByText('Event 6 /', { exact: false })).toBeVisible();
  await page.getByRole('button', { name: 'Previous event', exact: true }).click();
  await expect(page.getByText('Event 5 /', { exact: false })).toBeVisible();
  await page.getByRole('button', { name: 'Reproduce run', exact: true }).click();
  await expect(page.getByRole('status')).toHaveText('Exact result hash reproduced');
  const exported = await page.request.get(
    (await page.getByRole('link', { name: 'Export full event history' }).getAttribute('href')) ??
      '',
  );
  const artifact = await exported.json();
  expect(artifact.result.journal.length).toBeGreaterThan(5);
  expect(artifact.result.economically_verified).toBe(false);
  await page.screenshot({ path: test.info().outputPath('laboratory-replay.png'), fullPage: true });
});

test('controlled adversarial violation preserves minimized incident and replay', async ({
  page,
}) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Laboratory', exact: true }).click();
  await page.getByRole('tab', { name: 'Experiment builder', exact: true }).click();
  await page.getByLabel('Scenario family').selectOption('ledger_mutation');
  await page.getByLabel('Number of scenarios').fill('1');
  await page.getByRole('button', { name: 'Launch experiment', exact: true }).click();
  await expect(page.getByText('1 / 1 runs committed', { exact: true })).toBeVisible({
    timeout: 30000,
  });
  await page.getByRole('tab', { name: 'Adversarial testing', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'Invariant discoveries and preserved reproductions' }),
  ).toBeVisible();
  await expect(page.getByText('3 → 2 events', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Open failure replay', exact: true }).first().click();
  await expect(page.getByRole('heading', { name: 'Persisted event replay' })).toBeVisible();
  await page.getByLabel('Replay timeline').fill('9');
  await expect(page.getByText('MUTATE', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Reproduce run', exact: true }).click();
  await expect(page.getByRole('status')).toHaveText('Exact result hash reproduced');
});

test('Laboratory inspects a saved Frontier discovery artifact without launching work', async ({
  page,
}) => {
  const requests: { url: string; method: string }[] = [];
  page.on('request', (request) => requests.push({ url: request.url(), method: request.method() }));
  await page.route(
    (url) =>
      url.pathname === '/api/arena/frontier-discovery-comparisons' &&
      url.searchParams.get('limit') === '20',
    (route) =>
      route.fulfill({
        json: {
          items: [
            {
              job_id: 'job-frontier-running',
              state: 'RUNNING',
              created_at: 1793167200,
              updated_at: 1793167200,
              elapsed_seconds: 1,
              progress: { done: 1, total: 2 },
              phase: 'discovering',
              error: null,
              snapshot_id: 'running-snapshot',
              snapshot_sha256: 'a'.repeat(64),
              result: null,
            },
            {
              job_id: 'job-frontier-saved',
              state: 'COMPLETED',
              created_at: 1793163600,
              updated_at: 1793163600,
              elapsed_seconds: 0.4,
              progress: { done: 3, total: 3 },
              phase: 'complete',
              error: null,
              snapshot_id: 'saved-snapshot',
              snapshot_sha256: 'b'.repeat(64),
              result: { comparison_id: 'saved-comparison' },
            },
          ],
          scanned: 2,
          scan_bound: 500,
          scan_may_be_incomplete: false,
          research_only: true,
        },
      }),
  );
  await page.route('**/api/arena/jobs/job-frontier-saved/frontier-discovery', (route) =>
    route.fulfill({
      json: {
        artifact: {
          snapshot_id: 'saved-snapshot',
          snapshot_sha256: 'b'.repeat(64),
          result_sha256: 'c'.repeat(64),
          comparison: {
            comparison_id: 'saved-comparison',
            normalized_input_sha256: 'd'.repeat(64),
            result_sha256: 'e'.repeat(64),
            code_version: 'frontier-e2e-fixture',
            replay_version: 'frontier-replay-e2e-fixture',
            as_of_utc: '2026-10-28T06:00:00Z',
            arms: ['polymarket_only', 'venue_local', 'cross_venue'].map((scope) => ({
              scope,
              venues: scope === 'cross_venue' ? ['polymarket', 'kalshi'] : ['polymarket'],
              market_count: 2,
              instrument_count: 2,
              observed_instrument_count: 1,
              book_count: 1,
              relationship_count: 1,
              candidates: [],
              family_counts: {},
            })),
            deltas: [
              ['polymarket_only', 'venue_local'],
              ['venue_local', 'cross_venue'],
              ['polymarket_only', 'cross_venue'],
            ].map(([baseline, compared]) => ({
              baseline,
              compared,
              matched_candidate_count: 0,
              changed_classification_count: 0,
              baseline_only_candidate_count: 0,
              compared_only_candidate_count: 0,
            })),
          },
        },
        integrity_verified: true,
        research_only: true,
        orders_submitted: false,
        authenticated_requests: false,
      },
    }),
  );

  await page.goto('/');
  await page.getByRole('button', { name: 'Laboratory', exact: true }).click();
  await page.getByRole('tab', { name: 'Frontier research', exact: true }).click();
  await page.getByRole('button', { name: /job-frontier-saved/ }).click();
  await expect(page.getByText('INTEGRITY VERIFIED')).toBeVisible();
  await expect(page.getByText('3 paired discovery scopes')).toBeVisible();
  await page.getByText('Reproducibility identities and execution limits').click();
  await expect(page.getByText('frontier-e2e-fixture · frontier-replay-e2e-fixture')).toBeVisible();
  await expect(
    page.getByText('No orders were submitted, and no authenticated requests were made.'),
  ).toBeVisible();
  expect(requests.some(({ url }) => url.includes('/probe/'))).toBe(false);
  expect(requests.some(({ url, method }) => url.includes('/api/arena/') && method !== 'GET')).toBe(
    false,
  );
});
