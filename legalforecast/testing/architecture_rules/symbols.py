"""Source-span measurements for tracked Python files."""

from __future__ import annotations

import ast
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class FileMetrics:
    """Size and largest top-level symbol for one Python file."""

    path: str
    line_count: int
    nonblank_line_count: int
    top_level_definition_count: int
    largest_symbol: str
    largest_symbol_lines: int


def measure_python_file(root: Path, relative: str) -> FileMetrics | None:
    """Return structural metrics for ``relative``, or ``None`` if it cannot parse."""

    path = root / relative
    try:
        source = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        tree = ast.parse(source, filename=relative)
    except SyntaxError:
        return None
    definitions = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]
    largest_name = ""
    largest_lines = 0
    for node in definitions:
        span = line_count(node)
        if span > largest_lines:
            largest_name = node.name
            largest_lines = span
    return FileMetrics(
        path=relative,
        line_count=len(source.splitlines()),
        nonblank_line_count=sum(bool(line.strip()) for line in source.splitlines()),
        top_level_definition_count=len(definitions),
        largest_symbol=largest_name,
        largest_symbol_lines=largest_lines,
    )


def line_count(node: ast.AST) -> int:
    """Return the inclusive source-line span of an AST node."""

    end = getattr(node, "end_lineno", None)
    start = getattr(node, "lineno", None)
    if not isinstance(start, int) or not isinstance(end, int):
        raise ValueError("AST node lacks source locations")
    return end - start + 1


def python_paths(package_root: Path) -> Iterable[str]:
    """Yield POSIX paths of Python files under ``package_root``.

    Paths are relative to ``package_root``'s parent.
    """

    root = package_root.parent
    for path in sorted(package_root.rglob("*.py")):
        yield path.relative_to(root).as_posix()
