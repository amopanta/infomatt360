import { expect, it } from 'vitest';
import { formatOperationalDate, operationalStatusLabel } from './operationalFormat';
it('interprets naive server dates as UTC and renders equivalent instants in Bogota', () => {
  const utc = formatOperationalDate('2026-10-07T15:00:00Z');
  expect(formatOperationalDate('2026-10-07T15:00:00')).toBe(utc);
  expect(formatOperationalDate('2026-10-07T10:00:00-05:00')).toBe(utc);
  expect(utc).toContain('10:00');
  expect(formatOperationalDate('invalid')).toBe('—');
});
it('translates operational states while preserving unknown states', () => {
  expect(operationalStatusLabel('under_review')).toBe('En revisión');
  expect(operationalStatusLabel('custom')).toBe('custom');
});
