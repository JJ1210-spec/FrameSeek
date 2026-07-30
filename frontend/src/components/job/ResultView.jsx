import { useRef } from 'react';
import { api } from '../../api/client';
import { formatDuration, formatScore, formatTimestamp } from '../../lib/format';
import { SUCCESS_STATUSES } from '../../lib/stages';

function downloadJson(filename, data) {
  if (typeof URL.createObjectURL !== 'function') return;
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const href = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = href;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(href);
}

function Stat({ label, value, hint }) {
  return (
    <div className="stat">
      <dt className="stat__label">{label}</dt>
      <dd className="stat__value">{value}</dd>
      {hint && <dd className="stat__hint">{hint}</dd>}
    </div>
  );
}

function describeLanguage(language) {
  if (!language) return null;
  const name = language.name || language.code;
  return language.probability ? `${name} (${Math.round(language.probability * 100)}%)` : name;
}

function SearchDetails({ result }) {
  const language = describeLanguage(result.language);
  const passes = (result.tier_info && result.tier_info.passes) || [];
  if (!language && passes.length === 0) return null;
  return (
    <p className="video-meta" data-testid="search-details">
      {language && <>Language: {language}</>}
      {language && passes.length > 0 && ' · '}
      {passes.length > 0 && <>Passes: {passes.join(' → ')}</>}
    </p>
  );
}

function Timings({ timings }) {
  const entries = Object.entries(timings || {}).filter(([k, v]) => k !== 'total' && v !== null);
  if (!entries.length) return null;
  const max = Math.max(...entries.map(([, v]) => v), 0.001);
  return (
    <div className="panel">
      <h3 className="section-label">Stage timings — total {formatDuration(timings.total)}</h3>
      <ul className="timings__list">
        {entries.map(([stage, seconds]) => (
          <li key={stage} className="timings__row">
            <span className="timings__name">{stage}</span>
            <span className="timings__bar">
              <span style={{ width: `${Math.max(2, (seconds / max) * 100)}%` }} />
            </span>
            <span className="timings__value">{formatDuration(seconds)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function MatchResult({ job, result }) {
  const videoRef = useRef(null);
  const ts = result.timestamp_sec;
  const jumpToMatch = () => {
    const video = videoRef.current;
    if (!video) return;
    video.currentTime = ts;
    const played = video.play && video.play();
    if (played && played.catch) played.catch(() => {});
  };

  return (
    <>
      <figure className="frame">
        {job.has_frame ? (
          <img src={api.frameUrl(job.id)} alt={`Matched frame at ${formatTimestamp(ts)}`} />
        ) : (
          <div className="frame__missing">Frame image unavailable</div>
        )}
        <figcaption>Frame #{result.frame_number} at {formatTimestamp(ts)}</figcaption>
      </figure>

      <dl className="stats">
        <Stat label="Timestamp" value={formatTimestamp(ts)} hint={`${ts} s`} />
        <Stat label="Frame number" value={result.frame_number} />
        <Stat label="Similarity" value={formatScore(result.similarity_score)} />
        {result.tier_info && (
          <Stat
            label="Tier / model"
            value={`${result.tier_info.tier} · ${result.tier_info.model_size}`}
            hint={`${formatDuration(result.tier_info.total_speech_sec)} of speech`}
          />
        )}
      </dl>

      <div className="compare">
        <div>
          <h3 className="compare__label">You searched for</h3>
          <blockquote>{result.query}</blockquote>
        </div>
        <div>
          <h3 className="compare__label">Heard in the video</h3>
          <blockquote className="compare__heard">{result.matched_text}</blockquote>
        </div>
      </div>

      {result.note && <p className="note">{result.note}</p>}

      <div className="player">
        <div className="player__header">
          <h3 className="section-label">Verify in the video</h3>
          <button type="button" className="btn btn--secondary btn--small" onClick={jumpToMatch}>
            Jump to {formatTimestamp(ts)}
          </button>
        </div>
        <video
          ref={videoRef}
          controls
          preload="metadata"
          src={`${api.videoUrl(job.id)}#t=${ts}`}
          data-testid="result-video"
        />
        {result.video_metadata && (
          <p className="video-meta">
            {Number(result.video_metadata.fps).toFixed(3)} fps ·{' '}
            {formatDuration(result.video_metadata.duration_sec)}
            {result.video_metadata.is_vfr ? ' · variable frame rate (frame math uses average fps)' : ''}
          </p>
        )}
        <SearchDetails result={result} />
      </div>
    </>
  );
}

function NoMatch({ result }) {
  return (
    <div className="no-match">
      <h3 className="t-tagline">That line wasn’t found in the video.</h3>
      {result.closest_text && (
        <>
          <p className="t-caption t-muted">Closest thing we heard</p>
          <blockquote>{result.closest_text}</blockquote>
          <p className="t-caption t-muted">Similarity {formatScore(result.similarity_score)}</p>
        </>
      )}
      {result.reason && <p className="t-caption t-muted">{result.reason}</p>}
      <SearchDetails result={result} />
      <p className="t-caption t-muted">
        Tip: check the wording, or lower the match threshold under Advanced options.
      </p>
    </div>
  );
}

function PipelineError({ result }) {
  return (
    <div className="pipeline-error" role="alert">
      <strong>The pipeline stopped: {result.status.replace(/_/g, ' ')}.</strong>
      {result.reason && <pre>{result.reason}</pre>}
    </div>
  );
}

export default function ResultView({ job }) {
  const result = job.result;
  if (!result) return null;

  let body;
  if (SUCCESS_STATUSES.includes(result.status)) body = <MatchResult job={job} result={result} />;
  else if (result.status === 'no_match') body = <NoMatch result={result} />;
  else body = <PipelineError result={result} />;

  return (
    <section className="result" aria-label="Result">
      {body}
      <Timings timings={result.timings} />
      <div className="result__actions">
        <button
          type="button"
          className="btn btn--secondary btn--small"
          onClick={() => downloadJson(`result_${job.id}.json`, result)}
        >
          Download result.json
        </button>
      </div>
    </section>
  );
}
