import { expect, it } from 'vitest';
import { preciseUtcTime } from './frontierTime';

it('keeps the full source precision in UTC trade timestamps', () => {
  expect(preciseUtcTime('2026-10-26T21:25:20.123000Z')).toBe('2026-10-26T21:25:20.123000 UTC');
  expect(preciseUtcTime('2026-10-26T21:25:20.750899Z')).toBe('2026-10-26T21:25:20.750899 UTC');
});

it('converts offset timestamps to UTC without rounding fractional digits', () => {
  expect(preciseUtcTime('2026-10-26T23:25:20.000123+02:00')).toBe('2026-10-26T21:25:20.000123 UTC');
});

it('labels absent timestamps and preserves the existing invalid-date fallback', () => {
  expect(preciseUtcTime(null)).toBe('Not recorded');
  expect(preciseUtcTime('not-a-date')).toBe(new Date('not-a-date').toLocaleString());
});
