import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import JobProgress from './JobProgress';
import { makeJob } from '../../test/fakeBackend';

const stateOf = (label) => screen.getByText(label).closest('li').dataset.state;

describe('JobProgress', () => {
  it('shows queue position while queued', () => {
    render(<JobProgress job={makeJob({ status: 'queued', queue_position: 2 })} />);
    expect(screen.getByText('Waiting in queue — 2 jobs ahead.')).toBeInTheDocument();
    expect(stateOf('Download video')).toBe('pending');
  });

  it('shows the active stage and its description while running', () => {
    render(
      <JobProgress
        job={makeJob({
          status: 'running',
          started_at: new Date(Date.now() - 5000).toISOString(),
          current_stage: 'run_vad',
          stage_history: ['acquire_video', 'get_video_metadata', 'extract_audio', 'run_vad'],
        })}
      />,
    );
    expect(stateOf('Extract audio')).toBe('done');
    expect(stateOf('Speech & language')).toBe('active');
    expect(stateOf('Transcribe')).toBe('pending');
    expect(screen.getByText('Finding speech with Silero VAD…')).toBeInTheDocument();
    expect(screen.getByText(/Elapsed/)).toBeInTheDocument();
  });

  it('shows total time when finished', () => {
    render(
      <JobProgress
        job={makeJob({
          status: 'completed',
          started_at: '2026-09-28T10:00:00Z',
          finished_at: '2026-09-28T10:00:32.9Z',
          stage_history: ['acquire_video', 'get_video_metadata', 'extract_audio', 'run_vad', 'transcribe', 'match_dialogue', 'extract_frame'],
          result: { status: 'success' },
        })}
      />,
    );
    expect(screen.getByText('Took 32.9 s')).toBeInTheDocument();
    expect(stateOf('Extract frame')).toBe('done');
    expect(screen.queryByText('Fine pass')).not.toBeInTheDocument();
  });
});
