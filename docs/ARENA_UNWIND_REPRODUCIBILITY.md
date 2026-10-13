# Unwind reproducibility

The verification and reexecution commands have different purposes.

## Check saved evidence

```bash
.venv/bin/python scripts/verify_unwind.py UNWIND_ID --root data/arena
```

This checks complete paired coverage, financial/journal hashes, independent
rational and Decimal ledger arithmetic, identical initial buy ledgers, observable
admission inputs, intervention orders, leaderboard metrics and grouped mean
intervals. Admission recomputation uses the policy implementation. It does not
reexecute the broker.

## Reexecute an episode

```bash
.venv/bin/python scripts/reproduce_unwind.py UNWIND_ID ROW_ID --root data/arena
```

This reruns the saved scenario and its fixed observable policy. It requires the
exact package source hash recorded by the study, and compares the complete
financial result hash, journal hash and intervention proposals. It rejects source
drift rather than silently substituting a newer simulator. Use the captured job
source or the recorded source checkpoint when reproducing older studies.

Do not overwrite historical replays with rerun outputs. The optional `--output`
publishes a separate verification report and refuses to overwrite an existing
report. A mismatch is a compatibility finding to investigate, not permission to
regenerate a dataset under its existing identity.

## Scientific limits

Exact reexecution demonstrates deterministic behavior under the same declared
generator, execution, fees and policy. It reuses the broker; independent arithmetic
audits provide a separate accounting check. Neither establishes observed fills,
real-world profitability, calibrated sell costs, or a population loss guarantee.

Four isolated test-study cases, including actually filled repair and sell episodes,
have matched both hashes and proposals. This is a reproducibility smoke check;
production cohort coverage is reported separately after its campaign completes.
