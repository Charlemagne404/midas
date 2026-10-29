import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import type { UseMutationResult } from '@tanstack/react-query';
import {
  KrakenBookUpdatesPanel,
  type KrakenBookUpdateCaptureResult,
} from './KrakenBookUpdatesPanel';

afterEach(cleanup);

type Mutation = UseMutationResult<
  KrakenBookUpdateCaptureResult,
  Error,
  { marketId: string },
  unknown
>;

const mutationState = (overrides: Record<string, unknown> = {}) =>
  ({
    isSuccess: false,
    isPending: false,
    isError: false,
    variables: undefined,
    data: undefined,
    error: null,
    mutate: vi.fn(),
    ...overrides,
  }) as unknown as Mutation;

const capture: KrakenBookUpdateCaptureResult = {
  venue: 'kraken',
  market_id: 'kraken:XBT/USD',
  native_market_id: 'XBT/USD',
  bound_market_observation_id: 'a'.repeat(64),
  capture_status: 'captured_book_states',
  frame_count: 2,
  book_state_count: 1,
  capture_bounds: {
    max_frames: 16,
    max_updates: 16,
    max_duration_seconds: 3,
    depth: 10,
    stream_connections: 1,
  },
  frames: [
    {
      observation_id: 'b'.repeat(64),
      raw_sha256: 'c'.repeat(64),
      received_at_utc: '2026-10-29T08:00:00Z',
      source_url: 'wss://ws.kraken.com/v2',
      source_schema_version: 'kraken-spot-websocket-v2',
      adapter_version: 'frontier-kraken-spot-12',
      frame_type: 'snapshot',
      stream_message_index: 1,
      symbol: 'BTC/USD',
      subscription_acknowledged: true,
      source_timestamp_utc: '2026-10-29T07:59:59.900Z',
      checksum: 123456,
      checksum_verified: true,
      bid_level_count: 10,
      ask_level_count: 10,
    },
  ],
  source_state: 'healthy',
  hypothetical_only: true,
  note: 'Fixture capture only.',
};

it('keeps capture disabled and explains a source policy hold', () => {
  const probe = mutationState();
  const disabledReason = 'Kraken public capture remains held pending source review.';
  render(
    <KrakenBookUpdatesPanel
      marketId="kraken:XBT/USD"
      nativeMarketId="XBT/USD"
      probe={probe}
      probeEnabled={false}
      disabledReason={disabledReason}
      renderEvidence={(observationId) => <span>Inspect stored {observationId}</span>}
    />,
  );

  const button = screen.getByRole('button', { name: 'Kraken stream unavailable' });
  expect(button).toBeDisabled();
  fireEvent.click(button);
  expect(probe.mutate).not.toHaveBeenCalled();
  expect(screen.getByText(disabledReason)).toBeInTheDocument();
});

it('submits only the explicitly selected saved market when capture is enabled', () => {
  const probe = mutationState();
  render(
    <KrakenBookUpdatesPanel
      marketId={capture.market_id}
      nativeMarketId={capture.native_market_id}
      probe={probe}
      probeEnabled
      renderEvidence={(observationId) => <span>Inspect stored {observationId}</span>}
    />,
  );

  fireEvent.click(screen.getByRole('button', { name: 'Capture 3-second Kraken spot stream' }));
  expect(probe.mutate).toHaveBeenCalledWith({ marketId: capture.market_id });
});

it('shows checksum state, source timing, and immutable evidence for a saved-market capture', () => {
  const probe = mutationState({
    isSuccess: true,
    variables: { marketId: capture.market_id },
    data: capture,
  });
  render(
    <KrakenBookUpdatesPanel
      marketId={capture.market_id}
      nativeMarketId={capture.native_market_id}
      probe={probe}
      probeEnabled
      renderEvidence={(observationId) => <span>Inspect stored {observationId}</span>}
    />,
  );

  expect(
    screen.getByText('Captured 1 checksum-verified book state across 2 messages.'),
  ).toBeInTheDocument();
  expect(screen.getByText(/Bound market evidence a{12}/)).toBeInTheDocument();
  expect(
    screen.getByText(/Snapshot\/update checksum: verified · CRC32 123456/),
  ).toBeInTheDocument();
  expect(
    screen.getByText(/Bid\/ask levels 10\/10 · subscription ack observed/),
  ).toBeInTheDocument();
  expect(screen.getByText(/raw SHA-256 c{12}/i)).toBeInTheDocument();
  expect(screen.getByText(`Inspect stored ${'b'.repeat(64)}`)).toBeInTheDocument();
  expect(
    screen.getByText(/Spot prices are contextual evidence; they are not event-contract payouts/),
  ).toBeInTheDocument();
});

it.each([
  {
    state: 'control_messages_only' as const,
    frameCount: 1,
    frames: [
      {
        ...capture.frames[0],
        frame_type: 'heartbeat',
        source_timestamp_utc: null,
        checksum: null,
        checksum_verified: false,
        bid_level_count: 0,
        ask_level_count: 0,
      },
    ],
    expected: 'The stream returned control messages only; no book state was captured.',
  },
  {
    state: 'no_stream_messages_observed' as const,
    frameCount: 0,
    frames: [],
    expected: 'No stream messages were observed within the bounded capture window.',
  },
])('does not imply a book state for $state', ({ state, frameCount, frames, expected }) => {
  const probe = mutationState({
    isSuccess: true,
    variables: { marketId: capture.market_id },
    data: {
      ...capture,
      capture_status: state,
      frame_count: frameCount,
      book_state_count: 0,
      frames,
    },
  });
  render(
    <KrakenBookUpdatesPanel
      marketId={capture.market_id}
      nativeMarketId={capture.native_market_id}
      probe={probe}
      probeEnabled
      renderEvidence={(observationId) => <span>Inspect stored {observationId}</span>}
    />,
  );

  expect(screen.getByText(expected)).toBeInTheDocument();
  expect(screen.queryByText(/Captured .*checksum-verified book state/)).not.toBeInTheDocument();
});

it('does not show a prior market capture after the selected market changes', () => {
  const probe = mutationState({
    isSuccess: true,
    variables: { marketId: 'kraken:ETH/USD' },
    data: capture,
  });
  render(
    <KrakenBookUpdatesPanel
      marketId="kraken:BTC/USD"
      nativeMarketId="BTC/USD"
      probe={probe}
      probeEnabled
      renderEvidence={(observationId) => <span>Inspect stored {observationId}</span>}
    />,
  );

  expect(screen.getByText('No capture')).toBeInTheDocument();
  expect(screen.queryByText(/Captured .*checksum-verified book state/)).not.toBeInTheDocument();
});
