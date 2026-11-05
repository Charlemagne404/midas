import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Reality } from './Reality';
import { historyBarrier, historySeries } from './reality-history';
vi.mock('./Chart', () => ({ Chart: () => <div>Chart</div> }));
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <Reality />
    </QueryClientProvider>,
  );
}
it('preserves unknown values and breaks sampled lines at missing intervals', () => {
  const rows = [
    { ns: 1e12, legs: { yes: { best_ask: '0.4' } } },
    { ns: 1e12 + 5e9, quality_reason: 'gap', legs: { yes: { best_ask: '0.5' } } },
    { ns: 1e12 + 30e9, legs: { yes: { best_ask: null } } },
  ];
  expect(historySeries(rows, 'yes', 'best_ask')).toEqual([
    [1e6, 0.4],
    [1005000, null],
    [1017500, null],
    [1030000, null],
  ]);
});
it('reports unavailable genuine evidence without inventing observations', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
  mount();
  expect(await screen.findByRole('alert', {}, { timeout: 3000 })).toHaveTextContent('offline');
  expect(screen.queryByText('The observation panel')).not.toBeInTheDocument();
  const executionBoundary = screen.getByText('NO ORDER EXECUTION').parentElement;
  expect(executionBoundary).toHaveTextContent(
    /A displayed price does not prove an order could have filled or made money\./,
  );
});
it('shows empty prospective candidates without treating them as profit', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation((url: string) =>
      Promise.resolve({
        ok: true,
        json: async () =>
          url.includes('/overview')
            ? {
                health: 'recording',
                collector: { cohort: [], books: {} },
                forward: {},
                capacity: {},
              }
            : { rows: [], has_more: false },
      }),
    ),
  );
  mount();
  await screen.findByText('The observation panel');
  fireEvent.click(screen.getByRole('button', { name: /Opportunities/ }));
  expect(
    await screen.findByText(/No positive theoretical discrepancy in this page/),
  ).toBeInTheDocument();
  expect(screen.getByRole('checkbox')).toBeChecked();
});

it('marks stale capacity evidence and exposes failed background analysis results', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      const value = url.includes('/operations')
        ? {
            services: [
              {
                unit: 'midas-veritas-source-analysis.service',
                available: true,
                properties: {
                  ActiveState: 'failed',
                  SubState: 'failed',
                  Result: 'oom-kill',
                  ExecMainStatus: '9',
                  NRestarts: '0',
                  ExecMainExitTimestamp: 'Thu 2026-11-05 17:41:16 CET',
                },
              },
            ],
          }
        : url.includes('/overview')
          ? {
              health: 'recording',
              collector: { cohort: [], books: {} },
              forward: {},
              capacity: {
                measured_ns: Date.now() * 1_000_000 - 2 * 60 * 60 * 1_000_000_000,
                freshness: { state: 'stale' },
                estimated_storage_seconds_remaining: 86400,
                alerts: [],
              },
            }
          : {};
      return Promise.resolve({ ok: true, json: async () => value });
    }),
  );
  mount();

  fireEvent.click(screen.getByRole('button', { name: /Operations/ }));
  expect(await screen.findByRole('alert')).toHaveTextContent(/Capacity estimate is stale/);
  expect(await screen.findByText(/oom-kill \/ 9/)).toBeInTheDocument();
  expect(screen.getByText(/Thu 2026-11-05 17:41:16 CET/)).toBeInTheDocument();
});

it('counts only confirmed sampled updates and refuses a gap-spanning update rate', () => {
  const samples = [
    { ns: 1e12, legs: { yes: { last: [10, 0] } } },
    { ns: 1e12 + 5e9, legs: { yes: { last: [20, 0] } } },
    { ns: 1e12 + 10e9, legs: { yes: { last: [20, 0] } } },
    { ns: 1e12 + 30e9, legs: { yes: { last: [30, 0] } } },
  ];
  expect(historySeries(samples, 'yes', 'sampled_update_rate').map((r) => r[1])).toEqual([
    null,
    0.2,
    0,
    null,
    null,
  ]);
});

it('breaks healthy-looking history across a recorded snapshot lineage reset', () => {
  const samples = [
    { ns: 1e12, legs: { yes: { snapshot: [1, 0], best_ask: '0.4', last: [2, 0] } } },
    { ns: 1e12 + 5e9, legs: { yes: { snapshot: [9, 0], best_ask: '0.5', last: [9, 0] } } },
  ];
  expect(historyBarrier(samples[1], samples[0])).toBe('snapshot_resynchronization_between_samples');
  expect(historySeries(samples, 'yes', 'best_ask')).toEqual([
    [1e6, 0.4],
    [1002500, null],
    [1005000, 0.5],
  ]);
  expect(historySeries(samples, 'yes', 'sampled_update_rate').at(-1)?.[1]).toBeNull();
});
