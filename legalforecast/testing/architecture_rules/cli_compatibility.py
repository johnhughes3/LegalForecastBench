"""CLI structure and test-compatibility inventories."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from legalforecast.testing.architecture_rules.imports import (
    absolute_import_from_module,
    call_argument,
    is_cli_adapter_module,
    parse_module,
    static_string_values,
)
from legalforecast.testing.architecture_rules.symbols import line_count, python_paths

CLI_PATH: str = "legalforecast/cli.py"
# Command adapters depend on narrow support modules rather than reaching back
# into this composition root.  Retired acquisition adapters intentionally have
# no compatibility allowlist entries.
UPWARD_IMPORT_ALLOWLIST: frozenset[str] = frozenset()


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


def scan_cli_metrics(root: Path) -> CliMetrics:
    """Measure the CLI facade's remaining structure."""

    cli_path = root / CLI_PATH
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
    return CliMetrics(
        line_count=len(source.splitlines()),
        nonblank_line_count=sum(bool(line.strip()) for line in source.splitlines()),
        top_level_definition_count=len(definitions),
        top_level_class_count=sum(
            isinstance(node, ast.ClassDef) for node in definitions
        ),
        parser_line_count=line_count(parser) if parser is not None else 0,
        command_handler_count=len(command_handlers),
        command_handler_lines=sum(line_count(node) for node in command_handlers),
        verifier_family_count=len(verifier_family),
        verifier_family_lines=sum(line_count(node) for node in verifier_family),
    )


def scan_upward_cli_dependencies(root: Path) -> tuple[str, ...]:
    """Return production modules that import CLI adapters."""

    return tuple(
        sorted(
            path
            for path in python_paths(root / "legalforecast")
            if path != CLI_PATH
            and not path.startswith("legalforecast/testing/")
            and imports_cli(
                root / path,
                include_console=not is_console_adapter_source(path),
            )
        )
    )


def scan_test_compatibility(root: Path) -> CompatibilityInventory:
    """Inventory test coupling to the CLI facade."""

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
    tests_root = root / "tests"
    if not tests_root.is_dir():
        return CompatibilityInventory(
            cli_import_files=(),
            cli_import_occurrences=(),
            private_cli_files=(),
            private_cli_targets=(),
            private_cli_occurrences=(),
            public_cli_files=(),
            public_cli_targets=(),
            public_cli_occurrences=(),
            monkeypatch_targets=(),
            monkeypatch_occurrences=(),
        )
    for path in sorted(tests_root.rglob("*.py")):
        relative = path.relative_to(root).as_posix()
        tree = parse_module(path, filename=relative)
        if tree is None:
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
                name_arg = call_argument(
                    node, position if position is not None else -1, keyword
                )
                if name_arg is None:
                    continue
                for target_name in static_string_values(name_arg, parents=parents):
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
            target_arg = call_argument(node, 0, "target")
            if target_arg is None:
                continue
            for string_target in static_string_values(target_arg, parents=parents):
                if string_target.startswith("legalforecast.cli."):
                    monkeypatch_targets.add(string_target)
                    monkeypatch_occurrences.append(f"{relative}::{string_target}")
            name_arg = call_argument(node, 1, "name")
            if name_arg is None:
                continue
            target_names = static_string_values(name_arg, parents=parents)
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


def imports_cli(path: Path, *, include_console: bool = True) -> bool:
    """Return whether a production module imports a CLI adapter module."""

    path_text = path.as_posix()
    if path_text.endswith("legalforecast/cli.py"):
        return False
    tree = parse_module(path, filename=str(path))
    if tree is None:
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
            is_cli_adapter_module(alias.name, include_console=include_console)
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
        module = absolute_import_from_module(path, node)
        if module is not None and is_cli_adapter_module(
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


def is_console_adapter_source(path: str) -> bool:
    """Return whether ``path`` lives in the console adapter package."""

    return path.startswith("legalforecast/console/")


def _dynamic_cli_adapter_import(
    node: ast.Call,
    *,
    importlib_module_aliases: set[str],
    import_module_aliases: set[str],
    include_console: bool = True,
) -> bool:
    module = call_argument(node, 0, "name")
    if module is None:
        return False
    if (
        not isinstance(module, ast.Constant)
        or not isinstance(module.value, str)
        or not is_cli_adapter_module(module.value, include_console=include_console)
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


def _is_dunder(name: str) -> bool:
    return len(name) >= 4 and name.startswith("__") and name.endswith("__")


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
        target_arg = call_argument(node, 0, "target")
        name_arg = call_argument(node, 1, "name")
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
