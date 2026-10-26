import { useQuery } from '@tanstack/react-query';
import {
  Activity,
  AlertTriangle,
  Clock3,
  Database,
  FlaskConical,
  Radio,
  RefreshCw,
  Server,
  ShieldCheck,
  ShieldX,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { api } from './api';
import './readiness.css';

type JsonRecord = Record<string, unknown>;
type GateStatus = 'PASS' | 'CONDITIONAL' | 'BLOCKED' | 'NOT MEASURED' | 'STALE';

const asRecord = (value: unknown): JsonRecord =>
  typeof value === 'object' && value !== null && !Array.isArray(value) ? (value as JsonRecord) : {};
const at = (value: unknown, ...keys: string[]): unknown =>
  keys.reduce<unknown>((current, key) => asRecord(current)[key], value);
const asNumber = (value: unknown): number | null =>
  typeof value === 'number' && Number.isFinite(value) ? value : null;
const asString = (value: unknown): string | null =>
  typeof value === 'string' && value.trim() ? value : null;
const asArray = (value: unknown): unknown[] => (Array.isArray(value) ? value : []);
const count = (value: unknown) =>
  asNumber(value) === null ? 'Not measured' : Number(value).toLocaleString();
const bytes = (value: unknown) => {
  const parsed = asNumber(value);
  if (parsed === null || parsed < 0) return 'Not measured';
  if (parsed < 1024) return `${parsed} B`;
  const units = ['KiB', 'MiB', 'GiB', 'TiB'];
  let size = parsed / 1024;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  return `${size.toFixed(1)} ${units[unit]}`;
};
const percent = (value: unknown) => {
  const parsed = asNumber(value);
  return parsed === null ? 'Not measured' : `${parsed.toFixed(1)}%`;
};
const fmtTime = (value: unknown) => {
  if (typeof value !== 'string' && typeof value !== 'number') return 'Not measured';
  const parsed = typeof value === 'number' ? new Date(value) : new Date(value);
  return Number.isNaN(parsed.getTime()) ? 'Not measured' : parsed.toLocaleString();
};
const disagreementTotal = (value: unknown) =>
  Object.values(asRecord(value)).reduce<number>((sum, item) => sum + (asNumber(item) ?? 0), 0);
const disagreementFor = (value: unknown, prefix: string) =>
  Object.entries(asRecord(value)).reduce(
    (sum, [key, item]) =>
      sum + (key === prefix || key.startsWith(`${prefix}:`) ? (asNumber(item) ?? 0) : 0),
    0,
  );
const queryOld = (updatedAt: number) => updatedAt > 0 && Date.now() - updatedAt > 90_000;

function Status({ value }: { value: GateStatus }) {
  return (
    <span className={`rr-status rr-${value.toLowerCase().replaceAll(' ', '-')}`}>{value}</span>
  );
}

function ServiceCard({
  title,
  status,
  detail,
  version,
  checkedAt,
  icon: Icon,
  error,
}: {
  title: string;
  status: GateStatus;
  detail: string;
  version?: string | null;
  checkedAt: unknown;
  icon: LucideIcon;
  error?: string;
}) {
  return (
    <article className="rr-service">
      <div className="rr-service-top">
        <span className="rr-icon">
          <Icon size={17} />
        </span>
        <h3>{title}</h3>
        <Status value={status} />
      </div>
      <p>{error ?? detail}</p>
      <div className="rr-service-meta">
        <span>Version: {version || 'Not reported'}</span>
        <span>Checked: {fmtTime(checkedAt)}</span>
      </div>
    </article>
  );
}

function GateCard({
  title,
  status,
  detail,
  evidence,
}: {
  title: string;
  status: GateStatus;
  detail: string;
  evidence: string;
}) {
  return (
    <article className="rr-gate">
      <div className="rr-gate-top">
        <h3>{title}</h3>
        <Status value={status} />
      </div>
      <p>{detail}</p>
      <span>{evidence}</span>
    </article>
  );
}

function MetricRow({
  label,
  value,
  denominator,
  basis,
}: {
  label: string;
  value: unknown;
  denominator?: unknown;
  basis: string;
}) {
  return (
    <div className="rr-funnel-row">
      <div className="rr-funnel-label">
        <span>{label}</span>
        <small>{basis}</small>
      </div>
      <strong>
        {count(value)}
        {denominator !== undefined ? ` / ${count(denominator)}` : ''}
      </strong>
    </div>
  );
}

export function Readiness() {
  const uiRevision = asString(import.meta.env.VITE_MIDAS_SOURCE_REVISION);
  const options = { refetchInterval: 30_000, staleTime: 30_000, retry: 1 };
  const health = useQuery({
    queryKey: ['readiness', 'health'],
    queryFn: () => api<JsonRecord>('/health'),
    ...options,
  });
  const state = useQuery({
    queryKey: ['readiness', 'state'],
    queryFn: () => api<JsonRecord>('/state'),
    ...options,
  });
  const reality = useQuery({
    queryKey: ['readiness', 'reality'],
    queryFn: () => api<JsonRecord>('/reality/overview'),
    ...options,
  });
  const veritas = useQuery({
    queryKey: ['readiness', 'veritas'],
    queryFn: () => api<JsonRecord>('/veritas/overview'),
    ...options,
  });
  const arena = useQuery({
    queryKey: ['readiness', 'arena'],
    queryFn: () => api<JsonRecord>('/arena/research-activity'),
    ...options,
  });
  const lab = useQuery({
    queryKey: ['readiness', 'laboratory'],
    queryFn: () => api<unknown[]>('/laboratory/campaigns'),
    ...options,
  });
  const resources = useQuery({
    queryKey: ['readiness', 'resources'],
    queryFn: () => api<JsonRecord>('/readiness/resources'),
    ...options,
  });

  const serviceHealth = asString(health.data?.status);
  const apiStatus: GateStatus = health.isError
    ? 'BLOCKED'
    : queryOld(health.dataUpdatedAt)
      ? 'STALE'
      : serviceHealth === 'READY'
        ? 'PASS'
        : serviceHealth === 'DEGRADED'
          ? 'CONDITIONAL'
          : serviceHealth === 'FAILED'
            ? 'BLOCKED'
            : 'NOT MEASURED';

  const realityHealth = asString(reality.data?.health);
  const realityAge = asNumber(reality.data?.collector_status_age_seconds);
  const realityStatus: GateStatus = reality.isError
    ? 'BLOCKED'
    : realityAge !== null && realityAge > 90
      ? 'STALE'
      : realityHealth === 'recording'
        ? 'CONDITIONAL'
        : realityHealth === 'degraded' || realityHealth === 'paused'
          ? 'BLOCKED'
          : realityHealth
            ? 'CONDITIONAL'
            : 'NOT MEASURED';

  const overview = asRecord(veritas.data?.opportunity_observatory);
  const economics = asRecord(overview.independent_economic_audit);
  const disagreementCount = disagreementTotal(economics.disagreement_counts);
  const referenceStatus = asString(economics.status);
  const veritasCurrent = economics.source_version_current === true;
  const validityDisagreements = disagreementFor(economics.disagreement_counts, 'validity');
  const sourceQualityDisagreements = disagreementFor(
    economics.disagreement_counts,
    'source_quality',
  );
  const priceDisagreements = disagreementFor(economics.disagreement_counts, 'gross');
  const feeDisagreements = disagreementFor(economics.disagreement_counts, 'fee_reference');
  const auditedPairCount = asNumber(economics.reference_pairs);
  const veritasStatus: GateStatus = veritas.isError
    ? 'BLOCKED'
    : queryOld(veritas.dataUpdatedAt)
      ? 'STALE'
      : referenceStatus === 'NOT_MEASURED' || auditedPairCount === null || auditedPairCount === 0
        ? 'NOT MEASURED'
        : referenceStatus === 'STALE' || !veritasCurrent
          ? 'STALE'
          : disagreementCount > 0
            ? 'BLOCKED'
            : asNumber(overview.pending_snapshot_count) !== 0 ||
                asNumber(overview.processed_snapshot_count) === null ||
                asNumber(overview.processed_snapshot_count) === 0
              ? 'CONDITIONAL'
              : referenceStatus !== 'MEASURED' && referenceStatus !== 'COMPLETE'
                ? 'CONDITIONAL'
                : 'PASS';

  const arenaJobs = asArray(arena.data?.jobs);
  const activeArenaJobs =
    asNumber(arena.data?.active_job_count) ??
    arenaJobs.filter((job) => ['RUNNING', 'QUEUED'].includes(String(asRecord(job).state))).length;
  const arenaStatus: GateStatus = arena.isError
    ? 'BLOCKED'
    : queryOld(arena.dataUpdatedAt)
      ? 'STALE'
      : (asNumber(arena.data?.stale_director_count) ?? 0) > 0
        ? 'BLOCKED'
        : activeArenaJobs > 0
          ? 'CONDITIONAL'
          : arena.data
            ? 'PASS'
            : 'NOT MEASURED';
  const laboratoryStatus: GateStatus = lab.isError
    ? 'BLOCKED'
    : queryOld(lab.dataUpdatedAt)
      ? 'STALE'
      : asString(at(health.data, 'laboratory', 'status')) === 'DEGRADED'
        ? 'CONDITIONAL'
        : lab.data
          ? 'PASS'
          : 'NOT MEASURED';

  const funnel = asRecord(overview.observation_funnel);
  const discovery = asRecord(overview.discovery);
  const integrity = asRecord(reality.data?.integrity);
  const capacity = asRecord(reality.data?.capacity);
  const collector = asRecord(reality.data?.collector);
  const sourceQuality = asRecord(reality.data?.source_quality);
  const runtimeResources = asRecord(resources.data?.services);
  const realityRuntime = asRecord(runtimeResources['midas-reality']);
  const apiRuntime = asRecord(runtimeResources['midas-api']);
  const observerRuntime = asRecord(runtimeResources['midas-veritas-observatory']);
  const observerLastRun = asRecord(resources.data?.observer_last_run);
  const realityService = asRecord(resources.data?.reality_service);
  const stagedReality = asRecord(resources.data?.staged_reality_candidate);
  const hostMemory = asRecord(resources.data?.host_memory);
  const hostPressure = asRecord(resources.data?.host_pressure);
  const disk = asRecord(resources.data?.reality_recording_filesystem);
  const effectiveRunwayDays = asNumber(capacity.effective_capacity_runway_days);
  const shortWindowRunwayDays = asNumber(capacity.short_window_capacity_runway_days);
  const configuredRunwayDays = asNumber(capacity.configured_capacity_runway_days);
  const capacityAlerts = asArray(capacity.alerts).map(String);
  const storageCritical =
    capacityAlerts.some((alert) =>
      [
        'CAPACITY_EXHAUSTED',
        'DISK_RESERVE_LOW',
        'SHORT_WINDOW_CAPACITY_CRITICAL_WITHIN_FOURTEEN_DAYS',
      ].includes(alert),
    ) ||
    (shortWindowRunwayDays !== null && shortWindowRunwayDays <= 14);
  const storageGateStatus: GateStatus =
    !Object.keys(capacity).length || asNumber(disk.available_bytes) === null
      ? 'NOT MEASURED'
      : storageCritical
        ? 'BLOCKED'
        : 'CONDITIONAL';
  const storageGateDetail = storageCritical
    ? `Active short-window runway is ${shortWindowRunwayDays === null ? 'not measured' : `${shortWindowRunwayDays.toFixed(1)} days`}; the capacity service reports a 14-day critical threshold. Staged budget or retention values remain inactive until the guarded recorder transition.`
    : 'Runway depends on the active retention and recording budget. Staged values remain separate until the guarded recorder transition.';
  const realitySample = asRecord(realityRuntime.sample_delta);
  const apiSample = asRecord(apiRuntime.sample_delta);
  const realityMemoryCurrent = asNumber(realityRuntime.memory_current_bytes);
  const realityMemoryHigh = asNumber(realityRuntime.memory_high_bytes);
  const realityMemoryHeadroom =
    realityMemoryCurrent !== null && realityMemoryHigh !== null
      ? Math.max(0, realityMemoryHigh - realityMemoryCurrent)
      : null;
  const realityNearMemoryHigh =
    realityMemoryCurrent !== null &&
    realityMemoryHigh !== null &&
    realityMemoryHigh > 0 &&
    // Hold 5% below the recorder's MemoryHigh boundary as minimum admission headroom.
    realityMemoryCurrent / realityMemoryHigh >= 0.95;
  const apiMemoryCurrent = asNumber(apiRuntime.memory_current_bytes);
  const apiMemoryHigh = asNumber(apiRuntime.memory_high_bytes);
  const apiMemoryHeadroom =
    apiMemoryCurrent !== null && apiMemoryHigh !== null
      ? Math.max(0, apiMemoryHigh - apiMemoryCurrent)
      : null;
  const apiNearMemoryHigh =
    apiMemoryCurrent !== null &&
    apiMemoryHigh !== null &&
    apiMemoryHigh > 0 &&
    apiMemoryCurrent / apiMemoryHigh >= 0.95;
  const currentCollectorError = asString(collector.error);
  const lastCollectorError = asString(collector.last_error);
  const lastCollectorErrorAt = asNumber(collector.last_error_ns);
  const configuredQueueBound = asNumber(collector.transport_queue_bound);
  const observabilityGaps = asArray(sourceQuality.observability_gaps).map(String);
  const finalized = asRecord(veritas.data?.finalized_reality_source);
  const funnelMeasured = funnel.reference_version_current === true;
  const recoveryStatus: GateStatus =
    finalized.full_recovery_verified === true
      ? 'PASS'
      : finalized.analysis_version
        ? 'BLOCKED'
        : 'NOT MEASURED';
  const eligible = asNumber(economics.net_eligible_pairs);
  const evidenceStatus: GateStatus = eligible === null ? 'NOT MEASURED' : 'CONDITIONAL';
  const resourceGateStatus: GateStatus =
    resources.isError || arenaStatus === 'BLOCKED' || apiStatus === 'BLOCKED'
      ? 'BLOCKED'
      : queryOld(resources.dataUpdatedAt)
        ? 'STALE'
        : realityNearMemoryHigh || apiNearMemoryHigh
          ? 'BLOCKED'
          : resources.data && realityRuntime.status === 'MEASURED'
            ? 'CONDITIONAL'
            : 'NOT MEASURED';
  const memoryPressureReasons = [
    realityNearMemoryHigh ? 'Reality is at or above 95% of MemoryHigh.' : null,
    apiNearMemoryHigh ? 'Mission Control API is at or above 95% of MemoryHigh.' : null,
  ].filter((reason): reason is string => reason !== null);
  const resourceGateDetail = memoryPressureReasons.length
    ? `${memoryPressureReasons.join(' ')} Defer additional heavy research until fresh admission evidence shows safe headroom.`
    : 'Cgroup and host pressure are sampled read-only. CPU and event deltas need two samples; Arena owner-job state supplies the bounded research admission view.';
  const gateStates: GateStatus[] = [
    veritasStatus,
    realityStatus,
    recoveryStatus,
    storageGateStatus,
    resourceGateStatus,
    evidenceStatus,
  ];
  const passingGates = gateStates.filter((status) => status === 'PASS').length;
  const updatedAt = Math.max(
    health.dataUpdatedAt,
    state.dataUpdatedAt,
    reality.dataUpdatedAt,
    veritas.dataUpdatedAt,
    arena.dataUpdatedAt,
    lab.dataUpdatedAt,
    resources.dataUpdatedAt,
  );
  const retryAll = () => {
    void Promise.all([
      health.refetch(),
      state.refetch(),
      reality.refetch(),
      veritas.refetch(),
      arena.refetch(),
      lab.refetch(),
      resources.refetch(),
    ]);
  };
  const currentMode = asString(state.data?.mode);

  return (
    <div className="readiness-page">
      <section className="rr-hero">
        <div>
          <div className="rr-eyebrow">ENGINEERING EVIDENCE / READINESS</div>
          <h1>Research Readiness</h1>
          <p>
            Evidence for reliable and reproducible market research. This view does not establish
            executable profitability.
          </p>
        </div>
        <div className="rr-hero-state">
          <span className="rr-demo">
            <FlaskConical size={15} />
            {currentMode === 'demo'
              ? 'DEMO MODE · NO LIVE ORDERS'
              : currentMode === 'live'
                ? 'LIVE PUBLIC OBSERVATION · NO LIVE ORDERS'
                : 'MODE NOT MEASURED · NO LIVE ORDERS'}
          </span>
          <span className="rr-updated">
            <Clock3 size={14} /> Refreshed {fmtTime(updatedAt)}
          </span>
          <button className="rr-refresh" onClick={retryAll} aria-label="Refresh readiness evidence">
            <RefreshCw size={15} /> Refresh
          </button>
        </div>
      </section>

      {(health.isError ||
        reality.isError ||
        veritas.isError ||
        arena.isError ||
        lab.isError ||
        resources.isError) && (
        <div className="rr-alert" role="alert">
          <AlertTriangle size={17} />
          One or more evidence services could not be read. Failed projections are shown as blocked;
          no gate passes on missing data.
        </div>
      )}

      <section className="rr-section">
        <div className="rr-section-heading">
          <div>
            <span>01</span>
            <h2>System readiness</h2>
          </div>
          <p>Current API projections with check times and reported versions.</p>
        </div>
        <div className="rr-services">
          <ServiceCard
            title="Mission Control API"
            status={apiStatus}
            icon={Server}
            detail={`Startup ${asString(health.data?.startup_status) ?? 'unreported'} · mode ${asString(health.data?.mode) ?? 'unknown'}`}
            version={`${asString(health.data?.application_version) ?? 'version unreported'} · ${asString(health.data?.api_release_identity) ?? 'release unreported'}`}
            checkedAt={health.data?.checked_at_utc ?? health.dataUpdatedAt}
            error={health.error?.message}
          />
          <ServiceCard
            title="Reality recorder"
            status={realityStatus}
            icon={Radio}
            detail={`${realityHealth ?? 'Health not measured'} · ${asString(collector.state) ?? 'collector state unavailable'} · source ${asString(sourceQuality.status) ?? 'quality unmeasured'}`}
            version={asString(collector.schema_version) ?? asString(collector.format_version)}
            checkedAt={
              collector.updated_ns
                ? Number(collector.updated_ns) / 1_000_000
                : reality.dataUpdatedAt
            }
            error={reality.error?.message}
          />
          <ServiceCard
            title="Veritas observer"
            status={veritasStatus}
            icon={Activity}
            detail={`${asString(overview.analysis_catchup_status) ?? asString(overview.status) ?? 'Analysis unavailable'} · ${count(overview.processed_snapshot_count)} snapshots indexed · ${count(overview.pending_snapshot_count)} pending · last processed capture ${fmtTime(overview.last_captured_at_utc)}`}
            version={asString(overview.analysis_version)}
            checkedAt={overview.updated_at_utc ?? veritas.dataUpdatedAt}
            error={veritas.error?.message}
          />
          <ServiceCard
            title="Laboratory"
            status={laboratoryStatus}
            icon={FlaskConical}
            detail={`${count(lab.data?.length)} persisted campaigns · recovery ${asString(at(health.data, 'laboratory', 'status')) ?? 'unreported'}`}
            version="Campaign manifests are individually versioned"
            checkedAt={lab.dataUpdatedAt}
            error={lab.error?.message}
          />
          <ServiceCard
            title="Arena"
            status={arenaStatus}
            icon={Database}
            detail={`${count(arenaJobs.length)} recent jobs · ${count(activeArenaJobs)} active in the bounded owner-job sample · synthetic / hypothetical evidence`}
            version={asString(arena.data?.state_source)}
            checkedAt={arena.dataUpdatedAt}
            error={arena.error?.message}
          />
        </div>
      </section>

      <section className="rr-section">
        <div className="rr-section-heading">
          <div>
            <span>02</span>
            <h2>Production and development versions</h2>
          </div>
          <p>
            Runtime labels come from active projections; absent release identities remain
            unreported.
          </p>
        </div>
        <div className="rr-version-grid">
          <div className="rr-version-card">
            <span className="rr-label">Mission Control web source revision</span>
            <strong>{uiRevision ?? 'Not declared by web service'}</strong>
            <small>
              Served by the local Vite dashboard service; verify against the API release below.
            </small>
          </div>
          <div className="rr-version-card">
            <span className="rr-label">API deployed release</span>
            <strong>{asString(health.data?.api_release_identity) ?? 'Not reported'}</strong>
            <small>
              {asString(health.data?.application_version) ?? 'Application version not reported'}
            </small>
          </div>
          <div className="rr-version-card">
            <span className="rr-label">Integrated MIDAS source revision</span>
            <strong>{asString(health.data?.integrated_source_revision) ?? 'Not reported'}</strong>
            <small>Only populated when the deployed service pins a source revision.</small>
          </div>
          <div className="rr-version-card">
            <span className="rr-label">Veritas analysis in persisted summary</span>
            <strong>{asString(overview.analysis_version) ?? 'Not measured'}</strong>
            <small>
              Reference {asString(economics.reference_version) ?? 'not measured'} · processed{' '}
              {count(overview.processed_snapshot_count)} /{' '}
              {count(
                (asNumber(overview.processed_snapshot_count) ?? 0) +
                  (asNumber(overview.pending_snapshot_count) ?? 0),
              )}{' '}
              snapshots
            </small>
          </div>
          <div className="rr-version-card">
            <span className="rr-label">Reality deployed collector</span>
            <strong>
              {asString(collector.release_commit) ??
                asString(collector.version) ??
                'Release identity not reported'}
            </strong>
            <small>
              Source root {asString(realityService.source_root_label) ?? 'not reported'} · state{' '}
              {asString(collector.state) ?? 'not measured'} · schema{' '}
              {asString(collector.schema_version) ?? 'not reported'}
            </small>
          </div>
          <div className="rr-version-card">
            <span className="rr-label">Veritas observer deployed release</span>
            <strong>
              {asString(observerLastRun.release_identity) ?? 'Release identity not reported'}
            </strong>
            <small>
              Last result {asString(observerLastRun.result) ?? 'not measured'} · exit{' '}
              {count(observerLastRun.exit_status)} ·{' '}
              {fmtTime(observerLastRun.execution_finished_at)}
            </small>
          </div>
          <div className="rr-version-card rr-version-muted">
            <span className="rr-label">Staged or undeployed candidate</span>
            <strong>{asString(stagedReality.commit) ?? 'Not reported by live APIs'}</strong>
            <small>
              {asString(stagedReality.branch) ?? 'Candidate branch unreported'} ·{' '}
              {asNumber(stagedReality.tracked_reality_source_changes) === null
                ? (asString(stagedReality.reason) ?? 'candidate state not measured')
                : `${count(stagedReality.tracked_reality_source_changes)} tracked source changes · ${stagedReality.tracked_reality_source_dirty === true ? 'dirty' : 'clean'}`}{' '}
              · not deployed
            </small>
          </div>
        </div>
      </section>

      <div className="rr-content-grid">
        <section className="rr-panel rr-span-two">
          <div className="rr-panel-heading">
            <div>
              <Database size={16} />
              <h2>Research evidence funnel</h2>
            </div>
            <span>
              {funnelMeasured
                ? `${count(overview.processed_snapshot_count)} of ${count((asNumber(overview.processed_snapshot_count) ?? 0) + (asNumber(overview.pending_snapshot_count) ?? 0))} snapshots · V6 reference cohort`
                : 'Evidence unavailable'}
            </span>
          </div>
          {!funnelMeasured ? (
            <div className="rr-empty">
              <Database size={22} />
              <strong>Independent cohort not measured</strong>
              <p>Missing counts remain blank; they are not treated as zero.</p>
            </div>
          ) : (
            <>
              <div className="rr-funnel-list">
                <MetricRow
                  label="Markets discovered"
                  value={discovery.latest_unique_market_ids}
                  denominator={discovery.latest_query_candidate_records}
                  basis="Latest bounded scan: unique IDs / candidate records"
                />
                <MetricRow
                  label="Selected market observations"
                  value={funnel.selected_market_observations}
                  denominator={funnel.bounded_query_frame_market_visits}
                  basis="Cumulative visits; repeated markets are retained"
                />
                <MetricRow
                  label="Observed pair observations"
                  value={funnel.observed_pair_observations}
                  basis="Repeated market observations with a pair result"
                />
                <MetricRow
                  label="Quality-valid pairs"
                  value={funnel.quality_valid_pair_observations}
                  denominator={funnel.observed_pair_observations}
                  basis="Same persisted reference version"
                />
                <MetricRow
                  label="Independently verified pairs"
                  value={funnel.independently_verified_pair_observations}
                  denominator={funnel.observed_pair_observations}
                  basis="Decimal reference replay; repeated observations"
                />
                <MetricRow
                  label="Positive gross candidates"
                  value={funnel.positive_gross_pair_observations}
                  denominator={funnel.independently_verified_pair_observations}
                  basis="Mathematical gross edge only"
                />
                <MetricRow
                  label="Economically eligible candidates"
                  value={funnel.net_economically_eligible_pair_observations}
                  denominator={economics.reference_pairs}
                  basis="Of all reference-audited pairs; support count is shown in the audit"
                />
              </div>
              <div className="rr-sampling-note">
                <strong>Sampling:</strong> {count(discovery.unique_market_ids_observed)} unique
                observed markets across {count(overview.processed_snapshot_count)} snapshots. Latest
                scan: {count(discovery.latest_stable_control_markets)} stable controls and{' '}
                {count(discovery.latest_rotating_markets)} rotating selections. These are correlated
                repeated observations, not independent trials.
              </div>
            </>
          )}
        </section>

        <section className="rr-panel">
          <div className="rr-panel-heading">
            <div>
              <ShieldCheck size={16} />
              <h2>Independent economic audit</h2>
            </div>
            <Status value={veritasStatus} />
          </div>
          <div className="rr-audit-metrics">
            <div>
              <span>Reference pairs</span>
              <strong>{count(economics.reference_pairs)}</strong>
            </div>
            <div>
              <span>Supported economics</span>
              <strong>{count(economics.economic_supported_pairs)}</strong>
            </div>
            <div>
              <span>Net eligible</span>
              <strong>{count(economics.net_eligible_pairs)}</strong>
            </div>
            <div>
              <span>Positive gross</span>
              <strong>{count(economics.positive_gross_pair_observations)}</strong>
            </div>
            <div>
              <span>Unsupported pairs</span>
              <strong>{count(economics.unsupported_pairs)}</strong>
            </div>
          </div>
          <dl className="rr-audit-list">
            <div>
              <dt>Source-quality disagreements</dt>
              <dd>{count(sourceQualityDisagreements)}</dd>
            </div>
            <div>
              <dt>Validity disagreements</dt>
              <dd>{count(validityDisagreements)}</dd>
            </div>
            <div>
              <dt>Price / gross disagreements</dt>
              <dd>{count(priceDisagreements)}</dd>
            </div>
            <div>
              <dt>Fee disagreements</dt>
              <dd>{count(feeDisagreements)}</dd>
            </div>
            <div>
              <dt>Other recorded disagreements</dt>
              <dd>
                {count(
                  disagreementCount -
                    validityDisagreements -
                    priceDisagreements -
                    feeDisagreements -
                    sourceQualityDisagreements,
                )}
              </dd>
            </div>
          </dl>
          <p className="rr-note">
            A zero-candidate result means none met this observed cohort’s constraints. Public books
            do not establish fills, queue position, acknowledgements, or realized P&amp;L.
          </p>
          <p className="rr-note">
            Disagreement values are category flags. One audited pair can contribute to more than one
            category, so the displayed flag total is not a count of unique affected pairs.
          </p>
          <details className="rr-details">
            <summary>Reference and artifact identities</summary>
            <p>Reference: {asString(economics.reference_version) ?? 'not measured'}</p>
            <p>
              Summary SHA-256:{' '}
              {asString(at(overview.summary_artifact, 'file_sha256')) ?? 'not reported'}
            </p>
            <p>Latest scan: {asString(discovery.latest_scan_id) ?? 'not measured'}</p>
            <p>
              Calculation agreement and source lineage are separately represented; the SHA
              identifies the persisted summary input.
            </p>
            {Object.entries(asRecord(economics.available_reference_versions)).map(
              ([version, metrics]) => (
                <p key={version}>
                  Historical reference {version}:{' '}
                  {asString(asRecord(metrics).status) ?? 'status unreported'} ·{' '}
                  {count(asRecord(metrics).processed_snapshot_count)} snapshots ·{' '}
                  {count(asRecord(metrics).net_eligible_pairs)} net eligible
                </p>
              ),
            )}
            <a href="/api/veritas/artifacts/continuous-analysis" target="_blank" rel="noreferrer">
              Open persisted analysis artifact
            </a>
          </details>
        </section>

        <section className="rr-panel">
          <div className="rr-panel-heading">
            <div>
              <Database size={16} />
              <h2>Data and recovery integrity</h2>
            </div>
            <Status value={recoveryStatus} />
          </div>
          <div className="rr-integrity-lines">
            <div>
              <span>Indexed finalized segments</span>
              <strong>
                {count(finalized.processed_segment_count)} /{' '}
                {count(finalized.catalog_segment_count)}
              </strong>
            </div>
            <div>
              <span>Analysis pending</span>
              <strong>
                {count(finalized.pending_segment_count)} · {count(finalized.pending_source_bytes)}{' '}
                bytes
              </strong>
            </div>
            <div>
              <span>Latest durable observation</span>
              <strong>
                {fmtTime(
                  collector.last_observation_ns
                    ? Number(collector.last_observation_ns) / 1_000_000
                    : null,
                )}
              </strong>
            </div>
            <div>
              <span>Source continuity</span>
              <strong>
                {asString(at(sourceQuality, 'sequence_state')) ?? 'Not measured'} · no global
                sequence proof
              </strong>
            </div>
            <div>
              <span>Integrity projection</span>
              <strong>
                {asString(integrity.status) ?? asString(integrity.state) ?? 'Not measured'}
              </strong>
            </div>
          </div>
          <p className="rr-note">
            Finalized-source analysis coverage is distinct from a full cold-recovery proof. The live
            API does not report a complete latest-boundary recovery receipt, so that gate remains
            unverified.
          </p>
          <div className="rr-observability-list" aria-label="Collector observability status">
            <div>
              <strong>Current collector error</strong>
              <span>
                {currentCollectorError ?? 'None reported by the current status projection'}
              </span>
            </div>
            <div>
              <strong>Last recorded error</strong>
              <span>
                {lastCollectorError
                  ? `${lastCollectorError.slice(0, 180)} · ${lastCollectorErrorAt === null ? 'time not reported' : fmtTime(lastCollectorErrorAt / 1_000_000)}`
                  : 'No prior error reported'}
              </span>
            </div>
            <div>
              <strong>Missing collector telemetry</strong>
              <span>
                {observabilityGaps.length
                  ? observabilityGaps
                      .map((gap) =>
                        gap === 'recent_persistence_window_incomplete'
                          ? 'recent persistence window / durable-write lag'
                          : gap === 'recovery_state_unreported'
                            ? 'recovery and replay state'
                            : gap === 'transport_queue_depth_unreported'
                              ? `transport queue depth${configuredQueueBound === null ? '' : ` (bound ${configuredQueueBound} frames)`}`
                              : gap.replaceAll('_', ' '),
                      )
                      .join(' · ')
                  : 'No gaps reported by the current source-quality projection'}
              </span>
            </div>
          </div>
          {asString(at(finalized.summary_artifact, 'url')) && (
            <a
              className="rr-link"
              href={String(at(finalized.summary_artifact, 'url'))}
              target="_blank"
              rel="noreferrer"
            >
              Open finalized-source evidence
            </a>
          )}
          <details className="rr-details">
            <summary>Recovery evidence</summary>
            <p>Analysis version: {asString(finalized.analysis_version) ?? 'not measured'}</p>
            <p>Last indexed ordinal: {count(finalized.last_processed_ordinal)}</p>
            <p>
              Artifact SHA-256:{' '}
              {asString(at(finalized.summary_artifact, 'file_sha256')) ?? 'not reported'}
            </p>
            <p>
              Cold recovery boundary:{' '}
              {finalized.full_recovery_verified === true
                ? 'verified by the active evidence API'
                : 'not verified by the active evidence API'}
            </p>
          </details>
        </section>

        <section className="rr-panel rr-span-two">
          <div className="rr-panel-heading">
            <div>
              <Activity size={16} />
              <h2>Resource sustainability and admission</h2>
            </div>
            <Status value={resourceGateStatus} />
          </div>
          {resources.isError ? (
            <div className="rr-empty" role="status">
              <AlertTriangle size={22} />
              <strong>Runtime resource telemetry unavailable</strong>
              <p>{resources.error.message}</p>
            </div>
          ) : (
            <>
              <div className="rr-resource-grid">
                <section>
                  <h3>Host pressure</h3>
                  <div>
                    <span>Available / total memory</span>
                    <strong>
                      {bytes(hostMemory.available_bytes)} / {bytes(hostMemory.total_bytes)}
                    </strong>
                  </div>
                  <div>
                    <span>CPU PSI avg10</span>
                    <strong>{percent(at(hostPressure, 'cpu', 'some', 'avg10'))}</strong>
                  </div>
                  <div>
                    <span>Memory PSI avg10</span>
                    <strong>{percent(at(hostPressure, 'memory', 'some', 'avg10'))}</strong>
                  </div>
                  <div>
                    <span>I/O PSI full avg10</span>
                    <strong>{percent(at(hostPressure, 'io', 'full', 'avg10'))}</strong>
                  </div>
                </section>
                <section>
                  <h3>Reality recorder cgroup</h3>
                  <div>
                    <span>Current / MemoryHigh</span>
                    <strong>
                      {bytes(realityRuntime.memory_current_bytes)} /{' '}
                      {bytes(realityRuntime.memory_high_bytes)}
                    </strong>
                  </div>
                  <div>
                    <span>Headroom below MemoryHigh</span>
                    <strong>{bytes(realityMemoryHeadroom)}</strong>
                  </div>
                  <div>
                    <span>CPU use of quota, latest sample</span>
                    <strong>{percent(realitySample.cpu_quota_utilization_percent)}</strong>
                  </div>
                  <div>
                    <span>CPU throttled, sample delta</span>
                    <strong>{count(realitySample.cpu_throttled_delta_usec)} μs</strong>
                  </div>
                  <div>
                    <span>High events since cgroup start</span>
                    <strong>
                      {count(at(realityRuntime, 'memory_events_since_cgroup_start', 'high'))}
                    </strong>
                  </div>
                </section>
                <section>
                  <h3>Mission Control API cgroup</h3>
                  <div>
                    <span>Current / MemoryHigh</span>
                    <strong>
                      {bytes(apiRuntime.memory_current_bytes)} /{' '}
                      {bytes(apiRuntime.memory_high_bytes)}
                    </strong>
                  </div>
                  <div>
                    <span>Headroom below MemoryHigh</span>
                    <strong>{bytes(apiMemoryHeadroom)}</strong>
                  </div>
                  <div>
                    <span>Current / MemoryMax</span>
                    <strong>
                      {bytes(apiRuntime.memory_current_bytes)} /{' '}
                      {bytes(apiRuntime.memory_max_bytes)}
                    </strong>
                  </div>
                  <div>
                    <span>CPU use of quota, latest sample</span>
                    <strong>{percent(apiSample.cpu_quota_utilization_percent)}</strong>
                  </div>
                  <div>
                    <span>CPU throttled, sample delta</span>
                    <strong>{count(apiSample.cpu_throttled_delta_usec)} μs</strong>
                  </div>
                  <div>
                    <span>OOM kills since cgroup start</span>
                    <strong>
                      {count(at(apiRuntime, 'memory_events_since_cgroup_start', 'oom_kill'))}
                    </strong>
                  </div>
                </section>
                <section>
                  <h3>Veritas observer last one-shot</h3>
                  <div>
                    <span>Result / exit code</span>
                    <strong>
                      {asString(observerLastRun.result) ?? 'Not measured'} /{' '}
                      {count(observerLastRun.exit_status)}
                    </strong>
                  </div>
                  <div>
                    <span>Peak memory / configured limit</span>
                    <strong>
                      {bytes(observerLastRun.memory_peak_bytes)} /{' '}
                      {bytes(observerLastRun.memory_max_bytes)}
                    </strong>
                  </div>
                  <div>
                    <span>Finished</span>
                    <strong>{fmtTime(observerLastRun.execution_finished_at)}</strong>
                  </div>
                  <div>
                    <span>Release identity</span>
                    <strong>{asString(observerLastRun.release_identity) ?? 'Not reported'}</strong>
                  </div>
                </section>
                <section>
                  <h3>Recording storage</h3>
                  <div>
                    <span>Filesystem available / total</span>
                    <strong>
                      {bytes(disk.available_bytes)} / {bytes(disk.total_bytes)}
                    </strong>
                  </div>
                  <div>
                    <span>Recorder budget</span>
                    <strong>{bytes(capacity.budget_bytes)}</strong>
                  </div>
                  <div>
                    <span>Effective runway, active config</span>
                    <strong>
                      {effectiveRunwayDays === null
                        ? 'Not measured'
                        : `${effectiveRunwayDays.toFixed(1)} days`}
                    </strong>
                  </div>
                  <div>
                    <span>Short-window runway</span>
                    <strong>
                      {shortWindowRunwayDays === null
                        ? 'Not measured'
                        : `${shortWindowRunwayDays.toFixed(1)} days`}
                    </strong>
                  </div>
                  <div>
                    <span>Staged budget / retention</span>
                    <strong>
                      {bytes(capacity.configured_budget_bytes)} /{' '}
                      {count(capacity.configured_retention_days)} days ·{' '}
                      {capacity.budget_change_pending_restart === true ||
                      capacity.retention_change_pending_restart === true
                        ? 'pending restart'
                        : 'reported active'}
                    </strong>
                  </div>
                  <div>
                    <span>Staged runway</span>
                    <strong>
                      {configuredRunwayDays === null
                        ? 'Not measured'
                        : `${configuredRunwayDays.toFixed(1)} days · not active`}
                    </strong>
                  </div>
                  <div>
                    <span>Retention remaining</span>
                    <strong>
                      {asNumber(capacity.retention_seconds_remaining) === null
                        ? 'Not measured'
                        : `${(Number(capacity.retention_seconds_remaining) / 86400).toFixed(1)} days`}
                    </strong>
                  </div>
                </section>
              </div>
              <div className="rr-sampling-note">
                <strong>Sampling bounds:</strong>{' '}
                {asString(resources.data?.sampling) ?? 'read method not reported'}. CPU and event
                deltas appear after two dashboard samples; cumulative counters are labeled
                separately. Observer cgroup: {asString(observerRuntime.status) ?? 'not measured'} ·
                last result {asString(observerLastRun.result) ?? 'not measured'} · exit{' '}
                {count(observerLastRun.exit_status)} · peak{' '}
                {bytes(observerLastRun.memory_peak_bytes)}.
              </div>
            </>
          )}
        </section>
      </div>

      <section className="rr-section rr-gates-section">
        <div className="rr-section-heading">
          <div>
            <span>03</span>
            <h2>Readiness gates</h2>
          </div>
          <p>{passingGates} of 6 gates currently pass. Missing evidence never counts as a pass.</p>
        </div>
        <div className="rr-gates">
          <GateCard
            title="Independent research correctness"
            status={veritasStatus}
            detail={
              veritasStatus === 'PASS'
                ? 'Current Decimal reference is present with no recorded calculation disagreements.'
                : 'Independent reference is missing, stale, or reports disagreements.'
            }
            evidence={`Reference ${asString(economics.reference_version) ?? 'not measured'} · ${count(disagreementCount)} disagreements`}
          />
          <GateCard
            title="Collector integrity and observability"
            status={realityStatus}
            detail={
              realityHealth === 'recording'
                ? 'Collector is recording; feed continuity remains explicitly unsequenced and some source uncertainty persists.'
                : 'Collector health or source-quality evidence is degraded or unavailable.'
            }
            evidence={`Age ${realityAge === null ? 'not measured' : `${realityAge.toFixed(1)} s`} · ${asString(sourceQuality.status) ?? 'quality not measured'}`}
          />
          <GateCard
            title="Recovery and reproducibility"
            status={recoveryStatus}
            detail="The indexed finalized-source replay is shown separately from cold recovery. Full latest-boundary verification is not reported."
            evidence={`${count(finalized.processed_segment_count)} of ${count(finalized.catalog_segment_count)} finalized segments indexed`}
          />
          <GateCard
            title="Storage sustainability"
            status={storageGateStatus}
            detail={storageGateDetail}
            evidence={`Active runway ${effectiveRunwayDays === null ? 'not measured' : `${effectiveRunwayDays.toFixed(1)} days`} · short window ${shortWindowRunwayDays === null ? 'not measured' : `${shortWindowRunwayDays.toFixed(1)} days`} · staged ${configuredRunwayDays === null ? 'not measured' : `${configuredRunwayDays.toFixed(1)} days`} · filesystem available ${bytes(disk.available_bytes)}`}
          />
          <GateCard
            title="Resource and scheduling stability"
            status={resourceGateStatus}
            detail={resourceGateDetail}
            evidence={`${count(activeArenaJobs)} active Arena jobs · queue ${count(at(state.data, 'telemetry', 'queue_depth'))} · Reality headroom ${bytes(realityMemoryHeadroom)}`}
          />
          <GateCard
            title="Economic evidence sufficiency"
            status={evidenceStatus}
            detail={
              eligible === 0
                ? 'No net-eligible candidates in the measured cohort; this is an informative result, not profitability evidence.'
                : 'Candidate evidence is observational and still does not establish execution or realized return.'
            }
            evidence={`${count(economics.net_eligible_pairs)} net eligible · fills and P&L unmeasured`}
          />
        </div>
      </section>

      <div className="rr-footer-note">
        <ShieldX size={15} /> No live order execution. Research readiness classifies evidence
        quality; it does not authorize trading or establish profitability.
      </div>
    </div>
  );
}
