import { expect, test } from '@playwright/test';

const USD_IDENTITY = {
  schema_version: 1,
  kind: 'fiat',
  code: 'USD',
  network_id: null,
  asset_reference: null,
} as const;

test('Frontier workspace uses isolated research state and remains responsive', async ({ page }) => {
  let probeRequests = 0;
  page.on('request', (request) => {
    if (request.url().includes('/api/frontier/probe/')) probeRequests += 1;
  });
  await page.goto('/');
  await page.getByRole('button', { name: 'Frontier', exact: true }).click();

  await expect(page.getByText('FRONTIER · READ-ONLY RESEARCH')).toBeVisible();
  await expect(
    page.getByRole('heading', { name: 'Market relationships, with evidence attached.' }),
  ).toBeVisible();
  await expect(page.getByText('No replay runs yet')).toBeVisible();
  await page.screenshot({ path: test.info().outputPath('frontier-overview.png'), fullPage: true });
  await expect(page.getByText('SYNTHETIC DATA')).toHaveCount(0);
  expect(probeRequests).toBe(0);

  await page.getByRole('button', { name: 'Economic workbench', exact: true }).click();
  await page
    .getByRole('button', { name: 'Compare quoted baseline with current assumptions' })
    .click();
  await expect(page.getByText(/Paired comparison saved/)).toBeVisible();
  await expect(page.getByText('0 matched constructions')).toBeVisible();
  expect(probeRequests).toBe(0);

  await page.getByRole('button', { name: 'Markets', exact: true }).click();
  await expect(page.getByText('No market observations recorded')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(1440);

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByText('No market observations recorded')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});

test('Arena replay history loads without submitting or launching work', async ({ page }) => {
  let replaySubmissions = 0;
  page.on('request', (request) => {
    if (request.method() === 'POST' && request.url().includes('/api/frontier/arena-replay')) {
      replaySubmissions += 1;
    }
  });
  await page.goto('/');
  await page.getByRole('button', { name: 'Frontier', exact: true }).click();
  await page.getByRole('button', { name: 'Replay & readiness', exact: true }).click();

  await expect(page.getByRole('heading', { name: 'Bounded paired replay' })).toBeVisible();
  await expect(page.getByText('No Arena replay jobs')).toBeVisible();
  await expect(page.getByText(/host-wide Arena resource gate/)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Run paired replay in Arena' })).toBeVisible();
  expect(replaySubmissions).toBe(0);
});

test('inspects fixture-only Kalshi settlement arithmetic without probing an exchange', async ({
  page,
}) => {
  let sourceProbeRequests = 0;
  page.on('request', (request) => {
    if (request.url().includes('/api/frontier/probe/')) sourceProbeRequests += 1;
  });
  await page.route('**/api/frontier/markets?limit=100', (route) =>
    route.fulfill({
      json: {
        items: [
          {
            canonical_id: 'kalshi:KX-E2E-MVE',
            source_observation_record_id: 'c'.repeat(64),
            native_market_id: 'KX-E2E-MVE',
            native_event_id: 'KX-E2E-EVENT',
            native_event_title: 'Fixture combo settlement',
            outcome_label: null,
            venue: 'kalshi',
            title: 'Fixture combo settlement',
            market_kind: 'conditional_event',
            lifecycle: 'settled',
            description: '',
            base_asset: null,
            quote_asset: null,
            settlement_asset: 'USD',
            reported_settlement_value_dollars: '0.3750',
            settlement_is_provisional: false,
            payoff: {
              state_ids: ['yes', 'no'],
              payout_currency: 'USD',
              exhaustive: false,
              verified: false,
              verification_basis: 'Fixture only; outcome is not independently verified.',
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
              note: 'Unknown',
            },
            native_fields: {},
            instruments: [],
            selected_components: [
              {
                venue: 'kalshi',
                native_event_id: 'KX-E2E-COMPONENT',
                native_market_id: 'KX-E2E-COMPONENT',
                selected_side: 'yes',
                yes_settlement_value_dollars: '0.3750',
              },
            ],
            quality_flags: ['E2E_FIXTURE_ONLY'],
            provenance: {
              response_received_at_utc: '2026-10-27T12:00:00Z',
              raw_sha256: 'd'.repeat(64),
              observation_id: 'e2e-settlement-observation',
            },
          },
        ],
        returned: 1,
        limit: 100,
        offset: 0,
      },
    }),
  );
  await page.route('**/api/frontier/economics/kalshi-mve-settlement-audit', async (route) => {
    expect(route.request().method()).toBe('POST');
    expect(route.request().postDataJSON()).toEqual({ market_id: 'kalshi:KX-E2E-MVE' });
    await route.fulfill({
      json: {
        audit: {
          state: 'SOURCE REPORTED PRODUCT MATCH',
          component_values: [
            {
              native_market_id: 'KX-E2E-COMPONENT',
              selected_side: 'yes',
              reported_yes_value_dollars: '0.3750',
              selected_position_value_dollars: '0.3750',
            },
          ],
          component_product_dollars: '0.3750',
          reported_settlement_value_dollars: '0.3750',
          missing_component_market_ids: [],
          source_observation_id: 'e2e-settlement-observation',
          source_raw_sha256: 'd'.repeat(64),
          lifecycle: 'settled',
          settlement_is_provisional: false,
          assumptions: ['A matching result checks source-reported settlement arithmetic only.'],
          rule_source_urls: [
            'https://help.kalshi.com/en/articles/13823820-combos',
            'https://help.kalshi.com/en/articles/17515177-protected-nfl-player-markets',
            'https://docs.kalshi.com/api-reference/events/get-multivariate-events',
          ],
        },
        network_calls: 0,
        candidate_generation: false,
        note: 'Fixture only; does not independently verify rules, outcomes, prices, or returns.',
      },
    });
  });

  await page.goto('/');
  await page.getByRole('button', { name: 'Frontier', exact: true }).click();
  await page.getByRole('button', { name: 'Markets', exact: true }).click();
  await page.getByRole('button', { name: 'Inspect', exact: true }).click();
  await page.getByRole('button', { name: 'Audit recorded settlement arithmetic' }).click();

  await expect(page.getByText(/SOURCE REPORTED PRODUCT MATCH/)).toBeVisible();
  await expect(page.getByText(/Recomputed component product: \$0\.3750/)).toBeVisible();
  await expect(page.getByText(/does not independently verify rules/)).toBeVisible();
  expect(sourceProbeRequests).toBe(0);
});

test('relationship network remains bounded, selectable, and scroll-contained on mobile', async ({
  page,
}) => {
  const capitalCandidateId = '8'.repeat(64);
  const graphQueries: string[] = [];
  const marketRecord = (venue: 'polymarket' | 'kalshi', nativeId: string, title: string) => ({
    canonical_id: `${venue}:${nativeId}`,
    source_observation_record_id: venue === 'polymarket' ? 'a'.repeat(64) : 'b'.repeat(64),
    native_market_id: nativeId,
    venue,
    title,
    market_kind: 'binary_event',
    lifecycle: 'open',
    description: '',
    base_asset: null,
    quote_asset: null,
    settlement_asset: 'USD',
    payoff: {
      state_ids: [`${nativeId}-world`],
      payout_currency: 'USD',
      exhaustive: true,
      verified: true,
      verification_basis: 'bounded browser fixture',
    },
    resolution: {
      primary_rule: 'Fixture rules only.',
      secondary_rule: null,
      authority: 'Fixture authority',
      closes_at_utc: '2026-12-01T00:00:00Z',
      settles_at_utc: '2026-12-02T00:00:00Z',
      evidence_sha256: 'b'.repeat(64),
      resolution_fingerprint: `${nativeId}-rules-v1`,
      verified: true,
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
    instruments: [
      { native_instrument_id: `${nativeId}-yes`, label: 'Yes', outcome_id: 'yes' },
      { native_instrument_id: `${nativeId}-no`, label: 'No', outcome_id: 'no' },
    ],
    selected_components:
      venue === 'kalshi'
        ? [
            {
              venue: 'kalshi',
              native_event_id: 'KX-E2E-COMPONENT-EVENT',
              native_market_id: 'KX-E2E-COMPONENT-MARKET',
              selected_side: 'no',
            },
          ]
        : [],
    quality_flags: ['E2E_FIXTURE_ONLY'],
    provenance: {
      response_received_at_utc: '2026-10-26T20:00:00Z',
      raw_sha256: 'a'.repeat(64),
      observation_id: `${venue}-observation`,
    },
  });
  const reason = 'Shared title terms; settlement rules and dates remain unreviewed.';
  const relationship = {
    relationship_id: 'fixture-edge-1',
    left_market_id: 'polymarket:election-1',
    right_market_id: 'kalshi:election-1',
    relationship_type: 'text_candidate',
    state: 'hypothesis',
    confidence: '0.75',
    reason,
    supersedes: null,
    review_target_relationship_id: 'fixture-edge-1',
    latest_review: null,
    evidence: [
      {
        method: 'e2e-test-fixture',
        observation_ids: ['p-fixture', 'k-fixture'],
        source_fields: ['title'],
        details: ['This is a UI fixture only.'],
      },
    ],
  };
  const fixtures: Record<string, unknown> = {
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
        database_bytes: 2048,
        max_bytes: 67_108_864,
      },
      sources: [],
      latest_evidence_at_utc: '2026-10-26T20:00:00Z',
      limitations: ['E2E-only fixture.'],
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
              reason: 'bounded E2E fixture',
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
          adapter_version: 'frontier-kalshi-12',
          public_probe_enabled: true,
          capabilities: [
            {
              capability: 'multivariate_event_discovery',
              supported: true,
              state: 'implemented',
              reason: 'One bounded MVE page for this browser fixture.',
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
    '/api/frontier/markets': {
      items: [
        marketRecord('polymarket', 'election-1', 'Who wins the mayoral election?'),
        marketRecord('kalshi', 'election-1', 'Who wins the mayoral election?'),
      ],
      returned: 2,
      limit: 100,
      offset: 0,
    },
    '/api/frontier/books': { items: [], returned: 0, limit: 100, offset: 0 },
    '/api/frontier/trades': {
      items: [],
      pages: [],
      observation_count: 0,
      trade_count: 0,
      limit: 100,
      offset: 0,
    },
    '/api/frontier/relationships': { items: [relationship], returned: 1, limit: 200 },
    '/api/frontier/graph': {
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
    '/api/frontier/opportunities': {
      items: [
        {
          candidate_id: 'multi-outcome-e2e-fixture',
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
              book_observation_id: 'fixture-red-book',
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
          received_skew_ms: 10,
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
            checks: ['controlled fixture arithmetic checks'],
            message: 'Independent arithmetic agrees for every terminal state.',
          },
          reasons: ['E2E fixture covers every terminal state.'],
          assumptions: ['Fixture only; not a market finding.'],
          evidence_sha256: 'c'.repeat(64),
        },
        {
          candidate_id: capitalCandidateId,
          source_run_id: 'a'.repeat(64),
          source_run_sha256: 'b'.repeat(64),
          family: 'cross_venue_complete_coverage',
          classification: 'INCOMPLETE EVIDENCE',
          hypothetical: true,
          practical_eligibility: false,
          venues: ['kalshi', 'polymarket'],
          legs: [
            {
              venue: 'kalshi',
              native_market_id: 'KX-CAPITAL-FIXTURE',
              instrument_id: 'KX-CAPITAL-FIXTURE:NO',
              outcome_id: 'no',
              quantity: '10',
              quoted_ask: '0.55',
              modeled_buy_price: '0.55',
              modeled_fee: '0',
              quote_currency: 'USD',
              quote_currency_identity: USD_IDENTITY,
              displayed_depth: '10',
              book_observation_id: 'fixture-kalshi-book',
            },
            {
              venue: 'polymarket',
              native_market_id: 'condition:capital-fixture',
              instrument_id: 'token-yes',
              outcome_id: 'yes',
              quantity: '10',
              quoted_ask: '0.35',
              modeled_buy_price: '0.35',
              modeled_fee: '0',
              quote_currency: 'USD',
              quote_currency_identity: USD_IDENTITY,
              displayed_depth: '10',
              book_observation_id: 'fixture-polymarket-book',
            },
          ],
          gross_cost: '9',
          modeled_fees: '0',
          modeled_net_cost: '9',
          outcome_payout_by_state: {},
          gross_pnl_by_state: {},
          net_pnl_by_state: {},
          worst_case_gross_pnl: null,
          worst_case_net_pnl: null,
          capital_by_venue: { kalshi: '5.5', polymarket: '3.5' },
          capital_currency_identity: USD_IDENTITY,
          received_skew_ms: 10,
          exchange_skew_ms: 5,
          timing_verified: false,
          reasons: ['Fixture for isolated virtual capital allocations.'],
          assumptions: ['Fixture only; not a market finding.'],
          evidence_sha256: 'e'.repeat(64),
        },
      ],
      returned: 2,
      limit: 100,
      offset: 0,
    },
    '/api/frontier/runs': { items: [], returned: 0, limit: 30, offset: 0 },
    '/api/frontier/readiness': { gates: [] },
  };
  let submittedReview: Record<string, unknown> | undefined;
  const tradePageRequests: Record<string, unknown>[] = [];
  const mvePageRequests: Record<string, unknown>[] = [];
  const capitalCarryRequests: Record<string, unknown>[] = [];
  await page.route('**/api/frontier/**', async (route) => {
    if (
      route.request().method() === 'GET' &&
      route
        .request()
        .url()
        .endsWith(`/observations/${'e'.repeat(64)}`)
    ) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          observation_id: 'e'.repeat(64),
          raw_sha256: 'f'.repeat(64),
          row_sha256: '1'.repeat(64),
          raw: {
            request_url:
              'https://external-api.kalshi.com/trade-api/v2/events/multivariate?tickers=KX-E2E-MVE-EVENT&limit=1&with_nested_markets=true',
            http_status: 200,
            raw_body: '{"events":[{"title":"MVE event with omitted members"}]}',
            adapter_version: 'frontier-kalshi-12',
          },
        }),
      });
    }
    if (
      route.request().method() === 'POST' &&
      route.request().url().endsWith('/probe/kalshi/multivariate-events')
    ) {
      mvePageRequests.push(route.request().postDataJSON() as Record<string, unknown>);
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          venue: 'kalshi',
          filter_type: 'tickers',
          filter_value: 'KX-E2E-MVE-EVENT',
          event_count: 1,
          market_count: 0,
          events: [
            {
              native_event_id: 'KX-E2E-MVE-EVENT',
              title: 'MVE event with omitted members',
              series_ticker: 'KX-E2E-SERIES',
              collection_ticker: null,
              market_count: 0,
              member_list_state: 'omitted',
            },
          ],
          complete_for_request: false,
          has_more_source_pages: true,
          observation_id: 'e'.repeat(64),
          raw_sha256: 'f'.repeat(64),
          request_count_delta: 1,
          network_calls_bounded_by: 1,
          hypothetical_only: true,
          note: 'One page; nested members were omitted by the source.',
        }),
      });
    }
    if (
      route.request().method() === 'POST' &&
      route.request().url().endsWith('/probe/polymarket/trades')
    ) {
      tradePageRequests.push(route.request().postDataJSON() as Record<string, unknown>);
      const hasMore = tradePageRequests.length === 1;
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          venue: 'polymarket',
          condition_id: `0x${'a'.repeat(64)}`,
          trade_count: 1,
          observation_id: `e2e-trade-page-${tradePageRequests.length}`,
          raw_sha256: 'd'.repeat(64),
          page_limit: 50,
          has_more: hasMore,
          next_cursor: hasMore ? 'e2e-frontier-next' : null,
          source_state: 'available',
          request_count_delta: 1,
          network_calls_bounded_by: 1,
          hypothetical_only: true,
          note: 'One explicit fixture page.',
        }),
      });
    }
    if (
      route.request().method() === 'POST' &&
      route.request().url().endsWith('/opportunities/capital-carry')
    ) {
      capitalCarryRequests.push(route.request().postDataJSON() as Record<string, unknown>);
      expect(route.request().postDataJSON()).toEqual({
        run_id: 'a'.repeat(64),
        run_sha256: 'b'.repeat(64),
        candidate_id: capitalCandidateId,
        annual_rate_bps_by_venue: { kalshi: '1000', polymarket: '1500' },
      });
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          model_version: 'frontier-virtual-capital-carry-1',
          run_id: 'a'.repeat(64),
          run_sha256: 'b'.repeat(64),
          candidate_id: capitalCandidateId,
          candidate_classification: 'INCOMPLETE EVIDENCE',
          classification_unchanged: true,
          hypothetical_only: true,
          capital_currency_identity: USD_IDENTITY,
          venues: [
            {
              venue: 'kalshi',
              capital: '5.5',
              annual_rate_bps: '1000',
              start_at_utc: '2026-10-26T20:00:00Z',
              capital_released_at_utc: '2026-10-27T20:00:00Z',
              duration_seconds: '86400',
              carry_cost: '0.001506849315068493150684931507',
              settlement_evidence: [
                {
                  market_id: 'kalshi:KX-CAPITAL-FIXTURE',
                  venue: 'kalshi',
                  observation_id: 'c'.repeat(64),
                  observation_row_sha256: 'd'.repeat(64),
                  raw_sha256: 'e'.repeat(64),
                  resolution_fingerprint: 'kalshi-fixture-settlement',
                  resolution_evidence_sha256: 'f'.repeat(64),
                  settles_at_utc: '2026-10-27T20:00:00Z',
                },
              ],
            },
            {
              venue: 'polymarket',
              capital: '3.5',
              annual_rate_bps: '1500',
              start_at_utc: '2026-10-26T20:00:00Z',
              capital_released_at_utc: '2026-10-28T20:00:00Z',
              duration_seconds: '172800',
              carry_cost: '0.002876712328767123287671232877',
              settlement_evidence: [
                {
                  market_id: 'polymarket:condition:capital-fixture',
                  venue: 'polymarket',
                  observation_id: '1'.repeat(64),
                  observation_row_sha256: '2'.repeat(64),
                  raw_sha256: '3'.repeat(64),
                  resolution_fingerprint: 'polymarket-fixture-settlement',
                  resolution_evidence_sha256: '4'.repeat(64),
                  settles_at_utc: '2026-10-28T20:00:00Z',
                },
              ],
            },
          ],
          total_carry_cost: '0.004383561643835616438356164384',
          worst_case_gross_pnl_before_carry: null,
          worst_case_gross_pnl_after_carry: null,
          worst_case_net_pnl_before_carry: null,
          worst_case_net_pnl_after_carry: null,
          input_sha256: '5'.repeat(64),
          result_sha256: '6'.repeat(64),
          audit: {
            disposition: 'verified',
            message: 'Independent arithmetic matches the pinned browser fixture.',
            recomputed_total_carry_cost: '0.004383561643835616438356164384',
            checks: ['Source and store-row hashes are pinned.'],
          },
          assumptions: ['Rates are hypothetical fixture assumptions.'],
          limitations: ['No exchange fee, financing offer, or execution is established.'],
        }),
      });
    }
    if (route.request().method() === 'POST' && route.request().url().endsWith('/review')) {
      submittedReview = route.request().postDataJSON() as Record<string, unknown>;
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ review: {}, relationship: {} }),
      });
    }
    const requestUrl = new URL(route.request().url());
    const path = requestUrl.pathname;
    if (path === '/api/frontier/graph') {
      graphQueries.push(requestUrl.searchParams.toString());
    }
    const fixture =
      path === '/api/frontier/graph'
        ? {
            ...(fixtures[path] as Record<string, unknown>),
            center_market_id: requestUrl.searchParams.get('center_market_id'),
            next_cursor:
              requestUrl.searchParams.get('center_market_id') &&
              !requestUrl.searchParams.get('cursor')
                ? 'frontier-page-2'
                : null,
            truncated_by_edge_limit:
              !!requestUrl.searchParams.get('center_market_id') &&
              !requestUrl.searchParams.get('cursor'),
          }
        : fixtures[path];
    if (fixture === undefined) return route.continue();
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(fixture),
    });
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('/');
  await page.getByRole('button', { name: 'Frontier', exact: true }).click();
  await page.getByRole('button', { name: 'Candidates', exact: true }).click();
  const multiOutcomeCandidate = page.locator('.fr-candidate').filter({ hasText: 'KX-THREEWAY' });
  await expect(
    multiOutcomeCandidate.getByRole('heading', { name: 'Terminal-state payoff analysis' }),
  ).toBeVisible();
  await expect(
    multiOutcomeCandidate.getByRole('heading', { name: 'Independent arithmetic audit' }),
  ).toBeVisible();
  await expect(
    page.getByText('Independent arithmetic agrees for every terminal state.'),
  ).toBeVisible();
  await expect(page.getByText('Modeled payout')).toBeVisible();
  const capital = multiOutcomeCandidate.getByRole('region', {
    name: 'Venue-separated virtual funding',
  });
  await expect(capital.getByText(/Modeled requirement: 9 USD/)).toBeVisible();
  const virtualBalance = capital.getByRole('textbox', {
    name: 'Virtual balance allocated to Kalshi USD (fiat:USD)',
  });
  await virtualBalance.fill('8.999999999999999999');
  await expect(capital.locator('.fr-capital-row').getByRole('status')).toHaveText(
    'Virtual funding shortfall at this venue.',
  );
  await virtualBalance.fill('9.000000000000000000');
  await expect(capital.locator('.fr-capital-row').getByRole('status')).toHaveText(
    'Modeled requirement covered at this venue.',
  );
  const crossVenueCapital = page
    .locator('.fr-candidate')
    .filter({ hasText: 'KX-CAPITAL-FIXTURE' })
    .getByRole('region', { name: 'Venue-separated virtual funding' });
  await expect(crossVenueCapital.locator('.fr-capital-row')).toHaveCount(2);
  const kalshiCapital = crossVenueCapital.locator('.fr-capital-row').filter({ hasText: 'Kalshi' });
  const polymarketCapital = crossVenueCapital
    .locator('.fr-capital-row')
    .filter({ hasText: 'Polymarket' });
  await kalshiCapital
    .getByRole('textbox', { name: 'Virtual balance allocated to Kalshi USD (fiat:USD)' })
    .fill('10');
  await polymarketCapital
    .getByRole('textbox', { name: 'Virtual balance allocated to Polymarket USD (fiat:USD)' })
    .fill('0');
  await expect(kalshiCapital.getByRole('status')).toHaveText(
    'Modeled requirement covered at this venue.',
  );
  await expect(polymarketCapital.getByRole('status')).toHaveText(
    'Virtual funding shortfall at this venue.',
  );
  await crossVenueCapital
    .getByRole('textbox', { name: 'Kalshi annual carry rate in basis points' })
    .fill('1000');
  await crossVenueCapital
    .getByRole('textbox', { name: 'Polymarket annual carry rate in basis points' })
    .fill('1500');
  await crossVenueCapital.getByRole('button', { name: 'Evaluate settlement carry' }).click();
  await expect(
    crossVenueCapital.getByText('Independent arithmetic matches the pinned browser fixture.'),
  ).toBeVisible();
  await expect(crossVenueCapital.getByText('INCOMPLETE EVIDENCE · unchanged')).toBeVisible();
  await expect(crossVenueCapital.getByText(/Total modeled carry/)).toBeVisible();
  await expect(crossVenueCapital.locator('.fr-capital-carry-result')).toContainText(
    'row dddddddddddd…',
  );
  expect(capitalCarryRequests).toEqual([
    {
      run_id: 'a'.repeat(64),
      run_sha256: 'b'.repeat(64),
      candidate_id: capitalCandidateId,
      annual_rate_bps_by_venue: { kalshi: '1000', polymarket: '1500' },
    },
  ]);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.getByRole('button', { name: 'Relationship graph', exact: true }).click();

  await page.getByLabel('Relationship graph center market').selectOption('polymarket:election-1');
  await page.getByLabel('Relationship graph depth').selectOption('2');
  await expect(page.getByRole('group', { name: /Relationship network showing 1/ })).toBeVisible();
  await page.getByRole('button', { name: 'Load more neighbors' }).click();
  await expect(page.getByText('Neighborhood page 2')).toBeVisible();
  await expect
    .poll(() =>
      graphQueries.some((query) => query.includes('depth=2') && query.includes('cursor=')),
    )
    .toBe(true);
  await page.getByRole('button', { name: 'Previous page' }).click();
  const edge = page.getByRole('button', { name: /text candidate hypothesis/i });
  await edge.click();
  await expect(edge).toHaveAttribute('aria-pressed', 'true');
  await expect(page.locator('.fr-edge details[open] p')).toHaveText(reason);
  await page.screenshot({
    path: test.info().outputPath('frontier-relationship-network.png'),
    fullPage: true,
  });

  await page.getByRole('button', { name: 'Review hypothesis' }).click();
  await page.getByLabel('Reviewer label').fill('e2e-reviewer');
  await page.getByLabel('Review reason').fill('This fixture remains ambiguous pending rules.');
  await page.getByRole('button', { name: 'Record immutable review' }).click();
  await expect
    .poll(() => submittedReview)
    .toMatchObject({
      decision: 'ambiguous',
      reviewer_label: 'e2e-reviewer',
      evidence_observation_ids: ['a'.repeat(64), 'b'.repeat(64)],
      expected_latest_review_id: null,
    });

  await page.getByRole('button', { name: 'Review hypothesis' }).click();
  await page.getByLabel('Decision').selectOption('verified');
  await page.getByLabel('Relationship claim').selectOption('logical_implication');
  await page.getByLabel('External assertion ID (reference only)').fill('fixture-assertion-e2e');
  await page
    .getByLabel('Complete state mapping (left to right JSON)')
    .fill('{"election-1-world":"election-1-world"}');
  await page.getByLabel('YES implication direction').selectOption('right_to_left');
  await page.getByRole('button', { name: 'Record immutable review' }).click();
  await expect
    .poll(() => submittedReview)
    .toMatchObject({
      decision: 'verified',
      relationship_type: 'logical_implication',
      external_assertion_id: 'fixture-assertion-e2e',
      state_mapping: { 'election-1-world': 'election-1-world' },
      instrument_mapping: {},
      implication_from_market_id: 'kalshi:election-1',
      implication_to_market_id: 'polymarket:election-1',
    });

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole('group', { name: /Relationship network showing 1/ })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await expect(page.locator('.fr-network-scroll')).toHaveCSS('overflow-x', 'auto');
  await page.getByRole('button', { name: 'Review hypothesis' }).click();
  await expect(page.locator('.fr-review-form')).toBeVisible();
  await page.getByLabel('Decision').selectOption('ambiguous');
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);

  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.getByRole('button', { name: 'Markets', exact: true }).click();
  await page.getByRole('button', { name: 'Inspect' }).last().click();
  await expect(page.getByText('Selected components from public MVE metadata')).toBeVisible();
  await expect(page.getByText('KX-E2E-COMPONENT-MARKET')).toBeVisible();
  await expect(page.getByText('Selected NO side')).toBeVisible();
  await expect(
    page.getByText(/do not verify component rules, combo payout, or resolution equivalence/),
  ).toBeVisible();
  await page.getByLabel('Recorded trade market').selectOption(`0x${'a'.repeat(64)}`);
  await page.getByRole('button', { name: 'Capture first page' }).click();
  await expect(page.getByRole('button', { name: 'Capture next page' })).toBeVisible();
  await page.getByRole('button', { name: 'Capture next page' }).click();
  await expect(page.getByText(/source reports no next page/)).toBeVisible();
  expect(tradePageRequests).toEqual([
    { condition_id: `0x${'a'.repeat(64)}`, limit: 50 },
    {
      condition_id: `0x${'a'.repeat(64)}`,
      limit: 50,
      cursor: 'e2e-frontier-next',
    },
  ]);

  await page.getByRole('button', { name: 'Exchanges', exact: true }).click();
  await page.getByLabel('Kalshi multivariate filter type').selectOption('event_ticker');
  await page.getByLabel('Kalshi multivariate filter ticker').fill('KX-E2E-MVE-EVENT');
  await page.getByRole('button', { name: 'Capture one event page' }).click();
  await expect(page.getByText(/nested markets omitted by source/)).toBeVisible();
  await page.getByText('Inspect immutable source response').last().click();
  await expect(page.getByText(/200 · https:\/\/external-api\.kalshi\.com/)).toBeVisible();
  expect(mvePageRequests).toEqual([{ event_ticker: 'KX-E2E-MVE-EVENT' }]);
});
