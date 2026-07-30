import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { JOB_POLL_MS } from '../config';
import { isActive } from '../lib/stages';

const EMPTY = { job: null, logs: [], error: null, loading: true };

/**
 * Live view of one job: polls the job + incremental logs until it finishes.
 * Logs are fetched *after* the job, so the final poll always has every line.
 */
export function useJob(jobId) {
  const [state, setState] = useState(EMPTY);

  useEffect(() => {
    if (!jobId) {
      setState({ ...EMPTY, loading: false });
      return undefined;
    }

    let cancelled = false;
    let timer = null;
    let logOffset = 0;
    setState(EMPTY);

    const poll = async () => {
      try {
        const job = await api.getJob(jobId);
        const { lines, total } = await api.getJobLogs(jobId, logOffset);
        if (cancelled) return;
        logOffset = total;
        setState((prev) => ({
          job,
          logs: lines.length ? [...prev.logs, ...lines] : prev.logs,
          error: null,
          loading: false,
        }));
        if (isActive(job)) timer = setTimeout(poll, JOB_POLL_MS);
      } catch (err) {
        if (cancelled) return;
        setState((prev) => ({ ...prev, error: err, loading: false }));
        // Keep retrying transient failures (e.g. backend restarting), but not 404s.
        if (err.status !== 404) timer = setTimeout(poll, JOB_POLL_MS * 3);
      }
    };

    poll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [jobId]);

  return state;
}
