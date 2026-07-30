import { useState } from 'react';
import { api } from '../../api/client';
import { useJob } from '../../hooks/useJob';
import { formatDateTime, hostOf } from '../../lib/format';
import StatusBadge from '../common/StatusBadge';
import JobProgress from './JobProgress';
import LogViewer from './LogViewer';
import ResultView from './ResultView';

export default function JobDetail({ jobId, onDeleted }) {
  const { job, logs, error, loading } = useJob(jobId);
  const [deleteError, setDeleteError] = useState(null);

  if (loading && !job) {
    return <p className="job-placeholder">Loading search…</p>;
  }

  if (!job) {
    const message = error && error.status === 404
      ? 'This search no longer exists.'
      : `Could not load this search: ${error ? error.message : 'unknown error'}`;
    return <p className="job-placeholder" role="alert">{message}</p>;
  }

  const handleDelete = async () => {
    if (!window.confirm('Delete this search and its files?')) return;
    try {
      await api.deleteJob(job.id);
      onDeleted(job.id);
    } catch (err) {
      setDeleteError(err.message);
    }
  };

  return (
    <article className="job" aria-label="Search details">
      <header className="job__header">
        <StatusBadge status={job.status} resultStatus={job.result && job.result.status} />
        <h2 className="t-display-lg">“{job.query}”</h2>
        <a className="job__source" href={job.source_url} target="_blank" rel="noreferrer">
          {hostOf(job.source_url)} — {job.source_url}
        </a>
        <div className="job__meta t-muted">
          <span>{formatDateTime(job.created_at)}</span>
          {job.status !== 'running' && (
            <button type="button" className="btn-link btn-link--danger" onClick={handleDelete}>
              Delete
            </button>
          )}
        </div>
        {deleteError && <p className="job__crash">{deleteError}</p>}
        {error && <p className="t-caption t-muted">Connection problem, retrying… ({error.message})</p>}
      </header>

      <JobProgress job={job} />

      {job.status === 'failed' && (
        <div className="job__crash" role="alert">
          <strong>The job crashed.</strong>
          <pre>{job.error}</pre>
        </div>
      )}

      {job.status === 'completed' && <ResultView job={job} />}

      <LogViewer lines={logs} defaultOpen={job.status === 'failed'} />
    </article>
  );
}
