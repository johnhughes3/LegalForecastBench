"""Issue and reauthenticate owner-adjudicated replacement evidence roots.

This is the issuance half of the v3 successor lane.  A fail-closed executor is
an unfinished feature without the supported tool that produces what it demands,
so the command that mints a replacement evidence root ships alongside the
projector that consumes one.

The mint reads a *plan* naming the documents, and receipts and validation
artifacts that were produced by earlier supported acquisition and validation
runs.  The plan carries no authority: every claim in it must be corroborated by
a receipt row, by the bytes on disk, and by a validation record, or the mint
refuses.

Reauthentication mirrors the supporting-document successor: a completed root's
own run card names exactly the inputs it was minted from, those paths are
replayed, and the re-minted bytes must equal the persisted bytes exactly.  A
root therefore cannot authorise itself.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from legalforecast.contracts import OWNER_ADJUDICATED_REPLACEMENT_PLAN_V1
from legalforecast.ingestion.canonical_json import canonical_json_bytes
from legalforecast.ingestion.exact100_successor_v3.replacement_evidence import (
    EVIDENCE_SCHEMA_VERSION,
    OwnerAdjudicatedReplacementError,
    VerifiedOwnerAdjudicatedReplacement,
    mint_verified_owner_adjudicated_replacement,
)

STAGE = "mint-owner-adjudicated-replacement-evidence"
PLAN_SCHEMA_VERSION = str(OWNER_ADJUDICATED_REPLACEMENT_PLAN_V1)

_OUTPUTS = {
    "selection": "replacement-selection.jsonl",
    "case_relevance": "replacement-case-relevance.jsonl",
    "download_manifest": "replacement-document-downloads.jsonl",
    "clearance": "replacement-disclosure-clearance.jsonl",
    "restriction": "replacement-restriction-evidence.jsonl",
    "run_card": "run-cards/mint-owner-adjudicated-replacement-evidence.json",
}
_INPUT_ORDER = (
    "plan",
    "docket_snapshot",
    "owner_disposition",
    "acquisition_receipts",
    "validations",
)
_PAID_ROUTES = frozenset({"pacer_purchase", "recap_fetch_purchase"})


class OwnerAdjudicatedReplacementCliError(ValueError):
    """Raised when replacement evidence cannot be minted or reauthenticated."""


def add_parser(subparsers: Any, *, handler: Any) -> None:
    parser = subparsers.add_parser(
        "mint-replacement-evidence",
        help="Seal one owner-adjudicated replacement into an evidence root.",
        description=(
            "Provider-free.  Reads an evidence plan plus the acquisition "
            "receipts, byte-role validations, docket snapshot and recorded "
            "owner disposition that already exist, re-derives every claim "
            "against those artifacts, and writes an immutable evidence root. "
            "It exposes no provider, retrieval, paid, model, evaluation, "
            "freeze or dispatch action."
        ),
    )
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--docket-snapshot", type=Path, required=True)
    parser.add_argument("--owner-disposition", type=Path, required=True)
    parser.add_argument(
        "--acquisition-receipt", type=Path, action="append", default=[], required=True
    )
    parser.add_argument(
        "--byte-role-validation", type=Path, action="append", default=[], required=True
    )
    parser.add_argument("--output-root", type=Path, required=True)
    parser.set_defaults(handler=handler)


def run(args: argparse.Namespace) -> int:
    plan_path = cast(Path, args.plan)
    inputs = _Inputs(
        plan=plan_path,
        docket_snapshot=cast(Path, args.docket_snapshot),
        owner_disposition=cast(Path, args.owner_disposition),
        acquisition_receipts=tuple(cast(list[Path], args.acquisition_receipt)),
        validations=tuple(cast(list[Path], args.byte_role_validation)),
    )
    output_root = cast(Path, args.output_root)
    for path in inputs.all_paths():
        if _overlaps(output_root, path):
            raise OwnerAdjudicatedReplacementCliError(
                "replacement evidence output overlaps its authenticated inputs"
            )
    replacement, payloads = _mint(inputs, output_root=output_root)
    for name, payload in payloads.items():
        _write_immutable(output_root / _OUTPUTS[name], payload)
    for relative, payload in replacement.document_bytes.items():
        _write_immutable(output_root / relative, payload)
    print(
        json.dumps(
            {
                "candidate_id": replacement.candidate_id,
                "replaces_candidate_id": replacement.replaces_candidate_id,
                "commitment_sha256": replacement.commitment_sha256,
                "document_count": len(replacement.download_manifest),
                "output_root": str(output_root.absolute()),
                "paid_activity_executed": False,
                "provider_activity_executed": False,
            },
            sort_keys=True,
        )
    )
    return 0


def verify_owner_adjudicated_replacement_evidence(
    root: Path,
) -> VerifiedOwnerAdjudicatedReplacement:
    """Replay a completed evidence root from the inputs its own card names."""

    card_path = root / _OUTPUTS["run_card"]
    card = _object(_read(card_path), card_path)
    if (
        card.get("schema_version") != EVIDENCE_SCHEMA_VERSION
        or card.get("stage") != STAGE
        or card.get("status") != "completed"
    ):
        raise OwnerAdjudicatedReplacementCliError(
            "replacement evidence run card is not a completed mint"
        )
    raw_inputs = card.get("input_paths")
    if not isinstance(raw_inputs, Mapping):
        raise OwnerAdjudicatedReplacementCliError(
            "replacement evidence run card lacks its input paths"
        )
    recorded = cast(Mapping[str, object], raw_inputs)
    if set(recorded) != set(_INPUT_ORDER):
        raise OwnerAdjudicatedReplacementCliError(
            "replacement evidence run card input paths differ"
        )
    inputs = _Inputs(
        plan=Path(_required_str(recorded, "plan")),
        docket_snapshot=Path(_required_str(recorded, "docket_snapshot")),
        owner_disposition=Path(_required_str(recorded, "owner_disposition")),
        acquisition_receipts=_path_tuple(recorded, "acquisition_receipts"),
        validations=_path_tuple(recorded, "validations"),
    )
    replacement, payloads = _mint(inputs, output_root=root)
    for name, payload in payloads.items():
        if _read(root / _OUTPUTS[name]) != payload:
            raise OwnerAdjudicatedReplacementCliError(
                f"replacement evidence differs from replay: {_OUTPUTS[name]}"
            )
    for relative, payload in replacement.document_bytes.items():
        if _read(root / relative) != payload:
            raise OwnerAdjudicatedReplacementCliError(
                f"replacement evidence document differs from replay: {relative}"
            )
    _require_closed_root(root, replacement)
    return replacement


class _Inputs:
    """The exact artifact set a replacement mint is allowed to read."""

    __slots__ = (
        "acquisition_receipts",
        "docket_snapshot",
        "owner_disposition",
        "plan",
        "validations",
    )

    def __init__(
        self,
        *,
        plan: Path,
        docket_snapshot: Path,
        owner_disposition: Path,
        acquisition_receipts: Sequence[Path],
        validations: Sequence[Path],
    ) -> None:
        if not acquisition_receipts or not validations:
            raise OwnerAdjudicatedReplacementCliError(
                "replacement evidence needs at least one receipt and validation"
            )
        self.plan = plan
        self.docket_snapshot = docket_snapshot
        self.owner_disposition = owner_disposition
        self.acquisition_receipts = tuple(acquisition_receipts)
        self.validations = tuple(validations)

    def all_paths(self) -> tuple[Path, ...]:
        return (
            self.plan,
            self.docket_snapshot,
            self.owner_disposition,
            *self.acquisition_receipts,
            *self.validations,
        )

    def recorded(self) -> dict[str, object]:
        return {
            "plan": str(self.plan.absolute()),
            "docket_snapshot": str(self.docket_snapshot.absolute()),
            "owner_disposition": str(self.owner_disposition.absolute()),
            "acquisition_receipts": [
                str(path.absolute()) for path in self.acquisition_receipts
            ],
            "validations": [str(path.absolute()) for path in self.validations],
        }


def _mint(
    inputs: _Inputs, *, output_root: Path
) -> tuple[VerifiedOwnerAdjudicatedReplacement, dict[str, bytes]]:
    snapshots: dict[Path, bytes] = {path: _read(path) for path in inputs.all_paths()}
    plan = _object(snapshots[inputs.plan], inputs.plan)
    if plan.get("schema_version") != PLAN_SCHEMA_VERSION:
        raise OwnerAdjudicatedReplacementCliError(
            "replacement evidence plan has an unexpected schema"
        )
    candidate_id = _required_str(plan, "candidate_id")
    replaces_candidate_id = _required_str(plan, "replaces_candidate_id")

    receipts = _receipt_index(
        tuple(snapshots[path] for path in inputs.acquisition_receipts),
        candidate_id=candidate_id,
    )
    validations = _validation_index(
        tuple(snapshots[path] for path in inputs.validations)
    )
    documents, document_bytes = _planned_documents(
        plan, receipts=receipts, candidate_id=candidate_id
    )
    replacement = mint_verified_owner_adjudicated_replacement(
        candidate_id=candidate_id,
        replaces_candidate_id=replaces_candidate_id,
        documents=documents,
        document_bytes_by_id=document_bytes,
        byte_role_validation_by_id=validations,
        docket_entries_by_number=_docket_entries(
            snapshots[inputs.docket_snapshot],
            path=inputs.docket_snapshot,
            candidate_id=candidate_id,
        ),
        case_identity=_mapping(plan.get("case_identity"), "plan case identity"),
        owner_disposition=_owner_disposition(
            snapshots[inputs.owner_disposition],
            path=inputs.owner_disposition,
            candidate_id=candidate_id,
            replaces_candidate_id=replaces_candidate_id,
        ),
        field_provenance=_mapping(plan.get("field_provenance"), "plan provenance"),
        source_commitments={
            "plan": _sha(snapshots[inputs.plan]),
            "docket_snapshot": _sha(snapshots[inputs.docket_snapshot]),
            "owner_disposition": _sha(snapshots[inputs.owner_disposition]),
            **{
                f"acquisition_receipt_{index}": _sha(snapshots[path])
                for index, path in enumerate(inputs.acquisition_receipts)
            },
            **{
                f"validation_{index}": _sha(snapshots[path])
                for index, path in enumerate(inputs.validations)
            },
        },
    )
    if any(_read(path) != payload for path, payload in snapshots.items()):
        raise OwnerAdjudicatedReplacementCliError(
            "replacement evidence inputs changed during the mint"
        )
    payloads = {
        "selection": _jsonl((replacement.selection_row,)),
        "case_relevance": _jsonl((replacement.case_relevance_row,)),
        "download_manifest": _jsonl(replacement.download_manifest),
        "clearance": _jsonl(replacement.disclosure_clearance),
        "restriction": _jsonl(replacement.restriction_evidence),
    }
    run_card = {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "stage": STAGE,
        "status": "completed",
        "dry_run": False,
        "execute": True,
        "candidate_id": replacement.candidate_id,
        "replaces_candidate_id": replacement.replaces_candidate_id,
        "record_count": len(replacement.download_manifest),
        "commitment_sha256": replacement.commitment_sha256,
        "field_provenance": dict(replacement.field_provenance),
        "input_paths": inputs.recorded(),
        "source_commitments": dict(replacement.source_commitments),
        "output_commitments": {
            **{_OUTPUTS[name]: _sha(payload) for name, payload in payloads.items()},
            **{
                relative: _sha(payload)
                for relative, payload in replacement.document_bytes.items()
            },
        },
        "output_root": str(output_root.absolute()),
        "provider_activity_requested": False,
        "provider_activity_executed": False,
        "pacer_activity_executed": False,
        "recap_fetch_activity_executed": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "evaluation_authorized": False,
        "freeze_authorized": False,
        "dispatch_authorized": False,
    }
    payloads["run_card"] = _canonical(run_card)
    return replacement, payloads


def _planned_documents(
    plan: Mapping[str, Any], *, receipts: Mapping[str, JsonMapping], candidate_id: str
) -> tuple[tuple[JsonMapping, ...], dict[str, bytes]]:
    """Corroborate every planned document against its receipt and its bytes."""

    raw = plan.get("documents")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)) or not raw:
        raise OwnerAdjudicatedReplacementCliError("replacement plan lists no documents")
    documents: list[JsonMapping] = []
    payloads: dict[str, bytes] = {}
    for item in cast(Sequence[object], raw):
        if not isinstance(item, Mapping):
            raise OwnerAdjudicatedReplacementCliError(
                "replacement plan document is malformed"
            )
        planned = cast(Mapping[str, Any], item)
        source_document_id = _required_str(planned, "source_document_id")
        receipt = receipts.get(source_document_id)
        if receipt is None:
            raise OwnerAdjudicatedReplacementCliError(
                f"replacement plan document has no acquisition receipt: "
                f"{source_document_id}"
            )
        pdf_path = Path(_required_str(receipt, "pdf_path"))
        payload = _read(pdf_path)
        digest = hashlib.sha256(payload).hexdigest()
        if digest != _required_str(receipt, "sha256").removeprefix("sha256:"):
            raise OwnerAdjudicatedReplacementCliError(
                f"replacement document bytes differ from the receipt: "
                f"{source_document_id}"
            )
        payloads[source_document_id] = payload
        documents.append(
            {
                "byte_count": len(payload),
                "candidate_id": candidate_id,
                "docket_entry_number": receipt["docket_entry_number"],
                "document_role": receipt["document_role"],
                "free_or_purchased": receipt["free_or_purchased"],
                "sha256": digest,
                "source_document_id": source_document_id,
                "source_url": receipt.get("source_url"),
            }
        )
    return tuple(documents), payloads


def _receipt_index(
    payloads: Sequence[bytes], *, candidate_id: str
) -> dict[str, JsonMapping]:
    """Normalise the repair tranches' two receipt shapes into one index."""

    index: dict[str, JsonMapping] = {}
    for payload in payloads:
        decoded = json.loads(payload)
        rows: list[Mapping[str, Any]] = []
        if isinstance(decoded, list):
            rows = [
                cast(Mapping[str, Any], row)
                for row in cast(list[object], decoded)
                if isinstance(row, Mapping)
            ]
        elif isinstance(decoded, Mapping):
            raw = cast(Mapping[str, object], decoded).get("documents")
            if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
                raise OwnerAdjudicatedReplacementCliError(
                    "acquisition receipt carries no documents"
                )
            rows = [
                cast(Mapping[str, Any], row)
                for row in cast(Sequence[object], raw)
                if isinstance(row, Mapping)
            ]
        else:
            raise OwnerAdjudicatedReplacementCliError(
                "acquisition receipt is not a supported shape"
            )
        for row in rows:
            if row.get("candidate_id") != candidate_id:
                continue
            if row.get("disposition") not in (None, "included"):
                continue
            normalised = _normalised_receipt(row)
            existing = index.get(normalised["source_document_id"])
            if existing is not None and existing != normalised:
                raise OwnerAdjudicatedReplacementCliError(
                    "acquisition receipts disagree about a document"
                )
            index[normalised["source_document_id"]] = normalised
    if not index:
        raise OwnerAdjudicatedReplacementCliError(
            "acquisition receipts cover no document for this candidate"
        )
    return index


def _normalised_receipt(row: Mapping[str, Any]) -> JsonMapping:
    digest = row.get("sha256") or row.get("pdf_sha256")
    path = row.get("path") or row.get("pdf_path")
    role = row.get("document_role") or row.get("role")
    if (
        not isinstance(digest, str)
        or not isinstance(path, str)
        or not isinstance(role, str)
    ):
        raise OwnerAdjudicatedReplacementCliError(
            "acquisition receipt row lacks a digest, path or role"
        )
    source = row.get("source")
    cost = row.get("committed_cost_usd")
    if isinstance(source, str):
        purchased = source in _PAID_ROUTES
    elif isinstance(cost, str):
        purchased = cost not in {"0.00", "0"}
    else:
        raise OwnerAdjudicatedReplacementCliError(
            "acquisition receipt row does not record its acquisition route"
        )
    entry_number = row.get("docket_entry_number")
    if type(entry_number) is not int:
        raise OwnerAdjudicatedReplacementCliError(
            "acquisition receipt row lacks a docket entry number"
        )
    return {
        "docket_entry_number": entry_number,
        "document_role": role,
        "free_or_purchased": "purchased" if purchased else "free",
        "pdf_path": path,
        "sha256": digest,
        "source_document_id": _required_str(row, "source_document_id"),
        "source_url": row.get("source_url"),
    }


def _validation_index(payloads: Sequence[bytes]) -> dict[str, JsonMapping]:
    """Normalise paid byte-role verdicts and free strict-PDF validations."""

    index: dict[str, JsonMapping] = {}
    for payload in payloads:
        decoded = json.loads(payload)
        if not isinstance(decoded, Mapping):
            raise OwnerAdjudicatedReplacementCliError(
                "validation artifact is not an object"
            )
        document = cast(Mapping[str, object], decoded)
        if "records" in document:
            for row in _sequence(document.get("records"), "validation records"):
                index[_required_str(row, "source_document_id")] = {
                    **{key: row.get(key) for key in row},
                    "validation_class": "document_repair_byte_role_verdict",
                }
            continue
        strict = document.get("strict_pdf_validation")
        visual = document.get("visual_validation")
        if not isinstance(strict, Mapping) or not isinstance(visual, Mapping):
            raise OwnerAdjudicatedReplacementCliError(
                "validation artifact is not a supported shape"
            )
        strict_record = cast(Mapping[str, object], strict)
        visual_record = cast(Mapping[str, object], visual)
        findings = document.get("role_findings")
        if (
            strict_record.get("all_pages_parsed") is not True
            or strict_record.get("all_documents_unencrypted") is not True
            or visual_record.get("result") != "pass"
            or not isinstance(findings, Mapping)
            or not findings
        ):
            raise OwnerAdjudicatedReplacementCliError(
                "free-tranche validation does not clear every document"
            )
        recorded_findings = cast(Mapping[str, object], findings)
        for row in _sequence(strict_record.get("documents"), "validation documents"):
            digest = _required_str(row, "sha256")
            source_document_id = _required_str(row, "source_document_id")
            # A synthesized "match" is only honest if the tranche actually
            # recorded a role finding for this document.  Without this the mere
            # presence of a role_findings key would promote every strictly
            # parseable PDF to a verified role.
            if not _mentions_document(recorded_findings, source_document_id):
                raise OwnerAdjudicatedReplacementCliError(
                    "free-tranche validation records no role finding for "
                    f"{source_document_id}"
                )
            index[source_document_id] = {
                "encrypted": False,
                "pdf_byte_count": row.get("byte_count"),
                "pdf_sha256": digest,
                "requested_role": row.get("role"),
                "role_verdict": "match",
                "source_document_id": source_document_id,
                "strict_parse": "pass",
                "structural_defects": [],
                "validation_class": "free_tranche_strict_pdf_and_role_findings",
            }
    if not index:
        raise OwnerAdjudicatedReplacementCliError(
            "validation artifacts carry no document records"
        )
    return index


def _mentions_document(findings: Mapping[str, object], source_document_id: str) -> bool:
    """Say whether the tranche's role findings actually cover this document.

    The shapes differ across tranches: some key findings by candidate with a
    nested evidence list naming ``document_id``, others key them directly by
    document.  Rather than guess, look for the identifier anywhere in the
    recorded findings.
    """

    if source_document_id in findings:
        return True
    return source_document_id in json.dumps(findings, sort_keys=True, default=str)


def _docket_entries(
    payload: bytes, *, path: Path, candidate_id: str
) -> dict[int, JsonMapping]:
    snapshot = _object(payload, path)
    if snapshot.get("candidate_id") != candidate_id:
        raise OwnerAdjudicatedReplacementCliError(
            "docket snapshot is for another candidate"
        )
    entries: dict[int, JsonMapping] = {}
    for entry in _sequence(snapshot.get("entries"), "docket entries"):
        number = entry.get("entry_number")
        if type(number) is not int:
            continue
        entries[number] = dict(entry)
    if not entries:
        raise OwnerAdjudicatedReplacementCliError("docket snapshot carries no entries")
    return entries


def _owner_disposition(
    payload: bytes, *, path: Path, candidate_id: str, replaces_candidate_id: str
) -> JsonMapping:
    """Select the one recorded owner swap record naming this exact pair."""

    document = _object(payload, path)
    matches = [
        dict(row)
        for row in _sequence(document.get("swaps"), "owner disposition swaps")
        if row.get("excluded_candidate_id") == replaces_candidate_id
        and row.get("replacement_candidate_id") == candidate_id
    ]
    if len(matches) != 1:
        raise OwnerAdjudicatedReplacementCliError(
            "owner disposition does not record exactly one matching swap"
        )
    return matches[0]


def _require_closed_root(
    root: Path, replacement: VerifiedOwnerAdjudicatedReplacement
) -> None:
    expected = set(_OUTPUTS.values()) | set(replacement.document_bytes)
    actual: set[str] = set()
    for path in root.rglob("*"):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise OwnerAdjudicatedReplacementCliError(
                "replacement evidence root contains a non-regular path"
            )
        if path.is_file():
            actual.add(path.relative_to(root).as_posix())
    if actual != expected:
        raise OwnerAdjudicatedReplacementCliError(
            "replacement evidence root contains unexpected paths"
        )


JsonMapping = dict[str, Any]


def _sequence(value: object, label: str) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise OwnerAdjudicatedReplacementCliError(f"{label} is malformed")
    rows: list[Mapping[str, Any]] = []
    for item in cast(Sequence[object], value):
        if not isinstance(item, Mapping):
            raise OwnerAdjudicatedReplacementCliError(f"{label} is malformed")
        rows.append(cast(Mapping[str, Any], item))
    return tuple(rows)


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise OwnerAdjudicatedReplacementCliError(f"{label} is malformed")
    return cast(Mapping[str, Any], value)


def _path_tuple(recorded: Mapping[str, object], name: str) -> tuple[Path, ...]:
    value = recorded.get(name)
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise OwnerAdjudicatedReplacementCliError(f"run card {name} is malformed")
    paths: list[Path] = []
    for item in cast(Sequence[object], value):
        if not isinstance(item, str) or not item:
            raise OwnerAdjudicatedReplacementCliError(f"run card {name} is malformed")
        paths.append(Path(item))
    return tuple(paths)


def _required_str(record: Mapping[str, Any], name: str) -> str:
    value = record.get(name)
    if not isinstance(value, str) or not value.strip():
        raise OwnerAdjudicatedReplacementCliError(f"record lacks {name}")
    return value


def _object(payload: bytes, path: Path) -> JsonMapping:
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OwnerAdjudicatedReplacementCliError(f"{path} is not JSON") from exc
    if not isinstance(value, dict):
        raise OwnerAdjudicatedReplacementCliError(f"{path} is not a JSON object")
    return cast(JsonMapping, value)


def _read(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise OwnerAdjudicatedReplacementCliError(
            f"missing regular evidence file: {path}"
        )
    return path.read_bytes()


def _write_immutable(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if _read(path) != payload:
            raise OwnerAdjudicatedReplacementCliError(
                f"immutable replacement evidence differs: {path}"
            )
        return
    path.write_bytes(payload)


def _canonical(value: object) -> bytes:
    try:
        return canonical_json_bytes(
            value,
            error_type=OwnerAdjudicatedReplacementError,
            error_message="replacement evidence serialization failed",
        )
    except OwnerAdjudicatedReplacementError as exc:
        raise OwnerAdjudicatedReplacementCliError(str(exc)) from exc


def _jsonl(rows: Sequence[Mapping[str, Any]]) -> bytes:
    return b"".join(_canonical(dict(row)) for row in rows)


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _overlaps(first: Path, second: Path) -> bool:
    left, right = Path(os.path.abspath(first)), Path(os.path.abspath(second))
    return left == right or left in right.parents or right in left.parents
