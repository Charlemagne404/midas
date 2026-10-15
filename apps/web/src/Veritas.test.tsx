import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Veritas } from './Veritas';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

it('labels measured evidence and keeps synthetic execution separate from actual fills', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation((input: RequestInfo | URL) =>
      Promise.resolve({
        ok: true,
        json: async () =>
          String(input).includes('/arena/research-activity')
            ? {
                status: 'available',
                state_source: 'persisted Arena manifests',
                active_job_count: 1,
                queued_job_count: 0,
                jobs: [
                  {
                    job_id: 'job-veritas-1',
                    kind: 'veritas_qualification',
                    state: 'RUNNING',
                    phase: 'validating finalized observations',
                    progress: { done: 2, total: 5 },
                    error: null,
                  },
                ],
                active_director_count: 1,
                directors: [
                  {
                    director_id: 'director-1',
                    state: 'RUNNING',
                    research_question: 'Does the independent challenge repeat?',
                    current_stage: 'fresh challenge',
                  },
                  {
                    director_id: 'director-veritas-opportunity-v1',
                    state: 'CURRENT',
                    research_question:
                      'Do new finalized public snapshots contain quality-valid economic candidates?',
                    current_stage: 'Evidence is qualified',
                    source_scan_id: 'scan-20261015T100000Z-6f98ffeaecab',
                    last_qualified_scan_id: 'scan-20261015T100000Z-6f98ffeaecab',
                    strategy_readiness: 'NOT_READY_NO_QUALIFIED_GROSS_CANDIDATE',
                    model_readiness: 'NOT_READY_NO_PUBLIC_OUTCOME_LABELS',
                    independent_confirmation_readiness:
                      'NOT_READY_LESS_THAN_48_HOURS_OR_NO_INDEPENDENT_SEQUENCE',
                    finalized_source_analysis: {
                      state: 'READY',
                      readiness: 'catching_up_finalized_source',
                      status: 'catching_up',
                      campaign_id: 'c'.repeat(64),
                      summary_sha256: 'd'.repeat(64),
                      processed_segment_count: 1072,
                      catalog_segment_count: 3136,
                      pending_segment_count: 2064,
                      pending_source_bytes: 557814406,
                      processed_source_bytes: 224233275,
                      last_processed_ordinal: 122759,
                      period_frame_records: 0,
                      touched_market_frame_states: 0,
                      quality_valid_states: 0,
                      positive_top_ask_pair_states: 0,
                      positive_full_depth_pre_fee_states: 0,
                    },
                    recommendation: 'Keep no-trade; continue bounded collection.',
                    latest_finding: {
                      finding_id: 'veritas-qualification-v1-0123456789abcdef',
                      experiment_run_id: 'VERITAS-M2-ECO-QUAL-001-RUN-test',
                      status: 'no_positive_gross_candidate_observed',
                      snapshot_count: 13,
                      quality_valid_pairs: 469,
                      unique_market_ids: 186,
                      positive_states_by_gate: { unchanged_top_ask_gross_sign: 0 },
                    },
                  },
                ],
                active_schedule_count: 1,
                schedules: [
                  {
                    schedule_id: 'schedule-1',
                    state: 'PENDING',
                    question: 'Run a bounded comparison',
                    steps: [{ name: 'qualification', state: 'PENDING', job_id: null }],
                  },
                ],
                alerts: [],
                invalid_artifact_count: 0,
                limits: {
                  maximum_record_bytes: 262144,
                  maximum_jobs_read: 25,
                  maximum_directors_read: 10,
                  maximum_schedules_read: 10,
                  maximum_alerts_read: 10,
                },
              }
            : {
                status: 'insufficient_independent_evidence',
                captured_at_utc: '2026-10-15T00:00:00Z',
                verdict: 'The selected public panel has no positive gross pair.',
                coverage: {
                  markets: 15,
                  connected_families: 6,
                  utc_days: ['2026-10-14'],
                  source_segments: 1924,
                  source_bytes: 450602772,
                  period_frame_records: 40651,
                  touched_market_frame_states: 31007,
                  quality_valid_states: 29932,
                },
                opportunity_funnel: {
                  quality_valid_states: 29932,
                  positive_top_ask_pair_states: 0,
                  positive_top_with_quantity_depth_states: 0,
                  quantity_depth_complete_states: 29932,
                  positive_full_depth_pre_fee_states: 0,
                  positive_full_depth_minimum_notional_satisfied_states: 0,
                  quantity_requested_shares: '100',
                  pre_fee_top_edge_distribution: {
                    count: 29932,
                    minimum: '-0.96',
                    median_nearest_rank: '-0.01',
                    maximum: '-0.001',
                    positive_count: 0,
                  },
                },
                followup_yield: {
                  valid_initial_decisions: 381,
                  by_horizon: [
                    {
                      horizon_ms: 1000,
                      observed: 27,
                      censored: 354,
                      invalid_initial: 1027,
                      pending: 0,
                      censor_reasons: { invalid_at_decision: 1027 },
                    },
                  ],
                  source_analysis_version: 'veritas-forward-forensics-v1.3',
                },
                followup_censoring: {
                  status: 'available',
                  analysis_version: 'veritas-forward-forensics-v1.3',
                  captured_at_utc: '2026-10-15T08:00:00Z',
                  campaign_id: 'campaign-fixture',
                  decision_count: 1408,
                  market_count: 10,
                  connected_family_count: 6,
                  valid_initial_decisions: 381,
                  invalid_initial_decisions: 1027,
                  utc_days: ['2026-10-15'],
                  query_truncated: false,
                  longest_horizon_ms: 5000,
                  by_market_at_longest_horizon: [
                    {
                      market_id: 'market-a',
                      scheduled_followups: 40,
                      valid_initial_followups: 20,
                      observed: 2,
                      valid_initial_censored: 18,
                      invalid_initial_censored: 20,
                      pending_followups: 0,
                      primary_valid_censor_reason: 'future_observation_not_recorded',
                      primary_valid_censor_count: 10,
                    },
                  ],
                  market_group_count: 10,
                  by_utc_hour_at_longest_horizon: [
                    {
                      utc_hour: '2026-10-15T08:00:00Z',
                      scheduled_followups: 40,
                      valid_initial_followups: 20,
                      observed: 2,
                      valid_initial_censored: 18,
                      invalid_initial_censored: 20,
                      pending_followups: 0,
                      primary_valid_censor_reason: 'future_observation_not_recorded',
                      primary_valid_censor_count: 10,
                    },
                  ],
                  utc_hour_group_count: 1,
                  by_censoring_regime_horizon: {
                    '5000': {
                      items: [
                        {
                          regime: 'future_observation_not_recorded',
                          censored_followups: 10,
                          censor_reasons: { future_observation_unavailable: 10 },
                        },
                      ],
                    },
                  },
                  followup_yield: [],
                  artifact: { id: 'censoring', label: 'Read-only censoring analysis' },
                  limitations: ['Interim correlated evidence.'],
                },
                baseline_policies: { count: 6, all_abstained: true },
                execution_sensitivity: {
                  quantity_shares_per_leg: '100',
                  completed_pair_pnl_single_match_usdc: '1.4178',
                  completed_pair_pnl_fragmentation_safe_usdc: '-0.7822',
                  unmatched_leg_loss_usdc: '50.1959',
                  required_matched_completions_per_unmatched_event: '35.4039',
                  required_matched_rate_at_1pct_unmatched: '0.3540',
                  required_matched_rate_at_5pct_unmatched: '1.7702',
                  break_even_at_5pct_unmatched_feasible: false,
                  half_depth_single_match_pair_pnl_usdc: '-1.0270',
                  rates_are_estimates: false,
                  actual_fills: 'unknown_counterfactual',
                },
                research_status: {
                  hypotheses: 21,
                  experiments: 18,
                  models: 0,
                  candidates: 0,
                  recent_hypotheses: [],
                },
                opportunity_observatory: {
                  status: 'recording',
                  analysis_version: 'veritas-public-observatory-v2',
                  processed_snapshot_count: 12,
                  pending_snapshot_count: 0,
                  readiness: 'collecting_repeated_temporal_coverage',
                  coverage_window_hours: 3,
                  first_captured_at_utc: null,
                  last_captured_at_utc: null,
                  observed_utc_days: [],
                  discovery: {
                    current_bounded_eligible_markets: 167,
                    maximum_bounded_eligible_markets_seen: 167,
                    unique_market_ids_observed: 161,
                    selected_market_observations: 480,
                    latest_phase: 'liquidity',
                    latest_scan_id: 'scan-20261015T090047Z-6f98ffeaecab',
                    latest_snapshot_url: null,
                    latest_selected_markets: 40,
                    latest_stable_control_markets: 6,
                    latest_rotating_markets: 34,
                    latest_by_category: { Politics: 1 },
                    latest_by_liquidity: { high: 1 },
                    latest_by_expiry: { near_7d: 1 },
                    latest_by_spread: { tight_le_0_01: 1 },
                    latest_exclusions: { unsupported_outcome_relationship: 133 },
                    latest_frame_protocol: 'stratified-gamma-page-rotation-v2',
                    latest_offset_bucket_seconds: 1800,
                    latest_query_count: 6,
                    latest_query_candidate_records: 300,
                    latest_unique_market_ids: 300,
                    latest_http_attempts: 7,
                    latest_target_markets: 40,
                    latest_selected_market_rows: [
                      {
                        market_id: 'market-a',
                        primary_category: 'Politics',
                        primary_category_source: 'market.category',
                        cohort_role: 'rotating_stratified',
                        selection_probability: '0.25',
                        selection_probability_basis: 'conditional on bounded query union',
                        selection_stratum: 'high_liquidity',
                      },
                    ],
                    collection_bounds: {
                      target_markets: 40,
                      maximum_markets: 50,
                      gamma_queries_per_scan: 6,
                      gamma_page_limit: 50,
                      maximum_public_read_calls_per_scan: 7,
                      maximum_public_http_attempts_per_scan: 14,
                      maximum_retries_per_public_read: 1,
                      request_timeout_seconds: 15,
                      maximum_response_bytes: 50331648,
                      minimum_request_interval_seconds: 1,
                      maximum_root_bytes: 1073741824,
                      quantity_grid: ['5', '10', '20', '50', '100'],
                    },
                    latest_snapshot_invalid_reasons: {},
                  },
                  opportunity: {
                    quality_valid_pairs: 0,
                    invalid_pairs: 0,
                    positive_top_gross_pairs: 0,
                    positive_full_depth_gross_by_quantity: {},
                    positive_minimum_notional_by_quantity: {},
                    positive_single_match_by_quantity: {},
                    positive_fragmentation_safe_by_quantity: {},
                    candidate_event_count: 0,
                    candidate_market_count: 0,
                    minimum_top_edge_per_share: null,
                    maximum_top_edge_per_share: null,
                  },
                  measurement_comparison: {
                    denominator_selected_market_observations: 0,
                    legacy_freshness_valid_pairs: 0,
                    corrected_freshness_valid_pairs: 0,
                    recovered_valid_pairs: 0,
                    legacy_valid_percent: null,
                    corrected_valid_percent: null,
                    recovered_percentage_points: null,
                    legacy_invalid_reasons: {},
                  },
                  data_quality: {
                    invalid_reasons: {},
                    latest_invalid_reasons: {},
                    reported_update_age_bands_by_leg: { yes: {}, no: {} },
                    reported_update_age_above_5s_by_leg: { yes: 0, no: 0 },
                    reported_update_timestamp_skew_bands: {},
                    reported_update_timestamp_skew_above_250ms_pairs: 0,
                    sampled_activity_bands: {},
                  },
                  market_coverage: {
                    coverage_denominator_snapshots: 0,
                    tracked_markets: 0,
                    sampled_state_comparisons: 0,
                    sampled_state_changes: 0,
                    sampled_state_change_fraction: null,
                    sampled_activity_bands: {},
                    least_observed_markets: [],
                    omitted_market_count: 0,
                  },
                  market_concentration: [],
                  category_coverage: [],
                  recent_candidates: [],
                  summary_artifact: null,
                  limitations: ['No public snapshots yet.'],
                },
                finalized_reality_source: {
                  status: 'not_started',
                  analysis_version: null,
                  processed_segment_count: 0,
                  catalog_segment_count: 0,
                  empty_finalized_segment_count: 0,
                  pending_segment_count: 0,
                  pending_source_bytes: 0,
                  processed_source_bytes: 0,
                  last_processed_ordinal: 0,
                  readiness: 'waiting_for_finalized_source',
                  campaign_window_ns: null,
                  active_segment_read: false,
                  cumulative: {
                    period_frame_records: 0,
                    touched_market_frame_states: 0,
                    quality_valid_states: 0,
                    quality_invalid_reason_counts: {},
                    positive_top_ask_pair_states: 0,
                    positive_full_depth_pre_fee_states: 0,
                    top_edge_distribution: null,
                  },
                  summary_artifact: null,
                  limitations: ['No finalized Reality source segments have been indexed yet.'],
                },
                artifacts: [
                  { id: 'raw-funnel', label: 'Observed raw opportunity funnel' },
                  {
                    id: 'censoring',
                    label: 'Read-only censoring by market, time, horizon and quality',
                  },
                ],
                limitations: ['Displayed liquidity is not guaranteed executable quantity.'],
              },
      }),
    ),
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <Veritas />
    </QueryClientProvider>,
  );

  expect(
    await screen.findByRole('heading', { level: 1, name: /Evidence before conviction/ }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole('heading', { level: 3, name: /Incremental Mission 2 campaign replay/ }),
  ).toBeInTheDocument();
  expect(screen.getByText('7.1% qualifying measurements')).toBeInTheDocument();
  expect(screen.getByText('354')).toBeInTheDocument();
  expect(screen.getAllByText('1,027').length).toBeGreaterThan(0);
  expect(screen.getByText('-1.03 USDC')).toBeInTheDocument();
  expect(screen.getByText('stratified-gamma-page-rotation-v2')).toBeInTheDocument();
  expect(screen.getByText(/40 target · 50 markets max/)).toBeInTheDocument();
  expect(screen.getByText(/7 HTTP attempts used in latest scan/)).toBeInTheDocument();
  expect(await screen.findByText(/validating finalized observations/)).toBeInTheDocument();
  expect(await screen.findByText(/Does the independent challenge repeat/)).toBeInTheDocument();
  expect(
    await screen.findByText(/Finalized source: catching up finalized source/),
  ).toBeInTheDocument();
  expect(await screen.findByText(/Keep no-trade; continue bounded collection/)).toBeInTheDocument();
  expect(screen.getByText(/469 quality-valid pairs across 186 markets/)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Run bounded qualification in Arena' })).toBeEnabled();
  fireEvent.click(screen.getByText(/Inspect latest per-market selection probabilities/));
  expect(screen.getByText(/Inclusion probability 0.25/)).toBeInTheDocument();
  expect(screen.getByText(/market category/)).toBeInTheDocument();
  expect(
    screen.getByText(/Real fills, queue position and profitability remain unknown/),
  ).toBeInTheDocument();
  expect(screen.getByText(/Latest read-only campaign snapshot/)).toBeInTheDocument();
  fireEvent.click(screen.getByText(/Inspect censoring by market and UTC hour/));
  expect(screen.getAllByText('market-a').length).toBeGreaterThanOrEqual(2);
  expect(screen.getByText('2026-10-15T08:00:00Z')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: /Observed raw opportunity funnel/ })).toHaveAttribute(
    'href',
    '/api/veritas/artifacts/raw-funnel',
  );
  expect(screen.getByRole('link', { name: /Read-only censoring by market/ })).toHaveAttribute(
    'href',
    '/api/veritas/artifacts/censoring',
  );
});
