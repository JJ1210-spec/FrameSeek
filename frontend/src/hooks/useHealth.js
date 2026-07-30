import { useCallback, useEffect, useState } from 'react';
import { api } from '../api/client';

export function useHealth() {
  const [health, setHealth] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setHealth(await api.health());
      setError(null);
    } catch (err) {
      setHealth(null);
      setError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { health, error, loading, refresh };
}
