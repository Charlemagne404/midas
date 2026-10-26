import { expect, test } from '@playwright/test';

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

  await page.getByRole('button', { name: 'Markets', exact: true }).click();
  await expect(page.getByText('No market observations recorded')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(1440);

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByText('No market observations recorded')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});

test('relationship network remains bounded, selectable, and scroll-contained on mobile', async ({
  page,
}) => {
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
    settlement_asset: null,
    payoff: {
      state_ids: [],
      payout_currency: null,
      exhaustive: false,
      verified: false,
      verification_basis: 'fixture, not attested',
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
      ],
      returned: 1,
      limit: 100,
      offset: 0,
    },
    '/api/frontier/runs': { items: [], returned: 0, limit: 30, offset: 0 },
    '/api/frontier/readiness': { gates: [] },
  };
  let submittedReview: Record<string, unknown> | undefined;
  const tradePageRequests: Record<string, unknown>[] = [];
  await page.route('**/api/frontier/**', async (route) => {
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
  await expect(page.getByRole('heading', { name: 'Terminal-state payoff analysis' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Independent arithmetic audit' })).toBeVisible();
  await expect(
    page.getByText('Independent arithmetic agrees for every terminal state.'),
  ).toBeVisible();
  await expect(page.getByText('Modeled payout')).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.getByRole('button', { name: 'Relationship graph', exact: true }).click();

  await page.getByLabel('Relationship graph center market').selectOption('polymarket:election-1');
  await expect(page.getByRole('group', { name: /Relationship network showing 1/ })).toBeVisible();
  await page.getByRole('button', { name: 'Load more neighbors' }).click();
  await expect(page.getByText('Neighborhood page 2')).toBeVisible();
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

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole('group', { name: /Relationship network showing 1/ })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await expect(page.locator('.fr-network-scroll')).toHaveCSS('overflow-x', 'auto');
  await page.getByRole('button', { name: 'Review hypothesis' }).click();
  await expect(page.locator('.fr-review-form')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);

  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.getByRole('button', { name: 'Markets', exact: true }).click();
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
});
