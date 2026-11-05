import { useState } from 'react';
import type { ReactNode } from 'react';
import type { UseMutationResult } from '@tanstack/react-query';

export type KalshiFeeMetadataCaptureResult = {
  market_id: string;
  metadata: {
    series_ticker: string;
    event_fee_type_override: string | null;
    event_fee_multiplier_override: string | null;
    series_fee_type: string;
    series_fee_multiplier: string;
    effective_fee_type: string;
    effective_fee_multiplier: string;
    fee_resolution_state:
      'event_override' | 'series_inherited' | 'partial_override' | 'override_unreported';
    economics_state: 'unresolved';
    limitations: string[];
  };
  observation_ids: [string, string];
  raw_sha256: { event: string; series: string };
  fee_cost_modeled: false;
  note: string;
};

export type KalshiFeeOrderSensitivityResponse = {
  market_id: string;
  estimate: {
    model_version: string;
    series_ticker: string;
    effective_fee_type: string;
    effective_fee_multiplier: string;
    fee_resolution_state: 'event_override' | 'series_inherited';
    input_received_at_utc: [string, string];
    order_fills: {
      native_instrument_id: string;
      side: 'buy' | 'sell';
      price_usd: string;
      quantity_contracts: string;
    }[];
    scenarios: {
      account_precision_class: string;
      balance_quantum: string;
      fills: {
        fill_index: number;
        native_instrument_id: string;
        side: 'buy' | 'sell';
        trade_fee_rounded_to_microdollar: string;
        rounding_fee_usd: string;
        rebate_usd: string;
        accumulated_rounding_after_rebate_usd: string;
        net_fee_usd: string;
      }[];
      total_trade_fee_usd: string;
      total_rounding_fee_usd: string;
      total_rebate_usd: string;
      total_net_fee_usd: string;
      total_balance_change_usd: string;
    }[];
    calculation_sha256: string;
    assumptions: string[];
  };
  hypothetical_only: true;
  candidate_net_economics_modified: false;
  note: string;
};

export type KalshiFeeScenarioFill = {
  instrumentId: string;
  side: 'buy' | 'sell';
  price: string;
  quantity: string;
};

export type KalshiFeeSensitivityInput = {
  marketId: string;
  eventObservationId: string;
  seriesObservationId: string;
  fills: {
    instrumentId: string;
    side: 'buy' | 'sell';
    priceUsd: string;
    quantityContracts: string;
  }[];
};

export type KalshiFeeMetadataMutation = Pick<
  UseMutationResult<KalshiFeeMetadataCaptureResult, Error, { marketId: string }, unknown>,
  'isPending' | 'isError' | 'error' | 'isSuccess' | 'variables' | 'data' | 'mutate'
>;

export type KalshiFeeSensitivityMutation = Pick<
  UseMutationResult<KalshiFeeOrderSensitivityResponse, Error, KalshiFeeSensitivityInput, unknown>,
  'isPending' | 'isError' | 'error' | 'isSuccess' | 'variables' | 'data' | 'mutate'
>;

type FeeInstrument = {
  native_instrument_id: string;
  label: string;
};

type KalshiFeePanelProps = {
  marketId: string;
  instruments: readonly FeeInstrument[];
  feeMetadataProbe: KalshiFeeMetadataMutation;
  feeMetadataProbeEnabled: boolean;
  feeSensitivity: KalshiFeeSensitivityMutation;
  renderEvidence: (observationId: string) => ReactNode;
  renderProbeFailure: (error: Error) => ReactNode;
  renderSensitivityError: (error: Error) => ReactNode;
};

const time = (value: string | null | undefined) =>
  value ? new Date(value).toLocaleString() : 'Not recorded';
const shortHash = (value: string | undefined) => (value ? `${value.slice(0, 12)}…` : '—');

export function KalshiFeePanel({
  marketId,
  instruments,
  feeMetadataProbe,
  feeMetadataProbeEnabled,
  feeSensitivity,
  renderEvidence,
  renderProbeFailure,
  renderSensitivityError,
}: KalshiFeePanelProps) {
  const [feeFills, setFeeFills] = useState<KalshiFeeScenarioFill[]>([
    {
      instrumentId: instruments[0]?.native_instrument_id ?? '',
      side: 'buy',
      price: '0.50',
      quantity: '1',
    },
  ]);
  const capturedFeeMetadata =
    feeMetadataProbe.isSuccess && feeMetadataProbe.variables?.marketId === marketId
      ? feeMetadataProbe.data
      : undefined;
  const feeMetadataResolved =
    capturedFeeMetadata?.metadata.fee_resolution_state === 'event_override' ||
    capturedFeeMetadata?.metadata.fee_resolution_state === 'series_inherited';
  const capturedSensitivity =
    feeSensitivity.isSuccess && feeSensitivity.variables?.marketId === marketId
      ? feeSensitivity.data
      : undefined;

  return (
    <div className="fr-fee-metadata-panel">
      <div>
        <strong>Public fee parameters</strong>
        <small>
          Fetches the recorded event’s overrides and series parameters. This evidence does not
          produce an account fee estimate.
        </small>
      </div>
      <button
        className="fr-inspect-button"
        disabled={!feeMetadataProbeEnabled || feeMetadataProbe.isPending}
        onClick={() => feeMetadataProbe.mutate({ marketId })}
      >
        {feeMetadataProbe.isPending && feeMetadataProbe.variables?.marketId === marketId
          ? 'Capturing…'
          : feeMetadataProbeEnabled
            ? 'Capture fee metadata'
            : 'Public probe disabled'}
      </button>
      {feeMetadataProbe.isError &&
        feeMetadataProbe.error &&
        renderProbeFailure(feeMetadataProbe.error)}
      {capturedFeeMetadata && (
        <div className="fr-fee-metadata-result" role="status">
          <strong>
            {capturedFeeMetadata.metadata.effective_fee_type} · multiplier{' '}
            {capturedFeeMetadata.metadata.effective_fee_multiplier}
          </strong>
          <small>
            Override status:{' '}
            {capturedFeeMetadata.metadata.fee_resolution_state.replaceAll('_', ' ')}
          </small>
          <small>
            Series {capturedFeeMetadata.metadata.series_ticker} · not added to candidate economics ·{' '}
            {capturedFeeMetadata.observation_ids.length} immutable evidence records
          </small>
          <small>{capturedFeeMetadata.note}</small>
          <small>
            Event {capturedFeeMetadata.raw_sha256.event} · series{' '}
            {capturedFeeMetadata.raw_sha256.series}
          </small>
          {capturedFeeMetadata.metadata.limitations.map((limitation) => (
            <small key={limitation}>{limitation}</small>
          ))}
          {capturedFeeMetadata.observation_ids.map((observationId, index) => (
            <div key={observationId}>
              <small>
                {index === 0 ? 'Event' : 'Series'} fee evidence {shortHash(observationId)}
              </small>
              {renderEvidence(observationId)}
            </div>
          ))}
          <div className="fr-fee-sensitivity-form">
            <small className="fr-fee-sensitivity-guidance">
              One-order taker scenario. Fill inputs are manual, share one buy or sell side, and are
              not read from the stored order book.
            </small>
            {!feeMetadataResolved && (
              <small className="fr-fee-sensitivity-guidance">
                Fee sensitivity is unavailable until both event override fields are complete or
                explicitly cleared.
              </small>
            )}
            {feeFills.map((fill, index) => (
              <div className="fr-fee-order-fill" key={index}>
                <strong>Fill {index + 1}</strong>
                <label>
                  Contract outcome
                  <select
                    aria-label={`Fill ${index + 1} contract outcome`}
                    value={fill.instrumentId}
                    onChange={(event) =>
                      setFeeFills((current) =>
                        current.map((item, itemIndex) =>
                          itemIndex === index
                            ? { ...item, instrumentId: event.target.value }
                            : item,
                        ),
                      )
                    }
                  >
                    {instruments.map((instrument) => (
                      <option
                        key={instrument.native_instrument_id}
                        value={instrument.native_instrument_id}
                      >
                        {instrument.label} · {instrument.native_instrument_id}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Side
                  <select
                    aria-label={`Fill ${index + 1} side`}
                    value={fill.side}
                    onChange={(event) =>
                      setFeeFills((current) =>
                        current.map((item, itemIndex) =>
                          itemIndex === index
                            ? { ...item, side: event.target.value as 'buy' | 'sell' }
                            : item,
                        ),
                      )
                    }
                  >
                    <option value="buy">Buy</option>
                    <option value="sell">Sell</option>
                  </select>
                </label>
                <label>
                  Price per contract (USD)
                  <input
                    aria-label={`Fill ${index + 1} price per contract (USD)`}
                    type="number"
                    min="0.000001"
                    max="0.999999"
                    step="any"
                    value={fill.price}
                    onChange={(event) =>
                      setFeeFills((current) =>
                        current.map((item, itemIndex) =>
                          itemIndex === index ? { ...item, price: event.target.value } : item,
                        ),
                      )
                    }
                  />
                </label>
                <label>
                  Quantity (contracts)
                  <input
                    aria-label={`Fill ${index + 1} quantity (contracts)`}
                    type="number"
                    min="0.000001"
                    max="1000000"
                    step="any"
                    value={fill.quantity}
                    onChange={(event) =>
                      setFeeFills((current) =>
                        current.map((item, itemIndex) =>
                          itemIndex === index ? { ...item, quantity: event.target.value } : item,
                        ),
                      )
                    }
                  />
                </label>
                {feeFills.length > 1 && (
                  <button
                    className="fr-inspect-button"
                    aria-label={`Remove fill ${index + 1}`}
                    onClick={() =>
                      setFeeFills((current) =>
                        current.filter((_, itemIndex) => itemIndex !== index),
                      )
                    }
                  >
                    Remove
                  </button>
                )}
              </div>
            ))}
            <div className="fr-fee-order-actions">
              <button
                className="fr-inspect-button"
                disabled={feeFills.length >= 32}
                onClick={() =>
                  setFeeFills((current) => [
                    ...current,
                    {
                      instrumentId: current[0].instrumentId,
                      side: current[0].side,
                      price: '0.50',
                      quantity: '1',
                    },
                  ])
                }
              >
                Add fill
              </button>
              <button
                className="fr-inspect-button"
                disabled={
                  !capturedFeeMetadata ||
                  !feeMetadataResolved ||
                  feeSensitivity.isPending ||
                  !instruments.some(
                    (instrument) => instrument.native_instrument_id === feeFills[0].instrumentId,
                  ) ||
                  feeFills.some((item) => item.instrumentId !== feeFills[0].instrumentId) ||
                  feeFills.some((item) => !item.price || !item.quantity) ||
                  feeFills.some((item) => item.side !== feeFills[0].side)
                }
                onClick={() => {
                  if (!capturedFeeMetadata) return;
                  feeSensitivity.mutate({
                    marketId,
                    eventObservationId: capturedFeeMetadata.observation_ids[0],
                    seriesObservationId: capturedFeeMetadata.observation_ids[1],
                    fills: feeFills.map((item) => ({
                      instrumentId: item.instrumentId,
                      side: item.side,
                      priceUsd: item.price,
                      quantityContracts: item.quantity,
                    })),
                  });
                }}
              >
                {feeSensitivity.isPending
                  ? 'Calculating…'
                  : feeMetadataResolved
                    ? 'Calculate order fee'
                    : 'Fee override unresolved'}
              </button>
            </div>
          </div>
          {feeSensitivity.isError &&
            feeSensitivity.error &&
            renderSensitivityError(feeSensitivity.error)}
          {capturedSensitivity && (
            <div className="fr-fee-sensitivity-result" role="status">
              <strong>
                One-order taker sensitivity · {capturedSensitivity.estimate.order_fills.length}{' '}
                manual fill{capturedSensitivity.estimate.order_fills.length === 1 ? '' : 's'} ·{' '}
                {capturedSensitivity.estimate.effective_fee_type} ×{' '}
                {capturedSensitivity.estimate.effective_fee_multiplier}
              </strong>
              <small>
                Hypothetical only. This sensitivity does not modify candidate net economics.
              </small>
              <small>
                Fee metadata received: event{' '}
                {time(capturedSensitivity.estimate.input_received_at_utc[0])} · series{' '}
                {time(capturedSensitivity.estimate.input_received_at_utc[1])}
              </small>
              <small>
                Override status:{' '}
                {capturedSensitivity.estimate.fee_resolution_state.replaceAll('_', ' ')}
              </small>
              {capturedSensitivity.estimate.scenarios.map((scenario) => (
                <div className="fr-fee-order-scenario" key={scenario.account_precision_class}>
                  <small>
                    {scenario.account_precision_class.replaceAll('_', ' ')} · balance quantum $
                    {scenario.balance_quantum} · total fee ${scenario.total_net_fee_usd} (trade $
                    {scenario.total_trade_fee_usd} + rounding ${scenario.total_rounding_fee_usd} −
                    rebates ${scenario.total_rebate_usd}) · balance change $
                    {scenario.total_balance_change_usd}
                  </small>
                  {scenario.fills.map((item) => (
                    <small key={item.fill_index}>
                      Fill {item.fill_index + 1}{' '}
                      {instruments.find(
                        (instrument) =>
                          instrument.native_instrument_id === item.native_instrument_id,
                      )?.label ?? item.native_instrument_id}{' '}
                      {item.side} · trade ${item.trade_fee_rounded_to_microdollar} · rounding $
                      {item.rounding_fee_usd} · rebate ${item.rebate_usd} · carry $
                      {item.accumulated_rounding_after_rebate_usd}
                    </small>
                  ))}
                </div>
              ))}
              <small>{capturedSensitivity.note}</small>
              <small>
                Calculation {shortHash(capturedSensitivity.estimate.calculation_sha256)}
              </small>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
