// Deployed acceptance: inspect saved evidence and validate configuration only.
const { chromium, expect } = require('../apps/web/node_modules/@playwright/test');
const fs = require('node:fs');
const path = require('node:path');

async function verify() {
  const repository = path.resolve(__dirname, '..');
  const inventory = JSON.parse(fs.readFileSync(path.join(repository, 'docs/PROMETHEUS_FINAL_RESEARCH_INVENTORY.json')));
  const dataset = 'dataset-86acfda4bc54dc0bf99bf987';
  const model = 'model-27006372c7ea4b7d850c0b9c';
  const tournament = 'tournament-999cf9ee983249599d1dccb8';
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = [];
  const writes = [];
  page.on('pageerror', error => errors.push(String(error)));
  page.on('request', request => {
    if (!['GET', 'HEAD', 'OPTIONS'].includes(request.method())) writes.push({ method: request.method(), url: request.url() });
  });
  const result = { checkedAt: new Date().toISOString(), dataset, model, tournament };
  async function get(href) {
    const response = await page.request.get(new URL(href, page.url()).href);
    if (response.status() !== 200) throw Error(`GET ${href}: ${response.status()}`);
    return response;
  }
  async function tab(name) {
    await page.getByRole('tab', { name, exact: true }).click();
  }
  async function selectArtifact(identity) {
    await page.locator('select').filter({ has: page.locator(`option[value="${identity}"]`) }).first().selectOption(identity);
  }
  try {
    await page.goto('http://127.0.0.1:5173/');
    result.health = await (await get('/api/health')).json();
    if (result.health.status !== 'READY' || result.health.live_execution !== false) throw Error('API must be READY and paper only');
    await page.getByRole('button', { name: 'Arena', exact: true }).click();
    await expect(page.getByText('Synthetic scenarios · Hypothetical fills · Economics unverified · Paper only')).toBeVisible();
    const overview = await (await get('/api/arena')).json();
    if (overview.models.length !== inventory.models.length || overview.tournaments.length !== inventory.tournaments.length) throw Error('Deployed registry differs from final inventory');
    result.registry = { models: overview.models.length, datasets: overview.datasets.length, tournaments: overview.tournaments.length, jobs: overview.jobs.length };
    if (overview.jobs.some(job => ['RUNNING', 'QUEUED'].includes(job.state))) throw Error('Production research is not terminal');

    await tab('Training console');
    await selectArtifact(dataset);
    await page.getByLabel('Epoch budget').fill('5');
    await page.getByRole('button', { name: 'Validate configuration', exact: true }).click();
    await expect(page.getByRole('status')).toHaveText('Configuration validated. Ready to launch.');
    result.trainingConfigurationValidated = true;
    const rows = await (await get(`/api/arena/datasets/${dataset}/rows?limit=25`)).json();
    if (rows.total !== 1593 || rows.rows.length !== 25 || !rows.rows.every(row => Array.isArray(row.features) && row.features.length === rows.feature_schema.length)) throw Error('Canonical migrated rows differ');
    result.canonicalDatasetRows = { total: rows.total, pageRows: rows.rows.length, featureCount: rows.feature_schema.length };

    await tab('Model registry');
    await page.locator('tr').filter({ hasText: model }).getByRole('button', { name: 'Inspect model', exact: true }).click();
    await expect(page.getByRole('heading', { name: `PPO / ${model}`, exact: true })).toBeVisible();
    const weights = page.getByRole('link', { name: 'Inference parameters / weights', exact: true });
    await expect(weights).toBeVisible();
    const weightResponse = await get(await weights.getAttribute('href'));
    result.modelWeightsBytes = (await weightResponse.body()).length;
    if (!result.modelWeightsBytes) throw Error('Empty model download');

    await tab('Tournaments');
    // Tournament options use their text as the implicit value.
    await page.locator('select').filter({ has: page.locator('option').filter({ hasText: tournament }) }).first().selectOption(tournament);
    await page.getByRole('button', { name: 'Replay episode', exact: true }).first().click();
    await expect(page.getByRole('heading', { name: 'Saved event replay', exact: true })).toBeVisible();
    const next = page.getByRole('button', { name: 'Next event', exact: true });
    if (await next.isEnabled()) {
      await next.click();
      await expect(page.getByText('Event 2 /', { exact: false })).toBeVisible();
    }
    const replay = await (await get(await page.getByRole('link', { name: 'Export replay', exact: true }).getAttribute('href'))).json();
    if (!replay.result.passed || !replay.result.complete) throw Error('Replay is invalid or incomplete');
    result.replay = { rowId: replay.row.id, journalStates: replay.result.journal.length, resultHash: replay.result.result_hash };

    await tab('Research director');
    for (const name of ['Evidence-driven research planning', 'Finite research schedules', 'Bounded missing-leg recovery', 'Residual sell, hold and repair']) await expect(page.getByRole('heading', { name, exact: true })).toBeVisible();
    result.plans = [];
    for (const plan of overview.plans) {
      const card = page.locator('article').filter({ has: page.locator(`a[href="/api/arena/plans/${plan.plan_id}"]`) });
      await expect(card).toBeVisible();
      await expect(card.getByRole('button', { name: 'Run frozen research plan', exact: true })).toBeDisabled();
      const saved = await (await get(`/api/arena/plans/${plan.plan_id}`)).json();
      if (!['CANCELLED', 'STALE_SOURCE'].includes(saved.state)) throw Error('Unexpected final plan state');
      result.plans.push({ planId: saved.plan_id, state: saved.state, runDisabled: true });
    }
    if (result.plans.length !== 2) throw Error('Expected two preserved terminal proposals');
    result.recoveryStudies = overview.recoveries.length;
    result.unwindStudies = overview.unwinds.length;

    await tab('Research findings');
    await expect(page.getByRole('heading', { name: 'Evidence-backed research findings', exact: true })).toBeVisible();
    result.findingsVisible = await page.locator('.arena-finding').count();
    if (result.findingsVisible !== overview.findings.length) throw Error('Findings catalog differs');
    await page.setViewportSize({ width: 390, height: 844 });
    await tab('Overview');
    await expect(page.getByRole('heading', { name: 'Dataset provenance', exact: true })).toBeVisible();
    result.mobileOverviewVisible = true;
    result.pageErrors = errors;
    result.mutationRequests = writes;
    if (errors.length || writes.some(request => !request.url.endsWith('/api/arena/jobs/validate'))) throw Error('Unexpected page error or mutation request');
    result.scope = 'Deployed saved-artifact workflows plus schema validation; no production job submitted, test metric opened, fitting or new economic evidence.';
    fs.writeFileSync(path.join(repository, 'docs/PROMETHEUS_FINAL_DEPLOYED_UI.json'), JSON.stringify(result, null, 2) + '\n', { flag: 'wx' });
    console.log(JSON.stringify(result));
  } finally {
    await browser.close();
  }
}

verify().catch(error => { console.error(error); process.exitCode = 1; });
