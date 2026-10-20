import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './api';
import type { PaperAccount, PaperAccountSummary, Stored } from './types';

const fmt = (value: string | undefined) => (value === undefined ? '—' : Number(value).toFixed(4));
export function PaperSummary() {
  const paper = useQuery({
    queryKey: ['paper'],
    queryFn: () => api<PaperAccountSummary>('/paper/summary'),
    refetchInterval: 2000,
  });
  const p = paper.data;
  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Persistent paper broker</h2>
        <span className="badge">
          {p?.status ?? 'UNAVAILABLE'} · {p?.mode ?? '—'}
        </span>
      </div>
      <div className="portfolio-grid">
        {[
          ['Virtual equity', p?.equity],
          ['Available', p?.available],
          ['Reserved', p?.reserved],
          ['Locked', p?.locked],
          ['Paper realized P&L', p?.realized_pnl],
          ['Paper unrealized P&L', p?.unrealized_pnl],
        ].map(([label, value]) => (
          <div key={label}>
            <span>{label}</span>
            <strong>{fmt(value)}</strong>
            <small>virtual USD/pUSD</small>
          </div>
        ))}
      </div>
      <p className="panel-note">
        {p?.paper_trades ?? 0} paper proposals · {p?.hypothetical_fills ?? 0} hypothetical fills ·{' '}
        {p?.settled_positions ?? 0} modeled settlements · {p?.pending_actions ?? 0} pending actions.
        Fills remain unverified.
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
          <h2>Internal virtual strategy controls</h2>
          <span className="badge">PAPER ONLY</span>
        </div>
        <div className="toolbar">
          <button
            disabled={control.isPending || p?.status === 'STOPPED'}
            onClick={() => control.mutate({ paused: p?.status !== 'PAUSED' })}
          >
            {p?.status === 'PAUSED' ? 'Resume paper decisions' : 'Pause paper decisions'}
          </button>
          <select
            aria-label="Paper execution model"
            value={p?.execution.name ?? 'standard'}
            onChange={(e) => control.mutate({ execution_model: e.target.value })}
          >
            {['optimistic', 'standard', 'conservative'].map((x) => (
              <option key={x}>{x}</option>
            ))}
          </select>
          <span className="toolbar-note">
            {p?.strategy_version} · {p?.recovery_count ?? 0} reconciled startups
          </span>
        </div>
        {(control.error || paper.error) && (
          <p role="alert" className="alert danger">
            {control.error?.message ?? paper.error?.message}
          </p>
        )}
        <p className="panel-note">
          Execution-model changes apply to new proposals. Emergency stop is in Settings and survives
          restart. All orders below exist only in Midas.
        </p>
        <div className="portfolio-grid">
          {[
            ['Fees', p?.fees],
            ['Unmatched shares', p?.net_exposure_shares],
            ['Maximum drawdown', p?.max_drawdown],
          ].map(([l, v]) => (
            <div key={l}>
              <span>{l}</span>
              <strong>{fmt(v)}</strong>
            </div>
          ))}
        </div>
        <div className="book-audit">
          <h3>Risk allocation</h3>
          {p &&
            [
              ['Total capital', p.locked, p.risk_limits.max_exposure],
              [
                'Reserved + locked',
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
          <span className="badge">HYPOTHETICAL · UNVERIFIED FILLS</span>
        </div>
        {p?.positions.length ? (
          p.positions.map((position) => (
            <details className="book-audit" key={position.id}>
              <summary>
                {position.market_id} · {position.execution_model.name} ·{' '}
                {position.settled ? 'MODELED SETTLEMENT' : 'OPEN PAPER POSITION'} · locked{' '}
                {fmt(position.portfolio.locked)}
              </summary>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Virtual order</th>
                      <th>Status</th>
                      <th>Filled / target</th>
                      <th>Acknowledged</th>
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
              <h3>Order and accounting timeline</h3>
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
              <h3>Full decision and assumptions</h3>
              <pre className="artifact-json">{JSON.stringify(position.decision, null, 2)}</pre>
            </details>
          ))
        ) : (
          <p className="panel-note">
            No virtual positions. Zero trades can be a correct research result.
          </p>
        )}
      </section>
      <section className="panel">
        <div className="panel-header">
          <h2>Every paper strategy decision</h2>
        </div>
        {decisionHistory.data?.map(({ decision: d }) => (
          <details className="book-audit" key={d.id}>
            <summary>
              {d.market_id} · {d.risk.allowed ? 'PAPER APPROVED' : 'PAPER REJECTED'} ·{' '}
              {d.risk.reasons.join('; ')}
            </summary>
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
          <h2>Durable event journal</h2>
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
        <h2>Execution sensitivity laboratory</h2>
        <span className="badge">SYNTHETIC · PRODUCTION BROKER STATE MACHINE</span>
      </div>
      <div className="toolbar">
        <label>
          Seed{' '}
          <input
            aria-label="Experiment seed"
            type="number"
            min={0}
            value={seed}
            onChange={(e) => setSeed(Number(e.target.value))}
          />
        </label>
        <label>
          Model{' '}
          <select
            aria-label="Experiment model"
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
            {['optimistic', 'standard', 'conservative'].map((x) => (
              <option key={x}>{x}</option>
            ))}
          </select>
        </label>
        <label>
          Latency ms{' '}
          <input
            aria-label="Experiment latency"
            type="number"
            min={0}
            max={60000}
            value={latency}
            onChange={(e) => setLatency(Number(e.target.value))}
          />
        </label>
        <label>
          Liquidity fraction{' '}
          <input
            aria-label="Executable fraction"
            type="number"
            min={0}
            max={1}
            step="0.1"
            value={fraction}
            onChange={(e) => setFraction(e.target.value)}
          />
        </label>
        <label>
          Adverse ticks{' '}
          <input
            aria-label="Adverse ticks"
            type="number"
            min={0}
            value={ticks}
            onChange={(e) => setTicks(Number(e.target.value))}
          />
        </label>
        <label>
          Fault{' '}
          <select
            aria-label="Experiment fault"
            value={fault}
            onChange={(e) => setFault(e.target.value)}
          >
            {[
              'none',
              'withdraw',
              'pause',
              'lost_ack',
              'delayed_ack',
              'out_of_order',
              'fee_change',
              'invalidate',
              'restart',
              'duplicate',
              'metadata_conflict',
              'settlement_delay',
              'ledger_fault',
              'malformed',
              'stale',
            ].map((x) => (
              <option key={x}>{x}</option>
            ))}
          </select>
        </label>
        <button disabled={run.isPending} onClick={() => run.mutate(false)}>
          Run paper experiment
        </button>
        <button disabled={run.isPending} onClick={() => run.mutate(true)}>
          Compare three models
        </button>
      </div>
      <p className="panel-note">
        Comparison uses the documented presets on the identical seed and fixture. Single runs use
        the edited parameters. Repeat a run with identical inputs to reproduce its artifact hash.
      </p>
      {run.error && (
        <p className="alert danger" role="alert">
          {run.error.message}
        </p>
      )}
      {comparisons.length > 0 && (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Execution model</th>
                <th>Theoretical profit</th>
                <th>Settled paper P&L</th>
                <th>Hypothetical fills</th>
                <th>Fees</th>
                <th>Drawdown</th>
              </tr>
            </thead>
            <tbody>
              {comparisons.map((c) => (
                <tr key={c.model}>
                  <td>{c.model}</td>
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
            Download reproducibility artifact
          </a>
          <details className="book-audit">
            <summary>Event timeline, portfolio evolution and configuration</summary>
            <pre className="artifact-json">{JSON.stringify(result, null, 2)}</pre>
          </details>
        </>
      )}
      <div className="book-audit">
        <h3>Recorded experiment history</h3>
        {history.data?.map((h) => (
          <button
            className="market-button"
            key={h.key}
            onClick={() => setSelected({ id: h.key, result: h.payload })}
          >
            {new Date(h.received_ts_ms).toLocaleString()} ·{' '}
            {h.payload.runs ? 'three-model comparison' : h.payload.execution_model?.name} ·{' '}
            {h.key.slice(0, 8)}
          </button>
        ))}
      </div>
    </section>
  );
}
