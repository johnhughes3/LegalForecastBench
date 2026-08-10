# pyright: reportPrivateUsage=false

from __future__ import annotations

import base64
import json
import os
from pathlib import Path

import legalforecast.cli as cli
import legalforecast.ingestion.exact100_zero_cost_recovery_cli as recovery_cli
import pytest
from legalforecast.ingestion.courtlistener_client import (
    COURTLISTENER_BASE_URL_ENV,
    CourtListenerClient,
    CourtListenerConfig,
    CourtListenerFixtureTransport,
)
from legalforecast.ingestion.exact100_zero_cost_recovery import (
    Exact100ZeroCostRecoveryResult,
    issue_exact100_zero_cost_recovery_request,
)
from legalforecast.ingestion.free_document_downloader import FixtureFreeDocumentSource
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


def _command(*, selection: Path, plan: Path, output: Path) -> list[str]:
    return [
        "acquisition",
        "recover-exact100-target-document-zero-cost",
        "--selection",
        str(selection),
        "--plan",
        str(plan),
        "--output-root",
        str(output),
    ]


def _fixture_client(fixture: Path) -> CourtListenerClient:
    return CourtListenerClient(
        config=CourtListenerConfig(),
        transport=CourtListenerFixtureTransport.from_jsonl(fixture),
        max_retries=0,
    )


def _run_fixture(
    *,
    selection: Path,
    plan: Path,
    output: Path,
    fixture: Path,
    public_document_source: FixtureFreeDocumentSource | None = None,
) -> int:
    return recovery_cli._run_with_test_dependencies(
        selection_path=selection,
        plan_path=plan,
        output_root=output,
        courtlistener=_fixture_client(fixture),
        public_document_source=public_document_source,
    )


def test_zero_cost_recovery_test_seam_404_resumes_without_a_get(
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
        _run_fixture(selection=selection, plan=plan, output=output, fixture=fixture)
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
    assert cli.main(_command(selection=selection, plan=plan, output=output)) == 0


def test_zero_cost_recovery_test_seam_public_handoff_is_not_terminal(
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
    public_document_source = FixtureFreeDocumentSource(
        {
            "https://storage.courtlistener.com/recap/2026/08/09/480673755.pdf": (
                b"%PDF-1.7 public memorandum"
            )
        }
    )
    output = tmp_path / "recovery"
    command = _command(selection=selection, plan=plan, output=output)

    assert (
        _run_fixture(
            selection=selection,
            plan=plan,
            output=output,
            fixture=fixture,
            public_document_source=public_document_source,
        )
        == 0
    )
    assert (output / "public-document-manifest.json").is_file()
    assert not (output / "recovery-receipt.json").exists()
    assert list((output / "documents").rglob("*.pdf"))
    fixture.unlink()
    assert cli.main(command) == 0
    if hasattr(os, "mkfifo"):
        os.mkfifo(output / "documents" / "unexpected.fifo")
        assert cli.main(command) == 2


def test_successor_recovery_replay_rejects_nonterminal_public_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selection_bytes = _selection()
    plan_bytes = _plan(selection_bytes)
    request = issue_exact100_zero_cost_recovery_request(
        selection_bytes=selection_bytes,
        plan_bytes=plan_bytes,
    )
    public_result = Exact100ZeroCostRecoveryResult(
        request=request,
        public_document_manifest={
            "candidate_id": "72449171",
            "source_document_id": "480673755",
            "terminal_exclusion_authority": False,
        },
        public_document_manifest_bytes=b"public handoff",
    )
    monkeypatch.setattr(
        recovery_cli,
        "_execute_terminal_recovery_with_verifier",
        lambda **_kwargs: public_result,
    )

    with pytest.raises(
        recovery_cli.Exact100ZeroCostRecoveryCliError,
        match="not terminally unavailable",
    ):
        recovery_cli.execute_terminal_recovery_for_successor(
            selection_bytes=selection_bytes,
            plan_bytes=plan_bytes,
        )


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
    command = _command(selection=selection, plan=plan, output=output)
    assert (
        _run_fixture(selection=selection, plan=plan, output=output, fixture=fixture)
        == 0
    )
    output.joinpath("recovery-receipt.json").write_bytes(b"{}\n")

    assert cli.main(command) == 2


def test_zero_cost_recovery_test_seam_fixture_404_requires_explicit_response_bytes(
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

    with pytest.raises(
        recovery_cli.Exact100ZeroCostRecoveryCliError,
        match="exact replayable response observation",
    ):
        _run_fixture(selection=selection, plan=plan, output=output, fixture=fixture)
    assert not output.exists()


def test_zero_cost_recovery_cli_requires_canonical_courtlistener_rest_base(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selection_bytes = _selection()
    selection = tmp_path / "selection.jsonl"
    plan = tmp_path / "plan.json"
    selection.write_bytes(selection_bytes)
    plan.write_bytes(_plan(selection_bytes))
    output = tmp_path / "recovery"
    monkeypatch.setenv(
        COURTLISTENER_BASE_URL_ENV,
        "https://www.courtlistener.com/not-the-rest-api",
    )

    assert cli.main(_command(selection=selection, plan=plan, output=output)) == 2
    assert not output.exists()


def test_zero_cost_recovery_cli_rejects_incomplete_terminal_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selection_bytes = _selection()
    selection = tmp_path / "selection.jsonl"
    plan = tmp_path / "plan.json"
    selection.write_bytes(selection_bytes)
    plan_bytes = _plan(selection_bytes)
    plan.write_bytes(plan_bytes)
    output = tmp_path / "recovery"
    request = issue_exact100_zero_cost_recovery_request(
        selection_bytes=selection_bytes,
        plan_bytes=plan_bytes,
    )

    def _incomplete_terminal_result(
        **_kwargs: object,
    ) -> Exact100ZeroCostRecoveryResult:
        return Exact100ZeroCostRecoveryResult(
            request=request,
            receipt_bytes=b"receipt",
        )

    monkeypatch.setattr(
        recovery_cli,
        "execute_exact100_zero_cost_recovery",
        _incomplete_terminal_result,
    )

    with pytest.raises(
        recovery_cli.Exact100ZeroCostRecoveryCliError,
        match=r"terminal recovery lacks required output: recovery-run-card\.json",
    ):
        recovery_cli._run_with_test_dependencies(
            selection_path=selection,
            plan_path=plan,
            output_root=output,
            courtlistener=CourtListenerClient(
                transport=CourtListenerFixtureTransport(()), max_retries=0
            ),
        )
    assert not output.exists()


def test_zero_cost_recovery_cli_resolves_symlinked_input_overlap(
    tmp_path: Path,
) -> None:
    selection_bytes = _selection()
    real_root = tmp_path / "real-inputs"
    real_root.mkdir()
    selection = real_root / "selection.jsonl"
    plan = real_root / "plan.json"
    selection.write_bytes(selection_bytes)
    plan.write_bytes(_plan(selection_bytes))
    alias_root = tmp_path / "aliased-inputs"
    alias_root.symlink_to(real_root, target_is_directory=True)

    with pytest.raises(
        recovery_cli.Exact100ZeroCostRecoveryCliError,
        match="overlaps immutable input",
    ):
        recovery_cli._run_with_test_dependencies(
            selection_path=selection,
            plan_path=plan,
            output_root=alias_root,
            courtlistener=CourtListenerClient(
                transport=CourtListenerFixtureTransport(()), max_retries=0
            ),
        )


def test_zero_cost_recovery_cli_rejects_fixture_404_before_terminal_authority(
    tmp_path: Path,
) -> None:
    selection_bytes = _selection()
    selection = tmp_path / "selection.jsonl"
    plan = tmp_path / "plan.json"
    selection.write_bytes(selection_bytes)
    plan.write_bytes(_plan(selection_bytes))
    fixture = tmp_path / "fabricated-responses.jsonl"
    _write_fixture(
        fixture,
        [
            _response(
                path="/recap-documents/480673755/",
                status_code=404,
                payload={"detail": "fabricated"},
            )
        ],
    )
    output = tmp_path / "recovery"

    with pytest.raises(SystemExit) as excinfo:
        cli.main(
            [
                *_command(selection=selection, plan=plan, output=output),
                "--fixture-courtlistener-responses",
                str(fixture),
            ]
        )

    assert excinfo.value.code == 2
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
    command = _command(selection=selection, plan=plan, output=output)
    assert (
        _run_fixture(selection=selection, plan=plan, output=output, fixture=fixture)
        == 0
    )
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
    for forbidden in (
        "--candidate-id",
        "--document-id",
        "--fixture-courtlistener-responses",
        "--fixture-public-documents",
        "--pacer",
        "--recap-fetch",
        "--fee",
    ):
        assert forbidden not in help_text
