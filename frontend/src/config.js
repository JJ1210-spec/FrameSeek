// App-wide constants. Poll intervals are tiny under Vitest so tests run fast.
const isTest = import.meta.env.MODE === 'test';

export const API_BASE = import.meta.env.VITE_API_BASE || '/api';

export const JOB_POLL_MS = isTest ? 20 : 1000;
export const JOBS_POLL_MS = isTest ? 20 : 3000;

export const WHISPER_MODELS = [
  'tiny.en', 'tiny', 'base.en', 'base', 'small.en', 'small',
  'medium.en', 'medium', 'large-v3',
];

export const LANGUAGES = [
  ['', 'Auto-detect'],
  ['en', 'English'],
  ['ta', 'Tamil'],
  ['hi', 'Hindi'],
  ['te', 'Telugu'],
  ['ml', 'Malayalam'],
  ['kn', 'Kannada'],
  ['bn', 'Bengali'],
  ['es', 'Spanish'],
  ['fr', 'French'],
  ['de', 'German'],
  ['ja', 'Japanese'],
  ['ko', 'Korean'],
  ['zh', 'Chinese'],
];

export const COOKIE_BROWSERS = ['chrome', 'firefox', 'edge', 'brave', 'opera', 'safari'];

export const DEFAULT_OPTIONS = {
  model: '',
  coarse_model: 'tiny.en',
  fine_model: 'tiny.en',
  verify_model: 'base.en',
  language: '',
  match_threshold: 80,
  coarse_threshold: 50,
  window_buffer: 45,
  cpu_threads: '',
  cookies_from_browser: '',
};

export const EXAMPLE_SEARCH = {
  sourceUrl: 'https://youtu.be/atOgj_ZaO7M',
  query: "I'm always angry",
};
