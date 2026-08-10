# ruff: noqa: E501

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import legalforecast.ingestion.free_support_memorandum_recovery as support_recovery
import pytest
from legalforecast.ingestion.target_raw_docket_auxiliary_provenance import (
    VerifiedTargetRawDocketAuxiliaryProvenanceBridge,
)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _raw_html(
    *,
    reference: str = "re: 13",
    document_rows: str | None = None,
) -> bytes:
    if document_rows is None:
        document_rows = """
          <div class="row recap-documents">
            <div>Main Document</div><div>Memorandum of Law in Support</div>
            <a href="https://storage.courtlistener.com/recap/gov.uscourts.nysd.1/gov.uscourts.nysd.1.14.0.pdf">Download PDF</a>
          </div>
        """
    return f"""
    <html><body><div id="docket-entry-table">
      <div id="entry-14" class="row">
        <div class="col-xs-1">14</div><div class="col-xs-3">Jul 6, 2026</div>
        <div class="col-xs-8">14 Jul 6, 2026 MEMORANDUM OF LAW in Support {reference} FIRST MOTION to Dismiss.
          {document_rows}
        </div>
      </div>
    </div></body></html>
    """.encode()


def _bridge(
    tmp_path: Path,
    *,
    raw_html: bytes | None = None,
    target_entries: list[int] | None = None,
    selected_ids: tuple[str, ...] = ("courtlistener-docket-73327542",),
) -> VerifiedTargetRawDocketAuxiliaryProvenanceBridge:
    raw_html = _raw_html() if raw_html is None else raw_html
    target_entries = [13] if target_entries is None else target_entries
    selection = (
        json.dumps(
            {
                "candidate_id": "73327542",
                "selected": True,
                "target_motion_entry_numbers": target_entries,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()
    selection_path = tmp_path / "selection.jsonl"
    selection_path.write_bytes(selection)
    descriptor = {
        "schema_version": "legalforecast.target_raw_docket_auxiliary_provenance_bridge.v1",
        "bridge": {
            "selection": {
                "path": "selection.jsonl",
                "sha256": _sha256(selection),
                "candidate_count": 100,
                "candidate_id_set_sha256": "a" * 64,
            }
        },
        "bridge_sha256": "b" * 64,
    }
    descriptor_bytes = json.dumps(
        descriptor, sort_keys=True, separators=(",", ":")
    ).encode()
    descriptor_path = tmp_path / "bridge.json"
    descriptor_path.write_bytes(descriptor_bytes)
    return VerifiedTargetRawDocketAuxiliaryProvenanceBridge(
        bridge_path=descriptor_path,
        bridge_sha256=_sha256(descriptor_bytes),
        raw_artifacts_manifest_path=tmp_path / "raw-artifacts.jsonl",
        raw_artifacts_manifest_sha256="c" * 64,
        run_card_path=tmp_path / "bridge-run-card.json",
        run_card_sha256="d" * 64,
        source_snapshot_path=tmp_path / "source",
        source_snapshot_manifest_sha256="e" * 64,
        source_raw_html_dir=tmp_path / "raw-html",
        selected_candidate_ids=selected_ids,
        raw_artifact_bytes_by_candidate={
            "courtlistener-docket-73327542": raw_html,
        },
        raw_artifact_bytes_by_path={},
    )


def _derive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    **bridge_kwargs: object,
) -> tuple[
    VerifiedTargetRawDocketAuxiliaryProvenanceBridge,
    support_recovery.FreeSupportMemorandumRecoveryPlan,
]:
    """Exercise the public descriptor-only API behind an authenticated seam."""

    bridge = _bridge(tmp_path, **bridge_kwargs)  # type: ignore[arg-type]
    monkeypatch.setattr(
        support_recovery,
        "load_verified_target_raw_docket_auxiliary_provenance_bridge",
        lambda descriptor_path: bridge,
    )
    return bridge, support_recovery.derive_free_support_memorandum_recovery_plan(
        bridge_descriptor_path=bridge.bridge_path
    )


def test_derives_the_only_free_support_memorandum_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bridge, plan = _derive(tmp_path, monkeypatch)

    assert (
        plan.record["schema_version"]
        == support_recovery.FREE_SUPPORT_MEMORANDUM_RECOVERY_PLAN_SCHEMA
    )
    assert plan.record["candidate_id"] == "73327542"
    assert plan.record["target_motion_entry_number"] == 13
    assert plan.record["supporting_entry_number"] == 14
    assert plan.record["source_document_id"] == (
        "73327542-entry-14-motion-to-dismiss-memorandum"
    )
    assert plan.record["document_role"] == "motion_to_dismiss_memorandum"
    assert plan.record["source_url"] == (
        "https://storage.courtlistener.com/recap/gov.uscourts.nysd.1/"
        "gov.uscourts.nysd.1.14.0.pdf"
    )
    assert all(
        value is False
        for key, value in plan.record.items()
        if key.endswith("_permitted")
    )
    assert (
        support_recovery.verify_free_support_memorandum_recovery_plan(
            persisted_plan_bytes=plan.record_bytes,
            bridge_descriptor_path=bridge.bridge_path,
        ).record_bytes
        == plan.record_bytes
    )


@pytest.mark.parametrize(
    ("raw_html", "match"),
    [
        (_raw_html(reference="re: 12"), "explicit support memorandum"),
        (_raw_html(reference="re: 13-1234"), "explicit support memorandum"),
        (
            _raw_html(
                document_rows="""
                <div class="row recap-documents"><div>Attachment 1</div><div>Exhibit</div>
                <a href="https://storage.courtlistener.com/recap/a.pdf">Download PDF</a></div>
                """
            ),
            "exactly one free main document",
        ),
        (
            _raw_html(
                document_rows="""
                <div class="row recap-documents"><div>Main Document</div><div>Memo</div>
                <a class="open_buy_pacer_modal" href="https://ecf.example.invalid/doc">Buy on PACER</a></div>
                """
            ),
            "exactly one free main document",
        ),
        (
            _raw_html(
                document_rows="""
                <div class="row recap-documents"><div>Main Document</div><div>Memo</div>
                <a href="https://example.invalid/recap/a.pdf">Download PDF</a></div>
                """
            ),
            "not canonical CourtListener storage",
        ),
    ],
)
def test_rejects_bad_support_document_or_linkage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, raw_html: bytes, match: str
) -> None:
    with pytest.raises(
        support_recovery.FreeSupportMemorandumRecoveryError, match=match
    ):
        _derive(tmp_path, monkeypatch, raw_html=raw_html)


def test_rejects_wrong_selected_target_or_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(
        support_recovery.FreeSupportMemorandumRecoveryError, match="not entry 13"
    ):
        _derive(tmp_path, monkeypatch, target_entries=[12])

    with pytest.raises(
        support_recovery.FreeSupportMemorandumRecoveryError, match="does not select"
    ):
        _derive(
            tmp_path,
            monkeypatch,
            selected_ids=("courtlistener-docket-70000000",),
        )


def test_persisted_plan_rejects_noncanonical_or_drifted_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bridge, plan = _derive(tmp_path, monkeypatch)

    with pytest.raises(
        support_recovery.FreeSupportMemorandumRecoveryError, match="not canonical"
    ):
        support_recovery.verify_free_support_memorandum_recovery_plan(
            persisted_plan_bytes=plan.record_bytes.rstrip(b"\n"),
            bridge_descriptor_path=bridge.bridge_path,
        )

    extra_output_root = dict(plan.record)
    extra_output_root["output_root"] = "/tmp/overlap"
    with pytest.raises(
        support_recovery.FreeSupportMemorandumRecoveryError, match="differs"
    ):
        support_recovery.verify_free_support_memorandum_recovery_plan(
            persisted_plan_bytes=(
                json.dumps(extra_output_root, sort_keys=True, separators=(",", ":"))
                + "\n"
            ).encode(),
            bridge_descriptor_path=bridge.bridge_path,
        )

    drifted = replace(
        bridge,
        raw_artifact_bytes_by_candidate={
            "courtlistener-docket-73327542": bridge.raw_artifact_bytes_by_candidate[
                "courtlistener-docket-73327542"
            ]
            + b" ",
        },
    )
    with pytest.raises(
        support_recovery.FreeSupportMemorandumRecoveryError, match="differs"
    ):
        monkeypatch.setattr(
            support_recovery,
            "load_verified_target_raw_docket_auxiliary_provenance_bridge",
            lambda descriptor_path: drifted,
        )
        support_recovery.verify_free_support_memorandum_recovery_plan(
            persisted_plan_bytes=plan.record_bytes,
            bridge_descriptor_path=bridge.bridge_path,
        )


def test_rejects_drifted_bridge_descriptor_or_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bridge, _ = _derive(tmp_path, monkeypatch)
    bridge.bridge_path.write_bytes(b"{}")
    with pytest.raises(
        support_recovery.FreeSupportMemorandumRecoveryError,
        match="descriptor drifted",
    ):
        support_recovery.derive_free_support_memorandum_recovery_plan(
            bridge_descriptor_path=bridge.bridge_path
        )

    bridge, _ = _derive(tmp_path, monkeypatch)
    selection_path = tmp_path / "selection.jsonl"
    selection_path.write_text(
        '{"candidate_id":"73327542","selected":true,"target_motion_entry_numbers":[13]} \n'
    )
    with pytest.raises(
        support_recovery.FreeSupportMemorandumRecoveryError,
        match="selection artifact drifted",
    ):
        support_recovery.derive_free_support_memorandum_recovery_plan(
            bridge_descriptor_path=bridge.bridge_path
        )


def test_public_api_rejects_caller_constructed_bridge(
    tmp_path: Path,
) -> None:
    bridge = _bridge(tmp_path)

    with pytest.raises(
        support_recovery.FreeSupportMemorandumRecoveryError, match="descriptor path"
    ):
        support_recovery.derive_free_support_memorandum_recovery_plan(
            bridge_descriptor_path=bridge  # type: ignore[arg-type]
        )
