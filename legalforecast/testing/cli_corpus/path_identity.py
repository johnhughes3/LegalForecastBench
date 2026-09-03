"""Inventory of path-bound, dynamic, and authenticated implementation identities."""

from __future__ import annotations

import ast
import re
from collections.abc import Mapping
from pathlib import Path

from legalforecast.testing.architecture_rules.imports import (
    call_argument,
    literal_legalforecast_python_paths,
    parse_module,
    tracked_python_files,
    uses_file_relative_resolution,
)
from legalforecast.testing.cli_corpus.paths import (
    IDENTITY_SCHEMA_VERSION,
    as_object_dict,
    as_object_list,
)

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_PYTHON_PATH = re.compile(r"legalforecast/.+\.py\Z")
_ENTRY_POINT_NAMES = ("legalforecast",)


def scan_path_identity(root: Path) -> dict[str, object]:
    """Scan tracked Python files for move-sensitive path identities."""

    files = tracked_python_files(root)
    relative_paths: list[str] = []
    literals: dict[str, list[str]] = {}
    dynamic_imports: dict[str, list[str]] = {}
    identity_checks: list[str] = []
    authenticated: list[dict[str, object]] = []
    for relative in files:
        path = root / relative
        if uses_file_relative_resolution(path):
            relative_paths.append(relative)
        found_literals = literal_legalforecast_python_paths(path)
        if found_literals:
            literals[relative] = list(found_literals)
        found_dynamic = _dynamic_imports(path)
        if found_dynamic:
            dynamic_imports[relative] = list(found_dynamic)
        identity_checks.extend(_identity_checks(path, relative))
        authenticated.extend(_authenticated_profiles(path, relative))
    return {
        "schema_version": IDENTITY_SCHEMA_VERSION,
        "authenticated_source_profiles": authenticated,
        "dynamic_imports": dynamic_imports,
        "entry_point_names": list(_ENTRY_POINT_NAMES),
        "file_relative_resolution": relative_paths,
        "identity_checks": identity_checks,
        "literal_implementation_paths": literals,
    }


def identity_covers_authenticated_cli(payload: Mapping[str, object]) -> bool:
    """Return whether Firecrawl/CLI authenticated source paths are inventoried."""

    profiles = payload.get("authenticated_source_profiles")
    if profiles is None:
        return False
    try:
        profile_list = as_object_list(profiles)
    except ValueError:
        return False
    named_paths: set[str] = set()
    for profile in profile_list:
        try:
            record = as_object_dict(profile)
        except ValueError:
            continue
        paths = record.get("paths")
        if paths is None:
            continue
        try:
            named_paths.update(str(item) for item in as_object_list(paths))
        except ValueError:
            continue
    return "legalforecast/cli.py" in named_paths


def _dynamic_imports(path: Path) -> tuple[str, ...]:
    tree = parse_module(path, filename=str(path))
    if tree is None:
        return ()
    importlib_aliases = {"importlib"}
    import_module_aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            importlib_aliases.update(
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
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not _is_dynamic_import(
            node,
            importlib_aliases=importlib_aliases,
            import_module_aliases=import_module_aliases,
        ):
            continue
        argument = call_argument(node, 0, "name")
        if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
            found.add(argument.value)
    return tuple(sorted(found))


def _is_dynamic_import(
    node: ast.Call,
    *,
    importlib_aliases: set[str],
    import_module_aliases: set[str],
) -> bool:
    function = node.func
    if isinstance(function, ast.Name):
        return function.id == "__import__" or function.id in import_module_aliases
    return (
        isinstance(function, ast.Attribute)
        and isinstance(function.value, ast.Name)
        and function.value.id in importlib_aliases
        and function.attr == "import_module"
    )


def _identity_checks(path: Path, relative: str) -> tuple[str, ...]:
    tree = parse_module(path, filename=relative)
    if tree is None:
        return ()
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        if any(isinstance(op, (ast.Is, ast.IsNot)) for op in node.ops):
            if _mentions_cli(node):
                found.append(f"{relative}::callable-identity")
        if _is_module_identity(node):
            found.append(f"{relative}::module-identity")
    return tuple(found)


def _mentions_cli(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and child.value == "legalforecast.cli":
            return True
        if isinstance(child, ast.Attribute) and child.attr in {"cli", "__file__"}:
            return True
        if isinstance(child, ast.Name) and child.id in {"cli", "cli_module"}:
            return True
    return False


def _is_module_identity(node: ast.Compare) -> bool:
    candidates = [node.left, *node.comparators]
    has_module_attr = any(
        isinstance(item, ast.Attribute) and item.attr in {"__module__", "__qualname__"}
        for item in candidates
    )
    has_cli = any(
        isinstance(item, ast.Constant)
        and isinstance(item.value, str)
        and item.value.startswith("legalforecast.cli")
        for item in candidates
    )
    return has_module_attr and has_cli


def _authenticated_profiles(path: Path, relative: str) -> list[dict[str, object]]:
    tree = parse_module(path, filename=relative)
    if tree is None:
        return []
    profiles: list[dict[str, object]] = []
    for node in ast.walk(tree):
        assigned = _assigned_name_value(node)
        if assigned is None:
            continue
        name, value = assigned
        if isinstance(value, (ast.Tuple, ast.List)):
            paths = [
                element.value
                for element in value.elts
                if isinstance(element, ast.Constant)
                and isinstance(element.value, str)
                and _PYTHON_PATH.fullmatch(element.value)
            ]
            if paths and ("SOURCE" in name or "PATHS" in name):
                profiles.append(
                    {
                        "file": relative,
                        "kind": "source-paths",
                        "name": name,
                        "paths": paths,
                    }
                )
        if isinstance(value, ast.Dict):
            mapping: dict[str, str] = {}
            for key, mapped in zip(value.keys, value.values, strict=True):
                if (
                    isinstance(key, ast.Constant)
                    and isinstance(mapped, ast.Constant)
                    and isinstance(key.value, str)
                    and isinstance(mapped.value, str)
                    and _PYTHON_PATH.fullmatch(key.value)
                    and _SHA256.fullmatch(mapped.value)
                ):
                    mapping[key.value] = mapped.value
            if mapping:
                profiles.append(
                    {
                        "file": relative,
                        "kind": "source-sha256",
                        "name": name,
                        "paths": sorted(mapping),
                    }
                )
    return profiles


def _assigned_name_value(node: ast.AST) -> tuple[str, ast.AST] | None:
    if isinstance(node, ast.Assign) and len(node.targets) == 1:
        target = node.targets[0]
        if isinstance(target, ast.Name):
            return target.id, node.value
        return None
    if (
        isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.value is not None
    ):
        return node.target.id, node.value
    return None
