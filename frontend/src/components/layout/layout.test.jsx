import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import Footer from './Footer';
import GlobalNav from './GlobalNav';
import SubNav from './SubNav';
import { READY_HEALTH } from '../../test/fakeBackend';

describe('GlobalNav', () => {
  it.each([
    [{ health: null, healthError: null }, 'Checking…'],
    [{ health: READY_HEALTH, healthError: null }, 'Pipeline ready'],
    [{ health: { ...READY_HEALTH, ready: false }, healthError: null }, 'Setup incomplete'],
    [{ health: null, healthError: new Error('down') }, 'Backend offline'],
  ])('shows pipeline status %#', (props, label) => {
    render(<GlobalNav onNavigate={() => {}} {...props} />);
    expect(screen.getByText(label)).toBeInTheDocument();
  });

  it('navigates to sections', async () => {
    const onNavigate = vi.fn();
    render(<GlobalNav onNavigate={onNavigate} />);
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'History' }));
    await user.click(screen.getByRole('button', { name: 'How it works' }));
    expect(onNavigate.mock.calls).toEqual([['history'], ['how']]);
  });
});

describe('SubNav', () => {
  it('offers history and a new-search CTA', async () => {
    const onNavigate = vi.fn();
    const onNewSearch = vi.fn();
    render(<SubNav onNavigate={onNavigate} onNewSearch={onNewSearch} />);
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'New search' }));
    await user.click(screen.getByRole('button', { name: 'History' }));
    expect(onNewSearch).toHaveBeenCalled();
    expect(onNavigate).toHaveBeenCalledWith('history');
  });
});

describe('Footer', () => {
  it('links the API docs and shows the backend version', () => {
    render(<Footer version="1.0.0" />);
    expect(screen.getByRole('link', { name: 'API docs' })).toHaveAttribute('href', 'http://localhost:8000/docs');
    expect(screen.getByText(/Backend v1\.0\.0\./)).toBeInTheDocument();
  });
});
