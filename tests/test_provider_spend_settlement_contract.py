"""Keep both spend authorities on the same aggregate settlement rule."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTHORITIES = (
    ("legalforecast/evals/provider_spend_control.py", "SqliteProviderSpendAuthority"),
    (
        "legalforecast/evals/provider_spend_dynamodb.py",
        "DynamoDbProviderSpendAuthority",
    ),
)
SETTLEMENT_METHODS = ("record_response", "reconcile_ambiguous")


def test_all_provider_settlement_paths_use_shared_budget_rule() -> None:
    for relative_path, class_name in AUTHORITIES:
        module = ast.parse((ROOT / relative_path).read_text(encoding="utf-8"))
        authority = next(
            node
            for node in module.body
            if isinstance(node, ast.ClassDef) and node.name == class_name
        )
        for method_name in SETTLEMENT_METHODS:
            method = next(
                node
                for node in authority.body
                if isinstance(node, ast.FunctionDef) and node.name == method_name
            )
            calls = (node for node in ast.walk(method) if isinstance(node, ast.Call))
            called_names = {
                call.func.id if isinstance(call.func, ast.Name) else call.func.attr
                for call in calls
                if isinstance(call.func, (ast.Name, ast.Attribute))
            }
            assert {"SettlementBudget", "fits_cap"} <= called_names, (
                f"{relative_path}:{class_name}.{method_name} bypasses the shared "
                "aggregate cap rule"
            )
