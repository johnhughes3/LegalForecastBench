from __future__ import annotations

import copy
import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any, cast

import pytest
from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPurchaseJournal,
    CaseDevPurchasePolicy,
    generate_case_dev_purchase_policy,
    verify_case_dev_purchase_policy,
)
from legalforecast.ingestion.courtlistener_recap_fetch import (
    COURTLISTENER_RECAP_FETCH_PROVIDER,
    CourtListenerRecapFetchError,
)
from legalforecast.ingestion.courtlistener_web import (
    CourtListenerEntryRole,
    CourtListenerWebParseError,
    parse_courtlistener_docket_html,
)
from legalforecast.ingestion.docket_decision_text_source import (
    MANIFEST_BOUND_REST_BASIS,
    RAW_COURTLISTENER_HTML_BASIS,
    DocketDecisionTextSourceError,
    ReplayedDocketDecisionLineage,
    VerifiedDocketDecisionTextSources,
    VerifiedTerminalPurchaseDispositionAuthority,
    _linkage_actual_decision_projection,  # pyright: ignore[reportPrivateUsage]
    _raw_entries_equivalent,  # pyright: ignore[reportPrivateUsage]
    replay_docket_decision_source_lineage,
    require_replayed_docket_decision_lineage,
    residual_terminal_exclusions_bytes,
    verified_docket_decision_document_keys,
    verified_docket_decision_source_records,
    verified_residual_terminal_records,
    verify_docket_decision_text_sources,
)
from legalforecast.ingestion.docket_sync import NormalizedDocketEntry
from legalforecast.ingestion.missing_core_budget import (
    CaseMissingCorePurchasePlan,
    MissingCoreBudgetPlan,
)
from legalforecast.ingestion.mtd_acquisition_screen import (
    screen_courtlistener_docket_for_mtd_decision,
)
from legalforecast.ingestion.provenance import DocumentRole
from legalforecast.ingestion.screening_snapshot_union import (
    UnionRawArtifact,
    VerifiedScreeningSnapshot,
)
from legalforecast.ingestion.terminal_purchase_failure import (
    VerifiedTerminalPurchaseFailureAuthority,
    verify_terminal_purchase_failure_authority,
)
from legalforecast.selection.motion_linkage import link_mtd_dispositions
from tests.purchase_approval_fixtures import allow_historical_v1_algorithm_fixtures

_SELECTION_SHA = "a" * 64
_MANIFEST_SHA = "b" * 64
_CYCLE_SHA = "c" * 64
_BATCH_SHA = "d" * 64
_FILE_SHA = "e" * 64
_ROLE_MAP = {
    CourtListenerEntryRole.MTD_NOTICE: DocumentRole.MTD_NOTICE,
    CourtListenerEntryRole.MTD_MEMORANDUM: DocumentRole.MTD_MEMORANDUM,
    CourtListenerEntryRole.OPPOSITION: DocumentRole.OPPOSITION,
    CourtListenerEntryRole.REPLY: DocumentRole.REPLY,
    CourtListenerEntryRole.EXHIBIT: DocumentRole.OTHER,
    CourtListenerEntryRole.DECISION: DocumentRole.DECISION,
    CourtListenerEntryRole.OTHER: DocumentRole.OTHER,
}


def test_replays_manifest_bound_complete_rest_decision() -> None:
    selection, snapshot = _fixture(raw=False)

    lineage = replay_docket_decision_source_lineage(
        selection_records=[selection],
        selection_payload_sha256=_SELECTION_SHA,
        screening_snapshot=snapshot,
        candidate_id="71942225",
        unavailable_recap_document_id="487196517",
    )
    record = require_replayed_docket_decision_lineage(lineage)

    assert record["source_basis"] == MANIFEST_BOUND_REST_BASIS
    assert record["decision_source_id"] == "docket-entry:71942225:40"
    assert record["unavailable_recap_document_id"] == "487196517"
    assert record["model_visible"] is False
    assert record["audit_only"] is True
    assert record["materialization_required"] is False
    assert (
        record["text_sha256"]
        == hashlib.sha256(str(record["text"]).encode()).hexdigest()
    )
    assert set(record["source_evidence"]) == {
        "schema_version",
        "canonical_rest_screen_complete",
        "reconstruction_proof",
        "decision_entry_evidence",
    }


def test_replays_rest_decision_when_representative_evidence_is_another_entry() -> None:
    selection, snapshot = _fixture(raw=False)
    screen = copy.deepcopy(dict(snapshot.screened[0]))
    motion = next(
        entry for entry in screen["selected_entries"] if entry["entry_number"] == "39"
    )
    screen["decision_entry_evidence"] = {
        "absolute_url": "/docket/71942225/39/example/",
        "description": motion["text"],
        "docket_entry_id": 470378518,
        "document_number": 39,
        "entry_date_filed": "2026-07-01",
        "entry_number": 39,
        "id": 487196516,
    }
    selection_document = selection["documents"][0]
    selection_document["description"] = "Order on Motion to Dismiss"
    selection_document["source_provider"] = "courtlistener+recap-fetch"
    selection_document["source_url"] = (
        "https://www.courtlistener.com/api/rest/v4/recap-documents/487196517/"
    )
    selection_document["source_url_or_reference"] = selection_document["source_url"]
    selection_document["restriction_evidence"] = [
        "courtlistener_rest_docket_exact_match",
        "courtlistener_rest_docket_entry_exact_match",
        "courtlistener_rest_recap_document_exact_match",
        "courtlistener_rest_recap_document_is_available_false",
        "courtlistener_rest_recap_document_seal_status_unknown",
        "courtlistener_rest_no_positive_restriction_marker",
    ]

    lineage = replay_docket_decision_source_lineage(
        selection_records=[selection],
        selection_payload_sha256=_SELECTION_SHA,
        screening_snapshot=_replace_snapshot(snapshot, screens=(screen,)),
        candidate_id="71942225",
        unavailable_recap_document_id="487196517",
    )

    assert (
        require_replayed_docket_decision_lineage(lineage)["decision_entry_number"] == 40
    )


@pytest.mark.parametrize(
    "mutation",
    ("source_url", "source_provider", "restriction", "extra_restriction", "rest_date"),
)
def test_alternate_rest_evidence_requires_exact_selected_document_lineage(
    mutation: str,
) -> None:
    selection, snapshot = _fixture(raw=False)
    screen = copy.deepcopy(dict(snapshot.screened[0]))
    motion = next(
        entry for entry in screen["selected_entries"] if entry["entry_number"] == "39"
    )
    screen["decision_entry_evidence"] = {
        "absolute_url": "/docket/71942225/39/example/",
        "description": motion["text"],
        "docket_entry_id": 470378518,
        "document_number": 39,
        "entry_date_filed": "2026-07-01",
        "entry_number": 39,
        "id": 487196516,
    }
    document = selection["documents"][0]
    document.update(
        {
            "description": "Order on Motion to Dismiss",
            "source_provider": "courtlistener+recap-fetch",
            "source_url": "https://www.courtlistener.com/api/rest/v4/recap-documents/487196517/",
            "source_url_or_reference": "https://www.courtlistener.com/api/rest/v4/recap-documents/487196517/",
            "restriction_evidence": [
                "courtlistener_rest_docket_exact_match",
                "courtlistener_rest_docket_entry_exact_match",
                "courtlistener_rest_recap_document_exact_match",
                "courtlistener_rest_recap_document_is_available_false",
                "courtlistener_rest_recap_document_seal_status_unknown",
                "courtlistener_rest_no_positive_restriction_marker",
            ],
        }
    )
    if mutation == "source_url":
        document["source_url"] = "https://example.test/wrong"
    elif mutation == "source_provider":
        document["source_provider"] = "other"
    elif mutation == "restriction":
        document["restriction_evidence"].remove(
            "courtlistener_rest_recap_document_exact_match"
        )
    elif mutation == "extra_restriction":
        document["restriction_evidence"].append("positive_restriction_evidence")
    else:
        screen["decision_entry_evidence"]["entry_date_filed"] = "2099-01-01"

    with pytest.raises(DocketDecisionTextSourceError):
        replay_docket_decision_source_lineage(
            selection_records=[selection],
            selection_payload_sha256=_SELECTION_SHA,
            screening_snapshot=_replace_snapshot(snapshot, screens=(screen,)),
            candidate_id="71942225",
            unavailable_recap_document_id="487196517",
        )


def test_replays_raw_html_decision_with_policy_rebind() -> None:
    selection, snapshot = _fixture(raw=True)

    lineage = replay_docket_decision_source_lineage(
        selection_records=[selection],
        selection_payload_sha256=_SELECTION_SHA,
        screening_snapshot=snapshot,
        candidate_id="72192698",
        unavailable_recap_document_id="485754024",
    )
    record = require_replayed_docket_decision_lineage(lineage)

    assert record["source_basis"] == RAW_COURTLISTENER_HTML_BASIS
    assert record["decision_source_id"] == "docket-entry:72192698:34"
    assert "\u00ad" in str(record["text"])
    assert "🙏" in str(record["text"])
    assert record["text_byte_count"] > len(str(record["text"]))
    assert set(record["source_evidence"]) == {
        "schema_version",
        "raw_artifact_path",
        "raw_artifact_sha256",
        "raw_artifact_byte_count",
        "raw_artifact_retrieved_at",
        "policy_rebind",
    }


def test_normalizes_raw_parser_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    selection, snapshot = _fixture(raw=True)

    def fail_parse(*args: object, **kwargs: object) -> None:
        raise CourtListenerWebParseError("synthetic parser failure")

    monkeypatch.setattr(
        "legalforecast.ingestion.docket_decision_text_source."
        "parse_courtlistener_docket_html",
        fail_parse,
    )

    with pytest.raises(
        DocketDecisionTextSourceError,
        match="raw CourtListener HTML cannot be replayed",
    ):
        replay_docket_decision_source_lineage(
            selection_records=[selection],
            selection_payload_sha256=_SELECTION_SHA,
            screening_snapshot=snapshot,
            candidate_id="72192698",
            unavailable_recap_document_id="485754024",
        )


@pytest.mark.parametrize(
    ("collaborator", "message"),
    (
        ("screen_courtlistener_docket_for_mtd_decision", "MTD screen"),
        ("link_mtd_dispositions", "motion linkage"),
    ),
)
def test_normalizes_screen_and_linkage_failures(
    monkeypatch: pytest.MonkeyPatch,
    collaborator: str,
    message: str,
) -> None:
    selection, snapshot = _fixture(raw=False)

    def fail_replay(*args: object, **kwargs: object) -> None:
        raise ValueError("synthetic collaborator failure")

    monkeypatch.setattr(
        f"legalforecast.ingestion.docket_decision_text_source.{collaborator}",
        fail_replay,
    )

    with pytest.raises(DocketDecisionTextSourceError, match=message):
        replay_docket_decision_source_lineage(
            selection_records=[selection],
            selection_payload_sha256=_SELECTION_SHA,
            screening_snapshot=snapshot,
            candidate_id="71942225",
            unavailable_recap_document_id="487196517",
        )


def test_raw_replay_preserves_the_frozen_decision_window_upper_bound() -> None:
    selection, snapshot = _fixture(raw=True)
    html = _html(
        motion_entry=25,
        decision_entry=34,
        include_unicode=True,
        post_window_decision_entry=35,
    )
    page = parse_courtlistener_docket_html(
        html,
        source_url="https://www.courtlistener.com/docket/72192698/example/",
        docket_id="72192698",
    )
    screen = copy.deepcopy(dict(snapshot.screened[0]))
    screen["decision_window_end"] = "2026-07-31"
    screen["selected_entries"] = [entry.to_record() for entry in page.entries]
    screen["mtd_decision_screen"] = screen_courtlistener_docket_for_mtd_decision(
        page,
        candidate_text="Example v. Example",
        court_id="mad",
        decision_filed_on_or_after=date(2026, 6, 30),
        decision_filed_on_or_before=date(2026, 7, 31),
    ).to_record()
    raw_bytes = html.encode()
    raw_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    raw = UnionRawArtifact(
        candidate_id="courtlistener-docket-72192698",
        path=Path(f"fixture/{raw_sha256}.html"),
        content=raw_bytes,
        content_authenticated=True,
        sha256=raw_sha256,
        byte_count=len(raw_bytes),
        retrieved_at="2026-07-14T04:13:10Z",
    )

    lineage = replay_docket_decision_source_lineage(
        selection_records=[selection],
        selection_payload_sha256=_SELECTION_SHA,
        screening_snapshot=_replace_snapshot(
            snapshot,
            screens=(screen,),
            raw_artifacts=(raw,),
        ),
        candidate_id="72192698",
        unavailable_recap_document_id="485754024",
    )

    assert (
        require_replayed_docket_decision_lineage(lineage)["decision_entry_number"] == 34
    )


def test_lineage_is_opaque_and_not_downstream_omission_authority() -> None:
    with pytest.raises(TypeError, match="issued only"):
        ReplayedDocketDecisionLineage()
    with pytest.raises(DocketDecisionTextSourceError, match="not issued"):
        require_replayed_docket_decision_lineage(object())


def test_terminal_disposition_derives_mixed_retained_and_residual_partition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    allow_historical_v1_algorithm_fixtures(monkeypatch)
    selections, snapshot = _partition_fixture()
    policy = _terminal_policy(tmp_path)
    result_path = tmp_path / "purchase-result.json"
    terminal_pairs = (
        ("71942225", "motion-719", 6),
        ("72192698", "485754024", 3),
    )
    with CaseDevPurchaseJournal(
        policy.canonical_ledger_path,
        policy=policy,
        allow_create=True,
    ) as journal:
        failure_authority = _terminal_failure_authority(
            journal,
            result_path=result_path,
            terminal_pairs=terminal_pairs,
        )
        sources = verify_docket_decision_text_sources(
            selection_payload=_selection_bytes(selections),
            expected_selection_payload_sha256=_selection_sha(selections),
            screening_snapshot=snapshot,
            expected_snapshot_manifest_sha256=snapshot.manifest_sha256,
            terminal_purchase_failure_authority=failure_authority,
            purchase_journal=journal,
        )
        disposition = sources.terminal_purchase_disposition_authority(
            purchase_journal=journal
        )
        retained = verified_docket_decision_source_records(
            disposition,
            purchase_journal=journal,
        )
        residual = verified_residual_terminal_records(
            disposition,
            purchase_journal=journal,
        )
        residual_bytes = residual_terminal_exclusions_bytes(
            disposition,
            purchase_journal=journal,
        )
        omitted_keys = verified_docket_decision_document_keys(
            disposition,
            purchase_journal=journal,
        )

    assert [record["candidate_id"] for record in retained] == ["72192698"]
    assert retained[0]["unavailable_recap_document_id"] == "485754024"
    assert retained[0]["model_visible"] is False
    assert retained[0]["audit_only"] is True
    assert set(residual) == {"71942225"}
    assert residual_bytes.endswith(b"\n")
    assert b'"candidate_id":"71942225"' in residual_bytes
    assert b"72192698" not in residual_bytes
    assert omitted_keys == frozenset({("72192698", "485754024")})


def test_terminal_disposition_allows_an_exact_empty_residual_partition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    allow_historical_v1_algorithm_fixtures(monkeypatch)
    selection, snapshot = _fixture(raw=True)
    policy = _terminal_policy(tmp_path)
    with CaseDevPurchaseJournal(
        policy.canonical_ledger_path,
        policy=policy,
        allow_create=True,
    ) as journal:
        failure_authority = _terminal_failure_authority(
            journal,
            result_path=tmp_path / "purchase-result.json",
            terminal_pairs=(("72192698", "485754024", 3),),
        )
        sources = verify_docket_decision_text_sources(
            selection_payload=_selection_bytes([selection]),
            expected_selection_payload_sha256=_selection_sha([selection]),
            screening_snapshot=snapshot,
            expected_snapshot_manifest_sha256=snapshot.manifest_sha256,
            terminal_purchase_failure_authority=failure_authority,
            purchase_journal=journal,
        )
        disposition = sources.terminal_purchase_disposition_authority(
            purchase_journal=journal
        )

        assert [
            record["candidate_id"]
            for record in verified_docket_decision_source_records(
                disposition,
                purchase_journal=journal,
            )
        ] == ["72192698"]
        assert (
            verified_residual_terminal_records(
                disposition,
                purchase_journal=journal,
            )
            == {}
        )
        assert (
            residual_terminal_exclusions_bytes(
                disposition,
                purchase_journal=journal,
            )
            == b""
        )


def test_terminal_disposition_rejects_selection_records_with_an_unrelated_digest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    allow_historical_v1_algorithm_fixtures(monkeypatch)
    selection, snapshot = _fixture(raw=True)
    policy = _terminal_policy(tmp_path)
    with CaseDevPurchaseJournal(
        policy.canonical_ledger_path,
        policy=policy,
        allow_create=True,
    ) as journal:
        failure_authority = _terminal_failure_authority(
            journal,
            result_path=tmp_path / "purchase-result.json",
            terminal_pairs=(("72192698", "485754024", 3),),
        )
        with pytest.raises(
            DocketDecisionTextSourceError,
            match="differs from the frozen selection pin",
        ):
            verify_docket_decision_text_sources(
                selection_payload=_selection_bytes([selection]),
                expected_selection_payload_sha256="a" * 64,
                screening_snapshot=snapshot,
                expected_snapshot_manifest_sha256=snapshot.manifest_sha256,
                terminal_purchase_failure_authority=failure_authority,
                purchase_journal=journal,
            )


def test_terminal_disposition_accepts_compact_successor_selection_encoding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    allow_historical_v1_algorithm_fixtures(monkeypatch)
    selection, snapshot = _fixture(raw=True)
    compact_payload = (
        json.dumps(
            selection,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode()
    policy = _terminal_policy(tmp_path)
    with CaseDevPurchaseJournal(
        policy.canonical_ledger_path,
        policy=policy,
        allow_create=True,
    ) as journal:
        failure_authority = _terminal_failure_authority(
            journal,
            result_path=tmp_path / "purchase-result.json",
            terminal_pairs=(("72192698", "485754024", 3),),
        )
        sources = verify_docket_decision_text_sources(
            selection_payload=compact_payload,
            expected_selection_payload_sha256=hashlib.sha256(
                compact_payload
            ).hexdigest(),
            screening_snapshot=snapshot,
            expected_snapshot_manifest_sha256=snapshot.manifest_sha256,
            terminal_purchase_failure_authority=failure_authority,
            purchase_journal=journal,
        )

        assert verified_docket_decision_source_records(
            sources.terminal_purchase_disposition_authority(purchase_journal=journal),
            purchase_journal=journal,
        )


def test_terminal_disposition_rejects_digest_valid_nonproducer_selection_encoding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    allow_historical_v1_algorithm_fixtures(monkeypatch)
    selection, snapshot = _fixture(raw=True)
    nonproducer_payload = (
        json.dumps(
            selection,
            ensure_ascii=False,
            sort_keys=False,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode()
    policy = _terminal_policy(tmp_path)
    with CaseDevPurchaseJournal(
        policy.canonical_ledger_path,
        policy=policy,
        allow_create=True,
    ) as journal:
        failure_authority = _terminal_failure_authority(
            journal,
            result_path=tmp_path / "purchase-result.json",
            terminal_pairs=(("72192698", "485754024", 3),),
        )
        with pytest.raises(
            DocketDecisionTextSourceError,
            match="differs from producer encodings",
        ):
            verify_docket_decision_text_sources(
                selection_payload=nonproducer_payload,
                expected_selection_payload_sha256=hashlib.sha256(
                    nonproducer_payload
                ).hexdigest(),
                screening_snapshot=snapshot,
                expected_snapshot_manifest_sha256=snapshot.manifest_sha256,
                terminal_purchase_failure_authority=failure_authority,
                purchase_journal=journal,
            )


def test_terminal_disposition_rejects_digest_valid_selection_target_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    allow_historical_v1_algorithm_fixtures(monkeypatch)
    selection, snapshot = _fixture(raw=True)
    selection["target_motion_entry_numbers"] = [34]
    policy = _terminal_policy(tmp_path)
    with CaseDevPurchaseJournal(
        policy.canonical_ledger_path,
        policy=policy,
        allow_create=True,
    ) as journal:
        failure_authority = _terminal_failure_authority(
            journal,
            result_path=tmp_path / "purchase-result.json",
            terminal_pairs=(("72192698", "485754024", 3),),
        )
        with pytest.raises(
            DocketDecisionTextSourceError,
            match="target motions differ from authenticated screening evidence",
        ):
            verify_docket_decision_text_sources(
                selection_payload=_selection_bytes([selection]),
                expected_selection_payload_sha256=_selection_sha([selection]),
                screening_snapshot=snapshot,
                expected_snapshot_manifest_sha256=snapshot.manifest_sha256,
                terminal_purchase_failure_authority=failure_authority,
                purchase_journal=journal,
            )


@pytest.mark.parametrize("mutation", ("manifest_pin", "screen_record"))
def test_terminal_disposition_reauthenticates_the_screening_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    allow_historical_v1_algorithm_fixtures(monkeypatch)
    selection, snapshot = _fixture(raw=True)
    expected_manifest = snapshot.manifest_sha256
    if mutation == "manifest_pin":
        expected_manifest = "9" * 64
    else:
        screen = copy.deepcopy(dict(snapshot.screened[0]))
        screen["first_written_mtd_disposition_date"] = "2099-01-01"
        snapshot = VerifiedScreeningSnapshot(
            manifest=snapshot.manifest,
            manifest_sha256=snapshot.manifest_sha256,
            candidates=snapshot.candidates,
            screened=(screen,),
            exclusions=snapshot.exclusions,
            payloads=snapshot.payloads,
            raw_artifacts=snapshot.raw_artifacts,
        )
    policy = _terminal_policy(tmp_path)
    with CaseDevPurchaseJournal(
        policy.canonical_ledger_path,
        policy=policy,
        allow_create=True,
    ) as journal:
        failure_authority = _terminal_failure_authority(
            journal,
            result_path=tmp_path / "purchase-result.json",
            terminal_pairs=(("72192698", "485754024", 3),),
        )
        with pytest.raises(DocketDecisionTextSourceError, match="screening snapshot"):
            verify_docket_decision_text_sources(
                selection_payload=_selection_bytes([selection]),
                expected_selection_payload_sha256=_selection_sha([selection]),
                screening_snapshot=snapshot,
                expected_snapshot_manifest_sha256=expected_manifest,
                terminal_purchase_failure_authority=failure_authority,
                purchase_journal=journal,
            )


def test_terminal_candidate_with_decision_and_nondecision_failure_is_wholly_residual(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    allow_historical_v1_algorithm_fixtures(monkeypatch)
    selections, snapshot = _partition_fixture()
    raw_selection = next(
        selection for selection in selections if selection["candidate_id"] == "72192698"
    )
    raw_selection["documents"].append(  # type: ignore[union-attr]
        {
            "candidate_id": "72192698",
            "source_document_id": "motion-721",
            "document_role": "motion_to_dismiss_memorandum",
        }
    )
    policy = _terminal_policy(tmp_path)
    with CaseDevPurchaseJournal(
        policy.canonical_ledger_path,
        policy=policy,
        allow_create=True,
    ) as journal:
        failure_authority = _terminal_failure_authority(
            journal,
            result_path=tmp_path / "purchase-result.json",
            terminal_pairs=(
                ("72192698", "485754024", 3),
                ("72192698", "motion-721", 6),
            ),
        )
        sources = verify_docket_decision_text_sources(
            selection_payload=_selection_bytes(selections),
            expected_selection_payload_sha256=_selection_sha(selections),
            screening_snapshot=snapshot,
            expected_snapshot_manifest_sha256=snapshot.manifest_sha256,
            terminal_purchase_failure_authority=failure_authority,
            purchase_journal=journal,
        )
        disposition = sources.terminal_purchase_disposition_authority(
            purchase_journal=journal
        )
        assert (
            verified_docket_decision_source_records(
                disposition,
                purchase_journal=journal,
            )
            == ()
        )
        assert set(
            verified_residual_terminal_records(
                disposition,
                purchase_journal=journal,
            )
        ) == {"72192698"}


def test_terminal_disposition_types_are_opaque() -> None:
    with pytest.raises(TypeError, match="issued only"):
        VerifiedDocketDecisionTextSources()
    with pytest.raises(TypeError, match="issued only"):
        VerifiedTerminalPurchaseDispositionAuthority()
    fabricated = object.__new__(VerifiedTerminalPurchaseDispositionAuthority)
    policy = object.__new__(CaseDevPurchaseJournal)
    with pytest.raises(DocketDecisionTextSourceError, match="not verifier-issued"):
        verified_residual_terminal_records(fabricated, purchase_journal=policy)


def test_terminal_disposition_accessor_replays_current_journal_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    allow_historical_v1_algorithm_fixtures(monkeypatch)
    selections, snapshot = _partition_fixture()
    policy = _terminal_policy(tmp_path)
    with CaseDevPurchaseJournal(
        policy.canonical_ledger_path,
        policy=policy,
        allow_create=True,
    ) as journal:
        failure_authority = _terminal_failure_authority(
            journal,
            result_path=tmp_path / "purchase-result.json",
            terminal_pairs=(
                ("71942225", "motion-719", 6),
                ("72192698", "485754024", 3),
            ),
        )
        sources = verify_docket_decision_text_sources(
            selection_payload=_selection_bytes(selections),
            expected_selection_payload_sha256=_selection_sha(selections),
            screening_snapshot=snapshot,
            expected_snapshot_manifest_sha256=snapshot.manifest_sha256,
            terminal_purchase_failure_authority=failure_authority,
            purchase_journal=journal,
        )
        disposition = sources.terminal_purchase_disposition_authority(
            purchase_journal=journal
        )
        journal.plan(
            MissingCoreBudgetPlan(
                case_plans=(
                    CaseMissingCorePurchasePlan(
                        candidate_id="later-candidate",
                        purchase_document_ids=("later-document",),
                        missing_core_document_count=1,
                        estimated_cost=journal.policy.per_document_reservation_usd,
                        audit_only_document_count=0,
                        dry_run=False,
                        missing_core_roles=("complaint",),
                    ),
                ),
                cost_per_document=journal.policy.per_document_reservation_usd,
                max_projected_budget=journal.policy.per_document_reservation_usd,
                max_missing_core_documents_per_case=1,
                dry_run=False,
                target_case_count=1,
            )
        )
        with pytest.raises(
            DocketDecisionTextSourceError, match="another journal state"
        ):
            verified_docket_decision_source_records(
                disposition,
                purchase_journal=journal,
            )


def test_selected_decision_replay_failure_does_not_become_residual(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    allow_historical_v1_algorithm_fixtures(monkeypatch)
    selection, snapshot = _fixture(raw=True)
    screen = copy.deepcopy(dict(snapshot.screened[0]))
    decision = next(
        entry for entry in screen["selected_entries"] if entry["entry_number"] == "34"
    )
    decision["text"] = "NOTICE filed by Plaintiff."
    tampered_snapshot = _replace_snapshot(snapshot, screens=(screen,))
    policy = _terminal_policy(tmp_path)
    with CaseDevPurchaseJournal(
        policy.canonical_ledger_path,
        policy=policy,
        allow_create=True,
    ) as journal:
        failure_authority = _terminal_failure_authority(
            journal,
            result_path=tmp_path / "purchase-result.json",
            terminal_pairs=(("72192698", "485754024", 3),),
        )
        with pytest.raises(DocketDecisionTextSourceError):
            verify_docket_decision_text_sources(
                selection_payload=_selection_bytes([selection]),
                expected_selection_payload_sha256=_selection_sha([selection]),
                screening_snapshot=tampered_snapshot,
                expected_snapshot_manifest_sha256=snapshot.manifest_sha256,
                terminal_purchase_failure_authority=failure_authority,
                purchase_journal=journal,
            )


def test_raw_replay_ignores_only_synthetic_blank_document_on_unnumbered_row() -> None:
    parsed = [_unnumbered_entry(documents=[])]
    selected = [_unnumbered_entry(documents=[_synthetic_blank_document()])]

    assert _raw_entries_equivalent(parsed, selected)


@pytest.mark.parametrize(
    "mutation",
    ("numbered", "description", "href", "pacer_only", "restriction"),
)
def test_raw_replay_rejects_substantive_or_numbered_document_drift(
    mutation: str,
) -> None:
    parsed = [_unnumbered_entry(documents=[])]
    document = _synthetic_blank_document()
    selected_entry = _unnumbered_entry(documents=[document])
    if mutation == "numbered":
        selected_entry["entry_number"] = "68"
        parsed[0]["entry_number"] = "68"
    elif mutation == "description":
        document["description"] = "Order on Motion to Dismiss"
    elif mutation == "href":
        document["href"] = "https://example.test/order.pdf"
    elif mutation == "pacer_only":
        document["pacer_only"] = True
    elif mutation == "restriction":
        document["restriction_markers"] = ["sealed"]

    assert not _raw_entries_equivalent(parsed, [selected_entry])


def test_linkage_projection_ignores_only_nonactual_procedural_dispositions() -> None:
    actual_ids = frozenset({"entry-26"})
    expected: dict[str, Any] = {
        "candidate_id": "71924713",
        "case_id": "71924713",
        "links": [
            {
                "motion_entry_ids": ["entry-17"],
                "disposition_entry_ids": ["entry-26"],
            }
        ],
        "exclusion_entries": [],
        "is_clean": True,
    }
    replayed = copy.deepcopy(expected)
    replayed["links"][0]["disposition_entry_ids"].insert(0, "entry-22")

    assert (
        _linkage_actual_decision_projection(
            replayed,
            actual_decision_ids=actual_ids,
            require_already_projected=False,
        )
        == expected
    )

    wrong_actual = copy.deepcopy(replayed)
    wrong_actual["links"][0]["disposition_entry_ids"] = ["entry-22"]
    assert (
        _linkage_actual_decision_projection(
            wrong_actual,
            actual_decision_ids=actual_ids,
            require_already_projected=False,
        )
        != expected
    )

    with pytest.raises(
        DocketDecisionTextSourceError,
        match="frozen motion linkage includes a nonactual decision entry",
    ):
        _linkage_actual_decision_projection(
            replayed,
            actual_decision_ids=actual_ids,
            require_already_projected=True,
        )


@pytest.mark.parametrize(
    "mutation",
    (
        "wrong_candidate",
        "wrong_case",
        "wrong_document",
        "wrong_entry",
        "wrong_docket_entry_id",
        "wrong_date",
        "pre_anchor",
        "mislinked",
        "party_filing_forged_as_decision",
        "auxiliary_decision",
        "entry_restricted",
        "document_restricted",
        "selection_source_url",
        "selection_source_reference",
        "selection_source_provider",
        "selection_restriction_evidence",
        "sealed_selection",
        "private_selection",
        "model_visible",
        "outcome_hidden",
        "duplicate_screen",
    ),
)
def test_rejects_identity_screen_linkage_restriction_and_visibility_tamper(
    mutation: str,
) -> None:
    selection, snapshot = _fixture(raw=False)
    selection = copy.deepcopy(selection)
    screen = copy.deepcopy(dict(snapshot.screened[0]))
    screens: tuple[dict[str, Any], ...] = (screen,)
    decision = next(
        entry for entry in screen["selected_entries"] if entry["entry_number"] == "40"
    )
    selected_document = selection["documents"][0]
    if mutation == "wrong_candidate":
        selection["candidate_id"] = "other"
    elif mutation == "wrong_case":
        selection["case_id"] = "other"
    elif mutation == "wrong_document":
        selected_document["source_document_id"] = "other"
    elif mutation == "wrong_entry":
        selected_document["docket_entry_number"] = 39
    elif mutation == "wrong_docket_entry_id":
        selected_document["courtlistener_docket_entry_id"] = "999"
    elif mutation == "wrong_date":
        selection["decision_date"] = "2026-07-23"
    elif mutation == "pre_anchor":
        screen["first_written_mtd_disposition_date"] = "2026-06-29"
    elif mutation == "mislinked":
        screen["motion_linkage"]["links"][0]["motion_entry_ids"] = ["entry-99"]
    elif mutation == "party_filing_forged_as_decision":
        decision["text"] = "NOTICE filed by Plaintiff."
        decision["role"] = "decision"
        selected_document["description"] = decision["text"]
        screen["decision_entry_evidence"]["description"] = decision["text"]
    elif mutation == "auxiliary_decision":
        decision["entry_number"] = None
        decision["row_id"] = "minute-entry-40"
        decision["text"] = ""
    elif mutation == "entry_restricted":
        decision["restriction_markers"] = ["sealed"]
    elif mutation == "document_restricted":
        decision["documents"][0]["restriction_markers"] = ["private"]
    elif mutation == "selection_source_url":
        selected_document["source_url"] = "https://example.test/wrong"
    elif mutation == "selection_source_reference":
        selected_document["source_url_or_reference"] = "https://example.test/wrong"
    elif mutation == "selection_source_provider":
        selected_document["source_provider"] = "other"
    elif mutation == "selection_restriction_evidence":
        selected_document["restriction_evidence"].append("restricted")
    elif mutation == "sealed_selection":
        selected_document["is_sealed"] = True
    elif mutation == "private_selection":
        selected_document["is_private"] = True
    elif mutation == "model_visible":
        selected_document["model_visible"] = True
    elif mutation == "outcome_hidden":
        selected_document["contains_target_outcome"] = False
    elif mutation == "duplicate_screen":
        screens = (screen, copy.deepcopy(screen))
    tampered_snapshot = _replace_snapshot(snapshot, screens=screens)

    with pytest.raises(DocketDecisionTextSourceError):
        replay_docket_decision_source_lineage(
            selection_records=[selection],
            selection_payload_sha256=_SELECTION_SHA,
            screening_snapshot=tampered_snapshot,
            candidate_id="71942225",
            unavailable_recap_document_id="487196517",
        )


@pytest.mark.parametrize(
    "mutation",
    (
        "incomplete",
        "cursor_not_exhausted",
        "duplicate_entries",
        "entry_count",
        "rest_document_id",
        "rest_document_id_leading_zero",
        "rest_entry_id",
        "rest_entry_id_leading_zero",
        "rest_url",
        "raw_and_rest",
    ),
)
def test_rejects_incomplete_or_tampered_rest_source(mutation: str) -> None:
    selection, snapshot = _fixture(raw=False)
    screen = copy.deepcopy(dict(snapshot.screened[0]))
    proof = screen["reconstruction_proof"]
    if mutation == "incomplete":
        proof["complete"] = False
    elif mutation == "cursor_not_exhausted":
        proof["cursor_exhausted"] = False
    elif mutation == "duplicate_entries":
        proof["duplicate_entry_ids"] = [40]
    elif mutation == "entry_count":
        proof["entry_count"] += 1
    elif mutation == "rest_document_id":
        screen["decision_entry_evidence"]["id"] = 1
    elif mutation == "rest_document_id_leading_zero":
        screen["decision_entry_evidence"]["id"] = "0487196517"
    elif mutation == "rest_entry_id":
        screen["decision_entry_evidence"]["docket_entry_id"] = 1
    elif mutation == "rest_entry_id_leading_zero":
        screen["decision_entry_evidence"]["docket_entry_id"] = "0471775493"
    elif mutation == "rest_url":
        screen["decision_entry_evidence"]["absolute_url"] = "/docket/other/40/x/"
    elif mutation == "raw_and_rest":
        _, raw_snapshot = _fixture(raw=True)
        raw = raw_snapshot.raw_artifacts[0]
        snapshot = _replace_snapshot(
            snapshot,
            raw_artifacts=(
                UnionRawArtifact(
                    candidate_id="courtlistener-docket-71942225",
                    path=raw.path,
                    content=raw.content,
                    content_authenticated=raw.content_authenticated,
                    sha256=raw.sha256,
                    byte_count=raw.byte_count,
                    retrieved_at=raw.retrieved_at,
                ),
            ),
        )
    snapshot = _replace_snapshot(snapshot, screens=(screen,))

    with pytest.raises(DocketDecisionTextSourceError):
        replay_docket_decision_source_lineage(
            selection_records=[selection],
            selection_payload_sha256=_SELECTION_SHA,
            screening_snapshot=snapshot,
            candidate_id="71942225",
            unavailable_recap_document_id="487196517",
        )


@pytest.mark.parametrize(
    "mutation",
    (
        "raw_bytes",
        "raw_digest",
        "raw_missing",
        "raw_duplicate",
        "rebind_provider",
        "rebind_target_cycle",
        "rebind_schema",
        "rebind_delta",
    ),
)
def test_rejects_missing_tampered_or_contradictory_raw_source(mutation: str) -> None:
    selection, snapshot = _fixture(raw=True)
    screen = copy.deepcopy(dict(snapshot.screened[0]))
    raw = snapshot.raw_artifacts[0]
    raws = snapshot.raw_artifacts
    if mutation == "raw_bytes":
        raw = UnionRawArtifact(
            candidate_id=raw.candidate_id,
            path=raw.path,
            content=b"tampered",
            content_authenticated=True,
            sha256=raw.sha256,
            byte_count=raw.byte_count,
            retrieved_at=raw.retrieved_at,
        )
        raws = (raw,)
    elif mutation == "raw_digest":
        raw = UnionRawArtifact(
            candidate_id=raw.candidate_id,
            path=raw.path,
            content=raw.content,
            content_authenticated=True,
            sha256="0" * 64,
            byte_count=raw.byte_count,
            retrieved_at=raw.retrieved_at,
        )
        raws = (raw,)
    elif mutation == "raw_missing":
        raws = ()
    elif mutation == "raw_duplicate":
        raws = (raw, raw)
    elif mutation == "rebind_provider":
        screen["screening_union_policy_rebind"]["provider_activity_executed"] = True
    elif mutation == "rebind_target_cycle":
        screen["screening_union_policy_rebind"]["target_cycle_hash"] = "9" * 64
    elif mutation == "rebind_schema":
        screen["screening_union_policy_rebind"]["schema_version"] = "other"
    elif mutation == "rebind_delta":
        screen["screening_union_policy_rebind"]["policy_delta"] = "other"
    snapshot = _replace_snapshot(snapshot, screens=(screen,), raw_artifacts=raws)

    with pytest.raises(DocketDecisionTextSourceError):
        replay_docket_decision_source_lineage(
            selection_records=[selection],
            selection_payload_sha256=_SELECTION_SHA,
            screening_snapshot=snapshot,
            candidate_id="72192698",
            unavailable_recap_document_id="485754024",
        )


def _partition_fixture() -> tuple[list[dict[str, Any]], VerifiedScreeningSnapshot]:
    raw_selection, raw_snapshot = _fixture(raw=True)
    rest_selection, rest_snapshot = _fixture(raw=False)
    rest_selection["documents"].append(
        {
            "candidate_id": "71942225",
            "source_document_id": "motion-719",
            "document_role": "motion_to_dismiss_memorandum",
        }
    )
    snapshot = VerifiedScreeningSnapshot(
        manifest=raw_snapshot.manifest,
        manifest_sha256=raw_snapshot.manifest_sha256,
        candidates=(),
        screened=(raw_snapshot.screened[0], rest_snapshot.screened[0]),
        exclusions=(),
        payloads={},
        raw_artifacts=raw_snapshot.raw_artifacts,
    )
    return [raw_selection, rest_selection], _authenticate_fixture_snapshot(snapshot)


def _terminal_policy(tmp_path: Path) -> CaseDevPurchasePolicy:
    artifact = generate_case_dev_purchase_policy(
        {
            "cycle_id": "docket-decision-terminal-partition-test",
            "cohort_policy_sha256": "a" * 64,
            "canonical_ledger_path": str((tmp_path / "purchase.sqlite3").resolve()),
            "hard_cap_usd": "9.15",
            "opening_committed_spend_usd": "0.00",
            "opening_case_committed_spend_usd": {},
            "max_per_case_usd": "6.10",
            "per_document_reservation_usd": "3.05",
            "fee_schedule": {
                "source_citation": "fixture",
                "verified_at_utc": "2026-08-05T00:00:00Z",
                "includes_pacer_fees": True,
                "includes_service_fees": True,
                "includes_rounding": True,
            },
        }
    )
    return verify_case_dev_purchase_policy(artifact)


def _terminal_failure_authority(
    journal: CaseDevPurchaseJournal,
    *,
    result_path: Path,
    terminal_pairs: tuple[tuple[str, str, int], ...],
) -> VerifiedTerminalPurchaseFailureAuthority:
    pairs_by_candidate: dict[str, list[tuple[str, int]]] = {}
    for candidate_id, document_id, queue_status in terminal_pairs:
        pairs_by_candidate.setdefault(candidate_id, []).append(
            (document_id, queue_status)
        )
    case_plans = tuple(
        CaseMissingCorePurchasePlan(
            candidate_id=candidate_id,
            purchase_document_ids=tuple(
                document_id for document_id, _queue_status in candidate_pairs
            ),
            missing_core_document_count=len(candidate_pairs),
            estimated_cost=(
                journal.policy.per_document_reservation_usd * len(candidate_pairs)
            ),
            audit_only_document_count=sum(
                document_id.isdigit() for document_id, _queue_status in candidate_pairs
            ),
            dry_run=False,
            missing_core_roles=tuple(
                "decision" if document_id.isdigit() else "mtd_notice"
                for document_id, _queue_status in candidate_pairs
            ),
        )
        for candidate_id, candidate_pairs in pairs_by_candidate.items()
    )
    plan = MissingCoreBudgetPlan(
        case_plans=case_plans,
        cost_per_document=journal.policy.per_document_reservation_usd,
        max_projected_budget=(
            journal.policy.per_document_reservation_usd * len(terminal_pairs)
        ),
        max_missing_core_documents_per_case=max(
            plan.missing_core_document_count for plan in case_plans
        ),
        dry_run=False,
        target_case_count=len(case_plans),
    )
    budget_path = result_path.with_name("purchase-budget-plan.json")
    budget_path.write_bytes(_canonical_bytes(plan.to_record()))
    journal.plan(plan)
    attempts: list[dict[str, object]] = []
    for index, (candidate_id, document_id, queue_status) in enumerate(
        terminal_pairs, start=1
    ):
        assert journal.submit(document_id)
        journal.queue(
            document_id,
            response={
                "source_provider": COURTLISTENER_RECAP_FETCH_PROVIDER,
                "reservation_usd": (
                    f"{journal.policy.per_document_reservation_usd:.2f}"
                ),
                "queue_id": str(70 + index),
                "reservation_id": f"reservation-{index}",
            },
        )
        journal.fail(
            document_id,
            CourtListenerRecapFetchError(
                f"RECAP Fetch terminal queue status {queue_status}"
            ),
        )
        attempts.append(
            {
                "candidate_id": candidate_id,
                "source_document_id": document_id,
                "status": "provider_error",
                "reason": f"recap_fetch_status_{queue_status}",
                "fee_acknowledged": None,
                "pacer_fees": None,
                "download_url": None,
                "source_provider": COURTLISTENER_RECAP_FETCH_PROVIDER,
            }
        )
    total = journal.policy.per_document_reservation_usd * len(terminal_pairs)
    result: dict[str, object] = {
        "live": True,
        "acknowledge_pacer_fees": True,
        "capability": "document_level_purchase",
        "dry_run": False,
        "projected_cost_usd": f"{total:.2f}",
        "max_projected_budget_usd": f"{total:.2f}",
        "intended_purchase_count": len(attempts),
        "executed_purchase_count": 0,
        "quarantined_material_count": 0,
        "completed_purchase_count": 0,
        "attempts": attempts,
    }
    run_card: dict[str, object] = {
        "schema_version": "legalforecast.acquisition_run_card.v1",
        "stage": "purchase-missing-recap-fetch",
        "status": "completed",
        "dry_run": False,
        "execute": True,
        "resume": False,
        "record_count": len(attempts),
        "input_paths": [str(budget_path), "fixture/selection.jsonl"],
        "output_paths": [str(result_path), str(journal.policy.canonical_ledger_path)],
        "paid_activity_requested": True,
        "paid_activity_executed": True,
        "generated_at": "2026-08-05T00:00:00Z",
        "executed_purchase_count": 0,
        "quarantined_material_count": 0,
        "completed_purchase_count": 0,
        "courtlistener_live": True,
        "courtlistener_physical_requests": len(attempts),
        "courtlistener_rate_profile": "authenticated",
        "courtlistener_request_budget_max_wait_seconds": 3700.0,
        "courtlistener_request_ledger": "fixture/request-ledger.sqlite3",
        "courtlistener_reservations_this_phase": len(attempts),
        "courtlistener_reservations_total": len(attempts),
        "courtlistener_limits": {
            "per_minute": 50,
            "per_hour": 500,
            "per_day": 1400,
        },
    }
    result_path.write_bytes(_canonical_bytes(result))
    run_card_path = result_path.with_name("purchase-run-card.json")
    run_card_path.write_bytes(_canonical_bytes(run_card))
    return verify_terminal_purchase_failure_authority(
        purchase_result_path=result_path,
        purchase_run_card_path=run_card_path,
        purchase_journal=journal,
    )


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode()


def _selection_sha(records: list[dict[str, Any]]) -> str:
    return hashlib.sha256(_selection_bytes(records)).hexdigest()


def _selection_bytes(records: list[dict[str, Any]]) -> bytes:
    return b"".join(
        (json.dumps(record, sort_keys=True, allow_nan=False) + "\n").encode()
        for record in records
    )


def _fixture(*, raw: bool) -> tuple[dict[str, Any], VerifiedScreeningSnapshot]:
    docket_id = "72192698" if raw else "71942225"
    decision_entry = 34 if raw else 40
    motion_entry = 25 if raw else 39
    document_id = "485754024" if raw else "487196517"
    docket_entry_id = "470378519" if raw else "471783082"
    html = _html(
        motion_entry=motion_entry,
        decision_entry=decision_entry,
        include_unicode=raw,
    )
    page = parse_courtlistener_docket_html(
        html,
        source_url=f"https://www.courtlistener.com/docket/{docket_id}/example/",
        docket_id=docket_id,
    )
    screen = screen_courtlistener_docket_for_mtd_decision(
        page,
        candidate_text="Example v. Example",
        court_id="mad",
        decision_filed_on_or_after=date(2026, 6, 30),
    )
    linkage = link_mtd_dispositions(
        tuple(
            NormalizedDocketEntry(
                source_provider="courtlistener",
                source_case_id=docket_id,
                docket_entry_id=entry.row_id,
                entry_number=entry.entry_number,
                entry_text=entry.text,
                filed_at=entry.filed_at,
                document_role=_ROLE_MAP[entry.role],
                source_document_ids=tuple(
                    document.href
                    for document in entry.documents
                    if document.href is not None
                ),
                source_url=page.source_url,
            )
            for entry in page.entries
        ),
        candidate_id=docket_id,
        case_id=docket_id,
    )
    decision = next(
        entry for entry in page.entries if entry.entry_number == str(decision_entry)
    )
    evidence: dict[str, Any] = {
        "candidate_id": f"courtlistener-docket-{docket_id}",
        "candidate": {
            "candidate_key": docket_id,
            "docket_id": docket_id,
            "metadata": {
                "case_id": docket_id,
                "case_name": "Example v. Example",
                "court": "mad",
                "docket_number": "1:26-cv-00001",
            },
        },
        "ai": {
            "target_motion_entry_numbers": [str(motion_entry)],
            "decision_entry_numbers": [str(decision_entry)],
        },
        "first_written_mtd_disposition_date": "2026-07-10",
        "eligibility_anchor_date": "2026-06-30",
        "selected_entries": [entry.to_record() for entry in page.entries],
        "mtd_decision_screen": screen.to_record(),
        "motion_linkage": linkage.to_record(),
    }
    raw_artifacts: tuple[UnionRawArtifact, ...] = ()
    if raw:
        evidence["screening_union_policy_rebind"] = {
            "schema_version": "legalforecast.screening_union_policy_rebind_proof.v1",
            "source_cycle_hash": "1" * 64,
            "source_snapshot_manifest_sha256": "2" * 64,
            "source_terminal_sha256": "3" * 64,
            "target_cycle_hash": _CYCLE_SHA,
            "policy_delta": "restricted_material_public_hearing_false_positive_fix_v1",
            "current_policy_proof_available": True,
            "paid_activity_requested": False,
            "paid_activity_executed": False,
            "provider_activity_requested": False,
            "provider_activity_executed": False,
        }
        payload = html.encode()
        digest = hashlib.sha256(payload).hexdigest()
        raw_artifacts = (
            UnionRawArtifact(
                candidate_id=f"courtlistener-docket-{docket_id}",
                path=Path(f"/tmp/{digest}.html"),
                content=payload,
                content_authenticated=True,
                sha256=digest,
                byte_count=len(payload),
                retrieved_at="2026-07-14T04:13:10Z",
            ),
        )
    else:
        evidence.update(
            {
                "provider": "courtlistener-recap-rest-v4",
                "canonical_rest_screen_complete": True,
                "reconstruction_proof": {
                    "complete": True,
                    "cursor_exhausted": True,
                    "docket_id": docket_id,
                    "duplicate_entry_ids": [],
                    "entry_count": len(page.entries),
                    "entry_numbers_monotonic": True,
                    "pages_fetched": 1,
                },
                "decision_entry_evidence": {
                    "absolute_url": f"/docket/{docket_id}/{decision_entry}/example/",
                    "description": decision.text,
                    "docket_entry_id": int(docket_entry_id),
                    "document_number": decision_entry,
                    "entry_date_filed": "2026-07-10",
                    "entry_number": decision_entry,
                    "id": int(document_id),
                },
            }
        )
    selection: dict[str, Any] = {
        "candidate_id": docket_id,
        "case_id": docket_id,
        "selected": True,
        "decision_date": "2026-07-10",
        "decision_entry_numbers": [decision_entry],
        "target_motion_entry_numbers": [motion_entry],
        "documents": [
            {
                "candidate_id": docket_id,
                "source_document_id": document_id,
                "courtlistener_docket_entry_id": docket_entry_id,
                "docket_entry_number": decision_entry,
                "description": decision.text,
                "document_role": "decision",
                "contains_target_outcome": True,
                "model_visible": False,
                "is_predecision_material": False,
                "availability_status": "unavailable",
                "is_available": False,
                "requires_paid_recovery": True,
                "is_sealed": None,
                "is_private": None,
                "redaction_or_seal_status": "unknown",
                "restriction_evidence": [
                    "courtlistener_rest_no_positive_restriction_marker"
                ],
            }
        ],
    }
    if not raw:
        document = cast(dict[str, Any], selection["documents"][0])
        source_url = (
            f"https://www.courtlistener.com/api/rest/v4/recap-documents/{document_id}/"
        )
        document.update(
            {
                "source_provider": "courtlistener+recap-fetch",
                "source_url": source_url,
                "source_url_or_reference": source_url,
                "restriction_evidence": [
                    "courtlistener_rest_docket_exact_match",
                    "courtlistener_rest_docket_entry_exact_match",
                    "courtlistener_rest_recap_document_exact_match",
                    "courtlistener_rest_recap_document_is_available_false",
                    "courtlistener_rest_recap_document_seal_status_unknown",
                    "courtlistener_rest_no_positive_restriction_marker",
                ],
            }
        )
    snapshot = VerifiedScreeningSnapshot(
        manifest={
            "cycle_hash": _CYCLE_SHA,
            "batch_id": "batch",
            "batch_digest": _BATCH_SHA,
            "files": {
                name: {"sha256": _FILE_SHA}
                for name in (
                    "candidates.jsonl",
                    "screened-cases.jsonl",
                    "raw-artifacts.jsonl",
                )
            },
        },
        manifest_sha256=_MANIFEST_SHA,
        candidates=(),
        screened=(evidence,),
        exclusions=(),
        payloads={},
        raw_artifacts=raw_artifacts,
    )
    return selection, _authenticate_fixture_snapshot(snapshot)


def _replace_snapshot(
    snapshot: VerifiedScreeningSnapshot,
    *,
    screens: tuple[dict[str, Any], ...] | None = None,
    raw_artifacts: tuple[UnionRawArtifact, ...] | None = None,
) -> VerifiedScreeningSnapshot:
    replaced = VerifiedScreeningSnapshot(
        manifest=snapshot.manifest,
        manifest_sha256=snapshot.manifest_sha256,
        candidates=snapshot.candidates,
        screened=snapshot.screened if screens is None else screens,
        exclusions=snapshot.exclusions,
        payloads=snapshot.payloads,
        raw_artifacts=(
            snapshot.raw_artifacts if raw_artifacts is None else raw_artifacts
        ),
    )
    return _authenticate_fixture_snapshot(replaced)


def _authenticate_fixture_snapshot(
    snapshot: VerifiedScreeningSnapshot,
) -> VerifiedScreeningSnapshot:
    screened_bytes = b"".join(
        (
            json.dumps(
                dict(record),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n"
        ).encode()
        for record in snapshot.screened
    )
    raw_records = [
        {
            "artifact_id": index,
            "byte_count": artifact.byte_count,
            "candidate_id": artifact.candidate_id,
            "path": str(artifact.path),
            "retrieved_at": artifact.retrieved_at,
            "sha256": artifact.sha256,
        }
        for index, artifact in enumerate(snapshot.raw_artifacts, start=1)
    ]
    raw_bytes = b"".join(
        (
            json.dumps(
                record,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n"
        ).encode()
        for record in raw_records
    )
    manifest = copy.deepcopy(dict(snapshot.manifest))
    files = manifest["files"]
    files["screened-cases.jsonl"] = {
        "sha256": hashlib.sha256(screened_bytes).hexdigest()
    }
    files["raw-artifacts.jsonl"] = {"sha256": hashlib.sha256(raw_bytes).hexdigest()}
    manifest_bytes = (
        json.dumps(
            manifest,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode()
    return VerifiedScreeningSnapshot(
        manifest=manifest,
        manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        candidates=snapshot.candidates,
        screened=snapshot.screened,
        exclusions=snapshot.exclusions,
        payloads={
            **snapshot.payloads,
            "manifest.json": manifest_bytes,
            "screened-cases.jsonl": screened_bytes,
            "raw-artifacts.jsonl": raw_bytes,
        },
        raw_artifacts=snapshot.raw_artifacts,
    )


def _unnumbered_entry(*, documents: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "documents": documents,
        "entry_number": None,
        "filed_at": "July 14, 2026, 6:30 p.m.",
        "restriction_markers": [],
        "role": "other",
        "row_id": "minute-entry-457423921",
        "text": "Set Deadline as to 8 Motion to Dismiss.",
    }


def _synthetic_blank_document() -> dict[str, Any]:
    return {
        "action_label": None,
        "description": "",
        "freely_available": False,
        "href": None,
        "kind": "",
        "pacer_only": False,
        "restriction_markers": [],
    }


def _html(
    *,
    motion_entry: int,
    decision_entry: int,
    include_unicode: bool,
    post_window_decision_entry: int | None = None,
) -> str:
    unicode_suffix = " Main Doc \u00adument 🙏" if include_unicode else ""
    rows = [
        (
            motion_entry,
            "Jul 1, 2026",
            "MOTION to Dismiss for Failure to State a Claim filed by Defendant.",
            "Motion to Dismiss",
        ),
        (
            decision_entry,
            "Jul 10, 2026",
            f"TEXT ONLY ORDER granting {motion_entry} Motion to Dismiss. "
            "Signed by District Judge Example on July 10, 2026. "
            f"(Entered: 07/10/2026){unicode_suffix}",
            "Order on Motion to Dismiss",
        ),
    ]
    if post_window_decision_entry is not None:
        rows.append(
            (
                post_window_decision_entry,
                "Aug 1, 2026",
                f"TEXT ONLY ORDER denying {motion_entry} Motion to Dismiss. "
                "Signed by District Judge Example on August 1, 2026. "
                "(Entered: 08/01/2026)",
                "Order on Motion to Dismiss",
            )
        )
    rendered = "".join(
        f"""
        <div class="row odd" id="entry-{number}">
          <div class="col-xs-1 text-center"><p>{number}</p></div>
          <div class="col-xs-3 col-sm-2">
            <p><span title="{filed}, 9:39 a.m.">{filed}</span></p>
          </div>
          <div class="col-xs-8 col-lg-7">
            <p>{text}</p>
            <div class="row recap-documents">
              <div class="col-xs-3"><p>Main Document</p></div>
              <div class="col-xs-6"><p>{description}</p></div>
              <div class="btn-group">
                <a href="https://ecf.example.test/doc1/{number}">Buy on PACER</a>
              </div>
            </div>
          </div>
        </div>
        """
        for number, filed, text, description in rows
    )
    return f"""
    <html><head><title>Example v. Example</title></head><body>
      <a rel="next" class="btn btn-default disabled" href="#">Next</a>
      <div class="fake-table col-xs-12" id="docket-entry-table">{rendered}</div>
    </body></html>
    """
