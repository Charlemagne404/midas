import { expect, test } from '@playwright/test';

test('Frontier workspace uses isolated research state and remains responsive', async ({ page }) => {
  let probeRequests = 0;
  page.on('request', (request) => {
    if (request.url().includes('/api/frontier/probe/')) probeRequests += 1;
  });
  await page.goto('/');
  await page.getByRole('button', { name: 'Frontier', exact: true }).click();

  await expect(page.getByText('FRONTIER · READ-ONLY RESEARCH')).toBeVisible();
  await expect(
    page.getByRole('heading', { name: 'Market relationships, with evidence attached.' }),
  ).toBeVisible();
  await expect(page.getByText('No replay runs yet')).toBeVisible();
  await page.screenshot({ path: test.info().outputPath('frontier-overview.png'), fullPage: true });
  await expect(page.getByText('SYNTHETIC DATA')).toHaveCount(0);
  expect(probeRequests).toBe(0);

  await page.getByRole('button', { name: 'Markets', exact: true }).click();
  await expect(page.getByText('No market observations recorded')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(1440);

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByText('No market observations recorded')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});

test('relationship network remains bounded, selectable, and scroll-contained on mobile', async ({
  page,
}) => {
  const marketRecord = (venue: 'polymarket' | 'kalshi', nativeId: string, title: string) => ({
    canonical_id: `${venue}:${nativeId}`,
    source_observation_record_id: venue === 'polymarket' ? 'a'.repeat(64) : 'b'.repeat(64),
    native_market_id: nativeId,
    venue,
    title,
    market_kind: 'binary_event',
    lifecycle: 'open',
    description: '',
    base_asset: null,
    quote_asset: null,
    settlement_asset: null,
    payoff: {
      state_ids: [],
      payout_currency: null,
      exhaustive: false,
      verified: false,
      verification_basis: 'fixture, not attested',
    },
    resolution: {
      primary_rule: null,
      secondary_rule: null,
      authority: null,
      closes_at_utc: null,
      settles_at_utc: null,
      evidence_sha256: null,
      verified: false,
    },
    fees: {
      status: 'unknown',
      version: null,
      applies_to: null,
      rate: null,
      formula: null,
      fee_currency: null,
      source_url: null,
      note: 'unknown',
    },
    instruments: [],
    quality_flags: ['E2E_FIXTURE_ONLY'],
    provenance: {
      response_received_at_utc: '2026-10-26T20:00:00Z',
      raw_sha256: 'a'.repeat(64),
      observation_id: `${venue}-observation`,
    },
  });
  const reason = 'Shared title terms; settlement rules and dates remain unreviewed.';
  const relationship = {
    relationship_id: 'fixture-edge-1',
    left_market_id: 'polymarket:election-1',
    right_market_id: 'kalshi:election-1',
    relationship_type: 'text_candidate',
    state: 'hypothesis',
    confidence: '0.75',
    reason,
    supersedes: null,
    review_target_relationship_id: 'fixture-edge-1',
    latest_review: null,
    evidence: [
      {
        method: 'e2e-test-fixture',
        observation_ids: ['p-fixture', 'k-fixture'],
        source_fields: ['title'],
        details: ['This is a UI fixture only.'],
      },
    ],
  };
  const fixtures: Record<string, unknown> = {
    '/api/frontier/overview': {
      state: 'AVAILABLE',
      research_only: true,
      live_execution: false,
      summary: {
        observations: 2,
        relationships: 1,
        relationship_reviews: 0,
        runs: 0,
        markets_by_venue: { polymarket: 1, kalshi: 1 },
        instruments_by_venue: {},
        relationships_by_state: { hypothesis: 1 },
        database_bytes: 2048,
        max_bytes: 67_108_864,
      },
      sources: [],
      latest_evidence_at_utc: '2026-10-26T20:00:00Z',
      limitations: ['E2E-only fixture.'],
    },
    '/api/frontier/sources': { items: [] },
    '/api/frontier/markets': {
      items: [
        marketRecord('polymarket', 'election-1', 'Who wins the mayoral election?'),
        marketRecord('kalshi', 'election-1', 'Who wins the mayoral election?'),
      ],
      returned: 2,
      limit: 100,
      offset: 0,
    },
    '/api/frontier/books': { items: [], returned: 0, limit: 100, offset: 0 },
    '/api/frontier/relationships': { items: [relationship], returned: 1, limit: 200 },
    '/api/frontier/opportunities': { items: [], returned: 0, limit: 100, offset: 0 },
    '/api/frontier/runs': { items: [], returned: 0, limit: 30, offset: 0 },
    '/api/frontier/readiness': { gates: [] },
  };
  let submittedReview: Record<string, unknown> | undefined;
  await page.route('**/api/frontier/**', async (route) => {
    if (route.request().method() === 'POST' && route.request().url().endsWith('/review')) {
      submittedReview = route.request().postDataJSON() as Record<string, unknown>;
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ review: {}, relationship: {} }),
      });
    }
    const path = new URL(route.request().url()).pathname;
    const fixture = fixtures[path];
    if (fixture === undefined) return route.continue();
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(fixture),
    });
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('/');
  await page.getByRole('button', { name: 'Frontier', exact: true }).click();
  await page.getByRole('button', { name: 'Relationship graph', exact: true }).click();

  await expect(page.getByRole('group', { name: /Relationship network showing 1/ })).toBeVisible();
  const edge = page.getByRole('button', { name: /text candidate hypothesis/i });
  await edge.click();
  await expect(edge).toHaveAttribute('aria-pressed', 'true');
  await expect(page.locator('.fr-edge details[open] p')).toHaveText(reason);
  await page.screenshot({
    path: test.info().outputPath('frontier-relationship-network.png'),
    fullPage: true,
  });

  await page.getByRole('button', { name: 'Review hypothesis' }).click();
  await page.getByLabel('Reviewer label').fill('e2e-reviewer');
  await page.getByLabel('Review reason').fill('This fixture remains ambiguous pending rules.');
  await page.getByRole('button', { name: 'Record immutable review' }).click();
  await expect
    .poll(() => submittedReview)
    .toMatchObject({
      decision: 'ambiguous',
      reviewer_label: 'e2e-reviewer',
      evidence_observation_ids: ['a'.repeat(64), 'b'.repeat(64)],
      expected_latest_review_id: null,
    });

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole('group', { name: /Relationship network showing 1/ })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await expect(page.locator('.fr-network-scroll')).toHaveCSS('overflow-x', 'auto');
  await page.getByRole('button', { name: 'Review hypothesis' }).click();
  await expect(page.locator('.fr-review-form')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});
