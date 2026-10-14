import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Reality } from './Reality';
import { historySeries } from './reality-history';
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
