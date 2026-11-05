import { expect, test } from '@playwright/test';

const modelId = 'e2e-fixture-unmatched-model';
const metrics = {
  brier: 0.24,
  log_loss: 0.67,
  precision: 0.25,
  recall: 0.5,
  pr_auc: 0.28,
  base_episodes: 4,
  reliability: [{ predicted: 0.25, observed: 0.25, count: 4 }],
};
const model = {
  model_id: modelId,
  label_target: 'unmatched',
  family: 'mlp',
  state: 'TRAINED',
  dataset_id: 'e2e-fixture-dataset',
  artifact_sha256: 'a'.repeat(64),
  training_duration_seconds: 0.1,
  configuration: { fixture_only: true },
  validation: metrics,
  test: null,
  curves: [{ epoch: 1, training_loss: 0.72, validation_loss: 0.74 }],
  limitations: ['Synthetic browser fixture only; this is not a research finding.'],
  checkpoints: ['fixture-checkpoint.json'],
  diagnostics: {
    label_target: 'unmatched',
    base_episodes: 4,
    false_completion_count: 1,
    missed_completion_count: 0,
    false_positive_count: 1,
    false_negative_count: 0,
    feature_sensitivity: [
      { feature: 'ask_depth', mean_brier_increase: 0.01, episode_bootstrap_95: [0.001, 0.02] },
    ],
    representative_errors: [
      {
        base_episode_id: 'fixture-episode-001',
        execution_model: 'hypothetical',
        error: 'synthetic_fixture',
        completion_probability: 0.2,
        predicted_probability: 0.7,
      },
    ],
    limitations: ['No market observations, submitted orders, or fills are represented.'],
  },
};
const overview = {
  datasets: [],
  models: [model],
  tournaments: [],
  jobs: [],
  dependencies: {},
  health: { memory_mb: { MemAvailable: 4096 }, worker_cpu_cores: 1, worker_memory_mb: 4096 },
  findings: [],
};

test('renders persisted Arena evidence from an isolated fixture without launching workers', async ({
  page,
}) => {
  let submittedJobs = 0;
  page.on('request', (request) => {
    if (request.method() === 'POST' && /\/api\/arena\/jobs(?:\/|$)/.test(request.url())) {
      submittedJobs += 1;
    }
  });
  await page.route('**/api/arena', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(overview) }),
  );
  await page.route(`**/api/arena/models/${modelId}`, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(model) }),
  );

  await page.goto('/');
  await page.getByRole('button', { name: 'Arena', exact: true }).click();
  await expect(
    page.getByText('Synthetic scenarios · Hypothetical fills · Economics unverified · Paper only'),
  ).toBeVisible();
  await page.getByRole('tab', { name: 'Model registry' }).click();
  await page.getByRole('button', { name: 'Inspect model', exact: true }).click();

  await expect(page.getByRole('heading', { name: `MLP / ${modelId}` })).toBeVisible();
  await expect(page.getByRole('img', { name: 'Persisted training metrics' })).toBeVisible();
  await expect(
    page.getByRole('heading', { name: 'Validation decision diagnostics' }),
  ).toBeVisible();
  await expect(page.getByText('Final test labels excluded.', { exact: false })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Saved validation diagnostics' })).toHaveAttribute(
    'href',
    `/api/arena/models/${modelId}/artifacts/diagnostics.json`,
  );
  await expect(
    page.getByText('Independent test not yet evaluated.', { exact: false }),
  ).toBeVisible();
  await page.getByText('Known model limitations').click();
  await expect(
    page.getByText('Synthetic browser fixture only; this is not a research finding.', {
      exact: true,
    }),
  ).toBeVisible();
  expect(submittedJobs).toBe(0);
});
