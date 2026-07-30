import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import SearchForm, { validateSearch } from './SearchForm';
import { DEFAULT_OPTIONS } from '../../config';

const setup = (onSubmit = vi.fn().mockResolvedValue(undefined)) => {
  const user = userEvent.setup();
  render(<SearchForm onSubmit={onSubmit} />);
  return {
    user,
    onSubmit,
    url: screen.getByLabelText('Video URL'),
    query: screen.getByLabelText('Dialogue'),
    submit: screen.getByRole('button', { name: 'Find frame' }),
  };
};

describe('SearchForm', () => {
  it('requires a URL and a dialogue line', async () => {
    const { user, submit, onSubmit } = setup();
    await user.click(submit);

    expect(screen.getByText('Paste a video URL.')).toBeInTheDocument();
    expect(screen.getByText('Type the dialogue line to search for.')).toBeInTheDocument();
    expect(screen.getByLabelText('Video URL')).toHaveAttribute('aria-invalid', 'true');
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('rejects non-http URLs', async () => {
    const { user, url, query, submit, onSubmit } = setup();
    await user.type(url, 'C:/videos/movie.mp4');
    await user.type(query, 'hello');
    await user.click(submit);

    expect(screen.getByText('The URL must start with http:// or https://')).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('submits trimmed values with default options and clears the dialogue', async () => {
    const { user, url, query, submit, onSubmit } = setup();
    await user.type(url, '  https://www.youtube.com/watch?v=abc  ');
    await user.type(query, '  Elementary, my dear Watson ');
    await user.click(submit);

    expect(onSubmit).toHaveBeenCalledWith({
      sourceUrl: 'https://www.youtube.com/watch?v=abc',
      query: 'Elementary, my dear Watson',
      options: DEFAULT_OPTIONS,
    });
    expect(query).toHaveValue('');
    expect(url).toHaveValue('https://www.youtube.com/watch?v=abc'); // URL kept for the next search
  });

  it('fills in the example search', async () => {
    const { user, url, query } = setup();
    await user.click(screen.getByRole('button', { name: 'Use example' }));
    expect(url).toHaveValue('https://youtu.be/atOgj_ZaO7M');
    expect(query).toHaveValue("I'm always angry");
  });

  it('sends advanced options', async () => {
    const { user, url, query, submit, onSubmit } = setup();
    await user.click(screen.getByText('Advanced options'));
    await user.selectOptions(screen.getByLabelText('Fine model (long videos)'), 'small.en');
    const threshold = screen.getByLabelText('Match threshold (0–100)');
    await user.clear(threshold);
    await user.type(threshold, '70');
    await user.selectOptions(screen.getByLabelText('Browser cookies (login-gated videos)'), 'firefox');
    await user.selectOptions(screen.getByLabelText('Spoken language'), 'ta');
    await user.selectOptions(screen.getByLabelText('Verify model (near misses)'), 'small.en');
    await user.type(url, 'https://ok.ru/video/1');
    await user.type(query, 'hi');
    await user.click(submit);

    expect(onSubmit.mock.calls[0][0].options).toMatchObject({
      fine_model: 'small.en',
      match_threshold: '70',
      cookies_from_browser: 'firefox',
      language: 'ta',
      verify_model: 'small.en',
    });
  });

  it('shows the server error and keeps the input when submission fails', async () => {
    const onSubmit = vi.fn().mockRejectedValue(new Error('source_url: invalid'));
    const { user, url, query, submit } = setup(onSubmit);
    await user.type(url, 'https://ok.ru/video/1');
    await user.type(query, 'hi');
    await user.click(submit);

    expect(await screen.findByRole('alert')).toHaveTextContent('source_url: invalid');
    expect(query).toHaveValue('hi');
    expect(submit).toBeEnabled();
  });

  it('disables the form while submitting', async () => {
    let resolve;
    const onSubmit = vi.fn(() => new Promise((r) => { resolve = r; }));
    const { user, url, query } = setup(onSubmit);
    await user.type(url, 'https://ok.ru/video/1');
    await user.type(query, 'hi');
    await user.click(screen.getByRole('button', { name: 'Find frame' }));

    expect(screen.getByRole('button', { name: 'Starting…' })).toBeDisabled();
    expect(url).toBeDisabled();
    resolve();
    expect(await screen.findByRole('button', { name: 'Find frame' })).toBeEnabled();
  });
});

describe('validateSearch', () => {
  const valid = { sourceUrl: 'https://ok.ru/v/1', query: 'hi', options: DEFAULT_OPTIONS };

  it('accepts a valid search', () => {
    expect(validateSearch(valid)).toEqual({});
  });

  it.each([
    [{ match_threshold: 101 }, 'Thresholds must be between 0 and 100.'],
    [{ coarse_threshold: -5 }, 'Thresholds must be between 0 and 100.'],
    [{ window_buffer: 0 }, 'Window buffer must be between 1 and 600 seconds.'],
    [{ cpu_threads: 65 }, 'CPU threads must be between 1 and 64.'],
  ])('rejects bad options %o', (bad, message) => {
    expect(validateSearch({ ...valid, options: { ...DEFAULT_OPTIONS, ...bad } }).options).toBe(message);
  });

  it('rejects malformed URLs and very long dialogue', () => {
    expect(validateSearch({ ...valid, sourceUrl: 'https://' }).sourceUrl).toBe('That does not look like a valid URL.');
    expect(validateSearch({ ...valid, query: 'x'.repeat(1001) }).query).toMatch(/under 1000/);
  });
});
