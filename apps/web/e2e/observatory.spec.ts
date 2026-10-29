import { test, expect } from '@playwright/test';

test('explore the Observatory views with saved evidence or clear empty states', async ({
  page,
}) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Observatory', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Inside the machine.' })).toBeVisible();
  await expect(page.getByText('Evidence first.')).toBeVisible();

  const modelChoices = page.locator('#obs-model option');
  await expect
    .poll(
      async () =>
        (await modelChoices.count()) > 0 ||
        (await page.getByText('No inspectable MLP model is saved').count()) > 0,
    )
    .toBe(true);
  if (await modelChoices.count()) {
    await expect(page.getByText('MODEL INSPECTOR')).toBeVisible();
    await expect(page.locator('.obs-network-canvas')).toBeVisible();
    await page.getByRole('button', { name: 'Play this signal' }).click();
    await expect(page.getByRole('button', { name: 'Pause signal' })).toBeVisible();
    await page.getByLabel('Saved validation example').selectOption('1');
    await expect(page.getByText('Validation example 2')).toBeVisible();
    await page.screenshot({
      path: test.info().outputPath('observatory-network.png'),
      fullPage: true,
    });
  } else {
    await expect(page.getByText('No inspectable MLP model is saved')).toBeVisible();
  }

  await page.getByRole('button', { name: /How it learns/ }).click();
  await expect(
    page.getByRole('heading', { name: 'Watch what changed during training.' }),
  ).toBeVisible();
  if (await page.locator('#obs-training-run option').count()) {
    await expect(page.locator('.obs-learning-chart')).toBeVisible();
    await page.getByRole('button', { name: 'Replay this run' }).click();
    await expect(page.getByRole('button', { name: 'Pause replay' })).toBeVisible();
    await page.screenshot({
      path: test.info().outputPath('observatory-learning.png'),
      fullPage: true,
    });
  } else {
    await expect(page.getByText('No saved learning curve is available')).toBeVisible();
  }

  await page.getByRole('button', { name: /Research universe/ }).click();
  await expect(
    page.getByRole('heading', { name: 'Follow the evidence through MIDAS.' }),
  ).toBeVisible();
  await expect(page.getByText(/connected artifacts/)).toBeVisible();
  const universeCanvas = page.locator('.obs-universe-map canvas');
  await expect(universeCanvas).toBeVisible();
  await universeCanvas.hover({ position: { x: 400, y: 250 } });
  await page.mouse.wheel(0, -220);
  await page.getByRole('button', { name: 'Reset universe view' }).click();
  await page.screenshot({
    path: test.info().outputPath('observatory-universe.png'),
    fullPage: true,
  });

  await page.getByRole('button', { name: 'Simulations' }).click();
  await expect(
    page.getByRole('heading', { name: 'Step through a saved simulation.' }),
  ).toBeVisible();
  await expect
    .poll(
      async () =>
        (await page.locator('#obs-simulation option').count()) > 0 ||
        (await page.getByText('No recorded simulation to replay').count()) > 0,
    )
    .toBe(true);
  if (await page.locator('#obs-simulation option').count()) {
    await expect(page.locator('.obs-sim-summary')).toBeVisible({ timeout: 15_000 });
    await expect(page.locator('.obs-sim-replay-card')).toBeVisible({ timeout: 15_000 });
    await page.getByText(/What the policy received/).click();
    await expect(page.getByText('Combined ask prices')).toBeVisible();
    await expect(page.getByText('Proposal passed the saved eligibility check')).toBeVisible();
    await page.getByText(/What the policy received/).click();
    await page.screenshot({
      path: test.info().outputPath('observatory-simulation.png'),
      fullPage: true,
    });
  }

  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('button', { name: /Neural network/ }).click();
  await expect(
    page.getByRole('heading', { name: 'A real neural network, one signal at a time.' }),
  ).toBeVisible();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  expect(overflow).toBe(false);
  await page.screenshot({ path: test.info().outputPath('observatory-mobile.png'), fullPage: true });
});
