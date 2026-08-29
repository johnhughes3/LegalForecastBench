from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from legalforecast.hugging_face_publication import (
    OFFICIAL_HF_PUBLICATION_SCHEMA_VERSION,
    OFFICIAL_HF_PUBLICATION_SUPPLEMENTARY_SCHEMA_VERSION,
    OfficialHFPublicationConfig,
    OfficialHFPublicationError,
    build_official_hf_publication,
    validate_official_hf_publication,
)
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
from legalforecast.reporting.result_class import (
    SUPPLEMENTARY_CAVEAT,
    SUPPLEMENTARY_MARKER,
)
from tests.test_static_result_sites import (
    SUPPLEMENTARY_MODEL_ID,
    write_official_report_fixture,
    write_supplementary_report_fixture,
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


def test_builds_native_manually_gated_hf_package(tmp_path: Path) -> None:
    official = write_official_report_fixture(tmp_path)
    result = build_official_hf_publication(
        OfficialHFPublicationConfig(
            official_artifacts_dir=official,
            output_dir=tmp_path / "hugging-face",
            release_version="cycle-1.0.0",
            dataset_repository="example/legalforecastbench",
        )
    )

    card = result.readme_path.read_text(encoding="utf-8")
    evaluation = result.eval_path.read_text(encoding="utf-8")
    manifest = json.loads(result.publication_manifest_path.read_text(encoding="utf-8"))
    assert "gated: manual" in card
    assert "I agree to the Controlled-Access Terms: checkbox" in card
    assert "submit to the jurisdiction of the court" in card
    assert "delete or destroy information" in card
    assert "reasonable precautions not to republish" in card
    assert "evaluation_framework: legalforecastbench" in evaluation
    assert 'id: "legalforecast_mtd_fixture_cycle"' in evaluation
    assert manifest["release_path"] == "releases/cycle-1.0.0/fixture-cycle"
    assert manifest["manual_gate"]["mode"] == "manual"
    # An official-only package keeps the frozen -v1 manifest shape exactly.
    assert manifest["schema_version"] == OFFICIAL_HF_PUBLICATION_SCHEMA_VERSION
    assert "supplementary_path" not in manifest
    assert result.supplementary_artifact_index_sha256 is None
    assert validate_official_hf_publication(result.output_dir) == result


def test_hf_publication_separates_the_supplementary_split_and_carries_the_caveat(
    tmp_path: Path,
) -> None:
    official = write_official_report_fixture(tmp_path)
    supplementary = write_supplementary_report_fixture(tmp_path)
    release_path = "releases/cycle-1.0.0/fixture-cycle"

    result = build_official_hf_publication(
        OfficialHFPublicationConfig(
            official_artifacts_dir=official,
            output_dir=tmp_path / "hugging-face",
            release_version="cycle-1.0.0",
            dataset_repository="example/legalforecastbench",
            supplementary_artifacts_dir=supplementary,
        )
    )

    manifest = json.loads(result.publication_manifest_path.read_text(encoding="utf-8"))
    card = result.readme_path.read_text(encoding="utf-8")
    assert (
        manifest["schema_version"]
        == OFFICIAL_HF_PUBLICATION_SUPPLEMENTARY_SCHEMA_VERSION
    )
    assert manifest["supplementary_path"] == f"{release_path}/supplementary"
    assert (
        result.supplementary_artifact_index_sha256
        == manifest["supplementary_artifact_index_sha256"]
    )

    official_units = (
        result.output_dir / release_path / "aggregate" / "unit-scores.jsonl"
    ).read_text(encoding="utf-8")
    supplementary_units = (
        result.output_dir / release_path / "supplementary" / "unit-scores.jsonl"
    ).read_text(encoding="utf-8")
    assert SUPPLEMENTARY_MODEL_ID not in official_units
    assert SUPPLEMENTARY_MODEL_ID in supplementary_units

    assert SUPPLEMENTARY_CAVEAT in card
    assert "config_name: fixture-cycle_supplementary" in card
    assert "split: supplementary" in card
    assert "gated: manual" in card
    assert "I agree to the Controlled-Access Terms: checkbox" in card
    assert "submit to the jurisdiction of the court" in card

    site = (result.output_dir / release_path / "site" / "index.html").read_text(
        encoding="utf-8"
    )
    assert f"{SUPPLEMENTARY_MODEL_ID}{SUPPLEMENTARY_MARKER}" in site
    assert validate_official_hf_publication(result.output_dir) == result


def test_hf_publication_refuses_supplementary_files_under_an_official_only_manifest(
    tmp_path: Path,
) -> None:
    official = write_official_report_fixture(tmp_path)
    result = build_official_hf_publication(
        OfficialHFPublicationConfig(
            official_artifacts_dir=official,
            output_dir=tmp_path / "hugging-face",
            release_version="cycle-1.0.0",
            dataset_repository="example/legalforecastbench",
        )
    )
    relative = "releases/cycle-1.0.0/fixture-cycle/supplementary/unit-scores.jsonl"
    smuggled = result.output_dir / relative
    smuggled.parent.mkdir(parents=True, exist_ok=True)
    smuggled.write_text(
        f'{{"model_id": "{SUPPLEMENTARY_MODEL_ID}"}}\n', encoding="utf-8"
    )
    manifest = json.loads(result.publication_manifest_path.read_text(encoding="utf-8"))
    manifest["artifacts"].append(
        {
            "path": relative,
            "sha256": "sha256:" + hashlib.sha256(smuggled.read_bytes()).hexdigest(),
            "size_bytes": smuggled.stat().st_size,
        }
    )
    result.publication_manifest_path.write_text(
        json.dumps(manifest, sort_keys=True), encoding="utf-8"
    )

    with pytest.raises(
        OfficialHFPublicationError,
        match="carries supplementary artifacts",
    ):
        validate_official_hf_publication(result.output_dir)


def test_hf_package_rejects_mutable_version_and_existing_output(
    tmp_path: Path,
) -> None:
    official = write_official_report_fixture(tmp_path)
    with pytest.raises(OfficialHFPublicationError, match="mutable revision"):
        OfficialHFPublicationConfig(
            official_artifacts_dir=official,
            output_dir=tmp_path / "hugging-face",
            release_version="main",
            dataset_repository="example/legalforecastbench",
        )

    destination = tmp_path / "existing"
    destination.mkdir()
    with pytest.raises(OfficialHFPublicationError, match="already exists"):
        build_official_hf_publication(
            OfficialHFPublicationConfig(
                official_artifacts_dir=official,
                output_dir=destination,
                release_version="cycle-1.0.0",
                dataset_repository="example/legalforecastbench",
            )
        )


def test_hf_package_validation_rejects_byte_drift(tmp_path: Path) -> None:
    official = write_official_report_fixture(tmp_path)
    result = build_official_hf_publication(
        OfficialHFPublicationConfig(
            official_artifacts_dir=official,
            output_dir=tmp_path / "hugging-face",
            release_version="cycle-1.0.0",
            dataset_repository="example/legalforecastbench",
        )
    )
    result.eval_path.write_text("name: replaced\n", encoding="utf-8")

    with pytest.raises(OfficialHFPublicationError, match=r"hash mismatch: eval\.yaml"):
        validate_official_hf_publication(result.output_dir)


def test_hf_package_validation_binds_release_identity(tmp_path: Path) -> None:
    official = write_official_report_fixture(tmp_path)
    result = build_official_hf_publication(
        OfficialHFPublicationConfig(
            official_artifacts_dir=official,
            output_dir=tmp_path / "hugging-face",
            release_version="cycle-1.0.0",
            dataset_repository="example/legalforecastbench",
        )
    )
    manifest = json.loads(result.publication_manifest_path.read_text(encoding="utf-8"))
    manifest["release_version"] = "cycle-1.0.1"
    result.publication_manifest_path.write_text(
        json.dumps(manifest, sort_keys=True), encoding="utf-8"
    )

    with pytest.raises(OfficialHFPublicationError, match="release_path does not match"):
        validate_official_hf_publication(result.output_dir)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
