from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from io import BytesIO
from pathlib import Path
from typing import cast
from urllib.request import Request

import legalforecast.ingestion.disclosure_model_review_authority as authority_module
import pytest
from legalforecast.evals.live_model_solver import LiveModelProviderError
from legalforecast.ingestion.provenance_clearance import (
    canonical_json_bytes,
    exception_review_worksheet_v3,
)
from reportlab.pdfgen.canvas import Canvas

DisclosureModelReviewAuthorityError = (
    authority_module.DisclosureModelReviewAuthorityError
)
authenticate_disclosure_model_review = (
    authority_module.authenticate_disclosure_model_review
)
private_disclosure_model_review_records = (
    authority_module.private_disclosure_model_review_records
)
public_disclosure_model_review_record = (
    authority_module.public_disclosure_model_review_record
)

ROOT = Path(__file__).resolve().parents[1]
CYCLE_ID = "cycle-1-target-100-2026-07-25"


def _pdf(text: str) -> bytes:
    output = BytesIO()
    canvas = Canvas(output, invariant=1)
    canvas.drawString(72, 720, text)
    canvas.showPage()
    canvas.save()
    return output.getvalue()


def _row(data: bytes) -> dict[str, object]:
    return {
        "candidate_id": "courtlistener-docket-1",
        "source_document_id": "entry-2",
        "local_path": "courtlistener-docket-1/entry-2.pdf",
        "sha256": hashlib.sha256(data).hexdigest(),
        "byte_count": len(data),
        "free_or_purchased": "free",
        "source_provider": "courtlistener",
        "source_url": "https://storage.courtlistener.com/recap/a.pdf",
        "source_url_or_reference": "https://storage.courtlistener.com/recap/a.pdf",
        "restriction_status": "unknown",
        "restriction_evidence": sorted(
            [
                "courtlistener_rest_docket_exact_match",
                "courtlistener_rest_docket_entry_exact_match",
                "courtlistener_rest_recap_document_exact_match",
                "courtlistener_rest_recap_document_is_available_true",
                "courtlistener_rest_recap_document_is_sealed_unknown",
                "courtlistener_rest_public_download_url_allowlisted",
            ]
        ),
        "is_sealed": None,
        "is_private": None,
        "model_visible": False,
        "contains_target_outcome": True,
        "disclosure_pdf_scan": {
            "schema_version": "legalforecast.disclosure_pdf_scan.v1",
            "method": "pypdf_page_text_v1",
            "parsed_page_count": 1,
            "text_scanned_page_numbers": [1],
            "text_scanned_page_count": 1,
            "ocr_scanned_page_numbers": [],
            "ocr_scanned_page_count": 0,
            "unscanned_page_numbers": [],
            "coverage_status": "complete",
            "diagnostics": [],
            "automated_markers": ["medical"],
        },
        "automated_markers": ["medical"],
        "route": "exception_review",
        "route_reasons": ["automated_marker_present"],
        "exception_clearance_permitted": True,
    }


def _response(document_sha256: str) -> dict[str, object]:
    return {
        "schema_version": "legalforecast.disclosure_model_review_response.v1",
        "candidate_id": "courtlistener-docket-1",
        "source_document_id": "entry-2",
        "document_sha256": document_sha256,
        "model_id": "gemini-3.5-flash",
        "model_version": "gemini-3.5-flash",
        "decision": "cleared",
        "sensitive_content": "absent",
        "supporting_page_number": 1,
        "supporting_excerpt": "medical record cited only as a public allegation",
    }


def _inputs() -> tuple[
    dict[str, object], bytes, dict[str, object], bytes, dict[tuple[str, str], bytes]
]:
    data = _pdf("medical record cited only as a public allegation")
    row = _row(data)
    scan = cast(dict[str, object], row["disclosure_pdf_scan"])
    scan.update(
        {
            "parsed_page_count": 1,
            "text_scanned_page_numbers": [1],
            "text_scanned_page_count": 1,
        }
    )
    documents = [row]
    plan: dict[str, object] = {
        "schema_version": "legalforecast.disclosure_provenance_routing_plan.v3",
        "source_sha256": {
            "review_requests": "a" * 64,
            "download_manifest": "b" * 64,
            "restriction_evidence": "c" * 64,
            "case_relevance": "d" * 64,
        },
        "document_set_sha256": hashlib.sha256(
            canonical_json_bytes(documents)
        ).hexdigest(),
        "document_count": 1,
        "auto_clear_count": 0,
        "exception_review_count": 1,
        "documents": documents,
    }
    worksheet = exception_review_worksheet_v3(plan)
    return (
        plan,
        canonical_json_bytes(plan),
        worksheet,
        canonical_json_bytes(worksheet),
        {("courtlistener-docket-1", "entry-2"): data},
    )


def _provider_payload(document_sha256: str) -> dict[str, object]:
    item = _response(document_sha256)
    item["supporting_page_number"] = 1
    semantic = {
        "schema_version": "legalforecast.disclosure_model_review_batch_response.v1",
        "model_id": "gemini-3.5-flash",
        "model_version": "gemini-3.5-flash",
        "document_count": 1,
        "items": [item],
    }
    raw_output = json.dumps(semantic, sort_keys=True, separators=(",", ":")) + "\n"
    return {
        "modelVersion": "models/gemini-3.5-flash",
        "candidates": [{"content": {"parts": [{"text": raw_output}]}}],
        "usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 20},
    }


def _authenticate(tmp_path: Path, **overrides: object) -> object:
    plan, plan_bytes, worksheet, worksheet_bytes, documents = _inputs()
    payload = _provider_payload(
        cast(str, cast(list[dict[str, object]], plan["documents"])[0]["sha256"])
    )

    def transport(_request: Request, _timeout: float) -> dict[str, object]:
        return payload

    arguments: dict[str, object] = {
        "routing_plan": plan,
        "routing_plan_bytes": plan_bytes,
        "worksheet": worksheet,
        "worksheet_bytes": worksheet_bytes,
        "document_bytes_by_key": documents,
        "provider_journal_path": tmp_path / "provider-attempts.sqlite3",
        "provider_spend_authority_path": tmp_path / "provider-spend.sqlite3",
        "transport": transport,
        "environ": {"GEMINI_API_KEY": "test-only"},
        "retry_backoff_seconds": 0.0,
    }
    arguments.update(overrides)
    return authenticate_disclosure_model_review(**arguments)  # type: ignore[arg-type]


def test_authenticated_review_journals_before_parse_and_projects_by_capability(
    tmp_path: Path,
) -> None:
    capability = _authenticate(tmp_path)

    public = public_disclosure_model_review_record(capability)
    private = private_disclosure_model_review_records(capability)

    assert public["served_model_version"] == "models/gemini-3.5-flash"
    assert public["input_tokens"] == 100
    assert public["output_tokens"] == 20
    assert math.isclose(cast(float, public["actual_cost_usd"]), 0.00033)
    assert public["journal_attempt_ordinal"] == 1
    assert public["authority_attempt_ordinal"] == 1
    assert public["decisions"][0]["status"] == "cleared"  # type: ignore[index]
    serialized_public = json.dumps(public)
    assert "medical record" not in serialized_public
    assert "supporting_excerpt" not in serialized_public
    assert "raw_output" not in serialized_public
    assert "prompt_text" not in serialized_public
    assert private[0]["supporting_excerpt"] == (
        "medical record cited only as a public allegation"
    )

    with sqlite3.connect(tmp_path / "provider-attempts.sqlite3") as connection:
        row = connection.execute(
            "SELECT status, raw_response_json, normalized_response_json, "
            "input_tokens, output_tokens, actual_cost_usd FROM provider_attempts"
        ).fetchone()
    assert row is not None
    assert row[0] == "settled"
    assert json.loads(row[1])["modelVersion"] == "models/gemini-3.5-flash"
    assert json.loads(row[2])["raw_output"].startswith("{")
    assert row[3:5] == (100, 20)
    assert math.isclose(cast(float, row[5]), 0.00033)

    with pytest.raises(DisclosureModelReviewAuthorityError, match="capability"):
        public_disclosure_model_review_record(object())


def test_journal_replay_is_adopted_without_a_second_provider_call(
    tmp_path: Path,
) -> None:
    first = _authenticate(tmp_path)

    def unexpected_call(*_args: object) -> dict[str, object]:
        raise AssertionError("provider must not be called during journal adoption")

    replay = _authenticate(tmp_path, transport=unexpected_call)

    assert public_disclosure_model_review_record(replay) == (
        public_disclosure_model_review_record(first)
    )
    assert private_disclosure_model_review_records(replay) == (
        private_disclosure_model_review_records(first)
    )


@pytest.mark.parametrize(
    ("attribute", "substitute"),
    [
        (
            "_REVIEWER_REGISTRY",
            "model_registries/cycle-1-2026-06-30.json",
        ),
        (
            "_EVALUATED_REGISTRY",
            "model_registries/cycle-1-disclosure-reviewer-2026-07-27.json",
        ),
        (
            "_PROVIDER_CYCLE_CAPS",
            "model_registries/cycle-1-disclosure-reviewer-2026-07-27.json",
        ),
    ],
)
def test_frozen_authority_identity_is_verifier_owned(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    attribute: str,
    substitute: str,
) -> None:
    monkeypatch.setattr(authority_module, attribute, ROOT / substitute)

    with pytest.raises(
        DisclosureModelReviewAuthorityError, match="frozen artifact differs"
    ):
        _authenticate(tmp_path)


def test_explicit_source_root_supports_installed_wheel_layout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    installed_root = tmp_path / "installed-authority-data"
    for relative_path in (
        "model_registries/cycle-1-disclosure-reviewer-2026-07-27.json",
        "model_registries/cycle-1-2026-06-30.json",
        "model_registries/cycle-1-target-100-provider-caps-base-2026-07-28.json",
    ):
        destination = installed_root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / relative_path).read_bytes())
    missing = tmp_path / "site-packages-without-repository-data"
    monkeypatch.setattr(authority_module, "_REVIEWER_REGISTRY", missing / "reviewer")
    monkeypatch.setattr(authority_module, "_EVALUATED_REGISTRY", missing / "evaluated")
    monkeypatch.setattr(authority_module, "_PROVIDER_CYCLE_CAPS", missing / "caps")

    capability = _authenticate(tmp_path, source_root=installed_root)

    assert public_disclosure_model_review_record(capability)["decision_count"] == 1


def test_logical_call_identity_separates_input_boundaries() -> None:
    assert authority_module._logical_call_id(
        b"routing-plan-prefix", b"worksheet"
    ) != authority_module._logical_call_id(b"routing-plan", b"-prefixworksheet")


def test_module_exposes_no_direct_capability_issuer() -> None:
    assert not hasattr(authority_module, "_issue_capability")
    assert not hasattr(authority_module, "_issue")
    assert not hasattr(authority_module, "_CAPABILITY_TYPE")
    assert not hasattr(authority_module, "_CAPABILITY_STATES")
    assert not hasattr(authority_module, "_verifier_owned_capability_boundary")


def test_authenticated_review_rejects_wrong_served_version_after_raw_journaling(
    tmp_path: Path,
) -> None:
    payload = _provider_payload("a" * 64)
    payload["modelVersion"] = "models/gemini-3.5-flash-substituted"

    def wrong_version_transport(
        _request: Request, _timeout: float
    ) -> dict[str, object]:
        return payload

    with pytest.raises(Exception, match="served model version"):
        _authenticate(tmp_path, transport=wrong_version_transport)

    with sqlite3.connect(tmp_path / "provider-attempts.sqlite3") as connection:
        row = connection.execute(
            "SELECT status, raw_response_json FROM provider_attempts"
        ).fetchone()
    assert row is not None
    assert row[0] == "ambiguous"
    assert "gemini-3.5-flash-substituted" in row[1]


def test_authenticated_review_never_exceeds_two_transport_attempts(
    tmp_path: Path,
) -> None:
    calls = 0

    def unavailable(_request: Request, _timeout: float) -> dict[str, object]:
        nonlocal calls
        calls += 1
        raise LiveModelProviderError("temporarily unavailable", retryable=True)

    with pytest.raises(LiveModelProviderError, match="temporarily unavailable"):
        _authenticate(tmp_path, transport=unavailable)

    assert calls == 2
    with sqlite3.connect(tmp_path / "provider-attempts.sqlite3") as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM provider_attempts"
        ).fetchone() == (2,)


def test_authenticated_review_rejects_stale_journal_prompt_binding(
    tmp_path: Path,
) -> None:
    _authenticate(tmp_path)
    journal_path = tmp_path / "provider-attempts.sqlite3"
    with sqlite3.connect(journal_path) as connection:
        connection.execute(
            "UPDATE provider_attempts SET prompt_text = ?, prompt_sha256 = ?",
            ("substituted private prompt", "0" * 64),
        )

    with pytest.raises(Exception, match="frozen input changed on replay"):
        _authenticate(tmp_path)


def test_synthetic_local_journal_without_cross_store_authority_cannot_replay(
    tmp_path: Path,
) -> None:
    _authenticate(tmp_path)
    authority_path = tmp_path / "provider-spend.sqlite3"
    authority_path.unlink()

    with pytest.raises(Exception, match="replayable attempt"):
        _authenticate(tmp_path)


def test_capability_consumer_rejects_tampered_cross_store_receipt(
    tmp_path: Path,
) -> None:
    capability = _authenticate(tmp_path)
    with sqlite3.connect(tmp_path / "provider-spend.sqlite3") as connection:
        connection.execute(
            "UPDATE provider_attempts SET response_sha256 = ?",
            ("0" * 64,),
        )

    with pytest.raises(Exception, match="response evidence changed"):
        public_disclosure_model_review_record(capability)


def test_capability_consumer_rejects_tampered_local_raw_response(
    tmp_path: Path,
) -> None:
    capability = _authenticate(tmp_path)
    with sqlite3.connect(tmp_path / "provider-attempts.sqlite3") as connection:
        connection.execute(
            "UPDATE provider_attempts SET raw_response_json = ?",
            (json.dumps({"modelVersion": "models/substituted"}),),
        )

    with pytest.raises(DisclosureModelReviewAuthorityError):
        private_disclosure_model_review_records(capability)


def test_authenticated_review_rejects_noncanonical_semantic_output(
    tmp_path: Path,
) -> None:
    plan, _plan_bytes, _worksheet, _worksheet_bytes, _documents = _inputs()
    document_sha256 = cast(
        str, cast(list[dict[str, object]], plan["documents"])[0]["sha256"]
    )
    payload = _provider_payload(document_sha256)
    candidates = cast(list[dict[str, object]], payload["candidates"])
    content = cast(dict[str, object], candidates[0]["content"])
    parts = cast(list[dict[str, object]], content["parts"])
    semantic = json.loads(cast(str, parts[0]["text"]))
    parts[0]["text"] = json.dumps(semantic, indent=2) + "\n"

    def noncanonical(_request: Request, _timeout: float) -> dict[str, object]:
        return payload

    with pytest.raises(
        DisclosureModelReviewAuthorityError, match="not exact canonical JSON"
    ):
        _authenticate(tmp_path, transport=noncanonical)
