"""Semantic fences for the supported public LegalForecastBench runtime.

The scanners reuse the static import-graph helpers and inspect subprocess
argv, not file counts, help snapshots, or historical schema names.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Mapping, Sequence
from pathlib import Path

from legalforecast.testing.architecture_rules.imports import (
    absolute_import_from_module,
    call_argument,
    imported_legalforecast_modules,
    parse_module,
    static_string_values,
    tracked_python_files,
)

FORBIDDEN_IMPORT_PREFIXES: tuple[str, ...] = (
    "legalforecast.acquisition",
    "legalforecast.document_need",
    "legalforecast.extraction",
    "legalforecast.labeling",
    "legalforecast.selection",
    "legalforecast.unitization",
)
FORBIDDEN_TOP_LEVEL_IMPORTS: frozenset[str] = frozenset(
    {
        "beads",
        "courtlistener",
        "juriscraper",
        "pacer",
        "recap",
    }
)
RETIRED_OFFICIAL_WORKFLOWS: frozenset[str] = frozenset(
    {
        "official-paid-labeling-authority-smoke.yaml",
        "official-paid-labeling.yaml",
        "official-provider-authority-infra.yaml",
        "official-s3-access-validation.yaml",
        "run-benchmark-manifest.yaml",
        "stage-manifest-run.yaml",
        "stage-official-manifest-run.yaml",
    }
)
FORECAST_WORKFLOWS: frozenset[str] = frozenset({"run-benchmark.yaml"})
FAN_IN_WORKFLOWS: frozenset[str] = frozenset({"fan-in-publish.yaml"})
ALWAYS_RETIRED_INPUTS: frozenset[str] = frozenset(
    {
        "acquisition_cycle",
        "acquisition_cycle_uri",
        "courtlistener_token",
        "labels_uri",
        "pacer_login",
        "run_input_manifest_uri",
    }
)
FORECAST_RETIRED_INPUTS: frozenset[str] = frozenset({"labels_release_uri"})
OPERATOR_COMMANDS: tuple[str, ...] = ("manifest", "run", "score", "report")
_SUBPROCESS_FUNCS = frozenset({"Popen", "call", "check_call", "check_output", "run"})
_APPROVAL_PROSE_NAMES = frozenset(
    {
        "approval_prose",
        "load_approval_prose",
        "lookup_approval_prose",
        "lookup_owner_prose",
        "owner_prose",
        "read_owner_prose",
    }
)
_APPROVAL_PROSE_PATH = re.compile(
    r"(?:^|/)(?:approval-prose|approval_prose|owner-prose|owner_prose)"
    r"(?:\.[A-Za-z0-9]+)?$"
)
_PRIVATE_HELP_TOKEN = re.compile(
    r"\b(?:acquisition|bd|courtlistener|init-cycle|labeling-pipeline|"
    r"llm-label|pacer|recap|retrieve|run-cycle|unitizer)\b",
    re.IGNORECASE,
)


def is_forbidden_import(module: str) -> bool:
    """Return whether ``module`` is private corpus-construction runtime."""

    top_level = module.split(".", 1)[0]
    if top_level in FORBIDDEN_TOP_LEVEL_IMPORTS:
        return True
    return any(
        module == prefix or module.startswith(f"{prefix}.")
        for prefix in FORBIDDEN_IMPORT_PREFIXES
    )


def forbidden_imports_in(path: Path) -> tuple[str, ...]:
    """Return forbidden modules statically imported by ``path``."""

    modules = set(imported_legalforecast_modules(path))
    modules.update(_imported_external_modules(path))
    return tuple(sorted(module for module in modules if is_forbidden_import(module)))


def subprocess_argvs(path: Path) -> tuple[tuple[str, ...], ...]:
    """Return static argv tuples from subprocess and ``os.system`` calls."""

    tree = parse_module(path, filename=str(path))
    if tree is None:
        return ()
    parents = _parent_map(tree)
    subprocess_modules = {"subprocess"}
    os_modules = {"os"}
    func_aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "subprocess":
                    subprocess_modules.add(alias.asname or alias.name)
                elif alias.name == "os":
                    os_modules.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module == "subprocess":
            for alias in node.names:
                if alias.name in _SUBPROCESS_FUNCS:
                    func_aliases[alias.asname or alias.name] = alias.name
        elif isinstance(node, ast.ImportFrom) and node.module == "os":
            for alias in node.names:
                if alias.name == "system":
                    func_aliases[alias.asname or alias.name] = "system"
    found: list[tuple[str, ...]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not _is_process_call(
            node,
            subprocess_modules=subprocess_modules,
            os_modules=os_modules,
            func_aliases=func_aliases,
        ):
            continue
        argv = _static_argv(node, parents=parents)
        if argv:
            found.append(argv)
    return tuple(found)


def is_bd_execution(argv: Sequence[str]) -> bool:
    """Return whether ``argv`` invokes ``bd`` as the executable."""

    tokens = [token for token in argv if token]
    if not tokens:
        return False
    executable = Path(tokens[0]).name
    if executable == "bd":
        return True
    if executable in {"python", "python3"}:
        try:
            module_index = tokens.index("-m") + 1
        except ValueError:
            return False
        return module_index < len(tokens) and tokens[module_index] == "bd"
    if executable == "uv":
        return len(tokens) >= 3 and tokens[1] == "run" and Path(tokens[2]).name == "bd"
    return executable == "env" and any(Path(token).name == "bd" for token in tokens[1:])


def bd_execution_argvs(path: Path) -> tuple[tuple[str, ...], ...]:
    """Return static argv tuples that would execute Beads from ``path``."""

    return tuple(argv for argv in subprocess_argvs(path) if is_bd_execution(argv))


def approval_prose_lookups(path: Path) -> tuple[str, ...]:
    """Return owner-prose / Beads-comment lookups in ``path``."""

    tree = parse_module(path, filename=str(path))
    if tree is None:
        return ()
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in _APPROVAL_PROSE_NAMES:
            found.add(node.id)
        elif isinstance(node, ast.Attribute) and node.attr in _APPROVAL_PROSE_NAMES:
            found.add(node.attr)
        elif (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name in _APPROVAL_PROSE_NAMES
        ):
            found.add(node.name)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            marker = _approval_prose_path_marker(node.value)
            if marker is not None:
                found.add(marker)
    for argv in bd_execution_argvs(path):
        if "comments" in argv[1:]:
            found.add("bd comments")
    return tuple(sorted(found))


def dispatch_input_names(workflow_text: str) -> frozenset[str]:
    """Return ``workflow_dispatch`` input names from a workflow document."""

    names: set[str] = set()
    in_dispatch = False
    in_inputs = False
    inputs_indent: int | None = None
    for raw_line in workflow_text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        stripped = raw_line.strip()
        if stripped == "workflow_dispatch:":
            in_dispatch = True
            in_inputs = False
            inputs_indent = None
            continue
        if in_dispatch and stripped == "inputs:":
            in_inputs = True
            inputs_indent = indent
            continue
        if in_inputs:
            if inputs_indent is not None and indent <= inputs_indent:
                in_inputs = False
                in_dispatch = False
            elif (
                inputs_indent is not None
                and indent == inputs_indent + 2
                and stripped.endswith(":")
            ):
                key = _dispatch_input_key(stripped)
                if key is not None:
                    names.add(key)
                continue
        if in_dispatch and indent == 0:
            in_dispatch = False
            in_inputs = False
    return frozenset(names)


def workflow_role(filename: str) -> str:
    """Return the public-boundary role for a workflow filename."""

    if filename in FORECAST_WORKFLOWS:
        return "forecast"
    if filename in FAN_IN_WORKFLOWS:
        return "fan-in"
    return "other"


def retired_dispatch_inputs(workflow_text: str, *, role: str) -> tuple[str, ...]:
    """Return retired dispatch inputs accepted by a workflow of ``role``."""

    banned = set(ALWAYS_RETIRED_INPUTS)
    if role != "fan-in":
        banned |= FORECAST_RETIRED_INPUTS
    return tuple(sorted(dispatch_input_names(workflow_text) & banned))


def private_runtime_help_violations(help_text: str) -> tuple[str, ...]:
    """Return private-runtime tokens that operator help must not advertise."""

    return tuple(sorted(set(_PRIVATE_HELP_TOKEN.findall(help_text))))


def public_runtime_python_files(root: Path) -> tuple[str, ...]:
    """Return tracked public-runtime Python paths, excluding test helpers."""

    return tuple(
        path
        for path in tracked_python_files(root)
        if (
            path.startswith("legalforecast/")
            and not path.startswith("legalforecast/testing/")
        )
        or path.startswith(("scripts/", "examples/"))
    )


def scan_public_boundary(root: Path) -> tuple[str, ...]:
    """Return production violations of the supported public boundary."""

    violations: list[str] = []
    for relative in public_runtime_python_files(root):
        path = root / relative
        for module in forbidden_imports_in(path):
            violations.append(f"{relative} imports {module}")
        for argv in bd_execution_argvs(path):
            violations.append(f"{relative} executes {' '.join(argv)}")
        for lookup in approval_prose_lookups(path):
            violations.append(f"{relative} looks up {lookup}")
    workflow_root = root / ".github" / "workflows"
    for name in sorted(RETIRED_OFFICIAL_WORKFLOWS):
        if (workflow_root / name).is_file():
            violations.append(f"retired official workflow still present: {name}")
    if workflow_root.is_dir():
        for path in sorted(workflow_root.glob("*.y*ml")):
            for input_name in retired_dispatch_inputs(
                path.read_text(encoding="utf-8"),
                role=workflow_role(path.name),
            ):
                violations.append(f"{path.name} accepts retired input {input_name}")
    return tuple(violations)


def _imported_external_modules(path: Path) -> tuple[str, ...]:
    tree = parse_module(path, filename=str(path))
    if tree is None:
        return ()
    parents = _parent_map(tree)
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
                if not _is_legalforecast_module(alias.name):
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
            if module is None or _is_legalforecast_module(module):
                continue
            modules.add(module)
            if node.module is not None or node.level:
                for alias in node.names:
                    if alias.name != "*":
                        modules.add(f"{module}.{alias.name}")
        elif isinstance(node, ast.Call) and _is_dynamic_import(
            node,
            importlib_module_aliases=importlib_module_aliases,
            import_module_aliases=import_module_aliases,
        ):
            argument = call_argument(node, 0, "name")
            if argument is None:
                continue
            modules.update(_resolved_string_values(argument, parents=parents))
    return tuple(sorted(modules))


def _is_legalforecast_module(module: str) -> bool:
    return module == "legalforecast" or module.startswith("legalforecast.")


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


def _parent_map(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    return parents


def _is_process_call(
    node: ast.Call,
    *,
    subprocess_modules: set[str],
    os_modules: set[str],
    func_aliases: Mapping[str, str],
) -> bool:
    function = node.func
    if isinstance(function, ast.Name):
        return function.id in func_aliases
    return (
        isinstance(function, ast.Attribute)
        and isinstance(function.value, ast.Name)
        and (
            (
                function.value.id in subprocess_modules
                and function.attr in _SUBPROCESS_FUNCS
            )
            or (function.value.id in os_modules and function.attr == "system")
        )
    )


def _static_argv(
    node: ast.Call, *, parents: Mapping[ast.AST, ast.AST]
) -> tuple[str, ...]:
    argument = call_argument(node, 0, "args")
    if argument is None:
        argument = call_argument(node, 0, "command")
    if argument is None:
        return ()
    assigned = _assigned_value(argument, parents=parents)
    if assigned is not None:
        argument = assigned
    if isinstance(argument, (ast.List, ast.Tuple)):
        argv = [
            _single_static_string(element, parents=parents) or ""
            for element in argument.elts
        ]
        return tuple(argv) if any(argv) else ()
    values = _resolved_string_values(argument, parents=parents)
    if len(values) != 1:
        return ()
    return tuple(values[0].split())


def _dispatch_input_key(stripped: str) -> str | None:
    key = stripped[:-1].strip()
    if len(key) >= 2 and key[0] == key[-1] and key[0] in {"'", '"'}:
        key = key[1:-1]
    if not key or any(character.isspace() for character in key):
        return None
    return key


def _resolved_string_values(
    node: ast.AST, *, parents: Mapping[ast.AST, ast.AST]
) -> tuple[str, ...]:
    values = static_string_values(node, parents=parents)
    if values:
        return values
    assigned = _assigned_value(node, parents=parents)
    if assigned is None:
        return ()
    return static_string_values(assigned, parents=parents)


def _single_static_string(
    node: ast.AST, *, parents: Mapping[ast.AST, ast.AST]
) -> str | None:
    values = _resolved_string_values(node, parents=parents)
    if len(values) != 1:
        return None
    return values[0]


def _assigned_value(
    node: ast.AST, *, parents: Mapping[ast.AST, ast.AST]
) -> ast.AST | None:
    if not isinstance(node, ast.Name):
        return None
    current: ast.AST | None = node
    while current is not None:
        parent = parents.get(current)
        if isinstance(parent, (ast.AsyncFunctionDef, ast.FunctionDef, ast.Module)):
            assigned: ast.AST | None = None
            for statement in parent.body:
                if getattr(statement, "lineno", 0) >= node.lineno:
                    break
                value = _simple_assignment(statement, node.id)
                if value is not None:
                    assigned = value
            return assigned
        current = parent
    return None


def _simple_assignment(statement: ast.AST, name: str) -> ast.AST | None:
    if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
        target = statement.targets[0]
        if isinstance(target, ast.Name) and target.id == name:
            return statement.value
    if (
        isinstance(statement, ast.AnnAssign)
        and isinstance(statement.target, ast.Name)
        and statement.target.id == name
    ):
        return statement.value
    return None


def _approval_prose_path_marker(value: str) -> str | None:
    normalized = value.replace("\\", "/")
    if _APPROVAL_PROSE_PATH.search(normalized) is None:
        return None
    return Path(normalized).name
