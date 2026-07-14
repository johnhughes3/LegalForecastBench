from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, cast

import pytest
from legalforecast.cli import main
from legalforecast.ingestion.core_document_filter import filter_core_documents
from legalforecast.ingestion.courtlistener_case_dev_bridge import (
    CourtListenerCaseDevBridgeError,
    bridge_public_plan_paid_gap_candidate_via_courtlistener,
)
from legalforecast.ingestion.courtlistener_client import (
    CourtListenerClient,
    CourtListenerConfig,
    CourtListenerFixtureTransport,
    RecordedCourtListenerResponse,
)
from legalforecast.ingestion.public_packet_planner import plan_public_packet_downloads


def test_courtlistener_rest_bridge_emits_real_public_recap_id_for_plan() -> None:
    screened, gap, downloads = _paid_gap_inputs()
    client = _client(*_clean_responses())

    selection, relevance = bridge_public_plan_paid_gap_candidate_via_courtlistener(
        screened,
        paid_gap_record=gap,
        free_download_records=downloads,
        client=client,
        use_embedded_entries=True,
    )

    paid = [
        document
        for document in selection["documents"]
        if document.get("requires_paid_recovery") is True
    ]
    assert len(paid) == 1
    assert paid[0]["source_provider"] == "courtlistener+recap-fetch"
    assert paid[0]["source_document_id"] == "9005"
    assert paid[0]["courtlistener_docket_entry_id"] == "7005"
    assert paid[0]["is_sealed"] is False
    assert paid[0]["is_private"] is None
    assert paid[0]["redaction_or_seal_status"] == "public"
    assert paid[0]["restriction_evidence"] == [
        "courtlistener_rest_docket_exact_match",
        "courtlistener_rest_docket_entry_exact_match",
        "courtlistener_rest_recap_document_exact_match",
        "courtlistener_rest_recap_document_is_sealed_false",
    ]
    assert selection["identity_resolution"] == {
        "courtlistener_candidate_id": "123",
        "courtlistener_docket_id": "123",
        "matched_by": "direct_rest_exact_docket_court_caption_entries",
    }
    [result] = filter_core_documents((relevance,))
    assert result.purchase_document_ids == ("9005",)
    assert client.request_count == 3


def test_bridge_pacer_gaps_cli_runs_noncharging_courtlistener_rest_mode(
    tmp_path: Path,
) -> None:
    screened, gap, downloads = _paid_gap_inputs()
    screened_path = tmp_path / "screened.jsonl"
    public_path = tmp_path / "public.jsonl"
    gaps_path = tmp_path / "gaps.jsonl"
    downloads_path = tmp_path / "downloads.jsonl"
    fixture_path = tmp_path / "courtlistener.jsonl"
    output_root = tmp_path / "output"
    _write_jsonl(screened_path, [screened])
    _write_jsonl(public_path, [])
    _write_jsonl(gaps_path, [gap])
    _write_jsonl(downloads_path, list(downloads))
    _write_jsonl(
        fixture_path,
        [
            {
                "method": response.method,
                "path": response.path,
                "params": dict(response.params),
                "status_code": response.status_code,
                "payload": dict(response.payload),
            }
            for response in _clean_responses()
        ],
    )

    assert (
        main(
            [
                "acquisition",
                "bridge-pacer-gaps",
                "--screened-cases",
                str(screened_path),
                "--use-embedded-entries",
                "--courtlistener-fixture",
                str(fixture_path),
                "--public-selection",
                str(public_path),
                "--paid-gaps",
                str(gaps_path),
                "--free-download-manifest",
                str(downloads_path),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )
    [selection] = _read_jsonl(output_root / "public-packet-selection-reconciled.jsonl")
    paid = [
        document
        for document in selection["documents"]
        if document.get("requires_paid_recovery") is True
    ]
    assert [document["source_document_id"] for document in paid] == ["9005"]
    summary = json.loads(
        (output_root / "run-cards" / "bridge-pacer-gaps.json").read_text()
    )
    assert summary["courtlistener_request_count"] == 3
    assert summary["paid_activity_executed"] is False


def test_courtlistener_rest_bridge_checkpoints_and_resumes_without_refetch(
    tmp_path: Path,
) -> None:
    first = _screened_case()
    second = _screened_case_variant(
        candidate_id="456",
        docket_number="1:26-cv-00002",
        case_name="Second v. Example",
    )
    plan = plan_public_packet_downloads(
        (first, second), use_embedded_entries=True, target_clean_cases=2
    )
    screened_path = tmp_path / "screened.jsonl"
    public_path = tmp_path / "public.jsonl"
    gaps_path = tmp_path / "gaps.jsonl"
    downloads_path = tmp_path / "downloads.jsonl"
    fixture_path = tmp_path / "courtlistener.jsonl"
    output_root = tmp_path / "output"
    _write_jsonl(screened_path, [first, second])
    _write_jsonl(public_path, [])
    _write_jsonl(gaps_path, [gap.to_record() for gap in plan.paid_gap_cases])
    _write_jsonl(
        downloads_path,
        [
            {
                **request.to_record(),
                "local_path": (
                    f"{request.candidate_id}/{request.source_document_id}.pdf"
                ),
                "sha256": "a" * 64,
                "free_or_purchased": "free",
            }
            for request in plan.download_requests
        ],
    )
    rate_limit = {
        "method": "GET",
        "path": "/dockets/456/",
        "params": {},
        "status_code": 429,
        "payload": {"detail": "daily quota reached"},
    }
    _write_jsonl(
        fixture_path,
        [
            *(_recorded_response_record(response) for response in _clean_responses()),
            rate_limit,
            rate_limit,
            rate_limit,
        ],
    )
    command = [
        "acquisition",
        "bridge-pacer-gaps",
        "--screened-cases",
        str(screened_path),
        "--use-embedded-entries",
        "--courtlistener-fixture",
        str(fixture_path),
        "--public-selection",
        str(public_path),
        "--paid-gaps",
        str(gaps_path),
        "--free-download-manifest",
        str(downloads_path),
        "--output-root",
        str(output_root),
        "--execute",
    ]

    assert main(command) == 2
    checkpoints = [
        _read_json(path)
        for path in sorted(
            (output_root / "checkpoints" / "pacer-gap-bridge").glob("*.json")
        )
    ]
    assert [checkpoint["outcome"] for checkpoint in checkpoints] == [
        "success",
        "retryable",
    ]
    first_run = _read_json(output_root / "run-cards" / "bridge-pacer-gaps.json")
    assert first_run["courtlistener_request_count"] == 6
    assert first_run["checkpoint_terminal_candidate_count"] == 1
    assert first_run["retryable_candidate_count"] == 1

    _write_jsonl(
        fixture_path,
        [
            _recorded_response_record(response)
            for response in _clean_responses_for(
                candidate_id="456",
                docket_number="1:26-cv-00002",
                case_name="Second v. Example",
                docket_entry_id="7456",
                recap_document_id="9456",
            )
        ],
    )

    assert main(command) == 0
    selections = _read_jsonl(output_root / "public-packet-selection-reconciled.jsonl")
    assert {selection["candidate_id"] for selection in selections} == {"123", "456"}
    resumed = _read_json(output_root / "run-cards" / "bridge-pacer-gaps.json")
    assert resumed["courtlistener_request_count"] == 3
    assert resumed["resumed_terminal_candidate_count"] == 1
    assert resumed["checkpoint_terminal_candidate_count"] == 2
    assert resumed["retryable_candidate_count"] == 0


@pytest.mark.parametrize(
    ("docket_patch", "reason"),
    (
        ({"id": 999}, "courtlistener_direct_id_conflict"),
        ({"court": "cacd"}, "courtlistener_exact_match_not_found"),
        ({"docket_number": "9:99-cv-99999"}, "courtlistener_exact_match_not_found"),
        ({"case_name": "Wrong v. Caption"}, "courtlistener_caption_conflict"),
    ),
)
def test_courtlistener_rest_bridge_rejects_docket_identity_mismatch(
    docket_patch: dict[str, object],
    reason: str,
) -> None:
    screened, gap, downloads = _paid_gap_inputs()
    responses = list(_clean_responses())
    payload = dict(responses[0].payload)
    payload.update(docket_patch)
    responses[0] = _response(path="/dockets/123/", payload=payload)

    with pytest.raises(CourtListenerCaseDevBridgeError, match=reason):
        bridge_public_plan_paid_gap_candidate_via_courtlistener(
            screened,
            paid_gap_record=gap,
            free_download_records=downloads,
            client=_client(*responses),
            use_embedded_entries=True,
        )


@pytest.mark.parametrize(
    "source_url",
    (
        None,
        "https://www.courtlistener.com/api/rest/v4/dockets/123/",
    ),
)
def test_courtlistener_rest_bridge_accepts_source_without_web_docket_id(
    source_url: str | None,
) -> None:
    screened, gap, downloads = _paid_gap_inputs()
    candidate = cast(dict[str, object], screened["candidate"])
    if source_url is None:
        candidate.pop("url")
    else:
        candidate["url"] = source_url

    selection, _ = bridge_public_plan_paid_gap_candidate_via_courtlistener(
        screened,
        paid_gap_record=gap,
        free_download_records=downloads,
        client=_client(*_clean_responses()),
        use_embedded_entries=True,
    )

    assert selection["candidate_id"] == "123"


def test_courtlistener_rest_bridge_rejects_positive_source_id_mismatch() -> None:
    screened, gap, downloads = _paid_gap_inputs()
    candidate = cast(dict[str, object], screened["candidate"])
    candidate["url"] = "https://www.courtlistener.com/docket/999/wrong/"

    with pytest.raises(
        CourtListenerCaseDevBridgeError, match="courtlistener_source_id_conflict"
    ):
        bridge_public_plan_paid_gap_candidate_via_courtlistener(
            screened,
            paid_gap_record=gap,
            free_download_records=downloads,
            client=_client(*_clean_responses()),
            use_embedded_entries=True,
        )


@pytest.mark.parametrize(
    ("entry_patch", "reason"),
    (
        ({"docket": 999}, "courtlistener_entry_docket_conflict"),
        ({"entry_number": 6}, "courtlistener_entry_not_found"),
        ({"description": "Unrelated filing"}, "courtlistener_entry_text_conflict"),
        ({"date_filed": "2026-01-02"}, "courtlistener_entry_date_conflict"),
    ),
)
def test_courtlistener_rest_bridge_rejects_entry_mismatch(
    entry_patch: dict[str, object],
    reason: str,
) -> None:
    screened, gap, downloads = _paid_gap_inputs()
    responses = list(_clean_responses())
    payload = cast(dict[str, object], copy.deepcopy(dict(responses[1].payload)))
    results = payload["results"]
    assert isinstance(results, list)
    entry = cast(object, results[0])
    assert isinstance(entry, dict)
    entry.update(entry_patch)
    responses[1] = _response(
        path="/docket-entries/",
        params={"docket": "123", "page_size": 100},
        payload=payload,
    )

    with pytest.raises(CourtListenerCaseDevBridgeError, match=reason):
        bridge_public_plan_paid_gap_candidate_via_courtlistener(
            screened,
            paid_gap_record=gap,
            free_download_records=downloads,
            client=_client(*responses),
            use_embedded_entries=True,
        )


@pytest.mark.parametrize(
    ("document_patch", "reason"),
    (
        ({"id": 9999}, "courtlistener_recap_document_id_conflict"),
        ({"docket_entry": 7999}, "courtlistener_recap_entry_conflict"),
        ({"is_sealed": None}, "courtlistener_recap_privacy_unproven"),
        ({"is_sealed": True}, "restricted_core_document"),
        ({"is_private": True}, "restricted_core_document"),
        ({"is_available": True}, "courtlistener_recap_already_available"),
        ({"attachment_number": 1}, "courtlistener_recap_main_document_not_found"),
    ),
)
def test_courtlistener_rest_bridge_rejects_unproven_or_restricted_document(
    document_patch: dict[str, object],
    reason: str,
) -> None:
    screened, gap, downloads = _paid_gap_inputs()
    responses = list(_clean_responses())
    payload = dict(responses[2].payload)
    payload.update(document_patch)
    responses[2] = _response(path="/recap-documents/9005/", payload=payload)

    with pytest.raises(CourtListenerCaseDevBridgeError, match=reason):
        bridge_public_plan_paid_gap_candidate_via_courtlistener(
            screened,
            paid_gap_record=gap,
            free_download_records=downloads,
            client=_client(*responses),
            use_embedded_entries=True,
        )


def test_courtlistener_rest_bridge_rejects_web_document_that_became_free() -> None:
    screened, gap, downloads = _paid_gap_inputs()
    selected_entries = cast(list[dict[str, object]], screened["selected_entries"])
    motion = next(entry for entry in selected_entries if entry["entry_number"] == "5")
    documents = cast(list[dict[str, object]], motion["documents"])
    documents[0].update(
        {
            "action_label": "Download PDF",
            "freely_available": True,
            "href": "https://storage.courtlistener.com/recap/newly-free.pdf",
            "pacer_only": False,
        }
    )

    with pytest.raises(
        CourtListenerCaseDevBridgeError,
        match="paid_gap_public_document_conflict: 5",
    ):
        bridge_public_plan_paid_gap_candidate_via_courtlistener(
            screened,
            paid_gap_record=gap,
            free_download_records=downloads,
            client=_client(*_clean_responses()),
            use_embedded_entries=True,
        )


def _paid_gap_inputs() -> tuple[
    dict[str, object], dict[str, object], tuple[dict[str, object], ...]
]:
    screened = _screened_case()
    plan = plan_public_packet_downloads(
        (screened,), use_embedded_entries=True, target_clean_cases=1
    )
    [gap] = plan.paid_gap_cases
    downloads = tuple(
        {
            **request.to_record(),
            "local_path": f"123/{request.source_document_id}.pdf",
            "sha256": "a" * 64,
            "free_or_purchased": "free",
        }
        for request in plan.download_requests
    )
    return screened, gap.to_record(), downloads


def _clean_responses() -> tuple[RecordedCourtListenerResponse, ...]:
    return _clean_responses_for(
        candidate_id="123",
        docket_number="1:26-cv-00001",
        case_name="Fixture v. Example",
        docket_entry_id="7005",
        recap_document_id="9005",
    )


def _clean_responses_for(
    *,
    candidate_id: str,
    docket_number: str,
    case_name: str,
    docket_entry_id: str,
    recap_document_id: str,
) -> tuple[RecordedCourtListenerResponse, ...]:
    return (
        _response(
            path=f"/dockets/{candidate_id}/",
            payload={
                "id": int(candidate_id),
                "court": "nysd",
                "docket_number": docket_number,
                "case_name": case_name,
            },
        ),
        _response(
            path="/docket-entries/",
            params={"docket": candidate_id, "page_size": 100},
            payload={
                "results": [
                    {
                        "id": int(docket_entry_id),
                        "docket": int(candidate_id),
                        "entry_number": 5,
                        "description": "MOTION to Dismiss filed by Defendant.",
                        "date_filed": "2026-01-01",
                        "recap_documents": [{"id": int(recap_document_id)}],
                    }
                ],
                "next": None,
            },
        ),
        _response(
            path=f"/recap-documents/{recap_document_id}/",
            payload={
                "id": int(recap_document_id),
                "docket_entry": int(docket_entry_id),
                "document_number": "5",
                "attachment_number": None,
                "description": "Motion to Dismiss",
                "is_available": False,
                "is_sealed": False,
            },
        ),
    )


def _client(*responses: RecordedCourtListenerResponse) -> CourtListenerClient:
    return CourtListenerClient(
        config=CourtListenerConfig(),
        transport=CourtListenerFixtureTransport(responses),
    )


def _response(
    *,
    path: str,
    payload: dict[str, object],
    params: dict[str, object] | None = None,
) -> RecordedCourtListenerResponse:
    return RecordedCourtListenerResponse(
        method="GET",
        path=path,
        params={} if params is None else params,
        status_code=200,
        payload=payload,
    )


def _screened_case() -> dict[str, object]:
    return {
        "nature_of_suit": "440 Civil Rights",
        "nos_macro_category": "civil_rights",
        "candidate": {
            "docket_id": "123",
            "candidate_key": "123",
            "metadata": {
                "case_id": "123",
                "case_name": "Fixture v. Example",
                "court": "nysd",
                "docket_number": "1:26-cv-00001",
            },
            "url": "https://www.courtlistener.com/docket/123/example/",
        },
        "ai": {
            "target_motion_entry_numbers": ["5"],
            "decision_entry_numbers": ["16"],
        },
        "first_written_mtd_disposition_date": "2026-06-30",
        "eligibility_anchor_date": "2026-06-30",
        "selected_entries": [
            _entry(
                1,
                "COMPLAINT filed by Plaintiff.",
                "Complaint",
                "https://storage.courtlistener.com/complaint.pdf",
                pacer_only=False,
            ),
            _entry(
                5,
                "MOTION to Dismiss filed by Defendant.",
                "Motion to Dismiss",
                "https://ecf.nysd.uscourts.gov/doc1/12345",
                pacer_only=True,
            ),
            _entry(
                16,
                "ORDER on Motion to Dismiss.",
                "Order on Motion to Dismiss",
                "https://storage.courtlistener.com/decision.pdf",
                pacer_only=False,
            ),
        ],
    }


def _screened_case_variant(
    *, candidate_id: str, docket_number: str, case_name: str
) -> dict[str, object]:
    screened = copy.deepcopy(_screened_case())
    candidate = cast(object, screened["candidate"])
    assert isinstance(candidate, dict)
    candidate["docket_id"] = candidate_id
    candidate["candidate_key"] = candidate_id
    candidate["url"] = f"https://www.courtlistener.com/docket/{candidate_id}/example/"
    metadata = cast(object, candidate["metadata"])
    assert isinstance(metadata, dict)
    metadata["case_id"] = candidate_id
    metadata["docket_number"] = docket_number
    metadata["case_name"] = case_name
    return screened


def _write_jsonl(path: Path, records: list[object]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        cast(dict[str, Any], json.loads(line))
        for line in path.read_text().splitlines()
        if line
    ]


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def _recorded_response_record(
    response: RecordedCourtListenerResponse,
) -> dict[str, object]:
    return {
        "method": response.method,
        "path": response.path,
        "params": dict(response.params),
        "status_code": response.status_code,
        "payload": dict(response.payload),
    }


def _entry(
    number: int,
    text: str,
    description: str,
    href: str,
    *,
    pacer_only: bool,
) -> dict[str, object]:
    return {
        "row_id": f"entry-{number}",
        "entry_number": str(number),
        "filed_at": "2026-01-01",
        "text": text,
        "documents": [
            {
                "kind": "main_document",
                "description": description,
                "href": href,
                "action_label": "Buy on PACER" if pacer_only else "Download PDF",
                "pacer_only": pacer_only,
            }
        ],
    }
