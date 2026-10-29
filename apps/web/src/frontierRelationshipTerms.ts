type AssetIdentity = {
  kind: string;
  code: string;
  network_id: string | null;
  asset_reference: string | null;
};

type InstrumentTermRecord = {
  outcome_id: string | null;
  label: string;
  quantity_unit?: string | null;
  price_currency?: string | null;
  price_currency_identity?: AssetIdentity | null;
  tick_size?: string | null;
  price_increment_ranges?: { start: string; end: string; step: string }[] | null;
  quantity_step?: string | null;
  minimum_quantity?: string | null;
  minimum_notional?: string | null;
  payouts?: { state_id: string; amount: string }[];
};

export type RelationshipTermRecord = {
  market_kind: string;
  lifecycle: string;
  payoff: {
    state_ids: string[];
    payout_currency: string | null;
    settlement_asset?: string | null;
    settlement_asset_identity?: AssetIdentity | null;
    exhaustive: boolean;
    verified: boolean;
  };
  settlement_asset: string | null;
  settlement_asset_identity?: AssetIdentity | null;
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
    fixed_fee?: string | null;
    rate: string | null;
    fee_multiplier?: string | null;
    formula: string | null;
    fee_currency: string | null;
    fee_currency_identity?: AssetIdentity | null;
    source_url?: string | null;
    evidence_sha256?: string | null;
    evidence_observation_ids?: string[];
    evidence_observed_at_utc?: string | null;
    effective_at_utc?: string | null;
    expires_at_utc?: string | null;
  };
  instruments?: InstrumentTermRecord[];
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

const MAX_COMPARISON_INSTRUMENTS = 32;
const MAX_COMPARISON_LIST_ITEMS = 64;
const MAX_COMPARISON_TEXT_CHARS = 4096;

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

  const identityKey = (identity: AssetIdentity | null | undefined): string | null => {
    if (!identity) return null;
    return JSON.stringify([
      identity.kind,
      identity.code,
      identity.network_id,
      identity.asset_reference,
    ]);
  };
  const compareText = (leftText: string, rightText: string) =>
    leftText === rightText ? 0 : leftText < rightText ? -1 : 1;
  const sortedJson = <T>(items: T[]): string | null => {
    if (!items.length || items.length > MAX_COMPARISON_LIST_ITEMS) return null;
    const serialized = JSON.stringify(
      [...items].sort((leftItem, rightItem) =>
        compareText(JSON.stringify(leftItem) ?? '', JSON.stringify(rightItem) ?? ''),
      ),
    );
    return serialized && serialized.length <= MAX_COMPARISON_TEXT_CHARS ? serialized : null;
  };
  const instrumentValues = (
    instruments: InstrumentTermRecord[] | undefined,
    select: (instrument: InstrumentTermRecord) => string | null,
  ): string | null => {
    if (!instruments?.length || instruments.length > MAX_COMPARISON_INSTRUMENTS) {
      return null;
    }
    const entries: { key: string; value: string }[] = [];
    for (const instrument of instruments) {
      const key = instrument.outcome_id?.trim() || instrument.label.trim();
      const value = select(instrument);
      if (!key || !value?.trim()) return null;
      entries.push({ key, value });
    }
    entries.sort(
      (leftEntry, rightEntry) =>
        compareText(leftEntry.key, rightEntry.key) ||
        compareText(leftEntry.value, rightEntry.value),
    );
    const serialized = JSON.stringify(entries.map(({ key, value }) => [key, value]));
    return serialized.length <= MAX_COMPARISON_TEXT_CHARS ? serialized : null;
  };
  const priceIncrementRangesKey = (instrument: InstrumentTermRecord): string | null => {
    const ranges = instrument.price_increment_ranges;
    if (!ranges?.length || ranges.length > MAX_COMPARISON_LIST_ITEMS) return null;
    return sortedJson(ranges.map(({ start, end, step }) => [start, end, step]));
  };
  const payoutVectorKey = (instrument: InstrumentTermRecord): string | null => {
    const payouts = instrument.payouts;
    if (!payouts?.length || payouts.length > MAX_COMPARISON_LIST_ITEMS) return null;
    return sortedJson(payouts.map(({ state_id, amount }) => [state_id, amount]));
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
  if (left.instruments !== undefined || right.instruments !== undefined) {
    compare(
      'Instrument count',
      left.instruments?.length ? String(left.instruments.length) : null,
      right.instruments?.length ? String(right.instruments.length) : null,
    );
    compare(
      'Instrument outcome identifiers',
      instrumentValues(left.instruments, (instrument) => instrument.outcome_id),
      instrumentValues(right.instruments, (instrument) => instrument.outcome_id),
    );
    compare(
      'Instrument labels',
      instrumentValues(left.instruments, (instrument) => instrument.label),
      instrumentValues(right.instruments, (instrument) => instrument.label),
    );
    compare(
      'Instrument quantity units',
      instrumentValues(left.instruments, (instrument) => instrument.quantity_unit ?? null),
      instrumentValues(right.instruments, (instrument) => instrument.quantity_unit ?? null),
    );
    compare(
      'Instrument quote currencies',
      instrumentValues(left.instruments, (instrument) => instrument.price_currency ?? null),
      instrumentValues(right.instruments, (instrument) => instrument.price_currency ?? null),
    );
    compare(
      'Instrument quote asset identities',
      instrumentValues(left.instruments, (instrument) =>
        identityKey(instrument.price_currency_identity),
      ),
      instrumentValues(right.instruments, (instrument) =>
        identityKey(instrument.price_currency_identity),
      ),
    );
    compare(
      'Instrument tick sizes',
      instrumentValues(left.instruments, (instrument) => instrument.tick_size ?? null),
      instrumentValues(right.instruments, (instrument) => instrument.tick_size ?? null),
    );
    compare(
      'Instrument price increment ranges',
      instrumentValues(left.instruments, priceIncrementRangesKey),
      instrumentValues(right.instruments, priceIncrementRangesKey),
    );
    compare(
      'Instrument quantity steps',
      instrumentValues(left.instruments, (instrument) => instrument.quantity_step ?? null),
      instrumentValues(right.instruments, (instrument) => instrument.quantity_step ?? null),
    );
    compare(
      'Instrument minimum quantities',
      instrumentValues(left.instruments, (instrument) => instrument.minimum_quantity ?? null),
      instrumentValues(right.instruments, (instrument) => instrument.minimum_quantity ?? null),
    );
    compare(
      'Instrument minimum notionals',
      instrumentValues(left.instruments, (instrument) => instrument.minimum_notional ?? null),
      instrumentValues(right.instruments, (instrument) => instrument.minimum_notional ?? null),
    );
    compare(
      'Instrument payout vectors',
      instrumentValues(left.instruments, payoutVectorKey),
      instrumentValues(right.instruments, payoutVectorKey),
    );
  }
  compare('Settlement asset', left.settlement_asset, right.settlement_asset);
  compare(
    'Market settlement identity',
    identityKey(left.settlement_asset_identity),
    identityKey(right.settlement_asset_identity),
  );
  compare(
    'Payoff settlement asset',
    left.payoff.settlement_asset ?? null,
    right.payoff.settlement_asset ?? null,
  );
  compare(
    'Payoff settlement identity',
    identityKey(left.payoff.settlement_asset_identity),
    identityKey(right.payoff.settlement_asset_identity),
  );
  compare('Resolution authority', left.resolution.authority, right.resolution.authority);
  compare(
    'Resolution fingerprint',
    left.resolution.resolution_fingerprint,
    right.resolution.resolution_fingerprint,
  );
  compare('Close time (UTC)', left.resolution.closes_at_utc, right.resolution.closes_at_utc);
  compare('Settlement time (UTC)', left.resolution.settles_at_utc, right.resolution.settles_at_utc);
  compare('Fee status', left.fees.status, right.fees.status);
  compare('Fee version', left.fees.version, right.fees.version);
  compare('Fee applicability', left.fees.applies_to, right.fees.applies_to);
  compare('Fixed fee', left.fees.fixed_fee ?? null, right.fees.fixed_fee ?? null);
  compare('Fee rate', left.fees.rate, right.fees.rate);
  compare('Fee multiplier', left.fees.fee_multiplier ?? null, right.fees.fee_multiplier ?? null);
  compare('Fee formula', left.fees.formula, right.fees.formula);
  compare('Fee currency', left.fees.fee_currency, right.fees.fee_currency);
  compare(
    'Fee currency identity',
    identityKey(left.fees.fee_currency_identity),
    identityKey(right.fees.fee_currency_identity),
  );
  compare('Fee source URL', left.fees.source_url ?? null, right.fees.source_url ?? null);
  compare(
    'Fee evidence hash',
    left.fees.evidence_sha256 ?? null,
    right.fees.evidence_sha256 ?? null,
  );
  compare(
    'Fee evidence observations',
    left.fees.evidence_observation_ids?.length
      ? [...left.fees.evidence_observation_ids].sort().join(' · ')
      : null,
    right.fees.evidence_observation_ids?.length
      ? [...right.fees.evidence_observation_ids].sort().join(' · ')
      : null,
  );
  compare(
    'Fee evidence observed at (UTC)',
    left.fees.evidence_observed_at_utc ?? null,
    right.fees.evidence_observed_at_utc ?? null,
  );
  compare(
    'Fee effective at (UTC)',
    left.fees.effective_at_utc ?? null,
    right.fees.effective_at_utc ?? null,
  );
  compare(
    'Fee expires at (UTC)',
    left.fees.expires_at_utc ?? null,
    right.fees.expires_at_utc ?? null,
  );

  return { available: true, differences, unavailableFields };
}
