import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Arena } from './Arena';

vi.mock('./Chart', () => ({ Chart: () => <div>Chart</div> }));

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it('cancels an adaptive follow-up and links its active child job', async () => {
  const plan = {
    director_id: 'followup',
    director_version: 'adaptive-latency-1',
    state: 'RUNNING',
    research_question: 'Does delay reproduce the loss?',
    planning_rule: 'Frozen policy on fresh seeds',
    current_stage: 'cycle 1: baseline',
    steps: [
      {
        name: 'cycle 1: baseline',
        state: 'RUNNING',
        artifact: { kind: 'jobs', identity: 'child' },
      },
    ],
  };
  const overview = {
    datasets: [],
    models: [],
    jobs: [],
    findings: [],
    tournaments: [],
    directors: [plan],
    dependencies: {},
    health: { memory_mb: {}, worker_cpu_cores: 1, worker_memory_mb: 4096 },
  };
  const fetch = vi.fn(async (url: string, init?: RequestInit) => {
    if (url === '/api/arena/directors/followup/cancel') {
      expect(init?.method).toBe('POST');
      plan.state = 'CANCELLED';
      return new Response(JSON.stringify(plan), { status: 200 });
    }
    return new Response(JSON.stringify(overview), { status: 200 });
  });
  vi.stubGlobal('fetch', fetch);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <Arena />
    </QueryClientProvider>,
  );
  fireEvent.click(await screen.findByRole('tab', { name: 'Research director' }));
  const button = await screen.findByRole('button', { name: 'Cancel follow-up' });
  expect(screen.getByRole('link', { name: /Evidence/ })).toHaveAttribute(
    'href',
    '/api/arena/jobs/child',
  );
  fireEvent.click(button);
  expect(
    await screen.findByText('Follow-up cancelled. Completed evidence is retained.'),
  ).toBeInTheDocument();
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

it('submits declared economic perturbations before a tournament rerun', async () => {
  const overview = {
    datasets: [
      {
        dataset_id: 'parent',
        rows: 3,
        eligible_base_episodes: 1,
        generated_base_episodes: 30,
        partition_rows: {},
        label_frequency: {},
        limitations: [],
      },
    ],
    models: [],
    jobs: [],
    findings: [],
    tournaments: [],
    dependencies: {},
    health: { memory_mb: {}, worker_cpu_cores: 1, worker_memory_mb: 4096 },
  };
  const submitted: unknown[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (_url: string, init?: RequestInit) => {
      if (init?.method === 'POST') {
        submitted.push(JSON.parse(String(init.body)));
        return new Response(JSON.stringify({ job_id: 'job-fixture', state: 'QUEUED' }), {
          status: 200,
        });
      }
      return new Response(JSON.stringify(overview), { status: 200 });
    }),
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <Arena />
    </QueryClientProvider>,
  );
  fireEvent.click(await screen.findByRole('tab', { name: 'Tournaments' }));
  fireEvent.click(screen.getByRole('checkbox', { name: 'Rerun with hypothetical economics' }));
  fireEvent.change(screen.getByLabelText('Depth multiplier'), { target: { value: '0.5' } });
  fireEvent.change(screen.getByLabelText('Synthetic fee coefficient'), {
    target: { value: '0.01' },
  });
  fireEvent.change(screen.getByLabelText('Additional submission latency (ms)'), {
    target: { value: '200' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Run held-out tournament' }));
  await screen.findByText('Research job admitted. Progress appears below.');
  expect(submitted[0]).toMatchObject({
    configuration: {
      tournament: {
        economic_regime: {
          depth_multiplier: '0.5',
          taker_fee_rate: '0.01',
          additional_submission_latency_ms: 200,
        },
      },
    },
  });
  client.clear();
});

it('renders a verified study with a shared group denominator and paired changes', async () => {
  const rank = {
    policy: 'no_trade',
    rank: 1,
    mean_pnl: 0,
    score: 0,
    cvar_05_loss: 0,
    worst_loss: 0,
    no_trade_fraction: 1,
    mean_pnl_episode_bootstrap_95: [0, 0],
    quantiles: [0, 0, 0, 0, 0],
    max_drawdown: 0,
    unsupported_decisions: 0,
  };
  const tournament = {
    tournament_id: 'baseline',
    base_episodes: 2,
    variants: 6,
    leaderboard: [rank],
    configuration: {},
    paired: [],
    conclusion: 'Fixture',
    ranking_objective: 'Downside objective',
    uncertainty_note: 'Shared groups',
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
  const study = {
    study_id: 'study',
    source_groups: 2,
    correlated_variants: 12,
    conditions: [
      { name: 'baseline', tournament_id: 'baseline', leaderboard: [rank] },
      { name: 'half_depth', tournament_id: 'depth', leaderboard: [rank] },
    ],
    paired_comparisons: {
      half_depth: {
        policies: [{ policy: 'no_trade', mean_pnl_difference: 0, episode_bootstrap_95: [0, 0] }],
      },
    },
    limitations: ['Conditions share source identities'],
    interpretation: 'Hypothetical economics only',
  };
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      const value =
        url === '/api/arena'
          ? overview
          : url.endsWith('/economic-regimes')
            ? study
            : url.endsWith('/economics')
              ? null
              : url.includes('/rows?')
                ? { rows: [], total: 0 }
                : tournament;
      return new Response(JSON.stringify(value), { status: 200 });
    }),
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <Arena />
    </QueryClientProvider>,
  );
  fireEvent.click(await screen.findByRole('tab', { name: 'Tournaments' }));
  expect(
    await screen.findByRole('heading', { name: 'Verified economic regime reruns' }),
  ).toBeInTheDocument();
  expect(screen.getByText(/2 shared source groups \/ 12 correlated variants/)).toBeInTheDocument();
  expect(screen.getByText('Conditions share source identities')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'half depth' })).toBeInTheDocument();
  client.clear();
});
