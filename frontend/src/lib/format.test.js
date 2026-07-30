import { describe, expect, it } from 'vitest';
import {
  elapsedSeconds,
  formatDateTime,
  formatDuration,
  formatScore,
  formatTimestamp,
  hostOf,
} from './format';

describe('formatTimestamp', () => {
  it.each([
    [0, '00:00.000'],
    [5.5, '00:05.500'],
    [324.68, '05:24.680'],
    [324.77, '05:24.770'],
    [3725.5, '1:02:05.500'],
    ['12.25', '00:12.250'],
  ])('%s → %s', (input, expected) => {
    expect(formatTimestamp(input)).toBe(expected);
  });

  it('returns a dash for missing values', () => {
    expect(formatTimestamp(null)).toBe('—');
    expect(formatTimestamp(undefined)).toBe('—');
    expect(formatTimestamp('abc')).toBe('—');
  });
});

describe('formatDuration', () => {
  it.each([
    [0.123, '0.12 s'],
    [12.345, '12.3 s'],
    [60, '1 min'],
    [323.89, '5 min 24 s'],
  ])('%s → %s', (input, expected) => {
    expect(formatDuration(input)).toBe(expected);
  });

  it('returns a dash for missing values', () => {
    expect(formatDuration(null)).toBe('—');
  });
});

describe('elapsedSeconds', () => {
  it('measures between start and end', () => {
    expect(elapsedSeconds('2026-01-01T00:00:00Z', '2026-01-01T00:01:30Z')).toBe(90);
  });

  it('measures up to now while running', () => {
    const now = new Date('2026-01-01T00:00:10Z').getTime();
    expect(elapsedSeconds('2026-01-01T00:00:00Z', null, now)).toBe(10);
  });

  it('is null before the job starts', () => {
    expect(elapsedSeconds(null, null)).toBeNull();
  });
});

describe('misc formatters', () => {
  it('extracts a readable host', () => {
    expect(hostOf('https://www.youtube.com/watch?v=x')).toBe('youtube.com');
    expect(hostOf('https://ok.ru/video/1')).toBe('ok.ru');
    expect(hostOf('not a url')).toBe('not a url');
  });

  it('formats scores', () => {
    expect(formatScore(78.87)).toBe('78.9 / 100');
    expect(formatScore(null)).toBe('—');
  });

  it('formats dates defensively', () => {
    expect(formatDateTime(null)).toBe('—');
    expect(formatDateTime('garbage')).toBe('—');
    expect(formatDateTime('2026-09-28T10:00:00Z')).not.toBe('—');
  });
});
