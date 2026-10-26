import { useQuery } from '@tanstack/react-query';
import {
  Activity,
  ArrowUpRight,
  CheckCircle2,
  CircleHelp,
  Clock3,
  Database,
  HardDrive,
  Radio,
  RefreshCw,
  ShieldCheck,
  ShieldX,
  TriangleAlert,
} from 'lucide-react';
import { api } from './api';
import './research-readiness.css';

type JsonObject = Record<string, unknown>;
type GateStatus = 'PASS' | 'CONDITIONAL' | 'BLOCKED' | 'NOT MEASURED' | 'STALE';
type Query<T> = {
  data: T | undefined;
  error: Error | null;
  isError: boolean;
  isPending: boolean;
  dataUpdatedAt: number;
  refetch: () => Promise<unknown>;
};

const object = (value: unknown): JsonObject =>
  value && typeof value === 'object' && !Array.isArray(value) ? (value as JsonObject) : {};
const string = (value: unknown): string | undefined =>
  typeof value === 'string' && value.length > 0 ? value : undefined;
const number = (value: unknown): number | undefined =>
  typeof value === 'number' && Number.isFinite(value) ? value : undefined;
const systemdBytes = (value: unknown): number | undefined => {
  if (number(value) !== undefined) return number(value);
  if (typeof value !== 'string' || !/^\d+$/.test(value)) return undefined;
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) ? parsed : undefined;
};
const fmt = (value: unknown) =>
  number(value) === undefined ? '—' : number(value)!.toLocaleString('en-US');
const timestamp = (value: number | undefined) =>
  value ? new Date(value).toLocaleString() : 'Not measured';
const asUtcTime = (value: unknown) => {
  const parsed = typeof value === 'string' ? Date.parse(value) : NaN;
  return Number.isFinite(parsed) ? new Date(parsed).toLocaleString() : undefined;
};
const asNsTime = (value: unknown) => {
  const parsed = number(value);
  return parsed ? new Date(parsed / 1_000_000).toLocaleString() : undefined;
};
const statusText = (value: unknown) => string(value)?.replaceAll('_', ' ') ?? 'NOT REPORTED';
const ageText = (milliseconds: number | undefined) => {
  if (milliseconds === undefined || milliseconds < 0) return 'Age not measured';
  const seconds = Math.floor(milliseconds / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
};

function useEvidence<T extends JsonObject>(path: string): Query<T> {
  return useQuery<T, Error>({
    queryKey: ['research-readiness', path],
    queryFn: () => api<T>(path),
    refetchInterval: 30_000,
    staleTime: 15_000,
    retry: 1,
  });
}

function Badge({ status }: { status: GateStatus | string }) {
  const normalized = status
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');
  return <span className={`rr-badge ${normalized}`}>{status}</span>;
}

function Panel({
  title,
  subtitle,
  icon: Icon,
  children,
  className = '',
}: {
  title: string;
  subtitle?: string;
  icon: typeof Activity;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`rr-panel ${className}`}>
      <header className="rr-panel-head">
        <div className="rr-panel-icon">
          <Icon size={16} />
        </div>
        <div>
          <h2>{title}</h2>
          {subtitle && <p>{subtitle}</p>}
        </div>
      </header>
      {children}
    </section>
  );
}

function Gate({ title, status, detail }: { title: string; status: GateStatus; detail: string }) {
  return (
    <article className="rr-gate">
      <div className="rr-gate-title">
        <h3>{title}</h3>
        <Badge status={status} />
      </div>
      <p>{detail}</p>
    </article>
  );
}

function ServiceRow({
  name,
  state,
  version,
  verifiedAt,
  note,
  href,
}: {
  name: string;
  state: string;
  version?: string;
  verifiedAt: number | undefined;
  note: string;
  href: string;
}) {
  return (
    <tr>
      <th scope="row">{name}</th>
      <td>
        <Badge status={state} />
      </td>
      <td className="rr-mono">{version ?? 'Not reported by service'}</td>
      <td>
        <time dateTime={verifiedAt ? new Date(verifiedAt).toISOString() : undefined}>
          {timestamp(verifiedAt)}
        </time>
      </td>
      <td>{note}</td>
      <td>
        <a className="rr-source-link" href={href} target="_blank" rel="noreferrer">
          Evidence <ArrowUpRight size={13} />
        </a>
      </td>
    </tr>
  );
}

const gateStatus = (
  available: boolean,
  failed: boolean,
  stale: boolean,
  predicate: boolean,
): GateStatus => {
  if (!available) return failed ? 'BLOCKED' : 'NOT MEASURED';
  if (stale) return 'STALE';
  return predicate ? 'PASS' : 'CONDITIONAL';
};

export function ResearchReadiness() {
  const healthQuery = useEvidence<JsonObject>('/health');
  const realityQuery = useEvidence<JsonObject>('/reality/overview');
  const operationsQuery = useEvidence<JsonObject>('/reality/operations');
  const veritasQuery = useEvidence<JsonObject>('/veritas/overview');
  const historicalAuditQuery = useEvidence<JsonObject>(
    '/veritas/artifacts/independent-opportunity-audit',
  );
  const arenaQuery = useEvidence<JsonObject>('/arena/research-activity');
  const laboratoryQuery = useEvidence<JsonObject>('/laboratory/catalog');

  const health = object(healthQuery.data);
  const reality = object(realityQuery.data);
  const collector = object(reality.collector);
  const currentCollectorError = string(collector.error);
  const historicalCollectorError = string(collector.last_error);
  const historicalCollectorErrorTime = asNsTime(
    collector.last_error_ns ?? collector.last_error_at_ns,
  );
  const sourceQuality = object(reality.source_quality);
  const realityIntegrity = object(reality.integrity);
  const capacity = object(reality.capacity);
  const operations = object(operationsQuery.data);
  const recorderResources = object(operations.recorder_resources);
  const activeRealityConfig = object(operations.configuration);
  const stagedStoragePolicy = object(operations.storage_policy);
  const veritas = object(veritasQuery.data);
  const audit = object(veritas.independent_economic_audit);
  const funnel = object(veritas.observation_funnel);
  const arena = object(arenaQuery.data);
  const laboratory = object(health.laboratory);
  const now = Date.now();
  const queryAge = (query: Query<JsonObject>) =>
    query.dataUpdatedAt ? now - query.dataUpdatedAt : undefined;
  const isStale = (query: Query<JsonObject>) =>
    queryAge(query) !== undefined && queryAge(query)! > 90_000;
  const displayedServiceState = (query: Query<JsonObject>, state: string) =>
    query.isError && query.data ? 'STALE' : isStale(query) ? 'STALE' : state;

  const apiState = string(health.status) ?? (healthQuery.isError ? 'UNAVAILABLE' : 'CONNECTING');
  const realityState =
    string(reality.health) ?? (realityQuery.isError ? 'UNAVAILABLE' : 'NOT MEASURED');
  const veritasState =
    string(veritas.status) ?? (veritasQuery.isError ? 'UNAVAILABLE' : 'NOT MEASURED');
  const labState =
    string(laboratory.status) ?? (laboratoryQuery.isError ? 'UNAVAILABLE' : 'NOT MEASURED');
  const arenaState = string(arena.status) ?? (arenaQuery.isError ? 'UNAVAILABLE' : 'NOT MEASURED');

  const referenceCount = number(audit.reference_pairs);
  const supportedCount = number(audit.economic_supported_pairs);
  const rawDisagreementCounts = audit.disagreement_counts;
  const disagreementCountsAvailable =
    rawDisagreementCounts !== null &&
    typeof rawDisagreementCounts === 'object' &&
    !Array.isArray(rawDisagreementCounts);
  const disagreementMap = object(rawDisagreementCounts);
  const disagreementValues = Object.values(disagreementMap);
  const disagreementCountsValid =
    disagreementCountsAvailable &&
    disagreementValues.every(
      (value) => Number.isSafeInteger(value) && typeof value === 'number' && value >= 0,
    );
  const disagreementCount = disagreementCountsValid
    ? disagreementValues.reduce<number>((total, value) => total + (value as number), 0)
    : undefined;
  const disagreementCategoryTotal = (matches: (key: string) => boolean) =>
    disagreementCountsValid
      ? disagreementValues.reduce<number>((total, value, index) => {
          const key = Object.keys(disagreementMap)[index];
          return total + (matches(key) ? (value as number) : 0);
        }, 0)
      : undefined;
  const validityDisagreements = disagreementCategoryTotal((key) => /valid/i.test(key));
  const priceEdgeDisagreements = disagreementCategoryTotal((key) => /price|edge/i.test(key));
  const feeDisagreements = disagreementCategoryTotal((key) => /fee/i.test(key));
  const classifiedDisagreementCount = [
    validityDisagreements,
    priceEdgeDisagreements,
    feeDisagreements,
  ].reduce<number | undefined>(
    (total, value) => (total === undefined || value === undefined ? undefined : total + value),
    0,
  );
  const otherDisagreements =
    disagreementCount === undefined || classifiedDisagreementCount === undefined
      ? undefined
      : disagreementCount - classifiedDisagreementCount;
  const auditAvailable =
    string(audit.status) === 'MEASURED' &&
    referenceCount !== undefined &&
    supportedCount !== undefined;
  const auditReported =
    ['MEASURED', 'STALE'].includes(String(audit.status)) && referenceCount !== undefined;
  const auditHasRows =
    referenceCount !== undefined && Number.isSafeInteger(referenceCount) && referenceCount > 0;
  const auditVersionStale =
    audit.source_version_current === false && audit.reference_version != null;
  const summaryUpdatedAtMs =
    typeof veritas.updated_at_utc === 'string' ? Date.parse(veritas.updated_at_utc) : NaN;
  const auditTimestampAvailable = Number.isFinite(summaryUpdatedAtMs) && summaryUpdatedAtMs <= now;
  const auditFresh =
    !veritasQuery.isError &&
    !isStale(veritasQuery) &&
    auditTimestampAvailable &&
    now - summaryUpdatedAtMs < 24 * 60 * 60 * 1000;
  const researchCorrectness = gateStatus(
    auditReported &&
      auditHasRows &&
      supportedCount !== undefined &&
      disagreementCountsValid &&
      string(audit.reference_version) !== undefined &&
      audit.source_version_current !== undefined &&
      auditTimestampAvailable,
    veritasQuery.isError && !veritasQuery.data,
    auditTimestampAvailable && (!auditFresh || auditVersionStale),
    auditAvailable &&
      auditHasRows &&
      disagreementCountsValid &&
      audit.source_version_current === true &&
      supportedCount === referenceCount &&
      disagreementCount === 0 &&
      string(audit.reference_version) !== undefined,
  );

  const sourceStatus = statusText(sourceQuality.status).toLowerCase();
  const collectorObserved = realityQuery.data !== undefined;
  const collectorHealthy = ['healthy', 'recording'].includes(
    String(reality.capture_health ?? reality.health).toLowerCase(),
  );
  const collectorIntegrity = gateStatus(
    collectorObserved,
    realityQuery.isError && !realityQuery.data,
    isStale(realityQuery),
    collectorHealthy && sourceStatus === 'healthy' && collector.sequence_verified === true,
  );

  const recoveryStatus = String(
    realityIntegrity.status ?? realityIntegrity.readiness ?? '',
  ).toLowerCase();
  const recoveryObserved = Object.keys(realityIntegrity).length > 0;
  const capacityAlerts = Array.isArray(capacity.alerts)
    ? capacity.alerts.filter((item): item is string => typeof item === 'string')
    : undefined;
  const archiveAlerts = capacityAlerts?.filter((item) => item.startsWith('ARCHIVE_')) ?? [];
  const recoveryComplete =
    ['verified', 'complete', 'current'].includes(recoveryStatus) &&
    realityIntegrity.latest_boundary_verified === true &&
    archiveAlerts.length === 0 &&
    capacityAlerts !== undefined;
  const recoveryGate = gateStatus(
    recoveryObserved,
    realityQuery.isError && !realityQuery.data,
    isStale(realityQuery),
    recoveryComplete,
  );

  const capacitySample = object(capacity.sample);
  const byteRunwaySeconds = number(capacity.estimated_storage_seconds_remaining);
  const retentionRunwaySeconds = number(capacity.retention_seconds_remaining);
  const measuredRunwayDays = [byteRunwaySeconds, retentionRunwaySeconds]
    .filter((value): value is number => value !== undefined && value >= 0)
    .reduce<number | undefined>(
      (minimum, value) => (minimum === undefined ? value : Math.min(minimum, value)),
      undefined,
    );
  const runway =
    number(
      capacity.storage_runway_days ?? capacity.runway_days ?? capacity.projected_runway_days,
    ) ?? (measuredRunwayDays === undefined ? undefined : measuredRunwayDays / 86_400);
  const capacityMeasuredNs = number(capacity.measured_ns);
  const capacityAgeMs =
    capacityMeasuredNs === undefined ? undefined : now - capacityMeasuredNs / 1_000_000;
  const capacityMonitorIntervalSeconds =
    number(stagedStoragePolicy.capacity_monitor_interval_seconds) ?? 1_800;
  const capacityStale =
    capacityAgeMs !== undefined &&
    (capacityAgeMs < 0 || capacityAgeMs > capacityMonitorIntervalSeconds * 2_000);
  const capacitySampleSeconds = number(capacitySample.seconds);
  const capacityRate = number(capacity.compressed_bytes_per_second);
  const storageObserved =
    runway !== undefined &&
    capacityMeasuredNs !== undefined &&
    capacitySampleSeconds !== undefined &&
    capacitySampleSeconds >= 60 &&
    capacityRate !== undefined;
  const displayedRunway = storageObserved ? runway : undefined;
  const storageExhausted = capacityAlerts?.includes('CAPACITY_EXHAUSTED') === true;
  const storageGate: GateStatus = storageExhausted
    ? 'BLOCKED'
    : storageObserved
      ? isStale(realityQuery) || capacityStale
        ? 'STALE'
        : runway! >= 30
          ? 'PASS'
          : 'CONDITIONAL'
      : realityQuery.isError && !realityQuery.data
        ? 'BLOCKED'
        : 'NOT MEASURED';

  const activeJobs = number(arena.active_job_count);
  const queuedJobs = number(arena.queued_job_count);
  const staleDirectors = number(arena.stale_director_count);
  const unverifiedDirectors = number(arena.unverified_director_count);
  const arenaAlertCount = Array.isArray(arena.alerts) ? arena.alerts.length : undefined;
  const arenaNote = [
    `${fmt(activeJobs)} active / ${fmt(queuedJobs)} queued jobs`,
    staleDirectors === undefined ? undefined : `${fmt(staleDirectors)} stale directors`,
    unverifiedDirectors === undefined
      ? undefined
      : `${fmt(unverifiedDirectors)} unverified directors`,
    arenaAlertCount === undefined
      ? undefined
      : `${fmt(arenaAlertCount)} ${arenaAlertCount === 1 ? 'alert' : 'alerts'}`,
  ]
    .filter((part): part is string => part !== undefined)
    .join('; ');
  const serviceRows = Array.isArray(operations.services) ? operations.services.map(object) : [];
  const realityService = serviceRows.find((service) => service.unit === 'midas-reality.service');
  const serviceProperties = object(realityService?.properties);
  const memoryCurrent = systemdBytes(serviceProperties.MemoryCurrent);
  const memoryHigh = systemdBytes(serviceProperties.MemoryHigh);
  const memoryHeadroom =
    memoryCurrent !== undefined && memoryHigh !== undefined
      ? memoryHigh - memoryCurrent
      : undefined;
  const cpuTimeNs = systemdBytes(serviceProperties.CPUUsageNSec);
  const hostPressure = object(recorderResources.host_pressure);
  const pressureAvg10 = (name: string, mode: string) => {
    const raw = object(object(hostPressure[name])[mode]).avg10;
    const parsed = typeof raw === 'string' ? Number(raw) : number(raw);
    return parsed !== undefined && Number.isFinite(parsed)
      ? `${parsed.toFixed(1)}%`
      : 'Not reported';
  };
  const schedulingGate: GateStatus =
    arenaQuery.isError && !arenaQuery.data
      ? 'BLOCKED'
      : activeJobs !== undefined &&
          queuedJobs !== undefined &&
          memoryCurrent !== undefined &&
          memoryHigh !== undefined
        ? isStale(arenaQuery) || isStale(operationsQuery)
          ? 'STALE'
          : 'CONDITIONAL'
        : 'NOT MEASURED';

  const eligibleObservations = number(funnel.net_economically_eligible_pair_observations);
  const economicObserved =
    string(audit.status) === 'MEASURED' && auditHasRows && supportedCount !== undefined;
  const economicSufficiency: GateStatus = !economicObserved
    ? veritasQuery.isError && !veritasQuery.data
      ? 'BLOCKED'
      : 'NOT MEASURED'
    : !auditTimestampAvailable
      ? 'NOT MEASURED'
      : !auditFresh || auditVersionStale
        ? 'STALE'
        : 'CONDITIONAL';

  const gateRows = [
    {
      title: 'Independent research correctness',
      status: researchCorrectness,
      detail: auditReported
        ? !auditHasRows
          ? 'No independent reference pairs were audited; an empty result cannot establish calculation correctness.'
          : `${fmt(referenceCount)} ${string(audit.reference_version) ?? 'unversioned'} reference pairs; ${fmt(disagreementCount)} recorded disagreements. ${!auditTimestampAvailable ? 'Summary timestamp is missing or invalid; freshness cannot be verified. ' : ''}${auditVersionStale ? `Integrated reference ${string(audit.implementation_reference_version) ?? 'unreported'} has not audited these observations.` : 'Agreement does not prove execution.'}`
        : 'A current independent audit result is unavailable. Missing evidence cannot pass this gate.',
    },
    {
      title: 'Collector integrity and observability',
      status: collectorIntegrity,
      detail: `Capture ${statusText(reality.capture_health ?? reality.health)}; source quality ${statusText(sourceQuality.status)}; sequence state ${statusText(collector.sequence_state)}.`,
    },
    {
      title: 'Recovery and reproducibility',
      status: recoveryGate,
      detail: recoveryObserved
        ? `Recovery evidence reports ${statusText(realityIntegrity.status ?? realityIntegrity.readiness)}; latest boundary completion is ${String(realityIntegrity.latest_boundary_verified ?? 'not reported')}.`
        : 'No complete latest-boundary recovery evidence is exposed by the current service response.',
    },
    {
      title: 'Storage sustainability',
      status: storageGate,
      detail: storageObserved
        ? `${runway!.toFixed(1)} days to the lowest measured byte-budget or retention limit. The estimate uses ${fmt(capacitySample.segments)} segments over ${capacitySampleSeconds!.toFixed(0)} seconds and ${fmt(capacity.estimated_bytes_per_day)} compressed bytes per day; sampled ${ageText(capacityAgeMs)}.`
        : 'A supported storage runway estimate is not available from the capacity artifact.',
    },
    {
      title: 'Resource and scheduling stability',
      status: schedulingGate,
      detail:
        activeJobs !== undefined && memoryHeadroom !== undefined
          ? `${fmt(activeJobs)} active and ${fmt(queuedJobs)} queued Arena jobs; ${fmt(staleDirectors)} stale and ${fmt(unverifiedDirectors)} unverified directors; ${fmt(arenaAlertCount)} reported alerts. Reality systemd memory headroom is ${fmt(Math.max(0, memoryHeadroom))} bytes${memoryHeadroom < 0 ? ' (above MemoryHigh)' : ''}; overlap admission is not fully measured.`
          : 'Current job admission and collector resource headroom are not both available.',
    },
    {
      title: 'Economic evidence sufficiency',
      status: economicSufficiency,
      detail: economicObserved
        ? `${fmt(supportedCount)} supported pair observations across ${fmt(referenceCount)} audited reference pairs; ${fmt(eligibleObservations)} net eligible pair observations. No validated sufficiency threshold is configured.`
        : 'Current independent economic evidence is unavailable; candidate counts remain unmeasured.',
    },
  ];

  const stages = [
    [
      'Bounded frame market visits',
      funnel.bounded_frame_market_visits ?? funnel.bounded_query_frame_market_visits,
    ],
    ['Selected market observations', funnel.selected_market_observations],
    ['Observed pair records', funnel.observed_pair_observations],
    ['Quality-valid pairs', funnel.quality_valid_pair_observations],
    ['Independently verified pairs', funnel.independent_snapshot_valid_pair_observations],
    ['Independent economic support', funnel.independent_economic_supported_pair_observations],
    ['Positive gross pairs', funnel.positive_gross_pair_observations],
    ['Net economically eligible pairs', funnel.net_economically_eligible_pair_observations],
  ] as const;
  const largestStage = Math.max(1, ...stages.map(([, value]) => number(value) ?? 0));
  const funnelAvailable = string(funnel.basis) !== undefined;

  const historicalAudit = object(historicalAuditQuery.data);
  const historicalData = object(historicalAudit.data);
  const historicalDate = asUtcTime(
    historicalData.generated_at_utc ??
      historicalData.captured_at_utc ??
      historicalData.timestamp_utc,
  );
  const artifactSha = string(historicalAudit.file_sha256);
  const demo = String(health.mode).toLowerCase() === 'demo';
  const runtimeVeritasVersion = string(veritas.analysis_version);
  const runtimeRealityHash = string(
    collector.implementation_sha256 ?? collector.source_code_sha256,
  );
  const runtimeRealityVersion =
    string(collector.code_version ?? collector.version) ??
    (runtimeRealityHash ? `sha256:${runtimeRealityHash.slice(0, 12)}` : undefined);
  const apiVersion = string(health.api_version ?? health.version ?? health.build_id);
  const apiBuildCommit = string(health.build_commit);
  const stagedCandidateIdentity = string(operations.staged_candidate_identity);
  const integratedBranch = import.meta.env.VITE_MIDAS_INTEGRATED_BRANCH;
  const integratedCommit = import.meta.env.VITE_MIDAS_INTEGRATED_COMMIT;
  const integratedDirty = import.meta.env.VITE_MIDAS_INTEGRATED_DIRTY;
  const summaryUpdatedAt = asUtcTime(veritas.updated_at_utc);
  const visibleRunwayStale = capacityStale || isStale(realityQuery);

  const retryAll = () => {
    void Promise.all([
      healthQuery.refetch(),
      realityQuery.refetch(),
      operationsQuery.refetch(),
      veritasQuery.refetch(),
      historicalAuditQuery.refetch(),
      arenaQuery.refetch(),
      laboratoryQuery.refetch(),
    ]);
  };

  return (
    <div className="research-readiness">
      <div className="rr-intro">
        <div>
          <div className="rr-eyebrow">MISSION CONTROL / RESEARCH EVIDENCE</div>
          <h1>Research Readiness</h1>
          <p>
            Assess whether MIDAS can collect, verify, reproduce, and interpret public market
            evidence reliably.
          </p>
        </div>
        <div className="rr-intro-actions">
          <Badge status={demo ? 'DEMO · SYNTHETIC' : 'LIVE SERVICE MODE'} />
          <button className="rr-refresh" onClick={retryAll}>
            <RefreshCw size={14} /> Refresh evidence
          </button>
        </div>
      </div>

      {demo && (
        <div className="rr-demo-banner" role="status">
          <TriangleAlert size={18} />
          <div>
            <strong>DEMO MODE IS ACTIVE</strong>
            <span>
              The Mission Control API reports synthetic demo mode. Do not interpret synthetic
              observations as production market evidence.
            </span>
          </div>
        </div>
      )}

      {healthQuery.isError && !healthQuery.data && (
        <div className="rr-alert" role="alert">
          <ShieldX size={17} /> Core API health could not be verified:{' '}
          {healthQuery.error?.message ?? 'request failed'}
          <button onClick={() => void healthQuery.refetch()}>Retry</button>
        </div>
      )}

      <Panel
        title="System readiness"
        subtitle="Read-only health and evidence timestamps from current service APIs."
        icon={Activity}
      >
        <div className="rr-table-wrap">
          <table className="rr-service-table">
            <thead>
              <tr>
                <th scope="col">Service</th>
                <th scope="col">State</th>
                <th scope="col">Reported version</th>
                <th scope="col">Last verified</th>
                <th scope="col">Evidence note</th>
                <th scope="col">Source</th>
              </tr>
            </thead>
            <tbody>
              <ServiceRow
                name="Mission Control API"
                state={displayedServiceState(healthQuery, apiState)}
                version={apiVersion}
                verifiedAt={healthQuery.dataUpdatedAt}
                note={`Mode ${statusText(health.mode)}; live execution ${String(health.live_execution ?? 'not reported')}.`}
                href="/api/health"
              />
              <ServiceRow
                name="Reality"
                state={displayedServiceState(realityQuery, realityState)}
                version={runtimeRealityVersion}
                verifiedAt={realityQuery.dataUpdatedAt}
                note={`Capture ${statusText(reality.capture_health)}; source ${statusText(sourceQuality.status)}.`}
                href="/api/reality/overview"
              />
              <ServiceRow
                name="Veritas"
                state={displayedServiceState(veritasQuery, veritasState)}
                version={runtimeVeritasVersion}
                verifiedAt={veritasQuery.dataUpdatedAt}
                note={
                  veritasQuery.error?.message ??
                  `Analysis ${statusText(veritas.analysis_catchup_status ?? veritas.measurement_status)}.`
                }
                href="/api/veritas/overview"
              />
              <ServiceRow
                name="Laboratory"
                state={displayedServiceState(laboratoryQuery, labState)}
                version={string(laboratory.version)}
                verifiedAt={laboratoryQuery.dataUpdatedAt}
                note={`${fmt(object(laboratoryQuery.data).datasets instanceof Array ? (object(laboratoryQuery.data).datasets as unknown[]).length : undefined)} datasets listed by catalog.`}
                href="/api/laboratory/catalog"
              />
              <ServiceRow
                name="Arena"
                state={displayedServiceState(arenaQuery, arenaState)}
                version={string(arena.version)}
                verifiedAt={arenaQuery.dataUpdatedAt}
                note={arenaNote}
                href="/api/arena/research-activity"
              />
            </tbody>
          </table>
        </div>
        <div className="rr-evidence-note">
          <Clock3 size={14} /> “Last verified” is this dashboard’s successful API read time. It is
          separate from the underlying observation timestamp.
        </div>
      </Panel>

      <div className="rr-grid rr-grid-two">
        <Panel
          title="Deployment and code identities"
          subtitle="Current service identities are separate from integrated and staged code."
          icon={Radio}
        >
          <div className="rr-version-list">
            <div>
              <span>Mission Control mode</span>
              <strong>{statusText(health.mode)}</strong>
              <small>Execution enabled: {String(health.live_execution ?? 'not reported')}</small>
            </div>
            <div>
              <span>Deployed Mission Control API version</span>
              <strong className="rr-mono">{apiVersion ?? 'Not reported by API'}</strong>
              <small>Build commit: {apiBuildCommit ?? 'Not supplied by deployment metadata'}</small>
            </div>
            <div>
              <span>Integrated repository identity</span>
              <strong className="rr-mono">
                {integratedBranch} @ {integratedCommit}
              </strong>
              <small>
                Dashboard build source; working tree {integratedDirty ? 'had changes' : 'was clean'}
                at build time.
              </small>
            </div>
            <div>
              <span>Reality runtime identity</span>
              <strong className="rr-mono">
                {runtimeRealityVersion ?? 'Not exposed by the active status API'}
              </strong>
              {runtimeRealityHash && (
                <small className="rr-mono">Implementation SHA-256 {runtimeRealityHash}</small>
              )}
              <small>{statusText(reality.collector_deployment)}</small>
            </div>
            <div>
              <span>Veritas analysis identity</span>
              <strong className="rr-mono">
                {runtimeVeritasVersion ?? 'Unavailable or not reported'}
              </strong>
              <small>
                {veritasQuery.isError
                  ? 'Active overview request failed; prior artifacts are displayed separately as historical evidence.'
                  : 'Identity comes from the active Veritas summary.'}
              </small>
            </div>
            <div>
              <span>Other component versions</span>
              <strong>Not reported</strong>
              <small>
                Laboratory and Arena APIs do not publish a build identity in these health responses.
              </small>
            </div>
            <div>
              <span>Staged Reality candidate</span>
              <strong className="rr-mono">
                {stagedCandidateIdentity ?? 'Not reported by operations API'}
              </strong>
              <small>
                {string(operations.collector_deployment) ??
                  'No candidate identity or deployment procedure is exposed.'}
              </small>
            </div>
          </div>
          <p className="rr-panel-foot">
            Un-deployed checkout changes are not observable from service health. The saved audit
            below is historical and keeps its own date and checksum.
          </p>
        </Panel>

        <Panel
          title="Observation funnel"
          subtitle="Cumulative repeated observations across processed snapshots; these are dependent visits, not independent trials."
          icon={Activity}
        >
          {funnelAvailable ? (
            <div className="rr-funnel" aria-label="Cumulative observation funnel">
              {stages.map(([label, value]) => {
                const count = number(value);
                const width = count === undefined ? 0 : Math.max(1, (count / largestStage) * 100);
                return (
                  <div className="rr-funnel-row" key={label}>
                    <span>{label}</span>
                    <div className="rr-bar-track">
                      <div className="rr-bar" style={{ width: `${width}%` }} />
                    </div>
                    <strong>{fmt(count)}</strong>
                  </div>
                );
              })}
              <div className="rr-funnel-meta">
                <span>
                  Summary updated: <strong>{summaryUpdatedAt ?? 'Not measured'}</strong>{' '}
                  <Badge
                    status={
                      !auditTimestampAvailable ? 'NOT MEASURED' : auditFresh ? 'CURRENT' : 'STALE'
                    }
                  />
                </span>
                <span>
                  Audit version:{' '}
                  <strong className="rr-mono">
                    {string(funnel.reference_version) ?? 'Not measured'}
                  </strong>{' '}
                  {funnel.reference_version_current === true
                    ? '(current)'
                    : '(historical or stale)'}
                </span>
                <span>
                  Bounded markets in latest discovery:{' '}
                  <strong>{fmt(object(veritas.discovery).current_bounded_eligible_markets)}</strong>
                </span>
                <span>
                  Unique markets observed: <strong>{fmt(funnel.unique_markets_observed)}</strong>
                </span>
                <span>
                  Unique positive-gross markets:{' '}
                  <strong>{fmt(funnel.unique_markets_with_positive_gross)}</strong>
                </span>
              </div>
              <p className="rr-panel-foot">
                {string(funnel.basis)}.{' '}
                {String(funnel.independent_trials) === 'false'
                  ? 'Repeated scans and market states are correlated.'
                  : ''}
              </p>
              {number(funnel.positive_gross_pair_observations) === 0 &&
                number(funnel.quality_valid_pair_observations) !== undefined &&
                number(funnel.quality_valid_pair_observations)! > 0 && (
                  <p className="rr-zero-result">
                    No positive gross pair was found in the measured quality-valid observations.
                  </p>
                )}
            </div>
          ) : (
            <div className="rr-empty">
              <Database size={20} />
              <p>
                {veritasQuery.isError
                  ? 'The current Veritas overview is unavailable, so this funnel is unmeasured.'
                  : 'No processed Veritas observations are available yet.'}
              </p>
            </div>
          )}
        </Panel>
      </div>

      <Panel
        title="Evidence-based readiness gates"
        subtitle="Missing evidence never passes a gate. A conditional status means the evidence supports only a limited claim."
        icon={ShieldCheck}
      >
        <div className="rr-gates">
          {gateRows.map((gate) => (
            <Gate key={gate.title} {...gate} />
          ))}
        </div>
      </Panel>

      <div className="rr-grid rr-grid-three">
        <Panel
          title="Economic verification"
          subtitle="Separate mathematical agreement from source lineage and execution."
          icon={CheckCircle2}
        >
          {auditAvailable ? (
            <div className="rr-economic-metrics">
              <div>
                <span>Audited reference pairs</span>
                <strong>{fmt(referenceCount)}</strong>
              </div>
              <div>
                <span>Snapshot-valid pairs</span>
                <strong>{fmt(audit.snapshot_valid_pairs)}</strong>
              </div>
              <div>
                <span>Economic support</span>
                <strong>{fmt(supportedCount)}</strong>
              </div>
              <div>
                <span>Positive gross observations</span>
                <strong>{fmt(audit.positive_gross_pair_observations)}</strong>
              </div>
              <div>
                <span>Net eligible observations</span>
                <strong>{fmt(audit.net_eligible_pairs ?? eligibleObservations)}</strong>
              </div>
              <div>
                <span>Unsupported pairs</span>
                <strong>{fmt(audit.unsupported_pairs)}</strong>
              </div>
              <div>
                <span>Disagreements</span>
                <strong>{fmt(disagreementCount)}</strong>
              </div>
            </div>
          ) : (
            <div className="rr-empty compact">
              <CircleHelp size={18} />
              <p>Current independent audit counts are not available.</p>
            </div>
          )}
          <div className="rr-economic-disagreements" aria-label="Economic disagreement breakdown">
            <div>
              <span>Validity</span>
              <strong>{fmt(validityDisagreements)}</strong>
            </div>
            <div>
              <span>Price / edge</span>
              <strong>{fmt(priceEdgeDisagreements)}</strong>
            </div>
            <div>
              <span>Fees</span>
              <strong>{fmt(feeDisagreements)}</strong>
            </div>
            <div>
              <span>Other</span>
              <strong>{fmt(otherDisagreements)}</strong>
            </div>
          </div>
          <details className="rr-details">
            <summary>Audit status and source lineage</summary>
            <pre>
              {JSON.stringify(
                {
                  status: audit.status ?? 'NOT MEASURED',
                  disagreement_counts: audit.disagreement_counts ?? null,
                  unsupported_pairs: audit.unsupported_pairs ?? null,
                  unsupported_assumptions: audit.limitations ?? audit.unsupported_reasons ?? null,
                  basis: audit.basis ?? null,
                  source_lineage_agreement_is_separate: true,
                },
                null,
                2,
              )}
            </pre>
          </details>
          <p className="rr-panel-foot">
            Order-book evidence cannot establish queue position, acknowledgment, fills, settlement,
            or realized P&amp;L. Gamma&apos;s market-level restricted flag is metadata;
            user-specific geoblock and order acceptance are not measured.
          </p>
        </Panel>

        <Panel
          title="Data and recovery integrity"
          subtitle="Latest state exposed by Reality; absent fields are not inferred."
          icon={Database}
        >
          <div className="rr-integrity-list">
            <div>
              <span>Source continuity</span>
              <strong>{statusText(collector.sequence_state ?? collector.sequence_verified)}</strong>
            </div>
            <div>
              <span>Recovery status</span>
              <strong>{statusText(realityIntegrity.status ?? realityIntegrity.readiness)}</strong>
            </div>
            <div>
              <span>Persisted Veritas analysis coverage</span>
              <strong>
                {veritas.processed_snapshot_count === undefined
                  ? 'Not reported'
                  : `${fmt(veritas.processed_snapshot_count)} processed / ${fmt(veritas.pending_snapshot_count)} pending`}
              </strong>
              <small>
                {statusText(veritas.analysis_catchup_status ?? veritas.measurement_status)}; summary
                updated {summaryUpdatedAt ?? 'at an unknown time'}.
              </small>
            </div>
            <div>
              <span>Latest durable observation</span>
              <strong>
                {asNsTime(collector.last_durable_write_ns ?? collector.last_persisted_ns) ??
                  asUtcTime(collector.last_durable_write_utc) ??
                  'Not reported'}
              </strong>
            </div>
            <div>
              <span>Archive / catalog integrity</span>
              <strong>
                {statusText(
                  realityIntegrity.archive_status ??
                    realityIntegrity.catalog_status ??
                    realityIntegrity.status,
                )}
              </strong>
            </div>
            <div>
              <span>Archive staging alerts</span>
              <strong>
                {capacityAlerts === undefined
                  ? 'Not reported'
                  : archiveAlerts.length
                    ? archiveAlerts.join(', ')
                    : 'No archive alert reported'}
              </strong>
            </div>
          </div>
          <details className="rr-details">
            <summary>Underlying Reality and Veritas evidence</summary>
            <pre>
              {JSON.stringify(
                {
                  collector: reality.collector,
                  source_quality: reality.source_quality,
                  integrity: reality.integrity,
                  capacity_alerts: capacityAlerts ?? null,
                  veritas: {
                    status: veritas.status,
                    analysis_version: veritas.analysis_version,
                    updated_at_utc: veritas.updated_at_utc,
                    processed_snapshot_count: veritas.processed_snapshot_count,
                    pending_snapshot_count: veritas.pending_snapshot_count,
                    analysis_catchup_status: veritas.analysis_catchup_status,
                    observation_funnel: veritas.observation_funnel,
                  },
                },
                null,
                2,
              )}
            </pre>
          </details>
        </Panel>

        <Panel
          title="Resource sustainability"
          subtitle="Runtime readings and declared capacity estimates only."
          icon={HardDrive}
        >
          <div className="rr-integrity-list">
            <div>
              <span>Storage runway to lowest measured limit</span>
              <strong>
                {displayedRunway === undefined
                  ? 'Not measured'
                  : `${displayedRunway.toFixed(1)} days${visibleRunwayStale ? ' · STALE' : ''}`}
              </strong>
            </div>
            <div>
              <span>Active recorder budget / retention</span>
              <strong>
                {activeRealityConfig.budget_bytes !== undefined ||
                activeRealityConfig.retention_days !== undefined
                  ? `${fmt(activeRealityConfig.budget_bytes)} bytes / ${fmt(activeRealityConfig.retention_days)} days`
                  : 'Not reported'}
              </strong>
            </div>
            <div>
              <span>Staged raw budget / retention policy</span>
              <strong>
                {stagedStoragePolicy.raw_budget_bytes !== undefined ||
                stagedStoragePolicy.retention_stop_days !== undefined
                  ? `${fmt(stagedStoragePolicy.raw_budget_bytes)} bytes / ${fmt(stagedStoragePolicy.retention_stop_days)} days`
                  : 'Not reported'}
              </strong>
            </div>
            <div>
              <span>Measured free disk space</span>
              <strong>{fmt(capacity.filesystem_free_bytes)} bytes</strong>
            </div>
            <div>
              <span>Capacity sample</span>
              <strong>
                {capacityMeasuredNs !== undefined && capacitySampleSeconds !== undefined
                  ? `${fmt(capacitySample.segments)} segments / ${capacitySampleSeconds.toFixed(0)} s; ${ageText(capacityAgeMs)}`
                  : 'Not measured'}
              </strong>
            </div>
            <div>
              <span>Estimated compressed growth</span>
              <strong>
                {capacity.compressed_bytes_per_second !== undefined
                  ? `${fmt(capacity.estimated_bytes_per_day)} bytes/day`
                  : 'Not measured'}
              </strong>
            </div>
            <div>
              <span>Reality capture status</span>
              <strong>{statusText(reality.capture_health)}</strong>
            </div>
            <div>
              <span>Reality unit CPU time since start</span>
              <strong>
                {cpuTimeNs !== undefined
                  ? `${(cpuTimeNs / 1_000_000_000).toLocaleString(undefined, { maximumFractionDigits: 1 })} s`
                  : 'Not reported'}
              </strong>
            </div>
            <div>
              <span>Host CPU pressure, avg10</span>
              <strong>{pressureAvg10('cpu', 'some')}</strong>
            </div>
            <div>
              <span>Host memory pressure, avg10</span>
              <strong>{pressureAvg10('memory', 'some')}</strong>
            </div>
            <div>
              <span>Host I/O full pressure, avg10</span>
              <strong>{pressureAvg10('io', 'full')}</strong>
            </div>
            <div>
              <span>Active research jobs</span>
              <strong>{fmt(activeJobs)}</strong>
            </div>
            <div>
              <span>Queued research jobs</span>
              <strong>{fmt(queuedJobs)}</strong>
            </div>
            <div>
              <span>Reality cgroup memory current / MemoryHigh</span>
              <strong>
                {memoryCurrent !== undefined && memoryHigh !== undefined
                  ? `${fmt(memoryCurrent)} / ${fmt(memoryHigh)} bytes`
                  : 'Not reported'}
              </strong>
            </div>
            <div>
              <span>Reality cgroup memory headroom</span>
              <strong>
                {memoryHeadroom !== undefined
                  ? memoryHeadroom < 0
                    ? `${fmt(-memoryHeadroom)} bytes above MemoryHigh`
                    : `${fmt(memoryHeadroom)} bytes`
                  : 'Not reported'}
              </strong>
            </div>
          </div>
          <details className="rr-details">
            <summary>Capacity and service telemetry</summary>
            <pre>
              {JSON.stringify(
                {
                  capacity,
                  active_recorder_configuration: activeRealityConfig,
                  staged_storage_policy: stagedStoragePolicy,
                  operations: operations.services ?? null,
                  arena: {
                    active_job_count: arena.active_job_count,
                    queued_job_count: arena.queued_job_count,
                    stale_director_count: arena.stale_director_count,
                    unverified_director_count: arena.unverified_director_count,
                    alerts: arena.alerts ?? null,
                  },
                  retention: operations.storage_policy ?? null,
                },
                null,
                2,
              )}
            </pre>
          </details>
          <p className="rr-panel-foot">
            CPU time is cumulative for the unit lifetime. Pressure values are host PSI averages over
            the previous ten seconds and remain unmeasured when the recorder cgroup is absent.
          </p>
        </Panel>
      </div>

      <div className="rr-grid rr-grid-two">
        <Panel
          title="Historical independent audit"
          subtitle="A saved artifact is labeled by its own timestamp and checksum; it is not a current service result."
          icon={Clock3}
        >
          {historicalAuditQuery.data ? (
            <div className="rr-history-card">
              <div className="rr-history-head">
                <Badge status="HISTORICAL" />
                <strong>
                  {string(historicalAudit.artifact) ?? 'Independent opportunity audit'}
                </strong>
              </div>
              <dl>
                <div>
                  <dt>Artifact time</dt>
                  <dd>{historicalDate ?? 'Not present in artifact'}</dd>
                </div>
                <div>
                  <dt>Campaign / evidence identity</dt>
                  <dd className="rr-mono">
                    {string(historicalData.campaign_id ?? historicalData.artifact_id) ??
                      'Not reported'}
                  </dd>
                </div>
                <div>
                  <dt>SHA-256</dt>
                  <dd className="rr-mono">{artifactSha ?? 'Not returned by API'}</dd>
                </div>
              </dl>
              <details className="rr-details">
                <summary>Inspect saved audit payload</summary>
                <pre>{JSON.stringify(historicalData, null, 2)}</pre>
              </details>
            </div>
          ) : (
            <div className="rr-empty compact">
              <Database size={18} />
              <p>{historicalAuditQuery.error?.message ?? 'Historical artifact unavailable.'}</p>
            </div>
          )}
          <a
            className="rr-source-link"
            href="/api/veritas/artifacts/independent-opportunity-audit"
            target="_blank"
            rel="noreferrer"
          >
            Open artifact response <ArrowUpRight size={13} />
          </a>
        </Panel>

        <Panel
          title="Evidence freshness and service errors"
          subtitle="The polling timestamp is separate from capture and persistence timestamps."
          icon={Clock3}
        >
          <div className="rr-freshness-list">
            <div>
              <span>Current Reality collector error</span>
              <strong>
                {currentCollectorError
                  ? 'Active incident'
                  : collector.error === null
                    ? 'None reported'
                    : 'Not reported'}
              </strong>
              {currentCollectorError && <small>{currentCollectorError}</small>}
            </div>
            <div>
              <span>Historical Reality collector error</span>
              <strong>
                {historicalCollectorError
                  ? `Last error ${historicalCollectorErrorTime ?? '(timestamp not reported)'}`
                  : 'Not reported'}
              </strong>
              {historicalCollectorError && <small>{historicalCollectorError}</small>}
            </div>
            {[
              ['Mission Control API', healthQuery],
              ['Reality', realityQuery],
              ['Reality operations', operationsQuery],
              ['Veritas overview', veritasQuery],
              ['Arena', arenaQuery],
              ['Laboratory', laboratoryQuery],
            ].map(([label, query]) => {
              const q = query as Query<JsonObject>;
              return (
                <div key={label as string}>
                  <span>{label as string}</span>
                  <strong>
                    {q.isError
                      ? 'Read failed'
                      : q.dataUpdatedAt
                        ? ageText(queryAge(q))
                        : q.isPending
                          ? 'Loading'
                          : 'Not measured'}
                  </strong>
                  {q.isError && <small>{q.error?.message ?? 'Request failed'}</small>}
                </div>
              );
            })}
          </div>
          {operationsQuery.isError && (
            <p className="rr-error-note">
              <TriangleAlert size={14} /> Read-only Reality operations details are unavailable. The
              dashboard does not change service state.
            </p>
          )}
        </Panel>
      </div>

      <footer className="rr-footer">
        <ShieldCheck size={14} />
        <span>
          Read-only research readiness. No orders, wallet actions, recorder restarts, or service
          control are available from this view.
        </span>
        <span className="rr-footer-time">
          Refreshed{' '}
          {timestamp(
            Math.max(
              healthQuery.dataUpdatedAt,
              realityQuery.dataUpdatedAt,
              veritasQuery.dataUpdatedAt,
              arenaQuery.dataUpdatedAt,
              laboratoryQuery.dataUpdatedAt,
            ) || undefined,
          )}
        </span>
      </footer>
    </div>
  );
}
