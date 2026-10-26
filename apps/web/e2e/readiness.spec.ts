import { expect, test } from '@playwright/test';

test('Research Readiness labels demo mode and keeps missing evidence visible', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Research Readiness', exact: true }).click();

  await expect(
    page.getByRole('heading', { name: 'Research Readiness', exact: true }),
  ).toBeVisible();
  await expect(page.getByText('READINESS · EVIDENCE CLASSIFICATION')).toBeVisible();
  await expect(page.getByText('DEMO MODE', { exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Readiness gates' })).toBeVisible();
  await expect(page.getByText(/Missing evidence never counts as a pass/)).toBeVisible();
  await expect(page.locator('.rr-footer-note')).toContainText('No live order execution');
  await page.screenshot({ path: test.info().outputPath('research-readiness.png'), fullPage: true });

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole('heading', { name: 'Readiness gates' })).toBeVisible();
  await expect(page.locator('.rr-gates .rr-gate').first()).toBeVisible();
});
