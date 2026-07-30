// Thin true-black bar: brand, section links, pipeline status.
export default function GlobalNav({ onNavigate, health, healthError }) {
  let status = { tone: '', label: 'Checking…' };
  if (healthError) status = { tone: 'error', label: 'Backend offline' };
  else if (health && health.ready) status = { tone: 'ok', label: 'Pipeline ready' };
  else if (health) status = { tone: 'error', label: 'Setup incomplete' };

  const links = [
    { id: 'search', label: 'Search' },
    { id: 'history', label: 'History' },
    { id: 'how', label: 'How it works' },
  ];

  return (
    <nav className="global-nav" aria-label="Global">
      <div className="global-nav__inner">
        <span className="global-nav__brand">
          <img className="global-nav__glyph" src="/frameseek.svg" alt="" width="20" height="20" />
          FrameSeek
        </span>
        <ul className="global-nav__links">
          {links.map((link) => (
            <li key={link.id}>
              <button type="button" className="global-nav__link" onClick={() => onNavigate(link.id)}>
                {link.label}
              </button>
            </li>
          ))}
        </ul>
        <span className="global-nav__status" title="Pipeline dependency check">
          <span className={`status-dot${status.tone ? ` status-dot--${status.tone}` : ''}`} aria-hidden="true" />
          {status.label}
        </span>
      </div>
    </nav>
  );
}
