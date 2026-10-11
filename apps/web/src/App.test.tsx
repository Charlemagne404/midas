import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
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
});
