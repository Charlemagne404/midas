import { useQuery } from '@tanstack/react-query';
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

type Artifact = { id: string; label: string };

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
  followup_yield: { valid_initial_decisions: number; by_horizon: Horizon[] };
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
  artifacts: Artifact[];
  limitations: string[];
};

const fmt = (value: number) => value.toLocaleString('en-US');
const usdc = (value: string) => `${Number(value) >= 0 ? '+' : ''}${Number(value).toFixed(2)} USDC`;
const rate = (value: number, denominator: number) =>
  denominator ? `${((100 * value) / denominator).toFixed(1)}%` : '—';
const bytes = (value: number) => `${(value / 1024 / 1024).toFixed(1)} MiB`;
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
  const query = useQuery({
    queryKey: ['veritas', 'overview'],
    queryFn: () => api<Overview>('/veritas/overview'),
    refetchInterval: 60_000,
    staleTime: 30_000,
    retry: 1,
  });
  const data = query.data;

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
          note={`Observed and censored counts use ${fmt(denominator)} valid starts. Invalid initial states are shown separately; this one-day cohort is not venue-wide.`}
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
