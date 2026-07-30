export default function Footer({ version }) {
  return (
    <footer className="footer">
      <div className="footer__inner t-fine-print">
        <ul className="footer__links">
          <li><a href="http://localhost:8000/docs" target="_blank" rel="noreferrer">API docs</a></li>
          <li>faster-whisper</li>
          <li>Silero VAD</li>
          <li>OpenCV</li>
          <li>yt-dlp</li>
          <li>rapidfuzz</li>
        </ul>
        <p className="footer__legal">
          FrameSeek — CPU-Optimized Speech-to-Frame Localization Pipeline. MIT License.
          Runs entirely on this machine — videos, audio and results never leave it.
          {version ? ` Backend v${version}.` : ''}
        </p>
      </div>
    </footer>
  );
}
