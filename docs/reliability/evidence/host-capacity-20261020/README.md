# Capacity-overhaul evidence

See the parent report for workload definitions, limitations and verdicts. JSON values use bytes/seconds unless explicitly named otherwise. CPU percentages distinguish one-core service consumption from aggregate six-core busy time.

- `baseline-summary.json`: 13 samples before first API restart (3.03 minutes).
- `pre-codec-summary.json`: stable plain-head intermediate window (38.80 minutes).
- `final-summary.json`: 242 samples inside uninterrupted final observation (60.72 minutes).
- `endurance-summary.json`: 62 health observations spanning 3660 seconds; actual useful work and source-quality exceptions.
- `normalized-production-work.json`: index-bounded observation counts, accounted writes/command and CPU/command including API reads. Different external request activity remains a confounder.
- Component benchmark samples preserve equivalent outputs/hashes. They are not full-host claims. `state-storage-benchmark.json` includes FULL-sync commits and checkpoint, two repetitions/version.
- `cgroup-details.json` distinguishes cache, reclaim, local pressure, high/max/OOM events and process RSS.
- Release manifests, identity comparison, old-code rollback receipt and final verification record what was deployed and protected.
- `full-store-admission.json` / `final-full-store-admission.json` are negative guard receipts; no full-store workload was launched.
- `storage-growth-model.json` is a one-hour linear estimate; `capacity-monitor-final.json` independently corroborates runway. Neither proves long-term or multi-source capacity.

Raw process time series and captured private account state stay gitignored under `data/host-capacity-20261020/`. No raw financial head payload or whole-process trace is included here. Required production services were not disabled for measurements, protected recorder was never restarted, and caches/swap were not cleared.
