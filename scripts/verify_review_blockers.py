#!/usr/bin/env python3
"""Verify the blocker findings from the 2026-07-03 benchmark design review are fixed.

Companion to the 2026-07-03 benchmark design review (removed from the working
tree; see git history) and the beads tracked under LegalForecastBench-t78
(pre-first-run gate). Run:

    uv run scripts/verify_review_blockers.py

Every check must PASS before the first official benchmark run. Checks are
intentionally heuristic (mostly static scans of the package source): each one
states its *intent*, and if an implementation legitimately chose names the scan
does not match, update the check to match the implementation while preserving
the stated intent — do not delete the check.

Exit code 0 iff all checks pass.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

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
        # This directory also contains cycle-scoped policy manifests, such as
        # provider caps. Only list-shaped files are model registries.
        if not isinstance(entries, list):
            continue
        for index, item in enumerate(cast(list[object], entries)):
            if not isinstance(item, dict):
                problems.append(
                    f"{registry_path.name}: entry {index} is not a model object"
                )
                continue
            entry = cast(dict[str, object], item)
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
    # v2 hardening: the v1 symbol-reference check was satisfied by reading
    # `.__name__` off the audit functions without calling them. Require an
    # actual invocation (name followed by an open paren) outside ensemble.py.
    hits = _files_referencing(
        r"\b(?:audit_ensemble_labels|enforce_label_audit_acceptance)\(",
        frozenset({"legalforecast/labeling/ensemble.py"}),
    )
    return bool(
        hits
    ), f"production call sites: {hits or 'none (name-only refs do not count)'}"


def check_b2_2() -> tuple[bool, str]:
    # v2 hardening: routing that constructs LawyerReviewPacket and then throws
    # it away is not adjudication. Require (a) a durable queue write and (b) a
    # consumer for adjudicated responses (resume path).
    targets = (PACKAGE / "labeling" / "llm_pipeline.py", PACKAGE / "cli.py")
    combined = "\n".join(path.read_text(encoding="utf-8") for path in targets)
    queue = bool(re.search(r"lawyer[_-]review[_-]queue", combined))
    consumer = bool(
        re.search(r"\b(?:AdjudicatedReview|LawyerReviewResponse)\b", combined)
    )
    problems: list[str] = []
    if not queue:
        problems.append("no durable lawyer-review queue write in pipeline/CLI")
    if not consumer:
        problems.append("no consumer for adjudicated responses (resume path missing)")
    return not problems, "; ".join(
        problems
    ) or "queue write and resume consumer present"


def check_b2_3() -> tuple[bool, str]:
    # v2 hardening: the v1 literal-string check was defeated by wrapping the
    # constant in helper functions that ignore their inputs. Use the AST: any
    # function whose name mentions human_verified and whose body is a bare
    # `return False` is a stub; additionally, some code path must be able to
    # produce a True value.
    path = PACKAGE / "labeling" / "llm_pipeline.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    stubs: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        if "human_verified" not in node.name:
            continue
        body = [stmt for stmt in node.body if not isinstance(stmt, ast.Expr)]
        if (
            len(body) == 1
            and isinstance(body[0], ast.Return)
            and isinstance(body[0].value, ast.Constant)
        ):
            stubs.append(f"{node.name} (constant return {body[0].value.value!r})")
    if stubs:
        return False, f"human_verified stub functions detected: {stubs}"
    ok = '"human_verified": False' not in path.read_text(encoding="utf-8")
    return ok, (
        "human_verified is derived, not constant"
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


# --- V2 checks (post-implementation review, 2026-07-03 second pass) ---------
# The first fix round satisfied several v1 checks with changes shaped to the
# grep rather than the intent (stub functions, name-only references). These
# checks are keyed to the FIX-round beads and gated by LegalForecastBench-48k.


def check_v2_1() -> tuple[bool, str]:
    # Scope to the plan-packet-inputs parser: its --model-registry help text
    # currently reads "Optional frozen model registry". The gate is enforced
    # when that argument is required=True or the handler raises when absent.
    text = (PACKAGE / "cli.py").read_text(encoding="utf-8")
    lines = text.splitlines()
    flag_lines = [
        index for index, line in enumerate(lines) if "--model-registry" in line
    ]
    enforced = False
    optional_help = False
    for index in flag_lines:
        window = "\n".join(lines[index : index + 10])
        if "plan-packet-inputs" not in window and "plan_packet" not in window:
            # Identify the plan-packet-inputs flag by its distinctive help text.
            if "When supplied, plan-packet-inputs" not in window:
                continue
        optional_help = "Optional frozen model registry" in window
        if "required=True" in window:
            enforced = True
    if not enforced:
        enforced = bool(
            re.search(
                r"model_registry\s+is\s+None[\s\S]{0,300}?raise"
                r"[\s\S]{0,200}?plan[-_]packet",
                text,
            )
            or re.search(
                r"plan[-_]packet[\s\S]{0,600}?model_registry\s+is\s+None"
                r"[\s\S]{0,200}?raise",
                text,
            )
        )
    ok = enforced and not optional_help
    return ok, (
        "plan-packet-inputs refuses to run without a frozen registry"
        if ok
        else "--model-registry is still optional; eligibility screening is opt-in"
    )


def check_v2_2() -> tuple[bool, str]:
    path = PACKAGE / "evals" / "per_case_runner.py"
    text = path.read_text(encoding="utf-8").lower()
    ok = ("decision" in text) and any(
        marker in text for marker in ("release", "anchor", "eligib")
    )
    return ok, (
        "eval path re-verifies case eligibility against the release anchor"
        if ok
        else "per_case_runner never re-verifies case decision date vs release anchor"
    )


def check_v2_3() -> tuple[bool, str]:
    ledger_text = (PACKAGE / "selection" / "exclusion_ledger.py").read_text(
        encoding="utf-8"
    )
    reason = "release_anchor" in ledger_text.lower()
    return reason, (
        "release-anchor exclusion reason exists in the ledger taxonomy"
        if reason
        else (
            "no release-anchor exclusion reason; out-of-window candidates"
            " still batch-fatal"
        )
    )


def check_v2_4() -> tuple[bool, str]:
    text = (PACKAGE / "publication" / "official_aggregate.py").read_text(
        encoding="utf-8"
    )
    ok = bool(re.search(r"\bpaired_clustered_bootstrap\(", text))
    return ok, (
        "official aggregation computes bootstrap inference for the leaderboard"
        if ok
        else (
            "official_aggregate never calls paired_clustered_bootstrap;"
            " leaderboards ship without CIs"
        )
    )


def check_v2_5() -> tuple[bool, str]:
    # Intent: aggregation fails loud without baselines unless the bypass is an
    # explicit, dispatch-time override. Require both halves: (1) the aggregation
    # library still raises when baselines are missing and allow_no_baselines is
    # not set, and (2) the official workflow exposes the override as a
    # workflow_dispatch INPUT and forwards --allow-no-baselines conditionally on
    # it, rather than hardcoding the flag unconditionally.
    text = (PACKAGE / "publication" / "official_aggregate.py").read_text(
        encoding="utf-8"
    )
    library_guard = bool(
        re.search(r"allow_no_baselines", text)
        and re.search(r"not\s+config\.allow_no_baselines", text)
    )
    workflow = (REPO / ".github" / "workflows" / "run-benchmark.yaml").read_text(
        encoding="utf-8"
    )
    has_input = "allow_no_baselines:" in workflow and (
        "${{ inputs.allow_no_baselines }}" in workflow
    )
    conditional_flag = (
        '[[ "${ALLOW_NO_BASELINES}" == "true" ]]' in workflow
        and "optional_args+=(--allow-no-baselines)" in workflow
    )
    # The old unconditional hardcoded flag must be gone from the aggregate step.
    hardcoded = "\n            --allow-no-baselines \\\n" in workflow
    ok = library_guard and has_input and conditional_flag and not hardcoded
    if ok:
        detail = (
            "aggregation fails loud without baselines unless the allow_no_baselines"
            " workflow input explicitly overrides it"
        )
    else:
        missing: list[str] = []
        if not library_guard:
            missing.append("library allow_no_baselines guard")
        if not has_input:
            missing.append("workflow allow_no_baselines input")
        if not conditional_flag:
            missing.append("conditional --allow-no-baselines forwarding")
        if hardcoded:
            missing.append("hardcoded --allow-no-baselines still present")
        detail = f"baseline override is not a dispatch-time input: {missing}"
    return ok, detail


def check_v2_6() -> tuple[bool, str]:
    tests_text = (TESTS / "test_official_aggregate.py").read_text(encoding="utf-8")
    ok = "subset" in tests_text
    return ok, (
        "registry-coverage subset case is tested"
        if ok
        else (
            "--model-key strict-subset-of-registry still aggregates as"
            " complete (untested)"
        )
    )


def check_v2_7() -> tuple[bool, str]:
    text = (PACKAGE / "evals" / "packet_builder.py").read_text(encoding="utf-8")
    match = re.search(
        r"def _model_visible_unit_record[\s\S]*?\n(?=\ndef |\nclass |\Z)", text
    )
    body = match.group(0) if match else ""
    leaks = [
        field for field in ("challenge_scope", "challenged_by_motion") if field in body
    ]
    return not leaks, (
        f"model-visible packet record still serializes: {leaks}"
        if leaks
        else "model-visible packet record omits challenge scope fields"
    )


def check_v2_8() -> tuple[bool, str]:
    problems: list[str] = []
    for registry_path in sorted((REPO / "model_registries").glob("*.json")):
        entries = json.loads(registry_path.read_text(encoding="utf-8"))
        if not isinstance(entries, list):
            continue
        for index, item in enumerate(cast(list[object], entries)):
            if not isinstance(item, dict):
                problems.append(f"{registry_path.name}: malformed entry {index}")
                continue
            entry = cast(dict[str, object], item)
            if entry.get("release_timestamp") is None:
                continue
            if not str(entry.get("release_timestamp_source") or "").strip():
                key = f"{entry.get('provider')}:{entry.get('model_id')}"
                problems.append(f"{registry_path.name}: {key}")
    return not problems, (
        "every release_timestamp carries a source citation"
        if not problems
        else f"release timestamps without source citations: {problems}"
    )


def check_v2_9() -> tuple[bool, str]:
    text = (PACKAGE / "labeling" / "llm_pipeline.py").read_text(encoding="utf-8")
    ok = "requires_frozen_unit_workflow" in text
    return ok, (
        "missing-unit flags gate the pipeline"
        if ok
        else "requires_frozen_unit_workflow is still ignored by the labeling pipeline"
    )


def check_v2_10() -> tuple[bool, str]:
    builder_path = PACKAGE / "cli.py"
    builder_text = builder_path.read_text(encoding="utf-8")
    builder_wired = all(
        needle in builder_text
        for needle in (
            "def _cmd_acquisition_build_packets",
            "assembly.model_packet.to_record()",
        )
    )

    fixture_root = TESTS / "fixtures" / "packet_render_ci"
    expected_packets_path = fixture_root / "expected-packets.jsonl"
    expected_manifest_path = fixture_root / "expected-packet-render.json"
    golden_valid = False
    golden_detail = "missing or malformed packet-render golden"
    try:
        manifest = json.loads(expected_manifest_path.read_text(encoding="utf-8"))
        candidates = manifest["candidates"]
        expected_sha256 = candidates[0]["packet_render"]["packet_sha256"]
        actual_sha256 = hashlib.sha256(expected_packets_path.read_bytes()).hexdigest()
        golden_valid = (
            isinstance(expected_sha256, str)
            and re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is not None
            and expected_sha256 == actual_sha256
        )
        golden_detail = (
            f"reviewed golden sha256={expected_sha256}"
            if golden_valid
            else "expected-packets.jsonl does not match expected-packet-render.json"
        )
    except (IndexError, KeyError, OSError, TypeError, json.JSONDecodeError):
        pass

    workflow_hits: list[str] = []
    for path in sorted((REPO / ".github" / "workflows").glob("*.y*ml")):
        text = path.read_text(encoding="utf-8")
        workflow_step_pattern = (
            r"- name: Rebuild and verify packet renders\n"
            r"(?P<body>.*?)(?=\n\s+- name:|\Z)"
        )
        match = re.search(
            workflow_step_pattern,
            text,
            flags=re.DOTALL,
        )
        if match is None:
            continue
        body = match.group("body")
        if (
            "uv run pytest -q" in body
            and (
                "tests/test_packet_render_ci_workflow.py::"
                "test_production_packet_builder_matches_reviewed_golden"
            )
            in body
            and "uv run legalforecast acquisition build-packets" not in body
            and "private_store_export.py" not in body
        ):
            workflow_hits.append(path.name)

    wired = builder_wired and golden_valid and bool(workflow_hits)
    return wired, (
        "production acquisition builder, independent reviewed golden, and "
        f"focused golden workflow are wired; {golden_detail}; workflows={workflow_hits}"
        if wired
        else (
            "packet-render verification requires the production acquisition builder, "
            "an independently frozen matching golden, and a focused golden workflow; "
            f"builder={builder_wired}, golden={golden_detail}, "
            f"workflows={workflow_hits or 'none'}"
        )
    )


def check_v2_11() -> tuple[bool, str]:
    combined = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(TESTS.glob("*.py"))
    )
    names = ("latest_release_timestamp", "require_official_registry_entries")
    missing = [name for name in names if name not in combined]
    return not missing, (
        "release-anchor gate functions have direct tests"
        if not missing
        else f"untested anchor-gate functions: {missing}"
    )


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
    Check(
        "V2-1",
        "LegalForecastBench-c57",
        "plan-packet-inputs cannot run without a frozen model registry",
        check_v2_1,
    ),
    Check(
        "V2-2",
        "LegalForecastBench-c57",
        "eval path re-verifies per-case eligibility against the release anchor",
        check_v2_2,
    ),
    Check(
        "V2-3",
        "LegalForecastBench-av2",
        "anchor-window exclusions produce ledger entries instead of batch aborts",
        check_v2_3,
    ),
    Check(
        "V2-4",
        "LegalForecastBench-csu",
        "official aggregation wires bootstrap inference into the leaderboard",
        check_v2_4,
    ),
    Check(
        "V2-5",
        "LegalForecastBench-wie",
        "aggregation without baselines fails loud unless explicitly overridden",
        check_v2_5,
    ),
    Check(
        "V2-6",
        "LegalForecastBench-30l",
        "--model-key strict subset of the registry is rejected (tested)",
        check_v2_6,
    ),
    Check(
        "V2-7",
        "LegalForecastBench-1vl",
        "model-visible packet record omits challenge_scope/challenged_by_motion",
        check_v2_7,
    ),
    Check(
        "V2-8",
        "LegalForecastBench-550",
        "every non-null release_timestamp carries a source citation field",
        check_v2_8,
    ),
    Check(
        "V2-9",
        "LegalForecastBench-t62",
        "Stage B missing-unit flags gate the labeling pipeline",
        check_v2_9,
    ),
    Check(
        "V2-10",
        "LegalForecastBench-89o",
        "CI compares a production packet rebuild with independent reviewed goldens",
        check_v2_10,
    ),
    Check(
        "V2-11",
        "LegalForecastBench-614",
        "release-anchor gate functions have direct unit tests",
        check_v2_11,
    ),
)


def main() -> int:
    failures = 0
    print("Blocker verification — 2026-07-03 benchmark design review (see git history)")
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
