"""One-command campaigns, search, integrity validation and exact reproduction."""

import argparse
import json
import time
from pathlib import Path
from typing import Any

from midas.laboratory.adversarial import search
from midas.laboratory.campaigns import Campaigns, CampaignSpec
from midas.laboratory.datasets import load_dataset, validate
from midas.laboratory.runtime import execute
from midas.laboratory.spec import Scenario


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    campaign = sub.add_parser("campaign")
    campaign.add_argument("--config", type=Path)
    campaign.add_argument("--runs", type=int, default=32)
    campaign.add_argument("--workers", type=int, default=1)
    campaign.add_argument("--seed", type=int, default=7)
    campaign.add_argument("--preset", default="Quick")
    campaign.add_argument("--root", type=Path, default=Path("data/laboratory"))
    campaign.add_argument("--resume")
    campaign.add_argument("--dataset")
    campaign.add_argument("--compare", action="store_true")
    reproduce = sub.add_parser("reproduce")
    reproduce.add_argument("--root", type=Path, default=Path("data/laboratory"))
    reproduce.add_argument("--run")
    reproduce.add_argument("--incident", type=Path)
    reproduce.add_argument("--scenario", type=Path)
    adversarial = sub.add_parser("search")
    adversarial.add_argument("--seed", type=int, default=7)
    adversarial.add_argument("--trials", type=int, default=100)
    adversarial.add_argument("--controlled", action="store_true")
    adversarial.add_argument("--output", type=Path, default=Path("data/laboratory/search.json"))
    dataset = sub.add_parser("validate")
    dataset.add_argument("id")
    args = parser.parse_args()
    datasets = Path(__file__).resolve().parents[1] / "data/datasets"
    result: Any
    if args.action == "validate":
        path, manifest = load_dataset(datasets, args.id)
        result = validate(path, manifest)
    elif args.action == "search":
        if not 1 <= args.trials <= 10_000:
            parser.error("Search trials must be between 1 and 10000")
        result = search(args.seed, args.trials, args.controlled)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n")
        for incident in result["discoveries"]:
            (args.output.parent / f"incident-{incident['id']}.json").write_text(
                json.dumps(incident, indent=2) + "\n"
            )
        print(
            json.dumps(
                {k: v for k, v in result.items() if k != "discoveries"}
                | {"discoveries": len(result["discoveries"]), "output": str(args.output)},
                indent=2,
            )
        )
        return
    elif args.action == "reproduce" and (args.incident or args.scenario):
        data = json.loads((args.incident or args.scenario).read_text())
        scenario = Scenario.model_validate(data["minimized_scenario"] if args.incident else data)
        result = execute(scenario)
        if args.incident and result["result_hash"] != data["reproduction_result_hash"]:
            raise ValueError("Incident did not reproduce its archived result")
        result = {
            "passed": result["passed"],
            "errors": result["errors"],
            "result_hash": result["result_hash"],
            "metrics": result["metrics"],
        }
    else:
        lab = Campaigns(args.root, datasets, read_only=args.action == "reproduce")
        try:
            if args.action == "reproduce":
                if not args.run:
                    parser.error("Select --run, --scenario or --incident")
                result = lab.artifact(args.run)
            else:
                if args.resume:
                    id = args.resume
                    lab.launch(id)
                else:
                    spec = (
                        CampaignSpec.model_validate_json(args.config.read_text())
                        if args.config
                        else CampaignSpec(
                            runs=args.runs,
                            workers=args.workers,
                            seed=args.seed,
                            preset=args.preset,
                            dataset_id=args.dataset,
                            models=("optimistic", "standard", "conservative")
                            if args.compare
                            else ("standard",),
                        )
                    )
                    id = lab.create(spec)["id"]
                while True:
                    row = lab.get(id)
                    if row["status"] != "RUNNING":
                        result = row
                        break
                    time.sleep(0.1)
        finally:
            lab.close()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
