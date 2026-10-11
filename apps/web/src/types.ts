export type Financial = string;
export interface Instrument {
  asset_id: string;
  label: string;
}
export interface Level {
  price: Financial;
  size: Financial;
}
export interface Book {
  asset_id: string;
  condition_id: string;
  asks: Level[];
  bids: Level[];
  tick_size: Financial;
  min_order_size: Financial;
  received_ts_ms: number;
  exchange_ts_ms: number | null;
  valid: boolean;
  integrity: string;
  invalid_reason: string | null;
}
export interface Market {
  id: string;
  question: string;
  condition_id: string;
  protocol: string;
  instruments: Instrument[];
  source: string;
  fee: { rate: string; verified: boolean; evidence: string };
  payout_evidence: string;
  attestation?: Record<string, unknown>;
}
export interface Risk {
  allowed: boolean;
  reasons: string[];
  limits: Record<string, unknown>;
}
export interface Evaluation {
  market_id: string;
  question: string;
  source: string;
  observed_ts_ms: number;
  status: string;
  reasons: string[];
  quantity: Financial;
  available_quantity: Financial;
  gross_cost: Financial;
  fees: Financial;
  required_capital: Financial;
  minimum_payout: Financial;
  gross_profit: Financial;
  net_profit: Financial;
  gross_edge: Financial;
  net_edge: Financial;
  slippage: Financial;
  payouts: Record<string, Financial>;
  books: Book[];
  market: Market | null;
  slices: { asset_id: string; price: string; quantity: string; notional: string; fee: string }[];
  assumptions: string[];
  risk: Risk;
  economic_proof?: Record<string, unknown>;
}
export interface SystemEvent {
  severity: string;
  message: string;
  timestamp_ms: number;
  source: string;
}
export interface State {
  mode: string;
  source: string;
  status: string;
  connection: string;
  timestamp_ms: number;
  markets: number;
  instruments: number;
  books: number;
  invalid_books: number;
  oldest_book_age_ms: number | null;
  verified_opportunities: number;
  rejected_opportunities: number;
  potential_gross_profit: string;
  potential_net_profit: string;
  virtual_starting_capital: string;
  latest_simulated_pnl: string | null;
  latest_simulation: string | null;
  unit: string;
  warnings: number;
  errors: number;
  events: SystemEvent[];
  telemetry: {
    cpu_seconds?: number;
    peak_memory_kib?: number;
    broker_healthy?: boolean;
    broker_pending_actions?: number;
    broker_processing_delay_ms?: number;
    broker_recoveries?: number;
    scanner_markets_per_second?: number | null;
    uptime_seconds: number;
    processing_latency_ms: number;
    queue_depth: number;
    queue_capacity: number;
    reconnects: number;
    last_stream_message_ms: number | null;
    database_healthy: boolean;
    recording_healthy: boolean;
    last_refresh_ms: number | null;
  };
  safety: { live_execution: boolean; credentials_required: boolean; emergency_stop: boolean };
}
export interface Scenario {
  id: string;
  category: string;
  description: string;
  expected_behavior: string;
}
export interface Portfolio {
  starting_capital: string;
  available: string;
  reserved: string;
  locked: string;
  fees: string;
  settlement_proceeds: string;
  realized_pnl: string;
  unrealized_pnl: string;
  max_drawdown: string;
  positions: Record<string, string>;
  matched_quantity: string;
  unmatched_quantity: string;
  unit: string;
}
export interface TimelineEvent {
  time_ms: number;
  sequence: number;
  kind: string;
  detail: Record<string, unknown>;
  portfolio: Portfolio;
}
export interface Run {
  scenario_id: string;
  seed: number;
  passed: boolean;
  invariant_violations: string[];
  description: string;
  reproducibility_hash: string;
  strategy_version: string;
  simulator_version: string;
  dataset_version: string;
  evaluation: Evaluation;
  risk: Risk;
  portfolio: Portfolio;
  timeline: TimelineEvent[];
  ledger: Record<string, unknown>[];
  orders: Record<string, unknown>[];
}
export interface Stored<T> {
  id: number;
  key: string;
  source: string;
  received_ts_ms: number;
  payload: T;
}
export interface Analytics {
  source: string;
  observation_window: number;
  status_distribution: Record<string, number>;
  activity: { timestamp_ms: number; observations: number; verified: number }[];
  simulations: {
    id: string;
    timestamp_ms: number;
    scenario_id: string;
    seed: number;
    passed: boolean;
    pnl: string;
    source: string;
  }[];
  note: string;
  feasibility?: {
    positive_observed_candidates: number;
    structurally_supported_observations: number;
    passing_net_edge_samples: number;
    hypothetical_fill_count: number;
    modeled_settled_positions: number;
    net_return_on_total_virtual_capital: string;
    note: string;
    opportunity_episodes: Record<string, unknown>[];
    paper_trades: Record<string, unknown>[];
    rejection_reasons: Record<string, number>;
  };
}
export interface Settings {
  mode: string;
  market_limit: number;
  refresh_seconds: number;
  risk_limits: Record<string, unknown>;
  execution: string;
}

export interface PaperAccount {
  status: string;
  healthy: boolean;
  mode: string;
  strategy_version: string;
  execution: { name: string };
  unit: string;
  initial_capital: string;
  available: string;
  reserved: string;
  locked: string;
  equity: string;
  realized_pnl: string;
  unrealized_pnl: string;
  fees: string;
  max_drawdown: string;
  capital_utilization: string;
  net_exposure_shares: string;
  paper_trades: number;
  hypothetical_fills: number;
  settled_positions: number;
  rejected: number;
  observations: number;
  pending_actions: number;
  recovery_count: number;
  risk_limits: Record<string, string | number>;
  decisions: { id: string; ts: number; market_id: string; risk: Risk; evaluation: Evaluation }[];
  positions: {
    id: string;
    market_id: string;
    source: string;
    execution_model: { name: string };
    fill_certainty: string;
    settled: boolean;
    portfolio: Portfolio;
    orders: {
      id: string;
      status: string;
      quantity: string;
      remaining: string;
      acknowledged: boolean;
    }[];
    decision: Record<string, unknown>;
    ledger: Record<string, unknown>[];
  }[];
}
