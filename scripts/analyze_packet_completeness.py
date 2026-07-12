"""Compare legacy and approved packet-completeness yields offline."""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from legalforecast.ingestion.public_packet_planner import plan_public_packet_downloads


def analyze_packet_completeness(
    records: Iterable[Mapping[str, Any]],
) -> dict[str, object]:
    """Compute both definitions from one immutable planner-input record set."""

    frozen = tuple(records)
    approved = plan_public_packet_downloads(
        frozen,
        target_clean_cases=max(1, len(frozen)),
        use_embedded_entries=True,
    )
    return {
        "schema_version": "legalforecast.packet_completeness_comparison.v1",
        "input_candidate_count": len(frozen),
        "legacy_optional_opposition_bare_notice_yield": sum(
            _legacy_complete(record) for record in frozen
        ),
        "approved_conditional_opposition_memorandum_yield": len(
            approved.selected_cases
        ),
    }


def _legacy_complete(record: Mapping[str, Any]) -> bool:
    ai = record.get("ai")
    entries = record.get("selected_entries")
    if not isinstance(ai, Mapping) or not isinstance(entries, Sequence):
        return False
    typed_ai = cast(Mapping[str, object], ai)
    targets = {
        str(value)
        for value in cast(
            Sequence[object], typed_ai.get("target_motion_entry_numbers", ())
        )
    }
    decisions = {
        str(value)
        for value in cast(Sequence[object], typed_ai.get("decision_entry_numbers", ()))
    }
    complaint = target = decision = False
    for raw in cast(Sequence[object], entries):
        if not isinstance(raw, Mapping):
            continue
        entry = cast(Mapping[str, object], raw)
        number = str(entry.get("entry_number", ""))
        text = str(entry.get("text", "")).casefold()
        free = any(
            isinstance(document, Mapping)
            and not cast(Mapping[str, object], document).get("pacer_only", False)
            and bool(cast(Mapping[str, object], document).get("href"))
            for document in cast(Sequence[object], entry.get("documents", ()))
        )
        complaint |= (
            free and bool(re.search(r"\bcomplaint\b", text)) and number not in targets
        )
        target |= free and number in targets
        decision |= free and number in decisions
    return complaint and target and decision


def main() -> int:
    """Run the comparison without network or provider credentials."""

    parser = argparse.ArgumentParser()
    parser.add_argument("snapshot", type=Path)
    args = parser.parse_args()
    input_path = args.snapshot
    if input_path.is_dir():
        input_path = input_path / "screened-cases.jsonl"
    records = tuple(
        json.loads(line)
        for line in input_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    print(json.dumps(analyze_packet_completeness(records), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
