import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { App, money, WorkspaceErrorBoundary } from './App';
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
    const simulationBoundary = screen.getByText(/Simulation boundary/);
    expect(simulationBoundary).toHaveTextContent(/Simulation boundary.*No live order execution/);
    expect(screen.getAllByText('No live orders').length).toBeGreaterThan(0);
    expect(await screen.findByText('Data service offline')).toBeInTheDocument();
    expect(
      screen.getByText(/MIDAS cannot reach its data service\. Some values may be out of date\./),
    ).toBeInTheDocument();
  });

  it('contains a failed lazy workspace and explains how to retry it', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    function FailedWorkspace(): never {
      throw new Error('chunk unavailable');
    }

    render(
      <WorkspaceErrorBoundary name="Frontier">
        <FailedWorkspace />
      </WorkspaceErrorBoundary>,
    );

    expect(screen.getByRole('alert')).toHaveTextContent('Frontier workspace could not load');
    expect(
      screen.getByText('Refresh Mission Control to try loading this workspace again.'),
    ).toBeInTheDocument();
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

    expect(await screen.findByText('Saved economic evidence')).toBeInTheDocument();
    expect(
      await screen.findByText('Veritas evidence is unavailable.', {}, { timeout: 3000 }),
    ).toBeInTheDocument();
    expect(screen.queryByText('DEMO · SYNTHETIC')).not.toBeInTheDocument();
    expect(screen.queryByText('SYNTHETIC DATA')).not.toBeInTheDocument();
  });

  it('opens the Observatory as a read-only view of saved Arena research', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <App />
      </QueryClientProvider>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Observatory' }));

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Inside the machine.' }),
    ).toBeInTheDocument();
    expect(await screen.findByText('READ ONLY')).toBeInTheDocument();
    expect(await screen.findByText('The Observatory could not reach Arena')).toBeInTheDocument();
    expect(screen.queryByText('SYNTHETIC DATA')).not.toBeInTheDocument();
  });
});
