from __future__ import annotations

import builtins
import hashlib
import json
import os
import subprocess
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import legalforecast.cli as cli_module
import legalforecast.ingestion.disclosure_review_bundle as review_bundle_module
import pytest
from cryptography.hazmat.primitives import serialization
from legalforecast.cli import main
from legalforecast.ingestion.disclosure_review_bundle import (
    ReviewBundleError,
    canonical_json_bytes,
)
from tests.disclosure_review_fixtures import (
    ServiceReviewSigner,
    service_disclosure_authority_from_policy_bytes,
    service_review_signer,
)


@pytest.fixture(autouse=True)
def _test_disclosure_authority(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cli_module,
        "load_main_disclosure_review_authority",
        lambda _cohort, *, reviewer_policy_bytes: (
            service_disclosure_authority_from_policy_bytes(reviewer_policy_bytes)
        ),
    )


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _inputs(
    tmp_path: Path, *, document_count: int = 1
) -> tuple[Path, Path, Path, Path]:
    document_root = tmp_path / "documents"
    manifest_rows: list[dict[str, object]] = []
    restriction_rows: list[dict[str, object]] = []
    request_rows: list[dict[str, object]] = []
    for ordinal in range(1, document_count + 1):
        candidate_id = f"cand-{ordinal}"
        document_id = f"doc-{ordinal}"
        document = document_root / candidate_id / f"{document_id}.pdf"
        document.parent.mkdir(parents=True)
        content = (
            b"%PDF-1.4\n/Type /Page\n<< >>\nstream\n"
            + f"BT (Public motion memorandum {ordinal}) Tj ET\n".encode()
            + b"endstream"
        )
        document.write_bytes(content)
        manifest_row: dict[str, object] = {
            "candidate_id": candidate_id,
            "source_document_id": document_id,
            "local_path": f"{candidate_id}/{document_id}.pdf",
            "sha256": hashlib.sha256(content).hexdigest(),
            "byte_count": len(content),
            "free_or_purchased": "free",
        }
        restriction_row: dict[str, object] = {
            "candidate_id": candidate_id,
            "source_document_id": document_id,
            "restriction_status": "public",
            "restriction_evidence": "courtlistener-public-docket",
        }
        manifest_rows.append(manifest_row)
        restriction_rows.append(restriction_row)
        request_rows.append(
            {
                **manifest_row,
                "schema_version": "legalforecast.disclosure_review_request.v1",
                "restriction_status": "public",
                "restriction_evidence": "courtlistener-public-docket",
                "required_human_decision": "cleared_or_quarantined",
            }
        )
    requests = tmp_path / "requests.jsonl"
    manifest = tmp_path / "manifest.jsonl"
    restrictions = tmp_path / "restrictions.jsonl"
    _write_jsonl(requests, request_rows)
    _write_jsonl(manifest, manifest_rows)
    _write_jsonl(restrictions, restriction_rows)
    return requests, manifest, restrictions, document_root


def _prepare_args(
    tmp_path: Path,
    *,
    document_count: int = 1,
    signer: ServiceReviewSigner | None = None,
) -> list[str]:
    requests, manifest, restrictions, document_root = _inputs(
        tmp_path, document_count=document_count
    )
    if signer is None:
        signer = service_review_signer(
            reviewer_id="reviewer:john",
            controlled_store_uri="private-store://cycle-1/reviews/batch-001",
        )
    policy = tmp_path / "reviewer-policy.json"
    policy.write_bytes(signer["reviewer_policy_bytes"])
    cohort_policy = tmp_path / "cohort-policy.json"
    cohort_policy.write_text("{}\n", encoding="utf-8")
    return [
        "acquisition",
        "prepare-disclosure-review",
        "--review-requests",
        str(requests),
        "--download-manifest",
        str(manifest),
        "--restriction-evidence",
        str(restrictions),
        "--reviewer-policy",
        str(policy),
        "--cohort-policy",
        str(cohort_policy),
        "--document-root",
        str(document_root),
        "--controlled-private-store-root",
        str(tmp_path / "private-review"),
        "--output-root",
        str(tmp_path / "output"),
        "--execute",
    ]


class _TTY:
    @staticmethod
    def isatty() -> bool:
        return True


class _NotTTY:
    @staticmethod
    def isatty() -> bool:
        return False


def _record_command(tmp_path: Path) -> list[str]:
    private_root = tmp_path / "private-review"
    return [
        "acquisition",
        "record-disclosure-review-decisions",
        "--review-worksheet",
        str(tmp_path / "output/disclosure-review-worksheet.json"),
        "--private-inspection-map",
        str(private_root / "private-document-inspection-map.jsonl"),
        "--reviewer-id",
        "reviewer:john",
        "--controlled-private-store-root",
        str(private_root),
        "--output-root",
        str(private_root / "recorder-metadata"),
        "--execute",
        "--resume",
    ]


def _complete_recorder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, decision: str = "cleared"
) -> list[str]:
    worksheet = json.loads(
        (tmp_path / "output/disclosure-review-worksheet.json").read_text()
    )
    digests = {
        (str(row["candidate_id"]), str(row["source_document_id"])): str(row["sha256"])
        for row in worksheet["documents"]
    }
    ordered_digests = iter(digests.values())
    monkeypatch.setattr(cli_module.sys, "stdin", _TTY())

    def answer(prompt: str) -> str:
        if prompt.startswith("Type the full inspected"):
            return next(ordered_digests)
        if prompt.startswith("Decision"):
            return decision
        return prompt.removeprefix("Type exactly '").removesuffix("': ")

    monkeypatch.setattr("builtins.input", answer)
    command = _record_command(tmp_path)
    assert main(command) == 0
    return command


def test_prepare_review_is_resumable_and_keeps_private_map_out_of_run_card(
    tmp_path: Path,
) -> None:
    args = _prepare_args(tmp_path)
    assert main(args) == 0
    worksheet = tmp_path / "output/disclosure-review-worksheet.json"
    private_map = tmp_path / "private-review/private-document-inspection-map.jsonl"
    assert worksheet.is_file()
    assert private_map.is_file()
    run_card = json.loads(
        (tmp_path / "output/run-cards/prepare-disclosure-review.json").read_text()
    )
    assert str(private_map) not in json.dumps(run_card)
    assert run_card["private_inspection_map_excluded_from_commitments"] is True
    run_card_path = tmp_path / "output/run-cards/prepare-disclosure-review.json"
    log_path = tmp_path / "output/logs/prepare-disclosure-review.jsonl"
    metadata_before = {
        path: (path.read_bytes(), path.stat().st_mtime_ns)
        for path in (run_card_path, log_path)
    }
    assert main(args) == 0
    assert {
        path: (path.read_bytes(), path.stat().st_mtime_ns)
        for path in (run_card_path, log_path)
    } == metadata_before
    requests_path = tmp_path / "requests.jsonl"
    request_before = requests_path.read_bytes()
    request = json.loads(request_before)
    request["sha256"] = "0" * 64
    _write_jsonl(requests_path, [request])
    assert main(args) == 2
    assert {
        path: (path.read_bytes(), path.stat().st_mtime_ns)
        for path in (run_card_path, log_path)
    } == metadata_before
    requests_path.write_bytes(request_before)
    private_map.write_text("tampered\n", encoding="utf-8")
    assert main(args) == 2


def test_prepare_review_rejects_input_alias_and_output_symlink(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    args = _prepare_args(tmp_path)
    manifest = tmp_path / "manifest.jsonl"
    assert main([*args, "--worksheet-output", str(manifest)]) == 2

    output = tmp_path / "output/disclosure-review-worksheet.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    target = tmp_path / "symlink-target"
    target.write_text("do not overwrite", encoding="utf-8")
    output.symlink_to(target)
    assert main(args) == 2
    assert target.read_text(encoding="utf-8") == "do not overwrite"

    output.unlink()
    dangling_parent = tmp_path / "dangling-parent"
    missing_target = tmp_path / "missing-parent-target"
    dangling_parent.symlink_to(missing_target, target_is_directory=True)
    assert (
        main([*args, "--worksheet-output", str(dangling_parent / "worksheet.json")])
        == 2
    )
    assert "output parent is a symlink" in capsys.readouterr().err
    assert not missing_target.exists()

    traversal_case = tmp_path / "traversal-case"
    traversal_args = _prepare_args(traversal_case)
    traversal_root = traversal_case / "traversal-root"
    traversal_root.mkdir()
    outside_parent = traversal_case / "outside-parent"
    symlink_target = outside_parent / "target"
    symlink_target.mkdir(parents=True)
    (traversal_root / "jump").symlink_to(symlink_target, target_is_directory=True)
    escaped_output = outside_parent / "escaped-worksheet.json"
    traversal_output = traversal_root / "jump" / ".." / escaped_output.name
    assert main([*traversal_args, "--worksheet-output", str(traversal_output)]) == 2
    assert "output parent is a symlink" in capsys.readouterr().err
    assert not escaped_output.exists()


def test_prepare_review_rejects_metadata_alias_without_mutating_input(
    tmp_path: Path,
) -> None:
    args = _prepare_args(tmp_path)
    requests = tmp_path / "requests.jsonl"
    original = requests.read_bytes()
    assert main([*args, "--run-card-output", str(requests)]) == 2
    assert requests.read_bytes() == original

    dangling_target = tmp_path / "missing-run-card-target"
    dangling_run_card = tmp_path / "dangling-run-card"
    dangling_run_card.symlink_to(dangling_target)
    assert main([*args, "--run-card-output", str(dangling_run_card)]) == 2
    assert dangling_run_card.is_symlink()
    assert not dangling_target.exists()


def test_signer_preflight_reports_missing_hardware_without_key_material(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    policy = {
        "schema_version": "legalforecast.disclosure_reviewer_policy.v1",
        "reviewer_id": "reviewer:john",
        "ssh_principal": "john",
        "ssh_public_key": "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFixture",
        "identity_kind": "human_hardware",
        "controlled_store_uri_prefix": "private-store://cycle-1/reviews/",
        "signature_namespace": "legalforecast-disclosure-review-v1",
    }
    policy_path = tmp_path / "policy.json"
    policy_bytes = (
        json.dumps(policy, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    policy_path.write_bytes(policy_bytes)
    (tmp_path / "cohort-policy.json").write_text("{}\n", encoding="utf-8")
    assert (
        main(
            [
                "acquisition",
                "preflight-disclosure-review-signer",
                "--reviewer-policy",
                str(policy_path),
                "--cohort-policy",
                str(tmp_path / "cohort-policy.json"),
            ]
        )
        == 2
    )
    captured = capsys.readouterr()
    assert "LegalForecastBench-5qd6.39.7.1" in captured.err
    assert "AAAAC3" not in captured.err


@pytest.mark.parametrize(
    "command",
    [
        "prepare-disclosure-review",
        "preflight-disclosure-review-signer",
        "build-disclosure-review-bundle",
        "seal-disclosure-review-bundle",
        "clear-disclosures",
    ],
)
def test_disclosure_review_help_names_main_pinned_authority(
    command: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["acquisition", command, "--help"])
    assert exc.value.code == 0
    help_text = capsys.readouterr().out
    assert "main-pinned disclosure authority" in help_text
    assert "--expected-reviewer-policy-sha256" not in help_text


def test_private_interactive_recorder_requires_hash_and_batch_confirmation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    args = _prepare_args(tmp_path)
    assert main(args) == 0
    worksheet = json.loads(
        (tmp_path / "output/disclosure-review-worksheet.json").read_text()
    )
    digest = worksheet["documents"][0]["sha256"]

    class _TTY:
        @staticmethod
        def isatty() -> bool:
            return True

    monkeypatch.setattr(cli_module.sys, "stdin", _TTY())

    def answer(prompt: str) -> str:
        if prompt.startswith("Type the full inspected"):
            return str(digest)
        if prompt.startswith("Decision"):
            return "cleared"
        assert prompt.startswith("Type exactly '")
        return prompt.removeprefix("Type exactly '").removesuffix("': ")

    monkeypatch.setattr("builtins.input", answer)
    private_root = tmp_path / "private-review"
    assert (
        main(
            [
                "acquisition",
                "record-disclosure-review-decisions",
                "--review-worksheet",
                str(tmp_path / "output/disclosure-review-worksheet.json"),
                "--private-inspection-map",
                str(private_root / "private-document-inspection-map.jsonl"),
                "--reviewer-id",
                "reviewer:john",
                "--controlled-private-store-root",
                str(private_root),
                "--output-root",
                str(private_root / "recorder-metadata"),
                "--execute",
            ]
        )
        == 0
    )
    decisions = [
        json.loads(line)
        for line in (private_root / "disclosure-review-decisions.jsonl")
        .read_text()
        .splitlines()
    ]
    assert decisions[0]["recording_method"] == "interactive_review_cli"
    assert decisions[0]["status"] == "cleared"
    assert len(decisions[0]["batch_confirmation_sha256"]) == 64


def test_private_recorder_checkpoints_each_document_and_resumes_remaining_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert main(_prepare_args(tmp_path, document_count=2)) == 0
    worksheet_path = tmp_path / "output/disclosure-review-worksheet.json"
    worksheet = json.loads(worksheet_path.read_text())
    digests = [str(row["sha256"]) for row in worksheet["documents"]]

    class _TTY:
        @staticmethod
        def isatty() -> bool:
            return True

    monkeypatch.setattr(cli_module.sys, "stdin", _TTY())
    prompt_count = 0

    def interrupt_after_first(prompt: str) -> str:
        nonlocal prompt_count
        prompt_count += 1
        if prompt_count == 1:
            return digests[0]
        if prompt_count == 2:
            return "cleared"
        raise KeyboardInterrupt

    monkeypatch.setattr("builtins.input", interrupt_after_first)
    private_root = tmp_path / "private-review"
    command = [
        "acquisition",
        "record-disclosure-review-decisions",
        "--review-worksheet",
        str(worksheet_path),
        "--private-inspection-map",
        str(private_root / "private-document-inspection-map.jsonl"),
        "--reviewer-id",
        "reviewer:john",
        "--controlled-private-store-root",
        str(private_root),
        "--output-root",
        str(private_root / "recorder-metadata"),
        "--execute",
        "--resume",
    ]
    with pytest.raises(KeyboardInterrupt):
        main(command)
    checkpoint_dir = private_root / "checkpoints/documents"
    [first_checkpoint] = list(checkpoint_dir.glob("*.json"))
    interrupted_publish_alias = checkpoint_dir / (
        f".{first_checkpoint.name}.interrupted.tmp"
    )
    interrupted_publish_alias.hardlink_to(first_checkpoint)
    assert first_checkpoint.stat().st_nlink == 2

    resumed_prompts: list[str] = []

    def resume_answers(prompt: str) -> str:
        resumed_prompts.append(prompt)
        if prompt.startswith("Type the full inspected"):
            return digests[1]
        if prompt.startswith("Decision"):
            return "cleared"
        return prompt.removeprefix("Type exactly '").removesuffix("': ")

    monkeypatch.setattr("builtins.input", resume_answers)
    assert main(command) == 0
    assert not interrupted_publish_alias.exists()
    assert first_checkpoint.stat().st_nlink == 1
    assert len(list(checkpoint_dir.glob("*.json"))) == 2
    assert (
        sum(prompt.startswith("Type the full inspected") for prompt in resumed_prompts)
        == 1
    )

    decisions = private_root / "disclosure-review-decisions.jsonl"
    run_card = private_root / (
        "recorder-metadata/run-cards/record-disclosure-review-decisions.json"
    )
    log = private_root / (
        "recorder-metadata/logs/record-disclosure-review-decisions.jsonl"
    )
    before = {
        path: (path.read_bytes(), path.stat().st_mtime_ns)
        for path in (decisions, run_card, log)
    }

    class _NotTTY:
        @staticmethod
        def isatty() -> bool:
            return False

    monkeypatch.setattr(cli_module.sys, "stdin", _NotTTY())
    monkeypatch.setattr(
        "builtins.input",
        lambda _prompt: pytest.fail("completed resume must not prompt"),
    )
    assert main(command) == 0
    assert {
        path: (path.read_bytes(), path.stat().st_mtime_ns)
        for path in (decisions, run_card, log)
    } == before


def test_private_recorder_rejects_checkpoint_corruption_input_drift_and_duplicates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert main(_prepare_args(tmp_path)) == 0
    worksheet_path = tmp_path / "output/disclosure-review-worksheet.json"
    worksheet = json.loads(worksheet_path.read_text())
    digest = str(worksheet["documents"][0]["sha256"])

    class _TTY:
        @staticmethod
        def isatty() -> bool:
            return True

    monkeypatch.setattr(cli_module.sys, "stdin", _TTY())
    answers = iter((digest, "cleared"))

    def interrupt_at_batch(_prompt: str) -> str:
        try:
            return next(answers)
        except StopIteration:
            raise KeyboardInterrupt from None

    monkeypatch.setattr("builtins.input", interrupt_at_batch)
    private_root = tmp_path / "private-review"
    command = [
        "acquisition",
        "record-disclosure-review-decisions",
        "--review-worksheet",
        str(worksheet_path),
        "--private-inspection-map",
        str(private_root / "private-document-inspection-map.jsonl"),
        "--reviewer-id",
        "reviewer:john",
        "--controlled-private-store-root",
        str(private_root),
        "--output-root",
        str(private_root / "recorder-metadata"),
        "--execute",
        "--resume",
    ]
    with pytest.raises(KeyboardInterrupt):
        main(command)
    [checkpoint] = list((private_root / "checkpoints/documents").glob("*.json"))
    checkpoint_before = checkpoint.read_bytes()
    checkpoint_record = json.loads(checkpoint_before)
    checkpoint_record["status"] = "invalid"
    checkpoint.write_text(
        json.dumps(checkpoint_record, sort_keys=True, separators=(",", ":")) + "\n"
    )
    assert main(command) == 2
    checkpoint.write_bytes(checkpoint_before)

    worksheet_before = worksheet_path.read_bytes()
    worksheet_path.write_text(json.dumps(worksheet, indent=2, sort_keys=True) + "\n")
    assert main(command) == 2
    worksheet_path.write_bytes(worksheet_before)

    inspection_map = private_root / "private-document-inspection-map.jsonl"
    inspection_before = inspection_map.read_bytes()
    inspection_map.write_bytes(inspection_before + inspection_before)
    assert main(command) == 2


def test_disclosure_failure_history_can_resume_to_completion(tmp_path: Path) -> None:
    args = _prepare_args(tmp_path)
    requests = tmp_path / "requests.jsonl"
    original = requests.read_bytes()
    row = json.loads(original)
    row["sha256"] = "0" * 64
    _write_jsonl(requests, [row])
    assert main(args) == 2

    requests.write_bytes(original)
    assert main(args) == 0
    run_card = json.loads(
        (tmp_path / "output/run-cards/prepare-disclosure-review.json").read_text()
    )
    assert run_card["status"] == "completed"
    statuses = [
        json.loads(line)["status"]
        for line in (tmp_path / "output/logs/prepare-disclosure-review.jsonl")
        .read_text()
        .splitlines()
    ]
    assert statuses == ["failed", "completed"]


def test_build_and_seal_authority_failures_resume_with_exact_input_lineage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controlled_store_uri = "private-store://cycle-1/reviews/batch-001"
    signer = service_review_signer(
        reviewer_id="reviewer:john",
        controlled_store_uri=controlled_store_uri,
    )
    assert main(_prepare_args(tmp_path, signer=signer)) == 0
    _complete_recorder(tmp_path, monkeypatch)
    production_preflight = cli_module.reviewer_policy_preflight

    def test_service_preflight(
        reviewer_policy_bytes: bytes,
        *,
        expected_reviewer_policy_sha256: str,
        allow_test_service_identity: bool = False,
    ) -> review_bundle_module.ReviewerPolicy:
        del allow_test_service_identity
        return production_preflight(
            reviewer_policy_bytes,
            expected_reviewer_policy_sha256=expected_reviewer_policy_sha256,
            allow_test_service_identity=True,
        )

    monkeypatch.setattr(cli_module, "reviewer_policy_preflight", test_service_preflight)
    monkeypatch.setattr(
        review_bundle_module, "reviewer_policy_preflight", test_service_preflight
    )

    worksheet = tmp_path / "output/disclosure-review-worksheet.json"
    decisions = tmp_path / "private-review/disclosure-review-decisions.jsonl"
    policy = tmp_path / "reviewer-policy.json"
    cohort_policy = tmp_path / "cohort-policy.json"
    build_root = tmp_path / "bundle"
    build_args = [
        "acquisition",
        "build-disclosure-review-bundle",
        "--review-worksheet",
        str(worksheet),
        "--decisions",
        str(decisions),
        "--reviewer-policy",
        str(policy),
        "--cohort-policy",
        str(cohort_policy),
        "--controlled-store-uri",
        controlled_store_uri,
        "--authenticated-at",
        datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "--output-root",
        str(build_root),
        "--execute",
        "--resume",
    ]
    original_policy = policy.read_bytes()
    wrong_policy = json.loads(original_policy)
    wrong_policy["reviewer_id"] = "reviewer:substituted"
    policy.write_bytes(canonical_json_bytes(wrong_policy))
    assert main(build_args) == 2
    build_card_path = build_root / "run-cards/build-disclosure-review-bundle.json"
    expected_build_inputs = [
        str(worksheet),
        str(decisions),
        str(policy),
        str(cohort_policy),
    ]
    assert json.loads(build_card_path.read_text())["input_paths"] == (
        expected_build_inputs
    )

    policy.write_bytes(original_policy)
    assert main(build_args) == 0
    assert json.loads(build_card_path.read_text())["input_paths"] == (
        expected_build_inputs
    )
    build_log = build_root / "logs/build-disclosure-review-bundle.jsonl"
    assert [
        json.loads(line)["status"] for line in build_log.read_text().splitlines()
    ] == [
        "failed",
        "completed",
    ]

    statement = build_root / "disclosure-review-signing-statement.json"
    private_key = tmp_path / "reviewer-key"
    private_key.write_bytes(
        signer["private_key"].private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.OpenSSH,
            serialization.NoEncryption(),
        )
    )
    private_key.chmod(0o600)
    subprocess.run(
        [
            "/usr/bin/ssh-keygen",
            "-Y",
            "sign",
            "-f",
            str(private_key),
            "-n",
            "legalforecast-disclosure-review-v1",
            str(statement),
        ],
        check=True,
        capture_output=True,
    )
    signature = Path(f"{statement}.sig")
    reviews = build_root / "disclosure-reviews.jsonl"
    seal_root = tmp_path / "seal"
    seal_args = [
        "acquisition",
        "seal-disclosure-review-bundle",
        "--review-requests",
        str(tmp_path / "requests.jsonl"),
        "--download-manifest",
        str(tmp_path / "manifest.jsonl"),
        "--restriction-evidence",
        str(tmp_path / "restrictions.jsonl"),
        "--review-worksheet",
        str(worksheet),
        "--reviews",
        str(reviews),
        "--decisions",
        str(decisions),
        "--signing-statement",
        str(statement),
        "--signature",
        str(signature),
        "--reviewer-policy",
        str(policy),
        "--cohort-policy",
        str(cohort_policy),
        "--output-root",
        str(seal_root),
        "--execute",
        "--resume",
    ]
    policy.write_bytes(canonical_json_bytes(wrong_policy))
    assert main(seal_args) == 2
    seal_card_path = seal_root / "run-cards/seal-disclosure-review-bundle.json"
    expected_seal_inputs = [
        str(tmp_path / "requests.jsonl"),
        str(tmp_path / "manifest.jsonl"),
        str(tmp_path / "restrictions.jsonl"),
        str(worksheet),
        str(reviews),
        str(decisions),
        str(statement),
        str(signature),
        str(policy),
        str(cohort_policy),
    ]
    assert json.loads(seal_card_path.read_text())["input_paths"] == expected_seal_inputs

    policy.write_bytes(original_policy)
    assert main(seal_args) == 0
    assert json.loads(seal_card_path.read_text())["input_paths"] == expected_seal_inputs
    seal_log = seal_root / "logs/seal-disclosure-review-bundle.jsonl"
    assert [
        json.loads(line)["status"] for line in seal_log.read_text().splitlines()
    ] == [
        "failed",
        "completed",
    ]


@pytest.mark.parametrize("missing", ["run_card", "log"])
def test_disclosure_resume_repairs_partial_terminal_metadata(
    tmp_path: Path, missing: str
) -> None:
    args = _prepare_args(tmp_path)
    assert main(args) == 0
    run_card = tmp_path / "output/run-cards/prepare-disclosure-review.json"
    log = tmp_path / "output/logs/prepare-disclosure-review.jsonl"
    survivor = log if missing == "run_card" else run_card
    removed = run_card if missing == "run_card" else log
    survivor_before = (survivor.read_bytes(), survivor.stat().st_mtime_ns)
    removed.unlink()

    assert main(args) == 0
    assert run_card.is_file() and log.is_file()
    assert json.loads(run_card.read_text())["status"] == "completed"
    assert (survivor.read_bytes(), survivor.stat().st_mtime_ns) == survivor_before


def test_completed_recorder_decisions_are_exactly_checkpoint_derived(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert main(_prepare_args(tmp_path)) == 0
    command = _complete_recorder(tmp_path, monkeypatch)
    private_root = tmp_path / "private-review"
    decisions_path = private_root / "disclosure-review-decisions.jsonl"
    [decision] = [json.loads(line) for line in decisions_path.read_text().splitlines()]
    decision["status"] = "quarantined"
    base = {
        key: value
        for key, value in decision.items()
        if key != "batch_confirmation_sha256"
    }
    confirmation_sha256 = hashlib.sha256(canonical_json_bytes(base)).hexdigest()
    decision["batch_confirmation_sha256"] = confirmation_sha256
    decisions_path.write_bytes(canonical_json_bytes(decision))
    run_card_path = private_root / (
        "recorder-metadata/run-cards/record-disclosure-review-decisions.json"
    )
    run_card = json.loads(run_card_path.read_text())
    run_card["human_batch_summary"].update(
        {
            "cleared_count": 0,
            "quarantined_count": 1,
            "confirmation_sha256": "sha256:" + confirmation_sha256,
        }
    )
    run_card_path.write_bytes(canonical_json_bytes(run_card))
    monkeypatch.setattr(cli_module.sys, "stdin", _NotTTY())
    monkeypatch.setattr(
        builtins, "input", lambda _prompt: pytest.fail("resume must not prompt")
    )
    assert main(command) == 2


def test_recorder_rehashes_after_decision_and_failure_is_resumable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert main(_prepare_args(tmp_path)) == 0
    worksheet = json.loads(
        (tmp_path / "output/disclosure-review-worksheet.json").read_text()
    )
    digest = str(worksheet["documents"][0]["sha256"])
    inspected_path = Path(
        json.loads(
            (tmp_path / "private-review/private-document-inspection-map.jsonl")
            .read_text()
            .splitlines()[0]
        )["inspection_path"]
    )
    original = inspected_path.read_bytes()
    monkeypatch.setattr(cli_module.sys, "stdin", _TTY())

    def mutate_after_inspection(prompt: str) -> str:
        if prompt.startswith("Type the full inspected"):
            return digest
        if prompt.startswith("Decision"):
            inspected_path.write_bytes(original + b"changed")
            return "cleared"
        pytest.fail("batch confirmation must not be reached after byte drift")

    monkeypatch.setattr(builtins, "input", mutate_after_inspection)
    command = _record_command(tmp_path)
    assert main(command) == 2
    assert not list((tmp_path / "private-review/checkpoints/documents").glob("*.json"))
    failed_card = json.loads(
        (
            tmp_path
            / (
                "private-review/recorder-metadata/run-cards/"
                "record-disclosure-review-decisions.json"
            )
        ).read_text()
    )
    assert failed_card["status"] == "failed"

    inspected_path.write_bytes(original)
    answers = iter((digest, "cleared"))

    def complete(prompt: str) -> str:
        if prompt.startswith("Type exactly '"):
            return prompt.removeprefix("Type exactly '").removesuffix("': ")
        return next(answers)

    monkeypatch.setattr(builtins, "input", complete)
    assert main(command) == 0


def test_recorder_reloads_checkpoints_after_batch_confirmation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert main(_prepare_args(tmp_path)) == 0
    worksheet = json.loads(
        (tmp_path / "output/disclosure-review-worksheet.json").read_text()
    )
    digest = str(worksheet["documents"][0]["sha256"])
    monkeypatch.setattr(cli_module.sys, "stdin", _TTY())

    def change_checkpoint(prompt: str) -> str:
        if prompt.startswith("Type the full inspected"):
            return digest
        if prompt.startswith("Decision"):
            return "cleared"
        [checkpoint] = list(
            (tmp_path / "private-review/checkpoints/documents").glob("*.json")
        )
        row = json.loads(checkpoint.read_text())
        row["status"] = "quarantined"
        checkpoint.write_bytes(canonical_json_bytes(row))
        return prompt.removeprefix("Type exactly '").removesuffix("': ")

    monkeypatch.setattr(builtins, "input", change_checkpoint)
    assert main(_record_command(tmp_path)) == 2
    assert not (tmp_path / "private-review/disclosure-review-decisions.jsonl").exists()


def test_unique_private_reader_rejects_links_fifo_and_read_race(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reader = review_bundle_module.read_unique_regular_file
    regular = tmp_path / "regular"
    regular.write_bytes(b"original")
    assert reader(regular) == b"original"

    symlink = tmp_path / "symlink"
    symlink.symlink_to(regular)
    with pytest.raises(ReviewBundleError):
        reader(symlink)
    hardlink = tmp_path / "hardlink"
    hardlink.hardlink_to(regular)
    with pytest.raises(ReviewBundleError):
        reader(regular)
    hardlink.unlink()
    fifo = tmp_path / "fifo"
    os.mkfifo(fifo)
    with pytest.raises(ReviewBundleError):
        reader(fifo)
    with pytest.raises(ReviewBundleError):
        reader(Path("/dev/null"))

    parent_link = tmp_path / "linked-parent"
    real_parent = tmp_path / "real-parent"
    real_parent.mkdir()
    nested = real_parent / "nested"
    nested.write_bytes(b"nested")
    parent_link.symlink_to(real_parent, target_is_directory=True)
    with pytest.raises(ReviewBundleError):
        reader(parent_link / "nested")

    original_read = os.read
    changed = False

    def racing_read(fd: int, count: int) -> bytes:
        nonlocal changed
        data = original_read(fd, count)
        if not changed:
            changed = True
            regular.write_bytes(b"changed-during-read")
        return data

    monkeypatch.setattr(os, "read", racing_read)
    with pytest.raises(ReviewBundleError):
        reader(regular)


def test_recorder_publish_failure_is_durable_and_resumable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert main(_prepare_args(tmp_path)) == 0
    worksheet = json.loads(
        (tmp_path / "output/disclosure-review-worksheet.json").read_text()
    )
    digest = str(worksheet["documents"][0]["sha256"])
    monkeypatch.setattr(cli_module.sys, "stdin", _TTY())
    answers = iter((digest, "cleared"))

    def answer(prompt: str) -> str:
        if prompt.startswith("Type exactly '"):
            return prompt.removeprefix("Type exactly '").removesuffix("': ")
        return next(answers)

    monkeypatch.setattr(builtins, "input", answer)
    original_publish = cli_module._ensure_disclosure_review_artifact
    decisions_path = tmp_path / "private-review/disclosure-review-decisions.jsonl"
    failed_once = False

    def fail_decisions(path: Path, payload: bytes, *, resume: bool) -> None:
        nonlocal failed_once
        if path == decisions_path and not failed_once:
            failed_once = True
            raise OSError("injected decision publish failure")
        original_publish(path, payload, resume=resume)

    monkeypatch.setattr(
        cli_module, "_ensure_disclosure_review_artifact", fail_decisions
    )
    command = _record_command(tmp_path)
    assert main(command) == 2
    run_card = tmp_path / (
        "private-review/recorder-metadata/run-cards/record-disclosure-review-decisions.json"
    )
    assert json.loads(run_card.read_text())["status"] == "failed"

    batch_prompts: list[str] = []

    def resume_answer(prompt: str) -> str:
        batch_prompts.append(prompt)
        return prompt.removeprefix("Type exactly '").removesuffix("': ")

    monkeypatch.setattr(builtins, "input", resume_answer)
    assert main(command) == 0
    assert len(batch_prompts) == 1


def test_malformed_private_map_failure_is_durable_and_resumable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert main(_prepare_args(tmp_path)) == 0
    inspection_map = tmp_path / "private-review/private-document-inspection-map.jsonl"
    original = inspection_map.read_bytes()
    inspection_map.write_bytes(b"{malformed\n")
    command = _record_command(tmp_path)
    monkeypatch.setattr(cli_module.sys, "stdin", _TTY())
    assert main(command) == 2
    run_card = tmp_path / (
        "private-review/recorder-metadata/run-cards/record-disclosure-review-decisions.json"
    )
    assert json.loads(run_card.read_text())["status"] == "failed"

    inspection_map.write_bytes(original)
    _complete_recorder(tmp_path, monkeypatch)
    assert json.loads(run_card.read_text())["status"] == "completed"


def test_terminal_log_failure_preserves_completion_and_resume_repairs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    args = _prepare_args(tmp_path)
    original_append = cli_module._append_disclosure_review_log
    failed_once = False

    def fail_terminal_log(path: Path, records: Iterable[Mapping[str, Any]]) -> None:
        nonlocal failed_once
        if not failed_once:
            failed_once = True
            raise OSError("injected terminal log fsync failure")
        original_append(path, records)

    monkeypatch.setattr(cli_module, "_append_disclosure_review_log", fail_terminal_log)
    assert main(args) == 2
    run_card = tmp_path / "output/run-cards/prepare-disclosure-review.json"
    log = tmp_path / "output/logs/prepare-disclosure-review.jsonl"
    assert json.loads(run_card.read_text())["status"] == "completed"
    assert not log.exists()
    completed_before = (run_card.read_bytes(), run_card.stat().st_mtime_ns)

    monkeypatch.setattr(cli_module, "_append_disclosure_review_log", original_append)
    assert main(args) == 0
    assert (run_card.read_bytes(), run_card.stat().st_mtime_ns) == completed_before
    [terminal] = [json.loads(line) for line in log.read_text().splitlines()]
    assert terminal["status"] == "completed"
