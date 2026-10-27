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
      'Coinbase Exchange source use remains held until the operator acknowledges the reviewed Market Data Terms version None.',
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
    '/api/frontier/comparisons?limit=30': { items: [], returned: 0, limit: 30, offset: 0 },
    '/api/frontier/readiness': { gates: [] },
    '/api/frontier/analytics/coverage': {
      schema_version: 1,
      as_of_utc: '2026-10-27T21:00:00Z',
      scope: 'Latest bounded hash-checked stored market, book, and eligible replay samples.',
      samples: {
        distinct_markets: 0,
        market_records: 0,
        book_observation_records: 0,
        invalid_normalized_book_records: 0,
        unique_instrument_books: 0,
        eligible_replay_runs: 0,
        candidate_records: 0,
        candidate_scan_truncated: false,
        market_record_limit: 50,
        book_record_limit: 50,
        replay_run_limit: 20,
        candidate_record_limit: 5000,
      },
      market_mix: [],
      stored_market_counts_by_venue: [],
      source_quality: ['polymarket', 'kalshi', 'kraken', 'coinbase_exchange'].map((venue) => ({
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
  fireEvent.click(screen.getByRole('button', { name: 'Coverage & quality' }));
  expect(await screen.findByRole('heading', { name: 'Recent market mix' })).toBeInTheDocument();
  expect(screen.getByText('No eligible market records')).toBeInTheDocument();
  expect(screen.getByText('No quality-valid book pairs')).toBeInTheDocument();
  expect(screen.getByText(/not venue-wide coverage/)).toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', { name: 'Exchanges' }));
  expect(
    await screen.findByText(/Live capture and stored records are held from research use/),
  ).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: 'Coinbase Exchange Spot' })).toBeInTheDocument();
  expect(screen.getByText(/Market Data Terms version 2026-08-07/)).toBeInTheDocument();
  expect(screen.getAllByRole('button', { name: 'Public probe disabled' })).toHaveLength(1);
  screen
    .getAllByRole('button', { name: 'Public probe disabled' })
    .forEach((button) => expect(button).toBeDisabled());

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
  expect(screen.getByText(/0\.51 USD · denomination identity unknown/)).toBeInTheDocument();

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
  await waitFor(() =>
    expect(screen.getByText('Recomputed receipt skew').parentElement).toHaveTextContent(
      'Not recorded',
    ),
  );
  expect(screen.getByText('Recomputed exchange timestamp skew').parentElement).toHaveTextContent(
    'Not recorded',
  );
  expect(screen.getByText('Independent timing gate').parentElement).toHaveTextContent(
    'Not recorded',
  );
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
        ? { ...item, source_run_id: 'a'.repeat(64), source_run_sha256: 'b'.repeat(64) }
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
  expect(screen.getAllByText('red')).toHaveLength(2);

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
  fireEvent.click(screen.getByRole('button', { name: 'Replay & readiness' }));
  expect(await screen.findByText('2 fee metadata observations')).toBeInTheDocument();
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
    market_kind: 'conditional_event',
    lifecycle: 'settled',
    instruments: [],
    quality_flags: [],
    provenance: { response_received_at_utc: '2026-10-26T20:00:00Z' },
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
    '/api/frontier/sources': { items: [source] },
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
  expect(await screen.findByText('Public event context')).toBeInTheDocument();
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

it('submits a bounded Arena replay and displays its integrity-verified comparison', async () => {
  const jobId = 'job-0123456789abcdef01234567';
  const snapshotId = 'a'.repeat(64);
  const snapshotSha256 = 'b'.repeat(64);
  const resultSha256 = 'c'.repeat(64);
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
  let submission: Record<string, unknown> | undefined;
  let timelineSubmission: Record<string, unknown> | undefined;
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
                source_status_sha256s: [],
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
                  source_states: [],
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

  expect(await screen.findByText('No event-time replay jobs')).toBeInTheDocument();
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
    screen.getByText('1 fresh · 0 stale · 0 not yet observed · 0 source-excluded'),
  ).toBeInTheDocument();
  expect(screen.getByText(/No explicit source-state event was pinned/)).toBeInTheDocument();
  expect(timelineSubmission).toEqual({ max_book_age_ms: 5000 });
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
    '/api/frontier/comparisons?limit=30': { items: [], returned: 0, limit: 30, offset: 0 },
    '/api/frontier/readiness': { gates: [] },
  };
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    if (path === '/api/frontier/probe/kalshi/multivariate-events' && init?.method === 'POST') {
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
  expect(
    await screen.findByText(/HTTP request\/body elapsed \(monotonic\): 9\.123 ms/),
  ).toBeInTheDocument();
  expect(fetchMock.mock.calls.some(([input]) => String(input).includes('/probe/'))).toBe(true);
  queryClient.clear();
});
