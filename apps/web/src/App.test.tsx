import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { App, money } from './App';
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
describe('application integrity', () => {
  it('does not manufacture absent financial metrics', () => {
    expect(money(null)).toBe('—');
    expect(money('0')).toBe('0.00');
  });
  it('reports backend failure and preserves the execution boundary', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <App />
      </QueryClientProvider>,
    );
    expect(screen.getAllByText(/SIMULATION ONLY/).length).toBeGreaterThan(0);
    expect(await screen.findByText(/API DISCONNECTED/)).toBeInTheDocument();
    expect(screen.getByText(/Backend connection unavailable/)).toBeInTheDocument();
  });

  it('opens Veritas as its own evidence workspace without a synthetic-data badge', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <App />
      </QueryClientProvider>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Veritas' }));

    expect(await screen.findByText('VERITAS · ECONOMIC EVIDENCE')).toBeInTheDocument();
    expect(
      await screen.findByText('Veritas evidence is unavailable.', {}, { timeout: 3000 }),
    ).toBeInTheDocument();
    expect(screen.queryByText('DEMO · SYNTHETIC')).not.toBeInTheDocument();
    expect(screen.queryByText('SYNTHETIC DATA')).not.toBeInTheDocument();
  });

  it('shows a readiness dashboard from service responses and keeps missing evidence unmeasured', async () => {
    const responses: Record<string, { status: number; body: unknown }> = {
      '/api/state': {
        status: 200,
        body: {
          status: 'READY',
          mode: 'demo',
          timestamp_ms: Date.now(),
          safety: { emergency_stop: false },
        },
      },
      '/api/health': {
        status: 200,
        body: {
          status: 'READY',
          mode: 'demo',
          live_execution: false,
          laboratory: { status: 'READY' },
        },
      },
      '/api/reality/overview': {
        status: 200,
        body: {
          health: 'degraded',
          capture_health: 'recording',
          collector: {
            sequence_state: 'unsequenced',
            implementation_sha256:
              '0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef',
            error: null,
            last_error: 'ConnectionClosedOK: previous server shutdown',
          },
          source_quality: { status: 'incomplete_observability' },
          integrity: { status: 'partial' },
          capacity: {},
        },
      },
      '/api/reality/operations': { status: 200, body: { services: [], storage_policy: {} } },
      '/api/veritas/overview': { status: 503, body: { detail: 'Veritas summary unavailable' } },
      '/api/veritas/artifacts/independent-opportunity-audit': {
        status: 200,
        body: {
          artifact: 'independent-opportunity-audit',
          file_sha256: 'abc123',
          data: { artifact_id: 'VERITAS-AUDIT-001', captured_at_utc: '2026-10-16T12:00:00Z' },
        },
      },
      '/api/arena/research-activity': {
        status: 200,
        body: {
          status: 'available',
          active_job_count: 0,
          queued_job_count: 0,
          stale_director_count: 3,
          unverified_director_count: 0,
          alerts: [{ alert_id: 'schedule-expired', state: 'OPEN' }],
        },
      },
      '/api/laboratory/catalog': { status: 200, body: { datasets: [] } },
    };
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const match = responses[String(input)];
        if (!match) throw new Error(`Unexpected request: ${String(input)}`);
        return {
          ok: match.status >= 200 && match.status < 300,
          status: match.status,
          statusText: 'Service unavailable',
          json: async () => match.body,
        } as Response;
      }),
    );
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <App />
      </QueryClientProvider>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Research Readiness' }));

    expect(await screen.findByRole('heading', { name: 'Research Readiness' })).toBeInTheDocument();
    expect(await screen.findByText('DEMO MODE IS ACTIVE')).toBeInTheDocument();
    expect(
      await screen.findByText(
        'The current Veritas overview is unavailable, so this funnel is unmeasured.',
      ),
    ).toBeInTheDocument();
    expect(screen.getByText('HISTORICAL')).toBeInTheDocument();
    expect(await screen.findByText(/3 stale directors/)).toBeInTheDocument();
    expect(screen.getByText(/1 alert/)).toBeInTheDocument();
    expect(screen.getByText('Current Reality collector error')).toBeInTheDocument();
    expect(screen.getByText(/timestamp not reported/)).toBeInTheDocument();
    expect(screen.getAllByText('sha256:0123456789ab')).toHaveLength(2);
    expect(screen.getByText(/Implementation SHA-256 0123456789abcdef/)).toBeInTheDocument();
    expect(screen.getAllByText('Not measured').length).toBeGreaterThan(0);
  });

  it('shows measured storage runway and distinguishes active from staged limits', async () => {
    const measuredNs = Date.now() * 1_000_000;
    const responses: Record<string, { status: number; body: unknown }> = {
      '/api/state': {
        status: 200,
        body: {
          status: 'READY',
          mode: 'demo',
          timestamp_ms: Date.now(),
          safety: { emergency_stop: false },
        },
      },
      '/api/health': {
        status: 200,
        body: {
          status: 'READY',
          api_version: '0.2.0',
          mode: 'demo',
          live_execution: false,
          laboratory: { status: 'READY' },
        },
      },
      '/api/reality/overview': {
        status: 200,
        body: {
          health: 'degraded',
          capture_health: 'recording',
          collector: { sequence_state: 'unsequenced' },
          source_quality: { status: 'incomplete_observability' },
          integrity: { status: 'partial', latest_boundary_verified: false },
          capacity: {
            measured_ns: measuredNs,
            estimated_storage_seconds_remaining: 1_394_445,
            retention_seconds_remaining: 6_773_127,
            compressed_bytes_per_second: 11_615,
            estimated_bytes_per_day: 1_003_536_000,
            filesystem_free_bytes: 163_500_000_000,
            sample: { segments: 120, seconds: 3_653 },
            alerts: ['ARCHIVE_SEGMENT_INVENTORY_INVALID', 'ARCHIVE_MANIFEST_PROVENANCE_INVALID'],
          },
        },
      },
      '/api/reality/operations': {
        status: 200,
        body: {
          services: [
            {
              unit: 'midas-reality.service',
              properties: {
                CPUUsageNSec: '1000000000',
                MemoryCurrent: '1000000',
                MemoryHigh: '2000000',
              },
            },
          ],
          recorder_resources: {
            status: 'measured',
            host_pressure: {
              cpu: { some: { avg10: '2.00' } },
              memory: { some: { avg10: '0.10' } },
              io: { full: { avg10: '0.00' } },
            },
          },
          configuration: { budget_bytes: 25_769_803_776, retention_days: 90 },
          storage_policy: {
            raw_budget_bytes: 120_259_084_288,
            retention_stop_days: 120,
            capacity_monitor_interval_seconds: 1800,
          },
        },
      },
      '/api/veritas/overview': {
        status: 200,
        body: {
          status: 'available',
          analysis_version: 'veritas-finalized-snapshot-analysis-v6',
          independent_economic_audit: {
            status: 'MEASURED',
            reference_pairs: 1,
            economic_supported_pairs: 0,
            disagreement_counts: {},
            reference_version: 'independent-economics-v2',
            source_version_current: true,
          },
          observation_funnel: {
            basis: 'fixture only',
            independent_trials: false,
            reference_version: 'independent-economics-v2',
            reference_version_current: true,
            bounded_frame_market_visits: 1,
            selected_market_observations: 1,
            observed_pair_observations: 1,
            quality_valid_pair_observations: 1,
            independent_snapshot_valid_pair_observations: 1,
            independent_economic_supported_pair_observations: 0,
            positive_gross_pair_observations: 0,
            net_economically_eligible_pair_observations: 0,
          },
        },
      },
      '/api/veritas/artifacts/independent-opportunity-audit': {
        status: 200,
        body: {
          artifact: 'independent-opportunity-audit',
          file_sha256: 'abc123',
          data: { artifact_id: 'VERITAS-AUDIT-001', captured_at_utc: '2026-10-16T12:00:00Z' },
        },
      },
      '/api/arena/research-activity': {
        status: 200,
        body: { status: 'available', active_job_count: 1, queued_job_count: 2 },
      },
      '/api/laboratory/catalog': { status: 200, body: { datasets: [] } },
    };
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const match = responses[String(input)];
        if (!match) throw new Error(`Unexpected request: ${String(input)}`);
        return {
          ok: match.status >= 200 && match.status < 300,
          status: match.status,
          statusText: 'Service unavailable',
          json: async () => match.body,
        } as Response;
      }),
    );
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <App />
      </QueryClientProvider>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Research Readiness' }));

    expect(await screen.findByText('16.1 days')).toBeInTheDocument();
    expect(screen.getByText('25,769,803,776 bytes / 90 days')).toBeInTheDocument();
    expect(screen.getByText('120,259,084,288 bytes / 120 days')).toBeInTheDocument();
    expect(
      screen.getByText('ARCHIVE_SEGMENT_INVENTORY_INVALID, ARCHIVE_MANIFEST_PROVENANCE_INVALID'),
    ).toBeInTheDocument();
    expect(screen.getByText('2.0%')).toBeInTheDocument();
  });
});
