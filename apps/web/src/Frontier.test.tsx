import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Frontier } from './Frontier';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

it('renders recorded-evidence empty states and never probes a source automatically', async () => {
  const source = {
    venue: 'polymarket',
    adapter_version: 'frontier-polymarket-1',
    public_probe_enabled: false,
    capabilities: [
      {
        capability: 'market_discovery',
        supported: true,
        state: 'implemented',
        reason: 'public endpoint',
      },
    ],
    health: {
      state: 'not_probed',
      last_success_at_utc: null,
      last_error_code: null,
      last_error: null,
      notes: ['local-only status'],
    },
  };
  const responses: Record<string, unknown> = {
    '/api/frontier/overview': {
      state: 'EMPTY',
      research_only: true,
      live_execution: false,
      summary: {
        observations: 0,
        relationships: 0,
        runs: 0,
        markets_by_venue: {},
        instruments_by_venue: {},
        relationships_by_state: {},
        database_bytes: 0,
        max_bytes: 67_108_864,
      },
      sources: [source],
      latest_evidence_at_utc: null,
      limitations: ['No recorded evidence.'],
    },
    '/api/frontier/sources': { items: [source] },
    '/api/frontier/markets?limit=100': { items: [], returned: 0, limit: 100, offset: 0 },
    '/api/frontier/books?limit=100': { items: [], returned: 0, limit: 100, offset: 0 },
    '/api/frontier/relationships?limit=200': { items: [], returned: 0, limit: 200, offset: 0 },
    '/api/frontier/opportunities?limit=100': { items: [], returned: 0, limit: 100, offset: 0 },
    '/api/frontier/runs?limit=30': { items: [], returned: 0, limit: 30, offset: 0 },
    '/api/frontier/readiness': { gates: [] },
  };
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    const body = responses[path];
    if (body === undefined) throw new Error(`Unexpected frontend request: ${path}`);
    void init;
    return { ok: true, json: async () => body } as Response;
  });
  vi.stubGlobal('fetch', fetchMock);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <Frontier />
    </QueryClientProvider>,
  );

  expect(await screen.findByText('No replay runs yet')).toBeInTheDocument();
  expect(screen.getByText(/Latest evidence/)).toBeInTheDocument();
  expect(fetchMock.mock.calls.every(([, init]) => init?.method !== 'POST')).toBe(true);

  fireEvent.click(screen.getByRole('button', { name: 'Markets' }));
  expect(await screen.findByText('No market observations recorded')).toBeInTheDocument();
  expect(fetchMock.mock.calls.some(([input]) => String(input).includes('/probe/'))).toBe(false);
});
