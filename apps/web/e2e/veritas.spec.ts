import { expect, test } from '@playwright/test';

test('shows the bounded discovery cohort and links its finalized evidence', async ({ page }) => {
  await page.route('**/api/arena/research-activity', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        status: 'available',
        state_source: 'persisted Arena manifests',
        active_job_count: 0,
        queued_job_count: 0,
        jobs: [],
        active_director_count: 0,
        directors: [
          {
            director_id: 'director-veritas-opportunity-v1',
            state: 'CURRENT',
            research_question: 'Do new finalized public snapshots contain candidates?',
            current_stage: 'Evidence is qualified',
            source_scan_id: 'scan-20261015T113126Z-bf24f3a0706b',
            strategy_readiness: 'NOT_READY_NO_QUALIFIED_GROSS_CANDIDATE',
            model_readiness: 'NOT_READY_NO_PUBLIC_OUTCOME_LABELS',
            recommendation: 'Keep no-trade; continue bounded collection.',
            latest_finding: null,
            recent_events: [
              {
                recorded_at_utc: '2026-10-15T11:20:56+00:00',
                state: 'FAILED',
                stage: 'Reviewing a failed qualification',
                note: 'The admitted job failed; automatic retry is disabled for this scan',
                scan_id: 'scan-20261015T110153Z-93de340dd5ce',
                job_id: 'job-source-drift',
                finding_id: null,
                experiment_run_id: null,
                experiment_sha256: null,
                dataset_sha256: null,
                source_revision_sha256: 'a'.repeat(64),
                strategy_readiness: 'NOT_READY_NO_QUALIFIED_GROSS_CANDIDATE',
                model_readiness: 'NOT_READY_NO_PUBLIC_OUTCOME_LABELS',
                positive_states_by_gate: null,
                recommendation: 'Wait for a new scan and stable source revision.',
              },
              {
                recorded_at_utc: '2026-10-15T11:46:11+00:00',
                state: 'QUALIFICATION_COMPLETED',
                stage: 'Published reproducible economic qualification',
                note: 'Qualification completed on the committed revision',
                scan_id: 'scan-20261015T113126Z-bf24f3a0706b',
                job_id: 'job-stable-revision',
                finding_id: 'veritas-qualification-v1-0e39c79c039a76cf',
                experiment_run_id: 'VERITAS-M2-ECO-QUAL-001-RUN-b3fc19f69680',
                experiment_sha256: 'b'.repeat(64),
                dataset_sha256: 'c'.repeat(64),
                source_revision_sha256: 'd'.repeat(64),
                strategy_readiness: 'NOT_READY_NO_QUALIFIED_GROSS_CANDIDATE',
                model_readiness: 'NOT_READY_NO_PUBLIC_OUTCOME_LABELS',
                positive_states_by_gate: { unchanged_top_ask_gross_sign: 0 },
                recommendation: 'Keep no-trade; continue bounded collection.',
              },
            ],
            recent_events_truncated: false,
          },
        ],
        active_schedule_count: 0,
        schedules: [],
        alerts: [],
        invalid_artifact_count: 0,
      }),
    }),
  );
  await page.goto('/');
  await page.getByRole('button', { name: 'Veritas', exact: true }).click();

  await expect(
    page.getByRole('heading', { level: 1, name: /Evidence before conviction/ }),
  ).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Market discovery and coverage' })).toBeVisible();
  await expect(page.getByText('stratified-gamma-page-rotation-v2')).toBeVisible();
  await expect(page.getByText(/40 target · 50 markets max/)).toBeVisible();
  await page.getByText(/Recent Director history/).click();
  await expect(page.getByText(/automatic retry is disabled for this scan/)).toBeVisible();
  await expect(page.getByText(/VERITAS-M2-ECO-QUAL-001-RUN-b3fc19f69680/)).toBeVisible();
  await expect(page.getByText(/veritas-qualification-v1-0e39c79c039a76cf/)).toBeVisible();
  await expect(page.getByLabel('Current collector limits')).toBeVisible();
  await expect(
    page.getByRole('button', { name: 'Run bounded qualification in Arena' }),
  ).toBeVisible();
  await page.getByText(/Inspect latest per-market selection probabilities/).click();
  await expect(page.getByText(/Inclusion probability/).first()).toBeVisible();
  await expect(
    page.getByRole('heading', { name: 'Opportunity observatory and data quality' }),
  ).toBeVisible();
  await expect(page.getByText(/0.000 events \/ panel hour/)).toBeVisible();
  const economicGateTable = page.getByRole('table', {
    name: 'Positive economic states by quantity and gate',
  });
  await expect(economicGateTable.getByRole('row', { name: '20 0 0 0 0' })).toBeVisible();
  await expect(
    page.getByText(/No quality-valid positive full-depth gross candidate has been recorded/),
  ).toBeVisible();
  await expect(page.getByText(/Latest read-only campaign snapshot/)).toBeVisible();

  const snapshotLink = page.getByRole('link', { name: /Inspect latest immutable snapshot/ });
  await expect(snapshotLink).toHaveAttribute(
    'href',
    /\/api\/veritas\/observatory\/snapshots\/scan-/,
  );
  const snapshotUrl = await snapshotLink.getAttribute('href');
  expect(snapshotUrl).toBeTruthy();
  const snapshotResponse = await page.request.get(snapshotUrl!);
  expect(snapshotResponse.ok()).toBeTruthy();
  const snapshot = await snapshotResponse.json();
  expect(snapshot.artifact).toBe('finalized_public_observation_snapshot');
  expect(snapshot.data.orders_submitted).toBe(false);

  const analysis = await page.request.get('/api/veritas/artifacts/continuous-analysis');
  expect(analysis.ok()).toBeTruthy();
  expect((await analysis.json()).data.analysis_version).toBe(
    'veritas-finalized-snapshot-analysis-v4',
  );

  const censoring = await page.request.get('/api/veritas/artifacts/censoring');
  expect(censoring.ok()).toBeTruthy();
  const censoringArtifact = await censoring.json();
  expect(censoringArtifact.data.analysis.analysis_version).toBe('veritas-forward-forensics-v1.3');
  expect(censoringArtifact.data.analysis.coverage.decisions).toBeGreaterThan(1_000);
  await page.getByText(/Inspect censoring by market and UTC hour/).click();
  await expect(page.getByText('future observation not recorded').first()).toBeVisible();

  await expect(page.getByText('Frozen campaign censor attribution')).toBeVisible();
  await expect(page.getByText(/179 → 97 verified gap records/)).toBeVisible();
  await expect(page.getByText(/160 → 60 later source records/)).toBeVisible();
  await expect(
    page.getByText(/direct causal link to the original gap was not verified/),
  ).toBeVisible();
  await expect(page.getByText('Frozen campaign gap attribution')).toBeVisible();
  await expect(page.getByRole('link', { name: 'Inspect attribution' })).toHaveAttribute(
    'href',
    '/api/veritas/artifacts/censor-gap-attribution',
  );
  await expect(page.getByText('Incremental finalized-source gap detail')).toBeVisible();
  await expect(page.getByRole('link', { name: 'Inspect source audit' })).toHaveAttribute(
    'href',
    '/api/veritas/artifacts/censor-gap-audit',
  );
  await expect(page.getByRole('link', { name: 'Inspect verified prefix' })).toHaveAttribute(
    'href',
    '/api/veritas/artifacts/gap-detail-current',
  );

  const attribution = await page.request.get('/api/veritas/artifacts/censor-gap-attribution');
  expect(attribution.ok()).toBeTruthy();
  const attributionArtifact = await attribution.json();
  expect(attributionArtifact.data.analysis_version).toBe('veritas-censor-gap-attribution-v1');
  expect(attributionArtifact.data.query.gap_censored_outcomes).toBe(339);
  expect(attributionArtifact.data.gap_censors.same_market_preceding_gap_is_causal_proof).toBe(
    false,
  );
});
