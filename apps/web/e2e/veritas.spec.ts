import { expect, test } from '@playwright/test';

test('separates historical Veritas audits from the unstarted live observatory', async ({
  page,
}) => {
  const browserErrors: string[] = [];
  page.on('pageerror', (error) => browserErrors.push(error.message));
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
  const health = await page.request.get('/api/health');
  expect(health.ok(), await health.text()).toBeTruthy();
  expect((await health.json()).startup_status).toBe('READY');
  const overview = await page.request.get('/api/veritas/overview');
  expect(overview.ok(), await overview.text()).toBeTruthy();
  const overviewData = await overview.json();
  const observatory = overviewData.opportunity_observatory;
  expect(observatory.processed_snapshot_count).toBe(0);
  expect(observatory.summary_artifact).toBeNull();
  expect(observatory.opportunity.quality_valid_pairs).toBeNull();
  expect(observatory.opportunity.positive_top_gross_pairs).toBeNull();
  expect(observatory.opportunity.candidate_event_count).toBeNull();
  expect(observatory.opportunity.positive_full_depth_gross_by_quantity).toBeNull();
  await page.getByRole('button', { name: 'Veritas', exact: true }).click();
  await expect(
    page.getByRole('heading', { level: 1, name: /Evidence before conviction/ }),
  ).toBeVisible();
  expect(browserErrors).toEqual([]);
  await expect(page.getByRole('heading', { name: 'Snapshot quality prediction' })).toBeVisible();
  await expect(page.getByText(/Held-out positive gross candidates: 0/)).toBeVisible();
  const qualityExperimentLink = page.getByRole('link', {
    name: /Inspect preregistration, split, metrics and source hashes/,
  });
  await expect(qualityExperimentLink).toHaveAttribute(
    'href',
    '/api/veritas/artifacts/market-quality-experiment',
  );
  const qualityExperimentResponse = await page.request.get(
    '/api/veritas/artifacts/market-quality-experiment',
  );
  expect(qualityExperimentResponse.ok()).toBeTruthy();
  const qualityExperiment = await qualityExperimentResponse.json();
  expect(qualityExperiment.data.experiment_id).toBe('VERITAS-M2-MARKET-QUALITY-PREDICTION-001');
  expect(qualityExperiment.data.model.not_deployed).toBe(true);
  expect(qualityExperiment.data.evaluation.positive_gross_candidates_in_held_out_markets).toBe(0);
  await expect(
    page.getByText('Historical independent opportunity audit', { exact: true }),
  ).toBeVisible();
  await expect(page.getByText(/84 scans · 3,360 selected observations/)).toBeVisible();
  const independentAuditLink = page.getByRole('link', { name: 'Inspect replay' });
  await expect(independentAuditLink).toHaveAttribute(
    'href',
    '/api/veritas/artifacts/independent-opportunity-audit',
  );
  const independentAuditResponse = await page.request.get(
    '/api/veritas/artifacts/independent-opportunity-audit',
  );
  expect(independentAuditResponse.ok()).toBeTruthy();
  const independentAudit = await independentAuditResponse.json();
  expect(independentAudit.data.snapshot_count).toBe(84);
  expect(independentAudit.data.independent_fee_disagreement_count).toBe(0);
  await expect(page.getByRole('heading', { name: 'Market discovery and coverage' })).toBeVisible();
  await expect(page.getByText('BOUNDED PUBLIC DISCOVERY · NOT STARTED')).toBeVisible();
  await expect(page.getByText('No finalized public snapshot has been indexed yet.')).toBeVisible();
  await expect(page.getByText('NOT MEASURED', { exact: true }).first()).toBeVisible();
  await expect(
    page.getByText(
      'No finalized public snapshot is indexed, so opportunity counts have not been measured.',
    ),
  ).toBeVisible();
  const universeCoverage = observatory.market_universe_coverage;
  expect(universeCoverage.status).toBe('available');
  const universeAudit = page.getByLabel('Saved market-universe coverage audit');
  await expect(universeAudit.getByText('HISTORICAL · HASH VERIFIED')).toBeVisible();
  await expect(universeAudit.getByText(/58 scans/)).toBeVisible();
  const universeAuditResponse = await page.request.get(
    '/api/veritas/artifacts/market-universe-coverage',
  );
  expect(universeAuditResponse.ok()).toBeTruthy();
  const universeAuditArtifact = await universeAuditResponse.json();
  expect(universeAuditArtifact.file_sha256).toBe(universeCoverage.artifact.file_sha256);
  expect(universeAuditArtifact.data.analysis_version).toBe(universeCoverage.analysis_version);
  expect(universeCoverage.source_hashes_verified).toBe(true);
  expect(universeAuditArtifact.data.source.snapshot_evidence_hashes_verified).toBe(true);

  const coverageDesign = observatory.coverage_design_audit;
  expect(coverageDesign.status).toBe('available');
  const coverageDesignCard = page.getByTestId('coverage-design-audit');
  await expect(coverageDesignCard).toBeVisible();
  await expect(coverageDesignCard.getByText('Historical inclusion-support audit')).toBeVisible();
  await expect(
    coverageDesignCard.getByText(
      `Audited ${coverageDesign.study_scan_count} scans · pilot now at ${coverageDesign.current_pilot_scan_count}`,
    ),
  ).toBeVisible();
  const coverageAuditResponse = await page.request.get(
    '/api/veritas/artifacts/coverage-design-audit',
  );
  expect(coverageAuditResponse.ok()).toBeTruthy();
  const coverageAuditArtifact = await coverageAuditResponse.json();
  expect(coverageAuditArtifact.file_sha256).toBe(coverageDesign.artifact.file_sha256);
  expect(coverageAuditArtifact.data.analysis_version).toBe(coverageDesign.analysis_version);
  expect(coverageAuditArtifact.data.source.event_count).toBe(coverageDesign.study_scan_count);
  expect(coverageAuditArtifact.data.interpretation.no_venue_wide_inference).toBe(true);

  await page.getByText(/Recent Director history/).click();
  await expect(page.getByText(/automatic retry is disabled for this scan/)).toBeVisible();
  await expect(page.getByText(/VERITAS-M2-ECO-QUAL-001-RUN-b3fc19f69680/)).toBeVisible();
  await expect(page.getByText(/veritas-qualification-v1-0e39c79c039a76cf/)).toBeVisible();
  await expect(
    page.getByRole('button', { name: 'Run bounded qualification in Arena' }),
  ).toBeDisabled();
  await expect(
    page.getByRole('heading', { name: 'Opportunity observatory and data quality' }),
  ).toBeVisible();
  await expect(page.getByText('Not measured', { exact: true }).first()).toBeVisible();
  const economicGateTable = page.getByRole('table', {
    name: 'Positive economic states by quantity and gate',
  });
  await expect(economicGateTable.getByRole('row', { name: /Not measured/ })).toBeVisible();
  await expect(page.getByText('Not measured', { exact: true }).nth(2)).toBeVisible();
  await expect(page.getByText(/Latest read-only campaign snapshot/)).toBeVisible();

  expect(
    overviewData.artifacts.some(
      (artifact: { id: string }) => artifact.id === 'continuous-analysis',
    ),
  ).toBe(false);
  const analysis = await page.request.get('/api/veritas/artifacts/continuous-analysis');
  expect(analysis.status()).toBe(404);
  await expect(page.getByRole('link', { name: /Inspect latest immutable snapshot/ })).toHaveCount(
    0,
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
  if (overviewData.finalized_gap_detail) {
    await expect(page.getByText('Incremental finalized-source gap detail')).toBeVisible();
    await expect(page.getByRole('link', { name: 'Inspect source audit' })).toHaveAttribute(
      'href',
      '/api/veritas/artifacts/censor-gap-audit',
    );
    await expect(page.getByRole('link', { name: 'Inspect verified prefix' })).toHaveAttribute(
      'href',
      '/api/veritas/artifacts/gap-detail-current',
    );
  } else {
    await expect(page.getByRole('link', { name: 'Inspect verified prefix' })).toHaveCount(0);
    const gapDetail = await page.request.get('/api/veritas/artifacts/gap-detail-current');
    expect(gapDetail.status()).toBe(404);
  }

  const attribution = await page.request.get('/api/veritas/artifacts/censor-gap-attribution');
  expect(attribution.ok()).toBeTruthy();
  const attributionArtifact = await attribution.json();
  expect(attributionArtifact.data.analysis_version).toBe('veritas-censor-gap-attribution-v1');
  expect(attributionArtifact.data.query.gap_censored_outcomes).toBe(339);
  expect(attributionArtifact.data.gap_censors.same_market_preceding_gap_is_causal_proof).toBe(
    false,
  );
});
