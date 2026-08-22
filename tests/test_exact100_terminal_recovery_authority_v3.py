# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false
# pyright: reportPrivateUsage=false

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from legalforecast.contracts import EXACT100_ZERO_COST_RECOVERY_TERMINAL_AUTHORITY_V3
from legalforecast.ingestion import exact100_zero_cost_recovery as recovery
from legalforecast.ingestion.exact100_terminal_recovery_authority_v3.authority import (
    AUTHORITY_SCHEMA_VERSION,
    VerifiedExact100TerminalRecoveryAuthorityV3,
    authorize_persisted_terminal_recovery_evidence_v3,
    mint_exact100_terminal_recovery_authority_v3,
    require_verified_exact100_terminal_recovery_authority_v3,
)
from legalforecast.ingestion.exact100_zero_cost_recovery import (
    _execute_terminal_recovery_with_verifier,
    execute_exact100_zero_cost_recovery,
)
from legalforecast.ingestion.free_document_downloader import FixtureFreeDocumentSource
from legalforecast.ingestion.post_selection_terminal_exclusion import (
    PostSelectionTerminalExclusionError,
    TerminalExclusionReason,
    VerifiedTerminalExclusionEvidence,
    _mint_terminal_evidence,
    _mint_terminal_recovery_evidence_from_producer,
    authorize_persisted_terminal_recovery_evidence,
    validate_terminal_recovery_evidence,
)
from tests.test_exact100_zero_cost_recovery import (
    _client,
    _plan,
    _public_payload,
    _selection,
)
from tests.test_post_selection_terminal_exclusion import (
    _bytes,
    _rebind_recovery_transcript,
    _recovery_fixture,
    _sha,
)


def _authorize_v3(
    live_evidence: VerifiedTerminalExclusionEvidence, inputs: dict[str, Any]
) -> VerifiedTerminalExclusionEvidence:
    return authorize_persisted_terminal_recovery_evidence_v3(
        live_evidence=live_evidence, **inputs
    )


def _rebind_response(inputs: dict[str, Any], response_bytes: bytes) -> None:
    record = json.loads(inputs["rest_observation_transcript_bytes"])
    record["response_sha256"] = _sha(response_bytes)
    inputs["rest_observation_response_bytes"] = response_bytes
    _rebind_recovery_transcript(inputs, _bytes(record), record_count=1)
    inputs["run_card"]["output_commitments"]["rest_observation_response"] = _sha(
        response_bytes
    )
    inputs["run_card_bytes"] = _bytes(inputs["run_card"])


def test_v3_schema_is_versioned_and_distinct_from_v2_recovery_artifacts() -> None:
    assert AUTHORITY_SCHEMA_VERSION == (
        "legalforecast.exact100_zero_cost_recovery_terminal_authority.v3"
    )
    assert str(EXACT100_ZERO_COST_RECOVERY_TERMINAL_AUTHORITY_V3) == (
        AUTHORITY_SCHEMA_VERSION
    )


def test_v2_authorize_still_requires_exact_404_body_equality() -> None:
    live = _mint_terminal_recovery_evidence_from_producer(**_recovery_fixture())
    persisted = _recovery_fixture()
    _rebind_response(persisted, b'{"detail":"Not Found"}')

    with pytest.raises(
        PostSelectionTerminalExclusionError,
        match=(
            r"does not bind the persisted terminal evidence; "
            r"divergent commitments: .*rest_observation_response"
        ),
    ):
        authorize_persisted_terminal_recovery_evidence(live_evidence=live, **persisted)


def test_v3_accepts_semantically_identical_different_404_bytes() -> None:
    live_inputs = _recovery_fixture()
    live = _mint_terminal_recovery_evidence_from_producer(**live_inputs)
    persisted = _recovery_fixture()
    different_404 = b'{"detail":"Not Found"}'
    assert different_404 != persisted["rest_observation_response_bytes"]
    _rebind_response(persisted, different_404)

    authorized = _authorize_v3(live, persisted)

    assert authorized.candidate_id == "C002"
    assert authorized.source_document_id == "D002"
    assert authorized.evidence_commitments["rest_observation_response"] == _sha(
        different_404
    )
    assert (
        authorized.evidence_commitments["rest_observation_response"]
        != (live.evidence_commitments["rest_observation_response"])
    )
    assert authorized.evidence_commitments["selection"] == _sha(
        persisted["selection_bytes"]
    )
    assert authorized.evidence_commitments["recovery_request"] == _sha(
        persisted["request_bytes"]
    )


def test_v3_rejects_fresh_nonterminal_status() -> None:
    inputs = _recovery_fixture()
    with pytest.raises(PostSelectionTerminalExclusionError, match="not a terminal 404"):
        mint_exact100_terminal_recovery_authority_v3(
            selection_bytes=inputs["selection_bytes"],
            request=inputs["request"],
            request_bytes=inputs["request_bytes"],
            observation_status_code=200,
        )


def test_v3_rejects_live_capability_that_does_not_bind_the_request() -> None:
    persisted = _recovery_fixture()
    live = _mint_terminal_evidence(
        candidate_id="C002",
        source_document_id="D002",
        reason=TerminalExclusionReason.TERMINAL_MISSING_CORE_DOCUMENT,
        evidence_kind="completed_courtlistener_rest_noncharging_recovery",
        evidence_commitments={
            "selection": "sha256:" + "0" * 64,
            "recovery_request": "sha256:" + "1" * 64,
        },
    )

    with pytest.raises(
        PostSelectionTerminalExclusionError,
        match="does not bind the persisted terminal identity",
    ):
        _authorize_v3(live, persisted)


def test_validated_resume_bundle_cannot_reuse_terminal_authority() -> None:
    inputs = _recovery_fixture()
    validate_terminal_recovery_evidence(**inputs)
    forged = object.__new__(VerifiedTerminalExclusionEvidence)

    with pytest.raises(
        PostSelectionTerminalExclusionError,
        match="not produced by verified replay",
    ):
        _authorize_v3(forged, inputs)


def test_caller_constructed_v3_capability_has_no_authority() -> None:
    forged = object.__new__(VerifiedExact100TerminalRecoveryAuthorityV3)

    with pytest.raises(
        PostSelectionTerminalExclusionError,
        match="not produced by verified replay",
    ):
        require_verified_exact100_terminal_recovery_authority_v3(forged)


def test_verifier_404_mints_v3_identity_without_granting_result_authority() -> None:
    selection_bytes = _selection()
    client, _transport = _client(status_code=404, payload={"detail": "not found"})

    result = _execute_terminal_recovery_with_verifier(
        selection_bytes=selection_bytes,
        plan_bytes=_plan(selection_bytes),
        courtlistener=client,
    )

    assert result.terminal_exclusion_authority is False
    authority = result.terminal_authority_v3
    assert authority is not None
    require_verified_exact100_terminal_recovery_authority_v3(authority)
    assert authority.candidate_id == recovery._KNOWN_CANDIDATE_ID
    assert authority.source_document_id == recovery._KNOWN_RECAP_DOCUMENT_ID
    assert authority.courtlistener_docket_id == recovery._KNOWN_DOCKET_ID
    assert authority.courtlistener_docket_entry_id == recovery._KNOWN_DOCKET_ENTRY_ID
    assert authority.observation_status_code == 404
    assert authority.terminal_status == "unavailable"


def test_fresh_public_document_result_does_not_mint_v3_authority(
    tmp_path: Path,
) -> None:
    selection_bytes = _selection()
    client, _transport = _client(status_code=200, payload=_public_payload())
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

    assert result.receipt is None
    assert result.terminal_evidence is None
    assert result.terminal_authority_v3 is None


def test_public_execute_path_still_cannot_mint_terminal_or_v3_authority() -> None:
    selection_bytes = _selection()
    client, _transport = _client(
        status_code=404, payload={"detail": "caller fabricated"}
    )

    result = execute_exact100_zero_cost_recovery(
        selection_bytes=selection_bytes,
        plan_bytes=_plan(selection_bytes),
        courtlistener=client,
    )

    assert result.receipt is not None
    assert result.terminal_evidence is None
    assert result.terminal_authority_v3 is None
