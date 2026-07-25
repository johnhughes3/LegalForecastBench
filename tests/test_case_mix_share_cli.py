from __future__ import annotations

import hashlib
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from legalforecast.cli import build_parser


def test_plan_public_downloads_parses_case_mix_share_as_exact_decimal(
    tmp_path: Path,
) -> None:
    args = build_parser().parse_args(
        _plan_public_downloads_args("0.299999999999999999", tmp_path)
    )

    assert args.max_case_mix_share == Decimal("0.299999999999999999")
    assert isinstance(args.max_case_mix_share, Decimal)


@pytest.mark.parametrize(
    "value",
    (
        "0",
        "-0.1",
        "1.000000000000000001",
        "NaN",
        "sNaN",
        "Infinity",
        "-Infinity",
        "not-a-decimal",
    ),
)
def test_plan_public_downloads_rejects_invalid_case_mix_share_at_parse_time(
    value: str,
    capsys: Any,
    tmp_path: Path,
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        build_parser().parse_args(_plan_public_downloads_args(value, tmp_path))

    assert exc_info.value.code == 2
    error = capsys.readouterr().err
    assert "--max-case-mix-share" in error
    assert "must be a finite decimal greater than 0 and at most 1" in error


def test_plan_public_downloads_help_documents_exact_floor_cap(
    capsys: Any,
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        build_parser().parse_args(["acquisition", "plan-public-downloads", "--help"])

    assert exc_info.value.code == 0
    output = capsys.readouterr().out
    assert "Target-relative allowance" in output
    assert "per-bucket cap is" in output
    assert "floor(target clean cases multiplied by this decimal" in output
    assert "share)" in output
    assert "shares producing a zero cap are" in output
    assert "rejected" in output


def _plan_public_downloads_args(share: str, tmp_path: Path) -> list[str]:
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    manifest = snapshot / "manifest.json"
    manifest.write_text("{}\n", encoding="utf-8")
    return [
        "acquisition",
        "plan-public-downloads",
        "--output-root",
        "unused-output-root",
        "--snapshot",
        str(snapshot),
        "--expected-snapshot-manifest-sha256",
        hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "--expected-cycle-hash",
        "unused-cycle-hash",
        f"--max-case-mix-share={share}",
    ]
