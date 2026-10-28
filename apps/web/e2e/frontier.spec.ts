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
  let collectionPosts = 0;
  page.on('request', (request) => {
    if (request.url().includes('/api/frontier/probe/')) probeRequests += 1;
    if (request.method() === 'POST' && request.url().includes('/api/frontier/collect/')) {
      collectionPosts += 1;
    }
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

  const coverageResponse = page.waitForResponse(
    (response) =>
      response.url().includes('/api/frontier/analytics/coverage') &&
      response.request().method() === 'GET',
  );
  await page.getByRole('button', { name: 'Coverage & quality', exact: true }).click();
  const response = await coverageResponse;
  expect(response.status()).toBe(200);
  expect((await response.json()).network_called).toBe(false);
  await expect(page.getByRole('heading', { name: 'Recent market mix' })).toBeVisible();
  await expect(page.getByText('No eligible market records')).toBeVisible();
  await expect(page.getByText('No quality-valid book pairs')).toBeVisible();
  expect(probeRequests).toBe(0);

  const collectionHistoryResponse = page.waitForResponse(
    (item) =>
      item.url().includes('/api/frontier/collection-runs') && item.request().method() === 'GET',
  );
  await page.getByRole('button', { name: 'Exchanges', exact: true }).click();
  const history = await collectionHistoryResponse;
  expect(history.status()).toBe(200);
  expect((await history.json()).network_called).toBe(false);
  await expect(
    page.getByText('No verified finite collection runs for this source on this page.').first(),
  ).toBeVisible();
  expect(collectionPosts).toBe(0);
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

test('saved Polymarket price samples replay only after explicit user actions', async ({ page }) => {
  let captureRequests = 0;
  let replayRequests = 0;
  let probeRequests = 0;
  let captureRequest: Record<string, unknown> | null = null;
  let replayRequest: Record<string, unknown> | null = null;
  const capturedHistoryId = 'e'.repeat(64);
  const secondHistoryId = '6'.repeat(64);
  const secondHistoryRawHash = '7'.repeat(64);
  let capturedHistoryRecord: Record<string, unknown> | null = null;
  let savedHistoryReplays: Record<string, unknown>[] = [];
  const marketObservationId = 'a'.repeat(64);
  const priceMarket = {
    canonical_id: 'polymarket:e2e-price-history',
    source_observation_record_id: marketObservationId,
    native_market_id: 'e2e-price-history-market',
    native_event_id: null,
    native_event_title: null,
    outcome_label: null,
    venue: 'polymarket',
    title: 'E2E historical price fixture',
    market_kind: 'binary_event',
    lifecycle: 'open',
    description: 'Browser fixture for explicit history actions.',
    base_asset: null,
    quote_asset: 'USDC',
    settlement_asset: 'USDC',
    payoff: {
      state_ids: ['yes', 'no'],
      payout_currency: 'USDC',
      exhaustive: true,
      verified: true,
      verification_basis: 'E2E fixture only.',
    },
    resolution: {
      primary_rule: 'E2E fixture rules.',
      secondary_rule: null,
      authority: 'Fixture authority',
      closes_at_utc: null,
      settles_at_utc: null,
      evidence_sha256: 'b'.repeat(64),
      resolution_fingerprint: 'e2e-history-rules-v1',
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
      note: 'E2E fixture only.',
    },
    native_fields: {},
    instruments: [
      { native_instrument_id: '123456789', label: 'Yes', outcome_id: 'yes' },
      { native_instrument_id: '987654321', label: 'No', outcome_id: 'no' },
    ],
    selected_components: [],
    quality_flags: ['E2E_FIXTURE_ONLY'],
    provenance: {
      response_received_at_utc: '2026-10-27T00:00:00Z',
      raw_sha256: marketObservationId,
      observation_id: marketObservationId,
    },
  };

  page.on('request', (request) => {
    if (request.url().includes('/api/frontier/probe/')) probeRequests += 1;
  });
  await page.route('**/api/frontier/sources', async (route) => {
    await route.fulfill({
      json: {
        items: [
          {
            venue: 'polymarket',
            adapter_version: 'frontier-e2e-history-fixture-v1',
            public_probe_enabled: true,
            capabilities: [
              {
                capability: 'price_history',
                supported: true,
                state: 'implemented',
                reason: 'Intercepted E2E fixture.',
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
    });
  });
  await page.route('**/api/frontier/markets*', async (route) => {
    await route.fulfill({
      json: { items: [priceMarket], returned: 1, limit: 100, offset: 0 },
    });
  });
  await page.route('**/api/frontier/price-history?*', async (route) => {
    const url = new URL(route.request().url());
    const isInstrumentDetail = url.searchParams.has('native_instrument_id');
    const items = isInstrumentDetail
      ? []
      : [
          ...(capturedHistoryRecord ? [capturedHistoryRecord] : []),
          {
            series: {
              venue: 'polymarket',
              native_instrument_id: 'e2e-token-2',
              interval: '1w',
              fidelity_minutes: 1440,
              requested_start_ts: 1792972800,
              requested_end_ts: 1793577600,
              bound_market_observation_id: marketObservationId,
              points: [
                { timestamp_utc: '2026-10-27T00:00:00Z', price: '0.37' },
                { timestamp_utc: '2026-10-28T00:00:00Z', price: '0.44' },
              ],
              source_price_semantics: 'source_reported_price_sample',
              source_limit_note: 'E2E fixture only.',
              provenance: { observation_id: secondHistoryId, raw_sha256: secondHistoryRawHash },
            },
            observation_id: secondHistoryId,
            raw_sha256: secondHistoryRawHash,
            received_at_utc: '2026-10-28T00:02:00Z',
          },
        ];
    await route.fulfill({
      json: {
        items,
        venue: 'polymarket',
        native_instrument_id: isInstrumentDetail ? '123456789' : null,
        returned: items.length,
        limit: isInstrumentDetail ? 1 : 20,
        offset: 0,
        scan_bound: isInstrumentDetail ? 100 : 20,
        has_more: false,
        scan_may_be_incomplete: false,
        source_state: 'recorded observations only',
      },
    });
  });
  await page.route('**/api/frontier/probe/polymarket/price-history', async (route) => {
    captureRequests += 1;
    captureRequest = route.request().postDataJSON() as Record<string, unknown>;
    const body = captureRequest;
    const series = {
      venue: 'polymarket',
      native_instrument_id: body.native_instrument_id,
      interval: body.interval,
      fidelity_minutes: body.fidelity_minutes,
      requested_start_ts: body.start_ts,
      requested_end_ts: body.end_ts,
      bound_market_observation_id: marketObservationId,
      points: [
        {
          timestamp_utc: new Date((Number(body.start_ts) + 60) * 1000).toISOString(),
          price: '0.42',
        },
      ],
      source_price_semantics: 'source_reported_price_sample',
      source_limit_note: 'E2E fixture sample only; OHLC and volume are not inferred.',
      provenance: { observation_id: 'c'.repeat(64), raw_sha256: 'd'.repeat(64) },
    };
    capturedHistoryRecord = {
      series,
      observation_id: capturedHistoryId,
      raw_sha256: 'd'.repeat(64),
      received_at_utc: '2026-10-28T00:01:00Z',
    };
    await route.fulfill({
      json: {
        venue: 'polymarket',
        native_instrument_id: body.native_instrument_id,
        bound_market_id: priceMarket.canonical_id,
        bound_market_observation_id: marketObservationId,
        series,
        point_count: 1,
        observation_id: 'e'.repeat(64),
        raw_sha256: 'd'.repeat(64),
        source_state: 'healthy',
        request_count_delta: 1,
        network_calls_bounded_by: 1,
        hypothetical_only: true,
        note: 'Intercepted E2E fixture; not a live observation.',
      },
    });
  });
  await page.route('**/api/frontier/price-history/replay', async (route) => {
    replayRequests += 1;
    replayRequest = route.request().postDataJSON() as Record<string, unknown>;
    const observationIds = (replayRequest.observation_ids as string[]).slice().sort();
    const runId = observationIds.length === 1 ? 'f'.repeat(64) : '8'.repeat(64);
    const replayResult = {
      schema_version: 1,
      run_id: runId,
      result_sha256: '9'.repeat(64),
      manifest: {
        schema_version: 1,
        input_sha256: '8'.repeat(64),
        observation_ids: observationIds,
        replay_version: 'frontier-price-history-replay-1',
        code_version: 'frontier-e2e-fixture-v1',
        as_of_utc: '2026-10-28T00:02:00Z',
        interpretation: 'descriptive_source_sample_replay',
      },
      series: observationIds.map((observationId) => {
        const firstSeries = observationId === capturedHistoryId;
        const instrumentId = firstSeries ? '123456789' : 'e2e-token-2';
        const rawSha256 = firstSeries ? 'd'.repeat(64) : secondHistoryRawHash;
        return {
          observation_id: observationId,
          raw_sha256: rawSha256,
          venue: 'polymarket',
          native_instrument_id: instrumentId,
          interval: firstSeries ? '1d' : '1w',
          fidelity_minutes: firstSeries ? 60 : 1440,
          requested_start_ts: 1792972800,
          requested_end_ts: 1793577600,
          bound_market_observation_id: marketObservationId,
          point_count: 2,
          first_point_ts: 1793059200,
          last_point_ts: 1793145600,
          observed_point_span_seconds: 86400,
          largest_adjacent_sample_gap_seconds: 86400,
          minimum_sampled_price: firstSeries ? '0.42' : '0.37',
          maximum_sampled_price: firstSeries ? '0.46' : '0.44',
          future_point_timestamp_count: 0,
        };
      }),
      candidate_generation: 'not_performed',
    };
    savedHistoryReplays = [replayResult, ...savedHistoryReplays];
    await route.fulfill({
      json: replayResult,
    });
  });
  await page.route('**/api/frontier/price-history/replays?*', async (route) => {
    await route.fulfill({
      json: {
        items: savedHistoryReplays,
        returned: savedHistoryReplays.length,
        limit: 20,
        offset: 0,
        held_replays_omitted: 0,
        has_more: false,
        scan_may_be_incomplete: false,
        source_state: 'saved deterministic local replay results only',
        network_called: false,
      },
    });
  });
  await page.route('**/api/frontier/price-history/replays/*', async (route) => {
    const runId = new URL(route.request().url()).pathname.split('/').at(-1);
    const selectedRun = savedHistoryReplays.find((item) => item.run_id === runId);
    if (!selectedRun) {
      await route.fulfill({ status: 404, json: { detail: 'Replay fixture not found.' } });
      return;
    }
    await route.fulfill({ json: selectedRun });
  });

  await page.goto('/');
  await page.getByRole('button', { name: 'Frontier', exact: true }).click();
  await page.getByRole('button', { name: 'Markets', exact: true }).click();
  await page.getByRole('button', { name: 'Inspect', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Historical price points' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Capture one series' })).toBeEnabled();
  expect(captureRequests).toBe(0);
  expect(replayRequests).toBe(0);
  expect(probeRequests).toBe(0);

  await page.getByRole('button', { name: 'Capture one series' }).click();
  await expect(page.getByText('0.42', { exact: true })).toBeVisible();
  expect(captureRequests).toBe(1);
  expect(captureRequest).toMatchObject({
    native_instrument_id: '123456789',
    interval: '1d',
    fidelity_minutes: 60,
  });
  expect(Number(captureRequest?.end_ts) - Number(captureRequest?.start_ts)).toBeLessThanOrEqual(
    7 * 24 * 60 * 60,
  );

  await page.getByRole('button', { name: 'Replay saved series' }).click();
  await expect(page.getByText('Deterministic source-sample replay')).toBeVisible();
  await expect(page.getByText(/Candidate generation was not performed/)).toBeVisible();
  expect(replayRequests).toBe(1);
  expect(replayRequest).toEqual({ observation_ids: ['e'.repeat(64)] });
  expect(probeRequests).toBe(1);

  await page.getByRole('button', { name: 'Replay & readiness', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'Multi-series descriptive replay' }),
  ).toBeVisible();
  await expect(page.getByText('candidate generation not performed')).toBeVisible();
  await page.getByRole('checkbox', { name: /123456789/ }).check();
  await page.getByRole('checkbox', { name: /e2e-token-2/ }).check();
  await page.getByRole('button', { name: 'Replay 2 selected series' }).click();
  await expect(page.getByText(secondHistoryRawHash)).toBeVisible();
  expect(replayRequests).toBe(2);
  expect(replayRequest).toEqual({
    observation_ids: [capturedHistoryId, secondHistoryId],
  });
  expect(probeRequests).toBe(1);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByText(secondHistoryRawHash)).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});

test('Arena replay history loads without submitting or launching work', async ({ page }) => {
  let replaySubmissions = 0;
  let discoverySubmissions = 0;
  let timelineSubmissions = 0;
  let sourceProbeRequests = 0;
  page.on('request', (request) => {
    if (request.method() === 'POST' && request.url().includes('/api/frontier/arena-replay')) {
      replaySubmissions += 1;
    }
    if (
      request.method() === 'POST' &&
      request.url().includes('/api/frontier/arena-timeline-replay')
    ) {
      timelineSubmissions += 1;
    }
    if (
      request.method() === 'POST' &&
      request.url().includes('/api/frontier/arena-discovery-comparison')
    ) {
      discoverySubmissions += 1;
    }
    if (request.url().includes('/api/frontier/probe/')) sourceProbeRequests += 1;
  });
  await page.goto('/');
  await page.getByRole('button', { name: 'Frontier', exact: true }).click();
  await page.getByRole('button', { name: 'Replay & readiness', exact: true }).click();

  await expect(page.getByRole('heading', { name: 'Bounded paired replay' })).toBeVisible();
  await expect(page.getByText('No Arena replay jobs')).toBeVisible();
  await expect(page.getByText(/host-wide Arena resource gate/).first()).toBeVisible();
  await expect(page.getByRole('button', { name: 'Run paired replay in Arena' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Discovery scope comparison' })).toBeVisible();
  await expect(page.getByText('No discovery scope comparisons')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Compare scopes in Arena' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Timeline replay' })).toBeVisible();
  await expect(page.getByRole('group', { name: 'Recorded adapter health' })).toBeVisible();
  await expect(page.getByText('No verified health checkpoints')).toBeVisible();
  await expect(page.getByText('No event-time replay jobs')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Replay saved timeline' })).toBeDisabled();
  expect(replaySubmissions).toBe(0);
  expect(discoverySubmissions).toBe(0);
  expect(timelineSubmissions).toBe(0);
  expect(sourceProbeRequests).toBe(0);
});

test('saved Arena discovery artifact exposes scoped candidate evidence', async ({ page }) => {
  const jobId = `job-${'a'.repeat(24)}`;
  const candidateId = 'f'.repeat(64);
  const replayIds = ['1', '2', '3', '4'].map((value) => value.repeat(64));
  const comparison = {
    comparison_id: '9'.repeat(64),
    normalized_input_sha256: 'a'.repeat(64),
    result_sha256: 'b'.repeat(64),
    code_version: 'frontier-e2e-fixture-v1',
    as_of_utc: '2026-10-27T00:00:00Z',
    arms: [
      {
        scope: 'polymarket_only',
        venues: ['polymarket'],
        replay_run_ids: [replayIds[0]],
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
        replay_run_ids: [replayIds[1], replayIds[2]],
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
        replay_run_ids: [replayIds[3]],
        market_count: 2,
        instrument_count: 4,
        book_count: 4,
        observed_instrument_count: 4,
        relationship_count: 1,
        candidates: [
          {
            candidate_id: candidateId,
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
        classification_count_delta: { 'CONDITIONAL ECONOMIC OPPORTUNITY': 1 },
      },
    ],
  };
  await page.route('**/api/arena/frontier-discovery-comparisons*', async (route) => {
    await route.fulfill({
      json: {
        items: [
          {
            job_id: jobId,
            state: 'COMPLETED',
            created_at: 1_793_049_600,
            updated_at: 1_793_049_601,
            elapsed_seconds: 0.17,
            progress: { done: 3, total: 3 },
            phase: 'publishing-hash-verified-discovery-result',
            error: null,
            snapshot_id: 'c'.repeat(64),
            snapshot_sha256: 'c'.repeat(64),
            runtime_profile: null,
            result: {
              comparison_id: comparison.comparison_id,
              frontier_discovery_sha256: comparison.result_sha256,
            },
          },
        ],
        limit: 20,
        scanned: 1,
        scan_bound: 500,
        scan_may_be_incomplete: false,
        research_only: true,
      },
    });
  });
  await page.route(`**/api/arena/jobs/${jobId}/frontier-discovery`, async (route) => {
    await route.fulfill({
      json: {
        artifact: {
          comparison,
          replays: replayIds.map((runId, index) => ({
            run_id: runId,
            candidates:
              index === 3
                ? [
                    {
                      candidate_id: candidateId,
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
                          quote_currency_identity: USD_IDENTITY,
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
                          quote_currency_identity: USD_IDENTITY,
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
                      capital_currency_identity: USD_IDENTITY,
                      practical_eligibility: false,
                      received_skew_ms: null,
                      exchange_skew_ms: null,
                      timing_verified: false,
                      independent_audit: {
                        disposition: 'verified',
                        input_sha256: '2'.repeat(64),
                        checks: ['Arithmetic independently recomputed.'],
                        message: 'This fixture verifies arithmetic only.',
                      },
                      assumptions: ['Explicit E2E fixture; not observed exchange evidence.'],
                      reasons: ['External mapping and execution remain conditional.'],
                      evidence_sha256: '3'.repeat(64),
                    },
                  ]
                : [],
          })),
          snapshot_id: 'c'.repeat(64),
          snapshot_sha256: 'c'.repeat(64),
          result_sha256: comparison.result_sha256,
        },
        research_only: true,
        orders_submitted: false,
        authenticated_requests: false,
        integrity_verified: true,
      },
    });
  });

  await page.goto('/');
  await page.getByRole('button', { name: 'Frontier', exact: true }).click();
  await page.getByRole('button', { name: 'Replay & readiness', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Inspect modeled constructions' })).toBeVisible();
  await page.getByText(/Inspect candidate/).click();
  await expect(page.getByText('Terminal outcomes under the pinned payoff model')).toBeVisible();
  await expect(page.getByText(/Hypothetical replay only/)).toBeVisible();
  await expect(page.getByText('0.450000000000000001 USD').first()).toBeVisible();
  await page.getByText(/Independent audit, assumptions, and evidence hashes/).click();
  await expect(page.getByText('Arithmetic independently recomputed.')).toBeVisible();
  await expect(page.getByText(/not observed exchange evidence/)).toBeVisible();
});

test('joint-state replay submits an explicit fixture map without probing a venue', async ({
  page,
}) => {
  let sourceProbeRequests = 0;
  let jointReplayRequests = 0;
  page.on('request', (request) => {
    if (request.url().includes('/api/frontier/probe/')) sourceProbeRequests += 1;
  });
  const eventMarket = (key: string, title: string, observation: string) => ({
    canonical_id: `polymarket:${key}`,
    source_observation_record_id: observation.repeat(64),
    native_market_id: key,
    native_event_id: null,
    native_event_title: null,
    outcome_label: null,
    venue: 'polymarket',
    title,
    market_kind: 'binary_event',
    lifecycle: 'open',
    description: 'Explicit E2E fixture only.',
    base_asset: null,
    quote_asset: null,
    settlement_asset: 'USD',
    payoff: {
      state_ids: ['no', 'yes'],
      payout_currency: 'USD',
      exhaustive: true,
      verified: true,
      verification_basis: 'E2E fixture only.',
    },
    resolution: {
      primary_rule: 'Fixture-only resolution.',
      secondary_rule: null,
      authority: 'Fixture authority',
      closes_at_utc: '2026-12-01T00:00:00Z',
      settles_at_utc: '2026-12-02T00:00:00Z',
      evidence_sha256: 'c'.repeat(64),
      resolution_fingerprint: `${key}-rules-v1`,
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
      note: 'Unknown in fixture.',
    },
    native_fields: {},
    instruments: [
      { native_instrument_id: `${key}-yes`, label: 'Yes', outcome_id: 'yes' },
      { native_instrument_id: `${key}-no`, label: 'No', outcome_id: 'no' },
    ],
    quality_flags: ['E2E_FIXTURE_ONLY'],
    provenance: {
      response_received_at_utc: '2026-10-27T12:00:00Z',
      raw_sha256: 'd'.repeat(64),
      observation_id: observation.repeat(64),
    },
  });
  await page.route('**/api/frontier/markets?limit=100', (route) =>
    route.fulfill({
      json: {
        items: [
          eventMarket('event-a', 'Fixture event A', 'a'),
          eventMarket('event-b', 'Fixture event B', 'b'),
        ],
        returned: 2,
        limit: 100,
        offset: 0,
      },
    }),
  );
  await page.route('**/api/frontier/replay/joint-state', async (route) => {
    expect(route.request().method()).toBe('POST');
    jointReplayRequests += 1;
    const payload = route.request().postDataJSON() as {
      mapping: Record<string, unknown>;
      scenario: Record<string, unknown>;
    };
    expect(payload.mapping).not.toHaveProperty('mapping_id');
    expect(payload.mapping).toMatchObject({
      external_assertion_id: 'fixture-shared-event-reference',
      market_ids: ['polymarket:event-a', 'polymarket:event-b'],
      joint_state_ids: ['world-no', 'world-yes'],
      evidence_observation_ids: ['a'.repeat(64), 'b'.repeat(64)],
      semantic_status: 'externally_asserted_unverified',
      state_by_market: {
        'polymarket:event-a': { 'world-no': 'no', 'world-yes': 'yes' },
        'polymarket:event-b': { 'world-no': 'no', 'world-yes': 'yes' },
      },
    });
    await route.fulfill({
      json: {
        run_id: 'e'.repeat(64),
        manifest: { joint_state_mappings: [{ mapping_id: 'f'.repeat(64) }] },
        candidates: [],
        classification_counts: {},
      },
    });
  });

  await page.goto('/');
  await page.getByRole('button', { name: 'Frontier', exact: true }).click();
  await page.getByRole('button', { name: 'Replay & readiness', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Assert a joint-state map' })).toBeVisible();
  const markets = page.getByRole('listbox', {
    name: 'Stored event markets for joint-state replay',
  });
  await markets.selectOption(['polymarket:event-a', 'polymarket:event-b']);
  await page.getByLabel('External assertion reference').fill('fixture-shared-event-reference');
  await page.getByLabel('Assertion time').fill('2026-10-29T12:00');
  await page.getByLabel('Joint-state IDs').fill('world-no\nworld-yes');
  await page.getByLabel('world-no local payoff state for Fixture event A').selectOption('no');
  await page.getByLabel('world-yes local payoff state for Fixture event A').selectOption('yes');
  await page.getByLabel('world-no local payoff state for Fixture event B').selectOption('no');
  await page.getByLabel('world-yes local payoff state for Fixture event B').selectOption('yes');
  const submit = page.getByRole('button', { name: 'Replay conditional basket' });
  await expect(submit).toBeEnabled();
  await submit.click();

  await expect(page.getByRole('status').getByText('Conditional replay saved')).toBeVisible();
  expect(jointReplayRequests).toBe(1);
  expect(sourceProbeRequests).toBe(0);
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
  const fundingCurrencyRequests: Record<string, unknown>[] = [];
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
        post_settlement_delay_seconds_by_venue: { kalshi: '0', polymarket: '0' },
      });
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          schema_version: 2,
          model_version: 'frontier-virtual-capital-carry-2',
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
              post_settlement_delay_seconds: 0,
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
              post_settlement_delay_seconds: 0,
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
    if (
      route.request().method() === 'POST' &&
      route.request().url().endsWith('/opportunities/funding-currency-sensitivity')
    ) {
      const request = route.request().postDataJSON() as Record<string, unknown>;
      fundingCurrencyRequests.push(request);
      expect(request).toEqual({
        run_id: 'a'.repeat(64),
        run_sha256: 'b'.repeat(64),
        candidate_id: capitalCandidateId,
        venues: [
          {
            venue: 'kalshi',
            funding_currency_identity: {
              schema_version: 1,
              kind: 'fiat',
              code: 'EUR',
              network_id: null,
              asset_reference: null,
            },
            balance_amount: '6',
            target_units_per_funding_unit: '1.1',
            conversion_fee_bps: '25',
          },
          {
            venue: 'polymarket',
            funding_currency_identity: USD_IDENTITY,
            balance_amount: '4',
            target_units_per_funding_unit: '1',
            conversion_fee_bps: '0',
          },
        ],
      });
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          schema_version: 2,
          model_version: 'frontier-virtual-funding-currency-2',
          run_id: 'a'.repeat(64),
          run_sha256: 'b'.repeat(64),
          candidate_id: capitalCandidateId,
          candidate_evidence_sha256: 'e'.repeat(64),
          candidate_classification: 'INCOMPLETE EVIDENCE',
          candidate_practical_eligibility: false,
          classification_unchanged: true,
          practical_eligibility_unchanged: true,
          candidate_economics_unchanged: true,
          hypothetical_only: true,
          target_currency_identity: USD_IDENTITY,
          unresolved_candidate_fee_leg_count: 2,
          venues: [
            {
              venue: 'kalshi',
              required_capital_target: '5.5',
              funding_currency_identity: {
                schema_version: 1,
                kind: 'fiat',
                code: 'EUR',
                network_id: null,
                asset_reference: null,
              },
              balance_amount: '6',
              target_units_per_funding_unit: '1.1',
              conversion_fee_bps: '25',
              required_funding_amount:
                '5.012531328320802005012531328320802005012531328320802005012531328320802005012531328320802005012531328321',
              available_capital_target_after_fee: '6.5835',
              conversion_fee_target_amount:
                '0.013784461152882205513784461152882205513784461152882205513784461152882205513784461152882205513784461153',
              shortfall_target: '0',
              shortfall_funding: '0',
              model_requirement_covered: true,
            },
            {
              venue: 'polymarket',
              required_capital_target: '3.5',
              funding_currency_identity: USD_IDENTITY,
              balance_amount: '4',
              target_units_per_funding_unit: '1',
              conversion_fee_bps: '0',
              required_funding_amount: '3.5',
              available_capital_target_after_fee: '4',
              conversion_fee_target_amount: '0',
              shortfall_target: '0',
              shortfall_funding: '0',
              model_requirement_covered: true,
            },
          ],
          total_conversion_fee_target:
            '0.013784461152882205513784461152882205513784461152882205513784461152882205513784461152882205513784461153',
          pnl_scenario: {
            status: 'unavailable',
            reason: 'The saved candidate has no verified independent economic audit.',
            funding_input_sha256: 'f'.repeat(64),
            target_currency_identity: USD_IDENTITY,
            modeled_conversion_fee_target:
              '0.013784461152882205513784461152882205513784461152882205513784461152882205513784461152882205513784461153',
            candidate_net_pnl_by_state: {},
            net_pnl_after_conversion_by_state: {},
            worst_case_net_pnl_after_conversion: null,
            all_outcomes_positive_after_conversion: null,
            audit: {
              algorithm_version: 'frontier-independent-funding-pnl-audit-1',
              disposition: 'unavailable',
              input_sha256: 'f'.repeat(64),
              candidate_audit_input_sha256: null,
              recomputed_net_pnl_after_conversion_by_state: {},
              recomputed_worst_case_net_pnl_after_conversion: null,
              checks: [],
              message: 'The saved candidate has no verified independent economic audit.',
            },
          },
          input_sha256: 'f'.repeat(64),
          result_sha256: '1'.repeat(64),
          audit: {
            disposition: 'verified',
            input_sha256: 'f'.repeat(64),
            recomputed_total_conversion_fee_target:
              '0.013784461152882205513784461152882205513784461152882205513784461152882205513784461152882205513784461153',
            checks: ['Funding conversion arithmetic is independently reproduced.'],
            message: 'Independent funding arithmetic matches the pinned browser fixture.',
          },
          assumptions: ['User-entered virtual FX assumptions only.'],
          limitations: ['No live rate, conversion availability, or candidate fee is established.'],
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
      post_settlement_delay_seconds_by_venue: { kalshi: '0', polymarket: '0' },
    },
  ]);
  const fundingCurrency = page
    .locator('.fr-candidate')
    .filter({ hasText: 'KX-CAPITAL-FIXTURE' })
    .locator('.fr-fx-sensitivity');
  const kalshiFundingCode = fundingCurrency.getByRole('textbox', {
    name: 'Kalshi funding asset code',
  });
  await kalshiFundingCode.fill('EUR');
  const kalshiFundingRate = fundingCurrency.getByRole('textbox', {
    name: 'Kalshi target units per funding unit',
  });
  const kalshiFundingFee = fundingCurrency.getByRole('textbox', {
    name: 'Kalshi conversion fee in basis points',
  });
  await expect(kalshiFundingRate).toHaveValue('');
  await expect(kalshiFundingFee).toHaveValue('');
  await fundingCurrency
    .getByRole('textbox', { name: 'Kalshi funding currency virtual balance' })
    .fill('6');
  await kalshiFundingRate.fill('1.1');
  await kalshiFundingFee.fill('25');
  await fundingCurrency
    .getByRole('textbox', { name: 'Polymarket funding currency virtual balance' })
    .fill('4');
  await fundingCurrency
    .getByRole('button', { name: 'Evaluate virtual funding sensitivity' })
    .click();
  await expect(
    fundingCurrency.getByText('Independent funding arithmetic matches the pinned browser fixture.'),
  ).toBeVisible();
  await expect(
    fundingCurrency.getByText('INCOMPLETE EVIDENCE · classification unchanged'),
  ).toBeVisible();
  await expect(fundingCurrency.getByText(/unresolved fees remain/)).toHaveCount(2);
  await expect(
    fundingCurrency.getByRole('region', { name: 'Conversion-adjusted outcome P&L scenario' }),
  ).toContainText('Outcome P&L is unavailable');
  expect(fundingCurrencyRequests).toHaveLength(1);
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
