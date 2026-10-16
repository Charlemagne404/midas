import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowUpRight, BarChart3, Database, ShieldCheck, TrendingDown } from 'lucide-react';
import { api } from './api';
import './veritas.css';

type Horizon = {
  horizon_ms: number;
  observed: number;
  censored: number;
  invalid_initial: number;
  pending: number;
  censor_reasons: Record<string, number>;
};

type CensoringDimensionRow = {
  scheduled_followups: number;
  valid_initial_followups: number;
  observed: number;
  valid_initial_censored: number;
  invalid_initial_censored: number;
  pending_followups: number;
  primary_valid_censor_reason: string | null;
  primary_valid_censor_count: number;
} & ({ market_id: string; utc_hour?: never } | { utc_hour: string; market_id?: never });

type FollowupCensoring = {
  status: string;
  analysis_version: string;
  captured_at_utc: string;
  campaign_id: string;
  decision_count: number;
  market_count: number;
  connected_family_count: number;
  valid_initial_decisions: number;
  invalid_initial_decisions: number;
  utc_days: string[];
  query_truncated: boolean;
  longest_horizon_ms: number;
  by_market_at_longest_horizon: CensoringDimensionRow[];
  market_group_count: number;
  by_utc_hour_at_longest_horizon: CensoringDimensionRow[];
  utc_hour_group_count: number;
  by_censoring_regime_horizon: Record<
    string,
    {
      items: Array<{
        regime: string;
        censored_followups: number;
        censor_reasons: Record<string, number>;
      }>;
    }
  >;
  followup_yield: Horizon[];
  artifact: Artifact;
  limitations: string[];
};

type Artifact = { id: string; label: string };

type GapCensorAudit = {
  status: string;
  analysis_version: string;
  captured_at_utc: string;
  campaign_id: string;
  outcome_rows: number;
  explicit_recorded_gap_outcomes: number;
  book_issue_gap_outcomes: number;
  unique_explicit_gap_records_verified: number;
  unique_termination_records: number;
  unique_book_issue_termination_records_by_source_kind: Record<string, number>;
  book_issue_direct_gap_causality_verified: boolean;
  source_verification: {
    unique_source_records_verified: number;
    unique_finalized_segments_verified: number;
    record_offsets_and_hashes_verified: boolean;
    active_open_segments_read: boolean;
  };
  journal_hash_chain_reverified: boolean | null;
  artifact: Artifact & { file_sha256: string; url: string };
  limitations: string[];
};

type FinalizedGapDetail = {
  status: string;
  analysis_version: string;
  generated_at_utc: string;
  campaign_id: string;
  processed_segment_count: number;
  replayable_catalog_segment_count: number;
  catalog_segment_count: number;
  empty_finalized_segment_count: number;
  pending_segment_count: number;
  pending_source_bytes: number;
  processed_source_bytes: number;
  last_processed_ordinal: number;
  readiness: string;
  campaign_window_ns: { start: number; end_exclusive: number };
  active_segment_read: boolean;
  all_period_gap_event_count: number;
  all_period_gap_counts_by_reason: Record<string, number>;
  campaign_window_gap_event_count: number;
  campaign_window_gap_counts_by_reason: Record<string, number>;
  campaign_window_gap_events_without_reported_assets: number;
  campaign_window_unmapped_affected_asset_count: number;
  latest_gap_event: {
    reason: string;
    received_at_utc: string;
    in_campaign_window: boolean;
  } | null;
  summary_artifact: Artifact & { file_sha256: string; url: string };
  limitations: string[];
};

type LabelFeasibilityHorizon = {
  horizon_ms: number;
  scheduled_followups: number;
  valid_initial_decisions: number;
  observed: number;
  observed_yield_per_valid_initial: number | null;
  censored: number;
  pending: number;
  opportunity_target_status: Record<string, number>;
  opportunity_persistence: Record<string, number>;
  execution_ground_truth: Record<string, number>;
  markouts: Record<
    string,
    {
      count: number;
      minimum: string;
      median_nearest_rank: string;
      maximum: string;
      positive_count: number;
    }
  >;
};

type LabelFeasibility = {
  status: string;
  analysis_version: string;
  source_kind: string;
  captured_at_utc: string;
  campaign_id: string;
  decision_count: number;
  market_count: number;
  connected_family_count: number;
  valid_initial_decisions: number;
  invalid_initial_decisions: number;
  horizons: LabelFeasibilityHorizon[];
  five_second: {
    observed: number;
    opportunity_target_status: Record<string, number>;
    opportunity_persistence: Record<string, number>;
    execution_ground_truth: Record<string, number>;
  };
  economic_observations: {
    pre_fee_positive_count: number;
    pre_fee_edge_per_unit: {
      count: number;
      minimum: string;
      p25_nearest_rank: string;
      median_nearest_rank: string;
      p75_nearest_rank: string;
      maximum: string;
    };
    actual_orders_submitted: number;
    actual_fills: string;
    realized_money: null;
  };
  suitable_strategy_target_support: boolean;
  assessment: string | null;
  censor_reasons: Record<string, number>;
  artifact: Artifact & { file_sha256: string; url: string };
  limitations: string[];
};

type ObservatoryCandidate = {
  scan_id: string;
  market_id: string;
  question: string;
  positive_full_depth_minimum_notional_quantities: string[];
  positive_single_match_quantities: string[];
  positive_fragmentation_safe_quantities: string[];
  snapshot_url: string;
};

type CoveragePilotCohort = {
  selected: number;
  quality_valid: number;
  invalid_pairs: number;
  quality_valid_yield: number | null;
  invalid_reasons?: Record<string, number>;
};

type CoveragePilotScan = {
  scan_id: string;
  snapshot_url: string;
  captured_at_utc: string;
  selection_sequence: number;
  phase: string;
  selected_market_pairs: number;
  quality_valid_pairs: number;
  quality_valid_yield: number | null;
  stable_control_available: number;
  stable_control_missing_count: number;
  discovered_unique_market_ids: number;
  bounded_eligible_markets: number;
  excluded_market_ids: number;
  positive_top_gross_pairs: number;
  role_counts: Record<string, { selected: number; quality_valid: number }>;
};

type CoveragePilotControlAvailability = {
  status: string;
  source_scan_id: string | null;
  snapshot_url: string | null;
  frozen_control_count?: number;
  available_in_selected_cohort?: number;
  missing_from_selected_cohort?: number;
  missing_by_bounded_discovery_status?: Record<string, number>;
  bounded_query_union_markets?: number;
  eligible_markets_in_query_union?: number;
  selection_basis?: string | null;
  limitations?: string[];
  reason?: string;
};

type CoveragePilot = {
  study_id: string;
  protocol_version: string;
  status: string;
  started_at_utc: string | null;
  ends_at_utc: string | null;
  maximum_elapsed_hours: number;
  maximum_completed_scans: number;
  completed_scans: number;
  selected_market_pair_slots: number;
  quality_valid_pairs: number;
  invalid_pairs: number;
  quality_valid_yield: number | null;
  distinct_selected_market_ids: number;
  skipped_scan_sequences: number;
  invalid_reasons: Record<string, number>;
  by_cohort_role: Record<string, CoveragePilotCohort>;
  by_selection_stratum: Record<string, CoveragePilotCohort & { distinct_market_count: number }>;
  scans: CoveragePilotScan[];
  latest_scan: CoveragePilotScan | null;
  latest_control_availability: CoveragePilotControlAvailability | null;
  summary_artifact: (Artifact & { file_sha256: string; url: string }) | null;
  limitations: string[];
};

type MarketUniverseCoverage = {
  status: string;
  analysis_version: string;
  captured_at_utc: string;
  coverage_kind: string;
  snapshot_count: number;
  first_scan_id: string;
  last_scan_id: string;
  distinct_gamma_market_ids: number;
  eligible_market_ids_at_least_once: number;
  distinct_condition_ids: number;
  distinct_outcome_asset_ids: number;
  mean_unique_market_ids_per_bounded_union: number;
  mean_eligible_market_ids_per_bounded_union: number;
  latest_scan: {
    scan_id: string;
    gamma_market_ids: number;
    eligible_market_ids: number;
    excluded_market_ids: number;
    selected_market_ids: number;
    distinct_selected_condition_ids: number;
    distinct_selected_outcome_asset_ids: number;
    distinct_payoff_verified_outcome_asset_ids: number;
  };
  latest_eligible_metadata_distributions: {
    liquidity: Record<string, number>;
    expiry: Record<string, number>;
    spread: Record<string, number>;
  };
  selected_slots_by_cohort_role: Record<string, number>;
  conditional_selection_probabilities: {
    count_numeric_conditional_probabilities: number;
    min: number | null;
    median: number | null;
    max: number | null;
    scope: string;
  };
  total_attempted_market_pairs: number;
  total_quality_valid_market_pairs_current_replay: number;
  positive_top_gross_pairs: number;
  candidate_events: number;
  capture_vs_current_replay_delta: number;
  capture_vs_replay_count_mismatches: Array<Record<string, unknown>>;
  source_hashes_verified: boolean;
  limitations: string[];
  artifact: Artifact & { file_sha256: string; url: string };
};

type Observatory = {
  status: string;
  analysis_version: string | null;
  processed_snapshot_count: number;
  pending_snapshot_count: number;
  readiness: string;
  coverage_window_hours: number;
  first_captured_at_utc: string | null;
  last_captured_at_utc: string | null;
  observed_utc_days: string[];
  discovery: {
    current_bounded_eligible_markets: number;
    maximum_bounded_eligible_markets_seen: number;
    unique_market_ids_observed: number;
    selected_market_observations: number;
    latest_phase: string | null;
    latest_scan_id: string | null;
    latest_snapshot_url: string | null;
    latest_selected_markets: number;
    latest_stable_control_markets: number;
    latest_rotating_markets: number;
    latest_by_category: Record<string, number>;
    latest_by_liquidity: Record<string, number>;
    latest_by_expiry: Record<string, number>;
    latest_by_spread: Record<string, number>;
    latest_exclusions: Record<string, number>;
    latest_frame_protocol: string | null;
    latest_offset_bucket_seconds: number | null;
    latest_query_count: number;
    latest_query_candidate_records: number;
    latest_unique_market_ids: number;
    latest_http_attempts: number;
    latest_target_markets: number;
    latest_selected_market_rows: Array<{
      market_id: string;
      primary_category: string | null;
      primary_category_source: string | null;
      cohort_role: string;
      selection_probability: string;
      selection_probability_basis: string;
      selection_stratum: string | null;
    }>;
    collection_bounds: {
      target_markets: number;
      maximum_markets: number;
      gamma_queries_per_scan: number;
      gamma_page_limit: number;
      maximum_public_read_calls_per_scan: number;
      maximum_public_http_attempts_per_scan: number;
      maximum_retries_per_public_read: number;
      request_timeout_seconds: number;
      maximum_response_bytes: number;
      minimum_request_interval_seconds: number;
      maximum_root_bytes: number;
      quantity_grid: string[];
    } | null;
    latest_snapshot_invalid_reasons: Record<string, number>;
  };
  opportunity: {
    quality_valid_pairs: number;
    invalid_pairs: number;
    positive_top_gross_pairs: number;
    positive_full_depth_gross_by_quantity: Record<string, number>;
    positive_minimum_notional_by_quantity: Record<string, number>;
    positive_single_match_by_quantity: Record<string, number>;
    positive_fragmentation_safe_by_quantity: Record<string, number>;
    candidate_event_count: number;
    candidate_market_count: number;
    minimum_top_edge_per_share: string | null;
    maximum_top_edge_per_share: string | null;
  };
  measurement_comparison: {
    denominator_selected_market_observations: number;
    legacy_freshness_valid_pairs: number;
    corrected_freshness_valid_pairs: number;
    recovered_valid_pairs: number;
    legacy_valid_percent: number | null;
    corrected_valid_percent: number | null;
    recovered_percentage_points: number | null;
    legacy_invalid_reasons: Record<string, number>;
  };
  data_quality: {
    invalid_reasons: Record<string, number>;
    latest_invalid_reasons: Record<string, number>;
    reported_update_age_bands_by_leg: Record<string, Record<string, number>>;
    reported_update_age_above_5s_by_leg: Record<string, number>;
    reported_update_timestamp_skew_bands: Record<string, number>;
    reported_update_timestamp_skew_above_250ms_pairs: number;
    sampled_activity_bands: Record<string, number>;
  };
  market_coverage: {
    coverage_denominator_snapshots: number;
    tracked_markets: number;
    sampled_state_comparisons: number;
    sampled_state_changes: number;
    sampled_state_change_fraction: number | null;
    sampled_activity_bands: Record<string, number>;
    least_observed_markets: Array<{
      market_id: string;
      selected_observations: number;
      snapshot_coverage_percent: number | null;
      quality_valid_pairs: number;
      quality_valid_percent: number | null;
      legacy_freshness_valid_pairs: number;
      legacy_quality_valid_percent: number | null;
      legacy_freshness_invalid_reasons: Record<string, number>;
      invalid_reasons: Record<string, number>;
      categories: string[];
      cohort_roles: Record<string, number>;
      first_observed_at_utc: string | null;
      last_observed_at_utc: string | null;
      sampled_state_fingerprints: number;
      sampled_state_comparisons: number;
      sampled_state_changes: number;
      sampled_state_change_fraction: number | null;
      sampled_activity_band: string;
    }>;
    omitted_market_count: number;
  };
  market_concentration: Array<{
    market_id: string;
    selected_observations: number;
    quality_valid_pairs: number;
    categories: string[];
  }>;
  category_coverage: Array<{ category: string; selected_market_observations: number }>;
  recent_candidates: ObservatoryCandidate[];
  summary_artifact: Artifact | null;
  measurement_pilot: CoveragePilot;
  market_universe_coverage?: MarketUniverseCoverage | null;
  limitations: string[];
};

type FinalizedRealitySource = {
  status: string;
  analysis_version: string | null;
  campaign_id?: string | null;
  processed_segment_count: number;
  catalog_segment_count: number;
  empty_finalized_segment_count: number;
  pending_segment_count: number;
  pending_source_bytes: number;
  processed_source_bytes: number;
  last_processed_ordinal: number;
  readiness: string;
  campaign_window_ns: { start: number; end_exclusive: number } | null;
  active_segment_read: boolean;
  cumulative: {
    period_frame_records: number;
    touched_market_frame_states: number;
    quality_valid_states: number;
    quality_invalid_reason_counts: Record<string, number>;
    positive_top_ask_pair_states: number;
    positive_full_depth_pre_fee_states: number;
    top_edge_distribution: {
      count: number;
      minimum: string;
      median_nearest_rank: string;
      maximum: string;
      positive_count: number;
    } | null;
  };
  summary_artifact: (Artifact & { file_sha256: string; url: string }) | null;
  limitations: string[];
};

type Overview = {
  status: string;
  captured_at_utc: string;
  verdict: string;
  coverage: {
    markets: number;
    connected_families: number;
    utc_days: string[];
    source_segments: number;
    source_bytes: number;
    period_frame_records: number;
    touched_market_frame_states: number;
    quality_valid_states: number;
  };
  opportunity_funnel: {
    quality_valid_states: number;
    positive_top_ask_pair_states: number;
    positive_top_with_quantity_depth_states: number;
    quantity_depth_complete_states: number;
    positive_full_depth_pre_fee_states: number;
    positive_full_depth_minimum_notional_satisfied_states: number;
    quantity_requested_shares: string;
    pre_fee_top_edge_distribution: {
      count: number;
      minimum: string;
      median_nearest_rank: string;
      maximum: string;
      positive_count: number;
    };
  };
  followup_yield: {
    valid_initial_decisions: number;
    by_horizon: Horizon[];
    source_analysis_version?: string;
  };
  followup_censoring: FollowupCensoring | null;
  label_feasibility: LabelFeasibility | null;
  gap_censor_audit: GapCensorAudit | null;
  finalized_gap_detail: FinalizedGapDetail | null;
  baseline_policies: { count: number; all_abstained: boolean };
  execution_sensitivity: {
    quantity_shares_per_leg: string;
    completed_pair_pnl_single_match_usdc: string;
    completed_pair_pnl_fragmentation_safe_usdc: string;
    unmatched_leg_loss_usdc: string;
    required_matched_completions_per_unmatched_event: string;
    required_matched_rate_at_1pct_unmatched: string;
    required_matched_rate_at_5pct_unmatched: string;
    break_even_at_5pct_unmatched_feasible: boolean;
    half_depth_single_match_pair_pnl_usdc: string;
    rates_are_estimates: boolean;
    actual_fills: string;
  };
  research_status: {
    hypotheses: number;
    experiments: number;
    models: number;
    candidates: number;
    recent_hypotheses: Array<{
      id: string;
      title: string;
      status: string;
      result_status: string;
      decision: string;
    }>;
  };
  opportunity_observatory: Observatory;
  finalized_reality_source: FinalizedRealitySource;
  artifacts: Artifact[];
  limitations: string[];
};

type ArenaResearchActivity = {
  status: string;
  state_source: string;
  active_job_count: number;
  queued_job_count: number;
  jobs: Array<{
    job_id: string | null;
    kind: string | null;
    source_scan_id: string | null;
    state: string | null;
    phase: string | null;
    progress: { done?: number; total?: number } | null;
    error: string | null;
  }>;
  latest_veritas_qualification?: {
    job_id: string | null;
    source_scan_id: string;
    finding_id: string;
    experiment_run_id: string;
    snapshot_count: number;
    attempted_market_pairs: number;
    quality_valid_pairs: number;
    unique_market_ids: number;
    top_pair_edge_per_share: {
      count: number;
      minimum_per_share: string;
      median_nearest_rank_per_share: string;
      maximum_per_share: string;
      positive_count: number;
    };
    finding_url: string;
  } | null;
  active_director_count: number;
  directors: Array<{
    director_id: string | null;
    state: string | null;
    research_question: string | null;
    current_stage: string | null;
    source_scan_id?: string | null;
    last_qualified_scan_id?: string | null;
    strategy_readiness?: string | null;
    model_readiness?: string | null;
    independent_confirmation_readiness?: string | null;
    source_revision_sha256?: string | null;
    finalized_source_analysis?: {
      state: string | null;
      readiness: string | null;
      status: string | null;
      campaign_id: string | null;
      summary_sha256: string | null;
      processed_segment_count: number | null;
      catalog_segment_count: number | null;
      pending_segment_count: number | null;
      pending_source_bytes: number | null;
      processed_source_bytes: number | null;
      last_processed_ordinal: number | null;
      period_frame_records: number | null;
      touched_market_frame_states: number | null;
      quality_valid_states: number | null;
      positive_top_ask_pair_states: number | null;
      positive_full_depth_pre_fee_states: number | null;
    } | null;
    recommendation?: string | null;
    updated_at_utc?: string | null;
    latest_finding?: {
      finding_id: string | null;
      experiment_run_id: string | null;
      experiment_sha256?: string | null;
      dataset_sha256?: string | null;
      status: string | null;
      snapshot_count: number | null;
      quality_valid_pairs: number | null;
      unique_market_ids: number | null;
      gross_candidate_evidence_count?: number | null;
      gross_candidate_replay_status?: string | null;
      gross_candidate_replayed_count?: number | null;
      gross_candidate_replay_complete?: boolean | null;
      positive_states_by_gate: Record<string, number> | null;
    } | null;
    recent_events?: Array<{
      recorded_at_utc: string | null;
      state: string | null;
      stage: string | null;
      note: string | null;
      scan_id: string | null;
      job_id: string | null;
      finding_id: string | null;
      experiment_run_id: string | null;
      experiment_sha256: string | null;
      dataset_sha256: string | null;
      source_revision_sha256: string | null;
      strategy_readiness: string | null;
      model_readiness: string | null;
      positive_states_by_gate: Record<string, number> | null;
      recommendation: string | null;
    }>;
    recent_events_truncated?: boolean;
  }>;
  active_schedule_count: number;
  schedules: Array<{
    schedule_id: string | null;
    state: string | null;
    question: string | null;
    steps: Array<{ name: string | null; state: string | null; job_id: string | null }>;
  }>;
  alerts: Array<{
    alert_id: string | null;
    state: string | null;
    reason: string | null;
    schedule_id: string | null;
  }>;
  invalid_artifact_count: number;
};

type ArenaActivityJob = {
  job_id: string;
  state: string;
};

const fmt = (value: number) => value.toLocaleString('en-US');
const usdc = (value: string) => `${Number(value) >= 0 ? '+' : ''}${Number(value).toFixed(2)} USDC`;
const rate = (value: number, denominator: number) =>
  denominator ? `${((100 * value) / denominator).toFixed(1)}%` : '—';
const bytes = (value: number) => `${(value / 1024 / 1024).toFixed(1)} MiB`;
const controlAvailabilityLabel = (reason: string) => {
  if (reason === 'not_returned_by_bounded_query_union') return 'not returned by bounded query';
  if (reason === 'eligible_but_not_selected') return 'eligible, not selected';
  if (reason.startsWith('excluded_')) {
    return `excluded: ${reason.slice('excluded_'.length).replaceAll('_', ' ')}`;
  }
  return reason.replaceAll('_', ' ');
};
const time = (value: string) =>
  new Date(value).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });

function Stat({
  label,
  value,
  detail,
  tone = 'gold',
}: {
  label: string;
  value: string;
  detail: string;
  tone?: string;
}) {
  return (
    <article className={`ve-stat ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </article>
  );
}

function Panel({
  eyebrow,
  title,
  note,
  children,
}: {
  eyebrow: string;
  title: string;
  note?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="ve-panel">
      <header className="ve-panel-head">
        <div>
          <span className="ve-eyebrow">{eyebrow}</span>
          <h3>{title}</h3>
        </div>
        {note && <p>{note}</p>}
      </header>
      {children}
    </section>
  );
}

export function Veritas() {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ['veritas', 'overview'],
    queryFn: () => api<Overview>('/veritas/overview'),
    refetchInterval: 60_000,
    staleTime: 30_000,
    retry: 1,
  });
  const arenaActivityQuery = useQuery({
    queryKey: ['arena', 'research-activity'],
    queryFn: () => api<ArenaResearchActivity>('/arena/research-activity'),
    refetchInterval: 60_000,
    staleTime: 30_000,
    retry: 1,
  });
  const qualificationJobMutation = useMutation({
    mutationFn: () =>
      api<ArenaActivityJob>('/arena/jobs/veritas-qualification', { method: 'POST' }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['arena', 'research-activity'] });
    },
  });
  const data = query.data;
  const arenaActivity = arenaActivityQuery.data;
  const arenaJobs = Array.isArray(arenaActivity?.jobs) ? arenaActivity.jobs : [];
  const latestVeritasQualification = arenaActivity?.latest_veritas_qualification ?? null;
  const arenaDirectors = Array.isArray(arenaActivity?.directors) ? arenaActivity.directors : [];
  const arenaSchedules = Array.isArray(arenaActivity?.schedules) ? arenaActivity.schedules : [];
  const arenaAlerts = Array.isArray(arenaActivity?.alerts) ? arenaActivity.alerts : [];

  if (query.isPending) {
    return <div className="veritas-loading">Loading versioned Veritas evidence…</div>;
  }
  if (query.isError || !data) {
    return (
      <div className="veritas-error" role="alert">
        <ShieldCheck size={18} />
        <div>
          <strong>Veritas evidence is unavailable.</strong>
          <p>{query.error?.message ?? 'No versioned evidence was returned.'}</p>
        </div>
        <button onClick={() => void query.refetch()}>Retry</button>
      </div>
    );
  }

  const denominator = data.followup_yield.valid_initial_decisions;
  const funnelMaximum = Math.max(data.coverage.period_frame_records, 1);
  const observatory = data.opportunity_observatory;
  const measurementPilot = observatory.measurement_pilot;
  const universeCoverage = observatory.market_universe_coverage ?? null;
  const finalizedSource = data.finalized_reality_source;
  const observatoryDiscovery = observatory.discovery;
  const existingQualificationJob = arenaJobs.find(
    (job) =>
      job.kind === 'veritas_qualification' &&
      job.source_scan_id === observatoryDiscovery.latest_scan_id,
  );
  const observatoryOpportunity = observatory.opportunity;
  const observatoryQuality = observatory.data_quality;
  const followupCensoring = data.followup_censoring ?? null;
  const labelFeasibility = data.label_feasibility ?? null;
  const gapCensorAudit = data.gap_censor_audit ?? null;
  const finalizedGapDetail = data.finalized_gap_detail ?? null;
  const indirectGapTerminationCount = gapCensorAudit
    ? Object.values(gapCensorAudit.unique_book_issue_termination_records_by_source_kind).reduce(
        (sum, count) => sum + count,
        0,
      )
    : 0;
  const indirectGapTerminationSources = gapCensorAudit
    ? Object.entries(gapCensorAudit.unique_book_issue_termination_records_by_source_kind)
        .map(([kind, count]) => `${kind.replaceAll('_', ' ')} ${fmt(count)}`)
        .join(' · ')
    : '';
  const positiveFullDepthAt20 =
    observatoryOpportunity.positive_minimum_notional_by_quantity['20'] ?? 0;
  const economicGateQuantities = Object.keys(
    observatoryOpportunity.positive_full_depth_gross_by_quantity,
  ).sort((left, right) => Number(left) - Number(right));
  const candidateEventsPerPanelHour =
    observatory.coverage_window_hours > 0
      ? observatoryOpportunity.candidate_event_count / observatory.coverage_window_hours
      : null;
  const latestCategories = Object.entries(observatoryDiscovery.latest_by_category).sort(
    (left, right) => right[1] - left[1] || left[0].localeCompare(right[0]),
  );
  const latestCategoryMaximum = Math.max(1, ...latestCategories.map(([, count]) => count));
  const latestExcludedMarkets = Object.values(observatoryDiscovery.latest_exclusions).reduce(
    (sum, count) => sum + count,
    0,
  );
  const latestSelectedMarketRows = observatoryDiscovery.latest_selected_market_rows ?? [];
  const collectionBounds = observatoryDiscovery.collection_bounds ?? null;
  const latestStrata = [
    ['Liquidity', observatoryDiscovery.latest_by_liquidity],
    ['Expiry', observatoryDiscovery.latest_by_expiry],
    ['Spread', observatoryDiscovery.latest_by_spread],
  ] as const;
  const leastObservedMarkets = observatory.market_coverage.least_observed_markets;
  const invalidReasons = Object.entries(observatoryQuality.latest_invalid_reasons).sort(
    (left, right) => right[1] - left[1] || left[0].localeCompare(right[0]),
  );
  const funnel = [
    ['Captured frame records', data.coverage.period_frame_records, 'observed'],
    ['Paired-market frame states', data.coverage.touched_market_frame_states, 'derived'],
    ['Quality-valid states', data.opportunity_funnel.quality_valid_states, 'derived'],
    [
      'Complete quantity-depth states',
      data.opportunity_funnel.quantity_depth_complete_states,
      'derived',
    ],
    ['Positive top-ask pairs', data.opportunity_funnel.positive_top_ask_pair_states, 'derived'],
    [
      'Positive after quantity depth',
      data.opportunity_funnel.positive_top_with_quantity_depth_states,
      'derived',
    ],
    [
      'Positive at full displayed depth, pre-fee',
      data.opportunity_funnel.positive_full_depth_pre_fee_states,
      'derived',
    ],
    [
      'Positive after full-depth costs',
      data.opportunity_funnel.positive_full_depth_minimum_notional_satisfied_states,
      'derived',
    ],
  ] as const;

  return (
    <section className="veritas-dashboard" aria-label="Veritas economic intelligence">
      <div className="ve-masthead">
        <div>
          <span className="ve-kicker">
            <BarChart3 size={15} /> PROJECT VERITAS / ECONOMIC INTELLIGENCE
          </span>
          <h1>
            Evidence before conviction<span>.</span>
          </h1>
          <p>Opportunity, execution uncertainty and research progress in one bounded view.</p>
        </div>
        <div className="ve-snapshot">
          <span className="ve-grade">{data.status.replaceAll('_', ' ')}</span>
          <small>Source snapshot · {time(data.captured_at_utc)}</small>
        </div>
      </div>

      <section className="ve-verdict" aria-labelledby="verdict-title">
        <div className="ve-verdict-icon">
          <TrendingDown size={19} />
        </div>
        <div>
          <span className="ve-eyebrow">CURRENT ECONOMIC ASSESSMENT</span>
          <h2 id="verdict-title">
            No quality-valid positive gross pair appeared in the measured panel.
          </h2>
          <p>{data.verdict}</p>
        </div>
        <span className="ve-observed-tag">OBSERVED PANEL</span>
      </section>

      <div className="ve-stats">
        <Stat
          label="Quality-valid states"
          value={fmt(data.opportunity_funnel.quality_valid_states)}
          detail={`${fmt(data.coverage.markets)} monitored markets · ${data.coverage.connected_families} connected families`}
        />
        <Stat
          label="Positive gross pairs"
          value={fmt(data.opportunity_funnel.positive_full_depth_pre_fee_states)}
          detail="No positive state at top ask or full depth"
          tone="red"
        />
        <Stat
          label="1 s public follow-ups"
          value={`${fmt(data.followup_yield.by_horizon.find((row) => row.horizon_ms === 1000)?.observed ?? 0)} / ${fmt(denominator)}`}
          detail={`${rate(data.followup_yield.by_horizon.find((row) => row.horizon_ms === 1000)?.observed ?? 0, denominator)} qualifying measurements`}
          tone="cyan"
        />
        <Stat
          label="Real fills / research models"
          value="Unknown / 0"
          detail={`${data.research_status.candidates} research candidates · no real execution labels`}
          tone="purple"
        />
      </div>

      <div className="ve-grid ve-grid-wide">
        <Panel
          eyebrow="FINALIZED REALITY SOURCE · READ ONLY"
          title="Incremental Mission 2 campaign replay"
          note="This panel advances through hash-verified finalized Reality segments in bounded batches. It is separate from the recurring public discovery snapshots."
        >
          <div className="ve-observatory-stats compact">
            <div>
              <span>Finalized segments indexed</span>
              <strong>
                {fmt(finalizedSource.processed_segment_count)} /{' '}
                {fmt(finalizedSource.catalog_segment_count)}
              </strong>
            </div>
            <div>
              <span>Remaining finalized data</span>
              <strong>
                {fmt(finalizedSource.pending_segment_count)} segments ·{' '}
                {bytes(finalizedSource.pending_source_bytes)}
              </strong>
            </div>
            <div>
              <span>Campaign frame records</span>
              <strong>{fmt(finalizedSource.cumulative.period_frame_records)}</strong>
            </div>
            <div>
              <span>Quality-valid paired states</span>
              <strong>{fmt(finalizedSource.cumulative.quality_valid_states)}</strong>
            </div>
          </div>
          <div className="ve-observatory-meta">
            <span>
              Analysis status <b>{finalizedSource.status.replaceAll('_', ' ')}</b>
            </span>
            <span>
              Readiness <b>{finalizedSource.readiness.replaceAll('_', ' ')}</b>
            </span>
            <span>
              Last source ordinal <b>{fmt(finalizedSource.last_processed_ordinal)}</b>
            </span>
            <span>
              Positive top / full depth{' '}
              <b>
                {fmt(finalizedSource.cumulative.positive_top_ask_pair_states)} /{' '}
                {fmt(finalizedSource.cumulative.positive_full_depth_pre_fee_states)}
              </b>
            </span>
          </div>
          {finalizedSource.summary_artifact && (
            <a
              className="ve-latest-snapshot"
              href={finalizedSource.summary_artifact.url}
              target="_blank"
              rel="noreferrer"
            >
              Inspect versioned source-analysis summary <ArrowUpRight size={13} />
            </a>
          )}
          <p className="ve-observatory-note">
            The active Reality segment is never read. A missing or changed catalog prefix stops
            resume; quote counts remain correlated observations and do not establish fills.
          </p>
        </Panel>
        <Panel
          eyebrow="PROSPECTIVE MEASUREMENT · READ ONLY"
          title="24-hour coverage pilot"
          note="Tracks quality-valid paired-book yield over scheduled snapshots. This is a measurement study, not a strategy or fill outcome."
        >
          <div className="ve-observatory-stats compact">
            <div>
              <span>Pilot status</span>
              <strong className="ve-readiness">
                {measurementPilot.status.replaceAll('_', ' ')}
              </strong>
            </div>
            <div>
              <span>Completed scans</span>
              <strong>
                {fmt(measurementPilot.completed_scans)} /{' '}
                {fmt(measurementPilot.maximum_completed_scans)}
              </strong>
            </div>
            <div>
              <span>Quality-valid pair slots</span>
              <strong>
                {fmt(measurementPilot.quality_valid_pairs)} /{' '}
                {fmt(measurementPilot.selected_market_pair_slots)}
              </strong>
            </div>
            <div>
              <span>Overall quality yield</span>
              <strong>
                {measurementPilot.quality_valid_yield === null
                  ? '—'
                  : rate(
                      measurementPilot.quality_valid_pairs,
                      measurementPilot.selected_market_pair_slots,
                    )}
              </strong>
              <small>{fmt(measurementPilot.invalid_pairs)} invalid selected slots</small>
            </div>
          </div>

          <div className="ve-pilot-breakdown">
            <div>
              <span>Yield by cohort</span>
              {Object.entries(measurementPilot.by_cohort_role).length ? (
                Object.entries(measurementPilot.by_cohort_role).map(([role, cohort]) => (
                  <p key={role}>
                    <b>{role.replaceAll('_', ' ')}</b>
                    <strong>
                      {fmt(cohort.quality_valid)} / {fmt(cohort.selected)} ·{' '}
                      {rate(cohort.quality_valid, cohort.selected)}
                    </strong>
                  </p>
                ))
              ) : (
                <small>No pilot scans recorded yet.</small>
              )}
            </div>
            <div>
              <span>Yield by selection stratum</span>
              {Object.entries(measurementPilot.by_selection_stratum).length ? (
                Object.entries(measurementPilot.by_selection_stratum).map(([stratum, cohort]) => (
                  <p key={stratum}>
                    <b>{stratum.replaceAll('_', ' ')}</b>
                    <strong>
                      {fmt(cohort.quality_valid)} / {fmt(cohort.selected)} ·{' '}
                      {rate(cohort.quality_valid, cohort.selected)}
                    </strong>
                  </p>
                ))
              ) : (
                <small>No pilot scans recorded yet.</small>
              )}
            </div>
          </div>

          <div className="ve-observatory-meta">
            <span>
              Selected markets <b>{fmt(measurementPilot.distinct_selected_market_ids)}</b>
            </span>
            <span>
              Missed scan sequences <b>{fmt(measurementPilot.skipped_scan_sequences)}</b>
            </span>
            {measurementPilot.started_at_utc && (
              <span>
                Started <b>{time(measurementPilot.started_at_utc)}</b>
              </span>
            )}
            {measurementPilot.ends_at_utc && (
              <span>
                Fixed end <b>{time(measurementPilot.ends_at_utc)}</b>
              </span>
            )}
          </div>

          {measurementPilot.latest_scan && (
            <>
              <div className="ve-pilot-latest">
                <span>Latest scan · {measurementPilot.latest_scan.phase.replaceAll('_', ' ')}</span>
                <strong>
                  {fmt(measurementPilot.latest_scan.quality_valid_pairs)} /{' '}
                  {fmt(measurementPilot.latest_scan.selected_market_pairs)} quality-valid ·{' '}
                  {fmt(measurementPilot.latest_scan.positive_top_gross_pairs)} positive gross
                </strong>
                <small>
                  {time(measurementPilot.latest_scan.captured_at_utc)} ·{' '}
                  {fmt(measurementPilot.latest_scan.bounded_eligible_markets)} eligible in the
                  bounded query frame · {fmt(measurementPilot.latest_scan.excluded_market_ids)}{' '}
                  excluded
                </small>
              </div>
              <a
                className="ve-latest-snapshot"
                href={measurementPilot.latest_scan.snapshot_url}
                target="_blank"
                rel="noreferrer"
              >
                Inspect latest pilot snapshot <ArrowUpRight size={13} />
              </a>
            </>
          )}
          {measurementPilot.latest_control_availability && (
            <div className="ve-pilot-latest" data-testid="pilot-control-availability">
              <span>Frozen-control availability · latest scan</span>
              {measurementPilot.latest_control_availability.status === 'verified' ? (
                <>
                  <strong>
                    {fmt(
                      measurementPilot.latest_control_availability.available_in_selected_cohort ??
                        0,
                    )}{' '}
                    / {fmt(measurementPilot.latest_control_availability.frozen_control_count ?? 0)}{' '}
                    selected ·{' '}
                    {fmt(
                      measurementPilot.latest_control_availability.missing_from_selected_cohort ??
                        0,
                    )}{' '}
                    missing
                  </strong>
                  <small>
                    {Object.entries(
                      measurementPilot.latest_control_availability
                        .missing_by_bounded_discovery_status ?? {},
                    )
                      .map(([reason, count]) => `${controlAvailabilityLabel(reason)} ${fmt(count)}`)
                      .join(' · ')}
                  </small>
                  <small>
                    {measurementPilot.latest_control_availability.limitations?.[0] ??
                      'Availability describes only the bounded public query union.'}
                  </small>
                  {measurementPilot.latest_control_availability.snapshot_url && (
                    <a
                      className="ve-latest-snapshot"
                      href={measurementPilot.latest_control_availability.snapshot_url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Inspect control-availability snapshot <ArrowUpRight size={13} />
                    </a>
                  )}
                </>
              ) : (
                <small>
                  {measurementPilot.latest_control_availability.reason ??
                    'The latest control-availability evidence could not be verified.'}
                </small>
              )}
            </div>
          )}
          {measurementPilot.summary_artifact && (
            <a
              className="ve-latest-snapshot"
              href={measurementPilot.summary_artifact.url}
              target="_blank"
              rel="noreferrer"
            >
              Inspect hash-verified pilot summary <ArrowUpRight size={13} />
            </a>
          )}
          <p className="ve-observatory-note">
            Cohort yields are descriptive; stable controls are not randomized against rotating
            markets. Intermittent snapshots do not establish venue-wide coverage, quote lifetime,
            sequence freshness, fills, or profitability.
          </p>
          {measurementPilot.limitations.length > 0 && (
            <details className="ve-pilot-limitations">
              <summary>Protocol limitations ({measurementPilot.limitations.length})</summary>
              <ul>
                {measurementPilot.limitations.map((limitation) => (
                  <li key={limitation}>{limitation}</li>
                ))}
              </ul>
            </details>
          )}
        </Panel>
      </div>

      <div className="ve-grid ve-grid-wide">
        <Panel
          eyebrow="CONTINUOUS PUBLIC DISCOVERY"
          title="Market discovery and coverage"
          note="Six bounded public market frames use seeded half-hour page offsets across liquidity and ID strata, then feed a rotating stratified panel and a frozen random control. The frame is conditional on those query responses; snapshots are not continuous quotes."
        >
          <div className="ve-observatory-stats">
            <div>
              <span>Latest bounded query frame</span>
              <strong>{fmt(observatoryDiscovery.latest_unique_market_ids)} IDs</strong>
              <small>
                {fmt(observatoryDiscovery.latest_query_candidate_records)} returned rows ·{' '}
                {fmt(observatoryDiscovery.current_bounded_eligible_markets)} eligible ·{' '}
                {fmt(latestExcludedMarkets)} excluded across{' '}
                {fmt(observatoryDiscovery.latest_query_count)} pages
              </small>
            </div>
            <div>
              <span>Latest monitored cohort</span>
              <strong>
                {fmt(observatoryDiscovery.latest_selected_markets)} /{' '}
                {fmt(observatoryDiscovery.unique_market_ids_observed)} unique seen
              </strong>
            </div>
            <div>
              <span>Finalized snapshots indexed</span>
              <strong>
                {fmt(observatory.processed_snapshot_count)}
                {observatory.pending_snapshot_count
                  ? ` · ${fmt(observatory.pending_snapshot_count)} pending`
                  : ''}
              </strong>
            </div>
            <div>
              <span>Research readiness</span>
              <strong className="ve-readiness">{observatory.readiness.replaceAll('_', ' ')}</strong>
            </div>
          </div>
          <div className="ve-observatory-meta">
            <span>
              Latest phase <b>{observatoryDiscovery.latest_phase ?? 'awaiting scan'}</b>
            </span>
            <span>
              Frame protocol{' '}
              <b>{observatoryDiscovery.latest_frame_protocol ?? 'awaiting versioned scan'}</b>
            </span>
            <span>
              Stable controls <b>{fmt(observatoryDiscovery.latest_stable_control_markets)}</b>
            </span>
            <span>
              Rotating strata <b>{fmt(observatoryDiscovery.latest_rotating_markets)}</b>
            </span>
            <span>
              Window <b>{observatory.coverage_window_hours.toFixed(1)} h</b>
            </span>
          </div>
          {universeCoverage?.status === 'available' && (
            <div className="ve-universe-audit" aria-label="Saved market-universe coverage audit">
              <div className="ve-observatory-stats">
                <div>
                  <span>Hash-verified saved snapshots</span>
                  <strong>{fmt(universeCoverage.snapshot_count)} scans</strong>
                  <small>
                    {universeCoverage.first_scan_id} → {universeCoverage.last_scan_id}
                  </small>
                </div>
                <div>
                  <span>Distinct markets in bounded unions</span>
                  <strong>{fmt(universeCoverage.distinct_gamma_market_ids)} market IDs</strong>
                  <small>
                    {fmt(universeCoverage.eligible_market_ids_at_least_once)} eligible at least once
                  </small>
                </div>
                <div>
                  <span>Latest bounded discovery union</span>
                  <strong>{fmt(universeCoverage.latest_scan.gamma_market_ids)} IDs</strong>
                  <small>
                    {fmt(universeCoverage.latest_scan.eligible_market_ids)} eligible ·{' '}
                    {fmt(universeCoverage.latest_scan.excluded_market_ids)} excluded
                  </small>
                </div>
                <div>
                  <span>Current v4 quality replay</span>
                  <strong>
                    {fmt(universeCoverage.total_quality_valid_market_pairs_current_replay)} /{' '}
                    {fmt(universeCoverage.total_attempted_market_pairs)} pairs
                  </strong>
                  <small>
                    {fmt(universeCoverage.positive_top_gross_pairs)} positive top-gross ·{' '}
                    {fmt(universeCoverage.candidate_events)} candidates
                  </small>
                </div>
              </div>
              <div className="ve-observatory-meta">
                <span>
                  Identity counts{' '}
                  <b>
                    {fmt(universeCoverage.distinct_gamma_market_ids)} markets ·{' '}
                    {fmt(universeCoverage.distinct_condition_ids)} conditions ·{' '}
                    {fmt(universeCoverage.distinct_outcome_asset_ids)} outcome assets
                  </b>
                </span>
                <span>
                  Latest selected books{' '}
                  <b>
                    {fmt(universeCoverage.latest_scan.selected_market_ids)} markets ·{' '}
                    {fmt(universeCoverage.latest_scan.distinct_selected_condition_ids)} conditions ·{' '}
                    {fmt(universeCoverage.latest_scan.distinct_selected_outcome_asset_ids)} assets
                  </b>
                </span>
                <span>
                  Mean bounded union{' '}
                  <b>
                    {universeCoverage.mean_unique_market_ids_per_bounded_union.toFixed(1)} IDs ·{' '}
                    {universeCoverage.mean_eligible_market_ids_per_bounded_union.toFixed(1)}{' '}
                    eligible
                  </b>
                </span>
              </div>
              <div className="ve-strata-grid">
                {(
                  [
                    [
                      'Liquidity',
                      universeCoverage.latest_eligible_metadata_distributions.liquidity,
                    ],
                    ['Expiry', universeCoverage.latest_eligible_metadata_distributions.expiry],
                    ['Spread', universeCoverage.latest_eligible_metadata_distributions.spread],
                  ] as const
                ).map(([label, distribution]) => (
                  <div key={label}>
                    <span className="ve-subhead">Latest eligible by {label.toLowerCase()}</span>
                    {Object.entries(distribution).map(([band, count]) => (
                      <span className="ve-strata-item" key={band}>
                        {band.replaceAll('_', ' ')} <b>{fmt(count)}</b>
                      </span>
                    ))}
                  </div>
                ))}
              </div>
              {universeCoverage.capture_vs_replay_count_mismatches.length > 0 && (
                <p className="ve-observatory-note">
                  {fmt(universeCoverage.capture_vs_replay_count_mismatches.length)} saved scan
                  {universeCoverage.capture_vs_replay_count_mismatches.length === 1
                    ? ' has'
                    : 's have'}{' '}
                  a capture-to-replay count mismatch of{' '}
                  {fmt(universeCoverage.capture_vs_current_replay_delta)} pair counts; the report
                  preserves both versions.
                </p>
              )}
              <p className="ve-observatory-note">
                These are intermittent snapshots from bounded query unions. They do not provide a
                venue-wide denominator, continuous quotes, order arrival, fills, or profitability.
              </p>
              <a
                className="ve-latest-snapshot"
                href={universeCoverage.artifact.url}
                target="_blank"
                rel="noreferrer"
              >
                Inspect hash-verified A1 coverage artifact <ArrowUpRight size={13} />
              </a>
            </div>
          )}
          {latestCategories.length ? (
            <div className="ve-discovery-list">
              <span className="ve-subhead">Latest cohort by category</span>
              {latestCategories.slice(0, 8).map(([category, count]) => (
                <div className="ve-discovery-row" key={category}>
                  <span>{category}</span>
                  <div className="ve-track">
                    <i
                      style={{ width: `${Math.max((100 * count) / latestCategoryMaximum, 2)}%` }}
                    />
                  </div>
                  <b>{fmt(count)}</b>
                </div>
              ))}
            </div>
          ) : (
            <p className="ve-observatory-empty">
              No finalized public snapshot has been indexed yet.
            </p>
          )}
          <div className="ve-strata-grid">
            {latestStrata.map(([label, values]) => (
              <div key={label}>
                <span className="ve-subhead">Latest cohort by {label.toLowerCase()}</span>
                {Object.entries(values).length ? (
                  Object.entries(values)
                    .sort(([left], [right]) => left.localeCompare(right))
                    .map(([stratum, count]) => (
                      <span className="ve-strata-item" key={stratum}>
                        {stratum.replaceAll('_', ' ')} <b>{fmt(count)}</b>
                      </span>
                    ))
                ) : (
                  <span className="ve-strata-item muted">No measured strata</span>
                )}
              </div>
            ))}
          </div>
          {collectionBounds && (
            <div className="ve-strata-grid" aria-label="Current collector limits">
              <div>
                <span className="ve-subhead">Collector limits</span>
                <span className="ve-strata-item">
                  {fmt(collectionBounds.target_markets)} target ·{' '}
                  {fmt(collectionBounds.maximum_markets)} markets max
                </span>
              </div>
              <div>
                <span className="ve-subhead">Public discovery</span>
                <span className="ve-strata-item">
                  {fmt(collectionBounds.gamma_queries_per_scan)} pages ×{' '}
                  {fmt(collectionBounds.gamma_page_limit)} rows
                </span>
                <span className="ve-strata-item">
                  {fmt(collectionBounds.maximum_public_read_calls_per_scan)} reads ·{' '}
                  {fmt(collectionBounds.maximum_public_http_attempts_per_scan)} HTTP attempts max
                </span>
                <span className="ve-strata-item">
                  {fmt(collectionBounds.maximum_retries_per_public_read)} retry max per read ·{' '}
                  {collectionBounds.minimum_request_interval_seconds.toFixed(1)}s pacing ·{' '}
                  {collectionBounds.request_timeout_seconds.toFixed(0)}s timeout
                </span>
                <span className="ve-strata-item">
                  {fmt(observatoryDiscovery.latest_http_attempts)} HTTP attempts used in latest scan
                </span>
              </div>
              <div>
                <span className="ve-subhead">Storage and quantities</span>
                <span className="ve-strata-item">
                  {bytes(collectionBounds.maximum_response_bytes)} response cap ·{' '}
                  {bytes(collectionBounds.maximum_root_bytes)} root cap
                </span>
                <span className="ve-strata-item">
                  {collectionBounds.quantity_grid.join(', ')} shares per leg
                </span>
              </div>
            </div>
          )}
          {latestSelectedMarketRows.length > 0 && (
            <details className="ve-censor-details">
              <summary>
                Inspect latest per-market selection probabilities ·{' '}
                {fmt(latestSelectedMarketRows.length)} selected
              </summary>
              <p className="ve-observatory-note">
                Probabilities are conditional on the bounded query-response union and frozen stable
                control cohort. Rotating page offsets broaden the observed frame but do not provide
                venue-wide inclusion probabilities.
              </p>
              <div className="ve-censor-list">
                {latestSelectedMarketRows.map((market) => (
                  <div key={market.market_id}>
                    <strong>{market.market_id}</strong>
                    <span>
                      {market.primary_category ?? 'Category unknown'}
                      {market.primary_category_source
                        ? ` (${market.primary_category_source.replaceAll('.', ' ')})`
                        : ''}{' '}
                      · {market.cohort_role.replaceAll('_', ' ')} ·{' '}
                      {market.selection_stratum?.replaceAll('_', ' ') ?? 'no rotating stratum'}
                    </span>
                    <span>
                      Inclusion probability {market.selection_probability} ·{' '}
                      {market.selection_probability_basis.replaceAll('_', ' ')}
                    </span>
                  </div>
                ))}
              </div>
            </details>
          )}
          {Object.keys(observatoryDiscovery.latest_exclusions).length > 0 && (
            <p className="ve-observatory-note">
              Latest discovery exclusions:{' '}
              {Object.entries(observatoryDiscovery.latest_exclusions)
                .map(([reason, count]) => `${reason.replaceAll('_', ' ')} ${fmt(count)}`)
                .join(' · ')}
            </p>
          )}
          {observatoryDiscovery.latest_snapshot_url && observatoryDiscovery.latest_scan_id && (
            <a
              className="ve-latest-snapshot"
              href={observatoryDiscovery.latest_snapshot_url}
              target="_blank"
              rel="noreferrer"
            >
              Inspect latest immutable snapshot · {observatoryDiscovery.latest_scan_id}
              <ArrowUpRight size={13} />
            </a>
          )}
        </Panel>

        <Panel
          eyebrow="OBSERVED · REPLAYABLE"
          title="Opportunity observatory and data quality"
          note="Each indexed row points to an immutable source snapshot. Repeated snapshots are dependent; no fill, persistence or profitability is inferred."
        >
          <div className="ve-observatory-stats compact">
            <div>
              <span>Quality-valid paired books</span>
              <strong>{fmt(observatoryOpportunity.quality_valid_pairs)}</strong>
            </div>
            <div>
              <span>Positive top gross pairs</span>
              <strong
                className={observatoryOpportunity.positive_top_gross_pairs ? 'candidate' : 'none'}
              >
                {fmt(observatoryOpportunity.positive_top_gross_pairs)}
              </strong>
            </div>
            <div>
              <span>Full depth + minimum at 20 shares</span>
              <strong className={positiveFullDepthAt20 ? 'candidate' : 'none'}>
                {fmt(positiveFullDepthAt20)}
              </strong>
            </div>
            <div>
              <span>Candidate markets / events</span>
              <strong>
                {fmt(observatoryOpportunity.candidate_market_count)} /{' '}
                {fmt(observatoryOpportunity.candidate_event_count)}
              </strong>
            </div>
          </div>
          <div className="ve-observatory-meta ve-candidate-frequency">
            <span>
              Recorded candidate frequency
              <b>
                {candidateEventsPerPanelHour === null
                  ? 'Not enough elapsed panel time'
                  : `${candidateEventsPerPanelHour.toFixed(3)} events / panel hour`}
              </b>
            </span>
            <span>
              {fmt(observatoryOpportunity.candidate_event_count)} candidate events across a{' '}
              {observatory.coverage_window_hours.toFixed(1)} h panel window. Snapshots are
              intermittent, not continuous observations.
            </span>
          </div>
          <div className="ve-economic-gates">
            <div className="ve-economic-gates-heading">
              <span className="ve-subhead">Positive economic states by requested size</span>
              <small>
                Observed paired-book states after each gross, depth, minimum, and fee gate
              </small>
            </div>
            <div
              className="ve-economic-gates-table"
              role="table"
              aria-label="Positive economic states by quantity and gate"
            >
              <div className="ve-economic-gates-row header" role="row">
                <span role="columnheader">Shares / leg</span>
                <span role="columnheader">Full-depth gross</span>
                <span role="columnheader">+ Per-leg minimum</span>
                <span role="columnheader">Single-match fees</span>
                <span role="columnheader">Fragmentation-safe fees</span>
              </div>
              {economicGateQuantities.map((quantity) => (
                <div className="ve-economic-gates-row" role="row" key={quantity}>
                  <strong role="cell">{quantity}</strong>
                  <span role="cell">
                    {fmt(
                      observatoryOpportunity.positive_full_depth_gross_by_quantity[quantity] ?? 0,
                    )}
                  </span>
                  <span role="cell">
                    {fmt(
                      observatoryOpportunity.positive_minimum_notional_by_quantity[quantity] ?? 0,
                    )}
                  </span>
                  <span role="cell">
                    {fmt(observatoryOpportunity.positive_single_match_by_quantity[quantity] ?? 0)}
                  </span>
                  <span role="cell">
                    {fmt(
                      observatoryOpportunity.positive_fragmentation_safe_by_quantity[quantity] ?? 0,
                    )}
                  </span>
                </div>
              ))}
            </div>
            <p>
              The per-leg minimum and fee columns show where a positive gross state fails later
              checks. Repeated states are correlated observations, not independent opportunities or
              fills.
            </p>
          </div>
          {latestVeritasQualification && (
            <div className="ve-qualified-edge">
              <div className="ve-qualified-edge-heading">
                <div>
                  <span className="ve-subhead">
                    Latest completed qualification edge distribution
                  </span>
                  <small>
                    {fmt(latestVeritasQualification.quality_valid_pairs)} quality-valid states ·{' '}
                    {fmt(latestVeritasQualification.snapshot_count)} snapshots · through{' '}
                    {latestVeritasQualification.source_scan_id}
                  </small>
                </div>
                <a href={latestVeritasQualification.finding_url} target="_blank" rel="noreferrer">
                  Open sealed finding <ArrowUpRight size={13} />
                </a>
              </div>
              <div className="ve-qualified-edge-values">
                <div>
                  <span>Minimum</span>
                  <b>{latestVeritasQualification.top_pair_edge_per_share.minimum_per_share}</b>
                </div>
                <div>
                  <span>Median nearest rank</span>
                  <b>
                    {
                      latestVeritasQualification.top_pair_edge_per_share
                        .median_nearest_rank_per_share
                    }
                  </b>
                </div>
                <div>
                  <span>Maximum</span>
                  <b>{latestVeritasQualification.top_pair_edge_per_share.maximum_per_share}</b>
                </div>
                <div>
                  <span>Positive gross states</span>
                  <b>
                    {fmt(latestVeritasQualification.top_pair_edge_per_share.positive_count)} /{' '}
                    {fmt(latestVeritasQualification.top_pair_edge_per_share.count)}
                  </b>
                </div>
              </div>
              <p>
                Collateral per share from quality-valid paired top asks. This sealed qualification
                may trail the latest observer scan; repeated states are correlated measurements, not
                independent opportunities or fills.
              </p>
            </div>
          )}
          <div className="ve-quality-diagnostics">
            <div>
              <span>Reported timestamp age &gt; 5 s</span>
              <b>
                YES {fmt(observatoryQuality.reported_update_age_above_5s_by_leg.yes ?? 0)} · NO{' '}
                {fmt(observatoryQuality.reported_update_age_above_5s_by_leg.no ?? 0)}
              </b>
            </div>
            <div>
              <span>Reported timestamp skew &gt; 250 ms</span>
              <b>{fmt(observatoryQuality.reported_update_timestamp_skew_above_250ms_pairs)}</b>
            </div>
            <div>
              <span>Latest invalid reasons</span>
              <b>
                {invalidReasons.length
                  ? invalidReasons
                      .map(([reason, count]) => `${reason.replaceAll('_', ' ')} ${fmt(count)}`)
                      .join(' · ')
                  : 'None recorded'}
              </b>
            </div>
            <div>
              <span>Between-visit sampled state changes</span>
              <b>
                {observatory.market_coverage.sampled_state_change_fraction === null
                  ? 'Not enough repeated fingerprints'
                  : `${(100 * observatory.market_coverage.sampled_state_change_fraction).toFixed(
                      1,
                    )}% · ${fmt(
                      observatory.market_coverage.sampled_state_changes,
                    )} / ${fmt(observatory.market_coverage.sampled_state_comparisons)}`}
              </b>
            </div>
          </div>
          <div className="ve-measurement-comparison">
            <div>
              <span>Prior timestamp gate</span>
              <b>
                {fmt(observatory.measurement_comparison.legacy_freshness_valid_pairs)} /{' '}
                {fmt(observatory.measurement_comparison.denominator_selected_market_observations)}
              </b>
              <small>
                {observatory.measurement_comparison.legacy_valid_percent === null
                  ? 'No paired snapshots'
                  : `${observatory.measurement_comparison.legacy_valid_percent.toFixed(1)}% valid`}
              </small>
            </div>
            <div>
              <span>Request/receipt gate</span>
              <b>
                {fmt(observatory.measurement_comparison.corrected_freshness_valid_pairs)} /{' '}
                {fmt(observatory.measurement_comparison.denominator_selected_market_observations)}
              </b>
              <small>
                {observatory.measurement_comparison.corrected_valid_percent === null
                  ? 'No paired snapshots'
                  : `${observatory.measurement_comparison.corrected_valid_percent.toFixed(1)}% valid`}
              </small>
            </div>
            <div>
              <span>Paired yield difference</span>
              <b>+{fmt(observatory.measurement_comparison.recovered_valid_pairs)} pairs</b>
              <small>
                {observatory.measurement_comparison.recovered_percentage_points === null
                  ? 'No paired snapshots'
                  : `+${observatory.measurement_comparison.recovered_percentage_points.toFixed(1)} percentage points`}
              </small>
            </div>
          </div>
          <div className="ve-market-coverage">
            <div className="ve-market-coverage-heading">
              <span className="ve-subhead">Least-covered sampled markets</span>
              <span>
                {fmt(observatory.market_coverage.tracked_markets)} markets ·{' '}
                {fmt(observatory.market_coverage.coverage_denominator_snapshots)} snapshots
              </span>
            </div>
            <div className="ve-market-table" role="table" aria-label="Per-market snapshot coverage">
              <div className="ve-market-table-row header" role="row">
                <span role="columnheader">Market</span>
                <span role="columnheader">Snapshots</span>
                <span role="columnheader">Valid</span>
                <span role="columnheader">Sampled changes</span>
              </div>
              {leastObservedMarkets.map((market) => (
                <div className="ve-market-table-row" role="row" key={market.market_id}>
                  <span role="cell">
                    {market.market_id}
                    <small>{market.categories.slice(0, 2).join(' · ') || 'Category unknown'}</small>
                  </span>
                  <span role="cell">
                    {market.snapshot_coverage_percent === null
                      ? '—'
                      : `${market.snapshot_coverage_percent.toFixed(1)}%`}
                    <small>{fmt(market.selected_observations)} selected visits</small>
                  </span>
                  <span role="cell">
                    {market.quality_valid_percent === null
                      ? '—'
                      : `${market.quality_valid_percent.toFixed(1)}%`}
                    <small>
                      {fmt(market.quality_valid_pairs)} current ·{' '}
                      {market.legacy_quality_valid_percent === null
                        ? '—'
                        : `${market.legacy_quality_valid_percent.toFixed(1)}%`}{' '}
                      legacy
                    </small>
                  </span>
                  <span role="cell">
                    {market.sampled_state_change_fraction === null
                      ? '—'
                      : `${(100 * market.sampled_state_change_fraction).toFixed(0)}%`}
                    <small>
                      {fmt(market.sampled_state_changes)} / {fmt(market.sampled_state_comparisons)}{' '}
                      · {market.sampled_activity_band.replaceAll('_', ' ')}
                    </small>
                  </span>
                </div>
              ))}
            </div>
            <p className="ve-observatory-note">
              Snapshot coverage is selected visits divided by indexed scans. Sampled state changes
              compare returned YES/NO book hashes at those visits; they do not measure continuous
              quote-update frequency or venue sequence.
              {observatory.market_coverage.omitted_market_count
                ? ` Showing the 24 least-covered IDs; ${fmt(
                    observatory.market_coverage.omitted_market_count,
                  )} additional observed IDs are in the summary artifact.`
                : ''}
            </p>
          </div>
          {observatory.recent_candidates.length ? (
            <div className="ve-candidate-list">
              {observatory.recent_candidates.map((candidate) => (
                <article key={`${candidate.scan_id}-${candidate.market_id}`}>
                  <div>
                    <b>{candidate.question}</b>
                    <span>
                      {candidate.positive_full_depth_minimum_notional_quantities.join(', ')} shares
                      · gross, pre-fee
                    </span>
                  </div>
                  <a href={candidate.snapshot_url} target="_blank" rel="noreferrer">
                    Inspect source snapshot <ArrowUpRight size={13} />
                  </a>
                </article>
              ))}
            </div>
          ) : (
            <p className="ve-observatory-empty">
              No quality-valid positive full-depth gross candidate has been recorded. The detector
              remains active.
            </p>
          )}
          {(gapCensorAudit || finalizedGapDetail) && (
            <div className="ve-gap-evidence" aria-label="Gap attribution and source continuity">
              {gapCensorAudit && (
                <section>
                  <div className="ve-gap-evidence-heading">
                    <div>
                      <span className="ve-subhead">Frozen campaign censor attribution</span>
                      <small>
                        Hash-verified outcome references · {time(gapCensorAudit.captured_at_utc)}
                      </small>
                    </div>
                    <a href={gapCensorAudit.artifact.url} target="_blank" rel="noreferrer">
                      Inspect source audit <ArrowUpRight size={13} />
                    </a>
                  </div>
                  <div className="ve-gap-evidence-stats">
                    <div>
                      <span>Explicit recorded-gap outcomes</span>
                      <b>
                        {fmt(gapCensorAudit.explicit_recorded_gap_outcomes)} →{' '}
                        {fmt(gapCensorAudit.unique_explicit_gap_records_verified)} verified gap
                        records
                      </b>
                    </div>
                    <div>
                      <span>Indirect book-issue outcomes</span>
                      <b>
                        {fmt(gapCensorAudit.book_issue_gap_outcomes)} →{' '}
                        {fmt(indirectGapTerminationCount)} later source records
                      </b>
                    </div>
                    <div>
                      <span>Source records independently checked</span>
                      <b>
                        {fmt(gapCensorAudit.source_verification.unique_source_records_verified)}{' '}
                        across{' '}
                        {fmt(gapCensorAudit.source_verification.unique_finalized_segments_verified)}{' '}
                        finalized segments
                      </b>
                    </div>
                  </div>
                  <p>
                    Record offsets and hashes were verified; no active segment was read. The later
                    records behind book-issue labels are{' '}
                    {indirectGapTerminationSources || 'not listed'}. Their direct causal link to the
                    original gap was not verified. The SQLite event hash chain{' '}
                    {gapCensorAudit.journal_hash_chain_reverified ? 'was' : 'was not'} reverified.
                  </p>
                </section>
              )}
              {finalizedGapDetail && (
                <section>
                  <div className="ve-gap-evidence-heading">
                    <div>
                      <span className="ve-subhead">Incremental finalized-source gap detail</span>
                      <small>
                        {finalizedGapDetail.readiness.replaceAll('_', ' ')} · as of{' '}
                        {time(finalizedGapDetail.generated_at_utc)}
                      </small>
                    </div>
                    <a
                      href={finalizedGapDetail.summary_artifact.url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Inspect verified prefix <ArrowUpRight size={13} />
                    </a>
                  </div>
                  <div className="ve-gap-evidence-stats">
                    <div>
                      <span>All-period finalized gap events</span>
                      <b>{fmt(finalizedGapDetail.all_period_gap_event_count)}</b>
                    </div>
                    <div>
                      <span>Campaign-window events in processed prefix</span>
                      <b>{fmt(finalizedGapDetail.campaign_window_gap_event_count)}</b>
                    </div>
                    <div>
                      <span>Replayable finalized segments</span>
                      <b>
                        {fmt(finalizedGapDetail.processed_segment_count)} /{' '}
                        {fmt(finalizedGapDetail.replayable_catalog_segment_count)} ·{' '}
                        {bytes(finalizedGapDetail.pending_source_bytes)} pending
                      </b>
                    </div>
                  </div>
                  <p>
                    The campaign-window count covers the processed prefix only; while the source
                    analysis is catching up, zero is not evidence that the campaign had no gaps.
                    {finalizedGapDetail.latest_gap_event
                      ? ` Latest gap in the prefix: ${finalizedGapDetail.latest_gap_event.reason.replaceAll('_', ' ')} at ${time(finalizedGapDetail.latest_gap_event.received_at_utc)}${finalizedGapDetail.latest_gap_event.in_campaign_window ? ' (inside the campaign window).' : ' (outside the campaign window).'}`
                      : ' No gap event has been indexed in the current prefix.'}{' '}
                    The analyzer read no active segment.
                  </p>
                </section>
              )}
            </div>
          )}
        </Panel>
      </div>

      <div className="ve-grid ve-grid-wide">
        <Panel
          eyebrow="OBSERVED + DERIVED"
          title="Opportunity funnel"
          note={`${fmt(data.coverage.source_segments)} finalized segments · ${bytes(data.coverage.source_bytes)} replayed · ${data.coverage.utc_days.join(', ')}`}
        >
          <div className="ve-funnel">
            {funnel.map(([label, value, kind]) => (
              <div className="ve-funnel-row" key={label}>
                <div className="ve-funnel-label">
                  <span>
                    {label}
                    <em>{kind}</em>
                  </span>
                  <strong>{fmt(value)}</strong>
                </div>
                <div className="ve-track">
                  <i
                    style={{ width: `${Math.max((100 * value) / funnelMaximum, value ? 1 : 0)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
          <div className="ve-edge-summary">
            <div>
              <span>Pre-fee edge range</span>
              <strong>
                {data.opportunity_funnel.pre_fee_top_edge_distribution.minimum} to{' '}
                {data.opportunity_funnel.pre_fee_top_edge_distribution.maximum}
              </strong>
            </div>
            <div>
              <span>Median nearest rank</span>
              <strong>
                {data.opportunity_funnel.pre_fee_top_edge_distribution.median_nearest_rank}
              </strong>
            </div>
            <p>Collateral per share. The highest measured edge stayed below zero.</p>
          </div>
        </Panel>

        <Panel
          eyebrow="OBSERVED PUBLIC MEASUREMENTS"
          title="Follow-up yield"
          note={
            followupCensoring
              ? `Latest read-only campaign snapshot · ${fmt(followupCensoring.decision_count)} decisions across ${fmt(followupCensoring.market_count)} markets · ${followupCensoring.query_truncated ? 'query capped at its decision bound' : 'all indexed decisions in this snapshot'}.`
              : `Observed and censored counts use ${fmt(denominator)} valid starts from the preserved baseline snapshot. Invalid initial states are shown separately.`
          }
        >
          <div className="ve-horizon-table">
            <div className="ve-table-head">
              <span>Horizon</span>
              <span>Observed</span>
              <span>Yield</span>
              <span>Censored</span>
              <span>Invalid</span>
            </div>
            {data.followup_yield.by_horizon.map((row) => (
              <div className="ve-table-row" key={row.horizon_ms}>
                <strong>
                  {row.horizon_ms >= 1000 ? `${row.horizon_ms / 1000} s` : `${row.horizon_ms} ms`}
                </strong>
                <span>{fmt(row.observed)}</span>
                <span className="ve-yield">{rate(row.observed, denominator)}</span>
                <span>{fmt(row.censored)}</span>
                <span>{fmt(row.invalid_initial)}</span>
              </div>
            ))}
          </div>
          <details className="ve-censor-details">
            <summary>Inspect censor reasons and invalid starts by horizon</summary>
            <div className="ve-censor-list">
              {data.followup_yield.by_horizon.map((row) => (
                <div key={row.horizon_ms}>
                  <strong>
                    {row.horizon_ms >= 1000 ? `${row.horizon_ms / 1000} s` : `${row.horizon_ms} ms`}
                  </strong>
                  {Object.entries(row.censor_reasons).map(([reason, count]) => (
                    <span key={reason}>
                      {reason.replaceAll('_', ' ')} <b>{fmt(count)}</b>
                    </span>
                  ))}
                </div>
              ))}
            </div>
          </details>
          {followupCensoring && (
            <details className="ve-censor-details">
              <summary>
                Inspect censoring by market and UTC hour ·{' '}
                {followupCensoring.longest_horizon_ms >= 1000
                  ? `${followupCensoring.longest_horizon_ms / 1000} s`
                  : `${followupCensoring.longest_horizon_ms} ms`}
              </summary>
              <div className="ve-censor-dimensions">
                <p>
                  As of {time(followupCensoring.captured_at_utc)} ·{' '}
                  {fmt(followupCensoring.valid_initial_decisions)} valid initial decisions ·{' '}
                  {fmt(followupCensoring.invalid_initial_decisions)} invalid initial decisions. The
                  market table shows up to{' '}
                  {fmt(followupCensoring.by_market_at_longest_horizon.length)} of{' '}
                  {fmt(followupCensoring.market_group_count)} markets.
                </p>
                <div className="ve-censor-dimension-grid">
                  <div className="ve-censor-dimension-block">
                    <strong>Market</strong>
                    <div className="ve-censor-dimension-head">
                      <span>Market</span>
                      <span>Valid starts</span>
                      <span>Observed</span>
                      <span>Valid censored</span>
                      <span>Pending</span>
                    </div>
                    {followupCensoring.by_market_at_longest_horizon.map((row) => (
                      <div className="ve-censor-dimension-row" key={row.market_id}>
                        <code>{row.market_id}</code>
                        <span>{fmt(row.valid_initial_followups)}</span>
                        <span>{fmt(row.observed)}</span>
                        <span>{fmt(row.valid_initial_censored)}</span>
                        <span>{fmt(row.pending_followups)}</span>
                      </div>
                    ))}
                  </div>
                  <div className="ve-censor-dimension-block">
                    <strong>UTC hour</strong>
                    <div className="ve-censor-dimension-head">
                      <span>Hour</span>
                      <span>Valid starts</span>
                      <span>Observed</span>
                      <span>Valid censored</span>
                      <span>Pending</span>
                    </div>
                    {followupCensoring.by_utc_hour_at_longest_horizon.map((row) => (
                      <div className="ve-censor-dimension-row" key={row.utc_hour}>
                        <code>{row.utc_hour}</code>
                        <span>{fmt(row.valid_initial_followups)}</span>
                        <span>{fmt(row.observed)}</span>
                        <span>{fmt(row.valid_initial_censored)}</span>
                        <span>{fmt(row.pending_followups)}</span>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="ve-censor-regimes">
                  <strong>Censoring mechanism by horizon</strong>
                  {Object.entries(followupCensoring.by_censoring_regime_horizon).map(
                    ([horizon, group]) => (
                      <div key={horizon}>
                        <b>
                          {Number(horizon) >= 1000
                            ? `${Number(horizon) / 1000} s`
                            : `${horizon} ms`}
                        </b>
                        {group.items.map((item) => (
                          <span key={item.regime}>
                            {item.regime.replaceAll('_', ' ')}{' '}
                            <em>{fmt(item.censored_followups)}</em>
                          </span>
                        ))}
                      </div>
                    ),
                  )}
                </div>
                <p className="ve-censor-limit">
                  “Future observation unavailable” means no qualifying synchronized follow-up was
                  recorded; it does not prove that the venue had no quote. Pending means no outcome
                  row existed in this read snapshot. See the linked artifact for every market, hour,
                  quality regime, and recorded censor reason.
                </p>
              </div>
            </details>
          )}
          {labelFeasibility && (
            <div className="ve-label-feasibility" aria-label="Frozen Mission 2 label feasibility">
              <div className="ve-label-heading">
                <strong>Frozen Mission 2 campaign · public markouts</strong>
                <span>
                  {labelFeasibility.analysis_version} ·{' '}
                  {labelFeasibility.source_kind.replaceAll('_', ' ')} · as of{' '}
                  {time(labelFeasibility.captured_at_utc)}
                </span>
              </div>
              <div className="ve-observatory-stats compact">
                <div>
                  <span>Decisions / markets</span>
                  <strong>
                    {fmt(labelFeasibility.decision_count)} / {fmt(labelFeasibility.market_count)}
                  </strong>
                </div>
                <div>
                  <span>Valid initial states</span>
                  <strong>{fmt(labelFeasibility.valid_initial_decisions)}</strong>
                </div>
                <div>
                  <span>Five-second observed</span>
                  <strong>
                    {fmt(labelFeasibility.five_second.observed)} /{' '}
                    {fmt(labelFeasibility.valid_initial_decisions)} ·{' '}
                    {rate(
                      labelFeasibility.five_second.observed,
                      labelFeasibility.valid_initial_decisions,
                    )}
                  </strong>
                </div>
                <div>
                  <span>Positive pre-fee starts / suitable target</span>
                  <strong className="none">
                    {fmt(labelFeasibility.economic_observations.pre_fee_positive_count)} /{' '}
                    {labelFeasibility.suitable_strategy_target_support
                      ? 'supported'
                      : 'unsupported'}
                  </strong>
                </div>
              </div>
              <div className="ve-label-table">
                <div className="ve-table-head">
                  <span>Horizon</span>
                  <span>Observed</span>
                  <span>Yield</span>
                  <span>No initial discrepancy</span>
                  <span>Execution unknown</span>
                </div>
                {labelFeasibility.horizons.map((row) => (
                  <div className="ve-table-row" key={row.horizon_ms}>
                    <strong>
                      {row.horizon_ms >= 1000
                        ? `${row.horizon_ms / 1000} s`
                        : `${row.horizon_ms} ms`}
                    </strong>
                    <span>{fmt(row.observed)}</span>
                    <span className="ve-yield">
                      {rate(row.observed, row.valid_initial_decisions)}
                    </span>
                    <span>{fmt(row.opportunity_target_status.no_initial_discrepancy ?? 0)}</span>
                    <span>{fmt(row.execution_ground_truth.unknown_counterfactual ?? 0)}</span>
                  </div>
                ))}
              </div>
              <p className="ve-label-note">
                At five seconds, all {fmt(labelFeasibility.five_second.observed)} observed starts
                had no initial discrepancy, undefined opportunity persistence, and unknown
                counterfactual execution outcomes. No orders were submitted; realized P&amp;L is
                absent. {labelFeasibility.assessment}
              </p>
              <a
                className="ve-latest-snapshot"
                href={labelFeasibility.artifact.url}
                target="_blank"
                rel="noreferrer"
              >
                Inspect hash-verified frozen label analysis <ArrowUpRight size={13} />
              </a>
            </div>
          )}
        </Panel>
      </div>

      <div className="ve-grid">
        <Panel
          eyebrow="SIMULATED · ASSUMPTIONS ONLY"
          title="Execution sensitivity"
          note={`${data.execution_sensitivity.quantity_shares_per_leg} shares per leg · full displayed depth · no empirical fill probability`}
        >
          <div className="ve-execution-pair">
            <div className="ve-execution-card favorable">
              <span>Completed pair · single-match rounding</span>
              <strong>
                {usdc(data.execution_sensitivity.completed_pair_pnl_single_match_usdc)}
              </strong>
            </div>
            <div className="ve-execution-card adverse">
              <span>Completed pair · fragmentation-safe fee bound</span>
              <strong>
                {usdc(data.execution_sensitivity.completed_pair_pnl_fragmentation_safe_usdc)}
              </strong>
            </div>
          </div>
          <dl className="ve-assumptions">
            <div>
              <dt>Adverse unmatched leg</dt>
              <dd>{usdc(`-${data.execution_sensitivity.unmatched_leg_loss_usdc}`)}</dd>
            </div>
            <div>
              <dt>Matched completions per unmatched event</dt>
              <dd>
                {Number(
                  data.execution_sensitivity.required_matched_completions_per_unmatched_event,
                ).toFixed(1)}
              </dd>
            </div>
            <div>
              <dt>Required matched rate at 1% unmatched</dt>
              <dd>
                {(
                  100 * Number(data.execution_sensitivity.required_matched_rate_at_1pct_unmatched)
                ).toFixed(1)}
                %
              </dd>
            </div>
            <div>
              <dt>Required matched rate at 5% unmatched</dt>
              <dd>
                {(
                  100 * Number(data.execution_sensitivity.required_matched_rate_at_5pct_unmatched)
                ).toFixed(1)}
                % ·{' '}
                {data.execution_sensitivity.break_even_at_5pct_unmatched_feasible
                  ? 'feasible'
                  : 'infeasible'}
              </dd>
            </div>
            <div>
              <dt>Completed pair at half displayed depth</dt>
              <dd>{usdc(data.execution_sensitivity.half_depth_single_match_pair_pnl_usdc)}</dd>
            </div>
          </dl>
          <div className="ve-caveat">
            <ShieldCheck size={16} />{' '}
            {data.execution_sensitivity.rates_are_estimates
              ? 'Rates are modeled estimates.'
              : 'Rates are sensitivity inputs, not estimates.'}{' '}
            Real fills, queue position and profitability remain unknown.
          </div>
        </Panel>

        <Panel
          eyebrow="OPTIMIZATION RESEARCH"
          title="Hypotheses and evidence"
          note={`${data.baseline_policies.count} baseline policies · ${data.baseline_policies.all_abstained ? 'all abstained' : 'actions recorded'} · ${data.research_status.hypotheses} hypotheses · ${data.research_status.experiments} experiments · ${data.research_status.models} Veritas models`}
        >
          <div className="ve-hypotheses">
            {data.research_status.recent_hypotheses.map((item) => (
              <article key={item.id}>
                <div>
                  <span>{item.id}</span>
                  <b>{item.result_status.replaceAll('_', ' ')}</b>
                </div>
                <h4>{item.title}</h4>
                <p>{item.decision}</p>
              </article>
            ))}
          </div>
        </Panel>

        <Panel
          eyebrow="ARENA / RESEARCH DIRECTOR"
          title="Bounded research activity"
          note="The Veritas Director checks for new finalized scans every 30 minutes and admits one bounded qualification job per scan; readiness and findings stay read-only."
        >
          {arenaActivityQuery.isPending ? (
            <p className="ve-observatory-note">Loading bounded Arena activity…</p>
          ) : arenaActivityQuery.isError || arenaActivity?.status !== 'available' ? (
            <p className="ve-observatory-note">Arena activity is unavailable.</p>
          ) : (
            <>
              <div className="ve-observatory-stats">
                <div>
                  <span>Active / queued jobs</span>
                  <strong>{fmt(arenaActivity.active_job_count)}</strong>
                  <small>{fmt(arenaActivity.queued_job_count)} queued in the bounded catalog</small>
                </div>
                <div>
                  <span>Active Director workflows</span>
                  <strong>{fmt(arenaActivity.active_director_count)}</strong>
                </div>
                <div>
                  <span>Active finite schedules</span>
                  <strong>{fmt(arenaActivity.active_schedule_count)}</strong>
                </div>
              </div>
              {arenaJobs.length + arenaDirectors.length + arenaSchedules.length === 0 ? (
                <p className="ve-observatory-note">
                  No Arena jobs, schedules, or Director activity is recorded.
                </p>
              ) : (
                <div className="ve-hypotheses">
                  {arenaJobs.slice(0, 5).map((job) => (
                    <article key={job.job_id ?? `${job.kind}-${job.state}`}>
                      <div>
                        <span>{job.kind?.replaceAll('_', ' ') ?? 'Arena job'}</span>
                        <b>{job.state ?? 'unknown'}</b>
                      </div>
                      <p>
                        {job.phase ?? job.job_id ?? 'No phase published'}
                        {job.progress && typeof job.progress.done === 'number'
                          ? ` · ${fmt(job.progress.done)} / ${fmt(job.progress.total ?? 0)}`
                          : ''}
                      </p>
                    </article>
                  ))}
                  {arenaDirectors.slice(0, 3).map((director) => (
                    <article key={director.director_id ?? director.current_stage ?? 'director'}>
                      <div>
                        <span>Research Director</span>
                        <b>{director.state ?? 'unknown'}</b>
                      </div>
                      <h4>
                        {director.current_stage ??
                          director.research_question ??
                          'No stage published'}
                      </h4>
                      {director.source_scan_id && (
                        <p>
                          Latest scan {director.source_scan_id}
                          {director.last_qualified_scan_id
                            ? ` · qualified ${director.last_qualified_scan_id}`
                            : ' · qualification pending'}
                        </p>
                      )}
                      {(director.strategy_readiness || director.model_readiness) && (
                        <p>
                          Strategy: {director.strategy_readiness?.replaceAll('_', ' ') ?? 'unknown'}
                          {' · Model: '}
                          {director.model_readiness?.replaceAll('_', ' ') ?? 'unknown'}
                        </p>
                      )}
                      {director.independent_confirmation_readiness && (
                        <p>
                          Confirmation:{' '}
                          {director.independent_confirmation_readiness.replaceAll('_', ' ')}
                        </p>
                      )}
                      {director.finalized_source_analysis && (
                        <p>
                          Finalized source:{' '}
                          {director.finalized_source_analysis.readiness?.replaceAll('_', ' ') ??
                            director.finalized_source_analysis.state?.replaceAll('_', ' ') ??
                            'unknown'}
                          {' · '}
                          {fmt(
                            director.finalized_source_analysis.processed_segment_count ?? 0,
                          )} / {fmt(director.finalized_source_analysis.catalog_segment_count ?? 0)}
                          {' segments · '}
                          {fmt(director.finalized_source_analysis.quality_valid_states ?? 0)}
                          {' quality-valid · '}
                          {fmt(
                            director.finalized_source_analysis.positive_full_depth_pre_fee_states ??
                              0,
                          )}
                          {' positive full-depth pre-fee'}
                        </p>
                      )}
                      {director.latest_finding && (
                        <>
                          <p>
                            {fmt(director.latest_finding.quality_valid_pairs ?? 0)} quality-valid
                            pairs across {fmt(director.latest_finding.unique_market_ids ?? 0)}{' '}
                            markets
                            {' · '}
                            {director.latest_finding.status?.replaceAll('_', ' ') ?? 'finding'}
                          </p>
                          {director.latest_finding.gross_candidate_evidence_count != null && (
                            <p>
                              Gross candidates:{' '}
                              {fmt(director.latest_finding.gross_candidate_evidence_count)}
                              {' · Source replay: '}
                              {director.latest_finding.gross_candidate_replay_status?.replaceAll(
                                '_',
                                ' ',
                              ) ?? 'unknown'}
                              {' · '}
                              {fmt(director.latest_finding.gross_candidate_replayed_count ?? 0)}
                              {' / '}
                              {fmt(director.latest_finding.gross_candidate_evidence_count)}
                              {' replayed'}
                              {director.latest_finding.gross_candidate_replay_complete === false
                                ? ' · incomplete'
                                : ''}
                            </p>
                          )}
                          {director.latest_finding.finding_id && (
                            <a
                              href={`/api/arena/findings/${encodeURIComponent(director.latest_finding.finding_id)}`}
                              target="_blank"
                              rel="noreferrer"
                            >
                              Open source and replay evidence
                            </a>
                          )}
                        </>
                      )}
                      {director.recommendation && <p>{director.recommendation}</p>}
                      {director.research_question && <p>{director.research_question}</p>}
                      {(director.recent_events?.length ?? 0) > 0 && (
                        <details className="ve-director-history">
                          <summary>
                            Recent Director history ({director.recent_events?.length ?? 0}
                            {director.recent_events_truncated ? '+' : ''} events)
                          </summary>
                          <div className="ve-director-history-list">
                            {director.recent_events?.map((event, index) => (
                              <div
                                className="ve-director-event"
                                key={`${event.recorded_at_utc ?? 'event'}-${event.state ?? index}`}
                              >
                                <div>
                                  <span>{event.stage ?? 'Research event'}</span>
                                  <b>{event.state ?? 'unknown'}</b>
                                </div>
                                <small>
                                  {event.recorded_at_utc ?? 'Time unavailable'}
                                  {event.scan_id ? ` · ${event.scan_id}` : ''}
                                  {event.job_id ? ` · ${event.job_id}` : ''}
                                  {event.finding_id ? ` · ${event.finding_id}` : ''}
                                </small>
                                {event.note && <p>{event.note}</p>}
                                {event.experiment_run_id && (
                                  <p>
                                    Experiment {event.experiment_run_id}
                                    {event.experiment_sha256
                                      ? ` · result ${event.experiment_sha256.slice(0, 12)}`
                                      : ''}
                                    {event.dataset_sha256
                                      ? ` · dataset ${event.dataset_sha256.slice(0, 12)}`
                                      : ''}
                                  </p>
                                )}
                                {event.source_revision_sha256 && (
                                  <p>Source revision {event.source_revision_sha256.slice(0, 12)}</p>
                                )}
                                {event.positive_states_by_gate && (
                                  <p>
                                    Positive states by gate:{' '}
                                    {Object.entries(event.positive_states_by_gate)
                                      .map(
                                        ([gate, count]) =>
                                          `${gate.replaceAll('_', ' ')} ${fmt(count)}`,
                                      )
                                      .join(' · ')}
                                  </p>
                                )}
                                {event.recommendation && <p>{event.recommendation}</p>}
                              </div>
                            ))}
                          </div>
                          {director.recent_events_truncated && (
                            <p className="ve-observatory-note">
                              The view shows up to eight hash-verified events and scans at most 128
                              event files per Director; the durable Arena archive retains the full
                              stream.
                            </p>
                          )}
                        </details>
                      )}
                    </article>
                  ))}
                  {arenaSchedules.slice(0, 3).map((schedule) => (
                    <article key={schedule.schedule_id ?? schedule.question ?? 'schedule'}>
                      <div>
                        <span>Finite research schedule</span>
                        <b>{schedule.state ?? 'unknown'}</b>
                      </div>
                      <h4>{schedule.question ?? 'No research question published'}</h4>
                      <p>
                        {fmt(schedule.steps.filter((step) => step.state !== 'COMPLETED').length)}{' '}
                        steps remain
                      </p>
                    </article>
                  ))}
                </div>
              )}
              {arenaAlerts.length > 0 && (
                <p className="ve-observatory-note">
                  Latest schedule alert:{' '}
                  {arenaAlerts[0].reason ?? 'Review the persisted Arena alert'}
                </p>
              )}
              {arenaActivity.invalid_artifact_count > 0 && (
                <p className="ve-observatory-note">
                  {fmt(arenaActivity.invalid_artifact_count)} malformed Arena activity artifacts
                  were omitted from this bounded view.
                </p>
              )}
              <div className="ve-research-action-row">
                <button
                  className="ve-research-action"
                  disabled={
                    observatoryDiscovery.latest_frame_protocol !==
                      'stratified-gamma-page-rotation-v2' ||
                    !observatoryDiscovery.latest_scan_id ||
                    !!existingQualificationJob ||
                    qualificationJobMutation.isPending
                  }
                  onClick={() => qualificationJobMutation.mutate()}
                >
                  {qualificationJobMutation.isPending
                    ? 'Queueing bounded qualification…'
                    : existingQualificationJob
                      ? `Qualification already ${existingQualificationJob.state ?? 'queued'}`
                      : 'Run bounded qualification in Arena'}
                </button>
                {qualificationJobMutation.error && (
                  <span role="status">{qualificationJobMutation.error.message}</span>
                )}
              </div>
              <p className="ve-observatory-note">
                The job reads finalized v4 public-snapshot events only, up to 512 events / 64 MiB,
                and writes an idempotent Arena finding. It makes no market requests and cannot
                modify collector, Reality, or campaign records.
              </p>
            </>
          )}
        </Panel>
      </div>

      <Panel
        eyebrow="PROVENANCE"
        title="Inspect versioned evidence"
        note="Every link returns a bounded JSON artifact with its SHA256 digest. The dashboard never embeds raw observations."
      >
        <div className="ve-artifacts">
          {data.artifacts.map((artifact) => (
            <a
              key={artifact.id}
              href={`/api/veritas/artifacts/${artifact.id}`}
              target="_blank"
              rel="noreferrer"
            >
              <Database size={15} />
              <span>{artifact.label}</span>
              <ArrowUpRight size={14} />
            </a>
          ))}
        </div>
      </Panel>

      <footer className="ve-limitations">
        <span>
          <ShieldCheck size={15} /> Interpretation limits
        </span>
        {data.limitations.map((item) => (
          <p key={item}>{item}</p>
        ))}
      </footer>
    </section>
  );
}
