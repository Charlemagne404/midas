/** Public sampled states: quality barriers and intervals >10 s are not interpolated. */
export type HistorySample = {
  ns: number;
  quality_reason?: unknown;
  legs?: Record<string, Record<string, unknown>>;
};
export function historyDiscontinuity(row: HistorySample, previous?: HistorySample): string | null {
  if (!previous) return null;
  if (row.ns - previous.ns > 10_000_000_000) return 'missing_observations_between_samples';
  for (const leg of ['yes', 'no']) {
    const current = row.legs?.[leg]?.snapshot,
      prior = previous.legs?.[leg]?.snapshot;
    if (current && prior && JSON.stringify(current) !== JSON.stringify(prior))
      return 'snapshot_resynchronization_between_samples';
  }
  return null;
}
export function historyBarrier(row: HistorySample, previous?: HistorySample): string | null {
  return row.quality_reason ? String(row.quality_reason) : historyDiscontinuity(row, previous);
}
export function historySeries(
  rows: HistorySample[],
  leg: string,
  field: string,
): [number, number | null][] {
  const result: [number, number | null][] = [];
  rows.forEach((row, i) => {
    const discontinuity = historyDiscontinuity(row, rows[i - 1]);
    if (i && discontinuity) result.push([(rows[i - 1].ns + row.ns) / 2e6, null]);
    const previous = rows[i - 1];
    const elapsed = previous ? (row.ns - previous.ns) / 1e9 : 0;
    let value = row.legs?.[leg]?.[field];
    if (field === 'sampled_update_rate') {
      const lineage = row.legs?.[leg]?.last,
        prior = previous?.legs?.[leg]?.last;
      value =
        row.quality_reason ||
        previous?.quality_reason ||
        elapsed <= 0 ||
        elapsed > 10 ||
        discontinuity ||
        !lineage ||
        !prior
          ? null
          : JSON.stringify(lineage) === JSON.stringify(prior)
            ? 0
            : 1 / elapsed;
    }
    result.push([
      row.ns / 1e6,
      row.quality_reason || value === null || value === undefined ? null : Number(value),
    ]);
  });
  return result;
}
