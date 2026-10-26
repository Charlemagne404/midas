import { useMemo, useState } from 'react';
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
  research_only: boolean;
  live_execution: boolean;
  summary: {
    observations: number;
    relationships: number;
    relationship_reviews: number;
    runs: number;
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
type Market = {
  canonical_id: string;
  source_observation_record_id: string;
  native_market_id: string;
  venue: Venue;
  title: string;
  market_kind: string;
  lifecycle: string;
  description: string;
  base_asset: string | null;
  quote_asset: string | null;
  settlement_asset: string | null;
  payoff: {
    state_ids: string[];
    payout_currency: string | null;
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
    source_url: string | null;
    note: string;
  };
  instruments: { native_instrument_id: string; label: string; outcome_id: string | null }[];
  quality_flags: string[];
  provenance: { response_received_at_utc: string; raw_sha256: string; observation_id: string };
};
type Book = {
  source_observation_record_id: string;
  venue: Venue;
  native_market_id: string;
  native_instrument_id: string;
  asks: { price: string; quantity: string; exchange_timestamp_utc: string | null }[];
  bids: { price: string; quantity: string; exchange_timestamp_utc: string | null }[];
  price_unit: string;
  quantity_unit: string;
  received_at_utc: string;
  exchange_timestamp_utc: string | null;
  exchange_timestamp_semantics: string;
  quality_flags: string[];
  provenance: { observation_id: string; raw_sha256: string };
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
    observation_ids: string[];
    source_fields: string[];
    details: string[];
  }[];
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
    displayed_depth: string;
    book_observation_id: string;
  }[];
  worst_case_gross_pnl: string | null;
  worst_case_net_pnl: string | null;
  capital_by_venue: Record<string, string>;
  received_skew_ms: number | null;
  exchange_skew_ms: number | null;
  timing_verified: boolean;
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
      book_observation_ids: string[];
      relationship_ids: string[];
      as_of_utc: string;
      scenario: Record<string, string | number>;
    };
    candidates: Candidate[];
    classification_counts: Record<string, number>;
  };
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
const time = (value: string | null | undefined) =>
  value ? new Date(value).toLocaleString() : 'Not recorded';
const shortHash = (value: string | undefined) => (value ? `${value.slice(0, 12)}…` : '—');
const venueLabel = (value: string) =>
  ({ polymarket: 'Polymarket', kalshi: 'Kalshi', kraken: 'Kraken Spot' })[value] ?? value;

function StateBadge({ state }: { state: string }) {
  const tone = ['HEALTHY', 'PASS', 'VERIFIED'].includes(state.toUpperCase())
    ? 'good'
    : ['DEGRADED', 'HYPOTHESIS', 'CONDITIONAL'].includes(state.toUpperCase())
      ? 'watch'
      : ['FAILED', 'BLOCKED', 'REJECTED'].includes(state.toUpperCase())
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
  const [slippage, setSlippage] = useState('25');
  const [delay, setDelay] = useState('500');
  const [fillPercent, setFillPercent] = useState('80');
  const queryClient = useQueryClient();
  const options = { staleTime: 10_000, retry: 1 };
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
  const relationships = useQuery({
    queryKey: ['frontier', 'relationships'],
    queryFn: () => api<ListResponse<Relationship>>('/frontier/relationships?limit=200'),
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
  const readiness = useQuery({
    queryKey: ['frontier', 'readiness'],
    queryFn: () => api<Readiness>('/frontier/readiness'),
    ...options,
  });

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
  const probe = useMutation({
    mutationFn: ({ venue, includeOneBook }: { venue: Venue; includeOneBook: boolean }) =>
      api('/frontier/probe/' + venue, {
        method: 'POST',
        body: JSON.stringify({
          limit: venue === 'kraken' ? 1 : 10,
          include_one_book: includeOneBook,
        }),
      }),
    onSuccess: refresh,
  });

  const marketById = useMemo(
    () => new Map((markets.data?.items ?? []).map((market) => [market.canonical_id, market])),
    [markets.data],
  );
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
  const filteredRelationships = (relationships.data?.items ?? [])
    .filter((relationship) => {
      const left = marketById.get(relationship.left_market_id);
      const right = marketById.get(relationship.right_market_id);
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
  const overviewError = overview.error?.message ?? sources.error?.message;
  const summary = overview.data?.summary;
  const marketTotal = Object.values(summary?.markets_by_venue ?? {}).reduce(
    (sum, value) => sum + value,
    0,
  );
  const instrumentTotal = Object.values(summary?.instruments_by_venue ?? {}).reduce(
    (sum, value) => sum + value,
    0,
  );
  const verifiedRelationships = summary?.relationships_by_state?.verified ?? 0;

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
              title="Recorded markets"
              value={count(marketTotal)}
              note={`${count(instrumentTotal)} canonical instruments`}
              icon={Layers3}
            />
            <Metric
              title="Immutable observations"
              value={count(summary?.observations)}
              note={`Store ${summary ? `${money(summary.database_bytes)} / ${money(summary.max_bytes)} bytes` : 'size not measured'}`}
              icon={Database}
            />
            <Metric
              title="Verified relationships"
              value={count(verifiedRelationships)}
              note={`${count(summary?.relationships)} effective edges · ${count(summary?.relationship_reviews)} review decisions`}
              icon={GitBranch}
            />
            <Metric
              title="Replay runs"
              value={count(summary?.runs)}
              note="Deterministic, pinned inputs and assumptions"
              icon={Play}
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
                    markets={summary?.markets_by_venue?.[source.venue] ?? 0}
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
              market={selectedMarket}
              books={selectedBooks}
              booksLoading={books.isLoading}
            />
          )}
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
          {propose.isError && <InlineError message={propose.error.message} />}
          {relationships.isLoading ? (
            <div className="fr-loading">Loading stored relationship evidence…</div>
          ) : relationships.isError ? (
            <EmptyState title="Relationship query failed" detail={relationships.error.message} />
          ) : filteredRelationships.length ? (
            <>
              <RelationshipGraph
                relationships={filteredRelationships.slice(0, 18)}
                marketById={marketById}
                selectedId={selectedRelationshipId}
                onSelect={setSelectedRelationshipId}
              />
              <div className="fr-graph-list">
                {filteredRelationships.map((relationship) => {
                  const left = marketById.get(relationship.left_market_id);
                  const right = marketById.get(relationship.right_market_id);
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
                            <small key={`${relationship.relationship_id}-${index}`}>
                              {evidence.method} · fields:{' '}
                              {evidence.source_fields.join(', ') || 'none'} · observations:{' '}
                              {evidence.observation_ids.map(shortHash).join(', ') || 'none'}
                            </small>
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
              title="No relationship edges in this view"
              detail="Text and native metadata matching create hypotheses only. A verified edge requires exhaustive payout and resolution evidence plus independent mapping."
            />
          )}
          <div className="fr-footnote">
            The evidence list is capped at 30 edges; the network shows the first 18. Similar titles
            never certify payoff equivalence. Relationship identity is versioned and tied to pinned
            observation IDs.
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

function SourceRow({ source, markets }: { source: Source; markets: number }) {
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
      <span className="fr-market-count">{count(markets)} markets</span>
      <StateBadge state={source.health.state} />
    </div>
  );
}

function MarketDetails({
  market,
  books,
  booksLoading,
}: {
  market: Market;
  books: Book[];
  booksLoading: boolean;
}) {
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
          <small>{market.fees.note}</small>
        </div>
        <div>
          <span>Settlement asset</span>
          <strong>{market.settlement_asset ?? market.quote_asset ?? 'Not established'}</strong>
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
              {booksLoading ? (
                <small>Loading stored public book snapshots…</small>
              ) : book ? (
                <>
                  <div className="fr-book-meta">
                    <span>{book.price_unit}</span>
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

function SourcesView({
  sources,
  markets,
  probe,
  loading,
  error,
}: {
  sources: Source[];
  markets: Record<string, number>;
  probe: ProbeMutation;
  loading: boolean;
  error?: string;
}) {
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
              <div className="fr-venue-stats">
                <span>
                  <strong>{count(markets[source.venue] ?? 0)}</strong> recorded markets
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
                      ? 'Capture one bounded sample'
                      : 'Public probe disabled'}
                </button>
                <small>
                  {source.health.last_success_at_utc
                    ? `Last source response ${time(source.health.last_success_at_utc)}`
                    : 'No request is made automatically.'}
                </small>
              </div>
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
          Worst modeled net result<strong>{money(candidate.worst_case_net_pnl)}</strong>
        </span>
        <span>
          Timing verified<strong>{candidate.timing_verified ? 'Yes' : 'No'}</strong>
        </span>
        <span>
          Practical eligibility
          <strong>{candidate.practical_eligibility ? 'Established' : 'Not established'}</strong>
        </span>
      </div>
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
                  </td>
                  <td>{leg.displayed_depth}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
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
