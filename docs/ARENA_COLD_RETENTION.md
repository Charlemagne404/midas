# Bounded cold replay retention

The active Arena retains its 1 GiB limit. An explicit additional replay tier at
`data/arena-cold` has a separate 1 GiB limit and requires at least 2 GiB free disk
after copying. This expands bounded local retention capacity; it does not reduce
total disk consumption. Existing exports and protected Laboratory backups are
separate and are not automatically deleted or managed by this mechanism.

Only completed tournaments, recovery studies and unwind studies with verified,
pruned packed stores are eligible. No models, datasets, source snapshots,
Laboratory records or scientific bundles are removed. Selection is explicit;
there is no automatic eviction or age-based deletion.

## Operations

Prepare a verified cold copy while retaining the hot database:

```sh
.venv/bin/python scripts/archive_replays.py --kind tournaments TOURNAMENT_ID
```

After deployment and independent checks, repeat with `--prune` to remove only
the verified hot duplicate. The durable reference is published before unlinking.
The content-addressed cold store retains the exact SQLite bytes. Repeating an
operation reuses and checks the existing copy. Divergent references, checksums,
rows, formats or active workers stop maintenance. Cold-tier maintenance and native
worker/admission locks prevent overlapping writers.

Readers resolve the fixed sibling tier through a validated marker; markers do
not accept arbitrary paths. Replay payload checksums remain checked on reads.
Missing or corrupt evidence fails visibly. Copy publication fsyncs file and
directories; a crash before marker publication leaves the hot copy intact and
the already published cold object reusable. No reference points to an unpublished
temporary file. A read racing with hot unlink retries against the cold store.

The overview reports archived database bytes, the separate limit, reference
count and unavailable stores. This is an availability observation, not a full
integrity audit. Full archive checks verify database hash/schema/quick_check,
exact row coverage and every original replay payload hash.

## Reproduction and restoration

`read_replay`, API replay endpoints, current-policy reproduction and
`scripts/reproduce_archived_policy.py` resolve cold stores. Original-byte replay
restoration through `scripts/pack_replays.py --restore ... --destination ...`
works against either tier and refuses overwriting restored files.

Scientific bundle exports embed the exact database at its original local path
and omit the external-tier marker, so extracted bundles do not depend on the
producer's cold directory. Native test tournaments reproduce both before export
and after isolated extraction. Older captured readers still need original-byte
restoration or the source-aware reproduction helper.

## Production gate and pilot

No production database may be removed until the focused tests, frontend checks,
full backend regression and original-byte backup verification have passed, and
the API is using the new reader. First pilot: the already packed 2,100-replay
generator tournament `tournament-244c26f362d3434084c7f3f3` with its existing
verified original export. Prepare first, independently check all payloads, then
remove the hot duplicate and recheck API/browser replay, original-source inference,
restoration and self-contained export. Record both hot/cold usage and exact hashes.
Do not claim disk savings or multi-day reliability from this operation.

The current implementation handles explicit retention only. Automatic retention
selection, cold-store monitoring/alerts and wider artifact migrations remain
unfinished Prometheus objectives.
