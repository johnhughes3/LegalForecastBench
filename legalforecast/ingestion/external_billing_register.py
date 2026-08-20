"""Owner-ratified register of documents billed outside the canonical ledger.

Cohort consolidation holds one invariant about money: every document the final
projection treats as paid must trace to recorded purchase authority.  It reads
that authority from exactly one place -- the operations in the canonical
purchase ledger the approved policy names.

Some documents were legitimately purchased against a different, separately
owner-approved authority chain, and no supported path can make the canonical
ledger say it billed them: the ledger's recorder authorises *future* purchases
and has no adopt or import path, and its status vocabulary is a SQL CHECK
constraint, so an "adopted" operation would require migrating the cycle's most
sensitive artifact.

This register is the alternative, and it is deliberately the smaller claim.  It
does not weaken the invariant -- it widens what counts as *recorded authority*,
from "an operation in the canonical ledger" to "an operation in the canonical
ledger **or** a row in a register the owner signed, naming the tranche receipt
that billed the document and the owner's own typed confirmation".  Nothing
becomes implicit: the register enumerates exactly which documents were billed
elsewhere and under what authority, and it is authenticated by digest like any
other consolidation input.

It is fail-closed in both directions.  Absent a register, coverage is exactly
the canonical ledger's operations and nothing widens.  Given a register, every
row must be complete and well-formed, unknown fields refuse, and an empty
register refuses rather than reading as "widen by nothing" -- a register that
widens nothing is a mistake, not a no-op.

The module is free of paths, providers and ledgers: it receives bytes and
returns a sealed value or raises.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, cast

from legalforecast.contracts import EXTERNAL_BILLING_REGISTER_V1

EXTERNAL_BILLING_REGISTER_SCHEMA = str(EXTERNAL_BILLING_REGISTER_V1)

_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_ENVELOPE_FIELDS = frozenset(
    {"schema_version", "owner_signoff", "records"},
)
_SIGNOFF_FIELDS = frozenset(
    {"owner_verbatim", "signoff_source", "artifact_sha256"},
)
_RECORD_FIELDS = frozenset(
    {
        "candidate_id",
        "source_document_id",
        "tranche_receipt_sha256",
        "typed_confirmation_sha256",
    }
)

DocumentKey = tuple[str, str]


class ExternalBillingRegisterError(ValueError):
    """Raised when a register is not a complete, owner-signed enumeration."""


@dataclass(frozen=True, slots=True)
class VerifiedExternalBillingRegister:
    """One authenticated register, sealed after field-by-field re-derivation."""

    document_keys: frozenset[DocumentKey]
    register_sha256: str
    owner_signoff: Mapping[str, str]


def verify_external_billing_register(payload: bytes) -> VerifiedExternalBillingRegister:
    """Authenticate register bytes and return the keys they cover.

    The digest is computed here rather than accepted from a caller, so the
    value a run card commits is derived from the same bytes that were read.
    """

    record = _object(payload)
    _require_exact_fields(record, _ENVELOPE_FIELDS, "external billing register")
    if record.get("schema_version") != EXTERNAL_BILLING_REGISTER_SCHEMA:
        raise ExternalBillingRegisterError(
            "external billing register has an unexpected schema"
        )
    signoff = _mapping(record.get("owner_signoff"), "external billing register signoff")
    _require_exact_fields(signoff, _SIGNOFF_FIELDS, "external billing register signoff")
    owner_signoff = {
        "owner_verbatim": _text(signoff, "owner_verbatim"),
        "signoff_source": _text(signoff, "signoff_source"),
        "artifact_sha256": _digest(signoff, "artifact_sha256"),
    }

    rows = record.get("records")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)) or not rows:
        raise ExternalBillingRegisterError(
            "external billing register enumerates no billed documents"
        )
    keys: set[DocumentKey] = set()
    for row in cast(Sequence[object], rows):
        entry = _mapping(row, "external billing register record")
        _require_exact_fields(entry, _RECORD_FIELDS, "external billing register record")
        key = (
            _text(entry, "candidate_id"),
            _text(entry, "source_document_id"),
        )
        # Each row is an authority claim about one document, so two rows for one
        # document are two claims -- and nothing here could say which governs.
        if key in keys:
            raise ExternalBillingRegisterError(
                f"external billing register names {key[0]}/{key[1]} twice"
            )
        _digest(entry, "tranche_receipt_sha256")
        _digest(entry, "typed_confirmation_sha256")
        keys.add(key)

    return VerifiedExternalBillingRegister(
        document_keys=frozenset(keys),
        register_sha256=f"sha256:{hashlib.sha256(payload).hexdigest()}",
        owner_signoff=MappingProxyType(owner_signoff),
    )


def _object(payload: bytes) -> Mapping[str, Any]:
    try:
        value = json.loads(payload)
    except ValueError as error:
        raise ExternalBillingRegisterError(
            "external billing register is not valid JSON"
        ) from error
    if not isinstance(value, Mapping):
        raise ExternalBillingRegisterError(
            "external billing register is not a JSON object"
        )
    return cast(Mapping[str, Any], value)


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ExternalBillingRegisterError(f"{label} is not a JSON object")
    return cast(Mapping[str, Any], value)


def _require_exact_fields(
    record: Mapping[str, Any], expected: frozenset[str], label: str
) -> None:
    """Refuse unknown and missing fields alike.

    A register is read for authority, so a field this version does not know is
    not decoration: it may be the very qualification that limits the claim.
    """

    if frozenset(record) != expected:
        raise ExternalBillingRegisterError(
            f"{label} fields differ from {sorted(expected)}"
        )


def _text(record: Mapping[str, Any], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ExternalBillingRegisterError(
            f"external billing register field is empty: {field}"
        )
    return value


def _digest(record: Mapping[str, Any], field: str) -> str:
    value = _text(record, field)
    if _DIGEST.fullmatch(value) is None:
        raise ExternalBillingRegisterError(
            f"external billing register digest is malformed: {field}"
        )
    return value
