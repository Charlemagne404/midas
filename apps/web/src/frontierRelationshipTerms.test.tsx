import { expect, it } from 'vitest';
import { compareRelationshipTerms, type RelationshipTermRecord } from './frontierRelationshipTerms';

const contract = (overrides: Partial<RelationshipTermRecord> = {}): RelationshipTermRecord => ({
  market_kind: 'binary_event',
  lifecycle: 'open',
  payoff: {
    state_ids: ['yes', 'no'],
    payout_currency: 'USD',
    exhaustive: true,
    verified: true,
  },
  settlement_asset: 'USD',
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
    rate: '0.02',
    formula: 'rate * price * (1-price)',
    fee_currency: 'USD',
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

it('makes the comparison unavailable when one market is outside the loaded graph window', () => {
  expect(compareRelationshipTerms(contract(), undefined)).toEqual({
    available: false,
    differences: [],
    unavailableFields: 0,
  });
});
