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
    '/api/frontier/trades?limit=100': {
      items: [],
      pages: [],
      observation_count: 0,
      trade_count: 0,
      limit: 100,
      offset: 0,
    },
    '/api/frontier/relationships?limit=200': { items: [], returned: 0, limit: 200, offset: 0 },
    '/api/frontier/graph?depth=1&limit=100': {
      nodes: [],
      edges: [],
      center_market_id: null,
      search: null,
      depth: 1,
      edge_limit: 100,
      returned_nodes: 0,
      returned_edges: 0,
      truncated_by_edge_limit: false,
      relationship_scan_limit: 500,
      relationships_scanned: 0,
      relationship_scan_may_be_incomplete: false,
      next_cursor: null,
      source_market_window_limit: 200,
    },
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
  queryClient.setQueryData(['frontier', 'trades'], {
    items: [
      {
        venue: 'polymarket',
        native_market_id: 'condition:trade-fixture',
        native_trade_id: 'trade-fixture',
        native_instrument_id: null,
        outcome_label: null,
        outcome_index: null,
        price: '0.51',
        quantity: '3',
        quote_currency: 'USD',
        aggressor_side: 'BUY',
        exchange_timestamp_utc: null,
        received_at_utc: '2026-10-26T21:25:20.750899Z',
        source_observation_record_id: 'a'.repeat(64),
        source_raw_sha256: 'b'.repeat(64),
      },
    ],
    pages: [],
    observation_count: 1,
    trade_count: 1,
    limit: 100,
    offset: 0,
  });
  expect(await screen.findByText('condition:trade-fixture')).toBeInTheDocument();
  expect(screen.getByText('0.51 USD')).toBeInTheDocument();

  queryClient.setQueryData(['frontier', 'opportunities'], {
    items: [
      {
        candidate_id: 'multi-outcome-fixture-candidate',
        family: 'within_market_multi_outcome_coverage',
        classification: 'VERIFIED MATHEMATICAL INCONSISTENCY',
        hypothetical: true,
        practical_eligibility: false,
        venues: ['kalshi'],
        legs: [
          {
            venue: 'kalshi',
            native_market_id: 'KX-THREEWAY',
            instrument_id: 'KX-THREEWAY:RED',
            outcome_id: 'red',
            quantity: '10',
            quoted_ask: '0.20',
            modeled_buy_price: '0.20',
            modeled_fee: '0',
            displayed_depth: '10',
            book_observation_id: 'kalshi-red-book',
          },
        ],
        gross_cost: '9',
        modeled_fees: '0',
        modeled_net_cost: '9',
        outcome_payout_by_state: { red: '10', green: '10', blue: '10' },
        gross_pnl_by_state: { red: '1', green: '1', blue: '1' },
        net_pnl_by_state: { red: '1', green: '1', blue: '1' },
        worst_case_gross_pnl: '1',
        worst_case_net_pnl: '1',
        capital_by_venue: { kalshi: '9' },
        received_skew_ms: 12,
        exchange_skew_ms: 5,
        timing_verified: true,
        independent_audit: {
          disposition: 'verified',
          input_sha256: 'd'.repeat(64),
          checked_market_count: 1,
          checked_leg_count: 3,
          recomputed_gross_cost: '9',
          recomputed_modeled_fees: '0',
          recomputed_modeled_net_cost: '9',
          recomputed_worst_case_gross_pnl: '1',
          recomputed_worst_case_net_pnl: '1',
          checks: ['fixture audit checks'],
          message: 'Independent arithmetic agrees for every terminal state.',
        },
        reasons: ['The fixture covers every verified terminal state.'],
        assumptions: ['Hypothetical only.'],
        evidence_sha256: 'c'.repeat(64),
      },
    ],
    returned: 1,
    limit: 100,
    offset: 0,
  });
  fireEvent.click(screen.getByRole('button', { name: 'Candidates' }));
  expect(
    await screen.findByRole('heading', { name: 'Terminal-state payoff analysis' }),
  ).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: 'Independent arithmetic audit' })).toBeInTheDocument();
  expect(
    screen.getByText('Independent arithmetic agrees for every terminal state.'),
  ).toBeInTheDocument();
  expect(screen.getByText('Recomputed basket cost')).toBeInTheDocument();
  expect(screen.getByText('Gross basket cost')).toBeInTheDocument();
  expect(screen.getAllByText('red')).toHaveLength(2);
});

it('captures one explicit Polymarket trade page and follows its bound cursor', async () => {
  const conditionId = `0x${'a'.repeat(64)}`;
  const requests: Record<string, unknown>[] = [];
  const market = {
    canonical_id: 'polymarket:trade-condition',
    native_market_id: conditionId,
    native_fields: { conditionId },
    venue: 'polymarket',
    title: 'Recorded condition for page capture',
    market_kind: 'binary_event',
    lifecycle: 'open',
    instruments: [],
    quality_flags: [],
    provenance: { response_received_at_utc: '2026-10-26T20:00:00Z' },
  };
  const responses: Record<string, unknown> = {
    '/api/frontier/overview': {
      state: 'AVAILABLE',
      research_only: true,
      live_execution: false,
      summary: {
        observations: 1,
        relationships: 0,
        relationship_reviews: 0,
        runs: 0,
        markets_by_venue: { polymarket: 1 },
        instruments_by_venue: {},
        relationships_by_state: {},
        database_bytes: 1024,
        max_bytes: 67_108_864,
      },
      sources: [],
      latest_evidence_at_utc: '2026-10-26T20:00:00Z',
      limitations: [],
    },
    '/api/frontier/sources': {
      items: [
        {
          venue: 'polymarket',
          adapter_version: 'frontier-polymarket-2',
          public_probe_enabled: true,
          capabilities: [
            {
              capability: 'paginated_public_trades',
              supported: true,
              state: 'implemented',
              reason: 'explicit test fixture',
            },
          ],
          health: {
            state: 'not_probed',
            last_success_at_utc: null,
            last_error_code: null,
            last_error: null,
            notes: [],
          },
        },
      ],
    },
    '/api/frontier/markets?limit=100': { items: [market], returned: 1, limit: 100, offset: 0 },
    '/api/frontier/books?limit=100': { items: [], returned: 0, limit: 100, offset: 0 },
    '/api/frontier/trades?limit=100': {
      items: [],
      pages: [],
      observation_count: 0,
      trade_count: 0,
      limit: 100,
      offset: 0,
    },
    '/api/frontier/relationships?limit=200': { items: [], returned: 0, limit: 200, offset: 0 },
    '/api/frontier/graph?depth=1&limit=100': {
      nodes: [],
      edges: [],
      center_market_id: null,
      search: null,
      depth: 1,
      edge_limit: 100,
      returned_nodes: 0,
      returned_edges: 0,
      truncated_by_edge_limit: false,
      relationship_scan_limit: 500,
      relationships_scanned: 0,
      relationship_scan_may_be_incomplete: false,
      next_cursor: null,
      source_market_window_limit: 200,
    },
    '/api/frontier/opportunities?limit=100': { items: [], returned: 0, limit: 100, offset: 0 },
    '/api/frontier/runs?limit=30': { items: [], returned: 0, limit: 30, offset: 0 },
    '/api/frontier/readiness': { gates: [] },
  };
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    if (path === '/api/frontier/probe/polymarket/trades' && init?.method === 'POST') {
      const body = JSON.parse(String(init.body)) as Record<string, unknown>;
      requests.push(body);
      const hasMore = requests.length === 1;
      const result = {
        venue: 'polymarket',
        condition_id: conditionId,
        trade_count: 2,
        observation_id: `page-${requests.length}`,
        raw_sha256: 'b'.repeat(64),
        page_limit: 50,
        has_more: hasMore,
        next_cursor: hasMore ? 'frontier-next-page' : null,
        source_state: 'available',
        request_count_delta: 1,
        network_calls_bounded_by: 1,
        hypothetical_only: true,
        note: 'One public source page captured.',
      };
      return { ok: true, json: async () => result } as Response;
    }
    const body = responses[path];
    if (body === undefined) throw new Error(`Unexpected frontend request: ${path}`);
    void init;
    return { ok: true, json: async () => body } as Response;
  });
  vi.stubGlobal('fetch', fetchMock);
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <Frontier />
    </QueryClientProvider>,
  );

  expect(await screen.findByText('No replay runs yet')).toBeInTheDocument();
  expect(fetchMock.mock.calls.every(([, init]) => init?.method !== 'POST')).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: 'Markets' }));
  const conditionPicker = await screen.findByRole('combobox', {
    name: 'Polymarket trade condition',
  });
  fireEvent.change(conditionPicker, { target: { value: conditionId } });
  fireEvent.click(screen.getByRole('button', { name: 'Capture first page' }));
  expect(await screen.findByText(/Saved 2 trades/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Capture next page' }));
  await screen.findByText(/source reports no next page/);
  expect(requests).toEqual([
    { condition_id: conditionId, limit: 50 },
    { condition_id: conditionId, limit: 50, cursor: 'frontier-next-page' },
  ]);
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
    native_fields: venue === 'polymarket' ? { conditionId: `0x${'a'.repeat(64)}` } : {},
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
    '/api/frontier/trades?limit=100': {
      items: [],
      pages: [],
      observation_count: 0,
      trade_count: 0,
      limit: 100,
      offset: 0,
    },
    '/api/frontier/relationships?limit=200': {
      items: [relation],
      returned: 1,
      limit: 200,
      offset: 0,
    },
    '/api/frontier/graph?depth=1&limit=100': {
      nodes: [],
      edges: [relation],
      center_market_id: null,
      search: null,
      depth: 1,
      edge_limit: 100,
      returned_nodes: 0,
      returned_edges: 1,
      truncated_by_edge_limit: false,
      relationship_scan_limit: 500,
      relationships_scanned: 500,
      relationship_scan_may_be_incomplete: true,
      next_cursor: null,
      source_market_window_limit: 200,
    },
    '/api/frontier/opportunities?limit=100': { items: [], returned: 0, limit: 100, offset: 0 },
    '/api/frontier/runs?limit=30': { items: [], returned: 0, limit: 30, offset: 0 },
    '/api/frontier/readiness': { gates: [] },
  };
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input);
    const graphBase = responses['/api/frontier/graph?depth=1&limit=100'] as {
      edges: unknown[];
      [key: string]: unknown;
    };
    const graphParams = new URL(path, 'http://localhost').searchParams;
    const body = path.startsWith('/api/frontier/graph?')
      ? {
          ...graphBase,
          center_market_id: graphParams.get('center_market_id'),
          next_cursor: graphParams.get('cursor') ? null : 'cursor-page-2',
          truncated_by_edge_limit: !graphParams.get('cursor'),
        }
      : responses[path];
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
  expect(
    await screen.findByText(
      /considered 500 relationship rows.*additional neighbors may be omitted/,
    ),
  ).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Relationship graph center market'), {
    target: { value: 'polymarket:event-1' },
  });
  await vi.waitFor(() =>
    expect(
      fetchMock.mock.calls.some(([input]) => String(input).includes('center_market_id=')),
    ).toBe(true),
  );
  fireEvent.click(await screen.findByRole('button', { name: 'Load more neighbors' }));
  expect(await screen.findByText('Neighborhood page 2')).toBeInTheDocument();
  expect(
    fetchMock.mock.calls.some(([input]) => String(input).includes('cursor=cursor-page-2')),
  ).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: 'Previous page' }));
  const edge = await screen.findByRole('button', { name: /text candidate hypothesis/i });
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
    '/api/frontier/trades?limit=100': {
      items: [],
      pages: [],
      observation_count: 0,
      trade_count: 0,
      limit: 100,
      offset: 0,
    },
    '/api/frontier/relationships?limit=200': {
      items: [relationship],
      returned: 1,
      limit: 200,
    },
    '/api/frontier/graph?depth=1&limit=100': {
      nodes: [],
      edges: [relationship],
      center_market_id: null,
      search: null,
      depth: 1,
      edge_limit: 100,
      returned_nodes: 0,
      returned_edges: 1,
      truncated_by_edge_limit: false,
      relationship_scan_limit: 500,
      relationships_scanned: 1,
      relationship_scan_may_be_incomplete: false,
      next_cursor: null,
      source_market_window_limit: 200,
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
