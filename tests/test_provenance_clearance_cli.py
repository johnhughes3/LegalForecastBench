from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

import legalforecast.cli as cli_module
import pytest
from legalforecast.cli import main
from legalforecast.ingestion.disclosure_clearance import DisclosureClearanceError
from legalforecast.ingestion.provenance_clearance import (
    build_provenance_clearance_plan as build_plan,
)


class _TTY:
    @staticmethod
    def isatty() -> bool:
        return True


def _jsonl(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _inputs(tmp_path: Path) -> dict[str, Path]:
    document_root = tmp_path / "documents"
    document_root.mkdir()
    manifest: list[dict[str, object]] = []
    restrictions: list[dict[str, object]] = []
    relevance_documents: list[dict[str, object]] = []
    for document_id, payload in (
        ("auto", b"auto"),
        ("marker", b"marker"),
        ("sealed", b"sealed"),
    ):
        relative_path = f"case-a/{document_id}.pdf"
        target = document_root / relative_path
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(payload)
        digest = hashlib.sha256(payload).hexdigest()
        source_url = f"https://storage.courtlistener.com/recap/case/{document_id}.pdf"
        manifest.append(
            {
                "candidate_id": "case-a",
                "source_document_id": document_id,
                "local_path": relative_path,
                "sha256": digest,
                "byte_count": len(payload),
                "free_or_purchased": "free",
                "source_provider": "courtlistener",
                "source_url": source_url,
            }
        )
        evidence = ["courtlistener_public_download_record_checked"]
        if document_id == "sealed":
            evidence = ["courtlistener_recap_document_is_sealed_true"]
        restrictions.append(
            {
                "candidate_id": "case-a",
                "source_document_id": document_id,
                "restriction_status": "public",
                "restriction_evidence": evidence,
                "is_sealed": None,
                "is_private": None,
            }
        )
        relevance_documents.append(
            {
                "source_document_id": document_id,
                "source_url_or_reference": source_url,
                "model_visible": True,
                "contains_target_outcome": False,
            }
        )
    requests = [
        {
            "schema_version": "legalforecast.disclosure_review_request.v1",
            "candidate_id": source["candidate_id"],
            "source_document_id": source["source_document_id"],
            "sha256": source["sha256"],
            "byte_count": source["byte_count"],
            "free_or_purchased": source["free_or_purchased"],
            "restriction_status": restriction["restriction_status"],
            "restriction_evidence": restriction["restriction_evidence"],
            "required_human_decision": "cleared_or_quarantined",
        }
        for source, restriction in zip(manifest, restrictions, strict=True)
    ]
    paths = {
        "requests": tmp_path / "requests.jsonl",
        "manifest": tmp_path / "manifest.jsonl",
        "restrictions": tmp_path / "restrictions.jsonl",
        "relevance": tmp_path / "case-relevance.jsonl",
        "document_root": document_root,
        "output": tmp_path / "output",
        "private": tmp_path.parent / f"{tmp_path.name}-private",
    }
    _jsonl(paths["requests"], requests)
    _jsonl(paths["manifest"], manifest)
    _jsonl(paths["restrictions"], restrictions)
    _jsonl(
        paths["relevance"],
        [{"candidate_id": "case-a", "documents": relevance_documents}],
    )
    return paths


def _install_marker_scanner(monkeypatch: pytest.MonkeyPatch) -> None:
    def deterministic_plan(
        review_requests: Sequence[Mapping[str, object]],
        download_manifest: Sequence[Mapping[str, object]],
        restriction_evidence: Sequence[Mapping[str, object]],
        case_relevance: Sequence[Mapping[str, object]],
        **kwargs: object,
    ) -> dict[str, object]:
        typed = kwargs
        return build_plan(
            review_requests,
            download_manifest,
            restriction_evidence,
            case_relevance,
            document_root=cast(Path, typed["document_root"]),
            review_requests_bytes=cast(bytes, typed["review_requests_bytes"]),
            download_manifest_bytes=cast(bytes, typed["download_manifest_bytes"]),
            restriction_evidence_bytes=cast(bytes, typed["restriction_evidence_bytes"]),
            case_relevance_bytes=cast(bytes, typed["case_relevance_bytes"]),
            marker_scanner=lambda payload: (
                ("extraction_page_count_mismatch",) if payload == b"marker" else ()
            ),
        )

    monkeypatch.setattr(
        cli_module, "build_provenance_clearance_plan", deterministic_plan
    )


def _plan_command(paths: Mapping[str, Path]) -> list[str]:
    return [
        "acquisition",
        "plan-disclosure-provenance",
        "--review-requests",
        str(paths["requests"]),
        "--download-manifest",
        str(paths["manifest"]),
        "--case-relevance",
        str(paths["relevance"]),
        "--restriction-evidence",
        str(paths["restrictions"]),
        "--document-root",
        str(paths["document_root"]),
        "--controlled-private-store-root",
        str(paths["private"]),
        "--output-root",
        str(paths["output"]),
        "--execute",
    ]


def test_provenance_planner_and_interactive_exception_recorder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _inputs(tmp_path)
    _install_marker_scanner(monkeypatch)
    assert main(_plan_command(paths)) == 0

    plan = json.loads((paths["output"] / "disclosure-provenance-plan.json").read_text())
    assert (plan["auto_clear_count"], plan["john_review_count"]) == (1, 2)
    run_card = json.loads(
        (paths["output"] / "run-cards/plan-disclosure-provenance.json").read_text()
    )
    document_tree_sha256 = run_card["source_commitments"]["document_root"][
        "tree_sha256"
    ]
    assert document_tree_sha256.startswith("sha256:")
    assert not document_tree_sha256.startswith("sha256:sha256:")
    worksheet = json.loads(
        (paths["output"] / "disclosure-exception-worksheet.json").read_text()
    )
    digests = {
        str(row["source_document_id"]): str(row["sha256"])
        for row in worksheet["documents"]
    }
    monkeypatch.setattr(cli_module.sys, "stdin", _TTY())
    digest_iterator = iter(digests.values())
    decision_iterator = iter(("cleared", "quarantined"))

    def ordered_answer(prompt: str) -> str:
        if prompt.startswith("Type the full inspected"):
            return next(digest_iterator)
        if prompt.startswith("Decision"):
            return next(decision_iterator)
        return prompt.removeprefix("Type exactly '").removesuffix("': ")

    monkeypatch.setattr("builtins.input", ordered_answer)
    assert (
        main(
            [
                "acquisition",
                "record-disclosure-review-decisions",
                "--review-worksheet",
                str(paths["output"] / "disclosure-exception-worksheet.json"),
                "--private-inspection-map",
                str(paths["private"] / "private-document-inspection-map.jsonl"),
                "--reviewer-id",
                "John Hughes",
                "--controlled-private-store-root",
                str(paths["private"]),
                "--output-root",
                str(paths["private"] / "metadata"),
                "--execute",
            ]
        )
        == 0
    )
    decisions = paths["private"] / "disclosure-review-decisions.jsonl"
    decision_rows = [json.loads(line) for line in decisions.read_text().splitlines()]
    assert [row["status"] for row in decision_rows] == ["cleared", "quarantined"]
    recorder_card = paths["private"] / (
        "metadata/run-cards/record-disclosure-review-decisions.json"
    )
    recorder = json.loads(recorder_card.read_text())
    assert recorder["authentication_claim"] == "interactive_hash_confirmation_only"
    assert recorder["routing_plan_sha256"] == worksheet["routing_plan_sha256"]

    cohort_policy = tmp_path / "cohort-policy.json"
    cohort_policy.write_text("{}\n", encoding="utf-8")

    def verify_fixture_policy(_policy: Mapping[str, object]) -> str:
        return "1" * 64

    monkeypatch.setattr(cli_module, "verify_cohort_policy", verify_fixture_policy)
    assert (
        main(
            [
                "acquisition",
                "clear-provenance-disclosures",
                "--review-requests",
                str(paths["requests"]),
                "--download-manifest",
                str(paths["manifest"]),
                "--case-relevance",
                str(paths["relevance"]),
                "--restriction-evidence",
                str(paths["restrictions"]),
                "--document-root",
                str(paths["document_root"]),
                "--routing-plan",
                str(paths["output"] / "disclosure-provenance-plan.json"),
                "--exception-worksheet",
                str(paths["output"] / "disclosure-exception-worksheet.json"),
                "--exception-decisions",
                str(decisions),
                "--exception-review-run-card",
                str(recorder_card),
                "--cohort-policy",
                str(cohort_policy),
                "--output-root",
                str(tmp_path / "clearance"),
                "--execute",
            ]
        )
        == 0
    )
    clearance_rows = [
        json.loads(line)
        for line in (tmp_path / "clearance/disclosure-clearance.jsonl")
        .read_text()
        .splitlines()
    ]
    by_id = {row["source_document_id"]: row for row in clearance_rows}
    assert by_id["auto"]["clearance_basis"] == "affirmative_public_provenance"
    assert by_id["marker"]["clearance_basis"] == "john_exception_review"
    assert by_id["marker"]["status"] == "cleared"
    assert by_id["sealed"]["status"] == "quarantined"
    clearance_path = tmp_path / "clearance/disclosure-clearance.jsonl"
    clearance_card = tmp_path / "clearance/run-cards/clear-disclosures.json"
    cli_module._verify_authenticated_clearance_run_card(  # pyright: ignore[reportPrivateUsage]
        clearance_path=clearance_path,
        clearance_run_card_path=clearance_card,
        expected_download_manifest_path=paths["manifest"],
        expected_restriction_path=paths["restrictions"],
    )

    tamper_paths = (
        paths["output"] / "disclosure-provenance-plan.json",
        paths["output"] / "disclosure-exception-worksheet.json",
        decisions,
        recorder_card,
        cohort_policy,
        clearance_path,
    )
    for tamper_path in tamper_paths:
        original = tamper_path.read_bytes()
        tamper_path.write_bytes(original + b" ")
        with pytest.raises(cli_module.CommandError):
            cli_module._verify_authenticated_clearance_run_card(  # pyright: ignore[reportPrivateUsage]
                clearance_path=clearance_path,
                clearance_run_card_path=clearance_card,
                expected_download_manifest_path=paths["manifest"],
                expected_restriction_path=paths["restrictions"],
            )
        tamper_path.write_bytes(original)

    marker_path = paths["document_root"] / "case-a/marker.pdf"
    marker_before = marker_path.read_bytes()
    marker_path.write_bytes(b"changed")
    with pytest.raises(cli_module.CommandError):
        cli_module._verify_authenticated_clearance_run_card(  # pyright: ignore[reportPrivateUsage]
            clearance_path=clearance_path,
            clearance_run_card_path=clearance_card,
        )
    marker_path.write_bytes(marker_before)


def test_recorder_rejects_broad_private_root_and_public_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = _inputs(tmp_path)
    _install_marker_scanner(monkeypatch)
    assert main(_plan_command(paths)) == 0
    broad_inspection_map = tmp_path / "private-document-inspection-map.jsonl"
    broad_inspection_map.write_bytes(
        (paths["private"] / "private-document-inspection-map.jsonl").read_bytes()
    )

    assert (
        main(
            [
                "acquisition",
                "record-disclosure-review-decisions",
                "--review-worksheet",
                str(paths["output"] / "disclosure-exception-worksheet.json"),
                "--private-inspection-map",
                str(broad_inspection_map),
                "--reviewer-id",
                "John Hughes",
                "--controlled-private-store-root",
                str(tmp_path),
                "--output-root",
                str(paths["output"] / "public-recorder-metadata"),
                "--decisions-output",
                str(paths["output"] / "public-decisions.jsonl"),
                "--checkpoint-dir",
                str(paths["output"] / "public-checkpoints"),
                "--execute",
            ]
        )
        == 2
    )
    assert "separate from the review worksheet tree" in capsys.readouterr().err
    assert not (paths["output"] / "public-decisions.jsonl").exists()


def test_provenance_finalizer_rejects_hand_authored_decisions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _inputs(tmp_path)
    _install_marker_scanner(monkeypatch)
    assert main(_plan_command(paths)) == 0
    decisions = paths["private"] / "hand-authored.jsonl"
    _jsonl(decisions, [])
    fake_run_card = paths["private"] / "fake-run-card.json"
    fake_run_card.write_text("{}\n", encoding="utf-8")
    cohort_policy = tmp_path / "cohort-policy.json"
    cohort_policy.write_text("{}\n", encoding="utf-8")

    def verify_fixture_policy(_policy: Mapping[str, object]) -> str:
        return "1" * 64

    monkeypatch.setattr(cli_module, "verify_cohort_policy", verify_fixture_policy)

    assert (
        main(
            [
                "acquisition",
                "clear-provenance-disclosures",
                "--review-requests",
                str(paths["requests"]),
                "--download-manifest",
                str(paths["manifest"]),
                "--case-relevance",
                str(paths["relevance"]),
                "--restriction-evidence",
                str(paths["restrictions"]),
                "--document-root",
                str(paths["document_root"]),
                "--routing-plan",
                str(paths["output"] / "disclosure-provenance-plan.json"),
                "--exception-worksheet",
                str(paths["output"] / "disclosure-exception-worksheet.json"),
                "--exception-decisions",
                str(decisions),
                "--exception-review-run-card",
                str(fake_run_card),
                "--cohort-policy",
                str(cohort_policy),
                "--output-root",
                str(tmp_path / "clearance"),
                "--execute",
            ]
        )
        == 2
    )
    assert not (tmp_path / "clearance/disclosure-clearance.jsonl").exists()


def test_zero_exception_cohort_completes_without_prompt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _inputs(tmp_path)
    _install_marker_scanner(monkeypatch)
    for name in ("requests", "manifest", "restrictions"):
        rows = [json.loads(line) for line in paths[name].read_text().splitlines()]
        _jsonl(
            paths[name],
            [row for row in rows if row["source_document_id"] == "auto"],
        )
    relevance = json.loads(paths["relevance"].read_text())
    relevance["documents"] = [
        row for row in relevance["documents"] if row["source_document_id"] == "auto"
    ]
    _jsonl(paths["relevance"], [relevance])
    assert main(_plan_command(paths)) == 0
    worksheet = paths["output"] / "disclosure-exception-worksheet.json"
    assert json.loads(worksheet.read_text())["document_count"] == 0

    def reject_prompt(_prompt: str) -> str:
        pytest.fail("zero exceptions must not prompt")

    monkeypatch.setattr("builtins.input", reject_prompt)
    assert (
        main(
            [
                "acquisition",
                "record-disclosure-review-decisions",
                "--review-worksheet",
                str(worksheet),
                "--private-inspection-map",
                str(paths["private"] / "private-document-inspection-map.jsonl"),
                "--reviewer-id",
                "John Hughes",
                "--controlled-private-store-root",
                str(paths["private"]),
                "--output-root",
                str(paths["private"] / "metadata"),
                "--execute",
            ]
        )
        == 0
    )
    assert (paths["private"] / "disclosure-review-decisions.jsonl").read_bytes() == b""


@pytest.mark.parametrize("private_kind", ["relative", "nested"])
def test_provenance_planner_rejects_private_root_inside_source_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    private_kind: str,
) -> None:
    paths = _inputs(tmp_path)
    _install_marker_scanner(monkeypatch)
    paths["private"] = (
        Path(f"relative-private-{tmp_path.name}")
        if private_kind == "relative"
        else tmp_path / "nested-private"
    )
    assert main(_plan_command(paths)) == 2
    assert not (paths["private"] / "private-document-inspection-map.jsonl").exists()


def test_provenance_planner_rejects_symlinked_source_and_document_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _inputs(tmp_path)
    _install_marker_scanner(monkeypatch)
    original_requests = paths["requests"]
    requests_target = tmp_path / "requests-target.jsonl"
    original_requests.replace(requests_target)
    original_requests.symlink_to(requests_target)
    assert main(_plan_command(paths)) == 2
    assert not (paths["output"] / "disclosure-provenance-plan.json").exists()

    original_requests.unlink()
    requests_target.replace(original_requests)
    real_documents = paths["document_root"]
    moved_documents = tmp_path / "real-documents"
    real_documents.replace(moved_documents)
    real_documents.symlink_to(moved_documents, target_is_directory=True)
    assert main(_plan_command(paths)) == 2
    assert not (paths["output"] / "disclosure-provenance-plan.json").exists()


def test_provenance_snapshot_reread_translates_unsafe_path_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unsafe_path(_root: Path, _relative: str) -> Path:
        raise DisclosureClearanceError("document became symlinked")

    monkeypatch.setattr(cli_module, "safe_disclosure_document_path", unsafe_path)

    with pytest.raises(
        cli_module.CommandError,
        match="disclosure document became unsafe during execution",
    ):
        cli_module._require_provenance_document_snapshot_unchanged(
            {"case/document.pdf": b"captured"}, document_root=tmp_path
        )
