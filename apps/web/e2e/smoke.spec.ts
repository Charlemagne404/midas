import { test, expect } from '@playwright/test';
test('discover, inspect, simulate, replay and expose execution failure', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Mission Control', exact: true })).toBeVisible();
  await expect(page.getByText('DEMO · SYNTHETIC')).toBeVisible();
  await expect(page.getByText('API DISCONNECTED')).toHaveCount(0);
  await expect(page.locator('.chart svg')).toBeVisible();
  await page.screenshot({ path: test.info().outputPath('mission-control.png'), fullPage: true });
  await page.getByRole('button', { name: 'Scanner', exact: false }).first().click();
  await page.getByRole('button', { name: /Synthetic binary • profitable/ }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await expect(page.getByText('Minimum net profit')).toBeVisible();
  await page.getByRole('button', { name: 'Close observation detail' }).click();
  await page.getByRole('button', { name: 'Simulation Lab', exact: true }).click();
  await page.getByRole('button', { name: 'Run scenario', exact: true }).click();
  await expect(page.getByText('INVARIANTS PASSED')).toBeVisible();
  await expect(page.locator('.portfolio-grid').getByText('0.5000', { exact: true })).toBeVisible();
  await page.getByLabel('Replay event timeline').fill('4');
  await expect(page.locator('.timeline-row.current')).toBeVisible();
  await page
    .locator('.scenario-panel')
    .getByRole('button', { name: 'first leg only', exact: true })
    .click();
  await page.getByRole('button', { name: 'Run scenario', exact: true }).click();
  await expect(page.locator('.portfolio-grid').getByText('-4.2000', { exact: true })).toBeVisible();
  await page
    .locator('.scenario-panel')
    .getByRole('button', { name: 'unprofitable', exact: true })
    .click();
  await page.getByRole('button', { name: 'Run scenario', exact: true }).click();
  await expect(page.locator('.audit-summary').getByText('negative edge')).toBeVisible();
  await page.screenshot({ path: test.info().outputPath('dashboard-smoke.png'), fullPage: true });
  for (const name of ['Analytics', 'Arena', 'Incidents', 'Telemetry', 'Settings']) {
    await page.getByRole('button', { name, exact: true }).click();
    await expect(page.getByRole('heading', { name, exact: true })).toBeVisible();
  }
  await page.getByRole('button', { name: 'Activate stop', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Release stop', exact: true })).toBeVisible();
  const blocked = await page.request.post('/api/scenarios/profitable/run', { data: { seed: 7 } });
  expect(blocked.status()).toBe(409);
  await page.getByRole('button', { name: 'Release stop', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Activate stop', exact: true })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('button', { name: 'Mission Control', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Mission Control', exact: true })).toBeVisible();
  await page.screenshot({
    path: test.info().outputPath('mission-control-mobile.png'),
    fullPage: true,
  });
});
