// Maps backend pipeline stage names (pipeline.py `enter(...)` calls) onto the
// user-facing progress steps, and pipeline result statuses onto labels.

export const PHASES = [
  { key: 'download', label: 'Download video', stages: ['acquire_video'] },
  { key: 'metadata', label: 'Read metadata', stages: ['get_video_metadata'] },
  { key: 'audio', label: 'Extract audio', stages: ['extract_audio'] },
  { key: 'vad', label: 'Speech & language', stages: ['run_vad', 'detect_language'] },
  {
    key: 'transcribe',
    label: 'Transcribe',
    stages: ['transcribe', 'transcribe_coarse', 'transcribe_full'],
  },
  {
    key: 'match',
    label: 'Match dialogue',
    stages: ['match_dialogue', 'match_dialogue_coarse', 'match_dialogue_full'],
  },
  {
    key: 'refine',
    label: 'Refine match',
    stages: [
      'extract_audio_slice', 'transcribe_fine', 'match_dialogue_fine',
      'extract_audio_slice_verify', 'transcribe_verify', 'match_dialogue_verify',
    ],
    optional: true, // long videos (fine pass) and near-miss verification only
  },
  { key: 'frame', label: 'Extract frame', stages: ['extract_frame'] },
];

export const STAGE_DESCRIPTIONS = {
  acquire_video: 'Downloading the video…',
  get_video_metadata: 'Reading FPS and duration…',
  extract_audio: 'Extracting 16 kHz mono audio…',
  run_vad: 'Finding speech with Silero VAD…',
  detect_language: 'Detecting the spoken language…',
  transcribe: 'Transcribing speech with faster-whisper…',
  match_dialogue: 'Matching your dialogue against the transcript…',
  transcribe_coarse: 'Long video: coarse transcription of the full audio…',
  match_dialogue_coarse: 'Locating the candidate window…',
  extract_audio_slice: 'Cutting a ±45 s window around the candidate…',
  transcribe_fine: 'Fine transcription of the candidate window…',
  match_dialogue_fine: 'Refining the match to word level…',
  transcribe_full: 'Not found in the speech-only pass — transcribing the full audio…',
  match_dialogue_full: 'Matching against the full-audio transcript…',
  extract_audio_slice_verify: 'Close match found — cutting a window around it…',
  transcribe_verify: 'Confirming the close match with a larger model…',
  match_dialogue_verify: 'Checking the confirmed transcript…',
  extract_frame: 'Grabbing the exact frame…',
};

export const SUCCESS_STATUSES = ['success', 'partial_match'];

const RESULT_LABELS = {
  success: { label: 'Exact match', tone: 'success' },
  partial_match: { label: 'Close match', tone: 'info' },
  no_match: { label: 'No match', tone: 'warning' },
  download_failed: { label: 'Download failed', tone: 'danger' },
  metadata_failed: { label: 'Unreadable video', tone: 'danger' },
  no_audio_track: { label: 'No speech / audio', tone: 'danger' },
  audio_extraction_failed: { label: 'Audio extraction failed', tone: 'danger' },
  transcription_failed: { label: 'Transcription failed', tone: 'danger' },
  frame_extraction_failed: { label: 'Frame extraction failed', tone: 'danger' },
};

const JOB_LABELS = {
  queued: { label: 'Queued', tone: 'neutral' },
  running: { label: 'Running', tone: 'progress' },
  failed: { label: 'Error', tone: 'danger' },
};

// One badge per job: live state while active, pipeline outcome once finished.
export function statusDisplay(jobStatus, resultStatus) {
  if (jobStatus === 'completed') {
    return RESULT_LABELS[resultStatus] || { label: resultStatus || 'Completed', tone: 'danger' };
  }
  return JOB_LABELS[jobStatus] || { label: jobStatus || 'Unknown', tone: 'neutral' };
}

export function phaseIndexOf(stage) {
  return PHASES.findIndex((phase) => phase.stages.includes(stage));
}

/**
 * Step states for the progress tracker.
 * Returns [{ key, label, state }] where state ∈ pending | active | done | failed | skipped.
 */
export function buildSteps(job) {
  const history = (job && job.stage_history) || [];
  const reachedRefine = history.some((stage) => PHASES[6].stages.includes(stage));
  const phases = PHASES.filter((phase) => !phase.optional || reachedRefine);
  const reached = history.reduce(
    (max, stage) => Math.max(max, phases.findIndex((p) => p.stages.includes(stage))),
    -1,
  );

  const status = job ? job.status : 'queued';
  const resultStatus = job && job.result ? job.result.status : null;

  return phases.map((phase, index) => {
    let state = 'pending';
    if (status === 'running') {
      if (index < reached) state = 'done';
      else if (index === reached) state = 'active';
    } else if (status === 'completed' && SUCCESS_STATUSES.includes(resultStatus)) {
      state = 'done';
    } else if (status === 'completed' && resultStatus === 'no_match') {
      state = index <= reached ? 'done' : 'skipped';
    } else if (status === 'completed' || status === 'failed') {
      if (index < reached) state = 'done';
      else if (index === reached) state = 'failed';
      else state = 'skipped';
    }
    return { key: phase.key, label: phase.label, state };
  });
}

export function isActive(job) {
  return Boolean(job) && (job.status === 'queued' || job.status === 'running');
}
