import { api } from '../../api/client';
import { formatDateTime, hostOf } from '../../lib/format';
import StatusBadge from '../common/StatusBadge';

function Thumbnail({ job }) {
  if (job.has_frame) {
    return <img src={api.frameUrl(job.id)} alt="" loading="lazy" />;
  }
  const label = job.status === 'queued' || job.status === 'running' ? 'In progress…' : 'No frame';
  return <span>{label}</span>;
}

export default function JobHistory({ jobs, selectedId, onSelect, loading, error }) {
  return (
    <section id="history" className="tile tile--parchment" aria-label="Search history">
      <div className="tile__inner tile__inner--wide">
        <header className="tile__header">
          <h2 className="t-display-md">Recent searches.</h2>
          {jobs.length > 0 && (
            <p className="t-caption t-muted">{jobs.length} saved on this machine</p>
          )}
        </header>

        {error && <p className="history__empty">Could not load history: {error.message}</p>}
        {!error && loading && jobs.length === 0 && <p className="history__empty">Loading…</p>}
        {!error && !loading && jobs.length === 0 && (
          <p className="history__empty">No searches yet. Your results will appear here.</p>
        )}

        <ul className="history__grid">
          {jobs.map((job) => {
            const selected = job.id === selectedId;
            return (
              <li key={job.id}>
                <button
                  type="button"
                  className={`card history-card${selected ? ' history-card--selected' : ''}`}
                  onClick={() => onSelect(job.id)}
                  aria-current={selected ? 'true' : undefined}
                >
                  <span className="history-card__thumb"><Thumbnail job={job} /></span>
                  <span className="history-card__body">
                    <StatusBadge status={job.status} resultStatus={job.result_status} />
                    <span className="t-body-strong history-card__query">“{job.query}”</span>
                    <span className="history-card__meta t-caption">
                      <span>{hostOf(job.source_url)}</span>
                      <span>{formatDateTime(job.created_at)}</span>
                    </span>
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      </div>
    </section>
  );
}
