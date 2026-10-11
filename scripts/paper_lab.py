import argparse
import json

from midas.paper.broker import ExecutionModel
from midas.paper.experiments import differential, run_experiment

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--fault", default="none")
    parser.add_argument("--model", default="standard")
    parser.add_argument("--compare", action="store_true")
    args = parser.parse_args()
    result = (
        differential(args.seed, args.fault)
        if args.compare
        else run_experiment(args.seed, ExecutionModel.preset(args.model), args.fault)
    )
    print(json.dumps(result, indent=2))
