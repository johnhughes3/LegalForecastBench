from __future__ import annotations

import hashlib
from typing import Any

import pytest
from legalforecast.ingestion.canonical_json import canonical_json_bytes
from legalforecast.ingestion.courtlistener_client import (
    CourtListenerClient,
    CourtListenerFixtureTransport,
    CourtListenerUnavailableError,
    RecordedCourtListenerResponse,
)
from legalforecast.ingestion.exact100_zero_cost_recovery import (
    Exact100ZeroCostRecoveryError,
    execute_exact100_zero_cost_recovery,
    issue_exact100_zero_cost_recovery_request,
)
from legalforecast.ingestion.free_document_downloader import FixtureFreeDocumentSource
from legalforecast.ingestion.post_selection_terminal_exclusion import (
    verify_terminal_recovery_evidence,
)


def _bytes(value: object) -> bytes:
    return canonical_json_bytes(
        value, error_type=ValueError, error_message="test serialization failed"
    )


def _selection(
    *, source_document_id: str = "480673755", docket_id: str = "72449171"
) -> bytes:
    selected = {
        "candidate_id": "72449171",
        "identity_resolution": {"courtlistener_docket_id": docket_id},
        "documents": [
            {
                "source_document_id": source_document_id,
                "document_role": "motion_to_dismiss_memorandum",
                "courtlistener_docket_entry_id": "465468661",
            }
        ],
    }
    fillers = [
        {
            "candidate_id": str(80000000 + number),
            "identity_resolution": {"courtlistener_docket_id": str(90000000 + number)},
            "documents": [
                {
                    "source_document_id": str(100000000 + number),
                    "document_role": "motion_to_dismiss_memorandum",
                    "courtlistener_docket_entry_id": str(110000000 + number),
                }
            ],
        }
        for number in range(1, 100)
    ]
    return b"".join(_bytes(record) for record in [selected, *fillers])


def _plan(selection_bytes: bytes, *, source_document_id: str = "480673755") -> bytes:
    import hashlib

    return _bytes(
        {
            "schema_version": "legalforecast.exact100_zero_cost_recovery_plan.v1",
            "selection_sha256": "sha256:" + hashlib.sha256(selection_bytes).hexdigest(),
            "records": [
                {
                    "candidate_id": "72449171",
                    "source_document_id": source_document_id,
                }
            ],
        }
    )


def _client(
    *,
    status_code: int,
    payload: dict[str, object],
    docket_entry_payload: dict[str, object] | None = None,
    raw_body: bytes | None = None,
) -> tuple[CourtListenerClient, CourtListenerFixtureTransport]:
    responses = [
        RecordedCourtListenerResponse(
            method="GET",
            path="/recap-documents/480673755/",
            params={},
            status_code=status_code,
            payload=payload,
            raw_body=_bytes(payload) if raw_body is None else raw_body,
        )
    ]
    if status_code == 200:
        responses.append(
            RecordedCourtListenerResponse(
                method="GET",
                path="/docket-entries/465468661/",
                params={},
                status_code=200,
                payload=(
                    _docket_entry_payload()
                    if docket_entry_payload is None
                    else docket_entry_payload
                ),
            )
        )
    transport = CourtListenerFixtureTransport(tuple(responses))
    return CourtListenerClient(transport=transport, max_retries=0), transport


def _public_payload(**overrides: object) -> dict[str, object]:
    return {
        "id": "480673755",
        "docket_entry": "/api/rest/v4/docket-entries/465468661/",
        "is_available": True,
        "is_sealed": False,
        "is_private": False,
        "filepath_local": "recap/2026/08/09/480673755.pdf",
        **overrides,
    }


def _docket_entry_payload(**overrides: object) -> dict[str, object]:
    return {
        "id": "465468661",
        "docket": "/api/rest/v4/dockets/72449171/",
        "description": "MEMORANDUM in support of motion to dismiss",
        "recap_documents": ["480673755"],
        **overrides,
    }


def test_unavailable_404_emits_only_replay_accepted_terminal_evidence() -> None:
    selection_bytes = _selection()
    client, transport = _client(status_code=404, payload={"detail": "not found"})

    result = execute_exact100_zero_cost_recovery(
        selection_bytes=selection_bytes,
        plan_bytes=_plan(selection_bytes),
        courtlistener=client,
    )

    assert transport.requests == [("GET", "/recap-documents/480673755/", {})]
    assert result.public_document_manifest is None
    assert result.terminal_exclusion_authority is False
    assert result.receipt is not None
    assert result.receipt_bytes is not None
    assert result.run_card is not None
    assert result.run_card_bytes is not None
    assert result.rest_observation is not None
    assert result.rest_observation_bytes is not None
    assert result.rest_observation_transcript_bytes is not None
    assert result.rest_observation_response_bytes == _bytes({"detail": "not found"})
    evidence = verify_terminal_recovery_evidence(
        selection_bytes=selection_bytes,
        request=result.request.record,
        request_bytes=result.request.record_bytes,
        receipt=result.receipt,
        receipt_bytes=result.receipt_bytes,
        run_card=result.run_card,
        run_card_bytes=result.run_card_bytes,
        rest_observation=result.rest_observation,
        rest_observation_bytes=result.rest_observation_bytes,
        rest_observation_transcript_bytes=result.rest_observation_transcript_bytes,
        rest_observation_response_bytes=result.rest_observation_response_bytes,
    )
    assert evidence.candidate_id == "72449171"
    assert evidence.source_document_id == "480673755"


def test_unavailable_404_preserves_exact_noncanonical_response_bytes() -> None:
    selection_bytes = _selection()
    raw_body = b'{  "detail" : "not found", "extra": [1, 2] }\n'
    client, _transport = _client(
        status_code=404,
        payload={"detail": "not found", "extra": [1, 2]},
        raw_body=raw_body,
    )

    result = execute_exact100_zero_cost_recovery(
        selection_bytes=selection_bytes,
        plan_bytes=_plan(selection_bytes),
        courtlistener=client,
    )

    assert result.rest_observation_response_bytes == raw_body
    assert result.rest_observation_transcript_bytes is not None
    digest = b"sha256:" + hashlib.sha256(raw_body).hexdigest().encode()
    assert digest in result.rest_observation_transcript_bytes


def test_unavailable_404_without_observed_response_bytes_fails_closed() -> None:
    selection_bytes = _selection()
    transport = CourtListenerFixtureTransport(
        (
            RecordedCourtListenerResponse(
                method="GET",
                path="/recap-documents/480673755/",
                params={},
                status_code=404,
                payload={"detail": "not found"},
                raw_body=None,
            ),
        )
    )
    client = CourtListenerClient(transport=transport, max_retries=0)

    with pytest.raises(
        Exact100ZeroCostRecoveryError, match="exact replayable response observation"
    ):
        execute_exact100_zero_cost_recovery(
            selection_bytes=selection_bytes,
            plan_bytes=_plan(selection_bytes),
            courtlistener=client,
        )


@pytest.mark.parametrize(
    "error",
    [
        CourtListenerUnavailableError("missing observation"),
        CourtListenerUnavailableError(
            "wrong method",
            method="POST",
            path="/recap-documents/480673755/",
            status_code=404,
            response_bytes=b"not found",
        ),
        CourtListenerUnavailableError(
            "wrong path",
            method="GET",
            path="/recap-documents/480673754/",
            status_code=404,
            response_bytes=b"not found",
        ),
        CourtListenerUnavailableError(
            "wrong status",
            method="GET",
            path="/recap-documents/480673755/",
            status_code=410,
            response_bytes=b"gone",
        ),
    ],
)
def test_unavailable_exception_without_exact_observation_fails_closed(
    monkeypatch: pytest.MonkeyPatch, error: CourtListenerUnavailableError
) -> None:
    selection_bytes = _selection()
    client, _transport = _client(status_code=404, payload={"detail": "not found"})

    def _raise_unavailable(_document_id: str) -> None:
        raise error

    monkeypatch.setattr(client, "get_recap_document", _raise_unavailable)
    with pytest.raises(
        Exact100ZeroCostRecoveryError, match="exact replayable response observation"
    ):
        execute_exact100_zero_cost_recovery(
            selection_bytes=selection_bytes,
            plan_bytes=_plan(selection_bytes),
            courtlistener=client,
        )


def test_successful_public_recovery_retains_candidate_for_normal_handoff(
    tmp_path: Any,
) -> None:
    selection_bytes = _selection()
    client, transport = _client(status_code=200, payload=_public_payload())
    source = FixtureFreeDocumentSource(
        {
            "https://storage.courtlistener.com/recap/2026/08/09/480673755.pdf": (
                b"%PDF-1.7 public memorandum"
            )
        }
    )

    result = execute_exact100_zero_cost_recovery(
        selection_bytes=selection_bytes,
        plan_bytes=_plan(selection_bytes),
        courtlistener=client,
        public_document_source=source,
        public_output_root=tmp_path,
    )

    assert transport.requests == [
        ("GET", "/recap-documents/480673755/", {}),
        ("GET", "/docket-entries/465468661/", {}),
    ]
    assert source.requested_urls == (
        "https://storage.courtlistener.com/recap/2026/08/09/480673755.pdf",
    )
    assert result.receipt is None
    assert result.run_card is None
    assert result.rest_observation is None
    assert result.terminal_exclusion_authority is False
    assert result.public_document_manifest is not None
    assert result.public_document_manifest["candidate_id"] == "72449171"
    assert result.public_document_manifest["terminal_exclusion_authority"] is False
    assert result.public_download is not None
    assert result.public_download.byte_count == len(b"%PDF-1.7 public memorandum")
    assert (tmp_path / result.public_download.local_path).is_file()
    # The authenticated predecessor selection remains unchanged; this output is
    # a handoff sidecar, not a terminal exclusion or replacement decision.
    assert result.request.selection_bytes == selection_bytes


def test_request_issues_only_the_allowlisted_memorandum_not_the_complaint() -> None:
    selection_bytes = _selection()

    request = issue_exact100_zero_cost_recovery_request(
        selection_bytes=selection_bytes,
        plan_bytes=_plan(selection_bytes),
    )

    assert request.record["candidate_id"] == "72449171"
    assert request.record["source_document_id"] == "480673755"
    assert request.record["courtlistener_docket_id"] == "72449171"
    assert request.record["courtlistener_docket_entry_id"] == "465468661"
    with pytest.raises(Exact100ZeroCostRecoveryError, match="fixed allowlist"):
        issue_exact100_zero_cost_recovery_request(
            selection_bytes=_selection(source_document_id="471866646"),
            plan_bytes=_plan(
                _selection(source_document_id="471866646"),
                source_document_id="471866646",
            ),
        )
    with pytest.raises(Exact100ZeroCostRecoveryError, match="stipulated CourtListener"):
        issue_exact100_zero_cost_recovery_request(
            selection_bytes=_selection(docket_id="72449000"),
            plan_bytes=_plan(_selection(docket_id="72449000")),
        )


@pytest.mark.parametrize(
    "docket_entry_payload",
    [
        _docket_entry_payload(id="465468660"),
        _docket_entry_payload(docket="/api/rest/v4/dockets/72449170/"),
        _docket_entry_payload(recap_documents=["480673754"]),
    ],
)
def test_public_recovery_fails_closed_on_exact_docket_entry_drift(
    tmp_path: Any, docket_entry_payload: dict[str, object]
) -> None:
    selection_bytes = _selection()
    client, transport = _client(
        status_code=200,
        payload=_public_payload(),
        docket_entry_payload=docket_entry_payload,
    )

    with pytest.raises(Exact100ZeroCostRecoveryError, match="docket-entry identity"):
        execute_exact100_zero_cost_recovery(
            selection_bytes=selection_bytes,
            plan_bytes=_plan(selection_bytes),
            courtlistener=client,
            public_document_source=FixtureFreeDocumentSource({}),
            public_output_root=tmp_path,
        )
    assert transport.requests == [
        ("GET", "/recap-documents/480673755/", {}),
        ("GET", "/docket-entries/465468661/", {}),
    ]


@pytest.mark.parametrize(
    ("status_code", "payload"),
    [
        (401, {"detail": "authentication required"}),
        (429, {"detail": "rate limited"}),
        (503, {"detail": "unavailable"}),
        (200, _public_payload(id="480673754")),
        (200, _public_payload(is_available=False)),
        (200, _public_payload(filepath_local="https://example.test/memo.pdf")),
    ],
)
def test_nonterminal_or_unsafe_metadata_fails_closed(
    tmp_path: Any, status_code: int, payload: dict[str, object]
) -> None:
    selection_bytes = _selection()
    client, _transport = _client(status_code=status_code, payload=payload)

    with pytest.raises(Exact100ZeroCostRecoveryError):
        execute_exact100_zero_cost_recovery(
            selection_bytes=selection_bytes,
            plan_bytes=_plan(selection_bytes),
            courtlistener=client,
            public_document_source=FixtureFreeDocumentSource({}),
            public_output_root=tmp_path,
        )


@pytest.mark.parametrize(
    "unsafe_url",
    [
        "recap/2026/08/09/480673754.pdf",
        "https://storage.courtlistener.com/recap/2026/08/09/480673754.pdf",
        "https://storage.courtlistener.com/recap/2026/08/09/480673755.pdf?q=1",
        "https://storage.courtlistener.com/recap/2026/08/09/480673755.pdf#page=1",
        "https://storage.courtlistener.com/recap/2026/08/09/%34%38%30%36%37%33%37%35%35.pdf",
        "https://example.test/recap/2026/08/09/480673755.pdf",
    ],
)
def test_public_recovery_rejects_unbound_or_noncanonical_url_before_download(
    tmp_path: Any, unsafe_url: str
) -> None:
    selection_bytes = _selection()
    client, _transport = _client(
        status_code=200,
        payload=_public_payload(filepath_local=unsafe_url),
    )
    source = FixtureFreeDocumentSource({})

    with pytest.raises(Exact100ZeroCostRecoveryError, match=r"document-bound|unsafe"):
        execute_exact100_zero_cost_recovery(
            selection_bytes=selection_bytes,
            plan_bytes=_plan(selection_bytes),
            courtlistener=client,
            public_document_source=source,
            public_output_root=tmp_path,
        )
    assert source.requested_urls == ()
