"""Describe saved recovery proposal coverage without conditioning primary results."""

import argparse
import json
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

from midas.arena.artifacts import artifact_path, read_replay, sha256
from midas.economics.attestation import digest


def summarize(entries: list[tuple[dict, list[dict]]]) -> dict:
    buckets = defaultdict(list)
    for row, proposals in entries:
        for proposal in proposals:
            if (
                digest({k: v for k, v in proposal.items() if k != "evidence_sha256"})
                != proposal["evidence_sha256"]
            ):
                raise ValueError("Proposal checksum differs")
        if sum(bool(p["allowed"]) for p in proposals) != row["intervention_requests"]:
            raise ValueError("Requested intervention count differs")
        buckets[row["policy"] + "/" + row["execution_model"]].append((row, proposals))
    report = {}
    for name, rows in sorted(buckets.items()):
        reasons = Counter()
        residual, proposed, allowed, filled = set(), set(), set(), set()
        for row, proposals in rows:
            group = row["base_episode_id"]
            if proposals:
                proposed.add(group)
            for proposal in proposals:
                if Decimal(proposal.get("residual_before", "0")) > 0:
                    residual.add(group)
                if proposal["allowed"]:
                    allowed.add(group)
                else:
                    reasons.update(set(proposal["reasons"]))
            if Decimal(row["intervention_filled_shares"]) > 0:
                filled.add(group)
        report[name] = {
            "source_groups": len({row["base_episode_id"] for row, _ in rows}),
            "groups_with_proposals": len(proposed),
            "groups_with_residual_at_proposal": len(residual),
            "groups_with_allowed_request": len(allowed),
            "groups_with_intervention_fill": len(filled),
            "blocked_reason_counts": dict(reasons),
        }
    return report


def analyze(root: Path, identity: str) -> dict:
    directory = artifact_path(root, "unwinds", identity)
    manifest = json.loads((directory / "manifest.json").read_text())
    if (
        manifest["state"] != "COMPLETED"
        or sha256(directory / "rows.json") != manifest["rows_sha256"]
    ):
        raise ValueError("Require completed unchanged rows")
    rows = json.loads((directory / "rows.json").read_text())
    entries = []
    for row in rows:
        saved = read_replay(directory / "replays" / (row["id"] + ".json"))
        if saved["row"] != row or digest(saved["result"]["journal"]) != row["journal_hash"]:
            raise ValueError("Saved replay differs from row")
        entries.append((row, saved["intervention_decisions"]))
    return {
        "unwind_id": identity,
        "rows_sha256": manifest["rows_sha256"],
        "source_groups": manifest["source_groups"],
        "correlated_variants": len(rows),
        "coverage": summarize(entries),
        "producer_sha256": sha256(Path(__file__)),
        "limitations": [
            "Descriptive coverage only; primary comparisons retain every source group.",
            "Residual is measured at saved proposal time, not throughout all episodes.",
            "Reasons can overlap; counts are not mutually exclusive.",
            "No proposal can mean no initial trade, no decision callback, or a hold/no-trade control.",
            "Synthetic fills; not empirical exit liquidity or execution probability.",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("identity")
    parser.add_argument("--root", type=Path, default=Path("data/arena"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = analyze(args.root, args.identity)
    with args.output.open("x") as stream:
        stream.write(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
