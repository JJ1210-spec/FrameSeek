// Full user flow against the in-memory fake backend.
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import App from './App';
import { SUCCESS_RESULT, installFakeBackend, makeJob } from './test/fakeBackend';

async function search(user, url, query) {
  await user.type(screen.getByLabelText('Video URL'), url);
  await user.type(screen.getByLabelText('Dialogue'), query);
  await user.click(screen.getByRole('button', { name: 'Find frame' }));
}

describe('App', () => {
  it('runs a search from submission to the matched frame', async () => {
    const backend = installFakeBackend();
    const user = userEvent.setup();
    render(<App />);

    expect(await screen.findByText('Pipeline ready')).toBeInTheDocument();
    expect(screen.getByText(/No searches yet/)).toBeInTheDocument();

    await search(user, 'https://www.youtube.com/watch?v=abc', 'My mind rebels at stagnation');

    expect(backend.state.created).toEqual([
      {
        source_url: 'https://www.youtube.com/watch?v=abc',
        query: 'My mind rebels at stagnation',
        options: {
          coarse_model: 'tiny.en', fine_model: 'tiny.en', verify_model: 'base.en',
          match_threshold: 80, coarse_threshold: 50, window_buffer: 45,
        },
      },
    ]);

    const detail = await screen.findByRole('article', { name: 'Search details' });
    expect(within(detail).getByRole('heading', { name: '“My mind rebels at stagnation”' })).toBeInTheDocument();

    const img = await within(detail).findByRole('img', { name: 'Matched frame at 05:24.680' });
    expect(img).toHaveAttribute('src', '/api/jobs/job000000001/frame');
    expect(within(detail).getByText('Exact match')).toBeInTheDocument();
    expect(within(detail).getByTestId('log-output')).toHaveTextContent('[INFO] Downloading video ...');
    expect(window.location.hash).toBe('#/jobs/job000000001');

    const history = screen.getByRole('region', { name: 'Search history' });
    await waitFor(() => expect(within(history).getByText('Exact match')).toBeInTheDocument());
  });

  it('shows backend validation errors on the form', async () => {
    installFakeBackend({
      createError: { status: 422, detail: [{ loc: ['body', 'source_url'], msg: 'Value error, unsupported' }] },
    });
    const user = userEvent.setup();
    render(<App />);
    await search(user, 'https://example.com/v', 'hello');

    expect(await screen.findByText('source_url: unsupported')).toBeInTheDocument();
    expect(screen.queryByRole('article', { name: 'Search details' })).not.toBeInTheDocument();
  });

  it('warns when the backend is down', async () => {
    installFakeBackend({ healthStatus: 0 });
    render(<App />);
    expect(await screen.findByText('Backend not reachable.')).toBeInTheDocument();
  });

  it('opens a job from history, restores it from the URL hash and deletes it', async () => {
    const done = makeJob({
      id: 'old000000001',
      status: 'completed',
      query: 'The game is afoot',
      result: { ...SUCCESS_RESULT, query: 'The game is afoot' },
      has_frame: true,
      stage_history: ['acquire_video', 'get_video_metadata', 'extract_audio', 'run_vad', 'transcribe', 'match_dialogue', 'extract_frame'],
    });
    installFakeBackend({ jobs: [done] });
    window.history.replaceState(null, '', '/#/jobs/old000000001');
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    const user = userEvent.setup();
    render(<App />);

    const detail = await screen.findByRole('article', { name: 'Search details' });
    expect(await within(detail).findByRole('heading', { name: '“The game is afoot”' })).toBeInTheDocument();

    await user.click(within(detail).getByRole('button', { name: 'Delete' }));
    await waitFor(() => expect(screen.queryByRole('article', { name: 'Search details' })).not.toBeInTheDocument());
    expect(window.location.hash).toBe('');
    await waitFor(() => expect(screen.getByText(/No searches yet/)).toBeInTheDocument());
  });

  it('shows a crashed job with its error and open log', async () => {
    installFakeBackend({
      timeline: [
        { status: 'running', stage_history: ['acquire_video'], logs: ['[INFO] Loading Silero VAD ...'] },
        { status: 'failed', stage_history: ['acquire_video'], error: 'ModuleNotFoundError: No module named torch', logs: ['Traceback (most recent call last):'] },
      ],
    });
    const user = userEvent.setup();
    render(<App />);
    await search(user, 'https://ok.ru/video/1', 'hello');

    const detail = await screen.findByRole('article', { name: 'Search details' });
    expect(await within(detail).findByText('The job crashed.')).toBeInTheDocument();
    expect(within(detail).getByText(/No module named torch/)).toBeInTheDocument();
    expect(within(detail).getByText('Download video').closest('li').dataset.state).toBe('failed');
    expect(within(detail).getByTestId('log-output')).toHaveTextContent('Traceback');
  });
});

describe('App navigation', () => {
  it('"New search" focuses the URL field', async () => {
    installFakeBackend();
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole('button', { name: 'New search' }));
    expect(screen.getByLabelText('Video URL')).toHaveFocus();
  });
});
