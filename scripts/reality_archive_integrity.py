import json
import time
from pathlib import Path

from midas.reality.operations import file_hash_list
from midas.reality.replay import replay
from midas.reality.storage import atomic_json, describe

root = Path("/home/charlie/midas-reality/data/recordings/reality-archive-mission2")
raw = root.with_name("reality")
began = time.monotonic()
manifest = json.loads((root / "manifest.json").read_text())
for segment in manifest["segments"]:
    if describe(root / segment["file"]) != segment or describe(raw / segment["file"]) != segment:
        raise ValueError("Archive/source mismatch")
if (
    file_hash_list(manifest["segments"])
    != manifest["archival_provenance"]["source_manifest_sha256"]
):
    raise ValueError("Archive manifest provenance mismatch")
engine, checkpoints = replay(root, manifest)
report = dict(
    checked_ns=time.time_ns(),
    state="VERIFIED",
    segments=len(manifest["segments"]),
    bytes=sum(s["bytes"] for s in manifest["segments"]),
    online_checkpoints=checkpoints,
    source_manifest_sha256=manifest["archival_provenance"]["source_manifest_sha256"],
    published_verified_ns=manifest["archival_provenance"]["verified_ns"],
    originals_deleted=False,
    elapsed_seconds=time.monotonic() - began,
    scope="Last published daily archive prefix; newer raw segments remain in recorder root until next scheduled archive.",
)
atomic_json(Path("/home/charlie/midas-reality/docs/REALITY_GATE_G_ARCHIVE_INTEGRITY.json"), report)
print(json.dumps(report))
