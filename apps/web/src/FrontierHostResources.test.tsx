import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { FrontierHostResourcePanel } from './FrontierHostResources';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function renderPanel() {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <FrontierHostResourcePanel />
    </QueryClientProvider>,
  );
}

it('renders measured host and user-manager metrics as a point-in-time snapshot', async () => {
  const response = {
    captured_at_utc: '2026-10-29T17:15:00.000Z',
    host_memory: {
      total_bytes: 16 * 1024 ** 3,
      available_bytes: 10 * 1024 ** 3,
      swap_total_bytes: 4 * 1024 ** 3,
      swap_free_bytes: 16 * 1024 ** 2,
    },
    host_pressure: {
      memory: { some: { avg10: 0.23 }, full: { avg10: 0.02 } },
    },
    services: {
      'user-manager': {
        status: 'MEASURED',
        memory_events_since_cgroup_start: {
          high: 16_438_055,
          max: 731_783,
          oom: 19,
          oom_kill: 15,
          oom_group_kill: 0,
        },
        pressure: { memory: { some: { avg10: 0.7 }, full: { avg10: 0.2 } } },
      },
    },
  };
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    expect(String(input)).toBe('/api/readiness/resources');
    return { ok: true, json: async () => response } as Response;
  });
  vi.stubGlobal('fetch', fetchMock);

  renderPanel();

  expect(await screen.findByText('Captured 2026-10-29T17:15:00.000 UTC')).toBeInTheDocument();
  expect(screen.getByText('10.0 GiB / 16.0 GiB')).toBeInTheDocument();
  expect(screen.getByText('16.0 MiB free / 4.0 GiB total · 99.6% used')).toBeInTheDocument();
  expect(screen.getByText('0.23% / 0.02%')).toBeInTheDocument();
  expect(screen.getByText('0.70% / 0.20%')).toBeInTheDocument();
  expect(screen.getByText('16,438,055 / 731,783 / 19 / 15 / 0')).toBeInTheDocument();
  expect(
    screen.getByText(/event counts are cumulative since cgroup start, include descendants/),
  ).toBeInTheDocument();
  expect(
    screen.getByText(
      /Point-in-time telemetry only; it does not establish sustained resource capacity/,
    ),
  ).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledTimes(1);
});

it('does not infer swap or user-manager metrics omitted by the deployed API', async () => {
  const response = {
    captured_at_utc: '2026-10-29T17:33:23.830325+00:00',
    host_memory: {
      total_bytes: 16_665_567_232,
      available_bytes: 11_189_633_024,
    },
    host_pressure: {
      memory: { some: { avg10: 0 }, full: { avg10: 0 } },
    },
    services: { 'midas-api': { status: 'MEASURED' } },
  };
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({ ok: true, json: async () => response }) as Response),
  );

  renderPanel();

  expect(await screen.findByText('Captured 2026-10-29T17:33:23.830325 UTC')).toBeInTheDocument();
  expect(screen.getByText('10.4 GiB / 15.5 GiB')).toBeInTheDocument();
  expect(screen.getAllByText('Not measured')).toHaveLength(2);
  expect(
    screen.getByText(
      /The connected API omitted swap totals and user-manager memory PSI and user-manager memory event counters/,
    ),
  ).toBeInTheDocument();
});

it('shows a bounded degraded state when the readiness API is unavailable', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(
      async () =>
        ({
          ok: false,
          status: 503,
          statusText: 'Service Unavailable',
          json: async () => ({ detail: 'Resource snapshot is unavailable.' }),
        }) as Response,
    ),
  );

  renderPanel();

  expect(
    await screen.findByText('Host resource telemetry unavailable', {}, { timeout: 4000 }),
  ).toBeInTheDocument();
  expect(screen.getByText('Resource snapshot is unavailable.')).toBeInTheDocument();
});
