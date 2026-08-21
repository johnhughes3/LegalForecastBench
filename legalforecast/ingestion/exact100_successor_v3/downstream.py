"""Downstream projection re-verifier for a v3 exact-100 cohort root.

Every earlier successor generation ships one of these, and the materialization
and parse stages read a cohort root only through it.  v3 shipped none, so a v3
root -- however well it authenticates itself -- is unreadable downstream: the
consumers look for a target-cohort run card that a v3 root does not have, and
fail on the missing file before any schema dispatch is reached.

Two questions are kept apart here, because conflating them is what makes this
kind of verifier weak:

*Authentication* asks whether the root was produced by the run it claims.  That
is a replay of every input root, recursing to a sealed cohort head whose digest
is pinned in code, and it already exists in this package.  It is injected
rather than imported so that the publication surface below can be exercised
without that sealed head, and so a caller cannot accidentally get publication
without authentication -- there is no default that skips it.

*Publication* asks whether the bytes on disk are the ones the run card commits,
and reshapes them into what downstream expects.  Two things matter in the
reshaping.  The v3 root stores one merged download manifest where downstream
consumes free and purchased separately, so the split happens here and a row of
any other phase refuses rather than silently vanishing from both halves.  And
the run card commits the promoted candidates' own PDFs alongside the cohort
surface files; those are the evidence each promotion rests on, so they are
verified too.  A verifier that checked only the surface files would report a
root whose purchased documents had been replaced as sound.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from legalforecast.contracts import EXACT100_SUCCESSOR_REPLACEMENT_STATE_V3

STATE_SCHEMA_VERSION = str(EXACT100_SUCCESSOR_REPLACEMENT_STATE_V3)
STAGE = "project-exact100-successor-replacement-v3"
REQUIRED_CASE_COUNT = 100

#: Relative paths of the cohort surface a v3 root publishes, by the role name
#: downstream knows them by.  This mirrors the emitter's own output map; the
#: two are pinned together by a test rather than shared, because the emitter's
#: copy is what the run card's commitments are keyed on.
OUTPUT_NAMES: Mapping[str, str] = {
    "selection": "target-cohort-selection.jsonl",
    "config": "target-cohort-projection.json",
    "case_relevance": "case-relevance.jsonl",
    "download_manifest": "document-downloads-merged.jsonl",
    "clearance": "disclosure-clearance.jsonl",
    "restriction": "restriction-evidence.jsonl",
    "core_filter": "core-filter-results.jsonl",
    "terminal_exclusions": "successor-terminal-exclusions.jsonl",
    "promotions": "successor-promotions.jsonl",
    "methods_disclosure": "methods-disclosure.json",
    "state": "run-cards/project-exact100-successor-replacement-v3.json",
}

_PHASES = frozenset({"free", "purchased"})


@dataclass(frozen=True, slots=True)
class AuthenticatedV3Root:
    """Receipt that a specific root was replayed, returned by the hook.

    The hook returns a receipt rather than ``None`` so that "did not
    authenticate" is a state this module can detect.  An unconstrained hook
    accepts a no-op happily -- it type-checks, the tests pass, and publication
    proceeds on a root nothing replayed -- and the receipt is what closes that.
    Naming the root makes a receipt non-transferable between roots.
    """

    root: Path
    anchor_root: Path | None = None


#: Called with the root under verification; must replay it and return an
#: :class:`AuthenticatedV3Root` naming that same root, or raise.  Typed as
#: returning ``object`` deliberately: the hook is injected across a trust
#: boundary by callers this module does not type-check, so the return value is
#: narrowed at runtime rather than assumed.  Annotating the contract instead
#: would make that check look redundant and invite its removal.
Authenticate = Callable[[Path], object]


class Exact100SuccessorV3DownstreamError(ValueError):
    """Raised when a v3 cohort root cannot be published downstream."""


def is_exact100_successor_v3_root(root: Path) -> bool:
    """Whether this root carries a v3 state run card.

    The probe is file existence rather than a schema read, because that is the
    shape of the failure: a v3 root has no target-cohort run card at all, so a
    consumer dispatching on schema never gets far enough to look at one.
    """

    return (root / OUTPUT_NAMES["state"]).is_file()


def verify_exact100_successor_replacement_v3_projection(
    target_root: Path, *, authenticate: Authenticate
) -> dict[str, Any]:
    """Authenticate a v3 cohort root and publish its downstream surface."""

    card_path = target_root / OUTPUT_NAMES["state"]
    if not card_path.is_file():
        raise Exact100SuccessorV3DownstreamError(
            f"target cohort root carries no v3 state run card: {target_root}"
        )
    card_bytes = _read(card_path)
    card = _object(card_bytes, card_path)
    if (
        card.get("schema_version") != STATE_SCHEMA_VERSION
        or card.get("stage") != STAGE
        or card.get("status") != "completed"
        or card.get("selected_case_count") != REQUIRED_CASE_COUNT
    ):
        raise Exact100SuccessorV3DownstreamError(
            f"target cohort root is not a completed v3 projection: {target_root}"
        )

    # Authentication first: nothing below should read a root that does not
    # replay, and no code path here can reach publication without this call.
    # The receipt has to name this root -- a hook that returns nothing, or a
    # receipt for some other root, has not authenticated the one being read.
    receipt = authenticate(target_root)
    if not isinstance(receipt, AuthenticatedV3Root) or (
        receipt.root.resolve() != target_root.resolve()
    ):
        raise Exact100SuccessorV3DownstreamError(
            f"v3 cohort root did not authenticate: {target_root}"
        )

    commitments = _mapping(card.get("output_commitments"), "v3 output commitments")
    payloads = {
        name: _committed_bytes(target_root, relative, commitments)
        for name, relative in OUTPUT_NAMES.items()
        if relative != OUTPUT_NAMES["state"]
    }
    payloads["state"] = card_bytes
    # Everything the card commits that is not a surface file is a promoted
    # candidate's own document, and it is verified for exactly that reason.
    surface = set(OUTPUT_NAMES.values())
    documents = {
        relative: _committed_bytes(target_root, relative, commitments)
        for relative in sorted(commitments)
        if relative not in surface
    }

    manifest = _jsonl(payloads["download_manifest"], OUTPUT_NAMES["download_manifest"])
    clearance = _jsonl(payloads["clearance"], OUTPUT_NAMES["clearance"])
    for row in manifest:
        if row.get("free_or_purchased") not in _PHASES:
            raise Exact100SuccessorV3DownstreamError(
                "completed v3 successor manifest has invalid phase"
            )

    manifest_by_key = _index(manifest, "v3 download manifest")
    clearance_by_key = _index(clearance, "v3 disclosure clearance")
    if set(clearance_by_key) != set(manifest_by_key):
        raise Exact100SuccessorV3DownstreamError(
            "completed v3 successor clearance coverage differs"
        )
    free_keys = {
        key
        for key, row in manifest_by_key.items()
        if row.get("free_or_purchased") == "free"
    }
    purchased_keys = set(manifest_by_key) - free_keys
    verified_document_bytes = {
        str((target_root / relative).absolute()): payload
        for relative, payload in documents.items()
    }

    return {
        "run_card": card,
        "run_card_bytes": card_bytes,
        "summary": _object(payloads["config"], target_root / OUTPUT_NAMES["config"]),
        "summary_path": target_root / OUTPUT_NAMES["config"],
        "run_card_path": card_path,
        "selection_path": target_root / OUTPUT_NAMES["selection"],
        "selection_bytes": payloads["selection"],
        "selection_records": _jsonl(payloads["selection"], OUTPUT_NAMES["selection"]),
        "free_manifest_path": target_root / OUTPUT_NAMES["download_manifest"],
        "free_manifest": tuple(manifest_by_key[key] for key in sorted(free_keys)),
        "purchased_manifest": tuple(
            manifest_by_key[key] for key in sorted(purchased_keys)
        ),
        "case_relevance": _jsonl(
            payloads["case_relevance"], OUTPUT_NAMES["case_relevance"]
        ),
        "free_clearance": tuple(clearance_by_key[key] for key in sorted(free_keys)),
        "purchased_clearance": tuple(
            clearance_by_key[key] for key in sorted(purchased_keys)
        ),
        "restriction_path": target_root / OUTPUT_NAMES["restriction"],
        "restriction_records": _jsonl(
            payloads["restriction"], OUTPUT_NAMES["restriction"]
        ),
        "selected_document_keys": {
            (_text(row, "candidate_id"), _text(row, "source_document_id"))
            for row in manifest
        },
        "verified_artifact_bytes": {
            str((target_root / relative).absolute()): payloads[name]
            for name, relative in OUTPUT_NAMES.items()
        }
        | verified_document_bytes,
        "anchor_root": receipt.anchor_root,
        # Published separately from the cohort surface so a caller can hold the
        # promoted evidence to the same intra-operation coherence checks as the
        # surface files, rather than verifying it once and then forgetting it.
        "verified_document_bytes": verified_document_bytes,
    }


def _index(
    rows: Sequence[Mapping[str, Any]], label: str
) -> dict[tuple[str, str], Mapping[str, Any]]:
    result: dict[tuple[str, str], Mapping[str, Any]] = {}
    for row in rows:
        key = (_text(row, "candidate_id"), _text(row, "source_document_id"))
        if key in result:
            raise Exact100SuccessorV3DownstreamError(f"{label} repeats {key}")
        result[key] = row
    return result


def _committed_bytes(
    root: Path, relative: str, commitments: Mapping[str, Any]
) -> bytes:
    """Read one committed file and re-derive its digest from the bytes read."""

    relative_path = Path(relative)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise Exact100SuccessorV3DownstreamError(
            f"v3 output commitment path is unsafe: {relative}"
        )
    expected = commitments.get(relative)
    if not isinstance(expected, str) or not expected:
        raise Exact100SuccessorV3DownstreamError(
            f"v3 run card commits no digest for {relative}"
        )
    path = root / relative
    if not path.is_file():
        raise Exact100SuccessorV3DownstreamError(
            f"v3 committed output is missing: {relative}"
        )
    payload = path.read_bytes()
    if f"sha256:{hashlib.sha256(payload).hexdigest()}" != expected:
        raise Exact100SuccessorV3DownstreamError(
            f"v3 committed output differs from its commitment: {relative}"
        )
    return payload


def _read(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as error:
        raise Exact100SuccessorV3DownstreamError(
            f"v3 cohort root input is unreadable: {path}"
        ) from error


def _object(payload: bytes, path: Path) -> dict[str, Any]:
    try:
        value = json.loads(payload)
    except ValueError as error:
        raise Exact100SuccessorV3DownstreamError(
            f"v3 cohort root artifact is not valid JSON: {path}"
        ) from error
    if not isinstance(value, dict):
        raise Exact100SuccessorV3DownstreamError(
            f"v3 cohort root artifact is not a JSON object: {path}"
        )
    return cast(dict[str, Any], value)


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise Exact100SuccessorV3DownstreamError(f"{label} is not a JSON object")
    return cast(Mapping[str, Any], value)


def _jsonl(payload: bytes, label: str) -> tuple[Mapping[str, Any], ...]:
    rows: list[Mapping[str, Any]] = []
    for index, line in enumerate(payload.decode("utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except ValueError as error:
            raise Exact100SuccessorV3DownstreamError(
                f"v3 cohort root record is not valid JSON: {label} line {index}"
            ) from error
        if not isinstance(value, Mapping):
            raise Exact100SuccessorV3DownstreamError(
                f"v3 cohort root record is not a JSON object: {label} line {index}"
            )
        rows.append(cast(Mapping[str, Any], value))
    return tuple(rows)


def _text(record: Mapping[str, Any], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value:
        raise Exact100SuccessorV3DownstreamError(
            f"v3 cohort root record field is empty: {field}"
        )
    return value
