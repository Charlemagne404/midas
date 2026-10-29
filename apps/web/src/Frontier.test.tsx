import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Frontier } from './Frontier';

const USD_IDENTITY = {
  schema_version: 1,
  kind: 'fiat',
  code: 'USD',
  network_id: null,
  asset_reference: null,
} as const;

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

it('renders recorded-evidence empty states and never probes a source automatically', async () => {
  const source = {
    venue: 'coinbase_exchange',
    adapter_version: 'frontier-coinbase-exchange-spot-1',
    public_probe_enabled: false,
    probe_policy_block_reason:
      'Coinbase Exchange source use remains held because Frontier has no validated permission or intended-scope review. The 2026-08-07 Market Data Terms require prior express written consent to use data to develop, train, fine-tune, teach, validate, benchmark, or improve AI/ML models, algorithms, chatbots, agents, or other automated systems, or for related AI research, development, or operation. Acknowledging the terms does not lift the hold; no Coinbase request will be made.',
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
  const enabledSource = {
    venue: 'polymarket',
    adapter_version: 'frontier-polymarket-v1',
    public_probe_enabled: true,
    capabilities: [
      {
        capability: 'market_discovery',
        supported: true,
        state: 'implemented',
        reason: 'one bounded public listing request',
      },
      {
        capability: 'book_snapshot',
        supported: true,
        state: 'implemented',
        reason: 'one bounded public book request',
      },
      {
        capability: 'public_trades',
        supported: true,
        state: 'implemented',
        reason: 'one bounded public trade request',
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
  const geminiSource = {
    venue: 'gemini_spot',
    adapter_version: 'frontier-gemini-spot-1',
    public_probe_enabled: false,
    probe_policy_block_reason:
      'Gemini source use remains held until its residency-specific agreement, intended scope, and API Use Form are reviewed.',
    capabilities: [
      {
        capability: 'market_discovery',
        supported: true,
        state: 'implemented',
        reason: 'configured symbols only',
      },
      {
        capability: 'book_snapshot',
        supported: true,
        state: 'implemented',
        reason: 'bounded aggregated book',
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
      sources: [source, geminiSource],
      latest_evidence_at_utc: null,
      limitations: ['No recorded evidence.'],
    },
    '/api/frontier/sources': { items: [source, enabledSource, geminiSource] },
    '/api/frontier/collection-runs?limit=20': {
      items: [],
      returned: 0,
      limit: 20,
      next_before_run_id: null,
      network_called: false,
      research_only: true,
    },
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
    '/api/frontier/comparisons?limit=30': { items: [], returned: 0, limit: 30, offset: 0 },
    '/api/frontier/readiness': { gates: [] },
    '/api/frontier/analytics/coverage': {
      schema_version: 3,
      as_of_utc: '2026-10-27T21:00:00Z',
      scope: 'Latest bounded hash-checked stored market, book, and eligible replay samples.',
      samples: {
        distinct_markets: 0,
        market_records: 0,
        book_observation_records: 0,
        invalid_normalized_book_records: 0,
        public_trade_observation_records: 0,
        invalid_normalized_public_trade_records: 0,
        price_history_observation_records: 0,
        invalid_normalized_price_history_records: 0,
        unique_instrument_books: 0,
        eligible_replay_runs: 0,
        candidate_records: 0,
        candidate_scan_truncated: false,
        market_record_limit: 50,
        book_record_limit: 50,
        public_trade_record_limit: 50,
        replay_run_limit: 20,
        price_history_record_limit: 20,
        candidate_record_limit: 5000,
      },
      market_mix: [],
      stored_market_counts_by_venue: [],
      source_quality: ['polymarket', 'kalshi', 'kraken', 'coinbase_exchange', 'gemini_spot'].map(
        (venue) => ({
          venue,
          latest_instrument_books: 0,
          quality_valid_pricing_books: 0,
          two_sided_books: 0,
          one_sided_or_empty_books: 0,
          crossed_books: 0,
          flagged_books: 0,
          unflagged_books: 0,
          unjoined_or_provenance_mismatch_records: 0,
          with_exchange_timestamp: 0,
          with_clock_uncertainty: 0,
          with_declared_freshness_limit: 0,
          without_declared_freshness_limit: 0,
          within_declared_freshness_limit: 0,
          stale_by_declared_freshness_limit: 0,
          future_received_timestamp: 0,
          median_receipt_age_ms: null,
          p90_receipt_age_ms: null,
        }),
      ),
      historical_price_quality_scope:
        'Newest bounded saved captures by venue; gaps describe returned samples only.',
      public_trade_quality_scope:
        'Newest bounded saved public-trade responses. Empty results do not establish venue-wide volume.',
      public_trade_quality: [
        'polymarket',
        'kalshi',
        'kraken',
        'coinbase_exchange',
        'gemini_spot',
      ].map((venue) => ({
        venue,
        capture_count: 0,
        invalid_capture_count: 0,
        trade_print_count: 0,
        empty_capture_count: 0,
        unique_market_count: 0,
        unique_instrument_count: 0,
        prints_with_exchange_timestamp: 0,
        prints_without_exchange_timestamp: 0,
        prints_with_clock_uncertainty: 0,
        prints_without_clock_uncertainty: 0,
        future_capture_timestamp_count: 0,
        future_exchange_timestamp_count: 0,
        latest_capture_received_at_utc: null,
        median_capture_age_ms: null,
        p90_capture_age_ms: null,
      })),
      historical_price_quality: [
        'polymarket',
        'kalshi',
        'kraken',
        'coinbase_exchange',
        'gemini_spot',
      ].map((venue) => ({
        venue,
        capture_count: 0,
        unique_instrument_count: 0,
        source_point_count: 0,
        empty_capture_count: 0,
        market_bound_capture_count: 0,
        unbound_capture_count: 0,
        future_capture_timestamp_count: 0,
        future_point_timestamp_count: 0,
        latest_capture_received_at_utc: null,
        median_capture_age_ms: null,
        p90_capture_age_ms: null,
        earliest_source_point_at_utc: null,
        latest_source_point_at_utc: null,
        largest_adjacent_sample_gap_seconds: null,
      })),
      pricing: [],
      candidate_research: {
        counts_by_classification: {},
        independently_audited_candidates: 0,
        audited_timing_verified_candidates: 0,
        median_audited_received_skew_ms: null,
        p90_audited_received_skew_ms: null,
        median_audited_exchange_skew_ms: null,
        p90_audited_exchange_skew_ms: null,
        gross_positive_audited_timing_verified_constructions_repeated_across_distinct_books: 0,
        gross_positive_candidate_construction_signatures: 0,
        rejection_reasons: [],
      },
      network_called: false,
      limitations: ['Counts describe bounded recorded samples, not venue-wide coverage.'],
    },
  };
  let collectionState = 'paused';
  const jointReplayRequests: { mapping: Record<string, unknown> }[] = [];
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    if (
      path ===
      '/api/frontier/collection-runs?limit=20&before_run_id=f79d58bb-e799-4718-93f1-a94bb7492f21'
    ) {
      return {
        ok: true,
        json: async () => ({
          items: [
            {
              run_id: '01234567-89ab-41cd-8ef0-123456789abc',
              venue: 'polymarket',
              adapter_version: 'frontier-polymarket-v1',
              created_at_utc: '2026-10-27T00:00:00Z',
              updated_at_utc: '2026-10-27T00:00:00Z',
              state: 'completed',
              checkpoint_sequence: 4,
              checkpoint_sha256: 'b'.repeat(64),
              market_count: 2,
              book_count: 1,
              failed_book_count: 0,
              trade_batch_count: 1,
              trade_count: 2,
              failed_trade_count: 0,
              request_count: 3,
              failure_count: 0,
              source_health_state: 'healthy',
              resumable: false,
              resume_block_reason: 'Collection run is terminal.',
            },
          ],
          returned: 1,
          limit: 20,
          next_before_run_id: null,
          network_called: false,
          research_only: true,
        }),
      } as Response;
    }
    if (path === '/api/frontier/collection-runs?limit=20') {
      const items = collectionState
        ? [
            {
              run_id: 'f79d58bb-e799-4718-93f1-a94bb7492f21',
              venue: 'polymarket',
              adapter_version: 'frontier-polymarket-v1',
              created_at_utc: '2026-10-28T00:00:00Z',
              updated_at_utc: '2026-10-28T00:00:00Z',
              state: collectionState,
              checkpoint_sequence: 2,
              checkpoint_sha256: 'a'.repeat(64),
              market_count: 1,
              book_count: 0,
              failed_book_count: 0,
              trade_batch_count: 0,
              trade_count: 0,
              failed_trade_count: 0,
              request_count: 1,
              failure_count: 1,
              source_health_state: 'degraded',
              resumable: collectionState === 'paused',
              resume_block_reason:
                collectionState === 'paused' ? null : 'Collection run is terminal.',
            },
          ]
        : [];
      return {
        ok: true,
        json: async () => ({
          items,
          returned: items.length,
          limit: 20,
          next_before_run_id: items.length > 0 ? items[0].run_id : null,
          network_called: false,
          research_only: true,
        }),
      } as Response;
    }
    if (path === '/api/frontier/collect/polymarket' && init?.method === 'POST') {
      expect(JSON.parse(String(init.body))).toEqual({
        market_limit: 3,
        book_limit: 1,
        book_depth: 5,
        trade_market_limit: 1,
        trade_limit_per_market: 10,
        max_wall_seconds: 30,
      });
      return {
        ok: true,
        json: async () => ({
          venue: 'polymarket',
          collection_run: {
            run_id: 'f79d58bb-e799-4718-93f1-a94bb7492f21',
            state: 'paused',
            market_count: 1,
            book_count: 0,
            failed_book_count: 0,
            trade_batch_count: 0,
            trade_count: 0,
            failed_trade_count: 0,
            request_count: 1,
            updated_at_utc: '2026-10-28T00:00:00Z',
            failures: [{ code: 'COLLECTION_WALL_LIMIT', message: 'Fixture pause.' }],
            source_health: { state: 'degraded' },
          },
          adapter_request_count: 1,
          adapter_request_upper_bound_per_attempt: 10,
          research_only: true,
          live_orders: false,
          source_health_scope: 'adapter_local_checkpoint',
          note: 'Fixture response only.',
        }),
      } as Response;
    }
    if (
      path === '/api/frontier/collect/polymarket/f79d58bb-e799-4718-93f1-a94bb7492f21/resume' &&
      init?.method === 'POST'
    ) {
      collectionState = 'completed';
      return {
        ok: true,
        json: async () => ({
          venue: 'polymarket',
          collection_run: {
            run_id: 'f79d58bb-e799-4718-93f1-a94bb7492f21',
            state: 'completed',
            market_count: 1,
            book_count: 1,
            failed_book_count: 0,
            trade_batch_count: 1,
            trade_count: 2,
            failed_trade_count: 0,
            request_count: 3,
            updated_at_utc: '2026-10-28T00:00:30Z',
            failures: [],
            source_health: { state: 'healthy' },
          },
          adapter_request_count: 3,
          adapter_request_upper_bound_per_attempt: 10,
          research_only: true,
          live_orders: false,
          source_health_scope: 'adapter_local_checkpoint',
          note: 'Fixture response only.',
        }),
      } as Response;
    }
    if (path === '/api/frontier/replay/joint-state' && init?.method === 'POST') {
      jointReplayRequests.push(
        JSON.parse(String(init.body)) as { mapping: Record<string, unknown> },
      );
      return {
        ok: true,
        json: async () => ({
          run_id: 'c'.repeat(64),
          manifest: {
            joint_state_mappings: [{ mapping_id: 'd'.repeat(64) }],
          },
          candidates: [],
          classification_counts: {},
        }),
      } as Response;
    }
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
  fireEvent.click(screen.getByRole('button', { name: 'Coverage & quality' }));
  expect(await screen.findByRole('heading', { name: 'Recent market mix' })).toBeInTheDocument();
  expect(
    screen.getByRole('heading', { name: 'Price-history capture coverage' }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole('heading', { name: 'Public trade capture coverage' }),
  ).toBeInTheDocument();
  expect(screen.getByText('No eligible market records')).toBeInTheDocument();
  expect(screen.getByText('No quality-valid book pairs')).toBeInTheDocument();
  expect(screen.getByText('No saved price-history captures')).toBeInTheDocument();
  expect(screen.getByText('No saved public-trade captures')).toBeInTheDocument();
  expect(screen.getByText(/not venue-wide coverage/)).toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', { name: 'Exchanges' }));
  expect(
    await screen.findAllByText(/Live capture and stored records are held from research use/),
  ).toHaveLength(2);
  expect(screen.getByRole('heading', { name: 'Coinbase Exchange Spot' })).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: 'Gemini Spot' })).toBeInTheDocument();
  expect(screen.getAllByText(/A spot price is not a prediction-contract payoff/)).toHaveLength(2);
  expect(screen.getByText(/terms acknowledgment is not authorization/)).toBeInTheDocument();
  expect(
    screen.getByText(/develop, train, fine-tune, teach, validate, benchmark, or improve/),
  ).toBeInTheDocument();
  expect(screen.getByText(/residency-specific agreement and.*scope review/)).toBeInTheDocument();
  expect(screen.getAllByRole('button', { name: 'Public probe disabled' })).toHaveLength(2);
  screen
    .getAllByRole('button', { name: 'Public probe disabled' })
    .forEach((button) => expect(button).toBeDisabled());
  fireEvent.click(
    screen.getByRole('checkbox', {
      name: 'Include up to 10 public trade prints from 1 discovered market',
    }),
  );
  fireEvent.click(screen.getByRole('button', { name: 'Capture finite batch with checkpoints' }));
  expect(await screen.findByText('Finite capture paused')).toBeInTheDocument();
  expect(screen.getAllByText(/1 market\(s\) · 0 book\(s\) · 0 failed book\(s\)/)).toHaveLength(2);
  expect(
    screen.getByText(/1 total adapter requests across run · at most 10 per attempt/),
  ).toBeInTheDocument();
  expect(screen.getByText(/does not establish continuous venue availability/)).toBeInTheDocument();
  const resumeButton = screen.getByRole('button', {
    name: /Resume collection run f79d58bb-e79/,
  });
  expect(resumeButton).toBeEnabled();
  fireEvent.click(resumeButton);
  expect(
    await screen.findByText(/3 total adapter requests across run · at most 10 per attempt/),
  ).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /Resume collection run f79d58bb-e79/ })).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: 'Load older runs' }));
  expect(await screen.findByText(/Run 01234567-89a…/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Newest runs' }));
  expect(await screen.findByText(/Run f79d58bb-e79…/)).toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', { name: 'Markets' }));
  expect(await screen.findByText('No market observations recorded')).toBeInTheDocument();
  expect(fetchMock.mock.calls.some(([input]) => String(input).includes('/probe/'))).toBe(false);
  queryClient.setQueryData(['frontier', 'trades'], {
    items: [
      {
        venue: 'kalshi',
        native_market_id: 'KX-FRONTIER-TRADE',
        native_trade_id: 'kalshi-trade-fixture',
        native_instrument_id: 'KX-FRONTIER-TRADE:YES',
        outcome_label: 'YES price reference',
        outcome_index: null,
        price: '0.51',
        quantity: '3',
        quote_currency: 'USD',
        aggressor_side: null,
        is_block_trade: true,
        taker_outcome_side: 'no',
        taker_book_side: 'bid',
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
  expect(await screen.findByText('KX-FRONTIER-TRADE')).toBeInTheDocument();
  expect(screen.getByText(/0\.51 USD · denomination identity unknown/)).toBeInTheDocument();
  expect(screen.getByText('Taker no · bid book')).toBeInTheDocument();
  expect(screen.getByText('Block trade')).toBeInTheDocument();

  queryClient.setQueryData(['frontier', 'opportunities'], {
    items: [
      {
        candidate_id: 'multi-outcome-fixture-candidate',
        family: 'within_market_payoff_basket',
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
            quantity_unit: 'contract',
            quantity: '10',
            quoted_ask: '0.20',
            modeled_buy_price: '0.20',
            modeled_fee: '0',
            quote_currency: 'USD',
            quote_currency_identity: USD_IDENTITY,
            displayed_depth: '10',
            book_observation_id: 'kalshi-red-book',
          },
          {
            venue: 'kalshi',
            native_market_id: 'KX-THREEWAY',
            instrument_id: 'KX-THREEWAY:GREEN',
            outcome_id: 'green',
            quantity_unit: 'contract',
            quantity: '10',
            quoted_ask: '0.30',
            modeled_buy_price: '0.30',
            modeled_fee: '0',
            quote_currency: 'USD',
            quote_currency_identity: USD_IDENTITY,
            displayed_depth: '10',
            book_observation_id: 'kalshi-green-book',
          },
          {
            venue: 'kalshi',
            native_market_id: 'KX-THREEWAY',
            instrument_id: 'KX-THREEWAY:BLUE',
            outcome_id: 'blue',
            quantity_unit: 'contract',
            quantity: '10',
            quoted_ask: '0.40',
            modeled_buy_price: '0.40',
            modeled_fee: '0',
            quote_currency: 'USD',
            quote_currency_identity: USD_IDENTITY,
            displayed_depth: '10',
            book_observation_id: 'kalshi-blue-book',
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
        capital_currency_identity: USD_IDENTITY,
        one_sided_fill_sensitivity: {
          model_version: 'frontier-full-or-none-fill-patterns-1',
          leg_count: 3,
          pattern_space_size: 8,
          fees_complete: true,
          worst_before_fees: {
            terminal_state_id: 'red',
            filled_leg_ids: [
              'kalshi:KX-THREEWAY:KX-THREEWAY:GREEN',
              'kalshi:KX-THREEWAY:KX-THREEWAY:BLUE',
            ],
            unfilled_leg_ids: ['kalshi:KX-THREEWAY:KX-THREEWAY:RED'],
            pnl_before_fees: '-7',
            pnl_after_fees: null,
          },
          worst_after_fees: {
            terminal_state_id: 'red',
            filled_leg_ids: [
              'kalshi:KX-THREEWAY:KX-THREEWAY:GREEN',
              'kalshi:KX-THREEWAY:KX-THREEWAY:BLUE',
            ],
            unfilled_leg_ids: ['kalshi:KX-THREEWAY:KX-THREEWAY:RED'],
            pnl_before_fees: '-7',
            pnl_after_fees: '-7',
          },
          assumptions: ['Pattern comparison only; not an execution forecast.'],
        },
        partial_fill_grid_sensitivity: {
          model_version: 'frontier-partial-fill-grid-1',
          leg_count: 3,
          fill_fraction_grid: ['0', '0.25', '0.5', '0.75', '1'],
          feasible_fill_fractions_by_leg: {
            'kalshi:KX-THREEWAY:KX-THREEWAY:RED': ['0', '0.25', '0.5', '0.75', '1'],
            'kalshi:KX-THREEWAY:KX-THREEWAY:GREEN': ['0', '0.25', '0.5', '0.75', '1'],
            'kalshi:KX-THREEWAY:KX-THREEWAY:BLUE': ['0', '0.25', '0.5', '0.75', '1'],
          },
          fees_complete: true,
          worst_before_fees: {
            terminal_state_id: 'red',
            leg_fills: [
              {
                leg_id: 'kalshi:KX-THREEWAY:KX-THREEWAY:RED',
                fill_fraction: '0',
                filled_quantity: '0',
              },
              {
                leg_id: 'kalshi:KX-THREEWAY:KX-THREEWAY:GREEN',
                fill_fraction: '0.25',
                filled_quantity: '2.5',
              },
              {
                leg_id: 'kalshi:KX-THREEWAY:KX-THREEWAY:BLUE',
                fill_fraction: '0.5',
                filled_quantity: '5',
              },
            ],
            pnl_before_fees: '-3',
            pnl_after_fees: null,
          },
          worst_after_fees: {
            terminal_state_id: 'red',
            leg_fills: [
              {
                leg_id: 'kalshi:KX-THREEWAY:KX-THREEWAY:RED',
                fill_fraction: '0',
                filled_quantity: '0',
              },
              {
                leg_id: 'kalshi:KX-THREEWAY:KX-THREEWAY:GREEN',
                fill_fraction: '0.25',
                filled_quantity: '2.5',
              },
              {
                leg_id: 'kalshi:KX-THREEWAY:KX-THREEWAY:BLUE',
                fill_fraction: '0.5',
                filled_quantity: '5',
              },
            ],
            pnl_before_fees: '-3',
            pnl_after_fees: '-3.01',
          },
          assumptions: ['Fixture partial-fill grid; no fill probability.'],
        },
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
          recomputed_received_skew_ms: 12,
          recomputed_exchange_skew_ms: 5,
          recomputed_timing_verified: true,
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
  expect(await screen.findByText('within market payoff basket')).toBeInTheDocument();
  expect(
    await screen.findByRole('heading', { name: 'Terminal-state payoff analysis' }),
  ).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: 'Independent arithmetic audit' })).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: 'One-sided fill stress' })).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: 'Bounded partial-fill grid' })).toBeInTheDocument();
  expect(screen.getByText(/Exact worst case over 8 full-or-none leg patterns/)).toBeInTheDocument();
  const fillStress = screen.getByRole('region', { name: 'One-sided fill stress' });
  expect(fillStress.textContent).toContain(
    'Filled: Kalshi · green (KX-THREEWAY), Kalshi · blue (KX-THREEWAY)',
  );
  const partialFillStress = screen.getByRole('region', { name: 'Partial-fill grid sensitivity' });
  expect(partialFillStress.textContent).toContain('green (KX-THREEWAY): 25% (2.5)');
  expect(partialFillStress.textContent).toContain('Worst sampled result after fees');
  expect(
    screen.getByText('Independent arithmetic agrees for every terminal state.'),
  ).toBeInTheDocument();
  expect(screen.getByText('Recomputed basket cost')).toBeInTheDocument();
  expect(screen.getByText('Recomputed receipt skew').parentElement).toHaveTextContent('12 ms');
  expect(screen.getByText('Recomputed exchange timestamp skew').parentElement).toHaveTextContent(
    '5 ms',
  );
  expect(screen.getByText('Independent timing gate').parentElement).toHaveTextContent('Pass');
  const candidateCache = queryClient.getQueryData<{
    items: Array<
      Record<string, unknown> & {
        candidate_id: string;
        independent_audit: Record<string, unknown> | null;
      }
    >;
  }>(['frontier', 'opportunities']);
  expect(candidateCache).toBeDefined();
  queryClient.setQueryData(['frontier', 'opportunities'], {
    ...candidateCache!,
    items: candidateCache!.items.map((item) => {
      if (item.candidate_id !== 'multi-outcome-fixture-candidate' || !item.independent_audit) {
        return item;
      }
      const legacyAudit = Object.fromEntries(
        Object.entries(item.independent_audit).filter(
          ([key]) =>
            ![
              'recomputed_received_skew_ms',
              'recomputed_exchange_skew_ms',
              'recomputed_timing_verified',
            ].includes(key),
        ),
      );
      return { ...item, independent_audit: legacyAudit };
    }),
  });
  await waitFor(() => {
    const missingReceiptSkew = screen
      .getAllByText('Recomputed receipt skew')
      .find((item) => item.parentElement?.textContent?.includes('Not recorded'));
    expect(missingReceiptSkew?.parentElement).toHaveTextContent('Not recorded');
  });
  const missingExchangeSkew = screen
    .getAllByText('Recomputed exchange timestamp skew')
    .find((item) => item.parentElement?.textContent?.includes('Not recorded'));
  expect(missingExchangeSkew?.parentElement).toHaveTextContent('Not recorded');
  const missingTimingGate = screen
    .getAllByText('Independent timing gate')
    .find((item) => item.parentElement?.textContent?.includes('Not recorded'));
  expect(missingTimingGate?.parentElement).toHaveTextContent('Not recorded');
  expect(screen.getByText('Gross basket cost')).toBeInTheDocument();
  const capital = screen.getByRole('region', { name: 'Venue-separated virtual funding' });
  expect(capital).toHaveTextContent('Modeled requirement: 9 USD (fiat:USD)');
  expect(capital).toHaveTextContent('separate virtual balance');
  const virtualBalance = screen.getByRole('textbox', {
    name: 'Virtual balance allocated to Kalshi USD (fiat:USD)',
  });
  fireEvent.change(virtualBalance, { target: { value: '8.999999999999999999' } });
  expect(capital).toHaveTextContent('Virtual funding shortfall at this venue.');
  fireEvent.change(virtualBalance, { target: { value: '9.000000000000000000' } });
  expect(capital).toHaveTextContent('Modeled requirement covered at this venue.');
  expect(capital).toHaveTextContent('No account, wallet, deposit, transfer, or order interface');
  const recordedCandidates = queryClient.getQueryData<{
    items: Array<{
      candidate_id: string;
      modeled_fees: string | null;
      modeled_net_cost: string | null;
      capital_by_venue: Record<string, string>;
      legs: Array<{ modeled_fee: string | null }>;
    }>;
  }>(['frontier', 'opportunities']);
  expect(recordedCandidates).toBeDefined();
  queryClient.setQueryData(['frontier', 'opportunities'], {
    ...recordedCandidates!,
    items: recordedCandidates!.items.map((item) =>
      item.candidate_id === 'multi-outcome-fixture-candidate'
        ? {
            ...item,
            modeled_fees: null,
            modeled_net_cost: null,
            capital_by_venue: { kalshi: '9.0E+0' },
            legs: item.legs.map((leg) => ({ ...leg, modeled_fee: null })),
          }
        : item,
    ),
  });
  await waitFor(() =>
    expect(capital).toHaveTextContent('Recorded principal is covered; unresolved fees remain.'),
  );
  queryClient.setQueryData(['frontier', 'opportunities'], {
    ...recordedCandidates!,
    items: recordedCandidates!.items.map((item) =>
      item.candidate_id === 'multi-outcome-fixture-candidate'
        ? {
            ...item,
            legs: item.legs.map((leg, index) =>
              index === 1 ? { ...leg, quote_currency: null } : leg,
            ),
          }
        : item,
    ),
  });
  await waitFor(() =>
    expect(capital).toHaveTextContent(
      'Currency identity is missing or mixed; comparison unavailable.',
    ),
  );
  expect(
    within(capital).getByRole('textbox', {
      name: 'Virtual balance allocated to Kalshi unknown currency',
    }),
  ).toBeDisabled();

  const tokenUsdIdentity = {
    schema_version: 1,
    kind: 'token',
    code: 'USD',
    network_id: 'eip155:137',
    asset_reference: `0x${'cafe'.repeat(10)}`,
  } as const;
  const tokenIdentityLabel = 'token:USD:eip155%3A137:' + tokenUsdIdentity.asset_reference;
  const withTokenCapital = (includeMatchingLegUnits: boolean) => ({
    ...recordedCandidates!,
    items: recordedCandidates!.items.map((item) =>
      item.candidate_id === 'multi-outcome-fixture-candidate'
        ? {
            ...item,
            capital_currency_identity: tokenUsdIdentity,
            legs: item.legs.map((leg) => ({
              ...leg,
              quote_currency_identity: includeMatchingLegUnits ? tokenUsdIdentity : USD_IDENTITY,
            })),
          }
        : item,
    ),
  });
  queryClient.setQueryData(['frontier', 'opportunities'], withTokenCapital(false));
  await waitFor(() =>
    expect(capital).toHaveTextContent(
      'Currency identity is missing or mixed; comparison unavailable.',
    ),
  );
  expect(
    within(capital).getByRole('textbox', {
      name: 'Virtual balance allocated to Kalshi unknown currency',
    }),
  ).toBeDisabled();

  queryClient.setQueryData(['frontier', 'opportunities'], withTokenCapital(true));
  const tokenBalance = await within(capital).findByRole('textbox', {
    name: `Virtual balance allocated to Kalshi USD (${tokenIdentityLabel})`,
  });
  expect(tokenBalance).toHaveValue('');
  expect(tokenBalance).toBeEnabled();
  expect(capital).toHaveTextContent('Enter an isolated virtual balance.');

  const boundaryIdentity = {
    schema_version: 1,
    kind: 'token',
    code: 'USD',
    network_id: 'net:alpha',
    asset_reference: 'asset:beta',
  } as const;
  const collidingDelimiterIdentity = {
    schema_version: 1,
    kind: 'token',
    code: 'USD',
    network_id: 'net:alpha:asset',
    asset_reference: 'beta',
  } as const;
  const percentIdentity = {
    ...boundaryIdentity,
    network_id: 'net%alpha',
    asset_reference: 'asset%beta',
  } as const;
  const withIdentities = (capitalIdentity: object, legIdentity: object) => ({
    ...recordedCandidates!,
    items: recordedCandidates!.items.map((item) =>
      item.candidate_id === 'multi-outcome-fixture-candidate'
        ? {
            ...item,
            capital_currency_identity: capitalIdentity,
            legs: item.legs.map((leg) => ({
              ...leg,
              quote_currency_identity: legIdentity,
            })),
          }
        : item,
    ),
  });
  queryClient.setQueryData(
    ['frontier', 'opportunities'],
    withIdentities(percentIdentity, percentIdentity),
  );
  const percentBalance = await within(capital).findByRole('textbox', {
    name: 'Virtual balance allocated to Kalshi USD (token:USD:net%25alpha:asset%25beta)',
  });
  expect(percentBalance).toBeEnabled();

  queryClient.setQueryData(
    ['frontier', 'opportunities'],
    withIdentities(boundaryIdentity, boundaryIdentity),
  );
  const boundaryBalance = await within(capital).findByRole('textbox', {
    name: 'Virtual balance allocated to Kalshi USD (token:USD:net%3Aalpha:asset%3Abeta)',
  });
  expect(boundaryBalance).toBeEnabled();
  fireEvent.change(boundaryBalance, { target: { value: '7' } });
  queryClient.setQueryData(
    ['frontier', 'opportunities'],
    withIdentities(collidingDelimiterIdentity, collidingDelimiterIdentity),
  );
  const distinctBoundaryBalance = await within(capital).findByRole('textbox', {
    name: 'Virtual balance allocated to Kalshi USD (token:USD:net%3Aalpha%3Aasset:beta)',
  });
  expect(distinctBoundaryBalance).toHaveValue('');
  queryClient.setQueryData(
    ['frontier', 'opportunities'],
    withIdentities(boundaryIdentity, collidingDelimiterIdentity),
  );
  await waitFor(() =>
    expect(capital).toHaveTextContent(
      'Currency identity is missing or mixed; comparison unavailable.',
    ),
  );
  expect(
    within(capital).getByRole('textbox', {
      name: 'Virtual balance allocated to Kalshi unknown currency',
    }),
  ).toBeDisabled();

  const unsupportedIdentity = { ...boundaryIdentity, schema_version: 2 } as const;
  queryClient.setQueryData(
    ['frontier', 'opportunities'],
    withIdentities(unsupportedIdentity, unsupportedIdentity),
  );
  await waitFor(() =>
    expect(capital).toHaveTextContent(
      'Currency identity is missing or mixed; comparison unavailable.',
    ),
  );
  expect(
    within(capital).getByRole('textbox', {
      name: 'Virtual balance allocated to Kalshi unknown currency',
    }),
  ).toBeDisabled();

  const invalidAssetReferences = ['asset:non-ascii-é'];
  for (const assetReference of invalidAssetReferences) {
    const invalidIdentity = { ...boundaryIdentity, asset_reference: assetReference } as const;
    queryClient.setQueryData(
      ['frontier', 'opportunities'],
      withIdentities(invalidIdentity, invalidIdentity),
    );
    await waitFor(() =>
      expect(capital).toHaveTextContent(
        'Currency identity is missing or mixed; comparison unavailable.',
      ),
    );
    expect(
      within(capital).getByRole('textbox', {
        name: 'Virtual balance allocated to Kalshi unknown currency',
      }),
    ).toBeDisabled();
  }

  responses['/api/frontier/opportunities/capital-carry'] = {
    schema_version: 2,
    model_version: 'frontier-virtual-capital-carry-2',
    run_id: 'a'.repeat(64),
    run_sha256: 'b'.repeat(64),
    candidate_id: 'multi-outcome-fixture-candidate',
    candidate_classification: 'VERIFIED MATHEMATICAL INCONSISTENCY',
    classification_unchanged: true,
    hypothetical_only: true,
    capital_currency_identity: tokenUsdIdentity,
    total_carry_cost: '0.02465753424657534246575342466',
    worst_case_gross_pnl_before_carry: '1',
    worst_case_gross_pnl_after_carry: '0.9753424657534246575342465753',
    worst_case_net_pnl_before_carry: '1',
    worst_case_net_pnl_after_carry: '0.9753424657534246575342465753',
    input_sha256: 'c'.repeat(64),
    result_sha256: 'd'.repeat(64),
    audit: {
      disposition: 'verified',
      message: 'Independent arithmetic matches the pinned fixture.',
      recomputed_total_carry_cost: '0.02465753424657534246575342466',
      checks: ['Pinned settlement evidence checked.'],
    },
    venues: [
      {
        venue: 'kalshi',
        capital: '9',
        annual_rate_bps: '1000',
        post_settlement_delay_seconds: 3600,
        start_at_utc: '2026-10-26T20:00:00Z',
        capital_released_at_utc: '2026-10-27T20:00:00Z',
        duration_seconds: '86400',
        carry_cost: '0.02465753424657534246575342466',
        settlement_evidence: [
          {
            market_id: 'kalshi:KX-THREEWAY',
            observation_id: 'e'.repeat(64),
            observation_row_sha256: '1'.repeat(64),
            raw_sha256: 'f'.repeat(64),
            resolution_evidence_sha256: '2'.repeat(64),
            resolution_fingerprint: 'three-way-fixture',
            settles_at_utc: '2026-10-27T19:00:00Z',
          },
        ],
      },
    ],
    assumptions: ['Fixture response.'],
    limitations: ['No execution modeled.'],
  };
  queryClient.setQueryData(['frontier', 'opportunities'], {
    ...withTokenCapital(true),
    items: withTokenCapital(true).items.map((item) =>
      item.candidate_id === 'multi-outcome-fixture-candidate'
        ? {
            ...item,
            source_run_id: 'a'.repeat(64),
            source_run_sha256: 'b'.repeat(64),
            modeled_fees: null,
            modeled_net_cost: null,
            legs: item.legs.map((leg) => ({ ...leg, modeled_fee: null })),
          }
        : item,
    ),
  });
  const carryRate = await within(capital).findByRole('textbox', {
    name: 'Kalshi annual carry rate in basis points',
  });
  fireEvent.change(carryRate, { target: { value: '1000' } });
  const carryReleaseDelay = within(capital).getByRole('textbox', {
    name: 'Kalshi post-settlement release delay in seconds',
  });
  fireEvent.change(carryReleaseDelay, { target: { value: '3600' } });
  fireEvent.click(within(capital).getByRole('button', { name: 'Evaluate settlement carry' }));
  expect(
    await within(capital).findByText('Independent arithmetic matches the pinned fixture.'),
  ).toBeInTheDocument();
  expect(capital).toHaveTextContent('Classification');
  expect(capital).toHaveTextContent('unchanged');
  expect(capital).toHaveTextContent('3600s additional delay after settlement');
  const carryCall = fetchMock.mock.calls.find(
    ([input]) => String(input) === '/api/frontier/opportunities/capital-carry',
  );
  expect(carryCall?.[1]?.method).toBe('POST');
  expect(JSON.parse(String(carryCall?.[1]?.body))).toEqual({
    run_id: 'a'.repeat(64),
    run_sha256: 'b'.repeat(64),
    candidate_id: 'multi-outcome-fixture-candidate',
    annual_rate_bps_by_venue: { kalshi: '1000' },
    post_settlement_delay_seconds_by_venue: { kalshi: '3600' },
  });
  const eurIdentity = {
    schema_version: 1,
    kind: 'fiat',
    code: 'EUR',
    network_id: null,
    asset_reference: null,
  } as const;
  responses['/api/frontier/opportunities/funding-currency-sensitivity'] = {
    schema_version: 2,
    model_version: 'frontier-virtual-funding-currency-2',
    run_id: 'a'.repeat(64),
    run_sha256: 'b'.repeat(64),
    candidate_id: 'multi-outcome-fixture-candidate',
    candidate_evidence_sha256: 'c'.repeat(64),
    candidate_classification: 'VERIFIED MATHEMATICAL INCONSISTENCY',
    candidate_practical_eligibility: false,
    classification_unchanged: true,
    practical_eligibility_unchanged: true,
    candidate_economics_unchanged: true,
    hypothetical_only: true,
    target_currency_identity: tokenUsdIdentity,
    unresolved_candidate_fee_leg_count: 3,
    total_conversion_fee_target: '0.02255639097744360902255639098',
    pnl_scenario: {
      status: 'unavailable',
      reason: 'The saved candidate has no verified independent economic audit.',
      funding_input_sha256: 'e'.repeat(64),
      target_currency_identity: tokenUsdIdentity,
      modeled_conversion_fee_target: '0.02255639097744360902255639098',
      candidate_net_pnl_by_state: {},
      net_pnl_after_conversion_by_state: {},
      worst_case_net_pnl_after_conversion: null,
      all_outcomes_positive_after_conversion: null,
      audit: {
        algorithm_version: 'frontier-independent-funding-pnl-audit-1',
        disposition: 'unavailable',
        input_sha256: 'e'.repeat(64),
        candidate_audit_input_sha256: null,
        recomputed_net_pnl_after_conversion_by_state: {},
        recomputed_worst_case_net_pnl_after_conversion: null,
        checks: [],
        message: 'The saved candidate has no verified independent economic audit.',
      },
    },
    input_sha256: 'e'.repeat(64),
    result_sha256: 'f'.repeat(64),
    audit: {
      disposition: 'verified',
      message: 'Independent rational arithmetic matches every explicit funding assumption.',
      checks: ['Full identities and venue isolation checked.'],
    },
    venues: [
      {
        venue: 'kalshi',
        required_capital_target: '9',
        funding_currency_identity: eurIdentity,
        balance_amount: '10',
        target_units_per_funding_unit: '1.1',
        conversion_fee_bps: '25',
        required_funding_amount: '8.20200501253132832',
        available_capital_target_after_fee: '10.9725',
        conversion_fee_target_amount: '0.02255639097744360902255639098',
        shortfall_target: '0',
        shortfall_funding: '0',
        model_requirement_covered: true,
      },
    ],
    assumptions: ['Rates and balances are user assumptions.'],
    limitations: ['No conversion is performed.'],
  };
  const fxPanel = screen.getByRole('region', { name: 'Venue-separated virtual funding' });
  fireEvent.change(within(fxPanel).getByLabelText('Kalshi funding asset kind'), {
    target: { value: 'fiat' },
  });
  fireEvent.change(within(fxPanel).getByLabelText('Kalshi funding asset code'), {
    target: { value: 'EUR' },
  });
  expect(within(fxPanel).getByLabelText('Kalshi target units per funding unit')).toHaveValue('');
  expect(within(fxPanel).getByLabelText('Kalshi conversion fee in basis points')).toHaveValue('');
  fireEvent.change(within(fxPanel).getByLabelText('Kalshi funding currency virtual balance'), {
    target: { value: '10' },
  });
  fireEvent.change(within(fxPanel).getByLabelText('Kalshi target units per funding unit'), {
    target: { value: '1.1' },
  });
  fireEvent.change(within(fxPanel).getByLabelText('Kalshi conversion fee in basis points'), {
    target: { value: '25' },
  });
  fireEvent.change(within(fxPanel).getByLabelText('Kalshi funding currency virtual balance'), {
    target: { value: '1e-1' },
  });
  expect(
    within(fxPanel).getByRole('button', { name: 'Evaluate virtual funding sensitivity' }),
  ).toBeDisabled();
  fireEvent.change(within(fxPanel).getByLabelText('Kalshi funding currency virtual balance'), {
    target: { value: '10' },
  });
  fireEvent.click(
    within(fxPanel).getByRole('button', { name: 'Evaluate virtual funding sensitivity' }),
  );
  expect(
    await within(fxPanel).findByText(
      'Independent rational arithmetic matches every explicit funding assumption.',
    ),
  ).toBeInTheDocument();
  expect(fxPanel).toHaveTextContent(
    /candidate state VERIFIED MATHEMATICAL INCONSISTENCY · classification unchanged · practical eligibility not established \(unchanged\) · candidate economics unchanged/,
  );
  expect(fxPanel).toHaveTextContent('unresolved fees remain');
  expect(
    within(fxPanel).getByRole('region', { name: 'Conversion-adjusted outcome P&L scenario' }),
  ).toHaveTextContent('Outcome P&L is unavailable');
  const priorFundingResponse = responses[
    '/api/frontier/opportunities/funding-currency-sensitivity'
  ] as Record<string, unknown>;
  const adjustedStates = {
    blue: '-0.12255639097744360902255639098',
    red: '0.17744360902255639097744360902',
  };
  responses['/api/frontier/opportunities/funding-currency-sensitivity'] = {
    ...priorFundingResponse,
    unresolved_candidate_fee_leg_count: 0,
    pnl_scenario: {
      status: 'verified',
      reason: null,
      funding_input_sha256: 'e'.repeat(64),
      target_currency_identity: tokenUsdIdentity,
      modeled_conversion_fee_target: '0.02255639097744360902255639098',
      candidate_net_pnl_by_state: { blue: '-0.1', red: '0.2' },
      net_pnl_after_conversion_by_state: adjustedStates,
      worst_case_net_pnl_after_conversion: adjustedStates.blue,
      all_outcomes_positive_after_conversion: false,
      audit: {
        algorithm_version: 'frontier-independent-funding-pnl-audit-1',
        disposition: 'verified',
        input_sha256: 'e'.repeat(64),
        candidate_audit_input_sha256: '9'.repeat(64),
        recomputed_net_pnl_after_conversion_by_state: adjustedStates,
        recomputed_worst_case_net_pnl_after_conversion: adjustedStates.blue,
        checks: ['The fixture state values match their independent audit.'],
        message: 'Independent fixture audit verifies the adjusted terminal-state P&L.',
      },
    },
  };
  fireEvent.click(
    within(fxPanel).getByRole('button', { name: 'Evaluate virtual funding sensitivity' }),
  );
  const conversionPnlPanel = within(fxPanel).getByRole('region', {
    name: 'Conversion-adjusted outcome P&L scenario',
  });
  expect(
    await within(conversionPnlPanel).findByText(
      'Independent fixture audit verifies the adjusted terminal-state P&L.',
    ),
  ).toBeInTheDocument();
  expect(conversionPnlPanel).toHaveTextContent('blue');
  expect(conversionPnlPanel).toHaveTextContent('0.17744360902255639097744360902');
  expect(conversionPnlPanel).toHaveTextContent('all outcomes positive under these assumptions: no');
  const fundingCall = fetchMock.mock.calls.find(
    ([input]) => String(input) === '/api/frontier/opportunities/funding-currency-sensitivity',
  );
  expect(fundingCall?.[1]?.method).toBe('POST');
  expect(JSON.parse(String(fundingCall?.[1]?.body))).toEqual({
    run_id: 'a'.repeat(64),
    run_sha256: 'b'.repeat(64),
    candidate_id: 'multi-outcome-fixture-candidate',
    venues: [
      {
        venue: 'kalshi',
        funding_currency_identity: eurIdentity,
        balance_amount: '10',
        target_units_per_funding_unit: '1.1',
        conversion_fee_bps: '25',
      },
    ],
  });
  expect(screen.getAllByText('red')).toHaveLength(3);

  const jointMapping = {
    mapping_id: 'f'.repeat(64),
    market_ids: ['polymarket:event-a', 'polymarket:event-b'],
    joint_state_ids: ['world-no', 'world-yes'],
    state_by_market: {
      'polymarket:event-a': { 'world-no': 'no', 'world-yes': 'yes' },
      'polymarket:event-b': { 'world-no': 'no', 'world-yes': 'yes' },
    },
    external_assertion_id: 'fixture-equivalence-assertion',
    evidence_observation_ids: ['a'.repeat(64), 'b'.repeat(64)],
    asserted_at_utc: '2026-10-26T20:00:00.050Z',
    semantic_status: 'externally_asserted_unverified',
  } as const;
  queryClient.setQueryData(['frontier', 'runs'], {
    items: [
      {
        run_id: 'joint-state-ui-run',
        created_at_utc: '2026-10-26T20:00:00Z',
        result_sha256: 'e'.repeat(64),
        result: {
          manifest: { joint_state_mappings: [jointMapping] },
          candidates: [],
          classification_counts: {},
        },
      },
    ],
  });
  const candidateBeforeJointFixture = queryClient.getQueryData<{
    items: Array<Record<string, unknown> & { candidate_id: string }>;
  }>(['frontier', 'opportunities']);
  expect(candidateBeforeJointFixture).toBeDefined();
  queryClient.setQueryData(['frontier', 'opportunities'], {
    ...candidateBeforeJointFixture!,
    items: [
      ...candidateBeforeJointFixture!.items,
      {
        ...candidateBeforeJointFixture!.items[0],
        candidate_id: 'joint-state-ui-candidate',
        source_run_id: 'joint-state-ui-run',
        source_run_sha256: 'e'.repeat(64),
        family: 'multi_market_joint_state_basket',
        classification: 'CONDITIONAL ECONOMIC OPPORTUNITY',
        market_ids: jointMapping.market_ids,
        joint_state_mapping_id: jointMapping.mapping_id,
        outcome_payout_by_state: { 'world-no': '10', 'world-yes': '10' },
        gross_pnl_by_state: { 'world-no': '1', 'world-yes': '1' },
        net_pnl_by_state: { 'world-no': '1', 'world-yes': '1' },
      },
    ],
  });
  const jointStateRegion = await screen.findByRole('region', {
    name: 'External joint-state assertion',
  });
  expect(jointStateRegion).toHaveTextContent(
    /completeness and semantic equivalence are unverified/,
  );
  expect(jointStateRegion).toHaveTextContent('fixture-equivalence-assertion');
  expect(jointStateRegion).toHaveTextContent('polymarket:event-a');
  expect(
    await screen.findByRole('heading', { name: 'Payoffs over asserted joint states' }),
  ).toBeInTheDocument();
  fireEvent.click(screen.getByText(/Inspect the asserted projections/));
  expect(
    within(jointStateRegion).getByRole('columnheader', { name: 'polymarket:event-a' }),
  ).toBeInTheDocument();

  queryClient.setQueryData(['frontier', 'runs'], {
    items: [
      {
        run_id: 'saved-fee-evidence-replay',
        created_at_utc: '2026-10-27T17:00:00Z',
        result_sha256: 'd'.repeat(64),
        result: {
          manifest: {
            replay_version: 'frontier-deterministic-replay-8',
            code_version: 'frontier-test',
            normalized_input_sha256: 'e'.repeat(64),
            market_observation_ids: ['f'.repeat(64)],
            fee_metadata_observation_ids: ['1'.repeat(64), '2'.repeat(64)],
            book_observation_ids: [],
            relationship_ids: [],
            as_of_utc: '2026-10-27T17:00:00Z',
            scenario: {},
          },
          candidates: [],
          classification_counts: {},
        },
      },
    ],
    returned: 1,
    limit: 30,
    offset: 0,
  });
  const jointMarketFixture = (suffix: string, observation: string) => ({
    canonical_id: `polymarket:joint-${suffix}`,
    source_observation_record_id: observation.repeat(64),
    venue: 'polymarket',
    title: `Fixture event ${suffix.toUpperCase()}`,
    market_kind: 'binary_event',
    lifecycle: 'open',
    instruments: [],
    payoff: {
      state_ids: ['yes', 'no'],
      verified: true,
      exhaustive: true,
    },
    resolution: { verified: true },
    provenance: { response_received_at_utc: '2026-10-27T17:00:00Z' },
  });
  queryClient.setQueryData(['frontier', 'markets'], {
    items: [jointMarketFixture('a', 'a'), jointMarketFixture('b', 'b')],
    returned: 2,
    limit: 100,
    offset: 0,
  });
  fireEvent.click(screen.getByRole('button', { name: 'Replay & readiness' }));
  expect(await screen.findByText('2 fee metadata observations')).toBeInTheDocument();
  const marketSelector = await screen.findByRole('listbox', {
    name: 'Stored event markets for joint-state replay',
  });
  for (const option of Array.from((marketSelector as HTMLSelectElement).options)) {
    option.selected = ['polymarket:joint-a', 'polymarket:joint-b'].includes(option.value);
  }
  fireEvent.change(marketSelector);
  fireEvent.change(screen.getByLabelText('External assertion reference'), {
    target: { value: 'fixture-state-assertion' },
  });
  fireEvent.change(screen.getByLabelText('Joint-state IDs'), {
    target: { value: 'world-no\nworld-yes' },
  });
  fireEvent.change(screen.getByLabelText('world-no local payoff state for Fixture event A'), {
    target: { value: 'no' },
  });
  fireEvent.change(screen.getByLabelText('world-yes local payoff state for Fixture event A'), {
    target: { value: 'yes' },
  });
  fireEvent.change(screen.getByLabelText('world-no local payoff state for Fixture event B'), {
    target: { value: 'no' },
  });
  fireEvent.change(screen.getByLabelText('world-yes local payoff state for Fixture event B'), {
    target: { value: 'yes' },
  });
  const jointReplayButton = screen.getByRole('button', { name: 'Replay conditional basket' });
  expect(jointReplayButton).toBeEnabled();
  fireEvent.click(jointReplayButton);
  await waitFor(() => expect(jointReplayRequests).toHaveLength(1));
  expect(await screen.findByText('Conditional replay saved')).toBeInTheDocument();
  const submittedJointMapping = jointReplayRequests[0]!.mapping;
  expect(submittedJointMapping).not.toHaveProperty('mapping_id');
  expect(submittedJointMapping).toMatchObject({
    external_assertion_id: 'fixture-state-assertion',
    market_ids: ['polymarket:joint-a', 'polymarket:joint-b'],
    joint_state_ids: ['world-no', 'world-yes'],
    evidence_observation_ids: ['a'.repeat(64), 'b'.repeat(64)],
    state_by_market: {
      'polymarket:joint-a': { 'world-no': 'no', 'world-yes': 'yes' },
      'polymarket:joint-b': { 'world-no': 'no', 'world-yes': 'yes' },
    },
  });
});

it('captures one explicit Polymarket trade page and follows its bound cursor', async () => {
  const conditionId = `0x${'a'.repeat(64)}`;
  const requests: Record<string, unknown>[] = [];
  const priceHistoryRequests: Record<string, unknown>[] = [];
  const bookUpdateRequests: Record<string, unknown>[] = [];
  const priceHistoryReplayRequests: Record<string, unknown>[] = [];
  let savedPriceHistory: Record<string, unknown> | null = null;
  const market = {
    canonical_id: 'polymarket:trade-condition',
    source_observation_record_id: 'market-observation',
    native_market_id: conditionId,
    native_event_id: null,
    native_event_title: null,
    outcome_label: null,
    native_fields: { conditionId },
    venue: 'polymarket',
    title: 'Recorded condition for page capture',
    market_kind: 'conditional_event',
    lifecycle: 'settled',
    description: '',
    base_asset: null,
    quote_asset: 'USDC',
    settlement_asset: 'USDC',
    settlement_asset_identity: null,
    payoff: {
      state_ids: ['yes', 'no'],
      payout_currency: 'USDC',
      exhaustive: false,
      verified: false,
      verification_basis: 'fixture only',
    },
    resolution: {
      primary_rule: null,
      secondary_rule: null,
      authority: null,
      closes_at_utc: null,
      settles_at_utc: null,
      evidence_sha256: null,
      resolution_fingerprint: null,
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
      note: 'Fixture fee is unknown.',
    },
    instruments: [
      { native_instrument_id: '123456789', label: 'Yes', outcome_id: 'yes' },
      { native_instrument_id: '987654321', label: 'No', outcome_id: 'no' },
    ],
    selected_components: [],
    quality_flags: [],
    provenance: {
      response_received_at_utc: '2026-10-26T20:00:00Z',
      raw_sha256: 'a'.repeat(64),
      observation_id: 'market-observation',
    },
  };
  const kalshiMarket = {
    ...market,
    canonical_id: 'kalshi:KX-FRONTIER-1',
    native_market_id: 'KX-FRONTIER-1',
    native_fields: {},
    venue: 'kalshi',
    title: 'Recorded Kalshi ticker for page capture',
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
            {
              capability: 'price_history',
              supported: true,
              state: 'implemented',
              reason: 'bounded source-reported price samples',
            },
            {
              capability: 'book_updates',
              supported: true,
              state: 'implemented',
              reason: 'finite public stream capture without sequence claims',
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
        {
          venue: 'kalshi',
          adapter_version: 'frontier-kalshi-4',
          public_probe_enabled: true,
          capabilities: [
            {
              capability: 'paginated_public_trades',
              supported: true,
              state: 'implemented',
              reason: 'one bounded public page',
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
    '/api/frontier/markets?limit=100': {
      items: [market, kalshiMarket],
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
    '/api/frontier/comparisons?limit=30': { items: [], returned: 0, limit: 30, offset: 0 },
    '/api/frontier/readiness': { gates: [] },
  };
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    if (path.startsWith('/api/frontier/price-history?')) {
      return {
        ok: true,
        json: async () => ({
          items: savedPriceHistory ? [savedPriceHistory] : [],
          venue: 'polymarket',
          native_instrument_id: '123456789',
          returned: savedPriceHistory ? 1 : 0,
        }),
      } as Response;
    }
    if (path === '/api/frontier/probe/polymarket/price-history' && init?.method === 'POST') {
      const body = JSON.parse(String(init.body)) as Record<string, unknown>;
      priceHistoryRequests.push(body);
      const series = {
        venue: 'polymarket',
        native_instrument_id: body.native_instrument_id,
        interval: body.interval,
        fidelity_minutes: body.fidelity_minutes,
        requested_start_ts: body.start_ts,
        requested_end_ts: body.end_ts,
        bound_market_observation_id: 'market-observation',
        points: [{ timestamp_utc: '2026-10-27T00:00:00Z', price: '0.42' }],
        source_price_semantics: 'source_reported_price_sample',
        source_limit_note: 'Fixture source price point. OHLC and volume are not inferred.',
        provenance: { observation_id: 'history-provenance', raw_sha256: 'b'.repeat(64) },
      };
      savedPriceHistory = {
        series,
        observation_id: 'history-observation',
        raw_sha256: 'b'.repeat(64),
        received_at_utc: '2026-10-27T00:01:00Z',
      };
      return {
        ok: true,
        json: async () => ({
          venue: 'polymarket',
          native_instrument_id: '123456789',
          bound_market_id: market.canonical_id,
          bound_market_observation_id: 'market-observation',
          series,
          point_count: 1,
          observation_id: 'history-observation',
          raw_sha256: 'b'.repeat(64),
          source_state: 'healthy',
          request_count_delta: 1,
          network_calls_bounded_by: 1,
          hypothetical_only: true,
          note: 'Source-reported sample fixture only.',
        }),
      } as Response;
    }
    if (path === '/api/frontier/probe/polymarket/book-updates' && init?.method === 'POST') {
      const body = JSON.parse(String(init.body)) as Record<string, unknown>;
      bookUpdateRequests.push(body);
      return {
        ok: true,
        json: async () => ({
          venue: 'polymarket',
          market_id: market.canonical_id,
          native_market_id: conditionId,
          bound_market_observation_id: 'market-observation',
          capture_status: 'captured',
          frame_count: 1,
          normalized_update_count: 1,
          capture_bounds: {
            max_frames: 8,
            max_updates: 50,
            max_duration_seconds: 3,
            stream_connections: 1,
          },
          frames: [
            {
              observation_id: 'stream-observation',
              raw_sha256: 'f'.repeat(64),
              received_at_utc: '2026-10-27T00:01:00Z',
              source_url: 'wss://ws-subscriptions-clob.polymarket.com/ws/market',
              source_schema_version: 'polymarket-market-stream-v1',
              adapter_version: 'frontier-polymarket-2',
              updates: [
                {
                  native_market_id: conditionId,
                  native_instrument_id: '123456789',
                  event_type: 'book',
                  source_timestamp_utc: '2026-10-27T00:00:00Z',
                  bid_level_count: 1,
                  ask_level_count: 1,
                  price_change_count: 0,
                  reported_best_bid: null,
                  reported_best_ask: null,
                  continuity: 'unverified_no_sequence_or_gap_detection',
                  quality_flags: ['NO_SEQUENCE_FIELD', 'DELTAS_NOT_APPLIED_TO_LOCAL_BOOK'],
                },
              ],
            },
          ],
          source_state: 'available',
          hypothetical_only: true,
          note: 'Public events are not sequenced book snapshots.',
        }),
      } as Response;
    }
    if (path === '/api/frontier/price-history/replay' && init?.method === 'POST') {
      priceHistoryReplayRequests.push(JSON.parse(String(init.body)) as Record<string, unknown>);
      return {
        ok: true,
        json: async () => ({
          run_id: 'c'.repeat(64),
          result_sha256: 'e'.repeat(64),
          manifest: {
            input_sha256: 'd'.repeat(64),
            observation_ids: ['history-observation'],
            replay_version: 'frontier-price-history-replay-1',
            as_of_utc: '2026-10-27T00:01:00Z',
          },
          series: [
            {
              observation_id: 'history-observation',
              point_count: 1,
              first_point_ts: 1793059200,
              last_point_ts: 1793059200,
              observed_point_span_seconds: 0,
              largest_adjacent_sample_gap_seconds: null,
              minimum_sampled_price: '0.42',
              maximum_sampled_price: '0.42',
            },
          ],
          candidate_generation: 'not_performed',
        }),
      } as Response;
    }
    if (
      (path === '/api/frontier/probe/polymarket/trades' ||
        path === '/api/frontier/probe/kalshi/trades') &&
      init?.method === 'POST'
    ) {
      const body = JSON.parse(String(init.body)) as Record<string, unknown>;
      requests.push(body);
      const isPolymarket = path.includes('polymarket');
      const hasMore =
        isPolymarket && requests.filter((item) => 'condition_id' in item).length === 1;
      const result = {
        venue: isPolymarket ? 'polymarket' : 'kalshi',
        ...(isPolymarket
          ? { condition_id: conditionId, market_id: conditionId }
          : { market_id: 'KX-FRONTIER-1' }),
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
  const tradeMarketPicker = await screen.findByRole('combobox', {
    name: 'Recorded trade market',
  });
  const inspectButtons = await screen.findAllByRole('button', { name: 'Inspect' });
  fireEvent.click(inspectButtons[0]!);
  expect(
    await screen.findByRole('heading', { name: 'Historical price points' }),
  ).toBeInTheDocument();
  expect(bookUpdateRequests).toHaveLength(0);
  fireEvent.click(screen.getByRole('button', { name: 'Capture 3-second market stream' }));
  expect(
    await screen.findByText(/Captured 1 stream frame with 1 normalized event/),
  ).toBeInTheDocument();
  expect(screen.getByText(/NO_SEQUENCE_FIELD/)).toBeInTheDocument();
  expect(screen.getByText('Inspect immutable source response')).toBeInTheDocument();
  expect(bookUpdateRequests).toEqual([{ market_id: market.canonical_id }]);
  fireEvent.click(screen.getByRole('button', { name: 'Capture one series' }));
  expect(await screen.findByText('0.42')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Replay saved series' }));
  expect(await screen.findByText('Deterministic source-sample replay')).toBeInTheDocument();
  expect(screen.getByText(/Candidate generation was not performed/)).toBeInTheDocument();
  expect(priceHistoryReplayRequests).toEqual([{ observation_ids: ['history-observation'] }]);
  expect(priceHistoryRequests).toHaveLength(1);
  expect(priceHistoryRequests[0]).toMatchObject({
    native_instrument_id: '123456789',
    interval: '1d',
    fidelity_minutes: 60,
  });
  fireEvent.change(tradeMarketPicker, { target: { value: conditionId } });
  fireEvent.click(screen.getByRole('button', { name: 'Capture first page' }));
  expect(await screen.findByText(/Saved 2 trades/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Capture next page' }));
  await screen.findByText(/source reports no next page/);
  expect(requests).toEqual([
    { condition_id: conditionId, limit: 50 },
    { condition_id: conditionId, limit: 50, cursor: 'frontier-next-page' },
  ]);
  fireEvent.change(screen.getByRole('combobox', { name: 'Trade research source' }), {
    target: { value: 'kalshi' },
  });
  fireEvent.change(screen.getByRole('combobox', { name: 'Recorded trade market' }), {
    target: { value: 'KX-FRONTIER-1' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Capture first page' }));
  await screen.findByText(/Saved 2 trades/);
  await waitFor(() => expect(requests).toHaveLength(3));
  expect(requests[2]).toEqual({ market_id: 'KX-FRONTIER-1', limit: 50 });
});

it('replays multiple saved price-history series and inspects persisted source lineage', async () => {
  const firstObservationId = 'a'.repeat(64);
  const secondObservationId = 'b'.repeat(64);
  const firstRawHash = 'c'.repeat(64);
  const secondRawHash = 'd'.repeat(64);
  const oldRunId = 'e'.repeat(64);
  const newRunId = 'f'.repeat(64);
  const makeSeriesReplay = (
    observationId: string,
    rawSha256: string,
    nativeInstrumentId: string,
  ) => ({
    observation_id: observationId,
    raw_sha256: rawSha256,
    venue: 'polymarket' as const,
    native_instrument_id: nativeInstrumentId,
    interval: '1d' as const,
    fidelity_minutes: 60,
    requested_start_ts: 1792972800,
    requested_end_ts: 1793577600,
    bound_market_observation_id: '9'.repeat(64),
    point_count: 2,
    first_point_ts: 1793059200,
    last_point_ts: 1793145600,
    observed_point_span_seconds: 86400,
    largest_adjacent_sample_gap_seconds: 86400,
    minimum_sampled_price: '0.41',
    maximum_sampled_price: '0.46',
    future_point_timestamp_count: 0,
  });
  const makeReplay = (
    runId: string,
    observationIds: string[],
    series: ReturnType<typeof makeSeriesReplay>[],
  ) => ({
    schema_version: 1,
    run_id: runId,
    result_sha256: '8'.repeat(64),
    manifest: {
      schema_version: 1,
      input_sha256: '7'.repeat(64),
      observation_ids: observationIds,
      replay_version: 'frontier-price-history-replay-1',
      code_version: 'frontier-test',
      as_of_utc: '2026-10-27T00:01:00Z',
      interpretation: 'descriptive_source_sample_replay' as const,
    },
    series,
    candidate_generation: 'not_performed' as const,
  });
  const firstCapture = {
    series: {
      venue: 'polymarket',
      native_instrument_id: 'token-asset-1',
      interval: '1d',
      fidelity_minutes: 60,
      requested_start_ts: 1792972800,
      requested_end_ts: 1793577600,
      bound_market_observation_id: '9'.repeat(64),
      points: [
        { timestamp_utc: '2026-10-27T00:00:00Z', price: '0.41' },
        { timestamp_utc: '2026-10-28T00:00:00Z', price: '0.46' },
      ],
      source_price_semantics: 'source_reported_price_sample',
      source_limit_note: 'Historical sample fixture.',
      provenance: { observation_id: firstObservationId, raw_sha256: firstRawHash },
    },
    observation_id: firstObservationId,
    raw_sha256: firstRawHash,
    received_at_utc: '2026-10-28T00:01:00Z',
  };
  const secondCapture = {
    series: {
      ...firstCapture.series,
      native_instrument_id: 'token-asset-2',
      points: [
        { timestamp_utc: '2026-10-27T00:00:00Z', price: '0.41' },
        { timestamp_utc: '2026-10-28T00:00:00Z', price: '0.46' },
      ],
      provenance: { observation_id: secondObservationId, raw_sha256: secondRawHash },
    },
    observation_id: secondObservationId,
    raw_sha256: secondRawHash,
    received_at_utc: '2026-10-28T00:02:00Z',
  };
  const additionalCaptures = Array.from({ length: 18 }, (_, index) => {
    const observationId = `${index.toString(16).padStart(2, '0')}${'1'.repeat(62)}`;
    const rawSha256 = `${index.toString(16).padStart(2, '0')}${'2'.repeat(62)}`;
    const nativeInstrumentId = `token-asset-${index + 3}`;
    return {
      series: {
        ...secondCapture.series,
        native_instrument_id: nativeInstrumentId,
        provenance: { observation_id: observationId, raw_sha256: rawSha256 },
      },
      observation_id: observationId,
      raw_sha256: rawSha256,
      received_at_utc: '2026-10-28T00:03:00Z',
    };
  });
  const olderCapture = {
    ...secondCapture,
    series: {
      ...secondCapture.series,
      native_instrument_id: 'token-older-page',
      provenance: { observation_id: '0'.repeat(64), raw_sha256: '9'.repeat(64) },
    },
    observation_id: '0'.repeat(64),
    raw_sha256: '9'.repeat(64),
  };
  const oldReplay = makeReplay(
    oldRunId,
    [firstObservationId],
    [makeSeriesReplay(firstObservationId, firstRawHash, 'token-asset-1')],
  );
  let savedReplays = [oldReplay];
  const replayRequests: Record<string, unknown>[] = [];
  const detailReads: string[] = [];
  const baseResponses: Record<string, unknown> = {
    '/api/frontier/overview': {
      state: 'AVAILABLE',
      research_only: true,
      live_execution: false,
      summary: {
        observations: 2,
        relationships: 0,
        relationship_reviews: 0,
        runs: 0,
        comparisons: 0,
        markets_by_venue: { polymarket: 1 },
        instruments_by_venue: { polymarket: 2 },
        relationships_by_state: {},
        database_bytes: 1024,
        max_bytes: 67_108_864,
      },
      sources: [],
      latest_evidence_at_utc: '2026-10-28T00:02:00Z',
      limitations: [],
    },
    '/api/frontier/sources': { items: [] },
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
    '/api/frontier/comparisons?limit=30': { items: [], returned: 0, limit: 30, offset: 0 },
    '/api/frontier/readiness': { gates: [] },
    '/api/arena/frontier-replays?limit=20': {
      items: [],
      limit: 20,
      scanned: 0,
      scan_bound: 500,
      scan_may_be_incomplete: false,
      research_only: true,
    },
    '/api/arena/frontier-discovery-comparisons?limit=20': {
      items: [],
      limit: 20,
      scanned: 0,
      scan_bound: 500,
      scan_may_be_incomplete: false,
      research_only: true,
    },
    '/api/arena/frontier-timelines?limit=20': {
      items: [],
      limit: 20,
      scanned: 0,
      scan_bound: 500,
      scan_may_be_incomplete: false,
      research_only: true,
    },
    '/api/frontier/collection-health-events?limit=20': {
      items: [],
      returned: 0,
      limit: 20,
      network_called: false,
      research_only: true,
      source_health_scope: 'adapter_local_checkpoint',
    },
  };
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    if (path.startsWith('/api/frontier/price-history?venue=polymarket&limit=20&offset=')) {
      const offset = Number(new URLSearchParams(path.split('?')[1]).get('offset'));
      const items =
        offset === 0 ? [firstCapture, secondCapture, ...additionalCaptures] : [olderCapture];
      return {
        ok: true,
        json: async () => ({
          items,
          venue: 'polymarket',
          native_instrument_id: null,
          returned: items.length,
          limit: 20,
          offset,
          scan_bound: 20,
          has_more: offset === 0,
          scan_may_be_incomplete: false,
          source_state: 'recorded observations only',
        }),
      } as Response;
    }
    if (path === '/api/frontier/price-history/replays?limit=20&offset=0') {
      return {
        ok: true,
        json: async () => ({
          items: savedReplays,
          returned: savedReplays.length,
          limit: 20,
          offset: 0,
          held_replays_omitted: 0,
          has_more: false,
          scan_may_be_incomplete: false,
          source_state: 'saved deterministic local replay results only',
          network_called: false,
        }),
      } as Response;
    }
    if (path.startsWith('/api/frontier/price-history/replays/')) {
      const runId = path.split('/').at(-1)!;
      detailReads.push(runId);
      const found = savedReplays.find((run) => run.run_id === runId);
      if (!found) throw new Error(`Unknown replay detail ${runId}`);
      return { ok: true, json: async () => found } as Response;
    }
    if (path === '/api/frontier/price-history/replay' && init?.method === 'POST') {
      const request = JSON.parse(String(init.body)) as Record<string, unknown>;
      replayRequests.push(request);
      const result = makeReplay(
        newRunId,
        [firstObservationId, secondObservationId],
        [
          makeSeriesReplay(firstObservationId, firstRawHash, 'token-asset-1'),
          makeSeriesReplay(secondObservationId, secondRawHash, 'token-asset-2'),
        ],
      );
      savedReplays = [result, ...savedReplays];
      return { ok: true, json: async () => result } as Response;
    }
    const response = baseResponses[path];
    if (response === undefined) throw new Error(`Unexpected frontend request: ${path}`);
    return { ok: true, json: async () => response } as Response;
  });
  vi.stubGlobal('fetch', fetchMock);
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <Frontier />
    </QueryClientProvider>,
  );

  fireEvent.click(await screen.findByRole('button', { name: 'Replay & readiness' }));
  expect(
    await screen.findByRole('heading', { name: 'Multi-series descriptive replay' }),
  ).toBeInTheDocument();
  expect(await screen.findByRole('heading', { name: 'Replay lineage' })).toBeInTheDocument();
  expect(await screen.findByText(firstRawHash)).toBeInTheDocument();
  expect(detailReads).toContain(oldRunId);
  expect(replayRequests).toHaveLength(0);
  expect(fetchMock.mock.calls.every(([, init]) => init?.method !== 'POST')).toBe(true);

  for (let index = 1; index <= 8; index += 1) {
    fireEvent.click(
      screen.getByRole('checkbox', { name: new RegExp(`token-asset-${index} · 1d`) }),
    );
  }
  expect(screen.getByRole('checkbox', { name: /token-asset-9 · 1d/ })).toBeDisabled();
  for (let index = 3; index <= 8; index += 1) {
    fireEvent.click(
      screen.getByRole('checkbox', { name: new RegExp(`token-asset-${index} · 1d`) }),
    );
  }
  expect(screen.getByRole('checkbox', { name: /token-asset-9 · 1d/ })).toBeEnabled();
  fireEvent.click(screen.getByRole('button', { name: 'Replay 2 selected series' }));

  await waitFor(() => expect(replayRequests).toHaveLength(1));
  expect(replayRequests[0]).toEqual({
    observation_ids: [firstObservationId, secondObservationId],
  });
  expect(await screen.findByText(newRunId)).toBeInTheDocument();
  expect(await screen.findByText(secondRawHash)).toBeInTheDocument();
  expect(screen.getByText('candidate generation not performed')).toBeInTheDocument();
  expect(screen.getAllByText(/do not establish missing-data rates/).length).toBeGreaterThan(0);

  const sourcePages = screen.getByLabelText('Saved source capture pages');
  fireEvent.click(within(sourcePages).getByRole('button', { name: 'Next' }));
  expect(await screen.findByRole('checkbox', { name: /token-older-page/ })).toBeInTheDocument();
  expect(screen.getByText('0 / 8 selected')).toBeInTheDocument();
});

it('captures Kalshi fee metadata and exposes a separate hypothetical fee sensitivity', async () => {
  const market = {
    canonical_id: 'kalshi:KX-FEE-1',
    source_observation_record_id: 'market-observation',
    native_market_id: 'KX-FEE-1',
    native_event_id: 'KX-FEE-1-EVENT',
    native_event_title: 'Example public event',
    outcome_label: 'Democratic Party',
    venue: 'kalshi',
    title: 'Recorded Kalshi fee fixture',
    market_kind: 'binary_event',
    lifecycle: 'open',
    description: '',
    base_asset: null,
    quote_asset: null,
    settlement_asset: 'USD',
    settlement_asset_identity: {
      schema_version: 1,
      kind: 'fiat',
      code: 'USD',
      network_id: null,
      asset_reference: null,
    },
    reported_settlement_value_dollars: '0.3750',
    settlement_is_provisional: false,
    payoff: {
      state_ids: ['yes', 'no'],
      payout_currency: 'USD',
      settlement_asset_identity: {
        schema_version: 1,
        kind: 'fiat',
        code: 'USD',
        network_id: null,
        asset_reference: null,
      },
      exhaustive: false,
      verified: false,
      verification_basis: 'fixture is not payoff verified',
    },
    resolution: {
      primary_rule: null,
      secondary_rule: null,
      authority: null,
      closes_at_utc: null,
      settles_at_utc: null,
      evidence_sha256: null,
      resolution_fingerprint: null,
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
      note: 'Account fee remains unknown',
    },
    native_fields: {},
    instruments: [
      {
        canonical_id: `instrument-v1:${'a'.repeat(64)}`,
        native_instrument_id: 'KX-FEE-1:YES',
        label: 'Yes',
        outcome_id: 'yes',
        price_increment_ranges: [
          { start: '0.01', end: '0.49', step: '0.01' },
          { start: '0.50', end: '0.99', step: '0.001' },
        ],
        quantity_step: '0.1',
        minimum_quantity: '0.2',
        minimum_notional: '5',
      },
      {
        native_instrument_id: 'KX-FEE-1:NO',
        label: 'No',
        outcome_id: 'no',
        tick_size: '0.01',
      },
    ],
    selected_components: [
      {
        venue: 'kalshi',
        native_event_id: 'KX-COMPONENT-EVENT',
        native_market_id: 'KX-COMPONENT-MARKET',
        selected_side: 'yes',
        yes_settlement_value_dollars: '0.3750',
      },
    ],
    quality_flags: ['FEE_SCHEDULE_UNKNOWN'],
    provenance: {
      response_received_at_utc: '2026-10-26T20:00:00Z',
      raw_sha256: 'a'.repeat(64),
      observation_id: 'market-observation',
    },
  };
  const source = {
    venue: 'kalshi',
    adapter_version: 'frontier-kalshi-12',
    public_probe_enabled: true,
    capabilities: [
      {
        capability: 'fee_metadata',
        supported: true,
        state: 'implemented',
        reason: 'Native fee metadata, not account fee costs',
      },
      {
        capability: 'event_market_groups',
        supported: true,
        state: 'implemented',
        reason: 'One bounded public event detail request',
      },
      {
        capability: 'market_metadata',
        supported: true,
        state: 'implemented',
        reason: 'One ticker-bound public market detail request',
      },
    ],
    health: {
      state: 'not_probed',
      last_success_at_utc: null,
      last_error_code: null,
      last_error: null,
      notes: [],
    },
  };
  const requestBodies: Record<string, unknown>[] = [];
  const eventGroupBodies: Record<string, unknown>[] = [];
  const marketMetadataBodies: Record<string, unknown>[] = [];
  const componentMarketBodies: Record<string, unknown>[] = [];
  const sensitivityBodies: Record<string, unknown>[] = [];
  const settlementAuditBodies: Record<string, unknown>[] = [];
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
        markets_by_venue: { kalshi: 1 },
        instruments_by_venue: {},
        relationships_by_state: {},
        database_bytes: 2048,
        max_bytes: 67_108_864,
      },
      sources: [source],
      latest_evidence_at_utc: '2026-10-26T20:00:00Z',
      limitations: [],
    },
    '/api/frontier/sources': {
      items: [source],
      operation_admission: {
        scope: 'frontier_router_instance',
        max_concurrent_source_operations: 2,
        single_flight_per_venue: true,
        maximum_acquire_wait_ms: 50,
        overload_status: 429,
        overload_behavior: 'fail_fast_no_request_queued',
      },
      network_called: false,
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
    '/api/frontier/relationships?limit=200': { items: [], returned: 0, limit: 200 },
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
    '/api/frontier/comparisons?limit=30': { items: [], returned: 0, limit: 30, offset: 0 },
    '/api/frontier/readiness': { gates: [] },
  };
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    if (path === '/api/frontier/probe/kalshi/market-metadata' && init?.method === 'POST') {
      marketMetadataBodies.push(JSON.parse(String(init.body)) as Record<string, unknown>);
      return {
        ok: true,
        json: async () => ({
          venue: 'kalshi',
          market_id: market.canonical_id,
          bound_market_observation_id: 'market-observation',
          market: {
            ...market,
            resolution: {
              ...market.resolution,
              primary_rule: 'Captured source detail rule.',
              authority: 'Example public resolution authority',
            },
          },
          observation_id: 'metadata-observation-id',
          raw_sha256: 'f'.repeat(64),
          request_count_delta: 1,
          network_calls_bounded_by: 1,
          catalogue_market_replaced: false,
          hypothetical_only: true,
          note: 'One detail response linked to the recorded source row.',
        }),
      } as Response;
    }
    if (path === '/api/frontier/probe/kalshi/event-markets' && init?.method === 'POST') {
      eventGroupBodies.push(JSON.parse(String(init.body)) as Record<string, unknown>);
      return {
        ok: true,
        json: async () => ({
          venue: 'kalshi',
          market_id: market.canonical_id,
          native_event_id: 'KX-FEE-1-EVENT',
          event_title: 'Example public event',
          market_count: 2,
          observation_id: 'event-group-observation',
          raw_sha256: 'd'.repeat(64),
          request_count_delta: 1,
          network_calls_bounded_by: 1,
          hypothetical_only: true,
          note: 'Event context only; no payoff equivalence verified.',
        }),
      } as Response;
    }
    if (path === '/api/frontier/probe/kalshi/mve-component-market' && init?.method === 'POST') {
      componentMarketBodies.push(JSON.parse(String(init.body)) as Record<string, unknown>);
      return {
        ok: true,
        json: async () => ({
          parent_market_id: market.canonical_id,
          component_market_id: 'KX-COMPONENT-MARKET',
          market: {
            ...market,
            canonical_id: 'kalshi:KX-COMPONENT-MARKET',
            native_market_id: 'KX-COMPONENT-MARKET',
            title: 'Component two assists or more',
            resolution: {
              ...market.resolution,
              primary_rule: 'The player records two or more assists.',
              secondary_rule: 'The official box score is the source.',
            },
          },
          observation_id: 'component-observation',
          raw_sha256: 'e'.repeat(64),
          request_count_delta: 1,
          network_calls_bounded_by: 1,
          combo_payoff_verified: false,
          hypothetical_only: true,
          note: 'Component metadata only; combo payoff is not verified.',
        }),
      } as Response;
    }
    if (path === '/api/frontier/economics/kalshi-mve-settlement-audit' && init?.method === 'POST') {
      settlementAuditBodies.push(JSON.parse(String(init.body)) as Record<string, unknown>);
      return {
        ok: true,
        json: async () => ({
          audit: {
            schema_version: 2,
            audit_algorithm_version: 'kalshi-mve-settlement-audit-2',
            lifecycle: 'settled',
            settlement_is_provisional: false,
            state: 'SOURCE REPORTED PRODUCT MATCH',
            component_values: [
              {
                native_market_id: 'KX-COMPONENT-MARKET',
                selected_side: 'yes',
                reported_yes_value_dollars: '0.3750',
                selected_position_value_dollars: '0.3750',
              },
            ],
            component_product_dollars: '0.3750',
            reported_settlement_value_dollars: '0.3750',
            missing_component_market_ids: [],
            source_observation_id: 'settled-mve-observation',
            source_raw_sha256: 'a'.repeat(64),
            assumptions: ['A matching result checks source-reported settlement arithmetic only.'],
            rule_source_urls: [
              'https://help.kalshi.com/en/articles/13823820-combos',
              'https://help.kalshi.com/en/articles/17515177-protected-nfl-player-markets',
              'https://docs.kalshi.com/api-reference/events/get-multivariate-events',
            ],
          },
          source_observation_id: 'settled-mve-observation',
          network_calls: 0,
          candidate_generation: false,
          note: 'Arithmetic only; rules and outcomes are not independently verified.',
        }),
      } as Response;
    }
    if (path === '/api/frontier/probe/kalshi/fee-metadata' && init?.method === 'POST') {
      requestBodies.push(JSON.parse(String(init.body)) as Record<string, unknown>);
      return {
        ok: true,
        json: async () => ({
          market_id: market.canonical_id,
          metadata: {
            series_ticker: 'KX-FEE-SERIES',
            event_fee_type_override: null,
            event_fee_multiplier_override: null,
            series_fee_type: 'quadratic',
            series_fee_multiplier: '1',
            effective_fee_type: 'quadratic',
            effective_fee_multiplier: '1',
            fee_resolution_state: 'series_inherited',
            economics_state: 'unresolved',
            limitations: ['Account rounding remains unknown.'],
          },
          observation_ids: ['event-observation', 'series-observation'],
          raw_sha256: { event: 'b'.repeat(64), series: 'c'.repeat(64) },
          fee_cost_modeled: false,
          note: 'Fee parameters saved; no account fee estimate was made.',
        }),
      } as Response;
    }
    if (
      path === '/api/frontier/economics/kalshi-fee-order-sensitivity' &&
      init?.method === 'POST'
    ) {
      sensitivityBodies.push(JSON.parse(String(init.body)) as Record<string, unknown>);
      return {
        ok: true,
        json: async () => ({
          market_id: market.canonical_id,
          hypothetical_only: true,
          candidate_net_economics_modified: false,
          note: 'Local one-order sensitivity only.',
          estimate: {
            model_version: 'kalshi-event-taker-order-fee-sensitivity-2026-07-07-v2',
            series_ticker: 'KX-FEE-SERIES',
            effective_fee_type: 'quadratic',
            effective_fee_multiplier: '1',
            fee_resolution_state: 'series_inherited',
            order_fills: [
              {
                native_instrument_id: 'KX-FEE-1:YES',
                side: 'buy',
                price_usd: '0.50',
                quantity_contracts: '1',
              },
              {
                native_instrument_id: 'KX-FEE-1:YES',
                side: 'buy',
                price_usd: '0.50',
                quantity_contracts: '1',
              },
            ],
            input_received_at_utc: ['2026-10-26T23:16:17.916305Z', '2026-10-26T23:16:18.408650Z'],
            scenarios: [
              {
                account_precision_class: 'direct_member',
                balance_quantum: '0.0001',
                fills: [
                  {
                    fill_index: 0,
                    native_instrument_id: 'KX-FEE-1:YES',
                    side: 'buy',
                    trade_fee_rounded_to_microdollar: '0.0175',
                    rounding_fee_usd: '0',
                    rebate_usd: '0',
                    accumulated_rounding_after_rebate_usd: '0',
                    net_fee_usd: '0.0175',
                  },
                  {
                    fill_index: 1,
                    native_instrument_id: 'KX-FEE-1:YES',
                    side: 'buy',
                    trade_fee_rounded_to_microdollar: '0.0175',
                    rounding_fee_usd: '0',
                    rebate_usd: '0',
                    accumulated_rounding_after_rebate_usd: '0',
                    net_fee_usd: '0.0175',
                  },
                ],
                total_trade_fee_usd: '0.035',
                total_rounding_fee_usd: '0',
                total_rebate_usd: '0',
                total_net_fee_usd: '0.035',
                total_balance_change_usd: '-1.035',
              },
              {
                account_precision_class: 'non_direct_member',
                balance_quantum: '0.01',
                fills: [
                  {
                    fill_index: 0,
                    native_instrument_id: 'KX-FEE-1:YES',
                    side: 'buy',
                    trade_fee_rounded_to_microdollar: '0.0175',
                    rounding_fee_usd: '0.0025',
                    rebate_usd: '0',
                    accumulated_rounding_after_rebate_usd: '0.0025',
                    net_fee_usd: '0.02',
                  },
                  {
                    fill_index: 1,
                    native_instrument_id: 'KX-FEE-1:YES',
                    side: 'buy',
                    trade_fee_rounded_to_microdollar: '0.0175',
                    rounding_fee_usd: '0.0025',
                    rebate_usd: '0',
                    accumulated_rounding_after_rebate_usd: '0.005',
                    net_fee_usd: '0.02',
                  },
                ],
                total_trade_fee_usd: '0.035',
                total_rounding_fee_usd: '0.005',
                total_rebate_usd: '0',
                total_net_fee_usd: '0.04',
                total_balance_change_usd: '-1.04',
              },
            ],
            calculation_sha256: 'f'.repeat(64),
            assumptions: ['one-fill fixture'],
          },
        }),
      } as Response;
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

  fireEvent.click(await screen.findByRole('button', { name: 'Markets' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Inspect' }));
  expect(screen.getByText('Market identity: fiat:USD')).toBeInTheDocument();
  expect(screen.getByText('Payoff identity: fiat:USD')).toBeInTheDocument();
  expect(
    await screen.findByText(
      /0\.01–0\.49 by 0\.01; 0\.50–0\.99 by 0\.001 · range boundaries are not treated as validated ticks/,
    ),
  ).toBeInTheDocument();
  expect(
    screen.getByText(/Quantity step: 0\.1 · minimum: 0\.2 · minimum notional: 5/),
  ).toBeInTheDocument();
  expect(screen.getByText(`instrument-v1:${'a'.repeat(64)}`)).toBeInTheDocument();
  expect(await screen.findByText('Public event context')).toBeInTheDocument();
  fireEvent.click(await screen.findByRole('button', { name: 'Capture market detail' }));
  expect(await screen.findByText('Captured source detail rule.')).toBeInTheDocument();
  expect(marketMetadataBodies).toEqual([{ market_id: market.canonical_id }]);
  fireEvent.click(screen.getByRole('button', { name: 'Capture event context' }));
  expect(
    await screen.findByText('2 markets · saved observation event-group-observation'),
  ).toBeInTheDocument();
  expect(eventGroupBodies).toEqual([
    { market_id: market.canonical_id, native_event_id: 'KX-FEE-1-EVENT' },
  ]);
  expect(
    await screen.findByText('Selected components from public MVE metadata'),
  ).toBeInTheDocument();
  expect(screen.getByText('KX-COMPONENT-MARKET')).toBeInTheDocument();
  expect(screen.getByText('Selected YES side')).toBeInTheDocument();
  expect(screen.getByText('Kalshi reported YES settlement value: $0.3750')).toBeInTheDocument();
  expect(
    screen.getByText(/do not verify component rules, combo payout, or resolution equivalence/),
  ).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Audit recorded settlement arithmetic' }));
  expect(
    await screen.findByText(
      /Source-reported settlement arithmetic · SOURCE REPORTED PRODUCT MATCH/,
    ),
  ).toBeInTheDocument();
  expect(
    screen.getByText(/Audit kalshi-mve-settlement-audit-2 · parent lifecycle settled/),
  ).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'combo settlement rule' })).toHaveAttribute(
    'href',
    'https://help.kalshi.com/en/articles/13823820-combos',
  );
  expect(
    screen.getByText(/Recomputed component product: \$0\.3750 · parent reported/),
  ).toBeInTheDocument();
  expect(settlementAuditBodies).toEqual([{ market_id: market.canonical_id }]);
  fireEvent.click(screen.getByRole('button', { name: 'Capture component rules' }));
  expect(
    await screen.findByText('Primary rule: The player records two or more assists.'),
  ).toBeInTheDocument();
  expect(componentMarketBodies).toEqual([
    {
      parent_market_id: market.canonical_id,
      component_market_id: 'KX-COMPONENT-MARKET',
    },
  ]);
  expect(await screen.findByText('Capture fee metadata')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Capture fee metadata' }));
  expect(await screen.findByText(/quadratic · multiplier 1/)).toBeInTheDocument();
  expect(screen.getByText(/not added to candidate economics/)).toBeInTheDocument();
  expect(screen.getByText('Account rounding remains unknown.')).toBeInTheDocument();
  expect(screen.getByText(/Event fee evidence event-observ/)).toBeInTheDocument();
  expect(screen.getByText(/Series fee evidence series-obse/)).toBeInTheDocument();
  expect(requestBodies).toEqual([{ market_id: market.canonical_id }]);
  fireEvent.click(screen.getByRole('button', { name: 'Add fill' }));
  expect(screen.getByLabelText('Fill 2 price per contract (USD)')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Calculate order fee' }));
  expect(
    await screen.findByText(/One-order taker sensitivity · 2 manual fills/),
  ).toBeInTheDocument();
  expect(screen.getByText(/Fee metadata received: event/)).toBeInTheDocument();
  expect(screen.getByText(/total fee \$0.04/)).toBeInTheDocument();
  expect(sensitivityBodies).toEqual([
    {
      market_id: market.canonical_id,
      event_observation_id: 'event-observation',
      series_observation_id: 'series-observation',
      fills: [
        {
          native_instrument_id: 'KX-FEE-1:YES',
          side: 'buy',
          price_usd: '0.50',
          quantity_contracts: '1',
        },
        {
          native_instrument_id: 'KX-FEE-1:YES',
          side: 'buy',
          price_usd: '0.50',
          quantity_contracts: '1',
        },
      ],
    },
  ]);
});

it('compares baseline and current assumptions over saved evidence and shows paired results', async () => {
  const comparison = {
    schema_version: 1,
    comparator_version: 'frontier-paired-replay-1',
    comparison_id: 'a'.repeat(64),
    evidence_input_sha256: 'b'.repeat(64),
    as_of_utc: '2026-10-26T20:00:00Z',
    arms: [
      {
        scenario: { name: 'quoted baseline' },
        run_id: 'c'.repeat(64),
        result_sha256: 'd'.repeat(64),
        candidate_count: 2,
        classification_counts: { 'VERIFIED MATHEMATICAL INCONSISTENCY': 2 },
        audit_disposition_counts: { verified: 2 },
        positive_gross_count: 2,
        positive_net_count: 2,
        unknown_net_count: 0,
      },
      {
        scenario: { name: 'current assumptions' },
        run_id: 'e'.repeat(64),
        result_sha256: 'f'.repeat(64),
        candidate_count: 2,
        classification_counts: { 'NEGATIVE AFTER MODELED COSTS': 1 },
        audit_disposition_counts: { verified: 2 },
        positive_gross_count: 2,
        positive_net_count: 1,
        unknown_net_count: 0,
      },
    ],
    delta: {
      baseline_scenario: 'quoted baseline',
      compared_scenario: 'current assumptions',
      matched_candidate_count: 2,
      unchanged_classification_count: 1,
      changed_classification_count: 1,
      baseline_only_candidate_count: 0,
      compared_only_candidate_count: 0,
      classification_count_delta: {
        'NEGATIVE AFTER MODELED COSTS': 1,
        'VERIFIED MATHEMATICAL INCONSISTENCY': -2,
      },
      positive_gross_count_delta: 0,
      positive_net_count_delta: -1,
      unknown_net_count_delta: 0,
    },
    result_sha256: '1'.repeat(64),
  };
  const empty = { items: [], returned: 0, limit: 100, offset: 0 };
  const responses: Record<string, unknown> = {
    '/api/frontier/overview': {
      state: 'AVAILABLE',
      research_only: true,
      live_execution: false,
      summary: {
        observations: 0,
        relationships: 0,
        relationship_reviews: 0,
        runs: 0,
        comparisons: 0,
        markets_by_venue: {},
        instruments_by_venue: {},
        relationships_by_state: {},
        database_bytes: 0,
        max_bytes: 1_000_000,
      },
      sources: [],
      latest_evidence_at_utc: null,
      limitations: [],
    },
    '/api/frontier/sources': {
      items: ['polymarket', 'kalshi'].map((venue) => ({
        venue,
        adapter_version: 'fixture-adapter',
        public_probe_enabled: false,
        capabilities: [],
        health: {
          state: 'available',
          last_success_at_utc: null,
          last_error_code: null,
          last_error: null,
          notes: [],
        },
      })),
    },
    '/api/frontier/markets?limit=100': empty,
    '/api/frontier/books?limit=100': empty,
    '/api/frontier/trades?limit=100': { ...empty, pages: [] },
    '/api/frontier/relationships?limit=200': empty,
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
    '/api/frontier/opportunities?limit=100': empty,
    '/api/frontier/runs?limit=30': empty,
    '/api/frontier/comparisons?limit=30': empty,
    '/api/frontier/readiness': { gates: [] },
  };
  let comparisonInput: Record<string, unknown> | undefined;
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    if (path === '/api/frontier/replay/compare' && init?.method === 'POST') {
      comparisonInput = JSON.parse(String(init.body)) as Record<string, unknown>;
      return {
        ok: true,
        json: async () => ({
          comparison,
          runs: [
            { run_id: comparison.arms[0].run_id, result_sha256: comparison.arms[0].result_sha256 },
            { run_id: comparison.arms[1].run_id, result_sha256: comparison.arms[1].result_sha256 },
          ],
        }),
      } as Response;
    }
    const body = responses[path];
    if (body === undefined) throw new Error(`Unexpected frontend request: ${path}`);
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

  fireEvent.click(screen.getByRole('button', { name: 'Economic workbench' }));
  fireEvent.change(
    await screen.findByRole('spinbutton', { name: 'Additional execution delay for Kalshi' }),
    { target: { value: '1500' } },
  );
  fireEvent.click(
    await screen.findByRole('button', { name: 'Compare quoted baseline with current assumptions' }),
  );

  expect(await screen.findByText(/Paired comparison saved/)).toBeInTheDocument();
  expect(screen.getByText('2 matched constructions')).toBeInTheDocument();
  expect(comparisonInput?.scenarios).toEqual([
    { name: 'quoted baseline' },
    {
      name: 'current assumptions',
      slippage_bps: '25',
      execution_delay_ms: 500,
      additional_execution_delay_ms_by_venue: { kalshi: 1500 },
      fill_fraction: '0.8000',
      quote_decay_bps_per_second: '15',
    },
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
        matcher_version: 'frontier-relationship-matcher-5',
        verifier_version: null,
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
      items: [marketRecord('polymarket', 'event-1', 'Who wins the mayoral election?')],
      returned: 1,
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
      entity_context: {
        schema_version: 1,
        model_version: 'frontier-market-entity-context-v2',
        scope: 'loaded_relationship_market_nodes',
        semantics: 'structural_metadata_only',
        economic_equivalence_asserted: false,
        source_market_count: 1,
        represented_market_count: 1,
        nodes: [
          {
            entity_id: `frontier-entity-v1:market:${'a'.repeat(64)}`,
            kind: 'market',
            label: 'Who wins the mayoral election?',
            label_truncated: true,
            venue: 'polymarket',
            native_id: 'event-1',
            native_id_truncated: false,
            market_kind: 'binary_event',
            lifecycle: 'open',
            quantity_unit: null,
            outcome_id: null,
            selected_side: null,
            identity_scope: null,
            value: null,
            resolution_authority: 'Official election authority',
            resolution_primary_rule: 'Candidate with the most votes wins.',
            resolution_secondary_rule: null,
            resolution_closes_at_utc: '2026-11-01T00:00:00Z',
            resolution_settles_at_utc: '2026-11-01T04:00:00Z',
            resolution_fingerprint: 'election-rules-v1',
            resolution_verified: false,
            payoff_state_ids: ['no', 'yes'],
            payoff_state_ids_truncated: true,
            payoff_exhaustive: true,
            payoff_verified: false,
            record_available: true,
            market_ids: ['polymarket:event-1'],
            source_observation_ids: ['poly-observation'],
          },
          {
            entity_id: `frontier-entity-v1:event:${'b'.repeat(64)}`,
            kind: 'event',
            label: 'Mayor election',
            venue: 'polymarket',
            native_id: 'native-election-event',
            native_id_truncated: false,
            market_kind: null,
            lifecycle: null,
            quantity_unit: null,
            outcome_id: null,
            selected_side: null,
            identity_scope: null,
            value: null,
            resolution_authority: null,
            resolution_primary_rule: null,
            resolution_secondary_rule: null,
            resolution_closes_at_utc: null,
            resolution_settles_at_utc: null,
            resolution_fingerprint: null,
            resolution_verified: null,
            payoff_state_ids: [],
            payoff_exhaustive: null,
            payoff_verified: null,
            record_available: true,
            market_ids: ['polymarket:event-1'],
            source_observation_ids: ['poly-observation'],
          },
        ],
        links: [
          {
            link_id: 'c'.repeat(64),
            source_entity_id: `frontier-entity-v1:market:${'a'.repeat(64)}`,
            target_entity_id: `frontier-entity-v1:event:${'b'.repeat(64)}`,
            link_type: 'part_of_event',
            source_market_id: 'polymarket:event-1',
            source_observation_id: 'poly-observation',
            source_field: 'native_event_id',
            semantic_basis: 'normalized_source_metadata',
            economic_equivalence_asserted: false,
          },
        ],
        truncated: true,
        truncation_reasons: ['entity_field_length_limit'],
        limitations: ['Event identifiers are venue-scoped.'],
      },
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
    '/api/frontier/comparisons?limit=30': { items: [], returned: 0, limit: 30, offset: 0 },
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
          entity_context:
            graphParams.get('include_entity_context') === 'true'
              ? graphBase.entity_context
              : undefined,
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
    fetchMock.mock.calls.some(
      ([input]) =>
        String(input).includes('/api/frontier/graph?') &&
        String(input).includes('include_entity_context=true'),
    ),
  ).toBe(true);
  expect(await screen.findByText('Not in loaded window')).toBeInTheDocument();
  expect(screen.getByText('market not in loaded window')).toBeInTheDocument();
  expect(
    screen.getByText('NOT IN LOADED WINDOW', { selector: 'text.fr-network-column' }),
  ).toBeInTheDocument();
  expect(
    await screen.findByText(
      /considered 500 relationship rows.*additional neighbors may be omitted/,
    ),
  ).toBeInTheDocument();
  fireEvent.click(await screen.findByText(/Source structure and asset context/));
  expect(
    await screen.findByText(/Structural links come from normalized source metadata/),
  ).toBeInTheDocument();
  expect(
    screen.getByRole('option', { name: /Who wins the mayoral election\?…/ }),
  ).toBeInTheDocument();
  expect(screen.getByText(/graph display clipped/)).toBeInTheDocument();
  expect(
    screen.getByText(/Structural context is bounded; omitted detail: entity_field_length_limit/),
  ).toBeInTheDocument();
  expect(screen.getByText(/Resolution authority: Official election authority/)).toBeInTheDocument();
  expect(screen.getByText(/native_event_id · native native-election-event/)).toBeInTheDocument();
  expect(screen.getByText('Source observation: poly-observation')).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Relationship graph center market'), {
    target: { value: 'polymarket:event-1' },
  });
  fireEvent.change(screen.getByLabelText('Relationship graph depth'), {
    target: { value: '2' },
  });
  await vi.waitFor(() =>
    expect(
      fetchMock.mock.calls.some(
        ([input]) =>
          String(input).includes('center_market_id=') && String(input).includes('depth=2'),
      ),
    ).toBe(true),
  );
  fireEvent.click(await screen.findByRole('button', { name: 'Load more neighbors' }));
  expect(await screen.findByText('Neighborhood page 2')).toBeInTheDocument();
  expect(
    fetchMock.mock.calls.some(
      ([input]) =>
        String(input).includes('cursor=cursor-page-2') && String(input).includes('depth=2'),
    ),
  ).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: 'Previous page' }));
  const edge = await screen.findByRole('button', { name: /text candidate hypothesis/i });
  fireEvent.click(edge);
  expect(edge).toHaveAttribute('aria-pressed', 'true');
  expect(
    await screen.findByText(/Shared title terms; rules and resolution dates/, { selector: 'p' }),
  ).toBeInTheDocument();
  expect(screen.getByText(/matcher frontier-relationship-matcher-5/)).toBeInTheDocument();
  expect(screen.getByText('shared_terms=mayor,election')).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText('Relationship graph center market'), {
    target: { value: '' },
  });
  fireEvent.change(screen.getByLabelText('Relationship graph depth'), {
    target: { value: '1' },
  });
  fireEvent.change(screen.getByPlaceholderText('Search recorded market titles or IDs'), {
    target: { value: 'mayor election' },
  });
  await vi.waitFor(() =>
    expect(fetchMock.mock.calls.some(([input]) => String(input).includes('q=mayor+election'))).toBe(
      true,
    ),
  );
  expect(
    await screen.findByText(/Text search seeds at most 200 recorded markets/),
  ).toBeInTheDocument();
  fireEvent.click(await screen.findByRole('button', { name: 'Load more matches' }));
  expect(await screen.findByText('Search page 2')).toBeInTheDocument();
  expect(
    fetchMock.mock.calls.some(
      ([input]) =>
        String(input).includes('q=mayor+election') &&
        String(input).includes('cursor=cursor-page-2'),
    ),
  ).toBe(true);
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
      instruments: [
        { native_instrument_id: 'poly-yes', label: 'Yes', outcome_id: 'yes' },
        { native_instrument_id: 'poly-no', label: 'No', outcome_id: 'no' },
      ],
      settlement_asset: 'USD',
      payoff: {
        state_ids: ['left-state'],
        payout_currency: 'USD',
        exhaustive: true,
        verified: true,
        verification_basis: 'fixture only',
      },
      resolution: {
        authority: null,
        closes_at_utc: null,
        settles_at_utc: null,
        resolution_fingerprint: null,
        verified: true,
      },
    },
    {
      canonical_id: 'kalshi:event-1',
      source_observation_record_id: 'b'.repeat(64),
      native_market_id: 'kalshi-event',
      venue: 'kalshi',
      title: 'Election event at Kalshi',
      market_kind: 'binary_event',
      instruments: [
        { native_instrument_id: 'kalshi-yes', label: 'Yes', outcome_id: 'yes' },
        { native_instrument_id: 'kalshi-no', label: 'No', outcome_id: 'no' },
      ],
      settlement_asset: 'USD',
      payoff: {
        state_ids: ['right-state'],
        payout_currency: 'USD',
        exhaustive: true,
        verified: true,
        verification_basis: 'fixture only',
      },
      resolution: {
        authority: null,
        closes_at_utc: null,
        settles_at_utc: null,
        resolution_fingerprint: null,
        verified: true,
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
    '/api/frontier/comparisons?limit=30': { items: [], returned: 0, limit: 30, offset: 0 },
    '/api/frontier/readiness': { gates: [] },
  };
  const reviewRequest = vi.fn();
  const recordedReviews: Record<string, unknown>[] = [];
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    if (path.endsWith('/relationships/' + 'c'.repeat(64) + '/review')) {
      const request = JSON.parse(String(init?.body));
      reviewRequest(request);
      const reviewRecord = {
        review_id: String(recordedReviews.length + 1).padStart(64, 'd'),
        relationship_id: 'c'.repeat(64),
        adjudicated_relationship_id: String(recordedReviews.length + 1).padStart(64, 'e'),
        decision: request.decision,
        reviewer_label: request.reviewer_label,
        reason: request.reason,
        evidence_observation_ids: request.evidence_observation_ids,
        external_assertion_id: request.external_assertion_id ?? null,
        supersedes_review_id: recordedReviews.at(-1)?.review_id ?? null,
        created_at_utc: new Date(Date.now() + recordedReviews.length * 1000).toISOString(),
      };
      recordedReviews.push(reviewRecord);
      Object.assign(relationship, { latest_review: reviewRecord, state: request.decision });
      return {
        ok: true,
        json: async () => ({ review: reviewRecord, relationship }),
      } as Response;
    }
    if (path.includes('/relationships/' + 'c'.repeat(64) + '/reviews?limit=20')) {
      return {
        ok: true,
        json: async () => ({
          items: [...recordedReviews].reverse(),
          total: recordedReviews.length,
          limit: 20,
          has_more: false,
          next_cursor: null,
          reviewer_identity_authenticated: false,
          external_assertions_authenticated: false,
        }),
      } as Response;
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
  fireEvent.click(await screen.findByRole('button', { name: 'Review hypothesis' }));
  fireEvent.change(screen.getByLabelText('Reviewer label'), { target: { value: 'reviewer-1' } });
  fireEvent.change(screen.getByLabelText('Review reason'), {
    target: { value: 'Rules remain incomplete for equivalence.' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Record immutable review' }));

  await vi.waitFor(() => expect(reviewRequest).toHaveBeenCalledOnce());
  expect(reviewRequest.mock.calls[0][0]).toMatchObject({
    decision: 'ambiguous',
    relationship_type: 'same_payoff',
    reviewer_label: 'reviewer-1',
    evidence_observation_ids: ['a'.repeat(64), 'b'.repeat(64)],
    expected_latest_review_id: null,
  });

  fireEvent.click(await screen.findByRole('button', { name: 'Append review' }));
  fireEvent.change(screen.getByLabelText('Review reason'), {
    target: { value: 'The source fields do not fully establish equivalence.' },
  });
  fireEvent.change(screen.getByLabelText('Decision'), { target: { value: 'verified' } });
  fireEvent.change(screen.getByLabelText('Relationship claim'), {
    target: { value: 'logical_implication' },
  });
  fireEvent.change(screen.getByLabelText('External assertion ID (reference only)'), {
    target: { value: 'fixture-assertion-1' },
  });
  fireEvent.change(screen.getByLabelText('Complete state mapping (left to right JSON)'), {
    target: { value: '{"left-state":1}' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Record immutable review' }));
  expect(
    await screen.findByText('State mapping must be a JSON object with nonblank string identifiers'),
  ).toBeInTheDocument();
  expect(reviewRequest).toHaveBeenCalledOnce();

  fireEvent.change(screen.getByLabelText('Complete state mapping (left to right JSON)'), {
    target: { value: '{"left-state":"right-state"}' },
  });
  fireEvent.change(screen.getByLabelText('YES implication direction'), {
    target: { value: 'right_to_left' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Record immutable review' }));

  await vi.waitFor(() => expect(reviewRequest).toHaveBeenCalledTimes(2));
  expect(reviewRequest.mock.calls[1][0]).toMatchObject({
    decision: 'verified',
    relationship_type: 'logical_implication',
    reviewer_label: 'reviewer-1',
    external_assertion_id: 'fixture-assertion-1',
    state_mapping: { 'left-state': 'right-state' },
    instrument_mapping: {},
    implication_from_market_id: 'kalshi:event-1',
    implication_to_market_id: 'polymarket:event-1',
  });

  fireEvent.click(await screen.findByRole('button', { name: 'View review history' }));
  expect(
    await screen.findByText(
      '2 append-only review record(s). Reviewer labels and assertion IDs are references, not authenticated identities.',
    ),
  ).toBeInTheDocument();
  expect(screen.getAllByText('The source fields do not fully establish equivalence.')).toHaveLength(
    2,
  );
  expect(screen.getByText('Rules remain incomplete for equivalence.')).toBeInTheDocument();
});

it('submits bounded Arena replay and discovery comparisons with verified results', async () => {
  const jobId = 'job-0123456789abcdef01234567';
  const discoveryJobId = 'job-abcdef0123456789abcdef01';
  const snapshotId = 'a'.repeat(64);
  const snapshotSha256 = 'b'.repeat(64);
  const resultSha256 = 'c'.repeat(64);
  const discoverySnapshotId = '6'.repeat(64);
  const discoverySnapshotSha256 = '7'.repeat(64);
  const discoveryResultSha256 = '8'.repeat(64);
  const healthCheckpointSha256 = '9'.repeat(64);
  const comparison = {
    comparison_id: 'd'.repeat(64),
    evidence_input_sha256: 'e'.repeat(64),
    as_of_utc: '2026-10-27T00:00:00Z',
    result_sha256: resultSha256,
    arms: [
      {
        scenario: { name: 'quoted baseline' },
        run_id: 'f'.repeat(64),
        result_sha256: '1'.repeat(64),
        candidate_count: 0,
        classification_counts: {},
        audit_disposition_counts: {},
        positive_gross_count: 0,
        positive_net_count: 0,
        unknown_net_count: 0,
      },
      {
        scenario: { name: 'current assumptions' },
        run_id: '2'.repeat(64),
        result_sha256: '3'.repeat(64),
        candidate_count: 0,
        classification_counts: {},
        audit_disposition_counts: {},
        positive_gross_count: 0,
        positive_net_count: 0,
        unknown_net_count: 0,
      },
    ],
    delta: {
      baseline_scenario: 'quoted baseline',
      compared_scenario: 'current assumptions',
      matched_candidate_count: 0,
      unchanged_classification_count: 0,
      changed_classification_count: 0,
      baseline_only_candidate_count: 0,
      compared_only_candidate_count: 0,
      classification_count_delta: {},
      positive_gross_count_delta: 0,
      positive_net_count_delta: 0,
      unknown_net_count_delta: 0,
    },
  };
  const discoveryComparison = {
    comparison_id: '9'.repeat(64),
    normalized_input_sha256: 'a'.repeat(64),
    result_sha256: discoveryResultSha256,
    code_version: 'frontier-fixture-scope-v1',
    as_of_utc: '2026-10-27T00:00:00Z',
    arms: [
      {
        scope: 'polymarket_only',
        venues: ['polymarket'],
        replay_run_ids: ['b'.repeat(64)],
        market_count: 1,
        instrument_count: 2,
        book_count: 2,
        observed_instrument_count: 2,
        relationship_count: 0,
        candidates: [],
        family_counts: {},
        classification_counts: {},
        audit_disposition_counts: {},
      },
      {
        scope: 'venue_local',
        venues: ['kalshi', 'polymarket'],
        replay_run_ids: ['c'.repeat(64), 'd'.repeat(64)],
        market_count: 2,
        instrument_count: 4,
        book_count: 4,
        observed_instrument_count: 4,
        relationship_count: 0,
        candidates: [],
        family_counts: {},
        classification_counts: {},
        audit_disposition_counts: {},
      },
      {
        scope: 'cross_venue',
        venues: ['kalshi', 'polymarket'],
        replay_run_ids: ['e'.repeat(64)],
        market_count: 2,
        instrument_count: 4,
        book_count: 4,
        observed_instrument_count: 4,
        relationship_count: 1,
        candidates: [
          {
            candidate_id: 'f'.repeat(64),
            family: 'cross_venue_complete_coverage',
            classification: 'CONDITIONAL ECONOMIC OPPORTUNITY',
            audit_disposition: 'verified',
            market_ids: ['kalshi:scope-event', 'polymarket:scope-event'],
            participating_venues: ['kalshi', 'polymarket'],
            leg_count: 2,
            worst_case_gross_pnl: '0.049999999999999998',
            worst_case_net_pnl: '0.049699999999999998',
          },
        ],
        family_counts: { cross_venue_complete_coverage: 1 },
        classification_counts: { 'CONDITIONAL ECONOMIC OPPORTUNITY': 1 },
        audit_disposition_counts: { verified: 1 },
      },
    ],
    deltas: [
      {
        baseline: 'polymarket_only',
        compared: 'venue_local',
        matched_candidate_count: 0,
        unchanged_classification_count: 0,
        changed_classification_count: 0,
        baseline_only_candidate_count: 0,
        compared_only_candidate_count: 0,
        family_count_delta: {},
        classification_count_delta: {},
      },
      {
        baseline: 'venue_local',
        compared: 'cross_venue',
        matched_candidate_count: 0,
        unchanged_classification_count: 0,
        changed_classification_count: 0,
        baseline_only_candidate_count: 0,
        compared_only_candidate_count: 1,
        family_count_delta: { cross_venue_complete_coverage: 1 },
        classification_count_delta: { 'CONDITIONAL ECONOMIC OPPORTUNITY': 1 },
      },
      {
        baseline: 'polymarket_only',
        compared: 'cross_venue',
        matched_candidate_count: 0,
        unchanged_classification_count: 0,
        changed_classification_count: 0,
        baseline_only_candidate_count: 0,
        compared_only_candidate_count: 1,
        family_count_delta: { cross_venue_complete_coverage: 1 },
        classification_count_delta: { 'CONDITIONAL ECONOMIC OPPORTUNITY': 1 },
      },
    ],
  };
  const empty = { items: [], returned: 0, limit: 100, offset: 0 };
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
        comparisons: 0,
        markets_by_venue: {},
        instruments_by_venue: {},
        relationships_by_state: {},
        database_bytes: 0,
        max_bytes: 1_000_000,
      },
      sources: [],
      latest_evidence_at_utc: null,
      limitations: [],
    },
    '/api/frontier/sources': { items: [] },
    '/api/frontier/markets?limit=100': {
      items: [
        {
          venue: 'polymarket',
          native_market_id: 'timeline-fixture',
          native_fields: { conditionId: 'timeline-fixture' },
          instruments: [],
        },
      ],
      returned: 1,
      limit: 100,
      offset: 0,
    },
    '/api/frontier/books?limit=100': empty,
    '/api/frontier/trades?limit=100': { ...empty, pages: [] },
    '/api/frontier/relationships?limit=200': empty,
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
    '/api/frontier/opportunities?limit=100': empty,
    '/api/frontier/runs?limit=30': empty,
    '/api/frontier/comparisons?limit=30': empty,
    '/api/frontier/readiness': { gates: [] },
    '/api/frontier/collection-health-events?limit=20': {
      items: [
        {
          event: {
            venue: 'polymarket',
            observed_at_utc: '2026-10-27T00:00:00Z',
            state: 'available',
            basis: 'recorded',
            evidence_observation_id: healthCheckpointSha256,
            reason: 'Verified collector checkpoint reported healthy source health.',
          },
          run_id: '0'.repeat(36),
          adapter_version: 'fixture-adapter-v1',
          checkpoint_sequence: 2,
          checkpoint_updated_at_utc: '2026-10-27T00:00:01Z',
          last_success_at_utc: '2026-10-27T00:00:00Z',
          source_health_state: 'healthy',
        },
        {
          event: {
            venue: 'polymarket',
            observed_at_utc: '2026-10-27T00:00:00Z',
            state: 'unavailable',
            basis: 'recorded',
            evidence_observation_id: '8'.repeat(64),
            reason: 'Verified collector checkpoint reported unavailable source health.',
          },
          run_id: '1'.repeat(36),
          adapter_version: 'fixture-adapter-v1',
          checkpoint_sequence: 1,
          checkpoint_updated_at_utc: '2026-10-27T00:00:01Z',
          last_success_at_utc: null,
          source_health_state: 'unavailable',
        },
      ],
      returned: 2,
      limit: 20,
      network_called: false,
      research_only: true,
      source_health_scope: 'adapter_local_checkpoint',
    },
  };
  const jobSummary = {
    job_id: jobId,
    state: 'COMPLETED',
    created_at: 1_793_049_600,
    updated_at: 1_793_049_601,
    elapsed_seconds: 0.1993923489935696,
    progress: { done: 3, total: 3 },
    phase: 'publishing-hash-verified-result',
    error: null,
    snapshot_id: snapshotId,
    snapshot_sha256: snapshotSha256,
    runtime_profile: {
      worker_process_user_cpu_seconds: 0.067554,
      worker_process_system_cpu_seconds: 0.010943,
      worker_process_peak_rss_bytes: 167288832,
    },
    result: { comparison_id: comparison.comparison_id, frontier_replay_sha256: resultSha256 },
  };
  const discoveryJobSummary = {
    job_id: discoveryJobId,
    state: 'COMPLETED',
    created_at: 1_793_049_600,
    updated_at: 1_793_049_601,
    elapsed_seconds: 0.174,
    progress: { done: 3, total: 3 },
    phase: 'publishing-hash-verified-discovery-result',
    error: null,
    snapshot_id: discoverySnapshotId,
    snapshot_sha256: discoverySnapshotSha256,
    runtime_profile: null,
    result: {
      comparison_id: discoveryComparison.comparison_id,
      frontier_discovery_sha256: discoveryResultSha256,
    },
  };
  let submission: Record<string, unknown> | undefined;
  let discoverySubmission: Record<string, unknown> | undefined;
  let timelineSubmission: Record<string, unknown> | undefined;
  const submittedSourceEvents = () =>
    Array.isArray(timelineSubmission?.source_status_events)
      ? (timelineSubmission.source_status_events as {
          venue: string;
          state: string;
          basis: string;
          reason: string;
          evidence_observation_id: string;
        }[])
      : [];
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    if (path === '/api/arena/frontier-timelines?limit=20') {
      return {
        ok: true,
        json: async () => ({
          items: timelineSubmission
            ? [
                {
                  job_id: jobId,
                  state: 'COMPLETED',
                  created_at: jobSummary.created_at,
                  updated_at: jobSummary.updated_at,
                  elapsed_seconds: 0.1,
                  progress: { done: 3, total: 3 },
                  phase: 'publishing-hash-verified-timeline',
                  error: null,
                  snapshot_id: snapshotId,
                  snapshot_sha256: snapshotSha256,
                  runtime_profile: null,
                  result: { timeline_id: '4'.repeat(64), frontier_timeline_sha256: '5'.repeat(64) },
                },
              ]
            : [],
          limit: 20,
          scanned: timelineSubmission ? 1 : 0,
          scan_bound: 500,
          scan_may_be_incomplete: false,
          research_only: true,
        }),
      } as Response;
    }
    if (path === '/api/frontier/arena-timeline-replay' && init?.method === 'POST') {
      timelineSubmission = JSON.parse(String(init.body)) as Record<string, unknown>;
      return {
        ok: true,
        json: async () => ({
          job_id: jobId,
          state: 'COMPLETED',
          created_at: jobSummary.created_at,
          updated_at: jobSummary.updated_at,
          elapsed_seconds: 0.1,
          progress: { done: 3, total: 3 },
          phase: 'publishing-hash-verified-timeline',
          error: null,
          result: { timeline_id: '4'.repeat(64), frontier_timeline_sha256: '5'.repeat(64) },
          frontier_snapshot_id: snapshotId,
          frontier_snapshot_sha256: snapshotSha256,
          timeline_frame_policy: 'input_event_times_and_book_freshness_boundaries',
        }),
      } as Response;
    }
    if (path === `/api/arena/jobs/${jobId}/frontier-timeline`) {
      return {
        ok: true,
        json: async () => ({
          artifact: {
            snapshot_id: snapshotId,
            snapshot_sha256: snapshotSha256,
            result_sha256: '5'.repeat(64),
            timeline: {
              timeline_id: '4'.repeat(64),
              result_sha256: '6'.repeat(64),
              manifest: {
                code_version: 'frontier-fixture',
                input_sha256: '7'.repeat(64),
                market_observation_ids: ['market-fixture'],
                book_observation_ids: ['book-fixture'],
                relationship_ids: [],
                source_status_sha256s: submittedSourceEvents().map(
                  (event) => event.evidence_observation_id,
                ),
                evaluation_times_utc: ['2026-10-27T00:00:00Z'],
                max_book_age_ms: Number(timelineSubmission?.max_book_age_ms ?? 15_000),
              },
              frames: [
                {
                  as_of_utc: '2026-10-27T00:00:00Z',
                  replay_run_id: '8'.repeat(64),
                  replay_result_sha256: '9'.repeat(64),
                  fresh_book_count: 1,
                  included_book_count: 1,
                  stale_book_count: 0,
                  not_yet_observed_count: 0,
                  excluded_source_book_count: 0,
                  source_states: submittedSourceEvents().map((event) => ({
                    venue: event.venue,
                    state: event.state,
                    basis: event.basis,
                    reason: event.reason,
                  })),
                  instrument_states: [
                    {
                      market_id: 'fixture-market',
                      venue: 'polymarket',
                      native_market_id: 'fixture-native-market',
                      native_instrument_id: 'fixture-token',
                      book_state: 'fresh',
                      exclusion: 'none',
                      included_in_replay: true,
                      observation_id: 'fixture-book',
                      received_at_utc: '2026-10-27T00:00:00Z',
                      age_ms: 0,
                      exchange_timestamp_utc: '2026-10-26T23:59:59.900Z',
                      exchange_timestamp_semantics: 'CLOB snapshot timestamp',
                      clock_uncertainty_ms: '2.5',
                      freshness_limit_ms: 1200,
                    },
                  ],
                  candidate_count: 0,
                  classification_counts: {},
                  candidates: [],
                },
              ],
            },
          },
          research_only: true,
          orders_submitted: false,
          authenticated_requests: false,
          integrity_verified: true,
        }),
      } as Response;
    }
    if (path === '/api/arena/frontier-replays?limit=20') {
      return {
        ok: true,
        json: async () => ({
          items: submission ? [jobSummary] : [],
          limit: 20,
          scanned: submission ? 1 : 0,
          scan_bound: 500,
          scan_may_be_incomplete: false,
          research_only: true,
        }),
      } as Response;
    }
    if (path === '/api/arena/frontier-discovery-comparisons?limit=20') {
      return {
        ok: true,
        json: async () => ({
          items: discoverySubmission ? [discoveryJobSummary] : [],
          limit: 20,
          scanned: discoverySubmission ? 1 : 0,
          scan_bound: 500,
          scan_may_be_incomplete: false,
          research_only: true,
        }),
      } as Response;
    }
    if (path === '/api/frontier/arena-discovery-comparison' && init?.method === 'POST') {
      discoverySubmission = JSON.parse(String(init.body)) as Record<string, unknown>;
      return {
        ok: true,
        json: async () => ({
          job_id: discoveryJobId,
          state: 'COMPLETED',
          created_at: discoveryJobSummary.created_at,
          updated_at: discoveryJobSummary.updated_at,
          elapsed_seconds: discoveryJobSummary.elapsed_seconds,
          progress: discoveryJobSummary.progress,
          phase: discoveryJobSummary.phase,
          error: null,
          result: discoveryJobSummary.result,
          frontier_snapshot_id: discoverySnapshotId,
          frontier_snapshot_sha256: discoverySnapshotSha256,
        }),
      } as Response;
    }
    if (path === `/api/arena/jobs/${discoveryJobId}/frontier-discovery`) {
      return {
        ok: true,
        json: async () => ({
          artifact: {
            comparison: discoveryComparison,
            replays: [
              {
                run_id: 'e'.repeat(64),
                candidates: [
                  {
                    candidate_id: 'f'.repeat(64),
                    family: 'cross_venue_complete_coverage',
                    classification: 'CONDITIONAL ECONOMIC OPPORTUNITY',
                    venues: ['kalshi', 'polymarket'],
                    legs: [
                      {
                        venue: 'kalshi',
                        native_market_id: 'scope-event',
                        instrument_id: 'KX-SCOPE-YES',
                        outcome_id: 'yes',
                        quantity_unit: 'contracts',
                        quantity: '1',
                        quoted_ask: '0.450000000000000001',
                        modeled_buy_price: '0.450000000000000001',
                        modeled_fee: '0',
                        quote_currency: 'USD',
                        quote_currency_identity: {
                          schema_version: 1,
                          kind: 'fiat',
                          code: 'USD',
                          network_id: null,
                          asset_reference: null,
                        },
                        displayed_depth: '10',
                        book_observation_id: '1'.repeat(64),
                      },
                      {
                        venue: 'polymarket',
                        native_market_id: 'scope-event-complement',
                        instrument_id: 'PM-SCOPE-NO',
                        outcome_id: 'no',
                        quantity_unit: 'shares',
                        quantity: '1',
                        quoted_ask: '0.500000000000000001',
                        modeled_buy_price: '0.500000000000000001',
                        modeled_fee: '0.0003',
                        quote_currency: 'USD',
                        quote_currency_identity: {
                          schema_version: 1,
                          kind: 'fiat',
                          code: 'USD',
                          network_id: null,
                          asset_reference: null,
                        },
                        displayed_depth: '20',
                        book_observation_id: '4'.repeat(64),
                      },
                    ],
                    gross_cost: '0.950000000000000002',
                    modeled_fees: '0.0003',
                    modeled_net_cost: '0.950300000000000002',
                    outcome_payout_by_state: { yes: '1', no: '1' },
                    gross_pnl_by_state: {
                      yes: '0.049999999999999998',
                      no: '0.049999999999999998',
                    },
                    net_pnl_by_state: {
                      yes: '0.049699999999999998',
                      no: '0.049699999999999998',
                    },
                    worst_case_gross_pnl: '0.049999999999999998',
                    worst_case_net_pnl: '0.049699999999999998',
                    capital_currency_identity: {
                      schema_version: 1,
                      kind: 'fiat',
                      code: 'USD',
                      network_id: null,
                      asset_reference: null,
                    },
                    practical_eligibility: false,
                    received_skew_ms: null,
                    exchange_skew_ms: null,
                    timing_verified: false,
                    independent_audit: {
                      disposition: 'verified',
                      input_sha256: '2'.repeat(64),
                      checks: ['Arithmetic independently recomputed.'],
                      message: 'The stored construction passed the independent arithmetic audit.',
                    },
                    assumptions: ['Explicit hypothetical fixture.'],
                    reasons: ['External mapping remains conditional.'],
                    evidence_sha256: '3'.repeat(64),
                  },
                ],
              },
            ],
            snapshot_id: discoverySnapshotId,
            snapshot_sha256: discoverySnapshotSha256,
            result_sha256: discoveryResultSha256,
          },
          research_only: true,
          orders_submitted: false,
          authenticated_requests: false,
          integrity_verified: true,
        }),
      } as Response;
    }
    if (path === '/api/frontier/arena-replay' && init?.method === 'POST') {
      submission = JSON.parse(String(init.body)) as Record<string, unknown>;
      return {
        ok: true,
        json: async () => ({
          job_id: jobId,
          state: 'COMPLETED',
          created_at: jobSummary.created_at,
          updated_at: jobSummary.updated_at,
          progress: jobSummary.progress,
          phase: jobSummary.phase,
          error: null,
          result: jobSummary.result,
          frontier_snapshot_id: snapshotId,
          frontier_snapshot_sha256: snapshotSha256,
        }),
      } as Response;
    }
    if (path === `/api/arena/jobs/${jobId}/frontier-replay`) {
      return {
        ok: true,
        json: async () => ({
          artifact: {
            comparison,
            snapshot_id: snapshotId,
            snapshot_sha256: snapshotSha256,
            result_sha256: resultSha256,
          },
          research_only: true,
          orders_submitted: false,
          authenticated_requests: false,
          integrity_verified: true,
        }),
      } as Response;
    }
    const body = responses[path];
    if (body === undefined) throw new Error(`Unexpected frontend request: ${path}`);
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

  fireEvent.click(await screen.findByRole('button', { name: 'Replay & readiness' }));
  expect(await screen.findByText('No Arena replay jobs')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Run paired replay in Arena' }));

  expect(await screen.findByText(/Hash checks passed/)).toBeInTheDocument();
  expect(screen.getByText('0 matched constructions')).toBeInTheDocument();
  expect(screen.getByText(snapshotSha256)).toBeInTheDocument();
  expect(screen.getByText('Worker process CPU (user / system)')).toBeInTheDocument();
  expect(screen.getByText('0.068 / 0.011 s')).toBeInTheDocument();
  expect(screen.getByText(/159\.5/)).toBeInTheDocument();
  expect(screen.getByText(/do not establish sustained Arena capacity/)).toBeInTheDocument();
  expect(submission?.scenarios).toEqual([
    { name: 'quoted baseline' },
    {
      name: 'current assumptions',
      slippage_bps: '25',
      execution_delay_ms: 500,
      additional_execution_delay_ms_by_venue: {},
      fill_fraction: '0.8000',
      quote_decay_bps_per_second: '15',
    },
  ]);

  fireEvent.click(screen.getByRole('button', { name: 'Compare scopes in Arena' }));
  expect(await screen.findByText(/Verified artifact/)).toBeInTheDocument();
  expect(screen.getAllByText('4 saved books')).toHaveLength(2);
  expect(screen.getAllByText(/1 added/)).toHaveLength(2);
  expect(screen.getByText(/Counts describe this saved evidence window only/)).toBeInTheDocument();
  fireEvent.click(screen.getByText(/Inspect candidate/));
  expect(
    await screen.findByText('Terminal outcomes under the pinned payoff model'),
  ).toBeInTheDocument();
  expect(screen.getByText(/Hypothetical replay only/)).toBeInTheDocument();
  fireEvent.click(screen.getByText(/Independent audit, assumptions, and evidence hashes/));
  expect(screen.getByText('Arithmetic independently recomputed.')).toBeInTheDocument();
  expect(screen.getByText(/Book evidence/)).toBeInTheDocument();
  expect(screen.getAllByText('0.450000000000000001 USD')).toHaveLength(2);
  expect(screen.getAllByText(/Net 0\.049699999999999998/)).toHaveLength(2);
  expect(discoverySubmission).toEqual({
    relationship_limit: 500,
    scenario: { name: 'quoted baseline' },
  });

  expect(await screen.findByText('No event-time replay jobs')).toBeInTheDocument();
  const recordedHealthCheckbox = await screen.findByRole('checkbox', {
    name: /Include recorded polymarket available health/,
  });
  expect(recordedHealthCheckbox).not.toBeChecked();
  expect(
    fetchMock.mock.calls.some(
      ([input, init]) =>
        String(input) === '/api/frontier/arena-timeline-replay' && init?.method === 'POST',
    ),
  ).toBe(false);
  expect(fetchMock.mock.calls.some(([input]) => String(input).includes('/probe/'))).toBe(false);
  fireEvent.click(recordedHealthCheckbox);
  expect(
    screen.getByRole('checkbox', {
      name: /Include recorded polymarket unavailable health/,
    }),
  ).toBeDisabled();
  const freshnessInput = screen.getByLabelText('Maximum book age (milliseconds)');
  const timelineReplayButton = screen.getByRole('button', { name: 'Replay saved timeline' });
  fireEvent.change(freshnessInput, { target: { value: '0' } });
  expect(timelineReplayButton).toBeDisabled();
  fireEvent.change(freshnessInput, { target: { value: '5000' } });
  expect(timelineReplayButton).toBeEnabled();
  fireEvent.click(timelineReplayButton);
  expect(await screen.findByText(/1 event-time frames are pinned/)).toBeInTheDocument();
  expect(screen.getByText('Freshness limit 5,000 ms')).toBeInTheDocument();
  expect(
    screen.getByText(/Recorded source states replay adapter-local checkpoint health/),
  ).toBeInTheDocument();
  expect(
    screen.getByText('1 fresh · 0 stale · 0 not yet observed · 0 source-excluded'),
  ).toBeInTheDocument();
  expect(screen.getByText('polymarket: available')).toBeInTheDocument();
  expect(
    screen.getByRole('table', { name: 'Per-instrument source timing evidence' }),
  ).toHaveTextContent('2.5 ms');
  expect(screen.getByText('CLOB snapshot timestamp')).toBeInTheDocument();
  expect(screen.getByLabelText('Recorded health checkpoint digests')).toHaveTextContent(
    healthCheckpointSha256,
  );
  expect(timelineSubmission).toEqual({
    max_book_age_ms: 5000,
    source_status_events: [
      {
        venue: 'polymarket',
        observed_at_utc: '2026-10-27T00:00:00Z',
        state: 'available',
        basis: 'recorded',
        evidence_observation_id: healthCheckpointSha256,
        reason: 'Verified collector checkpoint reported healthy source health.',
      },
    ],
  });
});

it('captures one explicit bounded Kalshi multivariate event page', async () => {
  const source = {
    venue: 'kalshi',
    adapter_version: 'frontier-kalshi-9',
    public_probe_enabled: true,
    capabilities: [
      {
        capability: 'multivariate_event_discovery',
        supported: true,
        state: 'implemented',
        reason: 'One filtered public event page with nested markets.',
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
        comparisons: 0,
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
    '/api/frontier/sources': {
      items: [source],
      operation_admission: {
        scope: 'frontier_router_instance',
        max_concurrent_source_operations: 2,
        single_flight_per_venue: true,
        maximum_acquire_wait_ms: 50,
        overload_status: 429,
        overload_behavior: 'fail_fast_no_request_queued',
        runtime_snapshot: {
          sampled_at_utc: '2026-10-29T05:41:00Z',
          active_operations: 1,
          active_venues: ['kalshi'],
          admitted_operations_total: 7,
          busy_rejections_total: 3,
          busy_rejections_by_scope: { venue: 1, capacity: 2 },
        },
      },
      network_called: false,
    },
    '/api/frontier/collection-runs?limit=20': {
      items: [],
      returned: 0,
      limit: 20,
      next_before_run_id: null,
      network_called: false,
      research_only: true,
    },
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
    '/api/frontier/comparisons?limit=30': { items: [], returned: 0, limit: 30, offset: 0 },
    '/api/frontier/readiness': { gates: [] },
  };
  let multivariateCaptureCount = 0;
  const failureObservationId = 'd'.repeat(64);
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    if (path === '/api/frontier/probe/kalshi' && init?.method === 'POST') {
      return {
        ok: false,
        headers: new Headers({ 'Retry-After': '1' }),
        json: async () => ({
          detail: {
            code: 'SOURCE_OPERATION_BUSY',
            venue: 'kalshi',
            scope: 'capacity',
            message:
              'Public source operation is busy: the shared source-operation capacity is full',
          },
        }),
      } as Response;
    }
    if (path === '/api/frontier/probe/kalshi/multivariate-events' && init?.method === 'POST') {
      multivariateCaptureCount += 1;
      if (multivariateCaptureCount === 2) {
        return {
          ok: false,
          json: async () => ({
            detail: {
              code: 'RESPONSE_TOO_LARGE',
              message: 'Response exceeds configured byte bound',
              diagnostic_observation_ids: [failureObservationId],
              diagnostic_persistence_error: null,
            },
          }),
        } as Response;
      }
      expect(JSON.parse(String(init.body))).toEqual({ event_ticker: 'KX-MVE-EVENT' });
      return {
        ok: true,
        json: async () => ({
          venue: 'kalshi',
          filter_type: 'tickers',
          filter_value: 'KX-MVE-EVENT',
          event_count: 1,
          market_count: 1,
          events: [
            {
              native_event_id: 'KX-MVE-EVENT',
              title: 'One selected event',
              series_ticker: 'KX-SERIES',
              collection_ticker: null,
              market_count: 1,
              member_list_state: 'included',
            },
          ],
          complete_for_request: false,
          has_more_source_pages: true,
          observation_id: 'a'.repeat(64),
          raw_sha256: 'b'.repeat(64),
          request_count_delta: 1,
          network_calls_bounded_by: 1,
          hypothetical_only: true,
          note: 'One page; source cursor retained.',
        }),
      } as Response;
    }
    if (path === `/api/frontier/observations/${failureObservationId}`) {
      return {
        ok: true,
        json: async () => ({
          observation_id: failureObservationId,
          venue: 'kalshi',
          observation_kind: 'source_failure',
          received_at_utc: '2026-10-27T20:00:01Z',
          raw_sha256: 'e'.repeat(64),
          row_sha256: 'f'.repeat(64),
          raw: {
            request_url: 'https://public.example.test/events/KX-MVE-EVENT',
            http_status: 200,
            request_started_at_utc: '2026-10-27T20:00:00Z',
            received_at_utc: '2026-10-27T20:00:01Z',
            request_elapsed_monotonic_ns: 1_234_000,
            raw_body: '',
            raw_body_state: 'not_captured_after_size_limit',
            adapter_version: 'fixture-v1',
          },
          normalized: {
            schema_version: 2,
            record_kind: 'source_failure',
            failure_stage: 'transport_rejection',
            error_code: 'RESPONSE_TOO_LARGE',
            message: 'Response exceeds configured byte bound',
            response_rejection: {
              schema_version: 1,
              rejection_stage: 'content_length',
              response_body_state: 'not_captured_after_size_limit',
              response_body_limit_bytes: 262144,
              declared_content_length_bytes: 524288,
              bytes_yielded_at_rejection: 0,
            },
          },
        }),
      } as Response;
    }
    if (path === `/api/frontier/observations/${'a'.repeat(64)}`) {
      return {
        ok: true,
        json: async () => ({
          observation_id: 'a'.repeat(64),
          venue: 'kalshi',
          observation_kind: 'multivariate_event_listing',
          received_at_utc: '2026-10-27T20:00:00Z',
          raw_sha256: 'b'.repeat(64),
          row_sha256: 'c'.repeat(64),
          raw: {
            request_url: 'https://public.example.test/events',
            http_status: 200,
            request_started_at_utc: '2026-10-27T19:59:59.990Z',
            received_at_utc: '2026-10-27T20:00:00Z',
            request_elapsed_monotonic_ns: 9_123_456,
            raw_body: '{}',
            adapter_version: 'fixture-v1',
          },
          normalized: {},
        }),
      } as Response;
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

  await screen.findByText('No replay runs yet');
  expect(fetchMock.mock.calls.every(([, init]) => init?.method !== 'POST')).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: 'Exchanges' }));
  expect(await screen.findByText('Multivariate event discovery')).toBeInTheDocument();
  expect(
    screen.getByText(/Public captures allow at most 2 concurrent source operations/),
  ).toBeInTheDocument();
  expect(
    screen.getByText(
      /1 of 2 slots active; 7 admitted and 3 contention rejections since this API router started/,
    ),
  ).toBeInTheDocument();
  expect(screen.getByText(/same-venue 1, shared-capacity 2/)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Refresh source status' })).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Kalshi multivariate filter type'), {
    target: { value: 'event_ticker' },
  });
  fireEvent.change(screen.getByLabelText('Kalshi multivariate filter ticker'), {
    target: { value: 'KX-MVE-EVENT' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Capture one event page' }));
  expect(await screen.findByText(/Saved 1 event\(s\) and 1 nested market/)).toBeInTheDocument();
  expect(screen.getByText(/One selected event · KX-MVE-EVENT/)).toBeInTheDocument();
  expect(screen.getByText('Inspect immutable source response')).toBeInTheDocument();
  fireEvent.click(screen.getByText('Inspect immutable source response'));
  expect(await screen.findByText(`Observation ID · ${'a'.repeat(64)}`)).toBeInTheDocument();
  expect(
    await screen.findByText(/HTTP request\/body elapsed \(monotonic\): 9\.123 ms/),
  ).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Capture one event page' }));
  expect(
    await screen.findByText(/RESPONSE_TOO_LARGE: Response exceeds configured byte bound/),
  ).toBeInTheDocument();
  const failureEvidence = screen.getByText(
    `Saved diagnostic observation · ${failureObservationId}`,
  ).parentElement;
  expect(failureEvidence).not.toBeNull();
  fireEvent.click(within(failureEvidence!).getByText('Inspect immutable source response'));
  expect(
    await screen.findByText(/Rejected at content length · body cap 262144 bytes/),
  ).toBeInTheDocument();
  expect(
    await screen.findByText(
      /Response body not captured because it exceeded the configured size limit/,
    ),
  ).toBeInTheDocument();
  expect(screen.getByText(`Stored raw SHA-256 · ${'e'.repeat(64)}`)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Capture markets, one book & trades' }));
  expect(
    await screen.findByText(/Source capture busy for kalshi:.*Retry after 1 second/),
  ).toBeInTheDocument();
  expect(fetchMock.mock.calls.some(([input]) => String(input).includes('/probe/'))).toBe(true);
  queryClient.clear();
});
