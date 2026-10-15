import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { App, money } from './App';
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
describe('application integrity', () => {
  it('does not manufacture absent financial metrics', () => {
    expect(money(null)).toBe('—');
    expect(money('0')).toBe('0.00');
  });
  it('reports backend failure and preserves the execution boundary', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <App />
      </QueryClientProvider>,
    );
    expect(screen.getAllByText(/SIMULATION ONLY/).length).toBeGreaterThan(0);
    expect(await screen.findByText(/API DISCONNECTED/)).toBeInTheDocument();
    expect(screen.getByText(/Backend connection unavailable/)).toBeInTheDocument();
  });

  it('opens Veritas as its own evidence workspace without a synthetic-data badge', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <App />
      </QueryClientProvider>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Veritas' }));

    expect(await screen.findByText('VERITAS · ECONOMIC EVIDENCE')).toBeInTheDocument();
    expect(
      await screen.findByText('Veritas evidence is unavailable.', {}, { timeout: 3000 }),
    ).toBeInTheDocument();
    expect(screen.queryByText('DEMO · SYNTHETIC')).not.toBeInTheDocument();
    expect(screen.queryByText('SYNTHETIC DATA')).not.toBeInTheDocument();
  });
});
