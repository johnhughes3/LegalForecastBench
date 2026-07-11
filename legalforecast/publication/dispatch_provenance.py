"""Build and validate provenance for staged official-model dispatches."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from legalforecast._hashing import is_lowercase_sha256
from legalforecast.protocol.manifest import hash_payload

DISPATCH_PROVENANCE_SCHEMA_VERSION = "legalforecast.dispatch_provenance.v1"
JsonRecord = dict[str, Any]


class DispatchProvenanceError(ValueError):
    """Raised when a staged dispatch would violate amendment provenance."""


@dataclass(frozen=True, slots=True)
class _FreezeRecord:
    path: Path
    record: Mapping[str, Any]
    bundle_sha256: str


def build_dispatch_provenance(
    *,
    current_freeze_bundle_path: str | Path,
    candidate_freeze_bundle_paths: Sequence[str | Path],
    root_path: str | Path,
    current_model_registry_path: str | Path,
    prior_dispatches: Sequence[Mapping[str, Any]],
    current_workflow_run_id: str,
    current_workflow_run_attempt: int,
    requested_model_keys: Sequence[str],
    supersedes_report_uri: str | None = None,
) -> JsonRecord:
    """Build fail-closed dispatch provenance for one original or amended freeze."""

    root = Path(root_path)
    current_path = Path(current_freeze_bundle_path)
    candidates = tuple(Path(path) for path in candidate_freeze_bundle_paths)
    if current_path not in candidates:
        candidates = (*candidates, current_path)
    records = tuple(_load_freeze_record(path) for path in candidates)
    by_sha = _unique_freeze_records(records)
    current = _load_freeze_record(current_path)
    by_sha[current.bundle_sha256] = current
    chain = _freeze_chain(current, by_sha)

    registry_keys_by_freeze: dict[str, tuple[str, ...]] = {}
    introduced_keys_by_freeze: dict[str, tuple[str, ...]] = {}
    prior_keys: set[str] = set()
    freeze_chain_records: list[JsonRecord] = []
    model_entry_freezes: list[JsonRecord] = []
    for index, freeze in enumerate(chain):
        registry_path = (
            Path(current_model_registry_path)
            if index == len(chain) - 1
            else _registry_path(freeze.record, root=root)
        )
        registry_keys = _load_registry_keys(
            registry_path,
            expected_sha256=_registry_sha256(freeze.record),
        )
        registry_key_set = set(registry_keys)
        if not prior_keys.issubset(registry_key_set):
            removed = sorted(prior_keys - registry_key_set)
            raise DispatchProvenanceError(
                f"amended registry removes prior model keys: {removed}"
            )
        introduced = tuple(sorted(registry_key_set - prior_keys))
        if index > 0 and not introduced:
            raise DispatchProvenanceError(
                "amendment freeze must introduce at least one model key"
            )
        registry_keys_by_freeze[freeze.bundle_sha256] = registry_keys
        introduced_keys_by_freeze[freeze.bundle_sha256] = introduced
        freeze_chain_records.append(
            {
                "bundle_sha256": freeze.bundle_sha256,
                "amends_bundle_sha256": _optional_sha256(
                    freeze.record,
                    "amends_bundle_sha256",
                ),
                "cycle_id": _required_str(freeze.record, "cycle_id"),
                "freeze_timestamp": _required_str(
                    freeze.record,
                    "freeze_timestamp",
                ),
                "introduced_model_keys": list(introduced),
            }
        )
        model_entry_freezes.extend(
            {
                "model_key": model_key,
                "freeze_bundle_sha256": freeze.bundle_sha256,
            }
            for model_key in introduced
        )
        prior_keys = registry_key_set

    requested = tuple(sorted(_unique_model_keys(requested_model_keys)))
    current_introduced = introduced_keys_by_freeze[current.bundle_sha256]
    if requested != current_introduced:
        raise DispatchProvenanceError(
            "requested model keys must exactly equal models introduced by the "
            f"current freeze: expected {list(current_introduced)}, got "
            f"{list(requested)}"
        )

    dispatch_records = [
        _validated_dispatch_record(
            dispatch,
            introduced_keys_by_freeze=introduced_keys_by_freeze,
        )
        for dispatch in prior_dispatches
    ]
    dispatch_records.append(
        _validated_dispatch_record(
            {
                "workflow_run_id": current_workflow_run_id,
                "workflow_run_attempt": current_workflow_run_attempt,
                "freeze_bundle_sha256": current.bundle_sha256,
                "model_keys": list(requested),
            },
            introduced_keys_by_freeze=introduced_keys_by_freeze,
        )
    )
    _require_dispatch_coverage(
        dispatch_records,
        expected_model_keys=tuple(
            sorted(registry_keys_by_freeze[current.bundle_sha256])
        ),
    )

    is_amendment = len(chain) > 1
    if is_amendment and not supersedes_report_uri:
        raise DispatchProvenanceError(
            "amendment publication requires supersedes_report_uri"
        )
    record: JsonRecord = {
        "schema_version": DISPATCH_PROVENANCE_SCHEMA_VERSION,
        "cycle_id": _required_str(current.record, "cycle_id"),
        "current_freeze_bundle_sha256": current.bundle_sha256,
        "freeze_chain": freeze_chain_records,
        "dispatches": dispatch_records,
        "model_entry_freezes": sorted(
            model_entry_freezes,
            key=lambda row: cast(str, row["model_key"]),
        ),
        "publication": {
            "mode": "additive_supersession" if is_amendment else "initial",
            "supersedes_report_uri": supersedes_report_uri if is_amendment else None,
        },
    }
    _validate_provenance_record(
        record,
        expected_cycle_id=cast(str, record["cycle_id"]),
        expected_model_keys=tuple(
            sorted(registry_keys_by_freeze[current.bundle_sha256])
        ),
    )
    return record


def load_dispatch_provenance(
    path: str | Path,
    *,
    expected_cycle_id: str,
    expected_model_keys: Sequence[str],
) -> JsonRecord:
    """Load and cross-check a staged-dispatch provenance artifact."""

    provenance_path = Path(path)
    try:
        raw: object = json.loads(provenance_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DispatchProvenanceError(
            f"could not load dispatch provenance: {provenance_path}"
        ) from exc
    if not isinstance(raw, Mapping):
        raise DispatchProvenanceError("dispatch provenance must be a JSON object")
    record = dict(cast(Mapping[str, Any], raw))
    _validate_provenance_record(
        record,
        expected_cycle_id=expected_cycle_id,
        expected_model_keys=expected_model_keys,
    )
    return record


def write_dispatch_provenance(path: str | Path, record: Mapping[str, Any]) -> Path:
    """Write a stable dispatch-provenance JSON artifact."""

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def build_parser() -> argparse.ArgumentParser:
    """Build the staged-dispatch provenance CLI parser."""

    parser = argparse.ArgumentParser(
        description=(
            "Validate an original/amended freeze chain, enforce new-model-only "
            "dispatch, and write dispatch provenance."
        )
    )
    parser.add_argument("--current-freeze-bundle", type=Path, required=True)
    parser.add_argument(
        "--candidate-freeze-bundle",
        action="append",
        type=Path,
        default=[],
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--current-model-registry", type=Path, required=True)
    parser.add_argument(
        "--prior-dispatches-json",
        default="[]",
        help="JSON array of prior dispatch records.",
    )
    parser.add_argument("--workflow-run-id", required=True)
    parser.add_argument("--workflow-run-attempt", type=int, required=True)
    parser.add_argument("--requested-model-key", action="append", default=[])
    parser.add_argument("--supersedes-report-uri")
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the dispatch-provenance CLI."""

    args = build_parser().parse_args(argv)
    prior_dispatches = _prior_dispatches_json(cast(str, args.prior_dispatches_json))
    record = build_dispatch_provenance(
        current_freeze_bundle_path=cast(Path, args.current_freeze_bundle),
        candidate_freeze_bundle_paths=cast(
            Sequence[Path],
            args.candidate_freeze_bundle,
        ),
        root_path=cast(Path, args.root),
        current_model_registry_path=cast(Path, args.current_model_registry),
        prior_dispatches=prior_dispatches,
        current_workflow_run_id=cast(str, args.workflow_run_id),
        current_workflow_run_attempt=cast(int, args.workflow_run_attempt),
        requested_model_keys=cast(Sequence[str], args.requested_model_key),
        supersedes_report_uri=cast(str | None, args.supersedes_report_uri),
    )
    output_path = write_dispatch_provenance(cast(Path, args.output), record)
    print(json.dumps({"dispatch_provenance": str(output_path)}, sort_keys=True))
    return 0


def _load_freeze_record(path: Path) -> _FreezeRecord:
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DispatchProvenanceError(f"could not load freeze bundle: {path}") from exc
    if not isinstance(raw, Mapping):
        raise DispatchProvenanceError(f"freeze bundle must be a JSON object: {path}")
    record = cast(Mapping[str, Any], raw)
    bundle_sha256 = _required_sha256(record, "hash_bundle_sha256")
    commitment = dict(record)
    del commitment["hash_bundle_sha256"]
    if hash_payload(commitment) != bundle_sha256:
        raise DispatchProvenanceError(f"freeze bundle commitment hash mismatch: {path}")
    return _FreezeRecord(path=path, record=record, bundle_sha256=bundle_sha256)


def _unique_freeze_records(
    records: Sequence[_FreezeRecord],
) -> dict[str, _FreezeRecord]:
    by_sha: dict[str, _FreezeRecord] = {}
    for record in records:
        existing = by_sha.get(record.bundle_sha256)
        if existing is not None and existing.path != record.path:
            raise DispatchProvenanceError(
                "duplicate freeze commitment appears at multiple paths: "
                f"{existing.path}, {record.path}"
            )
        by_sha[record.bundle_sha256] = record
    return by_sha


def _freeze_chain(
    current: _FreezeRecord,
    by_sha: Mapping[str, _FreezeRecord],
) -> tuple[_FreezeRecord, ...]:
    reverse_chain: list[_FreezeRecord] = []
    seen: set[str] = set()
    node = current
    cycle_id = _required_str(current.record, "cycle_id")
    while True:
        if node.bundle_sha256 in seen:
            raise DispatchProvenanceError("freeze amendment chain contains a cycle")
        seen.add(node.bundle_sha256)
        if _required_str(node.record, "cycle_id") != cycle_id:
            raise DispatchProvenanceError("freeze amendment chain changes cycle_id")
        reverse_chain.append(node)
        parent_sha = _optional_sha256(node.record, "amends_bundle_sha256")
        if parent_sha is None:
            break
        try:
            node = by_sha[parent_sha]
        except KeyError as exc:
            raise DispatchProvenanceError(
                f"freeze amendment parent is missing: {parent_sha}"
            ) from exc
    return tuple(reversed(reverse_chain))


def _registry_path(record: Mapping[str, Any], *, root: Path) -> Path:
    registry = _required_mapping(record, "model_registry")
    raw_path = _required_str(registry, "path")
    path = Path(raw_path)
    return path if path.is_absolute() else root / path


def _registry_sha256(record: Mapping[str, Any]) -> str:
    return _required_sha256(_required_mapping(record, "model_registry"), "sha256")


def _load_registry_keys(path: Path, *, expected_sha256: str) -> tuple[str, ...]:
    try:
        payload = path.read_bytes()
        raw: object = json.loads(payload)
    except (OSError, json.JSONDecodeError) as exc:
        raise DispatchProvenanceError(f"could not load model registry: {path}") from exc
    if hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise DispatchProvenanceError(f"model registry hash mismatch: {path}")
    if not isinstance(raw, list):
        raise DispatchProvenanceError("model registry must be a JSON array")
    keys: list[str] = []
    for index, item in enumerate(cast(list[object], raw)):
        if not isinstance(item, Mapping):
            raise DispatchProvenanceError(
                f"model registry entry {index} must be a JSON object"
            )
        provider = _required_str(cast(Mapping[str, Any], item), "provider")
        model_id = _required_str(cast(Mapping[str, Any], item), "model_id")
        keys.append(f"{provider}:{model_id}")
    return tuple(sorted(_unique_model_keys(keys)))


def _validated_dispatch_record(
    raw: Mapping[str, Any],
    *,
    introduced_keys_by_freeze: Mapping[str, Sequence[str]],
) -> JsonRecord:
    workflow_run_id = _required_str(raw, "workflow_run_id")
    workflow_run_attempt = _required_int(raw, "workflow_run_attempt", minimum=1)
    freeze_sha = _required_sha256(raw, "freeze_bundle_sha256")
    if freeze_sha not in introduced_keys_by_freeze:
        raise DispatchProvenanceError(
            f"dispatch references freeze outside the chain: {freeze_sha}"
        )
    model_keys = tuple(sorted(_string_sequence(raw, "model_keys")))
    if not model_keys:
        raise DispatchProvenanceError("dispatch model_keys must not be empty")
    allowed = set(introduced_keys_by_freeze[freeze_sha])
    invalid = sorted(set(model_keys) - allowed)
    if invalid:
        raise DispatchProvenanceError(
            f"dispatch contains models not introduced by its freeze: {invalid}"
        )
    return {
        "workflow_run_id": workflow_run_id,
        "workflow_run_attempt": workflow_run_attempt,
        "freeze_bundle_sha256": freeze_sha,
        "model_keys": list(model_keys),
    }


def _require_dispatch_coverage(
    dispatches: Sequence[Mapping[str, Any]],
    *,
    expected_model_keys: Sequence[str],
) -> None:
    covered = {
        model_key
        for dispatch in dispatches
        for model_key in _string_sequence(dispatch, "model_keys")
    }
    missing = sorted(set(expected_model_keys) - covered)
    if missing:
        raise DispatchProvenanceError(
            f"dispatch provenance does not cover model keys: {missing}"
        )


def _validate_provenance_record(
    record: Mapping[str, Any],
    *,
    expected_cycle_id: str,
    expected_model_keys: Sequence[str],
) -> None:
    if _required_str(record, "schema_version") != DISPATCH_PROVENANCE_SCHEMA_VERSION:
        raise DispatchProvenanceError("unsupported dispatch provenance schema_version")
    if _required_str(record, "cycle_id") != expected_cycle_id:
        raise DispatchProvenanceError("dispatch provenance cycle_id mismatch")
    current_sha = _required_sha256(record, "current_freeze_bundle_sha256")
    chain = _mapping_sequence(record, "freeze_chain")
    if not chain:
        raise DispatchProvenanceError("freeze_chain must not be empty")
    chain_hashes: list[str] = []
    introduced_by_sha: dict[str, tuple[str, ...]] = {}
    prior_sha: str | None = None
    for index, node in enumerate(chain):
        sha = _required_sha256(node, "bundle_sha256")
        amends = _optional_sha256(node, "amends_bundle_sha256")
        if index == 0 and amends is not None:
            raise DispatchProvenanceError(
                "freeze_chain must begin at an original freeze"
            )
        if index > 0 and amends != prior_sha:
            raise DispatchProvenanceError("freeze_chain is not contiguous")
        if _required_str(node, "cycle_id") != expected_cycle_id:
            raise DispatchProvenanceError("freeze_chain cycle_id mismatch")
        _required_str(node, "freeze_timestamp")
        introduced_by_sha[sha] = tuple(
            sorted(_string_sequence(node, "introduced_model_keys"))
        )
        chain_hashes.append(sha)
        prior_sha = sha
    if chain_hashes[-1] != current_sha:
        raise DispatchProvenanceError("current freeze is not the end of freeze_chain")

    model_entry_freezes = _mapping_sequence(record, "model_entry_freezes")
    model_mapping: dict[str, str] = {}
    for item in model_entry_freezes:
        model_key = _required_str(item, "model_key")
        freeze_sha = _required_sha256(item, "freeze_bundle_sha256")
        if model_key in model_mapping:
            raise DispatchProvenanceError(
                f"duplicate model_entry_freezes model_key: {model_key}"
            )
        if model_key not in introduced_by_sha.get(freeze_sha, ()):
            raise DispatchProvenanceError(
                f"model entry freeze does not introduce {model_key}"
            )
        model_mapping[model_key] = freeze_sha
    expected = set(_unique_model_keys(expected_model_keys))
    if set(model_mapping) != expected:
        raise DispatchProvenanceError(
            "model_entry_freezes does not match expected registry model set"
        )

    dispatches = _mapping_sequence(record, "dispatches")
    validated_dispatches = [
        _validated_dispatch_record(
            dispatch,
            introduced_keys_by_freeze=introduced_by_sha,
        )
        for dispatch in dispatches
    ]
    _require_dispatch_coverage(
        validated_dispatches,
        expected_model_keys=tuple(sorted(expected)),
    )

    publication = _required_mapping(record, "publication")
    mode = _required_str(publication, "mode")
    expected_mode = "additive_supersession" if len(chain) > 1 else "initial"
    if mode != expected_mode:
        raise DispatchProvenanceError(
            f"publication mode must be {expected_mode} for this freeze chain"
        )
    supersedes = publication.get("supersedes_report_uri")
    if expected_mode == "additive_supersession":
        if not isinstance(supersedes, str) or not supersedes.strip():
            raise DispatchProvenanceError(
                "additive supersession requires supersedes_report_uri"
            )
    elif supersedes is not None:
        raise DispatchProvenanceError(
            "initial publication must not set supersedes_report_uri"
        )


def _prior_dispatches_json(value: str) -> tuple[Mapping[str, Any], ...]:
    try:
        raw: object = json.loads(value)
    except json.JSONDecodeError as exc:
        raise DispatchProvenanceError("prior_dispatches_json is invalid JSON") from exc
    if not isinstance(raw, list):
        raise DispatchProvenanceError("prior_dispatches_json must be a JSON array")
    records: list[Mapping[str, Any]] = []
    for index, item in enumerate(cast(list[object], raw)):
        if not isinstance(item, Mapping):
            raise DispatchProvenanceError(
                f"prior dispatch {index} must be a JSON object"
            )
        records.append(cast(Mapping[str, Any], item))
    return tuple(records)


def _unique_model_keys(values: Sequence[str]) -> tuple[str, ...]:
    keys: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not value.strip() or ":" not in value:
            raise DispatchProvenanceError(
                "model keys must be non-empty provider:model_id strings"
            )
        key = value.strip()
        if key in seen:
            raise DispatchProvenanceError(f"duplicate model key: {key}")
        seen.add(key)
        keys.append(key)
    return tuple(keys)


def _required_mapping(
    record: Mapping[str, Any],
    field_name: str,
) -> Mapping[str, Any]:
    value = record.get(field_name)
    if not isinstance(value, Mapping):
        raise DispatchProvenanceError(f"{field_name} must be a JSON object")
    return cast(Mapping[str, Any], value)


def _mapping_sequence(
    record: Mapping[str, Any],
    field_name: str,
) -> tuple[Mapping[str, Any], ...]:
    value = record.get(field_name)
    if not isinstance(value, list):
        raise DispatchProvenanceError(f"{field_name} must be a JSON array")
    result: list[Mapping[str, Any]] = []
    for index, item in enumerate(cast(list[object], value)):
        if not isinstance(item, Mapping):
            raise DispatchProvenanceError(
                f"{field_name}[{index}] must be a JSON object"
            )
        result.append(cast(Mapping[str, Any], item))
    return tuple(result)


def _string_sequence(
    record: Mapping[str, Any],
    field_name: str,
) -> tuple[str, ...]:
    value = record.get(field_name)
    if not isinstance(value, list):
        raise DispatchProvenanceError(f"{field_name} must be a JSON array")
    strings: list[str] = []
    for index, item in enumerate(cast(list[object], value)):
        if not isinstance(item, str) or not item.strip():
            raise DispatchProvenanceError(
                f"{field_name}[{index}] must be a non-empty string"
            )
        strings.append(item)
    return _unique_model_keys(strings)


def _required_str(record: Mapping[str, Any], field_name: str) -> str:
    value = record.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise DispatchProvenanceError(f"{field_name} must be a non-empty string")
    return value


def _required_int(
    record: Mapping[str, Any],
    field_name: str,
    *,
    minimum: int,
) -> int:
    value = record.get(field_name)
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise DispatchProvenanceError(f"{field_name} must be an integer >= {minimum}")
    return value


def _required_sha256(record: Mapping[str, Any], field_name: str) -> str:
    value = _required_str(record, field_name)
    if not is_lowercase_sha256(value):
        raise DispatchProvenanceError(
            f"{field_name} must be a lowercase SHA-256 digest"
        )
    return value


def _optional_sha256(
    record: Mapping[str, Any],
    field_name: str,
) -> str | None:
    value = record.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str) or not is_lowercase_sha256(value):
        raise DispatchProvenanceError(
            f"{field_name} must be null or a lowercase SHA-256 digest"
        )
    return value


if __name__ == "__main__":
    raise SystemExit(main())
