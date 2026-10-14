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
  ).toBeVisible();
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
