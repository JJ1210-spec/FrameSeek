// Notice strip driven by GET /api/health: backend down, or dependencies missing.
export default function SystemStatus({ health, error, loading, onRetry }) {
  if (loading && !health && !error) return null;

  if (error) {
    return (
      <div className="notice notice--error" role="alert">
        <div className="notice__inner">
          <div>
            <strong className="notice__title">Backend not reachable.</strong> Start it with{' '}
            <code>cd backend &amp;&amp; uvicorn app.main:app --port 8000</code>, then retry.
          </div>
          <button type="button" className="btn btn--secondary btn--small" onClick={onRetry}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (health && !health.ready) {
    const missing = health.checks.filter((check) => !check.ok);
    return (
      <div className="notice notice--error" role="alert">
        <div className="notice__inner">
          <div>
            <strong className="notice__title">Some pipeline dependencies are missing.</strong>{' '}
            Searches will fail until they are installed:
            <ul className="notice__list">
              {missing.map((check) => (
                <li key={check.name}>
                  <strong>{check.name}</strong> — {check.detail}
                </li>
              ))}
            </ul>
          </div>
          <button type="button" className="btn btn--secondary btn--small" onClick={onRetry}>
            Re-check
          </button>
        </div>
      </div>
    );
  }

  return null;
}
