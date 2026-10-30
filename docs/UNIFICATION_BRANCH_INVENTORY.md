# MIDAS Git branch and worktree inventory

This is the disposition manifest for the 2026-10-30 unification review. The
repository comparison baseline for unique-commit counts is code commit
`88581c28953565ded0c3e6db2f69df785732895d`; the Reality archive provenance
safeguard followed at `fd3d16d`. The later documentation commit is a descendant
of that code state. Counts show commits reachable from each local branch but
not from the comparison baseline. Equivalent changes can be present in the
unified tree without the source branch commits being ancestors.

At the end-state inventory there were **26 local branches, 7 live remote
heads, 29 worktrees, and no stashes**. The unification checkout is the only
authoritative development workspace. No existing branch or worktree was
deleted, reset, cleaned, or rewritten.

The shared repository enables `extensions.worktreeConfig`. Of the 29 worktrees,
the only `config.worktree` found is for
`/tmp/midas-frontier-regression-sparse-20261028T0440Z`; it enables cone-mode
sparse checkout. The unification worktree has no separate worktree config.

## Local branches

| Branch | Head | Branch-only commits | Disposition | Finding |
|---|---:|---:|---|---|
| `codex/midas-unification` | b13477e plus migration documentation closeout | — | **AUTHORITATIVE** | Unified development source; b13477e is the validated release source, while production adoption remains pending. |
| `codex/frontier-20261026` | `f6ac37f` | 0 | **FULLY INTEGRATED** | Selected starting baseline; Frontier and Veritas V6 implementation history is retained in ancestry. |
| `codex/frontier-capacity-scan-bound-20261029` | `d5847df` | 0 | **FULLY INTEGRATED** | Included as the second parent of the bounded Reality/capacity integration. |
| `checkpoint/frontier-memory-interruption-20261029-0854` | `75e6f26` | 0 | **HISTORICAL / RETAIN FOR PROVENANCE** | Checkpoint in selected Frontier history; retain as a recovery reference. |
| `checkpoint/frontier-pre-followup-20261029-0558` | `0bbb62e` | 0 | **HISTORICAL / RETAIN FOR PROVENANCE** | Checkpoint in selected Frontier history; retain as a recovery reference. |
| `checkpoint/frontier-pre-memory-incident-20261029` | `a8fbcd7` | 0 | **HISTORICAL / RETAIN FOR PROVENANCE** | Checkpoint in selected Frontier history; retain as a recovery reference. |
| `codex/midas-comprehensive-engineering-mission-20261025` | `005f6fa` | 11 | **HISTORICAL / RETAIN FOR PROVENANCE** | `f7bd4b2` supplied readiness/reliability implementation lineage; current APIs and workspaces are newer. `resources.py` was restored from this commit. Ten later evidence/handoff commits stay on the source branch. Its worktree has 3,160 dirty entries, mostly preserved replay data. |
| `codex/readiness-loading-state-20261026` | `767f330` | 2 | **FULLY INTEGRATED** | Initial loading and memory-composition UI are present in the unified `Readiness.tsx`. |
| `codex/readiness-memory-composition-api-20261026` | `a152999` | 1 | **FULLY INTEGRATED** | Cgroup memory-composition API is present in the unified readiness API. |
| `codex/readiness-memory-composition-web-20261026` | `4e64a2e` | 1 | **FULLY INTEGRATED** | Cgroup memory-composition display is present in the unified readiness workspace. |
| `codex/real-market-research-overhaul` | `3b10292` | 0 | **UNMERGED WORK** | Branch tip has no unique commits against the baseline, but its worktree has 25 dirty entries including V6 files/docs. The current target has later catalog versions; preserve the dirty work for review. |
| `codex/reality-archive-provenance-20261026` | `a1f2fe9` | 21 | **HISTORICAL / RETAIN FOR PROVENANCE** | Selected recovery, queue/persistence, and archive-safety changes were reconciled. Candidate-transition tooling and dated canary/readiness evidence remain in the source branch. |
| `codex/veritas-v6-integration-20261026` | `11d32a0` | 0 | **FULLY INTEGRATED** | The selected baseline contains the V6 implementation; current catalogs and independent audit remain separate. |
| `fix/reality-archive-quota-20261020` | `350db69` | 0 | **FULLY INTEGRATED** | No branch-only commit remains outside the unified ancestry. |
| `fix/reality-foundation-20261020` | `4278b5b` | 17 | **HISTORICAL / RETAIN FOR PROVENANCE** | Its 17 unique commits overlap the Reality provenance line; selected code was reconciled. Its attached worktree retains two source modifications and 24 canary/evidence files. |
| `fix/reality-report-hotpath-20261020` | `397ec50` | 0 | **FULLY INTEGRATED** | No branch-only commit remains outside the unified ancestry. |
| `fix/reality-stale-error-status` | `b0610c1` | 1 | **FULLY INTEGRATED** | Clearing a stale connection diagnostic on a valid frame is present in the unified collector. |
| `fix/veritas-gap-market-bound` | `49275d9` | 1 | **FULLY INTEGRATED** | The unified Veritas code keeps the gap-reason bound separate from the market bound; tests cover 129 affected markets. |
| `fix/veritas-gap-timer-stagger-20261020` | `e530cef` | 0 | **FULLY INTEGRATED** | No branch-only commit remains outside the unified ancestry. |
| `main` | `55601b9` | 0 | **ACTIVE RUNTIME DEPENDENCY** | Protected historical branch; `/home/charlie/midas` remains the API working directory and Arena scheduler source path. It was not changed by this mission. |
| `project/reality` | `d8629e4` | 0 | **ACTIVE RUNTIME DEPENDENCY** | `/home/charlie/midas-reality` remains the protected recorder and Reality interface source/workspace. |
| `project/veritas` | `3b10292` | 0 | **ACTIVE RUNTIME DEPENDENCY** | `/home/charlie/midas-veritas` remains the source path for Veritas timers. |
| `recovery/preconsolidation-main-20261017` | `f968095` | 0 | **HISTORICAL / RETAIN FOR PROVENANCE** | Retained recovery reference; no unique commit outside selected ancestry. |
| `recovery/preconsolidation-reality-20261017` | `2b83818` | 0 | **HISTORICAL / RETAIN FOR PROVENANCE** | Retained recovery reference; no unique commit outside selected ancestry. |
| `recovery/preconsolidation-veritas-20261017` | `1f8f1df` | 0 | **HISTORICAL / RETAIN FOR PROVENANCE** | Retained recovery reference; no unique commit outside selected ancestry. |
| `recovery/veritas-uncommitted-20261017` | `683dba2` | 0 | **HISTORICAL / RETAIN FOR PROVENANCE** | Retained recovery reference; no unique commit outside selected ancestry. |

### Source-only Reality provenance commits

The 21 commits unique to `codex/reality-archive-provenance-20261026` were
reviewed. Current code carries or implements equivalent behavior from
`b06eff8` (verified checkpoint and bounded ingestion), `c2e73eb` (checkpoint
prefix matching across inserted empty segments), `dc7489b` and `cb6a120`
(bounded transport/queue and persistence freshness), `b0610c1` (clear stale
connection error), `d298957` and `987481f` (preserve ambiguous archive state).
The archive checks were adapted to the newer bounded archive code in
`fd3d16d`; synthetic tests ensure a partial, orphan segment, pending manifest,
or symlinked lock is preserved and reported instead of removed or followed.

The remaining source-only commits are `3b332d0`, `92e9648`, `f2dc9c7`,
`2eeb1a5`, `f20e388`, `c129b69`, `22fc3db`, `1f1faa8`, `1b3abd6`, `62ce199`,
`a4777a4`, `85df21b`, `4278b5b`, and `a1f2fe9`. They contain standalone
measurement/candidate-transition tooling, fixture-only changes, and dated
canary or readiness evidence. These remain preserved on the historical branch;
no active installed service depends on those branch paths. The production
transition plan now lives in `UNIFICATION_DEPLOYMENT_PLAN.md`.

The 17 unique commits on `fix/reality-foundation-20261020` overlap the earlier
part of this Reality lineage. The branch is retained; no whole-branch merge was
used. Veritas market-bound code and the Reality stale-error fix are already
represented by equivalent implementations in the unified source.

## Live remote heads

All seven live `origin` heads were fetched/read with `git ls-remote`; no push
occurred. The remote-only commit count is measured against the unified code
baseline.

| Remote ref | Head | Remote-only commits | Disposition |
|---|---:|---:|---|
| `origin/main` | `55601b9` | 0 | **ACTIVE RUNTIME DEPENDENCY**; protected, unchanged. |
| `origin/project/reality` | `4f5cb56` | 0 | **ACTIVE RUNTIME DEPENDENCY**; behind local runtime branch, no unique remote commit. |
| `origin/project/veritas` | `3b10292` | 0 | **ACTIVE RUNTIME DEPENDENCY**. |
| `origin/fix/reality-foundation-20261020` | `4278b5b` | 17 | **HISTORICAL / RETAIN FOR PROVENANCE**; same unique lineage as local branch. |
| `origin/fix/reality-report-hotpath-20261020` | `397ec50` | 0 | **FULLY INTEGRATED**. |
| `origin/fix/reality-stale-error-status` | `b0610c1` | 1 | **FULLY INTEGRATED** by equivalent collector behavior. |
| `origin/fix/veritas-gap-market-bound` | `49275d9` | 1 | **FULLY INTEGRATED** by equivalent Veritas bound. |

No `origin/codex/*` ref exists for the unification, Frontier, or V6 branches at
this snapshot. `codex/midas-unification` is local and was not pushed.

## Worktrees

Status counts below are `git status --porcelain -uall` counts observed during
the final inventory; the unification checkout was clean after closeout. A clean
worktree is not, by itself, permission to delete its history or data.

| Path | Branch / HEAD | Status | Disposition |
|---|---|---:|---|
| `/home/charlie/midas` | `main` | 69 entries | **ACTIVE RUNTIME DEPENDENCY**. Preserve local UI changes, `.arena-global.lock`, and endurance evidence. |
| `/home/charlie/midas-engineering-mission-20261025` | `codex/midas-comprehensive-engineering-mission-20261025` | 3,160 entries | **UNMERGED WORK**. Preserve 1.3 GiB offline replay and more than 3,000 untracked data files. |
| `/home/charlie/midas-frontier` | `codex/frontier-20261026` | 5 entries | **UNMERGED WORK**. Preserve untracked public probe artifacts. |
| `/home/charlie/midas-reality` | `project/reality` | clean | **ACTIVE RUNTIME DEPENDENCY**. Protected recorder/interface source and Reality data owner. |
| `/home/charlie/midas-reality-archive-provenance` | `codex/reality-archive-provenance-20261026` | clean | **HISTORICAL / RETAIN FOR PROVENANCE**. Unique source commits remain referenced. |
| `/home/charlie/midas-reality-capacity-scan-frontier-20261029` | `codex/frontier-capacity-scan-bound-20261029` | clean | **FULLY INTEGRATED**; retain history until routine branch review. |
| `/home/charlie/midas-reality-reliability` | `fix/reality-foundation-20261020` | 26 entries | **UNMERGED WORK**. Preserve source edits and 24 canary/evidence files. |
| `/home/charlie/midas-unification` | `codex/midas-unification` | clean | **AUTHORITATIVE** development checkout. |
| `/home/charlie/midas-veritas` | `project/veritas` | clean | **ACTIVE RUNTIME DEPENDENCY** for Veritas timers and data ownership. |
| `/home/charlie/midas-veritas-gap-v2-code` | detached `71dcdd90` | clean | **HISTORICAL / RETAIN FOR PROVENANCE** pending detached-commit ref review. |
| `/home/charlie/midas-veritas-research-overhaul` | `codex/real-market-research-overhaul` | 25 entries | **UNMERGED WORK**. Preserve 17 modified and 8 untracked V6 files/docs. |
| `/home/charlie/midas-veritas-v6-integration-20261026` | `codex/veritas-v6-integration-20261026` | clean | **FULLY INTEGRATED**; retain provenance history. |
| `/tmp/midas-api-veritas-v2-ccb4211` | detached `ccb42114` | clean | **HISTORICAL / RETAIN FOR PROVENANCE** pending detached-commit ref review. |
| `/tmp/midas-frontier-full-regression-20261028T0435Z` | detached `29b09fa0` | clean | **HISTORICAL / RETAIN FOR PROVENANCE**; isolated regression checkout. |
| `/tmp/midas-frontier-regression-sparse-20261028T0440Z` | detached `c8989d5e` | clean | **HISTORICAL / RETAIN FOR PROVENANCE**; isolated regression checkout. |
| `/tmp/midas-readiness-api-20261026` | `codex/readiness-memory-composition-api-20261026` | clean | **SAFE DELETION CANDIDATE** for the worktree only; branch ref preserves history and no runtime dependency was found. |
| `/tmp/midas-readiness-loading-20261026` | `codex/readiness-loading-state-20261026` | clean | **SAFE DELETION CANDIDATE** for the worktree only; branch ref preserves history and no runtime dependency was found. |
| `/tmp/midas-readiness-web-20261026` | `codex/readiness-memory-composition-web-20261026` | clean | **SAFE DELETION CANDIDATE** for the worktree only; branch ref preserves history and no runtime dependency was found. |
| `/tmp/midas-reality-archive-quota-20261020` | `fix/reality-archive-quota-20261020` | clean | **SAFE DELETION CANDIDATE** for the worktree only; branch ref preserves history and no runtime dependency was found. |
| `/tmp/midas-reality-deploy-guard-20261020` | detached `a4f49593` | 7 entries | **UNMERGED WORK**. Preserve preflight/evidence files and local environment. |
| `/tmp/midas-reality-report-hotpath-20261020` | `fix/reality-report-hotpath-20261020` | clean | **SAFE DELETION CANDIDATE** for the worktree only; branch ref preserves history and no runtime dependency was found. |
| `/tmp/midas-reality-staging-20261020` | detached `87788aee` | clean | **HISTORICAL / RETAIN FOR PROVENANCE**; staging boundary and detached commit need review. |
| `/tmp/midas-reality-status-clear-20261020` | `fix/reality-stale-error-status` | clean | **SAFE DELETION CANDIDATE** for the worktree only; branch ref preserves history and no runtime dependency was found. |
| `/tmp/midas-reliability-reality-361fd6a` | detached `361fd6a2` | 2 entries | **UNMERGED WORK**. Preserve modified source/test files and detached commit. |
| `/tmp/midas-reliability-tests-20261020` | detached `71dcdd90` | 4 entries | **UNMERGED WORK**. Preserve modified/untracked lifecycle tests and detached commit. |
| `/tmp/midas-veritas-fix` | `fix/veritas-gap-market-bound` | clean | **SAFE DELETION CANDIDATE** for the worktree only; branch ref preserves history and no runtime dependency was found. |
| `/tmp/midas-veritas-gap-timer-20261020` | `fix/veritas-gap-timer-stagger-20261020` | clean | **SAFE DELETION CANDIDATE** for the worktree only; branch ref preserves history and no runtime dependency was found. |
| `/tmp/midas-veritas-gapfix-9b0b104` | detached `9b0b1040` | clean | **HISTORICAL / RETAIN FOR PROVENANCE** pending detached-commit ref review. |
| `/tmp/midas-veritas-staging-20261020` | detached `9e342363` | clean | **HISTORICAL / RETAIN FOR PROVENANCE**; staging boundary and detached commit need review. |

“Safe deletion candidate” above refers only to the clean `/tmp` worktree; keep
the named branch ref. No deletion is performed by this manifest. All detached
worktrees remain until their exact commits are checked for other references
and any owner confirms their provenance value.

## Cleanup decision

- Do not delete protected `main`, runtime branches, recovery refs, or any branch
  with source-only history during this mission.
- The eight clean readiness/bug-fix `/tmp` worktrees identified above are
  candidates for later removal after this manifest is reviewed. Keep their
  branch refs.
- Keep all dirty worktrees. Their uncommitted files include evidence, source,
  or explicit staging material whose ownership is not safely disposable.
- Keep detached worktrees until their commits are reachable from a named branch
  or another recovery ref. Do not prune all worktrees or run `git clean`.
- The authoritative future checkout is `/home/charlie/midas-unification` on
  `codex/midas-unification`. Do not merge or push to protected `main` without
  separate authorization.

## Production migration addendum — 2026-10-30

The production migration used the authoritative checkout at release source
b13477e86477eadeccac22ebd84595a808dcd1f9 and staged its versioned artifact
outside the Git worktrees. It did not displace a runtime dependency: the
installed API and Arena scheduler still use /home/charlie/midas, the Reality
services still use /home/charlie/midas-reality or its separate release, and
Veritas timers still use /home/charlie/midas-veritas and their existing
release.

The earlier 29-worktree inventory count was rechecked; no branch or worktree
was removed, reset, cleaned, or rewritten. The current runtime dependencies
therefore do not justify retiring any inventoried worktree in this migration.
Keep the existing clean candidates and historical evidence for the separate
review described above. The complete release and service status are in
[UNIFICATION_PRODUCTION_MIGRATION_REPORT.md](UNIFICATION_PRODUCTION_MIGRATION_REPORT.md).
