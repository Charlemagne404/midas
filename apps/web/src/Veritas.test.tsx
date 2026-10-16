import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
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
                latest_veritas_qualification: {
                  job_id: 'job-qualified-1',
                  source_scan_id: 'scan-20261015T083047Z-6f98ffeaecab',
                  finding_id: 'veritas-qualification-v1-0123456789abcdef',
                  experiment_run_id: 'VERITAS-M2-ECO-QUAL-001-V3-RUN-test',
                  snapshot_count: 11,
                  attempted_market_pairs: 440,
                  quality_valid_pairs: 381,
                  unique_market_ids: 155,
                  top_pair_edge_per_share: {
                    count: 381,
                    minimum_per_share: '-0.996',
                    median_nearest_rank_per_share: '-0.020',
                    maximum_per_share: '-0.001',
                    positive_count: 0,
                  },
                  finding_url: '/api/arena/findings/veritas-qualification-v1-0123456789abcdef',
                },
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
                      gross_candidate_evidence_count: 0,
                      gross_candidate_replay_status: 'NO_POSITIVE_CANDIDATES_TO_REPLAY',
                      gross_candidate_replayed_count: 0,
                      gross_candidate_replay_complete: true,
                      positive_states_by_gate: { unchanged_top_ask_gross_sign: 0 },
                    },
                    recent_events: [
                      {
                        recorded_at_utc: '2026-10-15T11:20:00+00:00',
                        state: 'FAILED',
                        stage: 'Qualification stopped before event processing',
                        note: 'Source revision changed while the job was queued',
                        scan_id: 'scan-20261015T110153Z-93de340dd5ce',
                        job_id: 'job-source-drift',
                        finding_id: null,
                        experiment_run_id: null,
                        experiment_sha256: null,
                        dataset_sha256: null,
                        source_revision_sha256: 'e'.repeat(64),
                        strategy_readiness: 'NOT_READY_NO_QUALIFIED_GROSS_CANDIDATE',
                        model_readiness: 'NOT_READY_NO_PUBLIC_OUTCOME_LABELS',
                        positive_states_by_gate: null,
                        recommendation: 'Wait for a new finalized scan.',
                      },
                      {
                        recorded_at_utc: '2026-10-15T11:46:11+00:00',
                        state: 'QUALIFICATION_COMPLETED',
                        stage: 'Published reproducible economic qualification',
                        note: 'Qualification completed on the committed revision',
                        scan_id: 'scan-20261015T113126Z-bf24f3a0706b',
                        job_id: 'job-stable-revision',
                        finding_id: 'veritas-qualification-v1-0e39c79c039a76cf',
                        experiment_run_id: 'VERITAS-M2-ECO-QUAL-001-RUN-b3fc19f69680',
                        experiment_sha256: 'f'.repeat(64),
                        dataset_sha256: 'a'.repeat(64),
                        source_revision_sha256: 'b'.repeat(64),
                        strategy_readiness: 'NOT_READY_NO_QUALIFIED_GROSS_CANDIDATE',
                        model_readiness: 'NOT_READY_NO_PUBLIC_OUTCOME_LABELS',
                        positive_states_by_gate: { unchanged_top_ask_gross_sign: 0 },
                        recommendation: 'Keep no-trade; continue bounded collection.',
                      },
                    ],
                    recent_events_truncated: true,
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
                label_feasibility: {
                  status: 'available',
                  analysis_version: 'veritas-forward-forensics-v1.4',
                  source_kind: 'genuine_public_recording',
                  captured_at_utc: '2026-10-15T19:58:10Z',
                  campaign_id: 'campaign-fixture',
                  decision_count: 10253,
                  market_count: 43,
                  connected_family_count: 37,
                  valid_initial_decisions: 3503,
                  invalid_initial_decisions: 6750,
                  horizons: [
                    {
                      horizon_ms: 5000,
                      scheduled_followups: 10253,
                      valid_initial_decisions: 3503,
                      observed: 473,
                      observed_yield_per_valid_initial: 473 / 3503,
                      censored: 9780,
                      pending: 0,
                      opportunity_target_status: { no_initial_discrepancy: 473 },
                      opportunity_persistence: { null: 473 },
                      execution_ground_truth: { unknown_counterfactual: 473 },
                      markouts: {
                        quoted_exit_value_change: {
                          count: 473,
                          minimum: '0.00',
                          median_nearest_rank: '0.00',
                          maximum: '0.00',
                          positive_count: 0,
                        },
                      },
                    },
                  ],
                  five_second: {
                    observed: 473,
                    opportunity_target_status: { no_initial_discrepancy: 473 },
                    opportunity_persistence: { null: 473 },
                    execution_ground_truth: { unknown_counterfactual: 473 },
                  },
                  economic_observations: {
                    pre_fee_positive_count: 0,
                    pre_fee_edge_per_unit: {
                      count: 3503,
                      minimum: '-0.997',
                      p25_nearest_rank: '-0.015',
                      median_nearest_rank: '-0.01',
                      p75_nearest_rank: '-0.005',
                      maximum: '-0.001',
                    },
                    actual_orders_submitted: 0,
                    actual_fills: 'unknown_counterfactual',
                    realized_money: null,
                  },
                  suitable_strategy_target_support: false,
                  assessment:
                    'Do not train or compare strategy policies on these labels; they are markouts and execution remains unknown.',
                  censor_reasons: { future_observation_unavailable: 10233 },
                  artifact: {
                    id: 'label-feasibility',
                    label: 'Frozen Mission 2 public markout label feasibility',
                    file_sha256: 'a'.repeat(64),
                    url: '/api/veritas/artifacts/label-feasibility',
                  },
                  limitations: ['Public quote survival does not identify hypothetical fills.'],
                },
                baseline_policies: { count: 6, all_abstained: true },
                execution_sensitivity: {
                  quantity_shares_per_leg: '100',
                  fee_model_version: 'veritas-economic-feasibility-v3',
                  fee_collection_medium_for_buy: 'collateral',
                  completed_pair_pnl_single_match_usdc: '1.623991780821917808219178082',
                  completed_pair_pnl_fragmentation_safe_usdc: '-0.369824657534246575342465753',
                  unmatched_leg_loss_usdc: '52.19972602739726027397260274',
                  required_matched_completions_per_unmatched_event: '32.14285111774302117056399166',
                  required_matched_rate_at_1pct_unmatched: '0.3214285111774302117056399166',
                  required_matched_rate_at_5pct_unmatched: '1.607142555887151058528199583',
                  break_even_at_5pct_unmatched_feasible: false,
                  half_depth_single_match_pair_pnl_usdc: '-0.884209260273972602739726027',
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
                    positive_full_depth_gross_by_quantity: {
                      '5': 0,
                      '10': 0,
                      '20': 0,
                      '50': 0,
                      '100': 0,
                    },
                    positive_minimum_notional_by_quantity: {
                      '5': 0,
                      '10': 0,
                      '20': 0,
                      '50': 0,
                      '100': 0,
                    },
                    positive_single_match_by_quantity: {
                      '5': 0,
                      '10': 0,
                      '20': 0,
                      '50': 0,
                      '100': 0,
                    },
                    positive_fragmentation_safe_by_quantity: {
                      '5': 0,
                      '10': 0,
                      '20': 0,
                      '50': 0,
                      '100': 0,
                    },
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
                  measurement_pilot: {
                    study_id: 'VERITAS-M2-COVERAGE-PILOT-001',
                    protocol_version: 'veritas-coverage-pilot-v1',
                    status: 'historical_source_drift',
                    started_at_utc: '2026-10-15T19:00:55.062293+00:00',
                    ends_at_utc: '2026-10-16T19:00:55.062293+00:00',
                    maximum_elapsed_hours: 24,
                    maximum_completed_scans: 48,
                    completed_scans: 1,
                    selected_market_pair_slots: 40,
                    quality_valid_pairs: 32,
                    invalid_pairs: 8,
                    quality_valid_yield: 0.8,
                    distinct_selected_market_ids: 40,
                    skipped_scan_sequences: 0,
                    invalid_reasons: { no_empty_ask_side: 8 },
                    by_cohort_role: {
                      rotating_stratified: {
                        selected: 37,
                        quality_valid: 31,
                        invalid_pairs: 6,
                        quality_valid_yield: 31 / 37,
                        invalid_reasons: { no_empty_ask_side: 6 },
                      },
                      stable_random_control: {
                        selected: 3,
                        quality_valid: 1,
                        invalid_pairs: 2,
                        quality_valid_yield: 1 / 3,
                        invalid_reasons: { no_empty_ask_side: 2 },
                      },
                    },
                    by_selection_stratum: {
                      higher_snapshot_change: {
                        selected: 1,
                        quality_valid: 1,
                        invalid_pairs: 0,
                        distinct_market_count: 1,
                        quality_valid_yield: 1,
                      },
                    },
                    scans: [
                      {
                        scan_id: 'scan-20261015T190055Z-7799523b9d87',
                        snapshot_url:
                          '/api/veritas/observatory/snapshots/scan-20261015T190055Z-7799523b9d87',
                        captured_at_utc: '2026-10-15T19:00:55.062293+00:00',
                        selection_sequence: 30,
                        phase: 'snapshot_change',
                        selected_market_pairs: 40,
                        quality_valid_pairs: 32,
                        quality_valid_yield: 0.8,
                        stable_control_available: 3,
                        stable_control_missing_count: 5,
                        discovered_unique_market_ids: 300,
                        bounded_eligible_markets: 122,
                        excluded_market_ids: 178,
                        positive_top_gross_pairs: 0,
                        role_counts: {
                          rotating_stratified: { selected: 37, quality_valid: 31 },
                          stable_random_control: { selected: 3, quality_valid: 1 },
                        },
                      },
                    ],
                    latest_scan: {
                      scan_id: 'scan-20261015T190055Z-7799523b9d87',
                      snapshot_url:
                        '/api/veritas/observatory/snapshots/scan-20261015T190055Z-7799523b9d87',
                      captured_at_utc: '2026-10-15T19:00:55.062293+00:00',
                      selection_sequence: 30,
                      phase: 'snapshot_change',
                      selected_market_pairs: 40,
                      quality_valid_pairs: 32,
                      quality_valid_yield: 0.8,
                      stable_control_available: 3,
                      stable_control_missing_count: 5,
                      discovered_unique_market_ids: 300,
                      bounded_eligible_markets: 122,
                      excluded_market_ids: 178,
                      positive_top_gross_pairs: 0,
                      role_counts: {
                        rotating_stratified: { selected: 37, quality_valid: 31 },
                        stable_random_control: { selected: 3, quality_valid: 1 },
                      },
                    },
                    latest_control_availability: {
                      status: 'verified',
                      source_scan_id: 'scan-20261015T190055Z-7799523b9d87',
                      snapshot_url:
                        '/api/veritas/observatory/snapshots/scan-20261015T190055Z-7799523b9d87',
                      frozen_control_count: 4,
                      available_in_selected_cohort: 1,
                      missing_from_selected_cohort: 3,
                      missing_by_bounded_discovery_status: {
                        not_returned_by_bounded_query_union: 1,
                        excluded_unsupported_outcome_relationship: 1,
                        eligible_but_not_selected: 1,
                      },
                      bounded_query_union_markets: 4,
                      eligible_markets_in_query_union: 3,
                      selection_basis:
                        'seeded simple random control within bounded discovery union',
                      limitations: [
                        'Absence from the six bounded query responses does not establish that a market is closed or absent from the venue.',
                      ],
                    },
                    implementation_pin_status: 'historical_source_drift',
                    summary_artifact: {
                      id: 'coverage-pilot',
                      label: 'Verified prospective coverage-pilot summary',
                      file_sha256: 'a'.repeat(64),
                      url: '/api/veritas/artifacts/coverage-pilot',
                    },
                    limitations: ['Same-scan role comparison is descriptive.'],
                  },
                  measurement_pilot_v2: {
                    study_id: 'VERITAS-M2-COVERAGE-PILOT-002',
                    protocol_version: 'veritas-coverage-pilot-v2',
                    status: 'not_started',
                    started_at_utc: null,
                    ends_at_utc: null,
                    maximum_elapsed_hours: 24,
                    maximum_completed_scans: 48,
                    completed_scans: 0,
                    selected_market_pair_slots: 0,
                    quality_valid_pairs: 0,
                    quality_valid_yield: null,
                    distinct_selected_market_ids: 0,
                    implementation_pin_status: 'not_started',
                    measurement_diagnostics: {
                      strict_reported_fresh_pairs: 0,
                      reported_update_age_above_5s_by_leg: {},
                      reported_update_timestamp_skew_above_250ms_pairs: 0,
                      reported_update_timestamp_skew_bands: {},
                      batch_atomicity_verified_pairs: 0,
                      sequence_verified_pairs: 0,
                    },
                    latest_scan: null,
                    summary_sha256: null,
                    summary_artifact: null,
                    limitations: [],
                  },
                  market_universe_coverage: {
                    status: 'available',
                    analysis_version: 'veritas-market-universe-coverage-v1',
                    captured_at_utc: '2026-10-15T23:56:00Z',
                    coverage_kind: 'intermittent_public_snapshots',
                    snapshot_count: 40,
                    first_scan_id: 'scan-20261015T055928Z-c9777c1cc300',
                    last_scan_id: 'scan-20261015T233205Z-a2240a38b48f',
                    distinct_gamma_market_ids: 5319,
                    eligible_market_ids_at_least_once: 2077,
                    distinct_condition_ids: 5319,
                    distinct_outcome_asset_ids: 10638,
                    mean_unique_market_ids_per_bounded_union: 298.85,
                    mean_eligible_market_ids_per_bounded_union: 162.07,
                    latest_scan: {
                      scan_id: 'scan-20261015T233205Z-a2240a38b48f',
                      gamma_market_ids: 291,
                      eligible_market_ids: 77,
                      excluded_market_ids: 214,
                      selected_market_ids: 40,
                      distinct_selected_condition_ids: 40,
                      distinct_selected_outcome_asset_ids: 80,
                      distinct_payoff_verified_outcome_asset_ids: 60,
                    },
                    latest_eligible_metadata_distributions: {
                      liquidity: { high: 22, medium: 14, low: 41 },
                      expiry: { near_7d: 50, medium_90d: 12, long: 15 },
                      spread: { tight_le_0_01: 35, medium_le_0_05: 27, wide_gt_0_05: 15 },
                    },
                    selected_slots_by_cohort_role: {
                      rotating_stratified: 1435,
                      stable_random_control: 165,
                    },
                    conditional_selection_probabilities: {
                      count_numeric_conditional_probabilities: 1443,
                      min: 0.0414507772,
                      median: 0.2244897959,
                      max: 1,
                      scope: 'conditional on the bounded query-response union and frozen controls',
                    },
                    total_attempted_market_pairs: 1600,
                    total_quality_valid_market_pairs_current_replay: 1405,
                    positive_top_gross_pairs: 0,
                    candidate_events: 0,
                    capture_vs_current_replay_delta: 27,
                    capture_vs_replay_count_mismatches: [
                      { scan_id: 'scan-20261015T055928Z-c9777c1cc300' },
                    ],
                    source_hashes_verified: true,
                    limitations: ['The bounded discovery union is not a venue-wide denominator.'],
                    artifact: {
                      id: 'market-universe-coverage',
                      label: 'Hash-verified bounded market-universe coverage report',
                      file_sha256: 'b'.repeat(64),
                      url: '/api/veritas/artifacts/market-universe-coverage',
                    },
                  },
                  coverage_design_audit: {
                    status: 'available',
                    analysis_version: 'veritas-coverage-design-audit-v2',
                    captured_at_utc: '2026-10-16T07:36:23Z',
                    study_scan_count: 25,
                    current_pilot_scan_count: 25,
                    source_is_current: true,
                    selected_market_pair_slots: 1000,
                    quality_valid_pairs: 808,
                    role_totals: {
                      rotating_stratified: { selected: 931, valid: 779, yield: 0.8367 },
                      stable_random_control: { selected: 69, valid: 29, yield: 0.4203 },
                    },
                    fully_supported_scan_count: 23,
                    partially_supported_scan_count: 2,
                    unsupported_scan_count: 0,
                    mean_rotating_population_support_fraction: 0.99803757,
                    fully_supported_scan_weighted_yield_mean: 0.82964156,
                    supported_population_scan_yield_range: {
                      minimum: 0.66652098,
                      maximum: 0.95724258,
                    },
                    skipped_selection_sequences: 1,
                    compressed_snapshot_bytes: 15973408,
                    limitations: ['Conditional on bounded query unions.'],
                    artifact: {
                      id: 'coverage-design-audit',
                      label: 'Hash-verified coverage-pilot inclusion-support audit',
                      file_sha256: 'd'.repeat(64),
                      url: '/api/veritas/artifacts/coverage-design-audit',
                    },
                  },
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
                gap_censor_audit: {
                  status: 'verified',
                  analysis_version: 'veritas-censor-gap-reference-audit-v1',
                  captured_at_utc: '2026-10-15T21:52:08Z',
                  campaign_id: 'campaign-fixture',
                  outcome_rows: 5,
                  explicit_recorded_gap_outcomes: 3,
                  book_issue_gap_outcomes: 2,
                  unique_explicit_gap_records_verified: 2,
                  unique_termination_records: 4,
                  unique_book_issue_termination_records_by_source_kind: { discovery_page: 2 },
                  book_issue_direct_gap_causality_verified: false,
                  source_verification: {
                    unique_source_records_verified: 4,
                    unique_finalized_segments_verified: 3,
                    record_offsets_and_hashes_verified: true,
                    active_open_segments_read: false,
                  },
                  journal_hash_chain_reverified: false,
                  artifact: {
                    id: 'censor-gap-audit',
                    label: 'Verified finalized-source gap-censor attribution',
                    file_sha256: 'b'.repeat(64),
                    url: '/api/veritas/artifacts/censor-gap-audit',
                  },
                  limitations: ['The SQLite event hash chain was not reverified.'],
                },
                gap_censor_attribution: {
                  status: 'verified_partial_prefix',
                  analysis_version: 'veritas-censor-gap-attribution-v1',
                  captured_at_utc: '2026-10-16T03:10:11Z',
                  campaign_id: 'campaign-fixture',
                  censored_outcomes_scanned: 7,
                  gap_censored_outcomes: 5,
                  link_status_counts: {
                    candidate_preceding_same_market_gap: 1,
                    exact_recorded_gap_reference_verified_and_indexed: 1,
                    exact_recorded_gap_reference_verified_not_yet_indexed: 1,
                    no_prior_same_market_gap_in_indexed_prefix: 1,
                    termination_after_indexed_prefix: 1,
                  },
                  unique_gap_events_linked: 2,
                  unique_candidate_preceding_gap_events: 1,
                  unique_exact_recorded_gap_events_indexed: 1,
                  candidate_preceding_gap_age_bands: {
                    '0_to_1s': 0,
                    '1_to_60s': 0,
                    '60_to_300s': 0,
                    '300_to_3600s': 0,
                    over_3600s: 1,
                  },
                  same_market_preceding_gap_is_causal_proof: false,
                  gap_detail_index: {
                    complete: false,
                    processed_segment_count: 2,
                    catalog_segment_count: 3,
                    pending_segment_count: 1,
                    pending_source_bytes: 512,
                    indexed_campaign_gap_events: 2,
                    active_segment_read: false,
                  },
                  source_verification: {
                    unique_finalized_segments_verified: 3,
                    unique_source_records_verified: 4,
                    finalized_segment_bytes_hashed: 256,
                  },
                  artifact: {
                    id: 'censor-gap-attribution',
                    label: 'Verified partial-prefix gap-censor attribution',
                    file_sha256: 'd'.repeat(64),
                    url: '/api/veritas/artifacts/censor-gap-attribution',
                  },
                  limitations: ['The indexed gap prefix is incomplete.'],
                },
                finalized_gap_detail: {
                  status: 'catching_up',
                  analysis_version: 'veritas-finalized-reality-gap-detail-v1',
                  generated_at_utc: '2026-10-15T21:51:20+00:00',
                  campaign_id: 'campaign-fixture',
                  processed_segment_count: 1,
                  replayable_catalog_segment_count: 2,
                  catalog_segment_count: 3,
                  empty_finalized_segment_count: 1,
                  pending_segment_count: 1,
                  pending_source_bytes: 512,
                  processed_source_bytes: 256,
                  last_processed_ordinal: 30,
                  readiness: 'catching_up_finalized_source',
                  campaign_window_ns: { start: 100, end_exclusive: 200 },
                  active_segment_read: false,
                  all_period_gap_event_count: 2,
                  all_period_gap_counts_by_reason: { book_resynchronization: 2 },
                  campaign_window_gap_event_count: 0,
                  campaign_window_gap_counts_by_reason: {},
                  campaign_window_gap_events_without_reported_assets: 0,
                  campaign_window_unmapped_affected_asset_count: 0,
                  latest_gap_event: {
                    reason: 'book_resynchronization',
                    received_at_utc: '2026-10-14T10:24:24Z',
                    in_campaign_window: false,
                  },
                  summary_artifact: {
                    id: 'gap-detail-current',
                    label: 'Hash-verified finalized Reality gap-detail prefix',
                    file_sha256: 'c'.repeat(64),
                    url: '/api/veritas/artifacts/gap-detail-current',
                  },
                  limitations: ['Only finalized source segments were read.'],
                },
                artifacts: [
                  { id: 'raw-funnel', label: 'Observed raw opportunity funnel' },
                  {
                    id: 'censoring',
                    label: 'Read-only censoring by market, time, horizon and quality',
                  },
                  {
                    id: 'censor-gap-audit',
                    label: 'Verified finalized-source gap-censor attribution',
                  },
                  {
                    id: 'censor-gap-attribution',
                    label: 'Verified partial-prefix gap-censor attribution',
                  },
                  {
                    id: 'gap-detail-current',
                    label: 'Hash-verified finalized Reality gap-detail prefix',
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
  expect(
    screen.getByRole('heading', { level: 3, name: '24-hour coverage pilot' }),
  ).toBeInTheDocument();
  expect(screen.getByText('31 / 37 · 83.8%')).toBeInTheDocument();
  expect(screen.getByText('1 / 3 · 33.3%')).toBeInTheDocument();
  expect(screen.getByTestId('pilot-control-availability')).toHaveTextContent(
    '1 / 4 selected · 3 missing',
  );
  expect(screen.getByTestId('pilot-control-availability')).toHaveTextContent(
    'not returned by bounded query 1',
  );
  expect(screen.getByTestId('pilot-control-availability')).toHaveTextContent(
    'excluded: unsupported outcome relationship 1',
  );
  expect(screen.getByTestId('pilot-control-availability')).toHaveTextContent(
    'eligible, not selected 1',
  );
  expect(screen.getByText(/Cohort yields are descriptive/)).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Inspect latest pilot snapshot' })).toHaveAttribute(
    'href',
    '/api/veritas/observatory/snapshots/scan-20261015T190055Z-7799523b9d87',
  );
  expect(screen.getByRole('link', { name: 'Inspect hash-verified pilot summary' })).toHaveAttribute(
    'href',
    '/api/veritas/artifacts/coverage-pilot',
  );
  expect(screen.getByTestId('coverage-design-audit')).toHaveTextContent('Current through 25 scans');
  expect(screen.getByTestId('coverage-design-audit')).toHaveTextContent('99.80%');
  expect(screen.getByText('23 full · 2 partial · 0 unsupported scans')).toBeInTheDocument();
  expect(screen.getByTestId('coverage-design-audit')).toHaveTextContent('82.96%');
  expect(screen.getByTestId('pilot-v1-source-drift')).toHaveTextContent(
    'current observer source has changed',
  );
  expect(screen.getByRole('link', { name: 'Inspect audit' })).toHaveAttribute(
    'href',
    '/api/veritas/artifacts/coverage-design-audit',
  );
  expect(screen.getByText('7.1% qualifying measurements')).toBeInTheDocument();
  expect(screen.getByText('Frozen Mission 2 campaign · public markouts')).toBeInTheDocument();
  expect(screen.getByText(/genuine public recording/)).toBeInTheDocument();
  expect(screen.getByText(/473 \/ 3,503/)).toBeInTheDocument();
  expect(
    screen.getByText(/all 473 observed starts had no initial discrepancy/),
  ).toBeInTheDocument();
  expect(
    screen.getByRole('link', { name: /Inspect hash-verified frozen label analysis/ }),
  ).toHaveAttribute('href', '/api/veritas/artifacts/label-feasibility');
  expect(screen.getByText('354')).toBeInTheDocument();
  expect(screen.getAllByText('1,027').length).toBeGreaterThan(0);
  expect(screen.getByText('-52.20 USDC')).toBeInTheDocument();
  expect(
    screen.getByText(/veritas-economic-feasibility-v3 · buy fees charged in collateral at entry/),
  ).toBeInTheDocument();
  expect(screen.getByText('stratified-gamma-page-rotation-v2')).toBeInTheDocument();
  expect(screen.getByText('Latest completed qualification edge distribution')).toBeInTheDocument();
  expect(screen.getByText('-0.020')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Open sealed finding' })).toHaveAttribute(
    'href',
    '/api/arena/findings/veritas-qualification-v1-0123456789abcdef',
  );
  expect(screen.getByText(/40 target · 50 markets max/)).toBeInTheDocument();
  expect(screen.getByText('5,319 market IDs')).toBeInTheDocument();
  expect(screen.getByText('2,077 eligible at least once')).toBeInTheDocument();
  expect(screen.getByText(/Latest selected books/).parentElement).toHaveTextContent(
    '40 markets · 40 conditions · 80 assets',
  );
  expect(
    screen.getByText(/1 saved scan has a capture-to-replay count mismatch of 27 pair counts/),
  ).toBeInTheDocument();
  expect(
    screen.getByRole('link', { name: /Inspect hash-verified A1 coverage artifact/ }),
  ).toHaveAttribute('href', '/api/veritas/artifacts/market-universe-coverage');
  expect(screen.getByText(/They do not provide a venue-wide denominator/)).toBeInTheDocument();
  expect(screen.getByText(/7 HTTP attempts used in latest scan/)).toBeInTheDocument();
  expect(await screen.findByText(/validating finalized observations/)).toBeInTheDocument();
  expect(await screen.findByText(/Does the independent challenge repeat/)).toBeInTheDocument();
  expect(
    await screen.findByText(/Finalized source: catching up finalized source/),
  ).toBeInTheDocument();
  expect(
    (await screen.findAllByText(/Keep no-trade; continue bounded collection/)).length,
  ).toBeGreaterThan(0);
  expect(screen.getByText(/469 quality-valid pairs across 186 markets/)).toBeInTheDocument();
  expect(
    screen.getByText(/Gross candidates: 0 · Source replay: NO POSITIVE CANDIDATES TO REPLAY/),
  ).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Open source and replay evidence' })).toHaveAttribute(
    'href',
    '/api/arena/findings/veritas-qualification-v1-0123456789abcdef',
  );
  fireEvent.click(screen.getByText(/Recent Director history/));
  expect(screen.getByText(/Source revision changed while the job was queued/)).toBeInTheDocument();
  expect(screen.getByText(/VERITAS-M2-ECO-QUAL-001-RUN-b3fc19f69680/)).toBeInTheDocument();
  expect(screen.getByText(/Source revision bbbbbbbbbbbb/)).toBeInTheDocument();
  expect(screen.getByText(/durable Arena archive retains the full stream/)).toBeInTheDocument();
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
  expect(screen.getByText('Frozen campaign censor attribution')).toBeInTheDocument();
  expect(screen.getByText('3 → 2 verified gap records')).toBeInTheDocument();
  expect(screen.getByText('2 → 2 later source records')).toBeInTheDocument();
  expect(
    screen.getByText(/direct causal link to the original gap was not verified/),
  ).toBeInTheDocument();
  expect(screen.getByText('Frozen campaign gap attribution')).toBeInTheDocument();
  expect(screen.getByText('5 / 7')).toBeInTheDocument();
  expect(screen.getByText('Preceding same-market gap candidates')).toBeInTheDocument();
  expect(screen.getByText(/a temporal candidate, not proof of cause/)).toBeInTheDocument();
  expect(screen.getByText('Incremental finalized-source gap detail')).toBeInTheDocument();
  expect(screen.getByText('Campaign-window events in processed prefix')).toBeInTheDocument();
  expect(
    screen.getByText(/zero is not evidence that the campaign had no gaps/),
  ).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Inspect source audit' })).toHaveAttribute(
    'href',
    '/api/veritas/artifacts/censor-gap-audit',
  );
  expect(screen.getByRole('link', { name: 'Inspect attribution' })).toHaveAttribute(
    'href',
    '/api/veritas/artifacts/censor-gap-attribution',
  );
  expect(screen.getByRole('link', { name: 'Inspect verified prefix' })).toHaveAttribute(
    'href',
    '/api/veritas/artifacts/gap-detail-current',
  );
  expect(screen.getByText(/0.000 events \/ panel hour/)).toBeInTheDocument();
  const economicGateTable = screen.getByRole('table', {
    name: 'Positive economic states by quantity and gate',
  });
  expect(within(economicGateTable).getByRole('row', { name: '20 0 0 0 0' })).toBeInTheDocument();
});
