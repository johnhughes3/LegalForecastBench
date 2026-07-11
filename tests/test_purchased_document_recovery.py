from __future__ import annotations

import hashlib
import urllib.request
from datetime import UTC, datetime
from email.message import Message
from typing import Any, cast

import pytest
from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPacerPurchaseAttempt,
    CaseDevPacerPurchaseStatus,
)
from legalforecast.ingestion.free_document_downloader import FixtureFreeDocumentSource
from legalforecast.ingestion.provenance import DocumentRole
from legalforecast.ingestion.purchased_document_recovery import (
    PurchasedDocumentRecoveryError,
    PurchasedDocumentRecoveryRequest,
    PurchasedDocumentRecoveryStatus,
    UrlLibPurchasedDocumentSource,
    purchased_document_download_manifest_records,
    purchased_document_recovery_requests_from_records,
    recover_purchased_documents,
)


def test_live_recovery_source_fetches_only_allowlisted_case_dev_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class _Response:
        headers = Message()

        def __init__(self) -> None:
            self._content = b"%PDF purchased motion"

        def __enter__(self) -> _Response:
            self.headers["Content-Type"] = "application/pdf"
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def geturl(self) -> str:
            return "https://api.case.dev/download/doc-1.pdf"

        def read(self, size: int = -1) -> bytes:
            content, self._content = self._content[:size], self._content[size:]
            return content

    class _Opener:
        def open(
            self,
            request: urllib.request.Request,
            *,
            timeout: float,
        ) -> _Response:
            captured["url"] = request.full_url
            captured["authorization"] = request.get_header("Authorization")
            captured["accept"] = request.get_header("Accept")
            captured["timeout"] = timeout
            return _Response()

    def _build_opener(
        *_handlers: urllib.request.BaseHandler,
    ) -> _Opener:
        return _Opener()

    monkeypatch.setattr("urllib.request.build_opener", _build_opener)

    fetch = UrlLibPurchasedDocumentSource(
        api_key="case-dev-token",
        timeout_seconds=12.5,
    ).fetch("https://api.case.dev/download/doc-1.pdf")

    assert fetch.content == b"%PDF purchased motion"
    assert captured == {
        "url": "https://api.case.dev/download/doc-1.pdf",
        "authorization": "Bearer case-dev-token",
        "accept": "application/pdf,application/octet-stream;q=0.9,*/*;q=0.1",
        "timeout": 12.5,
    }


@pytest.mark.parametrize(
    "source_url",
    (
        "http://api.case.dev/download/doc-1.pdf",
        "https://api.case.dev.evil.example/download/doc-1.pdf",
        "https://api.case.dev@evil.example/download/doc-1.pdf",
        "https://127.0.0.1/download/doc-1.pdf",
    ),
)
def test_live_recovery_source_rejects_untrusted_urls_before_network(
    source_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _build_opener(*_args: Any, **_kwargs: Any) -> object:
        raise AssertionError("untrusted recovery URL must not open a socket")

    monkeypatch.setattr("urllib.request.build_opener", _build_opener)

    with pytest.raises(PurchasedDocumentRecoveryError, match="download URL"):
        UrlLibPurchasedDocumentSource(api_key="case-dev-token").fetch(source_url)


def test_live_recovery_source_rejects_redirect_to_untrusted_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened_urls: list[str] = []

    class _Opener:
        def __init__(
            self,
            redirect_handler: urllib.request.HTTPRedirectHandler,
        ) -> None:
            self.redirect_handler = redirect_handler

        def open(
            self,
            request: urllib.request.Request,
            *,
            timeout: float,
        ) -> object:
            del timeout
            opened_urls.append(request.full_url)
            return cast(
                object,
                cast(Any, self.redirect_handler).redirect_request(
                    request,
                    None,
                    302,
                    "Found",
                    Message(),
                    "https://evil.example/stolen.pdf",
                ),
            )

    def _build_redirecting_opener(
        redirect_handler: urllib.request.BaseHandler,
    ) -> _Opener:
        return _Opener(cast(urllib.request.HTTPRedirectHandler, redirect_handler))

    monkeypatch.setattr(
        "urllib.request.build_opener",
        _build_redirecting_opener,
    )

    with pytest.raises(PurchasedDocumentRecoveryError, match="download URL"):
        UrlLibPurchasedDocumentSource(api_key="case-dev-token").fetch(
            "https://api.case.dev/download/doc-1.pdf"
        )
    assert opened_urls == ["https://api.case.dev/download/doc-1.pdf"]


def test_live_recovery_source_strips_authorization_from_cross_host_redirect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class _Response:
        headers = Message()

        def __init__(self) -> None:
            self._content = b"%PDF purchased motion"

        def __enter__(self) -> _Response:
            self.headers["Content-Type"] = "application/pdf"
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def geturl(self) -> str:
            return "https://case.dev/download/doc-1.pdf"

        def read(self, size: int = -1) -> bytes:
            content, self._content = self._content[:size], self._content[size:]
            return content

    class _Opener:
        def __init__(
            self,
            redirect_handler: urllib.request.HTTPRedirectHandler,
        ) -> None:
            self.redirect_handler = redirect_handler

        def open(
            self,
            request: urllib.request.Request,
            *,
            timeout: float,
        ) -> _Response:
            del timeout
            redirected = cast(
                urllib.request.Request | None,
                cast(Any, self.redirect_handler).redirect_request(
                    request,
                    None,
                    302,
                    "Found",
                    Message(),
                    "https://case.dev/download/doc-1.pdf",
                ),
            )
            assert redirected is not None
            captured["authorization"] = redirected.get_header("Authorization")
            captured["url"] = redirected.full_url
            return _Response()

    def _build_redirecting_opener(
        redirect_handler: urllib.request.BaseHandler,
    ) -> _Opener:
        return _Opener(cast(urllib.request.HTTPRedirectHandler, redirect_handler))

    monkeypatch.setattr(
        "urllib.request.build_opener",
        _build_redirecting_opener,
    )

    fetch = UrlLibPurchasedDocumentSource(api_key="case-dev-token").fetch(
        "https://api.case.dev/download/doc-1.pdf"
    )

    assert fetch.content == b"%PDF purchased motion"
    assert captured == {
        "authorization": None,
        "url": "https://case.dev/download/doc-1.pdf",
    }


def test_live_recovery_source_rejects_oversized_content_length_before_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Response:
        headers = Message()

        def __enter__(self) -> _Response:
            self.headers["Content-Type"] = "application/pdf"
            self.headers["Content-Length"] = "9"
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def geturl(self) -> str:
            return "https://api.case.dev/download/doc-1.pdf"

        def read(self, _size: int = -1) -> bytes:
            raise AssertionError("oversized response must be rejected before reading")

    class _Opener:
        def open(
            self,
            request: urllib.request.Request,
            *,
            timeout: float,
        ) -> _Response:
            del request, timeout
            return _Response()

    def _build_opener(*_handlers: urllib.request.BaseHandler) -> _Opener:
        return _Opener()

    monkeypatch.setattr("urllib.request.build_opener", _build_opener)

    with pytest.raises(RuntimeError, match="exceeds the 8-byte maximum"):
        UrlLibPurchasedDocumentSource(
            api_key="case-dev-token",
            max_response_bytes=8,
        ).fetch("https://api.case.dev/download/doc-1.pdf")


def test_live_recovery_source_bounds_chunked_response_without_content_length(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Response:
        headers = Message()

        def __init__(self) -> None:
            self._chunks = [b"%PDF1234", b"56789012", b"X"]

        def __enter__(self) -> _Response:
            self.headers["Content-Type"] = "application/pdf"
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def geturl(self) -> str:
            return "https://api.case.dev/download/doc-1.pdf"

        def read(self, size: int = -1) -> bytes:
            assert 0 < size <= 17
            return self._chunks.pop(0) if self._chunks else b""

    class _Opener:
        def open(
            self,
            request: urllib.request.Request,
            *,
            timeout: float,
        ) -> _Response:
            del request, timeout
            return _Response()

    def _build_opener(*_handlers: urllib.request.BaseHandler) -> _Opener:
        return _Opener()

    monkeypatch.setattr("urllib.request.build_opener", _build_opener)

    with pytest.raises(RuntimeError, match="exceeds the 16-byte maximum"):
        UrlLibPurchasedDocumentSource(
            api_key="case-dev-token",
            max_response_bytes=16,
        ).fetch("https://api.case.dev/download/doc-1.pdf")


def test_recovery_downloads_purchased_document_and_marks_provenance(tmp_path) -> None:
    source = FixtureFreeDocumentSource(
        {"https://case.dev/download/doc-1.pdf": b"purchased complaint pdf"}
    )
    retrieved_at = datetime(2026, 5, 17, tzinfo=UTC)

    records = recover_purchased_documents(
        (
            _request(
                _attempt("doc-1", download_url="https://case.dev/download/doc-1.pdf"),
                role=DocumentRole.COMPLAINT,
                docket_entry_number=1,
                pre_purchase_evidence={"availability": "pacer_only"},
            ),
        ),
        output_root=tmp_path,
        source=source,
        retrieved_at=retrieved_at,
    )

    record = records[0]
    assert record.status is PurchasedDocumentRecoveryStatus.RECOVERED
    assert record.local_path == "cand-1/case-dev-pacer/entry-1_doc-1.pdf"
    assert (tmp_path / record.local_path).read_bytes() == b"purchased complaint pdf"
    assert record.sha256 == hashlib.sha256(b"purchased complaint pdf").hexdigest()
    assert record.free_or_purchased == "purchased"
    assert record.purchase_cost_usd == "3.05"
    assert record.pre_purchase_evidence == {"availability": "pacer_only"}
    assert record.post_purchase_evidence["availability"] == "available"
    assert record.provenance is not None
    assert record.provenance.source_provider == "case.dev+pacer"
    assert record.provenance.source_document_id == "doc-1"
    assert record.provenance.is_mounted_for_model is True
    assert record.provenance.retrieved_at == retrieved_at


def test_recovery_handles_partial_purchases_without_fetching_failed_attempts(
    tmp_path,
) -> None:
    source = FixtureFreeDocumentSource(
        {"https://case.dev/download/doc-1.pdf": b"purchased motion pdf"}
    )

    records = recover_purchased_documents(
        (
            _request(
                _attempt("doc-1", download_url="https://case.dev/download/doc-1.pdf"),
                role=DocumentRole.MTD_MEMORANDUM,
                docket_entry_number=34,
            ),
            _request(
                CaseDevPacerPurchaseAttempt(
                    candidate_id="cand-1",
                    source_document_id="doc-2",
                    status=CaseDevPacerPurchaseStatus.PROVIDER_ERROR,
                    reason="pacer fee cap exceeded",
                ),
                role=DocumentRole.OPPOSITION,
                docket_entry_number=35,
            ),
        ),
        output_root=tmp_path,
        source=source,
        retrieved_at=datetime(2026, 5, 17, tzinfo=UTC),
    )

    assert [record.status for record in records] == [
        PurchasedDocumentRecoveryStatus.RECOVERED,
        PurchasedDocumentRecoveryStatus.PURCHASE_NOT_EXECUTED,
    ]
    assert records[1].provenance is None
    assert records[1].post_purchase_evidence["purchase_status"] == "provider_error"
    assert source.requested_urls == ("https://case.dev/download/doc-1.pdf",)


def test_recovery_never_mounts_post_decision_outcome_material(tmp_path) -> None:
    source = FixtureFreeDocumentSource(
        {"https://case.dev/download/order.pdf": b"outcome order pdf"}
    )

    records = recover_purchased_documents(
        (
            _request(
                _attempt(
                    "order-doc",
                    download_url="https://case.dev/download/order.pdf",
                ),
                role=DocumentRole.DECISION,
                docket_entry_number=44,
                is_predecision_material=False,
                contains_target_outcome=True,
            ),
        ),
        output_root=tmp_path,
        source=source,
        retrieved_at=datetime(2026, 5, 17, tzinfo=UTC),
    )

    record = records[0]
    assert record.status is PurchasedDocumentRecoveryStatus.RECOVERED_AUDIT_ONLY
    assert record.provenance is not None
    assert record.provenance.contains_target_outcome is True
    assert record.provenance.is_mounted_for_model is False
    assert record.provenance.packet_section is None
    manifest = purchased_document_download_manifest_records(records)
    assert manifest == ()


@pytest.mark.parametrize(
    "restriction",
    (
        {"redaction_or_seal_status": "sealed"},
        {"is_private": True},
        {"availability_status": "restricted"},
    ),
)
def test_recovery_rejects_sealed_private_or_restricted_selected_documents(
    restriction: dict[str, object],
) -> None:
    purchase_result = _purchase_result_record()
    document = {
        "source_document_id": "doc-1",
        "document_role": "motion_to_dismiss_memorandum",
        "docket_entry_number": 34,
        **restriction,
    }

    with pytest.raises(
        PurchasedDocumentRecoveryError,
        match="sealed/private/restricted",
    ):
        purchased_document_recovery_requests_from_records(
            purchase_result,
            (
                {
                    "candidate_id": "cand-1",
                    "case_id": "case-1",
                    "court": "S.D.N.Y.",
                    "docket_number": "1:26-cv-00001",
                    "documents": [document],
                },
            ),
        )


def test_guarded_purchase_result_converts_to_parser_consumable_manifest(
    tmp_path,
) -> None:
    purchase_result = _purchase_result_record()
    selection_records = (
        {
            "candidate_id": "cand-1",
            "case_id": "case-1",
            "court": "S.D.N.Y.",
            "docket_number": "1:26-cv-00001",
            "documents": [
                {
                    "source_document_id": "doc-1",
                    "document_role": "motion_to_dismiss_memorandum",
                    "docket_entry_number": 34,
                    "model_visible": True,
                    "contains_target_outcome": False,
                    "availability_status": "unavailable",
                }
            ],
        },
    )

    requests = purchased_document_recovery_requests_from_records(
        purchase_result,
        selection_records,
    )
    records = recover_purchased_documents(
        requests,
        output_root=tmp_path,
        source=FixtureFreeDocumentSource(
            {"https://case.dev/download/doc-1.pdf": b"purchased motion pdf"}
        ),
        retrieved_at=datetime(2026, 7, 11, tzinfo=UTC),
    )
    manifest = purchased_document_download_manifest_records(records)

    assert len(manifest) == 1
    assert manifest[0] == {
        "candidate_id": "cand-1",
        "source_provider": "case.dev+pacer",
        "source_document_id": "doc-1",
        "docket_entry_number": 34,
        "document_role": "motion_to_dismiss_memorandum",
        "source_url": "https://case.dev/download/doc-1.pdf",
        "local_path": "cand-1/case-dev-pacer/entry-34_doc-1.pdf",
        "sha256": hashlib.sha256(b"purchased motion pdf").hexdigest(),
        "byte_count": len(b"purchased motion pdf"),
        "free_or_purchased": "purchased",
        "purchase_cost_usd": "3.05",
        "retry_count": 0,
        "rate_limited": False,
        "reused_existing": False,
    }


def test_recovery_accepts_plan_recorded_nondefault_cost_below_cap() -> None:
    purchase_result = _purchase_result_record()
    purchase_result["projected_cost_usd"] = "4.25"
    attempts = purchase_result["attempts"]
    assert isinstance(attempts, list)
    attempt = attempts[0]
    assert isinstance(attempt, dict)
    attempt["pacer_fees"] = {
        "pacer_fee_usd": "1.20",
        "service_fee_usd": "3.05",
        "total_usd": "4.25",
    }

    requests = purchased_document_recovery_requests_from_records(
        purchase_result,
        (
            {
                "candidate_id": "cand-1",
                "case_id": "case-1",
                "court": "S.D.N.Y.",
                "docket_number": "1:26-cv-00001",
                "documents": [
                    {
                        "source_document_id": "doc-1",
                        "document_role": "motion_to_dismiss_memorandum",
                        "availability_status": "unavailable",
                    }
                ],
            },
        ),
    )

    assert len(requests) == 1
    assert requests[0].purchase_attempt.pacer_fees == {
        "pacer_fee_usd": "1.20",
        "service_fee_usd": "3.05",
        "total_usd": "4.25",
    }


@pytest.mark.parametrize(
    ("override", "message"),
    (
        ({"acknowledge_pacer_fees": False}, "fee acknowledgment"),
        ({"capability": "unknown"}, "document-level capability"),
        ({"live": False}, "live purchase"),
        ({"dry_run": True}, "executed purchase result"),
        ({"max_projected_budget_usd": "2250.01"}, "configured cap"),
        ({"projected_cost_usd": "2250.01"}, "projected cost"),
    ),
)
def test_purchase_recovery_rejects_results_that_do_not_prove_guardrails(
    override: dict[str, object],
    message: str,
) -> None:
    purchase_result = {**_purchase_result_record(), **override}

    with pytest.raises(PurchasedDocumentRecoveryError, match=message):
        purchased_document_recovery_requests_from_records(
            purchase_result,
            (),
        )


def test_purchase_recovery_preserves_24_document_per_case_cap() -> None:
    attempts = []
    for index in range(25):
        attempt = _purchase_result_record()["attempts"][0]
        assert isinstance(attempt, dict)
        attempts.append(
            {
                **attempt,
                "source_document_id": f"doc-{index}",
                "status": "not_attempted",
                "fee_acknowledged": None,
                "pacer_fees": None,
                "download_url": None,
            }
        )
    purchase_result = {
        **_purchase_result_record(),
        "projected_cost_usd": "76.25",
        "intended_purchase_count": 25,
        "executed_purchase_count": 0,
        "attempts": attempts,
    }

    with pytest.raises(PurchasedDocumentRecoveryError, match="per-case cap is 24"):
        purchased_document_recovery_requests_from_records(purchase_result, ())


@pytest.mark.parametrize(
    ("count_field", "recorded_count"),
    (
        ("intended_purchase_count", 0),
        ("intended_purchase_count", 2),
        ("executed_purchase_count", 0),
        ("executed_purchase_count", 2),
    ),
)
def test_purchase_recovery_rejects_counts_inconsistent_with_attempts(
    count_field: str,
    recorded_count: int,
) -> None:
    purchase_result = _purchase_result_record()
    purchase_result[count_field] = recorded_count

    with pytest.raises(
        PurchasedDocumentRecoveryError,
        match=f"{count_field}.*attempts",
    ):
        purchased_document_recovery_requests_from_records(purchase_result, ())


@pytest.mark.parametrize(
    "count_field",
    ("intended_purchase_count", "executed_purchase_count"),
)
def test_purchase_recovery_requires_integer_purchase_counts(count_field: str) -> None:
    purchase_result = _purchase_result_record()
    purchase_result[count_field] = "1"

    with pytest.raises(PurchasedDocumentRecoveryError, match=f"{count_field}.*integer"):
        purchased_document_recovery_requests_from_records(purchase_result, ())


def _attempt(
    source_document_id: str,
    *,
    download_url: str,
) -> CaseDevPacerPurchaseAttempt:
    return CaseDevPacerPurchaseAttempt(
        candidate_id="cand-1",
        source_document_id=source_document_id,
        status=CaseDevPacerPurchaseStatus.PURCHASED,
        fee_acknowledged=True,
        pacer_fees={
            "pacer_fee_usd": "0.00",
            "service_fee_usd": "3.05",
            "total_usd": "3.05",
        },
        download_url=download_url,
    )


def _request(
    attempt: CaseDevPacerPurchaseAttempt,
    *,
    role: DocumentRole,
    docket_entry_number: int,
    pre_purchase_evidence: dict[str, str] | None = None,
    is_predecision_material: bool = True,
    contains_target_outcome: bool = False,
) -> PurchasedDocumentRecoveryRequest:
    return PurchasedDocumentRecoveryRequest(
        purchase_attempt=attempt,
        source_case_id="case-1",
        court="S.D.N.Y.",
        docket_number="1:26-cv-00001",
        document_role=role,
        docket_entry_number=docket_entry_number,
        pre_purchase_evidence=(
            {} if pre_purchase_evidence is None else pre_purchase_evidence
        ),
        is_predecision_material=is_predecision_material,
        contains_target_outcome=contains_target_outcome,
    )


def _purchase_result_record() -> dict[str, object]:
    return {
        "live": True,
        "acknowledge_pacer_fees": True,
        "capability": "document_level_purchase",
        "dry_run": False,
        "projected_cost_usd": "3.05",
        "max_projected_budget_usd": "2250.00",
        "intended_purchase_count": 1,
        "executed_purchase_count": 1,
        "attempts": [
            {
                "candidate_id": "cand-1",
                "source_document_id": "doc-1",
                "status": "purchased",
                "reason": None,
                "fee_acknowledged": True,
                "pacer_fees": {
                    "pacer_fee_usd": "0.00",
                    "service_fee_usd": "3.05",
                    "total_usd": "3.05",
                },
                "download_url": "https://case.dev/download/doc-1.pdf",
            }
        ],
    }
