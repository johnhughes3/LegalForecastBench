"""Compare paired public unit scores with case-cluster bootstrap intervals.

Run: uv run scripts/compare_site_results.py --inputs inputs.json --output result.json
The input models field maps public model slugs to relative JSONL unit-score paths.
It also records provenance, missing_models, and the planned family_model_count.
Use --family-model-count to retain a larger planned comparison family when some
models lack evidence. Missing pairs are never treated as nonsignificant.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from legalforecast.publication.site_comparison import compare


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--replicates", type=int, default=1_000_000)
    parser.add_argument("--seed", type=int, default=20260514)
    parser.add_argument("--family-model-count", type=int)
    args = parser.parse_args()
    inputs = json.loads(args.inputs.read_text())
    paths = inputs["models"]
    models = {
        model: [
            json.loads(line)
            for line in (args.inputs.parent / path).read_text().splitlines()
        ]
        for model, path in paths.items()
    }
    result = compare(
        models,
        replicates=args.replicates,
        seed=args.seed,
        family_model_count=args.family_model_count or inputs["family_model_count"],
    )
    result["sources"] = paths
    result["provenance"] = inputs["provenance"]
    result["missing_models"] = inputs["missing_models"]
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
