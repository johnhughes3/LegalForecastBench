"""Focused invariants for the one-document exact-100 successor."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import legalforecast.cli as legalforecast_cli
import pytest
from legalforecast.contracts import EXACT100_SUCCESSOR_REPLACEMENT_STATE_V2
from legalforecast.ingestion import supporting_document_successor_cli as successor_cli
from legalforecast.ingestion.disclosure_clearance import require_clearance_policy
from legalforecast.ingestion.free_document_downloader import (
    FreeDocumentDownloadError,
    FreeDocumentFetch,
)
from legalforecast.ingestion.free_support_memorandum_recovery import (
    FreeSupportMemorandumRecoveryPlan,
)
from legalforecast.ingestion.supporting_document_successor import (
    build_supporting_document_successor,
)


def _record(*, candidate_id: str, source_document_id: str, role: str) -> dict[str, Any]:
    payload = f"{candidate_id}/{source_document_id}".encode()
    return {
        "candidate_id": candidate_id,
        "source_document_id": source_document_id,
        "document_role": role,
        "free_or_purchased": "free",
        "local_path": f"{candidate_id}/{source_document_id}.pdf",
        "sha256": hashlib.sha256(payload).hexdigest(),
        "byte_count": len(payload),
        "source_url": (
            "https://storage.courtlistener.com/recap/gov.uscourts.nysd.663802/"
            "gov.uscourts.nysd.663802.14.0.pdf"
            if source_document_id == "73327542-entry-14-motion-to-dismiss-memorandum"
            else "https://storage.courtlistener.com/recap/example.pdf"
        ),
        "docket_entry_number": (
            14
            if source_document_id == "73327542-entry-14-motion-to-dismiss-memorandum"
            else 13
        ),
    }


def test_supporting_document_successor_adds_only_bound_ecf14() -> None:
    base = {
        "selection_records": (
            {
                "candidate_id": "73327542",
                "selected": True,
                "documents": [
                    {
                        "source_document_id": "73327542-entry-13-notice",
                        "document_role": "motion_to_dismiss_notice",
                    }
                ],
            },
            {"candidate_id": "other", "selected": True, "documents": []},
        ),
        "case_relevance": (
            {"candidate_id": "73327542", "documents": []},
            {"candidate_id": "other", "documents": []},
        ),
        "free_manifest": (
            _record(
                candidate_id="73327542",
                source_document_id="73327542-entry-13-notice",
                role="motion_to_dismiss_notice",
            ),
        ),
        "free_clearance": (),
        "restriction_records": (),
    }
    addition = _record(
        candidate_id="73327542",
        source_document_id="73327542-entry-14-motion-to-dismiss-memorandum",
        role="motion_to_dismiss_memorandum",
    )

    result = build_supporting_document_successor(
        base_projection=base,
        addition=addition,
        addition_clearance={
            **addition,
            "status": "cleared",
            "clearance_basis": "affirmative_public_provenance",
        },
        addition_restriction={
            **addition,
            "restriction_evidence": ["courtlistener_public_download_record_checked"],
            "is_private": False,
            "is_sealed": False,
        },
    )

    assert [row["candidate_id"] for row in result.selection_records] == [
        "73327542",
        "other",
    ]
    support = result.selection_records[0]["documents"][-1]
    assert support == {
        "availability_status": "available",
        "candidate_id": "73327542",
        "contains_target_outcome": False,
        "courtlistener_docket_entry_id": None,
        "description": "Memorandum of Law in Support",
        "docket_entry_number": 14,
        "document_role": "motion_to_dismiss_memorandum",
        "file_extension": "pdf",
        "is_available": True,
        "is_predecision_material": True,
        "is_private": False,
        "is_sealed": False,
        "model_visible": True,
        "redaction_or_seal_status": "public",
        "requires_paid_recovery": False,
        "resolved_from_paid_gap": False,
        "restriction_evidence": ["courtlistener_public_download_record_checked"],
        "source_document_id": "73327542-entry-14-motion-to-dismiss-memorandum",
        "source_provider": "courtlistener_public",
        "source_url": (
            "https://storage.courtlistener.com/recap/gov.uscourts.nysd.663802/"
            "gov.uscourts.nysd.663802.14.0.pdf"
        ),
        "source_url_or_reference": (
            "https://storage.courtlistener.com/recap/gov.uscourts.nysd.663802/"
            "gov.uscourts.nysd.663802.14.0.pdf"
        ),
    }
    assert result.selected_document_keys == frozenset(
        {
            ("73327542", "73327542-entry-13-notice"),
            ("73327542", "73327542-entry-14-motion-to-dismiss-memorandum"),
        }
    )
    assert result.free_manifest[-1] == addition
    support_filter = next(
        row for row in result.core_filter_records if row["candidate_id"] == "73327542"
    )
    assert support_filter["core_mtd_documents"] == [
        "73327542-entry-14-motion-to-dismiss-memorandum"
    ]


def test_successor_rejects_symlinked_output_before_source_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The public fetch seam is unreachable through a symlinked output parent."""

    v2_root = tmp_path / "v2"
    (v2_root / "run-cards").mkdir(parents=True)
    selection = v2_root / "target-cohort-selection.jsonl"
    selection.write_bytes(
        b'{"candidate_id":"73327542","documents":[],"selected":true}\n'
    )
    plan_path = tmp_path / "plan.json"
    plan_path.write_bytes(b"{}\n")
    bridge = tmp_path / "bridge.json"
    bridge.write_bytes(b"{}\n")
    outside = tmp_path / "outside"
    outside.mkdir()
    link = tmp_path / "linked-output"
    link.symlink_to(outside, target_is_directory=True)
    calls: list[str] = []

    class Source:
        def fetch(self, source_url: str) -> FreeDocumentFetch:
            calls.append(source_url)
            return FreeDocumentFetch(content=b"unexpected")

    plan = FreeSupportMemorandumRecoveryPlan(
        record={
            "candidate_id": "73327542",
            "source_document_id": "73327542-entry-14-motion-to-dismiss-memorandum",
            "supporting_entry_number": 14,
            "document_role": "motion_to_dismiss_memorandum",
            "source_url": (
                "https://storage.courtlistener.com/recap/gov.uscourts.nysd.663802/"
                "gov.uscourts.nysd.663802.14.0.pdf"
            ),
        },
        record_bytes=b"{}\n",
    )
    monkeypatch.setattr(successor_cli, "_verified_plan", lambda *_args: plan)
    projection: dict[str, object] = {
        "selection_path": selection,
        "selection_bytes": selection.read_bytes(),
        "selection_records": (),
        "case_relevance": (),
        "free_manifest": (),
        "purchased_manifest": (),
        "free_clearance": (),
        "purchased_clearance": (),
        "restriction_records": (),
    }

    with pytest.raises(successor_cli.SupportingDocumentSuccessorCliError):
        successor_cli._run_with_test_dependencies(
            v2_root=v2_root,
            plan_path=plan_path,
            bridge_descriptor=bridge,
            output_root=link / "successor",
            verifier=lambda _root: projection,
            source=Source(),
        )

    assert calls == []
    assert list(outside.iterdir()) == []


def _exact100_executor_fixture(
    tmp_path: Path,
) -> tuple[
    Path,
    Path,
    Path,
    dict[str, object],
    FreeSupportMemorandumRecoveryPlan,
]:
    v2_root = tmp_path / "v2"
    (v2_root / "run-cards").mkdir(parents=True)
    historical = tmp_path / "historical"
    (historical / "documents").mkdir(parents=True)
    promoted: list[dict[str, Any]] = []
    promoted_clearance: list[dict[str, Any]] = []
    promoted_documents: list[dict[str, Any]] = []
    for index in range(5):
        payload = f"promoted-{index}".encode()
        local_path = f"72309378/doc-{index}.pdf"
        record = {
            "candidate_id": "72309378",
            "source_document_id": f"72309378-doc-{index}",
            "document_role": "other_predecision",
            "free_or_purchased": "free",
            "local_path": local_path,
            "sha256": hashlib.sha256(payload).hexdigest(),
            "byte_count": len(payload),
            "source_url": f"https://storage.courtlistener.com/{index}.pdf",
        }
        promoted.append(record)
        promoted_clearance.append({**record, "status": "cleared"})
        promoted_documents.append(
            {
                "source_document_id": record["source_document_id"],
                "document_role": record["document_role"],
            }
        )
        destination = historical / "documents" / local_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
    (historical / "free-document-downloads.jsonl").write_bytes(
        b"".join(
            (json.dumps(record, sort_keys=True) + "\n").encode() for record in promoted
        )
    )
    selection_records: list[dict[str, Any]] = []
    relevance: list[dict[str, Any]] = []
    for index in range(100):
        candidate_id = (
            "73327542" if index == 0 else "72309378" if index == 1 else f"c{index:03d}"
        )
        documents = promoted_documents if candidate_id == "72309378" else []
        selection_records.append(
            {"candidate_id": candidate_id, "selected": True, "documents": documents}
        )
        relevance.append({"candidate_id": candidate_id, "documents": []})
    selection_bytes = b"".join(
        successor_cli._bytes(record) for record in selection_records
    )
    selection_path = v2_root / "target-cohort-selection.jsonl"
    selection_path.write_bytes(selection_bytes)
    inputs = [str(tmp_path / f"input-{index}") for index in range(6)] + [
        str(historical)
    ]
    complete = Path(inputs[1]) / "01-materialized"
    (complete / "documents").mkdir(parents=True)
    (complete / "document-downloads-merged.jsonl").write_bytes(b"")
    promotion_path = v2_root / "successor-promotions.jsonl"
    promotion_bytes = successor_cli._bytes({"candidate_id": "72309378"})
    promotion_path.write_bytes(promotion_bytes)
    projection: dict[str, object] = {
        "run_card": {
            "schema_version": str(EXACT100_SUCCESSOR_REPLACEMENT_STATE_V2),
            "input_paths": inputs,
        },
        "selection_path": selection_path,
        "selection_bytes": selection_bytes,
        "selection_records": tuple(selection_records),
        "case_relevance": tuple(relevance),
        "free_manifest": tuple(promoted),
        "purchased_manifest": (),
        "free_clearance": tuple(promoted_clearance),
        "purchased_clearance": (),
        "restriction_records": (),
        "verified_artifact_bytes": {
            str(selection_path.absolute()): selection_bytes,
            str(promotion_path.absolute()): promotion_bytes,
        },
    }
    plan_path = tmp_path / "plan.json"
    plan_path.write_bytes(b"{}\n")
    bridge = tmp_path / "bridge.json"
    bridge.write_bytes(b"{}\n")
    plan = FreeSupportMemorandumRecoveryPlan(
        record={
            "candidate_id": "73327542",
            "source_document_id": "73327542-entry-14-motion-to-dismiss-memorandum",
            "supporting_entry_number": 14,
            "document_role": "motion_to_dismiss_memorandum",
            "source_url": successor_cli.SUPPORT_SOURCE_URL,
        },
        record_bytes=b"{}\n",
    )
    return v2_root, plan_path, bridge, projection, plan


def test_successor_executor_writes_replays_and_detects_tamper(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    v2_root, plan_path, bridge, projection, plan = _exact100_executor_fixture(tmp_path)
    monkeypatch.setattr(successor_cli, "_verified_plan", lambda *_args: plan)
    monkeypatch.setattr(
        successor_cli,
        "scan_disclosure_document",
        lambda _payload: SimpleNamespace(
            automated_markers=(), coverage_status="complete"
        ),
    )

    class Source:
        def fetch(self, source_url: str) -> FreeDocumentFetch:
            assert source_url == successor_cli.SUPPORT_SOURCE_URL
            return FreeDocumentFetch(content=b"%PDF-1.4\nECF14\n")

    output = tmp_path / "successor"

    def verifier(_root: Path) -> dict[str, object]:
        return projection

    assert (
        successor_cli._run_with_test_dependencies(
            v2_root=v2_root,
            plan_path=plan_path,
            bridge_descriptor=bridge,
            output_root=output,
            verifier=verifier,
            source=Source(),
            resume=False,
        )
        == 0
    )
    fresh_result = json.loads(capsys.readouterr().out)
    assert fresh_result["provider_activity_executed"] is True
    supplemental = successor_cli._jsonl(
        (output / successor_cli._OUTPUTS["supplemental_manifest"]).read_bytes(),
        "supplemental manifest",
    )
    assert len(supplemental) == 6
    supplemental_clearance = successor_cli._jsonl(
        (output / successor_cli._OUTPUTS["supplemental_clearance"]).read_bytes(),
        "supplemental clearance",
    )
    added_clearance = supplemental_clearance[-1]
    require_clearance_policy(
        added_clearance,
        key=(
            str(added_clearance["candidate_id"]),
            str(added_clearance["source_document_id"]),
        ),
        label="supporting successor document",
    )
    state = successor_cli._object(
        (output / successor_cli._OUTPUTS["state"]).read_bytes(), "successor state"
    )
    assert state["provider_activity_executed"] is True
    assert (
        len(
            successor_cli._jsonl(
                (output / successor_cli._OUTPUTS["selection"]).read_bytes(),
                "selection",
            )
        )
        == 100
    )
    verified = successor_cli.verify_supporting_document_successor_projection(
        output, verifier=verifier
    )
    monkeypatch.setattr(
        legalforecast_cli,
        "_verify_materializer_projection",
        lambda **_kwargs: verified,
    )
    outer, recovery_selection_path, recovery_selection = (
        legalforecast_cli._materializer_consolidated_target_inputs(
            target_root=output,
            free_clearance_path=output / "disclosure-clearance.jsonl",
            preparation_summary_path=tmp_path / "preparation-summary.json",
            preparation_config_path=tmp_path / "preparation-config.json",
            snapshot_manifest_path=tmp_path / "snapshot.json",
            expected_target_count=100,
        )
    )
    assert outer is verified
    assert recovery_selection_path == projection["selection_path"]
    assert recovery_selection == list(projection["selection_records"])  # type: ignore[arg-type]
    recovery_projection = {
        **projection,
        "selection_records": [
            dict(row)
            for row in projection["selection_records"]  # type: ignore[union-attr]
        ],
    }
    assert (
        legalforecast_cli._select_materializer_projection_after_recovery(
            outer_projection=outer,
            recovery_projection=recovery_projection,
            recovery_selection=recovery_selection,
        )
        is verified
    )
    assert recovery_projection is not verified
    with pytest.raises(
        legalforecast_cli.CommandError,
        match="recovery projection selection differs",
    ):
        legalforecast_cli._select_materializer_projection_after_recovery(
            outer_projection=outer,
            recovery_projection={**recovery_projection, "selection_records": []},
            recovery_selection=recovery_selection,
        )
    with pytest.raises(
        legalforecast_cli.CommandError,
        match="supporting-document successor base selection differs",
    ):
        legalforecast_cli._select_materializer_projection_after_recovery(
            outer_projection={
                **verified,
                "base_v2_projection": {
                    **projection,
                    "selection_records": [],
                },
            },
            recovery_projection=recovery_projection,
            recovery_selection=recovery_selection,
        )
    monkeypatch.setattr(
        legalforecast_cli,
        "_verify_materializer_projection",
        lambda **_kwargs: {
            **verified,
            "base_v2_projection": {
                **projection,
                "selection_records": [*recovery_selection, "not-an-object"],
            },
        },
    )
    with pytest.raises(
        legalforecast_cli.CommandError,
        match="base selection must contain only objects",
    ):
        legalforecast_cli._materializer_consolidated_target_inputs(
            target_root=output,
            free_clearance_path=output / "disclosure-clearance.jsonl",
            preparation_summary_path=tmp_path / "preparation-summary.json",
            preparation_config_path=tmp_path / "preparation-config.json",
            snapshot_manifest_path=tmp_path / "snapshot.json",
            expected_target_count=100,
        )
    sources = legalforecast_cli._materializer_successor_v2_free_sources(
        verified,
        preparation_root=tmp_path / "preparation",
        consolidated_recovery=True,
    )
    assert len(sources) == 2
    assert len(sources[0].manifest) == 0
    assert len(sources[1].manifest) == 6
    assert (
        successor_cli._run_with_test_dependencies(
            v2_root=v2_root,
            plan_path=plan_path,
            bridge_descriptor=bridge,
            output_root=output,
            verifier=verifier,
            source=Source(),
            resume=True,
        )
        == 0
    )
    resumed_result = json.loads(capsys.readouterr().out)
    assert resumed_result["provider_activity_executed"] is False
    monkeypatch.setattr(
        successor_cli,
        "scan_disclosure_document",
        lambda _payload: SimpleNamespace(
            automated_markers=("restricted",), coverage_status="complete"
        ),
    )
    with pytest.raises(
        successor_cli.SupportingDocumentSuccessorCliError,
        match="not cleared on replay",
    ):
        successor_cli.verify_supporting_document_successor_projection(
            output, verifier=verifier
        )
    monkeypatch.setattr(
        successor_cli,
        "scan_disclosure_document",
        lambda _payload: SimpleNamespace(
            automated_markers=(), coverage_status="complete"
        ),
    )
    supplemental_path = output / successor_cli._OUTPUTS["supplemental_manifest"]
    original_supplemental = supplemental_path.read_bytes()
    changed = list(supplemental)
    changed[0] = {**changed[0], "byte_count": 999}
    supplemental_path.write_bytes(
        b"".join(successor_cli._bytes(row) for row in changed)
    )
    with pytest.raises(successor_cli.SupportingDocumentSuccessorCliError):
        successor_cli.verify_supporting_document_successor_projection(
            output, verifier=verifier
        )
    supplemental_path.write_bytes(original_supplemental)
    promoted_path = output / "supplemental-free-source/documents/72309378/doc-0.pdf"
    promoted_path.write_bytes(b"tampered")
    with pytest.raises(
        successor_cli.SupportingDocumentSuccessorCliError,
        match="supplemental promoted bytes differ",
    ):
        successor_cli.verify_supporting_document_successor_projection(
            output, verifier=verifier
        )


def test_verified_v2_requires_exactly_100_selected_candidates(tmp_path: Path) -> None:
    v2_root, _plan_path, _bridge, projection, _plan = _exact100_executor_fixture(
        tmp_path
    )
    projection["selection_records"] = tuple(
        projection["selection_records"]  # type: ignore[arg-type]
    )[:-1]
    with pytest.raises(
        successor_cli.SupportingDocumentSuccessorCliError,
        match="exact 100 selected candidates",
    ):
        successor_cli._verified_v2(v2_root, lambda _root: projection)


def test_successor_detects_output_ancestor_swap(tmp_path: Path) -> None:
    original_parent = tmp_path / "parent"
    output = original_parent / "successor"
    descriptor = successor_cli._open_output_root_fd(output)
    try:
        moved_parent = tmp_path / "moved-parent"
        original_parent.rename(moved_parent)
        output.mkdir(parents=True)
        with pytest.raises(
            successor_cli.SupportingDocumentSuccessorCliError,
            match="output root changed",
        ):
            successor_cli._require_output_identity(output, descriptor)
    finally:
        os.close(descriptor)


def test_successor_rejects_input_overlap_before_fetch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    v2_root, plan_path, bridge, projection, plan = _exact100_executor_fixture(tmp_path)
    monkeypatch.setattr(successor_cli, "_verified_plan", lambda *_args: plan)
    calls: list[str] = []

    class Source:
        def fetch(self, source_url: str) -> FreeDocumentFetch:
            calls.append(source_url)
            return FreeDocumentFetch(content=b"unexpected")

    with pytest.raises(
        successor_cli.SupportingDocumentSuccessorCliError,
        match="overlaps immutable input",
    ):
        successor_cli._run_with_test_dependencies(
            v2_root=v2_root,
            plan_path=plan_path,
            bridge_descriptor=bridge,
            output_root=v2_root / "nested-output",
            verifier=lambda _root: projection,
            source=Source(),
            resume=False,
        )
    assert calls == []


def test_successor_translates_download_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    v2_root, plan_path, bridge, projection, plan = _exact100_executor_fixture(tmp_path)
    monkeypatch.setattr(successor_cli, "_verified_plan", lambda *_args: plan)

    class Source:
        def fetch(self, source_url: str) -> FreeDocumentFetch:
            assert source_url == successor_cli.SUPPORT_SOURCE_URL
            raise FreeDocumentDownloadError("network unavailable")

    with pytest.raises(
        successor_cli.SupportingDocumentSuccessorCliError,
        match="support memorandum download failed: network unavailable",
    ):
        successor_cli._run_with_test_dependencies(
            v2_root=v2_root,
            plan_path=plan_path,
            bridge_descriptor=bridge,
            output_root=tmp_path / "successor",
            verifier=lambda _root: projection,
            source=Source(),
            resume=False,
        )


def test_purchase_approval_verifier_routes_supporting_successor_without_legacy_card(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target_root = tmp_path / "successor"
    card_path = (
        target_root / "run-cards/project-exact100-supporting-document-successor.json"
    )
    card_path.parent.mkdir(parents=True)
    card_path.write_bytes(
        successor_cli._bytes(
            {
                "schema_version": successor_cli.SCHEMA_VERSION,
                "selected_case_count": 100,
            }
        )
    )
    expected = {"selection_records": ()}
    calls: list[dict[str, object]] = []

    def verify(**kwargs: object) -> dict[str, object]:
        calls.append(dict(kwargs))
        return expected

    monkeypatch.setattr(
        legalforecast_cli,
        "_verify_supporting_document_downstream_projection",
        verify,
    )

    assert (
        legalforecast_cli.verify_completed_target_cohort_projection_for_purchase_approval(
            target_root
        )
        is expected
    )
    assert calls == [
        {
            "target_root": target_root,
            "free_clearance_path": target_root / "disclosure-clearance.jsonl",
            "expected_target_count": 100,
        }
    ]


@pytest.mark.parametrize("payload", [b"not-json\n", b"", b"[]\n"])
def test_legacy_jsonl_rejects_invalid_rows(payload: bytes) -> None:
    with pytest.raises(
        successor_cli.SupportingDocumentSuccessorCliError,
        match="legacy manifest is not JSONL",
    ):
        successor_cli._legacy_jsonl(payload, "legacy manifest")
