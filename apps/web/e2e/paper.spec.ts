import { test, expect } from '@playwright/test';

test('persistent paper account, decision audit and execution comparison', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Paper Trading', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Paper Trading', exact: true })).toBeVisible();
  await expect(page.getByText('SIMULATION ONLY')).toBeVisible();
  await expect(page.getByText('VIRTUAL · ESTIMATED FILLS')).toBeVisible();
  await expect(
    page.getByText(/simulated fill does not prove that a real order could execute/),
  ).toBeVisible();
  await page.getByText('Advanced paper records', { exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Decision records' })).toBeVisible();
  await page.getByRole('button', { name: 'Pause new virtual decisions' }).click();
  await expect(page.getByRole('button', { name: 'Resume virtual decisions' })).toBeVisible();
  await page.reload();
  await page.getByRole('button', { name: 'Paper Trading', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Resume virtual decisions' })).toBeVisible();
  await page.getByRole('button', { name: 'Resume virtual decisions' }).click();
  await page.getByRole('button', { name: 'Simulation Lab', exact: true }).click();
  await page.getByRole('button', { name: 'Compare 3 assumptions' }).click();
  await expect(page.getByRole('cell', { name: 'Best case', exact: true })).toBeVisible();
  await expect(page.getByRole('cell', { name: 'More cautious', exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Download result record' })).toBeVisible();
  const paper = await (await page.request.get('/api/paper')).json();
  expect(paper.mode).toBe('synthetic');
  expect(paper.live_orders).toBe(0);
});
