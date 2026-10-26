import { expect, test } from '@playwright/test';

test('Frontier workspace uses isolated research state and remains responsive', async ({ page }) => {
  let probeRequests = 0;
  page.on('request', (request) => {
    if (request.url().includes('/api/frontier/probe/')) probeRequests += 1;
  });
  await page.goto('/');
  await page.getByRole('button', { name: 'Frontier', exact: true }).click();

  await expect(page.getByText('FRONTIER · READ-ONLY RESEARCH')).toBeVisible();
  await expect(
    page.getByRole('heading', { name: 'Market relationships, with evidence attached.' }),
  ).toBeVisible();
  await expect(page.getByText('No replay runs yet')).toBeVisible();
  await page.screenshot({ path: test.info().outputPath('frontier-overview.png'), fullPage: true });
  await expect(page.getByText('SYNTHETIC DATA')).toHaveCount(0);
  expect(probeRequests).toBe(0);

  await page.getByRole('button', { name: 'Markets', exact: true }).click();
  await expect(page.getByText('No market observations recorded')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(1440);

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByText('No market observations recorded')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});
