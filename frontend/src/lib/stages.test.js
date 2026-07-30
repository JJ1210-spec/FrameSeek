import { describe, expect, it } from 'vitest';
import { buildSteps, isActive, phaseIndexOf, statusDisplay } from './stages';

const SHORT = ['acquire_video', 'get_video_metadata', 'extract_audio', 'run_vad', 'transcribe', 'match_dialogue', 'extract_frame'];
const LONG = [
  'acquire_video', 'get_video_metadata', 'extract_audio', 'run_vad',
  'transcribe_coarse', 'match_dialogue_coarse', 'extract_audio_slice',
  'transcribe_fine', 'match_dialogue_fine', 'extract_frame',
];

const states = (job) => Object.fromEntries(buildSteps(job).map((s) => [s.key, s.state]));

describe('buildSteps', () => {
  it('shows every step pending while queued, without the fine pass', () => {
    const steps = buildSteps({ status: 'queued', stage_history: [] });
    expect(steps.map((s) => s.key)).toEqual(['download', 'metadata', 'audio', 'vad', 'transcribe', 'match', 'frame']);
    expect(steps.every((s) => s.state === 'pending')).toBe(true);
  });

  it('marks earlier steps done and the current one active while running', () => {
    expect(states({ status: 'running', stage_history: SHORT.slice(0, 5) })).toEqual({
      download: 'done', metadata: 'done', audio: 'done', vad: 'done',
      transcribe: 'active', match: 'pending', frame: 'pending',
    });
  });

  it('adds the fine-pass step for long videos and keeps order monotonic', () => {
    const job = { status: 'running', stage_history: LONG.slice(0, 7) };
    const steps = buildSteps(job);
    expect(steps.map((s) => s.key)).toContain('refine');
    expect(states(job)).toMatchObject({ transcribe: 'done', match: 'done', refine: 'active', frame: 'pending' });
  });

  it('maps the full-audio retry and near-miss verification onto existing steps', () => {
    const history = [
      'acquire_video', 'get_video_metadata', 'extract_audio', 'run_vad', 'detect_language',
      'transcribe', 'match_dialogue', 'transcribe_full', 'match_dialogue_full',
      'extract_audio_slice_verify', 'transcribe_verify',
    ];
    const job = { status: 'running', stage_history: history };
    expect(states(job)).toMatchObject({ vad: 'done', match: 'done', refine: 'active', frame: 'pending' });
    expect(phaseIndexOf('detect_language')).toBe(phaseIndexOf('run_vad'));
    expect(phaseIndexOf('transcribe_full')).toBe(phaseIndexOf('transcribe'));
  });

  it('marks everything done on a successful result', () => {
    const job = { status: 'completed', stage_history: SHORT, result: { status: 'partial_match' } };
    expect(buildSteps(job).every((s) => s.state === 'done')).toBe(true);
  });

  it('skips the frame step when no match was found', () => {
    const job = { status: 'completed', stage_history: SHORT.slice(0, 6), result: { status: 'no_match' } };
    expect(states(job)).toMatchObject({ match: 'done', frame: 'skipped' });
  });

  it('marks the failing stage for a pipeline error result', () => {
    const job = { status: 'completed', stage_history: ['acquire_video'], result: { status: 'download_failed' } };
    expect(states(job)).toMatchObject({ download: 'failed', metadata: 'skipped', frame: 'skipped' });
  });

  it('marks the failing stage for a crashed job', () => {
    const job = { status: 'failed', stage_history: SHORT.slice(0, 4), result: null };
    expect(states(job)).toMatchObject({ audio: 'done', vad: 'failed', transcribe: 'skipped' });
  });
});

describe('statusDisplay', () => {
  it.each([
    ['queued', null, 'Queued', 'neutral'],
    ['running', null, 'Running', 'progress'],
    ['failed', null, 'Error', 'danger'],
    ['completed', 'success', 'Exact match', 'success'],
    ['completed', 'partial_match', 'Close match', 'info'],
    ['completed', 'no_match', 'No match', 'warning'],
    ['completed', 'download_failed', 'Download failed', 'danger'],
    ['completed', 'something_new', 'something_new', 'danger'],
  ])('%s/%s → %s', (status, result, label, tone) => {
    expect(statusDisplay(status, result)).toEqual({ label, tone });
  });
});

describe('helpers', () => {
  it('finds the phase of a stage', () => {
    expect(phaseIndexOf('acquire_video')).toBe(0);
    expect(phaseIndexOf('transcribe_coarse')).toBe(phaseIndexOf('transcribe'));
    expect(phaseIndexOf('nope')).toBe(-1);
  });

  it('knows which jobs are active', () => {
    expect(isActive({ status: 'queued' })).toBe(true);
    expect(isActive({ status: 'running' })).toBe(true);
    expect(isActive({ status: 'completed' })).toBe(false);
    expect(isActive(null)).toBe(false);
  });
});
