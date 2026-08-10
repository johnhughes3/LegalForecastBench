from __future__ import annotations

from datetime import date

import pytest
from legalforecast.contracts import (
    ACQUISITION_RUN_CARD_V1,
    ARTIFACT_CANONICAL_JSON_V1,
    ARTIFACT_JSON_VALUE_V1,
    ARTIFACT_PREFIXED_SHA256_V1,
    ARTIFACT_RAW_SHA256_V1,
    EXACT100_SUCCESSOR_PROMOTION_V1,
    EXACT100_SUCCESSOR_REPLACEMENT_CONFIG_V1,
    EXACT100_SUCCESSOR_REPLACEMENT_STATE_V1,
    EXACT100_SUCCESSOR_TERMINAL_EXCLUSION_V1,
    EXACT100_ZERO_COST_RECOVERY_RECEIPT_V1,
    EXACT100_ZERO_COST_RECOVERY_REQUEST_V1,
    EXACT100_ZERO_COST_RECOVERY_RUN_V1,
    FINALIZED_PREDICTION_UNITS_V3,
    MANIFEST_CANONICAL_JSON_V1,
    MANIFEST_RAW_SHA256_V1,
    RAW_BYTES_RAW_SHA256_V1,
    RECOVERY_VERTICAL_SLICE_SCHEMAS,
    RESOLVED_POST_RECOVERY_PUBLIC_DOCUMENT_V4,
    RUN_CARD_INDENTED_JSON_V1,
    RUN_CARD_RAW_SHA256_V1,
    SELECTED_ACQUISITION_SLICE_V1,
    TARGET_RAW_DOCKET_RECOVERY_PLAN_V1,
    TARGET_RAW_DOCKET_RECOVERY_PROVENANCE_V1,
    TARGET_RAW_DOCKET_RECOVERY_RECEIPT_V1,
    TARGET_RAW_DOCKET_RECOVERY_SUCCESSOR_PLAN_V1,
    TARGET_RAW_DOCKET_RECOVERY_SUMMARY_V1,
    UNITIZATION_ADJUDICATION_V2,
    ZERO_COST_SUCCESSOR_CONFIG_V1,
    CanonicalJsonCodec,
    CommitmentEncodingError,
    CommitmentMismatchError,
    CommitmentProfile,
    PrefixedSha256,
    RawSha256,
    SchemaIdentifier,
)

_PAYLOAD = {"z": "é", "a": 1}


def test_cycle_1_canonical_json_characterization_vectors() -> None:
    assert ARTIFACT_CANONICAL_JSON_V1.encode(_PAYLOAD) == (b'{"a":1,"z":"\xc3\xa9"}\n')
    assert ARTIFACT_JSON_VALUE_V1.encode(_PAYLOAD) == b'{"a":1,"z":"\xc3\xa9"}'
    assert MANIFEST_CANONICAL_JSON_V1.encode(_PAYLOAD) == (b'{"a":1,"z":"\\u00e9"}')
    assert RUN_CARD_INDENTED_JSON_V1.encode(_PAYLOAD) == (
        b'{\n  "a": 1,\n  "z": "\\u00e9"\n}\n'
    )


def test_manifest_profile_preserves_default_string_characterization() -> None:
    assert MANIFEST_CANONICAL_JSON_V1.encode({"day": date(2026, 8, 7)}) == (
        b'{"day":"2026-08-07"}'
    )


@pytest.mark.parametrize(
    "codec",
    (
        ARTIFACT_CANONICAL_JSON_V1,
        ARTIFACT_JSON_VALUE_V1,
        MANIFEST_CANONICAL_JSON_V1,
        RUN_CARD_INDENTED_JSON_V1,
    ),
)
def test_blessed_codecs_reject_non_finite_numbers(codec: CanonicalJsonCodec) -> None:
    with pytest.raises(CommitmentEncodingError, match="non-finite"):
        codec.encode({"value": float("nan")})


def test_raw_and_prefixed_digest_vectors_are_distinct_types() -> None:
    raw = ARTIFACT_RAW_SHA256_V1.commit(
        _PAYLOAD,
        domain=RESOLVED_POST_RECOVERY_PUBLIC_DOCUMENT_V4,
    )
    prefixed = ARTIFACT_PREFIXED_SHA256_V1.commit(
        _PAYLOAD,
        domain=RESOLVED_POST_RECOVERY_PUBLIC_DOCUMENT_V4,
    )

    assert raw.digest == RawSha256(
        "3035c5ffd8eef123cb9b17334ab0f2006c992f32986bfb7a1e139b99a96d1c6b"
    )
    assert prefixed.digest == PrefixedSha256(
        "sha256:3035c5ffd8eef123cb9b17334ab0f2006c992f32986bfb7a1e139b99a96d1c6b"
    )


def test_raw_bytes_digest_preserves_exact_input_bytes() -> None:
    commitment = RAW_BYTES_RAW_SHA256_V1.commit(
        b"payload\n",
        domain=ACQUISITION_RUN_CARD_V1,
    )

    assert commitment.digest == RawSha256(
        "d4e4877bac978b7952f0d544fc52ebff5411d351d129f1f056fa43f11da9af2b"
    )


def test_manifest_digest_vector_has_no_artifact_newline() -> None:
    commitment = MANIFEST_RAW_SHA256_V1.commit(
        _PAYLOAD,
        domain=ACQUISITION_RUN_CARD_V1,
    )

    assert commitment.digest == RawSha256(
        "a1efe949872d8f37ca353d1590a3e89d159de89b315b1096f10e4d25498da8c2"
    )
    MANIFEST_RAW_SHA256_V1.verify(
        _PAYLOAD,
        commitment,
        domain=ACQUISITION_RUN_CARD_V1,
    )


def test_run_card_digest_vector_includes_indentation_and_newline() -> None:
    commitment = RUN_CARD_RAW_SHA256_V1.commit(
        _PAYLOAD,
        domain=ACQUISITION_RUN_CARD_V1,
    )

    assert commitment.digest == RawSha256(
        "2539346e2f7f241c1bdad0d41b7ae71e23eb4f7adf9ccff64326f5b8372c60cc"
    )


@pytest.mark.parametrize(
    "profile",
    (
        ARTIFACT_RAW_SHA256_V1,
        ARTIFACT_PREFIXED_SHA256_V1,
        MANIFEST_RAW_SHA256_V1,
        RUN_CARD_RAW_SHA256_V1,
    ),
)
@pytest.mark.parametrize(
    "payload",
    ({}, {"text": "é"}, {"nested": [1, True, None, {"key": "value"}]}),
)
def test_commit_and_verify_round_trip(
    profile: CommitmentProfile,
    payload: object,
) -> None:
    commitment = profile.commit(payload, domain=ACQUISITION_RUN_CARD_V1)

    profile.verify(payload, commitment, domain=ACQUISITION_RUN_CARD_V1)
    with pytest.raises(CommitmentMismatchError, match="digest"):
        profile.verify(
            {"tampered": payload},
            commitment,
            domain=ACQUISITION_RUN_CARD_V1,
        )


def test_verification_rejects_cross_profile_and_cross_schema_substitution() -> None:
    commitment = ARTIFACT_RAW_SHA256_V1.commit(
        _PAYLOAD,
        domain=RESOLVED_POST_RECOVERY_PUBLIC_DOCUMENT_V4,
    )

    with pytest.raises(CommitmentMismatchError, match="profile"):
        MANIFEST_RAW_SHA256_V1.verify(
            _PAYLOAD,
            commitment,
            domain=RESOLVED_POST_RECOVERY_PUBLIC_DOCUMENT_V4,
        )
    with pytest.raises(CommitmentMismatchError, match="domain"):
        ARTIFACT_RAW_SHA256_V1.verify(
            _PAYLOAD,
            commitment,
            domain=ACQUISITION_RUN_CARD_V1,
        )


def test_recovery_vertical_slice_schema_registry_is_versioned_and_unique() -> None:
    values = tuple(schema.value for schema in RECOVERY_VERTICAL_SLICE_SCHEMAS)

    assert {
        RESOLVED_POST_RECOVERY_PUBLIC_DOCUMENT_V4,
        SELECTED_ACQUISITION_SLICE_V1,
        TARGET_RAW_DOCKET_RECOVERY_PLAN_V1,
        TARGET_RAW_DOCKET_RECOVERY_PROVENANCE_V1,
        TARGET_RAW_DOCKET_RECOVERY_RECEIPT_V1,
        TARGET_RAW_DOCKET_RECOVERY_SUMMARY_V1,
        TARGET_RAW_DOCKET_RECOVERY_SUCCESSOR_PLAN_V1,
        FINALIZED_PREDICTION_UNITS_V3,
        EXACT100_SUCCESSOR_PROMOTION_V1,
        EXACT100_SUCCESSOR_REPLACEMENT_CONFIG_V1,
        EXACT100_SUCCESSOR_REPLACEMENT_STATE_V1,
        EXACT100_SUCCESSOR_TERMINAL_EXCLUSION_V1,
        EXACT100_ZERO_COST_RECOVERY_RECEIPT_V1,
        EXACT100_ZERO_COST_RECOVERY_REQUEST_V1,
        EXACT100_ZERO_COST_RECOVERY_RUN_V1,
        UNITIZATION_ADJUDICATION_V2,
        ZERO_COST_SUCCESSOR_CONFIG_V1,
    }.issubset(RECOVERY_VERTICAL_SLICE_SCHEMAS)
    assert len(values) == len(set(values))
    assert all(value.startswith("legalforecast.") for value in values)
    assert all(value.rsplit(".v", maxsplit=1)[-1].isdigit() for value in values)


@pytest.mark.parametrize(
    "value",
    (
        "legalforecast.multiharness.adapter_manifest.v1",
        "legalforecast.release.package_hashes.v1",
    ),
)
def test_schema_identifier_accepts_namespaced_versioned_schemas(value: str) -> None:
    assert SchemaIdentifier(value).value == value


@pytest.mark.parametrize(
    "value",
    ("legalforecast.unversioned", "other.example.v1", "legalforecast.bad.vzero"),
)
def test_schema_identifier_rejects_unversioned_or_foreign_names(value: str) -> None:
    with pytest.raises(ValueError, match="versioned legalforecast schema"):
        SchemaIdentifier(value)
