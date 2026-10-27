import { Fragment, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { UseMutationResult } from '@tanstack/react-query';
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Beaker,
  BookOpenCheck,
  Boxes,
  CircleHelp,
  Database,
  GitBranch,
  Globe2,
  Layers3,
  Play,
  Radio,
  RefreshCw,
  Search,
  ShieldCheck,
  SlidersHorizontal,
} from 'lucide-react';
import { api } from './api';
import './frontier.css';

type Venue = 'polymarket' | 'kalshi' | 'kraken';
type Source = {
  venue: Venue;
  adapter_version: string;
  public_probe_enabled: boolean;
  probe_policy_block_reason?: string | null;
  capabilities: { capability: string; supported: boolean; state: string; reason: string }[];
  health: {
    state: string;
    last_success_at_utc: string | null;
    last_error_code: string | null;
    last_error: string | null;
    notes: string[];
  };
};
type Overview = {
  state: string;
  research_eligible_observations: number;
  research_only: boolean;
  live_execution: boolean;
  summary: {
    observations: number;
    relationships: number;
    relationship_reviews: number;
    runs: number;
    comparisons: number;
    markets_by_venue: Record<string, number>;
    instruments_by_venue: Record<string, number>;
    relationships_by_state: Record<string, number>;
    database_bytes: number;
    max_bytes: number;
  };
  sources: Source[];
  latest_evidence_at_utc: string | null;
  limitations: string[];
};
type SettlementAssetIdentity = {
  schema_version: number;
  kind: 'fiat' | 'token' | 'other';
  code: string;
  network_id: string | null;
  asset_reference: string | null;
};
type Market = {
  canonical_id: string;
  source_observation_record_id: string;
  native_market_id: string;
  native_event_id: string | null;
  native_event_title: string | null;
  outcome_label: string | null;
  venue: Venue;
  title: string;
  market_kind: string;
  lifecycle: string;
  description: string;
  base_asset: string | null;
  quote_asset: string | null;
  settlement_asset: string | null;
  settlement_asset_identity?: SettlementAssetIdentity | null;
  reported_settlement_value_dollars?: string | null;
  settlement_is_provisional?: boolean | null;
  payoff: {
    state_ids: string[];
    payout_currency: string | null;
    settlement_asset_identity?: SettlementAssetIdentity | null;
    exhaustive: boolean;
    verified: boolean;
    verification_basis: string;
  };
  resolution: {
    primary_rule: string | null;
    secondary_rule: string | null;
    authority: string | null;
    closes_at_utc: string | null;
    settles_at_utc: string | null;
    evidence_sha256: string | null;
    resolution_fingerprint: string | null;
    verified: boolean;
  };
  fees: {
    status: string;
    version: string | null;
    applies_to: string | null;
    rate: string | null;
    formula: string | null;
    fee_currency: string | null;
    fee_currency_identity?: SettlementAssetIdentity | null;
    source_url: string | null;
    note: string;
  };
  native_fields: Record<string, unknown>;
  instruments: {
    native_instrument_id: string;
    label: string;
    outcome_id: string | null;
    price_currency?: string | null;
    price_currency_identity?: SettlementAssetIdentity | null;
  }[];
  selected_components?: {
    venue: Venue;
    native_event_id: string | null;
    native_market_id: string;
    selected_side: 'yes' | 'no';
    yes_settlement_value_dollars?: string | null;
  }[];
  quality_flags: string[];
  provenance: { response_received_at_utc: string; raw_sha256: string; observation_id: string };
};
type KalshiMveSettlementAuditResponse = {
  audit: {
    schema_version: number;
    audit_algorithm_version: string;
    lifecycle: string;
    settlement_is_provisional: boolean | null;
    state: string;
    component_values: {
      native_market_id: string;
      selected_side: 'yes' | 'no';
      reported_yes_value_dollars: string | null;
      selected_position_value_dollars: string | null;
    }[];
    component_product_dollars: string | null;
    reported_settlement_value_dollars: string | null;
    missing_component_market_ids: string[];
    source_observation_id: string;
    source_raw_sha256: string;
    assumptions: string[];
    rule_source_urls: string[];
  };
  network_calls: number;
  candidate_generation: boolean;
  note: string;
};
type Book = {
  source_observation_record_id: string;
  venue: Venue;
  native_market_id: string;
  native_instrument_id: string;
  asks: { price: string; quantity: string; exchange_timestamp_utc: string | null }[];
  bids: { price: string; quantity: string; exchange_timestamp_utc: string | null }[];
  price_unit: string;
  price_currency?: string | null;
  price_currency_identity?: SettlementAssetIdentity | null;
  quantity_unit: string;
  received_at_utc: string;
  exchange_timestamp_utc: string | null;
  exchange_timestamp_semantics: string;
  quality_flags: string[];
  provenance: { observation_id: string; raw_sha256: string };
};
type Trade = {
  venue: Venue;
  native_market_id: string;
  native_trade_id: string | null;
  native_instrument_id: string | null;
  outcome_label: string | null;
  outcome_index: number | null;
  price: string;
  quantity: string;
  quote_currency: string | null;
  quote_currency_identity?: SettlementAssetIdentity | null;
  aggressor_side: string | null;
  exchange_timestamp_utc: string | null;
  received_at_utc: string;
  source_observation_record_id: string;
  source_raw_sha256: string;
};
type TradeResponse = {
  items: Trade[];
  pages: TradePage[];
  observation_count: number;
  trade_count: number;
  limit: number;
  offset: number;
};
type TradePage = {
  venue: Venue;
  market_id: string;
  condition_id?: string;
  page_limit: number;
  has_more: boolean;
  next_cursor: string | null;
  observation_id: string;
  received_at_utc: string;
};
type TradePageCaptureResult = {
  venue: Venue;
  market_id?: string;
  condition_id?: string;
  trade_count: number;
  observation_id: string;
  raw_sha256: string;
  page_limit: number;
  has_more: boolean;
  next_cursor: string | null;
  source_state: string;
  request_count_delta: number;
  network_calls_bounded_by: number;
  hypothetical_only: true;
  note: string;
};
type EventMarketsCaptureResult = {
  venue: Venue;
  market_id: string;
  native_event_id: string;
  event_title: string;
  market_count: number;
  observation_id: string;
  raw_sha256: string;
  request_count_delta: number;
  network_calls_bounded_by: number;
  hypothetical_only: true;
  note: string;
};
type KalshiMultivariateCaptureResult = {
  venue: 'kalshi';
  filter_type: 'series_ticker' | 'collection_ticker' | 'tickers';
  filter_value: string;
  event_count: number;
  market_count: number;
  events: {
    native_event_id: string;
    title: string;
    series_ticker: string | null;
    collection_ticker: string | null;
    market_count: number;
    member_list_state: 'included' | 'empty' | 'omitted';
  }[];
  complete_for_request: boolean;
  has_more_source_pages: boolean;
  observation_id: string;
  raw_sha256: string;
  request_count_delta: number;
  network_calls_bounded_by: number;
  hypothetical_only: true;
  note: string;
};
type KalshiFeeMetadataCaptureResult = {
  market_id: string;
  metadata: {
    series_ticker: string;
    event_fee_type_override: string | null;
    event_fee_multiplier_override: string | null;
    series_fee_type: string;
    series_fee_multiplier: string;
    effective_fee_type: string;
    effective_fee_multiplier: string;
    fee_resolution_state:
      'event_override' | 'series_inherited' | 'partial_override' | 'override_unreported';
    economics_state: 'unresolved';
    limitations: string[];
  };
  observation_ids: [string, string];
  raw_sha256: { event: string; series: string };
  fee_cost_modeled: false;
  note: string;
};
type KalshiMveComponentMarketCaptureResult = {
  parent_market_id: string;
  component_market_id: string;
  market: Market;
  observation_id: string;
  raw_sha256: string;
  request_count_delta: number;
  network_calls_bounded_by: number;
  combo_payoff_verified: false;
  hypothetical_only: true;
  note: string;
};
type KalshiFeeScenarioFill = {
  instrumentId: string;
  side: 'buy' | 'sell';
  price: string;
  quantity: string;
};
type KalshiFeeOrderSensitivityResponse = {
  market_id: string;
  estimate: {
    model_version: string;
    series_ticker: string;
    effective_fee_type: string;
    effective_fee_multiplier: string;
    fee_resolution_state: 'event_override' | 'series_inherited';
    input_received_at_utc: [string, string];
    order_fills: {
      native_instrument_id: string;
      side: 'buy' | 'sell';
      price_usd: string;
      quantity_contracts: string;
    }[];
    scenarios: {
      account_precision_class: string;
      balance_quantum: string;
      fills: {
        fill_index: number;
        native_instrument_id: string;
        side: 'buy' | 'sell';
        trade_fee_rounded_to_microdollar: string;
        rounding_fee_usd: string;
        rebate_usd: string;
        accumulated_rounding_after_rebate_usd: string;
        net_fee_usd: string;
      }[];
      total_trade_fee_usd: string;
      total_rounding_fee_usd: string;
      total_rebate_usd: string;
      total_net_fee_usd: string;
      total_balance_change_usd: string;
    }[];
    calculation_sha256: string;
    assumptions: string[];
  };
  hypothetical_only: true;
  candidate_net_economics_modified: false;
  note: string;
};
type Relationship = {
  relationship_id: string;
  left_market_id: string;
  right_market_id: string;
  relationship_type: string;
  state: string;
  confidence: string;
  reason: string;
  supersedes?: string | null;
  review_target_relationship_id: string;
  latest_review: {
    review_id: string;
    decision: string;
    reviewer_label: string;
    reason: string;
    evidence_observation_ids: string[];
    created_at_utc: string;
  } | null;
  evidence: {
    method: string;
    matcher_version?: string;
    verifier_version?: string | null;
    observation_ids: string[];
    source_fields: string[];
    details: string[];
  }[];
};
type GraphNode = {
  market_id: string;
  market: Omit<Market, 'source_observation_record_id'> | null;
  source_observation_record_id: string | null;
  market_record_available: boolean;
};
type GraphResponse = {
  nodes: GraphNode[];
  edges: Relationship[];
  center_market_id: string | null;
  search: string | null;
  depth: number;
  edge_limit: number;
  returned_nodes: number;
  returned_edges: number;
  truncated_by_edge_limit: boolean;
  relationship_scan_limit: number;
  relationships_scanned: number;
  relationship_scan_may_be_incomplete: boolean;
  next_cursor: string | null;
  source_market_window_limit: number;
};
type GraphPoint = { id: string; title: string; venue: string; x: number; y: number };
type Candidate = {
  candidate_id: string;
  family: string;
  classification: string;
  hypothetical: boolean;
  practical_eligibility: boolean;
  venues: string[];
  legs: {
    venue: string;
    native_market_id: string;
    instrument_id: string;
    outcome_id: string;
    quantity: string;
    quoted_ask: string;
    modeled_buy_price: string;
    modeled_fee: string | null;
    quote_currency?: string | null;
    quote_currency_identity?: SettlementAssetIdentity | null;
    displayed_depth: string;
    book_observation_id: string;
  }[];
  gross_cost: string | null;
  modeled_fees: string | null;
  modeled_net_cost: string | null;
  outcome_payout_by_state: Record<string, string>;
  gross_pnl_by_state: Record<string, string>;
  net_pnl_by_state: Record<string, string>;
  worst_case_gross_pnl: string | null;
  worst_case_net_pnl: string | null;
  capital_by_venue: Record<string, string>;
  capital_currency_identity?: SettlementAssetIdentity | null;
  one_sided_fill_sensitivity?: {
    model_version: string;
    leg_count: number;
    pattern_space_size: number;
    fees_complete: boolean;
    worst_before_fees: {
      terminal_state_id: string;
      filled_leg_ids: string[];
      unfilled_leg_ids: string[];
      pnl_before_fees: string;
      pnl_after_fees: string | null;
    };
    worst_after_fees: {
      terminal_state_id: string;
      filled_leg_ids: string[];
      unfilled_leg_ids: string[];
      pnl_before_fees: string;
      pnl_after_fees: string | null;
    } | null;
    assumptions: string[];
  } | null;
  received_skew_ms: number | null;
  exchange_skew_ms: number | null;
  timing_verified: boolean;
  independent_audit?: {
    disposition: string;
    input_sha256: string;
    checked_market_count: number;
    checked_leg_count: number;
    recomputed_gross_cost: string | null;
    recomputed_modeled_fees: string | null;
    recomputed_modeled_net_cost: string | null;
    recomputed_worst_case_gross_pnl: string | null;
    recomputed_worst_case_net_pnl: string | null;
    recomputed_received_skew_ms?: number | null;
    recomputed_exchange_skew_ms?: number | null;
    recomputed_timing_verified?: boolean | null;
    checks: string[];
    message: string;
  } | null;
  assumptions: string[];
  reasons: string[];
  evidence_sha256: string;
};
type Run = {
  run_id: string;
  created_at_utc: string;
  result_sha256: string;
  result: {
    manifest: {
      replay_version: string;
      code_version: string;
      normalized_input_sha256: string;
      market_observation_ids: string[];
      fee_metadata_observation_ids?: string[];
      book_observation_ids: string[];
      relationship_ids: string[];
      as_of_utc: string;
      scenario: Record<string, string | number>;
    };
    candidates: Candidate[];
    classification_counts: Record<string, number>;
  };
};
type ReplayComparison = {
  comparison_id: string;
  evidence_input_sha256: string;
  as_of_utc: string;
  result_sha256: string;
  arms: [
    {
      scenario: Record<string, string | number>;
      run_id: string;
      result_sha256: string;
      candidate_count: number;
      classification_counts: Record<string, number>;
      audit_disposition_counts: Record<string, number>;
      positive_gross_count: number;
      positive_net_count: number;
      unknown_net_count: number;
    },
    {
      scenario: Record<string, string | number>;
      run_id: string;
      result_sha256: string;
      candidate_count: number;
      classification_counts: Record<string, number>;
      audit_disposition_counts: Record<string, number>;
      positive_gross_count: number;
      positive_net_count: number;
      unknown_net_count: number;
    },
  ];
  delta: {
    baseline_scenario: string;
    compared_scenario: string;
    matched_candidate_count: number;
    unchanged_classification_count: number;
    changed_classification_count: number;
    baseline_only_candidate_count: number;
    compared_only_candidate_count: number;
    classification_count_delta: Record<string, number>;
    positive_gross_count_delta: number;
    positive_net_count_delta: number;
    unknown_net_count_delta: number;
  };
};
type ReplayComparisonRecord = {
  comparison_id: string;
  created_at_utc: string;
  result_sha256: string;
  result: ReplayComparison;
};
type FrontierArenaReplayJob = {
  job_id: string;
  state: string;
  created_at: number | null;
  updated_at: number | null;
  elapsed_seconds: number | null;
  progress: { done?: number; total?: number } | null;
  phase: string | null;
  error: string | null;
  snapshot_id: string | null;
  snapshot_sha256: string | null;
  runtime_profile: {
    worker_process_user_cpu_seconds?: number;
    worker_process_system_cpu_seconds?: number;
    worker_process_peak_rss_bytes?: number;
  } | null;
  result: {
    comparison_id?: string;
    frontier_replay_sha256?: string;
  } | null;
};
type FrontierArenaReplayJobs = {
  items: FrontierArenaReplayJob[];
  limit: number;
  scanned: number;
  scan_bound: number;
  scan_may_be_incomplete: boolean;
  research_only: true;
};
type FrontierArenaReplayResult = {
  artifact: {
    comparison: ReplayComparison;
    snapshot_id: string;
    snapshot_sha256: string;
    result_sha256: string;
  };
  research_only: true;
  orders_submitted: false;
  authenticated_requests: false;
  integrity_verified: true;
};
type Readiness = { gates: { name: string; state: string; detail: string }[] };
type ListResponse<T> = { items: T[]; returned: number; limit: number; offset: number };
type ObservationEvidence = {
  observation_id: string;
  raw_sha256: string;
  row_sha256: string;
  raw: {
    request_url: string;
    http_status: number;
    raw_body: string;
    adapter_version: string;
  };
};
type Section =
  'overview' | 'sources' | 'markets' | 'relationships' | 'opportunities' | 'workbench' | 'replay';

const sections: { id: Section; label: string; icon: typeof Globe2 }[] = [
  { id: 'overview', label: 'Overview', icon: Activity },
  { id: 'sources', label: 'Exchanges', icon: Globe2 },
  { id: 'markets', label: 'Markets', icon: Layers3 },
  { id: 'relationships', label: 'Relationship graph', icon: GitBranch },
  { id: 'opportunities', label: 'Candidates', icon: Boxes },
  { id: 'workbench', label: 'Economic workbench', icon: SlidersHorizontal },
  { id: 'replay', label: 'Replay & readiness', icon: BookOpenCheck },
];

const label = (value: string) => value.replaceAll('_', ' ');
const count = (value: number | null | undefined) => (value == null ? '—' : value.toLocaleString());
const money = (value: string | number | null | undefined) =>
  value == null
    ? 'Not established'
    : Number(value).toLocaleString(undefined, { maximumFractionDigits: 4 });
type ExactMoney = { coefficient: bigint; scale: number };
const parseExactMoney = (value: string): ExactMoney | null => {
  const trimmed = value.trim();
  if (trimmed.length === 0 || trimmed.length > 110) return null;
  const match = /^(\d{1,36})(?:\.(\d{1,36}))?(?:[eE]([+-]?\d{1,2}))?$/.exec(trimmed);
  if (!match) return null;
  const whole = match[1];
  const fraction = match[2] ?? '';
  const exponent = match[3] ? Number(match[3]) : 0;
  if (whole.length + fraction.length > 72 || Math.abs(exponent) > 36) return null;
  let coefficient = BigInt(`${whole}${fraction}`);
  let scale = fraction.length - exponent;
  if (scale < 0) {
    if (whole.length + fraction.length - scale > 72) return null;
    coefficient *= 10n ** BigInt(-scale);
    return { coefficient, scale: 0 };
  }
  while (scale > 0 && coefficient % 10n === 0n) {
    coefficient /= 10n;
    scale -= 1;
  }
  if (scale > 36) return null;
  return { coefficient, scale };
};
const compareExactMoney = (left: ExactMoney, right: ExactMoney) => {
  const scale = Math.max(left.scale, right.scale);
  const leftScaled = left.coefficient * 10n ** BigInt(scale - left.scale);
  const rightScaled = right.coefficient * 10n ** BigInt(scale - right.scale);
  return leftScaled === rightScaled ? 0 : leftScaled < rightScaled ? -1 : 1;
};
const time = (value: string | null | undefined) =>
  value ? new Date(value).toLocaleString() : 'Not recorded';
const shortHash = (value: string | undefined) => (value ? `${value.slice(0, 12)}…` : '—');
const settlementIdentityLabel = (identity: SettlementAssetIdentity | null | undefined) => {
  if (!identity) return 'Identity not established';
  if (identity.kind === 'fiat') return `fiat:${identity.code}`;
  return `${identity.kind}:${identity.code}:${identity.network_id ?? 'network unknown'}:${identity.asset_reference ?? 'reference unknown'}`;
};
const venueLabel = (value: string) =>
  ({ polymarket: 'Polymarket', kalshi: 'Kalshi', kraken: 'Kraken Spot' })[value] ?? value;

function StateBadge({ state }: { state: string }) {
  const tone = ['HEALTHY', 'PASS', 'VERIFIED'].includes(state.toUpperCase())
    ? 'good'
    : [
          'DEGRADED',
          'HYPOTHESIS',
          'CONDITIONAL',
          'INCOMPLETE',
          'NOT_EVALUATED',
          'LIVE_VALIDATION_PENDING',
          'REVIEW_REQUIRED',
        ].includes(state.toUpperCase())
      ? 'watch'
      : ['FAILED', 'BLOCKED', 'REJECTED', 'DISAGREEMENT'].includes(state.toUpperCase())
        ? 'bad'
        : 'quiet';
  return <span className={`fr-state ${tone}`}>{label(state)}</span>;
}

function EmptyState({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="fr-empty">
      <CircleHelp size={20} />
      <strong>{title}</strong>
      <p>{detail}</p>
    </div>
  );
}

function Metric({
  title,
  value,
  note,
  icon: Icon,
}: {
  title: string;
  value: string;
  note: string;
  icon: typeof Activity;
}) {
  return (
    <article className="fr-metric">
      <div>
        <span>{title}</span>
        <Icon size={15} />
      </div>
      <strong>{value}</strong>
      <small>{note}</small>
    </article>
  );
}

function RelationshipGraph({
  relationships,
  marketById,
  selectedId,
  onSelect,
}: {
  relationships: Relationship[];
  marketById: Map<string, Market>;
  selectedId: string | null;
  onSelect: (relationshipId: string) => void;
}) {
  const graph = useMemo(() => {
    const venueOrder = ['polymarket', 'kalshi', 'kraken', 'unknown'];
    const ids = new Set(
      relationships.flatMap((edge) => [edge.left_market_id, edge.right_market_id]),
    );
    const groups = new Map<string, string[]>();
    for (const id of ids) {
      const venue = marketById.get(id)?.venue ?? 'unknown';
      const group = groups.get(venue) ?? [];
      group.push(id);
      groups.set(venue, group);
    }
    const centers: Record<string, number> = {
      polymarket: 170,
      kalshi: 500,
      kraken: 830,
      unknown: 500,
    };
    const nodes = new Map<string, GraphPoint>();
    let maxRows = 0;
    for (const venue of venueOrder) {
      const group = (groups.get(venue) ?? []).sort();
      maxRows = Math.max(maxRows, group.length);
      group.forEach((id, index) => {
        const market = marketById.get(id);
        nodes.set(id, {
          id,
          title: market?.title ?? id,
          venue,
          x: centers[venue],
          y: 78 + index * 66,
        });
      });
    }
    return { nodes, height: Math.max(250, 126 + maxRows * 66) };
  }, [relationships, marketById]);

  if (!relationships.length) return null;
  const color = (state: string) =>
    ({
      verified: '#83c69a',
      rejected: '#d4888f',
      hypothesis: '#d5b46d',
      ambiguous: '#8ea8c0',
      superseded: '#87909c',
    })[state] ?? '#a2acb8';
  const venueName = (venue: string) =>
    ({
      polymarket: 'POLYMARKET',
      kalshi: 'KALSHI',
      kraken: 'KRAKEN SPOT',
      unknown: 'NOT IN LOADED WINDOW',
    })[venue] ?? venue.toUpperCase();

  return (
    <div className="fr-network-shell">
      <div className="fr-network-head">
        <div>
          <strong>Bounded relationship network</strong>
          <span>{relationships.length} edges · select an edge to inspect its evidence below</span>
        </div>
        <span className="fr-network-legend">
          <i /> hypothesis <i className="verified" /> verified <i className="rejected" /> rejected
        </span>
      </div>
      <div className="fr-network-scroll">
        <svg
          className="fr-network-svg"
          viewBox={`0 0 1000 ${graph.height}`}
          height={graph.height}
          role="group"
          aria-label={`Relationship network showing ${relationships.length} bounded market relationships`}
        >
          {[
            ['polymarket', 170],
            ['kalshi', 500],
            ['kraken', 830],
          ].map(([venue, x]) => (
            <text
              key={String(venue)}
              className="fr-network-column"
              x={Number(x)}
              y="24"
              textAnchor="middle"
            >
              {venueName(String(venue))}
            </text>
          ))}
          {relationships.map((edge) => {
            const left = graph.nodes.get(edge.left_market_id);
            const right = graph.nodes.get(edge.right_market_id);
            if (!left || !right) return null;
            const picked = edge.relationship_id === selectedId;
            const edgeColor = color(edge.state);
            const labelX = left.x === right.x ? left.x + 50 : (left.x + right.x) / 2;
            const labelY = (left.y + right.y) / 2 - 8;
            const relationshipName = label(edge.relationship_type);
            const action = () => onSelect(edge.relationship_id);
            return (
              <g
                key={edge.relationship_id}
                className={`fr-network-edge${picked ? ' selected' : ''}`}
                role="button"
                tabIndex={0}
                aria-pressed={picked}
                aria-label={`${relationshipName} ${edge.state}: ${left.title} and ${right.title}`}
                onClick={action}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    action();
                  }
                }}
              >
                <title>{`${edge.reason} · ${edge.state} · score ${edge.confidence}`}</title>
                <line
                  className="fr-network-hit"
                  x1={left.x}
                  y1={left.y}
                  x2={right.x}
                  y2={right.y}
                />
                <line
                  className="fr-network-visible"
                  x1={left.x}
                  y1={left.y}
                  x2={right.x}
                  y2={right.y}
                  stroke={edgeColor}
                  strokeDasharray={edge.state === 'hypothesis' ? '5 5' : undefined}
                />
                <text x={labelX} y={labelY} textAnchor="middle">
                  {relationshipName.slice(0, 26)}
                </text>
              </g>
            );
          })}
          {[...graph.nodes.values()].map((node) => (
            <g key={node.id} className={`fr-network-node ${node.venue}`}>
              <title>{`${venueName(node.venue)} · ${node.title} · ${node.id}`}</title>
              <rect x={node.x - 104} y={node.y - 20} width="208" height="40" rx="5" />
              <circle cx={node.x - 88} cy={node.y} r="4" />
              <text className="fr-network-venue" x={node.x - 77} y={node.y - 3}>
                {venueName(node.venue)}
              </text>
              <text className="fr-network-title" x={node.x - 77} y={node.y + 10}>
                {node.title.slice(0, 24)}
              </text>
            </g>
          ))}
        </svg>
      </div>
    </div>
  );
}

function RelationshipReviewForm({
  relationship,
  reviewTargetId,
  left,
  right,
}: {
  relationship: Relationship;
  reviewTargetId: string;
  left?: Market;
  right?: Market;
}) {
  const [open, setOpen] = useState(false);
  const [decision, setDecision] = useState<'rejected' | 'ambiguous' | 'verified'>('ambiguous');
  const [reviewer, setReviewer] = useState('');
  const [reason, setReason] = useState('');
  const [assertion, setAssertion] = useState('');
  const [stateMapping, setStateMapping] = useState('');
  const [instrumentMapping, setInstrumentMapping] = useState('');
  const queryClient = useQueryClient();
  const evidenceIds = [
    ...new Set(
      [left?.source_observation_record_id, right?.source_observation_record_id].filter(
        (id): id is string => Boolean(id),
      ),
    ),
  ];
  const evidenceReady = Boolean(
    left?.source_observation_record_id && right?.source_observation_record_id,
  );
  const review = useMutation({
    mutationFn: async () => {
      const parseMapping = (value: string, title: string) => {
        if (!value.trim()) return {};
        const parsed: unknown = JSON.parse(value);
        if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed))
          throw new Error(`${title} must be a JSON object of string identifiers`);
        return parsed as Record<string, string>;
      };
      return api(`/frontier/relationships/${reviewTargetId}/review`, {
        method: 'POST',
        body: JSON.stringify({
          decision,
          reviewer_label: reviewer,
          reason,
          evidence_observation_ids: evidenceIds,
          external_assertion_id: decision === 'verified' ? assertion : undefined,
          state_mapping: decision === 'verified' ? parseMapping(stateMapping, 'State mapping') : {},
          instrument_mapping:
            decision === 'verified' ? parseMapping(instrumentMapping, 'Instrument mapping') : {},
          expected_latest_review_id: relationship.latest_review?.review_id ?? null,
        }),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['frontier'] });
      setOpen(false);
    },
  });

  return (
    <div className="fr-review-wrap">
      {relationship.latest_review && (
        <div className="fr-review-history">
          <StateBadge state={relationship.latest_review.decision} />
          <span>
            Reviewed by self-attributed label “{relationship.latest_review.reviewer_label}” ·{' '}
            {time(relationship.latest_review.created_at_utc)}
          </span>
          <p>{relationship.latest_review.reason}</p>
        </div>
      )}
      <button
        className="fr-inspect-button"
        type="button"
        onClick={() => setOpen((value) => !value)}
      >
        {open ? 'Close review' : relationship.latest_review ? 'Append review' : 'Review hypothesis'}
      </button>
      {open && (
        <form
          className="fr-review-form"
          onSubmit={(event) => {
            event.preventDefault();
            review.mutate();
          }}
        >
          <div className="fr-review-compared">
            {[left, right].map((market, index) => (
              <section key={market?.canonical_id ?? index}>
                <strong>{index === 0 ? 'Left market' : 'Right market'}</strong>
                <span>
                  {market?.title ?? 'Market details are outside the loaded evidence window'}
                </span>
                <small>
                  {market?.venue ?? 'unknown'} · {market?.market_kind ?? 'unknown'} ·{' '}
                  {market?.payoff.verified && market.payoff.exhaustive
                    ? `verified states: ${market.payoff.state_ids.join(', ')}`
                    : 'payoff not verified/exhaustive'}
                </small>
                <small>
                  Payout/settlement: {market?.payoff.payout_currency ?? 'unknown'} /{' '}
                  {market?.settlement_asset ?? 'unknown'}
                </small>
                <small>
                  Resolution: {market?.resolution.authority ?? 'authority unknown'} ·{' '}
                  {market?.resolution.resolution_fingerprint ?? 'fingerprint unknown'}
                </small>
                <small>
                  Closes {time(market?.resolution.closes_at_utc)} · settles{' '}
                  {time(market?.resolution.settles_at_utc)}
                </small>
              </section>
            ))}
          </div>
          <p>
            This creates an immutable, self-attributed review. A reviewer label is not
            authenticated. Both source market records are attached as evidence. Any external
            assertion ID is a reference only; MIDAS does not fetch or authenticate that assertion.
          </p>
          <label>
            Decision
            <select
              value={decision}
              onChange={(event) => setDecision(event.target.value as typeof decision)}
            >
              <option value="ambiguous">Ambiguous</option>
              <option value="rejected">Reject relationship</option>
              <option value="verified">Verify same payoff</option>
            </select>
          </label>
          <label>
            Reviewer label
            <input
              value={reviewer}
              onChange={(event) => setReviewer(event.target.value)}
              maxLength={80}
              required
            />
          </label>
          <label>
            Review reason
            <textarea
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              minLength={5}
              maxLength={1000}
              required
            />
          </label>
          {decision === 'verified' && (
            <>
              <label>
                Independent assertion ID
                <input
                  value={assertion}
                  onChange={(event) => setAssertion(event.target.value)}
                  maxLength={120}
                  required
                />
              </label>
              <label>
                Complete state mapping (JSON)
                <textarea
                  value={stateMapping}
                  onChange={(event) => setStateMapping(event.target.value)}
                  placeholder={'{"left-state":"right-state"}'}
                  required
                />
              </label>
              <label>
                Complete instrument mapping (JSON)
                <textarea
                  value={instrumentMapping}
                  onChange={(event) => setInstrumentMapping(event.target.value)}
                  placeholder={'{"left-instrument":"right-instrument"}'}
                  required
                />
              </label>
              <p className="fr-review-verifier-note">
                Mapping keys are from the left node to the right node. The independent verifier
                checks exhaustive outcomes, payout vectors, currency, resolution fingerprints,
                authorities, and settlement timing against stored market fields. It does not verify
                the source truth of those fields or the assertion ID.
              </p>
            </>
          )}
          <small>Source evidence: {evidenceIds.map(shortHash).join(' · ') || 'unavailable'}</small>
          {review.isError && <InlineError message={review.error.message} />}
          {review.isSuccess && <StateBadge state="recorded" />}
          <button className="fr-action" type="submit" disabled={review.isPending || !evidenceReady}>
            {review.isPending ? 'Recording…' : 'Record immutable review'}
          </button>
        </form>
      )}
    </div>
  );
}

export function Frontier({ onNavigate }: { onNavigate?: (page: string) => void }) {
  const [section, setSection] = useState<Section>('overview');
  const [search, setSearch] = useState('');
  const [selectedMarketId, setSelectedMarketId] = useState<string | null>(null);
  const [selectedRelationshipId, setSelectedRelationshipId] = useState<string | null>(null);
  const [relationshipState, setRelationshipState] = useState('all');
  const [graphCenterMarketId, setGraphCenterMarketId] = useState('');
  const [graphDepth, setGraphDepth] = useState(1);
  const [graphPageCursors, setGraphPageCursors] = useState<(string | null)[]>([null]);
  const [graphPageIndex, setGraphPageIndex] = useState(0);
  const [graphQuerySession, setGraphQuerySession] = useState(0);
  const [tradeVenue, setTradeVenue] = useState<Venue>('polymarket');
  const [tradeMarketId, setTradeMarketId] = useState('');
  const [tradePageCursor, setTradePageCursor] = useState<{
    marketKey: string;
    cursor: string | null;
  } | null>(null);
  const [slippage, setSlippage] = useState('25');
  const [delay, setDelay] = useState('500');
  const [fillPercent, setFillPercent] = useState('80');
  const [selectedArenaReplayId, setSelectedArenaReplayId] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const options = { staleTime: 10_000, retry: 1 };
  const resetGraphPagination = () => {
    setGraphPageCursors([null]);
    setGraphPageIndex(0);
    setGraphQuerySession((current) => current + 1);
  };
  const overview = useQuery({
    queryKey: ['frontier', 'overview'],
    queryFn: () => api<Overview>('/frontier/overview'),
    ...options,
  });
  const sources = useQuery({
    queryKey: ['frontier', 'sources'],
    queryFn: () => api<{ items: Source[] }>('/frontier/sources'),
    ...options,
  });
  const markets = useQuery({
    queryKey: ['frontier', 'markets'],
    queryFn: () => api<ListResponse<Market>>('/frontier/markets?limit=100'),
    ...options,
  });
  const books = useQuery({
    queryKey: ['frontier', 'books'],
    queryFn: () => api<ListResponse<Book>>('/frontier/books?limit=100'),
    ...options,
  });
  const trades = useQuery({
    queryKey: ['frontier', 'trades'],
    queryFn: () => api<TradeResponse>('/frontier/trades?limit=100'),
    ...options,
  });
  const graphCursor = graphPageCursors[graphPageIndex] ?? null;
  const graphPageSize = graphCenterMarketId ? 30 : 100;
  const graph = useQuery({
    queryKey: [
      'frontier',
      'graph',
      graphCenterMarketId,
      graphDepth,
      graphPageSize,
      graphCursor,
      graphQuerySession,
    ],
    queryFn: () => {
      const params = new URLSearchParams({
        depth: String(graphDepth),
        limit: String(graphPageSize),
      });
      if (graphCenterMarketId) params.set('center_market_id', graphCenterMarketId);
      if (graphCursor) params.set('cursor', graphCursor);
      return api<GraphResponse>(`/frontier/graph?${params.toString()}`);
    },
    ...options,
  });
  const candidates = useQuery({
    queryKey: ['frontier', 'opportunities'],
    queryFn: () => api<ListResponse<Candidate>>('/frontier/opportunities?limit=100'),
    ...options,
  });
  const runs = useQuery({
    queryKey: ['frontier', 'runs'],
    queryFn: () => api<ListResponse<Run>>('/frontier/runs?limit=30'),
    ...options,
  });
  const comparisons = useQuery({
    queryKey: ['frontier', 'comparisons'],
    queryFn: () => api<ListResponse<ReplayComparisonRecord>>('/frontier/comparisons?limit=30'),
    ...options,
  });
  const readiness = useQuery({
    queryKey: ['frontier', 'readiness'],
    queryFn: () => api<Readiness>('/frontier/readiness'),
    ...options,
  });
  const arenaReplayJobs = useQuery({
    queryKey: ['frontier', 'arena-replay-jobs'],
    queryFn: () => api<FrontierArenaReplayJobs>('/arena/frontier-replays?limit=20'),
    enabled: section === 'replay',
    refetchInterval: (query) =>
      query.state.data?.items.some((job) => ['QUEUED', 'RUNNING'].includes(job.state))
        ? 2000
        : false,
  });
  const listedArenaReplayJobs = arenaReplayJobs.data?.items ?? [];
  const selectedArenaReplayJob =
    listedArenaReplayJobs.find((job) => job.job_id === selectedArenaReplayId) ??
    listedArenaReplayJobs[0] ??
    null;
  const arenaReplayResult = useQuery({
    queryKey: ['frontier', 'arena-replay-result', selectedArenaReplayJob?.job_id],
    queryFn: () =>
      api<FrontierArenaReplayResult>(
        `/arena/jobs/${encodeURIComponent(selectedArenaReplayJob!.job_id)}/frontier-replay`,
      ),
    enabled: section === 'replay' && selectedArenaReplayJob?.state === 'COMPLETED',
    retry: false,
  });

  const tradeMarketKey = `${tradeVenue}:${tradeMarketId}`;
  const recordedTradePage = (trades.data?.pages ?? []).find(
    (page) => page.venue === tradeVenue && page.market_id === tradeMarketId,
  );
  const activeTradeCursor =
    tradePageCursor?.marketKey === tradeMarketKey
      ? tradePageCursor.cursor
      : (recordedTradePage?.next_cursor ?? null);
  const tradeMarketOptions = (markets.data?.items ?? []).flatMap((market) => {
    if (market.venue !== tradeVenue) return [];
    const marketId =
      tradeVenue === 'polymarket' ? market.native_fields?.conditionId : market.native_market_id;
    return typeof marketId === 'string' && marketId.length > 0 ? [{ market, marketId }] : [];
  });
  const tradePageProbeEnabled = (sources.data?.items ?? []).some(
    (source) =>
      source.venue === tradeVenue &&
      source.public_probe_enabled &&
      source.capabilities.some(
        (capability) => capability.capability === 'paginated_public_trades' && capability.supported,
      ),
  );
  const kalshiFeeMetadataProbeEnabled = (sources.data?.items ?? []).some(
    (source) =>
      source.venue === 'kalshi' &&
      source.public_probe_enabled &&
      source.capabilities.some(
        (capability) => capability.capability === 'fee_metadata' && capability.supported,
      ),
  );
  const kalshiMarketMetadataProbeEnabled = (sources.data?.items ?? []).some(
    (source) =>
      source.venue === 'kalshi' &&
      source.public_probe_enabled &&
      source.capabilities.some(
        (capability) => capability.capability === 'market_metadata' && capability.supported,
      ),
  );
  const eventMarketGroupsProbeEnabledFor = (venue: Venue) =>
    (sources.data?.items ?? []).some(
      (source) =>
        source.venue === venue &&
        source.public_probe_enabled &&
        source.capabilities.some(
          (capability) => capability.capability === 'event_market_groups' && capability.supported,
        ),
    );

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['frontier'] });
  const propose = useMutation({
    mutationFn: () =>
      api<{ proposed: number; persisted: number }>(
        '/frontier/relationships/propose?market_limit=200&max_pairs=1000',
        { method: 'POST' },
      ),
    onSuccess: refresh,
  });
  const replay = useMutation({
    mutationFn: () =>
      api<Run['result']>(
        '/frontier/replay?market_limit=200&book_limit=200&relationship_limit=500',
        {
          method: 'POST',
          body: JSON.stringify({
            name: 'frontier-ui-sensitivity',
            slippage_bps: slippage,
            execution_delay_ms: Number(delay),
            fill_fraction: (Number(fillPercent) / 100).toFixed(4),
            quote_decay_bps_per_second: '15',
          }),
        },
      ),
    onSuccess: refresh,
  });
  const pairedReplay = useMutation({
    mutationFn: () =>
      api<{ comparison: ReplayComparison; runs: { run_id: string; result_sha256: string }[] }>(
        '/frontier/replay/compare',
        {
          method: 'POST',
          body: JSON.stringify({
            scenarios: [
              { name: 'quoted baseline' },
              {
                name: 'current assumptions',
                slippage_bps: slippage,
                execution_delay_ms: Number(delay),
                fill_fraction: (Number(fillPercent) / 100).toFixed(4),
                quote_decay_bps_per_second: '15',
              },
            ],
          }),
        },
      ),
    onSuccess: refresh,
  });
  const arenaReplay = useMutation({
    mutationFn: () =>
      api<{
        job_id: string;
        state: string;
        created_at: number;
        updated_at: number;
        progress: FrontierArenaReplayJob['progress'];
        phase?: string | null;
        error?: string | null;
        elapsed_seconds?: number | null;
        runtime_profile?: FrontierArenaReplayJob['runtime_profile'];
        result: FrontierArenaReplayJob['result'];
        frontier_snapshot_id: string;
        frontier_snapshot_sha256: string;
      }>('/frontier/arena-replay', {
        method: 'POST',
        body: JSON.stringify({
          scenarios: [
            { name: 'quoted baseline' },
            {
              name: 'current assumptions',
              slippage_bps: slippage,
              execution_delay_ms: Number(delay),
              fill_fraction: (Number(fillPercent) / 100).toFixed(4),
              quote_decay_bps_per_second: '15',
            },
          ],
        }),
      }),
    onSuccess: (job) => {
      const summary: FrontierArenaReplayJob = {
        job_id: job.job_id,
        state: job.state,
        created_at: job.created_at,
        updated_at: job.updated_at,
        elapsed_seconds: job.elapsed_seconds ?? null,
        progress: job.progress,
        phase: job.phase ?? null,
        error: job.error ?? null,
        snapshot_id: job.frontier_snapshot_id,
        snapshot_sha256: job.frontier_snapshot_sha256,
        runtime_profile: job.runtime_profile ?? null,
        result: job.result,
      };
      setSelectedArenaReplayId(job.job_id);
      queryClient.setQueryData<FrontierArenaReplayJobs>(
        ['frontier', 'arena-replay-jobs'],
        (current) => ({
          items: [
            summary,
            ...(current?.items ?? []).filter((item) => item.job_id !== job.job_id),
          ].slice(0, 20),
          limit: current?.limit ?? 20,
          scanned: current?.scanned ?? 0,
          scan_bound: current?.scan_bound ?? 500,
          scan_may_be_incomplete: current?.scan_may_be_incomplete ?? false,
          research_only: true,
        }),
      );
      void queryClient.invalidateQueries({ queryKey: ['frontier', 'arena-replay-jobs'] });
    },
  });
  const probe = useMutation({
    mutationFn: ({ venue, includeOneBook }: { venue: Venue; includeOneBook: boolean }) =>
      api('/frontier/probe/' + venue, {
        method: 'POST',
        body: JSON.stringify({
          limit: venue === 'kraken' ? 1 : 10,
          include_one_book: includeOneBook,
          include_recent_trades: true,
          trade_limit: 10,
        }),
      }),
    onSuccess: refresh,
  });
  const captureTradePage = useMutation({
    mutationFn: ({
      venue,
      marketId,
      cursor,
    }: {
      venue: Venue;
      marketId: string;
      cursor: string | null;
    }) =>
      api<TradePageCaptureResult>(`/frontier/probe/${venue}/trades`, {
        method: 'POST',
        body: JSON.stringify({
          ...(venue === 'polymarket' ? { condition_id: marketId } : { market_id: marketId }),
          limit: 50,
          ...(cursor ? { cursor } : {}),
        }),
      }),
    onSuccess: (result) => {
      const marketId = result.market_id ?? result.condition_id;
      if (marketId) {
        setTradePageCursor({
          marketKey: `${result.venue}:${marketId}`,
          cursor: result.next_cursor,
        });
      }
      refresh();
    },
  });
  const captureKalshiFeeMetadata = useMutation({
    mutationFn: ({ marketId }: { marketId: string }) =>
      api<KalshiFeeMetadataCaptureResult>('/frontier/probe/kalshi/fee-metadata', {
        method: 'POST',
        body: JSON.stringify({ market_id: marketId }),
      }),
    onSuccess: refresh,
  });
  const captureEventMarketGroup = useMutation({
    mutationFn: ({
      marketId,
      venue,
      nativeEventId,
    }: {
      marketId: string;
      venue: Venue;
      nativeEventId: string;
    }) =>
      api<EventMarketsCaptureResult>(`/frontier/probe/${venue}/event-markets`, {
        method: 'POST',
        body: JSON.stringify({ market_id: marketId, native_event_id: nativeEventId }),
      }),
    onSuccess: refresh,
  });
  const captureKalshiMultivariate = useMutation({
    mutationFn: (input: KalshiMultivariateFilter) =>
      api<KalshiMultivariateCaptureResult>('/frontier/probe/kalshi/multivariate-events', {
        method: 'POST',
        body: JSON.stringify(input),
      }),
    onSuccess: refresh,
  });
  const captureKalshiMveComponentMarket = useMutation({
    mutationFn: ({
      parentMarketId,
      componentMarketId,
    }: {
      parentMarketId: string;
      componentMarketId: string;
    }) =>
      api<KalshiMveComponentMarketCaptureResult>('/frontier/probe/kalshi/mve-component-market', {
        method: 'POST',
        body: JSON.stringify({
          parent_market_id: parentMarketId,
          component_market_id: componentMarketId,
        }),
      }),
    onSuccess: refresh,
  });
  const auditKalshiMveSettlement = useMutation({
    mutationFn: ({ marketId }: { marketId: string }) =>
      api<KalshiMveSettlementAuditResponse>('/frontier/economics/kalshi-mve-settlement-audit', {
        method: 'POST',
        body: JSON.stringify({ market_id: marketId }),
      }),
  });
  const estimateKalshiTakerFee = useMutation({
    mutationFn: (input: {
      marketId: string;
      eventObservationId: string;
      seriesObservationId: string;
      fills: {
        instrumentId: string;
        side: 'buy' | 'sell';
        priceUsd: string;
        quantityContracts: string;
      }[];
    }) =>
      api<KalshiFeeOrderSensitivityResponse>('/frontier/economics/kalshi-fee-order-sensitivity', {
        method: 'POST',
        body: JSON.stringify({
          market_id: input.marketId,
          event_observation_id: input.eventObservationId,
          series_observation_id: input.seriesObservationId,
          fills: input.fills.map((fill) => ({
            native_instrument_id: fill.instrumentId,
            side: fill.side,
            price_usd: fill.priceUsd,
            quantity_contracts: fill.quantityContracts,
          })),
        }),
      }),
  });

  const marketById = useMemo(
    () => new Map((markets.data?.items ?? []).map((market) => [market.canonical_id, market])),
    [markets.data],
  );
  const graphMarketById = useMemo(() => {
    const result = new Map(marketById);
    for (const node of graph.data?.nodes ?? []) {
      if (node.market) {
        result.set(node.market_id, {
          ...node.market,
          source_observation_record_id:
            node.source_observation_record_id ?? node.market.provenance.observation_id,
        });
      }
    }
    return result;
  }, [marketById, graph.data]);
  const selectedMarket = (markets.data?.items ?? []).find(
    (market) => market.canonical_id === selectedMarketId,
  );
  const selectedBooks = (books.data?.items ?? []).filter(
    (book) =>
      selectedMarket &&
      book.venue === selectedMarket.venue &&
      book.native_market_id === selectedMarket.native_market_id,
  );
  const filteredMarkets = (markets.data?.items ?? []).filter((market) => {
    const needle = search.trim().toLocaleLowerCase();
    return (
      !needle ||
      `${market.title} ${market.native_market_id} ${market.venue}`
        .toLocaleLowerCase()
        .includes(needle)
    );
  });
  const filteredRelationships = (graph.data?.edges ?? [])
    .filter((relationship) => {
      const left = graphMarketById.get(relationship.left_market_id);
      const right = graphMarketById.get(relationship.right_market_id);
      const needle = search.trim().toLocaleLowerCase();
      const matchesText =
        !needle ||
        `${left?.title ?? ''} ${right?.title ?? ''} ${relationship.relationship_type}`
          .toLocaleLowerCase()
          .includes(needle);
      return (
        matchesText && (relationshipState === 'all' || relationship.state === relationshipState)
      );
    })
    .slice(0, 30);
  const latestRun = runs.data?.items[0];
  const latestComparison = comparisons.data?.items[0]?.result;
  const overviewError = overview.error?.message ?? sources.error?.message;
  const summary = overview.data?.summary;
  const marketTotal = markets.data?.items.length ?? 0;
  const instrumentTotal = (markets.data?.items ?? []).reduce(
    (sum, item) => sum + item.instruments.length,
    0,
  );
  const verifiedRelationships = (graph.data?.edges ?? []).filter(
    (relationship) => relationship.state === 'verified',
  ).length;

  return (
    <div className="frontier">
      <header className="fr-header">
        <div>
          <div className="fr-eyebrow">
            <span className="fr-mark">F</span> FRONTIER / MULTI-MARKET RESEARCH
          </div>
          <h1>Market relationships, with evidence attached.</h1>
          <p>
            Compare heterogeneous public sources, test explicit payoff relationships, and replay
            only what was recorded.
          </p>
        </div>
        <div className="fr-header-side">
          <StateBadge state={overview.data?.state ?? (overview.isError ? 'offline' : 'loading')} />
          <span>
            <ShieldCheck size={14} /> Research only · no order execution
          </span>
          <small>Latest evidence · {time(overview.data?.latest_evidence_at_utc)}</small>
        </div>
      </header>

      {overviewError && (
        <div className="fr-alert">
          <AlertTriangle size={17} />
          <div>
            <strong>Frontier API unavailable</strong>
            <span>{overviewError}</span>
          </div>
          <button onClick={() => void overview.refetch()}>
            <RefreshCw size={14} /> Retry
          </button>
        </div>
      )}
      {overview.data?.live_execution && (
        <div className="fr-alert">
          <AlertTriangle size={17} />
          <div>
            <strong>Unexpected execution state</strong>
            <span>The Frontier research API should report live execution as disabled.</span>
          </div>
        </div>
      )}

      <nav className="fr-tabs" aria-label="Frontier workspace sections">
        {sections.map(({ id, label: tabLabel, icon: Icon }) => (
          <button
            key={id}
            className={section === id ? 'active' : ''}
            aria-current={section === id ? 'page' : undefined}
            onClick={() => setSection(id)}
          >
            <Icon size={15} />
            <span>{tabLabel}</span>
          </button>
        ))}
        <button className="fr-refresh" aria-label="Refresh Frontier evidence" onClick={refresh}>
          <RefreshCw size={14} />
        </button>
      </nav>

      {section === 'overview' && (
        <>
          <div className="fr-metrics">
            <Metric
              title="Markets in view"
              value={count(marketTotal)}
              note={`${count(instrumentTotal)} instruments in this loaded page`}
              icon={Layers3}
            />
            <Metric
              title="Research eligible observations"
              value={count(overview.data?.research_eligible_observations)}
              note={`Store ${summary ? `${money(summary.database_bytes)} / ${money(summary.max_bytes)} bytes` : 'size not measured'} · inventory includes held captures`}
              icon={Database}
            />
            <Metric
              title="Verified relationships in view"
              value={count(verifiedRelationships)}
              note={`${count(graph.data?.edges.length ?? 0)} eligible edges in this bounded graph page`}
              icon={GitBranch}
            />
            <Metric
              title="Replay runs"
              value={count(runs.data?.items.length ?? 0)}
              note="Visible runs are filtered by held-source provenance"
              icon={Play}
            />
            <Metric
              title="Paired comparisons"
              value={count(comparisons.data?.items.length ?? 0)}
              note="Visible comparisons use only eligible replay evidence"
              icon={GitBranch}
            />
          </div>
          <div className="fr-overview-grid">
            <section className="fr-card fr-source-overview">
              <div className="fr-card-head">
                <div>
                  <span className="fr-kicker">PUBLIC DATA SOURCES</span>
                  <h2>Source status</h2>
                </div>
                <button className="fr-link-button" onClick={() => setSection('sources')}>
                  Explore sources <ArrowRight size={14} />
                </button>
              </div>
              {overview.isLoading ? (
                <div className="fr-loading">Loading local source state…</div>
              ) : overview.data?.sources.length ? (
                overview.data.sources.map((source) => (
                  <SourceRow
                    key={source.venue}
                    source={source}
                    markets={
                      source.probe_policy_block_reason
                        ? null
                        : (summary?.markets_by_venue?.[source.venue] ?? 0)
                    }
                  />
                ))
              ) : (
                <EmptyState
                  title="Source inventory unavailable"
                  detail="The API did not return a capability manifest."
                />
              )}
              <p className="fr-footnote">
                Health reports local adapter state. It does not probe venues or indicate account
                eligibility.
              </p>
            </section>
            <section className="fr-card">
              <div className="fr-card-head">
                <div>
                  <span className="fr-kicker">EVIDENCE BOUNDARY</span>
                  <h2>What these numbers mean</h2>
                </div>
                <ShieldCheck size={17} />
              </div>
              <ul className="fr-limitations">
                {(
                  overview.data?.limitations ?? [
                    'No source data is recorded yet.',
                    'Cross-venue snapshots do not prove simultaneous execution.',
                  ]
                ).map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
              <div className="fr-readiness-mini">
                <strong>Frontier readiness</strong>
                {(readiness.data?.gates ?? []).slice(0, 4).map((gate) => (
                  <div key={gate.name}>
                    <span>{label(gate.name)}</span>
                    <StateBadge state={gate.state} />
                  </div>
                ))}
              </div>
            </section>
          </div>
          <section className="fr-card fr-recent-card">
            <div className="fr-card-head">
              <div>
                <span className="fr-kicker">RESEARCH ACTIVITY</span>
                <h2>Recent recorded runs</h2>
              </div>
              <button className="fr-link-button" onClick={() => setSection('replay')}>
                Open replay <ArrowRight size={14} />
              </button>
            </div>
            {latestRun ? (
              <RunSummary run={latestRun} />
            ) : (
              <EmptyState
                title="No replay runs yet"
                detail="Replay uses saved markets, books, verified relationships, and an explicit virtual execution scenario."
              />
            )}
          </section>
        </>
      )}

      {section === 'sources' && (
        <SourcesView
          sources={sources.data?.items ?? []}
          markets={summary?.markets_by_venue ?? {}}
          probe={probe}
          multivariateProbe={captureKalshiMultivariate}
          loading={sources.isLoading}
          error={sources.error?.message}
        />
      )}

      {section === 'markets' && (
        <section className="fr-card">
          <div className="fr-card-head">
            <div>
              <span className="fr-kicker">NORMALIZED SOURCE RECORDS</span>
              <h2>Exchange explorer</h2>
            </div>
            <span className="fr-count">{filteredMarkets.length} loaded</span>
          </div>
          <SearchBox
            value={search}
            onChange={setSearch}
            placeholder="Search title, venue, or native ID"
          />
          {markets.isLoading ? (
            <div className="fr-loading">Loading recorded market snapshots…</div>
          ) : markets.isError ? (
            <EmptyState title="Market query failed" detail={markets.error.message} />
          ) : filteredMarkets.length ? (
            <div className="fr-table-wrap">
              <table className="fr-table">
                <thead>
                  <tr>
                    <th>Market / native ID</th>
                    <th>Venue</th>
                    <th>Structure</th>
                    <th>Lifecycle</th>
                    <th>Instruments</th>
                    <th>Books</th>
                    <th>Source quality</th>
                    <th>Captured</th>
                    <th>Detail</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredMarkets.map((market) => (
                    <tr key={market.canonical_id}>
                      <td>
                        <strong>{market.title}</strong>
                        <code>{market.native_market_id}</code>
                      </td>
                      <td>
                        <VenuePill venue={market.venue} />
                      </td>
                      <td>{label(market.market_kind)}</td>
                      <td>{label(market.lifecycle)}</td>
                      <td>{market.instruments.length}</td>
                      <td>
                        {
                          (books.data?.items ?? []).filter(
                            (book) =>
                              book.venue === market.venue &&
                              book.native_market_id === market.native_market_id,
                          ).length
                        }
                      </td>
                      <td>
                        {market.quality_flags.length
                          ? market.quality_flags.map(label).join(', ')
                          : 'No flags recorded'}
                      </td>
                      <td>{time(market.provenance.response_received_at_utc)}</td>
                      <td>
                        <button
                          className="fr-inspect-button"
                          onClick={() => setSelectedMarketId(market.canonical_id)}
                        >
                          Inspect
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState
              title="No market observations recorded"
              detail="Frontier does not fetch on page load. A source must be explicitly enabled and probed in the Exchanges section."
            />
          )}
          {selectedMarket && (
            <MarketDetails
              key={selectedMarket.canonical_id}
              market={selectedMarket}
              books={selectedBooks}
              booksLoading={books.isLoading}
              eventMarketsProbe={captureEventMarketGroup}
              eventMarketsProbeEnabled={eventMarketGroupsProbeEnabledFor(selectedMarket.venue)}
              mveComponentProbe={captureKalshiMveComponentMarket}
              mveComponentProbeEnabled={kalshiMarketMetadataProbeEnabled}
              settlementAudit={auditKalshiMveSettlement}
              feeMetadataProbe={captureKalshiFeeMetadata}
              feeMetadataProbeEnabled={kalshiFeeMetadataProbeEnabled}
              feeSensitivity={estimateKalshiTakerFee}
            />
          )}
          <section className="fr-trades-panel">
            <div className="fr-panel-head">
              <div>
                <span className="fr-kicker">RECORDED PUBLIC OBSERVATIONS</span>
                <h3>Recent trades</h3>
              </div>
              <span className="fr-count">
                {count(trades.data?.trade_count ?? 0)} trades ·{' '}
                {count(trades.data?.observation_count ?? 0)} captures
              </span>
            </div>
            <div className="fr-trade-capture">
              <label>
                Research source
                <select
                  aria-label="Trade research source"
                  value={tradeVenue}
                  onChange={(event) => {
                    setTradeVenue(event.target.value as Venue);
                    setTradeMarketId('');
                    setTradePageCursor(null);
                    captureTradePage.reset();
                  }}
                >
                  <option value="polymarket">Polymarket</option>
                  <option value="kalshi">Kalshi</option>
                </select>
              </label>
              <label>
                Recorded {tradeVenue === 'polymarket' ? 'condition' : 'market ticker'}
                <select
                  aria-label="Recorded trade market"
                  value={tradeMarketId}
                  onChange={(event) => {
                    setTradeMarketId(event.target.value);
                    setTradePageCursor(null);
                    captureTradePage.reset();
                  }}
                >
                  <option value="">Choose a recorded market</option>
                  {tradeMarketOptions.map(({ market, marketId }) => (
                    <option key={marketId} value={marketId}>
                      {market.title} · {shortHash(marketId)}
                    </option>
                  ))}
                </select>
              </label>
              <button
                className="fr-action"
                onClick={() =>
                  captureTradePage.mutate({
                    venue: tradeVenue,
                    marketId: tradeMarketId,
                    cursor: activeTradeCursor,
                  })
                }
                disabled={!tradeMarketId || !tradePageProbeEnabled || captureTradePage.isPending}
              >
                {captureTradePage.isPending
                  ? 'Capturing one page…'
                  : activeTradeCursor
                    ? 'Capture next page'
                    : 'Capture first page'}
              </button>
              {captureTradePage.isError && <InlineError message={captureTradePage.error.message} />}
              {captureTradePage.data && (
                <div className="fr-trade-capture-status" role="status">
                  Saved {count(captureTradePage.data.trade_count)} trades ·{' '}
                  {captureTradePage.data.has_more
                    ? 'another source page is available'
                    : 'source reports no next page'}{' '}
                  · evidence {shortHash(captureTradePage.data.observation_id)} · raw{' '}
                  {shortHash(captureTradePage.data.raw_sha256)} ·{' '}
                  {captureTradePage.data.request_count_delta} network{' '}
                  {captureTradePage.data.request_count_delta === 1 ? 'request' : 'requests'}{' '}
                  (maximum {captureTradePage.data.network_calls_bounded_by})
                </div>
              )}
              <p>
                {tradePageProbeEnabled
                  ? tradeVenue === 'polymarket'
                    ? 'Each click records one public Data API v2 page for a condition in the saved listing. Pages use the source’s taker-only, 0.01-share minimum-size filter and its fixed three-year condition history window.'
                    : 'Each click records one public ticker-filtered Kalshi trade page for a market in the saved listing. Kalshi includes block trades by default; pages are capped at 100 rows.'
                  : `Public trade page capture is disabled by the ${tradeVenue} source configuration.`}{' '}
                Trade prints do not establish available depth or simultaneous executability. Nothing
                is fetched automatically.
              </p>
            </div>
            {trades.isLoading ? (
              <div className="fr-loading">Loading recorded public trades…</div>
            ) : trades.isError ? (
              <EmptyState title="Trade query failed" detail={trades.error.message} />
            ) : trades.data?.items.length ? (
              <div className="fr-table-wrap">
                <table className="fr-table">
                  <thead>
                    <tr>
                      <th>Venue / market</th>
                      <th>Outcome instrument</th>
                      <th>Price</th>
                      <th>Quantity</th>
                      <th>Side</th>
                      <th>Exchange time</th>
                      <th>Received</th>
                      <th>Evidence</th>
                    </tr>
                  </thead>
                  <tbody>
                    {trades.data.items.map((trade, index) => (
                      <tr
                        key={`${trade.source_observation_record_id}-${trade.native_trade_id ?? 'no-id'}-${trade.native_instrument_id ?? 'no-instrument'}-${index}`}
                      >
                        <td>
                          <VenuePill venue={trade.venue} />
                          <code>{trade.native_market_id}</code>
                        </td>
                        <td>
                          {trade.outcome_label ?? 'Outcome not supplied'}
                          <code>
                            {trade.native_instrument_id ?? 'Instrument ID not supplied'}
                            {trade.outcome_index !== null
                              ? ` · outcome ${trade.outcome_index}`
                              : ''}
                          </code>
                        </td>
                        <td>
                          {money(trade.price)} {trade.quote_currency ?? ''}
                          {trade.quote_currency_identity
                            ? ` · ${settlementIdentityLabel(trade.quote_currency_identity)}`
                            : ' · denomination identity unknown'}
                        </td>
                        <td>{money(trade.quantity)}</td>
                        <td>{label(trade.aggressor_side ?? 'unknown')}</td>
                        <td>
                          {trade.exchange_timestamp_utc
                            ? time(trade.exchange_timestamp_utc)
                            : 'Not supplied'}
                        </td>
                        <td>{time(trade.received_at_utc)}</td>
                        <td>
                          <code title={trade.source_raw_sha256}>
                            {shortHash(trade.source_observation_record_id)} ·{' '}
                            {shortHash(trade.source_raw_sha256)}
                          </code>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyState
                title="No public trades recorded"
                detail="A source may return a valid empty trade response. Frontier does not infer zero volume when no trade endpoint was captured."
              />
            )}
            <div className="fr-footnote">
              Trade prints are source observations, not evidence of available depth or executable
              prices.
            </div>
          </section>
          <div className="fr-footnote">
            Showing a bounded window of up to 100 markets. Native market IDs and source timestamps
            remain attached to every normalized record.
          </div>
        </section>
      )}

      {section === 'relationships' && (
        <section className="fr-card">
          <div className="fr-card-head">
            <div>
              <span className="fr-kicker">DETERMINISTIC CANDIDATE MATCHING</span>
              <h2>Relationship graph explorer</h2>
            </div>
            <button
              className="fr-action"
              onClick={() => propose.mutate()}
              disabled={propose.isPending || !marketTotal}
            >
              <GitBranch size={14} />
              {propose.isPending ? 'Proposing…' : 'Propose from recorded markets'}
            </button>
          </div>
          <div className="fr-filter-row">
            <SearchBox
              value={search}
              onChange={setSearch}
              placeholder="Find events, venues, or relationship types"
            />
            <select
              aria-label="Filter relationship state"
              value={relationshipState}
              onChange={(event) => setRelationshipState(event.target.value)}
            >
              <option value="all">All validation states</option>
              <option value="hypothesis">Hypotheses</option>
              <option value="verified">Verified</option>
              <option value="rejected">Rejected</option>
              <option value="ambiguous">Ambiguous</option>
            </select>
          </div>
          <div className="fr-filter-row fr-graph-controls">
            <label>
              <span>Explore from a recorded market</span>
              <select
                aria-label="Relationship graph center market"
                value={graphCenterMarketId}
                onChange={(event) => {
                  setGraphCenterMarketId(event.target.value);
                  resetGraphPagination();
                  setSelectedRelationshipId(null);
                }}
              >
                <option value="">Latest recorded relationship window</option>
                {(markets.data?.items ?? []).map((market) => (
                  <option key={market.canonical_id} value={market.canonical_id}>
                    {venueLabel(market.venue)} · {market.title}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>Neighborhood depth</span>
              <select
                aria-label="Relationship graph depth"
                value={graphDepth}
                onChange={(event) => {
                  setGraphDepth(Number(event.target.value));
                  resetGraphPagination();
                }}
              >
                <option value={1}>1 hop</option>
                <option value={2}>2 hops</option>
                <option value={3}>3 hops</option>
              </select>
            </label>
          </div>
          {propose.isError && <InlineError message={propose.error.message} />}
          {graph.isLoading ? (
            <div className="fr-loading">Loading stored relationship evidence…</div>
          ) : graph.isError ? (
            <>
              <EmptyState title="Relationship query failed" detail={graph.error.message} />
              {graphCursor && (
                <button className="fr-action" onClick={resetGraphPagination}>
                  Restart neighborhood query
                </button>
              )}
            </>
          ) : filteredRelationships.length ? (
            <>
              <RelationshipGraph
                relationships={filteredRelationships.slice(0, 18)}
                marketById={graphMarketById}
                selectedId={selectedRelationshipId}
                onSelect={setSelectedRelationshipId}
              />
              <div className="fr-graph-list">
                {filteredRelationships.map((relationship) => {
                  const left = graphMarketById.get(relationship.left_market_id);
                  const right = graphMarketById.get(relationship.right_market_id);
                  return (
                    <article className="fr-edge" key={relationship.relationship_id}>
                      <div className="fr-node">
                        <VenuePill venue={left?.venue ?? 'polymarket'} />
                        <strong>{left?.title ?? relationship.left_market_id}</strong>
                        <code>{left?.native_market_id ?? 'market not in loaded window'}</code>
                      </div>
                      <div
                        className="fr-edge-link"
                        aria-label={`${label(relationship.relationship_type)} relationship`}
                      >
                        <span>{label(relationship.relationship_type)}</span>
                        <i />
                      </div>
                      <div className="fr-node">
                        <VenuePill venue={right?.venue ?? 'kalshi'} />
                        <strong>{right?.title ?? relationship.right_market_id}</strong>
                        <code>{right?.native_market_id ?? 'market not in loaded window'}</code>
                      </div>
                      <div className="fr-edge-meta">
                        <StateBadge state={relationship.state} />
                        <span>score {Number(relationship.confidence).toFixed(2)}</span>
                        <details
                          open={relationship.relationship_id === selectedRelationshipId}
                          onToggle={(event) => {
                            if (event.currentTarget.open)
                              setSelectedRelationshipId(relationship.relationship_id);
                            else if (selectedRelationshipId === relationship.relationship_id)
                              setSelectedRelationshipId(null);
                          }}
                        >
                          <summary>Evidence</summary>
                          <p>{relationship.reason}</p>
                          {relationship.evidence.map((evidence, index) => (
                            <Fragment key={`${relationship.relationship_id}-${index}`}>
                              <small>
                                {evidence.method} ·{' '}
                                {evidence.verifier_version
                                  ? `verifier ${evidence.verifier_version}`
                                  : `matcher ${evidence.matcher_version ?? 'unknown'}`}{' '}
                                · fields: {evidence.source_fields.join(', ') || 'none'} ·
                                observations:{' '}
                                {evidence.observation_ids.map(shortHash).join(', ') || 'none'}
                              </small>
                              {evidence.details.map((detail) => (
                                <small key={`${relationship.relationship_id}-${index}-${detail}`}>
                                  {detail}
                                </small>
                              ))}
                            </Fragment>
                          ))}
                        </details>
                      </div>
                      {relationship.review_target_relationship_id &&
                        (relationship.state === 'hypothesis' || relationship.latest_review) && (
                          <RelationshipReviewForm
                            relationship={relationship}
                            reviewTargetId={relationship.review_target_relationship_id}
                            left={left}
                            right={right}
                          />
                        )}
                    </article>
                  );
                })}
              </div>
            </>
          ) : (
            <EmptyState
              title={
                graph.data?.next_cursor
                  ? 'No matching edges on this page'
                  : 'No relationship edges in this view'
              }
              detail={
                graph.data?.next_cursor
                  ? 'Continue to the next page or adjust the search and validation-state filters.'
                  : 'Text and native metadata matching create hypotheses only. A verified edge requires exhaustive payout and resolution evidence plus independent mapping.'
              }
            />
          )}
          {(graph.data?.next_cursor ||
            graph.data?.truncated_by_edge_limit ||
            graph.data?.relationship_scan_may_be_incomplete) && (
            <div className="fr-footnote">
              {graph.data.relationship_scan_may_be_incomplete
                ? graph.data.next_cursor && graphCenterMarketId && graphDepth === 1
                  ? `This page reached its ${graph.data.relationship_scan_limit}-row scan bound. Continue with the next page; graph changes invalidate the cursor.`
                  : graph.data.next_cursor && graphCenterMarketId && graphDepth > 1
                    ? `This breadth-first traversal reached its ${graph.data.relationship_scan_limit}-row scan bound. Continue through the captured result window; additional neighbors may still be omitted.`
                    : `This query considered ${graph.data.relationships_scanned} relationship rows, reaching its ${graph.data.relationship_scan_limit}-row scan bound; additional neighbors may be omitted.`
                : graph.data.next_cursor && graphCenterMarketId && graphDepth === 1
                  ? `This page returned ${graph.data.returned_edges} edges. More neighbors are available through keyset pages; graph changes make the cursor stale.`
                  : graph.data.next_cursor && graphCenterMarketId && graphDepth > 1
                    ? `This page returned ${graph.data.returned_edges} edges in breadth-first order. Continue through the bounded traversal; graph changes make the cursor stale.`
                    : `This view is capped at ${graph.data.edge_limit} edges after considering ${graph.data.relationships_scanned} relationship rows.`}{' '}
              {!graphCenterMarketId && 'Choose a center market to inspect a smaller neighborhood.'}
            </div>
          )}
          {graph.data && graphCenterMarketId && (
            <div className="fr-graph-pagination" role="group" aria-label="Relationship pages">
              <button
                className="fr-action"
                disabled={graphPageIndex === 0 || graph.isFetching}
                onClick={() => setGraphPageIndex((current) => Math.max(0, current - 1))}
              >
                Previous page
              </button>
              <span>Neighborhood page {graphPageIndex + 1}</span>
              <button
                className="fr-action"
                disabled={!graph.data.next_cursor || graph.isFetching}
                onClick={() => {
                  const nextCursor = graph.data?.next_cursor;
                  if (!nextCursor) return;
                  setGraphPageCursors((current) => [
                    ...current.slice(0, graphPageIndex + 1),
                    nextCursor,
                  ]);
                  setGraphPageIndex(graphPageIndex + 1);
                }}
              >
                {graph.isFetching ? 'Loading…' : 'Load more neighbors'}
              </button>
            </div>
          )}
          <div className="fr-footnote">
            The evidence list shows up to 30 edges per page; the network shows the first 18. Similar
            titles never certify payoff equivalence. Relationship identity is versioned and tied to
            pinned observation IDs.
          </div>
        </section>
      )}

      {section === 'opportunities' && (
        <section className="fr-card">
          <div className="fr-card-head">
            <div>
              <span className="fr-kicker">INDEPENDENT ECONOMIC CHECKS</span>
              <h2>Opportunity candidates</h2>
            </div>
            <StateBadge state="hypothetical only" />
          </div>
          {candidates.isLoading ? (
            <div className="fr-loading">Loading replay-derived candidate classifications…</div>
          ) : candidates.isError ? (
            <EmptyState title="Candidate query failed" detail={candidates.error.message} />
          ) : candidates.data?.items.length ? (
            <div className="fr-candidate-list">
              {candidates.data.items.map((candidate) => (
                <CandidateCard key={candidate.candidate_id} candidate={candidate} />
              ))}
            </div>
          ) : (
            <EmptyState
              title="No candidates have been evaluated"
              detail="A candidate requires compatible verified payoff semantics, eligible observed books, and a saved replay. Price resemblance alone is insufficient."
            />
          )}
          <div className="fr-footnote">
            Public order-book snapshots are observations, not proof of fills. Hypothetical modeled
            returns are not realized profit.
          </div>
        </section>
      )}

      {section === 'workbench' && (
        <div className="fr-workbench">
          <section className="fr-card fr-controls-card">
            <div className="fr-card-head">
              <div>
                <span className="fr-kicker">VIRTUAL ASSUMPTIONS</span>
                <h2>Execution sensitivity</h2>
              </div>
              <SlidersHorizontal size={17} />
            </div>
            <p className="fr-copy">
              Set bounded replay assumptions. Values affect deterministic evaluation of saved
              evidence only; no orders are sent.
            </p>
            <label className="fr-field">
              Modeled slippage <span>basis points</span>
              <input
                type="number"
                min="0"
                max="5000"
                value={slippage}
                onChange={(event) => setSlippage(event.target.value)}
              />
            </label>
            <label className="fr-field">
              Execution delay <span>milliseconds</span>
              <input
                type="number"
                min="0"
                max="3600000"
                step="100"
                value={delay}
                onChange={(event) => setDelay(event.target.value)}
              />
            </label>
            <label className="fr-field">
              Assumed fill fraction <span>percent of requested size</span>
              <input
                type="number"
                min="1"
                max="100"
                value={fillPercent}
                onChange={(event) => setFillPercent(event.target.value)}
              />
            </label>
            <div className="fr-scenario-strip">
              <span>Scenario</span>
              <strong>15 bps/s quote decay</strong>
              <span>Partial fills modeled</span>
            </div>
            <button
              className="fr-action fr-run-button"
              onClick={() => replay.mutate()}
              disabled={replay.isPending}
            >
              <Play size={15} />
              {replay.isPending ? 'Replaying pinned data…' : 'Run deterministic replay'}
            </button>
            {replay.isError && <InlineError message={replay.error.message} />}
            {replay.data && (
              <div className="fr-inline-success">
                <ShieldCheck size={15} /> Replay saved · {replay.data.candidates.length} candidate
                evaluations
              </div>
            )}
            <button
              className="fr-action fr-run-button"
              onClick={() => pairedReplay.mutate()}
              disabled={pairedReplay.isPending}
            >
              <GitBranch size={15} />
              {pairedReplay.isPending
                ? 'Comparing the same saved evidence…'
                : 'Compare quoted baseline with current assumptions'}
            </button>
            <p className="fr-footnote">
              The baseline uses displayed quotes with zero delay and full fills. Both arms are
              hypothetical replays over the same saved evidence; a comparison does not establish
              execution or profitability.
            </p>
            {pairedReplay.isError && <InlineError message={pairedReplay.error.message} />}
            {pairedReplay.data && (
              <div className="fr-inline-success">
                <ShieldCheck size={15} /> Paired comparison saved ·{' '}
                {shortHash(pairedReplay.data.comparison.comparison_id)}
              </div>
            )}
          </section>
          <section className="fr-card">
            <div className="fr-card-head">
              <div>
                <span className="fr-kicker">LAST EVALUATED RESULT</span>
                <h2>Replay output</h2>
              </div>
              <Beaker size={17} />
            </div>
            {latestRun ? (
              <RunSummary run={latestRun} expanded />
            ) : (
              <EmptyState
                title="No persisted run"
                detail="Replay saves its input digest, adapter and verifier versions, scenario assumptions, and output hash for later reproduction."
              />
            )}
            {(pairedReplay.data?.comparison ?? latestComparison) && (
              <ReplayComparisonSummary
                comparison={pairedReplay.data?.comparison ?? latestComparison!}
              />
            )}
            <div className="fr-callout">
              <AlertTriangle size={16} />
              <span>
                Venue capital is accounted for by source. Virtual capital assumptions do not imply
                that funds can be transferred, settled, or accessed across venues.
              </span>
            </div>
          </section>
        </div>
      )}

      {section === 'replay' && (
        <div className="fr-overview-grid">
          <section className="fr-card">
            <div className="fr-card-head">
              <div>
                <span className="fr-kicker">REPRODUCIBILITY</span>
                <h2>Experiment history</h2>
              </div>
              <button
                className="fr-action"
                onClick={() => replay.mutate()}
                disabled={replay.isPending}
              >
                <Play size={14} />
                {replay.isPending ? 'Running…' : 'Replay saved evidence'}
              </button>
            </div>
            {runs.isError ? (
              <EmptyState title="Run history unavailable" detail={runs.error.message} />
            ) : runs.data?.items.length ? (
              <div className="fr-run-list">
                {runs.data.items.map((run) => (
                  <RunSummary key={run.run_id} run={run} expanded />
                ))}
              </div>
            ) : (
              <EmptyState
                title="No experiment history"
                detail="Recorded inputs are required before replay. Experiments do not start a collector or long-running campaign."
              />
            )}
            {replay.isError && <InlineError message={replay.error.message} />}
            <div className="fr-research-links">
              <div>
                <strong>Connected research workflows</strong>
                <span>
                  Use the existing bounded experiment and model workspaces alongside Frontier's
                  source-pinned replays.
                </span>
              </div>
              <button className="fr-link-button" onClick={() => onNavigate?.('Laboratory')}>
                Open Laboratory <ArrowRight size={14} />
              </button>
              <button className="fr-link-button" onClick={() => onNavigate?.('Arena')}>
                Open Arena <ArrowRight size={14} />
              </button>
            </div>
          </section>
          <section className="fr-card fr-comparison-history">
            <div className="fr-card-head">
              <div>
                <span className="fr-kicker">PAIRED REPLAY EVIDENCE</span>
                <h2>Scenario comparisons</h2>
              </div>
              <GitBranch size={17} />
            </div>
            {comparisons.isError ? (
              <EmptyState
                title="Comparison history unavailable"
                detail={comparisons.error.message}
              />
            ) : comparisons.data?.items.length ? (
              <div className="fr-run-list">
                {comparisons.data.items.map((item) => (
                  <ReplayComparisonSummary key={item.comparison_id} comparison={item.result} />
                ))}
              </div>
            ) : (
              <EmptyState
                title="No paired comparisons yet"
                detail="Compare two assumptions over the same saved markets, books and verified relationships. Each arm is also stored as a reproducible replay."
              />
            )}
          </section>
          <section className="fr-card fr-arena-replay-card">
            <div className="fr-card-head">
              <div>
                <span className="fr-kicker">LABORATORY / ARENA INTEGRATION</span>
                <h2>Bounded paired replay</h2>
              </div>
              <button
                className="fr-action"
                onClick={() => arenaReplay.mutate()}
                disabled={arenaReplay.isPending}
              >
                <Play size={14} />
                {arenaReplay.isPending ? 'Submitting…' : 'Run paired replay in Arena'}
              </button>
            </div>
            <p className="fr-arena-replay-intro">
              Arena stages a content-hashed snapshot of saved Frontier markets, books, and verified
              relationships, then runs both assumptions against that same input set.
            </p>
            <div className="fr-callout">
              <ShieldCheck size={16} />
              <span>
                Each worker is limited to 5 minutes, 512 MiB, half a CPU, and idle I/O. External IP
                networking is blocked; submission still requires the host-wide Arena resource gate.
              </span>
            </div>
            {arenaReplay.isError && <InlineError message={arenaReplay.error.message} />}
            {arenaReplayJobs.isLoading ? (
              <div className="fr-loading">Loading Arena replay history…</div>
            ) : arenaReplayJobs.isError ? (
              <EmptyState
                title="Arena replay history unavailable"
                detail={arenaReplayJobs.error.message}
              />
            ) : listedArenaReplayJobs.length === 0 ? (
              <EmptyState
                title="No Arena replay jobs"
                detail="Submitting a replay is explicit. It snapshots only local recorded evidence and does not probe an exchange or start a collector."
              />
            ) : (
              <div className="fr-arena-job-list" aria-label="Frontier Arena replay jobs">
                {listedArenaReplayJobs.map((job) => (
                  <button
                    key={job.job_id}
                    className={`fr-arena-job-row${job.job_id === selectedArenaReplayJob?.job_id ? ' selected' : ''}`}
                    aria-pressed={job.job_id === selectedArenaReplayJob?.job_id}
                    onClick={() => setSelectedArenaReplayId(job.job_id)}
                  >
                    <span>
                      <code>{shortHash(job.job_id)}</code>
                      <small>
                        {job.created_at == null
                          ? 'Time not recorded'
                          : new Date(job.created_at * 1000).toLocaleString()}
                      </small>
                    </span>
                    <StateBadge state={job.state} />
                  </button>
                ))}
              </div>
            )}
            {arenaReplayJobs.data?.scan_may_be_incomplete && (
              <p className="fr-arena-replay-note">
                Job history is limited to a bounded scan of {arenaReplayJobs.data.scan_bound} Arena
                records; older entries may be omitted.
              </p>
            )}
            {selectedArenaReplayJob && (
              <article className="fr-arena-job-detail" aria-label="Selected Arena replay">
                <div className="fr-arena-job-detail-head">
                  <div>
                    <span className="fr-kicker">SELECTED ARENA JOB</span>
                    <code>{selectedArenaReplayJob.job_id}</code>
                  </div>
                  <StateBadge state={selectedArenaReplayJob.state} />
                </div>
                {['QUEUED', 'RUNNING'].includes(selectedArenaReplayJob.state) && (
                  <p>
                    {selectedArenaReplayJob.phase
                      ? label(selectedArenaReplayJob.phase)
                      : 'Waiting for the Arena worker lease'}
                    {selectedArenaReplayJob.progress &&
                      ` · ${selectedArenaReplayJob.progress.done ?? 0} / ${selectedArenaReplayJob.progress.total ?? 0} steps`}
                  </p>
                )}
                {selectedArenaReplayJob.error && (
                  <div className="fr-alert" role="status">
                    <AlertTriangle size={16} />
                    <div>
                      <strong>Arena replay did not complete</strong>
                      <span>{selectedArenaReplayJob.error}</span>
                    </div>
                  </div>
                )}
                <dl className="fr-arena-job-hashes">
                  {selectedArenaReplayJob.elapsed_seconds != null && (
                    <div>
                      <dt>Worker elapsed time</dt>
                      <dd>{selectedArenaReplayJob.elapsed_seconds.toFixed(3)} s</dd>
                    </div>
                  )}
                  {selectedArenaReplayJob.runtime_profile && (
                    <>
                      {(selectedArenaReplayJob.runtime_profile.worker_process_user_cpu_seconds !=
                        null ||
                        selectedArenaReplayJob.runtime_profile.worker_process_system_cpu_seconds !=
                          null) && (
                        <div>
                          <dt>Worker process CPU (user / system)</dt>
                          <dd>
                            {selectedArenaReplayJob.runtime_profile.worker_process_user_cpu_seconds?.toFixed(
                              3,
                            ) ?? '—'}
                            {' / '}
                            {selectedArenaReplayJob.runtime_profile.worker_process_system_cpu_seconds?.toFixed(
                              3,
                            ) ?? '—'}{' '}
                            s
                          </dd>
                        </div>
                      )}
                      {selectedArenaReplayJob.runtime_profile.worker_process_peak_rss_bytes !=
                        null && (
                        <div>
                          <dt>Worker process peak RSS</dt>
                          <dd>
                            {(
                              selectedArenaReplayJob.runtime_profile.worker_process_peak_rss_bytes /
                              1024 /
                              1024
                            ).toFixed(1)}{' '}
                            MiB
                          </dd>
                        </div>
                      )}
                    </>
                  )}
                  <div>
                    <dt>Input snapshot ID</dt>
                    <dd>{selectedArenaReplayJob.snapshot_id ?? 'Not recorded'}</dd>
                  </div>
                  <div>
                    <dt>Input snapshot SHA-256</dt>
                    <dd>{selectedArenaReplayJob.snapshot_sha256 ?? 'Not recorded'}</dd>
                  </div>
                  {selectedArenaReplayJob.result?.frontier_replay_sha256 && (
                    <div>
                      <dt>Result SHA-256</dt>
                      <dd>{selectedArenaReplayJob.result.frontier_replay_sha256}</dd>
                    </div>
                  )}
                </dl>
                {selectedArenaReplayJob.runtime_profile?.worker_process_peak_rss_bytes != null && (
                  <p className="fr-arena-replay-note">
                    These are measurements from one worker process. They do not establish sustained
                    Arena capacity or host headroom.
                  </p>
                )}
                {selectedArenaReplayJob.state === 'COMPLETED' && arenaReplayResult.isLoading && (
                  <div className="fr-loading">Reading and verifying the completed artifact…</div>
                )}
                {arenaReplayResult.isError && (
                  <InlineError message={arenaReplayResult.error.message} />
                )}
                {arenaReplayResult.data?.integrity_verified && (
                  <>
                    <p className="fr-arena-replay-note">
                      Hash checks passed. This result describes deterministic hypothetical replay;
                      it does not establish fills, venue access, or profitability.
                    </p>
                    <ReplayComparisonSummary
                      comparison={arenaReplayResult.data.artifact.comparison}
                    />
                  </>
                )}
              </article>
            )}
          </section>
          <section className="fr-card">
            <div className="fr-card-head">
              <div>
                <span className="fr-kicker">FRONTIER READINESS</span>
                <h2>Evidence gates</h2>
              </div>
              <Radio size={17} />
            </div>
            {readiness.isLoading ? (
              <div className="fr-loading">Loading readiness evidence…</div>
            ) : readiness.isError ? (
              <EmptyState title="Readiness query failed" detail={readiness.error.message} />
            ) : (
              <div className="fr-readiness-list">
                {readiness.data?.gates.map((gate) => (
                  <div key={gate.name}>
                    <div>
                      <strong>{label(gate.name)}</strong>
                      <span>{gate.detail}</span>
                    </div>
                    <StateBadge state={gate.state} />
                  </div>
                ))}
              </div>
            )}
            <div className="fr-callout">
              <ShieldCheck size={16} />
              <span>
                Development readiness is separate from production eligibility. This workspace is not
                deployed and has no execution path.
              </span>
            </div>
          </section>
        </div>
      )}
      <footer className="fr-footer">
        <span>FRONTIER / READ-ONLY RESEARCH</span>
        <span>Source evidence stays distinct from normalized records and modeled scenarios.</span>
      </footer>
    </div>
  );
}

function SourceRow({ source, markets }: { source: Source; markets: number | null }) {
  const supported = source.capabilities.filter((item) => item.supported).length;
  return (
    <div className="fr-source-row">
      <VenuePill venue={source.venue} />
      <div className="fr-source-name">
        <strong>{venueLabel(source.venue)}</strong>
        <small>
          {source.adapter_version} · {supported}/{source.capabilities.length} capabilities
        </small>
      </div>
      <span className="fr-market-count">
        {markets === null ? 'Held from research' : `${count(markets)} eligible markets`}
      </span>
      <StateBadge state={source.health.state} />
    </div>
  );
}

function MarketDetails({
  market,
  books,
  booksLoading,
  eventMarketsProbe,
  eventMarketsProbeEnabled,
  mveComponentProbe,
  mveComponentProbeEnabled,
  settlementAudit,
  feeMetadataProbe,
  feeMetadataProbeEnabled,
  feeSensitivity,
}: {
  market: Market;
  books: Book[];
  booksLoading: boolean;
  eventMarketsProbe: UseMutationResult<
    EventMarketsCaptureResult,
    Error,
    { marketId: string; venue: Venue; nativeEventId: string },
    unknown
  >;
  eventMarketsProbeEnabled: boolean;
  mveComponentProbe: UseMutationResult<
    KalshiMveComponentMarketCaptureResult,
    Error,
    { parentMarketId: string; componentMarketId: string },
    unknown
  >;
  mveComponentProbeEnabled: boolean;
  settlementAudit: UseMutationResult<
    KalshiMveSettlementAuditResponse,
    Error,
    { marketId: string },
    unknown
  >;
  feeMetadataProbe: UseMutationResult<
    KalshiFeeMetadataCaptureResult,
    Error,
    { marketId: string },
    unknown
  >;
  feeMetadataProbeEnabled: boolean;
  feeSensitivity: UseMutationResult<
    KalshiFeeOrderSensitivityResponse,
    Error,
    {
      marketId: string;
      eventObservationId: string;
      seriesObservationId: string;
      fills: {
        instrumentId: string;
        side: 'buy' | 'sell';
        priceUsd: string;
        quantityContracts: string;
      }[];
    },
    unknown
  >;
}) {
  const [nativeEventId, setNativeEventId] = useState(
    market.native_event_id?.startsWith('market:') ? '' : (market.native_event_id ?? ''),
  );
  const [feeFills, setFeeFills] = useState<KalshiFeeScenarioFill[]>([
    {
      instrumentId: market.instruments[0]?.native_instrument_id ?? '',
      side: 'buy',
      price: '0.50',
      quantity: '1',
    },
  ]);
  const capturedFeeMetadata =
    feeMetadataProbe.isSuccess && feeMetadataProbe.variables?.marketId === market.canonical_id
      ? feeMetadataProbe.data
      : null;
  const feeMetadataResolved =
    capturedFeeMetadata?.metadata.fee_resolution_state === 'event_override' ||
    capturedFeeMetadata?.metadata.fee_resolution_state === 'series_inherited';
  const capturedEventMarkets =
    eventMarketsProbe.isSuccess && eventMarketsProbe.variables?.marketId === market.canonical_id
      ? eventMarketsProbe.data
      : null;
  const capturedMveComponent =
    mveComponentProbe.isSuccess &&
    mveComponentProbe.variables?.parentMarketId === market.canonical_id
      ? mveComponentProbe.data
      : null;
  return (
    <section className="fr-market-detail" aria-label="Market and book details">
      <div className="fr-market-detail-head">
        <div>
          <span className="fr-kicker">NATIVE SPECIFICATION / {market.native_market_id}</span>
          <h3>{market.title}</h3>
          <p>{market.description || 'No source description recorded.'}</p>
        </div>
        <VenuePill venue={market.venue} />
      </div>
      <div className="fr-market-facts">
        <div>
          <span>Parent event</span>
          <strong>{market.native_event_title ?? 'Not recorded'}</strong>
          <small>
            {market.native_event_id ?? 'No native event ID'}
            {market.outcome_label ? ` · outcome ${market.outcome_label}` : ''}
          </small>
        </div>
        <div>
          <span>Instrument type</span>
          <strong>{label(market.market_kind)}</strong>
        </div>
        <div>
          <span>Payoff states</span>
          <strong>
            {market.payoff.state_ids.length
              ? market.payoff.state_ids.join(', ')
              : 'No event payoff'}
          </strong>
        </div>
        <div>
          <span>Payoff evidence</span>
          <strong>
            {market.payoff.verified && market.payoff.exhaustive
              ? 'Verified and exhaustive'
              : 'Not verified'}
          </strong>
          <small>{market.payoff.verification_basis}</small>
        </div>
        <div>
          <span>Fees</span>
          <strong>
            {label(market.fees.status)}
            {market.fees.rate ? ` · rate ${market.fees.rate}` : ''}
          </strong>
          <small>
            Fee unit: {market.fees.fee_currency ?? 'Unknown'} ·{' '}
            {settlementIdentityLabel(market.fees.fee_currency_identity)}
          </small>
          <small>{market.fees.note}</small>
        </div>
        <div>
          <span>Settlement asset</span>
          <strong>{market.settlement_asset ?? market.quote_asset ?? 'Not established'}</strong>
          <small>
            Market identity: {settlementIdentityLabel(market.settlement_asset_identity)}
          </small>
          <small>
            Payoff identity: {settlementIdentityLabel(market.payoff.settlement_asset_identity)}
          </small>
        </div>
        <div>
          <span>Resolution authority</span>
          <strong>{market.resolution.authority ?? 'Not recorded'}</strong>
        </div>
        <div>
          <span>Closes / settles</span>
          <strong>
            {time(market.resolution.closes_at_utc)} / {time(market.resolution.settles_at_utc)}
          </strong>
        </div>
      </div>
      {market.selected_components?.length ? (
        <div className="fr-market-components" aria-label="Selected source components">
          <div>
            <strong>Selected components from public MVE metadata</strong>
            <small>
              These native market and side identifiers describe the selected combo inputs. They do
              not verify component rules, combo payout, or resolution equivalence.
            </small>
          </div>
          <ul>
            {market.selected_components.map((component) => (
              <li key={`${component.venue}:${component.native_market_id}`}>
                <span>
                  <VenuePill venue={component.venue} />
                  <strong>Selected {component.selected_side.toUpperCase()} side</strong>
                  <small>Event {component.native_event_id ?? 'not provided'}</small>
                  {component.yes_settlement_value_dollars != null && (
                    <small>
                      Kalshi reported YES settlement value: $
                      {component.yes_settlement_value_dollars}
                    </small>
                  )}
                </span>
                <code>{component.native_market_id}</code>
                {component.venue === 'kalshi' && (
                  <button
                    className="fr-inspect-button"
                    disabled={!mveComponentProbeEnabled || mveComponentProbe.isPending}
                    onClick={() =>
                      mveComponentProbe.mutate({
                        parentMarketId: market.canonical_id,
                        componentMarketId: component.native_market_id,
                      })
                    }
                  >
                    {mveComponentProbe.isPending &&
                    mveComponentProbe.variables?.componentMarketId === component.native_market_id
                      ? 'Capturing…'
                      : mveComponentProbeEnabled
                        ? 'Capture component rules'
                        : 'Public probe disabled'}
                  </button>
                )}
                {capturedMveComponent?.component_market_id === component.native_market_id && (
                  <div className="fr-component-capture" role="status">
                    <strong>{capturedMveComponent.market.title}</strong>
                    <span>
                      Primary rule:{' '}
                      {capturedMveComponent.market.resolution.primary_rule ?? 'Not provided'}
                    </span>
                    <span>
                      Secondary rule:{' '}
                      {capturedMveComponent.market.resolution.secondary_rule ?? 'Not provided'}
                    </span>
                    <small>
                      Saved {shortHash(capturedMveComponent.observation_id)} · raw{' '}
                      {shortHash(capturedMveComponent.raw_sha256)} · payoff remains unverified
                    </small>
                  </div>
                )}
              </li>
            ))}
          </ul>
          <button
            className="fr-inspect-button"
            disabled={settlementAudit.isPending}
            onClick={() => settlementAudit.mutate({ marketId: market.canonical_id })}
          >
            {settlementAudit.isPending
              ? 'Auditing recorded values…'
              : 'Audit recorded settlement arithmetic'}
          </button>
          {settlementAudit.isError && <InlineError message={settlementAudit.error.message} />}
          {settlementAudit.isSuccess &&
            settlementAudit.variables?.marketId === market.canonical_id && (
              <div className="fr-fee-sensitivity-result" role="status">
                <strong>
                  Source-reported settlement arithmetic · {settlementAudit.data.audit.state}
                </strong>
                <small>
                  Audit {settlementAudit.data.audit.audit_algorithm_version} · parent lifecycle{' '}
                  {settlementAudit.data.audit.lifecycle} · provisional flag{' '}
                  {settlementAudit.data.audit.settlement_is_provisional === null
                    ? 'unknown'
                    : String(settlementAudit.data.audit.settlement_is_provisional)}
                </small>
                <small>
                  Recomputed component product: $
                  {settlementAudit.data.audit.component_product_dollars ?? 'incomplete'} · parent{' '}
                  reported: $
                  {settlementAudit.data.audit.reported_settlement_value_dollars ?? 'not recorded'}
                </small>
                {settlementAudit.data.audit.component_values.map((component) => (
                  <small key={component.native_market_id}>
                    {component.native_market_id} · selected {component.selected_side.toUpperCase()}{' '}
                    · YES value ${component.reported_yes_value_dollars ?? 'missing'} · selected{' '}
                    value ${component.selected_position_value_dollars ?? 'missing'}
                  </small>
                ))}
                {settlementAudit.data.audit.missing_component_market_ids.length > 0 && (
                  <small>
                    Missing: {settlementAudit.data.audit.missing_component_market_ids.join(', ')}
                  </small>
                )}
                {settlementAudit.data.audit.assumptions.map((assumption) => (
                  <small key={assumption}>{assumption}</small>
                ))}
                <small>
                  Method sources:{' '}
                  {settlementAudit.data.audit.rule_source_urls.map((source, index) => (
                    <span key={source}>
                      {index > 0 ? ' · ' : ''}
                      <a href={source} target="_blank" rel="noreferrer">
                        {index === 0
                          ? 'combo settlement rule'
                          : index === 1
                            ? 'NO value rule'
                            : 'API field schema'}
                      </a>
                    </span>
                  ))}
                </small>
                <small>{settlementAudit.data.note}</small>
                <small>
                  Input record {shortHash(settlementAudit.data.audit.source_observation_id)} · raw{' '}
                  {shortHash(settlementAudit.data.audit.source_raw_sha256)}
                </small>
              </div>
            )}
          {mveComponentProbe.isError &&
            mveComponentProbe.variables?.parentMarketId === market.canonical_id && (
              <InlineError message={mveComponentProbe.error.message} />
            )}
        </div>
      ) : null}
      {market.venue !== 'kraken' && (
        <div className="fr-fee-metadata-panel">
          <div>
            <strong>Public event context</strong>
            <small>
              Captures one event and its bounded market group, linked to this recorded market. It
              can propose text relationships but cannot verify equivalent outcomes or settlement.
            </small>
          </div>
          <div className="fr-event-group-controls">
            <label htmlFor={`event-id-${market.canonical_id}`}>Native event ID</label>
            <input
              id={`event-id-${market.canonical_id}`}
              value={nativeEventId}
              maxLength={256}
              onChange={(event) => setNativeEventId(event.target.value)}
              placeholder={
                market.venue === 'polymarket' ? 'Gamma numeric event ID' : 'Kalshi event ticker'
              }
            />
            <button
              className="fr-inspect-button"
              disabled={
                !eventMarketsProbeEnabled || eventMarketsProbe.isPending || !nativeEventId.trim()
              }
              onClick={() =>
                eventMarketsProbe.mutate({
                  marketId: market.canonical_id,
                  venue: market.venue,
                  nativeEventId: nativeEventId.trim(),
                })
              }
            >
              {eventMarketsProbe.isPending &&
              eventMarketsProbe.variables?.marketId === market.canonical_id
                ? 'Capturing…'
                : eventMarketsProbeEnabled
                  ? 'Capture event context'
                  : 'Public probe disabled'}
            </button>
          </div>
          {eventMarketsProbe.isError && <InlineError message={eventMarketsProbe.error.message} />}
          {capturedEventMarkets && (
            <div className="fr-fee-metadata-result" role="status">
              <strong>{capturedEventMarkets.event_title}</strong>
              <small>
                {capturedEventMarkets.market_count} markets · saved observation{' '}
                {capturedEventMarkets.observation_id}
              </small>
              <small>{capturedEventMarkets.note}</small>
              <small>Raw SHA-256 {capturedEventMarkets.raw_sha256}</small>
            </div>
          )}
        </div>
      )}
      {market.venue === 'kalshi' && (
        <div className="fr-fee-metadata-panel">
          <div>
            <strong>Public fee parameters</strong>
            <small>
              Fetches the recorded event’s overrides and series parameters. This evidence does not
              produce an account fee estimate.
            </small>
          </div>
          <button
            className="fr-inspect-button"
            disabled={!feeMetadataProbeEnabled || feeMetadataProbe.isPending}
            onClick={() => feeMetadataProbe.mutate({ marketId: market.canonical_id })}
          >
            {feeMetadataProbe.isPending &&
            feeMetadataProbe.variables?.marketId === market.canonical_id
              ? 'Capturing…'
              : feeMetadataProbeEnabled
                ? 'Capture fee metadata'
                : 'Public probe disabled'}
          </button>
          {feeMetadataProbe.isError && <InlineError message={feeMetadataProbe.error.message} />}
          {feeMetadataProbe.isSuccess &&
            feeMetadataProbe.variables?.marketId === market.canonical_id && (
              <div className="fr-fee-metadata-result" role="status">
                <strong>
                  {feeMetadataProbe.data.metadata.effective_fee_type} · multiplier{' '}
                  {feeMetadataProbe.data.metadata.effective_fee_multiplier}
                </strong>
                <small>
                  Override status:{' '}
                  {feeMetadataProbe.data.metadata.fee_resolution_state.replaceAll('_', ' ')}
                </small>
                <small>
                  Series {feeMetadataProbe.data.metadata.series_ticker} · not added to candidate
                  economics · {feeMetadataProbe.data.observation_ids.length} immutable evidence
                  records
                </small>
                <small>{feeMetadataProbe.data.note}</small>
                <small>
                  Event {feeMetadataProbe.data.raw_sha256.event} · series{' '}
                  {feeMetadataProbe.data.raw_sha256.series}
                </small>
                {feeMetadataProbe.data.metadata.limitations.map((limitation) => (
                  <small key={limitation}>{limitation}</small>
                ))}
                {feeMetadataProbe.data.observation_ids.map((observationId, index) => (
                  <div key={observationId}>
                    <small>
                      {index === 0 ? 'Event' : 'Series'} fee evidence {shortHash(observationId)}
                    </small>
                    <EvidenceDisclosure observationId={observationId} />
                  </div>
                ))}
                <div className="fr-fee-sensitivity-form">
                  <small className="fr-fee-sensitivity-guidance">
                    One-order taker scenario. Fill inputs are manual, share one buy or sell side,
                    and are not read from the stored order book.
                  </small>
                  {!feeMetadataResolved && (
                    <small className="fr-fee-sensitivity-guidance">
                      Fee sensitivity is unavailable until both event override fields are complete
                      or explicitly cleared.
                    </small>
                  )}
                  {feeFills.map((fill, index) => (
                    <div className="fr-fee-order-fill" key={index}>
                      <strong>Fill {index + 1}</strong>
                      <label>
                        Contract outcome
                        <select
                          aria-label={`Fill ${index + 1} contract outcome`}
                          value={fill.instrumentId}
                          onChange={(event) =>
                            setFeeFills((current) =>
                              current.map((item, itemIndex) =>
                                itemIndex === index
                                  ? { ...item, instrumentId: event.target.value }
                                  : item,
                              ),
                            )
                          }
                        >
                          {market.instruments.map((instrument) => (
                            <option
                              key={instrument.native_instrument_id}
                              value={instrument.native_instrument_id}
                            >
                              {instrument.label} · {instrument.native_instrument_id}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label>
                        Side
                        <select
                          aria-label={`Fill ${index + 1} side`}
                          value={fill.side}
                          onChange={(event) =>
                            setFeeFills((current) =>
                              current.map((item, itemIndex) =>
                                itemIndex === index
                                  ? { ...item, side: event.target.value as 'buy' | 'sell' }
                                  : item,
                              ),
                            )
                          }
                        >
                          <option value="buy">Buy</option>
                          <option value="sell">Sell</option>
                        </select>
                      </label>
                      <label>
                        Price per contract (USD)
                        <input
                          aria-label={`Fill ${index + 1} price per contract (USD)`}
                          type="number"
                          min="0.000001"
                          max="0.999999"
                          step="any"
                          value={fill.price}
                          onChange={(event) =>
                            setFeeFills((current) =>
                              current.map((item, itemIndex) =>
                                itemIndex === index ? { ...item, price: event.target.value } : item,
                              ),
                            )
                          }
                        />
                      </label>
                      <label>
                        Quantity (contracts)
                        <input
                          aria-label={`Fill ${index + 1} quantity (contracts)`}
                          type="number"
                          min="0.000001"
                          max="1000000"
                          step="any"
                          value={fill.quantity}
                          onChange={(event) =>
                            setFeeFills((current) =>
                              current.map((item, itemIndex) =>
                                itemIndex === index
                                  ? { ...item, quantity: event.target.value }
                                  : item,
                              ),
                            )
                          }
                        />
                      </label>
                      {feeFills.length > 1 && (
                        <button
                          className="fr-inspect-button"
                          aria-label={`Remove fill ${index + 1}`}
                          onClick={() =>
                            setFeeFills((current) =>
                              current.filter((_, itemIndex) => itemIndex !== index),
                            )
                          }
                        >
                          Remove
                        </button>
                      )}
                    </div>
                  ))}
                  <div className="fr-fee-order-actions">
                    <button
                      className="fr-inspect-button"
                      disabled={feeFills.length >= 32}
                      onClick={() =>
                        setFeeFills((current) => [
                          ...current,
                          {
                            instrumentId: feeFills[0].instrumentId,
                            side: feeFills[0].side,
                            price: '0.50',
                            quantity: '1',
                          },
                        ])
                      }
                    >
                      Add fill
                    </button>
                    <button
                      className="fr-inspect-button"
                      disabled={
                        !capturedFeeMetadata ||
                        !feeMetadataResolved ||
                        feeSensitivity.isPending ||
                        !market.instruments.some(
                          (instrument) =>
                            instrument.native_instrument_id === feeFills[0].instrumentId,
                        ) ||
                        feeFills.some((item) => item.instrumentId !== feeFills[0].instrumentId) ||
                        feeFills.some((item) => !item.price || !item.quantity) ||
                        feeFills.some((item) => item.side !== feeFills[0].side)
                      }
                      onClick={() => {
                        if (!capturedFeeMetadata) return;
                        feeSensitivity.mutate({
                          marketId: market.canonical_id,
                          eventObservationId: capturedFeeMetadata.observation_ids[0],
                          seriesObservationId: capturedFeeMetadata.observation_ids[1],
                          fills: feeFills.map((item) => ({
                            instrumentId: item.instrumentId,
                            side: item.side,
                            priceUsd: item.price,
                            quantityContracts: item.quantity,
                          })),
                        });
                      }}
                    >
                      {feeSensitivity.isPending
                        ? 'Calculating…'
                        : feeMetadataResolved
                          ? 'Calculate order fee'
                          : 'Fee override unresolved'}
                    </button>
                  </div>
                </div>
                {feeSensitivity.isError && <InlineError message={feeSensitivity.error.message} />}
                {feeSensitivity.isSuccess &&
                  feeSensitivity.variables?.marketId === market.canonical_id && (
                    <div className="fr-fee-sensitivity-result" role="status">
                      <strong>
                        One-order taker sensitivity ·{' '}
                        {feeSensitivity.data.estimate.order_fills.length} manual fill
                        {feeSensitivity.data.estimate.order_fills.length === 1 ? '' : 's'} ·{' '}
                        {feeSensitivity.data.estimate.effective_fee_type} ×{' '}
                        {feeSensitivity.data.estimate.effective_fee_multiplier}
                      </strong>
                      <small>
                        Fee metadata received: event{' '}
                        {time(feeSensitivity.data.estimate.input_received_at_utc[0])} · series{' '}
                        {time(feeSensitivity.data.estimate.input_received_at_utc[1])}
                      </small>
                      <small>
                        Override status:{' '}
                        {feeSensitivity.data.estimate.fee_resolution_state.replaceAll('_', ' ')}
                      </small>
                      {feeSensitivity.data.estimate.scenarios.map((scenario) => (
                        <div
                          className="fr-fee-order-scenario"
                          key={scenario.account_precision_class}
                        >
                          <small>
                            {scenario.account_precision_class.replace('_', ' ')} · balance quantum $
                            {scenario.balance_quantum} · total fee ${scenario.total_net_fee_usd}{' '}
                            (trade ${scenario.total_trade_fee_usd} + rounding $
                            {scenario.total_rounding_fee_usd} − rebates ${scenario.total_rebate_usd}
                            ) · balance change ${scenario.total_balance_change_usd}
                          </small>
                          {scenario.fills.map((item) => (
                            <small key={item.fill_index}>
                              Fill {item.fill_index + 1}{' '}
                              {market.instruments.find(
                                (instrument) =>
                                  instrument.native_instrument_id === item.native_instrument_id,
                              )?.label ?? item.native_instrument_id}{' '}
                              {item.side} · trade ${item.trade_fee_rounded_to_microdollar} ·
                              rounding ${item.rounding_fee_usd} · rebate ${item.rebate_usd} · carry
                              ${item.accumulated_rounding_after_rebate_usd}
                            </small>
                          ))}
                        </div>
                      ))}
                      <small>{feeSensitivity.data.note}</small>
                      <small>
                        Calculation {shortHash(feeSensitivity.data.estimate.calculation_sha256)}
                      </small>
                    </div>
                  )}
              </div>
            )}
        </div>
      )}
      {market.resolution.primary_rule && (
        <div className="fr-resolution-text">
          <strong>Primary resolution text</strong>
          <p>{market.resolution.primary_rule}</p>
          {market.resolution.secondary_rule && <p>{market.resolution.secondary_rule}</p>}
        </div>
      )}
      <div className="fr-instrument-list">
        <strong>Native instruments</strong>
        {market.instruments.map((instrument) => {
          const book = books.find(
            (item) => item.native_instrument_id === instrument.native_instrument_id,
          );
          return (
            <article key={instrument.native_instrument_id}>
              <div className="fr-instrument-head">
                <span>
                  {instrument.label}
                  {instrument.outcome_id ? ` · ${instrument.outcome_id}` : ''}
                </span>
                <code>{instrument.native_instrument_id}</code>
              </div>
              <small>
                Quote unit: {instrument.price_currency ?? 'Unknown'} ·{' '}
                {settlementIdentityLabel(instrument.price_currency_identity)}
              </small>
              {booksLoading ? (
                <small>Loading stored public book snapshots…</small>
              ) : book ? (
                <>
                  <div className="fr-book-meta">
                    <span>{book.price_unit}</span>
                    <span>
                      Quote identity: {settlementIdentityLabel(book.price_currency_identity)}
                    </span>
                    <span>{book.quantity_unit}</span>
                    <span>received {time(book.received_at_utc)}</span>
                    <StateBadge state={book.quality_flags.length ? 'degraded' : 'recorded'} />
                  </div>
                  <div className="fr-book-sides">
                    <BookSide title="ASKS" levels={book.asks} />
                    <BookSide title="BIDS" levels={book.bids} />
                  </div>
                  <div className="fr-book-provenance">
                    Exchange timestamp: {time(book.exchange_timestamp_utc)} ·{' '}
                    {book.exchange_timestamp_semantics} · raw {book.provenance.raw_sha256}
                  </div>
                  <EvidenceDisclosure observationId={book.source_observation_record_id} />
                </>
              ) : (
                <small className="fr-no-book">
                  No public book snapshot stored for this instrument.
                </small>
              )}
            </article>
          );
        })}
      </div>
      <div className="fr-market-provenance">
        Market observation {market.provenance.observation_id} · raw SHA-256{' '}
        {market.provenance.raw_sha256}
      </div>
      <EvidenceDisclosure observationId={market.source_observation_record_id} />
    </section>
  );
}

function EvidenceDisclosure({ observationId }: { observationId: string }) {
  const [expanded, setExpanded] = useState(false);
  const evidence = useQuery({
    queryKey: ['frontier', 'observation', observationId],
    queryFn: () => api<ObservationEvidence>(`/frontier/observations/${observationId}`),
    enabled: expanded,
    retry: false,
  });
  return (
    <details
      className="fr-evidence-disclosure"
      onToggle={(event) => setExpanded(event.currentTarget.open)}
    >
      <summary>Inspect immutable source response</summary>
      {expanded &&
        (evidence.isLoading ? (
          <div className="fr-loading">Loading stored raw response…</div>
        ) : evidence.isError ? (
          <InlineError message={evidence.error.message} />
        ) : evidence.data ? (
          <div className="fr-evidence-body">
            <span>
              {evidence.data.raw.http_status} · {evidence.data.raw.request_url}
            </span>
            <span>Capture row SHA-256 · {evidence.data.row_sha256}</span>
            <pre>{evidence.data.raw.raw_body}</pre>
          </div>
        ) : null)}
    </details>
  );
}

function BookSide({ title, levels }: { title: string; levels: Book['asks'] }) {
  return (
    <div className="fr-book-side">
      <strong>{title}</strong>
      {levels.length ? (
        levels.slice(0, 5).map((level, index) => (
          <span key={`${title}-${level.price}-${index}`}>
            <b>{money(level.price)}</b>
            <i>{money(level.quantity)}</i>
          </span>
        ))
      ) : (
        <small>Empty side in captured response</small>
      )}
    </div>
  );
}

type ProbeVariables = { venue: Venue; includeOneBook: boolean };
type ProbeMutation = UseMutationResult<unknown, Error, ProbeVariables, unknown>;
type KalshiMultivariateFilter =
  { series_ticker: string } | { collection_ticker: string } | { event_ticker: string };
type KalshiMultivariateProbe = UseMutationResult<
  KalshiMultivariateCaptureResult,
  Error,
  KalshiMultivariateFilter,
  unknown
>;

function SourcesView({
  sources,
  markets,
  probe,
  multivariateProbe,
  loading,
  error,
}: {
  sources: Source[];
  markets: Record<string, number>;
  probe: ProbeMutation;
  multivariateProbe: KalshiMultivariateProbe;
  loading: boolean;
  error?: string;
}) {
  const [multivariateFilterType, setMultivariateFilterType] = useState<
    'series_ticker' | 'collection_ticker' | 'event_ticker'
  >('series_ticker');
  const [multivariateFilterValue, setMultivariateFilterValue] = useState('');
  return (
    <section className="fr-source-cards">
      {loading ? (
        <div className="fr-card fr-loading">Loading source capability declarations…</div>
      ) : error ? (
        <div className="fr-card">
          <EmptyState title="Source inventory unavailable" detail={error} />
        </div>
      ) : (
        sources.map((source) => {
          const supported = source.capabilities.filter((item) => item.supported);
          const unsupported = source.capabilities.filter((item) => !item.supported);
          return (
            <article className="fr-card fr-venue-card" key={source.venue}>
              <div className="fr-venue-top">
                <VenuePill venue={source.venue} />
                <StateBadge state={source.health.state} />
              </div>
              <h2>{venueLabel(source.venue)}</h2>
              <code>{source.adapter_version}</code>
              <p className="fr-copy">
                {source.venue === 'kraken'
                  ? 'Spot instruments provide context for event research. A spot price is not a prediction-contract payoff.'
                  : source.venue === 'kalshi'
                    ? 'Public event metadata and order books are retained with native rules and multivariate-event markers.'
                    : 'The existing Polymarket schema is adapted while preserving its legacy source identifiers and fee validation.'}
              </p>
              {source.probe_policy_block_reason && (
                <div className="fr-source-policy-warning" role="note">
                  <AlertTriangle size={14} />
                  <span>{source.probe_policy_block_reason}</span>
                </div>
              )}
              <div className="fr-venue-stats">
                <span>
                  <strong>
                    {source.probe_policy_block_reason ? 'Held' : count(markets[source.venue] ?? 0)}
                  </strong>{' '}
                  {source.probe_policy_block_reason ? 'from research use' : 'eligible markets'}
                </span>
                <span>
                  <strong>{supported.length}</strong> supported capabilities
                </span>
              </div>
              <details className="fr-capabilities">
                <summary>
                  Inspect {supported.length} supported and {unsupported.length} unsupported
                  capabilities
                </summary>
                <div className="fr-capability-list">
                  {source.capabilities.map((capability) => (
                    <div key={capability.capability}>
                      <span>{label(capability.capability)}</span>
                      <StateBadge state={capability.supported ? 'implemented' : 'unsupported'} />
                      <small>{capability.reason}</small>
                    </div>
                  ))}
                </div>
              </details>
              {source.health.last_error && (
                <div className="fr-source-error">
                  <AlertTriangle size={14} />
                  <span>
                    {source.health.last_error_code}: {source.health.last_error}
                  </span>
                </div>
              )}
              <div className="fr-probe-row">
                <button
                  className="fr-action"
                  disabled={!source.public_probe_enabled || probe.isPending}
                  onClick={() => probe.mutate({ venue: source.venue, includeOneBook: true })}
                >
                  <Radio size={14} />
                  {probe.isPending && probe.variables?.venue === source.venue
                    ? 'Probing…'
                    : source.public_probe_enabled
                      ? 'Capture markets, one book & trades'
                      : 'Public probe disabled'}
                </button>
                <small>
                  {source.probe_policy_block_reason
                    ? 'Live capture and stored records are held from research use; offline fixtures remain available.'
                    : source.health.last_success_at_utc
                      ? `Last source response ${time(source.health.last_success_at_utc)}`
                      : 'No request is made automatically.'}{' '}
                  Enabled capture requests at most one listing page, one book, and ten recent
                  trades.
                </small>
              </div>
              {source.venue === 'kalshi' && (
                <div className="fr-mve-capture">
                  <div>
                    <strong>Multivariate event discovery</strong>
                    <small>
                      One public page with nested markets. A returned source cursor is saved but
                      never followed automatically; selected legs do not verify combo payoff.
                    </small>
                  </div>
                  <label>
                    Filter type
                    <select
                      aria-label="Kalshi multivariate filter type"
                      value={multivariateFilterType}
                      onChange={(event) =>
                        setMultivariateFilterType(
                          event.target.value as
                            'series_ticker' | 'collection_ticker' | 'event_ticker',
                        )
                      }
                    >
                      <option value="series_ticker">Series ticker</option>
                      <option value="collection_ticker">Collection ticker</option>
                      <option value="event_ticker">One event ticker</option>
                    </select>
                  </label>
                  <label>
                    {multivariateFilterType === 'series_ticker'
                      ? 'Kalshi series ticker'
                      : multivariateFilterType === 'collection_ticker'
                        ? 'Kalshi collection ticker'
                        : 'Kalshi event ticker'}
                    <input
                      aria-label="Kalshi multivariate filter ticker"
                      maxLength={256}
                      value={multivariateFilterValue}
                      onChange={(event) => setMultivariateFilterValue(event.target.value)}
                      placeholder={
                        multivariateFilterType === 'series_ticker'
                          ? 'Series ticker'
                          : multivariateFilterType === 'collection_ticker'
                            ? 'Collection ticker'
                            : 'Event ticker'
                      }
                    />
                  </label>
                  <button
                    className="fr-action"
                    disabled={
                      !source.public_probe_enabled ||
                      !source.capabilities.some(
                        (item) =>
                          item.capability === 'multivariate_event_discovery' && item.supported,
                      ) ||
                      !multivariateFilterValue.trim() ||
                      multivariateProbe.isPending
                    }
                    onClick={() =>
                      multivariateProbe.mutate(
                        multivariateFilterType === 'series_ticker'
                          ? { series_ticker: multivariateFilterValue.trim() }
                          : multivariateFilterType === 'collection_ticker'
                            ? { collection_ticker: multivariateFilterValue.trim() }
                            : { event_ticker: multivariateFilterValue.trim() },
                      )
                    }
                  >
                    <Database size={14} />
                    {multivariateProbe.isPending
                      ? 'Capturing one event page…'
                      : source.public_probe_enabled
                        ? 'Capture one event page'
                        : 'Public probe disabled'}
                  </button>
                  {multivariateProbe.isError && (
                    <InlineError message={multivariateProbe.error.message} />
                  )}
                  {multivariateProbe.isSuccess && (
                    <div className="fr-mve-result" role="status">
                      Saved {count(multivariateProbe.data.event_count)} event(s) and{' '}
                      {count(multivariateProbe.data.market_count)} nested market(s) ·{' '}
                      {multivariateProbe.data.has_more_source_pages
                        ? 'another source page is available'
                        : 'no source continuation reported'}{' '}
                      · evidence {shortHash(multivariateProbe.data.observation_id)} · raw{' '}
                      {shortHash(multivariateProbe.data.raw_sha256)}
                      {multivariateProbe.data.events.map((event) => (
                        <span key={event.native_event_id}>
                          {event.title} · {event.native_event_id}
                          {event.member_list_state === 'omitted'
                            ? ' · nested markets omitted by source'
                            : event.member_list_state === 'empty'
                              ? ' · source returned an empty nested-market list'
                              : ''}
                        </span>
                      ))}
                      <EvidenceDisclosure observationId={multivariateProbe.data.observation_id} />
                    </div>
                  )}
                </div>
              )}
            </article>
          );
        })
      )}
    </section>
  );
}

function VenuePill({ venue }: { venue: string }) {
  const icon = venue === 'kraken' ? 'K' : venue === 'kalshi' ? 'Ka' : 'P';
  return (
    <span className={`fr-venue-pill ${venue}`}>
      <i>{icon}</i>
      {venueLabel(venue)}
    </span>
  );
}

function SearchBox({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
}) {
  return (
    <label className="fr-search">
      <Search size={14} />
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
      />
    </label>
  );
}

function InlineError({ message }: { message: string }) {
  return (
    <div className="fr-inline-error">
      <AlertTriangle size={14} />
      {message}
    </div>
  );
}

function CandidateCard({ candidate }: { candidate: Candidate }) {
  const [virtualBalances, setVirtualBalances] = useState<Record<string, string>>({});
  const describeFillLeg = (identity: string) => {
    const leg = candidate.legs.find(
      (item) => `${item.venue}:${item.native_market_id}:${item.instrument_id}` === identity,
    );
    return leg
      ? `${venueLabel(leg.venue)} · ${label(leg.outcome_id)} (${leg.native_market_id})`
      : identity;
  };
  const fillPatternList = (identities: string[]) =>
    identities.length > 0 ? identities.map(describeFillLeg).join(', ') : 'None';
  return (
    <article className="fr-candidate">
      <div className="fr-candidate-head">
        <div>
          <span className="fr-kicker">{label(candidate.family)}</span>
          <h3>{candidate.venues.map(venueLabel).join(' + ') || 'Venue evidence incomplete'}</h3>
        </div>
        <StateBadge state={candidate.classification} />
      </div>
      <div className="fr-candidate-summary">
        <span>
          Gross basket cost<strong>{money(candidate.gross_cost)}</strong>
        </span>
        <span>
          Modeled fees<strong>{money(candidate.modeled_fees)}</strong>
        </span>
        <span>
          Modeled net cost<strong>{money(candidate.modeled_net_cost)}</strong>
        </span>
        <span>
          Worst gross result<strong>{money(candidate.worst_case_gross_pnl)}</strong>
        </span>
        <span>
          Worst net result<strong>{money(candidate.worst_case_net_pnl)}</strong>
        </span>
        <span>
          Timing verified<strong>{candidate.timing_verified ? 'Yes' : 'No'}</strong>
        </span>
        <span>
          Practical eligibility
          <strong>{candidate.practical_eligibility ? 'Established' : 'Not established'}</strong>
        </span>
      </div>
      <section className="fr-candidate-audit" aria-label="Independent arithmetic audit">
        <div className="fr-candidate-audit-head">
          <h4>Independent arithmetic audit</h4>
          <StateBadge state={candidate.independent_audit?.disposition ?? 'not_evaluated'} />
        </div>
        <p>
          {candidate.independent_audit?.message ??
            'No independent arithmetic audit is recorded for this candidate.'}
        </p>
        {candidate.independent_audit && (
          <>
            <div className="fr-candidate-audit-values">
              <span>
                Recomputed basket cost
                <strong>{money(candidate.independent_audit.recomputed_gross_cost)}</strong>
              </span>
              <span>
                Recomputed fees
                <strong>{money(candidate.independent_audit.recomputed_modeled_fees)}</strong>
              </span>
              <span>
                Recomputed net cost
                <strong>{money(candidate.independent_audit.recomputed_modeled_net_cost)}</strong>
              </span>
              <span>
                Recomputed worst net result
                <strong>{money(candidate.independent_audit.recomputed_worst_case_net_pnl)}</strong>
              </span>
              <span>
                Recomputed receipt skew
                <strong>
                  {candidate.independent_audit.recomputed_received_skew_ms == null
                    ? 'Not recorded'
                    : `${count(candidate.independent_audit.recomputed_received_skew_ms)} ms`}
                </strong>
              </span>
              <span>
                Recomputed exchange timestamp skew
                <strong>
                  {candidate.independent_audit.recomputed_exchange_skew_ms == null
                    ? 'Not recorded'
                    : `${count(candidate.independent_audit.recomputed_exchange_skew_ms)} ms`}
                </strong>
              </span>
              <span>
                Independent timing gate
                <strong>
                  {candidate.independent_audit.recomputed_timing_verified == null
                    ? 'Not recorded'
                    : candidate.independent_audit.recomputed_timing_verified
                      ? 'Pass'
                      : 'Fail'}
                </strong>
              </span>
            </div>
            <small>
              Checked {candidate.independent_audit.checked_leg_count} legs across{' '}
              {candidate.independent_audit.checked_market_count} markets · input SHA-256{' '}
              <code>{shortHash(candidate.independent_audit.input_sha256)}</code>
            </small>
          </>
        )}
      </section>
      {Object.keys(candidate.capital_by_venue).length > 0 && (
        <section
          className="fr-candidate-fill-stress fr-capital-allocation"
          aria-label="Venue-separated virtual funding"
        >
          <div>
            <span className="fr-kicker">Economic workbench · local scenario</span>
            <h4>Venue-separated virtual funding</h4>
          </div>
          <p>
            Requirements cover the full modeled basket at modeled buy prices. Each exchange has a
            separate virtual balance; surplus at one venue is not pooled or transferred to another.
            Unknown fees are excluded from the displayed requirement and prevent a sufficiency
            claim.
          </p>
          <div className="fr-capital-rows">
            {Object.entries(candidate.capital_by_venue)
              .sort(([left], [right]) => left.localeCompare(right))
              .map(([venue, requirement]) => {
                const legs = candidate.legs.filter((leg) => leg.venue === venue);
                const capitalIdentity = candidate.capital_currency_identity;
                const capitalIdentityKey = capitalIdentity
                  ? settlementIdentityLabel(capitalIdentity)
                  : null;
                const exactLegUnits = Boolean(
                  capitalIdentity &&
                  legs.length > 0 &&
                  legs.every(
                    (leg) =>
                      leg.quote_currency === capitalIdentity.code &&
                      leg.quote_currency_identity &&
                      settlementIdentityLabel(leg.quote_currency_identity) === capitalIdentityKey,
                  ),
                );
                const currencyComplete = Boolean(capitalIdentityKey && exactLegUnits);
                const currency =
                  currencyComplete && capitalIdentity
                    ? `${capitalIdentity.code} (${capitalIdentityKey})`
                    : null;
                const balanceKey = `${venue}:${capitalIdentityKey ?? 'identity-unavailable'}`;
                const feesUnknown = legs.some((leg) => leg.modeled_fee == null);
                const budgetText = virtualBalances[balanceKey] ?? '';
                const budget = budgetText ? parseExactMoney(budgetText) : null;
                const required = parseExactMoney(requirement);
                const state = !currency
                  ? 'Currency identity is missing or mixed; comparison unavailable.'
                  : !required
                    ? 'Recorded requirement exceeds the exact comparison bound.'
                    : !budgetText
                      ? 'Enter an isolated virtual balance.'
                      : !budget
                        ? 'Enter a nonnegative amount using at most 36 decimal places.'
                        : compareExactMoney(budget, required) < 0
                          ? 'Virtual funding shortfall at this venue.'
                          : feesUnknown
                            ? 'Recorded principal is covered; unresolved fees remain.'
                            : 'Modeled requirement covered at this venue.';
                return (
                  <div
                    className="fr-capital-row"
                    key={`${candidate.candidate_id}-${venue}-${capitalIdentityKey ?? 'unknown'}`}
                  >
                    <div>
                      <strong>{venueLabel(venue)}</strong>
                      <span>
                        Modeled requirement: {requirement} {currency ?? 'currency unresolved'}
                        {feesUnknown
                          ? ' · unresolved fees excluded'
                          : ' · known modeled fees included'}
                      </span>
                    </div>
                    <label>
                      <span>Virtual balance ({currency ?? 'unavailable'})</span>
                      <input
                        aria-label={`Virtual balance allocated to ${venueLabel(venue)} ${currency ?? 'unknown currency'}`}
                        inputMode="decimal"
                        maxLength={110}
                        disabled={!currency}
                        value={budgetText}
                        onChange={(event) =>
                          setVirtualBalances((current) => ({
                            ...current,
                            [balanceKey]: event.target.value,
                          }))
                        }
                      />
                    </label>
                    <small role="status">{state}</small>
                  </div>
                );
              })}
          </div>
          <small>
            Scenario input only. No account, wallet, deposit, transfer, or order interface is used.
          </small>
        </section>
      )}
      {candidate.legs.length > 0 && (
        <div className="fr-table-wrap">
          <table className="fr-table">
            <thead>
              <tr>
                <th>Venue / native market</th>
                <th>Outcome</th>
                <th>Quantity</th>
                <th>Observed ask</th>
                <th>Modeled cost</th>
                <th>Depth</th>
              </tr>
            </thead>
            <tbody>
              {candidate.legs.map((leg) => (
                <tr key={`${candidate.candidate_id}-${leg.instrument_id}`}>
                  <td>
                    {venueLabel(leg.venue)}
                    <code>{leg.native_market_id}</code>
                  </td>
                  <td>{label(leg.outcome_id)}</td>
                  <td>{leg.quantity}</td>
                  <td>{money(leg.quoted_ask)}</td>
                  <td>
                    {money(leg.modeled_buy_price)} · fee {money(leg.modeled_fee)}
                    <small>
                      {leg.quote_currency ?? 'Unknown'} ·{' '}
                      {settlementIdentityLabel(leg.quote_currency_identity)}
                    </small>
                  </td>
                  <td>{leg.displayed_depth}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {candidate.one_sided_fill_sensitivity && (
        <section className="fr-candidate-fill-stress" aria-label="One-sided fill stress">
          <div>
            <span className="fr-kicker">Execution uncertainty</span>
            <h4>One-sided fill stress</h4>
          </div>
          <p>
            Exact worst case over{' '}
            {candidate.one_sided_fill_sensitivity.pattern_space_size.toLocaleString()} full-or-none
            leg patterns. No pattern probability, follow-on hedge, or exit recovery is modeled.
          </p>
          <div className="fr-fill-stress-values">
            <span>
              Worst modeled P&amp;L before venue fees
              <strong>
                {money(candidate.one_sided_fill_sensitivity.worst_before_fees.pnl_before_fees)}
              </strong>
              <small>
                State:{' '}
                {label(candidate.one_sided_fill_sensitivity.worst_before_fees.terminal_state_id)}
              </small>
            </span>
            <span>
              Worst modeled P&amp;L after venue fees
              <strong>
                {candidate.one_sided_fill_sensitivity.worst_after_fees
                  ? money(candidate.one_sided_fill_sensitivity.worst_after_fees.pnl_after_fees)
                  : 'Unknown'}
              </strong>
              <small>
                {candidate.one_sided_fill_sensitivity.worst_after_fees
                  ? `State: ${label(candidate.one_sided_fill_sensitivity.worst_after_fees.terminal_state_id)}`
                  : 'At least one leg has an unresolved fee.'}
              </small>
            </span>
          </div>
          <div className="fr-fill-stress-patterns">
            <p>
              <strong>Before-fee pattern</strong>
              <span>
                Filled:{' '}
                {fillPatternList(
                  candidate.one_sided_fill_sensitivity.worst_before_fees.filled_leg_ids,
                )}
              </span>
              <span>
                Unfilled:{' '}
                {fillPatternList(
                  candidate.one_sided_fill_sensitivity.worst_before_fees.unfilled_leg_ids,
                )}
              </span>
            </p>
            {candidate.one_sided_fill_sensitivity.worst_after_fees && (
              <p>
                <strong>After-fee pattern</strong>
                <span>
                  Filled:{' '}
                  {fillPatternList(
                    candidate.one_sided_fill_sensitivity.worst_after_fees.filled_leg_ids,
                  )}
                </span>
                <span>
                  Unfilled:{' '}
                  {fillPatternList(
                    candidate.one_sided_fill_sensitivity.worst_after_fees.unfilled_leg_ids,
                  )}
                </span>
              </p>
            )}
          </div>
          {candidate.one_sided_fill_sensitivity.assumptions.map((assumption) => (
            <small key={assumption}>{assumption}</small>
          ))}
        </section>
      )}
      {Object.keys(candidate.gross_pnl_by_state).length > 0 && (
        <section className="fr-candidate-states" aria-label="Terminal-state payoff analysis">
          <h4>Terminal-state payoff analysis</h4>
          <div className="fr-table-wrap">
            <table className="fr-table">
              <thead>
                <tr>
                  <th>Terminal state</th>
                  <th>Modeled payout</th>
                  <th>Gross result</th>
                  <th>Net result</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(candidate.gross_pnl_by_state).map(([state, gross]) => (
                  <tr key={`${candidate.candidate_id}-${state}`}>
                    <td>{label(state)}</td>
                    <td>{money(candidate.outcome_payout_by_state[state])}</td>
                    <td>{money(gross)}</td>
                    <td>{money(candidate.net_pnl_by_state[state])}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
      <details>
        <summary>Verification reasons and assumptions</summary>
        <ul>
          {[...candidate.reasons, ...candidate.assumptions].map((item, index) => (
            <li key={`${candidate.candidate_id}-${index}`}>{item}</li>
          ))}
        </ul>
        <div className="fr-hash">
          Evidence SHA-256 <code>{candidate.evidence_sha256}</code>
        </div>
      </details>
    </article>
  );
}

function RunSummary({ run, expanded = false }: { run: Run; expanded?: boolean }) {
  const { manifest, candidates: runCandidates, classification_counts: countsByClass } = run.result;
  return (
    <article className="fr-run-summary">
      <div className="fr-run-top">
        <div>
          <StateBadge state="replay persisted" />
          <strong>{time(run.created_at_utc)}</strong>
        </div>
        <code>{shortHash(run.run_id)}</code>
      </div>
      <div className="fr-run-stats">
        <span>{manifest.market_observation_ids.length} market observations</span>
        <span>{manifest.fee_metadata_observation_ids?.length ?? 0} fee metadata observations</span>
        <span>{manifest.book_observation_ids.length} book observations</span>
        <span>{manifest.relationship_ids.length} verified relationships</span>
        <span>{runCandidates.length} evaluated candidates</span>
      </div>
      <div className="fr-run-hashes">
        <span>
          Input <code>{manifest.normalized_input_sha256}</code>
        </span>
        <span>
          Output <code>{run.result_sha256}</code>
        </span>
      </div>
      {expanded && (
        <details className="fr-run-details">
          <summary>
            Replay manifest · {manifest.replay_version} · {manifest.code_version}
          </summary>
          <p>
            As of {time(manifest.as_of_utc)} · scenario {JSON.stringify(manifest.scenario)}
          </p>
          <p>
            Classifications:{' '}
            {Object.entries(countsByClass)
              .map(([key, value]) => `${key}: ${value}`)
              .join(' · ') || 'none'}
          </p>
          {runCandidates.slice(0, 10).map((candidate) => (
            <CandidateCard key={candidate.candidate_id} candidate={candidate} />
          ))}
        </details>
      )}
    </article>
  );
}

function ReplayComparisonSummary({ comparison }: { comparison: ReplayComparison }) {
  const [baseline, compared] = comparison.arms;
  const delta = comparison.delta;
  const signed = (value: number) => (value > 0 ? `+${value}` : String(value));
  return (
    <article className="fr-comparison-summary">
      <div className="fr-run-top">
        <div>
          <StateBadge state="paired hypothetical replay" />
          <strong>{time(comparison.as_of_utc)}</strong>
        </div>
        <code>{shortHash(comparison.comparison_id)}</code>
      </div>
      <div className="fr-comparison-arms">
        {[baseline, compared].map((arm) => (
          <div key={arm.run_id}>
            <strong>{String(arm.scenario.name ?? 'scenario')}</strong>
            <span>{arm.candidate_count} candidates evaluated</span>
            <span>{arm.positive_gross_count} positive gross worst cases</span>
            <span>{arm.positive_net_count} positive modeled net worst cases</span>
            <span>{arm.unknown_net_count} with unknown modeled net</span>
          </div>
        ))}
      </div>
      <div className="fr-run-stats">
        <span>{delta.matched_candidate_count} matched constructions</span>
        <span>{delta.changed_classification_count} changed classifications</span>
        <span>
          Modeled net-positive count Δ {signed(delta.positive_net_count_delta)} · unknown net Δ{' '}
          {signed(delta.unknown_net_count_delta)}
        </span>
      </div>
      <details className="fr-run-details">
        <summary>Paired evidence · {comparison.comparison_id}</summary>
        <p>
          Both arms used input set {comparison.evidence_input_sha256}. Each run stores its own
          manifest and independent arithmetic audit. Scenario deltas describe modeled replay
          results; they do not establish fills, access, or profitability.
        </p>
        <p>
          Baseline run {baseline.run_id} · output {baseline.result_sha256}
        </p>
        <p>
          Compared run {compared.run_id} · output {compared.result_sha256}
        </p>
        <p>
          Classification count changes:{' '}
          {Object.entries(delta.classification_count_delta)
            .map(([key, value]) => `${label(key)} ${signed(value)}`)
            .join(' · ') || 'none'}
        </p>
        <code>{comparison.result_sha256}</code>
      </details>
    </article>
  );
}
