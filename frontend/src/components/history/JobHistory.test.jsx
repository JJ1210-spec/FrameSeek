import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import JobHistory from './JobHistory';

const JOBS = [
  { id: 'a', status: 'running', source_url: 'https://www.youtube.com/watch?v=1', query: 'first line', created_at: '2026-09-28T10:00:00Z', result_status: null },
  { id: 'b', status: 'completed', source_url: 'https://ok.ru/video/2', query: 'second line', created_at: '2026-09-28T09:00:00Z', result_status: 'partial_match' },
  { id: 'c', status: 'completed', source_url: 'https://vimeo.com/3', query: 'third line', created_at: '2026-09-28T08:00:00Z', result_status: 'no_match' },
];

describe('JobHistory', () => {
  it('lists jobs with host and outcome badge', () => {
    render(<JobHistory jobs={JOBS} selectedId="b" onSelect={() => {}} />);
    expect(screen.getAllByRole('listitem')).toHaveLength(3);
    expect(screen.getByText('youtube.com')).toBeInTheDocument();
    expect(screen.getByText('Running')).toBeInTheDocument();
    expect(screen.getByText('Close match')).toBeInTheDocument();
    expect(screen.getByText('No match')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /second line/ })).toHaveAttribute('aria-current', 'true');
  });

  it('selects a job on click', async () => {
    const onSelect = vi.fn();
    render(<JobHistory jobs={JOBS} selectedId={null} onSelect={onSelect} />);
    await userEvent.setup().click(screen.getByRole('button', { name: /third line/ }));
    expect(onSelect).toHaveBeenCalledWith('c');
  });

  it('shows empty, loading and error states', () => {
    const { rerender } = render(<JobHistory jobs={[]} loading onSelect={() => {}} />);
    expect(screen.getByText('Loading…')).toBeInTheDocument();
    rerender(<JobHistory jobs={[]} loading={false} onSelect={() => {}} />);
    expect(screen.getByText(/No searches yet/)).toBeInTheDocument();
    rerender(<JobHistory jobs={[]} error={new Error('offline')} onSelect={() => {}} />);
    expect(screen.getByText('Could not load history: offline')).toBeInTheDocument();
  });
});
