import { test, expect } from '@playwright/test';

test('persistent paper account, decision audit and execution comparison', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Paper Trading', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Paper Trading', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Every paper strategy decision' })).toBeVisible();
  await expect(page.getByText('HYPOTHETICAL · UNVERIFIED FILLS')).toBeVisible();
  await page.getByRole('button', { name: 'Pause paper decisions' }).click();
  await expect(page.getByRole('button', { name: 'Resume paper decisions' })).toBeVisible();
  await page.reload();
  await page.getByRole('button', { name: 'Paper Trading', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Resume paper decisions' })).toBeVisible();
  await page.getByRole('button', { name: 'Resume paper decisions' }).click();
  await page.getByRole('button', { name: 'Simulation Lab', exact: true }).click();
  await page.getByRole('button', { name: 'Compare three models' }).click();
  await expect(page.getByRole('cell', { name: 'optimistic', exact: true })).toBeVisible();
  await expect(page.getByRole('cell', { name: 'conservative', exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Download reproducibility artifact' })).toBeVisible();
  const paper = await (await page.request.get('/api/paper')).json();
  expect(paper.mode).toBe('synthetic');
  expect(paper.live_orders).toBe(0);
});
