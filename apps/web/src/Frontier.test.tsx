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
        relationship_reviews: 0,
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

it('renders a bounded accessible relationship graph and opens selected evidence', async () => {
  const marketRecord = (venue: 'polymarket' | 'kalshi', nativeId: string, title: string) => ({
    canonical_id: `${venue}:${nativeId}`,
    source_observation_record_id: `${venue}-observation`,
    native_market_id: nativeId,
    venue,
    title,
    market_kind: 'binary_event',
    lifecycle: 'open',
    description: '',
    base_asset: null,
    quote_asset: null,
    settlement_asset: null,
    payoff: {
      state_ids: [],
      payout_currency: null,
      exhaustive: false,
      verified: false,
      verification_basis: 'unverified',
    },
    resolution: {
      primary_rule: null,
      secondary_rule: null,
      authority: null,
      closes_at_utc: null,
      settles_at_utc: null,
      evidence_sha256: null,
      verified: false,
    },
    fees: {
      status: 'unknown',
      version: null,
      applies_to: null,
      rate: null,
      formula: null,
      fee_currency: null,
      source_url: null,
      note: 'unknown',
    },
    instruments: [],
    quality_flags: [],
    provenance: {
      response_received_at_utc: '2026-10-26T20:00:00Z',
      raw_sha256: 'a'.repeat(64),
      observation_id: `${venue}-observation`,
    },
  });
  const relation = {
    relationship_id: 'edge-1',
    left_market_id: 'polymarket:event-1',
    right_market_id: 'kalshi:event-1',
    relationship_type: 'text_candidate',
    state: 'hypothesis',
    confidence: '0.75',
    reason: 'Shared title terms; rules and resolution dates have not been checked.',
    supersedes: null,
    review_target_relationship_id: 'edge-1',
    latest_review: null,
    evidence: [
      {
        method: 'deterministic-indexed-metadata-v1',
        observation_ids: ['p-obs', 'k-obs'],
        source_fields: ['title'],
        details: ['shared_terms=mayor,election'],
      },
    ],
  };
  const responses: Record<string, unknown> = {
    '/api/frontier/overview': {
      state: 'AVAILABLE',
      research_only: true,
      live_execution: false,
      summary: {
        observations: 2,
        relationships: 1,
        relationship_reviews: 0,
        runs: 0,
        markets_by_venue: { polymarket: 1, kalshi: 1 },
        instruments_by_venue: {},
        relationships_by_state: { hypothesis: 1 },
        database_bytes: 4096,
        max_bytes: 67_108_864,
      },
      sources: [],
      latest_evidence_at_utc: '2026-10-26T20:00:00Z',
      limitations: [],
    },
    '/api/frontier/sources': { items: [] },
    '/api/frontier/markets?limit=100': {
      items: [
        marketRecord('polymarket', 'event-1', 'Who wins the mayoral election?'),
        marketRecord('kalshi', 'event-1', 'Who wins the mayoral election?'),
      ],
      returned: 2,
      limit: 100,
      offset: 0,
    },
    '/api/frontier/books?limit=100': { items: [], returned: 0, limit: 100, offset: 0 },
    '/api/frontier/relationships?limit=200': {
      items: [relation],
      returned: 1,
      limit: 200,
      offset: 0,
    },
    '/api/frontier/opportunities?limit=100': { items: [], returned: 0, limit: 100, offset: 0 },
    '/api/frontier/runs?limit=30': { items: [], returned: 0, limit: 30, offset: 0 },
    '/api/frontier/readiness': { gates: [] },
  };
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const body = responses[String(input)];
    if (body === undefined) throw new Error(`Unexpected frontend request: ${String(input)}`);
    return { ok: true, json: async () => body } as Response;
  });
  vi.stubGlobal('fetch', fetchMock);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <Frontier />
    </QueryClientProvider>,
  );

  fireEvent.click(await screen.findByRole('button', { name: 'Relationship graph' }));
  expect(
    await screen.findByRole('group', { name: /Relationship network showing 1/ }),
  ).toBeInTheDocument();
  const edge = screen.getByRole('button', { name: /text candidate hypothesis/i });
  fireEvent.click(edge);
  expect(edge).toHaveAttribute('aria-pressed', 'true');
  expect(
    await screen.findByText(/Shared title terms; rules and resolution dates/, { selector: 'p' }),
  ).toBeInTheDocument();
});

it('records a self-attributed relationship review with both stored market sources', async () => {
  const markets = [
    {
      canonical_id: 'polymarket:event-1',
      source_observation_record_id: 'a'.repeat(64),
      native_market_id: 'poly-event',
      venue: 'polymarket',
      title: 'Election event at Polymarket',
      market_kind: 'binary_event',
      instruments: [],
      settlement_asset: null,
      payoff: {
        state_ids: [],
        payout_currency: null,
        exhaustive: false,
        verified: false,
        verification_basis: 'fixture only',
      },
      resolution: {
        authority: null,
        closes_at_utc: null,
        settles_at_utc: null,
        resolution_fingerprint: null,
      },
    },
    {
      canonical_id: 'kalshi:event-1',
      source_observation_record_id: 'b'.repeat(64),
      native_market_id: 'kalshi-event',
      venue: 'kalshi',
      title: 'Election event at Kalshi',
      market_kind: 'binary_event',
      instruments: [],
      settlement_asset: null,
      payoff: {
        state_ids: [],
        payout_currency: null,
        exhaustive: false,
        verified: false,
        verification_basis: 'fixture only',
      },
      resolution: {
        authority: null,
        closes_at_utc: null,
        settles_at_utc: null,
        resolution_fingerprint: null,
      },
    },
  ];
  const relationship = {
    relationship_id: 'c'.repeat(64),
    left_market_id: 'polymarket:event-1',
    right_market_id: 'kalshi:event-1',
    relationship_type: 'text_candidate',
    state: 'hypothesis',
    confidence: '0.75',
    reason: 'Shared terms only; review settlement details.',
    supersedes: null,
    review_target_relationship_id: 'c'.repeat(64),
    latest_review: null,
    evidence: [],
  };
  const responses: Record<string, unknown> = {
    '/api/frontier/overview': {
      state: 'AVAILABLE',
      research_only: true,
      live_execution: false,
      summary: {
        observations: 2,
        relationships: 1,
        relationship_reviews: 0,
        runs: 0,
        markets_by_venue: { polymarket: 1, kalshi: 1 },
        instruments_by_venue: {},
        relationships_by_state: { hypothesis: 1 },
        database_bytes: 4096,
        max_bytes: 67_108_864,
      },
      sources: [],
      latest_evidence_at_utc: '2026-10-26T20:00:00Z',
      limitations: [],
    },
    '/api/frontier/sources': { items: [] },
    '/api/frontier/markets?limit=100': { items: markets, returned: 2, limit: 100, offset: 0 },
    '/api/frontier/books?limit=100': { items: [], returned: 0, limit: 100, offset: 0 },
    '/api/frontier/relationships?limit=200': {
      items: [relationship],
      returned: 1,
      limit: 200,
    },
    '/api/frontier/opportunities?limit=100': { items: [], returned: 0, limit: 100, offset: 0 },
    '/api/frontier/runs?limit=30': { items: [], returned: 0, limit: 30, offset: 0 },
    '/api/frontier/readiness': { gates: [] },
  };
  const reviewRequest = vi.fn();
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    if (path.endsWith('/relationships/' + 'c'.repeat(64) + '/review')) {
      reviewRequest(JSON.parse(String(init?.body)));
      return { ok: true, json: async () => ({ review: {}, relationship: {} }) } as Response;
    }
    const body = responses[path];
    if (body === undefined) throw new Error(`Unexpected frontend request: ${path}`);
    return { ok: true, json: async () => body } as Response;
  });
  vi.stubGlobal('fetch', fetchMock);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <Frontier />
    </QueryClientProvider>,
  );

  fireEvent.click(await screen.findByRole('button', { name: 'Relationship graph' }));
  fireEvent.click(screen.getByRole('button', { name: 'Review hypothesis' }));
  fireEvent.change(screen.getByLabelText('Reviewer label'), { target: { value: 'reviewer-1' } });
  fireEvent.change(screen.getByLabelText('Review reason'), {
    target: { value: 'Rules remain incomplete for equivalence.' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Record immutable review' }));

  await vi.waitFor(() => expect(reviewRequest).toHaveBeenCalledOnce());
  expect(reviewRequest.mock.calls[0][0]).toMatchObject({
    decision: 'ambiguous',
    reviewer_label: 'reviewer-1',
    evidence_observation_ids: ['a'.repeat(64), 'b'.repeat(64)],
    expected_latest_review_id: null,
  });
});
