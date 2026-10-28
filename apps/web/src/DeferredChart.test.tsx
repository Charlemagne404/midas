import { act, cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { DeferredChart } from './DeferredChart';

const observers: MockObserver[] = [];

vi.mock('./Chart', () => ({
  Chart: ({ label }: { label: string }) => <div data-testid="heavy-chart">{label}</div>,
}));

class MockObserver implements IntersectionObserver {
  readonly root = null;
  readonly rootMargin: string;
  readonly thresholds: readonly number[] = [];
  private target: Element | null = null;
  private readonly callback: IntersectionObserverCallback;
  disconnected = false;

  constructor(callback: IntersectionObserverCallback, options?: IntersectionObserverInit) {
    this.callback = callback;
    this.rootMargin = options?.rootMargin ?? '0px';
    observers.push(this);
  }

  observe(target: Element) {
    this.target = target;
  }

  unobserve() {}

  disconnect() {
    this.disconnected = true;
  }

  takeRecords(): IntersectionObserverEntry[] {
    return [];
  }

  enter() {
    if (!this.target) throw new Error('No observed chart container');
    const entry = { isIntersecting: true, target: this.target } as IntersectionObserverEntry;
    this.callback([entry], this);
  }
}

describe('DeferredChart', () => {
  beforeEach(() => {
    observers.length = 0;
    Object.defineProperty(globalThis, 'IntersectionObserver', {
      configurable: true,
      writable: true,
      value: MockObserver,
    });
  });

  afterEach(() => {
    cleanup();
    Reflect.deleteProperty(globalThis, 'IntersectionObserver');
  });

  it('defers the chart module until its reserved space approaches the viewport', async () => {
    render(<DeferredChart label="Price history" option={{}} />);

    expect(screen.getByRole('status')).toHaveTextContent('Chart loads when visible');
    expect(screen.queryByTestId('heavy-chart')).not.toBeInTheDocument();
    expect(observers).toHaveLength(1);
    expect(observers[0].rootMargin).toBe('120px');

    await act(async () => observers[0].enter());

    expect(await screen.findByTestId('heavy-chart')).toHaveTextContent('Price history');
    expect(observers[0].disconnected).toBe(true);
    expect(document.querySelector('.chart-deferred')).toHaveAttribute('aria-busy', 'false');
  });
});
