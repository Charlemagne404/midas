# Veritas gap-detail v2 operational-capacity release

This immutable runtime continues the existing `gap-detail-state-v2.json`
checkpoint. The analyzer package files and the pinned analyzer CLI are byte for
byte identical to the prior production runtime. The persisted
`analysis_code_sha256` remains
`29cf366aa905f70963e1223d8c54872c08526a604e209f0941542bd879dd9708`; no v1 or
v2 event, state, summary, campaign, or source file is rewritten.

Only the batch wrapper and its systemd unit change. The wrapper applies the
configured artifact ceiling to the analyzer in memory for that invocation,
then restores its imported default. It reports cumulative artifact bytes on
each run that obtains the global admission lease, warns at 75%, and pauses
before analysis at 90% so the analyzer does not fail midway through an append
at its hard bound. The ceiling is 4 GiB. Admission also preserves 20 GiB for
the shared NVMe reserve
and one full 4 GiB next-batch artifact allowance; it defers work below 24 GiB
free. CPU, memory, I/O, Arena-worker and global-lease gates remain enabled.

At 2026-10-21 10:12 CEST, analyzer-counted v2 artifacts were 35,258,139 bytes.
They grew over 1.316 days, about 26.8 MB/day. A 90-day forecast at 1.2 times
that measured rate is 2,892,980,257 bytes, below the 4 GiB ceiling; the ceiling
would provide about 134 days at that rate. This is a forecast from a short
window, not a long-term guarantee. The 75% warning and 90% pause make growth
visible and stop further processing before the bound is reached.

The pinned analyzer file identities are:

| File | SHA-256 |
| --- | --- |
| `gap_detail_analysis.py` | `95ecab847d79d0bfd27e54186fc301ef964bec0b90cc835d15c4003bebf5b000` |
| `gap_detail_control.py` | `1ca6293e8171dd18dc06376247869515ecc76700dace89c93c4f33a32d1f5029` |
| `reality/research_schema.py` | `fa31024164ae1e20b579403e79417c1eaa8fc2670d154153aae247546d8f9f33` |
| `reality/shadow_campaign.py` | `fbca040df77c90182fa7b94375590f89e95289b21e31a8990da390d1241c9aed` |
| `reality/storage.py` | `551966d10c2494dd6fcb50988bf32c26558ff6a02d6bd68617f8593b1f5ec3cc` |
| `scripts/veritas_gap_detail_analysis.py` | `c99af3561a83aef189dc077bc909d9f187f68e1a06fb365d21461135f927709c` |

Install the `packages/` and `scripts/` trees as a physical, read-only release
at `~/.local/share/midas-veritas/gap-detail-v2-20261021/runtime/`. The service
unit must point to this release rather than a mutable checkout. The analyzer
reads only finalized Reality segments and the pinned Mission 2 campaign. Its
output root remains `~/midas-veritas/data/veritas-gap-detail-v2`, separate
from preserved v1 results.
