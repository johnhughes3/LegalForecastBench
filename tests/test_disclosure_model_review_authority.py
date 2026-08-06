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
    ProvenanceClearanceError,
    build_authenticated_model_provenance_clearance_records_v3,
    canonical_json_bytes,
    exception_review_worksheet_v3,
)
from legalforecast.labeling.provider_journal import ProviderJournalError
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
replay_authenticated_disclosure_model_review = (
    authority_module.replay_authenticated_disclosure_model_review
)
disclosure_model_review_provider_call_executed = (
    authority_module.disclosure_model_review_provider_call_executed
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
        "supporting_page_number": None,
        "supporting_excerpt": None,
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
    assert private[0]["supporting_page_number"] is None
    assert private[0]["supporting_excerpt"] is None

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
    assert disclosure_model_review_provider_call_executed(first) is True

    def unexpected_call(*_args: object) -> dict[str, object]:
        raise AssertionError("provider must not be called during journal adoption")

    replay = _authenticate(tmp_path, transport=unexpected_call)
    assert disclosure_model_review_provider_call_executed(replay) is False

    assert public_disclosure_model_review_record(replay) == (
        public_disclosure_model_review_record(first)
    )
    assert private_disclosure_model_review_records(replay) == (
        private_disclosure_model_review_records(first)
    )


def test_replay_only_issuer_reconstructs_capability_without_transport(
    tmp_path: Path,
) -> None:
    original = _authenticate(tmp_path)
    plan, plan_bytes, worksheet, worksheet_bytes, documents = _inputs()

    replayed = replay_authenticated_disclosure_model_review(
        routing_plan=plan,
        routing_plan_bytes=plan_bytes,
        worksheet=worksheet,
        worksheet_bytes=worksheet_bytes,
        document_bytes_by_key=documents,
        provider_journal_path=tmp_path / "provider-attempts.sqlite3",
        provider_spend_authority_path=tmp_path / "provider-spend.sqlite3",
    )

    assert public_disclosure_model_review_record(replayed) == (
        public_disclosure_model_review_record(original)
    )
    assert private_disclosure_model_review_records(replayed) == (
        private_disclosure_model_review_records(original)
    )


def test_replay_only_issuer_never_falls_back_to_provider(tmp_path: Path) -> None:
    plan, plan_bytes, worksheet, worksheet_bytes, documents = _inputs()

    with pytest.raises(
        DisclosureModelReviewAuthorityError,
        match=r"provider call forbidden|journal",
    ):
        replay_authenticated_disclosure_model_review(
            routing_plan=plan,
            routing_plan_bytes=plan_bytes,
            worksheet=worksheet,
            worksheet_bytes=worksheet_bytes,
            document_bytes_by_key=documents,
            provider_journal_path=tmp_path / "missing-journal.sqlite3",
            provider_spend_authority_path=tmp_path / "missing-spend.sqlite3",
        )
    assert not (tmp_path / "missing-journal.sqlite3").exists()
    assert not (tmp_path / "missing-spend.sqlite3").exists()


def test_replay_only_issuer_rejects_symlinked_provider_state(tmp_path: Path) -> None:
    _authenticate(tmp_path)
    plan, plan_bytes, worksheet, worksheet_bytes, documents = _inputs()
    journal_link = tmp_path / "journal-link.sqlite3"
    journal_link.symlink_to(tmp_path / "provider-attempts.sqlite3")

    with pytest.raises(
        DisclosureModelReviewAuthorityError, match="no replayable store"
    ):
        replay_authenticated_disclosure_model_review(
            routing_plan=plan,
            routing_plan_bytes=plan_bytes,
            worksheet=worksheet,
            worksheet_bytes=worksheet_bytes,
            document_bytes_by_key=documents,
            provider_journal_path=journal_link,
            provider_spend_authority_path=tmp_path / "provider-spend.sqlite3",
        )


def test_v3_clearance_consumes_capability_not_public_mapping(tmp_path: Path) -> None:
    capability = _authenticate(tmp_path)
    plan, plan_bytes, _, _, _ = _inputs()
    routing_sha256 = hashlib.sha256(plan_bytes).hexdigest()

    records = build_authenticated_model_provenance_clearance_records_v3(
        plan,
        model_review_capability=capability,
        routing_plan_sha256=routing_sha256,
    )

    assert len(records) == 1
    assert records[0].status == "cleared"
    assert records[0].clearance_basis == "authenticated_model_exception_review"
    with pytest.raises(ProvenanceClearanceError, match="capability"):
        build_authenticated_model_provenance_clearance_records_v3(
            plan,
            model_review_capability=public_disclosure_model_review_record(capability),
            routing_plan_sha256=routing_sha256,
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


def test_authenticated_review_accepts_strict_noncanonical_semantic_output(
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

    capability = _authenticate(tmp_path, transport=noncanonical)

    assert disclosure_model_review_provider_call_executed(capability) is True
    [private_record] = private_disclosure_model_review_records(capability)
    assert (
        private_record["batch_response_sha256"]
        == hashlib.sha256(cast(str, parts[0]["text"]).encode()).hexdigest()
    )


def test_authenticated_review_retries_after_reconstruction_failure(
    tmp_path: Path,
) -> None:
    plan, _plan_bytes, _worksheet, _worksheet_bytes, _documents = _inputs()
    document_sha256 = cast(
        str, cast(list[dict[str, object]], plan["documents"])[0]["sha256"]
    )
    invalid_payload = _provider_payload(document_sha256)
    invalid_candidates = cast(list[dict[str, object]], invalid_payload["candidates"])
    invalid_content = cast(dict[str, object], invalid_candidates[0]["content"])
    invalid_parts = cast(list[dict[str, object]], invalid_content["parts"])
    semantic = json.loads(cast(str, invalid_parts[0]["text"]))
    cast(list[dict[str, object]], semantic["items"])[0]["decision"] = "invalid"
    invalid_parts[0]["text"] = (
        json.dumps(semantic, sort_keys=True, separators=(",", ":")) + "\n"
    )
    valid_payload = _provider_payload(document_sha256)
    calls = 0

    def improving_transport(_request: Request, _timeout: float) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return invalid_payload if calls == 1 else valid_payload

    with pytest.raises(Exception, match="decision is invalid"):
        _authenticate(tmp_path, transport=improving_transport)

    capability = _authenticate(tmp_path, transport=improving_transport)

    assert calls == 2
    assert disclosure_model_review_provider_call_executed(capability) is True
    public = public_disclosure_model_review_record(capability)
    assert public["journal_attempt_ordinal"] == 2
    assert public["authority_attempt_ordinal"] == 2

    def unexpected_call(*_args: object) -> dict[str, object]:
        raise AssertionError("settled retry must replay without another provider call")

    replayed = _authenticate(tmp_path, transport=unexpected_call)
    assert disclosure_model_review_provider_call_executed(replayed) is False
    assert public_disclosure_model_review_record(replayed) == public
    with sqlite3.connect(tmp_path / "provider-attempts.sqlite3") as connection:
        rows = connection.execute(
            "SELECT attempt_ordinal, status FROM provider_attempts "
            "ORDER BY attempt_ordinal"
        ).fetchall()
    assert rows == [(1, "reconstruction_failed"), (2, "settled")]


def test_reconstruction_failures_never_exceed_frozen_attempt_limit(
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
    cast(list[dict[str, object]], semantic["items"])[0]["decision"] = "invalid"
    parts[0]["text"] = (
        json.dumps(semantic, sort_keys=True, separators=(",", ":")) + "\n"
    )
    calls = 0

    def invalid_transport(_request: Request, _timeout: float) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return payload

    for _ in range(2):
        with pytest.raises(Exception, match="decision is invalid"):
            _authenticate(tmp_path, transport=invalid_transport)

    with pytest.raises(ProviderJournalError, match="attempt limit is exhausted"):
        _authenticate(tmp_path, transport=invalid_transport)

    assert calls == 2
    with sqlite3.connect(tmp_path / "provider-attempts.sqlite3") as connection:
        rows = connection.execute(
            "SELECT attempt_ordinal, status FROM provider_attempts "
            "ORDER BY attempt_ordinal"
        ).fetchall()
    assert rows == [(1, "reconstruction_failed"), (2, "reconstruction_failed")]


def test_corrected_reconstruction_recovers_latest_response_without_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_validator = authority_module._validate_semantic

    def legacy_rejection(*_args: object, **_kwargs: object) -> object:
        raise DisclosureModelReviewAuthorityError(
            "provider semantic output is not exact canonical JSON"
        )

    monkeypatch.setattr(authority_module, "_validate_semantic", legacy_rejection)
    calls = 0

    def transport(_request: Request, _timeout: float) -> dict[str, object]:
        nonlocal calls
        calls += 1
        plan, _plan_bytes, _worksheet, _worksheet_bytes, _documents = _inputs()
        return _provider_payload(
            cast(str, cast(list[dict[str, object]], plan["documents"])[0]["sha256"])
        )

    for _ in range(2):
        with pytest.raises(
            DisclosureModelReviewAuthorityError, match="not exact canonical JSON"
        ):
            _authenticate(tmp_path, transport=transport)
    assert calls == 2

    monkeypatch.setattr(authority_module, "_validate_semantic", original_validator)

    plan, plan_bytes, worksheet, worksheet_bytes, documents = _inputs()
    capability = replay_authenticated_disclosure_model_review(
        routing_plan=plan,
        routing_plan_bytes=plan_bytes,
        worksheet=worksheet,
        worksheet_bytes=worksheet_bytes,
        document_bytes_by_key=documents,
        provider_journal_path=tmp_path / "provider-attempts.sqlite3",
        provider_spend_authority_path=tmp_path / "provider-spend.sqlite3",
    )

    assert calls == 2
    assert disclosure_model_review_provider_call_executed(capability) is False
    assert (
        public_disclosure_model_review_record(capability)["journal_attempt_ordinal"]
        == 2
    )
    with sqlite3.connect(tmp_path / "provider-attempts.sqlite3") as connection:
        rows = connection.execute(
            "SELECT attempt_ordinal, status, failure_message "
            "FROM provider_attempts ORDER BY attempt_ordinal"
        ).fetchall()
    assert rows == [
        (
            1,
            "reconstruction_failed",
            "provider semantic output is not exact canonical JSON",
        ),
        (2, "settled", "provider semantic output is not exact canonical JSON"),
    ]


def test_provider_free_recovery_accepts_exact_prompt_schema_echo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_validator = authority_module._validate_semantic
    plan, plan_bytes, worksheet, worksheet_bytes, documents = _inputs()
    document_sha256 = cast(
        str, cast(list[dict[str, object]], plan["documents"])[0]["sha256"]
    )
    payload = _provider_payload(document_sha256)
    candidates = cast(list[dict[str, object]], payload["candidates"])
    content = cast(dict[str, object], candidates[0]["content"])
    parts = cast(list[dict[str, object]], content["parts"])
    semantic = json.loads(cast(str, parts[0]["text"]))
    semantic["schema_version"] = "legalforecast.disclosure_model_review_batch_prompt.v1"
    semantic["response_schema_version"] = (
        "legalforecast.disclosure_model_review_batch_response.v1"
    )
    [item] = cast(list[dict[str, object]], semantic["items"])
    item["decision"] = "quarantined"
    item["sensitive_content"] = "present"
    item["supporting_page_number"] = 1
    item["supporting_excerpt"] = "medical  record cited only as a public allegation"
    raw_output = json.dumps(semantic, indent=2) + "\n"
    parts[0]["text"] = raw_output

    def legacy_rejection(*_args: object, **_kwargs: object) -> object:
        raise DisclosureModelReviewAuthorityError(
            "provider semantic output is not exact canonical JSON"
        )

    monkeypatch.setattr(authority_module, "_validate_semantic", legacy_rejection)
    for _ in range(2):
        with pytest.raises(DisclosureModelReviewAuthorityError):
            _authenticate(tmp_path, transport=lambda *_args: payload)
    monkeypatch.setattr(authority_module, "_validate_semantic", original_validator)

    capability = replay_authenticated_disclosure_model_review(
        routing_plan=plan,
        routing_plan_bytes=plan_bytes,
        worksheet=worksheet,
        worksheet_bytes=worksheet_bytes,
        document_bytes_by_key=documents,
        provider_journal_path=tmp_path / "provider-attempts.sqlite3",
        provider_spend_authority_path=tmp_path / "provider-spend.sqlite3",
    )

    assert disclosure_model_review_provider_call_executed(capability) is False
    [private_record] = private_disclosure_model_review_records(capability)
    assert private_record["status"] == "quarantined"
    assert private_record["supporting_page_number"] is None
    assert private_record["supporting_excerpt"] is None
    assert (
        private_record["schema_version"]
        == "legalforecast.disclosure_model_review_private_review.v2"
    )
    assert (
        private_record["batch_response_sha256"]
        == hashlib.sha256(raw_output.encode()).hexdigest()
    )
    with sqlite3.connect(tmp_path / "provider-attempts.sqlite3") as connection:
        rows = connection.execute(
            "SELECT attempt_ordinal, status FROM provider_attempts "
            "ORDER BY attempt_ordinal"
        ).fetchall()
    assert rows == [(1, "reconstruction_failed"), (2, "settled")]


def test_provider_free_recovery_accepts_attempt_one_redundant_response_schema_echo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_validator = authority_module._validate_semantic
    plan, _plan_bytes, _worksheet, _worksheet_bytes, _documents = _inputs()
    document_sha256 = cast(
        str, cast(list[dict[str, object]], plan["documents"])[0]["sha256"]
    )
    payload = _provider_payload(document_sha256)
    candidates = cast(list[dict[str, object]], payload["candidates"])
    content = cast(dict[str, object], candidates[0]["content"])
    parts = cast(list[dict[str, object]], content["parts"])
    semantic = json.loads(cast(str, parts[0]["text"]))
    semantic["response_schema_version"] = (
        "legalforecast.disclosure_model_review_batch_response.v1"
    )
    raw_output = json.dumps(semantic, indent=2) + "\n"
    parts[0]["text"] = raw_output
    calls = 0

    def transport(_request: Request, _timeout: float) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return payload

    def legacy_rejection(*_args: object, **_kwargs: object) -> object:
        raise DisclosureModelReviewAuthorityError(
            "legacy redundant response schema rejection"
        )

    monkeypatch.setattr(authority_module, "_validate_semantic", legacy_rejection)
    with pytest.raises(
        DisclosureModelReviewAuthorityError,
        match="legacy redundant response schema rejection",
    ):
        _authenticate(tmp_path, transport=transport)
    assert calls == 1

    monkeypatch.setattr(authority_module, "_validate_semantic", original_validator)
    capability = _authenticate(tmp_path, transport=transport)

    assert calls == 1
    assert disclosure_model_review_provider_call_executed(capability) is False
    assert (
        public_disclosure_model_review_record(capability)["journal_attempt_ordinal"]
        == 1
    )
    [private_record] = private_disclosure_model_review_records(capability)
    assert (
        private_record["batch_response_sha256"]
        == hashlib.sha256(raw_output.encode()).hexdigest()
    )
    with sqlite3.connect(tmp_path / "provider-attempts.sqlite3") as connection:
        rows = connection.execute(
            "SELECT attempt_ordinal, status FROM provider_attempts "
            "ORDER BY attempt_ordinal"
        ).fetchall()
    assert rows == [(1, "settled")]


def test_provider_free_recovery_uses_older_valid_failed_response(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_validator = authority_module._validate_semantic
    plan, plan_bytes, worksheet, worksheet_bytes, documents = _inputs()
    document_sha256 = cast(
        str, cast(list[dict[str, object]], plan["documents"])[0]["sha256"]
    )
    valid_payload = _provider_payload(document_sha256)
    invalid_payload = _provider_payload(document_sha256)
    candidates = cast(list[dict[str, object]], invalid_payload["candidates"])
    content = cast(dict[str, object], candidates[0]["content"])
    parts = cast(list[dict[str, object]], content["parts"])
    semantic = json.loads(cast(str, parts[0]["text"]))
    cast(list[dict[str, object]], semantic["items"])[0]["decision"] = "invalid"
    parts[0]["text"] = (
        json.dumps(semantic, sort_keys=True, separators=(",", ":")) + "\n"
    )

    def legacy_rejection(*_args: object, **_kwargs: object) -> object:
        raise DisclosureModelReviewAuthorityError("legacy canonical rejection")

    monkeypatch.setattr(authority_module, "_validate_semantic", legacy_rejection)
    with pytest.raises(DisclosureModelReviewAuthorityError):
        _authenticate(tmp_path, transport=lambda *_args: valid_payload)

    validation_calls = 0

    def reject_recovery_then_validate(*args: object, **kwargs: object) -> object:
        nonlocal validation_calls
        validation_calls += 1
        if validation_calls == 1:
            raise DisclosureModelReviewAuthorityError("defer old response")
        return original_validator(*args, **kwargs)  # type: ignore[no-any-return]

    monkeypatch.setattr(
        authority_module, "_validate_semantic", reject_recovery_then_validate
    )
    with pytest.raises(Exception, match="decision is invalid"):
        _authenticate(tmp_path, transport=lambda *_args: invalid_payload)

    monkeypatch.setattr(authority_module, "_validate_semantic", original_validator)
    capability = replay_authenticated_disclosure_model_review(
        routing_plan=plan,
        routing_plan_bytes=plan_bytes,
        worksheet=worksheet,
        worksheet_bytes=worksheet_bytes,
        document_bytes_by_key=documents,
        provider_journal_path=tmp_path / "provider-attempts.sqlite3",
        provider_spend_authority_path=tmp_path / "provider-spend.sqlite3",
    )

    assert (
        public_disclosure_model_review_record(capability)["journal_attempt_ordinal"]
        == 1
    )
    with sqlite3.connect(tmp_path / "provider-attempts.sqlite3") as connection:
        rows = connection.execute(
            "SELECT attempt_ordinal, status FROM provider_attempts "
            "ORDER BY attempt_ordinal"
        ).fetchall()
    assert rows == [(1, "settled"), (2, "reconstruction_failed")]


def test_provider_free_recovery_rejects_tampered_served_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_validator = authority_module._validate_semantic

    def legacy_rejection(*_args: object, **_kwargs: object) -> object:
        raise DisclosureModelReviewAuthorityError("legacy canonical rejection")

    monkeypatch.setattr(authority_module, "_validate_semantic", legacy_rejection)
    with pytest.raises(DisclosureModelReviewAuthorityError):
        _authenticate(tmp_path)
    monkeypatch.setattr(authority_module, "_validate_semantic", original_validator)

    journal_path = tmp_path / "provider-attempts.sqlite3"
    with sqlite3.connect(journal_path) as connection:
        [(raw_response_json,)] = connection.execute(
            "SELECT raw_response_json FROM provider_attempts"
        ).fetchall()
        raw_response = json.loads(raw_response_json)
        raw_response["modelVersion"] = "models/substituted"
        connection.execute(
            "UPDATE provider_attempts SET raw_response_json = ?",
            (json.dumps(raw_response, sort_keys=True, separators=(",", ":")),),
        )

    plan, plan_bytes, worksheet, worksheet_bytes, documents = _inputs()
    with pytest.raises(
        DisclosureModelReviewAuthorityError,
        match="recovered provider envelope is invalid",
    ):
        replay_authenticated_disclosure_model_review(
            routing_plan=plan,
            routing_plan_bytes=plan_bytes,
            worksheet=worksheet,
            worksheet_bytes=worksheet_bytes,
            document_bytes_by_key=documents,
            provider_journal_path=journal_path,
            provider_spend_authority_path=tmp_path / "provider-spend.sqlite3",
        )


def test_provider_free_recovery_reuses_exact_live_envelope_parser(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_validator = authority_module._validate_semantic
    plan, plan_bytes, worksheet, worksheet_bytes, documents = _inputs()
    document_sha256 = cast(
        str, cast(list[dict[str, object]], plan["documents"])[0]["sha256"]
    )
    payload = _provider_payload(document_sha256)
    payload["modelVersion"] = " models/GEMINI-3.5-FLASH "
    candidates = cast(list[dict[str, object]], payload["candidates"])
    content = cast(dict[str, object], candidates[0]["content"])
    parts = cast(list[object], content["parts"])
    parts.insert(0, "provider metadata ignored by the live text extractor")

    def legacy_rejection(*_args: object, **_kwargs: object) -> object:
        raise DisclosureModelReviewAuthorityError("legacy canonical rejection")

    monkeypatch.setattr(authority_module, "_validate_semantic", legacy_rejection)
    with pytest.raises(DisclosureModelReviewAuthorityError):
        _authenticate(tmp_path, transport=lambda *_args: payload)
    monkeypatch.setattr(authority_module, "_validate_semantic", original_validator)

    capability = replay_authenticated_disclosure_model_review(
        routing_plan=plan,
        routing_plan_bytes=plan_bytes,
        worksheet=worksheet,
        worksheet_bytes=worksheet_bytes,
        document_bytes_by_key=documents,
        provider_journal_path=tmp_path / "provider-attempts.sqlite3",
        provider_spend_authority_path=tmp_path / "provider-spend.sqlite3",
    )

    assert (
        public_disclosure_model_review_record(capability)["served_model_version"]
        == "models/GEMINI-3.5-FLASH"
    )


def test_provider_free_recovery_does_not_retry_still_invalid_response(
    tmp_path: Path,
) -> None:
    plan, plan_bytes, worksheet, worksheet_bytes, documents = _inputs()
    document_sha256 = cast(
        str, cast(list[dict[str, object]], plan["documents"])[0]["sha256"]
    )
    payload = _provider_payload(document_sha256)
    candidates = cast(list[dict[str, object]], payload["candidates"])
    content = cast(dict[str, object], candidates[0]["content"])
    parts = cast(list[dict[str, object]], content["parts"])
    semantic = json.loads(cast(str, parts[0]["text"]))
    cast(list[dict[str, object]], semantic["items"])[0]["decision"] = "invalid"
    parts[0]["text"] = (
        json.dumps(semantic, sort_keys=True, separators=(",", ":")) + "\n"
    )

    def invalid_transport(_request: Request, _timeout: float) -> dict[str, object]:
        return payload

    with pytest.raises(Exception, match="decision is invalid"):
        _authenticate(tmp_path, transport=invalid_transport)

    with pytest.raises(
        DisclosureModelReviewAuthorityError,
        match="no provider-free validated response",
    ):
        replay_authenticated_disclosure_model_review(
            routing_plan=plan,
            routing_plan_bytes=plan_bytes,
            worksheet=worksheet,
            worksheet_bytes=worksheet_bytes,
            document_bytes_by_key=documents,
            provider_journal_path=tmp_path / "provider-attempts.sqlite3",
            provider_spend_authority_path=tmp_path / "provider-spend.sqlite3",
        )

    with sqlite3.connect(tmp_path / "provider-attempts.sqlite3") as connection:
        rows = connection.execute(
            "SELECT attempt_ordinal, status FROM provider_attempts"
        ).fetchall()
    assert rows == [(1, "reconstruction_failed")]


@pytest.mark.parametrize(
    "raw_output",
    [
        '{"schema_version":"legalforecast.disclosure_model_review_batch_response.v1",'
        '"schema_version":"legalforecast.disclosure_model_review_batch_response.v1"}',
        '{"document_count":NaN,"items":[],"model_id":"gemini-3.5-flash",'
        '"model_version":"gemini-3.5-flash",'
        '"schema_version":"legalforecast.disclosure_model_review_batch_response.v1"}',
        "{} trailing",
        "{}",
    ],
    ids=("duplicate-key", "nonfinite", "trailing-data", "schema-invalid"),
)
def test_semantic_recovery_rejects_unsafe_json_domains(
    tmp_path: Path, raw_output: str
) -> None:
    plan, _plan_bytes, _worksheet, _worksheet_bytes, _documents = _inputs()
    payload = _provider_payload(
        cast(str, cast(list[dict[str, object]], plan["documents"])[0]["sha256"])
    )
    candidates = cast(list[dict[str, object]], payload["candidates"])
    content = cast(dict[str, object], candidates[0]["content"])
    parts = cast(list[dict[str, object]], content["parts"])
    parts[0]["text"] = raw_output

    def invalid_transport(_request: Request, _timeout: float) -> dict[str, object]:
        return payload

    with pytest.raises(ValueError):
        _authenticate(tmp_path, transport=invalid_transport)
