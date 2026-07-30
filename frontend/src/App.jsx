import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from './api/client';
import SystemStatus from './components/common/SystemStatus';
import JobHistory from './components/history/JobHistory';
import JobDetail from './components/job/JobDetail';
import Footer from './components/layout/Footer';
import GlobalNav from './components/layout/GlobalNav';
import SubNav from './components/layout/SubNav';
import SearchForm from './components/search/SearchForm';
import HowItWorks from './components/sections/HowItWorks';
import { useHealth } from './hooks/useHealth';
import { useJobs } from './hooks/useJobs';

// The selected search lives in the URL hash (#/jobs/<id>) so reloads keep it.
const HASH_PREFIX = '#/jobs/';

function readHash() {
  const { hash } = window.location;
  return hash.startsWith(HASH_PREFIX) ? decodeURIComponent(hash.slice(HASH_PREFIX.length)) : null;
}

function useSelectedJob() {
  const [selectedId, setSelectedId] = useState(readHash);

  useEffect(() => {
    const onHashChange = () => setSelectedId(readHash());
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);

  const select = useCallback((id) => {
    setSelectedId(id);
    const next = id ? `${HASH_PREFIX}${encodeURIComponent(id)}` : '';
    if (window.location.hash !== next) {
      window.history.replaceState(null, '', next || window.location.pathname);
    }
  }, []);

  return [selectedId, select];
}

function scrollToSection(id) {
  const el = document.getElementById(id);
  if (el && typeof el.scrollIntoView === 'function') el.scrollIntoView({ behavior: 'smooth' });
}

export default function App() {
  const health = useHealth();
  const { jobs, error: jobsError, loading: jobsLoading, refresh: refreshJobs } = useJobs();
  const [selectedId, select] = useSelectedJob();
  const urlInputRef = useRef(null);
  const shouldScrollToResult = useRef(false);

  useEffect(() => {
    if (selectedId && shouldScrollToResult.current) {
      shouldScrollToResult.current = false;
      scrollToSection('result');
    }
  }, [selectedId]);

  const openJob = (id) => {
    shouldScrollToResult.current = true;
    select(id);
  };

  const handleSubmit = async (search) => {
    const job = await api.createJob(search);
    openJob(job.id);
    refreshJobs();
  };

  const handleDeleted = (id) => {
    if (id === selectedId) select(null);
    refreshJobs();
  };

  const startNewSearch = () => {
    scrollToSection('search');
    if (urlInputRef.current) urlInputRef.current.focus({ preventScroll: true });
  };

  return (
    <>
      <GlobalNav onNavigate={scrollToSection} health={health.health} healthError={health.error} />
      <SubNav onNavigate={scrollToSection} onNewSearch={startNewSearch} />
      <SystemStatus
        health={health.health}
        error={health.error}
        loading={health.loading}
        onRetry={health.refresh}
      />

      <main>
        <section id="search" className="tile tile--light" aria-labelledby="hero-title">
          <div className="tile__inner">
            <header className="tile__header">
              <h1 id="hero-title" className="t-hero">Find the exact frame.</h1>
              <p className="t-lead t-muted">
                Paste a video link, type a line of dialogue — get the frame where it’s spoken.
              </p>
            </header>
            <SearchForm onSubmit={handleSubmit} urlInputRef={urlInputRef} />
          </div>
        </section>

        {selectedId && (
          <section id="result" className="tile tile--dark" aria-label="Result tile">
            <div className="tile__inner">
              <JobDetail key={selectedId} jobId={selectedId} onDeleted={handleDeleted} />
            </div>
          </section>
        )}

        <JobHistory
          jobs={jobs}
          selectedId={selectedId}
          onSelect={openJob}
          loading={jobsLoading}
          error={jobsError}
        />

        <HowItWorks />
      </main>

      <Footer version={health.health && health.health.version} />
    </>
  );
}
