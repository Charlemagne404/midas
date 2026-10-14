/** Public sampled states: quality barriers and intervals >10 s are not interpolated. */
export type HistorySample = {
  ns: number;
  quality_reason?: unknown;
  legs?: Record<string, Record<string, unknown>>;
};
export function historySeries(
  rows: HistorySample[],
  leg: string,
  field: string,
): [number, number | null][] {
  const result: [number, number | null][] = [];
  rows.forEach((row, i) => {
    if (i && row.ns - rows[i - 1].ns > 10_000_000_000)
      result.push([(rows[i - 1].ns + row.ns) / 2e6, null]);
    const value = row.legs?.[leg]?.[field];
    result.push([
      row.ns / 1e6,
      row.quality_reason || value === null || value === undefined ? null : Number(value),
    ]);
  });
  return result;
}
