"""Repository architecture and CLI-sprawl ratchets.

This module deliberately measures structure rather than behavior.  It is the
small, pytest-authoritative fence that keeps the CLI monolith from growing
while the later, behavior-preserving extraction work is staged.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final, cast

BASELINE_PATH: Final[Path] = Path("legalforecast/testing/architecture_baseline.json")
CLI_PATH: Final[str] = "legalforecast/cli.py"
UPWARD_IMPORT_ALLOWLIST: Final[frozenset[str]] = frozenset(
    {
        "legalforecast/ingestion/purchase_approval.py",
        "legalforecast/ingestion/recovered_public_replay.py",
        "legalforecast/ingestion/resolved_post_recovery.py",
    }
)


@dataclass(frozen=True, slots=True)
class CliMetrics:
    """Monotonic measurements for the current CLI composition root."""

    line_count: int
    nonblank_line_count: int
    top_level_definition_count: int
    top_level_class_count: int
    parser_line_count: int
    command_handler_count: int
    command_handler_lines: int
    verifier_family_count: int
    verifier_family_lines: int


@dataclass(frozen=True, slots=True)
class CompatibilityInventory:
    """Reviewed test coupling that must shrink, never grow accidentally."""

    cli_import_files: tuple[str, ...]
    private_cli_files: tuple[str, ...]
    private_cli_targets: tuple[str, ...]
    monkeypatch_targets: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ArchitectureSnapshot:
    """All structure and coupling facts checked by the ratchet."""

    cli_metrics: CliMetrics
    upward_cli_dependencies: tuple[str, ...]
    compatibility: CompatibilityInventory


def scan_repository(root: Path) -> ArchitectureSnapshot:
    """Measure CLI structure, upward dependencies, and test coupling."""

    resolved_root = root.resolve()
    cli_path = resolved_root / CLI_PATH
    source = cli_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=CLI_PATH)
    definitions = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]
    functions = [
        node
        for node in definitions
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    command_handlers = [node for node in functions if node.name.startswith("_cmd_")]
    verifier_family = [
        node
        for node in functions
        if node.name.startswith(("_verify_", "_validate_", "_require_", "_guard_"))
    ]
    parser = next(node for node in functions if node.name == "build_parser")
    metrics = CliMetrics(
        line_count=len(source.splitlines()),
        nonblank_line_count=sum(bool(line.strip()) for line in source.splitlines()),
        top_level_definition_count=len(definitions),
        top_level_class_count=sum(
            isinstance(node, ast.ClassDef) for node in definitions
        ),
        parser_line_count=_line_count(parser),
        command_handler_count=len(command_handlers),
        command_handler_lines=sum(_line_count(node) for node in command_handlers),
        verifier_family_count=len(verifier_family),
        verifier_family_lines=sum(_line_count(node) for node in verifier_family),
    )
    upward = tuple(
        sorted(
            path
            for path in _python_paths(resolved_root / "legalforecast")
            if path != CLI_PATH and _imports_cli(resolved_root / path)
        )
    )
    return ArchitectureSnapshot(
        cli_metrics=metrics,
        upward_cli_dependencies=upward,
        compatibility=_scan_test_compatibility(resolved_root),
    )


def check_baseline(root: Path, baseline_path: Path = BASELINE_PATH) -> tuple[str, ...]:
    """Return reviewed architecture-ratchet violations, if any."""

    resolved_root = root.resolve()
    baseline = load_baseline(
        baseline_path if baseline_path.is_absolute() else resolved_root / baseline_path
    )
    current = scan_repository(resolved_root)
    violations: list[str] = []
    baseline_metrics = baseline.cli_metrics
    for field in (
        "line_count",
        "nonblank_line_count",
        "top_level_definition_count",
        "top_level_class_count",
        "parser_line_count",
        "command_handler_count",
        "command_handler_lines",
        "verifier_family_count",
        "verifier_family_lines",
    ):
        observed = getattr(current.cli_metrics, field)
        allowed = getattr(baseline_metrics, field)
        if observed > allowed:
            violations.append(f"cli_metrics.{field}: {observed} > reviewed {allowed}")

    unexpected_upward = sorted(
        set(current.upward_cli_dependencies) - set(baseline.upward_cli_dependencies)
    )
    if unexpected_upward:
        violations.append(
            "new upward CLI dependencies: " + ", ".join(unexpected_upward)
        )
    unexpected_allowlist = sorted(
        set(current.upward_cli_dependencies) - UPWARD_IMPORT_ALLOWLIST
    )
    if unexpected_allowlist:
        violations.append(
            "upward CLI dependency outside the three migration exceptions: "
            + ", ".join(unexpected_allowlist)
        )

    current_compat = current.compatibility
    baseline_compat = baseline.compatibility
    for field in (
        "cli_import_files",
        "private_cli_files",
        "private_cli_targets",
        "monkeypatch_targets",
    ):
        observed = set(getattr(current_compat, field))
        allowed = set(getattr(baseline_compat, field))
        additions = sorted(observed - allowed)
        if additions:
            violations.append(f"new compatibility.{field}: {', '.join(additions)}")
    return tuple(violations)


def load_baseline(path: Path) -> ArchitectureSnapshot:
    """Load and validate a checked-in architecture snapshot."""

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("architecture baseline must be a JSON object")
    payload = cast(dict[str, object], raw)
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported architecture baseline schema")
    metrics = _dataclass_from_mapping(CliMetrics, payload, "cli_metrics")
    compatibility = _dataclass_from_mapping(
        CompatibilityInventory, payload, "compatibility"
    )
    upward = _string_tuple(payload, "upward_cli_dependencies")
    return ArchitectureSnapshot(
        cli_metrics=metrics,
        upward_cli_dependencies=upward,
        compatibility=compatibility,
    )


def write_baseline(path: Path, snapshot: ArchitectureSnapshot) -> None:
    """Write a normalized reviewed snapshot."""

    payload = {
        "schema_version": 1,
        "cli_metrics": asdict(snapshot.cli_metrics),
        "upward_cli_dependencies": list(snapshot.upward_cli_dependencies),
        "compatibility": asdict(snapshot.compatibility),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the architecture ratchet from a shell or CI."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--baseline", type=Path, default=BASELINE_PATH)
    parser.add_argument("--write-baseline", action="store_true")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    baseline = args.baseline if args.baseline.is_absolute() else root / args.baseline
    snapshot = scan_repository(root)
    if args.write_baseline:
        write_baseline(baseline, snapshot)
        print(f"wrote architecture baseline to {baseline}")
        return 0
    violations = check_baseline(root, baseline)
    if violations:
        print("architecture ratchet found new violations:", file=sys.stderr)
        for violation in violations:
            print(f"- {violation}", file=sys.stderr)
        return 1
    print(f"architecture ratchet passed: {baseline.relative_to(root)}")
    return 0


def _scan_test_compatibility(root: Path) -> CompatibilityInventory:
    cli_import_files: set[str] = set()
    private_files: set[str] = set()
    private_targets: set[str] = set()
    monkeypatch_targets: set[str] = set()
    for path in sorted((root / "tests").rglob("*.py")):
        relative = path.relative_to(root).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        except SyntaxError:
            continue
        aliases: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "legalforecast.cli":
                        aliases.add(alias.asname or "cli")
                        cli_import_files.add(relative)
            elif (
                isinstance(node, ast.ImportFrom) and node.module == "legalforecast.cli"
            ):
                cli_import_files.add(relative)
                for alias in node.names:
                    if alias.name.startswith("_"):
                        private_files.add(relative)
                        private_targets.add(f"legalforecast.cli.{alias.name}")
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                if node.value.id in aliases and node.attr.startswith("_"):
                    private_files.add(relative)
                    private_targets.add(f"legalforecast.cli.{node.attr}")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr != "setattr" or len(node.args) < 2:
                    continue
                target = node.args[1]
                if isinstance(target, ast.Constant) and isinstance(target.value, str):
                    if (
                        isinstance(node.args[0], ast.Name)
                        and node.args[0].id in aliases
                    ):
                        monkeypatch_targets.add(f"legalforecast.cli.{target.value}")
                    elif target.value.startswith("legalforecast.cli."):
                        monkeypatch_targets.add(target.value)
        if private_files.intersection({relative}):
            cli_import_files.add(relative)
    return CompatibilityInventory(
        cli_import_files=tuple(sorted(cli_import_files)),
        private_cli_files=tuple(sorted(private_files)),
        private_cli_targets=tuple(sorted(private_targets)),
        monkeypatch_targets=tuple(sorted(monkeypatch_targets)),
    )


def _imports_cli(path: Path) -> bool:
    """Return whether a production module imports the CLI module."""

    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(
            alias.name == "legalforecast.cli" for alias in node.names
        ):
            return True
        if isinstance(node, ast.ImportFrom) and node.module == "legalforecast.cli":
            return True
        if isinstance(node, ast.ImportFrom) and node.module == "legalforecast":
            if any(alias.name == "cli" for alias in node.names):
                return True
    return False


def _python_paths(package_root: Path) -> Iterable[str]:
    root = package_root.parent
    for path in sorted(package_root.rglob("*.py")):
        yield path.relative_to(root).as_posix()


def _line_count(node: ast.AST) -> int:
    end = getattr(node, "end_lineno", None)
    start = getattr(node, "lineno", None)
    if not isinstance(start, int) or not isinstance(end, int):
        raise ValueError("AST node lacks source locations")
    return end - start + 1


def _dataclass_from_mapping[T](
    cls: type[T], payload: Mapping[str, object], field: str
) -> T:
    raw = payload.get(field)
    if not isinstance(raw, dict):
        raise ValueError(f"architecture baseline field {field} must be an object")
    return cls(**cast(dict[str, object], raw))


def _string_tuple(payload: Mapping[str, object], field: str) -> tuple[str, ...]:
    raw = payload.get(field)
    if not isinstance(raw, list):
        raise ValueError(f"architecture baseline field {field} must be a string list")
    values = cast(list[object], raw)
    if not all(isinstance(value, str) for value in values):
        raise ValueError(f"architecture baseline field {field} must be a string list")
    return tuple(cast(list[str], values))


if __name__ == "__main__":
    raise SystemExit(main())
