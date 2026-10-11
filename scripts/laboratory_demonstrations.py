"""Persist all four backend demonstrations; the fifth is browser-tested in Playwright."""

import argparse
import json
import time
from pathlib import Path

from midas.laboratory.adversarial import minimize, search
from midas.laboratory.analytics import compare
from midas.laboratory.campaigns import Campaigns, CampaignSpec
from midas.laboratory.spec import generate


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/laboratory-demonstrations"))
    parser.add_argument("--runs", type=int, default=1000)
    parser.add_argument("--output", type=Path, default=Path("docs/MILESTONE_3_DEMONSTRATIONS.json"))
    args = parser.parse_args()
    lab = Campaigns(args.root, Path("data/datasets"))
    output = {}
    specs = {
        "historical_replay": CampaignSpec(
            runs=1, dataset_id="ctf-4024677", models=("optimistic", "standard", "conservative")
        ),
        "scenario_campaign": CampaignSpec(
            runs=args.runs,
            preset="Standard",
            seed=20261011,
            workers=2,
            retain_successes=2,
            max_wall_seconds=600,
        ),
        "adversarial_discovery": CampaignSpec(runs=1, families=("ledger_mutation",), seed=7),
        "execution_comparison": CampaignSpec(
            runs=12,
            families=("calm", "one_sided", "volatile"),
            models=("optimistic", "standard", "conservative"),
            strategies=("arbitrage", "conservative", "no_trade"),
            seed=7,
            workers=2,
        ),
    }
    try:
        for name, spec in specs.items():
            campaign = lab.create(spec)
            while campaign["status"] == "RUNNING":
                time.sleep(0.25)
                campaign = lab.get(campaign["id"])
            lab.threads[campaign["id"]].join()
            campaign = lab.get(campaign["id"])
            rows = lab.runs(campaign["id"], limit=200)
            artifacts = [lab.artifact(r["id"]) for r in rows[:3]]
            # Preserve inspectable summaries and one-command inputs; large successful logs stay local.
            for row in artifacts:
                row["result"].pop("journal", None)
            output[name] = {
                "campaign": campaign,
                "selected_runs": artifacts,
                "reproduction": ".venv/bin/python scripts/laboratory.py campaign --config <campaign-spec.json> --root <new-directory>",
            }
            if name == "execution_comparison":
                output[name]["comparison"] = compare(rows)
            if name == "adversarial_discovery":
                incident = lab.artifact(rows[0]["id"])["incident"]
                artifact_path = args.root / f"incident-{incident['id']}.json"
                artifact_path.write_text(json.dumps(incident, indent=2) + "\n")
                output[name]["incident_path"] = str(artifact_path)
                minimized = minimize(generate("ledger_mutation", 7))
                # A permanent regression fixture contains the exact minimized input and outcome hash.
                fixture = Path("tests/fixtures/milestone3/controlled-ledger.json")
                fixture.parent.mkdir(parents=True, exist_ok=True)
                fixture.write_text(json.dumps(minimized, indent=2) + "\n")
        result = search(20261011, 100, controlled=False)
        output["bounded_adversarial_search"] = {
            k: v for k, v in result.items() if k != "discoveries"
        } | {"discoveries": len(result["discoveries"])}
        search_path = args.root / "adversarial-search.json"
        search_path.write_text(json.dumps(result, indent=2) + "\n")
        output["bounded_adversarial_search"]["artifact_path"] = str(search_path)
        output["interactive_dashboard"] = {
            "reproduction": "corepack pnpm test:e2e",
            "test": "apps/web/e2e/laboratory.spec.ts",
            "evidence": "Browser suite verifies launch, model comparison, stored replay, exact reproduction and controlled minimized incident",
        }
        args.output.write_text(json.dumps(output, indent=2) + "\n")
        print(
            json.dumps(
                {name: value.get("campaign", value) for name, value in output.items()}, indent=2
            )
        )
    finally:
        lab.close()


if __name__ == "__main__":
    main()
