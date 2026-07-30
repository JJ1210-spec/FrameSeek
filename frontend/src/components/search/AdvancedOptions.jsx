import { COOKIE_BROWSERS, LANGUAGES, WHISPER_MODELS } from '../../config';

// Mirrors the pipeline CLI flags (see docs/cli.md → CLI reference).
function Field({ label, children }) {
  return (
    <label className="advanced__field">
      <span className="advanced__label">{label}</span>
      {children}
    </label>
  );
}

export default function AdvancedOptions({ options, onChange, disabled, error }) {
  const set = (key) => (event) => onChange({ ...options, [key]: event.target.value });
  const modelOptions = WHISPER_MODELS.map((m) => <option key={m} value={m}>{m}</option>);
  const number = (key, min, max, placeholder) => (
    <input
      className="input--compact"
      type="number"
      min={min}
      max={max}
      step="1"
      placeholder={placeholder}
      value={options[key]}
      onChange={set(key)}
      disabled={disabled}
    />
  );

  return (
    <details className="advanced" open={Boolean(error)}>
      <summary>Advanced options</summary>
      <div className="card advanced__card">
        <Field label="Model (short/medium videos)">
          <select className="select" value={options.model} onChange={set('model')} disabled={disabled}>
            <option value="">Auto (tiny.en on CPU)</option>
            {modelOptions}
          </select>
        </Field>
        <Field label="Coarse model (long videos)">
          <select className="select" value={options.coarse_model} onChange={set('coarse_model')} disabled={disabled}>
            {modelOptions}
          </select>
        </Field>
        <Field label="Fine model (long videos)">
          <select className="select" value={options.fine_model} onChange={set('fine_model')} disabled={disabled}>
            {modelOptions}
          </select>
        </Field>
        <Field label="Verify model (near misses)">
          <select className="select" value={options.verify_model} onChange={set('verify_model')} disabled={disabled}>
            {modelOptions}
          </select>
        </Field>
        <Field label="Spoken language">
          <select className="select" value={options.language} onChange={set('language')} disabled={disabled}>
            {LANGUAGES.map(([code, name]) => <option key={code} value={code}>{name}</option>)}
          </select>
        </Field>
        <Field label="Match threshold (0–100)">{number('match_threshold', 0, 100)}</Field>
        <Field label="Coarse threshold (0–100)">{number('coarse_threshold', 0, 100)}</Field>
        <Field label="Window buffer (seconds)">{number('window_buffer', 1, 600)}</Field>
        <Field label="CPU threads">{number('cpu_threads', 1, 64, 'Auto')}</Field>
        <Field label="Browser cookies (login-gated videos)">
          <select
            className="select"
            value={options.cookies_from_browser}
            onChange={set('cookies_from_browser')}
            disabled={disabled}
          >
            <option value="">None</option>
            {COOKIE_BROWSERS.map((b) => <option key={b} value={b}>{b}</option>)}
          </select>
        </Field>
        {error && <p className="advanced__error">{error}</p>}
      </div>
    </details>
  );
}
