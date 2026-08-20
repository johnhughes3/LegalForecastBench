"""The owner-ratified external billing register.

The register widens what counts as recorded purchase authority, so every way it
can be incomplete is a way for a document to claim authority it does not have.
These tests pin the refusals rather than the happy path alone.

Every value here is invented: no corpus candidate, document or digest appears.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from legalforecast.ingestion.external_billing_register import (
    EXTERNAL_BILLING_REGISTER_SCHEMA,
    ExternalBillingRegisterError,
    verify_external_billing_register,
)

_RECEIPT = "sha256:" + "b" * 64
_CONFIRMATION = "sha256:" + "c" * 64


def _register(**overrides: Any) -> dict[str, Any]:
    record = {
        "schema_version": EXTERNAL_BILLING_REGISTER_SCHEMA,
        "owner_signoff": {
            "owner_verbatim": "I ratify the enumerated external billing.",
            "signoff_source": "synthetic sitting record",
            "artifact_sha256": "sha256:" + "a" * 64,
        },
        "records": [
            {
                "candidate_id": "case000",
                "source_document_id": "case000-doc-1",
                "tranche_receipt_sha256": _RECEIPT,
                "typed_confirmation_sha256": _CONFIRMATION,
            }
        ],
    }
    record.update(overrides)
    return record


def _verify(record: dict[str, Any]) -> Any:
    return verify_external_billing_register(json.dumps(record).encode())


def test_a_complete_register_seals_its_document_keys() -> None:
    verified = _verify(_register())

    assert verified.document_keys == frozenset({("case000", "case000-doc-1")})
    assert verified.register_sha256.startswith("sha256:")
    assert verified.owner_signoff["signoff_source"] == "synthetic sitting record"


def test_the_digest_is_derived_from_the_bytes_read() -> None:
    """A caller cannot hand in the digest the run card will commit."""

    payload = json.dumps(_register()).encode()

    assert (
        verify_external_billing_register(payload).register_sha256
        != verify_external_billing_register(payload + b" ").register_sha256
    )


def test_an_empty_register_refuses() -> None:
    """Widening by nothing is a mistake, not a no-op."""

    with pytest.raises(ExternalBillingRegisterError, match="enumerates no billed"):
        _verify(_register(records=[]))


def test_a_register_of_another_schema_refuses() -> None:
    with pytest.raises(ExternalBillingRegisterError, match="unexpected schema"):
        _verify(_register(schema_version="legalforecast.something_else.v1"))


def test_an_unknown_envelope_field_refuses() -> None:
    """A field this version does not know may be the limit on the claim."""

    with pytest.raises(ExternalBillingRegisterError, match="fields differ"):
        _verify(_register(supersedes="something"))


def test_an_unknown_record_field_refuses() -> None:
    record = _register()
    record["records"][0]["reimbursed"] = True

    with pytest.raises(ExternalBillingRegisterError, match="record fields differ"):
        _verify(record)


@pytest.mark.parametrize(
    "field",
    ["candidate_id", "source_document_id", "tranche_receipt_sha256"],
)
def test_a_record_missing_any_field_refuses(field: str) -> None:
    record = _register()
    record["records"][0].pop(field)

    with pytest.raises(ExternalBillingRegisterError, match="record fields differ"):
        _verify(record)


@pytest.mark.parametrize(
    "field", ["tranche_receipt_sha256", "typed_confirmation_sha256"]
)
def test_a_malformed_authority_digest_refuses(field: str) -> None:
    """The digests are the whole binding to the authority that billed it."""

    record = _register()
    record["records"][0][field] = "not-a-digest"

    with pytest.raises(ExternalBillingRegisterError, match="digest is malformed"):
        _verify(record)


def test_a_register_without_a_complete_owner_signoff_refuses() -> None:
    record = _register()
    record["owner_signoff"].pop("owner_verbatim")

    with pytest.raises(ExternalBillingRegisterError, match="signoff fields differ"):
        _verify(record)


def test_a_register_naming_one_document_twice_refuses() -> None:
    """Two authority claims for one document, and no rule to pick between them."""

    record = _register()
    record["records"].append(dict(record["records"][0]))

    with pytest.raises(ExternalBillingRegisterError, match="twice"):
        _verify(record)


def test_bytes_that_are_not_a_json_object_refuse() -> None:
    with pytest.raises(ExternalBillingRegisterError, match="not valid JSON"):
        verify_external_billing_register(b"{not json")
    with pytest.raises(ExternalBillingRegisterError, match="not a JSON object"):
        verify_external_billing_register(b"[]")
