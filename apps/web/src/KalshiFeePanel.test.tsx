import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import {
  KalshiFeePanel,
  type KalshiFeeMetadataMutation,
  type KalshiFeeMetadataCaptureResult,
  type KalshiFeeOrderSensitivityResponse,
  type KalshiFeeSensitivityMutation,
} from './KalshiFeePanel';

afterEach(cleanup);

const MARKET_ID = 'kalshi:KX-FEE-1';
const FEE_METADATA: KalshiFeeMetadataCaptureResult = {
  market_id: MARKET_ID,
  metadata: {
    series_ticker: 'KX-FEE-SERIES',
    event_fee_type_override: 'quadratic',
    event_fee_multiplier_override: '1',
    series_fee_type: 'quadratic',
    series_fee_multiplier: '1',
    effective_fee_type: 'quadratic',
    effective_fee_multiplier: '1',
    fee_resolution_state: 'event_override',
    economics_state: 'unresolved',
    limitations: ['Account rounding remains unknown.'],
  },
  observation_ids: ['event-fee-observation', 'series-fee-observation'],
  raw_sha256: { event: 'a'.repeat(64), series: 'b'.repeat(64) },
  fee_cost_modeled: false,
  note: 'Public fee parameters only; account fee is not inferred.',
};

const FEE_SENSITIVITY: KalshiFeeOrderSensitivityResponse = {
  market_id: MARKET_ID,
  estimate: {
    model_version: 'kalshi-event-taker-order-fee-sensitivity-v2',
    series_ticker: 'KX-FEE-SERIES',
    effective_fee_type: 'quadratic',
    effective_fee_multiplier: '1',
    fee_resolution_state: 'event_override',
    input_received_at_utc: ['2026-10-29T10:00:00Z', '2026-10-29T10:00:01Z'],
    order_fills: [
      {
        native_instrument_id: 'KX-FEE-1:YES',
        side: 'buy',
        price_usd: '0.50',
        quantity_contracts: '1',
      },
    ],
    scenarios: [
      {
        account_precision_class: 'non_direct_member',
        balance_quantum: '0.01',
        fills: [
          {
            fill_index: 0,
            native_instrument_id: 'KX-FEE-1:YES',
            side: 'buy',
            trade_fee_rounded_to_microdollar: '0.0175',
            rounding_fee_usd: '0.0025',
            rebate_usd: '0',
            accumulated_rounding_after_rebate_usd: '0.0025',
            net_fee_usd: '0.02',
          },
        ],
        total_trade_fee_usd: '0.0175',
        total_rounding_fee_usd: '0.0025',
        total_rebate_usd: '0',
        total_net_fee_usd: '0.02',
        total_balance_change_usd: '-0.52',
      },
    ],
    calculation_sha256: 'c'.repeat(64),
    assumptions: ['Manual one-order sensitivity; not an account quote.'],
  },
  hypothetical_only: true,
  candidate_net_economics_modified: false,
  note: 'Hypothetical sensitivity only.',
};

const instruments = [
  { native_instrument_id: 'KX-FEE-1:YES', label: 'Yes' },
  { native_instrument_id: 'KX-FEE-1:NO', label: 'No' },
];

const metadataMutation = (
  overrides: Partial<KalshiFeeMetadataMutation> = {},
): KalshiFeeMetadataMutation =>
  ({
    isPending: false,
    isError: false,
    error: null,
    isSuccess: true,
    variables: { marketId: MARKET_ID },
    data: FEE_METADATA,
    mutate: vi.fn(),
    ...overrides,
  }) as KalshiFeeMetadataMutation;

const sensitivityMutation = (
  overrides: Partial<KalshiFeeSensitivityMutation> = {},
): KalshiFeeSensitivityMutation =>
  ({
    isPending: false,
    isError: false,
    error: null,
    isSuccess: false,
    variables: undefined,
    data: undefined,
    mutate: vi.fn(),
    ...overrides,
  }) as KalshiFeeSensitivityMutation;

const renderPanel = (options?: {
  metadata?: KalshiFeeMetadataMutation;
  metadataEnabled?: boolean;
  sensitivity?: KalshiFeeSensitivityMutation;
}) =>
  render(
    <KalshiFeePanel
      marketId={MARKET_ID}
      instruments={instruments}
      feeMetadataProbe={options?.metadata ?? metadataMutation()}
      feeMetadataProbeEnabled={options?.metadataEnabled ?? true}
      feeSensitivity={options?.sensitivity ?? sensitivityMutation()}
      renderEvidence={(observationId) => <span>Evidence {observationId}</span>}
      renderProbeFailure={(error) => <div role="alert">{error.message}</div>}
      renderSensitivityError={(error) => <div role="alert">{error.message}</div>}
    />,
  );

it('keeps the manual fee calculation disabled until fee metadata is resolved', () => {
  const unresolved = metadataMutation({
    data: {
      ...FEE_METADATA,
      metadata: { ...FEE_METADATA.metadata, fee_resolution_state: 'partial_override' },
    },
  });
  renderPanel({ metadata: unresolved });

  expect(
    screen.getByText(/Fee sensitivity is unavailable until both event override fields/),
  ).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Fee override unresolved' })).toBeDisabled();
});

it('sends only validated manual fills with the captured event and series evidence', () => {
  const mutate = vi.fn();
  renderPanel({ sensitivity: sensitivityMutation({ mutate }) });

  fireEvent.click(screen.getByRole('button', { name: 'Add fill' }));
  fireEvent.change(screen.getByLabelText('Fill 2 side'), { target: { value: 'sell' } });
  expect(screen.getByRole('button', { name: 'Calculate order fee' })).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Fill 2 side'), { target: { value: 'buy' } });
  fireEvent.change(screen.getByLabelText('Fill 2 contract outcome'), {
    target: { value: 'KX-FEE-1:NO' },
  });
  expect(screen.getByRole('button', { name: 'Calculate order fee' })).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Fill 2 contract outcome'), {
    target: { value: 'KX-FEE-1:YES' },
  });
  fireEvent.change(screen.getByLabelText('Fill 2 price per contract (USD)'), {
    target: { value: '0.72' },
  });
  fireEvent.change(screen.getByLabelText('Fill 2 quantity (contracts)'), {
    target: { value: '3.25' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Calculate order fee' }));

  expect(mutate).toHaveBeenCalledWith({
    marketId: MARKET_ID,
    eventObservationId: 'event-fee-observation',
    seriesObservationId: 'series-fee-observation',
    fills: [
      {
        instrumentId: 'KX-FEE-1:YES',
        side: 'buy',
        priceUsd: '0.50',
        quantityContracts: '1',
      },
      {
        instrumentId: 'KX-FEE-1:YES',
        side: 'buy',
        priceUsd: '0.72',
        quantityContracts: '3.25',
      },
    ],
  });
});

it('labels the modeled result as a hypothetical fee sensitivity, separate from candidate economics', () => {
  renderPanel({
    sensitivity: sensitivityMutation({
      isSuccess: true,
      variables: {
        marketId: MARKET_ID,
        eventObservationId: 'event-fee-observation',
        seriesObservationId: 'series-fee-observation',
        fills: [],
      },
      data: FEE_SENSITIVITY,
    }),
  });

  const statusText = screen
    .getAllByRole('status')
    .map((status) => status.textContent ?? '')
    .join('\n');
  expect(statusText).toContain('One-order taker sensitivity');
  expect(screen.getByText(/total fee \$0\.02/)).toBeInTheDocument();
  expect(screen.getByText('Hypothetical sensitivity only.')).toBeInTheDocument();
  expect(screen.getByText(/not added to candidate economics/)).toBeInTheDocument();
  expect(statusText).toContain('This sensitivity does not modify candidate net economics.');
});
