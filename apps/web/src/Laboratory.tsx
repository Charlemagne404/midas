import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Activity,
  ArrowLeft,
  ArrowRight,
  Download,
  FlaskConical,
  Pause,
  Play,
  RotateCcw,
  ShieldAlert,
  Square,
} from 'lucide-react';
import { api } from './api';

type Configuration = {
  preset: string;
  runs: number;
  seed: number;
  families: string[];
  strategies: string[];
  models: string[];
  dataset_id: string | null;
  workers: number;
  memory_mb: number;
  max_wall_seconds: number;
  max_disk_mb: number;
  observation_latency_ms: number;
  submission_latency_ms: number | null;
  fee_rate: string | null;
  liquidity_fraction: string | null;
  capital: string;
  limits: Record<string, string | number | boolean>;
  costs: Record<string, unknown>;
  adversarial: boolean;
};
type Campaign = {
  id: string;
  status: string;
  spec: Configuration;
  completed: number;
  total: number;
  remaining: number;
  passed: number;
  failed: number;
  elapsed_seconds: number;
  runs_per_second: number;
  events_per_second: number;
  process_peak_rss_mb: number;
  worst_pnl: number | null;
  mean_pnl: number | null;
  error: string | null;
};
type Catalog = {
  families: string[];
  strategies: string[];
  models: string[];
  presets: Record<string, number>;
  default_config: Configuration;
  datasets: {
    id: string;
    quarantined?: boolean;
    manifest?: { completeness_limitations: string[] };
  }[];
};
type Metrics = {
  net_simulated_pnl: string;
  net_simulated_return: string;
  max_drawdown: string;
  fill_count: number;
  partial_orders: number;
  max_locked: string;
  operating_cost_estimate: string;
  financing_cost_estimate: string;
};
type Run = {
  id: string;
  index: number;
  variant: string;
  result: {
    passed: boolean;
    classification: string;
    metrics: Metrics;
    seed: number;
    result_hash: string;
    data_source: string;
  };
  incident: Incident | null;
};
type Incident = {
  campaign_id: string;
  id: string;
  run_id: string;
  classification: string;
  invariant: string;
  status: string;
  severity: string;
  original_events: number;
  minimized_events: number;
  actual: string[];
  reproduction: string;
};
type PortfolioState = Record<string, unknown> & {
  available?: string;
  reserved?: string;
  locked?: string;
  equity?: string;
  realized_pnl?: string;
};
type Journal = {
  index: number;
  id: string;
  kind: string;
  time_ms: number;
  before: PortfolioState;
  after: PortfolioState;
  payload: unknown;
  command: unknown;
  errors: string[];
  observation: {
    books: Record<
      string,
      {
        asks: { price: string; size: string }[];
        bids: { price: string; size: string }[];
        valid: boolean;
      }
    >;
  };
};
type Artifact = {
  campaign_id: string;
  run_id: string;
  reproduction: string;
  result: {
    scenario: unknown;
    journal: Journal[];
    metrics: Metrics;
    result_hash: string;
    warnings: string[];
    data_source: string;
    final_portfolio: PortfolioState;
  };
  incident: Incident | null;
};
type Comparison = {
  analyzed_runs: number;
  total_runs: number;
  note: string;
  settings: Configuration;
  distributions: {
    variant: string;
    count: number;
    min: number;
    max: number;
    mean: number;
    p05: number;
    median: number;
    p95: number;
    returns: number[];
    drawdowns: string[];
    capital_utilization: string[];
    fill_count: number;
    partial_orders: number;
    orders: number;
  }[];
  paired: {
    left: string;
    right: string;
    pairs: number;
    mean_difference_right_minus_left: number;
    synthetic_episode_bootstrap_95: (number | null)[];
    finding: string;
  }[];
};
const num = (value: unknown, digits = 3) =>
  value == null ? '—' : Number(value).toLocaleString(undefined, { maximumFractionDigits: digits });
const tabs = [
  'Overview',
  'Experiment builder',
  'Campaign monitor',
  'Replay workstation',
  'Adversarial testing',
  'Strategy comparison',
  'Scenario explorer',
] as const;
type Tab = (typeof tabs)[number];
function Json({ value }: { value: unknown }) {
  return <pre className="lab-json">{JSON.stringify(value, null, 2)}</pre>;
}
function Status({ value }: { value: string }) {
  return (
    <span
      className={`badge ${value === 'COMPLETED' || value === 'VALID_RUN' ? 'cyan' : value.includes('FAIL') ? 'red' : 'gold'}`}
    >
      {value}
    </span>
  );
}
function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="panel lab-panel">
      <div className="panel-header">
        <h2>{title}</h2>
      </div>
      {children}
    </section>
  );
}
function Stat({ label, value, detail }: { label: string; value: string | number; detail: string }) {
  return (
    <div className="metric">
      <div className="metric-label">
        {label}
        <Activity size={14} />
      </div>
      <div className="metric-value">{value}</div>
      <div className="metric-detail">{detail}</div>
    </div>
  );
}

export function Laboratory() {
  const cache = useQueryClient();
  const [tab, setTab] = useState<Tab>('Overview');
  const [campaignId, setCampaignId] = useState<string | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const [search, setSearch] = useState('');
  const catalog = useQuery({
    queryKey: ['lab-catalog'],
    queryFn: () => api<Catalog>('/laboratory/catalog'),
  });
  const campaigns = useQuery({
    queryKey: ['lab-campaigns'],
    queryFn: () => api<Campaign[]>('/laboratory/campaigns'),
    refetchInterval: 1500,
  });
  const selected = campaigns.data?.find((c) => c.id === campaignId) ?? campaigns.data?.[0];
  const runs = useQuery({
    queryKey: ['lab-runs', selected?.id, selected?.completed, offset],
    queryFn: () =>
      api<Run[]>(`/laboratory/campaigns/${selected?.id}/runs?offset=${offset}&limit=50`),
    enabled: !!selected,
    refetchInterval: selected?.status === 'RUNNING' ? 1500 : false,
  });
  const activeRun = runId ?? runs.data?.[0]?.id;
  const artifact = useQuery({
    queryKey: ['lab-artifact', activeRun],
    queryFn: () => api<Artifact>(`/laboratory/runs/${activeRun}`),
    enabled: !!activeRun && (tab === 'Replay workstation' || tab === 'Scenario explorer'),
  });
  const incidents = useQuery({
    queryKey: ['lab-incidents'],
    queryFn: () => api<Incident[]>('/laboratory/incidents'),
    refetchInterval: 2000,
  });
  const comparison = useQuery({
    queryKey: ['lab-comparison', selected?.id, selected?.completed],
    queryFn: () => api<Comparison>(`/laboratory/campaigns/${selected?.id}/comparison`),
    enabled: !!selected && tab === 'Strategy comparison',
  });
  const control = useMutation({
    mutationFn: (action: string) =>
      api(`/laboratory/campaigns/${selected?.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ action }),
      }),
    onSuccess: () => cache.invalidateQueries({ queryKey: ['lab-campaigns'] }),
  });
  const totals = (campaigns.data ?? []).reduce(
    (a, c) => ({
      complete: a.complete + c.completed,
      passed: a.passed + c.passed,
      failed: a.failed + c.failed,
    }),
    { complete: 0, passed: 0, failed: 0 },
  );
  const inspect = (id: string, destination: Tab = 'Replay workstation') => {
    const incident = incidents.data?.find((item) => item.run_id === id);
    if (incident) {
      setCampaignId(incident.campaign_id);
      setOffset(0);
    }
    setRunId(id);
    setTab(destination);
  };
  return (
    <div className="laboratory">
      <div className="lab-banner">
        <FlaskConical size={26} />
        <div>
          <span className="eyebrow">THE LABORATORY / DETERMINISTIC RESEARCH</span>
          <p>Challenge the assumptions. Preserve the evidence.</p>
        </div>
        <span className="badge cyan">SIMULATION ONLY</span>
      </div>
      <div className="lab-tabs" role="tablist" aria-label="Laboratory views">
        {tabs.map((t) => (
          <button
            key={t}
            role="tab"
            aria-selected={tab === t}
            className={tab === t ? 'active' : ''}
            onClick={() => setTab(t)}
          >
            {t}
          </button>
        ))}
      </div>
      {(campaigns.error || catalog.error) && (
        <p role="alert">{campaigns.error?.message ?? catalog.error?.message}</p>
      )}
      {selected && (
        <div className="lab-context">
          <label>
            Research campaign{' '}
            <select
              aria-label="Research campaign"
              value={selected.id}
              onChange={(e) => {
                setCampaignId(e.target.value);
                setRunId(null);
                setOffset(0);
              }}
            >
              {campaigns.data?.map((c) => (
                <option value={c.id} key={c.id}>
                  {c.id.slice(0, 8)} · {c.status} · {c.completed}/{c.total}
                </option>
              ))}
            </select>
          </label>
          <span>
            {selected.spec.models.join(' / ')} · seed {selected.spec.seed} ·{' '}
            {selected.spec.dataset_id ?? 'generated scenarios'}
          </span>
          <a className="text-button" href={`/api/laboratory/campaigns/${selected.id}/export`}>
            <Download size={14} /> Export campaign manifest
          </a>
        </div>
      )}
      {tab === 'Overview' && (
        <>
          <div className="metrics-grid">
            <Stat
              label="Scenarios executed"
              value={totals.complete}
              detail="Stored virtual runs across retained campaigns"
            />
            <Stat
              label="Invariant outcomes"
              value={`${totals.passed} / ${totals.failed}`}
              detail="Passed / violated; a loss can pass"
            />
            <Stat
              label="Active campaigns"
              value={campaigns.data?.filter((c) => c.status === 'RUNNING').length ?? 0}
              detail={`${campaigns.data?.filter((c) => c.status === 'COMPLETED').length ?? 0} completed`}
            />
            <Stat
              label="Simulation throughput"
              value={num(selected?.events_per_second)}
              detail="Events / second in selected campaign"
            />
          </div>
          <Section title="Research campaigns">
            <CampaignTable
              campaigns={campaigns.data ?? []}
              select={(id) => {
                setCampaignId(id);
                setRunId(null);
                setOffset(0);
                setTab('Campaign monitor');
              }}
            />
          </Section>
          <div className="lab-two">
            <Section title="Recent discoveries">
              {incidents.data?.length ? (
                incidents.data.slice(0, 5).map((i) => (
                  <button
                    className="lab-discovery"
                    key={i.id + i.run_id}
                    onClick={() => inspect(i.run_id)}
                  >
                    <ShieldAlert size={17} />
                    <span>
                      {i.invariant}
                      <small>
                        {i.classification} · {i.minimized_events} minimized events
                      </small>
                    </span>
                    <Status value={i.status} />
                  </button>
                ))
              ) : (
                <p className="empty">No stored invariant discoveries. This is bounded evidence.</p>
              )}
            </Section>
            <Section title="Research boundaries">
              <p className="lab-note">
                Recorded snapshots establish observed opportunities. Hypothetical fills remain
                uncertain. Synthetic episode counts do not measure real-world reliability. Costs and
                collateral value are explicit estimates.
              </p>
              <button className="primary-button" onClick={() => setTab('Experiment builder')}>
                <Play size={14} /> Configure experiment
              </button>
            </Section>
          </div>
        </>
      )}
      {tab === 'Experiment builder' && catalog.data && (
        <Builder
          catalog={catalog.data}
          launched={(id) => {
            setCampaignId(id);
            setRunId(null);
            setOffset(0);
            setTab('Campaign monitor');
            cache.invalidateQueries({ queryKey: ['lab-campaigns'] });
          }}
        />
      )}
      {tab === 'Campaign monitor' &&
        (selected ? (
          <>
            <Section title="Campaign execution">
              <div className="lab-progress">
                <div style={{ width: `${(selected.completed / selected.total) * 100}%` }} />
              </div>
              <div className="lab-controls">
                <Status value={selected.status} />
                <strong>
                  {selected.completed} / {selected.total} runs committed
                </strong>
                <button
                  disabled={control.isPending || selected.status !== 'RUNNING'}
                  onClick={() => control.mutate('pause')}
                >
                  <Pause size={14} /> Pause campaign
                </button>
                <button
                  disabled={
                    control.isPending ||
                    !['PAUSED', 'INTERRUPTED', 'CANCELLED', 'FAILED'].includes(selected.status)
                  }
                  onClick={() => control.mutate('resume')}
                >
                  <Play size={14} /> Resume campaign
                </button>
                <button
                  disabled={control.isPending || selected.status === 'COMPLETED'}
                  onClick={() => control.mutate('cancel')}
                >
                  <Square size={14} /> Cancel campaign
                </button>
              </div>
              {(selected.error || control.error) && (
                <p role="alert">{selected.error ?? control.error?.message}</p>
              )}
            </Section>
            <div className="metrics-grid">
              <Stat
                label="Throughput"
                value={num(selected.runs_per_second)}
                detail="Runs / second, including persistence"
              />
              <Stat
                label="Wall time"
                value={`${num(selected.elapsed_seconds, 1)}s`}
                detail={`${selected.remaining} runs remaining`}
              />
              <Stat
                label="Peak process RSS"
                value={`${num(selected.process_peak_rss_mb, 1)} MB`}
                detail="Coordinator lifetime peak; worker cap is separate"
              />
              <Stat
                label="Worst simulated P&L"
                value={num(selected.worst_pnl)}
                detail={`${selected.failed} invariant violations`}
              />
            </div>
            <Section title="Stored experiment results">
              <RunTable runs={runs.data ?? []} inspect={inspect} />
              <div className="lab-controls">
                <button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 50))}>
                  Previous runs
                </button>
                <span>
                  Rows {offset + 1}–{offset + (runs.data?.length ?? 0)}
                </span>
                <button
                  disabled={offset + 50 >= selected.completed}
                  onClick={() => setOffset(offset + 50)}
                >
                  Next runs
                </button>
              </div>
            </Section>
          </>
        ) : (
          <p className="empty">Launch a campaign to monitor real experiment output.</p>
        ))}
      {tab === 'Replay workstation' && (
        <>
          {artifact.isPending && activeRun && <p>Loading persisted event history…</p>}
          {artifact.error && <p role="alert">{artifact.error.message}</p>}
          {artifact.data ? (
            <Replay key={artifact.data.run_id} artifact={artifact.data} />
          ) : (
            !activeRun && (
              <p className="empty">
                Select a completed experiment to replay its stored transitions.
              </p>
            )
          )}
        </>
      )}
      {tab === 'Adversarial testing' && (
        <Section title="Invariant discoveries and preserved reproductions">
          <p className="lab-note">
            CONTROLLED_MUTATION deliberately corrupts a fill to calibrate detection. Legitimate
            trading losses pass when invariants hold. Issues retain their original and minimized
            scenarios.
          </p>
          {incidents.data?.map((i) => (
            <div className="lab-incident" key={i.id + i.run_id}>
              <div className="lab-controls">
                <Status value={i.classification} />
                <Status value={i.status} />
                <strong>{i.invariant}</strong>
                <span>
                  {i.original_events} → {i.minimized_events} events
                </span>
                <button onClick={() => inspect(i.run_id)}>Open failure replay</button>
                <a href={`/api/laboratory/runs/${i.run_id}/export`}>Export failure artifact</a>
              </div>
              <Json value={i.actual} />
              <code>{i.reproduction}</code>
            </div>
          ))}
          {!incidents.data?.length && (
            <p className="empty">
              No retained discoveries. Use the ledger_mutation family for a labeled detection
              demonstration.
            </p>
          )}
        </Section>
      )}
      {tab === 'Strategy comparison' && (
        <>
          {comparison.error && <p role="alert">{comparison.error.message}</p>}
          {comparison.data ? (
            <ComparisonView data={comparison.data} />
          ) : (
            <p className="empty">
              Choose a campaign with paired strategy or execution-model variants.
            </p>
          )}
        </>
      )}
      {tab === 'Scenario explorer' && (
        <Section title="Scenario definitions and recorded outcomes">
          <label className="lab-search">
            Search scenarios{' '}
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Model, classification, seed…"
            />
          </label>
          <RunTable
            runs={(runs.data ?? []).filter((r) =>
              `${r.variant} ${r.result.classification} ${r.result.seed} ${r.result.data_source}`
                .toLowerCase()
                .includes(search.toLowerCase()),
            )}
            inspect={(id) => inspect(id, 'Scenario explorer')}
          />
          {artifact.data && (
            <>
              <div className="lab-controls">
                <Status value={artifact.data.result.data_source} />
                <a href={`/api/laboratory/runs/${artifact.data.run_id}/export`}>
                  Export complete scenario and reproducibility artifact
                </a>
                <button onClick={() => inspect(artifact.data!.run_id)}>Open event replay</button>
              </div>
              <Json value={artifact.data.result.scenario} />
            </>
          )}
        </Section>
      )}
      <p className="lab-footnote">
        All financial outcomes are simulated. Economic verification is unavailable while collateral
        routing, empirical execution, and applicable costs remain unresolved.
      </p>
    </div>
  );
}

function CampaignTable({
  campaigns,
  select,
}: {
  campaigns: Campaign[];
  select: (id: string) => void;
}) {
  return campaigns.length ? (
    <table>
      <thead>
        <tr>
          <th>Campaign</th>
          <th>State</th>
          <th>Scenarios</th>
          <th>Pass / violation</th>
          <th>Mean simulated P&L</th>
        </tr>
      </thead>
      <tbody>
        {campaigns.map((c) => (
          <tr key={c.id}>
            <td>
              <button className="text-button" onClick={() => select(c.id)}>
                {c.id.slice(0, 12)}
              </button>
            </td>
            <td>
              <Status value={c.status} />
            </td>
            <td>
              {c.completed}/{c.total}
            </td>
            <td>
              {c.passed} / {c.failed}
            </td>
            <td>{num(c.mean_pnl)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  ) : (
    <p className="empty">No campaigns yet. Configure an experiment to begin.</p>
  );
}
function RunTable({ runs, inspect }: { runs: Run[]; inspect: (id: string) => void }) {
  return (
    <table>
      <thead>
        <tr>
          <th>Episode / seed</th>
          <th>Strategy / execution</th>
          <th>Outcome</th>
          <th>Net simulated P&L</th>
          <th>Fills</th>
          <th>Evidence</th>
        </tr>
      </thead>
      <tbody>
        {runs.map((r) => (
          <tr key={r.id}>
            <td>
              {r.index} / {r.result.seed}
            </td>
            <td>{r.variant}</td>
            <td>
              <Status value={r.result.classification} />
            </td>
            <td>{num(r.result.metrics.net_simulated_pnl)}</td>
            <td>{r.result.metrics.fill_count}</td>
            <td>
              <button className="text-button" onClick={() => inspect(r.id)}>
                Inspect run
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Builder({ catalog, launched }: { catalog: Catalog; launched: (id: string) => void }) {
  const [config, setConfig] = useState<Configuration>({ ...catalog.default_config, runs: 16 });
  const [family, setFamily] = useState('mixed');
  const [compareModels, setCompareModels] = useState(false);
  const [compareStrategies, setCompareStrategies] = useState(false);
  const launch = useMutation({
    mutationFn: () =>
      api<Campaign>('/laboratory/campaigns', {
        method: 'POST',
        body: JSON.stringify({
          ...config,
          families: family === 'mixed' ? ['calm', 'volatile', 'one_sided', 'unresolved'] : [family],
          models: compareModels ? catalog.models : config.models,
          strategies: compareStrategies ? catalog.strategies : config.strategies,
        }),
      }),
    onSuccess: (result) => launched(result.id),
  });
  const field = (name: keyof Configuration, value: unknown) =>
    setConfig((previous) => ({ ...previous, [name]: value }));
  return (
    <Section title="Experiment configuration">
      <form
        className="lab-builder"
        onSubmit={(e) => {
          e.preventDefault();
          launch.mutate();
        }}
      >
        <label>
          Workload preset
          <select
            value={config.preset}
            onChange={(e) =>
              setConfig((c) => ({
                ...c,
                preset: e.target.value,
                runs: catalog.presets[e.target.value],
              }))
            }
          >
            {Object.keys(catalog.presets).map((p) => (
              <option key={p}>{p}</option>
            ))}
          </select>
        </label>
        <label>
          Scenario family
          <select value={family} onChange={(e) => setFamily(e.target.value)}>
            <option value="mixed">Mixed market stress</option>
            {catalog.families.map((f) => (
              <option key={f}>{f}</option>
            ))}
          </select>
        </label>
        <label>
          Dataset
          <select
            value={config.dataset_id ?? ''}
            onChange={(e) =>
              setConfig((c) => ({ ...c, dataset_id: e.target.value || null, fee_rate: null }))
            }
          >
            <option value="">Generated synthetic scenarios</option>
            {catalog.datasets
              .filter((d) => !d.quarantined)
              .map((d) => (
                <option key={d.id}>{d.id}</option>
              ))}
          </select>
        </label>
        <label>
          Strategy
          <select
            value={config.strategies[0]}
            onChange={(e) => field('strategies', [e.target.value])}
          >
            {catalog.strategies.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </label>
        <label>
          Execution model
          <select value={config.models[0]} onChange={(e) => field('models', [e.target.value])}>
            {catalog.models.map((m) => (
              <option key={m}>{m}</option>
            ))}
          </select>
        </label>
        <label>
          Random seed
          <input
            required
            type="number"
            min="0"
            max="4294967295"
            value={config.seed}
            onChange={(e) => field('seed', Number(e.target.value))}
          />
        </label>
        <label>
          Number of scenarios
          <input
            required
            type="number"
            min="1"
            max="1000000"
            value={config.runs}
            onChange={(e) => field('runs', Number(e.target.value))}
          />
        </label>
        <label>
          Observation latency (ms)
          <input
            required
            type="number"
            min="0"
            max="60000"
            value={config.observation_latency_ms}
            onChange={(e) => field('observation_latency_ms', Number(e.target.value))}
          />
        </label>
        <label>
          Submission latency (ms)
          <input
            type="number"
            min="0"
            max="60000"
            placeholder="Execution model default"
            value={config.submission_latency_ms ?? ''}
            onChange={(e) =>
              field('submission_latency_ms', e.target.value === '' ? null : Number(e.target.value))
            }
          />
        </label>
        <label>
          Available liquidity fraction
          <input
            type="number"
            min="0"
            max="1"
            step="0.01"
            placeholder="Execution model default"
            value={config.liquidity_fraction ?? ''}
            onChange={(e) => field('liquidity_fraction', e.target.value || null)}
          />
        </label>
        <label>
          Fee-rate assumption
          <input
            type="number"
            min="0"
            max="1"
            step="0.001"
            disabled={!!config.dataset_id}
            placeholder="Market-specific evidence"
            value={config.fee_rate ?? ''}
            onChange={(e) => field('fee_rate', e.target.value || null)}
          />
        </label>
        <label>
          Starting virtual capital
          <input
            required
            type="number"
            min="0.01"
            step="0.01"
            value={config.capital}
            onChange={(e) => field('capital', e.target.value)}
          />
        </label>
        <label>
          Capital limit per trade
          <input
            required
            type="number"
            min="0"
            value={Number(config.limits.max_capital)}
            onChange={(e) => field('limits', { ...config.limits, max_capital: e.target.value })}
          />
        </label>
        <label>
          Workers
          <input
            required
            type="number"
            min="1"
            max="4"
            value={config.workers}
            onChange={(e) => field('workers', Number(e.target.value))}
          />
        </label>
        {(
          [
            ['max_exposure', 'Total exposure limit'],
            ['max_market_exposure', 'Market exposure limit'],
            ['min_edge', 'Minimum net edge'],
            ['max_drawdown', 'Maximum drawdown'],
            ['max_unmatched_exposure', 'Unmatched exposure limit'],
          ] as const
        ).map(([key, label]) => (
          <label key={key}>
            {label}
            <input
              required
              type="number"
              min="0"
              step="0.001"
              value={Number(config.limits[key] ?? 0)}
              onChange={(e) => field('limits', { ...config.limits, [key]: e.target.value })}
            />
          </label>
        ))}
        <label>
          Worker memory cap (MB)
          <input
            required
            type="number"
            min="256"
            max="2048"
            value={config.memory_mb}
            onChange={(e) => field('memory_mb', Number(e.target.value))}
          />
        </label>
        <label>
          Wall-time budget (seconds)
          <input
            required
            type="number"
            min="1"
            max="86400"
            value={config.max_wall_seconds}
            onChange={(e) => field('max_wall_seconds', Number(e.target.value))}
          />
        </label>
        <label>
          Operating cost per fill
          <input
            type="number"
            min="0"
            step="0.001"
            value={String(config.costs.operating_per_fill)}
            onChange={(e) =>
              field('costs', { ...config.costs, operating_per_fill: e.target.value })
            }
          />
        </label>
        <label>
          Storage budget (MB)
          <input
            required
            type="number"
            min="8"
            max="2048"
            value={config.max_disk_mb}
            onChange={(e) => field('max_disk_mb', Number(e.target.value))}
          />
        </label>
        <label>
          Redemption cost estimate
          <input
            type="number"
            min="0"
            step="0.001"
            value={String(config.costs.redemption_cost ?? '0')}
            onChange={(e) => field('costs', { ...config.costs, redemption_cost: e.target.value })}
          />
        </label>
        <label>
          Collateral value factor
          <input
            type="number"
            min="0"
            max="1"
            step="0.01"
            value={String(config.costs.collateral_value_factor ?? '1')}
            onChange={(e) =>
              field('costs', { ...config.costs, collateral_value_factor: e.target.value })
            }
          />
        </label>
        <label>
          Annual financing rate
          <input
            type="number"
            min="0"
            step="0.01"
            value={String(config.costs.annual_financing_rate)}
            onChange={(e) =>
              field('costs', { ...config.costs, annual_financing_rate: e.target.value })
            }
          />
        </label>
        <label className="lab-check">
          <input
            type="checkbox"
            checked={compareModels}
            onChange={(e) => setCompareModels(e.target.checked)}
          />{' '}
          Compare all execution models
        </label>
        <label className="lab-check">
          <input
            type="checkbox"
            checked={compareStrategies}
            onChange={(e) => setCompareStrategies(e.target.checked)}
          />{' '}
          Include conservative and no-trade baselines
        </label>
        <label className="lab-check">
          <input
            type="checkbox"
            checked={config.adversarial}
            onChange={(e) => field('adversarial', e.target.checked)}
          />{' '}
          Mutate event sequences and combine faults
        </label>
        <div className="lab-submit">
          <p>
            Every episode resets the same portfolio. Recorded fees retain their evidence. Extreme
            workloads require an explicit preset and remain subject to resource budgets.
          </p>
          {launch.error && <p role="alert">{launch.error.message}</p>}
          <button className="primary-button" disabled={launch.isPending} type="submit">
            <Play size={15} /> {launch.isPending ? 'Launching…' : 'Launch experiment'}
          </button>
        </div>
      </form>
    </Section>
  );
}

function Replay({ artifact }: { artifact: Artifact }) {
  const [cursor, setCursor] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [filter, setFilter] = useState('all');
  const [reproduced, setReproduced] = useState<string | null>(null);
  const journal = artifact.result.journal;
  const event = journal[cursor];
  useEffect(() => {
    if (!playing) return;
    const timer = window.setInterval(
      () => setCursor((c) => Math.min(c + 1, journal.length - 1)),
      800 / speed,
    );
    return () => window.clearInterval(timer);
  }, [playing, speed, journal.length]);
  if (!event)
    return (
      <p className="empty">
        This run has no events. Inspect its scenario horizon and data coverage.
      </p>
    );
  return (
    <>
      <Section title="Persisted event replay">
        <p className="lab-note">
          Run {artifact.run_id.slice(0, 12)} · campaign {artifact.campaign_id.slice(0, 12)}
        </p>
        <div className="lab-controls">
          <button
            aria-label="Previous event"
            onClick={() => setCursor(Math.max(0, cursor - 1))}
            disabled={cursor === 0}
          >
            <ArrowLeft size={16} />
          </button>
          <button onClick={() => setPlaying(!playing)}>
            {playing ? <Pause size={16} /> : <Play size={16} />}
            {playing ? 'Pause playback' : 'Play history'}
          </button>
          <button
            aria-label="Next event"
            onClick={() => setCursor(Math.min(journal.length - 1, cursor + 1))}
            disabled={cursor === journal.length - 1}
          >
            <ArrowRight size={16} />
          </button>
          <label>
            Playback speed
            <select
              aria-label="Playback speed"
              value={speed}
              onChange={(e) => setSpeed(Number(e.target.value))}
            >
              {[0.5, 1, 2, 5, 10].map((s) => (
                <option key={s} value={s}>
                  {s}×
                </option>
              ))}
            </select>
          </label>
          <a href={`/api/laboratory/runs/${artifact.run_id}/export`}>
            <Download size={14} /> Export full event history
          </a>
          <button
            onClick={async () => {
              try {
                const result = await api<{ matches: boolean }>(
                  `/laboratory/runs/${artifact.run_id}/reproduce`,
                  { method: 'POST' },
                );
                setReproduced(
                  result.matches ? 'Exact result hash reproduced' : 'Reproduction mismatch',
                );
              } catch (error) {
                setReproduced(String(error));
              }
            }}
          >
            <RotateCcw size={14} /> Reproduce run
          </button>
        </div>
        {reproduced && <p role="status">{reproduced}</p>}
        <input
          className="lab-scrubber"
          aria-label="Replay timeline"
          type="range"
          min="0"
          max={journal.length - 1}
          value={cursor}
          onChange={(e) => {
            setPlaying(false);
            setCursor(Number(e.target.value));
          }}
        />
        <div className="lab-event-heading">
          <Status value={event.kind.toUpperCase()} />
          <strong>
            Event {cursor + 1} / {journal.length}
          </strong>
          <code>{event.id}</code>
          <span>{new Date(event.time_ms).toISOString()}</span>
        </div>
        <Equity journal={journal} cursor={cursor} />
      </Section>
      <div className="lab-two">
        <Section title="Chronological event journal">
          <label>
            Event filter
            <select
              aria-label="Event filter"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            >
              <option value="all">All events</option>
              {[...new Set(journal.map((e) => e.kind))].map((k) => (
                <option key={k}>{k}</option>
              ))}
            </select>
          </label>
          <div className="lab-event-list">
            {journal
              .filter((e) => filter === 'all' || e.kind === filter)
              .map((e) => (
                <button
                  key={e.index}
                  className={e.index === cursor ? 'selected' : ''}
                  onClick={() => {
                    setCursor(e.index);
                    setPlaying(false);
                  }}
                >
                  <span>{e.index + 1}</span>
                  <strong>{e.kind}</strong>
                  <small>{e.id}</small>
                </button>
              ))}
          </div>
        </Section>
        <Section title="Observed order books">
          {Object.entries(event.observation.books).map(([id, book]) => (
            <div key={id} className="lab-book">
              <code>{id}</code>
              <Status value={book.valid ? 'OBSERVED' : 'INVALID'} />
              <table>
                <thead>
                  <tr>
                    <th>Ask price</th>
                    <th>Observed depth</th>
                  </tr>
                </thead>
                <tbody>
                  {book.asks.map((l) => (
                    <tr key={l.price}>
                      <td>{l.price}</td>
                      <td>{l.size}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </Section>
      </div>
      <div className="lab-two">
        <Section title="Before state">
          <Json value={event.before} />
        </Section>
        <Section title="After state">
          <Json value={event.after} />
        </Section>
      </div>
      <Section title="Decision, order action and fault evidence">
        <Json
          value={{ command: event.command, payload: event.payload, violations: event.errors }}
        />
        <p className="lab-note">{artifact.result.warnings.join(' · ')}</p>
        <code>{artifact.reproduction}</code>
      </Section>
    </>
  );
}
function Equity({ journal, cursor }: { journal: Journal[]; cursor: number }) {
  const values = journal.map((e) => Number(e.after.equity ?? 0));
  const min = Math.min(...values),
    max = Math.max(...values),
    span = max - min || 1;
  const point = (value: number, index: number) =>
    `${20 + (index / Math.max(1, values.length - 1)) * 940},${120 - ((value - min) / span) * 90}`;
  return (
    <div className="lab-equity">
      <svg viewBox="0 0 980 150" role="img" aria-label="Recorded virtual equity by event">
        <polyline
          points={values.map(point).join(' ')}
          fill="none"
          stroke="var(--cyan)"
          strokeWidth="2"
        />
        <circle
          cx={20 + (cursor / Math.max(1, values.length - 1)) * 940}
          cy={120 - ((values[cursor] - min) / span) * 90}
          r="5"
          fill="var(--gold)"
        />
        <text x="20" y="145" fill="var(--muted)">
          Virtual equity · {num(min)}–{num(max)} · includes hypothetical inventory marks
        </text>
      </svg>
    </div>
  );
}
function ComparisonView({ data }: { data: Comparison }) {
  return (
    <>
      <Section title="Paired strategy and execution results">
        <p className="lab-note">
          {data.note} Analyzed {data.analyzed_runs} of {data.total_runs} stored runs.
        </p>
        <table>
          <thead>
            <tr>
              <th>Variant</th>
              <th>Episodes</th>
              <th>Mean P&L</th>
              <th>Worst / best</th>
              <th>5% / median / 95%</th>
              <th>Partial orders</th>
            </tr>
          </thead>
          <tbody>
            {data.distributions.map((d) => (
              <tr key={d.variant}>
                <td>{d.variant}</td>
                <td>{d.count}</td>
                <td>{num(d.mean)}</td>
                <td>
                  {num(d.min)} / {num(d.max)}
                </td>
                <td>
                  {num(d.p05)} / {num(d.median)} / {num(d.p95)}
                </td>
                <td>
                  {d.partial_orders} / {d.orders}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>
      <div className="lab-two">
        {data.distributions.map((d) => (
          <Section key={d.variant} title={`${d.variant} · outcome distribution`}>
            <Histogram values={d.returns} />
            <p className="lab-note">
              Worst observed drawdown {num(Math.max(...d.drawdowns.map(Number)) * 100)}% · maximum
              capital utilization {num(Math.max(...d.capital_utilization.map(Number)) * 100)}%
            </p>
          </Section>
        ))}
      </div>
      <Section title="Paired differences and uncertainty">
        <Json value={data.paired} />
        <details>
          <summary>Visible comparison configuration</summary>
          <Json value={data.settings} />
        </details>
      </Section>
    </>
  );
}
function Histogram({ values }: { values: number[] }) {
  const min = Math.min(...values),
    max = Math.max(...values),
    span = max - min || 1;
  const bins = Array.from({ length: 12 }, () => 0);
  values.forEach((v) => bins[Math.min(11, Math.floor(((v - min) / span) * 12))]++);
  const height = Math.max(...bins, 1);
  return (
    <svg
      className="lab-histogram"
      viewBox="0 0 480 180"
      role="img"
      aria-label="Stored simulated return distribution"
    >
      {bins.map((v, i) => (
        <rect
          key={i}
          x={20 + i * 36}
          y={145 - (v / height) * 115}
          width="28"
          height={(v / height) * 115}
          fill="var(--gold)"
        >
          <title>{v} stored outcomes</title>
        </rect>
      ))}
      <text x="20" y="170" fill="var(--muted)">
        {num(min)} → {num(max)} virtual P&amp;L · {values.length} episodes
      </text>
    </svg>
  );
}
