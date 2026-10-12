import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Arena } from './Arena';

vi.mock('./Chart', () => ({ Chart: () => <div>Chart</div> }));

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it('labels the distinct model targets in a paired tournament', async () => {
  const rank = {
    rank: 1,
    mean_pnl: 1,
    mean_pnl_episode_bootstrap_95: [0, 2],
    cvar_05_loss: 0,
    worst_loss: 0,
    no_trade_fraction: 0.5,
    score: 1,
    quantiles: [0, 0, 1, 1, 2],
    max_drawdown: 0,
  };
  const tournament = {
    tournament_id: 'league',
    base_episodes: 2,
    variants: 12,
    conclusion: 'Validation comparison; independent evaluation required.',
    ranking_objective: 'Downside objective',
    uncertainty_note: 'Grouped validation outcomes',
    configuration: {},
    paired: [],
    leaderboard: [
      { ...rank, policy: 'completion-gate' },
      { ...rank, policy: 'risk-gate' },
    ],
    policy_bindings: {
      'completion-gate': { model_id: 'completion-model', threshold: 0.9, size: 'full' },
      'risk-gate': { model_id: 'risk-model', threshold: 0.1, size: 'full' },
    },
    model_dataset_bindings: {
      'completion-model': { dataset_id: 'derived', label_target: 'completion' },
      'risk-model': { dataset_id: 'parent', label_target: 'unmatched' },
    },
  };
  const overview = {
    datasets: [],
    models: [],
    jobs: [],
    findings: [],
    tournaments: [tournament],
    dependencies: {},
    health: { memory_mb: {}, worker_cpu_cores: 1, worker_memory_mb: 4096 },
  };
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      const result =
        url === '/api/arena'
          ? overview
          : url === '/api/arena/tournaments/league'
            ? tournament
            : { total: 0, rows: [] };
      return new Response(JSON.stringify(result), { status: 200 });
    }),
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <Arena />
    </QueryClientProvider>,
  );
  fireEvent.click(await screen.findByRole('tab', { name: 'Tournaments' }));
  expect(await screen.findByText('Predicts proposal completion')).toBeInTheDocument();
  expect(screen.getByText('Predicts unmatched exposure')).toBeInTheDocument();
  expect(screen.getByText(/Threshold 0.9/)).toBeInTheDocument();
  expect(screen.getByText(/Threshold 0.1/)).toBeInTheDocument();
  client.clear();
});

it('shows severity errors in shares and excludes probability diagnostics', async () => {
  const metrics = { mae: 1, rmse: 2, positive_mae: 3, positive_rmse: 4, base_episodes: 10 };
  const model = {
    model_id: 'model-severity',
    family: 'ridge',
    task: 'residual_severity_regression',
    label_target: 'residual_unmatched_shares',
    state: 'TRAINED',
    dataset_id: 'parent',
    artifact_sha256: 'weights',
    training_duration_seconds: 1,
    configuration: {},
    validation: metrics,
    test: null,
    curves: [],
    limitations: [],
    checkpoints: [],
    loss_definition: 'Train-normalized squared shares error',
    baselines_validation: { zero: metrics },
  };
  const overview = {
    datasets: [],
    models: [model],
    jobs: [],
    findings: [],
    tournaments: [],
    dependencies: {},
    health: { memory_mb: {}, worker_cpu_cores: 1, worker_memory_mb: 4096 },
  };
  vi.stubGlobal(
    'fetch',
    vi.fn(
      async (url: string) =>
        new Response(JSON.stringify(url === '/api/arena' ? overview : model), { status: 200 }),
    ),
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <Arena />
    </QueryClientProvider>,
  );
  fireEvent.click(await screen.findByRole('tab', { name: 'Model registry' }));
  expect(screen.getAllByText('RMSE (shares)')).toHaveLength(2);
  fireEvent.click(screen.getByRole('button', { name: 'Inspect model' }));
  expect(await screen.findByText(/Expected residual unmatched shares/)).toBeInTheDocument();
  expect(
    screen.getByRole('heading', { name: 'Validation regression controls' }),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole('button', { name: 'Inspect validation errors' }),
  ).not.toBeInTheDocument();
  expect(screen.getByText('positive rmse')).toBeInTheDocument();
  client.clear();
});
