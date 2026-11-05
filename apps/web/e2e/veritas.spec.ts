import { expect, test } from '@playwright/test';

type VeritasOverview = {
  finalized_gap_detail: Record<string, unknown> | null;
  opportunity_observatory: {
    analysis_version: string | null;
    measurement_status: string;
    processed_snapshot_count: number;
    discovery: {
      latest_by_category: Record<string, number>;
      latest_selected_market_rows: unknown[];
      latest_snapshot_url: string | null;
      latest_scan_id: string | null;
      collection_bounds: Record<string, unknown> | null;
    };
    opportunity: {
      quality_valid_pairs: number | null;
      positive_full_depth_gross_by_quantity: Record<string, number> | null;
    };
    recent_candidates: unknown[];
  };
};

test('shows historical evidence and matches current observatory labels to its data', async ({
  page,
}) => {
  page.on('pageerror', (error) =>
    console.error(`[veritas pageerror] ${error.stack ?? error.message}`),
  );
  const latestScanId = 'scan-20261104T000000Z-abcdef123456';
  const latestSnapshotUrl = `/api/veritas/observatory/snapshots/${latestScanId}`;
  await page.route('**/api/veritas/overview', async (route) => {
    const response = await route.fetch();
    const body = (await response.json()) as VeritasOverview;
    const observatory = body.opportunity_observatory;
    observatory.measurement_status = 'MEASURED';
    observatory.processed_snapshot_count = Math.max(1, observatory.processed_snapshot_count);
    Object.assign(observatory.discovery, {
      latest_scan_id: latestScanId,
      latest_snapshot_url: latestSnapshotUrl,
      latest_by_category: { Technology: 1 },
      latest_selected_market_rows: [
        {
          market_id: 'phase3-selection-probability-market',
          primary_category: 'Technology',
          primary_category_source: 'market.category',
          cohort_role: 'rotating_stratified',
          selection_probability: '1/40',
          selection_probability_basis: 'bounded_query_union',
          selection_stratum: 'high_liquidity',
        },
      ],
      collection_bounds: { target_markets: 40, maximum_markets: 50 },
    });
    await route.fulfill({
      status: response.status(),
      contentType: 'application/json',
      body: JSON.stringify(body),
    });
  });
  await page.route(latestSnapshotUrl, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        artifact: 'finalized_public_observation_snapshot',
        data: { scan_id: latestScanId, orders_submitted: false },
      }),
    }),
  );
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
  const overviewResponse = await page.evaluate(async () => {
    const response = await fetch('/api/veritas/overview');
    return { ok: response.ok, body: await response.json() };
  });
  expect(overviewResponse.ok).toBeTruthy();
  const overview = overviewResponse.body as VeritasOverview;
  const observatory = overview.opportunity_observatory;
  const opportunityMeasured =
    observatory.measurement_status === 'MEASURED' ||
    typeof observatory.opportunity.quality_valid_pairs === 'number';
  const economicGateQuantities = Object.keys(
    observatory.opportunity.positive_full_depth_gross_by_quantity ?? {},
  );
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
  await expect(page.getByText('Independent opportunity audit', { exact: true })).toBeVisible();
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
  if (Object.keys(observatory.discovery.latest_by_category).length === 0) {
    await expect(
      page.getByText('No finalized public snapshot has been indexed yet.'),
    ).toBeVisible();
  } else {
    await expect(page.getByText('No finalized public snapshot has been indexed yet.')).toHaveCount(
      0,
    );
  }
  await expect(page.getByLabel('Current collector limits')).toHaveCount(1);
  const selectionProbabilityDetails = page.getByText(
    /Inspect latest per-market selection probabilities/,
  );
  await expect(selectionProbabilityDetails).toHaveCount(1);
  await selectionProbabilityDetails.click();
  await expect(page.getByText(/Inclusion probability 1\/40/)).toBeVisible();
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
  if (!opportunityMeasured) {
    await expect(
      page.getByText(
        'No finalized public snapshot has been analyzed; candidate presence is not measured.',
      ),
    ).toBeVisible();
  } else if (observatory.recent_candidates.length === 0) {
    await expect(
      page.getByText(
        'No quality-valid positive full-depth gross candidate has been recorded in the analyzed snapshots.',
      ),
    ).toBeVisible();
  }
  const economicGateTable = page.getByRole('table', {
    name: 'Positive economic states by quantity and gate',
  });
  if (!opportunityMeasured) {
    await expect(
      economicGateTable.getByRole('row', {
        name: /Not measured — awaiting the first finalized snapshot/,
      }),
    ).toBeVisible();
    await expect(page.getByText(/candidate presence is not measured/).last()).toBeVisible();
  } else if (economicGateQuantities.length === 0) {
    await expect(
      economicGateTable.getByRole('row', {
        name: /No economic-gate rows are available in this measured summary/,
      }),
    ).toBeVisible();
  } else {
    await expect(economicGateTable.getByRole('row').nth(1)).toBeVisible();
  }
  await expect(page.getByText(/Latest read-only campaign snapshot/)).toBeVisible();

  const coverageDesignAudit = page.getByTestId('coverage-design-audit');
  await expect(coverageDesignAudit).toBeVisible();
  await expect(coverageDesignAudit.getByText(/Audited 25 scans · pilot now at \d+/)).toBeVisible();
  await expect(coverageDesignAudit.getByText('99.80%')).toBeVisible();
  await expect(coverageDesignAudit.getByText('82.96%')).toBeVisible();
  await expect(coverageDesignAudit.getByText(/bounded query union/)).toBeVisible();
  const coverageAuditLink = coverageDesignAudit.getByRole('link', { name: 'Inspect audit' });
  await expect(coverageAuditLink).toHaveAttribute(
    'href',
    '/api/veritas/artifacts/coverage-design-audit',
  );
  const coverageAuditResponse = await page.request.get(
    '/api/veritas/artifacts/coverage-design-audit',
  );
  expect(coverageAuditResponse.ok()).toBeTruthy();
  const coverageAuditArtifact = await coverageAuditResponse.json();
  expect(coverageAuditArtifact.artifact).toBe('coverage-design-audit');
  expect(coverageAuditArtifact.data.analysis_version).toBe('veritas-coverage-design-audit-v2');
  expect(coverageAuditArtifact.data.source.event_count).toBe(25);
  expect(coverageAuditArtifact.data.analysis.fully_supported_scan_count).toBe(23);
  expect(coverageAuditArtifact.data.interpretation.no_venue_wide_inference).toBe(true);

  const snapshotLink = page.getByRole('link', { name: /Inspect latest immutable snapshot/ });
  await expect(snapshotLink).toHaveCount(1);
  await expect(snapshotLink).toHaveAttribute('href', latestSnapshotUrl);
  const snapshotResponse = await page.evaluate(async (url) => {
    const response = await fetch(url);
    return { ok: response.ok, body: await response.json() };
  }, latestSnapshotUrl);
  expect(snapshotResponse.ok).toBeTruthy();
  expect(snapshotResponse.body.artifact).toBe('finalized_public_observation_snapshot');
  expect(snapshotResponse.body.data.scan_id).toBe(latestScanId);
  expect(snapshotResponse.body.data.orders_submitted).toBe(false);

  const analysis = await page.request.get('/api/veritas/artifacts/continuous-analysis');
  if (observatory.analysis_version) {
    expect(analysis.status()).toBe(200);
    expect((await analysis.json()).data.analysis_version).toBe(observatory.analysis_version);
  } else {
    expect(analysis.status()).toBe(404);
    expect((await analysis.json()).detail).toBe(
      'Veritas public observatory analysis has not been generated',
    );
  }

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
  if (overview.finalized_gap_detail) {
    await expect(page.getByText('Not available in the current workspace')).toHaveCount(0);
    await expect(page.getByRole('link', { name: 'Inspect verified prefix' })).toHaveAttribute(
      'href',
      '/api/veritas/artifacts/gap-detail-current',
    );
  } else {
    await expect(page.getByText('Not available in the current workspace')).toBeVisible();
    await expect(page.getByRole('link', { name: 'Inspect verified prefix' })).toHaveCount(0);
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

test('shows explicit not-measured state when no finalized snapshots exist', async ({ page }) => {
  await page.route('**/api/veritas/overview', async (route) => {
    const response = await route.fetch();
    const body = (await response.json()) as VeritasOverview;
    const observatory = body.opportunity_observatory;
    observatory.measurement_status = 'NOT_MEASURED';
    observatory.processed_snapshot_count = 0;
    observatory.discovery.latest_by_category = {};
    observatory.discovery.latest_selected_market_rows = [];
    observatory.discovery.latest_snapshot_url = null;
    observatory.discovery.latest_scan_id = null;
    observatory.discovery.collection_bounds = null;
    observatory.opportunity.quality_valid_pairs = null;
    observatory.opportunity.positive_full_depth_gross_by_quantity = null;
    observatory.recent_candidates = [];
    await route.fulfill({
      status: response.status(),
      contentType: 'application/json',
      body: JSON.stringify(body),
    });
  });
  await page.goto('/');
  await page.getByRole('button', { name: 'Veritas', exact: true }).click();

  await expect(page.getByText('No finalized public snapshot has been indexed yet.')).toBeVisible();
  await expect(
    page.getByText(
      'No finalized public snapshot has been analyzed; candidate presence is not measured.',
    ),
  ).toBeVisible();
  await expect(
    page.getByRole('row', { name: /Not measured — awaiting the first finalized snapshot/ }),
  ).toBeVisible();
  await expect(page.getByRole('link', { name: /Inspect latest immutable snapshot/ })).toHaveCount(
    0,
  );
  await expect(page.getByText(/Inspect latest per-market selection probabilities/)).toHaveCount(0);
});
