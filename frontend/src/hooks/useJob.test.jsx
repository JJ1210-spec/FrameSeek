import { renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { useJob } from './useJob';
import { installFakeBackend } from '../test/fakeBackend';
import { api } from '../api/client';

describe('useJob', () => {
  it('polls until the job finishes and accumulates logs incrementally', async () => {
    const backend = installFakeBackend();
    const job = await api.createJob({ sourceUrl: 'https://ok.ru/video/1', query: 'hi', options: {} });

    const { result } = renderHook(() => useJob(job.id));

    await waitFor(() => expect(result.current.job.status).toBe('completed'));
    expect(result.current.logs).toEqual([
      '[INFO] Downloading video ...',
      '[INFO] Tier: short  |  model: tiny.en  |  speech: 95.2s',
      '[INFO] Frame image   : matched_frame.jpg',
    ]);
    expect(result.current.job.result.frame_number).toBe(7785);

    // Log requests used increasing offsets
    const offsets = backend.fetch.mock.calls
      .map(([url]) => url)
      .filter((url) => url.includes('/logs'))
      .map((url) => Number(new URL(url, 'http://x').searchParams.get('offset')));
    expect(offsets[0]).toBe(0);
    expect(offsets).toEqual([...offsets].sort((a, b) => a - b));

    // Polling stops once the job is finished
    const calls = backend.fetch.mock.calls.length;
    await new Promise((r) => setTimeout(r, 100));
    expect(backend.fetch.mock.calls.length).toBe(calls);
  });

  it('reports a 404 without retrying', async () => {
    const backend = installFakeBackend();
    const { result } = renderHook(() => useJob('missing'));

    await waitFor(() => expect(result.current.error).not.toBeNull());
    expect(result.current.error.status).toBe(404);
    expect(result.current.job).toBeNull();
    const calls = backend.fetch.mock.calls.length;
    await new Promise((r) => setTimeout(r, 100));
    expect(backend.fetch.mock.calls.length).toBe(calls);
  });

  it('retries transient errors', async () => {
    let failures = 2;
    const backend = installFakeBackend();
    const real = backend.fetch.getMockImplementation();
    await api.createJob({ sourceUrl: 'https://ok.ru/video/1', query: 'hi', options: {} });
    globalThis.fetch = vi.fn(async (...args) => {
      if (failures > 0) {
        failures -= 1;
        throw new TypeError('Failed to fetch');
      }
      return real(...args);
    });

    const { result } = renderHook(() => useJob('job000000001'));
    await waitFor(() => expect(result.current.job && result.current.job.status).toBe('completed'));
    expect(result.current.error).toBeNull();
  });

  it('does nothing without a job id', () => {
    globalThis.fetch = vi.fn();
    const { result } = renderHook(() => useJob(null));
    expect(result.current.loading).toBe(false);
    expect(fetch).not.toHaveBeenCalled();
  });
});
