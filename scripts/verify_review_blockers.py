#!/usr/bin/env python3
"""Verify the blocker findings from the 2026-07-03 benchmark design review are fixed.

Companion to docs/reviews/benchmark-design-review-2026-07-03.md and the beads
tracked under LegalForecastBench-t78 (pre-first-run gate). Run:

    uv run scripts/verify_review_blockers.py

Every check must PASS before the first official benchmark run. Checks are
intentionally heuristic (mostly static scans of the package source): each one
states its *intent*, and if an implementation legitimately chose names the scan
does not match, update the check to match the implementation while preserving
the stated intent — do not delete the check.

Exit code 0 iff all checks pass.
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PACKAGE = REPO / "legalforecast"
TESTS = REPO / "tests"


def _package_files(exclude_relative: frozenset[str] = frozenset()) -> Iterable[Path]:
    """Yield package source files, excluding __init__ re-exports and given modules."""
    for path in sorted(PACKAGE.rglob("*.py")):
        relative = path.relative_to(REPO).as_posix()
        if path.name == "__init__.py":
            continue
        if relative in exclude_relative:
            continue
        yield path


def _files_referencing(
    pattern: str, exclude_relative: frozenset[str] = frozenset()
) -> list[str]:
    regex = re.compile(pattern)
    hits: list[str] = []
    for path in _package_files(exclude_relative):
        if regex.search(path.read_text(encoding="utf-8")):
            hits.append(path.relative_to(REPO).as_posix())
    return hits


def _window_hit(path: Path, anchor: str, needle: str, radius: int = 3) -> bool:
    """True if `needle` appears within `radius` lines of a line containing `anchor`."""
    lines = path.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if anchor not in line:
            continue
        window = lines[max(0, index - radius) : index + radius + 1]
        if any(needle in candidate for candidate in window):
            return True
    return False


def check_b1_1() -> tuple[bool, str]:
    hits = _files_referencing(
        r"\bdetect_outcome_leakage\b",
        frozenset({"legalforecast/selection/contamination_filters.py"}),
    )
    return bool(hits), f"production references: {hits or 'none'}"


def check_b1_2() -> tuple[bool, str]:
    hits = _files_referencing(
        r"\bscreen_courtlistener_docket_for_mtd_decision\b",
        frozenset({"legalforecast/ingestion/mtd_acquisition_screen.py"}),
    )
    return bool(hits), f"production references: {hits or 'none'}"


def check_b1_3() -> tuple[bool, str]:
    # Loose ExclusionLedgerEntry references exist in other unwired library
    # modules (protocol/manifest.py, motion_linkage.py, adjudication.py), so
    # require either the leakage constructor specifically, or ledger use from
    # the wired acquisition/packet path (cli.py or ingestion/).
    constructor_hits = _files_referencing(
        r"\bfrom_outcome_leakage\b",
        frozenset({"legalforecast/selection/exclusion_ledger.py"}),
    )
    wired_path_hits = [
        path.relative_to(REPO).as_posix()
        for path in (PACKAGE / "cli.py", *sorted((PACKAGE / "ingestion").glob("*.py")))
        if "ExclusionLedgerEntry" in path.read_text(encoding="utf-8")
    ]
    hits = constructor_hits + wired_path_hits
    return bool(hits), f"leakage ledgering from wired path: {hits or 'none'}"


def check_b1_4() -> tuple[bool, str]:
    hits = _files_referencing(r"latest_release|max\([^)\n]*release_timestamp")
    return bool(hits), f"anchor computation found in: {hits or 'none'}"


def check_b1_5() -> tuple[bool, str]:
    problems: list[str] = []
    registry_dir = REPO / "model_registries"
    for registry_path in sorted(registry_dir.glob("*.json")):
        entries = json.loads(registry_path.read_text(encoding="utf-8"))
        for entry in entries:
            if entry.get("release_timestamp") is None:
                model = f"{entry.get('provider')}:{entry.get('model_id')}"
                problems.append(
                    f"{registry_path.name}: {model} has null release_timestamp"
                )
    return not problems, "; ".join(
        problems
    ) or "all registry entries have release timestamps"


def check_b1_6() -> tuple[bool, str]:
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    ok = "no chance" not in readme.lower()
    return ok, "README no longer claims absolute contamination immunity" if ok else (
        "README.md still contains the absolute 'no chance' contamination claim"
    )


def check_b2_1() -> tuple[bool, str]:
    hits = _files_referencing(
        r"\baudit_ensemble_labels\b|\benforce_label_audit_acceptance\b",
        frozenset({"legalforecast/labeling/ensemble.py"}),
    )
    return bool(hits), f"production references: {hits or 'none'}"


def check_b2_2() -> tuple[bool, str]:
    targets = (
        PACKAGE / "labeling" / "llm_pipeline.py",
        PACKAGE / "cli.py",
    )
    hits = [
        path.relative_to(REPO).as_posix()
        for path in targets
        if re.search(
            r"\bLAWYER_ADJUDICATION\b|\bLawyerReviewPacket\b",
            path.read_text(encoding="utf-8"),
        )
    ]
    return bool(hits), f"adjudication routing referenced in: {hits or 'none'}"


def check_b2_3() -> tuple[bool, str]:
    text = (PACKAGE / "labeling" / "llm_pipeline.py").read_text(encoding="utf-8")
    ok = '"human_verified": False' not in text
    return ok, (
        "human_verified is no longer hardcoded False"
        if ok
        else 'llm_pipeline.py still hardcodes "human_verified": False'
    )


def check_b2_4() -> tuple[bool, str]:
    hits = [
        path.relative_to(REPO).as_posix()
        for path in sorted((PACKAGE / "labeling").glob("*.py"))
        if "ExclusionLedgerEntry" in path.read_text(encoding="utf-8")
        or "exclusion_ledger" in path.read_text(encoding="utf-8")
    ]
    return bool(hits), f"labeling-path exclusion ledgering in: {hits or 'none'}"


def check_b2_5() -> tuple[bool, str]:
    targets = (
        PACKAGE / "labeling" / "label_outcomes.py",
        PACKAGE / "unitization" / "schemas.py",
    )
    hits = [
        path.relative_to(REPO).as_posix()
        for path in targets
        if "not_addressed" in path.read_text(encoding="utf-8").lower()
    ]
    return bool(
        hits
    ), f"'not addressed by this disposition' resolution in: {hits or 'none'}"


def check_b2_6() -> tuple[bool, str]:
    path = PACKAGE / "labeling" / "llm_pipeline.py"
    lenient_challenged = _window_hit(path, "challenged_by_motion", "default=True")
    lenient_scope = _window_hit(path, "challenge_scope", "ENTIRE_CLAIM")
    problems: list[str] = []
    if lenient_challenged:
        problems.append("challenged_by_motion still defaults True on missing output")
    if lenient_scope:
        problems.append(
            "challenge_scope still defaults to ENTIRE_CLAIM on missing output"
        )
    return not problems, "; ".join(problems) or "unitization parsing fails closed"


def check_b3_1() -> tuple[bool, str]:
    path = PACKAGE / "ingestion" / "packet_input_planner.py"
    ok = _window_hit(path, "decision_entry_numbers", "raise", radius=6)
    return ok, (
        "missing decision_entry_numbers raises"
        if ok
        else (
            "packet_input_planner.py still fails open on missing decision_entry_numbers"
        )
    )


def check_b3_2() -> tuple[bool, str]:
    targets = (
        PACKAGE / "ingestion" / "packet_input_planner.py",
        PACKAGE / "ingestion" / "docket_markdown.py",
        PACKAGE / "ingestion" / "model_packet_assembly.py",
    )
    hits = [
        path.relative_to(REPO).as_posix()
        for path in targets
        if re.search(r"leakage", path.read_text(encoding="utf-8"), re.IGNORECASE)
    ]
    return bool(hits), f"packet-time leakage screening in: {hits or 'none'}"


def check_b3_3() -> tuple[bool, str]:
    markers = (
        "minute order",
        "minute_order",
        "report and recommendation",
        "report_and_recommendation",
        "tentative ruling",
        "tentative_ruling",
    )
    hits: list[str] = []
    for path in sorted(TESTS.rglob("*.py")):
        text = path.read_text(encoding="utf-8").lower()
        if "model_visible" in text and any(marker in text for marker in markers):
            hits.append(path.relative_to(REPO).as_posix())
    return bool(hits), f"adversarial leakage fixtures in: {hits or 'none'}"


@dataclass(frozen=True, slots=True)
class Check:
    check_id: str
    bead: str
    intent: str
    run: Callable[[], tuple[bool, str]]


CHECKS: tuple[Check, ...] = (
    Check(
        "B1-1",
        "LegalForecastBench-66z",
        "detect_outcome_leakage is invoked from a production path, not only tests",
        check_b1_1,
    ),
    Check(
        "B1-2",
        "LegalForecastBench-66z",
        "the MTD acquisition decision-date screen is invoked from a production path",
        check_b1_2,
    ),
    Check(
        "B1-3",
        "LegalForecastBench-66z",
        "exclusion-ledger entries are written from a production path",
        check_b1_3,
    ),
    Check(
        "B1-4",
        "LegalForecastBench-3i6",
        "the run's release anchor is computed in code from registry release timestamps",
        check_b1_4,
    ),
    Check(
        "B1-5",
        "LegalForecastBench-3i6",
        "no checked-in model registry entry has a null release_timestamp",
        check_b1_5,
    ),
    Check(
        "B1-6",
        "LegalForecastBench-e2u",
        "README states the contamination guarantee conditionally, not absolutely",
        check_b1_6,
    ),
    Check(
        "B2-1",
        "LegalForecastBench-u5g",
        "the unanimous-label human audit / acceptance gate is invoked in production",
        check_b2_1,
    ),
    Check(
        "B2-2",
        "LegalForecastBench-u5g",
        "lawyer-adjudication routing is reachable from the labeling pipeline or CLI",
        check_b2_2,
    ),
    Check(
        "B2-3",
        "LegalForecastBench-u5g",
        "labeling output no longer hardcodes human_verified: False",
        check_b2_3,
    ),
    Check(
        "B2-4",
        "LegalForecastBench-mm0",
        "labeling/unitization case drops are recorded through the exclusion ledger",
        check_b2_4,
    ),
    Check(
        "B2-5",
        "LegalForecastBench-mm0",
        "judges can return 'not addressed by this disposition' instead of guessing",
        check_b2_5,
    ),
    Check(
        "B2-6",
        "LegalForecastBench-utk",
        "unitization parsing fails closed on missing fields (no lenient defaults)",
        check_b2_6,
    ),
    Check(
        "B3-1",
        "LegalForecastBench-9v8",
        "packet planning raises on missing/empty decision_entry_numbers",
        check_b3_1,
    ),
    Check(
        "B3-2",
        "LegalForecastBench-9v8",
        "pre-decision docket entries are screened for outcome leakage at packet time",
        check_b3_2,
    ),
    Check(
        "B3-3",
        "LegalForecastBench-9v8",
        "adversarial leakage fixtures (minute order / R&R / tentative) exist",
        check_b3_3,
    ),
)


def main() -> int:
    failures = 0
    print("Blocker verification — docs/reviews/benchmark-design-review-2026-07-03.md")
    print(f"Gate bead: LegalForecastBench-t78\n{'-' * 88}")
    for check in CHECKS:
        ok, detail = check.run()
        status = "PASS" if ok else "FAIL"
        if not ok:
            failures += 1
        print(f"[{status}] {check.check_id} ({check.bead}): {check.intent}")
        print(f"       {detail}")
    print("-" * 88)
    if failures:
        print(f"{failures}/{len(CHECKS)} checks FAILED — blockers are not all fixed.")
        return 1
    print(f"All {len(CHECKS)} blocker checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
