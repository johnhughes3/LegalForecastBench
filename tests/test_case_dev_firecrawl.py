from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from hashlib import sha256

import pytest
from legalforecast.ingestion.case_dev_client import (
    CaseDevAuthError,
    CaseDevClient,
    CaseDevFixtureTransport,
    RecordedCaseDevResponse,
)
from legalforecast.ingestion.case_dev_config import CaseDevConfig
from legalforecast.ingestion.case_dev_firecrawl import (
    CaseDevFirecrawlBatchError,
    CaseDevFirecrawlCandidate,
    acquire_case_dev_firecrawl_html,
    screen_case_dev_firecrawl_successes,
)
from legalforecast.ingestion.firecrawl_source import (
    FirecrawlPaymentRequiredError,
    FirecrawlResponseError,
)
from legalforecast.selection.exclusion_ledger import merge_exclusion_ledger_records


@dataclass
class _FakeFirecrawlSource:
    html_by_docket_id: dict[str, str] = field(default_factory=dict)
    error_by_docket_id: dict[str, Exception] = field(default_factory=dict)
    requests: list[tuple[str, str]] = field(default_factory=list)

    def fetch(self, *, docket_id: str, source_url: str) -> str:
        self.requests.append((docket_id, source_url))
        error = self.error_by_docket_id.get(docket_id)
        if error is not None:
            raise error
        return self.html_by_docket_id[docket_id]


def test_bridge_dedupes_before_limit_and_writes_html_in_input_order(tmp_path) -> None:
    client, transport = _client(
        _lookup("case-a", courtlistener_docket_id="101"),
        _lookup("case-b", courtlistener_docket_id="202"),
    )
    source = _FakeFirecrawlSource(
        html_by_docket_id={"101": _docket_html("A"), "202": _docket_html("B")}
    )

    result = acquire_case_dev_firecrawl_html(
        client=client,
        source=source,
        candidates=(
            {"case_id": "case-a", "candidate_id": "candidate-a"},
            {"case_id": "case-a", "candidate_id": "duplicate-a"},
            CaseDevFirecrawlCandidate(case_id="case-b", candidate_id=None),
            {"case_id": "case-c", "candidate_id": "over-limit"},
        ),
        raw_html_directory=tmp_path,
        max_candidates=2,
    )

    assert [item.case_id for item in result.successes] == ["case-a", "case-b"]
    assert [item.candidate_id for item in result.successes] == ["candidate-a", None]
    assert [item.reason for item in result.exclusions] == ["candidate_limit_deferred"]
    assert result.unique_candidate_count == 3
    assert result.processed_candidate_count == 2
    assert result.scrape_count == 2
    assert (tmp_path / "101.html").read_text(encoding="utf-8") == _docket_html("A")
    assert (tmp_path / "202.html").read_text(encoding="utf-8") == _docket_html("B")
    assert [request[2]["docketId"] for request in transport.requests] == [
        "case-a",
        "case-b",
    ]
    assert [request[0] for request in source.requests] == ["101", "202"]
    assert result.successes[0].raw_html_sha256 == (
        f"sha256:{sha256(_docket_html('A').encode()).hexdigest()}"
    )
    assert result.successes[0].raw_html_bytes == len(_docket_html("A").encode())


def test_bridge_uses_self_contained_discovery_metadata_without_lookup(tmp_path) -> None:
    client, transport = _client()
    source = _FakeFirecrawlSource(html_by_docket_id={"101": _docket_html("A")})

    result = acquire_case_dev_firecrawl_html(
        client=client,
        source=source,
        candidates=(
            {
                "case_id": "case-a",
                "candidate_id": "case-a",
                "courtlistener_url": (
                    "https://www.courtlistener.com/docket/101/fixture-v-example/"
                ),
                "courtlistener_docket_id": "101",
                "case_metadata": {
                    "id": "case-a",
                    "caseName": "Fixture v. Example",
                    "courtId": "nysd",
                    "court": "nysd",
                    "docketNumber": "1:26-cv-00001",
                },
            },
        ),
        raw_html_directory=tmp_path,
        max_candidates=1,
    )

    assert [item.case_id for item in result.successes] == ["case-a"]
    assert transport.requests == []
    assert source.requests == [
        (
            "101",
            "https://www.courtlistener.com/docket/101/fixture-v-example/",
        )
    ]


def test_bridge_ledgers_missing_or_malformed_url_without_scraping(tmp_path) -> None:
    client, _ = _client(
        _lookup("unknown", include_source_url=False),
        _lookup("../escape", include_source_url=False),
    )
    source = _FakeFirecrawlSource()

    result = acquire_case_dev_firecrawl_html(
        client=client,
        source=source,
        candidates=(
            {"case_id": "unknown", "candidate_id": "missing"},
            {"case_id": "../escape", "candidate_id": "malformed"},
        ),
        raw_html_directory=tmp_path,
        max_candidates=2,
    )

    assert result.successes == ()
    assert [item.reason for item in result.exclusions] == [
        "courtlistener_url_missing",
        "courtlistener_url_malformed",
    ]
    assert source.requests == []
    assert list(tmp_path.iterdir()) == []
    assert not (tmp_path.parent / "escape.html").exists()


def test_bridge_metadata_and_restriction_gates_precede_firecrawl(tmp_path) -> None:
    client, _ = _client(
        _lookup(
            "case-state",
            courtlistener_docket_id="101",
            extra_payload={"courtId": "ca9"},
        ),
        _lookup(
            "case-sealed",
            courtlistener_docket_id="202",
            extra_payload={"privacyMetadata": {"isSealed": True}},
        ),
    )
    source = _FakeFirecrawlSource()

    result = acquire_case_dev_firecrawl_html(
        client=client,
        source=source,
        candidates=({"case_id": "case-state"}, {"case_id": "case-sealed"}),
        raw_html_directory=tmp_path,
        max_candidates=2,
    )

    assert result.successes == ()
    assert [item.reason for item in result.exclusions] == [
        "not_federal_district_court",
        "restricted_case_metadata",
    ]
    assert result.scrape_count == 0
    assert source.requests == []


def test_bridge_rejects_case_dev_identity_mismatch_before_firecrawl(tmp_path) -> None:
    mismatched = RecordedCaseDevResponse(
        method="POST",
        path="/legal/v1/docket",
        params={"type": "lookup", "docketId": "case-a"},
        status_code=200,
        payload={
            "id": "different-case",
            "caseName": "Fixture v. Example",
            "courtId": "nysd",
            "docketNumber": "1:26-cv-00001",
            "url": "https://www.courtlistener.com/api/rest/v4/dockets/101/",
        },
    )
    client, _ = _client(mismatched)
    source = _FakeFirecrawlSource()

    result = acquire_case_dev_firecrawl_html(
        client=client,
        source=source,
        candidates=({"case_id": "case-a", "candidate_id": "candidate-a"},),
        raw_html_directory=tmp_path,
        max_candidates=1,
    )

    [exclusion] = result.exclusions
    assert exclusion.reason == "case_dev_identity_mismatch"
    assert exclusion.to_record()["stage"] == "discovery"
    [ledger_entry] = merge_exclusion_ledger_records([exclusion.to_record()]).entries
    assert ledger_entry.candidate_id == "candidate-a"
    assert ledger_entry.case_id == "case-a"
    assert source.requests == []
    assert result.scrape_count == 0


def test_bridge_never_overwrites_an_existing_docket_file(tmp_path) -> None:
    destination = tmp_path / "101.html"
    destination.write_text("preserve me", encoding="utf-8")
    client, _ = _client(_lookup("case-a", courtlistener_docket_id="101"))
    source = _FakeFirecrawlSource(html_by_docket_id={"101": "replacement"})

    result = acquire_case_dev_firecrawl_html(
        client=client,
        source=source,
        candidates=({"case_id": "case-a"},),
        raw_html_directory=tmp_path,
        max_candidates=1,
    )

    assert result.successes == ()
    assert [item.reason for item in result.exclusions] == ["raw_html_path_exists"]
    assert destination.read_text(encoding="utf-8") == "preserve me"
    assert list(tmp_path.iterdir()) == [destination]


def test_bridge_adopts_valid_existing_html_only_with_matching_digest(tmp_path) -> None:
    raw_html = _docket_html("A")
    destination = tmp_path / "101.html"
    destination.write_text(raw_html, encoding="utf-8")
    expected_digest = f"sha256:{sha256(raw_html.encode()).hexdigest()}"
    client, transport = _client()
    source = _FakeFirecrawlSource()

    result = acquire_case_dev_firecrawl_html(
        client=client,
        source=source,
        candidates=(
            {
                "case_id": "case-a",
                "courtlistener_url": (
                    "https://www.courtlistener.com/docket/101/fixture-v-example/"
                ),
                "courtlistener_docket_id": "101",
                "raw_html_sha256": expected_digest,
                "case_metadata": {
                    "id": "case-a",
                    "caseName": "Fixture v. Example",
                    "courtId": "nysd",
                    "docketNumber": "1:26-cv-00001",
                },
            },
        ),
        raw_html_directory=tmp_path,
        max_candidates=1,
    )

    assert [item.raw_html_sha256 for item in result.successes] == [expected_digest]
    assert result.scrape_count == 0
    assert transport.requests == []
    assert source.requests == []


def test_bridge_rejects_conflicting_existing_html_hash(tmp_path) -> None:
    destination = tmp_path / "101.html"
    destination.write_text(_docket_html("old"), encoding="utf-8")
    client, _ = _client()

    result = acquire_case_dev_firecrawl_html(
        client=client,
        source=_FakeFirecrawlSource(),
        candidates=(
            {
                "case_id": "case-a",
                "courtlistener_url": (
                    "https://www.courtlistener.com/docket/101/fixture-v-example/"
                ),
                "courtlistener_docket_id": "101",
                "raw_html_sha256": f"sha256:{'0' * 64}",
                "case_metadata": {
                    "id": "case-a",
                    "caseName": "Fixture v. Example",
                    "courtId": "nysd",
                    "docketNumber": "1:26-cv-00001",
                },
            },
        ),
        raw_html_directory=tmp_path,
        max_candidates=1,
    )

    assert [item.reason for item in result.exclusions] == ["raw_html_hash_conflict"]
    assert destination.read_text(encoding="utf-8") == _docket_html("old")


def test_bridge_ledgers_nonfatal_provider_response_without_error_text(tmp_path) -> None:
    client, _ = _client(_lookup("case-a", courtlistener_docket_id="101"))
    source = _FakeFirecrawlSource(
        error_by_docket_id={
            "101": FirecrawlResponseError("secret-bearing upstream body")
        }
    )

    result = acquire_case_dev_firecrawl_html(
        client=client,
        source=source,
        candidates=({"case_id": "case-a", "candidate_id": "candidate-a"},),
        raw_html_directory=tmp_path,
        max_candidates=1,
    )

    [exclusion] = result.exclusions
    assert exclusion.reason == "firecrawl_response_invalid"
    assert "secret" not in exclusion.reason
    assert exclusion.source_url is not None
    assert exclusion.docket_id == "101"


def test_bridge_ledgers_malformed_case_dev_response_and_continues(tmp_path) -> None:
    malformed = RecordedCaseDevResponse(
        method="POST",
        path="/legal/v1/docket",
        params={"type": "lookup", "docketId": "case-a"},
        status_code=200,
        payload={"id": "case-a"},
    )
    client, _ = _client(
        malformed,
        _lookup("case-b", courtlistener_docket_id="202"),
    )
    source = _FakeFirecrawlSource(html_by_docket_id={"202": _docket_html("B")})

    result = acquire_case_dev_firecrawl_html(
        client=client,
        source=source,
        candidates=({"case_id": "case-a"}, {"case_id": "case-b"}),
        raw_html_directory=tmp_path,
        max_candidates=2,
    )

    assert [item.reason for item in result.exclusions] == ["case_dev_response_invalid"]
    assert [item.case_id for item in result.successes] == ["case-b"]
    assert [request[0] for request in source.requests] == ["202"]


def test_bridge_propagates_fatal_firecrawl_failures_and_stops(tmp_path) -> None:
    client, _ = _client(
        _lookup("case-a", courtlistener_docket_id="101"),
        _lookup("case-b", courtlistener_docket_id="202"),
    )
    source = _FakeFirecrawlSource(
        html_by_docket_id={"202": _docket_html("B")},
        error_by_docket_id={"101": FirecrawlPaymentRequiredError("credit details")},
    )

    with pytest.raises(CaseDevFirecrawlBatchError) as raised:
        acquire_case_dev_firecrawl_html(
            client=client,
            source=source,
            candidates=({"case_id": "case-a"}, {"case_id": "case-b"}),
            raw_html_directory=tmp_path,
            max_candidates=2,
        )

    assert isinstance(raised.value.provider_error, FirecrawlPaymentRequiredError)
    assert [item.reason for item in raised.value.partial_result.exclusions] == [
        "firecrawl_provider_blocker",
        "provider_blocker_deferred",
    ]
    assert [request[0] for request in source.requests] == ["101"]
    assert client.request_count == 1


def test_bridge_fatal_error_checkpoints_earlier_successes(tmp_path) -> None:
    client, _ = _client(
        _lookup("case-a", courtlistener_docket_id="101"),
        _lookup("case-b", courtlistener_docket_id="202"),
    )
    source = _FakeFirecrawlSource(
        html_by_docket_id={"101": _docket_html("A")},
        error_by_docket_id={"202": FirecrawlPaymentRequiredError("credit details")},
    )

    with pytest.raises(CaseDevFirecrawlBatchError) as raised:
        acquire_case_dev_firecrawl_html(
            client=client,
            source=source,
            candidates=({"case_id": "case-a"}, {"case_id": "case-b"}),
            raw_html_directory=tmp_path,
            max_candidates=2,
        )

    partial = raised.value.partial_result
    assert [item.case_id for item in partial.successes] == ["case-a"]
    assert [item.reason for item in partial.exclusions] == [
        "firecrawl_provider_blocker"
    ]
    assert partial.processed_candidate_count == 2
    assert partial.scrape_count == 2
    assert (tmp_path / "101.html").read_text(encoding="utf-8") == _docket_html("A")


def test_bridge_ledgers_non_docket_html_without_persisting(tmp_path) -> None:
    client, _ = _client(_lookup("case-a", courtlistener_docket_id="101"))
    source = _FakeFirecrawlSource(html_by_docket_id={"101": "<html>blocked</html>"})

    result = acquire_case_dev_firecrawl_html(
        client=client,
        source=source,
        candidates=({"case_id": "case-a"},),
        raw_html_directory=tmp_path,
        max_candidates=1,
    )

    assert [item.reason for item in result.exclusions] == ["firecrawl_response_invalid"]
    assert list(tmp_path.iterdir()) == []


def test_bridge_propagates_fatal_case_dev_failure_before_scraping(tmp_path) -> None:
    transport = CaseDevFixtureTransport(
        [
            RecordedCaseDevResponse(
                method="POST",
                path="/legal/v1/docket",
                params={"type": "lookup", "docketId": "case-a"},
                status_code=401,
                payload={"error": "bad token"},
            )
        ]
    )
    client = CaseDevClient(config=_config(), transport=transport, max_retries=0)
    source = _FakeFirecrawlSource()

    with pytest.raises(CaseDevFirecrawlBatchError) as raised:
        acquire_case_dev_firecrawl_html(
            client=client,
            source=source,
            candidates=({"case_id": "case-a"},),
            raw_html_directory=tmp_path,
            max_candidates=1,
        )

    assert isinstance(raised.value.provider_error, CaseDevAuthError)
    assert [item.reason for item in raised.value.partial_result.exclusions] == [
        "case_dev_provider_blocker"
    ]
    assert source.requests == []


def test_screen_recovers_source_bound_bankruptcy_adversary_from_html(tmp_path) -> None:
    raw_html = _strict_adversary_html(adversary_number="26-01028")
    (tmp_path / "101.html").write_text(raw_html, encoding="utf-8")

    result = screen_case_dev_firecrawl_successes(
        successes=(
            _firecrawl_success(
                docket_number="26-01028",
                case_name="Debtor LLC",
            ),
        ),
        raw_html_directory=tmp_path,
        decision_filed_on_or_after=date(2026, 6, 30),
    )

    assert len(result.screened_cases) == 1
    assert result.exclusions == ()
    assert (
        result.screened_cases[0]["candidate"]["metadata"]["case_type_stratum"]
        == "bankruptcy_adversary"
    )


def test_screen_does_not_promote_parent_bankruptcy_docket_from_child_adversary(
    tmp_path,
) -> None:
    raw_html = _strict_adversary_html(adversary_number="26-01028")
    (tmp_path / "101.html").write_text(raw_html, encoding="utf-8")

    result = screen_case_dev_firecrawl_successes(
        successes=(
            _firecrawl_success(
                docket_number="26-50001",
                case_name="In re Debtor LLC",
            ),
        ),
        raw_html_directory=tmp_path,
        decision_filed_on_or_after=date(2026, 6, 30),
    )

    assert result.screened_cases == ()
    assert [item.reason for item in result.exclusions] == ["bankruptcy_court"]


def test_screen_does_not_recover_bankruptcy_metadata_with_other_exclusions(
    tmp_path,
) -> None:
    raw_html = _strict_adversary_html(adversary_number="26-01028")
    (tmp_path / "101.html").write_text(raw_html, encoding="utf-8")

    result = screen_case_dev_firecrawl_successes(
        successes=(
            _firecrawl_success(
                docket_number="26-01028",
                case_name="Warden, Immigration Detention Facility",
            ),
        ),
        raw_html_directory=tmp_path,
        decision_filed_on_or_after=date(2026, 6, 30),
    )

    assert result.screened_cases == ()
    assert [item.reason for item in result.exclusions] == ["bankruptcy_court"]
    assert result.exclusions[0].secondary_reasons == (
        "not_civil_cv_docket",
        "habeas_or_immigration_detention_posture",
    )


@pytest.mark.parametrize("max_candidates", [0, -1])
def test_bridge_requires_positive_explicit_candidate_limit(
    tmp_path, max_candidates: int
) -> None:
    client, _ = _client()

    with pytest.raises(ValueError, match="max_candidates must be positive"):
        acquire_case_dev_firecrawl_html(
            client=client,
            source=_FakeFirecrawlSource(),
            candidates=(),
            raw_html_directory=tmp_path,
            max_candidates=max_candidates,
        )


def _config() -> CaseDevConfig:
    return CaseDevConfig(api_key=None, base_url="https://api.case.dev")


def _docket_html(label: str) -> str:
    return f"<html><div id='docket-entry-table'></div>{label}</html>"


def _firecrawl_success(*, docket_number: str, case_name: str) -> dict[str, object]:
    return {
        "case_id": "case-a",
        "source_url": "https://www.courtlistener.com/docket/101/fixture/",
        "docket_id": "101",
        "case_metadata": {
            "case_id": "case-a",
            "court_id": "nysb",
            "docket_number": docket_number,
            "case_name": case_name,
        },
    }


def _strict_adversary_html(*, adversary_number: str) -> str:
    return (
        "<html><head><title>Debtor LLC</title></head><body>"
        '<div id="docket-entry-table">'
        + _screening_entry_html(
            number=1,
            filed_at="January 2, 2026",
            text=(
                f"Adversary case {adversary_number}. Complaint by Trustee "
                "against Defendant LLC."
            ),
            description="Complaint",
        )
        + _screening_entry_html(
            number=5,
            filed_at="February 2, 2026",
            text="MOTION to Dismiss adversary complaint under Rule 7012",
            description="Motion to Dismiss",
        )
        + _screening_entry_html(
            number=16,
            filed_at="July 2, 2026",
            text="ORDER granting Motion to Dismiss adversary complaint",
            description="Order on Motion to Dismiss",
        )
        + "</div></body></html>"
    )


def _screening_entry_html(
    *, number: int, filed_at: str, text: str, description: str
) -> str:
    return (
        f'<div class="row" id="entry-{number}">'
        f'<div class="col-xs-1">{number}</div>'
        f'<div class="col-xs-3"><span title="{filed_at}">{filed_at}</span></div>'
        f'<div class="col-xs-8">{text}'
        '<div class="recap-documents"><div>Main Document</div>'
        f"<div>{description}</div>"
        f'<a href="https://storage.courtlistener.com/{number}.pdf">'
        "Download PDF</a></div></div></div>"
    )


def _client(
    *responses: RecordedCaseDevResponse,
) -> tuple[CaseDevClient, CaseDevFixtureTransport]:
    transport = CaseDevFixtureTransport(responses)
    return CaseDevClient(config=_config(), transport=transport), transport


def _lookup(
    case_id: str,
    *,
    courtlistener_docket_id: str | None = None,
    include_source_url: bool = True,
    extra_payload: dict[str, object] | None = None,
) -> RecordedCaseDevResponse:
    payload: dict[str, object] = {
        "id": case_id,
        "caseName": f"Fixture {case_id} v. Example",
        "courtId": "nysd",
        "docketNumber": "1:26-cv-00001",
    }
    if include_source_url:
        docket_id = courtlistener_docket_id or case_id
        payload["url"] = (
            f"https://www.courtlistener.com/api/rest/v4/dockets/{docket_id}/"
        )
    if extra_payload is not None:
        payload.update(extra_payload)
    return RecordedCaseDevResponse(
        method="POST",
        path="/legal/v1/docket",
        params={"type": "lookup", "docketId": case_id},
        status_code=200,
        payload=payload,
    )
