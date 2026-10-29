import { useQuery } from '@tanstack/react-query';
import { Activity, AlertTriangle } from 'lucide-react';
import { api } from './api';
import { preciseUtcTime } from './frontierTime';

type PressureWindow = { avg10?: number | null };
type PressureSample = { some?: PressureWindow | null; full?: PressureWindow | null };
type MemoryEventCounts = {
  high?: number | null;
  max?: number | null;
  oom?: number | null;
  oom_kill?: number | null;
  oom_group_kill?: number | null;
};
type ResourceSnapshot = {
  captured_at_utc?: string | null;
  host_memory?: {
    total_bytes?: number | null;
    available_bytes?: number | null;
    swap_total_bytes?: number | null;
    swap_free_bytes?: number | null;
  } | null;
  host_pressure?: { memory?: PressureSample | null } | null;
  services?: {
    'user-manager'?: {
      status?: string;
      memory_events_since_cgroup_start?: MemoryEventCounts | null;
      pressure?: { memory?: PressureSample | null } | null;
    } | null;
  } | null;
};

const resourceBytes = (value: number | null | undefined) => {
  if (value == null || !Number.isFinite(value) || value < 0) return 'Not measured';
  if (value < 1024) return `${value} B`;
  const units = ['KiB', 'MiB', 'GiB', 'TiB'];
  let amount = value / 1024;
  let unit = 0;
  while (amount >= 1024 && unit < units.length - 1) {
    amount /= 1024;
    unit += 1;
  }
  return `${amount.toFixed(1)} ${units[unit]}`;
};

const resourcePressure = (value: number | null | undefined) =>
  value == null || !Number.isFinite(value) || value < 0 ? 'Not measured' : `${value.toFixed(2)}%`;

const resourceCount = (value: number | null | undefined) =>
  value == null || !Number.isSafeInteger(value) || value < 0
    ? 'Not measured'
    : value.toLocaleString('en-US');

const swapSummary = (memory: ResourceSnapshot['host_memory']) => {
  const total = memory?.swap_total_bytes;
  const free = memory?.swap_free_bytes;
  if (
    total == null ||
    free == null ||
    !Number.isFinite(total) ||
    !Number.isFinite(free) ||
    total < 0 ||
    free < 0 ||
    free > total
  ) {
    return 'Not measured';
  }
  if (total === 0) return free === 0 ? 'No swap configured' : 'Not measured';
  return `${resourceBytes(free)} free / ${resourceBytes(total)} total · ${(((total - free) / total) * 100).toFixed(1)}% used`;
};

export function FrontierHostResourcePanel() {
  const snapshot = useQuery({
    queryKey: ['frontier', 'host-resource-snapshot'],
    queryFn: () => api<ResourceSnapshot>('/readiness/resources'),
    staleTime: 10_000,
    retry: false,
  });
  const data = snapshot.data;
  const manager = data?.services?.['user-manager'];
  const managerSome = resourcePressure(manager?.pressure?.memory?.some?.avg10);
  const managerFull = resourcePressure(manager?.pressure?.memory?.full?.avg10);
  const managerEvents = manager?.memory_events_since_cgroup_start;
  const managerEventCounts = [
    managerEvents?.high,
    managerEvents?.max,
    managerEvents?.oom,
    managerEvents?.oom_kill,
    managerEvents?.oom_group_kill,
  ];
  const unavailableMetrics = data
    ? [
        swapSummary(data.host_memory) === 'Not measured' ? 'swap totals' : null,
        manager?.status !== 'MEASURED' ||
        managerSome === 'Not measured' ||
        managerFull === 'Not measured'
          ? 'user-manager memory PSI'
          : null,
        manager?.status !== 'MEASURED' ||
        managerEventCounts.some(
          (count) => count == null || !Number.isSafeInteger(count) || count < 0,
        )
          ? 'user-manager memory event counters'
          : null,
      ].filter((metric): metric is string => metric !== null)
    : [];

  return (
    <section className="fr-card" aria-labelledby="frontier-host-resource-title">
      <div className="fr-card-head">
        <div>
          <span className="fr-kicker">FRONTIER HOST TELEMETRY</span>
          <h2 id="frontier-host-resource-title">Host resource snapshot</h2>
        </div>
        <Activity size={17} />
      </div>
      {snapshot.isLoading ? (
        <div className="fr-loading">Reading bounded host resource counters…</div>
      ) : snapshot.isError ? (
        <div className="fr-host-resource-error" role="status">
          <AlertTriangle size={16} />
          <div>
            <strong>Host resource telemetry unavailable</strong>
            <span>{snapshot.error.message}</span>
          </div>
        </div>
      ) : data ? (
        <>
          <p className="fr-host-resource-captured">
            Captured {preciseUtcTime(data.captured_at_utc)}
          </p>
          <dl className="fr-host-resource-list">
            <div>
              <dt>RAM available / total</dt>
              <dd>
                {resourceBytes(data.host_memory?.available_bytes)} /{' '}
                {resourceBytes(data.host_memory?.total_bytes)}
              </dd>
            </div>
            <div>
              <dt>Swap free / total · utilization</dt>
              <dd>{swapSummary(data.host_memory)}</dd>
            </div>
            <div>
              <dt>Host memory PSI some / full avg10</dt>
              <dd>
                {resourcePressure(data.host_pressure?.memory?.some?.avg10)} /{' '}
                {resourcePressure(data.host_pressure?.memory?.full?.avg10)}
              </dd>
            </div>
            <div>
              <dt>User-manager memory PSI some / full avg10</dt>
              <dd>
                {manager?.status === 'MEASURED'
                  ? `${managerSome} / ${managerFull}`
                  : 'Not measured'}
              </dd>
            </div>
            <div>
              <dt>User-manager high / max / OOM / kill / group-kill counts</dt>
              <dd>{managerEventCounts.map(resourceCount).join(' / ')}</dd>
            </div>
          </dl>
          <p className="fr-host-resource-note">
            Point-in-time telemetry only; it does not establish sustained resource capacity. Swap
            occupancy alone is not a pressure diagnosis. User-manager event counts are cumulative
            since cgroup start, include descendants, and do not identify a workload; a max event
            does not necessarily mean an OOM kill occurred.
            {unavailableMetrics.length > 0 && (
              <>
                {' '}
                The connected API omitted {unavailableMetrics.join(' and ')}; these remain not
                measured.
              </>
            )}
          </p>
        </>
      ) : (
        <div className="fr-host-resource-error" role="status">
          <AlertTriangle size={16} />
          <div>
            <strong>Host resource telemetry unavailable</strong>
            <span>The readiness API returned no snapshot.</span>
          </div>
        </div>
      )}
    </section>
  );
}
