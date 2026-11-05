import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { Laboratory } from './Laboratory';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
const config = {
  preset: 'Quick',
  runs: 32,
  seed: 7,
  families: ['calm'],
  strategies: ['arbitrage'],
  models: ['standard'],
  dataset_id: null,
  workers: 1,
  memory_mb: 512,
  max_wall_seconds: 300,
  max_disk_mb: 128,
  observation_latency_ms: 0,
  submission_latency_ms: null,
  fee_rate: null,
  liquidity_fraction: null,
  capital: '100',
  limits: { max_capital: '20' },
  costs: { operating_per_fill: '0', annual_financing_rate: '0' },
  adversarial: false,
};
function mount(fetch: ReturnType<typeof vi.fn>, onNavigate?: (page: string) => void) {
  vi.stubGlobal('fetch', fetch);
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <Laboratory onNavigate={onNavigate} />
    </QueryClientProvider>,
  );
}
function response(value: unknown, ok = true) {
  return Promise.resolve({ ok, json: () => Promise.resolve(value) });
}
function catalog() {
  return {
    default_config: config,
    families: ['calm', 'ledger_mutation'],
    models: ['optimistic', 'standard', 'conservative'],
    strategies: ['arbitrage', 'conservative', 'no_trade'],
    presets: { Quick: 32, Standard: 1000 },
    datasets: [],
  };
}

function discoveryArtifact(integrityVerified = true) {
  const scopes = ['polymarket_only', 'venue_local', 'cross_venue'];
  const arms = scopes.map((scope) => ({
    scope,
    venues: scope === 'cross_venue' ? ['polymarket', 'kalshi'] : ['polymarket'],
    market_count: 2,
    instrument_count: 2,
    observed_instrument_count: 1,
    book_count: 1,
    relationship_count: 1,
    candidates: [],
    family_counts: {},
  }));
  const pairs = [
    ['polymarket_only', 'venue_local'],
    ['venue_local', 'cross_venue'],
    ['polymarket_only', 'cross_venue'],
  ];
  return {
    artifact: {
      snapshot_id: 'snapshot-1',
      snapshot_sha256: 'a'.repeat(64),
      result_sha256: 'b'.repeat(64),
      comparison: {
        comparison_id: 'comparison-1',
        normalized_input_sha256: 'c'.repeat(64),
        result_sha256: 'd'.repeat(64),
        code_version: 'frontier-test-version',
        replay_version: 'frontier-replay-test-version',
        as_of_utc: '2026-10-28T06:00:00Z',
        arms,
        deltas: pairs.map(([baseline, compared]) => ({
          baseline,
          compared,
          matched_candidate_count: 0,
          changed_classification_count: 0,
          baseline_only_candidate_count: 0,
          compared_only_candidate_count: 0,
        })),
      },
    },
    integrity_verified: integrityVerified,
    research_only: true,
    orders_submitted: false,
    authenticated_requests: false,
  };
}

it('builder sends exact seeded comparison settings and surfaces backend validation', async () => {
  let posted: Record<string, unknown> | null = null;
  mount(
    vi.fn((url: string, options?: RequestInit) => {
      if (options?.method === 'POST') {
        posted = JSON.parse(String(options.body));
        return response({ detail: 'Resource budget invalid' }, false);
      }
      return response(url.endsWith('/catalog') ? catalog() : []);
    }),
  );
  fireEvent.click(screen.getByRole('tab', { name: 'Experiment builder' }));
  await screen.findByRole('heading', { name: 'Experiment configuration' });
  fireEvent.change(screen.getByLabelText('Random seed'), { target: { value: '42' } });
  fireEvent.change(screen.getByLabelText('Number of scenarios'), { target: { value: '4' } });
  fireEvent.click(screen.getByLabelText('Compare all execution models'));
  fireEvent.click(screen.getByRole('button', { name: 'Launch experiment' }));
  await waitFor(() =>
    expect(posted).toMatchObject({
      seed: 42,
      runs: 4,
      models: ['optimistic', 'standard', 'conservative'],
    }),
  );
  expect(await screen.findByRole('alert')).toHaveTextContent('Resource budget invalid');
});

it('empty laboratory shows bounded evidence and simulation-only labeling', async () => {
  mount(vi.fn((url: string) => response(url.endsWith('/catalog') ? catalog() : [])));
  expect(screen.getByText('SIMULATION ONLY')).toBeInTheDocument();
  expect(
    await screen.findByText('No campaigns yet. Configure an experiment to begin.'),
  ).toBeInTheDocument();
  expect(
    screen.getByText('No stored invariant discoveries. This is bounded evidence.'),
  ).toBeInTheDocument();
});

it('Laboratory reviews a selected, integrity-verified Frontier Arena artifact', async () => {
  const requested: string[] = [];
  const onNavigate = vi.fn();
  mount(
    vi.fn((url: string) => {
      requested.push(url);
      if (url.endsWith('/catalog')) return response(catalog());
      if (url.endsWith('/frontier-discovery-comparisons?limit=20')) {
        return response({
          items: [
            {
              job_id: 'job-newer',
              state: 'RUNNING',
              created_at: 1793167200,
              updated_at: 1793167200,
              elapsed_seconds: 1,
              progress: { done: 1, total: 2 },
              phase: 'discovering',
              error: null,
              snapshot_id: 'new-snapshot',
              snapshot_sha256: 'e'.repeat(64),
              result: null,
            },
            {
              job_id: 'job-older',
              state: 'COMPLETED',
              created_at: 1793163600,
              updated_at: 1793163600,
              elapsed_seconds: 0.4,
              progress: { done: 3, total: 3 },
              phase: 'complete',
              error: null,
              snapshot_id: 'saved-snapshot',
              snapshot_sha256: 'f'.repeat(64),
              result: { comparison_id: 'comparison-1' },
            },
          ],
          scanned: 2,
          scan_bound: 500,
          scan_may_be_incomplete: false,
          research_only: true,
        });
      }
      if (url.endsWith('/jobs/job-older/frontier-discovery')) {
        return response(discoveryArtifact());
      }
      return response([]);
    }),
    onNavigate,
  );
  fireEvent.click(screen.getByRole('tab', { name: 'Frontier research' }));
  await screen.findByText('job-newer');
  fireEvent.click(screen.getByRole('button', { name: /job-older/ }));
  expect(await screen.findByText('INTEGRITY VERIFIED')).toBeInTheDocument();
  expect(screen.getByText('3 paired discovery scopes')).toBeInTheDocument();
  fireEvent.click(screen.getByText('Reproducibility identities and execution limits'));
  expect(
    screen.getByText('frontier-test-version · frontier-replay-test-version'),
  ).toBeInTheDocument();
  expect(requested).toContain('/api/arena/jobs/job-older/frontier-discovery');
  expect(requested.some((url) => url.includes('/probe/'))).toBe(false);
  fireEvent.click(screen.getByRole('button', { name: /Open Frontier workspace/ }));
  expect(onNavigate).toHaveBeenCalledWith('Frontier');
});

it('withholds Frontier study details when artifact integrity is not confirmed', async () => {
  mount(
    vi.fn((url: string) => {
      if (url.endsWith('/catalog')) return response(catalog());
      if (url.endsWith('/frontier-discovery-comparisons?limit=20')) {
        return response({
          items: [
            {
              job_id: 'job-unverified',
              state: 'COMPLETED',
              created_at: 1793163600,
              updated_at: 1793163600,
              elapsed_seconds: 0.4,
              progress: { done: 3, total: 3 },
              phase: 'complete',
              error: null,
              snapshot_id: 'unverified-snapshot',
              snapshot_sha256: 'f'.repeat(64),
              result: { comparison_id: 'comparison-unverified' },
            },
          ],
          scanned: 1,
          scan_bound: 500,
          scan_may_be_incomplete: false,
          research_only: true,
        });
      }
      if (url.endsWith('/jobs/job-unverified/frontier-discovery')) {
        return response(discoveryArtifact(false));
      }
      return response([]);
    }),
  );
  fireEvent.click(screen.getByRole('tab', { name: 'Frontier research' }));
  expect(
    await screen.findByText(
      'The API did not confirm artifact integrity; result details are withheld.',
    ),
  ).toBeInTheDocument();
  expect(screen.queryByText('3 paired discovery scopes')).not.toBeInTheDocument();
});
