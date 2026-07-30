// Thin fetch wrapper around the FastAPI backend (see backend/app/api).
import { API_BASE } from '../config';

export class ApiError extends Error {
  constructor(message, status, body) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

// FastAPI returns `detail` as a string, or as a list of validation errors.
export function describeError(body, status) {
  const detail = body && body.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    return detail
      .map((err) => {
        const field = (err.loc || []).filter((part) => part !== 'body').join('.');
        const msg = (err.msg || 'Invalid value').replace(/^Value error, /, '');
        return field ? `${field}: ${msg}` : msg;
      })
      .join('; ');
  }
  return `Request failed (HTTP ${status})`;
}

async function request(path, { method = 'GET', body, signal } = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      signal,
      headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch (err) {
    if (err && err.name === 'AbortError') throw err;
    throw new ApiError('Cannot reach the backend. Is it running on port 8000?', 0, null);
  }

  if (response.status === 204) return null;

  let data = null;
  const text = await response.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = null;
    }
  }

  if (!response.ok) {
    throw new ApiError(describeError(data, response.status), response.status, data);
  }
  return data;
}

// Empty strings from the form mean "use the backend default".
export function cleanOptions(options = {}) {
  const numeric = ['match_threshold', 'coarse_threshold', 'window_buffer', 'cpu_threads'];
  const cleaned = {};
  for (const [key, value] of Object.entries(options)) {
    if (value === '' || value === null || value === undefined) continue;
    cleaned[key] = numeric.includes(key) ? Number(value) : value;
  }
  return cleaned;
}

export const api = {
  health: (opts) => request('/health', opts),
  listJobs: (opts) => request('/jobs', opts),
  getJob: (id, opts) => request(`/jobs/${encodeURIComponent(id)}`, opts),
  getJobLogs: (id, offset = 0, opts) =>
    request(`/jobs/${encodeURIComponent(id)}/logs?offset=${offset}`, opts),
  createJob: ({ sourceUrl, query, options }) =>
    request('/jobs', {
      method: 'POST',
      body: { source_url: sourceUrl, query, options: cleanOptions(options) },
    }),
  deleteJob: (id) => request(`/jobs/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  frameUrl: (id) => `${API_BASE}/jobs/${encodeURIComponent(id)}/frame`,
  videoUrl: (id) => `${API_BASE}/jobs/${encodeURIComponent(id)}/video`,
};
