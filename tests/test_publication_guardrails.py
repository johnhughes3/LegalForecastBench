from __future__ import annotations

import json
from pathlib import Path

import pytest
from legalforecast.publication.publication_guardrails import (
    PublicationGuardrailCode,
    PublicationGuardrailConfig,
    PublicationGuardrailError,
    enforce_publication_guardrails,
    scan_publication_guardrails,
)
from legalforecast.publication.publication_guardrails import (
    main as publication_guardrails_main,
)


def test_publication_guardrails_accept_public_safe_outputs(tmp_path: Path) -> None:
    public_dir = tmp_path / "public"
    _write_text(public_dir / "report" / "leaderboard.json", '{"rows": []}\n')
    _write_text(
        public_dir / "unit-scores.jsonl",
        '{"raw_output_sha256": "sha256:abc", "model_id": "fixture"}\n',
    )

    assert (
        scan_publication_guardrails(
            PublicationGuardrailConfig(public_paths=(public_dir,))
        )
        == ()
    )


def test_publication_guardrails_reject_raw_private_public_paths(
    tmp_path: Path,
) -> None:
    public_dir = tmp_path / "public"
    _write_text(public_dir / "source-documents" / "case-1" / "order.pdf", "%PDF")

    with pytest.raises(PublicationGuardrailError) as exc_info:
        enforce_publication_guardrails(
            PublicationGuardrailConfig(public_paths=(public_dir,))
        )

    codes = {finding.code for finding in exc_info.value.findings}
    assert PublicationGuardrailCode.PRIVATE_PATH in codes
    assert PublicationGuardrailCode.RAW_DOCUMENT in codes


def test_publication_guardrails_reject_secrets_provider_ids_and_hidden_files(
    tmp_path: Path,
) -> None:
    public_dir = tmp_path / "public"
    _write_text(
        public_dir / "scores.json",
        json.dumps(
            {
                "CASE_DEV_API_KEY": "case-dev-key",
                "provider_account_id": "acct_fixture_123",
            }
        ),
    )
    _write_text(public_dir / ".env", "OPENAI_API_KEY=sk-fixture-secret\n")

    findings = scan_publication_guardrails(
        PublicationGuardrailConfig(public_paths=(public_dir,))
    )
    codes = {finding.code for finding in findings}

    assert PublicationGuardrailCode.SECRET in codes
    assert PublicationGuardrailCode.PROVIDER_ACCOUNT_ID in codes
    assert PublicationGuardrailCode.HIDDEN_FILE in codes


def test_publication_guardrails_scan_workflow_logs(tmp_path: Path) -> None:
    log_path = tmp_path / "runner-log.jsonl"
    _write_text(
        log_path,
        '{"message": "Authorization: Bearer secret-token-12345"}\n'
        '{"message": "source-documents/cycle/case/doc.pdf"}\n',
    )

    findings = scan_publication_guardrails(
        PublicationGuardrailConfig(log_paths=(log_path,))
    )
    codes = {finding.code for finding in findings}

    assert PublicationGuardrailCode.SECRET in codes
    assert PublicationGuardrailCode.PRIVATE_PATH in codes


def test_publication_guardrails_cli_reports_findings(
    tmp_path: Path,
    capsys,
) -> None:
    public_dir = tmp_path / "public"
    _write_text(public_dir / "audit-only.json", '{"status": "audit_only"}\n')

    assert publication_guardrails_main(["--public-dir", str(public_dir)]) == 1
    summary = json.loads(capsys.readouterr().out)

    assert summary["finding_count"] >= 1
    assert {finding["code"] for finding in summary["findings"]} >= {
        "audit_only_material"
    }


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
