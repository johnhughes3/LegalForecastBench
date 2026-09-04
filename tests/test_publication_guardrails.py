from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from legalforecast.hugging_face_publication import (
    OFFICIAL_HF_PUBLICATION_SCHEMA_VERSION,
    OFFICIAL_HF_PUBLICATION_SUPPLEMENTARY_SCHEMA_VERSION,
    RETAINED_HF_PUBLICATION_SCHEMA_VERSION,
    OfficialHFPublicationConfig,
    OfficialHFPublicationError,
    RetainedHFPublicationConfig,
    build_official_hf_publication,
    build_retained_hf_publication,
    validate_official_hf_publication,
    validate_retained_hf_publication,
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
    _refresh_official_artifact_manifests,
    write_official_report_fixture,
    write_supplementary_report_fixture,
)

_RELEASE_PATH = "releases/cycle-1.0.0/fixture-cycle"


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


def test_builds_retained_fan_in_hf_package_from_sanitized_outputs(
    tmp_path: Path,
) -> None:
    identity = {
        "run_manifest_id": "cycle-1-run",
        "run_manifest_sha256": "a" * 64,
        "forecast_release_id": "forecast-cycle-1",
        "forecast_release_digest": "b" * 64,
        "labels_release_id": "labels-cycle-1",
        "labels_release_digest": "c" * 64,
        "labels_forecast_release_digest": "d" * 64,
        "run_identity_sha256": "e" * 64,
        "model_registry_sha256": "f" * 64,
        "models": [
            {
                "model_key": "openai:fixture",
                "model_registry_entry_sha256": "1" * 64,
                "served_model_version": "fixture-v1",
            }
        ],
    }
    score_path = tmp_path / "score.json"
    _write_json(
        score_path,
        {"identity": identity, "summaries": [{"model_id": "fixture"}]},
    )
    unit_scores_path = tmp_path / "unit-scores.jsonl"
    _write_text(
        unit_scores_path,
        json.dumps({"model_id": "fixture", "unit_id": "unit-1", "case_id": "case-1"})
        + "\n",
    )
    report_dir = tmp_path / "report"
    _write_json(report_dir / "leaderboard.json", {"provenance": identity})
    for name in ("leaderboard.csv", "leaderboard.md", "leaderboard.html"):
        _write_text(report_dir / name, f"{name}\n")

    result = build_retained_hf_publication(
        RetainedHFPublicationConfig(
            score_path=score_path,
            unit_scores_path=unit_scores_path,
            report_dir=report_dir,
            output_dir=tmp_path / "hugging-face-retained",
            cycle_id="cycle-1",
            release_version="cycle-1.1.0",
            dataset_repository="example/legalforecastbench",
        )
    )

    manifest = json.loads(result.publication_manifest_path.read_text(encoding="utf-8"))
    release_root = result.output_dir / "releases/cycle-1.1.0/cycle-1"
    assert manifest["schema_version"] == RETAINED_HF_PUBLICATION_SCHEMA_VERSION
    assert manifest["manual_gate"]["mode"] == "manual"
    assert (
        release_root / "aggregate/scores.json"
    ).read_bytes() == score_path.read_bytes()
    assert (release_root / "aggregate/report/leaderboard.html").is_file()
    assert (release_root / "site/index.html").is_file()
    assert validate_retained_hf_publication(result.output_dir) == result


def test_retained_hf_package_refuses_report_identity_drift(tmp_path: Path) -> None:
    identity = {
        "run_manifest_id": "run",
        "run_manifest_sha256": "a" * 64,
        "forecast_release_id": "forecast",
        "forecast_release_digest": "b" * 64,
        "labels_release_id": "labels",
        "labels_release_digest": "c" * 64,
        "labels_forecast_release_digest": "d" * 64,
        "run_identity_sha256": "e" * 64,
        "model_registry_sha256": "f" * 64,
        "models": [{"model_key": "openai:fixture"}],
    }
    score_path = tmp_path / "score.json"
    _write_json(
        score_path,
        {"identity": identity, "summaries": [{"model_id": "fixture"}]},
    )
    _write_text(
        tmp_path / "unit-scores.jsonl",
        '{"model_id":"fixture","unit_id":"u","case_id":"c"}\n',
    )
    report_dir = tmp_path / "report"
    _write_json(
        report_dir / "leaderboard.json",
        {"provenance": {**identity, "run_manifest_id": "wrong"}},
    )
    for name in ("leaderboard.csv", "leaderboard.md", "leaderboard.html"):
        _write_text(report_dir / name, name)

    with pytest.raises(
        OfficialHFPublicationError,
        match="provenance differs for run_manifest_id",
    ):
        build_retained_hf_publication(
            RetainedHFPublicationConfig(
                score_path=score_path,
                unit_scores_path=tmp_path / "unit-scores.jsonl",
                report_dir=report_dir,
                output_dir=tmp_path / "output",
                cycle_id="cycle-1",
                release_version="cycle-1.1.0",
                dataset_repository="example/legalforecastbench",
            )
        )


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
    assert "Unofficial" not in card
    assert "must not be reported as official" not in card
    assert "Post-anchor" in card
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


def test_hf_publication_refuses_a_supplementary_solver_reused_under_a_new_label(
    tmp_path: Path,
) -> None:
    official = write_official_report_fixture(tmp_path)
    supplementary = write_supplementary_report_fixture(tmp_path)
    # A published model_id is a display label, so relabelling the official solver
    # fixture:model-a hides the collision from every model_id comparison. Only a
    # solver_id comparison -- the registry identity -- still sees it.
    scores_path = supplementary / "scores.json"
    scores = json.loads(scores_path.read_text(encoding="utf-8"))
    scores["summaries"][0]["solver_id"] = "fixture:model-a"
    _write_json(scores_path, scores)
    run_card_path = supplementary / "run-cards" / "aggregate-run-card.json"
    run_card = json.loads(run_card_path.read_text(encoding="utf-8"))
    for key in ("model_keys", "registry_model_keys", "expected_model_keys"):
        run_card[key] = ["fixture:model-a"]
    _write_json(run_card_path, run_card)
    _refresh_official_artifact_manifests(supplementary)

    with pytest.raises(
        OfficialHFPublicationError,
        match="supplementary solvers must not appear in the official split",
    ):
        build_official_hf_publication(
            OfficialHFPublicationConfig(
                official_artifacts_dir=official,
                output_dir=tmp_path / "hugging-face",
                release_version="cycle-1.0.0",
                dataset_repository="example/legalforecastbench",
                supplementary_artifacts_dir=supplementary,
            )
        )


def test_hf_publication_refuses_a_supplementary_bundle_from_another_cycle(
    tmp_path: Path,
) -> None:
    result = build_official_hf_publication(
        OfficialHFPublicationConfig(
            official_artifacts_dir=write_official_report_fixture(tmp_path),
            output_dir=tmp_path / "hugging-face",
            release_version="cycle-1.0.0",
            dataset_repository="example/legalforecastbench",
            supplementary_artifacts_dir=write_supplementary_report_fixture(tmp_path),
        )
    )
    supplementary_root = result.output_dir / _RELEASE_PATH / "supplementary"
    for relative in (
        "report/leaderboard.json",
        "scores.json",
        "run-cards/aggregate-run-card.json",
        "cycle-power.json",
    ):
        path = supplementary_root / relative
        record = json.loads(path.read_text(encoding="utf-8"))
        record["cycle_id"] = "other-cycle"
        nested = record.get("cycle_power")
        if isinstance(nested, dict):
            nested["cycle_id"] = "other-cycle"
        _write_json(path, record)
    # The swapped bundle stays internally consistent and fully committed, so only
    # a cross-bundle cycle check can refuse it.
    _refresh_official_artifact_manifests(supplementary_root)
    _recommit_publication_manifest(
        result.output_dir,
        supplementary_artifact_index_sha256=_digest(
            supplementary_root / "artifact-index.json"
        ),
    )

    with pytest.raises(
        OfficialHFPublicationError,
        match="supplementary bundle cycle_id differs from the official bundle",
    ):
        validate_official_hf_publication(result.output_dir)


def test_hf_publication_bounds_the_supplementary_split_by_path_segment(
    tmp_path: Path,
) -> None:
    official = write_official_report_fixture(tmp_path)
    sibling_package = build_official_hf_publication(
        OfficialHFPublicationConfig(
            official_artifacts_dir=official,
            output_dir=tmp_path / "sibling-package",
            release_version="cycle-1.0.0",
            dataset_repository="example/legalforecastbench",
        )
    )
    # A sibling directory shares the supplementary path's string prefix but is
    # not inside it, so it can never stand in for the supplementary split.
    sibling = sibling_package.output_dir / _RELEASE_PATH / "supplementary-extra"
    sibling.mkdir(parents=True)
    _write_text(sibling / "unit-scores.jsonl", '{"model_id": "supp-model"}\n')
    _recommit_publication_manifest(
        sibling_package.output_dir,
        schema_version=OFFICIAL_HF_PUBLICATION_SUPPLEMENTARY_SCHEMA_VERSION,
        supplementary_path=f"{_RELEASE_PATH}/supplementary",
        supplementary_artifact_index_sha256="sha256:" + "0" * 64,
    )
    with pytest.raises(
        OfficialHFPublicationError,
        match="lists no supplementary artifacts",
    ):
        validate_official_hf_publication(sibling_package.output_dir)

    # The supplementary path itself is inside the split even when it is occupied
    # by a file rather than a directory, so an official-only manifest may not
    # carry it.
    occupied_package = build_official_hf_publication(
        OfficialHFPublicationConfig(
            official_artifacts_dir=official,
            output_dir=tmp_path / "occupied-package",
            release_version="cycle-1.0.0",
            dataset_repository="example/legalforecastbench",
        )
    )
    _write_text(
        occupied_package.output_dir / _RELEASE_PATH / "supplementary",
        '{"model_id": "supp-model"}\n',
    )
    _recommit_publication_manifest(occupied_package.output_dir)

    with pytest.raises(
        OfficialHFPublicationError,
        match="carries supplementary artifacts",
    ):
        validate_official_hf_publication(occupied_package.output_dir)


def test_hf_publication_refuses_a_dangling_supplementary_digest_under_v1(
    tmp_path: Path,
) -> None:
    result = build_official_hf_publication(
        OfficialHFPublicationConfig(
            official_artifacts_dir=write_official_report_fixture(tmp_path),
            output_dir=tmp_path / "hugging-face",
            release_version="cycle-1.0.0",
            dataset_repository="example/legalforecastbench",
        )
    )
    manifest = json.loads(result.publication_manifest_path.read_text(encoding="utf-8"))
    manifest["supplementary_artifact_index_sha256"] = "sha256:" + "0" * 64
    result.publication_manifest_path.write_text(
        json.dumps(manifest, sort_keys=True), encoding="utf-8"
    )

    assert manifest["schema_version"] == OFFICIAL_HF_PUBLICATION_SCHEMA_VERSION
    with pytest.raises(
        OfficialHFPublicationError,
        match="declares a supplementary digest",
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


def _write_json(path: Path, payload: object) -> None:
    _write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _recommit_publication_manifest(root: Path, **updates: object) -> None:
    """Re-derive a package manifest over the edited tree, then apply ``updates``.

    Every per-file commitment is rebuilt, so a test that edits package bytes is
    left arguing about the check it targets rather than about stale digests.
    """

    manifest_path = root / "publication-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(updates)
    manifest["artifacts"] = [
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": _digest(path),
            "size_bytes": path.stat().st_size,
        }
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "publication-manifest.json"
    ]
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
