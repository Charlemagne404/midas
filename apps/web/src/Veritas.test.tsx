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
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
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
          status: 'not_started',
          analysis_version: null,
          processed_snapshot_count: 0,
          pending_snapshot_count: 0,
          readiness: 'waiting_for_first_finalized_snapshot',
          coverage_window_hours: 0,
          first_captured_at_utc: null,
          last_captured_at_utc: null,
          observed_utc_days: [],
          discovery: {
            current_bounded_eligible_markets: 0,
            maximum_bounded_eligible_markets_seen: 0,
            unique_market_ids_observed: 0,
            selected_market_observations: 0,
            latest_phase: null,
            latest_scan_id: null,
            latest_snapshot_url: null,
            latest_selected_markets: 0,
            latest_stable_control_markets: 0,
            latest_rotating_markets: 0,
            latest_by_category: {},
            latest_by_liquidity: {},
            latest_by_expiry: {},
            latest_by_spread: {},
            latest_exclusions: {},
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
          { id: 'censoring', label: 'Read-only censoring by market, time, horizon and quality' },
        ],
        limitations: ['Displayed liquidity is not guaranteed executable quantity.'],
      }),
    }),
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
  expect(screen.getByText(/No finalized public snapshot has been indexed yet/)).toBeInTheDocument();
  expect(
    screen.getByText(/Real fills, queue position and profitability remain unknown/),
  ).toBeInTheDocument();
  expect(screen.getByText(/Latest read-only campaign snapshot/)).toBeInTheDocument();
  fireEvent.click(screen.getByText(/Inspect censoring by market and UTC hour/));
  expect(screen.getByText('market-a')).toBeInTheDocument();
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
