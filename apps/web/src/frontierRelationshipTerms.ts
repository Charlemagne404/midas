export type RelationshipTermRecord = {
  market_kind: string;
  lifecycle: string;
  payoff: {
    state_ids: string[];
    payout_currency: string | null;
    exhaustive: boolean;
    verified: boolean;
  };
  settlement_asset: string | null;
  resolution: {
    authority: string | null;
    closes_at_utc: string | null;
    settles_at_utc: string | null;
    resolution_fingerprint: string | null;
  };
  fees: {
    status: string;
    version: string | null;
    applies_to: string | null;
    rate: string | null;
    formula: string | null;
    fee_currency: string | null;
  };
};

export type RelationshipTermDifference = {
  field: string;
  left: string;
  right: string;
};

export type RelationshipTermComparison = {
  available: boolean;
  differences: RelationshipTermDifference[];
  unavailableFields: number;
};

export function compareRelationshipTerms(
  left: RelationshipTermRecord | undefined,
  right: RelationshipTermRecord | undefined,
): RelationshipTermComparison {
  if (!left || !right) {
    return { available: false, differences: [], unavailableFields: 0 };
  }

  const differences: RelationshipTermDifference[] = [];
  let unavailableFields = 0;
  const compare = (field: string, leftValue: string | null, rightValue: string | null) => {
    if (!leftValue?.trim() || !rightValue?.trim()) {
      unavailableFields += 1;
      return;
    }
    if (leftValue !== rightValue) differences.push({ field, left: leftValue, right: rightValue });
  };

  const feeSchedule = (market: RelationshipTermRecord): string | null => {
    const { version, applies_to, rate, formula, fee_currency } = market.fees;
    if ([version, applies_to, rate, formula, fee_currency].some((value) => !value?.trim())) {
      return null;
    }
    return [version, applies_to, rate, formula, fee_currency].join(' · ');
  };

  compare('Instrument type', left.market_kind, right.market_kind);
  compare('Lifecycle', left.lifecycle, right.lifecycle);
  compare(
    'Payoff state identifiers',
    left.payoff.state_ids.some((state) => state.trim())
      ? [...left.payoff.state_ids].sort().join(' · ')
      : null,
    right.payoff.state_ids.some((state) => state.trim())
      ? [...right.payoff.state_ids].sort().join(' · ')
      : null,
  );
  compare('Payoff verification', String(left.payoff.verified), String(right.payoff.verified));
  compare('Outcome coverage', String(left.payoff.exhaustive), String(right.payoff.exhaustive));
  compare('Payout currency', left.payoff.payout_currency, right.payoff.payout_currency);
  compare('Settlement asset', left.settlement_asset, right.settlement_asset);
  compare('Resolution authority', left.resolution.authority, right.resolution.authority);
  compare(
    'Resolution fingerprint',
    left.resolution.resolution_fingerprint,
    right.resolution.resolution_fingerprint,
  );
  compare('Close time (UTC)', left.resolution.closes_at_utc, right.resolution.closes_at_utc);
  compare('Settlement time (UTC)', left.resolution.settles_at_utc, right.resolution.settles_at_utc);
  compare('Fee status', left.fees.status, right.fees.status);
  compare('Fee schedule', feeSchedule(left), feeSchedule(right));

  return { available: true, differences, unavailableFields };
}
