import { Fragment, useMemo, useState } from 'react';
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { UseMutationResult } from '@tanstack/react-query';
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BarChart3,
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
import {
  KalshiFeePanel,
  type KalshiFeeMetadataCaptureResult,
  type KalshiFeeOrderSensitivityResponse,
} from './KalshiFeePanel';
import { preciseUtcTime } from './frontierTime';
import { compareRelationshipTerms } from './frontierRelationshipTerms';
import { KrakenCandleHistoryPanel } from './KrakenCandleHistoryPanel';
import { FrontierHostResourcePanel } from './FrontierHostResources';
import {
  KrakenBookUpdatesPanel,
  type KrakenBookCaptureReplay,
  type KrakenBookUpdateCaptureResult,
} from './KrakenBookUpdatesPanel';
import './frontier.css';

type Venue = 'polymarket' | 'kalshi' | 'kraken' | 'coinbase_exchange' | 'gemini_spot';
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
type SourceOperationAdmission = {
  scope: 'frontier_router_instance';
  max_concurrent_source_operations: number;
  single_flight_per_venue: boolean;
  maximum_acquire_wait_ms: number;
  overload_status: number;
  overload_behavior: string;
  runtime_snapshot?: {
    sampled_at_utc: string;
    active_operations: number;
    active_venues: Venue[];
    admitted_operations_total: number;
    busy_rejections_total: number;
    busy_rejections_by_scope: { venue: number; capacity: number };
  };
};
type SourceInventory = {
  items: Source[];
  operation_admission?: SourceOperationAdmission;
  network_called?: false;
};
type FiniteCollectionResponse = {
  venue: Venue;
  collection_run: {
    run_id: string;
    state: string;
    market_count: number;
    book_count: number;
    failed_book_count: number;
    trade_batch_count: number;
    trade_count: number;
    failed_trade_count: number;
    request_count: number;
    updated_at_utc: string;
    failures: { code: string; message: string }[];
    source_health: { state: string } | null;
  };
  adapter_request_count: number;
  adapter_request_upper_bound_per_attempt: number;
  research_only: true;
  live_orders: false;
  source_health_scope: 'adapter_local_checkpoint';
  note: string;
};
type CollectionRunSummary = {
  run_id: string;
  venue: Venue;
  adapter_version: string;
  created_at_utc: string;
  updated_at_utc: string;
  state: string;
  checkpoint_sequence: number;
  checkpoint_sha256: string;
  market_count: number;
  book_count: number;
  failed_book_count: number;
  trade_batch_count?: number;
  trade_count?: number;
  failed_trade_count?: number;
  request_count: number;
  failure_count: number;
  source_health_state: string | null;
  resumable: boolean;
  resume_block_reason: string | null;
};
type CollectionRunsResponse = {
  items: CollectionRunSummary[];
  returned: number;
  limit: number;
  next_before_run_id: string | null;
  network_called: false;
  research_only: true;
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
type CoverageAnalytics = {
  schema_version: 3;
  as_of_utc: string;
  scope: string;
  samples: {
    distinct_markets: number;
    market_records: number;
    book_observation_records: number;
    invalid_normalized_book_records: number;
    public_trade_observation_records: number;
    invalid_normalized_public_trade_records: number;
    price_history_observation_records: number;
    invalid_normalized_price_history_records: number;
    unique_instrument_books: number;
    eligible_replay_runs: number;
    candidate_records: number;
    candidate_scan_truncated: boolean;
    market_record_limit: number;
    book_record_limit: number;
    public_trade_record_limit: number;
    replay_run_limit: number;
    price_history_record_limit: number;
    candidate_record_limit: number;
  };
  market_mix: {
    venue: Venue;
    market_kind: string;
    market_count: number;
    instrument_count: number;
    event_count: number;
  }[];
  stored_market_counts_by_venue: {
    venue: Venue;
    market_count: number;
    instrument_count: number;
  }[];
  source_quality: {
    venue: Venue;
    latest_instrument_books: number;
    quality_valid_pricing_books: number;
    two_sided_books: number;
    one_sided_or_empty_books: number;
    crossed_books: number;
    flagged_books: number;
    unflagged_books: number;
    unjoined_or_provenance_mismatch_records: number;
    with_exchange_timestamp: number;
    with_clock_uncertainty: number;
    with_declared_freshness_limit: number;
    without_declared_freshness_limit: number;
    within_declared_freshness_limit: number;
    stale_by_declared_freshness_limit: number;
    future_received_timestamp: number;
    median_receipt_age_ms: string | null;
    p90_receipt_age_ms: string | null;
  }[];
  historical_price_quality_scope: string;
  public_trade_quality_scope: string;
  public_trade_quality: {
    venue: Venue;
    capture_count: number;
    invalid_capture_count: number;
    trade_print_count: number;
    empty_capture_count: number;
    unique_market_count: number;
    unique_instrument_count: number;
    prints_with_exchange_timestamp: number;
    prints_without_exchange_timestamp: number;
    prints_with_clock_uncertainty: number;
    prints_without_clock_uncertainty: number;
    future_capture_timestamp_count: number;
    future_exchange_timestamp_count: number;
    latest_capture_received_at_utc: string | null;
    median_capture_age_ms: string | null;
    p90_capture_age_ms: string | null;
  }[];
  historical_price_quality: {
    venue: Venue;
    capture_count: number;
    unique_instrument_count: number;
    source_point_count: number;
    empty_capture_count: number;
    market_bound_capture_count: number;
    unbound_capture_count: number;
    future_capture_timestamp_count: number;
    future_point_timestamp_count: number;
    latest_capture_received_at_utc: string | null;
    median_capture_age_ms: string | null;
    p90_capture_age_ms: string | null;
    earliest_source_point_at_utc: string | null;
    latest_source_point_at_utc: string | null;
    largest_adjacent_sample_gap_seconds: number | null;
  }[];
  pricing: {
    venue: Venue;
    market_kind: string;
    quantity_unit: string;
    quote_asset_identity: string;
    instrument_count: number;
    median_relative_spread_bps: string | null;
    p90_relative_spread_bps: string | null;
    median_best_bid_depth: string | null;
    median_best_ask_depth: string | null;
  }[];
  candidate_research: {
    counts_by_classification: Record<string, number>;
    independently_audited_candidates: number;
    audited_timing_verified_candidates: number;
    median_audited_received_skew_ms: string | null;
    p90_audited_received_skew_ms: string | null;
    median_audited_exchange_skew_ms: string | null;
    p90_audited_exchange_skew_ms: string | null;
    gross_positive_audited_timing_verified_constructions_repeated_across_distinct_books: number;
    gross_positive_candidate_construction_signatures: number;
    rejection_reasons: { reason: string; count: number }[];
  };
  network_called: false;
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
    settlement_asset?: string | null;
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
    fixed_fee?: string | null;
    rate: string | null;
    fee_multiplier?: string | null;
    formula: string | null;
    fee_currency: string | null;
    fee_currency_identity?: SettlementAssetIdentity | null;
    source_url: string | null;
    evidence_sha256?: string | null;
    evidence_observation_ids?: string[];
    evidence_observed_at_utc?: string | null;
    effective_at_utc?: string | null;
    expires_at_utc?: string | null;
    note: string;
  };
  native_fields: Record<string, unknown>;
  instruments: {
    canonical_id?: string;
    native_instrument_id: string;
    label: string;
    outcome_id: string | null;
    quantity_unit?: string;
    price_currency?: string | null;
    price_currency_identity?: SettlementAssetIdentity | null;
    tick_size?: string | null;
    price_increment_ranges?: { start: string; end: string; step: string }[] | null;
    quantity_step?: string | null;
    minimum_quantity?: string | null;
    minimum_notional?: string | null;
    payouts?: { state_id: string; amount: string }[];
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
  is_block_trade?: boolean | null;
  taker_outcome_side?: 'yes' | 'no' | null;
  taker_book_side?: 'bid' | 'ask' | null;
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
type PriceHistoryPoint = { timestamp_utc: string; price: string };
type PriceHistorySeries = {
  venue: Venue;
  native_instrument_id: string;
  interval: '1d' | '1w';
  fidelity_minutes: number;
  requested_start_ts: number;
  requested_end_ts: number;
  bound_market_observation_id: string | null;
  points: PriceHistoryPoint[];
  source_price_semantics: 'source_reported_price_sample';
  source_limit_note: string;
  provenance: { observation_id: string; raw_sha256: string };
};
type PriceHistoryResponse = {
  items: {
    series: PriceHistorySeries;
    observation_id: string;
    raw_sha256: string;
    received_at_utc: string;
  }[];
  venue: Venue;
  native_instrument_id: string | null;
  returned: number;
  limit?: number;
  offset?: number;
  scan_bound?: number;
  scan_may_be_incomplete?: boolean;
  has_more?: boolean;
  source_state?: string;
};
type PriceHistoryCaptureResult = {
  venue: Venue;
  native_instrument_id: string;
  bound_market_id: string;
  bound_market_observation_id: string;
  series: PriceHistorySeries;
  point_count: number;
  observation_id: string;
  raw_sha256: string;
  source_state: string;
  request_count_delta: number;
  network_calls_bounded_by: number;
  hypothetical_only: true;
  note: string;
};
type PolymarketBookUpdateCaptureResult = {
  venue: 'polymarket';
  market_id: string;
  native_market_id: string;
  bound_market_observation_id: string;
  capture_status: 'captured' | 'no_market_updates_observed';
  frame_count: number;
  normalized_update_count: number;
  capture_bounds: {
    max_frames: number;
    max_updates: number;
    max_duration_seconds: number;
    stream_connections: number;
  };
  frames: {
    observation_id: string;
    raw_sha256: string;
    received_at_utc: string;
    source_url: string;
    source_schema_version: string;
    adapter_version: string;
    updates: {
      native_market_id: string;
      native_instrument_id: string;
      event_type: string;
      source_timestamp_utc: string | null;
      bid_level_count: number;
      ask_level_count: number;
      price_change_count: number;
      reported_best_bid: string | null;
      reported_best_ask: string | null;
      book_hash: string | null;
      min_order_size: string | null;
      tick_size: string | null;
      neg_risk: boolean | null;
      last_trade_price: string | null;
      continuity: string;
      quality_flags: string[];
    }[];
  }[];
  source_state: string;
  hypothetical_only: true;
  note: string;
};
type PolymarketStoredBookUpdateFrame = {
  observation_id: string;
  received_at_utc: string;
  raw_sha256: string;
  native_market_id: string;
  capture_started_at_utc: string;
  bound_market_observation_id: string | null;
  normalized_event_count: number;
  event_types: string[];
};
type PolymarketStoredBookUpdatePage = {
  items: PolymarketStoredBookUpdateFrame[];
  returned: number;
  limit: number;
  offset: number;
  next_offset: number | null;
  network_called: false;
  research_only: true;
};
type PolymarketBookReplayUpdate = {
  schema_version: 1 | 2;
  native_market_id: string;
  native_market_id_kind: 'condition_id';
  native_instrument_id: string;
  event_type: 'book' | 'price_change' | 'best_bid_ask' | 'tick_size_change';
  source_timestamp_utc: string | null;
  bids: { price: string; quantity: string; exchange_timestamp_utc: string | null }[];
  asks: { price: string; quantity: string; exchange_timestamp_utc: string | null }[];
  changes: {
    price: string;
    reported_size: string;
    side: 'BUY' | 'SELL';
    source_hash: string | null;
    reported_best_bid: string | null;
    reported_best_ask: string | null;
  }[];
  reported_best_bid: string | null;
  reported_best_ask: string | null;
  book_hash: string | null;
  min_order_size: string | null;
  tick_size: string | null;
  neg_risk: boolean | null;
  last_trade_price: string | null;
  old_tick_size: string | null;
  new_tick_size: string | null;
  continuity: 'unverified_no_sequence_or_gap_detection';
  quality_flags: string[];
};
type PolymarketBookUpdatesReplayResult = {
  replay_version: 'polymarket-book-event-replay-1' | 'polymarket-book-event-replay-2';
  schema_version: 1 | 2;
  native_market_id: string;
  bound_market_observation_id: string;
  capture_started_at_utc: string;
  frame_evidence: {
    observation_id: string;
    raw_sha256: string;
    normalized_sha256: string;
    frame_schema_version: 1 | 2;
    frame_ordinal: number;
    elapsed_since_capture_start_ns: number;
    received_at_utc: string;
    normalized_event_count: number;
  }[];
  frames: {
    observation_id: string;
    frame_ordinal: number;
    received_at_utc: string;
    updates: PolymarketBookReplayUpdate[];
  }[];
  event_count: number;
  input_sha256: string;
  result_sha256: string;
  message_order_basis: 'local_monotonic_elapsed';
  continuity: 'unverified_no_sequence_or_gap_detection';
  book_reconstructed: false;
  event_economics_eligible: false;
  classification: 'context_only';
};
type PriceHistoryReplayResult = {
  schema_version: number;
  run_id: string;
  result_sha256: string;
  manifest: {
    schema_version: number;
    input_sha256: string;
    observation_ids: string[];
    replay_version: string;
    code_version: string;
    as_of_utc: string;
    interpretation: 'descriptive_source_sample_replay';
  };
  series: {
    observation_id: string;
    raw_sha256: string;
    venue: Venue;
    native_instrument_id: string;
    interval: '1d' | '1w';
    fidelity_minutes: number;
    requested_start_ts: number;
    requested_end_ts: number;
    bound_market_observation_id: string | null;
    point_count: number;
    first_point_ts: number | null;
    last_point_ts: number | null;
    observed_point_span_seconds: number | null;
    largest_adjacent_sample_gap_seconds: number | null;
    minimum_sampled_price: string | null;
    maximum_sampled_price: string | null;
    future_point_timestamp_count: number;
  }[];
  candidate_generation: 'not_performed';
};
type PriceHistoryReplayListResponse = {
  items: PriceHistoryReplayResult[];
  returned: number;
  limit: number;
  offset: number;
  held_replays_omitted: number;
  has_more: boolean;
  scan_may_be_incomplete: boolean;
  source_state: string;
  network_called: false;
};
type MarketMetadataCaptureResult = {
  venue: 'polymarket' | 'kalshi';
  market_id: string;
  bound_market_observation_id: string;
  market: Market;
  observation_id: string;
  raw_sha256: string;
  request_count_delta: number;
  network_calls_bounded_by: number;
  catalogue_market_replaced: false;
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
  latest_review: RelationshipReviewRecord | null;
  evidence: {
    method: string;
    matcher_version?: string;
    verifier_version?: string | null;
    observation_ids: string[];
    source_fields: string[];
    details: string[];
  }[];
};
type RelationshipReviewRecord = {
  review_id: string;
  relationship_id: string;
  adjudicated_relationship_id: string;
  decision: string;
  reviewer_label: string;
  reason: string;
  evidence_observation_ids: string[];
  external_assertion_id: string | null;
  supersedes_review_id: string | null;
  created_at_utc: string;
};
type RelationshipReviewHistoryPage = {
  items: RelationshipReviewRecord[];
  total: number;
  limit: number;
  has_more: boolean;
  next_cursor: string | null;
  reviewer_identity_authenticated: false;
  external_assertions_authenticated: false;
};
type GraphNode = {
  market_id: string;
  market: Omit<Market, 'source_observation_record_id'> | null;
  source_observation_record_id: string | null;
  market_record_available: boolean;
};
type EntityContextNode = {
  entity_id: string;
  kind:
    | 'venue'
    | 'event'
    | 'market'
    | 'contract'
    | 'instrument'
    | 'component_contract'
    | 'outcome'
    | 'payoff_state'
    | 'asset_reference'
    | 'settlement_asset';
  label: string;
  label_truncated?: boolean;
  venue: Venue | null;
  native_id: string | null;
  native_id_truncated: boolean;
  market_kind: string | null;
  lifecycle: string | null;
  quantity_unit: string | null;
  outcome_id: string | null;
  outcome_id_truncated?: boolean;
  selected_side: 'yes' | 'no' | null;
  identity_scope: string | null;
  value: string | null;
  resolution_authority: string | null;
  resolution_primary_rule: string | null;
  resolution_secondary_rule: string | null;
  resolution_closes_at_utc: string | null;
  resolution_settles_at_utc: string | null;
  resolution_fingerprint: string | null;
  resolution_verified: boolean | null;
  payoff_state_ids: string[];
  payoff_state_ids_truncated?: boolean;
  payoff_exhaustive: boolean | null;
  payoff_verified: boolean | null;
  record_available: boolean;
  market_ids: string[];
  source_observation_ids: string[];
};
type EntityContextLink = {
  link_id: string;
  source_entity_id: string;
  target_entity_id: string;
  link_type: string;
  source_market_id: string;
  source_observation_id: string | null;
  source_field: string;
  semantic_basis: 'normalized_source_metadata';
  economic_equivalence_asserted: false;
};
type EntityContextGraph = {
  schema_version: 1;
  model_version: string;
  scope: 'loaded_relationship_market_nodes';
  semantics: 'structural_metadata_only';
  economic_equivalence_asserted: false;
  source_market_count: number;
  represented_market_count: number;
  nodes: EntityContextNode[];
  links: EntityContextLink[];
  truncated: boolean;
  truncation_reasons: string[];
  limitations: string[];
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
  entity_context?: EntityContextGraph;
};
type GraphPoint = { id: string; title: string; venue: string; x: number; y: number };
type JointStateMapping = {
  mapping_id: string;
  market_ids: string[];
  joint_state_ids: string[];
  state_by_market: Record<string, Record<string, string>>;
  external_assertion_id: string;
  evidence_observation_ids: string[];
  asserted_at_utc: string;
  semantic_status: 'externally_asserted_unverified';
};
type JointStateReplayResult = Run['result'] & { run_id: string };
type Candidate = {
  candidate_id: string;
  source_run_id?: string;
  source_run_sha256?: string;
  family: string;
  classification: string;
  market_ids?: string[];
  joint_state_mapping_id?: string | null;
  hypothetical: boolean;
  practical_eligibility: boolean;
  venues: string[];
  legs: {
    venue: string;
    native_market_id: string;
    instrument_id: string;
    outcome_id: string;
    quantity_unit?: string | null;
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
  partial_fill_grid_sensitivity?: {
    model_version: string;
    leg_count: number;
    fill_fraction_grid: string[];
    feasible_fill_fractions_by_leg: Record<string, string[]>;
    fees_complete: boolean;
    worst_before_fees: {
      terminal_state_id: string;
      leg_fills: { leg_id: string; fill_fraction: string; filled_quantity: string }[];
      pnl_before_fees: string;
      pnl_after_fees: string | null;
    };
    worst_after_fees: {
      terminal_state_id: string;
      leg_fills: { leg_id: string; fill_fraction: string; filled_quantity: string }[];
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
type CapitalCarrySensitivity = {
  schema_version: number;
  model_version: string;
  run_id: string;
  run_sha256: string;
  candidate_id: string;
  candidate_classification: string;
  classification_unchanged: boolean;
  hypothetical_only: boolean;
  capital_currency_identity: SettlementAssetIdentity;
  total_carry_cost: string;
  worst_case_gross_pnl_before_carry: string | null;
  worst_case_gross_pnl_after_carry: string | null;
  worst_case_net_pnl_before_carry: string | null;
  worst_case_net_pnl_after_carry: string | null;
  input_sha256: string;
  result_sha256: string;
  audit: {
    disposition: string;
    message: string;
    recomputed_total_carry_cost: string | null;
    checks: string[];
  };
  venues: {
    venue: string;
    capital: string;
    annual_rate_bps: string;
    post_settlement_delay_seconds: number;
    start_at_utc: string;
    capital_released_at_utc: string;
    duration_seconds: string;
    carry_cost: string;
    settlement_evidence: {
      market_id: string;
      observation_id: string;
      observation_row_sha256: string;
      raw_sha256: string;
      resolution_evidence_sha256: string;
      resolution_fingerprint: string;
      settles_at_utc: string;
    }[];
  }[];
  assumptions: string[];
  limitations: string[];
};
type FundingCurrencySensitivity = {
  schema_version: number;
  model_version: string;
  run_id: string;
  run_sha256: string;
  candidate_id: string;
  candidate_evidence_sha256: string;
  candidate_classification: string;
  candidate_practical_eligibility: boolean;
  classification_unchanged: boolean;
  practical_eligibility_unchanged: boolean;
  candidate_economics_unchanged: boolean;
  hypothetical_only: boolean;
  target_currency_identity: SettlementAssetIdentity;
  unresolved_candidate_fee_leg_count: number;
  total_conversion_fee_target: string;
  pnl_scenario: {
    status: string;
    reason: string | null;
    funding_input_sha256: string;
    target_currency_identity: SettlementAssetIdentity;
    modeled_conversion_fee_target: string;
    candidate_net_pnl_by_state: Record<string, string>;
    net_pnl_after_conversion_by_state: Record<string, string>;
    worst_case_net_pnl_after_conversion: string | null;
    all_outcomes_positive_after_conversion: boolean | null;
    audit: {
      algorithm_version: string;
      disposition: string;
      input_sha256: string;
      candidate_audit_input_sha256: string | null;
      recomputed_net_pnl_after_conversion_by_state: Record<string, string>;
      recomputed_worst_case_net_pnl_after_conversion: string | null;
      checks: string[];
      message: string;
    };
  };
  input_sha256: string;
  result_sha256: string;
  audit: { disposition: string; message: string; checks: string[] };
  venues: {
    venue: string;
    required_capital_target: string;
    funding_currency_identity: SettlementAssetIdentity;
    balance_amount: string;
    target_units_per_funding_unit: string;
    conversion_fee_bps: string;
    required_funding_amount: string;
    available_capital_target_after_fee: string;
    conversion_fee_target_amount: string;
    shortfall_target: string;
    shortfall_funding: string;
    model_requirement_covered: boolean;
  }[];
  assumptions: string[];
  limitations: string[];
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
      joint_state_mappings?: JointStateMapping[];
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
type DiscoveryScopeArm = {
  scope: 'polymarket_only' | 'venue_local' | 'cross_venue';
  venues: Venue[];
  replay_run_ids: string[];
  market_count: number;
  instrument_count: number;
  book_count: number;
  observed_instrument_count: number;
  relationship_count: number;
  candidates: {
    candidate_id: string;
    family: string;
    classification: string;
    audit_disposition: string;
    worst_case_gross_pnl: string | null;
    worst_case_net_pnl: string | null;
  }[];
  family_counts: Record<string, number>;
  classification_counts: Record<string, number>;
  audit_disposition_counts: Record<string, number>;
};
type DiscoveryScopeComparison = {
  comparison_id: string;
  normalized_input_sha256: string;
  result_sha256: string;
  code_version: string;
  as_of_utc: string;
  arms: [DiscoveryScopeArm, DiscoveryScopeArm, DiscoveryScopeArm];
  deltas: {
    baseline: string;
    compared: string;
    matched_candidate_count: number;
    unchanged_classification_count: number;
    changed_classification_count: number;
    baseline_only_candidate_count: number;
    compared_only_candidate_count: number;
    family_count_delta: Record<string, number>;
    classification_count_delta: Record<string, number>;
  }[];
};
type DiscoveryCandidateEvidence = {
  candidate_id: string;
  family: string;
  classification: string;
  venues: string[];
  legs: {
    venue: string;
    native_market_id: string;
    instrument_id: string;
    outcome_id: string;
    quantity_unit?: string | null;
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
  capital_currency_identity?: SettlementAssetIdentity | null;
  practical_eligibility: boolean;
  received_skew_ms: number | null;
  exchange_skew_ms: number | null;
  timing_verified: boolean;
  independent_audit: {
    disposition: string;
    input_sha256: string;
    checks: string[];
    message: string;
  } | null;
  assumptions: string[];
  reasons: string[];
  evidence_sha256: string;
};
type FrontierDiscoveryReplayEvidence = {
  run_id: string;
  candidates: DiscoveryCandidateEvidence[];
};
type FrontierArenaDiscoveryJob = {
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
  runtime_profile: FrontierArenaReplayJob['runtime_profile'];
  result: { comparison_id?: string; frontier_discovery_sha256?: string } | null;
};
type FrontierArenaDiscoveryJobs = {
  items: FrontierArenaDiscoveryJob[];
  limit: number;
  scanned: number;
  scan_bound: number;
  scan_may_be_incomplete: boolean;
  research_only: true;
};
type FrontierArenaDiscoveryResult = {
  artifact: {
    comparison: DiscoveryScopeComparison;
    replays: FrontierDiscoveryReplayEvidence[];
    snapshot_id: string;
    snapshot_sha256: string;
    result_sha256: string;
  };
  research_only: true;
  orders_submitted: false;
  authenticated_requests: false;
  integrity_verified: true;
};
type FrontierTimelineFrame = {
  as_of_utc: string;
  replay_run_id: string;
  replay_result_sha256: string;
  fresh_book_count: number;
  included_book_count: number;
  stale_book_count: number;
  not_yet_observed_count: number;
  excluded_source_book_count: number;
  source_states: { venue: string; state: string; basis: string | null; reason: string | null }[];
  instrument_states: {
    market_id: string;
    venue: string;
    native_market_id: string;
    native_instrument_id: string;
    book_state: string;
    exclusion: string;
    included_in_replay: boolean;
    observation_id: string | null;
    received_at_utc: string | null;
    age_ms: number | null;
    exchange_timestamp_utc?: string | null;
    exchange_timestamp_semantics?: string | null;
    clock_uncertainty_ms?: string | null;
    freshness_limit_ms?: number | null;
  }[];
  candidate_count: number;
  classification_counts: Record<string, number>;
  candidates: {
    candidate_id: string;
    family: string;
    classification: string;
    audit_disposition: string | null;
    worst_case_gross_pnl: string | null;
    worst_case_net_pnl: string | null;
    timing_verified: boolean;
    evidence_sha256: string;
  }[];
};
type FrontierTimelineJob = {
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
  runtime_profile: FrontierArenaReplayJob['runtime_profile'];
  result: { timeline_id?: string; frontier_timeline_sha256?: string } | null;
};
type FrontierTimelineJobs = {
  items: FrontierTimelineJob[];
  limit: number;
  scanned: number;
  scan_bound: number;
  scan_may_be_incomplete: boolean;
  research_only: true;
};
type FrontierTimelineResult = {
  artifact: {
    snapshot_id: string;
    snapshot_sha256: string;
    result_sha256: string;
    timeline: {
      timeline_id: string;
      result_sha256: string;
      manifest: {
        code_version: string;
        input_sha256: string;
        market_observation_ids: string[];
        book_observation_ids: string[];
        relationship_ids: string[];
        source_status_sha256s: string[];
        evaluation_times_utc: string[];
        max_book_age_ms: number;
      };
      frames: FrontierTimelineFrame[];
    };
  };
  research_only: true;
  orders_submitted: false;
  authenticated_requests: false;
  integrity_verified: true;
};
type RecordedSourceStatusEvent = {
  venue: Venue;
  observed_at_utc: string;
  state: 'available' | 'degraded' | 'unavailable';
  basis: 'recorded';
  evidence_observation_id: string;
  reason: string;
};
type RecordedSourceHealthCheckpoint = {
  event: RecordedSourceStatusEvent;
  run_id: string;
  adapter_version: string;
  checkpoint_sequence: number;
  checkpoint_updated_at_utc: string;
  last_success_at_utc: string | null;
  source_health_state: string;
};
type RecordedSourceHealthCatalog = {
  items: RecordedSourceHealthCheckpoint[];
  returned: number;
  limit: number;
  network_called: false;
  research_only: true;
  source_health_scope: 'adapter_local_checkpoint';
};
type Readiness = { gates: { name: string; state: string; detail: string }[] };
type ListResponse<T> = { items: T[]; returned: number; limit: number; offset: number };
type ObservationEvidence = {
  observation_id: string;
  raw_sha256: string;
  row_sha256: string;
  normalized?: {
    record_kind?: string;
    error_code?: string;
    message?: string;
    response_rejection?: {
      rejection_stage: 'content_length' | 'response_stream';
      response_body_limit_bytes: number;
      declared_content_length_bytes: number | null;
      bytes_yielded_at_rejection: number;
    } | null;
  };
  raw: {
    request_url: string;
    http_status: number;
    request_started_at_utc?: string;
    received_at_utc?: string;
    request_elapsed_monotonic_ns?: number | null;
    raw_body: string;
    raw_body_state?: 'complete' | 'not_captured_after_size_limit';
    adapter_version: string;
  };
};
type Section =
  | 'overview'
  | 'coverage'
  | 'sources'
  | 'markets'
  | 'relationships'
  | 'opportunities'
  | 'workbench'
  | 'replay';

const sections: { id: Section; label: string; icon: typeof Globe2 }[] = [
  { id: 'overview', label: 'Overview', icon: Activity },
  { id: 'coverage', label: 'Coverage & quality', icon: BarChart3 },
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
const exactMoney = (value: string | null | undefined) => {
  if (value == null) return 'Not established';
  const match = /^([+-]?)(\d+)(\.\d+)?$/.exec(value);
  if (!match) return value;
  const [, sign, whole, fraction = ''] = match;
  return `${sign}${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}${fraction}`;
};
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
type SettlementIdentityTuple = readonly [
  number,
  SettlementAssetIdentity['kind'],
  string,
  string | null,
  string | null,
];
const settlementIdentityTuple = (value: unknown): SettlementIdentityTuple | null => {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return null;
  const identity = value as Record<string, unknown>;
  const expectedFields = ['schema_version', 'kind', 'code', 'network_id', 'asset_reference'];
  if (
    Object.keys(identity).length !== expectedFields.length ||
    expectedFields.some((field) => !Object.prototype.hasOwnProperty.call(identity, field)) ||
    Object.keys(identity).some((field) => !expectedFields.includes(field))
  ) {
    return null;
  }
  const { schema_version, kind, code, network_id, asset_reference } = identity;
  if (
    schema_version !== 1 ||
    (kind !== 'fiat' && kind !== 'token' && kind !== 'other') ||
    typeof code !== 'string' ||
    !/^[A-Z0-9]{2,16}$/.test(code)
  ) {
    return null;
  }
  if (kind === 'fiat') {
    if (!/^[A-Z]{3}$/.test(code) || network_id !== null || asset_reference !== null) {
      return null;
    }
  } else {
    if (
      typeof network_id !== 'string' ||
      !network_id ||
      network_id.trim() !== network_id ||
      /\s/.test(network_id) ||
      network_id !== network_id.toLowerCase() ||
      typeof asset_reference !== 'string' ||
      !asset_reference ||
      asset_reference.trim() !== asset_reference ||
      /\s/.test(asset_reference) ||
      asset_reference.split('').some((character) => character.charCodeAt(0) > 0x7f)
    ) {
      return null;
    }
    try {
      encodeURIComponent(network_id);
      encodeURIComponent(asset_reference);
    } catch {
      return null;
    }
  }
  return [
    schema_version,
    kind,
    code,
    network_id as string | null,
    asset_reference as string | null,
  ];
};
const sameSettlementIdentity = (left: unknown, right: unknown) => {
  const leftFields = settlementIdentityTuple(left);
  const rightFields = settlementIdentityTuple(right);
  return Boolean(
    leftFields &&
    rightFields &&
    leftFields[0] === rightFields[0] &&
    leftFields[1] === rightFields[1] &&
    leftFields[2] === rightFields[2] &&
    leftFields[3] === rightFields[3] &&
    leftFields[4] === rightFields[4],
  );
};
const settlementIdentityLabel = (identity: SettlementAssetIdentity | null | undefined) => {
  if (!identity) return 'Identity not established';
  const fields = settlementIdentityTuple(identity);
  if (!fields) return 'Identity unsupported or malformed';
  const [, kind, code, networkId, assetReference] = fields;
  if (kind === 'fiat') return `fiat:${code}`;
  if (networkId === null || assetReference === null) return 'Identity unsupported or malformed';
  return `${kind}:${code}:${encodeURIComponent(networkId)}:${encodeURIComponent(assetReference)}`;
};
const venueLabel = (value: string) =>
  ({
    polymarket: 'Polymarket',
    kalshi: 'Kalshi',
    kraken: 'Kraken Spot',
    coinbase_exchange: 'Coinbase Exchange Spot',
    gemini_spot: 'Gemini Spot',
    unknown: 'Not in loaded window',
  })[value] ?? value;

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
    const venueOrder = [
      'polymarket',
      'kalshi',
      'kraken',
      'coinbase_exchange',
      'gemini_spot',
      'unknown',
    ];
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
      polymarket: 120,
      kalshi: 360,
      kraken: 600,
      coinbase_exchange: 840,
      gemini_spot: 1080,
      unknown: 1320,
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
    return { nodes, centers, venueOrder, height: Math.max(250, 126 + maxRows * 66) };
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
      coinbase_exchange: 'COINBASE SPOT',
      gemini_spot: 'GEMINI SPOT',
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
          viewBox={`0 0 1200 ${graph.height}`}
          height={graph.height}
          role="group"
          aria-label={`Relationship network showing ${relationships.length} bounded market relationships`}
        >
          {graph.venueOrder.map((venue) => (
            <text
              key={venue}
              className="fr-network-column"
              x={graph.centers[venue]}
              y="24"
              textAnchor="middle"
            >
              {venueName(venue)}
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

function EntityContextExplorer({ context }: { context?: EntityContextGraph }) {
  const [selectedMarketId, setSelectedMarketId] = useState('');
  const marketNodes = useMemo(
    () => context?.nodes.filter((node) => node.kind === 'market') ?? [],
    [context],
  );
  const marketByEntityId = useMemo(
    () => new Map((context?.nodes ?? []).map((node) => [node.entity_id, node])),
    [context],
  );
  if (!context) return null;
  if (!marketNodes.length) {
    return (
      <div className="fr-entity-context">
        <p>No structural market context is available for this bounded graph page.</p>
      </div>
    );
  }
  const effectiveMarketId = marketNodes.some((node) => node.market_ids.includes(selectedMarketId))
    ? selectedMarketId
    : (marketNodes[0].market_ids[0] ?? '');
  const selectedMarket = marketNodes.find((node) => node.market_ids.includes(effectiveMarketId));
  const marketLinks = context.links
    .filter((link) => link.source_market_id === effectiveMarketId)
    .slice(0, 100);
  const kindLabel = (kind: string) => kind.replaceAll('_', ' ');

  return (
    <details className="fr-entity-context">
      <summary>
        Source structure and asset context · {context.represented_market_count} recorded markets
      </summary>
      <div className="fr-entity-context-body">
        <p>
          Structural links come from normalized source metadata. They do not certify event
          equivalence, payoff equivalence, a hedge, or an executable opportunity.
        </p>
        <label>
          <span>Inspect a market’s source structure</span>
          <select
            aria-label="Structural context market"
            value={effectiveMarketId}
            onChange={(event) => setSelectedMarketId(event.target.value)}
          >
            {marketNodes.map((node) => {
              const marketId = node.market_ids[0] ?? '';
              return (
                <option key={node.entity_id} value={marketId}>
                  {node.venue ? `${venueLabel(node.venue)} · ` : ''}
                  {node.label}
                  {node.label_truncated ? '…' : ''}
                </option>
              );
            })}
          </select>
        </label>
        <div className="fr-entity-context-summary">
          <span>
            {context.nodes.length} typed entities · {context.links.length} metadata links
          </span>
          <span>
            {selectedMarket?.record_available
              ? 'Market record available'
              : 'Market record unavailable'}
            {selectedMarket?.native_id ? ` · ${selectedMarket.native_id}` : ''}
          </span>
        </div>
        {selectedMarket?.record_available && (
          <div className="fr-entity-context-market-facts">
            <span>
              Resolution authority: {selectedMarket.resolution_authority ?? 'not supplied'}
            </span>
            <span>
              Closes:{' '}
              {selectedMarket.resolution_closes_at_utc
                ? time(selectedMarket.resolution_closes_at_utc)
                : 'not supplied'}
              {' · '}settles:{' '}
              {selectedMarket.resolution_settles_at_utc
                ? time(selectedMarket.resolution_settles_at_utc)
                : 'not supplied'}
            </span>
            <span>
              Payoff states: {selectedMarket.payoff_state_ids.join(', ') || 'not supplied'}
              {selectedMarket.payoff_state_ids_truncated ? '… (graph display clipped)' : ''}
              {' · '}exhaustive:{' '}
              {selectedMarket.payoff_exhaustive == null
                ? 'unknown'
                : selectedMarket.payoff_exhaustive
                  ? 'source says yes'
                  : 'source says no'}
              {' · '}verified:{' '}
              {selectedMarket.payoff_verified == null
                ? 'unknown'
                : selectedMarket.payoff_verified
                  ? 'source says yes'
                  : 'source says no'}
            </span>
            {selectedMarket.resolution_primary_rule && (
              <span>Primary resolution rule: {selectedMarket.resolution_primary_rule}</span>
            )}
            {selectedMarket.resolution_secondary_rule && (
              <span>Secondary resolution rule: {selectedMarket.resolution_secondary_rule}</span>
            )}
          </div>
        )}
        {context.truncated && (
          <div className="fr-entity-context-warning" role="status">
            Structural context is bounded; omitted detail: {context.truncation_reasons.join(', ')}.
          </div>
        )}
        {marketLinks.length ? (
          <ul className="fr-entity-context-links">
            {marketLinks.map((link) => {
              const source = marketByEntityId.get(link.source_entity_id);
              const target = marketByEntityId.get(link.target_entity_id);
              return (
                <li key={link.link_id}>
                  <strong>
                    {source
                      ? `${kindLabel(source.kind)}: ${source.label}${source.label_truncated ? '…' : ''}`
                      : 'Source entity'}
                    <span> — {kindLabel(link.link_type)} → </span>
                    {target
                      ? `${kindLabel(target.kind)}: ${target.label}${target.label_truncated ? '…' : ''}`
                      : 'Unavailable entity'}
                  </strong>
                  <code>
                    {link.source_field}
                    {target?.native_id
                      ? ` · native ${target.native_id}${target.native_id_truncated ? '…' : ''}`
                      : ''}
                    {target?.quantity_unit ? ` · quantity ${target.quantity_unit}` : ''}
                    {target?.outcome_id
                      ? ` · outcome ${target.outcome_id}${target.outcome_id_truncated ? '…' : ''}`
                      : ''}
                    {target?.value ? ` · value ${target.value}` : ''}
                  </code>
                  <small>Source observation: {link.source_observation_id ?? 'not attached'}</small>
                </li>
              );
            })}
          </ul>
        ) : (
          <p>No structural links were recorded for this market.</p>
        )}
        {context.source_market_count > context.represented_market_count && (
          <small>
            {context.source_market_count - context.represented_market_count} graph markets lack a
            normalized market record in the loaded source window.
          </small>
        )}
        {context.limitations.map((limitation) => (
          <small key={limitation}>{limitation}</small>
        ))}
      </div>
    </details>
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
  const [historyOpen, setHistoryOpen] = useState(false);
  const [decision, setDecision] = useState<'rejected' | 'ambiguous' | 'verified'>('ambiguous');
  const [relationshipType, setRelationshipType] = useState<'same_payoff' | 'logical_implication'>(
    relationship.relationship_type === 'logical_implication'
      ? 'logical_implication'
      : 'same_payoff',
  );
  const [implicationDirection, setImplicationDirection] = useState<
    'left_to_right' | 'right_to_left'
  >('left_to_right');
  const [reviewer, setReviewer] = useState('');
  const [reason, setReason] = useState('');
  const [assertion, setAssertion] = useState('');
  const [stateMapping, setStateMapping] = useState('');
  const [instrumentMapping, setInstrumentMapping] = useState('');
  const queryClient = useQueryClient();
  const reviewHistory = useInfiniteQuery({
    queryKey: ['frontier', 'relationship-review-history', reviewTargetId],
    initialPageParam: null as string | null,
    queryFn: ({ pageParam }) =>
      api<RelationshipReviewHistoryPage>(
        `/frontier/relationships/${reviewTargetId}/reviews?limit=20${
          pageParam ? `&cursor=${encodeURIComponent(pageParam)}` : ''
        }`,
      ),
    getNextPageParam: (page) => page.next_cursor ?? undefined,
    enabled: historyOpen,
  });
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
  const logicalImplicationReady = Boolean(
    evidenceReady &&
    [left, right].every(
      (market) =>
        market?.market_kind === 'binary_event' &&
        market.payoff.verified &&
        market.payoff.exhaustive &&
        market.payoff.state_ids.length > 0 &&
        market.payoff.state_ids.length <= 1024 &&
        market.payoff.state_ids.every((stateId) => stateId.length <= 128) &&
        market.resolution.verified &&
        market.instruments.filter((instrument) => instrument.outcome_id === 'yes').length === 1 &&
        market.instruments.filter((instrument) => instrument.outcome_id === 'no').length === 1,
    ),
  );
  const review = useMutation({
    mutationFn: async () => {
      const parseMapping = (value: string, title: string) => {
        if (!value.trim()) return {};
        const parsed: unknown = JSON.parse(value);
        if (
          !parsed ||
          typeof parsed !== 'object' ||
          Array.isArray(parsed) ||
          Object.entries(parsed).some(
            ([key, target]) => !key.trim() || typeof target !== 'string' || !target.trim(),
          )
        )
          throw new Error(`${title} must be a JSON object with nonblank string identifiers`);
        return parsed as Record<string, string>;
      };
      return api(`/frontier/relationships/${reviewTargetId}/review`, {
        method: 'POST',
        body: JSON.stringify({
          decision,
          relationship_type: relationshipType,
          reviewer_label: reviewer,
          reason,
          evidence_observation_ids: evidenceIds,
          external_assertion_id: decision === 'verified' ? assertion : undefined,
          state_mapping: decision === 'verified' ? parseMapping(stateMapping, 'State mapping') : {},
          instrument_mapping:
            decision === 'verified' && relationshipType === 'same_payoff'
              ? parseMapping(instrumentMapping, 'Instrument mapping')
              : {},
          implication_from_market_id:
            decision === 'verified' && relationshipType === 'logical_implication'
              ? implicationDirection === 'left_to_right'
                ? left?.canonical_id
                : right?.canonical_id
              : undefined,
          implication_to_market_id:
            decision === 'verified' && relationshipType === 'logical_implication'
              ? implicationDirection === 'left_to_right'
                ? right?.canonical_id
                : left?.canonical_id
              : undefined,
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
        <>
          <div className="fr-review-history">
            <StateBadge state={relationship.latest_review.decision} />
            <span>
              Reviewed by self-attributed label “{relationship.latest_review.reviewer_label}” ·{' '}
              {time(relationship.latest_review.created_at_utc)}
            </span>
            <p>{relationship.latest_review.reason}</p>
          </div>
          <button
            className="fr-inspect-button"
            type="button"
            aria-expanded={historyOpen}
            onClick={() => setHistoryOpen((value) => !value)}
          >
            {historyOpen ? 'Hide review history' : 'View review history'}
          </button>
          {historyOpen && (
            <section className="fr-review-archive" aria-label="Relationship review history">
              {reviewHistory.isPending && <p>Loading stored review history…</p>}
              {reviewHistory.isError && (
                <p role="alert">Could not load review history: {reviewHistory.error.message}</p>
              )}
              {reviewHistory.data && (
                <>
                  <small>
                    {reviewHistory.data.pages[0]?.total ?? 0} append-only review record(s). Reviewer
                    labels and assertion IDs are references, not authenticated identities.
                  </small>
                  {reviewHistory.data.pages
                    .flatMap((page) => page.items)
                    .map((item) => (
                      <article className="fr-review-record" key={item.review_id}>
                        <div>
                          <StateBadge state={item.decision} />
                          <span>
                            Self-attributed label “{item.reviewer_label}” ·{' '}
                            {time(item.created_at_utc)}
                          </span>
                        </div>
                        <p>{item.reason}</p>
                        <small>
                          Evidence:{' '}
                          {item.evidence_observation_ids.map(shortHash).join(', ') || 'none'}
                          {' · '}assertion reference: {item.external_assertion_id ?? 'none'}
                          {' · '}record: {shortHash(item.review_id)}
                        </small>
                        {item.supersedes_review_id && (
                          <small>Supersedes review {shortHash(item.supersedes_review_id)}</small>
                        )}
                      </article>
                    ))}
                  {reviewHistory.hasNextPage && (
                    <button
                      className="fr-inspect-button"
                      type="button"
                      disabled={reviewHistory.isFetchingNextPage}
                      onClick={() => void reviewHistory.fetchNextPage()}
                    >
                      {reviewHistory.isFetchingNextPage
                        ? 'Loading older reviews…'
                        : 'Load older reviews'}
                    </button>
                  )}
                </>
              )}
            </section>
          )}
        </>
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
              <option value="verified">Verify relationship</option>
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
                Relationship claim
                <select
                  aria-label="Relationship claim"
                  value={relationshipType}
                  onChange={(event) =>
                    setRelationshipType(event.target.value as typeof relationshipType)
                  }
                >
                  <option value="same_payoff">Equivalent payoff</option>
                  <option value="logical_implication" disabled={!logicalImplicationReady}>
                    Directed YES implication
                    {!logicalImplicationReady ? ' · requirements not met' : ''}
                  </option>
                </select>
              </label>
              <label>
                External assertion ID (reference only)
                <input
                  value={assertion}
                  onChange={(event) => setAssertion(event.target.value)}
                  maxLength={120}
                  required
                />
              </label>
              <label>
                Complete state mapping (left to right JSON)
                <textarea
                  value={stateMapping}
                  onChange={(event) => setStateMapping(event.target.value)}
                  placeholder={'{"left-state":"right-state"}'}
                  required
                />
              </label>
              {relationshipType === 'same_payoff' ? (
                <>
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
                    authorities, and settlement timing against stored market fields. It does not
                    verify the source truth of those fields or the assertion ID.
                  </p>
                </>
              ) : (
                <>
                  <label>
                    YES implication direction
                    <select
                      aria-label="YES implication direction"
                      value={implicationDirection}
                      onChange={(event) =>
                        setImplicationDirection(event.target.value as typeof implicationDirection)
                      }
                    >
                      <option value="left_to_right">
                        {left?.title ?? 'Left market'} YES implies {right?.title ?? 'right market'}{' '}
                        YES
                      </option>
                      <option value="right_to_left">
                        {right?.title ?? 'Right market'} YES implies {left?.title ?? 'left market'}{' '}
                        YES
                      </option>
                    </select>
                  </label>
                  <p className="fr-review-verifier-note">
                    The verifier checks the directed payout inequality over the supplied state
                    mapping. It does not authenticate that the mapping describes the same real-world
                    event or verify the assertion ID. Both source market records are pinned as
                    evidence; incompatible settlement terms are rejected by replay.
                  </p>
                </>
              )}
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
  const [graphSearch, setGraphSearch] = useState('');
  const [selectedMarketId, setSelectedMarketId] = useState<string | null>(null);
  const [selectedRelationshipId, setSelectedRelationshipId] = useState<string | null>(null);
  const [openContractComparisonId, setOpenContractComparisonId] = useState<string | null>(null);
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
  const [latestCollectionResult, setLatestCollectionResult] =
    useState<FiniteCollectionResponse | null>(null);
  const [slippage, setSlippage] = useState('25');
  const [delay, setDelay] = useState('500');
  const [additionalVenueDelay, setAdditionalVenueDelay] = useState<Partial<Record<Venue, string>>>(
    {},
  );
  const [fillPercent, setFillPercent] = useState('80');
  const [selectedArenaReplayId, setSelectedArenaReplayId] = useState<string | null>(null);
  const [selectedPriceHistoryReplayId, setSelectedPriceHistoryReplayId] = useState<string | null>(
    null,
  );
  const [selectedPriceHistoryObservationIds, setSelectedPriceHistoryObservationIds] = useState<
    string[]
  >([]);
  const [priceHistorySourceOffset, setPriceHistorySourceOffset] = useState(0);
  const [priceHistoryReplayOffset, setPriceHistoryReplayOffset] = useState(0);
  const [selectedArenaDiscoveryId, setSelectedArenaDiscoveryId] = useState<string | null>(null);
  const [selectedTimelineJobId, setSelectedTimelineJobId] = useState<string | null>(null);
  const [timelineMaxBookAgeMs, setTimelineMaxBookAgeMs] = useState('15000');
  const [selectedSourceHealthDigests, setSelectedSourceHealthDigests] = useState<string[]>([]);
  const [jointMarketIds, setJointMarketIds] = useState<string[]>([]);
  const [jointStateLabels, setJointStateLabels] = useState('');
  const [jointAssertionId, setJointAssertionId] = useState('');
  const [jointAssertedAt, setJointAssertedAt] = useState(() => {
    const now = new Date();
    return new Date(now.getTime() - now.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
  });
  const [jointProjection, setJointProjection] = useState<Record<string, Record<string, string>>>(
    {},
  );
  const [jointStateReplayResult, setJointStateReplayResult] =
    useState<JointStateReplayResult | null>(null);
  const [collectionRunsBeforeRunId, setCollectionRunsBeforeRunId] = useState<string | null>(null);
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
  const coverageAnalytics = useQuery({
    queryKey: ['frontier', 'coverage-analytics'],
    queryFn: () => api<CoverageAnalytics>('/frontier/analytics/coverage'),
    enabled: section === 'coverage',
    ...options,
  });
  const sources = useQuery({
    queryKey: ['frontier', 'sources'],
    queryFn: () => api<SourceInventory>('/frontier/sources'),
    ...options,
  });
  const collectionRuns = useQuery({
    queryKey: ['frontier', 'collection-runs', collectionRunsBeforeRunId],
    queryFn: () =>
      api<CollectionRunsResponse>(
        `/frontier/collection-runs?limit=20${
          collectionRunsBeforeRunId
            ? `&before_run_id=${encodeURIComponent(collectionRunsBeforeRunId)}`
            : ''
        }`,
      ),
    enabled: section === 'sources',
    ...options,
  });
  const markets = useQuery({
    queryKey: ['frontier', 'markets'],
    queryFn: () => api<ListResponse<Market>>('/frontier/markets?limit=100'),
    ...options,
  });
  const jointMarketOptions = (markets.data?.items ?? []).filter(
    (market) =>
      ['binary_event', 'multi_outcome_event'].includes(market.market_kind) &&
      market.lifecycle === 'open' &&
      market.payoff.verified &&
      market.payoff.exhaustive &&
      market.resolution.verified &&
      market.payoff.state_ids.length >= 2 &&
      /^[0-9a-f]{64}$/.test(market.source_observation_record_id),
  );
  const selectedJointMarkets = jointMarketIds
    .map((marketId) => jointMarketOptions.find((market) => market.canonical_id === marketId))
    .filter((market): market is Market => market != null)
    .sort((left, right) => left.canonical_id.localeCompare(right.canonical_id));
  const jointStateIds = [...new Set(jointStateLabels.split(/\r?\n/).map((id) => id.trim()))]
    .filter(Boolean)
    .sort();
  const jointProjectionComplete =
    jointMarketIds.length >= 2 &&
    jointMarketIds.length <= 4 &&
    selectedJointMarkets.length === jointMarketIds.length &&
    jointStateIds.length >= 2 &&
    jointStateIds.length <= 64 &&
    jointAssertionId.trim().length > 0 &&
    jointAssertionId.trim().length <= 120 &&
    Number.isFinite(Date.parse(jointAssertedAt)) &&
    selectedJointMarkets.every((market) =>
      jointStateIds.every((stateId) =>
        market.payoff.state_ids.includes(jointProjection[market.canonical_id]?.[stateId] ?? ''),
      ),
    ) &&
    jointStateIds.every((stateId) => stateId.length <= 128) &&
    new Set(
      jointStateLabels
        .split(/\r?\n/)
        .map((id) => id.trim())
        .filter(Boolean),
    ).size === jointStateIds.length;
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
  const includeEntityContext = section === 'relationships';
  const graph = useQuery({
    queryKey: [
      'frontier',
      'graph',
      graphCenterMarketId,
      graphSearch.trim(),
      graphDepth,
      graphPageSize,
      graphCursor,
      graphQuerySession,
      includeEntityContext,
    ],
    queryFn: () => {
      const params = new URLSearchParams({
        depth: String(graphDepth),
        limit: String(graphPageSize),
        include_entity_context: String(includeEntityContext),
      });
      if (graphCenterMarketId) params.set('center_market_id', graphCenterMarketId);
      if (graphSearch.trim()) params.set('q', graphSearch.trim());
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
  const savedPriceHistorySources = useQuery({
    queryKey: ['frontier', 'saved-price-history-sources', priceHistorySourceOffset],
    queryFn: () =>
      api<PriceHistoryResponse>(
        `/frontier/price-history?venue=polymarket&limit=20&offset=${priceHistorySourceOffset}`,
      ),
    enabled: section === 'replay',
    ...options,
  });
  const savedPriceHistoryReplays = useQuery({
    queryKey: ['frontier', 'saved-price-history-replays', priceHistoryReplayOffset],
    queryFn: () =>
      api<PriceHistoryReplayListResponse>(
        `/frontier/price-history/replays?limit=20&offset=${priceHistoryReplayOffset}`,
      ),
    enabled: section === 'replay',
    ...options,
  });
  const listedPriceHistoryReplays = savedPriceHistoryReplays.data?.items ?? [];
  const selectedPriceHistoryReplay = selectedPriceHistoryReplayId
    ? (listedPriceHistoryReplays.find((run) => run.run_id === selectedPriceHistoryReplayId) ?? null)
    : (listedPriceHistoryReplays[0] ?? null);
  const priceHistoryReplayDetail = useQuery({
    queryKey: ['frontier', 'price-history-replay-detail', selectedPriceHistoryReplay?.run_id],
    queryFn: () =>
      api<PriceHistoryReplayResult>(
        `/frontier/price-history/replays/${encodeURIComponent(selectedPriceHistoryReplay!.run_id)}`,
      ),
    enabled: section === 'replay' && selectedPriceHistoryReplay != null,
    retry: false,
  });
  const listedPriceHistorySources = savedPriceHistorySources.data?.items ?? [];
  const selectedPriceHistorySources = selectedPriceHistoryObservationIds
    .map((observationId) =>
      listedPriceHistorySources.find((item) => item.observation_id === observationId),
    )
    .filter((item): item is PriceHistoryResponse['items'][number] => item != null);
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
  const arenaDiscoveryJobs = useQuery({
    queryKey: ['frontier', 'arena-discovery-jobs'],
    queryFn: () =>
      api<FrontierArenaDiscoveryJobs>('/arena/frontier-discovery-comparisons?limit=20'),
    enabled: section === 'replay',
    refetchInterval: (query) =>
      query.state.data?.items.some((job) => ['QUEUED', 'RUNNING'].includes(job.state))
        ? 2000
        : false,
  });
  const listedArenaDiscoveryJobs = arenaDiscoveryJobs.data?.items ?? [];
  const selectedArenaDiscoveryJob =
    listedArenaDiscoveryJobs.find((job) => job.job_id === selectedArenaDiscoveryId) ??
    listedArenaDiscoveryJobs[0] ??
    null;
  const arenaDiscoveryResult = useQuery({
    queryKey: ['frontier', 'arena-discovery-result', selectedArenaDiscoveryJob?.job_id],
    queryFn: () =>
      api<FrontierArenaDiscoveryResult>(
        `/arena/jobs/${encodeURIComponent(selectedArenaDiscoveryJob!.job_id)}/frontier-discovery`,
      ),
    enabled: section === 'replay' && selectedArenaDiscoveryJob?.state === 'COMPLETED',
    retry: false,
  });
  const timelineJobs = useQuery({
    queryKey: ['frontier', 'arena-timeline-jobs'],
    queryFn: () => api<FrontierTimelineJobs>('/arena/frontier-timelines?limit=20'),
    enabled: section === 'replay',
    refetchInterval: (query) =>
      query.state.data?.items.some((job) => ['QUEUED', 'RUNNING'].includes(job.state))
        ? 2000
        : false,
  });
  const recordedSourceHealth = useQuery({
    queryKey: ['frontier', 'collection-health-events'],
    queryFn: () => api<RecordedSourceHealthCatalog>('/frontier/collection-health-events?limit=20'),
    enabled: section === 'replay',
    ...options,
  });
  const listedTimelineJobs = timelineJobs.data?.items ?? [];
  const selectedTimelineJob =
    listedTimelineJobs.find((job) => job.job_id === selectedTimelineJobId) ??
    listedTimelineJobs[0] ??
    null;
  const timelineResult = useQuery({
    queryKey: ['frontier', 'arena-timeline-result', selectedTimelineJob?.job_id],
    queryFn: () =>
      api<FrontierTimelineResult>(
        `/arena/jobs/${encodeURIComponent(selectedTimelineJob!.job_id)}/frontier-timeline`,
      ),
    enabled: section === 'replay' && selectedTimelineJob?.state === 'COMPLETED',
    retry: false,
  });
  const parsedTimelineMaxBookAgeMs = Number(timelineMaxBookAgeMs);
  const timelineFreshnessValid =
    Number.isInteger(parsedTimelineMaxBookAgeMs) &&
    parsedTimelineMaxBookAgeMs >= 1 &&
    parsedTimelineMaxBookAgeMs <= 3_600_000;
  const recordedSourceHealthItems = recordedSourceHealth.data?.items ?? [];
  const selectedSourceHealthEvents = recordedSourceHealthItems
    .filter((item) => selectedSourceHealthDigests.includes(item.event.evidence_observation_id))
    .map((item) => item.event);

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
  const marketMetadataProbeEnabledFor = (venue: Venue) =>
    (venue === 'polymarket' || venue === 'kalshi') &&
    (sources.data?.items ?? []).some(
      (source) =>
        source.venue === venue &&
        source.public_probe_enabled &&
        source.capabilities.some(
          (capability) => capability.capability === 'market_metadata' && capability.supported,
        ),
    );
  const polymarketPriceHistoryProbeEnabled = (sources.data?.items ?? []).some(
    (source) =>
      source.venue === 'polymarket' &&
      source.public_probe_enabled &&
      !source.probe_policy_block_reason &&
      source.capabilities.some(
        (capability) => capability.capability === 'price_history' && capability.supported,
      ),
  );
  const polymarketBookUpdatesSource = (sources.data?.items ?? []).find(
    (source) => source.venue === 'polymarket',
  );
  const polymarketBookUpdatesProbeEnabled = Boolean(
    polymarketBookUpdatesSource?.public_probe_enabled &&
    !polymarketBookUpdatesSource.probe_policy_block_reason &&
    polymarketBookUpdatesSource.capabilities.some(
      (capability) => capability.capability === 'book_updates' && capability.supported,
    ),
  );
  const polymarketBookUpdatesReplayEnabled = Boolean(
    sources.data && !polymarketBookUpdatesSource?.probe_policy_block_reason,
  );
  const krakenBookUpdatesSource = (sources.data?.items ?? []).find(
    (source) => source.venue === 'kraken',
  );
  const krakenBookUpdatesProbeEnabled = Boolean(
    krakenBookUpdatesSource?.public_probe_enabled &&
    !krakenBookUpdatesSource.probe_policy_block_reason &&
    krakenBookUpdatesSource.capabilities.some(
      (capability) => capability.capability === 'book_updates' && capability.supported,
    ),
  );
  const krakenCandleSource = (sources.data?.items ?? []).find(
    (source) => source.venue === 'kraken',
  );
  const krakenCandleProbeEnabled = Boolean(
    krakenCandleSource?.public_probe_enabled &&
    !krakenCandleSource.probe_policy_block_reason &&
    krakenCandleSource.capabilities.some(
      (capability) => capability.capability === 'historical_candles' && capability.supported,
    ),
  );

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['frontier'] });
  const replaySavedPriceHistory = useMutation({
    mutationFn: (observationIds: string[]) =>
      api<PriceHistoryReplayResult>('/frontier/price-history/replay', {
        method: 'POST',
        body: JSON.stringify({ observation_ids: observationIds }),
      }),
    onSuccess: (result) => {
      setSelectedPriceHistoryReplayId(result.run_id);
      setPriceHistoryReplayOffset(0);
      queryClient.setQueryData(['frontier', 'price-history-replay-detail', result.run_id], result);
      void queryClient.invalidateQueries({ queryKey: ['frontier', 'saved-price-history-replays'] });
    },
  });
  const jointStateReplay = useMutation({
    mutationFn: () =>
      api<JointStateReplayResult>('/frontier/replay/joint-state', {
        method: 'POST',
        body: JSON.stringify({
          mapping: {
            external_assertion_id: jointAssertionId.trim(),
            market_ids: selectedJointMarkets.map((market) => market.canonical_id),
            joint_state_ids: jointStateIds,
            state_by_market: Object.fromEntries(
              selectedJointMarkets.map((market) => [
                market.canonical_id,
                Object.fromEntries(
                  jointStateIds.map((stateId) => [
                    stateId,
                    jointProjection[market.canonical_id]?.[stateId] ?? '',
                  ]),
                ),
              ]),
            ),
            evidence_observation_ids: selectedJointMarkets
              .map((market) => market.source_observation_record_id)
              .sort(),
            asserted_at_utc: new Date(jointAssertedAt).toISOString(),
            semantic_status: 'externally_asserted_unverified',
          },
          scenario: {
            name: 'external-joint-state-conditional',
            slippage_bps: slippage,
            execution_delay_ms: Number(delay),
            additional_execution_delay_ms_by_venue: additionalExecutionDelayPayload,
            fill_fraction: (Number(fillPercent) / 100).toFixed(4),
            quote_decay_bps_per_second: '15',
          },
        }),
      }),
    onMutate: () => setJointStateReplayResult(null),
    onSuccess: (result) => {
      setJointStateReplayResult(result);
      void Promise.all(
        ['overview', 'opportunities', 'readiness', 'runs'].map((key) =>
          queryClient.invalidateQueries({ queryKey: ['frontier', key] }),
        ),
      );
    },
  });
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
            additional_execution_delay_ms_by_venue: additionalExecutionDelayPayload,
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
                additional_execution_delay_ms_by_venue: additionalExecutionDelayPayload,
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
              additional_execution_delay_ms_by_venue: additionalExecutionDelayPayload,
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
  const arenaDiscovery = useMutation({
    mutationFn: () =>
      api<{
        job_id: string;
        state: string;
        created_at: number | null;
        updated_at: number | null;
        elapsed_seconds?: number | null;
        progress: FrontierArenaDiscoveryJob['progress'];
        phase?: string | null;
        error?: string | null;
        runtime_profile?: FrontierArenaDiscoveryJob['runtime_profile'];
        result: FrontierArenaDiscoveryJob['result'];
        frontier_snapshot_id: string;
        frontier_snapshot_sha256: string;
      }>('/frontier/arena-discovery-comparison', {
        method: 'POST',
        body: JSON.stringify({
          relationship_limit: 500,
          scenario: { name: 'quoted baseline' },
        }),
      }),
    onSuccess: (job) => {
      const summary: FrontierArenaDiscoveryJob = {
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
      setSelectedArenaDiscoveryId(job.job_id);
      queryClient.setQueryData<FrontierArenaDiscoveryJobs>(
        ['frontier', 'arena-discovery-jobs'],
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
      void queryClient.invalidateQueries({ queryKey: ['frontier', 'arena-discovery-jobs'] });
    },
  });
  const timelineReplay = useMutation({
    mutationFn: () =>
      api<{
        job_id: string;
        state: string;
        created_at: number | null;
        updated_at: number | null;
        elapsed_seconds?: number | null;
        progress: FrontierTimelineJob['progress'];
        phase?: string | null;
        error?: string | null;
        runtime_profile?: FrontierTimelineJob['runtime_profile'];
        result: FrontierTimelineJob['result'];
        frontier_snapshot_id: string;
        frontier_snapshot_sha256: string;
        timeline_frame_policy: string;
      }>('/frontier/arena-timeline-replay', {
        method: 'POST',
        body: JSON.stringify({
          max_book_age_ms: parsedTimelineMaxBookAgeMs,
          ...(selectedSourceHealthEvents.length > 0
            ? { source_status_events: selectedSourceHealthEvents }
            : {}),
        }),
      }),
    onSuccess: (job) => {
      const summary: FrontierTimelineJob = {
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
      setSelectedTimelineJobId(job.job_id);
      queryClient.setQueryData<FrontierTimelineJobs>(
        ['frontier', 'arena-timeline-jobs'],
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
      void queryClient.invalidateQueries({ queryKey: ['frontier', 'arena-timeline-jobs'] });
    },
  });
  const probe = useMutation({
    mutationFn: ({ venue, includeOneBook }: { venue: Venue; includeOneBook: boolean }) =>
      api('/frontier/probe/' + venue, {
        method: 'POST',
        body: JSON.stringify({
          limit:
            venue === 'kraken' || venue === 'coinbase_exchange' || venue === 'gemini_spot' ? 1 : 10,
          include_one_book: includeOneBook,
          include_recent_trades: true,
          trade_limit: 10,
        }),
      }),
    onSuccess: refresh,
  });
  const finiteCollection = useMutation({
    mutationFn: ({ venue, includePublicTrades }: { venue: Venue; includePublicTrades: boolean }) =>
      api<FiniteCollectionResponse>('/frontier/collect/' + venue, {
        method: 'POST',
        body: JSON.stringify({
          market_limit: 3,
          book_limit: 1,
          book_depth: 5,
          trade_market_limit: includePublicTrades ? 1 : 0,
          trade_limit_per_market: 10,
          max_wall_seconds: 30,
        }),
      }),
    onSuccess: (result) => {
      setLatestCollectionResult(result);
      setCollectionRunsBeforeRunId(null);
      refresh();
    },
  });
  const resumeCollection = useMutation({
    mutationFn: ({ venue, runId }: { venue: Venue; runId: string }) =>
      api<FiniteCollectionResponse>(
        `/frontier/collect/${venue}/${encodeURIComponent(runId)}/resume`,
        { method: 'POST' },
      ),
    onSuccess: (result) => {
      setLatestCollectionResult(result);
      setCollectionRunsBeforeRunId(null);
      refresh();
    },
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
  const captureMarketMetadata = useMutation({
    mutationFn: ({ marketId, venue }: { marketId: string; venue: 'polymarket' | 'kalshi' }) =>
      api<MarketMetadataCaptureResult>(`/frontier/probe/${venue}/market-metadata`, {
        method: 'POST',
        body: JSON.stringify({ market_id: marketId }),
      }),
    onSuccess: refresh,
  });
  const capturePolymarketPriceHistory = useMutation({
    mutationFn: (input: {
      nativeInstrumentId: string;
      interval: '1d' | '1w';
      fidelityMinutes: number;
      startTs: number;
      endTs: number;
    }) =>
      api<PriceHistoryCaptureResult>('/frontier/probe/polymarket/price-history', {
        method: 'POST',
        body: JSON.stringify({
          native_instrument_id: input.nativeInstrumentId,
          interval: input.interval,
          fidelity_minutes: input.fidelityMinutes,
          start_ts: input.startTs,
          end_ts: input.endTs,
        }),
      }),
    onSuccess: refresh,
  });
  const capturePolymarketBookUpdates = useMutation({
    mutationFn: (input: { marketId: string }) =>
      api<PolymarketBookUpdateCaptureResult>('/frontier/probe/polymarket/book-updates', {
        method: 'POST',
        body: JSON.stringify({ market_id: input.marketId }),
      }),
    onSuccess: refresh,
  });
  const replayPolymarketBookUpdates = useMutation({
    mutationFn: (input: { observationIds: string[]; nativeMarketId: string }) =>
      api<PolymarketBookUpdatesReplayResult>('/frontier/replay/polymarket/book-updates', {
        method: 'POST',
        body: JSON.stringify({ observation_ids: input.observationIds }),
      }),
  });
  const captureKrakenBookUpdates = useMutation({
    mutationFn: (input: { marketId: string }) =>
      api<KrakenBookUpdateCaptureResult>('/frontier/probe/kraken/book-updates', {
        method: 'POST',
        body: JSON.stringify({ market_id: input.marketId }),
      }),
    onSuccess: refresh,
  });
  const replayKrakenBookUpdates = useMutation({
    mutationFn: (input: { observationIds: string[] }) =>
      api<KrakenBookCaptureReplay>('/frontier/replay/kraken/book-updates', {
        method: 'POST',
        body: JSON.stringify({ observation_ids: input.observationIds }),
      }),
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
  const executionVenues = useMemo(
    () => [...new Set((sources.data?.items ?? []).map((source) => source.venue))].sort(),
    [sources.data],
  );
  const additionalExecutionDelayPayload = useMemo(() => {
    const payload: Partial<Record<Venue, number>> = {};
    for (const [venue, value] of Object.entries(additionalVenueDelay)) {
      const milliseconds = Number(value);
      if (
        (venue === 'polymarket' ||
          venue === 'kalshi' ||
          venue === 'kraken' ||
          venue === 'coinbase_exchange' ||
          venue === 'gemini_spot') &&
        Number.isInteger(milliseconds) &&
        milliseconds > 0
      ) {
        payload[venue] = milliseconds;
      }
    }
    return payload;
  }, [additionalVenueDelay]);
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
      const needle = graphSearch.trim().toLocaleLowerCase();
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

      {section === 'coverage' && (
        <>
          {coverageAnalytics.isLoading ? (
            <div className="fr-card fr-loading" role="status">
              Summarizing bounded local evidence…
            </div>
          ) : coverageAnalytics.isError ? (
            <section className="fr-card">
              <EmptyState
                title="Coverage analysis unavailable"
                detail={coverageAnalytics.error.message}
              />
            </section>
          ) : coverageAnalytics.data ? (
            <>
              <div className="fr-metrics">
                <Metric
                  title="Distinct recorded markets"
                  value={count(coverageAnalytics.data.samples.distinct_markets)}
                  note={`Up to ${count(coverageAnalytics.data.samples.market_record_limit)} recent market records`}
                  icon={Layers3}
                />
                <Metric
                  title="Structurally valid recorded books"
                  value={count(
                    coverageAnalytics.data.source_quality.reduce(
                      (sum, source) => sum + source.quality_valid_pricing_books,
                      0,
                    ),
                  )}
                  note="Latest joined two-sided, uncrossed, unflagged books with exact quote identity; freshness is reported separately"
                  icon={Radio}
                />
                <Metric
                  title="Independent timing audits"
                  value={count(
                    coverageAnalytics.data.candidate_research.independently_audited_candidates,
                  )}
                  note={`${count(coverageAnalytics.data.candidate_research.audited_timing_verified_candidates)} pass the pinned timing gate`}
                  icon={ShieldCheck}
                />
                <Metric
                  title="Repeated gross-positive constructions"
                  value={count(
                    coverageAnalytics.data.candidate_research
                      .gross_positive_audited_timing_verified_constructions_repeated_across_distinct_books,
                  )}
                  note="Verified candidate signatures across distinct books and replay times; net economics not implied"
                  icon={Activity}
                />
              </div>
              <p className="fr-footnote">
                {coverageAnalytics.data.scope} As of {time(coverageAnalytics.data.as_of_utc)}.
                Candidate records come from at most{' '}
                {count(coverageAnalytics.data.samples.replay_run_limit)} eligible saved runs.
              </p>

              <div className="fr-overview-grid">
                <section className="fr-card">
                  <div className="fr-card-head">
                    <div>
                      <span className="fr-kicker">RECORDED UNIVERSE</span>
                      <h2>Recent market mix</h2>
                    </div>
                    <Layers3 size={17} />
                  </div>
                  {coverageAnalytics.data.market_mix.length ? (
                    <div className="fr-table-wrap">
                      <table className="fr-table">
                        <thead>
                          <tr>
                            <th>Venue</th>
                            <th>Instrument type</th>
                            <th>Markets</th>
                            <th>Instruments</th>
                            <th>Events</th>
                          </tr>
                        </thead>
                        <tbody>
                          {coverageAnalytics.data.market_mix.map((item) => (
                            <tr key={`${item.venue}:${item.market_kind}`}>
                              <td>{label(item.venue)}</td>
                              <td>{label(item.market_kind)}</td>
                              <td>{count(item.market_count)}</td>
                              <td>{count(item.instrument_count)}</td>
                              <td>{count(item.event_count)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <EmptyState
                      title="No eligible market records"
                      detail="The bounded recent market sample has no stored, research-eligible records."
                    />
                  )}
                  <h3>Eligible stored inventory by venue</h3>
                  {coverageAnalytics.data.stored_market_counts_by_venue.length ? (
                    <div className="fr-table-wrap">
                      <table className="fr-table">
                        <thead>
                          <tr>
                            <th>Venue</th>
                            <th>Stored markets</th>
                            <th>Stored instruments</th>
                          </tr>
                        </thead>
                        <tbody>
                          {coverageAnalytics.data.stored_market_counts_by_venue.map((item) => (
                            <tr key={item.venue}>
                              <td>{label(item.venue)}</td>
                              <td>{count(item.market_count)}</td>
                              <td>{count(item.instrument_count)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p className="fr-footnote">No eligible market identities are stored.</p>
                  )}
                </section>

                <section className="fr-card">
                  <div className="fr-card-head">
                    <div>
                      <span className="fr-kicker">RECORDED PRINTS</span>
                      <h2>Public trade capture coverage</h2>
                    </div>
                    <Activity size={17} />
                  </div>
                  {coverageAnalytics.data.samples.public_trade_observation_records > 0 ? (
                    <div className="fr-table-wrap">
                      <table className="fr-table">
                        <thead>
                          <tr>
                            <th>Venue</th>
                            <th>Captures / markets</th>
                            <th>Returned prints</th>
                            <th>Empty / invalid captures</th>
                            <th>Instruments</th>
                            <th>Exchange timestamped / missing</th>
                            <th>Clock bound / missing</th>
                            <th>Future receipt / source time</th>
                            <th>Latest capture / median age</th>
                          </tr>
                        </thead>
                        <tbody>
                          {coverageAnalytics.data.public_trade_quality.map((source) => (
                            <tr key={source.venue}>
                              <td>{label(source.venue)}</td>
                              <td>
                                {count(source.capture_count)} / {count(source.unique_market_count)}
                              </td>
                              <td>{count(source.trade_print_count)}</td>
                              <td>
                                {count(source.empty_capture_count)} /{' '}
                                {count(source.invalid_capture_count)}
                              </td>
                              <td>{count(source.unique_instrument_count)}</td>
                              <td>
                                {count(source.prints_with_exchange_timestamp)} /{' '}
                                {count(source.prints_without_exchange_timestamp)}
                              </td>
                              <td>
                                {count(source.prints_with_clock_uncertainty)} /{' '}
                                {count(source.prints_without_clock_uncertainty)}
                              </td>
                              <td>
                                {count(source.future_capture_timestamp_count)} /{' '}
                                {count(source.future_exchange_timestamp_count)}
                              </td>
                              <td>
                                {source.latest_capture_received_at_utc
                                  ? `${time(source.latest_capture_received_at_utc)} / ${source.median_capture_age_ms == null ? '—' : `${money(source.median_capture_age_ms)} ms`}`
                                  : '—'}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <EmptyState
                      title="No saved public-trade captures"
                      detail="Print counts appear only after a bounded source response has been captured."
                    />
                  )}
                  <p className="fr-footnote">{coverageAnalytics.data.public_trade_quality_scope}</p>
                  {coverageAnalytics.data.samples.invalid_normalized_public_trade_records > 0 && (
                    <p className="fr-footnote">
                      {count(
                        coverageAnalytics.data.samples.invalid_normalized_public_trade_records,
                      )}{' '}
                      saved trade responses failed normalization or capture-lineage checks.
                    </p>
                  )}
                </section>

                <section className="fr-card">
                  <div className="fr-card-head">
                    <div>
                      <span className="fr-kicker">SOURCE QUALITY</span>
                      <h2>Latest instrument books</h2>
                    </div>
                    <Radio size={17} />
                  </div>
                  <div className="fr-table-wrap">
                    <table className="fr-table">
                      <thead>
                        <tr>
                          <th>Venue</th>
                          <th>Sample</th>
                          <th>Price-valid</th>
                          <th>Flagged / crossed</th>
                          <th>Unjoined / bad lineage</th>
                          <th>Future time</th>
                          <th>Exchange time</th>
                          <th>Clock bounds</th>
                          <th>Freshness rule</th>
                          <th>Median age</th>
                        </tr>
                      </thead>
                      <tbody>
                        {coverageAnalytics.data.source_quality.map((source) => (
                          <tr key={source.venue}>
                            <td>{label(source.venue)}</td>
                            <td>{count(source.latest_instrument_books)}</td>
                            <td>{count(source.quality_valid_pricing_books)}</td>
                            <td>
                              {count(source.flagged_books)} / {count(source.crossed_books)}
                            </td>
                            <td>{count(source.unjoined_or_provenance_mismatch_records)}</td>
                            <td>{count(source.future_received_timestamp)}</td>
                            <td>{count(source.with_exchange_timestamp)}</td>
                            <td>{count(source.with_clock_uncertainty)}</td>
                            <td>
                              {count(source.within_declared_freshness_limit)} in /{' '}
                              {count(source.stale_by_declared_freshness_limit)} stale /{' '}
                              {count(source.without_declared_freshness_limit)} unknown
                            </td>
                            <td>
                              {source.median_receipt_age_ms == null
                                ? '—'
                                : `${money(source.median_receipt_age_ms)} ms`}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {coverageAnalytics.data.samples.invalid_normalized_book_records > 0 && (
                    <p className="fr-footnote">
                      {count(coverageAnalytics.data.samples.invalid_normalized_book_records)} stored
                      book records could not be normalized for this summary.
                    </p>
                  )}
                </section>

                <section className="fr-card">
                  <div className="fr-card-head">
                    <div>
                      <span className="fr-kicker">HISTORICAL SOURCE SAMPLES</span>
                      <h2>Price-history capture coverage</h2>
                    </div>
                    <Activity size={17} />
                  </div>
                  {coverageAnalytics.data.samples.price_history_observation_records > 0 ? (
                    <div className="fr-table-wrap">
                      <table className="fr-table">
                        <thead>
                          <tr>
                            <th>Venue</th>
                            <th>Captures / instruments</th>
                            <th>Returned points</th>
                            <th>Empty / unbound</th>
                            <th>Future points</th>
                            <th>Latest capture</th>
                            <th>Largest observed sample gap</th>
                          </tr>
                        </thead>
                        <tbody>
                          {coverageAnalytics.data.historical_price_quality.map((source) => (
                            <tr key={source.venue}>
                              <td>{label(source.venue)}</td>
                              <td>
                                {count(source.capture_count)} /{' '}
                                {count(source.unique_instrument_count)}
                              </td>
                              <td>{count(source.source_point_count)}</td>
                              <td>
                                {count(source.empty_capture_count)} /{' '}
                                {count(source.unbound_capture_count)}
                              </td>
                              <td>{count(source.future_point_timestamp_count)}</td>
                              <td>
                                {source.latest_capture_received_at_utc
                                  ? time(source.latest_capture_received_at_utc)
                                  : '—'}
                              </td>
                              <td>
                                {source.largest_adjacent_sample_gap_seconds == null
                                  ? '—'
                                  : `${count(source.largest_adjacent_sample_gap_seconds)} s`}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <EmptyState
                      title="No saved price-history captures"
                      detail="Historical samples appear only after an explicit bounded public-data capture."
                    />
                  )}
                  <p className="fr-footnote">
                    {coverageAnalytics.data.historical_price_quality_scope} These values describe
                    returned samples, not completeness, executable quotes, or simultaneous venue
                    prices.
                  </p>
                  {coverageAnalytics.data.samples.invalid_normalized_price_history_records > 0 && (
                    <p className="fr-footnote">
                      {count(
                        coverageAnalytics.data.samples.invalid_normalized_price_history_records,
                      )}{' '}
                      saved history records could not be normalized for this summary.
                    </p>
                  )}
                </section>

                <section className="fr-card">
                  <div className="fr-card-head">
                    <div>
                      <span className="fr-kicker">RECORDED QUOTES</span>
                      <h2>Spread and top depth</h2>
                    </div>
                    <BarChart3 size={17} />
                  </div>
                  {coverageAnalytics.data.pricing.length ? (
                    <div className="fr-table-wrap">
                      <table className="fr-table">
                        <thead>
                          <tr>
                            <th>Venue / type</th>
                            <th>Denomination</th>
                            <th>Quantity unit</th>
                            <th>Books</th>
                            <th>Median / p90 spread (bps)</th>
                            <th>Median bid / ask depth</th>
                          </tr>
                        </thead>
                        <tbody>
                          {coverageAnalytics.data.pricing.map((item) => (
                            <tr
                              key={`${item.venue}:${item.market_kind}:${item.quantity_unit}:${item.quote_asset_identity}`}
                            >
                              <td>
                                {label(item.venue)} · {label(item.market_kind)}
                              </td>
                              <td>
                                <code>{item.quote_asset_identity}</code>
                              </td>
                              <td>{label(item.quantity_unit)}</td>
                              <td>{count(item.instrument_count)}</td>
                              <td>
                                {money(item.median_relative_spread_bps)} /{' '}
                                {money(item.p90_relative_spread_bps)}
                              </td>
                              <td>
                                {money(item.median_best_bid_depth)} /{' '}
                                {money(item.median_best_ask_depth)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <EmptyState
                      title="No quality-valid book pairs"
                      detail="Spread summaries require joined market instruments and matching quote-asset identities."
                    />
                  )}
                </section>

                <section className="fr-card">
                  <div className="fr-card-head">
                    <div>
                      <span className="fr-kicker">CANDIDATE REVIEW</span>
                      <h2>Replay classifications and rejection reasons</h2>
                    </div>
                    <GitBranch size={17} />
                  </div>
                  {Object.keys(coverageAnalytics.data.candidate_research.counts_by_classification)
                    .length ? (
                    <div className="fr-table-wrap">
                      <table className="fr-table">
                        <thead>
                          <tr>
                            <th>Classification</th>
                            <th>Replay candidate records</th>
                          </tr>
                        </thead>
                        <tbody>
                          {Object.entries(
                            coverageAnalytics.data.candidate_research.counts_by_classification,
                          ).map(([classification, value]) => (
                            <tr key={classification}>
                              <td>{label(classification)}</td>
                              <td>{count(value)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <EmptyState
                      title="No candidate records in the replay window"
                      detail="No count is inferred from absent or unavailable replay evidence."
                    />
                  )}
                  <h3>Most frequent rejection reasons</h3>
                  {coverageAnalytics.data.candidate_research.rejection_reasons.length ? (
                    <ul className="fr-limitations">
                      {coverageAnalytics.data.candidate_research.rejection_reasons.map((item) => (
                        <li key={item.reason}>
                          <span>{item.reason}</span> <strong>{count(item.count)}</strong>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="fr-footnote">No candidate rejection reasons were recorded.</p>
                  )}
                  <p className="fr-footnote">
                    Audited receipt skew median / p90:{' '}
                    {money(
                      coverageAnalytics.data.candidate_research.median_audited_received_skew_ms,
                    )}{' '}
                    /{' '}
                    {money(coverageAnalytics.data.candidate_research.p90_audited_received_skew_ms)}{' '}
                    ms · exchange timestamp skew median / p90:{' '}
                    {money(
                      coverageAnalytics.data.candidate_research.median_audited_exchange_skew_ms,
                    )}{' '}
                    /{' '}
                    {money(coverageAnalytics.data.candidate_research.p90_audited_exchange_skew_ms)}{' '}
                    ms
                  </p>
                </section>
              </div>
              {coverageAnalytics.data.samples.candidate_scan_truncated && (
                <div className="fr-alert" role="status">
                  Candidate analytics stopped at its bounded record limit; counts are incomplete.
                </div>
              )}
              <section className="fr-card">
                <div className="fr-card-head">
                  <div>
                    <span className="fr-kicker">INTERPRETATION</span>
                    <h2>Sample limits and scientific boundaries</h2>
                  </div>
                  <ShieldCheck size={17} />
                </div>
                <ul className="fr-limitations">
                  {coverageAnalytics.data.limitations.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </section>
            </>
          ) : (
            <section className="fr-card">
              <EmptyState
                title="Coverage analysis unavailable"
                detail="No coverage analytics response was returned."
              />
            </section>
          )}
        </>
      )}

      {section === 'sources' && (
        <SourcesView
          sources={sources.data?.items ?? []}
          operationAdmission={sources.data?.operation_admission}
          refreshSourceStatus={() => sources.refetch()}
          sourceStatusRefreshing={sources.isFetching}
          markets={summary?.markets_by_venue ?? {}}
          probe={probe}
          finiteCollection={finiteCollection}
          collectionRuns={collectionRuns.data}
          collectionRunsLoading={collectionRuns.isFetching}
          collectionRunsError={collectionRuns.error?.message}
          collectionRunsBeforeRunId={collectionRunsBeforeRunId}
          loadOlderCollectionRuns={setCollectionRunsBeforeRunId}
          showNewestCollectionRuns={() => setCollectionRunsBeforeRunId(null)}
          latestCollectionResult={latestCollectionResult}
          resumeCollection={resumeCollection}
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
              marketMetadataProbe={captureMarketMetadata}
              marketMetadataProbeEnabled={marketMetadataProbeEnabledFor(selectedMarket.venue)}
              priceHistoryProbe={capturePolymarketPriceHistory}
              priceHistoryProbeEnabled={polymarketPriceHistoryProbeEnabled}
              bookUpdatesProbe={capturePolymarketBookUpdates}
              bookUpdatesProbeEnabled={polymarketBookUpdatesProbeEnabled}
              bookUpdatesReplay={replayPolymarketBookUpdates}
              bookUpdatesReplayEnabled={polymarketBookUpdatesReplayEnabled}
              bookUpdatesReplayDisabledReason={
                polymarketBookUpdatesSource?.probe_policy_block_reason
              }
              krakenBookUpdatesProbe={captureKrakenBookUpdates}
              krakenBookUpdatesReplay={replayKrakenBookUpdates}
              krakenBookUpdatesProbeEnabled={krakenBookUpdatesProbeEnabled}
              krakenBookUpdatesDisabledReason={krakenBookUpdatesSource?.probe_policy_block_reason}
              krakenCandleProbeEnabled={krakenCandleProbeEnabled}
              krakenCandleDisabledReason={krakenCandleSource?.probe_policy_block_reason}
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
              {captureTradePage.isError && <ProbeFailureEvidence error={captureTradePage.error} />}
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
                      <th>Taker / aggressor</th>
                      <th>Trade type</th>
                      <th>Exchange time (UTC)</th>
                      <th>Received (UTC)</th>
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
                        <td>
                          {trade.taker_outcome_side
                            ? `Taker ${label(trade.taker_outcome_side)}${
                                trade.taker_book_side
                                  ? ` · ${label(trade.taker_book_side)} book`
                                  : ''
                              }`
                            : label(trade.aggressor_side ?? 'unknown')}
                        </td>
                        <td>
                          {trade.is_block_trade == null
                            ? 'Not reported'
                            : trade.is_block_trade
                              ? 'Block trade'
                              : 'Non-block trade'}
                        </td>
                        <td>
                          {trade.exchange_timestamp_utc ? (
                            <time dateTime={trade.exchange_timestamp_utc}>
                              {preciseUtcTime(trade.exchange_timestamp_utc)}
                            </time>
                          ) : (
                            'Not supplied'
                          )}
                        </td>
                        <td>
                          <time dateTime={trade.received_at_utc}>
                            {preciseUtcTime(trade.received_at_utc)}
                          </time>
                        </td>
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
              value={graphSearch}
              onChange={(value) => {
                setGraphSearch(value);
                resetGraphPagination();
              }}
              placeholder="Search recorded market titles or IDs"
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
                  const comparisonOpen = openContractComparisonId === relationship.relationship_id;
                  const termComparison = comparisonOpen
                    ? compareRelationshipTerms(left, right)
                    : null;
                  return (
                    <article className="fr-edge" key={relationship.relationship_id}>
                      <div className="fr-node">
                        <VenuePill venue={left?.venue ?? 'unknown'} />
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
                        <VenuePill venue={right?.venue ?? 'unknown'} />
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
                      <details
                        className="fr-contract-comparison"
                        open={comparisonOpen}
                        onToggle={(event) => {
                          if (event.currentTarget.open) {
                            setOpenContractComparisonId(relationship.relationship_id);
                          } else {
                            setOpenContractComparisonId((current) =>
                              current === relationship.relationship_id ? null : current,
                            );
                          }
                        }}
                      >
                        <summary>Compare recorded contract terms</summary>
                        <p className="fr-contract-comparison-note">
                          Side-by-side captured terms help review this relationship. Similarity
                          labels and this comparison do not establish equivalent payoffs.
                        </p>
                        {termComparison && (
                          <div className="fr-term-difference-summary">
                            <strong>Literal differences in reported fields</strong>
                            {termComparison.available ? (
                              <>
                                <p>
                                  {termComparison.differences.length
                                    ? `${termComparison.differences.length} recorded difference${termComparison.differences.length === 1 ? '' : 's'}`
                                    : 'No literal differences'}{' '}
                                  among comparable fields; {termComparison.unavailableFields}{' '}
                                  comparison
                                  {termComparison.unavailableFields === 1 ? ' is' : 's are'}{' '}
                                  unavailable in one or both captured records. This summary does not
                                  establish equivalent payoffs.
                                </p>
                                {termComparison.differences.length > 0 && (
                                  <dl>
                                    {termComparison.differences.map((difference) => (
                                      <div key={difference.field}>
                                        <dt>{difference.field}</dt>
                                        <dd>
                                          <span>Left: {difference.left}</span>
                                          <span>Right: {difference.right}</span>
                                        </dd>
                                      </div>
                                    ))}
                                  </dl>
                                )}
                              </>
                            ) : (
                              <p>
                                A market record is outside the loaded graph window; cross-source
                                field comparison is unavailable.
                              </p>
                            )}
                          </div>
                        )}
                        {comparisonOpen && (
                          <div className="fr-contract-comparison-grid">
                            <RelationshipContractTerms side="Left" market={left} />
                            <RelationshipContractTerms side="Right" market={right} />
                          </div>
                        )}
                      </details>
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
          {!graph.isLoading && !graph.isError && (
            <EntityContextExplorer context={graph.data?.entity_context} />
          )}
          {(graph.data?.next_cursor ||
            graph.data?.truncated_by_edge_limit ||
            graph.data?.relationship_scan_may_be_incomplete) && (
            <div className="fr-footnote">
              {graph.data.relationship_scan_may_be_incomplete
                ? graph.data.next_cursor && graphSearch.trim()
                  ? `Text search reached the ${graph.data.relationship_scan_limit}-row scan bound. Continue through its captured result window; additional matches may be omitted.`
                  : graph.data.next_cursor && graphCenterMarketId && graphDepth === 1
                    ? `This page reached its ${graph.data.relationship_scan_limit}-row scan bound. Continue with the next page; graph changes invalidate the cursor.`
                    : graph.data.next_cursor && graphCenterMarketId && graphDepth > 1
                      ? `This breadth-first traversal reached its ${graph.data.relationship_scan_limit}-row scan bound. Continue through the captured result window; additional neighbors may still be omitted.`
                      : `This query considered ${graph.data.relationships_scanned} relationship rows, reaching its ${graph.data.relationship_scan_limit}-row scan bound; additional neighbors may be omitted.`
                : graph.data.next_cursor && graphSearch.trim()
                  ? `Text search returned ${graph.data.returned_edges} edges on this page. Continue through the bounded result window; graph changes invalidate the cursor.`
                  : graph.data.next_cursor && graphCenterMarketId && graphDepth === 1
                    ? `This page returned ${graph.data.returned_edges} edges. More neighbors are available through keyset pages; graph changes make the cursor stale.`
                    : graph.data.next_cursor && graphCenterMarketId && graphDepth > 1
                      ? `This page returned ${graph.data.returned_edges} edges in breadth-first order. Continue through the bounded traversal; graph changes make the cursor stale.`
                      : `This view is capped at ${graph.data.edge_limit} edges after considering ${graph.data.relationships_scanned} relationship rows.`}{' '}
              {!graphCenterMarketId &&
                !graphSearch.trim() &&
                'Choose a center market or search recorded markets to inspect relationship edges.'}
            </div>
          )}
          {graph.data && (graphCenterMarketId || graphSearch.trim()) && (
            <div
              className="fr-graph-pagination"
              role="group"
              aria-label={graphSearch.trim() ? 'Relationship search pages' : 'Relationship pages'}
            >
              <button
                className="fr-action"
                disabled={graphPageIndex === 0 || graph.isFetching}
                onClick={() => setGraphPageIndex((current) => Math.max(0, current - 1))}
              >
                Previous page
              </button>
              <span>
                {graphSearch.trim() ? 'Search' : 'Neighborhood'} page {graphPageIndex + 1}
              </span>
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
                {graph.isFetching
                  ? 'Loading…'
                  : graphSearch.trim()
                    ? 'Load more matches'
                    : 'Load more neighbors'}
              </button>
            </div>
          )}
          <div className="fr-footnote">
            The evidence list shows up to 30 edges per page; the network shows the first 18. Similar
            titles never certify payoff equivalence. Relationship identity is versioned and tied to
            pinned observation IDs.
            {graphSearch.trim() && (
              <>
                {' '}
                Text search seeds at most {graph.data?.source_market_window_limit ?? 200} recorded
                markets and remains bounded; it does not represent the full market universe.
              </>
            )}
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
                <CandidateCard
                  key={candidate.candidate_id}
                  candidate={candidate}
                  jointStateMapping={runs.data?.items
                    .find((run) => run.run_id === candidate.source_run_id)
                    ?.result.manifest.joint_state_mappings?.find(
                      (mapping) => mapping.mapping_id === candidate.joint_state_mapping_id,
                    )}
                />
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
              Base execution delay <span>milliseconds · all venues</span>
              <input
                type="number"
                min="0"
                max="3600000"
                step="100"
                value={delay}
                onChange={(event) => setDelay(event.target.value)}
              />
            </label>
            {executionVenues.map((venue) => (
              <label className="fr-field" key={`execution-delay-${venue}`}>
                Additional delay · {venueLabel(venue)} <span>milliseconds · this venue only</span>
                <input
                  type="number"
                  min="0"
                  max={Math.max(0, 3_600_000 - (Number(delay) || 0))}
                  step="100"
                  aria-label={`Additional execution delay for ${venueLabel(venue)}`}
                  value={additionalVenueDelay[venue] ?? '0'}
                  onChange={(event) =>
                    setAdditionalVenueDelay((current) => ({
                      ...current,
                      [venue]: event.target.value,
                    }))
                  }
                />
              </label>
            ))}
            <label className="fr-field">
              Usable top-ask depth <span>percent of displayed depth</span>
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
              <span>Separate full-or-no-fill stress</span>
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
          <FrontierHostResourcePanel />
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
          <section className="fr-card fr-history-replay-card">
            <div className="fr-card-head">
              <div>
                <span className="fr-kicker">SAVED SOURCE PRICE SAMPLES</span>
                <h2>Multi-series descriptive replay</h2>
              </div>
              <Activity size={17} />
            </div>
            <p className="fr-history-replay-intro">
              Select up to eight locally stored Polymarket price-history captures. Replay reads
              immutable records only; it makes no exchange request, generates no opportunity, and
              does not treat historical samples as executable quotes. Selection applies to the
              current page.
            </p>
            <div className="fr-history-replay-layout">
              <section aria-label="Saved price-history replay inputs">
                <div className="fr-subsection-head">
                  <h3>Input series</h3>
                  <span>{selectedPriceHistorySources.length} / 8 selected</span>
                </div>
                {savedPriceHistorySources.isLoading ? (
                  <div className="fr-loading">Reading saved Polymarket price-history captures…</div>
                ) : savedPriceHistorySources.isError ? (
                  <EmptyState
                    title="Saved history unavailable"
                    detail={savedPriceHistorySources.error.message}
                  />
                ) : listedPriceHistorySources.length === 0 ? (
                  <EmptyState
                    title="No saved price-history captures"
                    detail="A capture must already exist in the local Frontier store. This view does not start a source request."
                  />
                ) : (
                  <div className="fr-history-capture-list">
                    {listedPriceHistorySources.map((capture) => {
                      const checked = selectedPriceHistoryObservationIds.includes(
                        capture.observation_id,
                      );
                      return (
                        <label className="fr-history-capture-option" key={capture.observation_id}>
                          <input
                            type="checkbox"
                            checked={checked}
                            disabled={!checked && selectedPriceHistoryObservationIds.length >= 8}
                            onChange={(event) =>
                              setSelectedPriceHistoryObservationIds((current) =>
                                event.target.checked
                                  ? [...current, capture.observation_id]
                                      .filter(
                                        (value, index, values) => values.indexOf(value) === index,
                                      )
                                      .slice(0, 8)
                                  : current.filter((value) => value !== capture.observation_id),
                              )
                            }
                          />
                          <span>
                            <strong>
                              {venueLabel(capture.series.venue)} ·{' '}
                              {capture.series.native_instrument_id} · {capture.series.interval}
                            </strong>
                            <small>
                              {count(capture.series.points.length)} returned points · received{' '}
                              {new Date(capture.received_at_utc).toLocaleString()}
                            </small>
                            <code>{capture.observation_id}</code>
                          </span>
                        </label>
                      );
                    })}
                  </div>
                )}
                {savedPriceHistorySources.data?.scan_may_be_incomplete && (
                  <p className="fr-history-replay-note">
                    The source list is a bounded scan of {savedPriceHistorySources.data.scan_bound}{' '}
                    saved captures; older records may be omitted.
                  </p>
                )}
                <nav className="fr-history-pagination" aria-label="Saved source capture pages">
                  <span>
                    Page {Math.floor(priceHistorySourceOffset / 20) + 1} ·{' '}
                    {savedPriceHistorySources.data?.returned ?? 0} captures
                  </span>
                  <div>
                    <button
                      className="fr-action"
                      type="button"
                      disabled={priceHistorySourceOffset === 0}
                      onClick={() => {
                        setSelectedPriceHistoryObservationIds([]);
                        setPriceHistorySourceOffset((offset) => Math.max(0, offset - 20));
                      }}
                    >
                      Previous
                    </button>
                    <button
                      className="fr-action"
                      type="button"
                      disabled={!savedPriceHistorySources.data?.has_more}
                      onClick={() => {
                        setSelectedPriceHistoryObservationIds([]);
                        setPriceHistorySourceOffset((offset) => offset + 20);
                      }}
                    >
                      Next
                    </button>
                  </div>
                </nav>
                <button
                  className="fr-action fr-run-button"
                  onClick={() =>
                    replaySavedPriceHistory.mutate(
                      selectedPriceHistorySources.map((capture) => capture.observation_id),
                    )
                  }
                  disabled={
                    replaySavedPriceHistory.isPending || selectedPriceHistorySources.length === 0
                  }
                >
                  <Play size={14} />
                  {replaySavedPriceHistory.isPending
                    ? 'Replaying stored samples…'
                    : `Replay ${selectedPriceHistorySources.length} selected series`}
                </button>
                {replaySavedPriceHistory.isError && (
                  <InlineError message={replaySavedPriceHistory.error.message} />
                )}
              </section>
              <section aria-label="Saved price-history replay results">
                <div className="fr-subsection-head">
                  <h3>Saved replay artifacts</h3>
                  <span>20 per page</span>
                </div>
                {savedPriceHistoryReplays.isLoading ? (
                  <div className="fr-loading">Loading saved source-sample replays…</div>
                ) : savedPriceHistoryReplays.isError ? (
                  <EmptyState
                    title="Replay history unavailable"
                    detail={savedPriceHistoryReplays.error.message}
                  />
                ) : listedPriceHistoryReplays.length === 0 ? (
                  <EmptyState
                    title="No saved source-sample replays"
                    detail="Choose saved inputs and run an explicit local replay to create an artifact."
                  />
                ) : (
                  <div className="fr-history-replay-list" aria-label="Saved price-history replays">
                    {listedPriceHistoryReplays.map((run) => (
                      <button
                        key={run.run_id}
                        className={`fr-history-replay-row${run.run_id === selectedPriceHistoryReplay?.run_id ? ' selected' : ''}`}
                        aria-pressed={run.run_id === selectedPriceHistoryReplay?.run_id}
                        onClick={() => setSelectedPriceHistoryReplayId(run.run_id)}
                      >
                        <span>
                          <code>{shortHash(run.run_id)}</code>
                          <small>
                            {run.series.length} source series ·{' '}
                            {new Date(run.manifest.as_of_utc).toLocaleString()}
                          </small>
                        </span>
                        <span className="fr-history-replay-state">descriptive</span>
                      </button>
                    ))}
                  </div>
                )}
                {savedPriceHistoryReplays.data?.scan_may_be_incomplete && (
                  <p className="fr-history-replay-note">
                    Older saved artifacts may be outside this 20-run page.
                  </p>
                )}
                {savedPriceHistoryReplays.data?.held_replays_omitted ? (
                  <p className="fr-history-replay-note">
                    {savedPriceHistoryReplays.data.held_replays_omitted} held-source replay(s) were
                    omitted from this page.
                  </p>
                ) : null}
                <nav className="fr-history-pagination" aria-label="Saved replay artifact pages">
                  <span>
                    Page {Math.floor(priceHistoryReplayOffset / 20) + 1} ·{' '}
                    {savedPriceHistoryReplays.data?.returned ?? 0} artifacts
                  </span>
                  <div>
                    <button
                      className="fr-action"
                      type="button"
                      disabled={priceHistoryReplayOffset === 0}
                      onClick={() => {
                        setSelectedPriceHistoryReplayId(null);
                        setPriceHistoryReplayOffset((offset) => Math.max(0, offset - 20));
                      }}
                    >
                      Previous
                    </button>
                    <button
                      className="fr-action"
                      type="button"
                      disabled={!savedPriceHistoryReplays.data?.has_more}
                      onClick={() => {
                        setSelectedPriceHistoryReplayId(null);
                        setPriceHistoryReplayOffset((offset) => offset + 20);
                      }}
                    >
                      Next
                    </button>
                  </div>
                </nav>
              </section>
            </div>
            {selectedPriceHistoryReplay && (
              <section className="fr-history-replay-detail" aria-label="Selected replay lineage">
                <div className="fr-subsection-head">
                  <div>
                    <span className="fr-kicker">PINNED INPUT AND RESULT</span>
                    <h3>Replay lineage</h3>
                  </div>
                  <span>candidate generation not performed</span>
                </div>
                {priceHistoryReplayDetail.isLoading ? (
                  <div className="fr-loading">Verifying saved replay artifact…</div>
                ) : priceHistoryReplayDetail.isError ? (
                  <InlineError message={priceHistoryReplayDetail.error.message} />
                ) : priceHistoryReplayDetail.data ? (
                  <>
                    <dl className="fr-history-replay-meta">
                      <div>
                        <dt>Run ID</dt>
                        <dd>
                          <code>{priceHistoryReplayDetail.data.run_id}</code>
                        </dd>
                      </div>
                      <div>
                        <dt>Input SHA-256</dt>
                        <dd>
                          <code>{priceHistoryReplayDetail.data.manifest.input_sha256}</code>
                        </dd>
                      </div>
                      <div>
                        <dt>Result SHA-256</dt>
                        <dd>
                          <code>{priceHistoryReplayDetail.data.result_sha256}</code>
                        </dd>
                      </div>
                      <div>
                        <dt>Replay and code version</dt>
                        <dd>
                          {priceHistoryReplayDetail.data.manifest.replay_version} ·{' '}
                          {priceHistoryReplayDetail.data.manifest.code_version}
                        </dd>
                      </div>
                      <div>
                        <dt>Latest input receipt time</dt>
                        <dd>
                          {new Date(
                            priceHistoryReplayDetail.data.manifest.as_of_utc,
                          ).toLocaleString()}
                        </dd>
                      </div>
                    </dl>
                    <div className="fr-history-lineage-list">
                      {priceHistoryReplayDetail.data.series.map((series) => {
                        const sourceCapture = listedPriceHistorySources.find(
                          (capture) => capture.observation_id === series.observation_id,
                        );
                        return (
                          <article key={series.observation_id}>
                            <h4>
                              {venueLabel(series.venue)} · {series.native_instrument_id}
                            </h4>
                            <dl>
                              <div>
                                <dt>Source observation</dt>
                                <dd>
                                  <code>{series.observation_id}</code>
                                </dd>
                              </div>
                              <div>
                                <dt>Raw response SHA-256</dt>
                                <dd>
                                  <code>{series.raw_sha256}</code>
                                </dd>
                              </div>
                              <div>
                                <dt>Local capture receipt</dt>
                                <dd>
                                  {sourceCapture
                                    ? new Date(sourceCapture.received_at_utc).toLocaleString()
                                    : 'outside the current 20-capture source page'}
                                </dd>
                              </div>
                              <div>
                                <dt>Bound market observation</dt>
                                <dd>
                                  <code>{series.bound_market_observation_id ?? 'unbound'}</code>
                                </dd>
                              </div>
                              <div>
                                <dt>Source request</dt>
                                <dd>
                                  {series.interval} · {series.fidelity_minutes} min ·{' '}
                                  {new Date(series.requested_start_ts * 1000).toISOString()} →{' '}
                                  {new Date(series.requested_end_ts * 1000).toISOString()}
                                </dd>
                              </div>
                              <div>
                                <dt>Returned sample range</dt>
                                <dd>
                                  {series.point_count} points ·{' '}
                                  {series.minimum_sampled_price ?? '—'}
                                  {' – '}
                                  {series.maximum_sampled_price ?? '—'}
                                </dd>
                              </div>
                              <div>
                                <dt>Point-time bounds and gap</dt>
                                <dd>
                                  {series.first_point_ts == null
                                    ? 'No returned points'
                                    : `${new Date(series.first_point_ts * 1000).toISOString()} → ${new Date(series.last_point_ts! * 1000).toISOString()}`}{' '}
                                  · largest adjacent returned-point gap{' '}
                                  {series.largest_adjacent_sample_gap_seconds == null
                                    ? 'not available'
                                    : `${count(series.largest_adjacent_sample_gap_seconds)} s`}
                                </dd>
                              </div>
                              <div>
                                <dt>Points later than capture receipt</dt>
                                <dd>{count(series.future_point_timestamp_count)}</dd>
                              </div>
                            </dl>
                          </article>
                        );
                      })}
                    </div>
                    <p className="fr-history-replay-note">
                      These are returned historical samples. They do not establish missing-data
                      rates, synchronized availability, executable quotes, fills, or economic
                      opportunity.
                    </p>
                  </>
                ) : null}
              </section>
            )}
          </section>
          <section className="fr-card fr-joint-state-editor">
            <div className="fr-card-head">
              <div>
                <span className="fr-kicker">CONDITIONAL MULTI-MARKET REPLAY</span>
                <h2>Assert a joint-state map</h2>
              </div>
              <GitBranch size={17} />
            </div>
            <p className="fr-joint-state-editor-copy">
              Select two to four stored event markets, then explicitly map each asserted shared
              state to a local payoff state for every market. Mission Control pins the market
              observations and derives a content hash. The assertion is self-attributed and remains
              semantically unverified; this tool makes no exchange requests.
            </p>
            {markets.isError ? (
              <EmptyState title="Stored markets unavailable" detail={markets.error.message} />
            ) : jointMarketOptions.length === 0 ? (
              <EmptyState
                title="No eligible stored event markets"
                detail="This editor requires open event markets with exhaustive verified payoff states, verified resolution metadata, and pinned public observations."
              />
            ) : (
              <>
                <label className="fr-field">
                  Stored event markets <span>select two to four · local evidence only</span>
                  <select
                    multiple
                    size={Math.min(8, Math.max(3, jointMarketOptions.length))}
                    aria-label="Stored event markets for joint-state replay"
                    value={jointMarketIds}
                    onChange={(event) =>
                      setJointMarketIds(
                        Array.from(event.currentTarget.selectedOptions, (option) => option.value)
                          .slice(0, 4)
                          .sort(),
                      )
                    }
                  >
                    {jointMarketOptions.map((market) => (
                      <option key={market.canonical_id} value={market.canonical_id}>
                        {venueLabel(market.venue)} · {market.title} ·{' '}
                        {market.payoff.state_ids.length} states
                      </option>
                    ))}
                  </select>
                </label>
                {selectedJointMarkets.map((market) => (
                  <div className="fr-joint-market-summary" key={market.canonical_id}>
                    <strong>{market.title}</strong>
                    <span>
                      {venueLabel(market.venue)} · local payoff states:{' '}
                      <code>{market.payoff.state_ids.join(', ')}</code>
                    </span>
                    <small>
                      Metadata observation{' '}
                      <code>{shortHash(market.source_observation_record_id)}</code>
                    </small>
                  </div>
                ))}
                <label className="fr-field">
                  External assertion reference <span>self-attributed, not authenticated</span>
                  <input
                    aria-label="External assertion reference"
                    value={jointAssertionId}
                    onChange={(event) => setJointAssertionId(event.target.value)}
                    maxLength={120}
                    placeholder="e.g. research-note-2026-10-28-01"
                  />
                </label>
                <label className="fr-field">
                  Assertion time <span>must postdate every selected market observation</span>
                  <input
                    aria-label="Assertion time"
                    type="datetime-local"
                    value={jointAssertedAt}
                    onChange={(event) => setJointAssertedAt(event.target.value)}
                  />
                </label>
                <label className="fr-field">
                  Joint-state IDs <span>one bounded label per line · 2 to 64</span>
                  <textarea
                    aria-label="Joint-state IDs"
                    value={jointStateLabels}
                    onChange={(event) => setJointStateLabels(event.target.value)}
                    maxLength={9000}
                    placeholder={'state-a\nstate-b'}
                    rows={4}
                  />
                </label>
                {jointStateIds.length > 0 && selectedJointMarkets.length > 0 && (
                  <div className="fr-table-wrap fr-joint-projection-table">
                    <table className="fr-table">
                      <thead>
                        <tr>
                          <th>Asserted shared state</th>
                          {selectedJointMarkets.map((market) => (
                            <th key={market.canonical_id}>{market.title}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {jointStateIds.map((stateId) => (
                          <tr key={stateId}>
                            <th scope="row">{stateId}</th>
                            {selectedJointMarkets.map((market) => (
                              <td key={`${market.canonical_id}:${stateId}`}>
                                <select
                                  aria-label={`${stateId} local payoff state for ${market.title}`}
                                  value={jointProjection[market.canonical_id]?.[stateId] ?? ''}
                                  onChange={(event) =>
                                    setJointProjection((current) => ({
                                      ...current,
                                      [market.canonical_id]: {
                                        ...current[market.canonical_id],
                                        [stateId]: event.target.value,
                                      },
                                    }))
                                  }
                                >
                                  <option value="">Choose a local state</option>
                                  {market.payoff.state_ids.map((localState) => (
                                    <option key={localState} value={localState}>
                                      {localState}
                                    </option>
                                  ))}
                                </select>
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
                <p className="fr-review-verifier-note">
                  These projections are the submitted assertion. The independent audit checks exact
                  payoff arithmetic over the listed states, but cannot prove that the list is
                  exhaustive, attainable, or equivalent across venues. Results remain conditional.
                </p>
                <button
                  className="fr-action fr-run-button"
                  onClick={() => jointStateReplay.mutate()}
                  disabled={jointStateReplay.isPending || !jointProjectionComplete}
                >
                  <Play size={14} />
                  {jointStateReplay.isPending
                    ? 'Replaying stored joint-state evidence…'
                    : 'Replay conditional basket'}
                </button>
              </>
            )}
            {jointStateReplay.isError && <InlineError message={jointStateReplay.error.message} />}
            {jointStateReplayResult && (
              <div className="fr-joint-state-result" role="status">
                <strong>Conditional replay saved</strong>
                <span>
                  Run <code>{shortHash(jointStateReplayResult.run_id)}</code> · mapping{' '}
                  <code>
                    {shortHash(
                      jointStateReplayResult.manifest.joint_state_mappings?.[0]?.mapping_id,
                    )}
                  </code>
                </span>
                <span>
                  {jointStateReplayResult.candidates.length} candidate evaluations ·{' '}
                  {Object.entries(jointStateReplayResult.classification_counts)
                    .map(([classification, value]) => `${label(classification)} ${value}`)
                    .join(' · ') || 'no candidate classifications'}
                </span>
              </div>
            )}
          </section>
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
          <section className="fr-card fr-arena-replay-card fr-discovery-comparison-card">
            <div className="fr-card-head">
              <div>
                <span className="fr-kicker">COMPARATIVE DISCOVERY COVERAGE</span>
                <h2>Discovery scope comparison</h2>
              </div>
              <button
                className="fr-action"
                onClick={() => arenaDiscovery.mutate()}
                disabled={arenaDiscovery.isPending}
              >
                <GitBranch size={14} />
                {arenaDiscovery.isPending ? 'Submitting…' : 'Compare scopes in Arena'}
              </button>
            </div>
            <p className="fr-arena-replay-intro">
              Arena runs the same pinned, saved evidence through Polymarket-only, venue-local, and
              all-venue relationship scopes. It reports which candidates each scope can see and how
              many recorded instruments have books.
            </p>
            <div className="fr-callout">
              <ShieldCheck size={16} />
              <span>
                This compares universe coverage with the current deterministic calculators. It does
                not compare independent algorithm versions, estimate venue-wide prevalence, or
                establish executable returns. Workers are limited to 5 minutes, 512 MiB, half a CPU,
                and idle I/O; job admission requires the host-wide Arena resource gate.
              </span>
            </div>
            {arenaDiscovery.isError && <InlineError message={arenaDiscovery.error.message} />}
            {arenaDiscoveryJobs.isLoading ? (
              <div className="fr-loading">Loading discovery comparison history…</div>
            ) : arenaDiscoveryJobs.isError ? (
              <EmptyState
                title="Discovery comparison history unavailable"
                detail={arenaDiscoveryJobs.error.message}
              />
            ) : listedArenaDiscoveryJobs.length === 0 ? (
              <EmptyState
                title="No discovery scope comparisons"
                detail="Submitting a comparison snapshots only local recorded evidence. It does not probe an exchange or start a collector."
              />
            ) : (
              <div className="fr-arena-job-list" aria-label="Frontier discovery comparison jobs">
                {listedArenaDiscoveryJobs.map((job) => (
                  <button
                    key={job.job_id}
                    className={`fr-arena-job-row${job.job_id === selectedArenaDiscoveryJob?.job_id ? ' selected' : ''}`}
                    aria-pressed={job.job_id === selectedArenaDiscoveryJob?.job_id}
                    onClick={() => setSelectedArenaDiscoveryId(job.job_id)}
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
            {arenaDiscoveryJobs.data?.scan_may_be_incomplete && (
              <p className="fr-arena-replay-note">
                Job history is limited to a bounded scan of {arenaDiscoveryJobs.data.scan_bound}{' '}
                Arena records; older entries may be omitted.
              </p>
            )}
            {selectedArenaDiscoveryJob && (
              <article className="fr-arena-job-detail" aria-label="Selected discovery comparison">
                <div className="fr-arena-job-detail-head">
                  <div>
                    <span className="fr-kicker">SELECTED ARENA COMPARISON</span>
                    <code>{selectedArenaDiscoveryJob.job_id}</code>
                  </div>
                  <StateBadge state={selectedArenaDiscoveryJob.state} />
                </div>
                {['QUEUED', 'RUNNING'].includes(selectedArenaDiscoveryJob.state) && (
                  <p>
                    {selectedArenaDiscoveryJob.phase
                      ? label(selectedArenaDiscoveryJob.phase)
                      : 'Waiting for the Arena worker lease'}
                    {selectedArenaDiscoveryJob.progress &&
                      ` · ${selectedArenaDiscoveryJob.progress.done ?? 0} / ${selectedArenaDiscoveryJob.progress.total ?? 0} steps`}
                  </p>
                )}
                {selectedArenaDiscoveryJob.error && (
                  <div className="fr-alert" role="status">
                    <AlertTriangle size={16} />
                    <div>
                      <strong>Discovery comparison did not complete</strong>
                      <span>{selectedArenaDiscoveryJob.error}</span>
                    </div>
                  </div>
                )}
                {selectedArenaDiscoveryJob.elapsed_seconds != null && (
                  <p className="fr-arena-replay-note">
                    Worker elapsed time: {selectedArenaDiscoveryJob.elapsed_seconds.toFixed(3)} s
                    {selectedArenaDiscoveryJob.runtime_profile?.worker_process_peak_rss_bytes !=
                      null &&
                      ` · peak RSS ${(selectedArenaDiscoveryJob.runtime_profile.worker_process_peak_rss_bytes / 1024 / 1024).toFixed(1)} MiB`}
                  </p>
                )}
                {selectedArenaDiscoveryJob.snapshot_id && (
                  <dl className="fr-arena-job-hashes">
                    <div>
                      <dt>Input snapshot ID</dt>
                      <dd>{selectedArenaDiscoveryJob.snapshot_id}</dd>
                    </div>
                    <div>
                      <dt>Input snapshot SHA-256</dt>
                      <dd>{selectedArenaDiscoveryJob.snapshot_sha256 ?? 'Not recorded'}</dd>
                    </div>
                  </dl>
                )}
                {selectedArenaDiscoveryJob.state === 'COMPLETED' &&
                  arenaDiscoveryResult.isLoading && (
                    <div className="fr-loading">Reading and verifying the comparison artifact…</div>
                  )}
                {arenaDiscoveryResult.isError && (
                  <InlineError message={arenaDiscoveryResult.error.message} />
                )}
                {arenaDiscoveryResult.data?.integrity_verified && (
                  <DiscoveryScopeComparisonSummary
                    comparison={arenaDiscoveryResult.data.artifact.comparison}
                    replays={arenaDiscoveryResult.data.artifact.replays}
                  />
                )}
              </article>
            )}
          </section>
          <section className="fr-card fr-arena-replay-card fr-arena-timeline-card">
            <div className="fr-card-head">
              <div>
                <span className="fr-kicker">EVENT-TIME EVIDENCE</span>
                <h2>Timeline replay</h2>
              </div>
              <button
                className="fr-action"
                onClick={() => timelineReplay.mutate()}
                disabled={
                  timelineReplay.isPending || !markets.data?.items.length || !timelineFreshnessValid
                }
                title={
                  !markets.data?.items.length
                    ? 'Recorded markets are required before replay'
                    : !timelineFreshnessValid
                      ? 'Book freshness must be an integer from 1 to 3600000 milliseconds'
                      : 'Stage saved local observations as a bounded Arena job'
                }
              >
                <Play size={14} />
                {timelineReplay.isPending ? 'Submitting…' : 'Replay saved timeline'}
              </button>
            </div>
            <p className="fr-arena-replay-intro">
              Re-evaluates saved books at their event times and freshness boundaries. The input is
              pinned locally; no exchange requests or collector start. Each completed result reports
              fresh, stale, not-yet-observed, and source-excluded books per frame.
            </p>
            <div className="fr-timeline-controls">
              <label htmlFor="frontier-timeline-max-book-age">
                Maximum book age (milliseconds)
              </label>
              <input
                id="frontier-timeline-max-book-age"
                type="number"
                min="1"
                max="3600000"
                step="1"
                inputMode="numeric"
                value={timelineMaxBookAgeMs}
                aria-invalid={!timelineFreshnessValid}
                aria-describedby="frontier-timeline-freshness-help"
                onChange={(event) => setTimelineMaxBookAgeMs(event.target.value)}
              />
              <small id="frontier-timeline-freshness-help">
                Books older than this receipt-time bound are excluded. Use an integer from 1 to
                3,600,000; the value is pinned into the replay snapshot.
              </small>
            </div>
            <fieldset className="fr-recorded-health-picker">
              <legend>Recorded adapter health</legend>
              <p>
                Select verified local collector checkpoints to replay as source-state events. These
                records describe adapter-local health at one checkpoint; they do not show continuous
                venue availability or account eligibility. This list reads the local journal only
                and never starts a collector or contacts a venue. Select at most one event for each
                venue and check time.
              </p>
              {recordedSourceHealth.isLoading ? (
                <div className="fr-loading">Reading verified local health checkpoints…</div>
              ) : recordedSourceHealth.isError ? (
                <InlineError message={recordedSourceHealth.error.message} />
              ) : recordedSourceHealthItems.length === 0 ? (
                <EmptyState
                  title="No verified health checkpoints"
                  detail="A bounded collector run must already have recorded adapter health. No source probe is started from this screen."
                />
              ) : (
                <div className="fr-recorded-health-list">
                  {recordedSourceHealthItems.map((item) => {
                    const digest = item.event.evidence_observation_id;
                    const checked = selectedSourceHealthDigests.includes(digest);
                    const conflictsWithSelection = selectedSourceHealthEvents.some(
                      (selected) =>
                        selected.venue === item.event.venue &&
                        selected.observed_at_utc === item.event.observed_at_utc &&
                        selected.evidence_observation_id !== digest,
                    );
                    return (
                      <label className="fr-recorded-health-row" key={digest}>
                        <input
                          type="checkbox"
                          checked={checked}
                          disabled={conflictsWithSelection && !checked}
                          title={
                            conflictsWithSelection && !checked
                              ? 'Another source event for this venue and check time is selected'
                              : undefined
                          }
                          onChange={(change) =>
                            setSelectedSourceHealthDigests((current) =>
                              change.target.checked
                                ? current.includes(digest)
                                  ? current
                                  : [...current, digest]
                                : current.filter((selected) => selected !== digest),
                            )
                          }
                          aria-label={`Include recorded ${item.event.venue} ${item.event.state} health from ${time(item.event.observed_at_utc)}`}
                        />
                        <span className="fr-recorded-health-copy">
                          <strong>
                            {item.event.venue} · {item.event.state}
                          </strong>
                          <small>
                            Checked {time(item.event.observed_at_utc)} · adapter{' '}
                            {item.adapter_version} · journal sequence {item.checkpoint_sequence}
                          </small>
                          <small>Last success {time(item.last_success_at_utc)}</small>
                          <code>{digest}</code>
                        </span>
                      </label>
                    );
                  })}
                </div>
              )}
            </fieldset>
            <div className="fr-callout">
              <ShieldCheck size={16} />
              <span>
                This is deterministic hypothetical research. A fresh book in a replay frame does not
                establish simultaneous executable quotes, fills, venue access, or profitability.
                Recorded source states replay adapter-local checkpoint health; they do not establish
                continuous venue availability or account eligibility. Worker admission remains
                subject to Arena’s host resource gate.
              </span>
            </div>
            {timelineReplay.isError && <InlineError message={timelineReplay.error.message} />}
            {timelineJobs.isLoading ? (
              <div className="fr-loading">Loading event-time replay history…</div>
            ) : timelineJobs.isError ? (
              <EmptyState
                title="Timeline replay history unavailable"
                detail={timelineJobs.error.message}
              />
            ) : listedTimelineJobs.length === 0 ? (
              <EmptyState
                title="No event-time replay jobs"
                detail={
                  markets.data?.items.length
                    ? 'Replay submission is explicit and uses only saved evidence. The timeline job is bounded to five minutes, 512 MiB, half a CPU, and idle I/O.'
                    : 'Record market and book observations before staging a timeline. No public feed is started from this screen.'
                }
              />
            ) : (
              <div className="fr-arena-job-list" aria-label="Frontier timeline replay jobs">
                {listedTimelineJobs.map((job) => (
                  <button
                    key={job.job_id}
                    className={`fr-arena-job-row${job.job_id === selectedTimelineJob?.job_id ? ' selected' : ''}`}
                    aria-pressed={job.job_id === selectedTimelineJob?.job_id}
                    onClick={() => setSelectedTimelineJobId(job.job_id)}
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
            {timelineJobs.data?.scan_may_be_incomplete && (
              <p className="fr-arena-replay-note">
                Timeline history is limited to a bounded scan of {timelineJobs.data.scan_bound}{' '}
                Arena records; older entries may be omitted.
              </p>
            )}
            {selectedTimelineJob && (
              <article className="fr-arena-job-detail" aria-label="Selected timeline replay">
                <div className="fr-arena-job-detail-head">
                  <div>
                    <span className="fr-kicker">SELECTED EVENT-TIME JOB</span>
                    <code>{selectedTimelineJob.job_id}</code>
                  </div>
                  <StateBadge state={selectedTimelineJob.state} />
                </div>
                {['QUEUED', 'RUNNING'].includes(selectedTimelineJob.state) && (
                  <p>
                    {selectedTimelineJob.phase
                      ? label(selectedTimelineJob.phase)
                      : 'Waiting for the Arena worker lease'}
                    {selectedTimelineJob.progress &&
                      ` · ${selectedTimelineJob.progress.done ?? 0} / ${selectedTimelineJob.progress.total ?? 0} steps`}
                  </p>
                )}
                {selectedTimelineJob.error && (
                  <div className="fr-alert" role="status">
                    <AlertTriangle size={16} />
                    <div>
                      <strong>Timeline replay did not complete</strong>
                      <span>{selectedTimelineJob.error}</span>
                    </div>
                  </div>
                )}
                <dl className="fr-arena-job-hashes">
                  {selectedTimelineJob.elapsed_seconds != null && (
                    <div>
                      <dt>Worker elapsed time</dt>
                      <dd>{selectedTimelineJob.elapsed_seconds.toFixed(3)} s</dd>
                    </div>
                  )}
                  <div>
                    <dt>Input snapshot SHA-256</dt>
                    <dd>{selectedTimelineJob.snapshot_sha256 ?? 'Not recorded'}</dd>
                  </div>
                  {selectedTimelineJob.result?.frontier_timeline_sha256 && (
                    <div>
                      <dt>Result SHA-256</dt>
                      <dd>{selectedTimelineJob.result.frontier_timeline_sha256}</dd>
                    </div>
                  )}
                  {selectedTimelineJob.result?.timeline_id && (
                    <div>
                      <dt>Timeline identity</dt>
                      <dd>{selectedTimelineJob.result.timeline_id}</dd>
                    </div>
                  )}
                </dl>
                {selectedTimelineJob.state === 'COMPLETED' && timelineResult.isLoading && (
                  <div className="fr-loading">Reading and verifying the completed timeline…</div>
                )}
                {timelineResult.isError && <InlineError message={timelineResult.error.message} />}
                {timelineResult.data?.integrity_verified && (
                  <>
                    <p className="fr-arena-replay-note">
                      Hash checks passed. {timelineResult.data.artifact.timeline.frames.length}{' '}
                      event-time frames are pinned to observation receipts, freshness policy, and
                      the stored input digest. Results remain hypothetical.
                    </p>
                    <div className="fr-timeline-provenance">
                      <span>
                        Markets{' '}
                        {
                          timelineResult.data.artifact.timeline.manifest.market_observation_ids
                            .length
                        }
                      </span>
                      <span>
                        Books{' '}
                        {timelineResult.data.artifact.timeline.manifest.book_observation_ids.length}
                      </span>
                      <span>
                        Verified relationships{' '}
                        {timelineResult.data.artifact.timeline.manifest.relationship_ids.length}
                      </span>
                      <span>
                        Recorded health checkpoints{' '}
                        {
                          timelineResult.data.artifact.timeline.manifest.source_status_sha256s
                            .length
                        }
                      </span>
                      <span>
                        Freshness limit{' '}
                        {timelineResult.data.artifact.timeline.manifest.max_book_age_ms.toLocaleString()}{' '}
                        ms
                      </span>
                    </div>
                    {timelineResult.data.artifact.timeline.manifest.source_status_sha256s.length >
                      0 && (
                      <div
                        className="fr-timeline-health-digests"
                        aria-label="Recorded health checkpoint digests"
                      >
                        <strong>Recorded health checkpoint digests</strong>
                        {timelineResult.data.artifact.timeline.manifest.source_status_sha256s.map(
                          (digest) => (
                            <code key={digest}>{digest}</code>
                          ),
                        )}
                      </div>
                    )}
                    <div className="fr-timeline-frame-list" aria-label="Timeline frame results">
                      {timelineResult.data.artifact.timeline.frames.map((frame) => (
                        <TimelineFrameSummary key={frame.as_of_utc} frame={frame} />
                      ))}
                    </div>
                    <p className="fr-arena-replay-note">
                      Input {timelineResult.data.artifact.timeline.manifest.input_sha256} · timeline{' '}
                      {timelineResult.data.artifact.timeline.timeline_id}
                    </p>
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

function PolymarketPriceHistoryPanel({
  market,
  probe,
  probeEnabled,
}: {
  market: Market;
  probe: UseMutationResult<
    PriceHistoryCaptureResult,
    Error,
    {
      nativeInstrumentId: string;
      interval: '1d' | '1w';
      fidelityMinutes: number;
      startTs: number;
      endTs: number;
    },
    unknown
  >;
  probeEnabled: boolean;
}) {
  const [instrumentId, setInstrumentId] = useState(
    market.instruments[0]?.native_instrument_id ?? '',
  );
  const [interval, setInterval] = useState<'1d' | '1w'>('1d');
  const [days, setDays] = useState('7');
  const storedHistory = useQuery({
    queryKey: ['frontier', 'price-history', instrumentId],
    queryFn: () =>
      api<PriceHistoryResponse>(
        `/frontier/price-history?venue=polymarket&native_instrument_id=${encodeURIComponent(instrumentId)}&limit=1`,
      ),
    enabled: Boolean(instrumentId),
  });
  const replayPriceHistory = useMutation({
    mutationFn: (sourceObservationId: string) =>
      api<PriceHistoryReplayResult>('/frontier/price-history/replay', {
        method: 'POST',
        body: JSON.stringify({ observation_ids: [sourceObservationId] }),
      }),
  });
  const isCurrentProbe =
    probe.isSuccess &&
    probe.variables?.nativeInstrumentId === instrumentId &&
    probe.variables.interval === interval;
  const series = isCurrentProbe
    ? probe.data.series
    : (storedHistory.data?.items[0]?.series ?? null);
  const observationId = isCurrentProbe
    ? probe.data.observation_id
    : (storedHistory.data?.items[0]?.observation_id ?? null);
  const rawSha256 = isCurrentProbe
    ? probe.data.raw_sha256
    : (storedHistory.data?.items[0]?.raw_sha256 ?? null);
  const endTs = Math.floor(Date.now() / 1000) - 60;
  const startTs = endTs - Number(days) * 24 * 60 * 60;
  const points = series?.points ?? [];
  const rangeSeconds = Math.max(
    1,
    (series?.requested_end_ts ?? endTs) - (series?.requested_start_ts ?? startTs),
  );
  const lastPoints = points.slice(-8);

  return (
    <section className="fr-price-history-panel" aria-label="Polymarket historical price samples">
      <div className="fr-price-history-heading">
        <div>
          <span className="fr-kicker">SOURCE REPORTED SERIES</span>
          <h4>Historical price points</h4>
          <p>
            One explicit CLOB request for this recorded outcome token. Samples are not executable
            quotes; the source does not supply OHLC or volume here.
          </p>
        </div>
        <span className="fr-count">{points.length} points</span>
      </div>
      <div className="fr-price-history-controls">
        <label>
          Outcome token
          <select
            aria-label="Historical price outcome token"
            value={instrumentId}
            onChange={(event) => setInstrumentId(event.target.value)}
          >
            {market.instruments.map((instrument) => (
              <option key={instrument.native_instrument_id} value={instrument.native_instrument_id}>
                {instrument.label} · {instrument.native_instrument_id}
              </option>
            ))}
          </select>
        </label>
        <label>
          CLOB interval
          <select
            aria-label="Historical price interval"
            value={interval}
            onChange={(event) => setInterval(event.target.value as '1d' | '1w')}
          >
            <option value="1d">1d</option>
            <option value="1w">1w</option>
          </select>
        </label>
        <label>
          Lookback
          <select
            aria-label="Historical price lookback"
            value={days}
            onChange={(event) => setDays(event.target.value)}
          >
            <option value="1">1 day</option>
            <option value="3">3 days</option>
            <option value="7">7 days</option>
          </select>
        </label>
        <button
          className="fr-inspect-button"
          disabled={!instrumentId || !probeEnabled || probe.isPending}
          onClick={() =>
            probe.mutate({
              nativeInstrumentId: instrumentId,
              interval,
              fidelityMinutes: 60,
              startTs,
              endTs,
            })
          }
        >
          {probe.isPending
            ? 'Capturing…'
            : probeEnabled
              ? 'Capture one series'
              : 'Public probe disabled'}
        </button>
      </div>
      <p className="fr-price-history-note">
        {probeEnabled
          ? 'Capture runs only after this button is pressed. Each request is capped at 7 days and 1500 returned points.'
          : 'Historical price capture is disabled by the Polymarket source configuration.'}{' '}
        Stored series below are read from Frontier’s local evidence store; page load does not
        contact Polymarket.
      </p>
      {probe.isError && probe.variables?.nativeInstrumentId === instrumentId && (
        <ProbeFailureEvidence error={probe.error} />
      )}
      {storedHistory.isLoading ? (
        <div className="fr-loading">Loading saved price history…</div>
      ) : storedHistory.isError ? (
        <EmptyState title="Saved history query failed" detail={storedHistory.error.message} />
      ) : points.length ? (
        <div className="fr-price-history-result" role="status">
          <figure>
            <svg
              viewBox="0 0 600 170"
              role="img"
              aria-label={`${points.length} source-reported price samples for ${instrumentId}; vertical scale is 0 to 1`}
              preserveAspectRatio="none"
            >
              <line x1="12" y1="10" x2="12" y2="154" />
              <line x1="12" y1="154" x2="588" y2="154" />
              {points.map((point) => {
                const timestamp = Math.floor(Date.parse(point.timestamp_utc) / 1000);
                const x =
                  12 + ((timestamp - (series?.requested_start_ts ?? startTs)) / rangeSeconds) * 576;
                const y = 154 - Number(point.price) * 144;
                return (
                  <circle key={`${point.timestamp_utc}:${point.price}`} cx={x} cy={y} r="2.5">
                    <title>
                      {time(point.timestamp_utc)} · source price {point.price}
                    </title>
                  </circle>
                );
              })}
            </svg>
            <figcaption>
              Each dot is one returned sample. The horizontal axis spans the requested time window;
              the vertical axis is the reported price from 0 to 1. No line is interpolated between
              observations.
            </figcaption>
          </figure>
          <div className="fr-price-history-meta">
            <span>
              CLOB interval {series?.interval} · fidelity {series?.fidelity_minutes} min
            </span>
            <span>Evidence {observationId ? shortHash(observationId) : 'unavailable'}</span>
            {rawSha256 && <span>Raw SHA-256 {shortHash(rawSha256)}</span>}
            {observationId && <EvidenceDisclosure observationId={observationId} />}
            {observationId && (
              <button
                className="fr-inspect-button"
                disabled={replayPriceHistory.isPending}
                onClick={() => replayPriceHistory.mutate(observationId)}
              >
                {replayPriceHistory.isPending ? 'Replaying…' : 'Replay saved series'}
              </button>
            )}
          </div>
          {replayPriceHistory.isError && replayPriceHistory.variables === observationId && (
            <EmptyState
              title="Local price-history replay failed"
              detail={replayPriceHistory.error.message}
            />
          )}
          {replayPriceHistory.isSuccess && replayPriceHistory.variables === observationId && (
            <div className="fr-price-history-replay" role="status">
              <strong>Deterministic source-sample replay</strong>
              <span>
                {count(replayPriceHistory.data.series[0]?.point_count ?? 0)} points · run{' '}
                {shortHash(replayPriceHistory.data.run_id)} · input{' '}
                {shortHash(replayPriceHistory.data.manifest.input_sha256)}
              </span>
              <span>
                Sampled prices {replayPriceHistory.data.series[0]?.minimum_sampled_price ?? '—'} to{' '}
                {replayPriceHistory.data.series[0]?.maximum_sampled_price ?? '—'} · largest observed
                adjacent gap{' '}
                {replayPriceHistory.data.series[0]?.largest_adjacent_sample_gap_seconds == null
                  ? '—'
                  : `${count(replayPriceHistory.data.series[0].largest_adjacent_sample_gap_seconds)} s`}
              </span>
              <small>
                Local replay of saved samples only. Candidate generation was not performed; returned
                point gaps do not estimate missing data.
              </small>
            </div>
          )}
          <div className="fr-table-wrap">
            <table className="fr-table">
              <thead>
                <tr>
                  <th>Sample time</th>
                  <th>Source reported price</th>
                </tr>
              </thead>
              <tbody>
                {lastPoints.map((point) => (
                  <tr key={`${point.timestamp_utc}:${point.price}`}>
                    <td>{time(point.timestamp_utc)}</td>
                    <td>{point.price}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <small>{series?.source_limit_note}</small>
        </div>
      ) : (
        <EmptyState
          title="No saved price history for this outcome token"
          detail="Capture one bounded series to persist its native response and normalized samples."
        />
      )}
    </section>
  );
}

function PolymarketBookUpdatesPanel({
  market,
  probe,
  probeEnabled,
  replay,
  replayEnabled,
  replayDisabledReason,
}: {
  market: Market;
  probe: UseMutationResult<PolymarketBookUpdateCaptureResult, Error, { marketId: string }, unknown>;
  probeEnabled: boolean;
  replay: UseMutationResult<
    PolymarketBookUpdatesReplayResult,
    Error,
    { observationIds: string[]; nativeMarketId: string },
    unknown
  >;
  replayEnabled: boolean;
  replayDisabledReason?: string | null;
}) {
  const [savedFrameOffset, setSavedFrameOffset] = useState(0);
  const savedFramePage = useQuery({
    queryKey: ['frontier', 'polymarket-book-update-frames', savedFrameOffset],
    queryFn: () =>
      api<PolymarketStoredBookUpdatePage>(
        `/frontier/polymarket/book-updates?limit=32&offset=${savedFrameOffset}`,
      ),
    enabled: replayEnabled,
    retry: false,
  });
  const result =
    probe.isSuccess && probe.variables?.marketId === market.canonical_id ? probe.data : null;
  const observationIds = result?.frames.map((frame) => frame.observation_id) ?? [];
  const replayMatchesMarket = replay.variables?.nativeMarketId === market.native_market_id;
  const replayResult = replay.isSuccess && replayMatchesMarket ? replay.data : null;
  const savedFrames = (savedFramePage.data?.items ?? []).filter(
    (frame) => frame.native_market_id === market.native_market_id,
  );

  return (
    <section className="fr-price-history-panel" aria-label="Polymarket public book update capture">
      <div className="fr-price-history-heading">
        <div>
          <span className="fr-kicker">FINITE PUBLIC STREAM CAPTURE</span>
          <h4>Book update events</h4>
          <p>
            Opens one explicitly requested stream for up to 3 seconds, 8 frames and 50 normalized
            updates. Events are stored with their raw frames and this market’s saved source record.
          </p>
        </div>
        <span className="fr-count">
          {result
            ? `${result.frame_count} frames · ${result.normalized_update_count} events`
            : 'No capture'}
        </span>
      </div>
      <div className="fr-price-history-controls">
        <button
          className="fr-inspect-button"
          disabled={!probeEnabled || probe.isPending}
          onClick={() => probe.mutate({ marketId: market.canonical_id })}
        >
          {probe.isPending
            ? 'Capturing…'
            : probeEnabled
              ? 'Capture 3-second market stream'
              : 'Public stream disabled'}
        </button>
        <button
          className="fr-inspect-button"
          disabled={observationIds.length === 0 || !replayEnabled || replay.isPending}
          onClick={() => replay.mutate({ observationIds, nativeMarketId: market.native_market_id })}
        >
          {replay.isPending
            ? 'Replaying stored frames…'
            : replayEnabled
              ? 'Replay saved capture offline'
              : 'Replay unavailable by source policy'}
        </button>
      </div>
      <p className="fr-price-history-note">
        {probeEnabled
          ? 'Capture starts only after this button is pressed. Public updates have no verified sequence or gap recovery; deltas are not applied to a local book.'
          : 'Capture is unavailable because the Polymarket source is disabled, held, or does not advertise book updates.'}
      </p>
      <p className="fr-price-history-note">
        Saved replay reads immutable raw frames, orders persisted event frames by local monotonic
        receipt timing, and never applies level changes to a book. Exchange sequence continuity
        remains unverified; replayed events are excluded from economics.
        {!replayEnabled && replayDisabledReason ? ` ${replayDisabledReason}` : ''}
      </p>
      {probe.isError && probe.variables?.marketId === market.canonical_id && (
        <ProbeFailureEvidence error={probe.error} />
      )}
      {replay.isError && replayMatchesMarket && (
        <p role="alert" className="fr-price-history-note">
          {replay.error?.message ?? 'Stored Polymarket replay failed without a diagnostic message.'}
        </p>
      )}
      {result && (
        <div className="fr-price-history-result" role="status">
          <p>
            {result.capture_status === 'captured'
              ? `Captured ${result.frame_count} stream frame${result.frame_count === 1 ? '' : 's'} with ${result.normalized_update_count} normalized event${result.normalized_update_count === 1 ? '' : 's'}.`
              : 'The bounded stream window opened successfully but contained no market updates.'}
          </p>
          <p>
            Bound market evidence {shortHash(result.bound_market_observation_id)} · source state{' '}
            {label(result.source_state)}
          </p>
          {result.frames.map((frame, frameOrdinal) => (
            <article key={frame.observation_id} className="fr-price-history-meta">
              <span>Stored event frame {frameOrdinal}</span>
              <span>Received {time(frame.received_at_utc)}</span>
              <span>Record {shortHash(frame.observation_id)}</span>
              <span>Raw SHA-256 {shortHash(frame.raw_sha256)}</span>
              {frame.updates.map((update, index) => (
                <div key={`${frame.observation_id}:${index}`}>
                  <span>
                    {update.event_type} · instrument {update.native_instrument_id} · bid/ask levels{' '}
                    {update.bid_level_count}/{update.ask_level_count} · changes{' '}
                    {update.price_change_count} · quality {update.quality_flags.join(', ')}
                  </span>
                  {update.event_type === 'book' && (
                    <small>
                      Snapshot · min size {update.min_order_size ?? 'not reported'} · tick{' '}
                      {update.tick_size ?? 'not reported'} · negative risk{' '}
                      {update.neg_risk == null ? 'not reported' : update.neg_risk ? 'yes' : 'no'} ·
                      last trade {update.last_trade_price ?? 'not reported'} · hash{' '}
                      {update.book_hash ? shortHash(update.book_hash) : 'not reported'}
                    </small>
                  )}
                </div>
              ))}
              <EvidenceDisclosure observationId={frame.observation_id} />
            </article>
          ))}
          <small>{result.note}</small>
        </div>
      )}
      <section aria-label="Saved Polymarket event frames" className="fr-price-history-result">
        <div className="fr-price-history-heading">
          <div>
            <strong>Saved event frames</strong>
            <small>Read from the local Frontier store. Listing does not contact Polymarket.</small>
          </div>
          <span className="fr-count">
            {savedFramePage.isPending
              ? 'Loading…'
              : `${savedFrames.length} for this market · ${savedFramePage.data?.returned ?? 0} on page`}
          </span>
        </div>
        {savedFramePage.isError && (
          <p role="alert" className="fr-price-history-note">
            {savedFramePage.error.message || 'Stored Polymarket event frames could not be loaded.'}
          </p>
        )}
        {savedFrames.map((frame) => (
          <article key={frame.observation_id} className="fr-price-history-meta">
            <span>Received {time(frame.received_at_utc)}</span>
            <span>Capture started {time(frame.capture_started_at_utc)}</span>
            <span>Record {shortHash(frame.observation_id)}</span>
            <span>Raw SHA-256 {shortHash(frame.raw_sha256)}</span>
            <span>
              {frame.normalized_event_count} normalized event
              {frame.normalized_event_count === 1 ? '' : 's'} ·{' '}
              {frame.event_types.map(label).join(', ')}
            </span>
            <button
              className="fr-inspect-button"
              disabled={!replayEnabled || replay.isPending}
              onClick={() =>
                replay.mutate({
                  observationIds: [frame.observation_id],
                  nativeMarketId: market.native_market_id,
                })
              }
            >
              Replay this saved frame offline
            </button>
            <EvidenceDisclosure observationId={frame.observation_id} />
          </article>
        ))}
        {savedFramePage.isSuccess && savedFrames.length === 0 && (
          <p className="fr-price-history-note">
            {savedFramePage.data.next_offset === null
              ? 'No saved stream frames for this market.'
              : 'No matching frame on this page. Continue to older saved frames.'}
          </p>
        )}
        <div className="fr-price-history-controls">
          <button
            className="fr-inspect-button"
            disabled={savedFrameOffset === 0 || savedFramePage.isFetching}
            onClick={() => setSavedFrameOffset((offset) => Math.max(0, offset - 32))}
          >
            Newer saved frames
          </button>
          <button
            className="fr-inspect-button"
            disabled={savedFramePage.data?.next_offset == null || savedFramePage.isFetching}
            onClick={() => setSavedFrameOffset(savedFramePage.data!.next_offset!)}
          >
            Older saved frames
          </button>
        </div>
      </section>
      {replayResult && (
        <div
          className="fr-price-history-result"
          role="status"
          aria-label="Polymarket offline event replay result"
        >
          <p>
            Replayed {replayResult.event_count} normalized event
            {replayResult.event_count === 1 ? '' : 's'} across {replayResult.frames.length} saved
            update frame{replayResult.frames.length === 1 ? '' : 's'} in local monotonic order.
          </p>
          <p>
            Replay {replayResult.replay_version} · frame evidence{' '}
            {replayResult.frame_evidence.length} · continuity unverified
          </p>
          {replayResult.frames.map((frame) => (
            <article key={frame.observation_id} className="fr-price-history-meta">
              <span>
                Stored event frame {frame.frame_ordinal} · received {time(frame.received_at_utc)}
              </span>
              <span>
                Events {frame.updates.map((update) => label(update.event_type)).join(', ')}
              </span>
              {frame.updates
                .filter((update) => update.event_type === 'book')
                .map((update, index) => (
                  <small key={`${frame.observation_id}:snapshot:${index}`}>
                    Snapshot · {update.bids.length} bid / {update.asks.length} ask levels · min size{' '}
                    {update.min_order_size ?? 'not reported'} · tick{' '}
                    {update.tick_size ?? 'not reported'} · negative risk{' '}
                    {update.neg_risk == null ? 'not reported' : update.neg_risk ? 'yes' : 'no'} ·
                    last trade {update.last_trade_price ?? 'not reported'} · hash{' '}
                    {update.book_hash ? shortHash(update.book_hash) : 'not reported'}
                  </small>
                ))}
              <span>Record {shortHash(frame.observation_id)}</span>
            </article>
          ))}
          <p>
            Input SHA-256 {shortHash(replayResult.input_sha256)} · result SHA-256{' '}
            {shortHash(replayResult.result_sha256)}
          </p>
          <strong>Context only · no book reconstruction · economics ineligible.</strong>
        </div>
      )}
    </section>
  );
}

function MarketDetails({
  market,
  books,
  booksLoading,
  marketMetadataProbe,
  marketMetadataProbeEnabled,
  priceHistoryProbe,
  priceHistoryProbeEnabled,
  bookUpdatesProbe,
  bookUpdatesProbeEnabled,
  bookUpdatesReplay,
  bookUpdatesReplayEnabled,
  bookUpdatesReplayDisabledReason,
  krakenBookUpdatesProbe,
  krakenBookUpdatesReplay,
  krakenBookUpdatesProbeEnabled,
  krakenBookUpdatesDisabledReason,
  krakenCandleProbeEnabled,
  krakenCandleDisabledReason,
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
  marketMetadataProbe: UseMutationResult<
    MarketMetadataCaptureResult,
    Error,
    { marketId: string; venue: 'polymarket' | 'kalshi' },
    unknown
  >;
  marketMetadataProbeEnabled: boolean;
  priceHistoryProbe: UseMutationResult<
    PriceHistoryCaptureResult,
    Error,
    {
      nativeInstrumentId: string;
      interval: '1d' | '1w';
      fidelityMinutes: number;
      startTs: number;
      endTs: number;
    },
    unknown
  >;
  priceHistoryProbeEnabled: boolean;
  bookUpdatesProbe: UseMutationResult<
    PolymarketBookUpdateCaptureResult,
    Error,
    { marketId: string },
    unknown
  >;
  bookUpdatesProbeEnabled: boolean;
  bookUpdatesReplay: UseMutationResult<
    PolymarketBookUpdatesReplayResult,
    Error,
    { observationIds: string[]; nativeMarketId: string },
    unknown
  >;
  bookUpdatesReplayEnabled: boolean;
  bookUpdatesReplayDisabledReason?: string | null;
  krakenBookUpdatesProbe: UseMutationResult<
    KrakenBookUpdateCaptureResult,
    Error,
    { marketId: string },
    unknown
  >;
  krakenBookUpdatesReplay: UseMutationResult<
    KrakenBookCaptureReplay,
    Error,
    { observationIds: string[] },
    unknown
  >;
  krakenBookUpdatesProbeEnabled: boolean;
  krakenBookUpdatesDisabledReason?: string | null;
  krakenCandleProbeEnabled: boolean;
  krakenCandleDisabledReason?: string | null;
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
  const capturedEventMarkets =
    eventMarketsProbe.isSuccess && eventMarketsProbe.variables?.marketId === market.canonical_id
      ? eventMarketsProbe.data
      : null;
  const capturedMarketMetadata =
    marketMetadataProbe.isSuccess && marketMetadataProbe.variables?.marketId === market.canonical_id
      ? marketMetadataProbe.data
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
      {market.venue === 'polymarket' && (
        <PolymarketPriceHistoryPanel
          market={market}
          probe={priceHistoryProbe}
          probeEnabled={priceHistoryProbeEnabled}
        />
      )}
      {market.venue === 'kraken' && (
        <>
          <KrakenCandleHistoryPanel
            nativeMarketId={market.native_market_id}
            marketObservationId={market.provenance.observation_id}
            probeEnabled={krakenCandleProbeEnabled}
            disabledReason={krakenCandleDisabledReason}
          />
          <KrakenBookUpdatesPanel
            marketId={market.canonical_id}
            nativeMarketId={market.native_market_id}
            probe={krakenBookUpdatesProbe}
            replay={krakenBookUpdatesReplay}
            probeEnabled={krakenBookUpdatesProbeEnabled}
            disabledReason={krakenBookUpdatesDisabledReason}
            renderEvidence={(observationId) => <EvidenceDisclosure observationId={observationId} />}
          />
        </>
      )}
      {market.venue === 'polymarket' && (
        <PolymarketBookUpdatesPanel
          key={market.native_market_id}
          market={market}
          probe={bookUpdatesProbe}
          probeEnabled={bookUpdatesProbeEnabled}
          replay={bookUpdatesReplay}
          replayEnabled={bookUpdatesReplayEnabled}
          replayDisabledReason={bookUpdatesReplayDisabledReason}
        />
      )}
      {(market.venue === 'polymarket' || market.venue === 'kalshi') && (
        <div className="fr-fee-metadata-panel">
          <div>
            <strong>
              Single-market {market.venue === 'polymarket' ? 'Gamma' : 'Kalshi'} detail
            </strong>
            <small>
              Fetches this saved native market ID directly. It supplements the listing evidence and
              does not enumerate the event or verify outcome completeness.
            </small>
          </div>
          <button
            className="fr-inspect-button"
            disabled={!marketMetadataProbeEnabled || marketMetadataProbe.isPending}
            onClick={() =>
              marketMetadataProbe.mutate({
                marketId: market.canonical_id,
                venue: market.venue as 'polymarket' | 'kalshi',
              })
            }
          >
            {marketMetadataProbe.isPending &&
            marketMetadataProbe.variables?.marketId === market.canonical_id
              ? 'Capturing…'
              : marketMetadataProbeEnabled
                ? 'Capture market detail'
                : 'Public probe disabled'}
          </button>
          {marketMetadataProbe.isError &&
            marketMetadataProbe.variables?.marketId === market.canonical_id && (
              <ProbeFailureEvidence error={marketMetadataProbe.error} />
            )}
          {capturedMarketMetadata && (
            <div className="fr-fee-metadata-result" role="status">
              <strong>{capturedMarketMetadata.market.title}</strong>
              <small>
                Detail observation {shortHash(capturedMarketMetadata.observation_id)} · linked
                listing {shortHash(capturedMarketMetadata.bound_market_observation_id)}
              </small>
              <small>
                Resolution source:{' '}
                {capturedMarketMetadata.market.resolution.authority ?? 'Not provided'}
              </small>
              <small>
                {capturedMarketMetadata.market.resolution.primary_rule ??
                  capturedMarketMetadata.market.description ??
                  'No rule text in the detail response.'}
              </small>
              <small>{capturedMarketMetadata.note}</small>
              <small>Raw SHA-256 {capturedMarketMetadata.raw_sha256}</small>
              <EvidenceDisclosure observationId={capturedMarketMetadata.observation_id} />
            </div>
          )}
        </div>
      )}
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
              <ProbeFailureEvidence error={mveComponentProbe.error} />
            )}
        </div>
      ) : null}
      {market.market_kind !== 'spot_pair' && (
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
          {eventMarketsProbe.isError && <ProbeFailureEvidence error={eventMarketsProbe.error} />}
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
        <KalshiFeePanel
          marketId={market.canonical_id}
          instruments={market.instruments}
          feeMetadataProbe={feeMetadataProbe}
          feeMetadataProbeEnabled={feeMetadataProbeEnabled}
          feeSensitivity={feeSensitivity}
          renderEvidence={(observationId) => <EvidenceDisclosure observationId={observationId} />}
          renderProbeFailure={(error) => <ProbeFailureEvidence error={error} />}
          renderSensitivityError={(error) => <InlineError message={error.message} />}
        />
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
              {instrument.canonical_id && (
                <small>
                  Canonical ID (venue-scoped; not an equivalence claim):{' '}
                  <code>{instrument.canonical_id}</code>
                </small>
              )}
              <small>
                Price increments:{' '}
                {instrument.price_increment_ranges?.length
                  ? `${instrument.price_increment_ranges
                      .map((range) => `${range.start}–${range.end} by ${range.step}`)
                      .join('; ')} · range boundaries are not treated as validated ticks`
                  : instrument.price_increment_ranges !== undefined &&
                      instrument.price_increment_ranges !== null
                    ? 'No ranges reported; price constraints unresolved'
                    : instrument.tick_size
                      ? `tick ${instrument.tick_size}`
                      : 'Not reported'}
                {' · '}Quantity step: {instrument.quantity_step ?? 'not reported'} · minimum:{' '}
                {instrument.minimum_quantity ?? 'not reported'} · minimum notional:{' '}
                {instrument.minimum_notional ?? 'not reported'}
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
            {evidence.data.normalized?.record_kind === 'source_failure' && (
              <div className="fr-evidence-diagnostic" role="status">
                <strong>{evidence.data.normalized.error_code ?? 'Source response failure'}</strong>
                <span>{evidence.data.normalized.message ?? 'Source response was rejected.'}</span>
                {evidence.data.normalized.response_rejection && (
                  <span>
                    Rejected at {label(evidence.data.normalized.response_rejection.rejection_stage)}{' '}
                    · body cap{' '}
                    {evidence.data.normalized.response_rejection.response_body_limit_bytes} bytes ·
                    declared length{' '}
                    {evidence.data.normalized.response_rejection.declared_content_length_bytes ??
                      'not supplied'}{' '}
                    · bytes yielded{' '}
                    {evidence.data.normalized.response_rejection.bytes_yielded_at_rejection}
                  </span>
                )}
              </div>
            )}
            <span>Observation ID · {evidence.data.observation_id}</span>
            <span>
              {evidence.data.raw.http_status} · {evidence.data.raw.request_url}
            </span>
            <span>
              Request start {time(evidence.data.raw.request_started_at_utc)} · response received{' '}
              {time(evidence.data.raw.received_at_utc)}
            </span>
            <span>
              HTTP request/body elapsed (monotonic):{' '}
              {evidence.data.raw.request_elapsed_monotonic_ns == null
                ? 'Not recorded'
                : `${(evidence.data.raw.request_elapsed_monotonic_ns / 1_000_000).toFixed(3)} ms`}
            </span>
            <span>Capture row SHA-256 · {evidence.data.row_sha256}</span>
            {evidence.data.raw.raw_body_state === 'not_captured_after_size_limit' ? (
              <div className="fr-evidence-body-omitted" role="note">
                Response body not captured because it exceeded the configured size limit. The raw
                SHA-256 below identifies the empty stored body, not the rejected source response.
                <span>Stored raw SHA-256 · {evidence.data.raw_sha256}</span>
              </div>
            ) : (
              <pre>{evidence.data.raw.raw_body}</pre>
            )}
          </div>
        ) : null)}
    </details>
  );
}

function ProbeFailureEvidence({ error }: { error: Error }) {
  let detail: {
    code?: string;
    message?: string;
    diagnostic_observation_ids?: string[];
    diagnostic_persistence_error?: string | null;
  } | null = null;
  try {
    const parsed: unknown = JSON.parse(error.message);
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      detail = parsed as {
        code?: string;
        message?: string;
        diagnostic_observation_ids?: string[];
        diagnostic_persistence_error?: string | null;
      };
    }
  } catch {
    // Non-JSON errors keep their original user-facing message.
  }
  const observationIds = Array.isArray(detail?.diagnostic_observation_ids)
    ? detail.diagnostic_observation_ids.filter(
        (value): value is string => typeof value === 'string' && /^[0-9a-f]{64}$/.test(value),
      )
    : [];
  const message = detail
    ? `${detail.code ?? 'Source probe failed'}: ${detail.message ?? error.message}`
    : error.message;
  return (
    <div className="fr-probe-failure">
      <InlineError message={message} />
      {detail?.diagnostic_persistence_error && (
        <small role="alert">
          Failure metadata could not be saved: {detail.diagnostic_persistence_error}
        </small>
      )}
      {observationIds.map((observationId) => (
        <div className="fr-probe-failure-evidence" key={observationId}>
          <small>Saved diagnostic observation · {observationId}</small>
          <EvidenceDisclosure observationId={observationId} />
        </div>
      ))}
    </div>
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
type FiniteCollectionMutation = UseMutationResult<
  FiniteCollectionResponse,
  Error,
  { venue: Venue; includePublicTrades: boolean },
  unknown
>;
type ResumeCollectionMutation = UseMutationResult<
  FiniteCollectionResponse,
  Error,
  { venue: Venue; runId: string },
  unknown
>;
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
  operationAdmission,
  refreshSourceStatus,
  sourceStatusRefreshing,
  markets,
  probe,
  finiteCollection,
  collectionRuns,
  collectionRunsLoading,
  collectionRunsError,
  collectionRunsBeforeRunId,
  loadOlderCollectionRuns,
  showNewestCollectionRuns,
  latestCollectionResult,
  resumeCollection,
  multivariateProbe,
  loading,
  error,
}: {
  sources: Source[];
  operationAdmission?: SourceOperationAdmission;
  refreshSourceStatus: () => Promise<unknown>;
  sourceStatusRefreshing: boolean;
  markets: Record<string, number>;
  probe: ProbeMutation;
  finiteCollection: FiniteCollectionMutation;
  collectionRuns?: CollectionRunsResponse;
  collectionRunsLoading: boolean;
  collectionRunsError?: string;
  collectionRunsBeforeRunId: string | null;
  loadOlderCollectionRuns: (runId: string) => void;
  showNewestCollectionRuns: () => void;
  latestCollectionResult: FiniteCollectionResponse | null;
  resumeCollection: ResumeCollectionMutation;
  multivariateProbe: KalshiMultivariateProbe;
  loading: boolean;
  error?: string;
}) {
  const [includeCollectionTrades, setIncludeCollectionTrades] = useState<
    Partial<Record<Venue, boolean>>
  >({});
  const [multivariateFilterType, setMultivariateFilterType] = useState<
    'series_ticker' | 'collection_ticker' | 'event_ticker'
  >('series_ticker');
  const [multivariateFilterValue, setMultivariateFilterValue] = useState('');
  const nextCollectionRunCursor = collectionRuns?.next_before_run_id ?? null;
  return (
    <section className="fr-source-cards">
      {!loading && !error && (
        <div className="fr-card fr-collection-history-pager">
          <div>
            <strong>Finite collection history</strong>
            <small>
              Read-only pages of up to {collectionRuns?.limit ?? 20} locally hash-verified runs. The
              run ID cursor keeps older pages stable when a new run is added.
              {collectionRunsLoading ? ' Loading page…' : ''}
            </small>
            {operationAdmission && (
              <small role="note">
                Public captures allow at most {operationAdmission.max_concurrent_source_operations}{' '}
                concurrent source operations in this API process, with one active operation per
                venue. Contention waits up to {operationAdmission.maximum_acquire_wait_ms} ms, then
                returns HTTP {operationAdmission.overload_status} without queueing or making a
                source request.
              </small>
            )}
            {operationAdmission?.runtime_snapshot && (
              <small role="status">
                Runtime snapshot at {time(operationAdmission.runtime_snapshot.sampled_at_utc)}:{' '}
                {operationAdmission.runtime_snapshot.active_operations} of{' '}
                {operationAdmission.max_concurrent_source_operations} slots active;{' '}
                {operationAdmission.runtime_snapshot.admitted_operations_total} admitted and{' '}
                {operationAdmission.runtime_snapshot.busy_rejections_total} contention rejections
                since this API router started (same-venue{' '}
                {operationAdmission.runtime_snapshot.busy_rejections_by_scope.venue},
                shared-capacity{' '}
                {operationAdmission.runtime_snapshot.busy_rejections_by_scope.capacity}). Active
                venues:{' '}
                {operationAdmission.runtime_snapshot.active_venues.length
                  ? operationAdmission.runtime_snapshot.active_venues.join(', ')
                  : 'none'}
                .
              </small>
            )}
          </div>
          <div className="fr-collection-history-actions">
            {operationAdmission && (
              <button
                className="fr-inspect-button"
                disabled={sourceStatusRefreshing}
                onClick={() => void refreshSourceStatus()}
              >
                {sourceStatusRefreshing ? 'Refreshing source status…' : 'Refresh source status'}
              </button>
            )}
            {collectionRunsBeforeRunId && (
              <button
                className="fr-inspect-button"
                disabled={collectionRunsLoading}
                onClick={showNewestCollectionRuns}
              >
                Newest runs
              </button>
            )}
            {nextCollectionRunCursor && (
              <button
                className="fr-inspect-button"
                disabled={collectionRunsLoading}
                onClick={() => loadOlderCollectionRuns(nextCollectionRunCursor)}
              >
                Load older runs
              </button>
            )}
          </div>
        </div>
      )}
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
          const collectionAvailable =
            source.public_probe_enabled &&
            !source.probe_policy_block_reason &&
            source.capabilities.some(
              (item) => item.capability === 'market_discovery' && item.supported,
            );
          const publicTradesSupported = source.capabilities.some(
            (item) => item.capability === 'public_trades' && item.supported,
          );
          const collectionRun =
            latestCollectionResult?.venue === source.venue ? latestCollectionResult : null;
          return (
            <article className="fr-card fr-venue-card" key={source.venue}>
              <div className="fr-venue-top">
                <VenuePill venue={source.venue} />
                <StateBadge state={source.health.state} />
              </div>
              <h2>{venueLabel(source.venue)}</h2>
              <code>{source.adapter_version}</code>
              <p className="fr-copy">
                {source.venue === 'kraken' ||
                source.venue === 'coinbase_exchange' ||
                source.venue === 'gemini_spot'
                  ? 'Spot instruments provide context for event research. A spot price is not a prediction-contract payoff.'
                  : source.venue === 'kalshi'
                    ? 'Public event metadata and order books are retained with native rules and multivariate-event markers.'
                    : 'The existing Polymarket schema is adapted while preserving its legacy source identifiers and fee validation.'}
                {source.venue === 'coinbase_exchange' && (
                  <small className="fr-source-terms-note">
                    Source use remains held pending validated permission and intended-scope review;
                    terms acknowledgment is not authorization. Maker-side trade fields are not
                    treated as aggressor-side.
                  </small>
                )}
                {source.venue === 'gemini_spot' && (
                  <small className="fr-source-terms-note">
                    Source use is held pending the applicable residency-specific agreement and
                    intended-scope review. The current hold prevents probes and stored-data
                    research.
                  </small>
                )}
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
                {probe.isError && probe.variables?.venue === source.venue && (
                  <InlineError message={probe.error.message} />
                )}
              </div>
              <div className="fr-probe-row fr-collection-row">
                <button
                  className="fr-action"
                  disabled={!collectionAvailable || finiteCollection.isPending}
                  onClick={() =>
                    finiteCollection.mutate({
                      venue: source.venue,
                      includePublicTrades: includeCollectionTrades[source.venue] ?? false,
                    })
                  }
                >
                  <Database size={14} />
                  {finiteCollection.isPending && finiteCollection.variables?.venue === source.venue
                    ? 'Saving finite capture…'
                    : collectionAvailable
                      ? 'Capture finite batch with checkpoints'
                      : source.probe_policy_block_reason
                        ? 'Collection held by source policy'
                        : 'Finite collection disabled'}
                </button>
                <small>
                  One explicit read-only request: up to 3 markets, 1 book, 5 levels, optional public
                  trades from 1 market, 4 MiB of evidence, and 30 seconds. It writes a restart-safe
                  local run journal and starts no Arena job or background collector. No credentials
                  or orders are used.
                </small>
                {publicTradesSupported && (
                  <label className="fr-collection-trades-toggle">
                    <input
                      type="checkbox"
                      checked={includeCollectionTrades[source.venue] ?? false}
                      disabled={!collectionAvailable || finiteCollection.isPending}
                      onChange={(event) =>
                        setIncludeCollectionTrades((current) => ({
                          ...current,
                          [source.venue]: event.currentTarget.checked,
                        }))
                      }
                    />
                    <span>Include up to 10 public trade prints from 1 discovered market</span>
                  </label>
                )}
                {finiteCollection.isError && finiteCollection.variables?.venue === source.venue && (
                  <InlineError message={finiteCollection.error.message} />
                )}
                {collectionRun && (
                  <div className="fr-collection-result" role="status">
                    <strong>Finite capture {label(collectionRun.collection_run.state)}</strong>
                    <span>
                      {count(collectionRun.collection_run.market_count)} market(s) ·{' '}
                      {count(collectionRun.collection_run.book_count)} book(s) ·{' '}
                      {count(collectionRun.collection_run.failed_book_count)} failed book(s) ·{' '}
                      {count(collectionRun.collection_run.trade_count)} trade print(s) ·{' '}
                      {count(collectionRun.collection_run.failed_trade_count)} failed trade
                      batch(es)
                    </span>
                    <span>
                      {count(collectionRun.adapter_request_count)} total adapter requests across run
                      · at most {count(collectionRun.adapter_request_upper_bound_per_attempt)} per
                      attempt · run {shortHash(collectionRun.collection_run.run_id)}
                    </span>
                    <small>
                      Health is adapter-local checkpoint state; it does not establish continuous
                      venue availability or account eligibility.
                    </small>
                    {collectionRun.collection_run.failures.slice(0, 3).map((failure, index) => (
                      <small key={`${failure.code}-${index}`}>
                        {failure.code}: {failure.message}
                      </small>
                    ))}
                  </div>
                )}
              </div>
              <div className="fr-probe-row fr-collection-history">
                <strong>Finite collection run checkpoints</strong>
                <small>
                  Read-only list of hash-verified local checkpoints. Resume is a separate explicit
                  public-data request and requires the source configuration to still match.
                </small>
                {collectionRunsLoading ? (
                  <small>Loading verified collection history…</small>
                ) : collectionRunsError ? (
                  <InlineError message={collectionRunsError} />
                ) : (
                  (collectionRuns?.items ?? [])
                    .filter((run) => run.venue === source.venue)
                    .map((run) => (
                      <article className="fr-collection-history-item" key={run.run_id}>
                        <div className="fr-collection-history-head">
                          <StateBadge state={run.state} />
                          <span>{time(run.updated_at_utc)}</span>
                        </div>
                        <span>
                          {count(run.market_count)} market(s) · {count(run.book_count)} book(s) ·{' '}
                          {count(run.failed_book_count)} failed book(s) · {count(run.request_count)}{' '}
                          recorded adapter request(s) · {count(run.trade_count ?? 0)} trade print(s)
                          · {count(run.failed_trade_count ?? 0)} failed trade batch(es)
                        </span>
                        <small>
                          Run {shortHash(run.run_id)} · checkpoint {run.checkpoint_sequence} ·{' '}
                          {shortHash(run.checkpoint_sha256)} · {run.adapter_version} · health{' '}
                          {run.source_health_state ?? 'not recorded'} · {run.failure_count}{' '}
                          failure(s)
                        </small>
                        {run.resumable && (
                          <button
                            className="fr-inspect-button"
                            disabled={!collectionAvailable || resumeCollection.isPending}
                            onClick={() =>
                              resumeCollection.mutate({ venue: source.venue, runId: run.run_id })
                            }
                          >
                            {resumeCollection.isPending &&
                            resumeCollection.variables?.runId === run.run_id
                              ? 'Resuming…'
                              : `Resume collection run ${shortHash(run.run_id)}`}
                          </button>
                        )}
                        {!run.resumable &&
                          !['completed', 'partial', 'failed'].includes(run.state) && (
                            <small>
                              Resume unavailable:{' '}
                              {run.resume_block_reason ?? 'current source checks failed.'}
                            </small>
                          )}
                      </article>
                    ))
                )}
                {resumeCollection.isError && resumeCollection.variables?.venue === source.venue && (
                  <InlineError message={resumeCollection.error.message} />
                )}
                {!collectionRunsLoading &&
                  !collectionRunsError &&
                  (collectionRuns?.items ?? []).every((run) => run.venue !== source.venue) && (
                    <small>No verified finite collection runs for this source on this page.</small>
                  )}
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
                    <ProbeFailureEvidence error={multivariateProbe.error} />
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
  const knownVenue =
    venue === 'polymarket' ||
    venue === 'kalshi' ||
    venue === 'kraken' ||
    venue === 'coinbase_exchange' ||
    venue === 'gemini_spot';
  const venueClass = knownVenue ? venue : 'unknown';
  const icon =
    venue === 'coinbase_exchange'
      ? 'C'
      : venue === 'kraken'
        ? 'K'
        : venue === 'gemini_spot'
          ? 'G'
          : venue === 'kalshi'
            ? 'Ka'
            : venue === 'polymarket'
              ? 'P'
              : '?';
  return (
    <span className={`fr-venue-pill ${venueClass}`}>
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
        maxLength={120}
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

const MAX_RELATIONSHIP_TERM_DETAIL_INSTRUMENTS = 32;
const MAX_RELATIONSHIP_TERM_DETAIL_PAYOUTS = 32;
const MAX_RELATIONSHIP_TERM_DETAIL_STATES = 32;

function RelationshipContractTerms({
  side,
  market,
}: {
  side: 'Left' | 'Right';
  market: Market | undefined;
}) {
  const payoffStateIds = market?.payoff.state_ids ?? [];
  const visiblePayoffStateIds = payoffStateIds.slice(0, MAX_RELATIONSHIP_TERM_DETAIL_STATES);
  const instruments = market?.instruments ?? [];
  const visibleInstruments = instruments.slice(0, MAX_RELATIONSHIP_TERM_DETAIL_INSTRUMENTS);

  return (
    <section className="fr-contract-terms" aria-label={`${side} recorded contract terms`}>
      {market ? (
        <>
          <div className="fr-contract-terms-head">
            <div>
              <span className="fr-kicker">{side} source contract</span>
              <VenuePill venue={market.venue} />
            </div>
            <h4>{market.title}</h4>
            <code>{market.canonical_id}</code>
          </div>
          <dl>
            <div>
              <dt>Native market ID</dt>
              <dd>
                <code>{market.native_market_id}</code>
              </dd>
            </div>
            <div>
              <dt>Type / lifecycle</dt>
              <dd>
                {label(market.market_kind)} · {label(market.lifecycle)}
              </dd>
            </div>
            <div>
              <dt>Payoff states</dt>
              <dd>
                {visiblePayoffStateIds.map(label).join(' · ') || 'Not reported'}
                {payoffStateIds.length > visiblePayoffStateIds.length && (
                  <small>
                    {payoffStateIds.length - visiblePayoffStateIds.length} additional payoff states
                    omitted from this view.
                  </small>
                )}
              </dd>
            </div>
            <div>
              <dt>Payoff evidence</dt>
              <dd>
                {market.payoff.verified ? 'Verified' : 'Not verified'} ·{' '}
                {market.payoff.exhaustive ? 'exhaustive' : 'exhaustiveness unestablished'}
              </dd>
            </div>
            <div>
              <dt>Payout / settlement identity</dt>
              <dd>
                Payout currency {market.payoff.payout_currency ?? 'not reported'} · market
                settlement {market.settlement_asset ?? 'not reported'} · payoff settlement{' '}
                {market.payoff.settlement_asset ?? 'not reported'} · market identity{' '}
                {settlementIdentityLabel(market.settlement_asset_identity)} · payoff identity{' '}
                {settlementIdentityLabel(market.payoff.settlement_asset_identity)}
              </dd>
            </div>
            <div>
              <dt>Resolution authority</dt>
              <dd>{market.resolution.authority ?? 'Not reported'}</dd>
            </div>
            <div>
              <dt>Close / settle</dt>
              <dd>
                {market.resolution.closes_at_utc ?? 'Not reported'} /{' '}
                {market.resolution.settles_at_utc ?? 'Not reported'}
              </dd>
            </div>
            <div>
              <dt>Fee metadata</dt>
              <dd>
                {label(market.fees.status)} · fixed {market.fees.fixed_fee ?? 'not reported'} · rate{' '}
                {market.fees.rate ?? 'not reported'} · multiplier{' '}
                {market.fees.fee_multiplier ?? 'not reported'} ·{' '}
                {market.fees.applies_to ?? 'applicability not reported'}
              </dd>
            </div>
          </dl>
          <details className="fr-contract-source-details">
            <summary>Rules, instruments, and source provenance</summary>
            <div className="fr-contract-rule">
              <strong>Primary resolution rule</strong>
              <p>{market.resolution.primary_rule ?? 'Not reported'}</p>
              {market.resolution.secondary_rule && (
                <>
                  <strong>Secondary resolution rule</strong>
                  <p>{market.resolution.secondary_rule}</p>
                </>
              )}
              <strong>Instrument definitions</strong>
              {instruments.length > visibleInstruments.length && (
                <p className="fr-contract-term-limit-note">
                  Showing the first {visibleInstruments.length} of {instruments.length} instruments.
                  Remaining captured terms are retained in the saved market record.
                </p>
              )}
              <ul>
                {visibleInstruments.map((instrument) => {
                  const payouts = instrument.payouts ?? [];
                  const visiblePayouts = payouts.slice(0, MAX_RELATIONSHIP_TERM_DETAIL_PAYOUTS);
                  return (
                    <li key={instrument.canonical_id ?? instrument.native_instrument_id}>
                      <span>
                        {instrument.label} · {instrument.outcome_id ?? 'outcome not identified'} ·{' '}
                        <code>{instrument.native_instrument_id}</code>
                      </span>
                      <span className="fr-contract-instrument-meta">
                        {[
                          instrument.quantity_unit
                            ? `quantity unit ${label(instrument.quantity_unit)}`
                            : 'quantity unit not reported',
                          instrument.price_currency
                            ? `price currency ${instrument.price_currency}`
                            : 'price currency not reported',
                          `price currency identity ${settlementIdentityLabel(instrument.price_currency_identity)}`,
                          instrument.tick_size
                            ? `tick ${instrument.tick_size}`
                            : 'tick size not reported',
                          instrument.price_increment_ranges?.length
                            ? `price increments ${instrument.price_increment_ranges
                                .map(({ start, end, step }) => `${start}–${end} by ${step}`)
                                .join(', ')}`
                            : 'price increments not reported',
                          instrument.quantity_step
                            ? `quantity step ${instrument.quantity_step}`
                            : 'quantity step not reported',
                          instrument.minimum_quantity
                            ? `minimum quantity ${instrument.minimum_quantity}`
                            : 'minimum quantity not reported',
                          instrument.minimum_notional
                            ? `minimum notional ${instrument.minimum_notional}`
                            : 'minimum notional not reported',
                        ]
                          .filter(Boolean)
                          .join(' · ')}
                      </span>
                      <span className="fr-contract-payout-vector">
                        Payout by state:{' '}
                        {visiblePayouts.length
                          ? visiblePayouts
                              .map(({ state_id, amount }) => `${state_id}: ${amount}`)
                              .join(' · ')
                          : 'not reported'}
                        {payouts.length > visiblePayouts.length && (
                          <small>
                            {payouts.length - visiblePayouts.length} additional payout states
                            omitted from this view.
                          </small>
                        )}
                      </span>
                    </li>
                  );
                })}
              </ul>
              <strong>Payoff verification basis</strong>
              <p>{market.payoff.verification_basis || 'Not reported'}</p>
              <strong>Fee schedule details</strong>
              <p>
                Version {market.fees.version ?? 'not reported'} · applies to{' '}
                {market.fees.applies_to ?? 'not reported'} · fixed fee{' '}
                {market.fees.fixed_fee ?? 'not reported'} · rate{' '}
                {market.fees.rate ?? 'not reported'}
                {' · '}multiplier {market.fees.fee_multiplier ?? 'not reported'} · formula{' '}
                {market.fees.formula ?? 'not reported'}
              </p>
              <p>
                Fee currency {market.fees.fee_currency ?? 'not reported'} · identity{' '}
                {settlementIdentityLabel(market.fees.fee_currency_identity)}
              </p>
              <p>
                Effective {market.fees.effective_at_utc ?? 'not reported'} · expires{' '}
                {market.fees.expires_at_utc ?? 'not reported'} · evidence observed{' '}
                {market.fees.evidence_observed_at_utc ?? 'not reported'}
              </p>
              <p>
                Fee evidence SHA-256 {market.fees.evidence_sha256 ?? 'not reported'} · observation{' '}
                {market.fees.evidence_observation_ids?.join(', ') || 'not reported'}
              </p>
              <p>
                Source {market.fees.source_url ?? 'not reported'} ·{' '}
                {market.fees.note || 'No fee note recorded'}
              </p>
              <strong>Source record</strong>
              <p>
                Received {market.provenance.response_received_at_utc} · observation{' '}
                <code>{market.provenance.observation_id}</code>
              </p>
              <p>
                Raw response SHA-256 <code>{market.provenance.raw_sha256}</code>
              </p>
              <p>
                Resolution evidence SHA-256{' '}
                <code>{market.resolution.evidence_sha256 ?? 'not reported'}</code>
              </p>
              <p>
                Resolution fingerprint{' '}
                <code>{market.resolution.resolution_fingerprint ?? 'not reported'}</code>
              </p>
            </div>
          </details>
        </>
      ) : (
        <>
          <span className="fr-kicker">{side} source contract</span>
          <p>Market details are outside the loaded graph window.</p>
        </>
      )}
    </section>
  );
}

function CandidateCard({
  candidate,
  jointStateMapping,
}: {
  candidate: Candidate;
  jointStateMapping?: JointStateMapping;
}) {
  const [virtualBalances, setVirtualBalances] = useState<Record<string, string>>({});
  const [carryRates, setCarryRates] = useState<Record<string, string>>({});
  const [carryReleaseDelays, setCarryReleaseDelays] = useState<Record<string, string>>({});
  const [fundingKinds, setFundingKinds] = useState<Record<string, SettlementAssetIdentity['kind']>>(
    {},
  );
  const [fundingCodes, setFundingCodes] = useState<Record<string, string>>({});
  const [fundingNetworks, setFundingNetworks] = useState<Record<string, string>>({});
  const [fundingAssetReferences, setFundingAssetReferences] = useState<Record<string, string>>({});
  const [fundingBalances, setFundingBalances] = useState<Record<string, string>>({});
  const [fundingRates, setFundingRates] = useState<Record<string, string>>({});
  const [fundingFees, setFundingFees] = useState<Record<string, string>>({});
  const carryMutation = useMutation({
    mutationFn: (body: {
      run_id: string;
      run_sha256: string;
      candidate_id: string;
      annual_rate_bps_by_venue: Record<string, string>;
      post_settlement_delay_seconds_by_venue: Record<string, string>;
    }) =>
      api<CapitalCarrySensitivity>('/frontier/opportunities/capital-carry', {
        method: 'POST',
        body: JSON.stringify(body),
      }),
  });
  const carryVenues = Object.keys(candidate.capital_by_venue).sort();
  const fundingCurrencyMutation = useMutation({
    mutationFn: (body: {
      run_id: string;
      run_sha256: string;
      candidate_id: string;
      venues: {
        venue: string;
        funding_currency_identity: SettlementAssetIdentity;
        balance_amount: string;
        target_units_per_funding_unit: string;
        conversion_fee_bps: string;
      }[];
    }) =>
      api<FundingCurrencySensitivity>('/frontier/opportunities/funding-currency-sensitivity', {
        method: 'POST',
        body: JSON.stringify(body),
      }),
  });
  const fundingIdentityFor = (venue: string): SettlementAssetIdentity | null => {
    const target = candidate.capital_currency_identity;
    if (!target) return null;
    const kind = fundingKinds[venue] ?? target.kind;
    return {
      schema_version: 1,
      kind,
      code: (fundingCodes[venue] ?? target.code).trim().toUpperCase(),
      network_id:
        kind === 'fiat' ? null : (fundingNetworks[venue] ?? target.network_id ?? '').trim(),
      asset_reference:
        kind === 'fiat'
          ? null
          : (fundingAssetReferences[venue] ?? target.asset_reference ?? '').trim(),
    };
  };
  const fundingIdentityMatches = (
    left: SettlementAssetIdentity | null | undefined,
    right: SettlementAssetIdentity | null | undefined,
  ) => Boolean(left && right && sameSettlementIdentity(left, right));
  const fundingInputsValid =
    carryVenues.length > 0 &&
    carryVenues.every((venue) => {
      const identity = fundingIdentityFor(venue);
      const target = candidate.capital_currency_identity;
      const sameIdentity = fundingIdentityMatches(identity, target);
      const balance = fundingBalances[venue] ?? '';
      const rate = fundingRates[venue] ?? (sameIdentity ? '1' : '');
      const fee = fundingFees[venue] ?? (sameIdentity ? '0' : '');
      const validCode =
        identity?.kind === 'fiat'
          ? /^[A-Z]{3}$/.test(identity.code)
          : /^[A-Z0-9]{2,16}$/.test(identity?.code ?? '');
      const validNamespace =
        identity?.kind === 'fiat' ||
        Boolean(
          identity?.network_id &&
          identity.asset_reference &&
          !/\s/.test(identity.network_id) &&
          !/\s/.test(identity.asset_reference),
        );
      const validBalance = Boolean(
        /^(?:0|[1-9][0-9]{0,35})(?:\.[0-9]{1,36})?$/.test(balance) && parseExactMoney(balance),
      );
      const validRate = /^(?:0|[1-9][0-9]{0,8})(?:\.[0-9]{1,12})?$/.test(rate) && Number(rate) > 0;
      const validFee = /^(?:0|[1-9][0-9]{0,4})(?:\.[0-9]{1,6})?$/.test(fee) && Number(fee) < 10000;
      return Boolean(
        target &&
        identity &&
        validCode &&
        validNamespace &&
        validBalance &&
        (sameIdentity || (validRate && validFee)),
      );
    });
  const carryInputsValid =
    carryVenues.length > 0 &&
    carryVenues.every((venue) => {
      const rate = carryRates[venue] ?? '';
      const delay = carryReleaseDelays[venue] ?? '0';
      return (
        rate.length <= 16 &&
        /^(?:0|[1-9][0-9]{0,5})(?:\.[0-9]{1,6})?$/.test(rate) &&
        delay.length <= 8 &&
        /^(?:0|[1-9][0-9]{0,7})$/.test(delay) &&
        Number(delay) <= 31_536_000
      );
    });
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
  const describePartialFillOutcome = (
    outcome: NonNullable<Candidate['partial_fill_grid_sensitivity']>['worst_before_fees'],
  ) =>
    outcome.leg_fills
      .map((fill) => {
        const percent = Math.round(Number(fill.fill_fraction) * 100);
        return `${describeFillLeg(fill.leg_id)}: ${percent}% (${fill.filled_quantity})`;
      })
      .join('; ');
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
      {candidate.joint_state_mapping_id && (
        <section className="fr-joint-state-map" aria-label="External joint-state assertion">
          <div>
            <span className="fr-kicker">CONDITIONAL CROSS-MARKET BASIS</span>
            <h4>External joint-state assertion</h4>
          </div>
          <p>
            Payoffs below are evaluated over this asserted state map. The map’s completeness and
            semantic equivalence are unverified, so the arithmetic audit does not certify a
            mathematical inconsistency or executable opportunity.
          </p>
          <dl>
            <div>
              <dt>Mapping SHA-256</dt>
              <dd>
                <code>{candidate.joint_state_mapping_id}</code>
              </dd>
            </div>
            <div>
              <dt>Market set</dt>
              <dd>
                {jointStateMapping?.market_ids.join(' · ') ??
                  candidate.market_ids?.join(' · ') ??
                  'Pinned to replay manifest'}
              </dd>
            </div>
            <div>
              <dt>External assertion</dt>
              <dd>
                {jointStateMapping?.external_assertion_id ?? 'Details not in loaded replay window'}
              </dd>
            </div>
            <div>
              <dt>Evidence observations</dt>
              <dd>
                {jointStateMapping
                  ? `${jointStateMapping.evidence_observation_ids.length} pinned source observations`
                  : 'Pinned with the source replay'}
              </dd>
            </div>
            <div>
              <dt>Assertion time</dt>
              <dd>
                {jointStateMapping
                  ? new Date(jointStateMapping.asserted_at_utc).toLocaleString()
                  : 'Pinned with the source replay'}
              </dd>
            </div>
          </dl>
          {jointStateMapping && (
            <details>
              <summary>
                Inspect the asserted projections · {jointStateMapping.joint_state_ids.length} joint
                states
              </summary>
              <div className="fr-table-wrap">
                <table className="fr-table">
                  <thead>
                    <tr>
                      <th>Asserted joint state</th>
                      {jointStateMapping.market_ids.map((marketId) => (
                        <th key={marketId}>{marketId}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {jointStateMapping.joint_state_ids.map((state) => (
                      <tr key={state}>
                        <th scope="row">{label(state)}</th>
                        {jointStateMapping.market_ids.map((marketId) => (
                          <td key={`${marketId}-${state}`}>
                            {label(
                              jointStateMapping.state_by_market[marketId]?.[state] ?? 'missing',
                            )}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          )}
        </section>
      )}
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
                const capitalIdentityFields = settlementIdentityTuple(capitalIdentity);
                const capitalIdentityLabel = capitalIdentityFields
                  ? settlementIdentityLabel(capitalIdentity)
                  : null;
                const exactLegUnits = Boolean(
                  capitalIdentityFields &&
                  legs.length > 0 &&
                  legs.every(
                    (leg) =>
                      leg.quote_currency === capitalIdentityFields[2] &&
                      sameSettlementIdentity(leg.quote_currency_identity, capitalIdentity),
                  ),
                );
                const currencyComplete = Boolean(capitalIdentityFields && exactLegUnits);
                const currency =
                  currencyComplete && capitalIdentityFields && capitalIdentityLabel
                    ? `${capitalIdentityFields[2]} (${capitalIdentityLabel})`
                    : null;
                const balanceKey = JSON.stringify([
                  venue,
                  capitalIdentityFields?.[0] ?? null,
                  capitalIdentityFields?.[1] ?? null,
                  capitalIdentityFields?.[2] ?? null,
                  capitalIdentityFields?.[3] ?? null,
                  capitalIdentityFields?.[4] ?? null,
                ]);
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
                  <div className="fr-capital-row" key={`${candidate.candidate_id}-${balanceKey}`}>
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
          <div className="fr-capital-carry">
            <div>
              <span className="fr-kicker">Settlement duration sensitivity</span>
              <h4>Virtual capital duration assumptions</h4>
            </div>
            <p>
              Enter a user-supplied annual rate and additional release delay for each venue. The API
              uses this candidate’s pinned market observations and source-marked verified settlement
              metadata, then holds venue capital to the latest settlement plus the assumed delay and
              independently rechecks the arithmetic. Delay is a scenario assumption, not a promise
              about actual capital availability. This does not estimate an exchange charge or change
              the candidate state.
            </p>
            {carryVenues.map((venue) => (
              <div
                className="fr-capital-carry-inputs"
                key={`${candidate.candidate_id}-carry-${venue}`}
              >
                <label>
                  <span>{venueLabel(venue)} annual carry rate (bps)</span>
                  <input
                    aria-label={`${venueLabel(venue)} annual carry rate in basis points`}
                    inputMode="decimal"
                    maxLength={16}
                    value={carryRates[venue] ?? ''}
                    onChange={(event) => {
                      setCarryRates((current) => ({ ...current, [venue]: event.target.value }));
                      carryMutation.reset();
                    }}
                  />
                </label>
                <label>
                  <span>{venueLabel(venue)} additional post-settlement delay (seconds)</span>
                  <input
                    aria-label={`${venueLabel(venue)} post-settlement release delay in seconds`}
                    inputMode="numeric"
                    maxLength={8}
                    value={carryReleaseDelays[venue] ?? '0'}
                    onChange={(event) => {
                      setCarryReleaseDelays((current) => ({
                        ...current,
                        [venue]: event.target.value,
                      }));
                      carryMutation.reset();
                    }}
                  />
                </label>
              </div>
            ))}
            {!candidate.source_run_id || !candidate.source_run_sha256 ? (
              <small role="status">
                This older candidate response does not include a pinned research run identity.
                Reload the current Frontier API before evaluating carry.
              </small>
            ) : (
              <button
                className="fr-action"
                type="button"
                disabled={!carryInputsValid || carryMutation.isPending}
                onClick={() =>
                  carryMutation.mutate({
                    run_id: candidate.source_run_id!,
                    run_sha256: candidate.source_run_sha256!,
                    candidate_id: candidate.candidate_id,
                    annual_rate_bps_by_venue: Object.fromEntries(
                      carryVenues.map((venue) => [venue, carryRates[venue]]),
                    ),
                    post_settlement_delay_seconds_by_venue: Object.fromEntries(
                      carryVenues.map((venue) => [venue, carryReleaseDelays[venue] ?? '0']),
                    ),
                  })
                }
              >
                {carryMutation.isPending ? 'Recomputing…' : 'Evaluate settlement carry'}
              </button>
            )}
            {carryMutation.isError && <InlineError message={carryMutation.error.message} />}
            {carryMutation.data &&
              carryMutation.data.run_id === candidate.source_run_id &&
              carryMutation.data.run_sha256 === candidate.source_run_sha256 &&
              carryMutation.data.candidate_id === candidate.candidate_id &&
              carryMutation.data.venues.every(
                (item) =>
                  item.annual_rate_bps === carryRates[item.venue] &&
                  item.post_settlement_delay_seconds ===
                    Number(carryReleaseDelays[item.venue] ?? '0'),
              ) && (
                <div
                  className="fr-capital-carry-result"
                  aria-label="Capital carry sensitivity result"
                >
                  <div className="fr-candidate-audit-head">
                    <h5>Hypothetical sensitivity</h5>
                    <StateBadge state={carryMutation.data.audit.disposition} />
                  </div>
                  <p>{carryMutation.data.audit.message}</p>
                  <dl>
                    <div>
                      <dt>Total modeled carry</dt>
                      <dd title={carryMutation.data.total_carry_cost}>
                        {money(carryMutation.data.total_carry_cost)}{' '}
                        {settlementIdentityLabel(carryMutation.data.capital_currency_identity)}
                      </dd>
                    </div>
                    <div>
                      <dt>Worst gross result after carry</dt>
                      <dd title={carryMutation.data.worst_case_gross_pnl_after_carry ?? undefined}>
                        {money(carryMutation.data.worst_case_gross_pnl_after_carry)}
                      </dd>
                    </div>
                    <div>
                      <dt>Worst net result after carry</dt>
                      <dd title={carryMutation.data.worst_case_net_pnl_after_carry ?? undefined}>
                        {money(carryMutation.data.worst_case_net_pnl_after_carry)}
                      </dd>
                    </div>
                    <div>
                      <dt>Classification</dt>
                      <dd>{carryMutation.data.candidate_classification} · unchanged</dd>
                    </div>
                  </dl>
                  {carryMutation.data.venues.map((item) => (
                    <p key={`${candidate.candidate_id}-carry-result-${item.venue}`}>
                      <strong>{venueLabel(item.venue)}</strong>: {money(item.capital)} capital at{' '}
                      {item.annual_rate_bps} bps for approximately{' '}
                      {item.post_settlement_delay_seconds}s additional delay after settlement and{' '}
                      {(Number(item.duration_seconds) / 86400).toLocaleString(undefined, {
                        maximumFractionDigits: 3,
                      })}{' '}
                      days; capital release {time(item.capital_released_at_utc)}; carry{' '}
                      {money(item.carry_cost)}. Pinned source records:{' '}
                      {item.settlement_evidence
                        .map(
                          (evidence) =>
                            `${shortHash(evidence.observation_id)} · row ${shortHash(evidence.observation_row_sha256)} · raw ${shortHash(evidence.raw_sha256)} · resolution ${shortHash(evidence.resolution_evidence_sha256)} · fingerprint ${evidence.resolution_fingerprint.slice(0, 28)}`,
                        )
                        .join(', ')}
                      .
                    </p>
                  ))}
                  <small>
                    Input SHA-256 <code>{shortHash(carryMutation.data.input_sha256)}</code> · result
                    SHA-256 <code>{shortHash(carryMutation.data.result_sha256)}</code>. Displayed
                    money values are rounded.
                  </small>
                  <details>
                    <summary>Exact decimal outputs, assumptions, and limitations</summary>
                    <p>
                      Total carry: <code>{carryMutation.data.total_carry_cost}</code> · gross after
                      carry:{' '}
                      <code>
                        {carryMutation.data.worst_case_gross_pnl_after_carry ?? 'not established'}
                      </code>{' '}
                      · net after carry:{' '}
                      <code>
                        {carryMutation.data.worst_case_net_pnl_after_carry ?? 'not established'}
                      </code>
                    </p>
                    <ul>
                      {[...carryMutation.data.assumptions, ...carryMutation.data.limitations].map(
                        (item, index) => (
                          <li key={`${candidate.candidate_id}-carry-note-${index}`}>{item}</li>
                        ),
                      )}
                    </ul>
                  </details>
                </div>
              )}
          </div>
          <div className="fr-fx-sensitivity">
            <div>
              <span className="fr-kicker">Funding denomination · virtual assumptions</span>
              <h4>Venue-local funding currency sensitivity</h4>
            </div>
            <p>
              Compare each isolated virtual balance with the candidate’s required settlement asset.
              Enter an explicit rate in <strong>target units per one funding unit</strong> and a
              conversion fee. No rate is fetched or inferred, and this funding view does not change
              the candidate classification or P&amp;L.
            </p>
            {carryVenues.map((venue) => {
              const identity = fundingIdentityFor(venue);
              const target = candidate.capital_currency_identity ?? null;
              const sameIdentity = fundingIdentityMatches(identity, target);
              const kind = identity?.kind ?? 'fiat';
              return (
                <div className="fr-fx-funding-row" key={`${candidate.candidate_id}-fx-${venue}`}>
                  <strong>{venueLabel(venue)}</strong>
                  <label>
                    <span>Funding asset kind</span>
                    <select
                      aria-label={`${venueLabel(venue)} funding asset kind`}
                      value={kind}
                      onChange={(event) => {
                        setFundingKinds((current) => ({
                          ...current,
                          [venue]: event.target.value as SettlementAssetIdentity['kind'],
                        }));
                        fundingCurrencyMutation.reset();
                      }}
                    >
                      <option value="fiat">Fiat currency</option>
                      <option value="token">Network-specific token</option>
                      <option value="other">Other namespaced asset</option>
                    </select>
                  </label>
                  <label>
                    <span>Funding asset code</span>
                    <input
                      aria-label={`${venueLabel(venue)} funding asset code`}
                      maxLength={16}
                      value={identity?.code ?? ''}
                      onChange={(event) => {
                        setFundingCodes((current) => ({ ...current, [venue]: event.target.value }));
                        fundingCurrencyMutation.reset();
                      }}
                    />
                  </label>
                  {kind !== 'fiat' && (
                    <>
                      <label>
                        <span>Network identifier</span>
                        <input
                          aria-label={`${venueLabel(venue)} funding asset network identifier`}
                          maxLength={128}
                          value={identity?.network_id ?? ''}
                          onChange={(event) => {
                            setFundingNetworks((current) => ({
                              ...current,
                              [venue]: event.target.value,
                            }));
                            fundingCurrencyMutation.reset();
                          }}
                        />
                      </label>
                      <label>
                        <span>Asset reference</span>
                        <input
                          aria-label={`${venueLabel(venue)} funding asset reference`}
                          maxLength={256}
                          value={identity?.asset_reference ?? ''}
                          onChange={(event) => {
                            setFundingAssetReferences((current) => ({
                              ...current,
                              [venue]: event.target.value,
                            }));
                            fundingCurrencyMutation.reset();
                          }}
                        />
                      </label>
                    </>
                  )}
                  <label>
                    <span>Virtual balance ({settlementIdentityLabel(identity)})</span>
                    <input
                      aria-label={`${venueLabel(venue)} funding currency virtual balance`}
                      inputMode="decimal"
                      maxLength={110}
                      value={fundingBalances[venue] ?? ''}
                      onChange={(event) => {
                        setFundingBalances((current) => ({
                          ...current,
                          [venue]: event.target.value,
                        }));
                        fundingCurrencyMutation.reset();
                      }}
                    />
                  </label>
                  <label>
                    <span>Target units per funding unit</span>
                    <input
                      aria-label={`${venueLabel(venue)} target units per funding unit`}
                      inputMode="decimal"
                      maxLength={24}
                      disabled={sameIdentity}
                      value={sameIdentity ? '1' : (fundingRates[venue] ?? '')}
                      onChange={(event) => {
                        setFundingRates((current) => ({ ...current, [venue]: event.target.value }));
                        fundingCurrencyMutation.reset();
                      }}
                    />
                  </label>
                  <label>
                    <span>Conversion fee (bps of target)</span>
                    <input
                      aria-label={`${venueLabel(venue)} conversion fee in basis points`}
                      inputMode="decimal"
                      maxLength={16}
                      disabled={sameIdentity}
                      value={sameIdentity ? '0' : (fundingFees[venue] ?? '')}
                      onChange={(event) => {
                        setFundingFees((current) => ({ ...current, [venue]: event.target.value }));
                        fundingCurrencyMutation.reset();
                      }}
                    />
                  </label>
                  <small>
                    Required candidate capital: {candidate.capital_by_venue[venue]}{' '}
                    {settlementIdentityLabel(target)}. Balances at other venues cannot cover this
                    requirement.
                  </small>
                </div>
              );
            })}
            {!candidate.source_run_id || !candidate.source_run_sha256 ? (
              <small role="status">
                This candidate does not include a pinned saved run identity. Reload current Frontier
                data before evaluating funding assumptions.
              </small>
            ) : (
              <button
                className="fr-action"
                type="button"
                disabled={!fundingInputsValid || fundingCurrencyMutation.isPending}
                onClick={() =>
                  fundingCurrencyMutation.mutate({
                    run_id: candidate.source_run_id!,
                    run_sha256: candidate.source_run_sha256!,
                    candidate_id: candidate.candidate_id,
                    venues: carryVenues.map((venue) => {
                      const identity = fundingIdentityFor(venue)!;
                      const sameIdentity = fundingIdentityMatches(
                        identity,
                        candidate.capital_currency_identity ?? null,
                      );
                      return {
                        venue,
                        funding_currency_identity: identity,
                        balance_amount: fundingBalances[venue],
                        target_units_per_funding_unit: sameIdentity
                          ? '1'
                          : (fundingRates[venue] ?? ''),
                        conversion_fee_bps: sameIdentity ? '0' : (fundingFees[venue] ?? ''),
                      };
                    }),
                  })
                }
              >
                {fundingCurrencyMutation.isPending
                  ? 'Recomputing…'
                  : 'Evaluate virtual funding sensitivity'}
              </button>
            )}
            {fundingCurrencyMutation.isError && (
              <InlineError message={fundingCurrencyMutation.error.message} />
            )}
            {fundingCurrencyMutation.data && (
              <div className="fr-capital-carry-result" aria-label="Virtual funding currency result">
                <div className="fr-candidate-audit-head">
                  <h5>Hypothetical funding sensitivity</h5>
                  <StateBadge state={fundingCurrencyMutation.data.audit.disposition} />
                </div>
                <p>{fundingCurrencyMutation.data.audit.message}</p>
                <p>
                  Target:{' '}
                  {settlementIdentityLabel(fundingCurrencyMutation.data.target_currency_identity)}
                  {' · '}candidate state {fundingCurrencyMutation.data.candidate_classification} ·
                  classification unchanged · practical eligibility{' '}
                  {fundingCurrencyMutation.data.candidate_practical_eligibility
                    ? 'established'
                    : 'not established'}{' '}
                  (unchanged) · candidate economics unchanged.
                </p>
                {fundingCurrencyMutation.data.venues.map((item) => (
                  <div
                    className="fr-fx-result-row"
                    key={`${candidate.candidate_id}-fx-result-${item.venue}`}
                  >
                    <strong>{venueLabel(item.venue)}</strong>
                    <span>
                      {item.model_requirement_covered
                        ? fundingCurrencyMutation.data.unresolved_candidate_fee_leg_count > 0
                          ? 'Recorded model requirement covered; unresolved fees remain.'
                          : 'Recorded model requirement covered under this assumption.'
                        : 'Virtual funding shortfall under this assumption.'}
                    </span>
                    <small>
                      Need <code>{item.required_funding_amount}</code>{' '}
                      {settlementIdentityLabel(item.funding_currency_identity)} from a balance of{' '}
                      <code>{item.balance_amount}</code>; target value after fee{' '}
                      <code>{item.available_capital_target_after_fee}</code>; target shortfall{' '}
                      <code>{item.shortfall_target}</code>; modeled conversion fee{' '}
                      <code>{item.conversion_fee_target_amount}</code>{' '}
                      {settlementIdentityLabel(
                        fundingCurrencyMutation.data.target_currency_identity,
                      )}
                      .
                    </small>
                  </div>
                ))}
                <section
                  className="fr-candidate-audit"
                  aria-label="Conversion-adjusted outcome P&L scenario"
                >
                  <div className="fr-candidate-audit-head">
                    <h5>Outcome P&amp;L after modeled conversion costs</h5>
                    <StateBadge state={fundingCurrencyMutation.data.pnl_scenario.status} />
                  </div>
                  <p>{fundingCurrencyMutation.data.pnl_scenario.audit.message}</p>
                  {fundingCurrencyMutation.data.pnl_scenario.status === 'verified' ? (
                    <>
                      <p>
                        Separate hypothetical sensitivity in{' '}
                        {settlementIdentityLabel(
                          fundingCurrencyMutation.data.pnl_scenario.target_currency_identity,
                        )}
                        . The saved candidate economics and classification remain unchanged.
                      </p>
                      {Object.entries(
                        fundingCurrencyMutation.data.pnl_scenario.net_pnl_after_conversion_by_state,
                      ).map(([state, pnl]) => (
                        <div
                          className="fr-fx-result-row"
                          key={`${candidate.candidate_id}-fx-pnl-${state}`}
                        >
                          <strong>{state}</strong>
                          <small>
                            Candidate audited net P&amp;L{' '}
                            <code>
                              {
                                fundingCurrencyMutation.data.pnl_scenario
                                  .candidate_net_pnl_by_state[state]
                              }
                            </code>{' '}
                            · after modeled conversion fee <code>{pnl}</code>
                          </small>
                        </div>
                      ))}
                      <p>
                        Worst terminal-state result after the modeled conversion fee:{' '}
                        <code>
                          {
                            fundingCurrencyMutation.data.pnl_scenario
                              .worst_case_net_pnl_after_conversion
                          }
                        </code>
                        {' · '}all outcomes positive under these assumptions:{' '}
                        {fundingCurrencyMutation.data.pnl_scenario
                          .all_outcomes_positive_after_conversion
                          ? 'yes'
                          : 'no'}
                        .
                      </p>
                    </>
                  ) : (
                    <p>
                      Outcome P&amp;L is unavailable:{' '}
                      {fundingCurrencyMutation.data.pnl_scenario.reason}
                    </p>
                  )}
                </section>
                <small>
                  Input SHA-256 <code>{shortHash(fundingCurrencyMutation.data.input_sha256)}</code>{' '}
                  · result SHA-256{' '}
                  <code>{shortHash(fundingCurrencyMutation.data.result_sha256)}</code>.
                </small>
                <details>
                  <summary>Funding assumptions and limitations</summary>
                  <ul>
                    {[
                      ...fundingCurrencyMutation.data.assumptions,
                      ...fundingCurrencyMutation.data.limitations,
                    ].map((item, index) => (
                      <li key={`${candidate.candidate_id}-fx-note-${index}`}>{item}</li>
                    ))}
                  </ul>
                </details>
              </div>
            )}
          </div>
        </section>
      )}
      {candidate.legs.length > 0 && (
        <div className="fr-table-wrap">
          <table className="fr-table">
            <thead>
              <tr>
                <th>Venue / native market</th>
                <th>Outcome</th>
                <th>Native quantity</th>
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
                  <td>
                    {leg.quantity}{' '}
                    {leg.quantity_unit ? label(leg.quantity_unit) : '(unit unrecorded)'}
                  </td>
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
      {candidate.partial_fill_grid_sensitivity && (
        <section className="fr-candidate-fill-stress" aria-label="Partial-fill grid sensitivity">
          <div>
            <span className="fr-kicker">Execution uncertainty</span>
            <h4>Bounded partial-fill grid</h4>
          </div>
          <p>
            Each leg is evaluated independently at the quantity-step-feasible points from{' '}
            {candidate.partial_fill_grid_sensitivity.fill_fraction_grid
              .map((fraction) => `${Math.round(Number(fraction) * 100)}%`)
              .join(', ')}{' '}
            of modeled size. Fees are recomputed for each aggregate partial quantity. The grid does
            not model fill probabilities or fractions between its points.
          </p>
          <div className="fr-fill-stress-values">
            <span>
              Worst sampled result before fees
              <strong>
                {money(candidate.partial_fill_grid_sensitivity.worst_before_fees.pnl_before_fees)}
              </strong>
              <small>
                State:{' '}
                {label(candidate.partial_fill_grid_sensitivity.worst_before_fees.terminal_state_id)}
              </small>
            </span>
            <span>
              Worst sampled result after fees
              <strong>
                {candidate.partial_fill_grid_sensitivity.worst_after_fees
                  ? money(candidate.partial_fill_grid_sensitivity.worst_after_fees.pnl_after_fees)
                  : 'Unknown'}
              </strong>
              <small>
                {candidate.partial_fill_grid_sensitivity.worst_after_fees
                  ? `State: ${label(candidate.partial_fill_grid_sensitivity.worst_after_fees.terminal_state_id)}`
                  : 'At least one feasible partial quantity has an unresolved fee.'}
              </small>
            </span>
          </div>
          <div className="fr-fill-stress-patterns">
            <p>
              <strong>Before-fee quantities</strong>
              <span>
                {describePartialFillOutcome(
                  candidate.partial_fill_grid_sensitivity.worst_before_fees,
                )}
              </span>
            </p>
            {candidate.partial_fill_grid_sensitivity.worst_after_fees && (
              <p>
                <strong>After-fee quantities</strong>
                <span>
                  {describePartialFillOutcome(
                    candidate.partial_fill_grid_sensitivity.worst_after_fees,
                  )}
                </span>
              </p>
            )}
          </div>
          <details>
            <summary>Quantity-step-feasible grid points by leg</summary>
            <ul>
              {Object.entries(
                candidate.partial_fill_grid_sensitivity.feasible_fill_fractions_by_leg,
              ).map(([legId, fractions]) => (
                <li key={legId}>
                  {describeFillLeg(legId)}:{' '}
                  {fractions.map((fraction) => `${Math.round(Number(fraction) * 100)}%`).join(', ')}
                </li>
              ))}
            </ul>
          </details>
          {candidate.partial_fill_grid_sensitivity.assumptions.map((assumption) => (
            <small key={assumption}>{assumption}</small>
          ))}
        </section>
      )}
      {Object.keys(candidate.gross_pnl_by_state).length > 0 && (
        <section className="fr-candidate-states" aria-label="Terminal-state payoff analysis">
          <h4>
            {candidate.joint_state_mapping_id
              ? 'Payoffs over asserted joint states'
              : 'Terminal-state payoff analysis'}
          </h4>
          <div className="fr-table-wrap">
            <table className="fr-table">
              <thead>
                <tr>
                  <th>
                    {candidate.joint_state_mapping_id ? 'Asserted joint state' : 'Terminal state'}
                  </th>
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
  const candidatePageSize = 10;
  const [candidatePage, setCandidatePage] = useState(0);
  const candidatePageCount = Math.ceil(runCandidates.length / candidatePageSize);
  const candidateStart = candidatePage * candidatePageSize;
  const visibleCandidates = runCandidates.slice(candidateStart, candidateStart + candidatePageSize);
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
          {visibleCandidates.map((candidate) => (
            <CandidateCard key={candidate.candidate_id} candidate={candidate} />
          ))}
          {candidatePageCount > 1 && (
            <div
              className="fr-graph-pagination"
              role="group"
              aria-label="Saved replay candidate pages"
            >
              <button
                className="fr-action"
                disabled={candidatePage === 0}
                onClick={() => setCandidatePage((current) => Math.max(0, current - 1))}
              >
                Previous replay candidates
              </button>
              <span aria-live="polite">
                Showing {candidateStart + 1}–
                {Math.min(candidateStart + candidatePageSize, runCandidates.length)} of{' '}
                {runCandidates.length} saved replay candidates
              </span>
              <button
                className="fr-action"
                disabled={candidatePage + 1 >= candidatePageCount}
                onClick={() =>
                  setCandidatePage((current) => Math.min(candidatePageCount - 1, current + 1))
                }
              >
                Next replay candidates
              </button>
            </div>
          )}
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

function DiscoveryScopeComparisonSummary({
  comparison,
  replays,
}: {
  comparison: DiscoveryScopeComparison;
  replays: FrontierDiscoveryReplayEvidence[];
}) {
  const signed = (value: number) => (value > 0 ? `+${value}` : String(value));
  const replaysById = new Map(replays.map((replay) => [replay.run_id, replay] as const));
  return (
    <div className="fr-discovery-scope-result">
      <div className="fr-arena-replay-note">
        Verified artifact · {time(comparison.as_of_utc)} · comparison{' '}
        {shortHash(comparison.comparison_id)}
      </div>
      <div className="fr-discovery-table-wrap">
        <table className="fr-discovery-scope-table">
          <thead>
            <tr>
              <th scope="col">Discovery scope</th>
              <th scope="col">Markets</th>
              <th scope="col">Observed instruments</th>
              <th scope="col">Relationships</th>
              <th scope="col">Candidates</th>
            </tr>
          </thead>
          <tbody>
            {comparison.arms.map((arm) => (
              <tr key={arm.scope}>
                <th scope="row">
                  <strong>{label(arm.scope)}</strong>
                  <small>{arm.venues.map(venueLabel).join(' · ') || 'No venue data'}</small>
                </th>
                <td>{arm.market_count}</td>
                <td>
                  {arm.observed_instrument_count} / {arm.instrument_count}
                  <small>{arm.book_count} saved books</small>
                </td>
                <td>{arm.relationship_count}</td>
                <td>
                  {arm.candidates.length}
                  <small>
                    {Object.entries(arm.family_counts)
                      .map(([family, count]) => `${label(family)} ${count}`)
                      .join(' · ') || 'No candidates'}
                  </small>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="fr-discovery-scope-deltas" aria-label="Pairwise scope differences">
        {comparison.deltas.map((delta) => (
          <div key={`${delta.baseline}:${delta.compared}`}>
            <strong>
              {label(delta.baseline)} → {label(delta.compared)}
            </strong>
            <span>
              {delta.matched_candidate_count} matched · {delta.compared_only_candidate_count} added
              · {delta.baseline_only_candidate_count} removed · {delta.changed_classification_count}{' '}
              classification changes
            </span>
            <small>
              Candidate construction differences under the same pinned prices and execution
              assumptions.
            </small>
          </div>
        ))}
      </div>
      <section
        className="fr-discovery-candidate-inspection"
        aria-label="Candidate inspection by scope"
      >
        <div>
          <span className="fr-kicker">CANDIDATE EVIDENCE</span>
          <h3>Inspect modeled constructions</h3>
        </div>
        {comparison.arms.map((arm) => (
          <section className="fr-discovery-candidate-scope" key={`${arm.scope}-candidate-details`}>
            <h4>
              {label(arm.scope)} <span>{arm.candidates.length} candidate(s)</span>
            </h4>
            {arm.candidates.length === 0 ? (
              <p className="fr-arena-replay-note">
                This scope produced no candidate constructions.
              </p>
            ) : (
              <div className="fr-discovery-candidate-list">
                {arm.candidates.slice(0, 50).map((summary) => {
                  const candidate = arm.replay_run_ids
                    .flatMap((runId) => replaysById.get(runId)?.candidates ?? [])
                    .find(
                      (item) =>
                        item.candidate_id === summary.candidate_id &&
                        item.family === summary.family &&
                        item.classification === summary.classification &&
                        item.independent_audit?.disposition === summary.audit_disposition &&
                        item.worst_case_gross_pnl === summary.worst_case_gross_pnl &&
                        item.worst_case_net_pnl === summary.worst_case_net_pnl,
                    );
                  return candidate ? (
                    <DiscoveryCandidateDetails candidate={candidate} key={candidate.candidate_id} />
                  ) : (
                    <p className="fr-alert" key={summary.candidate_id}>
                      Candidate detail is missing from the integrity-verified replay artifact.
                    </p>
                  );
                })}
                {arm.candidates.length > 50 && (
                  <p className="fr-arena-replay-note">
                    Showing the first 50 candidate details in deterministic identity order;{' '}
                    {arm.candidates.length - 50} more are present in the verified artifact.
                  </p>
                )}
              </div>
            )}
          </section>
        ))}
      </section>
      <details className="fr-run-details">
        <summary>Comparison provenance · {comparison.comparison_id}</summary>
        <p>Input SHA-256: {comparison.normalized_input_sha256}</p>
        <p>Result SHA-256: {comparison.result_sha256}</p>
        <p>Code version: {comparison.code_version}</p>
        <p>
          Classification deltas:{' '}
          {comparison.deltas
            .map((delta) => {
              const counts = Object.entries(delta.classification_count_delta)
                .map(([key, value]) => `${label(key)} ${signed(value)}`)
                .join(' · ');
              return `${label(delta.baseline)} → ${label(delta.compared)}: ${counts || 'none'}`;
            })
            .join(' | ')}
        </p>
      </details>
      <p className="fr-arena-replay-note">
        Counts describe this saved evidence window only. They do not estimate exchange-wide
        opportunity prevalence, authenticate external market mappings, or imply executable profit.
      </p>
    </div>
  );
}

function DiscoveryCandidateDetails({ candidate }: { candidate: DiscoveryCandidateEvidence }) {
  const stateIds = [
    ...new Set(
      Object.keys(candidate.outcome_payout_by_state).concat(
        Object.keys(candidate.gross_pnl_by_state),
        Object.keys(candidate.net_pnl_by_state),
      ),
    ),
  ].sort();
  return (
    <details className="fr-discovery-candidate">
      <summary>
        <span>
          Inspect candidate {shortHash(candidate.candidate_id)} · {label(candidate.family)}
        </span>
        <small>
          {label(candidate.classification)} · {candidate.legs.length} leg(s) ·{' '}
          {candidate.venues.map(venueLabel).join(' + ') || 'venue evidence incomplete'}
        </small>
      </summary>
      <div className="fr-discovery-candidate-detail">
        <dl className="fr-discovery-candidate-metrics">
          <div>
            <dt>Gross basket cost</dt>
            <dd>{exactMoney(candidate.gross_cost)}</dd>
          </div>
          <div>
            <dt>Modeled fees</dt>
            <dd>{exactMoney(candidate.modeled_fees)}</dd>
          </div>
          <div>
            <dt>Modeled net cost</dt>
            <dd>{exactMoney(candidate.modeled_net_cost)}</dd>
          </div>
          <div>
            <dt>Worst modeled gross P&amp;L</dt>
            <dd>{exactMoney(candidate.worst_case_gross_pnl)}</dd>
          </div>
          <div>
            <dt>Worst modeled net P&amp;L</dt>
            <dd>{exactMoney(candidate.worst_case_net_pnl)}</dd>
          </div>
          <div>
            <dt>Modeled settlement identity</dt>
            <dd>{settlementIdentityLabel(candidate.capital_currency_identity)}</dd>
          </div>
          <div>
            <dt>Practical eligibility</dt>
            <dd>{candidate.practical_eligibility ? 'Established' : 'Not established'}</dd>
          </div>
          <div>
            <dt>Timing verified</dt>
            <dd>{candidate.timing_verified ? 'Yes' : 'No'}</dd>
          </div>
        </dl>
        <div className="fr-table-wrap">
          <table className="fr-table">
            <thead>
              <tr>
                <th>Venue / native market</th>
                <th>Instrument / outcome</th>
                <th>Native quantity</th>
                <th>Observed ask</th>
                <th>Modeled price and fee</th>
                <th>Displayed depth</th>
                <th>Book evidence</th>
              </tr>
            </thead>
            <tbody>
              {candidate.legs.map((leg) => (
                <tr key={`${candidate.candidate_id}-${leg.venue}-${leg.instrument_id}`}>
                  <td>
                    <VenuePill venue={leg.venue} />
                    <code>{leg.native_market_id}</code>
                  </td>
                  <td>
                    <code>{leg.instrument_id}</code>
                    <small>{label(leg.outcome_id)}</small>
                  </td>
                  <td>
                    {leg.quantity} {leg.quantity_unit ? label(leg.quantity_unit) : '(unit unknown)'}
                  </td>
                  <td>
                    {exactMoney(leg.quoted_ask)} {leg.quote_currency ?? ''}
                    <small>{settlementIdentityLabel(leg.quote_currency_identity)}</small>
                  </td>
                  <td>
                    {exactMoney(leg.modeled_buy_price)} {leg.quote_currency ?? ''}
                    <small>Fee {exactMoney(leg.modeled_fee)}</small>
                  </td>
                  <td>{leg.displayed_depth}</td>
                  <td>
                    <code>{shortHash(leg.book_observation_id)}</code>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <h5>Terminal outcomes under the pinned payoff model</h5>
        <p className="fr-arena-replay-note">
          Hypothetical replay only. These modeled values do not establish fills, venue access, or
          realized profit.
        </p>
        <div className="fr-discovery-outcome-list">
          {stateIds.map((state) => (
            <div key={`${candidate.candidate_id}-${state}`}>
              <strong>{label(state)}</strong>
              <span>Payout {exactMoney(candidate.outcome_payout_by_state[state])}</span>
              <span>Gross {exactMoney(candidate.gross_pnl_by_state[state])}</span>
              <span>Net {exactMoney(candidate.net_pnl_by_state[state])}</span>
            </div>
          ))}
        </div>
        <p className="fr-arena-replay-note">
          Receipt skew{' '}
          {candidate.received_skew_ms == null
            ? 'unknown'
            : `${count(candidate.received_skew_ms)} ms`}
          {' · '}exchange-time skew{' '}
          {candidate.exchange_skew_ms == null
            ? 'unknown'
            : `${count(candidate.exchange_skew_ms)} ms`}
          {' · '}practical execution remains unestablished unless independently evidenced.
        </p>
        <details className="fr-run-details">
          <summary>Independent audit, assumptions, and evidence hashes</summary>
          <p>
            Audit {candidate.independent_audit?.disposition ?? 'not recorded'} · input{' '}
            {candidate.independent_audit
              ? shortHash(candidate.independent_audit.input_sha256)
              : 'unknown'}
          </p>
          <p>
            {candidate.independent_audit?.message ?? 'No independent audit message is available.'}
          </p>
          <p>Candidate evidence SHA-256: {candidate.evidence_sha256}</p>
          {candidate.independent_audit?.checks.length ? (
            <ul>
              {candidate.independent_audit.checks.map((check, index) => (
                <li key={`${candidate.candidate_id}-audit-${index}`}>{check}</li>
              ))}
            </ul>
          ) : null}
          <h5>Assumptions and limitations</h5>
          <ul>
            {[...candidate.assumptions, ...candidate.reasons].map((item, index) => (
              <li key={`${candidate.candidate_id}-assumption-${index}`}>{item}</li>
            ))}
          </ul>
        </details>
      </div>
    </details>
  );
}

function TimelineFrameSummary({ frame }: { frame: FrontierTimelineFrame }) {
  const timingPageSize = 24;
  const candidatePageSize = 8;
  const [timingPage, setTimingPage] = useState(0);
  const [candidatePage, setCandidatePage] = useState(0);
  const timingPageCount = Math.ceil(frame.instrument_states.length / timingPageSize);
  const candidatePageCount = Math.ceil(frame.candidates.length / candidatePageSize);
  const timingStart = timingPage * timingPageSize;
  const candidateStart = candidatePage * candidatePageSize;
  const visibleTiming = frame.instrument_states.slice(timingStart, timingStart + timingPageSize);
  const visibleCandidates = frame.candidates.slice(
    candidateStart,
    candidateStart + candidatePageSize,
  );
  const classifications = Object.entries(frame.classification_counts)
    .map(([key, value]) => `${label(key)}: ${value}`)
    .join(' · ');
  return (
    <details className="fr-timeline-frame">
      <summary>
        <span>{time(frame.as_of_utc)}</span>
        <span>
          {frame.fresh_book_count} fresh · {frame.stale_book_count} stale ·{' '}
          {frame.not_yet_observed_count} not yet observed · {frame.excluded_source_book_count}{' '}
          source-excluded
        </span>
        <span>{frame.candidate_count} hypothetical candidates</span>
      </summary>
      <div className="fr-timeline-frame-content">
        <div className="fr-timeline-provenance">
          <span>{frame.included_book_count} books passed freshness and source checks</span>
          <span>Run {shortHash(frame.replay_run_id)}</span>
          <span>Output {shortHash(frame.replay_result_sha256)}</span>
        </div>
        <p>Classifications: {classifications || 'none'}</p>
        {frame.source_states.length ? (
          <ul className="fr-timeline-source-states">
            {frame.source_states.map((source, index) => (
              <li key={`${source.venue}-${index}`}>
                <strong>
                  {label(source.venue)}: {label(source.state)}
                </strong>
                <span>{source.basis ? ` · ${label(source.basis)} status` : ''}</span>
                {source.reason && <span> · {source.reason}</span>}
              </li>
            ))}
          </ul>
        ) : (
          <p className="fr-timeline-no-source-state">
            No explicit source-state event was pinned. This absence does not certify source health;
            book receipt time and freshness are evaluated separately.
          </p>
        )}
        {frame.instrument_states.length > 0 && (
          <>
            <h4>Per-instrument timing evidence</h4>
            <p className="fr-arena-replay-note">
              Exchange timestamps retain each venue’s stated meaning. Clock uncertainty is shown as
              recorded; missing values remain unknown.
            </p>
            <div className="fr-table-wrap">
              <table className="fr-table" aria-label="Per-instrument source timing evidence">
                <thead>
                  <tr>
                    <th>Venue / native market</th>
                    <th>Instrument</th>
                    <th>Replay status</th>
                    <th>Receipt age</th>
                    <th>Received at</th>
                    <th>Exchange timestamp</th>
                    <th>Clock uncertainty</th>
                    <th>Source freshness limit</th>
                    <th>Timestamp meaning</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleTiming.map((instrument) => (
                    <tr
                      key={JSON.stringify([
                        instrument.venue,
                        instrument.native_market_id,
                        instrument.native_instrument_id,
                      ])}
                    >
                      <td>
                        <VenuePill venue={instrument.venue} />
                        <code>{instrument.native_market_id}</code>
                      </td>
                      <td>
                        <code>{instrument.native_instrument_id}</code>
                      </td>
                      <td>
                        {instrument.included_in_replay ? 'Included' : 'Excluded'}
                        <small>
                          {label(instrument.book_state)} · {label(instrument.exclusion)}
                        </small>
                      </td>
                      <td>{instrument.age_ms == null ? '—' : `${count(instrument.age_ms)} ms`}</td>
                      <td>{instrument.received_at_utc ?? 'Not observed'}</td>
                      <td>{instrument.exchange_timestamp_utc ?? 'Unknown'}</td>
                      <td>
                        {instrument.clock_uncertainty_ms == null
                          ? 'Unknown'
                          : `${instrument.clock_uncertainty_ms} ms`}
                      </td>
                      <td>
                        {instrument.freshness_limit_ms == null
                          ? 'Not supplied'
                          : `${count(instrument.freshness_limit_ms)} ms`}
                      </td>
                      <td>{instrument.exchange_timestamp_semantics ?? 'No observed book'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {timingPageCount > 1 && (
              <div
                className="fr-graph-pagination"
                role="group"
                aria-label="Per-instrument timing record pages"
              >
                <button
                  className="fr-action"
                  disabled={timingPage === 0}
                  onClick={() => setTimingPage((current) => Math.max(0, current - 1))}
                >
                  Previous timing records
                </button>
                <span aria-live="polite">
                  Showing {timingStart + 1}–
                  {Math.min(timingStart + timingPageSize, frame.instrument_states.length)} of{' '}
                  {frame.instrument_states.length} timing records
                </span>
                <button
                  className="fr-action"
                  disabled={timingPage + 1 >= timingPageCount}
                  onClick={() =>
                    setTimingPage((current) => Math.min(timingPageCount - 1, current + 1))
                  }
                >
                  Next timing records
                </button>
              </div>
            )}
          </>
        )}
        {frame.candidates.length > 0 && (
          <>
            <div className="fr-timeline-candidates">
              {visibleCandidates.map((candidate) => (
                <div className="fr-timeline-candidate" key={candidate.candidate_id}>
                  <div>
                    <strong>{label(candidate.classification)}</strong>
                    <span>
                      {label(candidate.family)} ·{' '}
                      {candidate.timing_verified ? 'timing verified' : 'timing not verified'}
                    </span>
                  </div>
                  <span>
                    Modeled worst-case net: {candidate.worst_case_net_pnl ?? 'not established'}
                  </span>
                  <code>{candidate.evidence_sha256}</code>
                </div>
              ))}
            </div>
            {frame.candidate_count > frame.candidates.length && (
              <p className="fr-arena-replay-note">
                The artifact contains {frame.candidates.length} candidate summaries for{' '}
                {frame.candidate_count} recorded candidates; additional summaries were not saved.
              </p>
            )}
            {candidatePageCount > 1 && (
              <div
                className="fr-graph-pagination"
                role="group"
                aria-label="Timeline candidate summary pages"
              >
                <button
                  className="fr-action"
                  disabled={candidatePage === 0}
                  onClick={() => setCandidatePage((current) => Math.max(0, current - 1))}
                >
                  Previous candidates
                </button>
                <span aria-live="polite">
                  Showing {candidateStart + 1}–
                  {Math.min(candidateStart + candidatePageSize, frame.candidates.length)} of{' '}
                  {frame.candidates.length} saved candidate summaries
                </span>
                <button
                  className="fr-action"
                  disabled={candidatePage + 1 >= candidatePageCount}
                  onClick={() =>
                    setCandidatePage((current) => Math.min(candidatePageCount - 1, current + 1))
                  }
                >
                  Next candidates
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </details>
  );
}
