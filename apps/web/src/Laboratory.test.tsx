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
function mount(fetch: ReturnType<typeof vi.fn>) {
  vi.stubGlobal('fetch', fetch);
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <Laboratory />
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
