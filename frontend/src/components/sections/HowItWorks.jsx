const STEPS = [
  { title: 'Download', text: 'yt-dlp fetches the video from the URL — YouTube, Vimeo, ok.ru and more.' },
  { title: 'Detect speech', text: 'Silero VAD measures how much speech there is and picks a speed tier.' },
  { title: 'Transcribe', text: 'faster-whisper transcribes with word timestamps. Long videos get a coarse pass, then a precise ±45 s fine pass.' },
  { title: 'Match', text: 'Your line is matched exactly first, then fuzzily with rapidfuzz.' },
  { title: 'Grab the frame', text: 'OpenCV seeks to the word-level timestamp and saves the exact frame.' },
];

export default function HowItWorks() {
  return (
    <section id="how" className="tile tile--light" aria-labelledby="how-title">
      <div className="tile__inner tile__inner--wide">
        <header className="tile__header">
          <h2 id="how-title" className="t-display-lg">How it works.</h2>
          <p className="t-lead t-muted">Five stages. One frame.</p>
        </header>
        <ol className="how">
          {STEPS.map((step) => (
            <li key={step.title} className="how__step">
              <h3 className="t-body-strong">{step.title}</h3>
              <p>{step.text}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
