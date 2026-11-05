import { expect, test } from '@playwright/test';

test('loads the chart payload only after a chart approaches the viewport', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 200 });
  const chartRequests: string[] = [];
  page.on('request', (request) => {
    if (/\/(?:src\/Chart\.tsx|assets\/Chart-[^/]+\.js)(?:\?|$)/.test(request.url())) {
      chartRequests.push(request.url());
    }
  });

  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Mission Control', exact: true })).toBeVisible();
  const chart = page.locator('.chart-deferred').first();
  await expect(chart).toBeVisible();
  expect(await chart.evaluate((node) => node.getBoundingClientRect().top)).toBeGreaterThan(320);
  expect(chartRequests).toHaveLength(0);

  await chart.scrollIntoViewIfNeeded();
  await expect(page.locator('.chart svg').first()).toBeVisible();
  expect(chartRequests).toHaveLength(1);
});
