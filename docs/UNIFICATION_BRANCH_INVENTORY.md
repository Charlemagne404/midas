# MIDAS Git branch and worktree inventory — 2026-11-05 snapshot

**Reference snapshot:** 2026-11-05 at `origin/main` commit
`4f17b875f1e2aa9d602530b07630d80be3157d29`, after the first source
integration. The table records refs at that point; later commits only refreshed
operational documentation. Verify current refs before using the per-branch
heads below.
There are **64 local branches**, **56 fetched `origin` branch heads**, and
**37 worktrees**. Each fetched origin head has a same-name local branch; eight
local branches have no matching origin ref. Source-only changes were
fast-forwarded to `origin/main` at
`4f17b875f1e2aa9d602530b07630d80be3157d29`. The active runtime checkout's
local `main` was at `b723bfda47dc5fae3103725a1dbe341f35487754`, 27 commits
behind at the snapshot, and was not advanced. The local maintenance branch
shared `origin/main`; its remote candidate ref was one commit behind then. Work reused
`/home/charlie/midas-maintenance`; no worktree was added. The maintenance
worktree was clean after first integration; this follow-up only refreshes
operational documentation. The last full worktree status audit found nine
dirty worktrees, but was not repeated while swap is full and production
services are active. Ignored data remains outside Git status. No branches,
worktrees, or files were removed. Recheck all statuses and ignored data before
cleanup. The old 2026-10-30 inventory follows as historical evidence.

For housekeeping planning, the local refs divide into 3 service-owned runtime
branches, 1 current release-readiness candidate, 30 validation/control
snapshots, 11 history or recovery references, and 19 other historical, feature,
or maintenance refs. These categories describe branch purpose; they do not
prove which commit a running process has loaded.

## Branch refs and dispositions

The table lists every local branch, its exact head, and the matching fetched origin head where one exists. `—` means the ref is local-only. At this inventory snapshot, `origin/main` was `4f17b875f1e2aa9d602530b07630d80be3157d29`; local runtime `main` was 27 commits behind. The squash integration `6aa7c7f00d736d02ee7ca5629d1b9f102e0ae9d9` is an ancestor of main. The original `codex/midas-unification` ref remains available at `c256cd1b0743d0c3ba6229c0115fd200fa0f014f`; its original development history is not an ancestor of the squash. The preservation tags from the consolidation remain present.

| Local branch | Head | Matching `origin` head | Current disposition |
|---|---:|---:|---|
| `checkpoint/frontier-memory-interruption-20261029-0854` | `75e6f26` | `75e6f26` | Checkpoint or recovery provenance; retain. |
| `checkpoint/frontier-pre-followup-20261029-0558` | `0bbb62e` | `0bbb62e` | Checkpoint or recovery provenance; retain. |
| `checkpoint/frontier-pre-memory-incident-20261029` | `a8fbcd7` | `a8fbcd7` | Checkpoint or recovery provenance; retain. |
| `codex/frontier-20261026` | `f6ac37f` | `f6ac37f` | Historical research/feature tip; compare with current source before reuse; retain until its commits and associated data are backed up and classified. |
| `codex/frontier-capacity-scan-bound-20261029` | `d5847df` | `d5847df` | Selected functionality was reconciled during consolidation; retain branch history pending a separate cleanup review. |
| `codex/midas-ci-stabilization-20261105` | `c00bd12` | `c00bd12` | Previous source base, superseded by `origin/main` at `7ab2d0d`; keep pending environment/data review. |
| `codex/midas-comprehensive-engineering-mission-20261025` | `005f6fa` | `005f6fa` | Historical research/feature tip; compare with current source before reuse; retain until its commits and associated data are backed up and classified. |
| `codex/midas-integration-20261104` | `b723bfd` | `—` | Historical integration checkpoint with a dirty worktree; preserve all edits and data. |
| `codex/midas-maintenance-20261105` | `3e700b9` | `3e700b9` | Previous maintenance baseline, superseded by `origin/main`; retain pending environment/data review. |
| `codex/midas-operational-resilience-20261105` | `dcefed2` | `dcefed2` | Previous Veritas bounded-memory source candidate; its source changes are in the later baseline. Retain its technical history pending environment/data review. |
| `codex/midas-release-readiness-20261105` | `4f17b87` | `7d06ec1` | At this snapshot, source-only changes were integrated in `origin/main`; remote candidate ref was one commit behind. Do not deploy. |
| `codex/midas-squash-integration-20261105` | `6aa7c7f` | `—` | Original squash integration, ancestor of current `origin/main`; retain as history. |
| `codex/midas-unification` | `c256cd1` | `c256cd1` | Original 1,196-commit development history; retained on its local and remote refs, not current baseline. |
| `codex/midas-validation-control-20261105` | `d1fb321` | `d1fb321` | Validation snapshot/checkpoint; retain until its evidence and owner are separately reviewed. |
| `codex/midas-validation-control-20261105-r2` | `c827be9` | `c827be9` | Validation snapshot/checkpoint; retain until its evidence and owner are separately reviewed. |
| `codex/midas-validation-control-20261105-r3` | `7910898` | `7910898` | Validation snapshot/checkpoint; retain until its evidence and owner are separately reviewed. |
| `codex/midas-validation-control-20261105-r4` | `4bdfbc0` | `4bdfbc0` | Validation snapshot/checkpoint; retain until its evidence and owner are separately reviewed. |
| `codex/midas-validation-control-20261105-r5` | `8b233f4` | `8b233f4` | Validation snapshot/checkpoint; retain until its evidence and owner are separately reviewed. |
| `codex/midas-validation-snapshot-20261105` | `8c450aa` | `—` | Validation snapshot/checkpoint; retain until its evidence and owner are separately reviewed. |
| `codex/midas-validation-snapshot-20261105-r10` | `93e94d2` | `93e94d2` | Validation snapshot/checkpoint; retain until its evidence and owner are separately reviewed. |
| `codex/midas-validation-snapshot-20261105-r10-preservation` | `1438d62` | `—` | Validation snapshot/checkpoint; retain until its evidence and owner are separately reviewed. |
| `codex/midas-validation-snapshot-20261105-r11` | `0b5303d` | `0b5303d` | Validation snapshot/checkpoint; retain until its evidence and owner are separately reviewed. |
| `codex/midas-validation-snapshot-20261105-r12` | `8a2bd48` | `8a2bd48` | Validation snapshot/checkpoint; retain until its evidence and owner are separately reviewed. |
| `codex/midas-validation-snapshot-20261105-r13` | `cd7a159` | `cd7a159` | Validation snapshot/checkpoint; retain until its evidence and owner are separately reviewed. |
| `codex/midas-validation-snapshot-20261105-r14` | `f4d9136` | `f4d9136` | Validation snapshot/checkpoint; retain until its evidence and owner are separately reviewed. |
| `codex/midas-validation-snapshot-20261105-r15` | `2c6dcaa` | `2c6dcaa` | Validation snapshot/checkpoint; retain until its evidence and owner are separately reviewed. |
| `codex/midas-validation-snapshot-20261105-r16` | `5c4d910` | `5c4d910` | Validation snapshot/checkpoint; retain until its evidence and owner are separately reviewed. |
| `codex/midas-validation-snapshot-20261105-r17` | `2715617` | `2715617` | Validation snapshot/checkpoint; retain until its evidence and owner are separately reviewed. |
| `codex/midas-validation-snapshot-20261105-r18` | `97d1c64` | `97d1c64` | Validation snapshot/checkpoint; retain until its evidence and owner are separately reviewed. |
| `codex/midas-validation-snapshot-20261105-r19` | `57d126f` | `57d126f` | Validation snapshot/checkpoint; retain until its evidence and owner are separately reviewed. |
| `codex/midas-validation-snapshot-20261105-r2` | `dcb800b` | `—` | Validation snapshot/checkpoint; retain until its evidence and owner are separately reviewed. |
| `codex/midas-validation-snapshot-20261105-r20` | `a20c184` | `a20c184` | Validation snapshot/checkpoint; retain until its evidence and owner are separately reviewed. |
| `codex/midas-validation-snapshot-20261105-r21` | `49602ae` | `49602ae` | Validation snapshot/checkpoint; retain until its evidence and owner are separately reviewed. |
| `codex/midas-validation-snapshot-20261105-r22` | `fb07638` | `fb07638` | Validation snapshot/checkpoint; retain until its evidence and owner are separately reviewed. |
| `codex/midas-validation-snapshot-20261105-r23` | `53a5dcc` | `53a5dcc` | Validation snapshot/checkpoint; retain until its evidence and owner are separately reviewed. |
| `codex/midas-validation-snapshot-20261105-r24` | `2708269` | `2708269` | Validation snapshot/checkpoint; retain until its evidence and owner are separately reviewed. |
| `codex/midas-validation-snapshot-20261105-r3` | `32a5ab3` | `—` | Validation snapshot/checkpoint; retain until its evidence and owner are separately reviewed. |
| `codex/midas-validation-snapshot-20261105-r4` | `1a159cc` | `—` | Validation snapshot/checkpoint; retain until its evidence and owner are separately reviewed. |
| `codex/midas-validation-snapshot-20261105-r5` | `91762c8` | `91762c8` | Validation snapshot/checkpoint; retain until its evidence and owner are separately reviewed. |
| `codex/midas-validation-snapshot-20261105-r6` | `001536c` | `001536c` | Validation snapshot/checkpoint; retain until its evidence and owner are separately reviewed. |
| `codex/midas-validation-snapshot-20261105-r7` | `4323137` | `4323137` | Validation snapshot/checkpoint; retain until its evidence and owner are separately reviewed. |
| `codex/midas-validation-snapshot-20261105-r8` | `b22b48f` | `—` | Validation snapshot/checkpoint; retain until its evidence and owner are separately reviewed. |
| `codex/midas-validation-snapshot-20261105-r9` | `1c41970` | `1c41970` | Validation snapshot/checkpoint; retain until its evidence and owner are separately reviewed. |
| `codex/readiness-loading-state-20261026` | `767f330` | `767f330` | Selected functionality was reconciled during consolidation; retain branch history pending a separate cleanup review. |
| `codex/readiness-memory-composition-api-20261026` | `a152999` | `a152999` | Selected functionality was reconciled during consolidation; retain branch history pending a separate cleanup review. |
| `codex/readiness-memory-composition-web-20261026` | `4e64a2e` | `4e64a2e` | Selected functionality was reconciled during consolidation; retain branch history pending a separate cleanup review. |
| `codex/real-market-research-overhaul` | `3b10292` | `3b10292` | Historical research/feature tip; compare with current source before reuse; retain until its commits and associated data are backed up and classified. |
| `codex/reality-archive-provenance-20261026` | `a1f2fe9` | `a1f2fe9` | Historical research/feature tip; compare with current source before reuse; retain until its commits and associated data are backed up and classified. |
| `codex/veritas-v6-integration-20261026` | `11d32a0` | `11d32a0` | Selected functionality was reconciled during consolidation; retain branch history pending a separate cleanup review. |
| `fix/reality-archive-quota-20261020` | `350db69` | `350db69` | Selected functionality was reconciled during consolidation; retain branch history pending a separate cleanup review. |
| `fix/reality-foundation-20261020` | `4278b5b` | `4278b5b` | Historical research/feature tip; compare with current source before reuse; retain until its commits and associated data are backed up and classified. |
| `fix/reality-report-hotpath-20261020` | `397ec50` | `397ec50` | Selected functionality was reconciled during consolidation; retain branch history pending a separate cleanup review. |
| `fix/reality-stale-error-status` | `b0610c1` | `b0610c1` | Selected functionality was reconciled during consolidation; retain branch history pending a separate cleanup review. |
| `fix/veritas-gap-market-bound` | `49275d9` | `49275d9` | Selected functionality was reconciled during consolidation; retain branch history pending a separate cleanup review. |
| `fix/veritas-gap-timer-stagger-20261020` | `e530cef` | `e530cef` | Selected functionality was reconciled during consolidation; retain branch history pending a separate cleanup review. |
| `main` | `b723bfd` | `4f17b87` | Runtime source branch; 27 commits behind `origin/main`; retain while loaded services depend on it. |
| `preservation/phase1/reality-staging-87788aee` | `87788ae` | `87788ae` | Checkpoint or recovery provenance; retain. |
| `preservation/phase1/veritas-staging-9e342363` | `9e34236` | `9e34236` | Checkpoint or recovery provenance; retain. |
| `project/reality` | `d8629e4` | `d8629e4` | Active Reality service/data branch; retain. |
| `project/veritas` | `3b10292` | `3b10292` | Active Veritas service/data branch; retain. |
| `recovery/preconsolidation-main-20261017` | `f968095` | `f968095` | Checkpoint or recovery provenance; retain. |
| `recovery/preconsolidation-reality-20261017` | `2b83818` | `2b83818` | Checkpoint or recovery provenance; retain. |
| `recovery/preconsolidation-veritas-20261017` | `1f8f1df` | `1f8f1df` | Checkpoint or recovery provenance; retain. |
| `recovery/veritas-uncommitted-20261017` | `683dba2` | `683dba2` | Checkpoint or recovery provenance; retain. |

## Worktrees and dispositions

All 37 registered worktrees are listed below. Preserve every dirty worktree and every clean historical checkout until both its ignored data and provenance are classified. “Clean” describes Git status only; it does not imply that the directory can be deleted.

| Worktree | Branch / state | HEAD | Tracked and untracked status entries | Disposition |
|---|---|---:|---:|---|
| `/home/charlie/midas` | `main` | `b723bfda` | 0 | Active runtime checkout; 27 commits behind current `origin/main`; preserve its files and processes. |
| `/home/charlie/midas-ci-stabilization-20261105` | `codex/midas-ci-stabilization-20261105` | `c00bd128` | 0 | Clean previous CI checkout, superseded by current `origin/main`; retain pending ignored-data and environment review. |
| `/home/charlie/midas-engineering-mission-20261025` | `codex/midas-comprehensive-engineering-mission-20261025` | `005f6fa5` | 6 | Preserve all modified/untracked entries exactly; ownership/data not safe to discard. |
| `/home/charlie/midas-frontier` | `codex/frontier-20261026` | `f6ac37ff` | 1 | Preserve all modified/untracked entries exactly; ownership/data not safe to discard. |
| `/home/charlie/midas-integration-20261104` | `codex/midas-integration-20261104` | `b723bfda` | 444 | Preserve 444 modified/untracked entries exactly; ownership/data not safe to discard. |
| `/home/charlie/midas-maintenance` | `codex/midas-release-readiness-20261105` | `4f17b875` | 0 | At the reference snapshot, release-readiness changes were integrated in `origin/main`; operational-document refresh follows. |
| `/home/charlie/midas-reality` | `project/reality` | `d8629e4b` | 0 | Active Reality service and recording data owner; preserve. |
| `/home/charlie/midas-reality-archive-provenance` | `codex/reality-archive-provenance-20261026` | `a1f2fe99` | 0 | Clean historical/experimental checkout; no deletion authorized; retain pending data and owner review. |
| `/home/charlie/midas-reality-capacity-scan-frontier-20261029` | `codex/frontier-capacity-scan-bound-20261029` | `d5847df1` | 0 | Clean historical/experimental checkout; no deletion authorized; retain pending data and owner review. |
| `/home/charlie/midas-reality-reliability` | `fix/reality-foundation-20261020` | `4278b5b5` | 26 | Preserve 26 modified/untracked entries exactly; ownership/data not safe to discard. |
| `/home/charlie/midas-unification` | `codex/midas-unification` | `c256cd1b` | 0 | Clean historical source checkout; preserve original unification history. |
| `/home/charlie/midas-validation-control-20261105` | `codex/midas-validation-control-20261105` | `d1fb3216` | 2 | Preserve 2 modified/untracked entries exactly; ownership/data not safe to discard. |
| `/home/charlie/midas-validation-control-20261105-r2` | `codex/midas-validation-control-20261105-r2` | `c827be91` | 0 | Clean historical/experimental checkout; no deletion authorized; retain pending data and owner review. |
| `/home/charlie/midas-validation-control-20261105-r3` | `codex/midas-validation-control-20261105-r3` | `79108982` | 0 | Clean historical/experimental checkout; no deletion authorized; retain pending data and owner review. |
| `/home/charlie/midas-validation-control-20261105-r4` | `codex/midas-validation-control-20261105-r4` | `4bdfbc07` | 0 | Clean historical/experimental checkout; no deletion authorized; retain pending data and owner review. |
| `/home/charlie/midas-validation-control-20261105-r5` | `codex/midas-validation-control-20261105-r5` | `8b233f45` | 0 | Clean historical/experimental checkout; no deletion authorized; retain pending data and owner review. |
| `/home/charlie/midas-veritas` | `project/veritas` | `3b102928` | 0 | Active Veritas timer/data owner; preserve. |
| `/home/charlie/midas-veritas-gap-v2-code` | `DETACHED` | `71dcdd90` | 0 | Detached historical checkout; retain its commit and inspect any ignored data before cleanup. |
| `/home/charlie/midas-veritas-research-overhaul` | `codex/real-market-research-overhaul` | `3b102928` | 25 | Preserve 25 modified/untracked entries exactly; ownership/data not safe to discard. |
| `/home/charlie/midas-veritas-v6-integration-20261026` | `codex/veritas-v6-integration-20261026` | `11d32a06` | 0 | Clean historical/experimental checkout; no deletion authorized; retain pending data and owner review. |
| `/tmp/midas-api-veritas-v2-ccb4211` | `DETACHED` | `ccb42114` | 0 | Detached historical checkout; retain its commit and inspect any ignored data before cleanup. |
| `/tmp/midas-frontier-full-regression-20261028T0435Z` | `DETACHED` | `29b09fa0` | 0 | Detached historical checkout; retain its commit and inspect any ignored data before cleanup. |
| `/tmp/midas-frontier-regression-sparse-20261028T0440Z` | `DETACHED` | `c8989d5e` | 0 | Detached historical checkout; retain its commit and inspect any ignored data before cleanup. |
| `/tmp/midas-readiness-api-20261026` | `codex/readiness-memory-composition-api-20261026` | `a1529991` | 0 | Clean historical/experimental checkout; no deletion authorized; retain pending data and owner review. |
| `/tmp/midas-readiness-loading-20261026` | `codex/readiness-loading-state-20261026` | `767f3300` | 0 | Clean historical/experimental checkout; no deletion authorized; retain pending data and owner review. |
| `/tmp/midas-readiness-web-20261026` | `codex/readiness-memory-composition-web-20261026` | `4e64a2ea` | 0 | Clean historical/experimental checkout; no deletion authorized; retain pending data and owner review. |
| `/tmp/midas-reality-archive-quota-20261020` | `fix/reality-archive-quota-20261020` | `350db699` | 0 | Clean historical/experimental checkout; no deletion authorized; retain pending data and owner review. |
| `/tmp/midas-reality-deploy-guard-20261020` | `DETACHED` | `a4f49593` | 6 | Preserve all modified/untracked entries exactly; ownership/data not safe to discard. |
| `/tmp/midas-reality-report-hotpath-20261020` | `fix/reality-report-hotpath-20261020` | `397ec50e` | 0 | Clean historical/experimental checkout; no deletion authorized; retain pending data and owner review. |
| `/tmp/midas-reality-staging-20261020` | `DETACHED` | `87788aee` | 0 | Detached historical checkout; retain its commit and inspect any ignored data before cleanup. |
| `/tmp/midas-reality-status-clear-20261020` | `fix/reality-stale-error-status` | `b0610c1b` | 0 | Clean historical/experimental checkout; no deletion authorized; retain pending data and owner review. |
| `/tmp/midas-reliability-reality-361fd6a` | `DETACHED` | `361fd6a2` | 2 | Preserve 2 modified/untracked entries exactly; ownership/data not safe to discard. |
| `/tmp/midas-reliability-tests-20261020` | `DETACHED` | `71dcdd90` | 4 | Preserve 4 modified/untracked entries exactly; ownership/data not safe to discard. |
| `/tmp/midas-veritas-fix` | `fix/veritas-gap-market-bound` | `49275d98` | 0 | Clean historical/experimental checkout; no deletion authorized; retain pending data and owner review. |
| `/tmp/midas-veritas-gap-timer-20261020` | `fix/veritas-gap-timer-stagger-20261020` | `e530ceff` | 0 | Clean historical/experimental checkout; no deletion authorized; retain pending data and owner review. |
| `/tmp/midas-veritas-gapfix-9b0b104` | `DETACHED` | `9b0b1040` | 0 | Detached historical checkout; retain its commit and inspect any ignored data before cleanup. |
| `/tmp/midas-veritas-staging-20261020` | `DETACHED` | `9e342363` | 0 | Detached historical checkout; retain its commit and inspect any ignored data before cleanup. |

## Preservation and cleanup result

- The 26 orphaned commit objects discovered in the refreshed object inventory are retained by **24 refs** under `refs/preservation/orphaned-20261105/`. `git fsck --no-reflogs --unreachable` reports no unreachable commits after pinning, though unrelated unreachable tree/blob objects remain. No garbage collection was run.
- No stale worktree or origin bookkeeping was identified by the dry-run prune commands. No pruning, checkout cleanup, branch deletion, or worktree removal was performed.
- Nine worktrees currently have uncommitted entries: `/home/charlie/midas-engineering-mission-20261025` (6), `/home/charlie/midas-frontier` (1), `/home/charlie/midas-integration-20261104` (444), `/home/charlie/midas-reality-reliability` (26), `/home/charlie/midas-validation-control-20261105` (2), `/home/charlie/midas-veritas-research-overhaul` (25), `/tmp/midas-reality-deploy-guard-20261020` (6), `/tmp/midas-reliability-reality-361fd6a` (2), and `/tmp/midas-reliability-tests-20261020` (4). Their entries remain untouched. The maintenance worktree has zero Git status entries.
- The current `data/backups/` ignore rule prevents accidental staging of local snapshots. It does not constitute backup storage or an independent copy.
- The separate 2026-10-30 tables below preserve the earlier code-level branch comparison and migration narrative. Use this refreshed table for today's Git refs and worktree states; verify again before any later cleanup.

## Future retirement candidates (not authorization)

- `codex/midas-maintenance-20261105` (`3e700b9`),
  `codex/midas-ci-stabilization-20261105` (`c00bd12`), and
  `codex/midas-operational-resilience-20261105` (`dcefed2`) are superseded by
  the current source baseline and are eventual branch retirement candidates.
  The `/home/charlie/midas-maintenance` worktree is now attached to the
  separate release-readiness branch; the other dated worktrees remain subject
  to their own ownership and data review. No candidate is safe to remove until
  ignored data is inventoried, required research evidence is backed up, and
  active sessions are confirmed finished.
- The largest future space cleanup candidates are the 30 validation/control
  snapshot branches and the 17 temporary `/tmp` worktrees. Several worktrees were
  dirty in the last full status audit, and even a clean Git status does not
  account for ignored stores. Preserve them until exact manifests and
  independent copies exist.
- Branches marked “selected functionality reconciled” have no current runtime
  path identified, but their research history remains valuable provenance.
  Keep those refs until their distinct commits and associated data have an
  independently preserved manifest.
- Do not retire the service-owned `main`, `project/reality`, or `project/veritas`
  worktrees, the current release-readiness worktree, any dirty worktree, the original `codex/midas-unification`
  history, recovery/preservation refs, or detached checkouts whose commit has
  not been pinned elsewhere. Ignored data must be inventoried and backed up
  before removing any worktree.

# Historical inventory (2026-10-30 snapshot; superseded)

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
