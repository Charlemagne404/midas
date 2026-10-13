"""Compare every cold replay's original bytes with a frozen scientific backup."""

import argparse
import gzip
import hashlib
import json
import sqlite3
import tarfile
from contextlib import closing
from pathlib import Path

from midas.arena.artifacts import artifact_path, sha256
from midas.economics.attestation import digest


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify(root: Path, kind: str, identity: str, backup: Path, expected_backup_sha256: str) -> dict:
    require(kind in {"tournaments", "recoveries", "unwinds"}, "Invalid replay study kind")
    require(sha256(backup) == expected_backup_sha256, "Frozen backup checksum differs")
    study = artifact_path(root, kind, identity)
    directory = study / "replays"
    marker = json.loads((directory / "cold.json").read_text())
    packing = json.loads((directory / "packing.json").read_text())
    require(
        marker["version"] == "cold-replays-1"
        and marker["identity"] == identity
        and marker["kind"] == kind,
        "Cold identity differs",
    )
    require(
        marker["database_sha256"] == packing["database_sha256"], "Cold database provenance differs"
    )
    checksum = marker["database_sha256"]
    require(
        len(checksum) == 64 and all(c in "0123456789abcdef" for c in checksum),
        "Invalid cold address",
    )
    database = root.parent / (root.name + "-cold") / checksum / "replays.sqlite"
    require(
        not any(p.is_symlink() for p in [database, database.parent, database.parent.parent]),
        "Cold path contains symlink",
    )
    require(sha256(database) == checksum, "Cold database checksum differs")
    require(
        sha256(study / "rows.json") == packing["rows_sha256"] == marker["rows_sha256"],
        "Frozen rows checksum differs",
    )
    rows = json.loads((study / "rows.json").read_text())
    indexed = {r["id"] + ".json": r for r in rows}
    require(len(indexed) == len(rows), "Duplicate frozen replay rows")
    verified = 0
    prefix = f"{kind}/{identity}/"
    with (
        tarfile.open(backup, "r:gz") as archive,
        closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as connection,
    ):
        members = archive.getmembers()
        require(len({m.name for m in members}) == len(members), "Duplicate backup member")
        require(
            connection.execute("pragma quick_check").fetchall() == [("ok",)]
            and connection.execute("pragma user_version").fetchone()[0] == 1,
            "Cold schema/integrity differs",
        )
        require(
            {r[0] for r in connection.execute("select name from replays")} == set(indexed),
            "Cold replay coverage differs",
        )
        for name in ("rows.json", "manifest.json"):
            payload = archive.extractfile(prefix + name)
            require(
                payload is not None and payload.read() == (study / name).read_bytes(),
                "Frozen study differs from backup",
            )
        require(
            {i["logical_name"] for i in packing["files"].values()} == set(indexed),
            "Packing replay coverage differs",
        )
        for filename, info in packing["files"].items():
            require(
                Path(filename).name == filename and info["original_format"] in {"json", "gzip"},
                "Invalid restoration entry",
            )
            payload, expected = connection.execute(
                "select payload,sha256 from replays where name=?", (info["logical_name"],)
            ).fetchone()
            require(
                hashlib.sha256(payload).hexdigest() == expected, "Cold payload checksum differs"
            )
            original = payload if info["original_format"] == "gzip" else gzip.decompress(payload)
            require(
                hashlib.sha256(original).hexdigest() == info["sha256"],
                "Original bytes checksum differs",
            )
            member = archive.getmember(prefix + "replays/" + filename)
            require(member.isfile(), "Original backup replay is not a file")
            saved = archive.extractfile(member)
            require(
                saved is not None and saved.read() == original,
                "Cold bytes differ from original backup",
            )
            replay = json.loads(
                gzip.decompress(original) if info["original_format"] == "gzip" else original
            )
            row = indexed[info["logical_name"]]
            result = replay["result"]
            core = {
                k: v
                for k, v in result.items()
                if k not in {"result_hash", "journal_hash", "journal", "runtime"}
            }
            require(
                replay["row"] == row
                and digest(core) == row["result_hash"] == result["result_hash"],
                "Financial replay payload differs",
            )
            require(digest(result["journal"]) == result["journal_hash"], "Replay journal differs")
            verified += 1
    return {
        "kind": kind,
        "identity": identity,
        "database_sha256": checksum,
        "backup_sha256": expected_backup_sha256,
        "original_byte_replays_verified": verified,
        "hot_copy_present": (directory / "replays.sqlite").exists(),
        "producer_sha256": sha256(Path(__file__)),
        "scope": "Independent SQLite reads, complete original-byte backup comparison and financial/journal hash checks; no new simulations or scientific samples.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    parser.add_argument("--kind", choices=("tournaments", "recoveries", "unwinds"), required=True)
    parser.add_argument("identity")
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--backup-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.root.resolve(), args.kind, args.identity, args.backup, args.backup_sha256)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
