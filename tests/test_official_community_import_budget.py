from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pytest


@dataclass(frozen=True, order=True)
class ImportEdge:
    importer: str
    imported: str


def _module_name(package_root: Path, source: Path) -> str:
    relative = source.relative_to(package_root.parent).with_suffix("")
    parts = relative.parts
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _reverse_community_imports(package_root: Path) -> set[ImportEdge]:
    edges: set[ImportEdge] = set()
    for source in package_root.rglob("*.py"):
        importer = _module_name(package_root, source)
        if importer == "legalforecast.multiharness" or importer.startswith(
            "legalforecast.multiharness."
        ):
            continue
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        for node in ast.walk(tree):
            imported_modules: list[str] = []
            if isinstance(node, ast.ImportFrom) and node.module is not None:
                imported_modules.append(node.module)
            elif isinstance(node, ast.Import):
                imported_modules.extend(alias.name for alias in node.names)
            for imported in imported_modules:
                if imported == "legalforecast.multiharness" or imported.startswith(
                    "legalforecast.multiharness."
                ):
                    edges.add(ImportEdge(importer=importer, imported=imported))
    return edges


def _load_budget(path: Path) -> set[ImportEdge]:
    payload = cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))
    assert (
        payload["schema_version"] == "legalforecast.official_community_import_budget.v1"
    )
    raw_entries = cast(list[dict[str, object]], payload["legacy_reverse_dependencies"])
    assert all(
        isinstance(entry.get("reason"), str) and entry["reason"]
        for entry in raw_entries
    )
    return {
        ImportEdge(
            importer=cast(str, entry["importer"]),
            imported=cast(str, entry["imported"]),
        )
        for entry in raw_entries
    }


def _assert_import_budget(package_root: Path, budgeted: set[ImportEdge]) -> None:
    actual = _reverse_community_imports(package_root)
    assert actual == budgeted, (
        "official code introduced an unbudgeted community dependency or the "
        f"reviewed baseline is stale: actual={sorted(actual)!r}, "
        f"budgeted={sorted(budgeted)!r}"
    )


def test_official_code_adds_no_unbudgeted_community_imports() -> None:
    root = Path(__file__).parents[1]
    budgeted = _load_budget(
        root / "tests" / "fixtures" / "official_community_import_budget.json"
    )

    _assert_import_budget(root / "legalforecast", budgeted)


def test_new_reverse_dependency_exceeds_the_budget(tmp_path: Path) -> None:
    package_root = tmp_path / "legalforecast"
    community_root = package_root / "multiharness"
    community_root.mkdir(parents=True)
    (package_root / "official.py").write_text(
        "from legalforecast.multiharness.spec import CanonicalTask\n",
        encoding="utf-8",
    )
    (community_root / "spec.py").write_text(
        "class CanonicalTask:\n    pass\n",
        encoding="utf-8",
    )

    with pytest.raises(AssertionError, match="unbudgeted community dependency"):
        _assert_import_budget(package_root, set())


def test_community_to_official_and_same_track_imports_are_permitted(
    tmp_path: Path,
) -> None:
    package_root = tmp_path / "legalforecast"
    community_root = package_root / "multiharness"
    community_root.mkdir(parents=True)
    (package_root / "official.py").write_text(
        "from legalforecast.protocol import freeze\n",
        encoding="utf-8",
    )
    (community_root / "adapter.py").write_text(
        "from legalforecast.protocol import freeze\n"
        "from legalforecast.multiharness import spec\n",
        encoding="utf-8",
    )

    _assert_import_budget(package_root, set())
