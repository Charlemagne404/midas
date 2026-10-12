import { lazy, Suspense, useState } from 'react';
import type { ReactNode } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Activity, ArrowUpRight, ShieldCheck } from 'lucide-react';
import { api } from './api';
import { chartBase } from './chart-theme';

const Chart = lazy(() => import('./Chart').then((module) => ({ default: module.Chart })));
type EconomicParameter =
  'operating_per_fill' | 'redemption_cost' | 'annual_financing_rate' | 'collateral_value_factor';
type Economics = {
  units: Record<EconomicParameter, string>;
  limitations: string[];
  policies: {
    policy: string;
    baseline_downside_score: number;
    mean_break_even_operating_per_fill: string | null;
    points: {
      parameter: EconomicParameter;
      value: string;
      mean_pnl: number;
      cvar_05_loss: number;
      score: number;
    }[];
  }[];
};
type EconomicStudy = {
  study_id: string;
  source_groups: number;
  correlated_variants: number;
  conditions: { name: string; tournament_id: string; leaderboard: Rank[] }[];
  paired_comparisons: Record<
    string,
    {
      policies: {
        policy: string;
        mean_pnl_difference: number;
        episode_bootstrap_95: number[];
      }[];
    }
  >;
  limitations: string[];
  interpretation: string;
};
type Metrics = {
  mae?: number;
  rmse?: number;
  positive_mae?: number | null;
  positive_rmse?: number | null;
  brier: number;
  log_loss: number;
  precision: number;
  recall: number;
  pr_auc: number | null;
  base_episodes: number;
  reliability: { predicted: number | null; observed: number | null; count: number }[];
};
type Dataset = {
  dataset_id: string;
  label_target?: string;
  execution_cost_label?: string;
  spec?: { costs?: Record<string, unknown>; families?: string[]; observation_latency_ms?: number };
  decision_scope?: string;
  rows: number;
  eligible_base_episodes: number;
  generated_base_episodes: number;
  partition_rows: Record<string, number>;
  label_frequency: Record<string, number>;
  limitations: string[];
  quality?: {
    warnings: string[];
    constant_features: string[];
    duplicate_vector_groups: number;
    cross_partition_duplicate_vector_groups: number;
    ambiguous_observable_vectors: number;
  };
};
type Model = {
  task?: string;
  label_version?: string;
  loss_definition?: string;
  quoted_baseline_definition?: string;
  baselines_validation?: Record<string, Metrics>;
  independent_policy_evaluations?: number;
  validation_policy_comparisons?: number;
  model_id: string;
  label_target?: string;
  family: string;
  state: string;
  dataset_id: string;
  artifact_sha256: string;
  training_duration_seconds: number;
  configuration: Record<string, unknown>;
  validation: Metrics | null;
  test: Metrics | null;
  curves?: {
    epoch?: number;
    timesteps?: number;
    training_loss?: number;
    validation_loss?: number;
    episode_return?: number;
  }[];
  limitations: string[];
  checkpoints: string[];
  timesteps?: number;
  training_episodes?: number;
  policy_evaluations?: { tournament_id: string; base_episodes: number }[];
  diagnostics?: {
    label_target?: string;
    false_positive_count?: number;
    false_negative_count?: number;
    base_episodes: number;
    false_completion_count: number;
    missed_completion_count: number;
    feature_sensitivity: {
      feature: string;
      mean_brier_increase: number;
      episode_bootstrap_95: number[];
    }[];
    representative_errors: {
      base_episode_id: string;
      family: string;
      execution_model: string;
      error: string;
      completion_probability: number;
      predicted_probability?: number;
    }[];
    limitations: string[];
  };
};
const isSeverity = (model: Model | undefined) => model?.task === 'residual_severity_regression';
const isCost = (model: Model | undefined) => model?.task === 'execution_cost_regression';
const isRegression = (model: Model | undefined) => isSeverity(model) || isCost(model);
const regressionUnits = (model: Model | undefined) => (isCost(model) ? 'virtual USD' : 'shares');
type Job = {
  job_id: string;
  state: string;
  configuration: { kind: string };
  progress: { done: number; total: number } | null;
  error: string | null;
  unit: string;
  budget: Record<string, number>;
  result: Record<string, string> | null;
  elapsed_seconds?: number;
  active_artifact?: { kind: string; identity: string };
};
type Rank = {
  policy: string;
  mean_pnl: number;
  worst_loss: number;
  cvar_05_loss: number;
  score: number;
  mean_pnl_episode_bootstrap_95: number[];
  no_trade_fraction: number;
  invariant_violations: number;
  partial_orders: number;
  base_episodes: number;
  quantiles: number[];
  max_drawdown: number;
  rank?: number;
  unsupported_decisions?: number;
};
type Tournament = {
  policy_bindings?: Record<string, { model_id: string; threshold: number; size: string }>;
  cost_policy_bindings?: Record<
    string,
    { kind: string; specification: { model_id: string; max_cost_usd: string; margin_usd: string } }
  >;
  model_dataset_bindings?: Record<string, { dataset_id: string; label_target: string }>;
  tournament_id: string;
  base_episodes: number;
  variants: number;
  leaderboard: Rank[];
  conclusion: string;
  ranking_objective: string;
  uncertainty_note: string;
  configuration: Record<string, unknown>;
  paired: {
    policy: string;
    control: string;
    mean_difference: number;
    bootstrap_95: number[];
    base_episodes: number;
  }[];
};

function policyTarget(tournament: Tournament | undefined, policy: string) {
  const modelId =
    tournament?.policy_bindings?.[policy]?.model_id ??
    tournament?.cost_policy_bindings?.[policy]?.specification.model_id ??
    policy;
  return tournament?.model_dataset_bindings?.[modelId]?.label_target;
}
type Row = {
  id: string;
  policy: string;
  family: string;
  execution_model: string;
  metrics: { net_simulated_pnl: string; partial_orders: number };
  passed: boolean;
};
type Replay = {
  result: {
    journal: {
      kind: string;
      time_ms: number;
      before: Record<string, unknown>;
      after: Record<string, unknown>;
      command: unknown;
    }[];
    metrics: Record<string, unknown>;
    final_portfolio: Record<string, unknown>;
  };
  decisions: unknown[];
};
type Overview = {
  recoveries?: {
    recovery_id: string;
    source_groups: number;
    correlated_variants: number;
    paired_recovery_minus_hold_mean: number;
    group_bootstrap_95: number[];
    leaderboard: {
      policy: string;
      mean_pnl: number;
      score: number;
      worst_pnl: number;
      recovery_requests: number;
      recovery_filled_shares: string;
    }[];
    limitations: string[];
  }[];
  searches?: {
    search_id: string;
    state: string;
    validation_tournament: string | null;
    test_tournament: string | null;
    selection: {
      policy: string;
      gate: { threshold: number; size: string } | null;
      reason: string;
    } | null;
    limitations: string[];
  }[];
  datasets: Dataset[];
  models: Model[];
  tournaments: Tournament[];
  jobs: Job[];
  dependencies: Record<string, boolean>;
  health: { memory_mb: Record<string, number>; worker_cpu_cores: number; worker_memory_mb: number };
  findings: {
    title: string;
    interpretation: string;
    caveats: string[];
    tournament_id?: string;
    director_id?: string;
    model_id?: string;
  }[];
  sweeps?: {
    sweep_id: string;
    state: string;
    test_labels_used_for_selection: boolean;
    trials: {
      model_id: string;
      state: string;
      seed: number;
      candidate_index: number;
      validation?: Metrics;
    }[];
    selection?: {
      selected_model_id: string;
      criterion: string;
      candidates: {
        configuration: { family: string; excluded_features?: string[] };
        mean_validation_brier: number;
        seed_brier_range: number[];
      }[];
    };
    ablation?: {
      interpretation: string;
      limitations: string[];
      comparisons: {
        candidate_index: number;
        family: string;
        excluded_features: string[];
        mean_group_brier_change: number;
        group_bootstrap_95: number[];
        source_groups: number;
      }[];
    };
  }[];
  directors?: {
    director_id: string;
    director_version?: string;
    state: string;
    research_question: string;
    planning_rule: string;
    current_stage?: string;
    observation_error?: string;
    steps: { name: string; state: string; artifact?: { kind: string; identity: string } }[];
  }[];
  recorded_sources?: {
    dataset_id: string;
    events?: number;
    capture_start_ms?: number;
    capture_end_ms?: number;
    valid: boolean;
    limitations?: string[];
    error?: string;
  }[];
};
const tabs = [
  'Overview',
  'Training console',
  'Model registry',
  'Tournaments',
  'Research findings',
  'Research director',
] as const;
const n = (value: number | null | undefined, digits = 3) =>
  value == null ? '—' : value.toFixed(digits);
function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="panel lab-panel">
      <div className="panel-header">
        <h2>{title}</h2>
      </div>
      {children}
    </section>
  );
}
function Json({ value }: { value: unknown }) {
  return <pre className="lab-json">{JSON.stringify(value, null, 2)}</pre>;
}
function State({ value }: { value: string }) {
  return (
    <span
      className={`badge ${value === 'COMPLETED' || value === 'EVALUATED' ? 'cyan' : value === 'FAILED' || value === 'INTERRUPTED' ? 'red' : 'gold'}`}
    >
      {value}
    </span>
  );
}

export function Arena() {
  const cache = useQueryClient();
  const [tab, setTab] = useState<(typeof tabs)[number]>('Overview');
  const [datasetId, setDatasetId] = useState('');
  const [modelId, setModelId] = useState('');
  const [tournamentId, setTournamentId] = useState('');
  const [rowId, setRowId] = useState('');
  const [eventIndex, setEventIndex] = useState(0);
  const [family, setFamily] = useState('mlp');
  const [epochs, setEpochs] = useState(80);
  const [learningRate, setLearningRate] = useState(0.001);
  const [hiddenSize, setHiddenSize] = useState(32);
  const [seed, setSeed] = useState(7);
  const [steps, setSteps] = useState(4096);
  const [episodes, setEpisodes] = useState(1000);
  const [labelTarget, setLabelTarget] = useState('completion');
  const [searchModelId, setSearchModelId] = useState('');
  const [economicParameter, setEconomicParameter] =
    useState<EconomicParameter>('operating_per_fill');
  const [scenarioFilter, setScenarioFilter] = useState('');
  const [executionFilter, setExecutionFilter] = useState('');
  const [offset, setOffset] = useState(0);
  const [economicEnabled, setEconomicEnabled] = useState(false);
  const [depthMultiplier, setDepthMultiplier] = useState('1');
  const [feeParameter, setFeeParameter] = useState('');
  const [extraSubmissionLatency, setExtraSubmissionLatency] = useState(0);
  const economicRegime = economicEnabled
    ? {
        depth_multiplier: depthMultiplier,
        taker_fee_rate: feeParameter === '' ? null : feeParameter,
        additional_submission_latency_ms: extraSubmissionLatency,
      }
    : undefined;
  const [costPreferenceCap, setCostPreferenceCap] = useState('0.30');
  const [costPreferenceMargin, setCostPreferenceMargin] = useState('0.10');
  const [costChallengeSeed, setCostChallengeSeed] = useState(313071);
  const [message, setMessage] = useState('');
  const overview = useQuery({
    queryKey: ['arena'],
    queryFn: () => api<Overview>('/arena'),
    refetchInterval: 10000,
  });
  const data = overview.data;
  const selectedDataset = datasetId || data?.datasets[0]?.dataset_id || '';
  const costDataMissing =
    ['cost_ridge', 'cost_mlp'].includes(family) &&
    data?.datasets.find((entry) => entry.dataset_id === selectedDataset)?.execution_cost_label !==
      'initial-position-friction-2';
  const costPolicyModel = data?.models.find(
    (entry) =>
      entry.dataset_id === selectedDataset &&
      isCost(entry) &&
      entry.label_version === 'initial-position-friction-2' &&
      entry.state === 'EVALUATED',
  );
  const selectedSearchModel =
    searchModelId ||
    data?.models.find(
      (entry) => entry.dataset_id === selectedDataset && entry.label_target === 'unmatched',
    )?.model_id ||
    '';
  const selectedTournament = tournamentId || data?.tournaments[0]?.tournament_id || '';
  const model = useQuery({
    queryKey: ['arena-model', modelId],
    queryFn: () => api<Model>(`/arena/models/${modelId}`),
    enabled: !!modelId,
    refetchInterval: (query) =>
      query.state.data?.state === 'TRAINING' ||
      data?.jobs.some(
        (job) =>
          job.active_artifact?.identity === modelId &&
          (['RUNNING', 'QUEUED'].includes(job.state) ||
            (job.state === 'COMPLETED' &&
              job.configuration.kind === 'diagnostics' &&
              !query.state.data?.diagnostics)),
      )
        ? 5000
        : false,
  });
  const tournament = useQuery({
    queryKey: ['arena-tournament', selectedTournament],
    queryFn: () => api<Tournament>(`/arena/tournaments/${selectedTournament}`),
    enabled: !!selectedTournament,
  });
  const economics = useQuery({
    queryKey: ['arena-economics', selectedTournament],
    queryFn: () => api<Economics | null>(`/arena/tournaments/${selectedTournament}/economics`),
    enabled: !!selectedTournament && tab === 'Tournaments',
  });
  const economicStudy = useQuery({
    queryKey: ['arena-economic-study', selectedTournament],
    queryFn: () =>
      api<EconomicStudy | null>(`/arena/tournaments/${selectedTournament}/economic-regimes`),
    enabled: !!selectedTournament && tab === 'Tournaments',
  });
  const rows = useQuery({
    queryKey: ['arena-rows', selectedTournament, scenarioFilter, executionFilter, offset],
    queryFn: () =>
      api<{ total: number; rows: Row[] }>(
        `/arena/tournaments/${selectedTournament}/rows?offset=${offset}&limit=25${scenarioFilter ? `&family=${scenarioFilter}` : ''}${executionFilter ? `&execution_model=${executionFilter}` : ''}`,
      ),
    enabled: !!selectedTournament && tab === 'Tournaments',
  });
  const replay = useQuery({
    queryKey: ['arena-replay', selectedTournament, rowId],
    queryFn: () => api<Replay>(`/arena/tournaments/${selectedTournament}/replay/${rowId}`),
    enabled: !!rowId,
  });
  const submit = useMutation({
    mutationFn: async ({
      configuration,
      validate,
    }: {
      configuration: unknown;
      validate?: boolean;
    }) =>
      api<Job | Record<string, unknown>>(`/arena/jobs${validate ? '/validate' : ''}`, {
        method: 'POST',
        body: JSON.stringify({ configuration }),
      }),
    onSuccess: (_, input) => {
      setMessage(
        input.validate
          ? 'Configuration validated. Ready to launch.'
          : 'Research job admitted. Progress appears below.',
      );
      void cache.invalidateQueries({ queryKey: ['arena'] });
    },
    onError: (error) => setMessage(error.message),
  });
  const cancel = useMutation({
    mutationFn: (id: string) => api(`/arena/jobs/${id}/cancel`, { method: 'POST' }),
    onSuccess: () => {
      setMessage('Cancellation requested. The worker will retain completed artifacts.');
      void cache.invalidateQueries({ queryKey: ['arena'] });
    },
  });
  const cancelDirector = useMutation({
    mutationFn: (id: string) => api(`/arena/directors/${id}/cancel`, { method: 'POST' }),
    onSuccess: () => {
      setMessage('Follow-up cancelled. Completed evidence is retained.');
      void cache.invalidateQueries({ queryKey: ['arena'] });
    },
    onError: (error) => setMessage(error.message),
  });
  const training =
    family === 'ppo'
      ? {
          kind: 'rl',
          rl: {
            dataset_id: selectedDataset,
            seed,
            timesteps: steps,
            hidden_size: hiddenSize,
            learning_rate: learningRate,
          },
        }
      : family === 'cost_ridge' || family === 'cost_mlp'
        ? {
            kind: 'cost',
            cost: {
              dataset_id: selectedDataset,
              family: family === 'cost_ridge' ? 'ridge' : 'cost_mlp',
              epochs,
              hidden_size: hiddenSize,
              learning_rate: learningRate,
              seed,
            },
          }
        : family === 'ridge' || family === 'severity_mlp'
          ? {
              kind: 'severity',
              severity: {
                dataset_id: selectedDataset,
                family,
                epochs,
                hidden_size: hiddenSize,
                learning_rate: learningRate,
                seed,
              },
            }
          : {
              kind: 'supervised',
              training: {
                dataset_id: selectedDataset,
                family,
                epochs,
                hidden_size: hiddenSize,
                learning_rate: learningRate,
                seed,
              },
            };
  const running = data?.jobs.filter((job) => ['RUNNING', 'QUEUED'].includes(job.state)) ?? [];
  if (overview.isPending)
    return (
      <div className="empty" role="status">
        Loading persisted Arena research…
      </div>
    );
  if (overview.isError)
    return (
      <div className="error-box" role="alert">
        {overview.error.message}
      </div>
    );
  return (
    <div className="laboratory arena-workstation">
      <div className="lab-banner">
        <ShieldCheck size={30} />
        <div>
          <div className="eyebrow">PROJECT PROMETHEUS / THE ARENA</div>
          <p>Learn. Compete. Inspect the evidence.</p>
          <small>
            Synthetic scenarios · Hypothetical fills · Economics unverified · Paper only
          </small>
        </div>
        <State value={running.length ? 'RESEARCH ACTIVE' : 'READY'} />
      </div>
      <div className="lab-tabs" role="tablist" aria-label="Arena views">
        {tabs.map((name) => (
          <button
            key={name}
            role="tab"
            aria-selected={tab === name}
            className={tab === name ? 'active' : ''}
            onClick={() => setTab(name)}
          >
            {name}
          </button>
        ))}
      </div>
      {message && (
        <p className="lab-note" role="status">
          {message}
        </p>
      )}
      {tab === 'Overview' && (
        <>
          <div className="metrics-grid">
            {[
              [
                data?.models.filter((model) => model.family !== 'heuristic').length,
                'Fitted models',
                'Plus a documented fixed heuristic control',
              ],
              [running.length, 'Active / queued jobs', 'One bounded worker at a time'],
              [
                data?.tournaments.length,
                'Completed tournaments',
                'Matched independent episode groups',
              ],
              [data?.datasets.length, 'Frozen datasets', 'Variants remain grouped'],
            ].map(([value, label, detail]) => (
              <div className="metric" key={String(label)}>
                <div className="metric-label">
                  {label}
                  <Activity size={14} />
                </div>
                <div className="metric-value">{value}</div>
                <div className="metric-detail">{detail}</div>
              </div>
            ))}
          </div>
          <div className="lab-two">
            <Section title="Research evidence">
              <p className="lab-note">
                {data?.tournaments[0]?.conclusion ??
                  'Independent strategy evaluations have not completed yet.'}
              </p>
              {data?.models.slice(0, 5).map((entry) => (
                <button
                  className="arena-entry"
                  key={entry.model_id}
                  onClick={() => {
                    setModelId(entry.model_id);
                    setTab('Model registry');
                  }}
                >
                  <span>
                    <b>{entry.family.toUpperCase()}</b>
                    <small>{entry.model_id}</small>
                  </span>
                  <State value={entry.state} />
                  <ArrowUpRight size={16} />
                </button>
              ))}
              {!data?.models.length && (
                <p className="empty">
                  No completed model artifacts. Start with a dataset and an interpretable baseline.
                </p>
              )}
            </Section>
            <Section title="Worker health">
              <p className="lab-note">
                {n((data?.health.memory_mb.MemAvailable ?? 0) / 1024, 1)} GiB available ·{' '}
                {data?.health.worker_cpu_cores} CPU core per worker · 4 GiB memory ceiling
              </p>
              <p className="lab-note">
                Jobs survive API and terminal closure under the user systemd supervisor. Every job
                has a wall time limit.
              </p>
              <div className="arena-dependencies">
                {Object.entries(data?.dependencies ?? {}).map(([name, available]) => (
                  <span key={name} className={`badge ${available ? 'cyan' : 'red'}`}>
                    {name} {available ? 'available' : 'missing'}
                  </span>
                ))}
              </div>
            </Section>
          </div>
          <Section title="Dataset provenance">
            {data?.datasets.map((entry) => (
              <div className="arena-entry" key={entry.dataset_id}>
                <span>
                  <b>{entry.dataset_id}</b>
                  <small>
                    Target: {entry.label_target ?? 'completion'} · {entry.rows} labeled variants /{' '}
                    {entry.eligible_base_episodes} base episodes from{' '}
                    {entry.generated_base_episodes} generated episodes
                  </small>
                  <small>
                    {Object.entries(entry.partition_rows)
                      .map(([name, count]) => `${name}: ${count}`)
                      .join(' · ')}
                  </small>
                  {entry.quality && (
                    <details>
                      <summary>Data quality diagnostics</summary>
                      <p>
                        {entry.quality.constant_features.length} constant features ·{' '}
                        {entry.quality.cross_partition_duplicate_vector_groups} identical-vector
                        groups cross partitions · {entry.quality.ambiguous_observable_vectors}{' '}
                        vectors have conflicting labels
                      </p>
                      {entry.quality.warnings.map((warning) => (
                        <p className="lab-footnote" key={warning}>
                          {warning}
                        </p>
                      ))}
                      <a
                        href={`/api/arena/datasets/${entry.dataset_id}/quality`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Full quality report ↗
                      </a>
                    </details>
                  )}
                </span>
                <a
                  href={`/api/arena/datasets/${entry.dataset_id}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  Manifest ↗
                </a>
              </div>
            ))}
            {!data?.datasets.length && <p className="empty">No frozen research datasets yet.</p>}
          </Section>
        </>
      )}
      {tab === 'Overview' && (
        <Section title="Recorded public source coverage">
          <p className="lab-note">
            These public observations are separate from generated training data. No empirical fill
            labels or continuous historical coverage are inferred.
          </p>
          {data?.recorded_sources?.map((source) => (
            <article className="arena-finding" key={source.dataset_id}>
              <h3>{source.dataset_id} / RECORDED PUBLIC</h3>
              <p>
                {source.events ?? 0} recorded events ·{' '}
                {source.valid ? 'Content and provenance verified' : 'Quarantined'} · No execution
                training labels
              </p>
              {source.error && <p role="alert">{source.error}</p>}
              <p className="lab-footnote">{source.limitations?.join(' ')}</p>
            </article>
          ))}
          {!data?.recorded_sources?.length && (
            <p className="empty">No verified public source collections in this artifact root.</p>
          )}
        </Section>
      )}
      {tab === 'Training console' && (
        <>
          <Section title="Training configuration">
            <div className="lab-builder">
              <label>
                Dataset
                <select
                  value={selectedDataset}
                  onChange={(event) => setDatasetId(event.target.value)}
                >
                  {!data?.datasets.length && <option value="">Build a dataset first</option>}
                  {data?.datasets.map((entry) => (
                    <option key={entry.dataset_id} value={entry.dataset_id}>
                      {entry.dataset_id} ·{' '}
                      {entry.execution_cost_label
                        ? 'execution costs available'
                        : (entry.label_target ?? 'completion')}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Architecture
                <select
                  value={family}
                  onChange={(event) => {
                    setFamily(event.target.value);
                    setLearningRate(event.target.value === 'ppo' ? 0.0003 : 0.001);
                  }}
                >
                  {[
                    'constant',
                    'heuristic',
                    'logistic',
                    'tree',
                    'mlp',
                    'ppo',
                    'ridge',
                    'severity_mlp',
                    'cost_ridge',
                    'cost_mlp',
                  ].map((name) => (
                    <option key={name}>{name}</option>
                  ))}
                </select>
              </label>
              <label>
                Training seed
                <input
                  type="number"
                  min={0}
                  value={seed}
                  onChange={(event) => setSeed(Number(event.target.value))}
                />
              </label>
              <label>
                Learning rate
                <input
                  type="number"
                  min={0.000001}
                  step={0.0001}
                  value={learningRate}
                  onChange={(event) => setLearningRate(Number(event.target.value))}
                />
              </label>
              <label>
                Hidden width
                <input
                  type="number"
                  min={4}
                  max={256}
                  value={hiddenSize}
                  onChange={(event) => setHiddenSize(Number(event.target.value))}
                />
              </label>
              {family === 'ppo' ? (
                <label>
                  PPO timesteps
                  <input
                    type="number"
                    min={512}
                    max={100000}
                    value={steps}
                    onChange={(event) => setSteps(Number(event.target.value))}
                  />
                </label>
              ) : (
                <label>
                  Epoch budget
                  <input
                    type="number"
                    min={5}
                    max={1000}
                    value={epochs}
                    onChange={(event) => setEpochs(Number(event.target.value))}
                  />
                </label>
              )}
            </div>
            <p className="lab-note">
              Transforms fit on training rows only. Neural weights are selected using validation
              loss. The final test partition remains frozen.
            </p>
            {costDataMissing && (
              <p className="lab-note" role="alert">
                This architecture requires version-two cost labels, including pending allocation
                reserves. Generate a new execution-cost dataset before training.
              </p>
            )}
            <div className="lab-controls">
              <button
                disabled={!selectedDataset || submit.isPending || costDataMissing}
                onClick={() => submit.mutate({ configuration: training, validate: true })}
              >
                Validate configuration
              </button>
              <button
                className="primary"
                disabled={!selectedDataset || submit.isPending || costDataMissing}
                onClick={() => submit.mutate({ configuration: training })}
              >
                Start training
              </button>
            </div>
          </Section>
          <Section title="Build a versioned dataset">
            <div className="lab-controls">
              <label>
                Prediction target
                <select
                  aria-label="Prediction target"
                  value={labelTarget}
                  onChange={(event) => setLabelTarget(event.target.value)}
                >
                  <option value="completion">Both legs fully complete</option>
                  <option value="unmatched">Residual unmatched inventory</option>
                  <option value="cost">Execution cost (virtual USD)</option>
                  <option value="persistence">Original quote persists to first arrival</option>
                </select>
              </label>
              <label>
                Base episodes
                <input
                  type="number"
                  min={30}
                  max={20000}
                  value={episodes}
                  onChange={(event) => setEpisodes(Number(event.target.value))}
                />
              </label>
              <button
                disabled={submit.isPending}
                onClick={() =>
                  submit.mutate({
                    configuration: {
                      kind: 'dataset',
                      dataset: {
                        episodes,
                        seed: 42070,
                        label_target: labelTarget === 'cost' ? 'completion' : labelTarget,
                        retain_execution_costs: labelTarget === 'cost',
                        ...(labelTarget === 'cost'
                          ? {
                              costs: {
                                operating_per_fill: '0.01',
                                redemption_cost: '0.02',
                                annual_financing_rate: '0.05',
                              },
                            }
                          : {}),
                        decision_scope: labelTarget !== 'completion' ? 'first_admitted' : 'initial',
                      },
                    },
                  })
                }
              >
                Generate dataset
              </button>
            </div>
            <p className="lab-note">
              Generated market behavior and simulated target labels. No real execution probability
              is inferred.
              {labelTarget === 'cost' &&
                ' First admitted position; operating estimate 0.01 virtual USD per fill, redemption 0.02 per settled position, annual financing rate 0.05. Settlement gains/losses and principal are excluded.'}
              {labelTarget === 'unmatched' &&
                ' Samples the first risk-admitted proposal, including later opportunities while the portfolio is still empty.'}
              {labelTarget === 'persistence' &&
                ' Predicts whether the original quantity remains eligible within its original budget and limits at first venue arrival. Future quotes are labels only; fills and second-leg availability are not guaranteed.'}
            </p>
          </Section>
        </>
      )}
      {(tab === 'Training console' || tab === 'Overview') && (
        <Section title="Durable research jobs">
          <div className="arena-table">
            <table>
              <thead>
                <tr>
                  <th>Job / purpose</th>
                  <th>State</th>
                  <th>Persisted progress</th>
                  <th>Elapsed</th>
                  <th>Control</th>
                </tr>
              </thead>
              <tbody>
                {data?.jobs.map((job) => (
                  <tr key={job.job_id}>
                    <td>
                      <a
                        href={`/api/arena/jobs/${job.job_id}/logs`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Worker logs
                      </a>{' '}
                      {job.configuration.kind}
                      <small className="arena-id">{job.job_id}</small>
                      {job.error && <span className="error-box">{job.error}</span>}
                    </td>
                    <td>
                      <State value={job.state} />
                    </td>
                    <td>
                      {job.progress
                        ? `${job.progress.done} / ${job.progress.total}`
                        : 'Awaiting worker'}
                      <small className="arena-id">{job.unit}</small>
                    </td>
                    <td>{n(job.elapsed_seconds, 1)} s</td>
                    <td>
                      {['QUEUED', 'RUNNING'].includes(job.state) && (
                        <button
                          disabled={cancel.isPending}
                          onClick={() => cancel.mutate(job.job_id)}
                        >
                          Cancel
                        </button>
                      )}
                      {(job.result?.model_id || job.active_artifact?.kind === 'models') && (
                        <button
                          onClick={() => {
                            setModelId(job.result?.model_id ?? job.active_artifact?.identity ?? '');
                            setTab('Model registry');
                          }}
                        >
                          {job.result?.model_id ? 'Inspect model' : 'Inspect training'}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!data?.jobs.length && <p className="empty">No jobs submitted.</p>}
        </Section>
      )}
      {tab === 'Model registry' && (
        <>
          <Section title="Model registry">
            <div className="arena-table">
              <table>
                <thead>
                  <tr>
                    <th>Architecture / model</th>
                    <th>Lifecycle</th>
                    <th>Validation metric</th>
                    <th>Held-out metric</th>
                    <th>Training</th>
                    <th>Evidence</th>
                  </tr>
                </thead>
                <tbody>
                  {data?.models.map((entry) => (
                    <tr key={entry.model_id}>
                      <td>
                        {entry.family.toUpperCase()}
                        <small>
                          {entry.family === 'ppo'
                            ? 'Reinforcement policy'
                            : `${entry.label_target ?? 'completion'} prediction`}
                        </small>
                        <small className="arena-id">{entry.model_id}</small>
                      </td>
                      <td>
                        <State value={entry.state} />
                      </td>
                      <td>
                        {n(isRegression(entry) ? entry.validation?.rmse : entry.validation?.brier)}
                        <small>
                          {isRegression(entry) ? `RMSE (${regressionUnits(entry)})` : 'Brier'}
                        </small>
                      </td>
                      <td>
                        {n(isRegression(entry) ? entry.test?.rmse : entry.test?.brier)}
                        <small>
                          {isRegression(entry) ? `RMSE (${regressionUnits(entry)})` : 'Brier'}
                        </small>
                      </td>
                      <td>{n(entry.training_duration_seconds, 1)} s</td>
                      <td>
                        <button onClick={() => setModelId(entry.model_id)}>Inspect model</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!data?.models.length && (
              <p className="empty">No trained models. Open Training console to begin.</p>
            )}
          </Section>
          {model.isError && <p role="alert">{model.error.message}</p>}
          {model.data && (
            <Section title={`${model.data.family.toUpperCase()} / ${model.data.model_id}`}>
              <p className="lab-note">
                {model.data.independent_policy_evaluations
                  ? `Policy independently evaluated in ${model.data.independent_policy_evaluations} tournament(s).`
                  : model.data.validation_policy_comparisons
                    ? 'Validation policy comparisons only; independent policy evaluation pending.'
                    : model.data.test
                      ? 'Frozen independent test evaluated.'
                      : 'Independent test not yet evaluated.'}{' '}
                {model.data.timesteps
                  ? `${model.data.timesteps} PPO transitions / ${model.data.training_episodes} completed training episodes.`
                  : isCost(model.data)
                    ? 'Expected first-position execution friction in virtual USD; excludes settlement gains/losses and purchase principal.'
                    : isRegression(model.data)
                      ? 'Expected residual unmatched shares; not a probability, dollar loss or recovery cost.'
                      : `Execution ${model.data.label_target ?? 'completion'} classifier.`}
              </p>
              {model.data.limitations.length > 0 && (
                <details open={isCost(model.data)}>
                  <summary>Known model limitations</summary>
                  <ul>
                    {model.data.limitations.map((limitation) => (
                      <li key={limitation}>{limitation}</li>
                    ))}
                  </ul>
                </details>
              )}
              {isRegression(model.data) && (
                <p className="lab-note">
                  {model.data.loss_definition} · Aggregate and positive-outcome errors are shown in
                  shares. Severity models are excluded from probability-gated tournaments.
                </p>
              )}
              {model.data.label_target === 'unmatched' && (
                <p className="lab-note">
                  Policy gate accepts predicted residual unmatched risk at or below the configured
                  maximum. No-fill outcomes are negative labels; low unmatched risk does not imply
                  profitable execution.
                </p>
              )}
              {model.data.label_target === 'persistence' && (
                <p className="lab-note">
                  Predicts quote eligibility for the original quantity, capital budget and order
                  limits at first venue arrival. A positive score does not establish fills or
                  availability when the second leg arrives. Future venue quotes are labels only.
                </p>
              )}
              {model.data.curves?.length ? (
                <Suspense fallback={<p>Loading chart…</p>}>
                  <Chart
                    label="Persisted training metrics"
                    option={{
                      ...chartBase,
                      legend: { textStyle: { color: '#a4aabc' } },
                      xAxis: {
                        ...chartBase.xAxis,
                        data: model.data.curves.map((curve) => curve.epoch ?? curve.timesteps),
                      },
                      series:
                        model.data.family === 'ppo'
                          ? [
                              {
                                name: 'Episode return',
                                type: 'line',
                                data: model.data.curves.map((curve) => curve.episode_return),
                                lineStyle: { color: '#4dbfb1' },
                                showSymbol: false,
                              },
                            ]
                          : [
                              {
                                name: 'Training loss',
                                type: 'line',
                                data: model.data.curves.map((curve) => curve.training_loss),
                                showSymbol: false,
                              },
                              {
                                name: 'Validation loss',
                                type: 'line',
                                data: model.data.curves.map((curve) => curve.validation_loss),
                                lineStyle: { color: '#d3a955' },
                                showSymbol: false,
                              },
                            ],
                    }}
                  />
                </Suspense>
              ) : null}
              <div className="lab-two">
                {(['validation', 'test'] as const).map((name) => (
                  <div key={name}>
                    <h3>{name === 'test' ? 'Independent test' : 'Validation'}</h3>
                    {model.data?.[name] ? (
                      <dl className="arena-facts">
                        {(isRegression(model.data)
                          ? ([
                              'mae',
                              'rmse',
                              'positive_mae',
                              'positive_rmse',
                              'base_episodes',
                            ] as const)
                          : ([
                              'brier',
                              'log_loss',
                              'precision',
                              'recall',
                              'pr_auc',
                              'base_episodes',
                            ] as const)
                        ).map((metric) => (
                          <div key={metric}>
                            <dt>{metric.replaceAll('_', ' ')}</dt>
                            <dd>{n(model.data?.[name]?.[metric])}</dd>
                          </div>
                        ))}
                      </dl>
                    ) : (
                      <p className="lab-note">
                        Not evaluated. Inspect tournament results for policy performance.
                      </p>
                    )}
                  </div>
                ))}
              </div>
              {isRegression(model.data) && model.data.baselines_validation && (
                <div>
                  <h3>Validation regression controls</h3>
                  {model.data.quoted_baseline_definition && (
                    <p className="lab-note">{model.data.quoted_baseline_definition}</p>
                  )}
                  {Object.entries(model.data.baselines_validation).map(([name, metrics]) => (
                    <p key={name}>
                      {name.replaceAll('_', ' ')}: RMSE {n(metrics.rmse)}{' '}
                      {regressionUnits(model.data)} · MAE {n(metrics.mae)}{' '}
                      {regressionUnits(model.data)}
                    </p>
                  ))}
                </div>
              )}
              {model.data.validation && !isRegression(model.data) && (
                <Suspense fallback={<p>Loading calibration…</p>}>
                  <Chart
                    label="Validation probability reliability"
                    option={{
                      ...chartBase,
                      xAxis: { type: 'value', min: 0, max: 1 },
                      yAxis: { type: 'value', min: 0, max: 1 },
                      series: [
                        {
                          type: 'line',
                          name: 'Observed frequency',
                          data: model.data.validation.reliability
                            .filter((bin) => bin.count)
                            .map((bin) => [bin.predicted, bin.observed]),
                          lineStyle: { color: '#4dbfb1' },
                        },
                        {
                          type: 'line',
                          name: 'Perfect calibration reference',
                          data: [
                            [0, 0],
                            [1, 1],
                          ],
                          lineStyle: { type: 'dashed', color: '#596270' },
                        },
                      ],
                    }}
                  />
                </Suspense>
              )}
              <p className="lab-note">
                Artifact SHA256: <code>{model.data.artifact_sha256}</code>
              </p>
              {model.data.diagnostics && (
                <div>
                  <h3>Validation decision diagnostics</h3>
                  <p className="lab-note">
                    {model.data.diagnostics.base_episodes} base episodes ·{' '}
                    {model.data.diagnostics.false_positive_count ??
                      model.data.diagnostics.false_completion_count}{' '}
                    false positive predictions ·{' '}
                    {model.data.diagnostics.false_negative_count ??
                      model.data.diagnostics.missed_completion_count}{' '}
                    missed positive outcomes for{' '}
                    {model.data.diagnostics.label_target ?? 'completion'} at threshold 0.5. Final
                    test labels excluded.
                  </p>
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Perturbed feature</th>
                          <th>Brier increase</th>
                          <th>Episode bootstrap 95%</th>
                        </tr>
                      </thead>
                      <tbody>
                        {model.data.diagnostics.feature_sensitivity.map((feature) => (
                          <tr key={feature.feature}>
                            <td>{feature.feature.replaceAll('_', ' ')}</td>
                            <td>{n(feature.mean_brier_increase, 5)}</td>
                            <td>{feature.episode_bootstrap_95.map((v) => n(v, 5)).join(' / ')}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <details>
                    <summary>Representative prediction errors and limitations</summary>
                    {model.data.diagnostics.representative_errors.map((error, index) => (
                      <p key={index}>
                        <code>{error.base_episode_id}</code> · {error.execution_model} ·{' '}
                        {error.error.replaceAll('_', ' ')} · prediction score{' '}
                        {n(error.predicted_probability ?? error.completion_probability, 3)}
                      </p>
                    ))}
                    {model.data.diagnostics.limitations.map((limitation) => (
                      <p className="lab-note" key={limitation}>
                        {limitation}
                      </p>
                    ))}
                  </details>
                </div>
              )}
              <div className="lab-controls">
                <a href={`/api/arena/models/${modelId}`} target="_blank" rel="noreferrer">
                  Full model manifest
                </a>
                {model.data.artifact_sha256 && (
                  <a
                    href={`/api/arena/models/${modelId}/artifacts/${model.data.family === 'ppo' ? 'policy.zip' : 'parameters.json'}`}
                  >
                    Inference parameters / weights
                  </a>
                )}
                {model.data.checkpoints.map((name) => (
                  <a key={name} href={`/api/arena/models/${modelId}/artifacts/${name}`}>
                    {name}
                  </a>
                ))}
                {model.data.family !== 'ppo' &&
                  !isRegression(model.data) &&
                  model.data.artifact_sha256 &&
                  (model.data.diagnostics ? (
                    <a href={`/api/arena/models/${modelId}/artifacts/diagnostics.json`}>
                      Saved validation diagnostics
                    </a>
                  ) : (
                    <button
                      onClick={() =>
                        submit.mutate({ configuration: { kind: 'diagnostics', model_id: modelId } })
                      }
                    >
                      Inspect validation errors
                    </button>
                  ))}
                {model.data.family !== 'ppo' &&
                  model.data.state !== 'TRAINING' &&
                  !model.data.test && (
                    <button
                      disabled={
                        isCost(model.data) &&
                        model.data.label_version !== 'initial-position-friction-2'
                      }
                      onClick={() =>
                        submit.mutate({ configuration: { kind: 'evaluation', model_id: modelId } })
                      }
                    >
                      Evaluate frozen test
                    </button>
                  )}
              </div>
              <details>
                <summary>Configuration and limitations</summary>
                <Json
                  value={{
                    configuration: model.data.configuration,
                    limitations: model.data.limitations,
                  }}
                />
              </details>
            </Section>
          )}
        </>
      )}
      {tab === 'Tournaments' && (
        <>
          <Section title="Matched policy competitions">
            <label>
              <input
                type="checkbox"
                checked={economicEnabled}
                onChange={(event) => setEconomicEnabled(event.target.checked)}
              />
              Rerun with hypothetical economics
            </label>
            {economicEnabled && (
              <div className="lab-controls">
                <label>
                  Depth multiplier
                  <input
                    type="number"
                    min={0}
                    max={2}
                    step={0.25}
                    value={depthMultiplier}
                    onChange={(event) => setDepthMultiplier(event.target.value)}
                  />
                </label>
                <label>
                  Synthetic fee coefficient
                  <input
                    type="number"
                    min={0}
                    max={0.25}
                    step={0.005}
                    value={feeParameter}
                    onChange={(event) => setFeeParameter(event.target.value)}
                  />
                </label>
                <label>
                  Additional submission latency (ms)
                  <input
                    type="number"
                    min={0}
                    max={10000}
                    step={100}
                    value={extraSubmissionLatency}
                    onChange={(event) => setExtraSubmissionLatency(Number(event.target.value))}
                  />
                </label>
                <p className="lab-footnote">
                  Inputs change generated scenarios before execution. The fee coefficient uses the
                  existing synthetic fee formula; blank preserves it. Trained policies may abstain
                  when inputs leave training ranges.
                </p>
              </div>
            )}
            <div className="lab-controls">
              <label>
                Tournament
                <select
                  value={selectedTournament}
                  onChange={(event) => {
                    setTournamentId(event.target.value);
                    setRowId('');
                    setOffset(0);
                  }}
                >
                  {!data?.tournaments.length && <option value="">No completed tournaments</option>}
                  {data?.tournaments.map((entry) => (
                    <option key={entry.tournament_id}>{entry.tournament_id}</option>
                  ))}
                </select>
              </label>
              <button
                disabled={!selectedDataset || submit.isPending}
                onClick={() =>
                  submit.mutate({
                    configuration: {
                      kind: 'tournament',
                      tournament: {
                        dataset_id: selectedDataset,
                        model_ids: data?.models
                          .filter(
                            (entry) => entry.dataset_id === selectedDataset && !isRegression(entry),
                          )
                          .map((entry) => entry.model_id),
                        max_episodes: 100,
                        economic_regime: economicRegime,
                      },
                    },
                  })
                }
              >
                Run held-out tournament
              </button>
              <button
                disabled={!selectedDataset || submit.isPending}
                onClick={() =>
                  submit.mutate({
                    configuration: {
                      kind: 'tournament',
                      tournament: {
                        dataset_id: selectedDataset,
                        model_ids: data?.models
                          .filter(
                            (entry) => entry.dataset_id === selectedDataset && !isRegression(entry),
                          )
                          .map((entry) => entry.model_id),
                        max_episodes: 100,
                        adversarial: true,
                        economic_regime: economicRegime,
                      },
                    },
                  })
                }
              >
                Run adversarial suite
              </button>
            </div>
            <div className="lab-controls">
              <label>
                Cost preference cap (virtual USD)
                <input
                  type="number"
                  min="0.01"
                  step="0.01"
                  value={costPreferenceCap}
                  onChange={(event) => setCostPreferenceCap(event.target.value)}
                />
              </label>
              <label>
                Research buffer (virtual USD)
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={costPreferenceMargin}
                  onChange={(event) => setCostPreferenceMargin(event.target.value)}
                />
              </label>
              <label>
                Fresh cost-policy seed
                <input
                  type="number"
                  min="0"
                  value={costChallengeSeed}
                  onChange={(event) => setCostChallengeSeed(Number(event.target.value))}
                />
              </label>
              <button
                disabled={!costPolicyModel || submit.isPending}
                onClick={() =>
                  submit.mutate({
                    configuration: {
                      kind: 'tournament',
                      max_wall_seconds: 1800,
                      tournament: {
                        dataset_id: selectedDataset,
                        cost_gates: [
                          {
                            model_id: costPolicyModel?.model_id,
                            max_cost_usd: costPreferenceCap,
                            margin_usd: costPreferenceMargin,
                          },
                        ],
                        max_episodes: 100,
                        minimum_champion_episodes: 2000,
                        challenge: {
                          episodes: 100,
                          seed: costChallengeSeed,
                          decision_scope: 'first_admitted',
                          retain_execution_costs: true,
                          families: data?.datasets.find(
                            (entry) => entry.dataset_id === selectedDataset,
                          )?.spec?.families,
                          costs: data?.datasets.find(
                            (entry) => entry.dataset_id === selectedDataset,
                          )?.spec?.costs,
                        },
                      },
                    },
                  })
                }
              >
                Run fresh cost-policy comparison
              </button>
            </div>
            <p className="lab-note">
              Cost comparisons include forecast, quoted-cost and matching first-position controls.
              The buffer is a research preference, not a calibrated confidence bound. Mathematical
              edge and broker risk admission remain required.
            </p>
            {tournament.data && (
              <>
                <p className="lab-note">
                  {tournament.data.base_episodes} base episodes / {tournament.data.variants}{' '}
                  correlated policy and execution variants. {tournament.data.ranking_objective}
                </p>
                <p className="arena-conclusion">{tournament.data.conclusion}</p>
                <div className="arena-table">
                  <table>
                    <thead>
                      <tr>
                        <th>Policy</th>
                        <th>Mean virtual P&amp;L</th>
                        <th>95% interval</th>
                        <th>5% tail loss</th>
                        <th>Worst outcome</th>
                        <th>No trade</th>
                        <th>Score</th>
                        <th>Outside training support</th>
                      </tr>
                    </thead>
                    <tbody>
                      {tournament.data.leaderboard.map((entry) => (
                        <tr key={entry.policy}>
                          <td>
                            {entry.rank != null && <span className="badge">Rank {entry.rank}</span>}{' '}
                            <button
                              disabled={
                                !entry.policy.startsWith('model-') &&
                                !tournament.data?.policy_bindings?.[entry.policy] &&
                                !tournament.data?.cost_policy_bindings?.[entry.policy]
                              }
                              onClick={() => {
                                setModelId(
                                  tournament.data?.policy_bindings?.[entry.policy]?.model_id ??
                                    tournament.data?.cost_policy_bindings?.[entry.policy]
                                      ?.specification.model_id ??
                                    entry.policy,
                                );
                                setTab('Model registry');
                              }}
                            >
                              {entry.policy}
                            </button>
                            {tournament.data?.cost_policy_bindings?.[entry.policy] && (
                              <small>
                                {tournament.data.cost_policy_bindings[entry.policy].kind} · cap{' '}
                                {
                                  tournament.data.cost_policy_bindings[entry.policy].specification
                                    .max_cost_usd
                                }{' '}
                                virtual USD · research buffer{' '}
                                {
                                  tournament.data.cost_policy_bindings[entry.policy].specification
                                    .margin_usd
                                }
                              </small>
                            )}
                            {tournament.data?.policy_bindings?.[entry.policy] && (
                              <small>
                                Threshold {tournament.data.policy_bindings[entry.policy].threshold}{' '}
                                · {tournament.data.policy_bindings[entry.policy].size} size
                              </small>
                            )}
                            {policyTarget(tournament.data, entry.policy) && (
                              <small>
                                {policyTarget(tournament.data, entry.policy) === 'completion'
                                  ? 'Predicts proposal completion'
                                  : 'Predicts unmatched exposure'}
                              </small>
                            )}
                          </td>
                          <td>{n(entry.mean_pnl)}</td>
                          <td>
                            {entry.mean_pnl_episode_bootstrap_95
                              .map((value) => n(value))
                              .join(' … ')}
                          </td>
                          <td>{n(entry.cvar_05_loss)}</td>
                          <td>{n(entry.worst_loss)}</td>
                          <td>{n(entry.no_trade_fraction * 100, 1)}%</td>
                          <td>{n(entry.score)}</td>
                          <td>{entry.unsupported_decisions ?? 'Not recorded'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="lab-footnote">{tournament.data.uncertainty_note}</p>
                <p className="lab-footnote">
                  Input-support checks use training feature ranges only. A covered range does not
                  establish joint-distribution support or calibrated execution probabilities.
                </p>
                <div className="lab-two">
                  <Suspense fallback={<p>Loading distribution…</p>}>
                    <Chart
                      label="Policy outcome distribution quantiles"
                      option={{
                        ...chartBase,
                        legend: { textStyle: { color: '#a4aabc' } },
                        xAxis: {
                          ...chartBase.xAxis,
                          data: tournament.data.leaderboard.map(
                            (entry) =>
                              data?.models.find((model) => model.model_id === entry.policy)
                                ?.family ?? entry.policy,
                          ),
                        },
                        series: [0, 2, 4].map((index) => ({
                          name: ['5th percentile', '', 'Median', '', '95th percentile'][index],
                          type: 'bar',
                          data: tournament.data?.leaderboard.map((entry) => entry.quantiles[index]),
                        })),
                      }}
                    />
                  </Suspense>
                  <Suspense fallback={<p>Loading drawdown…</p>}>
                    <Chart
                      label="Maximum virtual drawdown by policy"
                      option={{
                        ...chartBase,
                        xAxis: {
                          ...chartBase.xAxis,
                          data: tournament.data.leaderboard.map(
                            (entry) =>
                              data?.models.find((model) => model.model_id === entry.policy)
                                ?.family ?? entry.policy,
                          ),
                        },
                        series: [
                          {
                            name: 'Maximum drawdown %',
                            type: 'bar',
                            data: tournament.data.leaderboard.map(
                              (entry) => entry.max_drawdown * 100,
                            ),
                            itemStyle: { color: '#d3a955' },
                          },
                        ],
                      }}
                    />
                  </Suspense>
                </div>
                <details>
                  <summary>Paired confidence estimates</summary>
                  <div className="arena-table">
                    <table>
                      <thead>
                        <tr>
                          <th>Candidate / control</th>
                          <th>Base episodes</th>
                          <th>Mean difference</th>
                          <th>Grouped 95% interval</th>
                        </tr>
                      </thead>
                      <tbody>
                        {tournament.data.paired.map((pair) => (
                          <tr key={`${pair.policy}-${pair.control}`}>
                            <td>
                              {pair.policy} / {pair.control}
                            </td>
                            <td>{pair.base_episodes}</td>
                            <td>{n(pair.mean_difference)}</td>
                            <td>{pair.bootstrap_95.map((value) => n(value)).join(' … ')}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </details>
              </>
            )}
          </Section>
          <Section title="Fixed-path economic sensitivity">
            <p className="lab-note">
              Hypothetical extra costs applied to saved fills and capital paths. Trades stay fixed;
              this is not a cost-aware policy rerun or an observed fee schedule.
            </p>
            {economicStudy.data?.conditions && (
              <Section title="Verified economic regime reruns">
                <p className="lab-note">
                  {economicStudy.data.source_groups} shared source groups /{' '}
                  {economicStudy.data.correlated_variants} correlated variants. Conditions change
                  generated scenarios before execution; policies remain frozen.
                </p>
                <Suspense fallback={<p>Loading economic comparison…</p>}>
                  <Chart
                    label="Downside score by economic condition"
                    option={{
                      ...chartBase,
                      legend: { textStyle: { color: '#a4aabc' } },
                      xAxis: {
                        ...chartBase.xAxis,
                        data: economicStudy.data.conditions.map((c) => c.name.replaceAll('_', ' ')),
                      },
                      series: economicStudy.data.conditions[0].leaderboard.map((p) => ({
                        name: p.policy,
                        type: 'bar',
                        data: economicStudy.data?.conditions.map(
                          (c) => c.leaderboard.find((v) => v.policy === p.policy)?.score ?? null,
                        ),
                      })),
                    }}
                  />
                </Suspense>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Condition / policy</th>
                        <th>Mean virtual P&amp;L</th>
                        <th>5% tail loss</th>
                        <th>Score</th>
                        <th>Outside training support</th>
                        <th>Paired mean change / 95% interval</th>
                      </tr>
                    </thead>
                    <tbody>
                      {economicStudy.data.conditions.flatMap((c) =>
                        c.leaderboard.map((p) => {
                          const paired = economicStudy.data?.paired_comparisons[
                            c.name
                          ]?.policies.find((v) => v.policy === p.policy);
                          return (
                            <tr key={`${c.name}-${p.policy}`}>
                              <td>
                                <button
                                  onClick={() => {
                                    setTournamentId(c.tournament_id);
                                    setRowId('');
                                    setOffset(0);
                                  }}
                                >
                                  {c.name.replaceAll('_', ' ')}
                                </button>
                                <small>{p.policy}</small>
                              </td>
                              <td>{n(p.mean_pnl)}</td>
                              <td>{n(p.cvar_05_loss)}</td>
                              <td>{n(p.score)}</td>
                              <td>{p.unsupported_decisions ?? 'Not recorded'}</td>
                              <td>
                                {paired
                                  ? `${n(paired.mean_pnl_difference)} / ${paired.episode_bootstrap_95.map((v) => n(v)).join(' … ')}`
                                  : 'Baseline'}
                              </td>
                            </tr>
                          );
                        }),
                      )}
                    </tbody>
                  </table>
                </div>
                <p className="lab-footnote">{economicStudy.data.interpretation}</p>
                {economicStudy.data.limitations.map((limit) => (
                  <p className="lab-footnote" key={limit}>
                    {limit}
                  </p>
                ))}
              </Section>
            )}
            {economicStudy.isError && <p role="alert">{economicStudy.error.message}</p>}
            {economics.isPending && selectedTournament && (
              <p role="status">Loading saved cost analysis…</p>
            )}
            {!selectedTournament && <p className="lab-note">No completed tournament available.</p>}
            {economics.isError && <p role="alert">{economics.error.message}</p>}
            {economics.data === null && (
              <p className="lab-note">No saved economic analysis for this tournament.</p>
            )}
            {economics.data && (
              <>
                <label>
                  Economic assumption
                  <select
                    aria-label="Economic assumption"
                    value={economicParameter}
                    onChange={(event) =>
                      setEconomicParameter(event.target.value as EconomicParameter)
                    }
                  >
                    <option value="operating_per_fill">Additional cost per fill</option>
                    <option value="redemption_cost">Cost per settled position</option>
                    <option value="annual_financing_rate">Annual financing rate</option>
                    <option value="collateral_value_factor">Collateral value retained</option>
                  </select>
                </label>
                <p className="lab-note">
                  Units: {economics.data.units[economicParameter]}. Other extra costs reset to zero
                  on each axis.
                </p>
                <Suspense fallback={<p>Loading cost chart…</p>}>
                  <Chart
                    label="Fixed-path cost sensitivity"
                    option={{
                      ...chartBase,
                      grid: { ...chartBase.grid, top: 55, bottom: 35 },
                      legend: {
                        type: 'scroll',
                        top: 0,
                        bottom: 'auto',
                        textStyle: { color: '#a4aabc' },
                      },
                      xAxis: { type: 'value' },
                      yAxis: { type: 'value', name: 'Mean virtual USD' },
                      series: economics.data.policies.map((policy) => ({
                        name: policy.policy.startsWith('model-')
                          ? `${data?.models.find((m) => m.model_id === policy.policy)?.family ?? 'model'} ${policy.policy.slice(-6)}`
                          : policy.policy,
                        type: 'line',
                        data: policy.points
                          .filter((point) => point.parameter === economicParameter)
                          .sort((a, b) => Number(a.value) - Number(b.value))
                          .map((point) => [Number(point.value), point.mean_pnl]),
                      })),
                    }}
                  />
                </Suspense>
                <div className="arena-table">
                  <table>
                    <thead>
                      <tr>
                        <th>Policy</th>
                        <th>Zero-extra-cost downside score</th>
                        <th>Mean break-even extra USD/fill</th>
                      </tr>
                    </thead>
                    <tbody>
                      {economics.data.policies.map((policy) => (
                        <tr key={policy.policy}>
                          <td>
                            <code>{policy.policy}</code>
                          </td>
                          <td>{n(policy.baseline_downside_score)}</td>
                          <td>
                            {policy.mean_break_even_operating_per_fill === null
                              ? 'No positive margin / no fills'
                              : n(Number(policy.mean_break_even_operating_per_fill))}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <details>
                  <summary>Accounting assumptions and limits</summary>
                  {economics.data.limitations.map((limit) => (
                    <p className="lab-note" key={limit}>
                      {limit}
                    </p>
                  ))}
                </details>
                <a
                  href={`/api/arena/tournaments/${selectedTournament}/economics`}
                  target="_blank"
                  rel="noreferrer"
                >
                  Full economic report and confidence intervals
                </a>
              </>
            )}
          </Section>
          <Section title="Episode evidence and replay">
            <div className="lab-controls">
              <label>
                Scenario family
                <select
                  value={scenarioFilter}
                  onChange={(event) => {
                    setScenarioFilter(event.target.value);
                    setOffset(0);
                  }}
                >
                  <option value="">All</option>
                  {['calm', 'volatile', 'thin', 'deep', 'one_sided', 'disappearing'].map((name) => (
                    <option key={name}>{name}</option>
                  ))}
                </select>
              </label>
              <label>
                Execution assumptions
                <select
                  value={executionFilter}
                  onChange={(event) => {
                    setExecutionFilter(event.target.value);
                    setOffset(0);
                  }}
                >
                  <option value="">All</option>
                  {['optimistic', 'standard', 'conservative'].map((name) => (
                    <option key={name}>{name}</option>
                  ))}
                </select>
              </label>
            </div>
            <div className="arena-table">
              <table>
                <thead>
                  <tr>
                    <th>Policy</th>
                    <th>Scenario</th>
                    <th>Execution</th>
                    <th>Virtual P&amp;L</th>
                    <th>Replay</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.data?.rows.map((row) => (
                    <tr key={row.id}>
                      <td>{row.policy}</td>
                      <td>{row.family}</td>
                      <td>{row.execution_model}</td>
                      <td>{row.metrics.net_simulated_pnl}</td>
                      <td>
                        <button
                          onClick={() => {
                            setRowId(row.id);
                            setEventIndex(0);
                          }}
                        >
                          Replay episode
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="lab-controls">
              <button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 25))}>
                Previous rows
              </button>
              <span>
                {offset + 1} / {rows.data?.total ?? 0}
              </span>
              <button
                disabled={offset + 25 >= (rows.data?.total ?? 0)}
                onClick={() => setOffset(offset + 25)}
              >
                Next rows
              </button>
            </div>
            {replay.data && (
              <>
                <h3>Saved event replay</h3>
                <div className="lab-controls">
                  <button disabled={eventIndex === 0} onClick={() => setEventIndex(eventIndex - 1)}>
                    Previous event
                  </button>
                  <span>
                    Event {eventIndex + 1} / {replay.data.result.journal.length}
                  </span>
                  <button
                    disabled={eventIndex >= replay.data.result.journal.length - 1}
                    onClick={() => setEventIndex(eventIndex + 1)}
                  >
                    Next event
                  </button>
                  <a
                    href={`/api/arena/tournaments/${selectedTournament}/replay/${rowId}`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Export replay
                  </a>
                </div>
                <input
                  className="lab-scrubber"
                  aria-label="Arena replay timeline"
                  type="range"
                  min={0}
                  max={Math.max(0, replay.data.result.journal.length - 1)}
                  value={eventIndex}
                  onChange={(event) => setEventIndex(Number(event.target.value))}
                />
                <p className="lab-note">
                  {replay.data.result.journal[eventIndex]?.kind} · virtual time{' '}
                  {replay.data.result.journal[eventIndex]?.time_ms} ms
                </p>
                <dl className="arena-facts">
                  {[
                    'available',
                    'reserved',
                    'locked',
                    'realized_pnl',
                    'unrealized_pnl',
                    'net_exposure_shares',
                  ].map((name) => (
                    <div key={name}>
                      <dt>{name.replaceAll('_', ' ')}</dt>
                      <dd>{String(replay.data?.result.journal[eventIndex]?.after[name] ?? '—')}</dd>
                    </div>
                  ))}
                </dl>
                <Suspense fallback={<p>Loading portfolio history…</p>}>
                  <Chart
                    label="Replay realized and unrealized virtual P&L"
                    option={{
                      ...chartBase,
                      legend: { textStyle: { color: '#a4aabc' } },
                      xAxis: {
                        ...chartBase.xAxis,
                        data: replay.data.result.journal.map((_, index) => index + 1),
                      },
                      series: ['realized_pnl', 'unrealized_pnl'].map((name) => ({
                        name: name.replaceAll('_', ' '),
                        type: 'line',
                        showSymbol: false,
                        data: replay.data?.result.journal.map((entry) =>
                          Number(entry.after[name] ?? 0),
                        ),
                      })),
                    }}
                  />
                </Suspense>
                <details>
                  <summary>Observation, order and ledger details</summary>
                  <Json value={replay.data.result.journal[eventIndex]} />
                </details>
                <details>
                  <summary>Policy decisions and final outcome</summary>
                  <Json
                    value={{
                      decisions: replay.data.decisions,
                      metrics: replay.data.result.metrics,
                    }}
                  />
                </details>
              </>
            )}
          </Section>
        </>
      )}
      {tab === 'Research director' && (
        <>
          <Section title="Risk threshold and sizing search">
            <p className="lab-note">
              Compare eight preregistered gates on validation scenarios, then evaluate the selected
              gate once on unused seeds. No-trade is selected when no gate clears downside and
              paired uncertainty. Scores refer to full proposals; half-size execution is not
              separately calibrated.
            </p>
            <div className="lab-controls">
              <label>
                Risk predictor
                <select
                  aria-label="Risk predictor"
                  value={selectedSearchModel}
                  onChange={(event) => setSearchModelId(event.target.value)}
                >
                  {!selectedSearchModel && (
                    <option value="">Train an unmatched-risk predictor first</option>
                  )}
                  {data?.models
                    .filter(
                      (entry) =>
                        entry.dataset_id === selectedDataset && entry.label_target === 'unmatched',
                    )
                    .map((entry) => (
                      <option key={entry.model_id} value={entry.model_id}>
                        {entry.family} · {entry.model_id}
                      </option>
                    ))}
                </select>
              </label>
              <button
                disabled={!selectedSearchModel || submit.isPending}
                onClick={() =>
                  submit.mutate({
                    configuration: {
                      kind: 'policy_search',
                      policy_search: { dataset_id: selectedDataset, model_id: selectedSearchModel },
                      max_wall_seconds: 5400,
                    },
                  })
                }
              >
                Run validation policy search
              </button>
            </div>
            {data?.searches?.map((search) => (
              <article className="arena-finding" key={search.search_id}>
                <h3>
                  {search.search_id} · <State value={search.state} />
                </h3>
                <p>
                  {search.selection
                    ? search.selection.gate
                      ? `Selected maximum predicted risk ${search.selection.gate.threshold}, ${search.selection.gate.size} sizing.`
                      : 'Selected no-trade.'
                    : 'Selection pending validation outcomes.'}
                </p>
                {search.selection && <p className="lab-note">{search.selection.reason}</p>}
                <div className="lab-controls">
                  <a
                    href={`/api/arena/searches/${search.search_id}`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Frozen search evidence
                  </a>
                  {[search.validation_tournament, search.test_tournament]
                    .filter(Boolean)
                    .map((id) => (
                      <button
                        key={id}
                        onClick={() => {
                          setTournamentId(id ?? '');
                          setTab('Tournaments');
                        }}
                      >
                        Inspect {id === search.validation_tournament ? 'validation' : 'fresh test'}
                      </button>
                    ))}
                </div>
                <details>
                  <summary>Selection limits</summary>
                  {search.limitations.map((limit) => (
                    <p className="lab-note" key={limit}>
                      {limit}
                    </p>
                  ))}
                </details>
              </article>
            ))}
          </Section>
          <Section title="Bounded research director">
            <p className="lab-note">
              A preregistered rule selects candidates using validation only, then evaluates fresh
              seeds and a reordered family schedule. Final challenge outcomes never alter training
              or thresholds.
            </p>
            <div className="lab-controls">
              <button
                disabled={!selectedDataset || submit.isPending}
                onClick={() =>
                  submit.mutate({
                    configuration: {
                      kind: 'director',
                      max_wall_seconds: 3600,
                      director: {
                        dataset_id: selectedDataset,
                        incumbent_model_ids: data?.models
                          .filter(
                            (entry) =>
                              entry.dataset_id === selectedDataset &&
                              ['logistic', 'mlp', 'ppo'].includes(entry.family) &&
                              entry.state === 'EVALUATED',
                          )
                          .map((entry) => entry.model_id)
                          .slice(0, 8),
                      },
                    },
                  })
                }
              >
                Start bounded research plan
              </button>
              <button
                disabled={!selectedDataset || submit.isPending}
                onClick={() =>
                  submit.mutate({
                    configuration: { kind: 'sweep', sweep: { dataset_id: selectedDataset } },
                  })
                }
              >
                Run validation-only seed comparison
              </button>
              <button
                disabled={!selectedDataset || submit.isPending}
                onClick={() =>
                  submit.mutate({
                    configuration: {
                      kind: 'sweep',
                      max_wall_seconds: 1800,
                      sweep: {
                        dataset_id: selectedDataset,
                        seeds: [11, 29],
                        epochs: 80,
                        candidates: ['logistic', 'mlp'].flatMap((family) =>
                          [
                            [],
                            ['min_ask_depth', 'max_ask_depth', 'min_top_depth'],
                            [
                              'latency_ms',
                              'jitter_ms',
                              'liquidity_fraction',
                              'adverse_ticks',
                              'ack_delay_ms',
                              'observation_latency_ms',
                            ],
                          ].map((excluded_features) => ({ family, excluded_features })),
                        ),
                      },
                    },
                  })
                }
              >
                Run feature ablations (12 fits)
              </button>
            </div>
            {data?.directors?.map((plan) => (
              <article className="arena-finding" key={plan.director_id}>
                <h3>{plan.research_question}</h3>
                <State value={plan.state} />
                <p>{plan.planning_rule}</p>
                {plan.current_stage && <p>Current stage: {plan.current_stage}</p>}
                {plan.observation_error && <p className="lab-note">{plan.observation_error}</p>}
                {plan.director_version === 'adaptive-latency-1' &&
                  ['PLANNED', 'RUNNING', 'UNVERIFIED', 'INTERRUPTED'].includes(plan.state) && (
                    <button
                      disabled={cancelDirector.isPending}
                      onClick={() => cancelDirector.mutate(plan.director_id)}
                    >
                      Cancel follow-up
                    </button>
                  )}
                <ol>
                  {plan.steps.map((step) => (
                    <li key={step.name}>
                      {step.name} · {step.state}
                      {step.artifact && (
                        <a
                          href={`/api/arena/${step.artifact.kind}/${step.artifact.identity}`}
                          target="_blank"
                          rel="noreferrer"
                        >
                          {' '}
                          · Evidence ↗
                        </a>
                      )}
                    </li>
                  ))}
                </ol>
                <a
                  href={`/api/arena/directors/${plan.director_id}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  Frozen plan and lineage ↗
                </a>
              </article>
            ))}
            {!data?.directors?.length && (
              <p className="empty">No director plan has run in this artifact root.</p>
            )}
          </Section>
          <Section title="Bounded missing-leg recovery">
            <p className="lab-note">
              Compare one ordinary initial admission followed by holding or one missing-leg buy.
              Recovery uses only unused allocated capital and observed quotes. Existing loss and
              exposure limits remain active; unknown acknowledgments or stale books can force
              holding. No sell/unwind action or guaranteed fill is assumed.
            </p>
            <button
              disabled={submit.isPending}
              onClick={() =>
                submit.mutate({
                  configuration: {
                    kind: 'recovery',
                    recovery: { episodes: 60, seed: 213071 },
                    max_wall_seconds: 1800,
                  },
                })
              }
            >
              Run bounded recovery comparison
            </button>
            {data?.recoveries?.map((study) => (
              <article className="arena-finding" key={study.recovery_id}>
                <h3>{study.recovery_id}</h3>
                <p>
                  {study.source_groups} source groups / {study.correlated_variants} correlated
                  variants.
                </p>
                <p>
                  Mean recovery minus hold: {study.paired_recovery_minus_hold_mean.toFixed(3)} /
                  grouped 95% interval [
                  {study.group_bootstrap_95.map((v) => v.toFixed(3)).join(', ')}].
                </p>
                <table className="lab-table">
                  <thead>
                    <tr>
                      <th>Policy</th>
                      <th>Mean virtual P&amp;L</th>
                      <th>Downside score</th>
                      <th>Worst P&amp;L</th>
                      <th>Recovery requests / filled shares</th>
                    </tr>
                  </thead>
                  <tbody>
                    {study.leaderboard.map((row) => (
                      <tr key={row.policy}>
                        <td>{row.policy}</td>
                        <td>{row.mean_pnl.toFixed(3)}</td>
                        <td>{row.score.toFixed(3)}</td>
                        <td>{row.worst_pnl.toFixed(3)}</td>
                        <td>
                          {row.recovery_requests} / {row.recovery_filled_shares}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <a
                  href={`/api/arena/recoveries/${study.recovery_id}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  Saved recovery evidence ↗
                </a>
                <details>
                  <summary>Recovery scope and limits</summary>
                  {study.limitations.map((limit) => (
                    <p className="lab-note" key={limit}>
                      {limit}
                    </p>
                  ))}
                </details>
              </article>
            ))}
          </Section>
          <Section title="Validation-only evolution evidence">
            {data?.sweeps?.map((sweep) => (
              <article className="arena-finding" key={sweep.sweep_id}>
                <h3>{sweep.sweep_id}</h3>
                <State value={sweep.state} />
                <p>
                  Final-test labels used for selection:{' '}
                  {sweep.test_labels_used_for_selection ? 'yes' : 'no'}
                </p>
                <p>{sweep.selection?.criterion}</p>
                <div className="arena-table">
                  <table>
                    <thead>
                      <tr>
                        <th>Candidate</th>
                        <th>Mean validation Brier</th>
                        <th>Across-seed range</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sweep.selection?.candidates.map((candidate, index) => (
                        <tr key={index}>
                          <td>
                            {candidate.configuration.family} · removed:{' '}
                            {candidate.configuration.excluded_features?.join(', ') || 'none'}
                          </td>
                          <td>{n(candidate.mean_validation_brier)}</td>
                          <td>{candidate.seed_brier_range.map((value) => n(value)).join(' … ')}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {sweep.ablation && (
                  <div>
                    <h4>Refitted feature comparisons</h4>
                    <p>{sweep.ablation.interpretation}</p>
                    {sweep.ablation.comparisons.map((comparison) => (
                      <p key={comparison.candidate_index}>
                        {comparison.family} without {comparison.excluded_features.join(', ')}: Brier
                        change {n(comparison.mean_group_brier_change)}, grouped 95% interval{' '}
                        {comparison.group_bootstrap_95.map((value) => n(value)).join(' … ')} across{' '}
                        {comparison.source_groups} validation source groups.
                      </p>
                    ))}
                    {sweep.ablation.limitations.map((limitation) => (
                      <p className="lab-note" key={limitation}>
                        {limitation}
                      </p>
                    ))}
                  </div>
                )}
                <details>
                  <summary>All training trials, including unselected candidates</summary>
                  {sweep.trials.map((trial) => (
                    <div className="arena-entry" key={`${trial.candidate_index}-${trial.seed}`}>
                      <span>
                        Candidate {trial.candidate_index + 1} · seed {trial.seed} · {trial.state}
                      </span>
                      {trial.model_id && (
                        <button
                          onClick={() => {
                            setModelId(trial.model_id);
                            setTab('Model registry');
                          }}
                        >
                          Inspect trial
                        </button>
                      )}
                    </div>
                  ))}
                </details>
                <a href={`/api/arena/sweeps/${sweep.sweep_id}`} target="_blank" rel="noreferrer">
                  Selection manifest ↗
                </a>
              </article>
            ))}
            {!data?.sweeps?.length && (
              <p className="empty">No completed validation comparison yet.</p>
            )}
          </Section>
        </>
      )}
      {tab === 'Research findings' && (
        <Section title="Evidence-backed research findings">
          {data?.findings.map((finding) => (
            <article className="arena-finding" key={finding.title}>
              <h3>{finding.title}</h3>
              <p>{finding.interpretation}</p>
              <p className="lab-footnote">{finding.caveats.join(' ')}</p>
              {finding.tournament_id && (
                <button
                  onClick={() => {
                    setTournamentId(finding.tournament_id ?? '');
                    setTab('Tournaments');
                  }}
                >
                  Inspect supporting tournament
                </button>
              )}
              {finding.model_id && (
                <button
                  onClick={() => {
                    setModelId(finding.model_id ?? '');
                    setTab('Model registry');
                  }}
                >
                  Inspect supporting model
                </button>
              )}
              {finding.director_id && (
                <button onClick={() => setTab('Research director')}>
                  Inspect supporting research plan
                </button>
              )}
            </article>
          ))}
          {!data?.findings.length && (
            <p className="empty">
              No published findings yet. Completed tournaments retain conclusions and supporting
              episode evidence.
            </p>
          )}
        </Section>
      )}
    </div>
  );
}
