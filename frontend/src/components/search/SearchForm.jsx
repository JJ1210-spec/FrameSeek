import { useState } from 'react';
import { DEFAULT_OPTIONS, EXAMPLE_SEARCH } from '../../config';
import AdvancedOptions from './AdvancedOptions';

export function validateSearch({ sourceUrl, query, options }) {
  const errors = {};
  const url = sourceUrl.trim();
  if (!url) {
    errors.sourceUrl = 'Paste a video URL.';
  } else if (!/^https?:\/\//i.test(url)) {
    errors.sourceUrl = 'The URL must start with http:// or https://';
  } else {
    try {
      new URL(url);
    } catch {
      errors.sourceUrl = 'That does not look like a valid URL.';
    }
  }

  if (!query.trim()) errors.query = 'Type the dialogue line to search for.';
  else if (query.trim().length > 1000) errors.query = 'Keep the dialogue under 1000 characters.';

  const inRange = (value, min, max) => value === '' || (Number(value) >= min && Number(value) <= max);
  if (!inRange(options.match_threshold, 0, 100) || !inRange(options.coarse_threshold, 0, 100)) {
    errors.options = 'Thresholds must be between 0 and 100.';
  } else if (!inRange(options.window_buffer, 1, 600)) {
    errors.options = 'Window buffer must be between 1 and 600 seconds.';
  } else if (!inRange(options.cpu_threads, 1, 64)) {
    errors.options = 'CPU threads must be between 1 and 64.';
  }
  return errors;
}

export default function SearchForm({ onSubmit, urlInputRef }) {
  const [sourceUrl, setSourceUrl] = useState('');
  const [query, setQuery] = useState('');
  const [options, setOptions] = useState(DEFAULT_OPTIONS);
  const [errors, setErrors] = useState({});
  const [submitError, setSubmitError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();
    const found = validateSearch({ sourceUrl, query, options });
    setErrors(found);
    setSubmitError(null);
    if (Object.keys(found).length > 0) return;

    setSubmitting(true);
    try {
      await onSubmit({ sourceUrl: sourceUrl.trim(), query: query.trim(), options });
      setQuery('');
    } catch (err) {
      setSubmitError(err.message || 'Could not start the search.');
    } finally {
      setSubmitting(false);
    }
  };

  const fillExample = () => {
    setSourceUrl(EXAMPLE_SEARCH.sourceUrl);
    setQuery(EXAMPLE_SEARCH.query);
    setErrors({});
  };

  return (
    <form className="search" onSubmit={handleSubmit} noValidate aria-label="New search">
      <div className="search__field">
        <label className="sr-only" htmlFor="sourceUrl">Video URL</label>
        <input
          ref={urlInputRef}
          id="sourceUrl"
          className="input"
          type="url"
          name="sourceUrl"
          placeholder="Video URL — YouTube, Vimeo, ok.ru…"
          autoComplete="off"
          value={sourceUrl}
          onChange={(e) => setSourceUrl(e.target.value)}
          aria-invalid={Boolean(errors.sourceUrl)}
          aria-describedby={errors.sourceUrl ? 'sourceUrl-error' : undefined}
          disabled={submitting}
        />
        {errors.sourceUrl && (
          <span id="sourceUrl-error" className="field-error">{errors.sourceUrl}</span>
        )}
      </div>

      <div className="search__field">
        <label className="sr-only" htmlFor="query">Dialogue</label>
        <input
          id="query"
          className="input"
          type="text"
          name="query"
          placeholder="Dialogue — e.g. My mind rebels at stagnation"
          autoComplete="off"
          maxLength={1200}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-invalid={Boolean(errors.query)}
          aria-describedby={errors.query ? 'query-error' : undefined}
          disabled={submitting}
        />
        {errors.query && <span id="query-error" className="field-error">{errors.query}</span>}
      </div>

      {submitError && <p className="search__alert" role="alert">{submitError}</p>}

      <div className="search__actions">
        <button type="submit" className="btn btn--primary" disabled={submitting}>
          {submitting ? 'Starting…' : 'Find frame'}
        </button>
        <button type="button" className="btn btn--secondary" onClick={fillExample} disabled={submitting}>
          Use example
        </button>
      </div>

      <AdvancedOptions
        options={options}
        onChange={setOptions}
        disabled={submitting}
        error={errors.options}
      />
    </form>
  );
}
