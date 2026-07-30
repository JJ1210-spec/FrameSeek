import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import SystemStatus from './SystemStatus';
import { READY_HEALTH } from '../../test/fakeBackend';

describe('SystemStatus', () => {
  it('renders nothing when the pipeline is ready', () => {
    const { container } = render(<SystemStatus health={READY_HEALTH} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing while the first check is loading', () => {
    const { container } = render(<SystemStatus loading />);
    expect(container).toBeEmptyDOMElement();
  });

  it('explains how to start an unreachable backend', async () => {
    const onRetry = vi.fn();
    render(<SystemStatus error={new Error('down')} onRetry={onRetry} />);
    expect(screen.getByRole('alert')).toHaveTextContent('Backend not reachable.');
    expect(screen.getByText(/uvicorn app.main:app/)).toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole('button', { name: 'Retry' }));
    expect(onRetry).toHaveBeenCalled();
  });

  it('lists missing dependencies', () => {
    const health = {
      ...READY_HEALTH,
      ready: false,
      checks: [
        ...READY_HEALTH.checks,
        { name: 'ffprobe (video metadata)', ok: false, detail: "'ffprobe' not found on PATH" },
      ],
    };
    render(<SystemStatus health={health} onRetry={() => {}} />);
    const alert = screen.getByRole('alert');
    expect(alert).toHaveTextContent('Some pipeline dependencies are missing.');
    expect(alert).toHaveTextContent("ffprobe (video metadata) — 'ffprobe' not found on PATH");
    expect(alert).not.toHaveTextContent('ffmpeg (audio extraction)');
  });
});
