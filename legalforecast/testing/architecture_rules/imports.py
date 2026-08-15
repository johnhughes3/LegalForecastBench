"""Static import-graph, strongly connected components, and reverse-edge scans."""

from __future__ import annotations

import ast
import subprocess
from collections.abc import Mapping
from pathlib import Path

from legalforecast.testing.architecture_rules.symbols import python_paths


def tracked_python_files(root: Path) -> tuple[str, ...]:
    """Return git-tracked Python paths under ``root``, excluding workflow trees."""

    completed = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z", "--", "*.py"],
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        return ()
    return tuple(
        path
        for path in completed.stdout.decode("utf-8").split("\0")
        if path and not path.startswith(".github/")
    )


def parse_module(path: Path, *, filename: str) -> ast.AST | None:
    """Parse ``path`` as Python, returning ``None`` on syntax errors."""

    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=filename)
    except (OSError, SyntaxError):
        return None


def call_argument(node: ast.Call, position: int, keyword: str) -> ast.AST | None:
    """Return a positional or keyword argument from a call node."""

    if position >= 0 and len(node.args) > position:
        return node.args[position]
    return next((item.value for item in node.keywords if item.arg == keyword), None)


def static_string_values(
    node: ast.AST, *, parents: Mapping[ast.AST, ast.AST]
) -> tuple[str, ...]:
    """Resolve a node to constant strings, including simple f-strings and for-loops."""

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
                part_values = static_string_values(part.value, parents=parents)
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


def absolute_import_from_module(path: Path, node: ast.ImportFrom) -> str | None:
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


def is_cli_adapter_module(module: str, *, include_console: bool = True) -> bool:
    """Return whether ``module`` is a CLI, command, or console adapter."""

    if module == "legalforecast.cli" or module.startswith("legalforecast.cli."):
        return True
    if module == "legalforecast.cli_commands" or module.startswith(
        "legalforecast.cli_commands."
    ):
        return True
    return include_console and (
        module == "legalforecast.console" or module.startswith("legalforecast.console.")
    )


def module_to_relative_path(root: Path, module: str) -> str | None:
    """Map a ``legalforecast.*`` module name to a tracked file if it exists."""

    if not module.startswith("legalforecast"):
        return None
    dotted = module.split(".")
    file_path = root.joinpath(*dotted).with_suffix(".py")
    package_path = root.joinpath(*dotted, "__init__.py")
    if file_path.is_file():
        return file_path.relative_to(root).as_posix()
    if package_path.is_file():
        return package_path.relative_to(root).as_posix()
    return None


def imported_legalforecast_modules(path: Path) -> tuple[str, ...]:
    """Return ``legalforecast.*`` modules statically imported by ``path``."""

    tree = parse_module(path, filename=str(path))
    if tree is None:
        return ()
    modules: set[str] = set()
    importlib_module_aliases = {"importlib"}
    import_module_aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            importlib_module_aliases.update(
                alias.asname or alias.name
                for alias in node.names
                if alias.name == "importlib"
            )
            for alias in node.names:
                if alias.name == "legalforecast" or alias.name.startswith(
                    "legalforecast."
                ):
                    modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module == "importlib":
            import_module_aliases.update(
                alias.asname or alias.name
                for alias in node.names
                if alias.name == "import_module"
            )
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = absolute_import_from_module(path, node)
            if module is not None and (
                module == "legalforecast" or module.startswith("legalforecast.")
            ):
                modules.add(module)
                if module == "legalforecast":
                    for alias in node.names:
                        if alias.name != "*":
                            modules.add(f"legalforecast.{alias.name}")
                elif node.module is not None or node.level:
                    for alias in node.names:
                        if alias.name != "*":
                            modules.add(f"{module}.{alias.name}")
        if isinstance(node, ast.Call):
            argument = call_argument(node, 0, "name")
            if (
                isinstance(argument, ast.Constant)
                and isinstance(argument.value, str)
                and (
                    argument.value == "legalforecast"
                    or argument.value.startswith("legalforecast.")
                )
                and _is_dynamic_import(
                    node,
                    importlib_module_aliases=importlib_module_aliases,
                    import_module_aliases=import_module_aliases,
                )
            ):
                modules.add(argument.value)
    return tuple(sorted(modules))


def production_import_graph(root: Path) -> dict[str, tuple[str, ...]]:
    """Build a file-to-file import graph for ``legalforecast/`` production modules."""

    graph: dict[str, set[str]] = {}
    for relative in python_paths(root / "legalforecast"):
        source = root / relative
        targets: set[str] = set()
        for module in imported_legalforecast_modules(source):
            target = module_to_relative_path(root, module)
            if target is not None and target != relative:
                targets.add(target)
        graph[relative] = targets
    return {path: tuple(sorted(targets)) for path, targets in sorted(graph.items())}


def strongly_connected_components(
    graph: Mapping[str, tuple[str, ...]],
) -> tuple[tuple[str, ...], ...]:
    """Return non-trivial Tarjan SCCs as sorted path tuples."""

    index = 0
    stack: list[str] = []
    on_stack: set[str] = set()
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    components: list[tuple[str, ...]] = []

    def connect(node: str) -> None:
        nonlocal index
        indices[node] = index
        lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)
        for successor in graph.get(node, ()):
            if successor not in indices:
                connect(successor)
                lowlinks[node] = min(lowlinks[node], lowlinks[successor])
            elif successor in on_stack:
                lowlinks[node] = min(lowlinks[node], indices[successor])
        if lowlinks[node] == indices[node]:
            component: list[str] = []
            while True:
                member = stack.pop()
                on_stack.remove(member)
                component.append(member)
                if member == node:
                    break
            if len(component) > 1:
                components.append(tuple(sorted(component)))

    for node in graph:
        if node not in indices:
            connect(node)
    return tuple(sorted(components))


def cycle_membership(
    components: tuple[tuple[str, ...], ...],
) -> frozenset[str]:
    """Return every file that participates in a non-trivial SCC."""

    return frozenset(path for component in components for path in component)


def reverse_adapter_dependencies(
    root: Path,
    *,
    include_console: bool = True,
) -> tuple[str, ...]:
    """Return production files that import CLI, console, tests, or scripts."""

    forbidden: set[str] = set()
    for relative in python_paths(root / "legalforecast"):
        if relative == "legalforecast/cli.py" or relative.startswith(
            ("legalforecast/cli_commands/", "legalforecast/console/")
        ):
            continue
        if _imports_forbidden_adapter(
            root / relative,
            include_console=include_console,
        ):
            forbidden.add(relative)
    return tuple(sorted(forbidden))


def uses_file_relative_resolution(path: Path) -> bool:
    """Return whether the module uses ``__file__`` for sibling or root resolution."""

    tree = parse_module(path, filename=str(path))
    if tree is None:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "__file__":
            return True
    return False


def literal_legalforecast_python_paths(path: Path) -> tuple[str, ...]:
    """Return string literals that look like in-repo Python implementation paths."""

    tree = parse_module(path, filename=str(path))
    if tree is None:
        return ()
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        value = node.value.replace("\\", "/")
        if value.startswith("legalforecast/") and value.endswith(".py"):
            found.add(value)
    return tuple(sorted(found))


def _is_dynamic_import(
    node: ast.Call,
    *,
    importlib_module_aliases: set[str],
    import_module_aliases: set[str],
) -> bool:
    function = node.func
    if isinstance(function, ast.Name):
        return function.id == "__import__" or function.id in import_module_aliases
    return (
        isinstance(function, ast.Attribute)
        and isinstance(function.value, ast.Name)
        and function.value.id in importlib_module_aliases
        and function.attr == "import_module"
    )


def _imports_forbidden_adapter(path: Path, *, include_console: bool) -> bool:
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
            if any(
                _is_forbidden_module(alias.name, include_console=include_console)
                for alias in node.names
            ):
                return True
        elif isinstance(node, ast.ImportFrom) and node.module == "importlib":
            import_module_aliases.update(
                alias.asname or alias.name
                for alias in node.names
                if alias.name == "import_module"
            )
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _dynamic_forbidden_import(
            node,
            importlib_module_aliases=importlib_module_aliases,
            import_module_aliases=import_module_aliases,
            include_console=include_console,
        ):
            return True
        if not isinstance(node, ast.ImportFrom):
            continue
        module = absolute_import_from_module(path, node)
        if module is not None and _is_forbidden_module(
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
        if module in {"tests", "scripts"} or (
            module is not None
            and (module.startswith("tests.") or module.startswith("scripts."))
        ):
            return True
    return False


def _is_forbidden_module(module: str, *, include_console: bool) -> bool:
    if is_cli_adapter_module(module, include_console=include_console):
        return True
    return (
        module == "tests"
        or module.startswith("tests.")
        or module == "scripts"
        or module.startswith("scripts.")
    )


def _dynamic_forbidden_import(
    node: ast.Call,
    *,
    importlib_module_aliases: set[str],
    import_module_aliases: set[str],
    include_console: bool,
) -> bool:
    module = call_argument(node, 0, "name")
    if (
        not isinstance(module, ast.Constant)
        or not isinstance(module.value, str)
        or not _is_forbidden_module(module.value, include_console=include_console)
    ):
        return False
    return _is_dynamic_import(
        node,
        importlib_module_aliases=importlib_module_aliases,
        import_module_aliases=import_module_aliases,
    )
