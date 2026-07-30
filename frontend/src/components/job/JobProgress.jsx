import { useEffect, useState } from 'react';
import { elapsedSeconds, formatDuration } from '../../lib/format';
import { STAGE_DESCRIPTIONS, buildSteps } from '../../lib/stages';

const ICON_PATHS = {
  done: 'M3.5 8.5l3 3 6-7',
  failed: 'M4.5 4.5l7 7M11.5 4.5l-7 7',
  skipped: 'M4.5 8h7',
};

function StepIcon({ state }) {
  const d = ICON_PATHS[state];
  if (!d) return null;
  return (
    <svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true">
      <path d={d} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function useNow(active) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!active) return undefined;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [active]);
  return now;
}

export default function JobProgress({ job }) {
  const running = job.status === 'running';
  const now = useNow(running);
  const steps = buildSteps(job);
  const elapsed = elapsedSeconds(job.started_at, job.finished_at, now);

  let caption = null;
  if (job.status === 'queued') {
    caption = job.queue_position
      ? `Waiting in queue — ${job.queue_position} job${job.queue_position === 1 ? '' : 's'} ahead.`
      : 'Waiting to start…';
  } else if (running) {
    caption = STAGE_DESCRIPTIONS[job.current_stage] || 'Starting the pipeline…';
  }

  return (
    <section className="progress" aria-label="Pipeline progress">
      <ol className="steps">
        {steps.map((step) => (
          <li key={step.key} className={`step step--${step.state}`} data-state={step.state}>
            <span className="step__dot" aria-hidden="true"><StepIcon state={step.state} /></span>
            <span className="step__label">{step.label}</span>
          </li>
        ))}
      </ol>
      {caption && (
        <p className="progress__caption" aria-live="polite">
          {running && <span className="spinner" aria-hidden="true" />}
          {caption}
        </p>
      )}
      {elapsed !== null && (
        <p className="progress__caption">
          {running ? 'Elapsed' : 'Took'} {formatDuration(elapsed)}
        </p>
      )}
    </section>
  );
}
