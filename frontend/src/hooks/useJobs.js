import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import { JOBS_POLL_MS } from '../config';
import { isActive } from '../lib/stages';

// Job history. Polls while any job is queued/running so badges stay current.
export function useJobs() {
  const [jobs, setJobs] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const mounted = useRef(true);

  const refresh = useCallback(async () => {
    try {
      const list = await api.listJobs();
      if (!mounted.current) return;
      setJobs(list);
      setError(null);
    } catch (err) {
      if (mounted.current) setError(err);
    } finally {
      if (mounted.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    refresh();
    return () => {
      mounted.current = false;
    };
  }, [refresh]);

  const hasActive = jobs.some(isActive);
  useEffect(() => {
    if (!hasActive) return undefined;
    const timer = setInterval(refresh, JOBS_POLL_MS);
    return () => clearInterval(timer);
  }, [hasActive, refresh]);

  return { jobs, error, loading, refresh };
}
