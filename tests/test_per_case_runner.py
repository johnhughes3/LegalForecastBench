from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest
from legalforecast.cli import main
from legalforecast.evals.packet_builder import (
    ModelPacket,
    PacketAblation,
    PacketDocument,
)
from legalforecast.evals.per_case_runner import (
    PacketManifestError,
    PerCaseRunnerConfig,
    PerCaseRunnerError,
    run_per_case_evaluation,
)
from legalforecast.ingestion.provenance import DocumentRole, sha256_text
from legalforecast.protocol.freeze import sha256_file
from legalforecast.unitization.schemas import (
    ChallengeScope,
    PredictionUnit,
    SourceCitation,
)


def test_per_case_runner_verifies_packet_and_publishes_safe_outputs(
    tmp_path: Path,
) -> None:
    packet_text = "Operative complaint text for the isolated packet."
    store_root, manifest_path, packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(packet_text=packet_text),
    )
    output_dir = tmp_path / "runner-output"
    results_root = tmp_path / "results-store"

    artifacts = run_per_case_evaluation(
        PerCaseRunnerConfig(
            manifest_uri=str(manifest_path),
            packet_store_root=str(store_root),
            results_store_root=str(results_root),
            case_id="case-1",
            ablation="full_packet",
            output_dir=output_dir,
            solver_id="offline:fixture",
            mock_output=_mock_output(),
        )
    )

    assert artifacts.packet_sha256 == packet_sha256
    assert {path.name for path in artifacts.local_paths} == {
        "accounting.jsonl",
        "metrics.json",
        "runner-log.jsonl",
        "runs.jsonl",
    }
    assert all(path.is_file() for path in artifacts.local_paths)
    assert not (output_dir / "model-packet.json").exists()

    runs = _read_jsonl(output_dir / "runs.jsonl")
    assert runs[0]["case_id"] == "case-1"
    assert "packet" not in runs[0]
    assert "prompt" not in runs[0]

    log_text = (output_dir / "runner-log.jsonl").read_text(encoding="utf-8")
    metrics_text = (output_dir / "metrics.json").read_text(encoding="utf-8")
    accounting_text = (output_dir / "accounting.jsonl").read_text(encoding="utf-8")
    for text in (log_text, metrics_text, accounting_text):
        assert packet_text not in text
        assert "CASE_DEV_API_KEY" not in text

    uploaded_paths = {
        path.relative_to(results_root).as_posix()
        for path in results_root.rglob("*")
        if path.is_file()
    }
    assert uploaded_paths
    assert all(path.startswith(("metrics/", "reports/")) for path in uploaded_paths)
    assert not any(
        path.startswith(
            (
                "audit-bundles/",
                "extracted-text/",
                "model-packets/",
                "source-documents/",
                "withdrawn/",
            )
        )
        for path in uploaded_paths
    )


def test_per_case_runner_accepts_exported_packet_sha256_field(
    tmp_path: Path,
) -> None:
    store_root, manifest_path, packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(),
        hash_field="packet_sha256",
    )

    artifacts = run_per_case_evaluation(
        PerCaseRunnerConfig(
            manifest_uri=str(manifest_path),
            packet_store_root=str(store_root),
            case_id="case-1",
            ablation="full_packet",
            output_dir=tmp_path / "runner-output",
            solver_id="offline:fixture",
            mock_output=_mock_output(),
        )
    )

    assert artifacts.packet_sha256 == packet_sha256


def test_per_case_runner_refuses_hash_mismatch_without_retaining_packet(
    tmp_path: Path,
) -> None:
    packet_text = "Hash mismatch packet text must not be retained."
    store_root, manifest_path, _packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(packet_text=packet_text),
        manifest_sha256="0" * 64,
    )
    output_dir = tmp_path / "runner-output"

    with pytest.raises(PerCaseRunnerError, match="SHA-256 mismatch"):
        run_per_case_evaluation(
            PerCaseRunnerConfig(
                manifest_uri=str(manifest_path),
                packet_store_root=str(store_root),
                case_id="case-1",
                ablation="full_packet",
                output_dir=output_dir,
                mock_output=_mock_output(),
            )
        )

    assert (output_dir / "runner-log.jsonl").is_file()
    assert not (output_dir / "runs.jsonl").exists()
    assert packet_text not in (output_dir / "runner-log.jsonl").read_text(
        encoding="utf-8"
    )


def test_per_case_runner_refuses_audit_only_packet_objects(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    _write_json(
        manifest_path,
        {
            "cycle_id": "cycle-1",
            "model_packets": [
                {
                    "case_id": "case-1",
                    "ablation": "full_packet",
                    "object_key": "audit-bundles/cycle-1/case-1/full_packet.json",
                    "sha256": "1" * 64,
                }
            ],
        },
    )

    with pytest.raises(PacketManifestError, match="model packet object key"):
        run_per_case_evaluation(
            PerCaseRunnerConfig(
                manifest_uri=str(manifest_path),
                packet_store_root=str(tmp_path / "store"),
                case_id="case-1",
                ablation="full_packet",
                output_dir=tmp_path / "runner-output",
                mock_output=_mock_output(),
            )
        )


def test_eval_run_case_cli_writes_artifact_summary(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    store_root, manifest_path, _packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(),
    )
    output_dir = tmp_path / "cli-output"

    assert (
        main(
            [
                "eval",
                "run-case",
                "--manifest",
                str(manifest_path),
                "--packet-store-root",
                str(store_root),
                "--case-id",
                "case-1",
                "--ablation",
                "full_packet",
                "--output-dir",
                str(output_dir),
                "--mock-output",
                _mock_output(),
                "--evaluation-timestamp",
                "2026-05-17T12:00:00Z",
                "--timeout-seconds",
                "300",
            ]
        )
        == 0
    )

    stdout = capsys.readouterr().out
    summary = json.loads(stdout)
    assert summary["case_id"] == "case-1"
    assert (output_dir / "runs.jsonl").is_file()
    metrics = json.loads((output_dir / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["evaluation_timestamp"] == "2026-05-17T12:00:00Z"


def test_per_case_runner_repeats_prebudgeted_subset_rows(tmp_path: Path) -> None:
    store_root, manifest_path, _packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(),
    )
    output_dir = tmp_path / "runner-output"

    run_per_case_evaluation(
        PerCaseRunnerConfig(
            manifest_uri=str(manifest_path),
            packet_store_root=str(store_root),
            case_id="case-1",
            ablation="full_packet",
            output_dir=output_dir,
            mock_output=_mock_output(),
            repeat_count=3,
        )
    )

    runs = _read_jsonl(output_dir / "runs.jsonl")
    accounting = _read_jsonl(output_dir / "accounting.jsonl")
    metrics = json.loads((output_dir / "metrics.json").read_text(encoding="utf-8"))

    assert [record["repeat_index"] for record in runs] == [1, 2, 3]
    assert [record["repeat_sampling_role"] for record in runs] == [
        "primary",
        "repeat",
        "repeat",
    ]
    assert {record["repeat_group_id"] for record in runs} == {"cand-1"}
    assert len(accounting) == 3
    assert all(record["repeat_count"] == 3 for record in accounting)
    assert metrics["repeat_count"] == 3
    assert metrics["primary_run_record_count"] == 1
    assert metrics["run_record_count"] == 3


def test_per_case_runner_rejects_nonpositive_timeout(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="timeout_seconds must be positive"):
        PerCaseRunnerConfig(
            manifest_uri=str(tmp_path / "manifest.json"),
            case_id="case-1",
            ablation="full_packet",
            output_dir=tmp_path / "runner-output",
            mock_output=_mock_output(),
            timeout_seconds=0,
        )


def test_per_case_runner_rejects_nonpositive_repeat_count(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="repeat_count must be positive"):
        PerCaseRunnerConfig(
            manifest_uri=str(tmp_path / "manifest.json"),
            case_id="case-1",
            ablation="full_packet",
            output_dir=tmp_path / "runner-output",
            mock_output=_mock_output(),
            repeat_count=0,
        )


def test_per_case_runner_resolves_model_registry_entry(tmp_path: Path) -> None:
    store_root, manifest_path, _packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(),
    )
    registry_path = tmp_path / "model-registry.json"
    _write_json(
        registry_path,
        [
            {
                "provider": "example-provider",
                "model_id": "example-model",
                "display_name": "Example Model",
                "model_version_or_snapshot": "example-model",
                "release_timestamp": "2026-05-14T09:00:00Z",
                "provider_training_cutoff_status": "not_disclosed",
                "provider_training_cutoff": None,
                "temperature": 0,
                "top_p": 1,
                "max_output_tokens": 4096,
                "network_disabled": True,
                "search_disabled": True,
                "tool_policy": "controlled_docket_tool_only",
                "context_limit": 200000,
                "pricing_source": "fixture",
                "input_token_price": 0.25,
                "output_token_price": 1.0,
                "known_cutoff_publicity_caveats": (),
            }
        ],
    )

    run_per_case_evaluation(
        PerCaseRunnerConfig(
            manifest_uri=str(manifest_path),
            packet_store_root=str(store_root),
            case_id="case-1",
            ablation="full_packet",
            output_dir=tmp_path / "runner-output",
            mock_output=_mock_output(),
            model_registry_uri=str(registry_path),
            model_key="example-provider:example-model",
        )
    )

    runs = _read_jsonl(tmp_path / "runner-output" / "runs.jsonl")
    assert runs[0]["solver_id"] == "example-provider:example-model"
    metadata = cast(dict[str, Any], runs[0]["metadata"])
    assert metadata["provider"] == "example-provider"
    metrics = json.loads(
        (tmp_path / "runner-output" / "metrics.json").read_text(encoding="utf-8")
    )
    assert metrics["model_key"] == "example-provider:example-model"
    assert metrics["model_registry_sha256"] == sha256_file(registry_path)


def test_per_case_runner_rejects_unknown_model_key(tmp_path: Path) -> None:
    store_root, manifest_path, _packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(),
    )
    registry_path = tmp_path / "model-registry.json"
    _write_json(
        registry_path,
        [
            {
                "provider": "example-provider",
                "model_id": "example-model",
                "display_name": "Example Model",
                "model_version_or_snapshot": "example-model",
                "release_timestamp": "2026-05-14T09:00:00Z",
                "provider_training_cutoff_status": "not_disclosed",
                "provider_training_cutoff": None,
                "temperature": 0,
                "top_p": 1,
                "max_output_tokens": 4096,
                "network_disabled": True,
                "search_disabled": True,
                "tool_policy": "controlled_docket_tool_only",
                "context_limit": 200000,
                "pricing_source": "fixture",
                "input_token_price": 0.25,
                "output_token_price": 1.0,
                "known_cutoff_publicity_caveats": (),
            }
        ],
    )

    with pytest.raises(PerCaseRunnerError, match="model_key not found"):
        run_per_case_evaluation(
            PerCaseRunnerConfig(
                manifest_uri=str(manifest_path),
                packet_store_root=str(store_root),
                case_id="case-1",
                ablation="full_packet",
                output_dir=tmp_path / "runner-output",
                mock_output=_mock_output(),
                model_registry_uri=str(registry_path),
                model_key="example-provider:missing",
            )
        )


def test_per_case_runner_rejects_packet_before_release_anchor(tmp_path: Path) -> None:
    store_root, manifest_path, _packet_sha256 = _write_store_fixture(
        tmp_path,
        packet_record=_packet_record(decision_date="2026-05-15"),
    )
    registry_path = tmp_path / "model-registry.json"
    _write_json(
        registry_path,
        [
            {
                "provider": "example-provider",
                "model_id": "example-model",
                "display_name": "Example Model",
                "model_version_or_snapshot": "example-model",
                "release_timestamp": "2026-05-14T09:00:00Z",
                "provider_training_cutoff_status": "not_disclosed",
                "provider_training_cutoff": None,
                "temperature": 0,
                "top_p": 1,
                "max_output_tokens": 4096,
                "network_disabled": True,
                "search_disabled": True,
                "tool_policy": "controlled_docket_tool_only",
                "context_limit": 200000,
                "pricing_source": "fixture",
                "input_token_price": 0.25,
                "output_token_price": 1.0,
                "known_cutoff_publicity_caveats": (),
            }
        ],
    )

    with pytest.raises(PerCaseRunnerError, match="precedes release anchor"):
        run_per_case_evaluation(
            PerCaseRunnerConfig(
                manifest_uri=str(manifest_path),
                packet_store_root=str(store_root),
                case_id="case-1",
                ablation="full_packet",
                output_dir=tmp_path / "runner-output",
                mock_output=_mock_output(),
                model_registry_uri=str(registry_path),
                model_key="example-provider:example-model",
            )
        )


def _write_store_fixture(
    tmp_path: Path,
    *,
    packet_record: dict[str, object],
    manifest_sha256: str | None = None,
    hash_field: str = "sha256",
) -> tuple[Path, Path, str]:
    store_root = tmp_path / "packet-store"
    packet_key = "model-packets/cycle-1/case-1/full_packet.json"
    packet_path = store_root / packet_key
    _write_json(packet_path, packet_record)
    packet_sha256 = sha256_file(packet_path)
    manifest_path = tmp_path / "manifest.json"
    _write_json(
        manifest_path,
        {
            "cycle_id": "cycle-1",
            "model_packets": [
                {
                    "case_id": "case-1",
                    "ablation": "full_packet",
                    "object_key": packet_key,
                    hash_field: manifest_sha256 or packet_sha256,
                    "size_bytes": packet_path.stat().st_size,
                    "content_type": "application/json",
                    "decision_date": packet_record.get("decision_date"),
                }
            ],
        },
    )
    return store_root, manifest_path, packet_sha256


def _packet_record(
    *,
    decision_date: str = "2026-05-17",
    packet_text: str = "Fixture complaint text.",
) -> dict[str, object]:
    document = PacketDocument(
        source_document_id="doc-complaint",
        document_role=DocumentRole.COMPLAINT,
        docket_entry_number=12,
        source_provider="fixture",
        source_url_or_reference="fixture://case-1/doc-complaint",
        source_sha256=sha256_text(packet_text),
        text=packet_text,
        text_sha256=sha256_text(packet_text),
        packet_section="filings",
    )
    unit = PredictionUnit(
        unit_id="unit-1",
        count="I",
        claim_name="Breach of contract",
        defendant_group="Example Defendant",
        challenged_by_motion=True,
        challenge_scope=ChallengeScope.ENTIRE_CLAIM,
        unit_confidence=0.97,
        source_citations=(
            SourceCitation(
                document_id="doc-complaint",
                docket_entry_number=12,
                excerpt="Breach of contract claim.",
            ),
        ),
    )
    packet = ModelPacket(
        candidate_id="cand-1",
        case_id="case-1",
        court="D. Example",
        docket_number="1:26-cv-00001",
        ablation=PacketAblation.FULL_PACKET,
        metadata={"decision_date": decision_date, "fixture": "true"},
        documents=(document,),
        prediction_units=(unit,),
        excluded_document_ids=(),
        decision_date=decision_date,
    )
    return packet.to_record()


def _mock_output() -> str:
    return json.dumps(
        {
            "case_assessment": "The motion has modest dismissal risk.",
            "predictions": [
                {
                    "unit_id": "unit-1",
                    "probability_fully_dismissed": 0.25,
                }
            ],
        },
        sort_keys=True,
    )


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
