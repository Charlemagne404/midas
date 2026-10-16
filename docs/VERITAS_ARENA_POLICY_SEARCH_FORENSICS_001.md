# Arena policy-search failure forensics 001

## Finding

The Arena policy-search failure recorded by `midas-arena-job-39b5b0c0eac945d298b5c666`
was caused by a legacy tournament manifest that did not contain
`evaluation_generator`. The job's captured source indexed that key directly
while checking whether a fresh challenge seed had already been used.

The job started on 2026-10-12 at 08:54:59 CEST and failed at 08:55:02 CEST
with `KeyError: 'evaluation_generator'`. Its durable job record has SHA256
`8dd8c52fb4c941f93fb4e4cfbd35558fb06aca031cbecb4230bdf3e8be7a9c5c` and
reports submitted source hash
`4febfabb571a2d0c03a8bfc942be5b5cf70e27e56862dbfbd74a925e60e70069`.

## Resolution already in the release baseline

The job's captured `policy_search.py` has SHA256
`2c6fd5b96061cfee96a7bf2abf75fbc61a7395092e6c54fdbfb580eb03295976`. Its
`novel_seeds` function accessed
`record["evaluation_generator"]` directly. Commit
`7ec440ff5ded108e7ec491fada785f3fa41c3494` added the compatibility path:
read the field when present, otherwise use the tournament's challenge
configuration, or derive the generator spec from the referenced dataset.
That fix is an ancestor of release commit
`f968095feb9c591de38fe12d7493224425f62f3a` and is present in the current
`project/veritas` branch.

The current regression in
[`test_fresh_test_rejects_already_registered_seeds`](../tests/arena/test_policy_search.py)
creates a legacy tournament manifest with only `configuration.dataset_id` and
no `evaluation_generator`, then verifies seed overlap against the referenced
dataset manifest. The complete policy-search test file passed: **5 passed in
75.71 seconds**.

## Scope and decision

The failed Arena job was not rerun, and its job record or captured source was
not edited. No Arena or Reality service was restarted. This audit confirms a
historical pre-release defect already fixed and covered by the release test;
it does not identify a current policy-search implementation defect.

The separate job `job-76d27de1b74f4ccd9d6b278d` ended as `CANCELLED` at 384 of
1,001 dataset episodes with the recorded message `Cancellation requested;
completed artifacts retained`. It was not restarted or modified.
