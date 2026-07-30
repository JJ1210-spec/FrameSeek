// In-memory stand-in for the FastAPI backend, installed as global fetch.
// Each created job walks through `timeline` one step per GET /api/jobs/:id poll.
import { vi } from 'vitest';

export const READY_HEALTH = {
  status: 'ok',
  ready: true,
  version: '1.0.0',
  checks: [
    { name: 'dialogue_frame_finder_optimized (core)', ok: true, detail: '/repo' },
    { name: 'ffmpeg (audio extraction)', ok: true, detail: '/usr/bin/ffmpeg' },
  ],
};

export const SUCCESS_RESULT = {
  status: 'success',
  query: 'My mind rebels at stagnation',
  matched_text: 'My mind rebels at stagnation.',
  similarity_score: 100,
  timestamp_sec: 324.68,
  frame_number: 7785,
  video_metadata: { fps: 23.976, duration_sec: 3261.74, is_vfr: false },
  tier_info: { tier: 'short', model_size: 'tiny.en', total_speech_sec: 95.2 },
  timings: { acquire_video: 3.2, transcribe: 20.5, extract_frame: 0.2, total: 24.1 },
};

export const DEFAULT_TIMELINE = [
  { status: 'queued', stage_history: [], logs: [] },
  { status: 'running', stage_history: ['acquire_video'], logs: ['[INFO] Downloading video ...'] },
  {
    status: 'running',
    stage_history: ['acquire_video', 'get_video_metadata', 'extract_audio', 'run_vad', 'transcribe'],
    logs: ['[INFO] Tier: short  |  model: tiny.en  |  speech: 95.2s'],
  },
  {
    status: 'completed',
    stage_history: [
      'acquire_video', 'get_video_metadata', 'extract_audio', 'run_vad',
      'transcribe', 'match_dialogue', 'extract_frame',
    ],
    logs: ['[INFO] Frame image   : matched_frame.jpg'],
    result: SUCCESS_RESULT,
    has_frame: true,
  },
];

const json = (body, status = 200) =>
  new Response(body === null ? null : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

export function makeJob(overrides = {}) {
  return {
    id: 'job000000001',
    status: 'queued',
    source_url: 'https://www.youtube.com/watch?v=abc',
    query: 'My mind rebels at stagnation',
    options: {},
    created_at: '2026-09-28T10:00:00Z',
    started_at: null,
    finished_at: null,
    current_stage: null,
    stage_history: [],
    queue_position: null,
    result: null,
    error: null,
    has_frame: false,
    ...overrides,
  };
}

export function installFakeBackend({
  health = READY_HEALTH,
  healthStatus = 200,
  jobs = [],
  timeline = DEFAULT_TIMELINE,
  createError = null,
} = {}) {
  const state = {
    jobs: new Map(jobs.map((job) => [job.id, { job, step: timeline.length - 1, logs: [] }])),
    created: [],
    nextId: 1,
  };

  const applyStep = (entry) => {
    const step = timeline[Math.min(entry.step, timeline.length - 1)];
    const { logs = [], ...fields } = step;
    const stageHistory = fields.stage_history || entry.job.stage_history;
    entry.job = {
      ...entry.job,
      ...fields,
      current_stage: fields.status === 'running' ? stageHistory[stageHistory.length - 1] : null,
      started_at: fields.status === 'queued' ? null : '2026-09-28T10:00:01Z',
      finished_at: ['completed', 'failed'].includes(fields.status) ? '2026-09-28T10:00:25Z' : null,
    };
    entry.logs.push(...logs);
  };

  const summary = ({ job }) => ({
    id: job.id,
    status: job.status,
    source_url: job.source_url,
    query: job.query,
    created_at: job.created_at,
    finished_at: job.finished_at,
    result_status: job.result ? job.result.status : null,
    has_frame: job.has_frame,
  });

  const handler = vi.fn(async (url, init = {}) => {
    const method = (init.method || 'GET').toUpperCase();
    const { pathname, searchParams } = new URL(url, 'http://localhost');
    const parts = pathname.replace(/^\/api\//, '').split('/');

    if (pathname === '/api/health') {
      if (healthStatus === 0) throw new TypeError('Failed to fetch');
      return json(health, healthStatus);
    }

    if (pathname === '/api/jobs' && method === 'GET') {
      const list = [...state.jobs.values()].reverse().map(summary);
      return json(list);
    }

    if (pathname === '/api/jobs' && method === 'POST') {
      if (createError) return json({ detail: createError.detail }, createError.status);
      const body = JSON.parse(init.body);
      state.created.push(body);
      const id = `job${String(state.nextId++).padStart(9, '0')}`;
      const entry = {
        job: makeJob({
          id,
          source_url: body.source_url,
          query: body.query,
          options: body.options,
          created_at: new Date().toISOString(),
        }),
        step: 0,
        logs: [],
      };
      applyStep(entry);
      state.jobs.set(id, entry);
      return json(entry.job, 201);
    }

    const [, id, sub] = parts;
    const entry = state.jobs.get(id);
    if (!entry) return json({ detail: `Job '${id}' not found` }, 404);

    if (method === 'DELETE') {
      if (entry.job.status === 'running') return json({ detail: 'Cannot delete a job while it is running' }, 409);
      state.jobs.delete(id);
      return new Response(null, { status: 204 });
    }
    if (sub === 'logs') {
      const offset = Number(searchParams.get('offset') || 0);
      return json({ id, lines: entry.logs.slice(offset), total: entry.logs.length });
    }
    if (!sub) {
      if (entry.step < timeline.length - 1 && state.created.length > 0) {
        entry.step += 1;
        applyStep(entry);
      }
      return json(entry.job);
    }
    return json({ detail: 'Not found' }, 404);
  });

  globalThis.fetch = handler;
  return { fetch: handler, state };
}
