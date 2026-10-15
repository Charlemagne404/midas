import { expect, test } from '@playwright/test';

test('shows the bounded discovery cohort and links its finalized evidence', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Veritas', exact: true }).click();

  await expect(
    page.getByRole('heading', { level: 1, name: /Evidence before conviction/ }),
  ).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Market discovery and coverage' })).toBeVisible();
  await expect(
    page.getByRole('heading', { name: 'Opportunity observatory and data quality' }),
  ).toBeVisible();
  await expect(
    page.getByText(/No quality-valid positive full-depth gross candidate has been recorded/),
  ).toBeVisible();

  const snapshotLink = page.getByRole('link', { name: /Inspect latest immutable snapshot/ });
  await expect(snapshotLink).toHaveAttribute(
    'href',
    /\/api\/veritas\/observatory\/snapshots\/scan-/,
  );
  const snapshotUrl = await snapshotLink.getAttribute('href');
  expect(snapshotUrl).toBeTruthy();
  const snapshotResponse = await page.request.get(snapshotUrl!);
  expect(snapshotResponse.ok()).toBeTruthy();
  const snapshot = await snapshotResponse.json();
  expect(snapshot.artifact).toBe('finalized_public_observation_snapshot');
  expect(snapshot.data.orders_submitted).toBe(false);

  const analysis = await page.request.get('/api/veritas/artifacts/continuous-analysis');
  expect(analysis.ok()).toBeTruthy();
  expect((await analysis.json()).data.analysis_version).toBe(
    'veritas-finalized-snapshot-analysis-v2',
  );
});
