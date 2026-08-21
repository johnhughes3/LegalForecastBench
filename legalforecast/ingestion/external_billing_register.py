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
ledger **or** a row in a register the owner ratified, naming the tranche
checkpoint that billed the document and the request that the owner's own typed
confirmation committed".

**The register is pinned by digest, not by schema.**  The owner ratified one
exact byte sequence, and that sequence is what this reads.  It is deliberately
not normalised, re-emitted, or migrated onto a repository schema: re-emitting
it would produce bytes the owner never saw, which invalidates the ratification
and costs another owner sitting.  So the artifact keeps its producing lane's
own schema string, this module keeps the digest, and admitting a different
register is a deliberate code change rather than an operator's choice of path.

Fail-closed in both directions: absent a register, coverage is exactly the
canonical ledger's operations and nothing widens; given one, it must be the
ratified bytes and every row must be complete.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

#: The register the owner ratified on 2026-08-20, by digest of its exact bytes.
#: Pinning one digest is the point: it is the only artifact whose contents the
#: owner actually read and signed, so anything else -- including a re-emission
#: of the very same facts -- is refused until a later ratification is pinned.
RATIFIED_REGISTER_SHA256 = (
    "2b8266e1dbf31f06234de6f222c55b9566fe3a0cb7e78cb5cf0b9b34cfe70de1"
)

#: The producing lane's own schema string.  The register is authenticated by the
#: digest above; this is a second, cheaper signal, never the authority.
RATIFIED_REGISTER_SCHEMA = "sam.lane.external_billing_register.v1_draft"

_DIGEST = re.compile(r"[0-9a-f]{64}")
_RECORD_FIELDS = frozenset(
    {
        "authorizing_checkpoint_sha256",
        "authorizing_request_sha256",
        "billed_usd",
        "billing_channel",
        "billing_tranche",
        "candidate_id",
        "docket_entry_number",
        "document_sha256",
        "outside_required_document_sha256_set",
        "receipt_role",
        "reviewer_id",
        "source_document_id",
    }
)

DocumentKey = tuple[str, str]


class ExternalBillingRegisterError(ValueError):
    """Raised when a register is not the ratified, complete enumeration."""


@dataclass(frozen=True, slots=True)
class VerifiedExternalBillingRegister:
    """One authenticated register, sealed after digest and field re-derivation."""

    document_commitments: tuple[tuple[DocumentKey, str], ...]
    register_sha256: str
    billed_usd: str

    @property
    def document_keys(self) -> frozenset[DocumentKey]:
        return frozenset(key for key, _digest in self.document_commitments)

    def commitment_map(self) -> dict[DocumentKey, str]:
        return dict(self.document_commitments)


def verify_external_billing_register(
    payload: bytes, *, expected_sha256: str = RATIFIED_REGISTER_SHA256
) -> VerifiedExternalBillingRegister:
    """Authenticate register bytes against the ratified digest.

    ``expected_sha256`` defaults to the ratified pin.  It is a parameter so the
    shape can be exercised without the private artifact, never so that an
    operator can choose which register counts.
    """

    digest = hashlib.sha256(payload).hexdigest()
    if digest != expected_sha256:
        raise ExternalBillingRegisterError(
            "external billing register is not the ratified artifact"
        )
    record = _object(payload)
    if record.get("schema_version") != RATIFIED_REGISTER_SCHEMA:
        raise ExternalBillingRegisterError(
            "external billing register has an unexpected schema"
        )

    rows = record.get("documents")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)) or not rows:
        raise ExternalBillingRegisterError(
            "external billing register enumerates no billed documents"
        )
    commitments: dict[DocumentKey, str] = {}
    for row in cast(Sequence[object], rows):
        entry = _mapping(row, "external billing register record")
        if frozenset(entry) != _RECORD_FIELDS:
            raise ExternalBillingRegisterError(
                "external billing register record fields differ from "
                f"{sorted(_RECORD_FIELDS)}"
            )
        key = (_text(entry, "candidate_id"), _text(entry, "source_document_id"))
        # Each row is an authority claim about one document, so two rows for one
        # document are two claims -- and nothing here could say which governs.
        if key in commitments:
            raise ExternalBillingRegisterError(
                f"external billing register names {key[0]}/{key[1]} twice"
            )
        for field in (
            "authorizing_checkpoint_sha256",
            "authorizing_request_sha256",
        ):
            _hex_digest(entry, field)
        commitments[key] = _hex_digest(entry, "document_sha256")
        _text(entry, "reviewer_id")

    totals = _mapping(record.get("totals"), "external billing register totals")
    if totals.get("document_count") != len(commitments):
        raise ExternalBillingRegisterError(
            "external billing register totals disagree with its own rows"
        )
    return VerifiedExternalBillingRegister(
        document_commitments=tuple(sorted(commitments.items())),
        register_sha256=f"sha256:{digest}",
        billed_usd=_text(totals, "billed_usd"),
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


def _text(record: Mapping[str, Any], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ExternalBillingRegisterError(
            f"external billing register field is empty: {field}"
        )
    return value


def _hex_digest(record: Mapping[str, Any], field: str) -> str:
    value = _text(record, field)
    if _DIGEST.fullmatch(value) is None:
        raise ExternalBillingRegisterError(
            f"external billing register digest is malformed: {field}"
        )
    return value
