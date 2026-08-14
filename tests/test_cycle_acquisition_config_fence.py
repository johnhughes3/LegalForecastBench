from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from legalforecast.config.fence import (
    BASELINE_PATH,
    BaselineEntry,
    find_baseline_growth,
    find_new_violations,
    load_ancestor_baseline,
    load_baseline,
    scan_repository,
)


def test_fence_flags_out_of_home_constant_and_type_construction(tmp_path: Path) -> None:
    _write(
        tmp_path / "legalforecast" / "ingestion" / "sample.py",
        """
        from legalforecast.config import SelectorModel

        SELECTOR_MODEL_PRIMARY = "openai:gpt-5.6-luna"
        DEFAULT_PURCHASE_COST_USD = "3.05"

        def build() -> object:
            return SelectorModel(
                provider="openai",
                model_id="gpt-5.6-luna",
                model_version_or_snapshot="gpt-5.6-luna",
            )
        """,
    )

    findings = scan_repository(tmp_path)

    assert {(finding.rule, finding.subject) for finding in findings} >= {
        ("acquisition_selection_constant", "SELECTOR_MODEL_PRIMARY"),
        ("acquisition_selection_constant", "DEFAULT_PURCHASE_COST_USD"),
        ("cycle_config_type_construction", "SelectorModel"),
    }


def test_fence_allows_reviewed_baseline_and_inline_exception(tmp_path: Path) -> None:
    _write(
        tmp_path / "legalforecast" / "ingestion" / "legacy.py",
        """
        DEFAULT_PURCHASE_COST_USD = "3.05"
        """,
    )
    _write(
        tmp_path / "legalforecast" / "ingestion" / "allowed.py",
        """
        # acquisition-config-fence: allow local fixture price for a unit test helper
        DEFAULT_PURCHASE_COST_USD = "0.00"
        """,
    )

    findings = scan_repository(tmp_path)
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(
        json.dumps(
            [
                {
                    "rule": "acquisition_selection_constant",
                    "path": "legalforecast/ingestion/legacy.py",
                    "subject": "DEFAULT_PURCHASE_COST_USD",
                    "reason": "Cycle 1 live constant",
                }
            ]
        ),
        encoding="utf-8",
    )

    violations = find_new_violations(findings, load_baseline(baseline_path))

    assert violations == ()


def test_repository_fence_has_no_unreviewed_violations() -> None:
    root = Path(__file__).resolve().parents[1]
    findings = scan_repository(root)
    baseline = load_baseline(root / BASELINE_PATH)

    assert find_new_violations(findings, baseline) == ()


def test_fence_baseline_may_only_shrink() -> None:
    previous = (
        BaselineEntry(
            rule="acquisition_selection_constant",
            path="legalforecast/ingestion/legacy.py",
            subject="DEFAULT_PURCHASE_COST_USD",
            reason="Cycle 1 live constant",
        ),
    )
    extra = BaselineEntry(
        rule="acquisition_selection_constant",
        path="legalforecast/ingestion/extra.py",
        subject="SELECTOR_MODEL_PRIMARY",
        reason="should not be allowed to grow",
    )
    grown = (*previous, extra)

    assert find_baseline_growth(grown, previous) == (extra,)
    assert find_baseline_growth(previous, previous) == ()
    assert find_baseline_growth((), previous) == ()


def test_repository_fence_baseline_does_not_grow_from_main() -> None:
    root = Path(__file__).resolve().parents[1]
    current = load_baseline(root / BASELINE_PATH)
    ancestor = load_ancestor_baseline(root, root / BASELINE_PATH)
    if ancestor is None:
        pytest.skip("fence_baseline.json is not on origin/main yet")
    assert find_baseline_growth(current, ancestor) == ()


def _write(path: Path, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(source).strip() + "\n", encoding="utf-8")
