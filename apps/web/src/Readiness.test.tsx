import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Readiness } from './Readiness';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function renderReadiness() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <Readiness />
    </QueryClientProvider>,
  );
}

it('announces evidence loading without treating missing responses as measured', async () => {
  const pending = new Promise<Response>(() => {});
  vi.stubGlobal(
    'fetch',
    vi.fn(() => pending),
  );
  renderReadiness();

  const loading = await screen.findByText(/Loading evidence from 7 sources/);
  expect(loading.closest('[role="status"]')).toHaveAttribute('aria-live', 'polite');
  expect(
    screen.getByText('0 of 6 gates currently pass. Missing evidence never counts as a pass.'),
  ).toBeInTheDocument();
  const gate = screen
    .getByRole('heading', { name: 'Independent research correctness' })
    .closest('.rr-gate');
  expect(gate).toHaveTextContent('NOT MEASURED');
  expect(gate).not.toHaveTextContent('PASS');
});

it('shows measured zero-candidate evidence without turning it into a profitability claim', async () => {
  const now = Date.now();
  const replies: Record<string, unknown> = {
    '/health': {
      status: 'READY',
      startup_status: 'READY',
      mode: 'demo',
      application_version: '0.2.0',
      api_release_identity: 'e988cbb',
      integrated_source_revision: 'e988cbb',
      checked_at_utc: new Date(now).toISOString(),
      laboratory: { status: 'READY' },
    },
    '/state': { mode: 'demo', telemetry: { queue_depth: 1 }, timestamp_ms: now },
    '/reality/overview': {
      now_ns: now * 1_000_000,
      health: 'recording',
      collector_status_age_seconds: 2,
      collector: {
        state: 'RECORDING_UNSEQUENCED',
        updated_ns: now * 1_000_000,
        last_observation_ns: now * 1_000_000,
        schema_version: 'reality-observation-v4',
        error: null,
        last_error: 'ConnectionClosedOK: prior process shutdown',
        last_error_ns: (now - 60_000) * 1_000_000,
        transport_message_age_seconds: 0.7,
        market_event_age_seconds: 12.2,
        stale_book_count: 3,
        transport_queue_bound: 32,
        transport_queue_observation_available: false,
        transport_queue_depth: null,
        transport_queue_saturated: false,
      },
      source_quality: {
        status: 'incomplete_observability',
        sequence_state: 'unsequenced',
        observability_gaps: [
          'recent_persistence_window_incomplete',
          'recovery_state_unreported',
          'transport_queue_depth_unreported',
        ],
      },
      integrity: { status: 'verified' },
      capacity: {
        freshness: {
          state: 'stale',
          measured_ns: (now - 2 * 60 * 60 * 1000) * 1_000_000,
          age_seconds: 7200,
          stale_after_seconds: 3600,
        },
        status: 'measured',
        budget_bytes: 24 * 1024 ** 3,
        effective_capacity_runway_days: 16.5,
        short_window_capacity_runway_days: 12.5,
        configured_capacity_runway_days: 108.2,
        configured_budget_bytes: 112 * 1024 ** 3,
        configured_retention_days: 120,
        budget_change_pending_restart: true,
        retention_change_pending_restart: true,
        alerts: ['SHORT_WINDOW_CAPACITY_CRITICAL_WITHIN_FOURTEEN_DAYS'],
        free_bytes: 100_000_000,
      },
    },
    '/veritas/overview': {
      opportunity_observatory: {
        status: 'recording',
        analysis_version: 'veritas-finalized-snapshot-analysis-v6',
        processed_snapshot_count: 5,
        pending_snapshot_count: 0,
        updated_at_utc: new Date(now).toISOString(),
        last_captured_at_utc: new Date(now).toISOString(),
        discovery: {
          unique_market_ids_observed: 4,
          latest_unique_market_ids: 3,
          latest_query_candidate_records: 6,
          latest_stable_control_markets: 2,
          latest_rotating_markets: 4,
          latest_scan_id: 'scan-20261026T000000Z-123456789abc',
        },
        independent_economic_audit: {
          status: 'MEASURED',
          source_version_current: true,
          reference_version: 'decimal-reference-v6',
          reference_pairs: 12,
          economic_supported_pairs: 4,
          net_eligible_pairs: 0,
          positive_gross_pair_observations: 2,
          disagreement_counts: { validity: 0, 'gross:5': 0, 'fee_reference:5': 0 },
        },
        observation_funnel: {
          reference_version_current: true,
          selected_market_observations: 16,
          bounded_query_frame_market_visits: 16,
          observed_pair_observations: 12,
          quality_valid_pair_observations: 10,
          independently_verified_pair_observations: 10,
          positive_gross_pair_observations: 2,
          net_economically_eligible_pair_observations: 0,
        },
        summary_artifact: { file_sha256: 'a'.repeat(64) },
      },
      finalized_reality_source: {
        analysis_version: 'finalized-source-v1',
        processed_segment_count: 8,
        catalog_segment_count: 8,
        pending_segment_count: 0,
        pending_source_bytes: 0,
        last_processed_ordinal: 8,
        summary_artifact: {
          file_sha256: 'b'.repeat(64),
          url: '/api/veritas/artifacts/finalized-source-analysis',
        },
      },
    },
    '/arena/research-activity': {
      jobs: [],
      active_job_count: 0,
      stale_director_count: 0,
      state_source: 'persisted Arena manifests',
    },
    '/laboratory/campaigns': [],
    '/readiness/resources': {
      captured_at_utc: new Date(now).toISOString(),
      sampling: 'bounded procfs, cgroup-v2 and statvfs reads',
      host_memory: {
        total_bytes: 16_000_000_000,
        available_bytes: 7_000_000_000,
        swap_total_bytes: 8 * 1024 ** 3,
        swap_free_bytes: 2 * 1024 ** 3,
      },
      host_pressure: {
        cpu: { some: { avg10: 0.2 } },
        memory: { some: { avg10: 0.1 } },
        io: { full: { avg10: 0.3 } },
      },
      services: {
        'midas-api': {
          status: 'MEASURED',
          memory_current_bytes: 950_000_000,
          memory_high_bytes: 1_000_000_000,
          memory_max_bytes: 1_100_000_000,
          memory_composition_bytes: { anon: 256 * 1024 ** 2, file: 512 * 1024 ** 2 },
        },
        'midas-reality': {
          status: 'MEASURED',
          memory_current_bytes: 1_150_000_000,
          memory_high_bytes: 1_200_000_000,
          memory_composition_bytes: { anon: 384 * 1024 ** 2, file: 640 * 1024 ** 2 },
          memory_events_since_cgroup_start: { high: 2, max: 0, oom: 0, oom_kill: 0 },
          sample_delta: { cpu_quota_utilization_percent: 25, cpu_throttled_delta_usec: 0 },
        },
        'midas-veritas-observatory': { status: 'NOT_MEASURED' },
        'user-manager': {
          status: 'MEASURED',
          memory_current_bytes: 9 * 1024 ** 3,
          memory_events_since_cgroup_start: {
            high: 16_417_339,
            max: 730_045,
            oom: 19,
            oom_kill: 15,
            oom_group_kill: 0,
          },
          pressure: {
            memory: { some: { avg10: 0.5 }, full: { avg10: 0.1 } },
          },
        },
      },
      reality_recording_filesystem: {
        status: 'MEASURED',
        available_bytes: 100_000_000_000,
        total_bytes: 500_000_000_000,
      },
      observer_last_run: {
        status: 'MEASURED',
        result: 'success',
        exit_status: 0,
        memory_peak_bytes: 268_435_456,
        memory_max_bytes: 268_435_456,
        release_identity: 'e988cbb',
        execution_finished_at: new Date(now).toISOString(),
      },
      reality_service: { status: 'MEASURED', source_root_label: 'midas-reality' },
      staged_reality_candidate: {
        status: 'MEASURED',
        commit: '4278b5b5e66823e41a5d949b7b7c2e007c5b4ed0',
        branch: 'fix/reality-foundation-20261020',
        tracked_reality_source_changes: 2,
        tracked_reality_source_dirty: true,
      },
    },
  };
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation((input: RequestInfo | URL) => {
      const key = String(input).replace('/api', '');
      return Promise.resolve({ ok: true, json: async () => replies[key] });
    }),
  );

  renderReadiness();

  expect(await screen.findByText('Research Readiness')).toBeInTheDocument();
  expect(
    await screen.findByText(
      'No net-eligible candidates in the measured cohort; this is an informative result, not profitability evidence.',
    ),
  ).toBeInTheDocument();
  expect(screen.getByText('0 / 12')).toBeInTheDocument();
  expect(screen.getByText('2.0 GiB / 8.0 GiB free (75.0% used)')).toBeInTheDocument();
  expect(
    screen.getByText(
      /Swap occupancy is shown as context and does not independently determine admission/,
    ),
  ).toBeInTheDocument();
  expect(screen.getByText(/Full latest-boundary verification is not reported/)).toBeInTheDocument();
  expect(screen.getByText(/Cold recovery boundary: not verified/)).toBeInTheDocument();
  expect(
    screen.getByRole('heading', { name: 'Recovery and reproducibility' }).closest('.rr-gate'),
  ).toHaveTextContent('BLOCKED');
  expect(
    screen.getByRole('heading', { name: 'Independent research correctness' }).closest('.rr-gate'),
  ).toHaveTextContent('0 disagreement flags');
  expect(
    screen.getByRole('heading', { name: 'Resource and scheduling stability' }).closest('.rr-gate'),
  ).toHaveTextContent('BLOCKED');
  expect(screen.getByText(/None reported by the current status projection/)).toBeInTheDocument();
  expect(screen.getByText(/prior process shutdown/)).toBeInTheDocument();
  expect(
    screen.getByText(/WebSocket message 0.7s ago · market event 12.2s ago · stale books 3/),
  ).toBeInTheDocument();
  expect(screen.getByText(/Not reported \(bound 32 frames\)/)).toBeInTheDocument();
  expect(
    screen.getByText(
      /durable-write lag · recovery and replay state · transport queue depth \(bound 32 frames\)/,
    ),
  ).toBeInTheDocument();
  expect(screen.getByText(/Reality is at or above 95% of MemoryHigh/)).toBeInTheDocument();
  expect(
    screen.getByText(/Mission Control API is at or above 95% of MemoryHigh/),
  ).toBeInTheDocument();
  const storageGate = screen
    .getByRole('heading', { name: 'Storage sustainability' })
    .closest('.rr-gate');
  expect(storageGate).toHaveTextContent('STALE');
  expect(storageGate).toHaveTextContent('last recorded estimate and is not current');
  expect(storageGate).toHaveTextContent('Last measured runway 16.5 days');
  expect(screen.getByText(/112\.0 GiB \/ 120 days · pending restart/)).toBeInTheDocument();
  expect(screen.getByText(/108\.2 days · not active/)).toBeInTheDocument();
  expect(screen.getByText(/No live order execution/)).toBeInTheDocument();
  expect(screen.getByText(/DEMO MODE · NO LIVE ORDERS/)).toBeInTheDocument();
  expect(screen.getAllByText('e988cbb').length).toBeGreaterThan(0);
  expect(screen.getByText(/2 tracked source changes · dirty · not deployed/)).toBeInTheDocument();
  expect(screen.getAllByText('Anonymous / file-backed charge')).toHaveLength(2);
  const userManager = screen
    .getByRole('heading', { name: 'User-manager cgroup (systemd-oomd)' })
    .closest('section');
  expect(userManager).toHaveTextContent('9.0 GiB');
  expect(userManager).toHaveTextContent('0.5% / 0.1%');
  expect(userManager).toHaveTextContent('19 / 15 / 0');
  expect(screen.getByText('256.0 MiB / 512.0 MiB')).toBeInTheDocument();
  expect(
    screen.getByText(/File-backed charge may be reclaimable but still counts toward MemoryHigh/),
  ).toBeInTheDocument();
  expect(screen.getAllByText(/256\.0 MiB/).length).toBeGreaterThan(0);
});

it('does not pass gates when the evidence APIs fail', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
  renderReadiness();

  expect(await screen.findByRole('alert', {}, { timeout: 5000 })).toHaveTextContent(
    /could not be read/,
  );
  expect(screen.getAllByText('BLOCKED').length).toBeGreaterThan(0);
  expect(screen.getByText(/Missing evidence never counts as a pass/)).toBeInTheDocument();
});

it('does not pass independent correctness when the audited-pair denominator is missing', async () => {
  const now = Date.now();
  const replies: Record<string, unknown> = {
    '/health': {
      status: 'READY',
      startup_status: 'READY',
      mode: 'demo',
      checked_at_utc: new Date(now).toISOString(),
      laboratory: { status: 'READY' },
    },
    '/state': { mode: 'demo', telemetry: { queue_depth: 0 } },
    '/reality/overview': {
      health: 'recording',
      collector_status_age_seconds: 1,
      collector: { state: 'RECORDING_UNSEQUENCED' },
      source_quality: { status: 'measured', sequence_state: 'unsequenced' },
      capacity: {},
    },
    '/veritas/overview': {
      opportunity_observatory: {
        status: 'recording',
        analysis_version: 'veritas-finalized-snapshot-analysis-v6',
        processed_snapshot_count: 5,
        pending_snapshot_count: 0,
        updated_at_utc: new Date(now).toISOString(),
        discovery: {},
        independent_economic_audit: {
          status: 'MEASURED',
          source_version_current: true,
          reference_version: 'decimal-reference-v6',
          reference_pairs: null,
          disagreement_counts: {},
        },
        observation_funnel: { reference_version_current: true },
      },
      finalized_reality_source: {},
    },
    '/arena/research-activity': {
      jobs: [],
      active_job_count: 0,
      stale_director_count: 0,
      state_source: 'persisted Arena manifests',
    },
    '/laboratory/campaigns': [],
    '/readiness/resources': {
      captured_at_utc: new Date(now).toISOString(),
      host_memory: { total_bytes: 1_000_000_000, available_bytes: 500_000_000 },
      services: {
        'midas-api': { status: 'MEASURED' },
        'midas-reality': { status: 'MEASURED', memory_current_bytes: 0, memory_high_bytes: 100 },
      },
      reality_recording_filesystem: { status: 'MEASURED', available_bytes: 100_000_000 },
    },
  };
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation((input: RequestInfo | URL) => {
      const key = String(input).replace('/api', '');
      return Promise.resolve({ ok: true, json: async () => replies[key] });
    }),
  );

  renderReadiness();

  await screen.findByText('Research Readiness');
  const gate = screen
    .getByRole('heading', { name: 'Independent research correctness' })
    .closest('.rr-gate');
  expect(gate).toHaveTextContent('NOT MEASURED');
  expect(gate).not.toHaveTextContent('PASS');
});
