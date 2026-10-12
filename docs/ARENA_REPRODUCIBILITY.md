# Arena evidence and reproducibility

All research is synthetic, hypothetical and paper only. Accounting reproduction
does not establish observed fill rates, retrain a model or prove profitability.

## Verify retained evidence

From `/home/charlie/midas` with its CPU research environment:

```bash
.venv/bin/python scripts/verify_arena.py --full-replays
.venv/bin/python scripts/compare_arena.py \
  --control tournament-6bfc67591b6d437085ded3b9 \
  --candidate tournament-5ec7656a30614fd49d78f1cd
```

The audit checks dataset/model/row byte hashes, matched episode/execution
coverage, result financial hashes and replay journal hashes. Partial tournaments
are listed separately. The paired comparison averages execution variants within
each base episode before bootstrapping. Repeated studies do not create new
independent observations.

## Export a completed research director

```bash
.venv/bin/python scripts/arena_bundle.py \
  --director director-84332caaae9c280e078a799b \
  --output /home/charlie/midas-prometheus-bundles/new-evidence.tar.gz
```

Exports require a completed director and refuse to overwrite existing output.
They preserve the dataset, models, sweep, tournaments, replays and captured
director job source. `BUNDLE_MANIFEST.json` lists each file's SHA256 and dependency
versions. Native PPO files should only be loaded from trusted research artifacts.
Legacy incumbent training source snapshots may be unavailable.

The first director bundle is
`/home/charlie/midas-prometheus-bundles/director-84332caaae9c280e078a799b.tar.gz`.
Its digest is
`25bdb83c8bd8778839e6e99b683dabde46ae079f9c66ddd9c2102d84355e4adb`.
Keep the external bundle alongside the protected evidence; do not rewrite it.

## Reproduce a saved accounting path from the exported source

This example runs the captured source in a temporary extraction with the current
installed environment. It verifies a legitimate -7.548 virtual USD partial-leg
loss. It does not claim a fresh installation or repeat policy inference.

```bash
.venv/bin/python - <<'PY'
import sys, tarfile, tempfile
from pathlib import Path

bundle = Path('/home/charlie/midas-prometheus-bundles/director-84332caaae9c280e078a799b.tar.gz')
with tempfile.TemporaryDirectory(prefix='midas-reproduce-') as temporary:
    root = Path(temporary)
    with tarfile.open(bundle) as archive:
        archive.extractall(root, filter='data')
    sys.path.insert(0, str(root / 'jobs/job-605cdb0175c34a34bca7feff/source/packages'))
    from midas.arena.reproduce import reproduce
    print(reproduce(root, 'tournament-6bfc67591b6d437085ded3b9',
                    '40-optimistic-model-3141334b301947499b59913d'))
PY
```

## Validation diagnostics

The supervised model page's **Inspect validation errors** button submits a
bounded `diagnostics` job. It writes `diagnostics.json` next to the model weights,
leaving the original manifest and weights unchanged. Feature permutations retain
donor episode pairing across execution models. Reports contain error examples,
predictive sensitivity and fixed threshold counts, with no selected threshold.
The reports use validation labels only and are not policy P&L studies.

Jobs use the same one-CPU worker lease, 4 GiB memory ceiling and host pressure
checks as training. Inspect or cancel from the Arena job panel. Cancellation
retains finished artifacts; a partial diagnostic report is not published.
Completed reports are reused when provenance matches; changed provenance is
rejected to preserve the saved evidence.

## Policy-search evidence

The current supervised search is `search-948c67bb4c90175f0b1e0294`. Its validation
league and fresh test are separate artifacts. Wait for its authoritative job to
be terminal and its search manifest to say `COMPLETED` before these commands:

```bash
.venv/bin/python scripts/verify_policy_search.py \
  --search search-948c67bb4c90175f0b1e0294 --full-replays
.venv/bin/python scripts/arena_bundle.py \
  --search search-948c67bb4c90175f0b1e0294 \
  --output /home/charlie/midas-prometheus-bundles/policy-search-evidence.tar.gz
```

The search auditor independently recomputes the choice from frozen validation
rows. It checks matched controls, every preregistered gate, underlying weight
hashes, finite outcomes, the fixed downside score, grouped paired uncertainty and
the documented tie rule. It rejects changed selection or final policy bindings.
`--full-replays` additionally verifies every saved financial core/journal hash
and replay row. It does not rerun model inference or prove real fill probabilities.

Search export invokes the full replay audit before publication and rejects
incomplete/missing evidence. It includes the model, dataset, both tournaments,
saved source snapshots and findings associated with the search. Exported file
hashes are calculated from the exact bytes written, one file at a time, so later
model annotations cannot invalidate the bundle's checksum manifest. Existing
bundles are never replaced. Metadata snapshots can include later annotations;
the frozen weights and experiment input references remain explicit.

No-trade can be the selected policy. A validation winner is not an independent
research champion. Neither a mean break-even cost nor a model probability cutoff
is a guaranteed loss bound.

## Paired proposal targets and measured performance replay

```bash
.venv/bin/python scripts/compare_performance_replay.py --original-job job-65fcccb2fd5340c783923279 --replay-job job-6104eea7028e4f04b7233121
.venv/bin/python scripts/audit_proposal_outcomes.py --dataset dataset-f53981b7dd24c1521ce749b1
.venv/bin/python scripts/derive_proposal_target.py --source dataset-f53981b7dd24c1521ce749b1 --target completion
.venv/bin/python scripts/compare_proposal_targets.py --completion-model model-e8ea85c7e7fe49f7a0a2a7b9 --risk-model model-131794f0434945a286163323
```

The derived target preserves observations and partitions and freezes the producer
source. Its identity includes the producer hash, so later script revisions create
a distinct artifact. Reuse verifies existing rows and producer bytes. Development
reports exclude the classifier test partition and contain no refitting. The
performance comparison verifies saved journal/results and repeated specification;
it does not count the same stress seed block as independent research. Derived
parent/transform verification is included in `scripts/verify_arena.py`; recursive
parent and stored transformer inclusion are supported by experiment bundle export,
with parent hashes, exact paired observations and producer bytes verified.
