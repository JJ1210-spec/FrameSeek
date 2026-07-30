# FrameSeek — Frontend (React + JavaScript, Vite)

```bash
npm install
npm run dev            # http://localhost:5173 (proxies /api → http://127.0.0.1:8000)
npm test               # Vitest + React Testing Library
npm run test:coverage  # with coverage report
npm run build          # production bundle in dist/
```

The backend must be running (`cd backend && uvicorn app.main:app --port 8000`).
Set `VITE_BACKEND_URL` to proxy to a different backend address.

| Path | Purpose |
|------|---------|
| `src/api/client.js` | fetch wrapper for the REST API, readable error messages |
| `src/hooks/` | `useJob` (polls a job + incremental logs), `useJobs`, `useHealth` |
| `src/lib/stages.js` | Maps pipeline stage names to progress steps and status chips |
| `src/components/layout/` | Global nav, frosted sub-nav, footer |
| `src/components/search/` | Search form + advanced pipeline options |
| `src/components/job/` | Job detail: progress, result (frame, stats, video), log |
| `src/components/history/` | History grid with frame thumbnails |
| `src/styles/` | Design tokens and styles — see `docs/design-system.md` |
| `src/test/` | Test setup and an in-memory fake backend |

Design: black global nav → frosted parchment sub-nav → full-bleed tiles alternating
white / near-black / parchment, a single Action Blue (`#0066cc`) accent, pill CTAs,
17 px body text, and one shadow — under the matched frame.
