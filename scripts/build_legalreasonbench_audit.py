"""Extract pinned LegalReasonBench inputs or render saved audit reports.

Run from the repository root, outside the untrusted download directory::

    uv run --with pypdf --with fonttools python -I \
        scripts/build_legalreasonbench_audit.py extract \
        --rows /path/to/rows.json --api /path/to/api.json
    uv run python -I scripts/build_legalreasonbench_audit.py render

No model calls, upstream script execution, or citation adjudication occur here.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Isolated Python excludes the script directory; add only this trusted directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from legalreasonbench_extract import AUDIT, REVISION, extract


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser(
        "extract", help="download all attachments and extract selected inputs"
    )
    one.add_argument(
        "--rows",
        type=Path,
        required=True,
        help="Pinned raw rows JSON list or committed source-index.json (uses its rows; "
        "no parquet/pyarrow dependency). Source-index dataset/revision must match.",
    )
    one.add_argument(
        "--api",
        type=Path,
        required=True,
        help="Saved Hugging Face dataset API JSON (sha and cardData.license); "
        "sha must equal the pinned revision. Fetch from "
        "https://huggingface.co/api/datasets/micro1-inc/LegalReasonBench/revision/"
        + REVISION,
    )
    one.add_argument(
        "--upstream",
        type=Path,
        default=Path("tmp/legalreasonbench-audit/upstream"),
        help="Data-only download cache; run outside this directory. "
        "Reuses cached files.",
    )
    one.add_argument(
        "--out",
        type=Path,
        default=AUDIT,
        help="Audit subtree; existing in-scope.json decisions are preserved.",
    )
    two = sub.add_parser(
        "render",
        help="render saved rubric/citation checks, intent and document index; "
        "no model calls",
    )
    two.add_argument("--out", type=Path, default=AUDIT)
    args = parser.parse_args()
    if args.command == "extract":
        print(json.dumps(extract(args.rows, args.api, args.upstream, args.out)))
    else:
        from legalreasonbench_render import render

        render(args.out)


if __name__ == "__main__":
    main()
