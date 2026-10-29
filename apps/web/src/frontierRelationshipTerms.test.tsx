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
  instruments: [
    {
      outcome_id: 'no',
      label: 'No',
      quantity_unit: 'contract',
      price_currency: 'USD',
      price_currency_identity: {
        kind: 'fiat',
        code: 'USD',
        network_id: null,
        asset_reference: null,
      },
      tick_size: '0.01',
      price_increment_ranges: [{ start: '0', end: '1', step: '0.01' }],
      quantity_step: '1',
      minimum_quantity: '1',
      minimum_notional: '1',
      payouts: [
        { state_id: 'no', amount: '1' },
        { state_id: 'yes', amount: '0' },
      ],
    },
    {
      outcome_id: 'yes',
      label: 'Yes',
      quantity_unit: 'contract',
      price_currency: 'USD',
      price_currency_identity: {
        kind: 'fiat',
        code: 'USD',
        network_id: null,
        asset_reference: null,
      },
      tick_size: '0.01',
      price_increment_ranges: [{ start: '0', end: '1', step: '0.01' }],
      quantity_step: '1',
      minimum_quantity: '1',
      minimum_notional: '1',
      payouts: [
        { state_id: 'no', amount: '0' },
        { state_id: 'yes', amount: '1' },
      ],
    },
  ],
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

it('compares instrument quote identity, trading constraints, and complete payout vectors', () => {
  const left = contract();
  const right = contract({
    instruments: left.instruments?.map((instrument) => ({
      ...instrument,
      price_currency_identity: {
        kind: 'token',
        code: 'USD',
        network_id: 'eip155:137',
        asset_reference: `0x${'a'.repeat(40)}`,
      },
      quantity_step: '0.5',
      payouts:
        instrument.outcome_id === 'yes'
          ? [
              { state_id: 'yes', amount: '0.99' },
              { state_id: 'no', amount: '0' },
            ]
          : instrument.payouts,
    })),
  });

  const comparison = compareRelationshipTerms(left, right);
  const fields = comparison.differences.map(({ field }) => field);

  expect(fields).toEqual(
    expect.arrayContaining([
      'Instrument quote asset identities',
      'Instrument quantity steps',
      'Instrument payout vectors',
    ]),
  );
});

it('keeps partial instrument metadata unavailable instead of treating it as a match', () => {
  const left = contract();
  const right = contract({
    instruments: left.instruments?.map((instrument, index) =>
      index === 0 ? { ...instrument, price_currency_identity: null } : instrument,
    ),
  });

  const comparison = compareRelationshipTerms(left, right);

  expect(
    comparison.differences.some(({ field }) => field === 'Instrument quote asset identities'),
  ).toBe(false);
  expect(comparison.unavailableFields).toBe(1);
});

it('normalizes instrument ordering and refuses oversized detail summaries', () => {
  const left = contract();
  const reordered = contract({
    instruments: left.instruments
      ?.map((instrument) => ({
        ...instrument,
        price_increment_ranges: [...(instrument.price_increment_ranges ?? [])].reverse(),
        payouts: [...(instrument.payouts ?? [])].reverse(),
      }))
      .reverse(),
  });
  expect(compareRelationshipTerms(left, reordered).differences).toEqual([]);

  const oversized = contract({
    instruments: Array.from({ length: 33 }, (_, index) => ({
      ...left.instruments![index % left.instruments!.length]!,
      outcome_id: `outcome-${index}`,
    })),
  });
  const comparison = compareRelationshipTerms(oversized, oversized);

  expect(comparison.differences.some(({ field }) => field === 'Instrument payout vectors')).toBe(
    false,
  );
  expect(comparison.unavailableFields).toBeGreaterThan(0);

  const oversizedPayouts = contract({
    instruments: left.instruments?.map((instrument) => ({
      ...instrument,
      payouts: Array.from({ length: 65 }, (_, index) => ({
        state_id: `state-${index}`,
        amount: '1',
      })),
    })),
  });
  const payoutComparison = compareRelationshipTerms(oversizedPayouts, oversizedPayouts);
  expect(
    payoutComparison.differences.some(({ field }) => field === 'Instrument payout vectors'),
  ).toBe(false);
  expect(payoutComparison.unavailableFields).toBeGreaterThan(0);
});

it('makes the comparison unavailable when one market is outside the loaded graph window', () => {
  expect(compareRelationshipTerms(contract(), undefined)).toEqual({
    available: false,
    differences: [],
    unavailableFields: 0,
  });
});
