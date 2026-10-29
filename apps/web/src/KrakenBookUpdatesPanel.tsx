import type { UseMutationResult } from '@tanstack/react-query';
import type { ReactNode } from 'react';

export type KrakenBookUpdateCaptureResult = {
  venue: 'kraken';
  market_id: string;
  native_market_id: string;
  bound_market_observation_id: string;
  capture_status: 'captured_book_states' | 'control_messages_only' | 'no_stream_messages_observed';
  frame_count: number;
  book_state_count: number;
  capture_bounds: {
    max_frames: number;
    max_updates: number;
    max_duration_seconds: number;
    depth: number;
    stream_connections: number;
  };
  frames: {
    observation_id: string;
    raw_sha256: string;
    received_at_utc: string;
    source_url: string;
    source_schema_version: string;
    adapter_version: string;
    frame_type: string;
    stream_message_index: number;
    symbol: string;
    subscription_depth: number | null;
    subscription_acknowledged: boolean;
    source_timestamp_utc: string | null;
    checksum: number | null;
    checksum_verified: boolean;
    bid_level_count: number;
    ask_level_count: number;
  }[];
  source_state: string;
  hypothetical_only: true;
  note: string;
};

export type KrakenBookCaptureReplay = {
  replay_version: string;
  native_market_id: string;
  symbol: string;
  subscription_depth: 10 | 25 | 100;
  frame_evidence: { observation_id: string }[];
  book_states: {
    observation_id: string;
    frame_type: 'snapshot' | 'update';
    message_index: number;
    source_timestamp_utc: string;
    received_at_utc: string;
    bids: { price: string; quantity: string }[];
    asks: { price: string; quantity: string }[];
    checksum: number;
    checksum_verified: true;
  }[];
  reconstruction_status:
    'checksum_verified_states' | 'acknowledged_no_book_state' | 'control_only_no_ack';
  input_sha256: string;
  result_sha256: string;
  classification: 'context_only';
  event_economics_eligible: false;
};

type KrakenBookReplayInput = { observationIds: string[] };

type KrakenBookUpdatesPanelProps = {
  marketId: string;
  nativeMarketId: string;
  probe: UseMutationResult<KrakenBookUpdateCaptureResult, Error, { marketId: string }, unknown>;
  replay: UseMutationResult<KrakenBookCaptureReplay, Error, KrakenBookReplayInput, unknown>;
  probeEnabled: boolean;
  disabledReason?: string | null;
  renderEvidence: (observationId: string) => ReactNode;
};

const shortHash = (value: string) => value.slice(0, 12);

export function KrakenBookUpdatesPanel({
  marketId,
  nativeMarketId,
  probe,
  replay,
  probeEnabled,
  disabledReason,
  renderEvidence,
}: KrakenBookUpdatesPanelProps) {
  const result = probe.isSuccess && probe.variables?.marketId === marketId ? probe.data : null;
  const replayObservationIds = result?.frames.map((frame) => frame.observation_id) ?? [];
  const replayResult =
    replay.isSuccess &&
    replay.variables?.observationIds.join(',') === replayObservationIds.join(',')
      ? replay.data
      : null;
  const stateLabel = (value: string) => value.replaceAll('_', ' ');

  return (
    <section className="fr-price-history-panel" aria-label="Kraken spot book update capture">
      <div className="fr-price-history-heading">
        <div>
          <span className="fr-kicker">KRAKEN SPOT / {nativeMarketId}</span>
          <h4>Kraken book states</h4>
          <p>
            One explicit stream request, at most 3 seconds, 16 messages and 16 book states. A full
            snapshot is required before updates; accepted book states pass Kraken’s CRC32 checksum.
            Reconnect continuity is not established.
          </p>
        </div>
        <span className="fr-count">
          {result
            ? `${result.frame_count} messages · ${result.book_state_count} states`
            : 'No capture'}
        </span>
      </div>
      <div className="fr-price-history-controls">
        <button
          className="fr-inspect-button"
          disabled={!probeEnabled || probe.isPending}
          onClick={() => probe.mutate({ marketId })}
        >
          {probe.isPending
            ? 'Capturing…'
            : probeEnabled
              ? 'Capture 3-second Kraken spot stream'
              : 'Kraken stream unavailable'}
        </button>
        <button
          className="fr-inspect-button"
          disabled={
            replayObservationIds.length === 0 || Boolean(disabledReason) || replay.isPending
          }
          onClick={() => replay.mutate({ observationIds: replayObservationIds })}
        >
          {replay.isPending ? 'Replaying stored frames…' : 'Replay saved capture offline'}
        </button>
      </div>
      <p className="fr-price-history-note">
        {probeEnabled
          ? 'Capture starts only after this button is pressed. Saved-capture replay reads immutable frames and opens no source connection. Spot prices are contextual evidence; they are not event-contract payouts, a verified hedge, or proof of simultaneous executable depth.'
          : (disabledReason ??
            'Capture is unavailable because Kraken is disabled, held by source policy, or does not advertise book updates.')}
      </p>
      {probe.isError && probe.variables?.marketId === marketId && (
        <p role="alert" className="fr-price-history-note">
          {probe.error?.message ?? 'Kraken capture failed without a diagnostic message.'}
        </p>
      )}
      {replay.isError &&
        replay.variables?.observationIds.join(',') === replayObservationIds.join(',') && (
          <p role="alert" className="fr-price-history-note">
            {replay.error?.message ?? 'Stored Kraken replay failed without a diagnostic message.'}
          </p>
        )}
      {replayResult && (
        <div
          className="fr-price-history-result"
          role="status"
          aria-label="Kraken offline replay result"
        >
          <p>
            Reconstructed {replayResult.book_states.length} checksum-verified book state
            {replayResult.book_states.length === 1 ? '' : 's'} from{' '}
            {replayResult.frame_evidence.length} immutable stored frame
            {replayResult.frame_evidence.length === 1 ? '' : 's'} at depth{' '}
            {replayResult.subscription_depth}.
          </p>
          <p>
            Replay {replayResult.replay_version} · state{' '}
            {stateLabel(replayResult.reconstruction_status)}
          </p>
          <p>
            Input SHA-256 {shortHash(replayResult.input_sha256)} · result SHA-256{' '}
            {shortHash(replayResult.result_sha256)}
          </p>
          <strong>Context only · event-contract economics ineligible.</strong>
        </div>
      )}
      {result && (
        <div className="fr-price-history-result" role="status">
          <p>
            {result.capture_status === 'captured_book_states'
              ? `Captured ${result.book_state_count} checksum-verified book state${result.book_state_count === 1 ? '' : 's'} across ${result.frame_count} messages.`
              : result.capture_status === 'control_messages_only'
                ? 'The stream returned control messages only; no book state was captured.'
                : 'No stream messages were observed within the bounded capture window.'}
          </p>
          <p>
            Bound market evidence {shortHash(result.bound_market_observation_id)} · source state{' '}
            {stateLabel(result.source_state)} · hypothetical research only
          </p>
          {result.frames.map((frame) => (
            <article key={frame.observation_id} className="fr-price-history-meta">
              <span>
                Message {frame.stream_message_index} · {frame.frame_type} · {frame.symbol}
              </span>
              <span>
                Received {frame.received_at_utc} · source time{' '}
                {frame.source_timestamp_utc ?? 'not supplied'}
              </span>
              <span>
                Snapshot/update checksum: {frame.checksum_verified ? 'verified' : 'not applicable'}
                {frame.checksum !== null ? ` · CRC32 ${frame.checksum}` : ''}
              </span>
              <span>
                Bid/ask levels {frame.bid_level_count}/{frame.ask_level_count} · subscription ack{' '}
                {frame.subscription_acknowledged ? 'observed' : 'not observed'} · subscribed depth{' '}
                {frame.subscription_depth ?? 'not recorded'}
              </span>
              <span>
                Record {shortHash(frame.observation_id)} · raw SHA-256 {shortHash(frame.raw_sha256)}
              </span>
              {renderEvidence(frame.observation_id)}
            </article>
          ))}
          <small>{result.note}</small>
        </div>
      )}
    </section>
  );
}
