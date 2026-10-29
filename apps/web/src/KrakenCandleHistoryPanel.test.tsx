import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import '@testing-library/jest-dom/vitest';
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { KrakenCandleHistoryPanel } from './KrakenCandleHistoryPanel';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const wrap = (element: ReactNode) =>
  render(
    <QueryClientProvider
      client={
        new QueryClient({
          defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
        })
      }
    >
      {element}
    </QueryClientProvider>,
  );

const series = {
  venue: 'kraken' as const,
  native_market_id: 'XXBTZUSD',
  interval_seconds: 3600,
  candles: [
    {
      open_time_utc: '2026-10-29T15:00:00Z',
      open: '60000',
      high: '61000',
      low: '59000',
      close: '60500',
      volume: '1.5',
      trade_count: 23,
    },
  ],
  requested_since_epoch_seconds: null,
  bound_market_observation_id: 'a'.repeat(64),
  source_limit_note: 'The newest candle may be incomplete.',
  provenance: {
    source_url: 'https://api.kraken.com/0/public/OHLC?interval=60&pair=XXBTZUSD',
    raw_sha256: 'b'.repeat(64),
  },
};

const savedResponse = {
  items: [
    {
      series,
      observation_id: 'c'.repeat(64),
      raw_sha256: 'b'.repeat(64),
      received_at_utc: '2026-10-29T16:00:00Z',
    },
  ],
  venue: 'kraken' as const,
  native_market_id: 'XXBTZUSD',
  returned: 1,
  limit: 5,
  offset: 0,
  has_more: false,
  scan_bound: 20,
  scan_may_be_incomplete: false,
  source_state: 'recorded observations only',
  network_called: false as const,
};

it('shows saved candles and keeps a source-held probe disabled', async () => {
  const fetchMock = vi.fn<typeof fetch>(
    async () =>
      new Response(JSON.stringify({ ...savedResponse, items: [] }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
  );
  vi.stubGlobal('fetch', fetchMock);
  wrap(
    <KrakenCandleHistoryPanel
      nativeMarketId="XXBTZUSD"
      marketObservationId={'a'.repeat(64)}
      probeEnabled={false}
      disabledReason="Kraken public capture remains held pending source review."
    />,
  );

  expect(await screen.findByText('No saved candle captures')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Public candle probe unavailable' })).toBeDisabled();
  expect(screen.getByText(/held pending source review/)).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledTimes(1);
  expect(String(fetchMock.mock.calls[0]?.[0])).toContain('/api/frontier/candles?');
});

it('explains an empty result when the bounded saved-observation scan may be incomplete', async () => {
  const fetchMock = vi.fn<typeof fetch>(
    async () =>
      new Response(
        JSON.stringify({
          ...savedResponse,
          items: [],
          scan_bound: 20,
          scan_may_be_incomplete: true,
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
  );
  vi.stubGlobal('fetch', fetchMock);
  wrap(
    <KrakenCandleHistoryPanel
      nativeMarketId="XXBTZUSD"
      marketObservationId={'a'.repeat(64)}
      probeEnabled={false}
    />,
  );

  expect(await screen.findByText('No matching captures in the bounded scan')).toBeInTheDocument();
  expect(
    screen.getByText(
      /first 20 saved candle observations had no matching capture\. Additional matching captures may exist outside this scan\./,
    ),
  ).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledTimes(1);
});

it('starts a bounded capture only after action and renders persisted evidence', async () => {
  let getCalls = 0;
  const fetchMock = vi.fn<typeof fetch>(async (input, init) => {
    const path = String(input);
    if (path.includes('/api/frontier/candles?')) {
      getCalls += 1;
      return new Response(
        JSON.stringify(getCalls === 1 ? { ...savedResponse, items: [] } : savedResponse),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      );
    }
    if (path === '/api/frontier/probe/kraken/candles' && init?.method === 'POST') {
      expect(JSON.parse(String(init.body))).toEqual({
        native_market_id: 'XXBTZUSD',
        bound_market_observation_id: 'a'.repeat(64),
        interval_minutes: 60,
      });
      return new Response(
        JSON.stringify({
          venue: 'kraken',
          market_id: 'kraken:XBT/USD',
          native_market_id: 'XXBTZUSD',
          bound_market_observation_id: 'a'.repeat(64),
          series,
          candle_count: 1,
          observation_id: 'c'.repeat(64),
          raw_sha256: 'b'.repeat(64),
          source_state: 'healthy',
          request_count_delta: 1,
          network_calls_bounded_by: 1,
          hypothetical_only: true,
          spot_context_only: true,
          note: 'Context only.',
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      );
    }
    return new Response(JSON.stringify({ detail: 'Unexpected request' }), { status: 404 });
  });
  vi.stubGlobal('fetch', fetchMock);
  wrap(
    <KrakenCandleHistoryPanel
      nativeMarketId="XXBTZUSD"
      marketObservationId={'a'.repeat(64)}
      probeEnabled
    />,
  );

  expect(await screen.findByText('No saved candle captures')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Capture Kraken OHLC history' }));

  expect(await screen.findByText(/Capture c{12}/)).toBeInTheDocument();
  expect(screen.getByText('60500')).toBeInTheDocument();
  expect(screen.getByText(/context only · no executable P&L/)).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledTimes(3);
  expect(getCalls).toBe(2);
});
