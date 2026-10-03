"""Recompute the separate historical appendix without providers or private records.

Usage: uv run python scripts/reproduce_historical_comparison.py INPUT_JSON OUTPUT_JSON
The extract retains original units and nullable outcomes; invalid cases are excluded.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from legalforecast.publication.historical_comparison import reproduce

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_json", type=Path)
    parser.add_argument("output_json", type=Path)
    parser.add_argument(
        "--expected-case-count",
        type=int,
        default=100,
        help="Complete input population case count; use refreshed "
        "results' available_cases for a withdrawn cohort.",
    )
    parser.add_argument(
        "--expected-unit-count",
        type=int,
        default=425,
        help="Complete input population unit count; use refreshed "
        "results' available_units for a withdrawn cohort.",
    )
    args = parser.parse_args()
    reproduce(
        args.input_json,
        args.output_json,
        expected_case_count=args.expected_case_count,
        expected_unit_count=args.expected_unit_count,
    )
