// Frosted parchment strip with the product name and the persistent primary CTA.
export default function SubNav({ onNavigate, onNewSearch }) {
  return (
    <div className="sub-nav">
      <div className="sub-nav__inner">
        <span className="sub-nav__title t-tagline">FrameSeek</span>
        <div className="sub-nav__actions">
          <button type="button" className="btn-link t-caption" onClick={() => onNavigate('history')}>
            History
          </button>
          <button type="button" className="btn btn--primary btn--small" onClick={onNewSearch}>
            New search
          </button>
        </div>
      </div>
    </div>
  );
}
