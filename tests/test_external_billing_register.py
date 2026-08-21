"""The owner-ratified external billing register.

The register widens what counts as recorded purchase authority, so every way it
can be incomplete or substituted is a way for a document to claim authority it
does not have.  These tests pin the refusals, not the happy path alone.

The register is authenticated by the digest of the exact bytes the owner
ratified, so these build synthetic registers and inject their own expected
digest.  No corpus candidate, document or digest appears here.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import pytest
from legalforecast.ingestion.external_billing_register import (
    RATIFIED_REGISTER_SCHEMA,
    ExternalBillingRegisterError,
    verify_external_billing_register,
)


def _row(**overrides: Any) -> dict[str, Any]:
    row = {
        "authorizing_checkpoint_sha256": "a" * 64,
        "authorizing_request_sha256": "b" * 64,
        "billed_usd": "3.00",
        "billing_channel": "synthetic_channel",
        "billing_tranche": "synthetic/tranche",
        "candidate_id": "case000",
        "docket_entry_number": 7,
        "document_sha256": "c" * 64,
        "outside_required_document_sha256_set": False,
        "receipt_role": "opposition",
        "reviewer_id": "Synthetic Owner",
        "source_document_id": "case000-doc-1",
    }
    row.update(overrides)
    return row


def _register(**overrides: Any) -> dict[str, Any]:
    rows = overrides.pop("documents", [_row()])
    record = {
        "schema_version": RATIFIED_REGISTER_SCHEMA,
        "documents": rows,
        "totals": {"billed_usd": "3.00", "document_count": len(rows)},
    }
    record.update(overrides)
    return record


def _verify(record: dict[str, Any]) -> Any:
    payload = json.dumps(record).encode()
    return verify_external_billing_register(
        payload, expected_sha256=hashlib.sha256(payload).hexdigest()
    )


def test_a_complete_register_seals_its_document_keys() -> None:
    verified = _verify(_register())

    assert verified.document_keys == frozenset({("case000", "case000-doc-1")})
    assert verified.commitment_map() == {("case000", "case000-doc-1"): "c" * 64}
    assert verified.register_sha256.startswith("sha256:")
    assert verified.billed_usd == "3.00"


def test_bytes_that_are_not_the_ratified_artifact_refuse() -> None:
    """The owner ratified one byte sequence; nothing else carries his signature.

    A re-emission of the very same facts is still bytes he never read, which is
    why substitution is refused rather than reconciled.
    """

    payload = json.dumps(_register()).encode()

    with pytest.raises(ExternalBillingRegisterError, match="not the ratified artifact"):
        verify_external_billing_register(
            payload + b"\n", expected_sha256=hashlib.sha256(payload).hexdigest()
        )


def test_the_production_pin_refuses_a_synthetic_register() -> None:
    """The default pin is the ratified digest, not whatever it is handed."""

    with pytest.raises(ExternalBillingRegisterError, match="not the ratified artifact"):
        verify_external_billing_register(json.dumps(_register()).encode())


def test_an_empty_register_refuses() -> None:
    """Widening by nothing is a mistake, not a no-op."""

    with pytest.raises(ExternalBillingRegisterError, match="enumerates no billed"):
        _verify(_register(documents=[]))


def test_a_register_of_another_schema_refuses() -> None:
    with pytest.raises(ExternalBillingRegisterError, match="unexpected schema"):
        _verify(_register(schema_version="something.else.v1"))


def test_an_unknown_record_field_refuses() -> None:
    """A field this version does not know may be the limit on the claim."""

    with pytest.raises(ExternalBillingRegisterError, match="record fields differ"):
        _verify(_register(documents=[_row(reimbursed=True)]))


@pytest.mark.parametrize(
    "field",
    [
        "candidate_id",
        "source_document_id",
        "authorizing_checkpoint_sha256",
        "billed_usd",
    ],
)
def test_a_record_missing_any_field_refuses(field: str) -> None:
    row = _row()
    row.pop(field)

    with pytest.raises(ExternalBillingRegisterError, match="record fields differ"):
        _verify(_register(documents=[row]))


@pytest.mark.parametrize(
    "field",
    [
        "authorizing_checkpoint_sha256",
        "authorizing_request_sha256",
        "document_sha256",
    ],
)
def test_a_malformed_authority_digest_refuses(field: str) -> None:
    """These digests are the whole binding to the authority that billed it."""

    with pytest.raises(ExternalBillingRegisterError, match="digest is malformed"):
        _verify(_register(documents=[_row(**{field: "not-a-digest"})]))


def test_a_register_naming_one_document_twice_refuses() -> None:
    """Two authority claims for one document, and no rule to choose between them."""

    with pytest.raises(ExternalBillingRegisterError, match="twice"):
        _verify(_register(documents=[_row(), _row()]))


def test_totals_that_disagree_with_the_rows_refuse() -> None:
    """The owner read the totals, so the rows have to be what the totals say."""

    record = _register()
    record["totals"]["document_count"] = 5

    with pytest.raises(ExternalBillingRegisterError, match="totals disagree"):
        _verify(record)


def test_bytes_that_are_not_a_json_object_refuse() -> None:
    for payload in (b"{not json", b"[]"):
        with pytest.raises(ExternalBillingRegisterError):
            verify_external_billing_register(
                payload, expected_sha256=hashlib.sha256(payload).hexdigest()
            )
