import { expect, test } from '@playwright/test';

test('Research Readiness labels demo and historical evidence while keeping unavailable counts unmeasured', async ({
  page,
}) => {
  const measuredNs = Date.now() * 1_000_000;
  const responses: Record<string, { status: number; body: unknown }> = {
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
        collector: {
          sequence_state: 'unsequenced',
          implementation_sha256: '0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef',
          error: null,
          last_error: 'ConnectionClosedOK: previous server shutdown',
        },
        source_quality: { status: 'incomplete_observability' },
        integrity: { status: 'partial' },
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
  await page.route('**/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    const response = responses[path];
    if (!response) {
      await route.continue();
      return;
    }
    await route.fulfill({
      status: response.status,
      contentType: 'application/json',
      body: JSON.stringify(response.body),
    });
  });

  await page.goto('/');
  const readinessNavigation = page.getByRole('button', { name: 'Research Readiness', exact: true });
  await expect(readinessNavigation).toBeVisible();
  await readinessNavigation.click({ force: true });

  await expect(
    page.getByRole('heading', { name: 'Research Readiness', exact: true }),
  ).toBeVisible();
  await expect(page.getByText('DEMO MODE IS ACTIVE')).toBeVisible();
  await expect(page.getByText('HISTORICAL', { exact: true })).toBeVisible();
  await expect(page.getByText('16.1 days', { exact: true })).toBeVisible();
  await expect(page.getByText(/3 stale directors/)).toBeVisible();
  await expect(page.getByText(/1 alert/)).toBeVisible();
  await expect(page.getByText('25,769,803,776 bytes / 90 days')).toBeVisible();
  await expect(page.getByText('120,259,084,288 bytes / 120 days')).toBeVisible();
  await expect(page.getByText('Current Reality collector error')).toBeVisible();
  await expect(page.getByText(/timestamp not reported/)).toBeVisible();
  await expect(page.getByText('sha256:0123456789ab', { exact: true }).first()).toBeVisible();
  await expect(
    page.getByText('ARCHIVE_SEGMENT_INVENTORY_INVALID, ARCHIVE_MANIFEST_PROVENANCE_INVALID'),
  ).toBeVisible();
  await expect(
    page.getByText('The current Veritas overview is unavailable, so this funnel is unmeasured.'),
  ).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Evidence-based readiness gates' })).toBeVisible();

  await page.screenshot({ path: test.info().outputPath('research-readiness.png'), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    page.getByRole('heading', { name: 'Research Readiness', exact: true }),
  ).toBeVisible();
});
