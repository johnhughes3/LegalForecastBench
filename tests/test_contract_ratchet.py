from __future__ import annotations

import json
import textwrap
from pathlib import Path

from legalforecast.contracts.ratchet import (
    BaselineEntry,
    build_baseline,
    find_new_violations,
    load_baseline,
    scan_repository,
)


def test_ratchet_flags_each_forbidden_class(tmp_path: Path) -> None:
    _write(
        tmp_path / "legalforecast" / "sample.py",
        """
        import hashlib

        def _canonical_json_bytes(value: object) -> bytes:
            return b"{}"

        def build_digest() -> str:
            canonical_bytes = _canonical_json_bytes(
                {"schema_version": "legalforecast.sample.v1"}
            )
            return hashlib.sha256(canonical_bytes).hexdigest()
        """,
    )

    findings = scan_repository(tmp_path)

    assert {(finding.rule, finding.subject) for finding in findings} >= {
        ("private_commitment_helper", "_canonical_json_bytes"),
        ("direct_commitment_hash", "hashlib.sha256(canonical_bytes)"),
        ("inline_schema_literal", "legalforecast.sample.v1"),
    }


def test_ratchet_allows_reviewed_baseline_and_inline_exception(tmp_path: Path) -> None:
    _write(
        tmp_path / "legalforecast" / "allowed.py",
        """
        # contract-ratchet: allow non-persisted fixture canonicalization
        def _canonical_json_bytes(value: object) -> bytes:
            return b"{}"
        """,
    )
    _write(
        tmp_path / "legalforecast" / "new_violation.py",
        """
        NEW_SCHEMA = "legalforecast.new.violation.v1"
        """,
    )

    findings = scan_repository(tmp_path)
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(
        json.dumps(
            [
                {
                    "rule": "inline_schema_literal",
                    "path": "legalforecast/new_violation.py",
                    "subject": "legalforecast.new.violation.v1",
                    "reason": "reviewed legacy holdover",
                }
            ]
        ),
        encoding="utf-8",
    )

    baseline = load_baseline(baseline_path)
    violations = find_new_violations(findings, baseline)

    assert violations == ()


def test_build_baseline_requires_explicit_reason_on_reload(tmp_path: Path) -> None:
    _write(
        tmp_path / "scripts" / "schema_tool.py",
        """
        SCHEMA_VERSION = "legalforecast.tool.schema.v1"
        """,
    )

    findings = scan_repository(tmp_path)
    generated = build_baseline(findings)

    assert generated == (
        BaselineEntry(
            rule="inline_schema_literal",
            path="scripts/schema_tool.py",
            subject="legalforecast.tool.schema.v1",
            reason="legacy schema literal pending registry import",
        ),
    )


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")


def test_allow_marker_does_not_reach_past_the_next_line(tmp_path: Path) -> None:
    """One marker excuses its own line and the next, never a third.

    Regression: `_allowed_lines` records both the marker line and the line
    below it, and `_record` additionally accepted `line - 1`, so a single
    marker silently suppressed findings up to two lines below itself.
    """

    _write(
        tmp_path / "legalforecast" / "scope.py",
        """
        # contract-ratchet: allow reviewed exception
        COVERED = "legalforecast.covered.v1"
        NOT_COVERED = "legalforecast.not_covered.v1"
        """,
    )

    subjects = {finding.subject for finding in scan_repository(tmp_path)}

    assert "legalforecast.covered.v1" not in subjects
    assert "legalforecast.not_covered.v1" in subjects
