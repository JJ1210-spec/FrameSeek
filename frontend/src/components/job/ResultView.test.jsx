import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import ResultView from './ResultView';
import { SUCCESS_RESULT, makeJob } from '../../test/fakeBackend';

const completed = (result, extra = {}) =>
  makeJob({ id: 'abc', status: 'completed', result, has_frame: true, ...extra });

describe('ResultView', () => {
  it('renders the matched frame and key numbers', () => {
    render(<ResultView job={completed(SUCCESS_RESULT)} />);

    const img = screen.getByRole('img', { name: 'Matched frame at 05:24.680' });
    expect(img).toHaveAttribute('src', '/api/jobs/abc/frame');
    expect(screen.getByText('Frame #7785 at 05:24.680')).toBeInTheDocument();

    const stats = screen.getByText('Timestamp').closest('dl');
    expect(within(stats).getByText('05:24.680')).toBeInTheDocument();
    expect(within(stats).getByText('7785')).toBeInTheDocument();
    expect(within(stats).getByText('100.0 / 100')).toBeInTheDocument();
    expect(within(stats).getByText('short · tiny.en')).toBeInTheDocument();

    expect(screen.getByText('My mind rebels at stagnation.')).toBeInTheDocument();
    expect(screen.getByTestId('result-video')).toHaveAttribute('src', '/api/jobs/abc/video#t=324.68');
    expect(screen.getByText(/23\.976 fps/)).toBeInTheDocument();
  });

  it('shows the detected language and the passes that ran', () => {
    const result = {
      ...SUCCESS_RESULT,
      language: { code: 'en', name: 'English', probability: 0.66 },
      tier_info: { ...SUCCESS_RESULT.tier_info, passes: ['full audio · tiny.en', 'verify ±45 s · base.en'] },
    };
    render(<ResultView job={completed(result)} />);
    expect(screen.getByTestId('search-details')).toHaveTextContent(
      'Language: English (66%) · Passes: full audio · tiny.en → verify ±45 s · base.en',
    );
  });

  it('explains non-English audio on a no-match', () => {
    render(
      <ResultView
        job={completed(
          {
            status: 'no_match', query: 'i am always angry', closest_text: 'நல்லா இரு போ',
            similarity_score: 12, reason: 'The audio is Tamil — type the dialogue in that language.',
            language: { code: 'ta', name: 'Tamil', probability: 0.65 }, timings: {},
          },
          { has_frame: false },
        )}
      />,
    );
    expect(screen.getByText(/The audio is Tamil/)).toBeInTheDocument();
    expect(screen.getByTestId('search-details')).toHaveTextContent('Language: Tamil (65%)');
  });

  it('shows the stage timing breakdown', () => {
    render(<ResultView job={completed(SUCCESS_RESULT)} />);
    expect(screen.getByText('Stage timings — total 24.1 s')).toBeInTheDocument();
    expect(screen.getByText('transcribe')).toBeInTheDocument();
    expect(screen.getByText('20.5 s')).toBeInTheDocument();
  });

  it('shows the note on a partial match', () => {
    const result = { ...SUCCESS_RESULT, status: 'partial_match', similarity_score: 78.87, note: 'Fine-pass failed; using coarse timestamp.' };
    render(<ResultView job={completed(result)} />);
    expect(screen.getByText('78.9 / 100')).toBeInTheDocument();
    expect(screen.getByText('Fine-pass failed; using coarse timestamp.')).toBeInTheDocument();
  });

  it('seeks the video when "Jump to" is clicked', async () => {
    const user = userEvent.setup();
    render(<ResultView job={completed(SUCCESS_RESULT)} />);
    const video = screen.getByTestId('result-video');
    video.play = vi.fn().mockResolvedValue(undefined);

    await user.click(screen.getByRole('button', { name: 'Jump to 05:24.680' }));
    expect(video.currentTime).toBeCloseTo(324.68);
    expect(video.play).toHaveBeenCalled();
  });

  it('explains a no-match result with the closest text', () => {
    render(
      <ResultView
        job={completed(
          { status: 'no_match', query: 'x', closest_text: 'Something else', similarity_score: 41.2, timings: { total: 3 } },
          { has_frame: false },
        )}
      />,
    );
    expect(screen.getByText('That line wasn’t found in the video.')).toBeInTheDocument();
    expect(screen.getByText('Something else')).toBeInTheDocument();
    expect(screen.getByText('Similarity 41.2 / 100')).toBeInTheDocument();
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
  });

  it('shows pipeline errors with their reason', () => {
    render(<ResultView job={completed({ status: 'download_failed', reason: 'HTTP Error 403: Forbidden', timings: {} }, { has_frame: false })} />);
    const alert = screen.getByRole('alert');
    expect(alert).toHaveTextContent('The pipeline stopped: download failed.');
    expect(alert).toHaveTextContent('HTTP Error 403: Forbidden');
  });

  it('downloads result.json', async () => {
    const user = userEvent.setup();
    URL.createObjectURL = vi.fn(() => 'blob:result');
    URL.revokeObjectURL = vi.fn();
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});

    render(<ResultView job={completed(SUCCESS_RESULT)} />);
    await user.click(screen.getByRole('button', { name: 'Download result.json' }));

    expect(URL.createObjectURL).toHaveBeenCalledWith(expect.any(Blob));
    expect(click).toHaveBeenCalled();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:result');
  });

  it('renders nothing without a result', () => {
    const { container } = render(<ResultView job={makeJob({ status: 'completed' })} />);
    expect(container).toBeEmptyDOMElement();
  });
});
