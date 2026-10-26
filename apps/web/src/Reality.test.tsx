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
  expect(
    screen.getByText(/Displayed quotes do not establish hypothetical fills/),
  ).toBeInTheDocument();
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

it('reads the persisted selected cohort when the markets field is a count', async () => {
  const nowNs = Date.now() * 1_000_000;
  const yesAsset = 'yes-asset-fixture';
  const noAsset = 'no-asset-fixture';
  const market = {
    id: 'fixture-market',
    condition: 'fixture-condition',
    question: 'Fixture binary market',
    metadata_ordinal: 7,
    protocol: 'v1',
    selection_role: 'reference',
    negative_risk: false,
    tokens: { [yesAsset]: 'Yes', [noAsset]: 'No' },
  };
  const book = (bid: string, ask: string) => ({
    received_ns: nowNs,
    last: [10, 0],
    issue: null,
    best_bid: bid,
    best_ask: ask,
    spread: (Number(ask) - Number(bid)).toFixed(2),
    asks: [[ask, '100']],
    depth_truncated: false,
  });
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        now_ns: nowNs,
        health: 'recording',
        collector: {
          state: 'RECORDING_UNSEQUENCED',
          markets: 1,
          cohort: [market],
          books: { [yesAsset]: book('0.49', '0.51'), [noAsset]: book('0.48', '0.50') },
          observation_coverage: {
            [yesAsset]: {
              first_received_ns: nowNs - 1_000_000_000,
              last_received_ns: nowNs,
              book_update_frames: 2,
            },
            [noAsset]: {
              first_received_ns: nowNs - 1_000_000_000,
              last_received_ns: nowNs,
              book_update_frames: 2,
            },
          },
        },
        forward: {},
        capacity: {},
      }),
    }),
  );

  mount();
  await screen.findByText('The observation panel');
  expect(screen.getByText('Fixture binary market')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /Fixture binary market/ }));
  expect(await screen.findByRole('heading', { name: 'Yes' })).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: 'No' })).toBeInTheDocument();
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
