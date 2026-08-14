"""Lint fence: acquisition/selection knobs belong in legalforecast.config.

New module-level constants that look like acquisition/selection knobs, and
construction of the blessed config types, are forbidden outside this package.
Cycle 1 live modules keep their existing constants via the reviewed baseline
allowlist, which may only shrink.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
import tokenize
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final, cast

ALLOW_MARKER: Final[str] = "acquisition-config-fence: allow"
BASELINE_PATH: Final[Path] = Path("legalforecast/config/fence_baseline.json")
SCANNED_ROOTS: Final[tuple[str, ...]] = ("legalforecast", "scripts")
EXCLUDED_DIR_PARTS: Final[frozenset[str]] = frozenset({"__pycache__", "tmp"})
KNOB_ASSIGNMENT: Final[re.Pattern[str]] = re.compile(
    r"(?i)("
    r"PURCHASE_COST|"
    r"MAX_PROJECTED_BUDGET|"
    r"PER_DOCUMENT|"
    r"PRICE_CAP|"
    r"SPEND_CEILING|"
    r"HARD_CAP|"
    r"SELECTOR_MODEL|"
    r"FREE_FIRST|"
    r"DOCUMENT_NEED|"
    r"RANKING_POLICY|"
    r"RANKING_TIEBREAK|"
    r"TYPED_CONFIRMATION|"
    r"QUEUE_LAG|"
    r"POLL_ATTEMPTS|"
    r"POLL_BACKOFF|"
    r"EVALUATION_REGISTRY|"
    r"CYCLE_ACQUISITION_CONFIG"
    r")"
)
CONFIG_TYPE_NAMES: Final[frozenset[str]] = frozenset(
    {
        "CohortPolicyPin",
        "CycleConfig",
        "DocumentNeedBucketDefinitions",
        "EvaluationRegistryPin",
        "FreeFirstPolicy",
        "PerDocumentPriceCap",
        "RankingSortKey",
        "RankingTiebreakPolicy",
        "RetryQueueLagTolerances",
        "SelectorModel",
        "SelectorModelPolicy",
        "SpendCeiling",
        "StratificationPolicy",
        "TypedConfirmationParams",
    }
)


@dataclass(frozen=True, slots=True)
class Finding:
    """One fence violation candidate."""

    rule: str
    path: str
    subject: str
    line: int
    detail: str
    guidance: str


@dataclass(frozen=True, slots=True)
class BaselineEntry:
    """A reviewed exception for one historical finding."""

    rule: str
    path: str
    subject: str
    reason: str


def scan_repository(root: Path) -> tuple[Finding, ...]:
    """Scan Python sources for out-of-home acquisition/selection knobs."""

    findings: list[Finding] = []
    for relative in _iter_python_paths(root):
        findings.extend(_scan_file(root / relative, relative))
    return tuple(findings)


def load_baseline(path: Path) -> tuple[BaselineEntry, ...]:
    """Load the reviewed allowlist."""

    raw_payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw_payload, list):
        raise ValueError("acquisition-config fence baseline must be a JSON array")
    payload = cast(list[object], raw_payload)
    entries: list[BaselineEntry] = []
    seen: set[tuple[str, str, str]] = set()
    for index, raw_row in enumerate(payload):
        if not isinstance(raw_row, dict):
            raise ValueError(f"baseline entry {index} must be an object")
        row = cast(dict[str, object], raw_row)
        rule = _required_baseline_str(row, index, "rule")
        path_value = _required_baseline_str(row, index, "path")
        subject = _required_baseline_str(row, index, "subject")
        reason = _required_baseline_str(row, index, "reason")
        key = (rule, path_value, subject)
        if key in seen:
            raise ValueError(f"duplicate baseline entry: {key}")
        if not reason.strip():
            raise ValueError(f"baseline entry {index} needs a one-line reason")
        seen.add(key)
        entries.append(
            BaselineEntry(
                rule=rule,
                path=path_value,
                subject=subject,
                reason=reason.strip(),
            )
        )
    return tuple(entries)


def find_new_violations(
    findings: Sequence[Finding], baseline: Sequence[BaselineEntry]
) -> tuple[Finding, ...]:
    """Return findings not covered by the reviewed baseline."""

    allowed = {(entry.rule, entry.path, entry.subject) for entry in baseline}
    return tuple(
        finding
        for finding in findings
        if (finding.rule, finding.path, finding.subject) not in allowed
    )


def build_baseline(findings: Sequence[Finding]) -> tuple[BaselineEntry, ...]:
    """Turn a raw scan into a reviewed-looking baseline skeleton."""

    return tuple(
        BaselineEntry(
            rule=finding.rule,
            path=finding.path,
            subject=finding.subject,
            reason=(
                "Cycle 1 live constant; leave in place until post-Cycle-1 supersession"
            ),
        )
        for finding in findings
    )


def write_baseline(path: Path, findings: Sequence[Finding]) -> None:
    """Write a normalized baseline file."""

    payload = [asdict(entry) for entry in build_baseline(findings)]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Fail when new acquisition/selection constants or CycleConfig "
            "construction appear outside legalforecast.config."
        )
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--baseline",
        type=Path,
        default=BASELINE_PATH,
        help="Path to the reviewed fence baseline JSON file.",
    )
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="Rewrite the baseline from the current findings instead of checking it.",
    )
    args = parser.parse_args(argv)

    root = args.root.resolve()
    baseline_path = args.baseline
    if not baseline_path.is_absolute():
        baseline_path = root / baseline_path
    findings = scan_repository(root)
    if args.write_baseline:
        write_baseline(baseline_path, findings)
        print(f"Wrote {len(findings)} baseline entries to {baseline_path}")
        return 0
    baseline = load_baseline(baseline_path) if baseline_path.is_file() else ()
    violations = find_new_violations(findings, baseline)
    if not violations:
        return 0
    for finding in violations:
        print(
            f"{finding.path}:{finding.line}: {finding.rule}: {finding.subject}",
            file=sys.stderr,
        )
        print(f"  {finding.detail}", file=sys.stderr)
        print(f"  {finding.guidance}", file=sys.stderr)
    print(
        "\nPut new acquisition/selection knobs in legalforecast.config. "
        "If a finding is a reviewed Cycle 1 holdover, add a baseline entry "
        "with a one-line reason; the allowlist may only shrink.",
        file=sys.stderr,
    )
    return 1


def _iter_python_paths(root: Path) -> Iterable[str]:
    for base in SCANNED_ROOTS:
        base_path = root / base
        if not base_path.exists():
            continue
        for path in sorted(base_path.rglob("*.py")):
            relative = path.relative_to(root).as_posix()
            if any(part in EXCLUDED_DIR_PARTS for part in Path(relative).parts):
                continue
            if "legalforecast/config" in relative:
                continue
            yield relative


def _scan_file(path: Path, relative: str) -> tuple[Finding, ...]:
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=relative)
    except SyntaxError:
        return ()
    allowed_lines = _allowed_lines(path)
    findings: list[Finding] = []
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            findings.extend(_assignment_findings(node, relative, source, allowed_lines))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            finding = _type_call_finding(node, relative, source, allowed_lines)
            if finding is not None:
                findings.append(finding)
    return tuple(findings)


def _assignment_findings(
    node: ast.Assign | ast.AnnAssign,
    relative: str,
    source: str,
    allowed_lines: set[int],
) -> tuple[Finding, ...]:
    if node.lineno in allowed_lines:
        return ()
    names = _assigned_names(node)
    findings: list[Finding] = []
    for name in names:
        if KNOB_ASSIGNMENT.search(name) is None:
            continue
        findings.append(
            Finding(
                rule="acquisition_selection_constant",
                path=relative,
                subject=name,
                line=node.lineno,
                detail=_source_segment(source, node),
                guidance=(
                    "Define new acquisition/selection knobs in "
                    "legalforecast.config, or keep this Cycle 1 constant and "
                    "add a reviewed fence_baseline.json entry."
                ),
            )
        )
    return tuple(findings)


def _type_call_finding(
    node: ast.Call,
    relative: str,
    source: str,
    allowed_lines: set[int],
) -> Finding | None:
    if node.lineno in allowed_lines:
        return None
    called = _called_name(node.func)
    if called not in CONFIG_TYPE_NAMES:
        return None
    return Finding(
        rule="cycle_config_type_construction",
        path=relative,
        subject=called,
        line=node.lineno,
        detail=_source_segment(source, node),
        guidance=(
            "Construct CycleConfig and its knob types only inside "
            "legalforecast.config (or in tests)."
        ),
    )


def _assigned_names(node: ast.Assign | ast.AnnAssign) -> tuple[str, ...]:
    targets: list[ast.AST] = []
    if isinstance(node, ast.Assign):
        targets.extend(node.targets)
    else:
        targets.append(node.target)
    names: list[str] = []
    for target in targets:
        names.extend(_names_from_target(target))
    return tuple(names)


def _names_from_target(node: ast.AST) -> tuple[str, ...]:
    if isinstance(node, ast.Name):
        return (node.id,)
    if isinstance(node, (ast.Tuple, ast.List)):
        names: list[str] = []
        for element in node.elts:
            names.extend(_names_from_target(element))
        return tuple(names)
    return ()


def _called_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _allowed_lines(path: Path) -> set[int]:
    allowed: set[int] = set()
    with path.open("rb") as handle:
        for token in tokenize.tokenize(handle.readline):
            if token.type == tokenize.COMMENT and ALLOW_MARKER in token.string:
                allowed.add(token.start[0])
                allowed.add(token.start[0] + 1)
    return allowed


def _source_segment(source: str, node: ast.AST) -> str:
    segment = ast.get_source_segment(source, node)
    if segment is None:
        return ""
    return " ".join(segment.split())


def _required_baseline_str(
    row: Mapping[str, object], index: int, field_name: str
) -> str:
    value = row.get(field_name)
    if not isinstance(value, str):
        raise ValueError(f"fence baseline entry {index} has invalid {field_name}")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
