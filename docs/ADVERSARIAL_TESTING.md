# Adversarial testing and incident artifacts

The engine searches seeded scenario families, mutates event times around boundaries,
and combines cancellation/expiration, withdrawal, pause, acknowledgment loss and
idempotency probes. It checks independent invariants at each transition. This is an
active bounded search, not just a fixed catalog. Hypothesis additionally exercises
stateful scheduler sequences, checkpoint boundaries, arithmetic and metamorphic properties.

```bash
.venv/bin/python scripts/laboratory.py search --seed 20261011 --trials 100 --output data/laboratory/search.json
.venv/bin/python scripts/laboratory.py search --seed 7 --trials 8 --controlled --output data/laboratory/calibration.json
.venv/bin/python scripts/laboratory.py reproduce --incident tests/fixtures/milestone3/controlled-ledger.json
```

A failed invariant triggers deterministic delta debugging. The shrinker deletes event
chunks while preserving the failure category, then checks single-event deletion
minimality within an explicit attempt budget. It reports that bounded property, not a
global minimum. A legitimate loss or uncertain fill model cannot be shrunk as a software
failure. Failures are re-executed with complete logs even when successful logs are disabled.

Incident artifacts retain unique ID, component/severity, invariant, classification,
original and minimized inputs, seed, expected/actual behavior, source/simulator/strategy
versions, original/reproduction hashes, state journal, reproduction command and regression
reference. Campaign incidents add observation time and permanent run/campaign IDs.
The original artifact is never replaced merely because another episode passes. The
existing Incidents API includes these summaries; full artifacts remain downloadable.

The demonstration intentionally adds 0.01 to a fill's locked basis. Both rational and
production accounting checks detect it. The original three scenario events shrink to
initial observation plus mutation; the settlement is unnecessary. This is labeled
CONTROLLED_MUTATION/CONTROLLED, not a spontaneously discovered production bug. The
minimized fixture is retained permanently under `tests/fixtures/milestone3`.

Categories are deliberately conservative: controlled mutations remain explicit injected
defects, invariant failures are software-defect candidates pending component triage,
negative valid outcomes are legitimate losses, and execution/cost uncertainty is stored
separately as warnings. Automatic definitive strategy-versus-simulator root-cause analysis
is not implemented. No unsupported causal claim is made from a loss alone. Invalid
financial results are excluded from campaign/comparison financial aggregates while
violation counts remain visible. Losses with valid accounting stay in financial samples.

During development, checkpoint/journal tests caught mutable journal payload aliases;
immutability and exact checkpoint journal equality now have regression coverage.
Browser testing caught a completed-campaign result-cache refresh defect. These are
fixed development defects, distinct from the controlled accounting demonstration.
Manual incident resolution workflows and automated source-code regression-test authoring
are deferred; confirmed/minimized inputs and executable regression fixtures are supported.
