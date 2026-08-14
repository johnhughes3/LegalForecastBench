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
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final, cast

BASELINE_PATH: Final[Path] = Path("legalforecast/testing/architecture_baseline.json")
CLI_PATH: Final[str] = "legalforecast/cli.py"
UPWARD_IMPORT_ALLOWLIST: Final[frozenset[str]] = frozenset(
    {
        # Temporary compatibility bridge for extracted adapters.  The adapter
        # late-binds facade helpers so existing monkeypatch targets keep
        # working; this exception must disappear once those helpers are
        # injected through a cycle-neutral command context.
        "legalforecast/cli_commands/report.py",
        "legalforecast/cli_commands/score.py",
        "legalforecast/ingestion/downstream_lineage_verification.py",
        "legalforecast/ingestion/packet_build_replay.py",
        "legalforecast/ingestion/purchase_approval.py",
        "legalforecast/ingestion/recovered_public_replay.py",
        "legalforecast/ingestion/resolved_post_recovery.py",
        "legalforecast/ingestion/stage_a_lineage_verification.py",
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
    cli_import_occurrences: tuple[str, ...]
    private_cli_files: tuple[str, ...]
    private_cli_targets: tuple[str, ...]
    private_cli_occurrences: tuple[str, ...]
    public_cli_files: tuple[str, ...]
    public_cli_targets: tuple[str, ...]
    public_cli_occurrences: tuple[str, ...]
    monkeypatch_targets: tuple[str, ...]
    monkeypatch_occurrences: tuple[str, ...]


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
    parser = next((node for node in functions if node.name == "build_parser"), None)
    metrics = CliMetrics(
        line_count=len(source.splitlines()),
        nonblank_line_count=sum(bool(line.strip()) for line in source.splitlines()),
        top_level_definition_count=len(definitions),
        top_level_class_count=sum(
            isinstance(node, ast.ClassDef) for node in definitions
        ),
        parser_line_count=_line_count(parser) if parser is not None else 0,
        command_handler_count=len(command_handlers),
        command_handler_lines=sum(_line_count(node) for node in command_handlers),
        verifier_family_count=len(verifier_family),
        verifier_family_lines=sum(_line_count(node) for node in verifier_family),
    )
    upward = tuple(
        sorted(
            path
            for path in _python_paths(resolved_root / "legalforecast")
            if path != CLI_PATH
            and _imports_cli(
                resolved_root / path,
                include_console=not _is_console_adapter_source(path),
            )
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
        elif observed < allowed:
            violations.append(
                f"stale cli_metrics.{field} must be reduced: "
                f"reviewed {allowed} > observed {observed}"
            )

    unexpected_upward = sorted(
        set(current.upward_cli_dependencies) - set(baseline.upward_cli_dependencies)
    )
    if unexpected_upward:
        violations.append(
            "new upward CLI dependencies: " + ", ".join(unexpected_upward)
        )
    stale_upward = sorted(
        set(baseline.upward_cli_dependencies) - set(current.upward_cli_dependencies)
    )
    if stale_upward:
        violations.append(
            "stale upward CLI dependencies must be removed: " + ", ".join(stale_upward)
        )
    unexpected_allowlist = sorted(
        set(current.upward_cli_dependencies) - UPWARD_IMPORT_ALLOWLIST
    )
    if unexpected_allowlist:
        violations.append(
            "upward CLI dependency outside the upward-import allowlist: "
            + ", ".join(unexpected_allowlist)
        )

    current_compat = current.compatibility
    baseline_compat = baseline.compatibility
    for field in (
        "cli_import_files",
        "private_cli_files",
        "private_cli_targets",
        "public_cli_files",
        "public_cli_targets",
        "monkeypatch_targets",
    ):
        observed = set(getattr(current_compat, field))
        allowed = set(getattr(baseline_compat, field))
        additions = sorted(observed - allowed)
        if additions:
            violations.append(f"new compatibility.{field}: {', '.join(additions)}")
        removals = sorted(allowed - observed)
        if removals:
            violations.append(
                f"stale compatibility.{field} must be removed: {', '.join(removals)}"
            )
    for field in (
        "cli_import_occurrences",
        "private_cli_occurrences",
        "public_cli_occurrences",
        "monkeypatch_occurrences",
    ):
        observed = Counter(cast(tuple[str, ...], getattr(current_compat, field)))
        allowed = Counter(cast(tuple[str, ...], getattr(baseline_compat, field)))
        additions = sorted((observed - allowed).elements())
        if additions:
            violations.append(f"new compatibility.{field}: {', '.join(additions)}")
        removals = sorted((allowed - observed).elements())
        if removals:
            violations.append(
                f"stale compatibility.{field} must be removed: {', '.join(removals)}"
            )
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
    if args.write_baseline:
        write_baseline(baseline, scan_repository(root))
        print(f"wrote architecture baseline to {baseline}")
        return 0
    violations = check_baseline(root, baseline)
    if violations:
        print("architecture ratchet found new violations:", file=sys.stderr)
        for violation in violations:
            print(f"- {violation}", file=sys.stderr)
        return 1
    try:
        reported_baseline = baseline.relative_to(root)
    except ValueError:
        reported_baseline = baseline
    print(f"architecture ratchet passed: {reported_baseline}")
    return 0


def _scan_test_compatibility(root: Path) -> CompatibilityInventory:
    cli_import_files: set[str] = set()
    cli_import_occurrences: list[str] = []
    private_files: set[str] = set()
    private_targets: set[str] = set()
    private_occurrences: list[str] = []
    public_files: set[str] = set()
    public_targets: set[str] = set()
    public_occurrences: list[str] = []
    monkeypatch_targets: set[str] = set()
    monkeypatch_occurrences: list[str] = []
    for path in sorted((root / "tests").rglob("*.py")):
        relative = path.relative_to(root).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        except SyntaxError:
            continue
        parents = {
            child: parent
            for parent in ast.walk(tree)
            for child in ast.iter_child_nodes(parent)
        }
        direct_aliases: set[str] = set()
        package_aliases: set[str] = set()
        importlib_module_aliases = {"importlib"}
        import_module_aliases: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                importlib_module_aliases.update(
                    alias.asname or alias.name
                    for alias in node.names
                    if alias.name == "importlib"
                )
            elif isinstance(node, ast.ImportFrom) and node.module == "importlib":
                import_module_aliases.update(
                    alias.asname or alias.name
                    for alias in node.names
                    if alias.name == "import_module"
                )
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            value = node.value
            if not isinstance(value, ast.Call) or not _dynamic_cli_adapter_import(
                value,
                importlib_module_aliases=importlib_module_aliases,
                import_module_aliases=import_module_aliases,
                include_console=False,
            ):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    direct_aliases.add(target.id)
                    cli_import_files.add(relative)
                    cli_import_occurrences.append(relative)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "legalforecast.cli":
                        if alias.asname is None:
                            package_aliases.add("legalforecast")
                        else:
                            direct_aliases.add(alias.asname)
                        cli_import_files.add(relative)
                        cli_import_occurrences.append(relative)
            elif (
                isinstance(node, ast.ImportFrom) and node.module == "legalforecast.cli"
            ):
                cli_import_files.add(relative)
                cli_import_occurrences.append(relative)
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    _record_cli_member(
                        f"legalforecast.cli.{alias.name}",
                        relative=relative,
                        private_files=private_files,
                        private_targets=private_targets,
                        private_occurrences=private_occurrences,
                        public_files=public_files,
                        public_targets=public_targets,
                        public_occurrences=public_occurrences,
                    )
            elif isinstance(node, ast.ImportFrom) and node.module == "legalforecast":
                for alias in node.names:
                    if alias.name == "cli":
                        direct_aliases.add(alias.asname or "cli")
                        cli_import_files.add(relative)
                        cli_import_occurrences.append(relative)
        wrappers = _cli_patch_wrappers(
            tree,
            direct_aliases=direct_aliases,
            package_aliases=package_aliases,
        )
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                target = _cli_attribute_target(
                    node,
                    direct_aliases=direct_aliases,
                    package_aliases=package_aliases,
                )
                if target is not None:
                    _record_cli_member(
                        target,
                        relative=relative,
                        private_files=private_files,
                        private_targets=private_targets,
                        private_occurrences=private_occurrences,
                        public_files=public_files,
                        public_targets=public_targets,
                        public_occurrences=public_occurrences,
                    )
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name) and node.func.id in wrappers:
                position, keyword = wrappers[node.func.id]
                name_arg = _call_argument(
                    node, position if position is not None else -1, keyword
                )
                if name_arg is None:
                    continue
                for target_name in _static_string_values(name_arg, parents=parents):
                    qualified_target = (
                        target_name
                        if target_name.startswith("legalforecast.cli.")
                        else f"legalforecast.cli.{target_name}"
                    )
                    monkeypatch_targets.add(qualified_target)
                    monkeypatch_occurrences.append(f"{relative}::{qualified_target}")
                continue
            if not isinstance(node.func, ast.Attribute) or node.func.attr != "setattr":
                continue
            target_arg = _call_argument(node, 0, "target")
            if target_arg is None:
                continue
            for string_target in _static_string_values(target_arg, parents=parents):
                if string_target.startswith("legalforecast.cli."):
                    monkeypatch_targets.add(string_target)
                    monkeypatch_occurrences.append(f"{relative}::{string_target}")
            name_arg = _call_argument(node, 1, "name")
            if name_arg is None:
                continue
            target_names = _static_string_values(name_arg, parents=parents)
            for target_name in target_names:
                object_target = _cli_object_target(
                    target_arg,
                    direct_aliases=direct_aliases,
                    package_aliases=package_aliases,
                )
                if object_target is not None:
                    qualified_target = f"{object_target}.{target_name}"
                    monkeypatch_targets.add(qualified_target)
                    monkeypatch_occurrences.append(f"{relative}::{qualified_target}")
                elif target_name.startswith("legalforecast.cli."):
                    monkeypatch_targets.add(target_name)
                    monkeypatch_occurrences.append(f"{relative}::{target_name}")
        if relative in private_files or relative in public_files:
            cli_import_files.add(relative)
    return CompatibilityInventory(
        cli_import_files=tuple(sorted(cli_import_files)),
        cli_import_occurrences=tuple(sorted(cli_import_occurrences)),
        private_cli_files=tuple(sorted(private_files)),
        private_cli_targets=tuple(sorted(private_targets)),
        private_cli_occurrences=tuple(sorted(private_occurrences)),
        public_cli_files=tuple(sorted(public_files)),
        public_cli_targets=tuple(sorted(public_targets)),
        public_cli_occurrences=tuple(sorted(public_occurrences)),
        monkeypatch_targets=tuple(sorted(monkeypatch_targets)),
        monkeypatch_occurrences=tuple(sorted(monkeypatch_occurrences)),
    )


def _imports_cli(path: Path, *, include_console: bool = True) -> bool:
    """Return whether a production module imports a CLI adapter module."""

    path_text = path.as_posix()
    if path_text.endswith("legalforecast/cli.py"):
        return False

    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError:
        return False
    importlib_module_aliases = {"importlib"}
    import_module_aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            importlib_module_aliases.update(
                alias.asname or alias.name
                for alias in node.names
                if alias.name == "importlib"
            )
        elif isinstance(node, ast.ImportFrom) and node.module == "importlib":
            import_module_aliases.update(
                alias.asname or alias.name
                for alias in node.names
                if alias.name == "import_module"
            )
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(
            _is_cli_adapter_module(alias.name, include_console=include_console)
            for alias in node.names
        ):
            return True
        if isinstance(node, ast.Call) and _dynamic_cli_adapter_import(
            node,
            importlib_module_aliases=importlib_module_aliases,
            import_module_aliases=import_module_aliases,
            include_console=include_console,
        ):
            return True
        if not isinstance(node, ast.ImportFrom):
            continue
        module = _absolute_import_from_module(path, node)
        if module is not None and _is_cli_adapter_module(
            module, include_console=include_console
        ):
            return True
        if module == "legalforecast":
            adapter_names = (
                {"cli", "cli_commands", "console"}
                if include_console
                else {"cli", "cli_commands"}
            )
            if any(alias.name in adapter_names for alias in node.names):
                return True
    return False


def _is_console_adapter_source(path: str) -> bool:
    return path.startswith("legalforecast/console/")


def _is_cli_adapter_module(module: str, *, include_console: bool = True) -> bool:
    if module == "legalforecast.cli" or module.startswith("legalforecast.cli."):
        return True
    if module == "legalforecast.cli_commands" or module.startswith(
        "legalforecast.cli_commands."
    ):
        return True
    return include_console and (
        module == "legalforecast.console" or module.startswith("legalforecast.console.")
    )


def _dynamic_cli_adapter_import(
    node: ast.Call,
    *,
    importlib_module_aliases: set[str],
    import_module_aliases: set[str],
    include_console: bool = True,
) -> bool:
    module = _call_argument(node, 0, "name")
    if module is None:
        return False
    if (
        not isinstance(module, ast.Constant)
        or not isinstance(module.value, str)
        or not _is_cli_adapter_module(module.value, include_console=include_console)
    ):
        return False
    function = node.func
    if isinstance(function, ast.Name):
        return function.id == "__import__" or function.id in import_module_aliases
    return (
        isinstance(function, ast.Attribute)
        and isinstance(function.value, ast.Name)
        and function.value.id in importlib_module_aliases
        and function.attr == "import_module"
    )


def _static_string_values(
    node: ast.AST, *, parents: Mapping[ast.AST, ast.AST]
) -> tuple[str, ...]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return (node.value,)
    if isinstance(node, ast.JoinedStr):
        values: tuple[str, ...] = ("",)
        for part in node.values:
            if isinstance(part, ast.Constant) and isinstance(part.value, str):
                part_values: tuple[str, ...] = (part.value,)
            elif (
                isinstance(part, ast.FormattedValue)
                and part.conversion == -1
                and part.format_spec is None
            ):
                part_values = _static_string_values(part.value, parents=parents)
            else:
                return ()
            if not part_values:
                return ()
            values = tuple(
                prefix + suffix for prefix in values for suffix in part_values
            )
        return values
    if not isinstance(node, ast.Name):
        return ()
    current: ast.AST | None = node
    while current is not None:
        current = parents.get(current)
        if not isinstance(current, ast.For):
            continue
        if not isinstance(current.target, ast.Name) or current.target.id != node.id:
            continue
        if not isinstance(current.iter, (ast.List, ast.Tuple, ast.Set)):
            return ()
        values = tuple(
            element.value
            for element in current.iter.elts
            if isinstance(element, ast.Constant) and isinstance(element.value, str)
        )
        return values if len(values) == len(current.iter.elts) else ()
    return ()


def _call_argument(node: ast.Call, position: int, keyword: str) -> ast.AST | None:
    if position >= 0 and len(node.args) > position:
        return node.args[position]
    return next(
        (item.value for item in node.keywords if item.arg == keyword),
        None,
    )


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
    normalized = cast(dict[str, object], raw).copy()
    for name, value in tuple(normalized.items()):
        if isinstance(value, list):
            values = cast(list[object], value)
            if not all(isinstance(item, str) for item in values):
                raise ValueError(
                    f"architecture baseline field {field}.{name} must be a string list"
                )
            normalized[name] = tuple(cast(list[str], values))
    try:
        return cls(**normalized)
    except TypeError as exc:
        raise ValueError(f"invalid architecture baseline field {field}") from exc


def _is_dunder(name: str) -> bool:
    return len(name) >= 4 and name.startswith("__") and name.endswith("__")


def _absolute_import_from_module(path: Path, node: ast.ImportFrom) -> str | None:
    """Resolve an import-from module within the ``legalforecast`` package."""

    if node.level == 0:
        return node.module
    try:
        package_index = max(
            index
            for index, part in enumerate(path.parent.parts)
            if part == "legalforecast"
        )
    except ValueError:
        return None
    package = list(path.parent.parts[package_index:])
    parents = node.level - 1
    if parents >= len(package):
        return None
    if parents:
        del package[-parents:]
    if node.module:
        package.extend(node.module.split("."))
    return ".".join(package)


def _cli_object_target(
    node: ast.AST,
    *,
    direct_aliases: set[str],
    package_aliases: set[str],
) -> str | None:
    if isinstance(node, ast.Name) and node.id in direct_aliases:
        return "legalforecast.cli"
    if isinstance(node, ast.Attribute):
        return _cli_attribute_target(
            node,
            direct_aliases=direct_aliases,
            package_aliases=package_aliases,
        )
    return None


def _cli_attribute_target(
    node: ast.Attribute,
    *,
    direct_aliases: set[str],
    package_aliases: set[str],
) -> str | None:
    parts: list[str] = []
    current: ast.AST = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if not isinstance(current, ast.Name):
        return None
    parts.append(current.id)
    ordered = list(reversed(parts))
    if ordered[0] in direct_aliases:
        return ".".join(("legalforecast", "cli", *ordered[1:]))
    if ordered[0] in package_aliases and len(ordered) >= 2 and ordered[1] == "cli":
        return ".".join(("legalforecast", "cli", *ordered[2:]))
    return None


def _is_private_target(target: str) -> bool:
    cli_member = target.removeprefix("legalforecast.cli.").split(".", 1)[0]
    return cli_member.startswith("_") and not _is_dunder(cli_member)


def _is_public_target(target: str) -> bool:
    if not target.startswith("legalforecast.cli."):
        return False
    cli_member = target.removeprefix("legalforecast.cli.").split(".", 1)[0]
    return bool(cli_member) and not cli_member.startswith("_")


def _record_cli_member(
    target: str,
    *,
    relative: str,
    private_files: set[str],
    private_targets: set[str],
    private_occurrences: list[str],
    public_files: set[str],
    public_targets: set[str],
    public_occurrences: list[str],
) -> None:
    occurrence = f"{relative}::{target}"
    if _is_private_target(target):
        private_files.add(relative)
        private_targets.add(target)
        private_occurrences.append(occurrence)
    elif _is_public_target(target):
        public_files.add(relative)
        public_targets.add(target)
        public_occurrences.append(occurrence)


def _cli_patch_wrappers(
    tree: ast.AST,
    *,
    direct_aliases: set[str],
    package_aliases: set[str],
) -> dict[str, tuple[int | None, str]]:
    """Map helper names that setattr CLI members via a parameter to that parameter."""

    wrappers: dict[str, tuple[int | None, str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        resolved = _cli_patch_wrapper_name_parameter(
            node,
            direct_aliases=direct_aliases,
            package_aliases=package_aliases,
        )
        if resolved is not None:
            wrappers[node.name] = resolved
    return wrappers


def _cli_patch_wrapper_name_parameter(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
    *,
    direct_aliases: set[str],
    package_aliases: set[str],
) -> tuple[int | None, str] | None:
    positional = [arg.arg for arg in (*func.args.posonlyargs, *func.args.args)]
    for node in ast.walk(func):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "setattr":
            continue
        target_arg = _call_argument(node, 0, "target")
        name_arg = _call_argument(node, 1, "name")
        if target_arg is None or name_arg is None:
            continue
        if (
            _cli_object_target(
                target_arg,
                direct_aliases=direct_aliases,
                package_aliases=package_aliases,
            )
            is None
        ):
            continue
        if not isinstance(name_arg, ast.Name):
            continue
        parameter = name_arg.id
        if parameter in positional:
            return positional.index(parameter), parameter
        if any(arg.arg == parameter for arg in func.args.kwonlyargs):
            return None, parameter
    return None


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
