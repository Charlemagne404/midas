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
