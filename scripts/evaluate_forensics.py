"""Reproduce the controlled allocation experiment without any database credentials."""

import argparse
import json
from pathlib import Path

from settlement_recon.forensics_evaluation import evaluate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=40)
    parser.add_argument("--seed", type=int, default=20261030)
    parser.add_argument("--output", type=Path, default=Path("evidence/forensics-evaluation.json"))
    args = parser.parse_args()
    result = evaluate(args.trials, args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                name: {key: value[key] for key in ["precision", "coverage", "false_suggestions"]}
                for name, value in result["policies"].items()
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
