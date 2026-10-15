"""Case-scoped native workers retain the full locked recovery census."""

from __future__ import annotations

import ast
import os
import textwrap
from pathlib import Path
from types import SimpleNamespace

import pytest

WORKFLOW = (
    Path(__file__).resolve().parents[1] / ".github/workflows/run-benchmark.yaml"
).read_text(encoding="utf-8")
MATRIX_STEP = WORKFLOW.split("      - name: Build dynamic logical-cell matrices", 1)[1]
MATRIX_SOURCE = textwrap.dedent(
    MATRIX_STEP.split("          uv run python - <<'PY'\n", 1)[1].split(
        "          PY\n", 1
    )[0]
)
MATRIX_AST = ast.parse(MATRIX_SOURCE)


def _execute(nodes: list[ast.stmt], scope: dict[str, object]) -> None:
    exec(
        compile(ast.Module(body=nodes, type_ignores=[]), "workflow-matrix", "exec"),
        scope,
    )


def test_smoke_selector_rejects_unknown_locked_case(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selector_index = next(
        i
        for i, node in enumerate(MATRIX_AST.body)
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "selected_case_id"
    )
    nodes = MATRIX_AST.body[selector_index : selector_index + 2]
    forecast = SimpleNamespace(cases=[SimpleNamespace(case_id="case-a")])
    scope: dict[str, object] = {"os": os, "forecast": forecast}
    monkeypatch.setenv("TERMINAL_CASE_ID", "absent")
    with pytest.raises(SystemExit, match="absent from the locked forecast release"):
        _execute(nodes, scope)
    monkeypatch.setenv("TERMINAL_CASE_ID", "case-a")
    _execute(nodes, scope)
    assert scope["forecast"] is forecast
    assert len(forecast.cases) == 1


@pytest.mark.parametrize(
    ("mode", "selector", "expected"),
    [
        ("native", "case-a", ["case-a"]),
        ("native", "", ["case-a", "case-c"]),
        ("claude-code-terminal", "case-a", ["case-a", "case-c"]),
    ],
)
def test_scope_follows_full_census_restoration(
    monkeypatch: pytest.MonkeyPatch, mode: str, selector: str, expected: list[str]
) -> None:
    restore_index = next(
        i
        for i, node in enumerate(MATRIX_AST.body)
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and ast.unparse(node.value.func) == "recovery['prepare']"
    )
    nodes = MATRIX_AST.body[restore_index : restore_index + 2]
    seen: list[str] = []

    def restore(
        matrices: dict[str, list[dict[str, str]]],
        identity: str,
        input_root: Path,
        restored_root: Path,
    ) -> None:
        assert identity == "same-full-run-identity"
        assert input_root.name == "lfb-locked-inputs"
        assert restored_root.name == "lfb-restored-bundle"
        rows = matrices["anthropic"]
        seen.extend(row["case_id"] for row in rows)
        # Model an already completed case imported from the smoke source run.
        rows[:] = [row for row in rows if row["case_id"] != "case-b"]

    matrices = {
        "anthropic": [{"case_id": case} for case in ("case-a", "case-b", "case-c")]
    }
    monkeypatch.setenv("EXECUTION_MODE", mode)
    scope: dict[str, object] = {
        "os": os,
        "Path": Path,
        "recovery": {"prepare": restore},
        "matrices": matrices,
        "run_identity_sha256": "same-full-run-identity",
        "selected_case_id": selector,
    }
    _execute(nodes, scope)
    assert seen == ["case-a", "case-b", "case-c"]
    assert [row["case_id"] for row in matrices["anthropic"]] == expected
    identity = next(
        node
        for node in MATRIX_AST.body
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "run_identity_sha256"
    )
    assert "selected_case_id" not in ast.unparse(identity)
    assert "TERMINAL_CASE_ID" not in ast.unparse(identity)
