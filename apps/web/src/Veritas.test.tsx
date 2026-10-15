import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
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
        artifacts: [{ id: 'raw-funnel', label: 'Observed raw opportunity funnel' }],
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
  expect(screen.getByText('7.1% qualifying measurements')).toBeInTheDocument();
  expect(screen.getByText('354')).toBeInTheDocument();
  expect(screen.getAllByText('1,027').length).toBeGreaterThan(0);
  expect(screen.getByText('-1.03 USDC')).toBeInTheDocument();
  expect(
    screen.getByText(/Real fills, queue position and profitability remain unknown/),
  ).toBeInTheDocument();
  expect(screen.getByRole('link', { name: /Observed raw opportunity funnel/ })).toHaveAttribute(
    'href',
    '/api/veritas/artifacts/raw-funnel',
  );
});
