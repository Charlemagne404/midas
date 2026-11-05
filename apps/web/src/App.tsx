import { Component, lazy, Suspense, useEffect, useMemo, useState } from 'react';
import type { ComponentProps, ReactNode } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
} from '@tanstack/react-table';
import type { ColumnDef, SortingState } from '@tanstack/react-table';
import {
  Activity,
  ArrowUpRight,
  BarChart3,
  Beaker,
  CheckCircle2,
  ChevronRight,
  CircleHelp,
  Clock3,
  Database,
  FlaskConical,
  Globe2,
  LayoutDashboard,
  PanelLeftClose,
  Play,
  Radio,
  Search,
  Settings2,
  ShieldCheck,
  ShieldX,
  Sparkles,
  Terminal,
  TriangleAlert,
  X,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { api } from './api';
import { PaperPage, PaperSummary, ExperimentPanel } from './Paper';
import { chartBase } from './chart-theme';
import { DeferredChart } from './DeferredChart';
const LazyLaboratory = lazy(() =>
  import('./Laboratory').then((module) => ({ default: module.Laboratory })),
);
const LazyArena = lazy(() => import('./Arena').then((module) => ({ default: module.Arena })));
const LazyReality = lazy(() => import('./Reality').then((module) => ({ default: module.Reality })));
const LazyVeritas = lazy(() => import('./Veritas').then((module) => ({ default: module.Veritas })));
const LazyFrontier = lazy(() =>
  import('./Frontier').then((module) => ({ default: module.Frontier })),
);
const LazyReadiness = lazy(() =>
  import('./Readiness').then((module) => ({ default: module.Readiness })),
);
const LazyObservatory = lazy(() =>
  import('./Observatory').then((module) => ({ default: module.Observatory })),
);

type WorkspaceErrorBoundaryProps = {
  name: string;
  children: ReactNode;
};

type WorkspaceErrorBoundaryState = { failed: boolean };

export class WorkspaceErrorBoundary extends Component<
  WorkspaceErrorBoundaryProps,
  WorkspaceErrorBoundaryState
> {
  state: WorkspaceErrorBoundaryState = { failed: false };

  static getDerivedStateFromError(): WorkspaceErrorBoundaryState {
    return { failed: true };
  }

  render() {
    if (this.state.failed) {
      return (
        <div className="empty" role="alert">
          <h3>{this.props.name} workspace could not load</h3>
          <p>Refresh Mission Control to try loading this workspace again.</p>
        </div>
      );
    }
    return this.props.children;
  }
}

function LazyWorkspace({
  name,
  loading,
  children,
}: {
  name: string;
  loading: string;
  children: ReactNode;
}) {
  return (
    <WorkspaceErrorBoundary name={name}>
      <Suspense fallback={<div className="empty">{loading}</div>}>{children}</Suspense>
    </WorkspaceErrorBoundary>
  );
}

function Chart(props: ComponentProps<typeof DeferredChart>) {
  return (
    <LazyWorkspace name="Chart" loading="Loading chart…">
      <DeferredChart {...props} />
    </LazyWorkspace>
  );
}
import type {
  Analytics,
  Evaluation,
  Portfolio,
  Run,
  Scenario,
  Settings,
  State,
  Stored,
  SystemEvent,
} from './types';

const pageGroups = [
  {
    label: 'Overview',
    pages: [
      ['Mission Control', LayoutDashboard],
      ['Scanner', Search],
    ],
  },
  {
    label: 'Research',
    pages: [
      ['Research Readiness', ShieldCheck],
      ['Frontier', Globe2],
      ['Observatory', Sparkles],
      ['Reality', Radio],
      ['Veritas', BarChart3],
      ['Laboratory', Beaker],
      ['Arena', Sparkles],
    ],
  },
  {
    label: 'Experiments',
    pages: [
      ['Paper Trading', Database],
      ['Simulation Lab', FlaskConical],
    ],
  },
  {
    label: 'System',
    pages: [
      ['Analytics', Activity],
      ['Incidents', TriangleAlert],
      ['Telemetry', Radio],
      ['Settings', Settings2],
    ],
  },
] as const;
const pageSummaries: Record<string, string> = {
  'Mission Control':
    'A clear view of recent market checks, saved evidence, and virtual experiments.',
  Scanner: 'Search markets and see why each observation passed or failed the checks.',
  'Paper Trading': 'Track a virtual portfolio and review hypothetical paper orders.',
  'Simulation Lab':
    'Try a repeatable virtual scenario and see how its assumptions change the result.',
  Laboratory: 'Compare repeatable experiments and inspect the evidence behind each result.',
  Analytics: 'Review recorded market checks and virtual experiment results.',
  Arena: 'Train and compare research models using saved data and simulated markets.',
  'Research Readiness': 'Review bounded readiness evidence and its operational limitations.',
  Frontier: 'Inspect bounded multi-market research and its source-use limits.',
  Incidents: 'Review warnings and errors recorded by the system.',
  Telemetry: 'Check whether data feeds and background services are running as expected.',
  Settings: 'Review the safety boundaries and virtual risk controls.',
};
export const money = (value: string | number | null | undefined, digits = 2) =>
  value == null
    ? '—'
    : Number(value).toLocaleString(undefined, {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
      });
const percent = (value: string | number) => `${(Number(value) * 100).toFixed(2)}%`;
const date = (ts: number | null | undefined) =>
  ts ? new Date(ts).toLocaleTimeString(undefined, { hour12: false }) : '—';
const readable = (value: string) => value.replaceAll('_', ' ').toLowerCase();
const statusLabel = (value: string) =>
  value === 'VERIFIED_MATHEMATICAL'
    ? 'Passed math checks'
    : value === 'NEGATIVE_EDGE'
      ? 'No positive estimate'
      : readable(value);
const isVerified = (e: Evaluation) => e.status === 'VERIFIED_MATHEMATICAL';

function Badge({ children, tone = 'neutral' }: { children: React.ReactNode; tone?: string }) {
  return <span className={`badge ${tone}`}>{children}</span>;
}
function Empty({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <div className="empty">
      <Database size={26} />
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}
function Panel({
  title,
  aside,
  children,
  className = '',
}: {
  title: string;
  aside?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel-header">
        <h2>{title}</h2>
        {aside}
      </div>
      {children}
    </section>
  );
}
function Metric({
  label,
  value,
  unit,
  detail,
  positive,
  icon: Icon,
  help,
}: {
  label: string;
  value: React.ReactNode;
  unit?: string;
  detail: string;
  positive?: boolean;
  icon: LucideIcon;
  help?: string;
}) {
  return (
    <div className="metric">
      <div className="metric-label">
        <span>{label}</span>
        {help && <HelpTip label={label}>{help}</HelpTip>}
        <Icon size={15} />
      </div>
      <div className={`metric-value ${positive ? 'green' : ''}`}>
        {value}
        <span>{unit}</span>
      </div>
      <div className="metric-detail">{detail}</div>
    </div>
  );
}

function HelpTip({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <details className="help-tip">
      <summary aria-label={`About ${label}`} title={`About ${label}`}>
        <CircleHelp size={14} />
      </summary>
      <div className="help-tip-popover">{children}</div>
    </details>
  );
}

export function App() {
  const [page, setPage] = useState('Mission Control');
  const [selected, setSelected] = useState<Evaluation | null>(null);
  const stateQuery = useQuery({
    queryKey: ['state'],
    queryFn: () => api<State>('/state'),
  });
  const opportunities = useQuery({
    queryKey: ['opportunities'],
    queryFn: () => api<Evaluation[]>('/opportunities'),
  });
  const analytics = useQuery({
    queryKey: ['analytics'],
    queryFn: () => api<Analytics>('/analytics'),
  });
  const state = stateQuery.data;
  const disconnected = stateQuery.isError;
  const activeGroup =
    pageGroups.find((group) => group.pages.some(([name]) => name === page))?.label ?? 'Overview';
  const dataLabel =
    page === 'Observatory'
      ? 'Saved research evidence'
      : page === 'Research Readiness'
        ? 'Readiness evidence'
        : page === 'Frontier'
          ? 'Frontier research evidence'
          : page === 'Reality'
            ? 'Public market observations'
            : page === 'Veritas'
              ? 'Saved economic evidence'
              : state?.mode === 'live'
                ? 'Live public data'
                : state?.mode === 'demo'
                  ? 'Example data'
                  : 'Connecting to data';
  const dataHelp =
    page === 'Observatory'
      ? 'Saved research records updated about every 30 seconds. No market prices or live orders are used here.'
      : page === 'Research Readiness'
        ? 'Evidence classifications and measured gates; this page is not a deployment approval.'
        : page === 'Frontier'
          ? 'Bounded public-source research. Candidate states are evidence, not executable orders.'
          : page === 'Reality'
            ? 'Public market observations collected over time. The page shows when this record was last updated.'
            : page === 'Veritas'
              ? 'A saved evidence snapshot. Its capture time is shown beside the assessment.'
              : state?.mode === 'live'
                ? 'Prices come from public market data. Quote age and data quality appear in System status.'
                : state?.mode === 'demo'
                  ? 'Sample data is included so you can explore the site. It is not live market data, and all balances are virtual.'
                  : 'MIDAS is connecting to its data service. The source label will update when it is available.';
  useEffect(() => {
    document.title = `MIDAS — ${page}`;
  }, [page]);
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          className="wordmark"
          href="#"
          onClick={(event) => {
            event.preventDefault();
            setPage('Mission Control');
          }}
        >
          <span className="brand-mark">M</span>MIDAS<span className="brand-dot">.</span>
        </a>
        <div className="workspace">
          <span className="tiny-label">CURRENT AREA</span>
          <div>
            <Beaker size={15} />
            {activeGroup}
            {page === 'Observatory' && <Badge tone="gold">READ ONLY</Badge>}
            {page === 'Research Readiness' && <Badge tone="gold">EVIDENCE</Badge>}
            {page === 'Frontier' && <Badge tone="gold">R&D</Badge>}
          </div>
        </div>
        <nav aria-label="Main navigation">
          {pageGroups.map(({ label, pages: groupPages }) => (
            <div className="nav-group" key={label}>
              <span className="nav-group-label">{label}</span>
              {groupPages.map(([name, Icon]) => (
                <button
                  key={name}
                  aria-label={name}
                  aria-current={page === name ? 'page' : undefined}
                  className={page === name ? 'nav active' : 'nav'}
                  onClick={() => setPage(name)}
                >
                  <Icon size={17} />
                  <span>{name}</span>
                  {name === 'Scanner' && state && (
                    <span className="nav-count">{state.verified_opportunities}</span>
                  )}
                  {name === 'Arena' && <span className="soon">BETA</span>}
                </button>
              ))}
            </div>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="safety-mark">
            <ShieldCheck size={17} />
            <div>
              Simulation boundary<span>No live order execution</span>
            </div>
          </div>
          <div className="version">
            <span>ENGINE v0.2.0</span>
            <PanelLeftClose size={14} />
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            MIDAS
            <ChevronRight size={13} />
            <span>{page}</span>
          </div>
          <div className="topbar-right">
            <Badge
              tone={
                page === 'Reality' ||
                (state?.mode === 'live' &&
                  !['Veritas', 'Observatory', 'Research Readiness', 'Frontier'].includes(page))
                  ? 'cyan'
                  : 'gold'
              }
            >
              {dataLabel}
            </Badge>
            <HelpTip label={dataLabel}>{dataHelp}</HelpTip>
            <span className="topbar-boundary">
              <ShieldCheck size={13} />
              No live orders
            </span>
          </div>
        </header>
        <main>
          {page !== 'Reality' &&
            page !== 'Veritas' &&
            page !== 'Research Readiness' &&
            page !== 'Observatory' &&
            page !== 'Frontier' && (
              <div className="page-heading">
                <div>
                  <div className="eyebrow">WORKSPACE / {activeGroup}</div>
                  <h1>{page}</h1>
                  <p>{pageSummaries[page]}</p>
                </div>
                <div className="heading-status">
                  <span
                    className={`status-dot ${disconnected || state?.status === 'DEGRADED' ? 'red' : ''}`}
                  />
                  {disconnected
                    ? 'Data service offline'
                    : state?.status
                      ? readable(state.status)
                      : 'Connecting'}
                  <span className="heading-time">
                    Updated {date(state?.timestamp_ms)} local time
                  </span>
                </div>
              </div>
            )}
          {page !== 'Reality' &&
            page !== 'Veritas' &&
            page !== 'Research Readiness' &&
            page !== 'Observatory' &&
            page !== 'Frontier' &&
            disconnected && (
              <div className="alert danger">
                <TriangleAlert size={17} />
                <div>
                  MIDAS cannot reach its data service. Some values may be out of date.
                  <details className="error-details">
                    <summary>Connection details</summary>
                    <span>{stateQuery.error.message}</span>
                  </details>
                </div>
                <button onClick={() => void stateQuery.refetch()}>Retry connection</button>
              </div>
            )}
          {page === 'Research Readiness' && state?.mode === 'demo' && (
            <div className="demo-strip">
              <FlaskConical size={14} />
              <strong>DEMO MODE</strong>
              <span>
                Mission Control is in demo mode; Reality and Veritas panels show separately
                classified public observation evidence.
              </span>
              <span className="strip-end">No live orders</span>
            </div>
          )}
          {page !== 'Reality' &&
            page !== 'Veritas' &&
            page !== 'Research Readiness' &&
            page !== 'Observatory' &&
            page !== 'Frontier' &&
            state?.mode === 'demo' && (
              <div className="demo-strip">
                <FlaskConical size={14} />
                <strong>EXAMPLE DATA</strong>
                <span>
                  Sample market records for exploring the interface. All balances and results are
                  virtual.
                </span>
                <span className="strip-end">No real funds or orders</span>
              </div>
            )}
          {page !== 'Reality' &&
            page !== 'Veritas' &&
            page !== 'Research Readiness' &&
            page !== 'Observatory' &&
            page !== 'Frontier' &&
            state?.status === 'DEGRADED' &&
            !disconnected && (
              <div className="alert danger">
                <TriangleAlert size={17} />
                Some market quotes may be incomplete or out of date. Check System → Telemetry before
                relying on these summaries.
              </div>
            )}
          {page !== 'Reality' &&
            page !== 'Veritas' &&
            page !== 'Research Readiness' &&
            page !== 'Observatory' &&
            page !== 'Frontier' &&
            state?.safety.emergency_stop && (
              <div className="alert danger" role="alert">
                <ShieldX size={17} />
                The safety stop is on, so new virtual proposals and scenarios are paused.
                <button onClick={() => setPage('Settings')}>Review safety controls</button>
              </div>
            )}
          {page === 'Mission Control' && (
            <Mission
              state={state}
              evaluations={opportunities.data ?? []}
              analytics={analytics.data}
              onInspect={setSelected}
              navigate={setPage}
            />
          )}
          {page === 'Research Readiness' && (
            <LazyWorkspace name="Readiness" loading="Loading readiness evidence…">
              <LazyReadiness />
            </LazyWorkspace>
          )}
          {page === 'Observatory' && (
            <LazyWorkspace name="Observatory" loading="Loading saved research artifacts…">
              <LazyObservatory />
            </LazyWorkspace>
          )}
          {page === 'Scanner' && (
            <Scanner
              evaluations={opportunities.data ?? []}
              onInspect={setSelected}
              error={opportunities.error?.message}
            />
          )}
          {page === 'Paper Trading' && <PaperPage />}
          {page === 'Simulation Lab' && (
            <>
              <SimulationLab />
              <ExperimentPanel />
            </>
          )}
          {page === 'Laboratory' && (
            <LazyWorkspace name="Laboratory" loading="Loading Laboratory research…">
              <LazyLaboratory onNavigate={setPage} />
            </LazyWorkspace>
          )}
          {page === 'Analytics' && <AnalyticsPage data={analytics.data} />}
          {page === 'Arena' && (
            <LazyWorkspace name="Arena" loading="Loading Arena research…">
              <LazyArena />
            </LazyWorkspace>
          )}
          {page === 'Reality' && (
            <LazyWorkspace name="Reality" loading="Loading Reality observations…">
              <LazyReality />
            </LazyWorkspace>
          )}
          {page === 'Veritas' && (
            <LazyWorkspace name="Veritas" loading="Loading Veritas evidence…">
              <LazyVeritas />
            </LazyWorkspace>
          )}
          {page === 'Frontier' && (
            <LazyWorkspace name="Frontier" loading="Loading Frontier research workspace…">
              <LazyFrontier onNavigate={setPage} />
            </LazyWorkspace>
          )}
          {page === 'Incidents' && <Incidents />}
          {page === 'Telemetry' && <Telemetry state={state} />}
          {page === 'Settings' && <SettingsPage />}
          {page !== 'Observatory' && (
            <footer className="page-footer">
              <span>MIDAS / Independent prediction-market research</span>
              <span>
                Observed edge ≠ executable profit<span className="footer-divider">/</span>All
                balances are virtual
              </span>
            </footer>
          )}
        </main>
      </div>
      {selected && <Details evaluation={selected} close={() => setSelected(null)} />}
    </div>
  );
}

function ActivityChart({ data }: { data: Analytics | undefined }) {
  const option = useMemo(
    () => ({
      ...chartBase,
      color: ['#d3a955', '#55b7c8'],
      legend: { right: 20, textStyle: { color: '#8590a3' }, itemHeight: 7, itemWidth: 16 },
      xAxis: { ...chartBase.xAxis, data: data?.activity.map((x) => date(x.timestamp_ms)) ?? [] },
      series: [
        {
          name: 'Market checks',
          type: 'line',
          data: data?.activity.map((x) => x.observations),
          symbolSize: 5,
          lineStyle: { width: 2 },
          areaStyle: { opacity: 0.04 },
        },
        {
          name: 'Passed checks',
          type: 'line',
          data: data?.activity.map((x) => x.verified),
          symbolSize: 5,
          lineStyle: { width: 2 },
        },
      ],
    }),
    [data],
  );
  return data?.activity.length ? (
    <Chart option={option} label="Market checks and checks that passed each minute" />
  ) : (
    <Empty title="Waiting for observations">
      The chart appears when the backend records a refresh.
    </Empty>
  );
}
function Mission({
  state,
  evaluations,
  analytics,
  onInspect,
  navigate,
}: {
  state: State | undefined;
  evaluations: Evaluation[];
  analytics: Analytics | undefined;
  onInspect: (e: Evaluation) => void;
  navigate: (p: string) => void;
}) {
  return (
    <>
      <section className="mission-start">
        <div className="mission-start-copy">
          <span className="eyebrow">A QUICK WAY TO GET STARTED</span>
          <h2>Follow a market observation through the research process.</h2>
          <p>
            Explore what MIDAS checked, review the public evidence, then try a virtual scenario.
            Every result is for research; no live orders are placed.
          </p>
        </div>
        <div className="mission-start-actions">
          <button className="mission-start-action" onClick={() => navigate('Scanner')}>
            <span>01</span>
            <span>
              <strong>Explore markets</strong>
              <small>Review recent checks</small>
            </span>
            <ChevronRight size={16} />
          </button>
          <button className="mission-start-action" onClick={() => navigate('Reality')}>
            <span>02</span>
            <span>
              <strong>Read the evidence</strong>
              <small>See public observations</small>
            </span>
            <ChevronRight size={16} />
          </button>
          <button className="mission-start-action" onClick={() => navigate('Simulation Lab')}>
            <span>03</span>
            <span>
              <strong>Try a simulation</strong>
              <small>Test virtual outcomes</small>
            </span>
            <ChevronRight size={16} />
          </button>
        </div>
      </section>
      <PaperSummary compact />
      <div className="metrics">
        <Metric
          label="Markets checked"
          value={state?.markets ?? '—'}
          detail="Distinct markets included in the latest scan."
          help="A market is one question with possible outcomes. MIDAS checks its available public prices."
          icon={Radio}
        />
        <Metric
          label="Checks passed"
          value={state?.verified_opportunities ?? '—'}
          detail={`${state?.rejected_opportunities ?? 0} checks did not pass`}
          help="Passing means the observation met MIDAS’s built-in mathematical checks. It does not predict what will happen next."
          icon={ShieldCheck}
          positive
        />
        <Metric
          label="Modeled edge · estimate"
          value={money(state?.potential_net_profit)}
          unit={state?.unit ?? 'USD'}
          detail="Separate snapshots added together; they may not be achievable together."
          help="An estimate from observed prices and modeled costs. It does not guarantee a fill or profit. The gross estimate is shown in Scanner."
          icon={ArrowUpRight}
        />
        <Metric
          label="Starting virtual balance"
          value={money(state?.virtual_starting_capital)}
          unit="USD"
          detail="Each experiment starts with its own simulated balance."
          help="This is simulated money for research. No funds are deposited or moved."
          icon={Database}
        />
      </div>
      <div className="overview-grid">
        <Panel
          title="Recent market activity"
          aside={<Badge>{analytics?.observation_window ?? 0} recorded checks</Badge>}
        >
          <ActivityChart data={analytics} />
          <div className="chart-footnote">
            Counts are grouped by minute. The same market can appear in more than one check.
          </div>
        </Panel>
        <Panel title="System status" aside={<Badge tone="green">Research only</Badge>}>
          <div className="health-list">
            <div>
              <span>Public market connection</span>
              <strong>{state?.connection ? readable(state.connection) : 'Checking'}</strong>
            </div>
            <div>
              <span>Oldest available quote</span>
              <strong>
                {state?.oldest_book_age_ms == null
                  ? 'No quotes received'
                  : `About ${(state.oldest_book_age_ms / 1000).toFixed(1)} seconds old`}
              </strong>
            </div>
            <div>
              <span>Quote checks with issues</span>
              <strong>
                {state?.invalid_books ?? 0} of {state?.books ?? 0}
              </strong>
            </div>
            <div>
              <span>Real orders placed</span>
              <strong>None · virtual research only</strong>
            </div>
          </div>
          <details className="mission-details">
            <summary>Technical system details</summary>
            <div className="health-list">
              <div>
                <span>Pending paper proposals / processing delay</span>
                <strong>
                  {state?.telemetry.broker_pending_actions ?? '—'} /{' '}
                  {state?.telemetry.broker_processing_delay_ms ?? '—'} ms
                </strong>
              </div>
              <div>
                <span>Recovered broker restarts</span>
                <strong>{state?.telemetry.broker_recoveries ?? '—'}</strong>
              </div>
              <div>
                <span>Process CPU time / peak memory</span>
                <strong>
                  {state?.telemetry.cpu_seconds ?? '—'} s /{' '}
                  {state?.telemetry.peak_memory_kib ?? '—'} KiB
                </strong>
              </div>
              <div>
                <span>Latest scan speed, including saved records</span>
                <strong>
                  {state?.telemetry.scanner_markets_per_second?.toFixed(2) ?? '—'} markets/s
                </strong>
              </div>
              <div>
                <span>Research record storage</span>
                <strong>
                  {state == null
                    ? 'Checking'
                    : state.telemetry.database_healthy
                      ? 'Available'
                      : 'Unavailable'}
                </strong>
              </div>
            </div>
          </details>
          <div className="lab-result">
            <div className="tiny-label">LATEST VIRTUAL SCENARIO</div>
            <strong
              className={Number(state?.latest_simulated_pnl ?? 0) < 0 ? 'red-text' : 'cyan-text'}
            >
              {money(state?.latest_simulated_pnl)}
              <small> simulated USD result</small>
            </strong>
            <span>
              {state?.latest_simulation
                ? readable(state.latest_simulation)
                : 'Run a scenario to create a virtual result'}
            </span>
            <button className="text-button" onClick={() => navigate('Simulation Lab')}>
              Try a simulation <ChevronRight size={14} />
            </button>
          </div>
        </Panel>
      </div>
      <Panel
        title="Recent market checks"
        aside={
          <button className="text-button" onClick={() => navigate('Scanner')}>
            Open scanner <ChevronRight size={14} />
          </button>
        }
      >
        <div className="panel-note">
          These are observations based on public prices. A positive estimate does not guarantee a
          trade or a profit.
        </div>
        <CompactTable evaluations={evaluations.slice(0, 5)} onInspect={onInspect} />
      </Panel>
      <details className="mission-event-details">
        <summary>Recent system activity</summary>
        <Panel title="Latest recorded events" aside={<Badge>System log</Badge>}>
          <EventList events={state?.events.slice(0, 6) ?? []} />
        </Panel>
      </details>
    </>
  );
}
function CompactTable({
  evaluations,
  onInspect,
}: {
  evaluations: Evaluation[];
  onInspect: (e: Evaluation) => void;
}) {
  return evaluations.length ? (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Market</th>
            <th>Gross estimate</th>
            <th>After modeled costs</th>
            <th>Est. amount</th>
            <th>Check result</th>
            <th>Last checked</th>
          </tr>
        </thead>
        <tbody>
          {evaluations.map((e) => (
            <tr key={e.market_id}>
              <td>
                <button className="market-button" onClick={() => onInspect(e)}>
                  <span className="market-symbol">{e.source === 'SYNTHETIC' ? 'S' : 'P'}</span>
                  {e.question}
                  <ChevronRight size={13} />
                </button>
              </td>
              <td className="mono">{percent(e.gross_edge)}</td>
              <td className={`mono ${Number(e.net_edge) > 0 ? 'green' : 'muted'}`}>
                {percent(e.net_edge)}
              </td>
              <td className="mono">{money(e.quantity)} shares</td>
              <td>
                <Badge
                  tone={isVerified(e) ? 'green' : e.status === 'NEGATIVE_EDGE' ? 'red' : 'neutral'}
                >
                  {statusLabel(e.status)}
                </Badge>
              </td>
              <td className="mono muted">{date(e.observed_ts_ms)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  ) : (
    <Empty title="No market observations">
      No observations are available. Check the data connection or adjust your filters.
    </Empty>
  );
}

function Scanner({
  evaluations,
  onInspect,
  error,
}: {
  evaluations: Evaluation[];
  onInspect: (e: Evaluation) => void;
  error?: string;
}) {
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('all');
  const [protocol, setProtocol] = useState('all');
  const [reason, setReason] = useState('');
  const [sorting, setSorting] = useState<SortingState>([{ id: 'net_edge', desc: true }]);
  const data = useMemo(
    () =>
      evaluations.filter(
        (e) =>
          e.question.toLowerCase().includes(search.toLowerCase()) &&
          (status === 'all' || e.status === status) &&
          (protocol === 'all' || e.market?.protocol === protocol) &&
          e.reasons.join(' ').toLowerCase().includes(reason.toLowerCase()),
      ),
    [evaluations, search, status, protocol, reason],
  );
  const columns = useMemo<ColumnDef<Evaluation>[]>(
    () => [
      {
        accessorKey: 'question',
        header: 'Market',
        cell: (info) => (
          <button className="market-button" onClick={() => onInspect(info.row.original)}>
            {info.getValue<string>()}
            <ChevronRight size={13} />
          </button>
        ),
      },
      {
        id: 'type',
        header: 'Outcomes',
        cell: (i) => (
          <span className="muted">
            {i.row.original.market?.instruments.map((x) => x.label).join(' + ')}
          </span>
        ),
        enableSorting: false,
      },
      {
        accessorKey: 'gross_edge',
        header: 'Gross estimate',
        sortingFn: (a, b) => Number(a.original.gross_edge) - Number(b.original.gross_edge),
        cell: (i) => <span className="mono">{percent(i.getValue<string>())}</span>,
      },
      {
        accessorKey: 'net_edge',
        header: 'After modeled costs',
        sortingFn: (a, b) => Number(a.original.net_edge) - Number(b.original.net_edge),
        cell: (i) => (
          <span className={`mono ${Number(i.getValue()) > 0 ? 'green' : ''}`}>
            {percent(i.getValue<string>())}
          </span>
        ),
      },
      {
        accessorKey: 'quantity',
        header: 'Est. amount',
        sortingFn: (a, b) => Number(a.original.quantity) - Number(b.original.quantity),
        cell: (i) => <span className="mono">{money(i.getValue<string>())}</span>,
      },
      {
        accessorKey: 'available_quantity',
        header: 'Displayed amount',
        cell: (i) => <span className="mono">{money(i.getValue<string>())}</span>,
      },
      {
        accessorKey: 'required_capital',
        header: 'Virtual funds needed',
        sortingFn: (a, b) =>
          Number(a.original.required_capital) - Number(b.original.required_capital),
        cell: (i) => <span className="mono">{money(i.getValue<string>())}</span>,
      },
      {
        accessorKey: 'status',
        header: 'Check result',
        cell: (i) => (
          <Badge tone={isVerified(i.row.original) ? 'green' : 'neutral'}>
            {statusLabel(i.getValue<string>())}
          </Badge>
        ),
      },
      {
        id: 'reason',
        header: 'Why it passed or failed',
        cell: (i) => (
          <span className="reason" title={i.row.original.reasons.join('; ')}>
            {i.row.original.reasons[0]}
          </span>
        ),
        enableSorting: false,
      },
      {
        accessorKey: 'observed_ts_ms',
        header: 'Last checked',
        cell: (i) => <span className="mono muted">{date(i.getValue<number>())}</span>,
      },
    ],
    [onInspect],
  );
  const table = useReactTable({
    data,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });
  return (
    <Panel title="Market checks" aside={<Badge>{data.length} results</Badge>}>
      <div className="scanner-explainer">
        <strong>What you’re seeing</strong>
        <span>
          Each row is a check of public market prices. “Net edge” is an estimate after modeled
          costs; it does not guarantee that an order could fill or make money.
        </span>
      </div>
      <div className="toolbar scanner-toolbar">
        <label className="search-field">
          <Search size={15} />
          <input
            aria-label="Search markets"
            placeholder="Search markets…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
        <select
          aria-label="Filter opportunity status"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
        >
          <option value="all">All results</option>
          {[...new Set(evaluations.map((e) => e.status))].map((s) => (
            <option key={s} value={s}>
              {statusLabel(s)}
            </option>
          ))}
        </select>
        <details className="filter-more">
          <summary>More filters</summary>
          <select
            aria-label="Filter protocol"
            value={protocol}
            onChange={(e) => setProtocol(e.target.value)}
          >
            <option value="all">All protocols</option>
            <option value="v1">CTF v1</option>
            <option value="v2">Protocol V2</option>
          </select>
          <input
            aria-label="Filter rejection reason"
            placeholder="Rejection reason…"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
        </details>
        <span className="toolbar-note">{data.length} matching markets</span>
      </div>
      {error && (
        <div role="alert" className="alert danger">
          {error}
        </div>
      )}
      {data.length ? (
        <div className="table-scroll">
          <table>
            <thead>
              {table.getHeaderGroups().map((group) => (
                <tr key={group.id}>
                  {group.headers.map((h) => (
                    <th key={h.id}>
                      {h.column.getCanSort() ? (
                        <button onClick={h.column.getToggleSortingHandler()}>
                          {flexRender(h.column.columnDef.header, h.getContext())}
                          {h.column.getIsSorted() === 'desc'
                            ? ' ↓'
                            : h.column.getIsSorted() === 'asc'
                              ? ' ↑'
                              : ' ↕'}
                        </button>
                      ) : (
                        flexRender(h.column.columnDef.header, h.getContext())
                      )}
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody>
              {table.getRowModel().rows.map((row) => (
                <tr key={row.id}>
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id}>
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <Empty title="No matching observations">
          An empty list is a valid result. Adjust the filters or inspect data connection health.
        </Empty>
      )}
      <div className="panel-note">
        “Modeled size” estimates the quantity available at the observed price. Some checks have no
        size estimate. Open a row to see its assumptions and reasons.
      </div>
    </Panel>
  );
}

function Details({ evaluation: e, close }: { evaluation: Evaluation; close: () => void }) {
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const listener = (event: KeyboardEvent) => {
      if (event.key === 'Escape') close();
      if (event.key === 'Tab') {
        const nodes = Array.from(
          document.querySelectorAll<HTMLElement>(
            '.drawer button,.drawer [href],.drawer input,.drawer [tabindex="0"]',
          ),
        );
        const first = nodes[0],
          last = nodes[nodes.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }
    };
    document.addEventListener('keydown', listener);
    document.getElementById('close-details')?.focus();
    return () => {
      document.removeEventListener('keydown', listener);
      previous?.focus();
    };
  }, [close]);
  return (
    <div className="drawer-overlay" onClick={close}>
      <section
        className="drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="details-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="drawer-header">
          <span className="eyebrow">OBSERVATION AUDIT</span>
          <button id="close-details" aria-label="Close observation detail" onClick={close}>
            <X size={20} />
          </button>
        </div>
        <h2 id="details-title">{e.question}</h2>
        <div className="drawer-badges">
          <Badge tone={e.source === 'SYNTHETIC' ? 'gold' : 'cyan'}>{e.source}</Badge>
          <Badge tone={isVerified(e) ? 'green' : 'neutral'}>{readable(e.status)}</Badge>
        </div>
        <p>{e.reasons.join('; ')}</p>
        <div className="detail-grid">
          <div>
            <span>Complete sets</span>
            <strong>{money(e.quantity)}</strong>
          </div>
          <div>
            <span>Ask notional</span>
            <strong>{money(e.gross_cost, 6)}</strong>
          </div>
          <div>
            <span>Modeled fees + reserve</span>
            <strong>{money(e.fees, 6)}</strong>
          </div>
          <div>
            <span>Required collateral</span>
            <strong>{money(e.required_capital, 6)}</strong>
          </div>
          <div>
            <span>Minimum payout</span>
            <strong>{money(e.minimum_payout, 6)}</strong>
          </div>
          <div>
            <span>Minimum net profit</span>
            <strong className={Number(e.net_profit) > 0 ? 'green' : ''}>
              {money(e.net_profit, 6)}
            </strong>
          </div>
        </div>
        <div className="panel-note">
          Units: {e.source === 'SYNTHETIC' ? 'virtual USD' : 'modeled pUSD'}. These are modeled
          fully acquired positions.
        </div>
        <h3>Independent risk decision</h3>
        <Badge tone={e.risk.allowed ? 'green' : 'red'}>
          {e.risk.allowed ? 'ALLOW VIRTUAL PROPOSAL' : 'REJECT VIRTUAL PROPOSAL'}
        </Badge>
        <ul className="audit-list">
          {e.risk.reasons.map((x) => (
            <li key={x}>{x}</li>
          ))}
        </ul>
        <h3>Instrument & book evidence</h3>
        <div className="definition-row">
          <span>Protocol</span>
          <code>{e.market?.protocol ?? 'unknown'}</code>
        </div>
        <code className="identifier">{e.market?.condition_id}</code>
        {e.books.map((book) => (
          <div className="book-audit" key={book.asset_id}>
            <h4>
              {e.market?.instruments.find((i) => i.asset_id === book.asset_id)?.label ?? 'Outcome'}{' '}
              ask depth
            </h4>
            <code className="identifier">{book.asset_id}</code>
            <div className="book-meta">
              <span>
                Tick {book.tick_size} · minimum {book.min_order_size}
              </span>
              <Badge tone={book.valid ? 'green' : 'red'}>{book.integrity}</Badge>
            </div>
            <div className="book-meta">
              Exchange {date(book.exchange_ts_ms)} · receipt {date(book.received_ts_ms)}
            </div>
            {book.invalid_reason && <p className="red-text">{book.invalid_reason}</p>}
            <table>
              <thead>
                <tr>
                  <th>Ask / {e.source === 'LIVE' ? 'pUSD' : 'virtual USD'}</th>
                  <th>Shares</th>
                  <th>Selected shares</th>
                </tr>
              </thead>
              <tbody>
                {[...book.asks]
                  .sort((a, b) => Number(a.price) - Number(b.price))
                  .slice(0, 20)
                  .map((level) => (
                    <tr key={level.price}>
                      <td className="mono">{level.price}</td>
                      <td className="mono">{level.size}</td>
                      <td className="mono cyan-text">
                        {e.slices
                          .filter((s) => s.asset_id === book.asset_id && s.price === level.price)
                          .map((s) => s.quantity)
                          .join(', ') || '—'}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        ))}
        <h3>Modeled outcome payouts</h3>
        {Object.entries(e.payouts).map(([outcome, payout]) => (
          <div className="definition-row" key={outcome}>
            <span>{outcome}</span>
            <strong className="mono">{money(payout, 6)}</strong>
          </div>
        ))}
        <h3>Structural economic attestation</h3>
        <p>
          VERIFIED STRUCTURE establishes complementary instrument algebra under the recorded
          protocol and collateral assumptions. It does not prove natural-language rules or
          hypothetical fills.
        </p>
        <pre className="artifact-json">
          {JSON.stringify(
            e.market?.attestation ?? {
              status: 'SYNTHETIC CONTRACT',
              evidence: e.market?.payout_evidence,
            },
            null,
            2,
          )}
        </pre>
        <h3>Full economic calculation trace</h3>
        <pre className="artifact-json">{JSON.stringify(e.economic_proof, null, 2)}</pre>
        <h3>Fee evidence</h3>
        <p>{e.market?.fee.evidence}</p>
        <h3>Established assumptions</h3>
        <ul className="audit-list">
          {e.assumptions.length ? (
            e.assumptions.map((x) => <li key={x}>{x}</li>)
          ) : (
            <li>{e.market?.payout_evidence}</li>
          )}
        </ul>
        <div className="alert">
          <ShieldCheck size={16} />
          Mathematical verification describes a modeled complete position. Independent orders can
          leave unmatched exposure.
        </div>
      </section>
    </div>
  );
}

function PortfolioGrid({ portfolio: p }: { portfolio: Portfolio }) {
  return (
    <div className="portfolio-grid">
      {[
        ['Available', p.available],
        ['Reserved', p.reserved],
        ['Locked', p.locked],
        ['Realized P&L', p.realized_pnl],
        ['Fees paid', p.fees],
        ['Settlement proceeds', p.settlement_proceeds],
      ].map(([label, value]) => (
        <div key={label}>
          <span>{label}</span>
          <strong
            className={label === 'Realized P&L' ? (Number(value) < 0 ? 'red-text' : 'green') : ''}
          >
            {money(value, 4)}
          </strong>
          <small>virtual USD</small>
        </div>
      ))}
      <div>
        <span>Matched inventory</span>
        <strong>{money(p.matched_quantity)}</strong>
        <small>complete sets</small>
      </div>
      <div>
        <span>Unmatched inventory</span>
        <strong className={Number(p.unmatched_quantity) > 0 ? 'red-text' : ''}>
          {money(p.unmatched_quantity)}
        </strong>
        <small>shares</small>
      </div>
    </div>
  );
}
function SimulationLab() {
  const scenarios = useQuery({
    queryKey: ['scenarios'],
    queryFn: () => api<Scenario[]>('/scenarios'),
  });
  const history = useQuery({
    queryKey: ['simulations'],
    queryFn: () => api<Stored<Run>[]>('/simulations'),
  });
  const [scenario, setScenario] = useState('profitable');
  const [seed, setSeed] = useState(7);
  const [run, setRun] = useState<Run | null>(null);
  const [cursor, setCursor] = useState(0);
  const queryClient = useQueryClient();
  const execute = useMutation({
    mutationFn: () =>
      api<Run>(`/scenarios/${scenario}/run`, { method: 'POST', body: JSON.stringify({ seed }) }),
    onSuccess: (result) => {
      setRun(result);
      setCursor(result.timeline.length - 1);
      void queryClient.invalidateQueries();
    },
  });
  const selected = scenarios.data?.find((s) => s.id === scenario);
  const selectedEvent = run?.timeline[cursor];
  const groups = [...new Set(scenarios.data?.map((s) => s.category))];
  return (
    <>
      <details className="workspace-guide simulation-guide">
        <summary>How to run a virtual scenario</summary>
        <div>
          <p>
            Choose a scenario, keep or change the repeat number, then run it. The same scenario and
            repeat number reproduce the same virtual run.
          </p>
          <p>
            Results use sample market data and estimated fills. They are not live trading results.
          </p>
        </div>
      </details>
      <div className="simulation-grid">
        <Panel
          title="Scenario library"
          aside={<Badge>{scenarios.data?.length ?? 0} scenarios</Badge>}
          className="scenario-panel"
        >
          {groups.map((group) => (
            <div key={group} className="scenario-group">
              <div className="tiny-label">{group}</div>
              {scenarios.data
                ?.filter((s) => s.category === group)
                .map((s) => (
                  <button
                    className={`scenario-option ${scenario === s.id ? 'selected' : ''}`}
                    key={s.id}
                    onClick={() => setScenario(s.id)}
                  >
                    <span>{readable(s.id)}</span>
                    <ChevronRight size={13} />
                  </button>
                ))}
            </div>
          ))}
        </Panel>
        <div className="simulation-workbench">
          <Panel
            title="Set up a virtual scenario"
            aside={<Badge tone="cyan">REPEATABLE · SIMULATED</Badge>}
          >
            <div className="experiment-intro">
              <div className="experiment-icon">
                <FlaskConical size={25} />
              </div>
              <div>
                <h3>{readable(scenario)}</h3>
                <p>{selected?.description ?? 'Loading scenario definition…'}</p>
              </div>
            </div>
            <div className="run-controls">
              <label>
                Repeat number
                <input
                  type="number"
                  min={0}
                  max={4294967295}
                  value={seed}
                  onChange={(e) => setSeed(Number(e.target.value))}
                />
              </label>
              <span className="run-seed-note">Use the same number to repeat a run.</span>
              <button
                className="primary-button"
                disabled={
                  execute.isPending || !Number.isInteger(seed) || seed < 0 || seed > 4294967295
                }
                onClick={() => execute.mutate()}
              >
                <Play size={15} />
                {execute.isPending ? 'Running…' : 'Run scenario'}
              </button>
            </div>
            {execute.error && (
              <div className="alert danger" role="alert">
                {execute.error.message}
              </div>
            )}
            <details className="simulation-assumptions">
              <summary>How fills and costs are estimated</summary>
              <div>
                <p>
                  The scenario uses a saved sample dataset, modeled fees, delays, and price-based
                  matching. Actual market conditions and order fills may be different.
                </p>
                <code>dataset synthetic-1 · strategy binary-depth-1</code>
              </div>
            </details>
          </Panel>
          {run ? (
            <>
              <div className={`run-result ${run.passed ? 'pass' : 'fail'}`}>
                <CheckCircle2 size={21} />
                <div>
                  <strong>
                    {run.passed ? 'SCENARIO CHECKS PASSED' : 'SCENARIO CHECKS FOUND A PROBLEM'}
                  </strong>
                  <span>
                    {readable(run.scenario_id)} · repeat {run.seed} · {run.timeline.length} steps
                    recorded
                  </span>
                </div>
                <Badge tone="gold">SAMPLE SCENARIO</Badge>
              </div>
              <Panel
                title="Virtual balance at this step"
                aside={<Badge tone="cyan">Elapsed {selectedEvent?.time_ms ?? 0} ms</Badge>}
              >
                {selectedEvent && <PortfolioGrid portfolio={selectedEvent.portfolio} />}
              </Panel>
              <Panel
                title="Step-by-step replay"
                aside={
                  <span className="mono muted">
                    {cursor + 1} / {run.timeline.length}
                  </span>
                }
              >
                <div className="replay-controls">
                  <button
                    aria-label="Previous event"
                    disabled={cursor === 0}
                    onClick={() => setCursor((c) => c - 1)}
                  >
                    ←
                  </button>
                  <input
                    aria-label="Replay event timeline"
                    type="range"
                    min={0}
                    max={run.timeline.length - 1}
                    value={cursor}
                    onChange={(e) => setCursor(Number(e.target.value))}
                  />
                  <button
                    aria-label="Next event"
                    disabled={cursor === run.timeline.length - 1}
                    onClick={() => setCursor((c) => c + 1)}
                  >
                    →
                  </button>
                </div>
                <div className="event-timeline">
                  {run.timeline.map((event, index) => (
                    <button
                      key={event.sequence}
                      className={index === cursor ? 'timeline-row current' : 'timeline-row'}
                      onClick={() => setCursor(index)}
                    >
                      <span className="mono">+{event.time_ms} ms</span>
                      <span className="timeline-dot" />
                      <strong>{readable(event.kind)}</strong>
                      <span className="mono">
                        cash {money(event.portfolio.available)} / unmatched{' '}
                        {money(event.portfolio.unmatched_quantity)}
                      </span>
                    </button>
                  ))}
                </div>
                <details className="simulation-event-details">
                  <summary>Show the technical event record</summary>
                  <pre className="event-json" tabIndex={0}>
                    {JSON.stringify(selectedEvent?.detail, null, 2)}
                  </pre>
                </details>
              </Panel>
              <Panel
                title="Result details"
                aside={
                  <button
                    className="text-button"
                    onClick={() => {
                      const url = URL.createObjectURL(
                        new Blob([JSON.stringify(run, null, 2)], { type: 'application/json' }),
                      );
                      const link = document.createElement('a');
                      link.href = url;
                      link.download = `midas-${run.scenario_id}-${run.seed}.json`;
                      link.click();
                      URL.revokeObjectURL(url);
                    }}
                  >
                    Download result details ↓
                  </button>
                }
              >
                <div className="audit-summary">
                  <span>Market check</span>
                  <Badge tone={isVerified(run.evaluation) ? 'green' : 'neutral'}>
                    {statusLabel(run.evaluation.status)}
                  </Badge>
                  <span>Safety check</span>
                  <Badge tone={run.risk.allowed ? 'green' : 'red'}>
                    {run.risk.allowed ? 'passed' : 'blocked'}
                  </Badge>
                </div>
                <div className="panel-note">
                  A passed check means the virtual run followed its rules. It does not show that a
                  strategy would work in a real market. Repeating the same inputs reproduces the
                  saved result.
                </div>
                <details className="simulation-safety-details" open={!run.risk.allowed}>
                  <summary>
                    Why the safety check {run.risk.allowed ? 'passed' : 'was blocked'}
                  </summary>
                  <div>
                    <p className="audit-description">{run.risk.reasons.join('; ')}</p>
                    {run.invariant_violations.length > 0 && (
                      <ul className="red-text">
                        {run.invariant_violations.map((x) => (
                          <li key={x}>{x}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                </details>
                <details className="simulation-tech-record">
                  <summary>Technical result record</summary>
                  <div>
                    <code className="identifier hash">SHA-256 {run.reproducibility_hash}</code>
                    <details className="ledger-details">
                      <summary>Inspect full record ({run.ledger.length} movements)</summary>
                      <pre tabIndex={0}>{JSON.stringify(run.ledger, null, 2)}</pre>
                    </details>
                  </div>
                </details>
              </Panel>
            </>
          ) : (
            <Panel title="Experiment output">
              <Empty title="Ready for your first run">
                Choose a scenario and select Run scenario. Its virtual balance and recorded steps
                will appear here.
              </Empty>
            </Panel>
          )}
        </div>
      </div>
      <Panel title="Previous virtual runs" aside={<Badge>Each run is separate</Badge>}>
        {history.data?.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Scenario</th>
                  <th>Repeat number</th>
                  <th>Scenario checks</th>
                  <th>Virtual result · USD</th>
                  <th>Saved</th>
                </tr>
              </thead>
              <tbody>
                {history.data.slice(0, 10).map((row) => (
                  <tr key={row.id}>
                    <td>
                      <button
                        className="market-button"
                        onClick={() => {
                          setRun(row.payload);
                          setCursor(row.payload.timeline.length - 1);
                          setScenario(row.payload.scenario_id);
                          setSeed(row.payload.seed);
                        }}
                      >
                        {readable(row.payload.scenario_id)}
                        <ChevronRight size={14} />
                      </button>
                    </td>
                    <td className="mono">{row.payload.seed}</td>
                    <td>
                      <Badge tone={row.payload.passed ? 'green' : 'red'}>
                        {row.payload.passed ? 'Passed' : 'Review'}
                      </Badge>
                    </td>
                    <td
                      className={`mono ${Number(row.payload.portfolio.realized_pnl) < 0 ? 'red-text' : 'green'}`}
                    >
                      {money(row.payload.portfolio.realized_pnl, 4)}
                    </td>
                    <td className="mono muted">{date(row.received_ts_ms)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty title="No virtual runs yet">
            Runs you complete in the scenario library will appear here.
          </Empty>
        )}
      </Panel>
    </>
  );
}
function AnalyticsPage({ data }: { data: Analytics | undefined }) {
  const option = useMemo(
    () => ({
      ...chartBase,
      xAxis: {
        ...chartBase.xAxis,
        data: data?.simulations.map((x) => readable(x.scenario_id)),
        axisLabel: { rotate: 25, fontSize: 10 },
      },
      yAxis: { ...chartBase.yAxis, name: 'virtual USD' },
      series: [
        {
          type: 'bar',
          barMaxWidth: 24,
          data: data?.simulations.map((x) => ({
            value: Number(x.pnl),
            itemStyle: { color: Number(x.pnl) < 0 ? '#cf6d72' : '#5ab58f' },
          })),
        },
      ],
    }),
    [data],
  );
  return (
    <>
      {data?.feasibility && (
        <Panel title="Observed economics and simulated feasibility">
          <div className="portfolio-grid">
            {Object.entries({
              'Positive observed samples': data.feasibility.positive_observed_candidates,
              'Structural evidence samples': data.feasibility.structurally_supported_observations,
              'Passing net edge samples': data.feasibility.passing_net_edge_samples,
              'Hypothetical fills': data.feasibility.hypothetical_fill_count,
              'Modeled settlements': data.feasibility.modeled_settled_positions,
            }).map(([label, value]) => (
              <div key={label}>
                <span>{label}</span>
                <strong>{value}</strong>
              </div>
            ))}
          </div>
          <p className="panel-note">{data.feasibility.note}</p>
          <details className="book-audit">
            <summary>
              Opportunity lifetimes, executable fractions, lockup and rejection reasons
            </summary>
            <pre className="artifact-json">{JSON.stringify(data.feasibility, null, 2)}</pre>
          </details>
        </Panel>
      )}

      <div className="metrics">
        <Metric
          label="Recorded observations"
          value={data?.observation_window ?? 0}
          detail="Bounded window: latest 1,000 records"
          icon={Database}
        />
        <Metric
          label="Scenario experiments"
          value={data?.simulations.length ?? 0}
          detail="Latest 200 independent runs"
          icon={FlaskConical}
        />
        <Metric
          label="Invariant failures"
          value={data?.simulations.filter((x) => !x.passed).length ?? 0}
          detail="Expected virtual losses do not imply invariant failures"
          icon={ShieldX}
        />
        <Metric
          label="Observation provenance"
          value={data?.source === 'LIVE' ? 'LIVE' : 'DEMO'}
          detail="Separated from all synthetic execution results"
          icon={Radio}
        />
      </div>
      <Panel title="Recorded market activity" aside={<Badge>{data?.source ?? 'WAITING'}</Badge>}>
        <ActivityChart data={data} />
      </Panel>
      <div className="overview-grid">
        <Panel
          title="Independent experiment outcomes"
          aside={<Badge tone="cyan">SIMULATED · VIRTUAL USD</Badge>}
        >
          {data?.simulations.length ? (
            <Chart option={option} label="Realized virtual P&L per independent simulation" />
          ) : (
            <Empty title="No simulated results">
              Run scenarios to measure outcomes; this is not live trading performance.
            </Empty>
          )}
          <div className="panel-note">{data?.note}</div>
        </Panel>
        <Panel title="Classification distribution" aside={<Badge>RECORDED OBSERVATIONS</Badge>}>
          <div className="distribution">
            {Object.entries(data?.status_distribution ?? {}).map(([status, count]) => (
              <div key={status}>
                <div>
                  <span>{readable(status)}</span>
                  <strong className="mono">{count}</strong>
                </div>
                <div className="distribution-track">
                  <span style={{ width: `${(count / (data?.observation_window || 1)) * 100}%` }} />
                </div>
              </div>
            ))}
          </div>
        </Panel>
      </div>
    </>
  );
}
function EventList({ events }: { events: SystemEvent[] }) {
  return events.length ? (
    <div className="event-list">
      {events.map((event, i) => (
        <div className="system-event" key={`${event.timestamp_ms}:${i}`}>
          <span className="mono muted">{date(event.timestamp_ms)}</span>
          <Badge
            tone={
              event.severity === 'ERROR' ? 'red' : event.severity === 'WARNING' ? 'gold' : 'neutral'
            }
          >
            {event.severity}
          </Badge>
          <span>{event.message}</span>
          <span className="event-source">{event.source}</span>
        </div>
      ))}
    </div>
  ) : (
    <Empty title="No system events">Warnings and errors appear here when they occur.</Empty>
  );
}
function Incidents() {
  const query = useQuery({
    queryKey: ['incidents'],
    queryFn: () => api<Stored<SystemEvent>[]>('/incidents'),
  });
  const [severity, setSeverity] = useState('all');
  const [expanded, setExpanded] = useState<number | null>(null);
  const events =
    query.data?.filter((r) => severity === 'all' || r.payload.severity === severity) ?? [];
  return (
    <Panel
      title="Incident & system journal"
      aside={
        <select
          aria-label="Filter event severity"
          value={severity}
          onChange={(e) => setSeverity(e.target.value)}
        >
          <option value="all">All severities</option>
          <option>ERROR</option>
          <option>WARNING</option>
          <option>INFO</option>
        </select>
      }
    >
      {events.length ? (
        events.map((row) => (
          <div className="incident" key={row.id}>
            <button
              className="incident-button"
              onClick={() => setExpanded(expanded === row.id ? null : row.id)}
            >
              <span className="mono muted">{date(row.received_ts_ms)}</span>
              <Badge
                tone={
                  row.payload.severity === 'ERROR'
                    ? 'red'
                    : row.payload.severity === 'WARNING'
                      ? 'gold'
                      : 'neutral'
                }
              >
                {row.payload.severity}
              </Badge>
              <span>{row.payload.message}</span>
              <ChevronRight size={15} />
            </button>
            {expanded === row.id && (
              <pre className="event-json">{JSON.stringify(row, null, 2)}</pre>
            )}
          </div>
        ))
      ) : (
        <Empty title="No matching journal events">
          An empty incident list is healthy; operational events appear when recorded.
        </Empty>
      )}
    </Panel>
  );
}
function Telemetry({ state }: { state: State | undefined }) {
  return (
    <>
      <div className="metrics">
        <Metric
          label="Process uptime"
          value={state?.telemetry.uptime_seconds ?? '—'}
          unit="seconds"
          detail="Current API process"
          icon={Clock3}
        />
        <Metric
          label="Scan & persist latency"
          value={state?.telemetry.processing_latency_ms ?? '—'}
          unit="ms"
          detail="Last complete scan including database writes"
          icon={Activity}
        />
        <Metric
          label="Feed reconnects"
          value={state?.telemetry.reconnects ?? 0}
          detail="Current process; demo has no stream"
          icon={Radio}
        />
        <Metric
          label="Invalid books"
          value={state?.invalid_books ?? 0}
          detail="Excluded from verified observations"
          icon={TriangleAlert}
        />
      </div>
      <Panel title="Data pipeline health" aside={<Badge>{state?.connection ?? 'WAITING'}</Badge>}>
        <div className="telemetry-pipeline">
          {[
            [Radio, 'Public feed', state?.connection ?? 'Waiting'],
            [Database, 'Snapshot state', `${state?.books ?? 0} instruments`],
            [ShieldCheck, 'Mathematical engine', `${state?.verified_opportunities ?? 0} verified`],
            [Terminal, 'Audit storage', state?.telemetry.database_healthy ? 'Healthy' : 'Degraded'],
          ].map(([Icon, title, value], index) => {
            const Component = Icon as LucideIcon;
            return (
              <div key={index}>
                <Component size={21} />
                <strong>{String(title)}</strong>
                <span>{String(value)}</span>
              </div>
            );
          })}
        </div>
        <div className="health-list">
          <div>
            <span>Queue occupancy / bounded capacity</span>
            <strong>
              {state?.telemetry.queue_depth ?? 0} / {state?.telemetry.queue_capacity ?? 2048}
            </strong>
          </div>
          <div>
            <span>Last refresh</span>
            <strong>{date(state?.telemetry.last_refresh_ms)}</strong>
          </div>
          <div>
            <span>Last stream frame</span>
            <strong>{date(state?.telemetry.last_stream_message_ms)}</strong>
          </div>
          <div>
            <span>Append-only recorder</span>
            <strong>{state?.telemetry.recording_healthy ? 'Healthy' : 'Degraded'}</strong>
          </div>
        </div>
      </Panel>
    </>
  );
}
function SettingsPage() {
  const query = useQuery({ queryKey: ['settings'], queryFn: () => api<Settings>('/settings') });
  const client = useQueryClient();
  const stop = useMutation({
    mutationFn: (enabled: boolean) =>
      api<Settings>('/settings', {
        method: 'PATCH',
        body: JSON.stringify({ emergency_stop: enabled }),
      }),
    onSuccess: () => void client.invalidateQueries(),
  });
  return (
    <>
      <Panel title="Execution boundary" aside={<Badge tone="green">READ-ONLY + SIMULATION</Badge>}>
        <div className="settings-description">
          <ShieldCheck size={24} />
          <div>
            <h3>All trades are internal virtual events.</h3>
            <p>
              No wallet connection, trading keys, deposits, withdrawals, or live order endpoints
              exist in this application.
            </p>
          </div>
        </div>
        <div className="settings-row">
          <div>
            <strong>Emergency stop</strong>
            <p>
              Block new scenario runs and all new virtual proposals. Scenarios also test stop events
              during execution.
            </p>
          </div>
          <button
            className={query.data?.risk_limits.emergency_stop ? 'danger-button' : 'outline-button'}
            disabled={stop.isPending}
            onClick={() => stop.mutate(!query.data?.risk_limits.emergency_stop)}
          >
            {query.data?.risk_limits.emergency_stop ? 'Release stop' : 'Activate stop'}
          </button>
        </div>
        {stop.error && (
          <div className="alert danger" role="alert">
            {stop.error.message}
          </div>
        )}
      </Panel>
      <div className="overview-grid">
        <Panel title="Conservative risk limits" aside={<Badge>VIRTUAL USD / FRACTIONS</Badge>}>
          <div className="health-list">
            {Object.entries(query.data?.risk_limits ?? {}).map(([key, value]) => (
              <div key={key}>
                <span>{readable(key)}</span>
                <strong className="mono">{String(value)}</strong>
              </div>
            ))}
          </div>
        </Panel>
        <Panel title="Operating configuration">
          <div className="health-list">
            {[
              ['Mode', query.data?.mode],
              ['Discovery market limit', query.data?.market_limit],
              ['Refresh interval / seconds', query.data?.refresh_seconds],
              ['Execution', query.data?.execution],
            ].map(([key, value]) => (
              <div key={String(key)}>
                <span>{key}</span>
                <strong>{String(value ?? '—')}</strong>
              </div>
            ))}
          </div>
          <div className="panel-note">
            Mode and data parameters are configured through environment variables and take effect on
            restart. The emergency stop is process-local and resets to the configured default on
            restart.
          </div>
        </Panel>
      </div>
    </>
  );
}
