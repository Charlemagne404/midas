import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './api';
import type { PaperAccount, PaperAccountSummary, Stored } from './types';

const fmt = (value: string | undefined) => (value === undefined ? '—' : Number(value).toFixed(4));
const fmtBalance = (value: string | undefined) =>
  value === undefined
    ? '—'
    : Number(value).toLocaleString(undefined, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      });
const fillAssumptions: Record<string, string> = {
  optimistic: 'Best case',
  standard: 'Typical estimate',
  conservative: 'More cautious',
};
const experimentConditions: Record<string, string> = {
  none: 'No added issue',
  withdraw: 'Available funds are withdrawn',
  pause: 'The market pauses',
  lost_ack: 'An order confirmation is lost',
  delayed_ack: 'An order confirmation is delayed',
  out_of_order: 'Updates arrive out of order',
  fee_change: 'Fees change',
  invalidate: 'The market result is invalidated',
  restart: 'The service restarts',
  duplicate: 'An update is received twice',
  metadata_conflict: 'Market details change',
  settlement_delay: 'Settlement is delayed',
  ledger_fault: 'The event journal has a write issue',
  malformed: 'A response has invalid data',
  stale: 'The market data is old',
};
export function PaperSummary({ compact = false }: { compact?: boolean }) {
  const paper = useQuery({
    queryKey: ['paper'],
    queryFn: () => api<PaperAccountSummary>('/paper/summary'),
    refetchInterval: 2000,
  });
  const p = paper.data;
  const balances = [
    ['Total virtual balance', p?.equity],
    ['Available to use', p?.available],
    ['Set aside for proposals', p?.reserved],
    ['Used by open positions', p?.locked],
    ['Result from closed positions', p?.realized_pnl],
    ['Estimated result from open positions', p?.unrealized_pnl],
  ];
  return (
    <section className={`panel paper-summary ${compact ? 'compact' : ''}`}>
      <div className="panel-header">
        <h2>Virtual portfolio</h2>
        <span className="badge cyan">
          {paper.error
            ? 'Portfolio unavailable'
            : p?.status
              ? p.status.replaceAll('_', ' ').toLowerCase()
              : 'Loading portfolio'}
        </span>
      </div>
      {compact ? (
        <div className="paper-summary-overview">
          <div>
            <span>Current simulated balance</span>
            <strong>
              {fmtBalance(p?.equity)} <small>virtual USD</small>
            </strong>
          </div>
          <p>This portfolio uses simulated funds. It does not represent money in a real account.</p>
          <details className="paper-account-details">
            <summary>Show portfolio breakdown</summary>
            <div className="portfolio-grid">
              {balances.map(([label, value]) => (
                <div key={label}>
                  <span>{label}</span>
                  <strong>{fmt(value)}</strong>
                  <small>virtual USD</small>
                </div>
              ))}
            </div>
          </details>
        </div>
      ) : (
        <div className="portfolio-grid">
          {balances.map(([label, value]) => (
            <div key={label}>
              <span>{label}</span>
              <strong>{fmt(value)}</strong>
              <small>virtual USD</small>
            </div>
          ))}
        </div>
      )}
      <p className="panel-note">
        Activity: {p?.paper_trades ?? 0} virtual proposals · {p?.hypothetical_fills ?? 0} simulated
        fills · {p?.settled_positions ?? 0} closed positions · {p?.pending_actions ?? 0} pending. A
        simulated fill does not prove that a real order could execute.
      </p>
    </section>
  );
}

export function PaperPage() {
  const qc = useQueryClient();
  const [decisionCursor, setDecisionCursor] = useState<number | undefined>();
  const decisionHistory = useQuery({
    queryKey: ['paper-decisions', decisionCursor],
    queryFn: () =>
      api<{ revision: number; decision: PaperAccount['decisions'][number] }[]>(
        `/paper/decisions${decisionCursor === undefined ? '' : `?before_revision=${decisionCursor}`}`,
      ),
    refetchInterval: decisionCursor === undefined ? 5000 : false,
  });
  const paper = useQuery({
    queryKey: ['paper'],
    queryFn: () => api<PaperAccountSummary>('/paper/summary'),
    refetchInterval: 2000,
  });
  const journal = useQuery({
    queryKey: ['paper-journal'],
    queryFn: () =>
      api<
        { event_id: string; revision: number; command: Record<string, unknown>; checksum: string }[]
      >('/paper/journal'),
    refetchInterval: 5000,
  });
  const control = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api('/paper', { method: 'PATCH', body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['paper'] }),
  });
  const p = paper.data;
  return (
    <>
      <PaperSummary />
      <section className="panel">
        <div className="panel-header">
          <h2>Paper simulation settings</h2>
          <span className="badge cyan">SIMULATION ONLY</span>
        </div>
        <div className="toolbar">
          <button
            disabled={control.isPending || p?.status === 'STOPPED'}
            onClick={() => control.mutate({ paused: p?.status !== 'PAUSED' })}
          >
            {p?.status === 'PAUSED' ? 'Resume virtual decisions' : 'Pause new virtual decisions'}
          </button>
          <label className="paper-model-control">
            Fill assumption
            <select
              aria-label="Paper fill assumption"
              value={p?.execution.name ?? 'standard'}
              onChange={(e) => control.mutate({ execution_model: e.target.value })}
            >
              <option value="optimistic">Best case</option>
              <option value="standard">Typical estimate</option>
              <option value="conservative">More cautious</option>
            </select>
          </label>
        </div>
        {(control.error || paper.error) && (
          <p role="alert" className="alert danger">
            {control.error?.message ?? paper.error?.message}
          </p>
        )}
        <p className="panel-note">
          These settings affect new virtual proposals only. The emergency stop is in System →
          Settings. No real orders are sent.
        </p>
        <div className="portfolio-grid">
          {[
            ['Fees', p?.fees],
            ['Shares not paired', p?.net_exposure_shares],
            ['Largest estimated balance drop', p?.max_drawdown],
          ].map(([l, v]) => (
            <div key={l}>
              <span>{l}</span>
              <strong>{fmt(v)}</strong>
            </div>
          ))}
        </div>
        <div className="book-audit">
          <h3>How virtual funds are reserved</h3>
          {p &&
            [
              ['Total capital', p.locked, p.risk_limits.max_exposure],
              [
                'Reserved and in use',
                String(Number(p.reserved) + Number(p.locked)),
                p.risk_limits.max_exposure,
              ],
            ].map(([label, value, max]) => (
              <div className="definition-row" key={label}>
                <span>
                  {label}: {fmt(String(value))} / {String(max)}
                </span>
                <meter aria-label={String(label)} min={0} max={Number(max)} value={Number(value)} />
              </div>
            ))}
        </div>
      </section>
      <section className="panel">
        <div className="panel-header">
          <h2>Simulated positions and virtual orders</h2>
          <span className="badge">VIRTUAL · ESTIMATED FILLS</span>
        </div>
        {p?.positions.length ? (
          p.positions.map((position) => (
            <details className="book-audit" key={position.id}>
              <summary>
                {position.market_id} ·{' '}
                {fillAssumptions[position.execution_model.name] ?? position.execution_model.name} ·{' '}
                {position.settled ? 'settled in the model' : 'open virtual position'} · amount in
                use {fmt(position.portfolio.locked)}
              </summary>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Order reference</th>
                      <th>Status</th>
                      <th>Filled / target</th>
                      <th>Confirmation received</th>
                    </tr>
                  </thead>
                  <tbody>
                    {position.orders.map((o) => (
                      <tr key={o.id}>
                        <td>
                          <code>{o.id}</code>
                        </td>
                        <td>{o.status}</td>
                        <td>
                          {fmt(String(Number(o.quantity) - Number(o.remaining)))} / {o.quantity}
                        </td>
                        <td>{String(o.acknowledged)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <h3>Recorded steps</h3>
              {position.ledger.map((entry, i) => (
                <div className="definition-row" key={i}>
                  <span>
                    {String(entry.kind)} · {String(entry.order_id ?? entry.asset_id)}
                  </span>
                  <code>
                    {String(entry.quantity)} shares · fee {String(entry.fee)} · t=
                    {String(entry.time_ms)}
                  </code>
                </div>
              ))}
              <details className="book-audit">
                <summary>Show technical model details</summary>
                <pre className="artifact-json">{JSON.stringify(position.decision, null, 2)}</pre>
              </details>
            </details>
          ))
        ) : (
          <p className="panel-note">
            No virtual positions. Zero trades can be a correct research result.
          </p>
        )}
      </section>
      <details className="workspace-guide paper-advanced-records">
        <summary>Advanced paper records</summary>
        <div>
          <section className="panel">
            <div className="panel-header">
              <h2>Decision records</h2>
            </div>
            {decisionHistory.data?.map(({ decision: d }) => (
              <details className="book-audit" key={d.id}>
                <summary>
                  {d.market_id} ·{' '}
                  {d.risk.allowed ? 'Allowed by safety checks' : 'Blocked by safety checks'}
                </summary>
                <p className="panel-note">{d.risk.reasons.join('; ')}</p>
                <pre className="artifact-json">{JSON.stringify(d, null, 2)}</pre>
              </details>
            ))}
          </section>
          <div className="toolbar">
            <button onClick={() => setDecisionCursor(undefined)}>Newest decisions</button>
            <button
              disabled={!decisionHistory.data?.length}
              onClick={() =>
                setDecisionCursor(Math.min(...(decisionHistory.data ?? []).map((d) => d.revision)))
              }
            >
              Older decisions
            </button>
          </div>
          <section className="panel">
            <div className="panel-header">
              <h2>System event journal</h2>
            </div>
            {journal.data?.slice(0, 30).map((e) => (
              <details className="book-audit" key={e.revision}>
                <summary>
                  {e.revision} · {e.event_id}
                </summary>
                <code className="identifier">{e.checksum}</code>
                <pre className="artifact-json">{JSON.stringify(e.command, null, 2)}</pre>
              </details>
            ))}
          </section>
        </div>
      </details>
    </>
  );
}

interface ExperimentRun {
  execution_model: {
    name: string;
    latency_ms: number;
    liquidity_fraction: string;
    adverse_ticks: number;
    seed: number;
  };
  seed: number;
  fault: string;
  artifact_hash: string;
  actual_result: PaperAccount;
  timeline: { command: Record<string, unknown>; portfolio: PaperAccount }[];
  inputs: Record<string, unknown>[];
  config: Record<string, unknown>;
  passed: boolean;
}
interface ExperimentResult {
  runs?: ExperimentRun[];
  comparison?: {
    model: string;
    theoretical_profit: string;
    realized_pnl: string;
    fill_count: number;
    fees: string;
    max_drawdown: string;
    lockup_ms: number;
  }[];
  actual_result?: PaperAccount;
  execution_model?: ExperimentRun['execution_model'];
  seed?: number;
  fault?: string;
}

export function ExperimentPanel() {
  const [seed, setSeed] = useState(7);
  const [model, setModel] = useState('standard');
  const [latency, setLatency] = useState(200);
  const [fraction, setFraction] = useState('0.8');
  const [ticks, setTicks] = useState(0);
  const [fault, setFault] = useState('none');
  const [selected, setSelected] = useState<{ id: string; result: ExperimentResult } | null>(null);
  const qc = useQueryClient();
  const history = useQuery({
    queryKey: ['experiments'],
    queryFn: () => api<Stored<ExperimentResult>[]>('/experiments'),
  });
  const run = useMutation({
    mutationFn: (compare: boolean) =>
      api<{ id: string; result: ExperimentResult }>('/experiments', {
        method: 'POST',
        body: JSON.stringify({
          seed,
          fault,
          compare,
          execution: {
            name: model,
            latency_ms: latency,
            liquidity_fraction: fraction,
            adverse_ticks: ticks,
          },
        }),
      }),
    onSuccess: (data) => {
      setSelected(data);
      qc.invalidateQueries({ queryKey: ['experiments'] });
    },
  });
  const result = selected?.result;
  const comparisons =
    result?.comparison ??
    (result?.actual_result
      ? [
          {
            model: result.execution_model?.name ?? model,
            theoretical_profit: '—',
            realized_pnl: result.actual_result.realized_pnl,
            fill_count: result.actual_result.hypothetical_fills,
            fees: result.actual_result.fees,
            max_drawdown: result.actual_result.max_drawdown,
            lockup_ms: 0,
          },
        ]
      : []);
  return (
    <section className="panel">
      <div className="panel-header">
        <h2>How assumptions change virtual fills</h2>
        <span className="badge">SAMPLE DATA · SIMULATION ONLY</span>
      </div>
      <div className="toolbar experiment-toolbar">
        <label>
          Repeat number
          <input
            aria-label="Experiment repeat number"
            type="number"
            min={0}
            value={seed}
            onChange={(e) => setSeed(Number(e.target.value))}
          />
        </label>
        <label>
          Fill assumption
          <select
            aria-label="Experiment fill assumption"
            value={model}
            onChange={(e) => {
              setModel(e.target.value);
              setLatency(
                e.target.value === 'optimistic' ? 0 : e.target.value === 'conservative' ? 750 : 200,
              );
              setFraction(
                e.target.value === 'optimistic'
                  ? '1'
                  : e.target.value === 'conservative'
                    ? '0.5'
                    : '0.8',
              );
              setTicks(e.target.value === 'conservative' ? 1 : 0);
            }}
          >
            {Object.entries(fillAssumptions).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <button
          className="primary-button"
          disabled={run.isPending}
          onClick={() => run.mutate(false)}
        >
          Run virtual experiment
        </button>
        <button disabled={run.isPending} onClick={() => run.mutate(true)}>
          Compare 3 assumptions
        </button>
      </div>
      <details className="workspace-guide experiment-advanced">
        <summary>Advanced assumptions</summary>
        <div className="experiment-advanced-grid">
          <label>
            Delay before fill (ms)
            <input
              aria-label="Experiment delay before fill in milliseconds"
              type="number"
              min={0}
              max={60000}
              value={latency}
              onChange={(e) => setLatency(Number(e.target.value))}
            />
          </label>
          <label>
            Available amount (0 to 1)
            <input
              aria-label="Share of available amount"
              type="number"
              min={0}
              max={1}
              step="0.1"
              value={fraction}
              onChange={(e) => setFraction(e.target.value)}
            />
          </label>
          <label>
            Price movement against fill (ticks)
            <input
              aria-label="Price movement against fill in ticks"
              type="number"
              min={0}
              value={ticks}
              onChange={(e) => setTicks(Number(e.target.value))}
            />
          </label>
          <label>
            Scenario condition
            <select
              aria-label="Scenario condition"
              value={fault}
              onChange={(e) => setFault(e.target.value)}
            >
              {Object.entries(experimentConditions).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
        </div>
        <p>
          These options change only the virtual scenario. On the 0 to 1 scale, 1 uses all of the
          available amount and 0.5 uses half. One price tick is the model’s smallest price step.
        </p>
      </details>
      <p className="panel-note">
        Use the same repeat number to reproduce a run. A modeled fill does not show that an order
        could have filled in a real market.
      </p>
      {run.error && (
        <p className="alert danger" role="alert">
          {run.error.message}
        </p>
      )}
      {!selected && !run.isPending && (
        <div className="empty">
          <h3>Ready for an experiment</h3>
          <p>Run one assumption or compare all three. Results here use a saved sample scenario.</p>
        </div>
      )}
      {comparisons.length > 0 && (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Fill assumption</th>
                <th>Estimate before fills</th>
                <th>Virtual result</th>
                <th>Simulated fills</th>
                <th>Modeled fees</th>
                <th>Largest virtual drop</th>
              </tr>
            </thead>
            <tbody>
              {comparisons.map((c) => (
                <tr key={c.model}>
                  <td>{fillAssumptions[c.model] ?? c.model}</td>
                  <td>{c.theoretical_profit}</td>
                  <td>{c.realized_pnl}</td>
                  <td>{c.fill_count}</td>
                  <td>{c.fees}</td>
                  <td>{c.max_drawdown}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {selected && (
        <>
          <a className="market-button" href={`/api/experiments/${selected.id}`} download>
            Download result record
          </a>
          <details className="book-audit">
            <summary>Event timeline, portfolio evolution and configuration</summary>
            <pre className="artifact-json">{JSON.stringify(result, null, 2)}</pre>
          </details>
        </>
      )}
      <details className="experiment-history">
        <summary>Previous experiments ({history.data?.length ?? 0})</summary>
        <div>
          {history.data?.length ? (
            history.data.map((h) => (
              <button
                className="market-button"
                key={h.key}
                onClick={() => setSelected({ id: h.key, result: h.payload })}
              >
                {new Date(h.received_ts_ms).toLocaleString()} ·{' '}
                {h.payload.runs
                  ? '3-assumption comparison'
                  : (fillAssumptions[h.payload.execution_model?.name ?? ''] ??
                    'Custom assumptions')}
              </button>
            ))
          ) : (
            <p>No previous experiments have been saved yet.</p>
          )}
        </div>
      </details>
    </section>
  );
}
