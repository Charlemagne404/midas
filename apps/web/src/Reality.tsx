import { lazy, Suspense, useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Activity,
  ArrowUpRight,
  ChevronRight,
  Database,
  ExternalLink,
  Fingerprint,
  Radio,
  RefreshCw,
  Search,
  ShieldCheck,
  X,
} from 'lucide-react';
import { api } from './api';
import type { ComponentProps } from 'react';
const LazyChart = lazy(() => import('./Chart').then((m) => ({ default: m.Chart })));
function Chart(props: ComponentProps<typeof LazyChart>) {
  return (
    <Suspense fallback={<Empty>Loading chart…</Empty>}>
      <LazyChart {...props} />
    </Suspense>
  );
}
import { chartBase } from './chart-theme';
import './reality.css';
import { historyBarrier, historySeries } from './reality-history';
import type { HistorySample } from './reality-history';

type Json = null | boolean | number | string | Json[] | { [key: string]: Json };
type Obj = { [key: string]: Json };
const obj = (v: Json | undefined): Obj =>
  v && typeof v === 'object' && !Array.isArray(v) ? v : {};
const arr = (v: Json | undefined): Json[] => (Array.isArray(v) ? v : []);
const txt = (v: Json | undefined) =>
  v === null || v === undefined ? 'Unknown' : typeof v === 'object' ? JSON.stringify(v) : String(v);
const fmt = (v: Json | undefined, digits = 0) =>
  v === null || v === undefined || !Number.isFinite(Number(v))
    ? '—'
    : Number(v).toLocaleString('en-US', { maximumFractionDigits: digits });
const utc = (v: Json | undefined) =>
  Number(v) ? new Date(Number(v) / 1e6).toISOString().replace('T', ' ').slice(0, 23) + ' UTC' : '—';
const short = (v: Json | undefined) => (typeof v === 'string' ? v.slice(0, 12) + '…' : '—');
const pct = (v: Json | undefined) =>
  v === null || v === undefined ? '—' : `${(Number(v) * 100).toFixed(1)}%`;
const tabs = [
  'Overview',
  'Live explorer',
  'Historical',
  'Opportunities',
  'Calibration',
  'Models',
  'Shadow',
  'Forward',
  'Operations',
];
const descriptions = [
  'A continuous record of public markets. A measured account of what remains unknown.',
  'Complementary outcomes, displayed liquidity and observation quality.',
  'Sampled market history with quality barriers kept visible.',
  'Theoretical discrepancies and the evidence available at each decision.',
  'Observed market behavior and explicit execution assumptions.',
  'Chronological evaluation, simple controls and complete training provenance.',
  'Frozen hypothetical decisions. Public follow-ups. No submitted orders.',
  'Models and rules frozen before future observations arrive.',
  'Independent recording, bounded research and server-authoritative health.',
];
function useEvidence(path: string, enabled = true, interval = 15000) {
  return useQuery({
    queryKey: ['reality', path],
    queryFn: () => api<Obj>(`/reality${path}`),
    enabled,
    refetchInterval: interval,
    retry: 1,
  });
}
function Status({ children, good = false }: { children: React.ReactNode; good?: boolean }) {
  return (
    <span className={`r-status ${good ? 'good' : ''}`}>
      <i />
      {children}
    </span>
  );
}
function Metric({ label, value, note }: { label: string; value: React.ReactNode; note: string }) {
  return (
    <div className="r-metric">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{note}</small>
    </div>
  );
}
function Panel({
  title,
  note,
  children,
  className = '',
}: {
  title: string;
  note?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`r-panel ${className}`}>
      <header>
        <h3>{title}</h3>
        {note && <p>{note}</p>}
      </header>
      {children}
    </section>
  );
}
function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div className="r-empty">
      <Database size={22} />
      <p>{children}</p>
    </div>
  );
}
function Evidence({
  data,
  label = 'Inspect exact evidence',
}: {
  data: Json | undefined;
  label?: string;
}) {
  return (
    <details className="r-evidence">
      <summary>
        <Fingerprint size={14} />
        {label}
      </summary>
      <pre>{JSON.stringify(data ?? null, null, 2)}</pre>
    </details>
  );
}
function ArtifactLink({ kind, children }: { kind: string; children: React.ReactNode }) {
  return (
    <a className="r-link" href={`/api/reality/artifacts/${kind}`} target="_blank" rel="noreferrer">
      {children}
      <ExternalLink size={12} />
    </a>
  );
}
function QueryState({ query }: { query: ReturnType<typeof useEvidence> }) {
  return query.isPending ? (
    <Empty>Loading versioned research evidence…</Empty>
  ) : query.isError ? (
    <Empty>{query.error.message}</Empty>
  ) : null;
}
export function Reality() {
  const [tab, setTab] = useState('Overview');
  const [condition, setCondition] = useState('');
  const [decision, setDecision] = useState('');
  const query = useEvidence('/overview');
  const data = query.data ?? {};
  const c = obj(data.collector);
  const f = obj(data.forward);
  const markets = arr(c.cohort).map(obj);
  const selected = markets.find((m) => m.condition === condition) ?? markets[0];
  return (
    <div className="reality">
      <div className="r-masthead">
        <div>
          <span className="r-kicker">
            <Radio size={14} />
            PROJECT REALITY / CALIBRATION LABORATORY
          </span>
          <h2>
            Evidence before conviction<span>.</span>
          </h2>
          <p>{descriptions[tabs.indexOf(tab)]}</p>
        </div>
        <div className="r-live">
          <Status good={data.health === 'recording'}>{txt(data.health).toUpperCase()}</Status>
          <small>{utc(c.updated_ns)}</small>
          <button
            className="r-icon"
            aria-label="Refresh Reality evidence"
            onClick={() => void query.refetch()}
          >
            <RefreshCw size={15} />
          </button>
        </div>
      </div>
      <nav className="r-tabs" aria-label="Reality research areas">
        {tabs.map((name, i) => (
          <button
            key={name}
            aria-current={tab === name ? 'page' : undefined}
            className={tab === name ? 'active' : ''}
            onClick={() => setTab(name)}
          >
            <small>{String(i + 1).padStart(2, '0')}</small>
            {name}
          </button>
        ))}
      </nav>
      <div className="r-boundary">
        <ShieldCheck size={16} />
        <span>
          <b>Public observations</b> · Unsequenced receipt-order data. Displayed quotes do not
          establish hypothetical fills, queue position or actual profitability.
        </span>
        <span className="r-boundary-end">NO ORDER EXECUTION</span>
      </div>
      {query.isPending && <Empty>Connecting to the Reality evidence service…</Empty>}
      {query.isError && (
        <div className="r-error" role="alert">
          Reality evidence unavailable: {query.error.message}.{' '}
          <button onClick={() => void query.refetch()}>Retry</button>
        </div>
      )}
      {Number(data.collector_status_age_seconds) > 30 && (
        <div className="r-error" role="alert">
          Collector status is {fmt(data.collector_status_age_seconds)} seconds old. Displayed books
          may be outdated.
        </div>
      )}
      {query.data && (
        <>
          {tab === 'Overview' && (
            <>
              <div className="r-metrics">
                <Metric
                  label="Captured public records"
                  value={fmt(c.ordinal)}
                  note={`${fmt(c.frames)} frames in the active producer epoch`}
                />
                <Metric
                  label="Observation panel"
                  value={
                    <>
                      {fmt(c.markets)}
                      <em> markets</em>
                    </>
                  }
                  note={`${fmt(c.fresh_books)} / ${fmt(c.expected_books)} books fresh at collector's 60 s threshold`}
                />
                <Metric
                  label="Raw evidence"
                  value={
                    <>
                      {fmt(Number(c.storage_bytes) / 2 ** 20, 1)}
                      <em> MiB</em>
                    </>
                  }
                  note={`${fmt(Number(obj(data.capacity).estimated_storage_seconds_remaining) / 86400, 1)} days estimated remaining at recent ingest rate`}
                />
                <Metric
                  label="Prospective decisions"
                  value={fmt(f.decisions)}
                  note={`${fmt(f.markets)} markets · ${fmt(f.families)} families · ${arr(f.days).length} UTC day(s)`}
                />
              </div>
              <div className="r-grid">
                <Panel
                  title="The observation panel"
                  note="A bounded stratified cohort. Selection is recorded; this is not a representative sample of all markets."
                >
                  <div className="r-market-list">
                    {markets.map((m) => (
                      <button
                        key={txt(m.condition)}
                        onClick={() => {
                          setCondition(txt(m.condition));
                          setTab('Live explorer');
                        }}
                      >
                        <span className="r-market-glyph">
                          {txt(m.selection_role).slice(0, 1).toUpperCase()}
                        </span>
                        <span>
                          <b>{txt(m.question)}</b>
                          <small>
                            CTF {txt(m.protocol).toUpperCase()} · {txt(m.selection_role)} ·
                            same-condition Yes / No
                          </small>
                        </span>
                        <ChevronRight size={16} />
                      </button>
                    ))}
                  </div>
                </Panel>
                <div className="r-stack">
                  <Panel
                    title="Research posture"
                    note="A completed pipeline is not a validated trading claim."
                  >
                    <div className="r-posture">
                      <span className="r-orbit">
                        <Activity size={30} />
                      </span>
                      <Status>INSUFFICIENT EVIDENCE</Status>
                      <h3>No scientific champion</h3>
                      <p>
                        Short recording coverage and missing future observations limit inference.
                        Experimental models remain ineligible for policy activation.
                      </p>
                      <button className="r-link" onClick={() => setTab('Models')}>
                        Review chronological results <ArrowUpRight size={14} />
                      </button>
                    </div>
                  </Panel>
                  <Panel title="Forward research is accumulating">
                    <dl className="r-facts">
                      <dt>Campaign</dt>
                      <dd>{txt(f.state).replaceAll('_', ' ')}</dd>
                      <dt>Measured follow-ups</dt>
                      <dd>{fmt(obj(f.followups).observed_public_measurement)}</dd>
                      <dt>Censored follow-ups</dt>
                      <dd>{fmt(obj(f.followups).censored)}</dd>
                      <dt>Actual submitted orders</dt>
                      <dd>0</dd>
                    </dl>
                    <button className="r-link" onClick={() => setTab('Forward')}>
                      Inspect frozen analysis plan <ArrowUpRight size={14} />
                    </button>
                  </Panel>
                </div>
              </div>
              <div className="r-metrics r-secondary">
                <Metric
                  label="Collector uptime"
                  value={`${fmt((Number(data.now_ns) - Number(c.started_ns)) / 3.6e12, 1)} h`}
                  note="Current producer process epoch"
                />
                <Metric
                  label="Recorded quality gaps"
                  value={fmt(c.gaps)}
                  note="Includes resynchronization, not a count of disconnects"
                />
                <Metric
                  label="Timing-uncertain books"
                  value={fmt(c.timing_uncertain_books)}
                  note="Additional to unverified venue sequencing"
                />
                <Metric
                  label="Collector failures"
                  value={fmt(c.failures)}
                  note="Current process counters"
                />
              </div>
            </>
          )}
          {(tab === 'Live explorer' || tab === 'Historical') && (
            <MarketExplorer
              markets={markets}
              selected={selected}
              collector={c}
              now={Number(data.now_ns)}
              historical={tab === 'Historical'}
              choose={setCondition}
            />
          )}
          {(tab === 'Opportunities' || tab === 'Shadow') && (
            <Decisions opportunities={tab === 'Opportunities'} onInspect={setDecision} />
          )}
          {tab === 'Calibration' && <Calibration />}
          {tab === 'Models' && <Models />}
          {tab === 'Forward' && <Forward status={f} />}
          {tab === 'Operations' && <Operations overview={data} />}
        </>
      )}
      <div className="r-provenance">
        <Fingerprint size={13} />
        <span>Server-side queries · raw archives stay on disk</span>
        <span>UTC · shares · collateral units</span>
      </div>
      {decision && <DecisionDetail uid={decision} close={() => setDecision('')} />}
    </div>
  );
}
function MarketExplorer({
  markets,
  selected,
  collector,
  now,
  historical,
  choose,
}: {
  markets: Obj[];
  selected?: Obj;
  collector: Obj;
  now: number;
  historical: boolean;
  choose: (id: string) => void;
}) {
  const [search, setSearch] = useState('');
  const [role, setRole] = useState('all');
  const [hours, setHours] = useState(1);
  const [end, setEnd] = useState(() => now);
  const [quantity, setQuantity] = useState(5);
  const [field, setField] = useState('best_ask');
  const [cursor, setCursor] = useState(0);
  const history = useEvidence(
    `/history?condition=${encodeURIComponent(txt(selected?.condition))}&start_ns=${Math.floor(end - hours * 3.6e12)}&end_ns=${Math.floor(end)}&limit=1500`,
    !!selected,
    30000,
  );
  const rows = arr(history.data?.rows).map(obj);
  const samples = rows as unknown as HistorySample[];
  const books = obj(collector.books);
  return (
    <div className="r-explorer">
      <Panel
        title="Market directory"
        note={`${markets.length} monitored markets`}
        className="r-directory"
      >
        <label className="r-search">
          <Search size={15} />
          <input
            aria-label="Search Reality markets"
            placeholder="Search markets…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
        <select
          aria-label="Filter cohort role"
          value={role}
          onChange={(e) => setRole(e.target.value)}
        >
          <option value="all">All selection roles</option>
          {[...new Set(markets.map((m) => txt(m.selection_role)))].map((r) => (
            <option key={r}>{r}</option>
          ))}
        </select>
        <div className="r-market-list">
          {markets
            .filter(
              (m) =>
                txt(m.question).toLowerCase().includes(search.toLowerCase()) &&
                (role === 'all' || m.selection_role === role),
            )
            .map((m) => (
              <button
                className={m.condition === selected?.condition ? 'selected' : ''}
                key={txt(m.condition)}
                onClick={() => choose(txt(m.condition))}
              >
                <span>
                  <b>{txt(m.question)}</b>
                  <small>
                    {txt(m.selection_role)} · {txt(m.protocol).toUpperCase()}
                  </small>
                </span>
              </button>
            ))}
        </div>
      </Panel>
      <div className="r-stack">
        {selected ? (
          <>
            <Panel
              title={txt(selected.question)}
              note={`Same-condition Yes / No CTF · ${txt(selected.protocol).toUpperCase()} · metadata record #${txt(selected.metadata_ordinal)}`}
            >
              <div className="r-tags">
                <Status good>OBSERVED PUBLIC BOOK</Status>
                <span>
                  {selected.negative_risk
                    ? 'Negative-risk group; no cross-market conversion assumed'
                    : 'Standard binary pair'}
                </span>
              </div>
              <div className="r-book-grid">
                {Object.entries(obj(selected.tokens)).map(([asset, outcome]) => {
                  const b = obj(books[asset]);
                  const age = (now - Number(b.received_ns)) / 1e9;
                  const coverage = obj(obj(collector.observation_coverage)[asset]);
                  const span =
                    (Number(coverage.last_received_ns) - Number(coverage.first_received_ns)) / 1e9;
                  const asks = arr(b.asks).map(arr);
                  let remaining = quantity;
                  let cost = 0;
                  for (const [p, q] of asks) {
                    const take = Math.min(Number(q), remaining);
                    cost += take * Number(p);
                    remaining -= take;
                  }
                  return (
                    <div key={asset} className="r-book">
                      <div className="r-book-heading">
                        <h4>{txt(outcome)}</h4>
                        <Status good={age <= 5 && !b.issue}>
                          {b.issue ? txt(b.issue) : age <= 5 ? 'FRESH ≤ 5s' : 'STALE FOR RESEARCH'}
                        </Status>
                      </div>
                      <div className="r-quotes">
                        {['best_bid', 'best_ask', 'spread'].map((k) => (
                          <div key={k}>
                            <small>{k.replaceAll('_', ' ')}</small>
                            <strong>{txt(b[k])}</strong>
                          </div>
                        ))}
                      </div>
                      <small>
                        {age.toFixed(2)} s since receipt · source #{txt(arr(b.last)[0])}
                      </small>
                      <small className="r-update-rate">
                        {fmt(coverage.book_update_frames)} book-update frames over{' '}
                        {fmt(span / 3600, 1)} h ·{' '}
                        {span > 0 ? fmt(Number(coverage.book_update_frames) / span, 3) : '—'}{' '}
                        updates/s average in this producer epoch
                      </small>
                      <div className="r-depth">
                        <div>
                          <span>Ask price</span>
                          <span>Displayed shares</span>
                        </div>
                        {asks.slice(0, 8).map(([p, q], i) => (
                          <div
                            key={i}
                            style={
                              {
                                '--depth': `${Math.min(100, (Number(q) / Math.max(...asks.slice(0, 8).map((a) => Number(a[1])))) * 100)}%`,
                              } as React.CSSProperties
                            }
                          >
                            <b>{txt(p)}</b>
                            <span>{fmt(q, 2)}</span>
                          </div>
                        ))}
                      </div>
                      <div className="r-cost">
                        Observed ask-side cost for {quantity} shares
                        <b>
                          {remaining > 0
                            ? b.depth_truncated
                              ? 'Unknown beyond depth window'
                              : 'Insufficient displayed depth'
                            : `${cost.toFixed(4)} collateral`}
                        </b>
                      </div>
                      <small>
                        Before fees.{' '}
                        {b.depth_truncated
                          ? 'Depth truncated to 50 levels.'
                          : 'Complete recorded depth window.'}{' '}
                        Display is not a fill guarantee.
                      </small>
                    </div>
                  );
                })}
              </div>
              <label className="r-inline">
                Hypothetical size{' '}
                <input
                  aria-label="Hypothetical share quantity"
                  type="number"
                  min="1"
                  max="100000"
                  value={quantity}
                  onChange={(e) =>
                    setQuantity(Math.max(1, Math.min(100000, Number(e.target.value) || 1)))
                  }
                />{' '}
                shares
              </label>
              <Evidence
                data={selected}
                label="Protocol, fees, payoff, lifecycle and source metadata"
              />
            </Panel>
            <Panel
              title="Historical observatory"
              note="Sampled public observations from the frozen forward campaign. Invalid samples break the lines; no interpolation across missing intervals."
            >
              <div className="r-toolbar">
                <select
                  aria-label="History window"
                  value={hours}
                  onChange={(e) => setHours(Number(e.target.value))}
                >
                  <option value={1}>Last hour</option>
                  <option value={6}>Last 6 hours</option>
                  <option value={24}>Last 24 hours</option>
                </select>
                <select
                  aria-label="Historical metric"
                  value={field}
                  onChange={(e) => setField(e.target.value)}
                >
                  <option value="best_ask">Best ask price</option>
                  <option value="spread">Spread</option>
                  <option value="total_ask_quantity">Displayed ask liquidity (shares)</option>
                  <option value="age_ns">Receipt age (nanoseconds)</option>
                  <option value="sampled_update_rate">Observed update-rate lower bound (/s)</option>
                </select>
                {historical && (
                  <label>
                    End UTC{' '}
                    <input
                      aria-label="Historical interval end UTC"
                      type="datetime-local"
                      value={new Date(end / 1e6).toISOString().slice(0, 16)}
                      onChange={(e) => {
                        const value = Date.parse(e.target.value + 'Z');
                        if (Number.isFinite(value)) setEnd(value * 1e6);
                      }}
                    />
                  </label>
                )}
                <button onClick={() => setEnd(Date.now() * 1e6)}>Latest interval</button>
                <span>{rows.length} sampled states</span>
                {field === 'sampled_update_rate' && (
                  <small>
                    One confirmed lineage change per interval is counted. Multiple updates between
                    samples are unresolved; this is a lower bound, not venue message intensity.
                  </small>
                )}
              </div>
              {history.isError ? (
                <Empty>{history.error.message}</Empty>
              ) : !rows.length ? (
                <Empty>
                  {history.isPending
                    ? 'Loading selected interval…'
                    : 'No sampled observations in this interval. Earlier raw records remain preserved; this index begins with the forward campaign.'}
                </Empty>
              ) : (
                <>
                  <Chart
                    label="Historical complementary outcome asks"
                    option={{
                      ...chartBase,
                      legend: { top: 8, textStyle: { color: '#a1a9b8', fontSize: 9 } },
                      grid: { left: 45, right: 20, top: 50, bottom: 35 },
                      xAxis: {
                        ...chartBase.xAxis,
                        type: 'time',
                        axisLabel: {
                          formatter: (value: number) => new Date(value).toISOString().slice(11, 19),
                        },
                      },
                      yAxis: {
                        ...chartBase.yAxis,
                        name:
                          field === 'total_ask_quantity'
                            ? 'shares'
                            : field === 'sampled_update_rate'
                              ? 'updates / s (lower bound)'
                              : field === 'age_ns'
                                ? 'nanoseconds'
                                : 'collateral / share',
                      },
                      series: ['yes', 'no'].map((leg, i) => ({
                        name: `${leg.toUpperCase()} ${field.replaceAll('_', ' ')}`,
                        type: 'line',
                        showSymbol: false,
                        connectNulls: false,
                        lineStyle: { width: 1.5, color: i ? '#75b6c8' : '#d3ab61' },
                        data: historySeries(rows as unknown as HistorySample[], leg, field),
                      })),
                    }}
                  />
                  <div className="r-quality-band">
                    {rows.map((r, i) => (
                      <i
                        key={i}
                        className={historyBarrier(samples[i], samples[i - 1]) ? 'gap' : ''}
                        title={`${utc(r.ns)} · ${historyBarrier(samples[i], samples[i - 1]) ?? 'eligible sampled state'}`}
                      />
                    ))}
                  </div>
                  <small>
                    Gold: quality barrier, missing interval or snapshot resynchronization between
                    samples; exact interruption time inside that interval is unresolved. Green:
                    eligible sampled state. Nothing between samples is implied.
                  </small>
                  <div className="r-replay">
                    <label>
                      Replay sampled interval{' '}
                      <input
                        type="range"
                        aria-label="Replay historical observations"
                        min="0"
                        max={rows.length - 1}
                        value={Math.min(cursor, rows.length - 1)}
                        onChange={(e) => setCursor(Number(e.target.value))}
                      />
                    </label>
                    <span>
                      {utc(rows[Math.min(cursor, rows.length - 1)]?.ns)} · sample{' '}
                      {Math.min(cursor + 1, rows.length)} / {rows.length}
                    </span>
                    <Evidence
                      data={rows[Math.min(cursor, rows.length - 1)]}
                      label="Selected historical state and source ordinals"
                    />
                  </div>
                  <details className="r-evidence">
                    <summary>Inspect sampled spreads, liquidity and events</summary>
                    <div className="r-table-wrap">
                      <table>
                        <thead>
                          <tr>
                            <th>UTC observation</th>
                            <th>YES ask / spread</th>
                            <th>NO ask / spread</th>
                            <th>YES ask depth</th>
                            <th>Quality</th>
                            <th>Event</th>
                          </tr>
                        </thead>
                        <tbody>
                          {rows
                            .slice(-100)
                            .reverse()
                            .map((r) => {
                              const y = obj(obj(r.legs).yes);
                              const n = obj(obj(r.legs).no);
                              return (
                                <tr key={txt(r.event_seq)}>
                                  <td>{utc(r.ns)}</td>
                                  <td>
                                    {txt(y.best_ask)} / {txt(y.spread)}
                                  </td>
                                  <td>
                                    {txt(n.best_ask)} / {txt(n.spread)}
                                  </td>
                                  <td>{fmt(y.total_ask_quantity, 2)} sh</td>
                                  <td>{r.quality_reason ? txt(r.quality_reason) : 'Eligible'}</td>
                                  <td>
                                    <Evidence data={r} label={`#${txt(r.event_seq)}`} />
                                  </td>
                                </tr>
                              );
                            })}
                        </tbody>
                      </table>
                    </div>
                  </details>
                  {history.data?.truncated && (
                    <p className="r-warning">
                      1,500-state bound reached. Narrow the interval for all samples.
                    </p>
                  )}
                </>
              )}
            </Panel>
          </>
        ) : (
          <Empty>No monitored markets are available yet.</Empty>
        )}
      </div>
    </div>
  );
}
function Decisions({
  opportunities,
  onInspect,
}: {
  opportunities: boolean;
  onInspect: (uid: string) => void;
}) {
  const [before, setBefore] = useState('');
  const [only, setOnly] = useState(opportunities);
  const query = useEvidence(`/decisions?limit=40${before ? `&before_ns=${before}` : ''}`);
  const rows = arr(query.data?.rows).map(obj);
  const shown = only ? rows.filter((r) => obj(r.baseline).opportunity === true) : rows;
  return (
    <Panel
      title={opportunities ? 'Observed opportunity candidates' : 'Prospective decision journal'}
      note="Frozen decisions on genuine public observations. Apparent edge is before execution uncertainty; missing initial states abstain."
    >
      <div className="r-toolbar">
        <label>
          <input type="checkbox" checked={only} onChange={(e) => setOnly(e.target.checked)} /> Only
          positive theoretical discrepancies
        </label>
        <span>{rows.length} decisions in this page</span>
        <button
          onClick={() => {
            setBefore('');
            void query.refetch();
          }}
        >
          Latest
        </button>
      </div>
      {query.isError ? (
        <Empty>{query.error.message}</Empty>
      ) : !shown.length ? (
        <Empty>
          {query.isPending
            ? 'Loading immutable decisions…'
            : only
              ? 'No positive theoretical discrepancy in this page. Abstentions are evidence; no executable profit is inferred.'
              : 'No prospective decisions yet.'}
        </Empty>
      ) : (
        <div className="r-table-wrap">
          <table>
            <thead>
              <tr>
                <th>Decision UTC</th>
                <th>Market</th>
                <th>Initial state</th>
                <th>Observed cost / 5 shares</th>
                <th>Policy behavior</th>
                <th>Replay</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((r) => {
                const b = obj(r.baseline);
                const a = obj(b.acquisition);
                return (
                  <tr key={txt(r.id)}>
                    <td>
                      {utc(r.decision_ns)}
                      <small>source #{txt(r.decision_ordinal)}</small>
                    </td>
                    <td>
                      {txt(r.market_title)}
                      <small>{short(r.condition)}</small>
                    </td>
                    <td>
                      <Status good={!!r.baseline}>
                        {r.quality_reason
                          ? txt(r.quality_reason)
                          : b.opportunity
                            ? 'THEORETICAL DISCREPANCY'
                            : 'NO DISCREPANCY'}
                      </Status>
                    </td>
                    <td>
                      {r.baseline
                        ? (Number(obj(a.yes).value) + Number(obj(a.no).value)).toFixed(4)
                        : 'Unknown'}
                      <small>collateral · before fees</small>
                    </td>
                    <td>
                      {arr(r.policies).filter((p) => obj(p).action === 'abstain').length} /{' '}
                      {arr(r.policies).length} abstain
                    </td>
                    <td>
                      <button className="r-link" onClick={() => onInspect(txt(r.id))}>
                        Inspect <ArrowUpRight size={13} />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {query.data?.has_more && (
        <button
          className="r-page-button"
          onClick={() => setBefore(txt(rows[rows.length - 1]?.decision_ns))}
        >
          Earlier decisions <ChevronRight size={14} />
        </button>
      )}
    </Panel>
  );
}
function DecisionDetail({ uid, close }: { uid: string; close: () => void }) {
  const dialogRef = useRef<HTMLElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    dialogRef.current?.focus();
    function key(event: KeyboardEvent) {
      if (event.key === 'Escape') close();
      if (event.key === 'Tab') {
        const elements = dialogRef.current?.querySelectorAll<HTMLElement>(
          'button,a,input,select,summary',
        );
        if (!elements?.length) return;
        const first = elements[0],
          last = elements[elements.length - 1];
        if (
          event.shiftKey &&
          (document.activeElement === first || document.activeElement === dialogRef.current)
        ) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    }
    document.addEventListener('keydown', key);
    return () => {
      document.removeEventListener('keydown', key);
      previous?.focus();
    };
  }, [close]);
  const query = useEvidence(`/decisions/${uid}`);
  const d = obj(query.data?.decision);
  const ref = obj(d.source_record_ref);
  const [source, setSource] = useState(false);
  const raw = useEvidence(
    `/records/${txt(ref.ordinal)}?segment=${txt(ref.segment)}&offset=${txt(ref.offset)}`,
    source && !!ref.segment,
    60000,
  );
  return (
    <div className="r-modal-backdrop" onClick={close}>
      <section
        ref={dialogRef}
        tabIndex={-1}
        className="r-modal"
        role="dialog"
        aria-modal="true"
        aria-label="Frozen decision replay"
        onClick={(e) => e.stopPropagation()}
      >
        <header>
          <div>
            <span className="r-kicker">FROZEN DECISION REPLAY</span>
            <h2>{txt(d.market_title)}</h2>
          </div>
          <button className="r-icon" aria-label="Close decision replay" onClick={close}>
            <X />
          </button>
        </header>
        <QueryState query={query} />
        {query.data && (
          <>
            <p>
              {utc(d.decision_ns)} · durable commit {utc(query.data.commit_ns)}
            </p>
            <div className="r-warning">
              All execution scenarios and P&amp;L bounds are hypothetical. Actual fills remain
              unknown.
            </div>
            <dl className="r-facts">
              <dt>Decision identity</dt>
              <dd className="r-hash">{uid}</dd>
              <dt>Source revision</dt>
              <dd>
                {txt(d.reconstruction_version)} / {short(d.producer_implementation_sha256)}
              </dd>
              <dt>Input lag / computation</dt>
              <dd>
                {fmt(Number(d.source_input_lag_ns) / 1e6, 2)} /{' '}
                {fmt(Number(d.decision_latency_ns) / 1e6, 2)} ms
              </dd>
              <dt>Quality</dt>
              <dd>{d.quality_reason ? txt(d.quality_reason) : 'Eligible under frozen rules'}</dd>
            </dl>
            <Panel title="Frozen policy actions">
              {arr(d.policies)
                .map(obj)
                .map((p) => (
                  <div className="r-policy" key={txt(p.policy)}>
                    <b>{txt(p.policy).replaceAll('_', ' ')}</b>
                    <Status>{txt(p.action).toUpperCase()}</Status>
                    <span>{txt(p.reason).replaceAll('_', ' ')}</span>
                  </div>
                ))}
            </Panel>
            <Panel title="Later observations, kept separate">
              {arr(query.data.outcomes)
                .map(obj)
                .map((o) => (
                  <div key={txt(o.horizon_ms)}>
                    <div className="r-policy">
                      <b>{txt(o.horizon_ms)} ms</b>
                      <Status good={obj(o.labels).status === 'observed_public_measurement'}>
                        {txt(obj(o.labels).status)}
                      </Status>
                      <span>{txt(obj(o.labels).reason)}</span>
                    </div>
                    {arr(o.execution).length > 0 && (
                      <div className="r-table-wrap">
                        <table>
                          <thead>
                            <tr>
                              <th>Hypothetical scenario / policy</th>
                              <th>Outcome state</th>
                              <th>Hypothetical P&amp;L bounds</th>
                              <th>Unmatched shares</th>
                            </tr>
                          </thead>
                          <tbody>
                            {arr(o.execution)
                              .map(obj)
                              .flatMap((s) =>
                                arr(s.policy_results)
                                  .map(obj)
                                  .map((p) => {
                                    const e = obj(p.execution);
                                    return (
                                      <tr key={`${txt(s.scenario)}-${txt(p.policy)}`}>
                                        <td>
                                          {txt(s.scenario)} / {txt(p.policy)}
                                        </td>
                                        <td>{txt(e.status)}</td>
                                        <td>
                                          {e.hypothetical_pnl_bounds
                                            ? arr(e.hypothetical_pnl_bounds)
                                                .map((v) => fmt(v, 4))
                                                .join(' to ')
                                            : 'Unknown'}
                                          <small>collateral units, conditional assumptions</small>
                                        </td>
                                        <td>{fmt(e.unmatched_quantity, 4)}</td>
                                      </tr>
                                    );
                                  }),
                              )}
                          </tbody>
                        </table>
                      </div>
                    )}
                    <Evidence
                      data={o}
                      label="Labels, hypothetical scenarios and future source references"
                    />
                  </div>
                ))}
            </Panel>
            <Evidence data={d.features} label="Only decision-time features" />
            <Evidence
              data={d.predictions}
              label="Experimental predictions and frozen model hashes"
            />
            <Evidence data={d.feature_sources} label="Exact raw source lineage" />
            <Evidence
              data={d.baseline}
              label="Initial books and displayed acquisition / exit calculations"
            />
            <button className="r-page-button" onClick={() => setSource(true)}>
              Verify exact input source record <Fingerprint size={14} />
            </button>
            {source &&
              (raw.isError ? (
                <p role="alert">{raw.error.message}</p>
              ) : (
                <Evidence
                  data={raw.data}
                  label={
                    raw.isPending ? 'Loading source record…' : 'Checksum-verified raw input record'
                  }
                />
              ))}
          </>
        )}
      </section>
    </div>
  );
}
function Calibration() {
  const query = useEvidence('/artifacts/calibration', true, 60000);
  const d = obj(query.data?.data);
  const o = obj(d.overall);
  const p = obj(o.quote_persistence);
  const metrics = obj(o.metrics);
  const horizons = obj(d.horizons);
  const synthetic = obj(d.synthetic_comparison);
  return (
    <>
      <QueryState query={query} />
      <div className="r-metrics">
        <Metric
          label="Calibration anchors"
          value={fmt(o.anchors)}
          note={`${fmt(o.markets)} markets · ${fmt(o.families)} families · ${arr(o.days).length} UTC day(s)`}
        />
        <Metric
          label="Known future measurements"
          value={fmt(p.measured)}
          note={`${fmt(p.unknown)} unknown across horizons`}
        />
        <Metric
          label="Depth retention, measured mean"
          value={pct(obj(metrics.original_quote_depth_retention).mean)}
          note="Conditional on available observations; not a fill fraction"
        />
        <Metric
          label="Completed quote spells"
          value={fmt(obj(obj(d.receipt_observed_dynamics).completed_quote_spells_ms).count)}
          note="Right-censoring prevents a venue lifetime estimate"
        />
      </div>
      <div className="r-grid">
        <Panel
          title="Quote persistence and missingness"
          note="Conditional rates omit unknown futures. Identification bounds retain that uncertainty."
        >
          <Chart
            label="Measured persistence and missingness bounds by delay"
            option={{
              ...chartBase,
              legend: { top: 8, textStyle: { color: '#a1a9b8', fontSize: 9 } },
              grid: { left: 45, right: 20, top: 50, bottom: 35 },
              xAxis: { ...chartBase.xAxis, data: Object.keys(horizons).map((h) => `${h} ms`) },
              yAxis: { ...chartBase.yAxis, min: 0, max: 1 },
              series: [
                {
                  name: 'Conditional measured rate',
                  type: 'line',
                  data: Object.values(horizons).map(
                    (v) => obj(obj(v).quote_persistence).conditional_measured_rate,
                  ),
                  itemStyle: { color: '#d3ab61' },
                },
                {
                  name: 'Missingness lower bound',
                  type: 'line',
                  data: Object.values(horizons).map(
                    (v) =>
                      arr(obj(obj(v).quote_persistence).missing_outcome_identification_bounds)[0],
                  ),
                  itemStyle: { color: '#77b7a0' },
                },
                {
                  name: 'Missingness upper bound',
                  type: 'line',
                  data: Object.values(horizons).map(
                    (v) =>
                      arr(obj(obj(v).quote_persistence).missing_outcome_identification_bounds)[1],
                  ),
                  lineStyle: { type: 'dashed' },
                  itemStyle: { color: '#778294' },
                },
              ],
            }}
          />
          <div className="r-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Delay</th>
                  <th>Measured</th>
                  <th>Unknown</th>
                  <th>Identification range</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(horizons).map(([h, v]) => {
                  const q = obj(obj(v).quote_persistence);
                  return (
                    <tr key={h}>
                      <td>{h} ms</td>
                      <td>{fmt(q.measured)}</td>
                      <td>{fmt(q.unknown)}</td>
                      <td>{arr(q.missing_outcome_identification_bounds).map(pct).join(' – ')}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Panel>
        <Panel
          title="Reality versus synthetic controls"
          note="Separate evidence classes. Original synthetic artifacts remain unchanged."
        >
          <div className="r-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Distribution median</th>
                  <th>Observed</th>
                  <th>Synthetic</th>
                </tr>
              </thead>
              <tbody>
                {['spread', 'top_ask_quantity'].map((k) => (
                  <tr key={k}>
                    <td>{k.replaceAll('_', ' ')}</td>
                    <td>{fmt(obj(obj(metrics[k]).quantiles)['0.5'], 5)}</td>
                    <td>{fmt(obj(obj(obj(synthetic.metrics)[k]).quantiles)['0.5'], 5)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="r-body-copy">
            Synthetic controls contain deliberately constructed opportunities and synchronized
            updates. Their frequencies are not estimates of real-market prevalence.
          </p>
          <Evidence
            data={synthetic}
            label="Original generator, seeds, assumptions and comparison limits"
          />
          <Evidence
            data={d.receipt_observed_dynamics}
            label="Receipt-time dynamics and censor reasons"
          />
        </Panel>
      </div>
      <Panel
        title="Displayed depth retention and adverse quotes"
        note="Means among measurable public futures; unavailable horizons stay unknown. Depth is displayed quantity, never hypothetical fills."
      >
        <Chart
          label="Measured depth retention and adverse quote movement by horizon"
          option={{
            ...chartBase,
            legend: { top: 8, textStyle: { color: '#a1a9b8', fontSize: 9 } },
            grid: { left: 55, right: 70, top: 50, bottom: 35 },
            xAxis: { ...chartBase.xAxis, data: Object.keys(horizons).map((h) => `${h} ms`) },
            yAxis: [
              { ...chartBase.yAxis, min: 0, max: 1, name: 'depth fraction' },
              { ...chartBase.yAxis, name: 'adverse collateral/share', position: 'right', min: 0 },
            ],
            series: [
              {
                name: 'Mean original-quote depth retention',
                type: 'line',
                data: Object.values(horizons).map(
                  (v) => obj(obj(obj(v).metrics).original_quote_depth_retention).mean ?? null,
                ),
                itemStyle: { color: '#75b6c8' },
              },
              {
                name: 'Mean adverse ask movement',
                type: 'bar',
                yAxisIndex: 1,
                data: Object.values(horizons).map(
                  (v) => obj(obj(obj(v).metrics).adverse_ask_movement).mean ?? null,
                ),
                itemStyle: { color: '#d3ab61' },
              },
            ],
          }}
        />
        <Evidence
          data={Object.fromEntries(
            Object.entries(horizons).map(([h, v]) => [
              h,
              {
                depth: obj(obj(v).metrics).original_quote_depth_retention ?? null,
                adverse: obj(obj(v).metrics).adverse_ask_movement ?? null,
              },
            ]),
          )}
          label="Per-horizon distributions, tail quantiles and sample counts"
        />
      </Panel>
      <Panel
        title="Four execution scenarios"
        note="Imposed counterfactual assumptions, not identified execution probabilities."
      >
        <div className="r-scenarios">
          {[
            [
              'Optimistic',
              '100 ms',
              '100% displayed depth',
              'Favorable availability; no future observation required',
            ],
            [
              'Intermediate',
              '300 ms',
              '80% displayed depth',
              'Observed future + 0.001 per-share friction',
            ],
            [
              'Conservative',
              '1,000 ms',
              '50% displayed depth',
              'Strict timing + 0.005 per-share friction',
            ],
            [
              'Stress',
              '5,000 ms',
              '25% displayed depth',
              'Cheaper leg disappears; recovery may fail',
            ],
          ].map(([name, delay, depth, note]) => (
            <div key={name}>
              <small>HYPOTHETICAL</small>
              <h4>{name}</h4>
              <strong>{delay}</strong>
              <p>{depth}</p>
              <span>{note}</span>
            </div>
          ))}
        </div>
        <Evidence
          data={d.economic_sensitivity}
          label="Sizing / capital sensitivity and exact assumption identities"
        />
      </Panel>
      <ArtifactLink kind="calibration">
        Calibration artifact · {short(query.data?.file_sha256)}
      </ArtifactLink>
    </>
  );
}
function Models() {
  const query = useEvidence('/artifacts/training', true, 60000);
  const d = obj(query.data?.data);
  const targets = obj(d.targets);
  const [calibrationTarget, setCalibrationTarget] = useState('market_disruption');
  const target = obj(targets[calibrationTarget]);
  const candidate =
    arr(target.candidates)
      .map(obj)
      .find((c) => c.model_id === target.selected_by_validation) ?? obj(arr(target.candidates)[0]);
  const bins = arr(obj(candidate.test).calibration)
    .map(obj)
    .filter((b) => Number(b.count) > 0);
  const dataset = useEvidence('/artifacts/dataset', true, 60000);
  return (
    <>
      <QueryState query={query} />
      <div className="r-warning">
        <ShieldCheck size={16} />
        <span>
          <b>No scientific champion.</b> Single-day coverage is insufficient for activation. Target
          accuracy does not establish hypothetical decision usefulness.
        </span>
      </div>
      <div className="r-metrics">
        <Metric
          label="Preserved model artifacts"
          value={fmt(d.model_count)}
          note="Includes constant and heuristic controls"
        />
        <Metric
          label="Training wall time"
          value={`${fmt(d.elapsed_seconds, 1)} s`}
          note="Bounded worker; not a repeated benchmark"
        />
        <Metric
          label="Evaluation"
          value="Chronological"
          note="Train / validation / frozen final test + embargo"
        />
        <Metric
          label="Policy eligibility"
          value="Insufficient"
          note="No automatic promotion or final-test retuning"
        />
      </div>
      <Panel
        title="What the held-out evidence says"
        note="Frozen final-test findings; no variants are selected against this opened period."
      >
        <p className="r-body-copy">
          Risk-model validation gains did not survive the final test. The selected tree's Brier
          score was 0.3091 versus 0.1982 for the constant control (lower is better). For depth
          retention, the unchanged-depth heuristic outperformed learned alternatives.
          Quote-persistence labels were positive-only, adverse movement was zero in measured
          samples, and no initial positive opportunity supported an opportunity-persistence learner.
        </p>
      </Panel>
      <Panel
        title="Held-out probability calibration"
        note="Observed positive rates among measurable futures, conditional on evidence availability. Empty probability bins are omitted; no private execution probability is inferred."
      >
        <div className="r-toolbar">
          <select
            aria-label="Probability calibration target"
            value={calibrationTarget}
            onChange={(e) => setCalibrationTarget(e.target.value)}
          >
            {['market_disruption', 'quote_persistence', 'opportunity_persistence'].map((k) => (
              <option key={k} value={k}>
                {k.replaceAll('_', ' ')}
              </option>
            ))}
          </select>
          <span>{txt(candidate.family)} · validation-selected, not promoted</span>
        </div>
        {bins.length ? (
          <Chart
            label="Final test predicted versus observed probabilities"
            option={{
              ...chartBase,
              grid: { left: 50, right: 25, top: 40, bottom: 45 },
              xAxis: {
                ...chartBase.xAxis,
                type: 'value',
                min: 0,
                max: 1,
                name: 'predicted',
                nameLocation: 'middle',
                nameGap: 25,
              },
              yAxis: { ...chartBase.yAxis, min: 0, max: 1, name: 'observed' },
              series: [
                {
                  name: 'Perfect calibration reference',
                  type: 'line',
                  data: [
                    [0, 0],
                    [1, 1],
                  ],
                  showSymbol: false,
                  lineStyle: { type: 'dashed', color: '#485568' },
                },
                {
                  name: 'Measured bins',
                  type: 'line',
                  lineStyle: { color: '#d3ab61' },
                  itemStyle: { color: '#d3ab61' },
                  symbolSize: 8,
                  data: bins.map((b) => [b.predicted, b.observed]),
                },
              ],
            }}
          />
        ) : (
          <Empty>No supported calibration bins for this target.</Empty>
        )}
        <Evidence data={bins} label="Bin counts, mean predictions and observed rates" />
      </Panel>
      {Object.entries(targets).map(([name, value]) => {
        const t = obj(value);
        return (
          <Panel
            key={name}
            title={name.replaceAll('_', ' ')}
            note="Recorded public target · predictions conditional on measurable future observations"
          >
            <div className="r-table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Model / control</th>
                    <th>Final-test score ↓</th>
                    <th>Measured targets</th>
                    <th>Grouped score interval</th>
                    <th>Model identity</th>
                  </tr>
                </thead>
                <tbody>
                  {arr(t.candidates)
                    .map(obj)
                    .map((c) => {
                      const test = obj(c.test);
                      const interval = arr(test.exploratory_grouped_score_95);
                      return (
                        <tr key={txt(c.model_id)}>
                          <td>
                            {txt(c.family)}
                            <small>{txt(test.score_kind)}</small>
                          </td>
                          <td>{fmt(test.score, 6)}</td>
                          <td>{fmt(obj(test.coverage).measured_targets)}</td>
                          <td>
                            {interval.length
                              ? interval.map((v) => fmt(v, 4)).join(' – ')
                              : 'Unsupported'}
                          </td>
                          <td>
                            <span className="r-hash">{short(c.model_id)}</span>
                            <Evidence
                              data={c}
                              label="Metrics, calibration, slices and eligibility"
                            />
                          </td>
                        </tr>
                      );
                    })}
                </tbody>
              </table>
            </div>
            <Evidence data={t} label="Target support, selection and provenance" />
          </Panel>
        );
      })}
      <Panel title="Dataset and training lineage">
        <p className="r-body-copy">
          Genuine public recording. Preprocessing uses training partitions only. Connected market
          families and shared feed windows are grouped. Frozen final-test outcomes cannot select a
          new variant.
        </p>
        <Evidence
          data={dataset.data?.data}
          label="Immutable dataset coverage, chronological splits and builder identity"
        />
        <ArtifactLink kind="dataset">Source dataset manifest</ArtifactLink>
        <Evidence data={d.identity} label="Dataset identity, split rules, seeds and frozen code" />
        <Evidence data={d.source_audit} label="Independent source arithmetic audit" />
        <Evidence data={d.limitations} label="Scientific limitations" />
        <ArtifactLink kind="training">
          Versioned training report · {short(query.data?.file_sha256)}
        </ArtifactLink>
      </Panel>
    </>
  );
}
function Forward({ status }: { status: Obj }) {
  const planQuery = useEvidence('/artifacts/campaign', true, 60000);
  const query = useEvidence('/forward?limit=500');
  const d = query.data ?? {};
  const plan = obj(obj(planQuery.data?.data).identity);
  const coverage = obj(d.coverage);
  return (
    <>
      <QueryState query={query} />
      <div className="r-forward-banner">
        <div>
          <span className="r-kicker">GENUINELY PROSPECTIVE / EXPERIMENTAL</span>
          <h3>Freeze first. Observe what follows.</h3>
          <p>
            {utc(plan.start_ns)} <span>→</span> {utc(plan.end_ns)}
          </p>
        </div>
        <Status good={status.state === 'FORWARD_EVALUATING_EXPERIMENTAL'}>
          {txt(status.state).replaceAll('_', ' ')}
        </Status>
      </div>
      <div className="r-metrics">
        <Metric
          label="Total durable decisions"
          value={fmt(status.decisions)}
          note="Full campaign counters; report uses latest 500"
        />
        <Metric
          label="Matched report decisions"
          value={fmt(coverage.decisions)}
          note={`${fmt(coverage.markets)} markets · ${fmt(coverage.connected_families)} families`}
        />
        <Metric
          label="Independent UTC days"
          value={arr(coverage.utc_days).length}
          note={`${fmt(coverage.shared_feed_time_blocks)} shared feed blocks; correlated decisions are not independent`}
        />
        <Metric
          label="Measured / censored follow-ups"
          value={`${fmt(obj(status.followups).observed_public_measurement)} / ${fmt(obj(status.followups).censored)}`}
          note="Full campaign counters; unknown does not mean failure"
        />
      </div>
      <div className="r-grid">
        <Panel
          title="Matched frozen controls"
          note="Policies see the same inputs. Abstention is a valid result."
        >
          {Object.entries(obj(d.policy_actions)).map(([name, actions]) => (
            <div className="r-policy" key={name}>
              <b>{name.replaceAll('_', ' ')}</b>
              <span>
                {Object.entries(obj(actions))
                  .map(([k, v]) => `${fmt(v)} ${k}`)
                  .join(' · ')}
              </span>
            </div>
          ))}
          <Evidence data={d.policy_reasons} label="Abstention reasons by policy" />
        </Panel>
        <Panel
          title="Observable persistence"
          note="Conditional rates and missingness bounds, not fill probabilities."
        >
          {Object.entries(obj(d.horizons)).map(([h, v]) => {
            const p = obj(v);
            return (
              <div key={h} className="r-policy">
                <b>{h} ms</b>
                <span>
                  {fmt(p.measured)} measured / {fmt(p.unknown)} unknown
                </span>
                <span>{pct(p.conditional_persistence)} conditional</span>
              </div>
            );
          })}
          <Evidence
            data={d.horizons}
            label="Eligibility, censor reasons and identification bounds"
          />
        </Panel>
      </div>
      <Panel
        title="Hypothetical economic outcomes"
        note="Per-trial scenario bounds cannot be summed into realized portfolio money."
      >
        <Evidence
          data={d.scenarios}
          label="Matched scenarios, unmatched positions, recovery and hypothetical P&L bounds"
        />
        <p className="r-body-copy">
          Without hypothetical actions and measurable follow-ups, monetary estimates remain
          unavailable. Zero submitted orders is an operating boundary, not proof of profitable
          abstention.
        </p>
      </Panel>
      <Panel title="Immutable evaluation contract">
        <dl className="r-facts">
          <dt>Campaign identity</dt>
          <dd className="r-hash">{txt(status.campaign_id)}</dd>
          <dt>Frozen before start</dt>
          <dd>{utc(plan.frozen_ns)}</dd>
          <dt>Feature / label definitions</dt>
          <dd>
            {txt(plan.feature_version)} / {txt(plan.label_version)}
          </dd>
          <dt>Proposed size / capital</dt>
          <dd>
            {txt(plan.quantity)} shares / {txt(plan.capital)} hypothetical collateral
          </dd>
        </dl>
        <Evidence
          data={plan}
          label="Frozen models, controls, code hashes, risk limits and analysis plan"
        />
        <ArtifactLink kind="campaign">Frozen campaign artifact</ArtifactLink>
        <ArtifactLink kind="integrity">Latest frozen integrity check</ArtifactLink>
      </Panel>
    </>
  );
}
function Operations({ overview }: { overview: Obj }) {
  const query = useEvidence('/operations');
  const [result, setResult] = useState('');
  const [busy, setBusy] = useState(false);
  const capacity = obj(overview.capacity);
  async function operate(action: string) {
    setBusy(true);
    try {
      const r = await api<Obj>(`/reality/operations/${action}`, { method: 'POST' });
      setResult(
        `${action}: ${r.accepted ? 'accepted by systemd' : 'not accepted'}. Check latest service state.`,
      );
      void query.refetch();
    } catch (e) {
      setResult(e instanceof Error ? e.message : 'Operation failed');
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <QueryState query={query} />
      <div className="r-metrics">
        <Metric
          label="Raw storage budget"
          value={`${fmt(Number(capacity.budget_bytes) / 2 ** 30)} GiB`}
          note="Original observations are never silently deleted"
        />
        <Metric
          label="Compressed ingest"
          value={`${fmt(Number(capacity.estimated_bytes_per_day) / 2 ** 30, 2)} GiB/day`}
          note="Recent measured rate; future growth may change"
        />
        <Metric
          label="Filesystem free"
          value={`${fmt(Number(capacity.filesystem_free_bytes) / 2 ** 30, 1)} GiB`}
          note={`${fmt(Number(capacity.free_disk_reserve_bytes) / 2 ** 30)} GiB protected reserve`}
        />
        <Metric
          label="Action horizon"
          value={`${fmt(Number(capacity.estimated_storage_seconds_remaining) / 86400, 1)} days`}
          note={`Measured ${utc(capacity.measured_ns)}`}
        />
      </div>
      <Panel
        title="Independent background services"
        note="Recorder and prospective evaluation continue when this interface is closed."
      >
        <div className="r-table-wrap">
          <table>
            <thead>
              <tr>
                <th>Service</th>
                <th>State</th>
                <th>PID</th>
                <th>Restarts</th>
                <th>Cgroup memory</th>
              </tr>
            </thead>
            <tbody>
              {arr(query.data?.services)
                .map(obj)
                .map((s) => {
                  const p = obj(s.properties);
                  return (
                    <tr key={txt(s.unit)}>
                      <td>{txt(s.unit)}</td>
                      <td>
                        <Status good={p.ActiveState === 'active'}>
                          {s.available
                            ? `${txt(p.ActiveState)} / ${txt(p.SubState)}`
                            : 'Unavailable'}
                        </Status>
                      </td>
                      <td>{txt(p.MainPID)}</td>
                      <td>{txt(p.NRestarts)}</td>
                      <td>
                        {Number.isFinite(Number(p.MemoryCurrent))
                          ? `${fmt(Number(p.MemoryCurrent) / 2 ** 20, 1)} MiB`
                          : '—'}
                      </td>
                    </tr>
                  );
                })}
            </tbody>
          </table>
        </div>
      </Panel>
      <div className="r-grid">
        <Panel
          title="Safe operational controls"
          note="Fixed server operations recorded in an audit. Never restart the collector or retune this campaign."
        >
          <div className="r-controls">
            {[
              ['check-capacity', 'Check capacity'],
              ['check-integrity', 'Check frozen integrity'],
              ['pause-schedule', 'Pause future research schedule'],
              ['resume-schedule', 'Resume future research schedule'],
            ].map(([action, label]) => (
              <button key={action} disabled={busy} onClick={() => void operate(action)}>
                <Activity size={14} />
                {label}
              </button>
            ))}
          </div>
          <p role="status" className="r-body-copy">
            {result}
          </p>
          <small>
            Pausing affects future scheduled jobs. An already-running job continues. Collector
            replacement uses documented deployment gates.
          </small>
        </Panel>
        <Panel title="Capacity alerts">
          {arr(capacity.alerts).length ? (
            <Evidence data={capacity.alerts} label="Current alerts" />
          ) : (
            <div className="r-posture">
              <ShieldCheck size={26} />
              <h3>No capacity alerts recorded</h3>
              <p>Read alongside the measurement timestamp and current disk headroom.</p>
            </div>
          )}
        </Panel>
      </div>
      <Panel title="Server-authoritative configuration">
        <Evidence data={query.data?.configuration} label="Collector configuration" />
        <Evidence
          data={query.data?.storage_policy}
          label="Storage budgets, retention classes and archival rules"
        />
        <Evidence data={overview.schedule} label="Durable dataset / training schedule" />
        <Evidence data={overview.integrity} label="Frozen forward integrity result" />
        <Evidence
          data={obj(overview.collector).book_comparisons}
          label="Independent public book comparisons"
        />
        <Evidence
          data={obj(overview.collector).clock_health}
          label="Kernel clock health and limits"
        />
        <ArtifactLink kind="capacity">Exact capacity report</ArtifactLink>
      </Panel>
    </>
  );
}
