import { describe, expect, it, vi } from 'vitest';
import { ApiError, api, cleanOptions, describeError } from './client';

const respond = (body, status = 200) =>
  vi.fn(async () => new Response(body === null ? null : JSON.stringify(body), { status }));

describe('api client', () => {
  it('GETs JSON from /api', async () => {
    globalThis.fetch = respond({ ready: true });
    await expect(api.health()).resolves.toEqual({ ready: true });
    expect(fetch).toHaveBeenCalledWith('/api/health', expect.objectContaining({ method: 'GET' }));
  });

  it('POSTs a job with snake_case fields and cleaned options', async () => {
    globalThis.fetch = respond({ id: 'abc' }, 201);
    await api.createJob({
      sourceUrl: 'https://ok.ru/video/1',
      query: 'hello',
      options: { model: '', match_threshold: '75', cpu_threads: '', coarse_model: 'tiny.en' },
    });

    const [url, init] = fetch.mock.calls[0];
    expect(url).toBe('/api/jobs');
    expect(init.method).toBe('POST');
    expect(init.headers['Content-Type']).toBe('application/json');
    expect(JSON.parse(init.body)).toEqual({
      source_url: 'https://ok.ru/video/1',
      query: 'hello',
      options: { match_threshold: 75, coarse_model: 'tiny.en' },
    });
  });

  it('builds log, frame and video URLs', async () => {
    globalThis.fetch = respond({ lines: [], total: 0 });
    await api.getJobLogs('abc', 12);
    expect(fetch.mock.calls[0][0]).toBe('/api/jobs/abc/logs?offset=12');
    expect(api.frameUrl('abc')).toBe('/api/jobs/abc/frame');
    expect(api.videoUrl('abc')).toBe('/api/jobs/abc/video');
  });

  it('returns null for 204 responses', async () => {
    globalThis.fetch = vi.fn(async () => new Response(null, { status: 204 }));
    await expect(api.deleteJob('abc')).resolves.toBeNull();
  });

  it('throws ApiError with the backend detail message', async () => {
    globalThis.fetch = respond({ detail: "Job 'x' not found" }, 404);
    const error = await api.getJob('x').catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(404);
    expect(error.message).toBe("Job 'x' not found");
  });

  it('flattens FastAPI validation errors', async () => {
    globalThis.fetch = respond({
      detail: [{ loc: ['body', 'source_url'], msg: 'Value error, source_url must start with http:// or https://' }],
    }, 422);
    const error = await api.createJob({ sourceUrl: 'x', query: 'y', options: {} }).catch((e) => e);
    expect(error.status).toBe(422);
    expect(error.message).toBe('source_url: source_url must start with http:// or https://');
  });

  it('reports an unreachable backend clearly', async () => {
    globalThis.fetch = vi.fn(async () => {
      throw new TypeError('Failed to fetch');
    });
    const error = await api.listJobs().catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(0);
    expect(error.message).toMatch(/Cannot reach the backend/);
  });

  it('handles non-JSON error bodies', async () => {
    globalThis.fetch = vi.fn(async () => new Response('Internal Server Error', { status: 500 }));
    const error = await api.listJobs().catch((e) => e);
    expect(error.message).toBe('Request failed (HTTP 500)');
  });
});

describe('helpers', () => {
  it('describeError handles every shape', () => {
    expect(describeError({ detail: 'plain' }, 400)).toBe('plain');
    expect(describeError({ detail: [{ msg: 'bad' }] }, 422)).toBe('bad');
    expect(describeError(null, 502)).toBe('Request failed (HTTP 502)');
  });

  it('cleanOptions drops blanks and converts numbers', () => {
    expect(cleanOptions({ a: '', b: null, window_buffer: '30', fine_model: 'small.en' })).toEqual({
      window_buffer: 30,
      fine_model: 'small.en',
    });
    expect(cleanOptions()).toEqual({});
  });
});
