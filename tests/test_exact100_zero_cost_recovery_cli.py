# pyright: reportPrivateUsage=false

from __future__ import annotations

import base64
import json
import os
from pathlib import Path

import legalforecast.cli as cli
import pytest
from legalforecast.ingestion.courtlistener_client import COURTLISTENER_BASE_URL_ENV
from tests.test_exact100_zero_cost_recovery import (
    _docket_entry_payload,
    _plan,
    _public_payload,
    _selection,
)


def _write_fixture(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _response(
    *, path: str, status_code: int, payload: dict[str, object]
) -> dict[str, object]:
    raw_body = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return {
        "method": "GET",
        "path": path,
        "params": {},
        "status_code": status_code,
        "payload": payload,
        "response_body_base64": base64.b64encode(raw_body).decode("ascii"),
    }


def _command(*, selection: Path, plan: Path, output: Path, fixture: Path) -> list[str]:
    return [
        "acquisition",
        "recover-exact100-target-document-zero-cost",
        "--selection",
        str(selection),
        "--plan",
        str(plan),
        "--output-root",
        str(output),
        "--fixture-courtlistener-responses",
        str(fixture),
    ]


def test_zero_cost_recovery_cli_404_is_fixture_only_and_resumes_without_a_get(
    tmp_path: Path,
) -> None:
    selection_bytes = _selection()
    selection = tmp_path / "selection.jsonl"
    plan = tmp_path / "plan.json"
    selection.write_bytes(selection_bytes)
    plan.write_bytes(_plan(selection_bytes))
    fixture = tmp_path / "responses.jsonl"
    _write_fixture(
        fixture,
        [
            _response(
                path="/recap-documents/480673755/",
                status_code=404,
                payload={"detail": "not found"},
            )
        ],
    )
    output = tmp_path / "recovery"

    assert (
        cli.main(
            _command(selection=selection, plan=plan, output=output, fixture=fixture)
        )
        == 0
    )
    assert {path.name for path in output.iterdir()} == {
        "recovery-request.json",
        "recovery-receipt.json",
        "recovery-run-card.json",
        "rest-observation.json",
        "rest-observation-transcript.jsonl",
        "rest-observation-response.bin",
    }
    fixture.unlink()
    assert (
        cli.main(
            _command(selection=selection, plan=plan, output=output, fixture=fixture)
        )
        == 0
    )


def test_zero_cost_recovery_cli_public_handoff_is_fixture_backed_and_not_terminal(
    tmp_path: Path,
) -> None:
    selection_bytes = _selection()
    selection = tmp_path / "selection.jsonl"
    plan = tmp_path / "plan.json"
    selection.write_bytes(selection_bytes)
    plan.write_bytes(_plan(selection_bytes))
    fixture = tmp_path / "responses.jsonl"
    _write_fixture(
        fixture,
        [
            _response(
                path="/recap-documents/480673755/",
                status_code=200,
                payload=_public_payload(),
            ),
            _response(
                path="/docket-entries/465468661/",
                status_code=200,
                payload=_docket_entry_payload(),
            ),
        ],
    )
    documents = tmp_path / "documents.json"
    documents.write_text(
        json.dumps(
            {
                "https://storage.courtlistener.com/recap/2026/08/09/480673755.pdf": (
                    base64.b64encode(b"%PDF-1.7 public memorandum").decode()
                )
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "recovery"
    command = _command(selection=selection, plan=plan, output=output, fixture=fixture)
    command.extend(("--fixture-public-documents", str(documents)))

    assert cli.main(command) == 0
    assert (output / "public-document-manifest.json").is_file()
    assert not (output / "recovery-receipt.json").exists()
    assert list((output / "documents").rglob("*.pdf"))
    fixture.unlink()
    documents.unlink()
    assert cli.main(command) == 0
    if hasattr(os, "mkfifo"):
        os.mkfifo(output / "documents" / "unexpected.fifo")
        assert cli.main(command) == 2


def test_zero_cost_recovery_cli_rejects_mixed_or_tampered_resume_output(
    tmp_path: Path,
) -> None:
    selection_bytes = _selection()
    selection = tmp_path / "selection.jsonl"
    plan = tmp_path / "plan.json"
    selection.write_bytes(selection_bytes)
    plan.write_bytes(_plan(selection_bytes))
    fixture = tmp_path / "responses.jsonl"
    _write_fixture(
        fixture,
        [
            _response(
                path="/recap-documents/480673755/",
                status_code=404,
                payload={"detail": "not found"},
            )
        ],
    )
    output = tmp_path / "recovery"
    command = _command(selection=selection, plan=plan, output=output, fixture=fixture)
    assert cli.main(command) == 0
    output.joinpath("recovery-receipt.json").write_bytes(b"{}\n")

    assert cli.main(command) == 2


def test_zero_cost_recovery_cli_fixture_404_requires_explicit_response_bytes(
    tmp_path: Path,
) -> None:
    selection_bytes = _selection()
    selection = tmp_path / "selection.jsonl"
    plan = tmp_path / "plan.json"
    selection.write_bytes(selection_bytes)
    plan.write_bytes(_plan(selection_bytes))
    fixture = tmp_path / "responses.jsonl"
    _write_fixture(
        fixture,
        [
            {
                "method": "GET",
                "path": "/recap-documents/480673755/",
                "params": {},
                "status_code": 404,
                "payload": {"detail": "not found"},
            }
        ],
    )
    output = tmp_path / "recovery"

    assert (
        cli.main(
            _command(selection=selection, plan=plan, output=output, fixture=fixture)
        )
        == 2
    )
    assert not output.exists()


def test_zero_cost_recovery_cli_requires_canonical_courtlistener_rest_base(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selection_bytes = _selection()
    selection = tmp_path / "selection.jsonl"
    plan = tmp_path / "plan.json"
    selection.write_bytes(selection_bytes)
    plan.write_bytes(_plan(selection_bytes))
    fixture = tmp_path / "responses.jsonl"
    _write_fixture(
        fixture,
        [
            _response(
                path="/recap-documents/480673755/",
                status_code=404,
                payload={"detail": "not found"},
            )
        ],
    )
    output = tmp_path / "recovery"
    monkeypatch.setenv(
        COURTLISTENER_BASE_URL_ENV,
        "https://www.courtlistener.com/not-the-rest-api",
    )

    assert (
        cli.main(
            _command(selection=selection, plan=plan, output=output, fixture=fixture)
        )
        == 2
    )
    assert not output.exists()


def test_zero_cost_recovery_cli_terminal_resume_requires_response_sidecar(
    tmp_path: Path,
) -> None:
    selection_bytes = _selection()
    selection = tmp_path / "selection.jsonl"
    plan = tmp_path / "plan.json"
    selection.write_bytes(selection_bytes)
    plan.write_bytes(_plan(selection_bytes))
    fixture = tmp_path / "responses.jsonl"
    _write_fixture(
        fixture,
        [
            _response(
                path="/recap-documents/480673755/",
                status_code=404,
                payload={"detail": "not found"},
            )
        ],
    )
    output = tmp_path / "recovery"
    command = _command(selection=selection, plan=plan, output=output, fixture=fixture)
    assert cli.main(command) == 0
    (output / "rest-observation-response.bin").unlink()

    assert cli.main(command) == 2


def test_zero_cost_recovery_cli_help_has_no_paid_or_identifier_switches(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.main(
            ["acquisition", "recover-exact100-target-document-zero-cost", "--help"]
        )
    assert excinfo.value.code == 0
    help_text = capsys.readouterr().out
    assert "test-only" in help_text
    for forbidden in (
        "--candidate-id",
        "--document-id",
        "--pacer",
        "--recap-fetch",
        "--fee",
    ):
        assert forbidden not in help_text
