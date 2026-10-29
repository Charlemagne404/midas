import { expect, it } from 'vitest';
import { compareRelationshipTerms, type RelationshipTermRecord } from './frontierRelationshipTerms';

const contract = (overrides: Partial<RelationshipTermRecord> = {}): RelationshipTermRecord => ({
  market_kind: 'binary_event',
  lifecycle: 'open',
  payoff: {
    state_ids: ['yes', 'no'],
    payout_currency: 'USD',
    settlement_asset: 'USD',
    settlement_asset_identity: {
      kind: 'fiat',
      code: 'USD',
      network_id: null,
      asset_reference: null,
    },
    exhaustive: true,
    verified: true,
  },
  settlement_asset: 'USD',
  settlement_asset_identity: {
    kind: 'fiat',
    code: 'USD',
    network_id: null,
    asset_reference: null,
  },
  resolution: {
    authority: 'Official source',
    closes_at_utc: '2026-10-30T00:00:00Z',
    settles_at_utc: '2026-10-30T01:00:00Z',
    resolution_fingerprint: 'a'.repeat(64),
  },
  fees: {
    status: 'reported',
    version: 'fee-v1',
    applies_to: 'taker',
    fixed_fee: '0',
    rate: '0.02',
    fee_multiplier: '1',
    formula: 'rate * price * (1-price)',
    fee_currency: 'USD',
    fee_currency_identity: {
      kind: 'fiat',
      code: 'USD',
      network_id: null,
      asset_reference: null,
    },
    source_url: 'https://example.invalid/fees',
    evidence_sha256: 'b'.repeat(64),
    evidence_observation_ids: ['c'.repeat(64), 'd'.repeat(64)],
    evidence_observed_at_utc: '2026-10-29T00:00:00Z',
    effective_at_utc: '2026-10-29T00:00:00Z',
    expires_at_utc: '2026-11-29T00:00:00Z',
  },
  ...overrides,
});

it('reports literal recorded mismatches without certifying payoff equivalence', () => {
  const left = contract();
  const right = contract({
    resolution: {
      ...left.resolution,
      authority: 'Different source',
      resolution_fingerprint: 'b'.repeat(64),
    },
    payoff: { ...left.payoff, state_ids: ['above', 'below'] },
  });

  const comparison = compareRelationshipTerms(left, right);

  expect(comparison.available).toBe(true);
  expect(comparison.unavailableFields).toBe(0);
  expect(comparison.differences).toEqual(
    expect.arrayContaining([
      {
        field: 'Payoff state identifiers',
        left: 'no · yes',
        right: 'above · below',
      },
      {
        field: 'Resolution authority',
        left: 'Official source',
        right: 'Different source',
      },
      {
        field: 'Resolution fingerprint',
        left: 'a'.repeat(64),
        right: 'b'.repeat(64),
      },
    ]),
  );
});

it('sorts state identifiers and counts comparisons with incomplete source fields', () => {
  const left = contract();
  const right = contract({
    payoff: { ...left.payoff, state_ids: ['no', 'yes'], payout_currency: null },
    fees: { ...left.fees, formula: null },
    resolution: { ...left.resolution, authority: '   ' },
  });

  const comparison = compareRelationshipTerms(left, right);

  expect(comparison.differences).toEqual([]);
  expect(comparison.unavailableFields).toBe(3);
});

it('separates nominal currency codes from asset identity and fee evidence terms', () => {
  const left = contract();
  const tokenUsd = {
    kind: 'token',
    code: 'USD',
    network_id: 'eip155:137',
    asset_reference: `0x${'a'.repeat(40)}`,
  };
  const right = contract({
    settlement_asset_identity: tokenUsd,
    payoff: { ...left.payoff, settlement_asset_identity: tokenUsd },
    fees: {
      ...left.fees,
      fixed_fee: '0.10',
      fee_multiplier: '1.25',
      expires_at_utc: '2026-12-01T00:00:00Z',
      evidence_sha256: 'e'.repeat(64),
    },
  });

  const comparison = compareRelationshipTerms(left, right);
  const fields = comparison.differences.map(({ field }) => field);

  expect(fields).toEqual(
    expect.arrayContaining([
      'Market settlement identity',
      'Payoff settlement identity',
      'Fixed fee',
      'Fee multiplier',
      'Fee expires at (UTC)',
      'Fee evidence hash',
    ]),
  );
});

it('makes the comparison unavailable when one market is outside the loaded graph window', () => {
  expect(compareRelationshipTerms(contract(), undefined)).toEqual({
    available: false,
    differences: [],
    unavailableFields: 0,
  });
});
