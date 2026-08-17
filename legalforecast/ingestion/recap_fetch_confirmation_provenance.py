"""Non-authoritative provenance for RECAP Fetch purchase confirmations.

A queued RECAP Fetch purchase is normally confirmed from the queue receipt
(``status=2``).  When CourtListener's queue detail is still lagging behind the
paid dispatch, the client instead confirms from the already-published public
document, so a later retry cannot issue a second paid POST.  Both confirmations
are equally binding on billing, but they rest on different evidence, and only
the first one carries a queue receipt.

That distinction cannot live on the purchase row itself.  ``response_json`` is
embedded in the canonical purchase operation and state digests, and
``docs/cycle-1-change-control.md`` freezes those bytes for the rest of Cycle 1
while routing new observational metadata into non-authoritative sidecars.  A
previous attempt added the marker to ``response_json`` and had to be reverted.

This module owns the observation instead.  It writes one sidecar document
beside the canonical purchase ledger under a name outside the ledger's reserved
path namespace, so it is captured by neither
``_purchase_ledger_reserved_paths`` nor the authority byte closure that
``read_case_dev_purchase_authority_audit`` returns.  Nothing on the
authoritative purchase path reads it, and no failure here can change a billing
state: the sidecar only ever explains a confirmation that the journal already
recorded.

Two properties make the record honest rather than merely decorative:

* Every entry commits ``confirmed_response_sha256``, the digest of the exact
  confirmed response it annotates, so a reader can refuse an entry that no
  longer describes the row in front of it.
* The whole document is bound to one ledger generation by ``cycle_id`` and
  ``purchase_policy_sha256``.  A document from another generation describes a
  ledger that no longer exists at this path, so it is reported as saying
  nothing and is replaced on the next write rather than blocking acquisition.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, cast

from legalforecast.ingestion.canonical_json import canonical_json_bytes

SIDECAR_KIND: Final = "recap_fetch_confirmation_provenance_sidecar"
"""Document ``kind``; deliberately not a ``legalforecast.*.vN`` schema id."""

QUEUE_RECEIPT_CONFIRMATION: Final = "recap_fetch_queue_status_2"
"""Confirmation backed by a readable RECAP Fetch queue receipt."""

PUBLIC_DOCUMENT_CONFIRMATION: Final = "public_document_during_queue_lag"
"""Confirmation backed by the published public document during queue lag."""

CONFIRMATION_EVIDENCE_KINDS: Final = frozenset(
    {QUEUE_RECEIPT_CONFIRMATION, PUBLIC_DOCUMENT_CONFIRMATION}
)


class RecapFetchConfirmationProvenanceError(ValueError):
    """Raised when the observational confirmation sidecar is unreadable."""


def confirmation_provenance_path(ledger_path: Path) -> Path:
    """Return the sidecar path written beside one canonical purchase ledger.

    The suffix is deliberately outside ``_purchase_ledger_reserved_paths`` so
    the sidecar never enters the ledger's authenticated filesystem identity.
    """

    return ledger_path.with_name(f"{ledger_path.name}.confirmation-provenance.json")


@dataclass(frozen=True, slots=True)
class ConfirmationProvenance:
    """Which evidence confirmed one purchase, and any later queue receipt."""

    source_document_id: str
    queue_id: str
    confirmation_evidence: str
    confirmed_response_sha256: str
    queue_response: Mapping[str, Any] | None = None
    queue_response_sha256: str | None = None
    queue_receipt_attached_after_confirmation: bool = False

    def __post_init__(self) -> None:
        if self.confirmation_evidence not in CONFIRMATION_EVIDENCE_KINDS:
            raise RecapFetchConfirmationProvenanceError(
                "unknown RECAP Fetch confirmation evidence: "
                f"{self.confirmation_evidence}"
            )
        if (self.queue_response is None) != (self.queue_response_sha256 is None):
            raise RecapFetchConfirmationProvenanceError(
                "a queue receipt must carry both its payload and its digest"
            )
        if (
            self.queue_response is None
            and self.queue_receipt_attached_after_confirmation
        ):
            raise RecapFetchConfirmationProvenanceError(
                "a late queue-receipt attachment requires the receipt itself"
            )

    def to_record(self) -> dict[str, object]:
        """Return the stable JSON body stored under the document identifier."""

        record: dict[str, object] = {
            "queue_id": self.queue_id,
            "confirmation_evidence": self.confirmation_evidence,
            "confirmed_response_sha256": self.confirmed_response_sha256,
            "queue_receipt_attached_after_confirmation": (
                self.queue_receipt_attached_after_confirmation
            ),
        }
        if self.queue_response is not None:
            record["queue_response"] = dict(self.queue_response)
            record["queue_response_sha256"] = self.queue_response_sha256
        return record


def read_confirmation_provenance(
    path: Path,
    *,
    cycle_id: str,
    purchase_policy_sha256: str,
) -> dict[str, ConfirmationProvenance]:
    """Read every entry this sidecar records for the current ledger generation.

    An absent sidecar and a sidecar bound to another ledger generation both
    read as "no observation", because neither says anything about the ledger
    in front of the caller.  A present but malformed document is an honest
    failure and raises.
    """

    document = _read_document(path)
    if document is None:
        return {}
    if document.get("cycle_id") != cycle_id or (
        document.get("purchase_policy_sha256") != purchase_policy_sha256
    ):
        return {}
    raw = document.get("confirmations")
    if not isinstance(raw, Mapping):
        raise RecapFetchConfirmationProvenanceError(
            "confirmation provenance sidecar has no confirmations object"
        )
    confirmations = cast(Mapping[str, object], raw)
    return {
        str(document_id): _provenance_from_record(str(document_id), record)
        for document_id, record in confirmations.items()
    }


def record_confirmation_provenance(
    path: Path,
    *,
    cycle_id: str,
    purchase_policy_sha256: str,
    provenance: ConfirmationProvenance,
) -> None:
    """Persist which evidence confirmed one purchase, replacing any prior entry.

    This is called after the journal has already committed the confirmation, so
    it can only ever describe a durable billing state, never create one.
    """

    existing = read_confirmation_provenance(
        path, cycle_id=cycle_id, purchase_policy_sha256=purchase_policy_sha256
    )
    existing[provenance.source_document_id] = provenance
    _write_document(
        path,
        cycle_id=cycle_id,
        purchase_policy_sha256=purchase_policy_sha256,
        confirmations=existing,
    )


def provenance_from_confirmed_response(
    document_id: str,
    confirmed: Mapping[str, Any],
    *,
    confirmed_response_sha256: str,
    queue_response_sha256: str | None = None,
) -> ConfirmationProvenance:
    """Derive which evidence a confirmed response rests on.

    A confirmation carries its queue receipt only when the queue detail was
    readable, so the presence of ``queue_response`` is what separates the two
    evidence kinds.  Deriving it here rather than at the call site is what
    makes a lost entry reconstructible from bytes the journal already holds.
    """

    queue_response = confirmed.get("queue_response")
    if queue_response is not None and not isinstance(queue_response, Mapping):
        raise RecapFetchConfirmationProvenanceError(
            f"confirmed queue response must be an object: {document_id}"
        )
    receipt = (
        None
        if queue_response is None
        else dict(cast(Mapping[str, Any], queue_response))
    )
    if receipt is not None and queue_response_sha256 is None:
        raise RecapFetchConfirmationProvenanceError(
            f"a recorded queue receipt requires its digest: {document_id}"
        )
    return ConfirmationProvenance(
        source_document_id=document_id,
        queue_id=str(confirmed.get("queue_id", "")),
        confirmation_evidence=(
            QUEUE_RECEIPT_CONFIRMATION
            if receipt is not None
            else PUBLIC_DOCUMENT_CONFIRMATION
        ),
        confirmed_response_sha256=confirmed_response_sha256,
        queue_response=receipt,
        queue_response_sha256=None if receipt is None else queue_response_sha256,
    )


def reconcile_confirmation_provenance(
    path: Path,
    *,
    cycle_id: str,
    purchase_policy_sha256: str,
    provenance: ConfirmationProvenance,
) -> str | None:
    """Repair one entry and report any queue receipt still worth fetching.

    *provenance* is what the confirmed response says on its own.  A missing
    entry, or one describing a response that has since moved, is replaced with
    it: which branch confirmed a purchase is recoverable from bytes the journal
    already holds, so a lost observation is repaired rather than mourned.

    The return value is the queue id whose receipt is still missing, or
    ``None`` when there is nothing to fetch — the confirmation already rested
    on a queue receipt, one has since been attached, or the entry was just
    rewritten.  Callers use it to decide whether a free queue read is worth
    making at all.
    """

    recorded = read_confirmation_provenance(
        path, cycle_id=cycle_id, purchase_policy_sha256=purchase_policy_sha256
    ).get(provenance.source_document_id)
    if recorded is None or recorded.confirmed_response_sha256 != (
        provenance.confirmed_response_sha256
    ):
        record_confirmation_provenance(
            path,
            cycle_id=cycle_id,
            purchase_policy_sha256=purchase_policy_sha256,
            provenance=provenance,
        )
        return None
    if (
        recorded.confirmation_evidence != PUBLIC_DOCUMENT_CONFIRMATION
        or recorded.queue_response is not None
    ):
        return None
    return recorded.queue_id


def attach_queue_receipt(
    path: Path,
    *,
    cycle_id: str,
    purchase_policy_sha256: str,
    source_document_id: str,
    confirmed_response_sha256: str,
    queue_response: Mapping[str, Any],
    queue_response_sha256: str,
) -> bool:
    """Attach a late queue receipt to an existing public-document confirmation.

    Returns whether the receipt was newly attached.  The attachment is refused
    unless the recorded entry still describes the confirmed response the caller
    just read (``confirmed_response_sha256``), so a receipt can never be filed
    against a row that has since moved.  No billing state is touched: the queue
    detail became readable after the purchase was already confirmed, and the
    frozen purchase bytes stay exactly as the confirmation wrote them.
    """

    existing = read_confirmation_provenance(
        path, cycle_id=cycle_id, purchase_policy_sha256=purchase_policy_sha256
    )
    recorded = existing.get(source_document_id)
    if recorded is None:
        return False
    if recorded.confirmed_response_sha256 != confirmed_response_sha256:
        return False
    if recorded.confirmation_evidence != PUBLIC_DOCUMENT_CONFIRMATION:
        return False
    if recorded.queue_response is not None:
        return False
    existing[source_document_id] = ConfirmationProvenance(
        source_document_id=recorded.source_document_id,
        queue_id=recorded.queue_id,
        confirmation_evidence=recorded.confirmation_evidence,
        confirmed_response_sha256=recorded.confirmed_response_sha256,
        queue_response=dict(queue_response),
        queue_response_sha256=queue_response_sha256,
        queue_receipt_attached_after_confirmation=True,
    )
    _write_document(
        path,
        cycle_id=cycle_id,
        purchase_policy_sha256=purchase_policy_sha256,
        confirmations=existing,
    )
    return True


def _provenance_from_record(document_id: str, record: object) -> ConfirmationProvenance:
    if not isinstance(record, Mapping):
        raise RecapFetchConfirmationProvenanceError(
            f"confirmation provenance entry must be an object: {document_id}"
        )
    entry = cast(Mapping[str, object], record)
    queue_response = entry.get("queue_response")
    if queue_response is not None and not isinstance(queue_response, Mapping):
        raise RecapFetchConfirmationProvenanceError(
            f"confirmation provenance queue receipt must be an object: {document_id}"
        )
    attached = entry.get("queue_receipt_attached_after_confirmation", False)
    if not isinstance(attached, bool):
        raise RecapFetchConfirmationProvenanceError(
            f"confirmation provenance attachment flag must be boolean: {document_id}"
        )
    return ConfirmationProvenance(
        source_document_id=document_id,
        queue_id=_required_text(entry, "queue_id", document_id),
        confirmation_evidence=_required_text(
            entry, "confirmation_evidence", document_id
        ),
        confirmed_response_sha256=_required_text(
            entry, "confirmed_response_sha256", document_id
        ),
        queue_response=(
            None
            if queue_response is None
            else dict(cast(Mapping[str, Any], queue_response))
        ),
        queue_response_sha256=(
            None
            if queue_response is None
            else _required_text(entry, "queue_response_sha256", document_id)
        ),
        queue_receipt_attached_after_confirmation=attached,
    )


def _required_text(entry: Mapping[str, object], field: str, document_id: str) -> str:
    value = entry.get(field)
    if not isinstance(value, str) or not value:
        raise RecapFetchConfirmationProvenanceError(
            f"confirmation provenance {field} is missing: {document_id}"
        )
    return value


def _read_document(path: Path) -> Mapping[str, object] | None:
    if path.is_symlink():
        raise RecapFetchConfirmationProvenanceError(
            f"confirmation provenance sidecar must not be a symlink: {path}"
        )
    try:
        payload = path.read_bytes()
    except FileNotFoundError:
        return None
    try:
        decoded: object = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RecapFetchConfirmationProvenanceError(
            f"confirmation provenance sidecar is not valid JSON: {path}"
        ) from exc
    if not isinstance(decoded, Mapping):
        raise RecapFetchConfirmationProvenanceError(
            f"confirmation provenance sidecar must be an object: {path}"
        )
    document = cast(Mapping[str, object], decoded)
    if document.get("kind") != SIDECAR_KIND:
        raise RecapFetchConfirmationProvenanceError(
            f"confirmation provenance sidecar has an unexpected kind: {path}"
        )
    if document.get("authoritative") is not False:
        raise RecapFetchConfirmationProvenanceError(
            "confirmation provenance sidecar must declare itself "
            f"non-authoritative: {path}"
        )
    return document


def _write_document(
    path: Path,
    *,
    cycle_id: str,
    purchase_policy_sha256: str,
    confirmations: Mapping[str, ConfirmationProvenance],
) -> None:
    payload = canonical_json_bytes(
        {
            "kind": SIDECAR_KIND,
            "authoritative": False,
            "cycle_id": cycle_id,
            "purchase_policy_sha256": purchase_policy_sha256,
            "confirmations": {
                document_id: provenance.to_record()
                for document_id, provenance in confirmations.items()
            },
        },
        error_type=RecapFetchConfirmationProvenanceError,
        error_message="confirmation provenance sidecar is not serializable",
    )
    _atomic_private_write(path, payload)


def _atomic_private_write(path: Path, payload: bytes) -> None:
    """Replace the sidecar atomically, never widening it beyond the owner."""

    if path.is_symlink():
        raise RecapFetchConfirmationProvenanceError(
            f"confirmation provenance sidecar must not be a symlink: {path}"
        )
    directory = path.parent
    directory.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=directory, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            os.fchmod(handle.fileno(), 0o600)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
