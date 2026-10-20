# Veritas gap-detail v2 runtime release

This immutable source snapshot backs the bounded production v2 replay. Its
contents are the exact files loaded by the isolated runtime overlay used to
create `gap-detail-state-v2.json`; the state records those file hashes and its
aggregate code hash. The service must keep loading this release while that
checkpoint is being extended. A code change that alters those hashes needs a
new output root or an explicit migration.

Install the `packages/` and `scripts/` trees as a physical, read-only release
at `~/.local/share/midas-veritas/gap-detail-v2-20261020/runtime/`. Verify the
stored code identity against the installed files before enabling the timer.
The service unit intentionally reads the installed copy rather than a mutable
worktree. The older `gap-detail-v2-admission-20261020/runtime-overlay` remains
available for rollback.

The checkpoint's `analysis_code_sha256` is
`29cf366aa905f70963e1223d8c54872c08526a604e209f0941542bd879dd9708`. Its
file identities are:

| File | SHA-256 |
| --- | --- |
| `gap_detail_analysis.py` | `95ecab847d79d0bfd27e54186fc301ef964bec0b90cc835d15c4003bebf5b000` |
| `gap_detail_control.py` | `1ca6293e8171dd18dc06376247869515ecc76700dace89c93c4f33a32d1f5029` |
| `reality/research_schema.py` | `fa31024164ae1e20b579403e79417c1eaa8fc2670d154153aae247546d8f9f33` |
| `reality/shadow_campaign.py` | `fbca040df77c90182fa7b94375590f89e95289b21e31a8990da390d1241c9aed` |
| `reality/storage.py` | `551966d10c2494dd6fcb50988bf32c26558ff6a02d6bd68617f8593b1f5ec3cc` |
| `scripts/veritas_gap_detail_analysis.py` | `c99af3561a83aef189dc077bc909d9f187f68e1a06fb365d21461135f927709c` |

The release reads only finalized Reality segments and the pinned Mission 2
campaign. Its output root is `~/midas-veritas/data/veritas-gap-detail-v2`,
separate from the preserved v1 results. `scripts/veritas_gap_detail_v2_batch.py`
admits a batch only when the host pressure, disk and memory gates pass and
there is no active Arena job. Each admitted run is limited to 128 segments,
32 MiB source input, 256 MiB memory, no swap, one CPU and idle I/O priority.

The runtime output records the campaign SHA-256, source root, processed source
prefix, segment count and code identity. The v1 output and its pinned identity
are not rewritten.
