import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { api } from './api';

type Candle = {
  open_time_utc: string;
  open: string;
  high: string;
  low: string;
  close: string;
  volume: string;
  trade_count: number | null;
};

type CandleSeries = {
  venue: 'kraken';
  native_market_id: string;
  interval_seconds: number;
  candles: Candle[];
  requested_since_epoch_seconds: number | null;
  bound_market_observation_id: string | null;
  source_limit_note: string;
  provenance: { source_url: string; raw_sha256: string };
};

type SavedCandleObservation = {
  series: CandleSeries;
  observation_id: string;
  raw_sha256: string;
  received_at_utc: string;
};

type SavedCandleResponse = {
  items: SavedCandleObservation[];
  venue: 'kraken';
  native_market_id: string | null;
  returned: number;
  limit: number;
  offset: number;
  scan_offset: number;
  scanned_observations: number;
  next_scan_offset: number | null;
  has_more: boolean;
  scan_bound: number;
  scan_may_be_incomplete: boolean;
  source_state: string;
  network_called: false;
};

type CandleCaptureResponse = {
  venue: 'kraken';
  market_id: string;
  native_market_id: string;
  bound_market_observation_id: string;
  series: CandleSeries;
  candle_count: number;
  observation_id: string;
  raw_sha256: string;
  source_state: string;
  request_count_delta: number;
  network_calls_bounded_by: number;
  hypothetical_only: true;
  spot_context_only: true;
  note: string;
};

type KrakenCandleHistoryPanelProps = {
  nativeMarketId: string;
  marketObservationId: string;
  probeEnabled: boolean;
  disabledReason?: string | null;
};

const intervals = [
  { minutes: 1, label: '1 minute' },
  { minutes: 5, label: '5 minutes' },
  { minutes: 15, label: '15 minutes' },
  { minutes: 30, label: '30 minutes' },
  { minutes: 60, label: '1 hour' },
  { minutes: 240, label: '4 hours' },
  { minutes: 1440, label: '1 day' },
  { minutes: 10080, label: '1 week' },
  { minutes: 21600, label: '15 days' },
] as const;

const shortHash = (value: string) => value.slice(0, 12);

export function KrakenCandleHistoryPanel({
  nativeMarketId,
  marketObservationId,
  probeEnabled,
  disabledReason,
}: KrakenCandleHistoryPanelProps) {
  const queryClient = useQueryClient();
  const [intervalMinutes, setIntervalMinutes] = useState(60);
  const [sinceInput, setSinceInput] = useState('');
  const [selectedObservationId, setSelectedObservationId] = useState<string | null>(null);
  const queryKey = ['frontier', 'kraken-candles', nativeMarketId] as const;
  const saved = useInfiniteQuery({
    queryKey,
    initialPageParam: { scanOffset: 0, matchOffset: 0 },
    queryFn: ({ pageParam }) => {
      const params = new URLSearchParams({
        venue: 'kraken',
        native_market_id: nativeMarketId,
        limit: '5',
        offset: String(pageParam.matchOffset),
        scan_offset: String(pageParam.scanOffset),
      });
      return api<SavedCandleResponse>(`/frontier/candles?${params.toString()}`);
    },
    getNextPageParam: (lastPage, _pages, lastPageParam) => {
      if (lastPage.has_more) {
        return {
          ...lastPageParam,
          matchOffset: lastPageParam.matchOffset + lastPage.returned,
        };
      }
      if (lastPage.scan_may_be_incomplete && lastPage.next_scan_offset !== null) {
        return { scanOffset: lastPage.next_scan_offset, matchOffset: 0 };
      }
      return undefined;
    },
    maxPages: 10,
    retry: false,
  });
  const capture = useMutation({
    mutationFn: (input: { intervalMinutes: number; sinceEpochSeconds?: number }) =>
      api<CandleCaptureResponse>('/frontier/probe/kraken/candles', {
        method: 'POST',
        body: JSON.stringify({
          native_market_id: nativeMarketId,
          bound_market_observation_id: marketObservationId,
          interval_minutes: input.intervalMinutes,
          ...(input.sinceEpochSeconds === undefined
            ? {}
            : { since_epoch_seconds: input.sinceEpochSeconds }),
        }),
      }),
    onSuccess: async (result) => {
      setSelectedObservationId(result.observation_id);
      await queryClient.resetQueries({ queryKey });
    },
  });

  const uniqueItems = new Map<string, SavedCandleObservation>();
  for (const item of saved.data?.pages.flatMap((page) => page.items) ?? []) {
    uniqueItems.set(item.observation_id, item);
  }
  const items = Array.from(uniqueItems.values());
  const selected =
    items.find((item) => item.observation_id === selectedObservationId) ?? items[0] ?? null;
  const sinceMillis = sinceInput ? Date.parse(sinceInput) : null;
  const invalidSince =
    sinceMillis !== null &&
    (!Number.isFinite(sinceMillis) || sinceMillis < 0 || sinceMillis > Date.now());
  const canCapture = probeEnabled && !capture.isPending && !invalidSince;

  return (
    <section className="fr-price-history-panel" aria-label="Kraken historical spot candles">
      <div className="fr-price-history-heading">
        <div>
          <span className="fr-kicker">KRAKEN SPOT / {nativeMarketId}</span>
          <h4>Historical OHLC context</h4>
          <p>
            One explicit public request, bounded to Kraken’s 720 returned candles. The newest candle
            may be incomplete; spot history is contextual evidence, not a prediction-market payoff
            or hedge.
          </p>
        </div>
        <span className="fr-count">
          {saved.isLoading ? 'Reading saved data…' : `${items.length} saved`}
        </span>
      </div>
      <div className="fr-price-history-controls">
        <label>
          Interval
          <select
            value={intervalMinutes}
            onChange={(event) => setIntervalMinutes(Number(event.target.value))}
            disabled={capture.isPending}
          >
            {intervals.map((interval) => (
              <option key={interval.minutes} value={interval.minutes}>
                {interval.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Start time (optional)
          <input
            type="datetime-local"
            value={sinceInput}
            onChange={(event) => setSinceInput(event.target.value)}
            disabled={capture.isPending}
          />
        </label>
        <button
          className="fr-inspect-button"
          disabled={!canCapture}
          onClick={() =>
            capture.mutate({
              intervalMinutes,
              ...(sinceMillis === null
                ? {}
                : { sinceEpochSeconds: Math.floor(sinceMillis / 1000) }),
            })
          }
        >
          {capture.isPending
            ? 'Capturing candles…'
            : probeEnabled
              ? 'Capture Kraken OHLC history'
              : 'Public candle probe unavailable'}
        </button>
      </div>
      <p className="fr-price-history-note">
        {probeEnabled
          ? 'Saved rows load from MIDAS only. A source request starts only after you press Capture; no private credentials are used.'
          : (disabledReason ??
            'Capture is unavailable because Kraken is disabled, held by source policy, or does not advertise historical candles.')}
      </p>
      {invalidSince && (
        <p role="alert" className="fr-price-history-note">
          Start time must be a valid timestamp no later than now.
        </p>
      )}
      {saved.isError && (
        <p role="alert" className="fr-price-history-note">
          {saved.error.message || 'Saved candle evidence could not be read.'}
        </p>
      )}
      {capture.isError && (
        <p role="alert" className="fr-price-history-note">
          {capture.error.message || 'Kraken candle capture failed.'}
        </p>
      )}
      {capture.isSuccess && (
        <div
          className="fr-price-history-result"
          role="status"
          aria-label="Kraken candle capture result"
        >
          Captured {capture.data.candle_count} candles · source state {capture.data.source_state} ·
          {` ${capture.data.request_count_delta} request`} (maximum{' '}
          {capture.data.network_calls_bounded_by}) · context only · hypothetical research.
        </div>
      )}
      {!saved.isLoading && !saved.isError && items.length === 0 && (
        <div className="fr-empty">
          {saved.data?.pages.at(-1)?.scan_may_be_incomplete ? (
            <>
              <strong>No matching captures in the bounded scan</strong>
              <p>
                This batch checked{' '}
                {saved.data.pages.at(-1)?.scanned_observations ?? 0} of up to{' '}
                {saved.data.pages.at(-1)?.scan_bound ?? 20} saved candle observations and found no
                match. Additional matching
                captures may exist outside this scan.
              </p>
            </>
          ) : (
            <>
              <strong>No saved candle captures</strong>
              <p>This view is local evidence only; capture remains an explicit action.</p>
            </>
          )}
        </div>
      )}
      {items.length > 0 && (
        <div className="fr-price-history-controls" aria-label="Saved Kraken candle captures">
          {items.map((item) => (
            <button
              key={item.observation_id}
              type="button"
              className="fr-inspect-button"
              aria-pressed={selected?.observation_id === item.observation_id}
              onClick={() => setSelectedObservationId(item.observation_id)}
            >
              {intervals.find((interval) => interval.minutes * 60 === item.series.interval_seconds)
                ?.label ?? `${item.series.interval_seconds}s`}{' '}
              · {item.series.candles.length} candles · {shortHash(item.observation_id)}
            </button>
          ))}
          {saved.data?.pages.some((page) => page.scan_may_be_incomplete) && (
            <small>
              Saved observations are scanned newest first in bounded batches. New captures can
              shift later offset pages while scanning.
            </small>
          )}
        </div>
      )}
      {saved.hasNextPage && (
        <button
          type="button"
          className="fr-inspect-button"
          disabled={saved.isFetchingNextPage}
          onClick={() => void saved.fetchNextPage()}
        >
          {saved.isFetchingNextPage
            ? 'Scanning saved observations…'
            : saved.data?.pages.at(-1)?.has_more
              ? 'Load more matching captures'
              : `Scan next ${saved.data?.pages.at(-1)?.scan_bound ?? 20} observations`}
        </button>
      )}
      {selected && (
        <div className="fr-price-history-result" role="status">
          <p>
            Capture {shortHash(selected.observation_id)} · received {selected.received_at_utc} · raw
            SHA-256 {shortHash(selected.raw_sha256)}
          </p>
          <p>
            Bound market evidence {shortHash(selected.series.bound_market_observation_id ?? '')} ·
            source request {selected.series.provenance.source_url}
          </p>
          <p>{selected.series.source_limit_note}</p>
          <div className="fr-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Open time (UTC)</th>
                  <th>Open</th>
                  <th>High</th>
                  <th>Low</th>
                  <th>Close</th>
                  <th>Volume</th>
                  <th>Trades</th>
                </tr>
              </thead>
              <tbody>
                {selected.series.candles
                  .slice(-20)
                  .reverse()
                  .map((candle) => (
                    <tr key={candle.open_time_utc}>
                      <td>{candle.open_time_utc}</td>
                      <td>{candle.open}</td>
                      <td>{candle.high}</td>
                      <td>{candle.low}</td>
                      <td>{candle.close}</td>
                      <td>{candle.volume}</td>
                      <td>{candle.trade_count ?? 'Not supplied'}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
          <small>
            Showing the latest {Math.min(20, selected.series.candles.length)} of{' '}
            {selected.series.candles.length} candles · context only · no executable P&amp;L.
          </small>
        </div>
      )}
    </section>
  );
}
