import { test, expect } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

test('build, train, inspect and evaluate genuine Arena artifacts', async ({ page }) => {
  test.setTimeout(300000);
  await page.goto('/');
  await page.getByRole('button', { name: 'Arena', exact: true }).click();
  await expect(
    page.getByText('Synthetic scenarios · Hypothetical fills · Economics unverified · Paper only'),
  ).toBeVisible();
  await page.getByRole('tab', { name: 'Training console' }).click();
  await page.getByLabel('Prediction target', { exact: true }).selectOption('unmatched');
  await page.getByLabel('Base episodes', { exact: true }).fill('30');
  await page.getByRole('button', { name: 'Generate dataset' }).click();
  await expect(page.getByRole('combobox', { name: 'Dataset', exact: true })).not.toHaveValue('', {
    timeout: 30000,
  });
  await page.getByLabel('Epoch budget').fill('5');
  await page.getByRole('button', { name: 'Validate configuration' }).click();
  await expect(page.getByRole('status')).toHaveText('Configuration validated. Ready to launch.');
  await page.getByRole('button', { name: 'Start training' }).click();
  await expect(page.getByRole('button', { name: 'Inspect model', exact: true })).toBeVisible({
    timeout: 30000,
  });
  await page.getByRole('button', { name: 'Inspect model', exact: true }).click();
  await expect(page.getByText('Execution unmatched classifier.', { exact: false })).toBeVisible();
  await expect(
    page.getByText('Independent test not yet evaluated.', { exact: false }),
  ).toBeVisible();
  await expect(page.getByRole('img', { name: 'Persisted training metrics' })).toBeVisible();
  await page.getByRole('button', { name: 'Inspect validation errors' }).click();
  await expect(page.getByRole('heading', { name: 'Validation decision diagnostics' })).toBeVisible({
    timeout: 30000,
  });
  await expect(page.getByText('Final test labels excluded.', { exact: false })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Saved validation diagnostics' })).toBeVisible();
  await page.getByRole('button', { name: 'Evaluate frozen test' }).click();
  await expect
    .poll(
      async () => {
        const overview = await (await page.request.get('/api/arena')).json();
        return overview.models[0].test !== null;
      },
      { timeout: 30000 },
    )
    .toBe(true);
  const overview = await (await page.request.get('/api/arena')).json();
  const response = await page.request.post('/api/arena/jobs', {
    data: {
      configuration: {
        kind: 'tournament',
        tournament: {
          dataset_id: overview.datasets[0].dataset_id,
          model_ids: [overview.models[0].model_id],
          max_episodes: 2,
        },
      },
    },
  });
  expect(response.status()).toBe(201);
  await expect
    .poll(async () => (await (await page.request.get('/api/arena')).json()).tournaments.length, {
      timeout: 30000,
    })
    .toBe(1);
  const completed = await (await page.request.get('/api/arena')).json();
  const localPython = fileURLToPath(new URL('../../../.venv/bin/python', import.meta.url));
  const python =
    process.env.MIDAS_PYTHON ??
    (existsSync(localPython) ? localPython : '/home/charlie/midas/.venv/bin/python');
  execFileSync(
    python,
    [
      fileURLToPath(new URL('../../../scripts/arena_economics.py', import.meta.url)),
      '--root',
      completed.root,
      '--tournament',
      completed.tournaments[0].tournament_id,
    ],
    { timeout: 30000 },
  );
  await page.getByRole('tab', { name: 'Tournaments', exact: true }).click();
  await expect(
    page.getByRole('img', { name: 'Fixed-path cost sensitivity', exact: true }),
  ).toBeVisible();
  await page
    .getByLabel('Economic assumption', { exact: true })
    .selectOption('annual_financing_rate');
  await expect(page.getByText('fraction per 365-day year', { exact: false })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Replay episode' }).first()).toBeVisible({
    timeout: 15000,
  });
  await page.getByRole('button', { name: 'Replay episode' }).first().click();
  await expect(page.getByRole('heading', { name: 'Saved event replay' })).toBeVisible();
  await page.getByRole('button', { name: 'Next event', exact: true }).click();
  await expect(page.getByText('Event 2 /', { exact: false })).toBeVisible();
  await page.screenshot({ path: test.info().outputPath('arena-replay.png'), fullPage: true });
  await page.getByRole('tab', { name: 'Research director', exact: true }).click();
  await expect(page.getByLabel('Risk predictor', { exact: true })).not.toHaveValue('');
  await page.getByRole('button', { name: 'Run validation policy search', exact: true }).click();
  await expect
    .poll(async () => (await (await page.request.get('/api/arena')).json()).searches[0]?.state, {
      timeout: 180000,
    })
    .toBe('COMPLETED');
  await expect(page.getByText('Selected no-trade.', { exact: true })).toBeVisible({
    timeout: 15000,
  });
});
