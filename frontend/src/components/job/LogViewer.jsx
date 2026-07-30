import { useEffect, useRef } from 'react';

export default function LogViewer({ lines, defaultOpen = false }) {
  const preRef = useRef(null);

  useEffect(() => {
    const pre = preRef.current;
    if (pre) pre.scrollTop = pre.scrollHeight;
  }, [lines.length]);

  return (
    <details className="logs" open={defaultOpen}>
      <summary>Pipeline log ({lines.length} lines)</summary>
      <pre ref={preRef} className="logs__body" data-testid="log-output">
        {lines.length ? lines.join('\n') : 'No output yet.'}
      </pre>
    </details>
  );
}
