const pad = (n, width = 2) => String(n).padStart(width, '0');

// 324.68 → "05:24.680", 3725.5 → "1:02:05.500"
export function formatTimestamp(seconds) {
  if (seconds === null || seconds === undefined || Number.isNaN(Number(seconds))) return '—';
  const totalMs = Math.round(Number(seconds) * 1000);
  const ms = totalMs % 1000;
  const totalSec = Math.floor(totalMs / 1000);
  const s = totalSec % 60;
  const m = Math.floor(totalSec / 60) % 60;
  const h = Math.floor(totalSec / 3600);
  const base = h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`;
  return `${base}.${pad(ms, 3)}`;
}

// 0.42 → "0.42 s", 12.345 → "12.3 s", 323.89 → "5 min 24 s"
export function formatDuration(seconds) {
  if (seconds === null || seconds === undefined || Number.isNaN(Number(seconds))) return '—';
  const value = Number(seconds);
  if (value < 1) return `${value.toFixed(2)} s`;
  if (value < 60) return `${value.toFixed(1)} s`;
  const minutes = Math.floor(value / 60);
  const rest = Math.round(value - minutes * 60);
  return rest === 0 ? `${minutes} min` : `${minutes} min ${rest} s`;
}

export function elapsedSeconds(startIso, endIso, now = Date.now()) {
  if (!startIso) return null;
  const start = new Date(startIso).getTime();
  const end = endIso ? new Date(endIso).getTime() : now;
  return Math.max(0, (end - start) / 1000);
}

export function formatDateTime(iso) {
  if (!iso) return '—';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString(undefined, {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  });
}

export function hostOf(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url;
  }
}

export function formatScore(score) {
  if (score === null || score === undefined) return '—';
  return `${Number(score).toFixed(1)} / 100`;
}
