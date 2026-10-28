import { useQuery } from '@tanstack/react-query';
import { ArrowUpRight, RefreshCw } from 'lucide-react';
import { useState } from 'react';
import { api } from './api';

type FrontierDiscoveryJob = {
  job_id: string;
  state: string;
  created_at: number | null;
  updated_at: number | null;
  elapsed_seconds: number | null;
  progress: { done?: number; total?: number } | null;
  phase: string | null;
  error: string | null;
  snapshot_id: string | null;
  snapshot_sha256: string | null;
  result: { comparison_id?: string; frontier_discovery_sha256?: string } | null;
};

type FrontierDiscoveryJobs = {
  items: FrontierDiscoveryJob[];
  scanned: number;
  scan_bound: number;
  scan_may_be_incomplete: boolean;
  research_only: true;
};

type FrontierDiscoveryArtifact = {
  artifact: {
    snapshot_id: string;
    snapshot_sha256: string;
    result_sha256: string;
    comparison: {
      comparison_id: string;
      normalized_input_sha256: string;
      result_sha256: string;
      code_version: string;
      replay_version: string;
      as_of_utc: string;
      arms: {
        scope: string;
        venues: string[];
        market_count: number;
        instrument_count: number;
        observed_instrument_count: number;
        book_count: number;
        relationship_count: number;
        candidates: { family: string; classification: string }[];
        family_counts: Record<string, number>;
      }[];
      deltas: {
        baseline: string;
        compared: string;
        matched_candidate_count: number;
        changed_classification_count: number;
        baseline_only_candidate_count: number;
        compared_only_candidate_count: number;
      }[];
    };
  };
  integrity_verified: boolean;
  research_only: true;
  orders_submitted: false;
  authenticated_requests: false;
};

const label = (value: string) => value.replaceAll('_', ' ');
const date = (seconds: number | null) =>
  seconds == null ? 'Time not recorded' : new Date(seconds * 1000).toLocaleString();

export function LaboratoryFrontierResearch({
  onNavigate,
}: {
  onNavigate?: (page: string) => void;
}) {
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const jobs = useQuery({
    queryKey: ['laboratory', 'frontier-discovery-jobs'],
    queryFn: () => api<FrontierDiscoveryJobs>('/arena/frontier-discovery-comparisons?limit=20'),
    refetchInterval: (query) =>
      query.state.data?.items.some((job) => ['QUEUED', 'RUNNING'].includes(job.state))
        ? 2000
        : false,
  });
  const selected =
    jobs.data?.items.find((job) => job.job_id === selectedJobId) ?? jobs.data?.items[0] ?? null;
  const artifact = useQuery({
    queryKey: ['laboratory', 'frontier-discovery-artifact', selected?.job_id],
    queryFn: () =>
      api<FrontierDiscoveryArtifact>(
        `/arena/jobs/${encodeURIComponent(selected!.job_id)}/frontier-discovery`,
      ),
    enabled: selected?.state === 'COMPLETED',
    retry: false,
  });

  return (
    <section className="panel lab-panel lab-frontier-panel" aria-label="Frontier study history">
      <div className="panel-header">
        <div>
          <h2>Frontier discovery studies</h2>
          <p>Integrity-checked Arena experiments over pinned multi-market evidence.</p>
        </div>
        <button
          className="text-button"
          onClick={() => void jobs.refetch()}
          disabled={jobs.isFetching}
          aria-label="Refresh Frontier study history"
        >
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      <div className="lab-frontier-boundary">
        <strong>Shared Frontier and Arena evidence</strong>
        <p>
          This view reads the same bounded Arena job catalog and hash-verifies completed artifacts.
          It does not create a second campaign, copy data into the single-market Laboratory dataset
          format, admit a worker, or contact a source. Use the Frontier workspace to submit a
          comparison.
        </p>
        {onNavigate && (
          <button className="text-button" onClick={() => onNavigate('Frontier')}>
            Open Frontier workspace <ArrowUpRight size={14} />
          </button>
        )}
      </div>

      {jobs.isLoading ? (
        <p className="empty">Loading bounded Frontier study history…</p>
      ) : jobs.isError ? (
        <p className="empty" role="alert">
          Frontier study history is unavailable: {jobs.error.message}
        </p>
      ) : jobs.data?.items.length ? (
        <>
          <div className="lab-frontier-job-list" aria-label="Frontier study jobs">
            {jobs.data.items.map((job) => (
              <article
                key={job.job_id}
                className={`lab-frontier-job ${selected?.job_id === job.job_id ? 'is-selected' : ''}`}
              >
                <button
                  type="button"
                  className="lab-frontier-job-select"
                  aria-pressed={selected?.job_id === job.job_id}
                  onClick={() => setSelectedJobId(job.job_id)}
                >
                  <strong>{job.job_id}</strong>
                  <small>{date(job.created_at)}</small>
                </button>
                <span className={`badge ${job.state === 'COMPLETED' ? 'cyan' : 'gold'}`}>
                  {job.state}
                </span>
                {job.phase && <small>{label(job.phase)}</small>}
                {job.progress && (
                  <small>
                    {job.progress.done ?? 0} / {job.progress.total ?? 0} steps
                  </small>
                )}
                {job.elapsed_seconds != null && (
                  <small>Worker elapsed {job.elapsed_seconds.toFixed(3)} s</small>
                )}
                {job.error && <p role="status">{job.error}</p>}
              </article>
            ))}
          </div>
          {jobs.data.scan_may_be_incomplete && (
            <p className="lab-note">
              This history is bounded to {jobs.data.scan_bound} Arena records; older studies may be
              outside the scan.
            </p>
          )}
          {selected?.snapshot_id && (
            <dl className="lab-frontier-identities">
              <div>
                <dt>Pinned input snapshot</dt>
                <dd>{selected.snapshot_id}</dd>
              </div>
              <div>
                <dt>Snapshot SHA-256</dt>
                <dd>{selected.snapshot_sha256 ?? 'Not recorded'}</dd>
              </div>
              {selected.result?.comparison_id && (
                <div>
                  <dt>Comparison ID</dt>
                  <dd>{selected.result.comparison_id}</dd>
                </div>
              )}
            </dl>
          )}
          {selected?.state === 'COMPLETED' && artifact.isLoading && (
            <p className="empty">Verifying the saved Frontier study artifact…</p>
          )}
          {artifact.isError && (
            <p className="empty" role="alert">
              Saved study artifact failed integrity verification: {artifact.error.message}
            </p>
          )}
          {selected?.state !== 'COMPLETED' && (
            <p className="empty">Select a completed study to inspect its saved result.</p>
          )}
          {artifact.data?.integrity_verified && <DiscoveryStudySummary result={artifact.data} />}
          {artifact.data && !artifact.data.integrity_verified && (
            <p className="empty" role="alert">
              The API did not confirm artifact integrity; result details are withheld.
            </p>
          )}
        </>
      ) : (
        <p className="empty">
          No Frontier discovery studies are recorded in the shared Arena workspace. This view
          remains read-only.
        </p>
      )}
    </section>
  );
}

function DiscoveryStudySummary({ result }: { result: FrontierDiscoveryArtifact }) {
  const { artifact } = result;
  return (
    <section className="lab-frontier-result" aria-label="Verified Frontier study result">
      <div className="lab-frontier-result-head">
        <div>
          <span className="badge cyan">INTEGRITY VERIFIED</span>
          <h3>{label(artifact.comparison.comparison_id.slice(0, 16))}</h3>
          <small>As of {new Date(artifact.comparison.as_of_utc).toLocaleString()}</small>
        </div>
        <span>{artifact.comparison.arms.length} paired discovery scopes</span>
      </div>
      <div className="lab-frontier-table-wrap">
        <table>
          <thead>
            <tr>
              <th>Discovery scope</th>
              <th>Markets</th>
              <th>Observed instruments</th>
              <th>Relationships</th>
              <th>Candidate constructions</th>
            </tr>
          </thead>
          <tbody>
            {artifact.comparison.arms.map((arm) => (
              <tr key={arm.scope}>
                <th>
                  {label(arm.scope)}
                  <small>{arm.venues.map(label).join(' · ') || 'No venue data'}</small>
                </th>
                <td>{arm.market_count}</td>
                <td>
                  {arm.observed_instrument_count} / {arm.instrument_count}
                  <small>{arm.book_count} saved books</small>
                </td>
                <td>{arm.relationship_count}</td>
                <td>
                  {arm.candidates.length}
                  <small>
                    {Object.entries(arm.family_counts)
                      .map(([family, count]) => `${label(family)} ${count}`)
                      .join(' · ') || 'No candidates'}
                  </small>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="lab-frontier-deltas" aria-label="Paired scope comparisons">
        {artifact.comparison.deltas.map((delta) => (
          <article key={`${delta.baseline}-${delta.compared}`}>
            <strong>
              {label(delta.baseline)} → {label(delta.compared)}
            </strong>
            <span>
              {delta.matched_candidate_count} matched · {delta.compared_only_candidate_count} added
              · {delta.baseline_only_candidate_count} removed · {delta.changed_classification_count}{' '}
              classification changes
            </span>
          </article>
        ))}
      </div>
      <details>
        <summary>Reproducibility identities and execution limits</summary>
        <dl className="lab-frontier-identities">
          <div>
            <dt>Normalized input SHA-256</dt>
            <dd>{artifact.comparison.normalized_input_sha256}</dd>
          </div>
          <div>
            <dt>Artifact result SHA-256</dt>
            <dd>{artifact.result_sha256}</dd>
          </div>
          <div>
            <dt>Comparison result SHA-256</dt>
            <dd>{artifact.comparison.result_sha256}</dd>
          </div>
          <div>
            <dt>Discovery and replay versions</dt>
            <dd>
              {artifact.comparison.code_version} · {artifact.comparison.replay_version}
            </dd>
          </div>
        </dl>
      </details>
      <p className="lab-note">
        These paired scopes use the same pinned data and execution assumptions. Counts describe this
        saved evidence window; they do not measure venue-wide prevalence, authenticate market
        relationships, or establish fills or profit. No orders were submitted, and no authenticated
        requests were made.
      </p>
    </section>
  );
}
