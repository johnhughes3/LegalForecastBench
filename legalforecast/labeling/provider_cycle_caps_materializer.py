"""Provider-free construction of an authority-enabled provider-caps successor."""

from __future__ import annotations

import ctypes
import errno
import hashlib
import json
import os
import secrets
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType
from typing import cast

from legalforecast.labeling.provider_journal import (
    PROVIDER_CYCLE_CAPS_SCHEMA_VERSION,
    ProviderJournalError,
    load_provider_cycle_caps_bytes,
)

AUTHORITY_SMOKE_SCHEMA_VERSION = "legalforecast.official_labeling_authority_smoke.v1"
SUCCESSOR_POLICY_SCHEMA_VERSION = (
    "legalforecast.provider_cycle_caps_successor_policy.v1"
)
SUCCESSOR_RECEIPT_SCHEMA_VERSION = (
    "legalforecast.provider_cycle_caps_successor_receipt.v1"
)
SUCCESSOR_STAGE = "materialize-provider-cycle-caps-successor"
SUCCESSOR_CAPS_NAME = "provider-cycle-caps.json"
SUCCESSOR_RECEIPT_NAME = "provider-cycle-caps-successor-receipt.json"
SUCCESSOR_RUN_CARD_NAME = f"{SUCCESSOR_STAGE}.json"

_SHA256_LENGTH = 64
_RELEASE_SHA_LENGTH = 40
_SMOKE_FIELDS = frozenset(
    {
        "schema_version",
        "release_sha",
        "authority_resource_identity_sha256",
        "provider_call_made",
        "allowed",
        "denied",
    }
)
_ALLOWED_FIELDS = frozenset(
    {
        "describe_table",
        "describe_time_to_live",
        "get_item",
        "put_item",
        "update_item",
        "condition_check_item",
        "transact_write_items",
    }
)
_DENIED_FIELDS = frozenset(
    {
        "scan",
        "delete_item",
        "outside_table_describe",
        "outside_table_get_item",
        "outside_table_put_item",
        "outside_table_update_item",
        "outside_table_transact_write_items",
        "list_tables",
    }
)
_POLICY_FIELDS = frozenset(
    {"schema_version", "cycle_id", "provider_accounts", "spend_authority"}
)
_AUTHORITY_POLICY_FIELDS = frozenset(
    {
        "backend",
        "ledger_scope_fields",
        "max_billable_attempts",
        "failure_threshold",
        "failure_window_seconds",
    }
)
_ACCOUNT_FIELDS = frozenset({"provider", "account"})
_ROOT_ENTRIES = frozenset({SUCCESSOR_CAPS_NAME, SUCCESSOR_RECEIPT_NAME, "run-cards"})
_RUN_CARD_ENTRIES = frozenset({SUCCESSOR_RUN_CARD_NAME})
_STABLE_STAT_FIELDS = (
    "st_dev",
    "st_ino",
    "st_mode",
    "st_nlink",
    "st_size",
    "st_mtime_ns",
    "st_ctime_ns",
)


class ProviderCycleCapsMaterializationError(RuntimeError):
    """Raised when immutable inputs cannot produce one safe successor."""


@dataclass(frozen=True, slots=True)
class _VerifiedAuthoritySmoke:
    """Authenticated public identity recovered from the exact smoke bytes."""

    byte_count: int
    sha256: str
    release_sha: str
    resource_identity_sha256: str


@dataclass(frozen=True, slots=True)
class _ProviderCycleCapsSuccessorPolicy:
    """Canonical public aliases and breaker limits for one successor."""

    byte_count: int
    sha256: str
    cycle_id: str
    provider_accounts: Mapping[str, str]
    max_billable_attempts: int
    failure_threshold: int
    failure_window_seconds: int


@dataclass(frozen=True, slots=True)
class MaterializedProviderCycleCaps:
    """Deterministic caps bytes and their public lineage receipt."""

    caps_bytes: bytes
    caps_sha256: str
    receipt: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class PublishedProviderCycleCapsSuccessor:
    """Exact paths and commitments published by the supported CLI."""

    caps_path: Path
    receipt_path: Path
    run_card_path: Path
    caps_sha256: str
    receipt_sha256: str
    run_card_sha256: str


@dataclass(frozen=True, slots=True)
class _InputSnapshot:
    path: Path
    label: str
    payload: bytes
    stat_identity: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class _OutputTreeState:
    exists: bool
    root_identity: tuple[int, ...] | None
    run_cards_identity: tuple[int, ...] | None
    caps_identity: tuple[int, ...] | None
    receipt_identity: tuple[int, ...] | None
    run_card_identity: tuple[int, ...] | None
    missing: frozenset[str]


@dataclass(frozen=True, slots=True)
class _StagedOutputTree:
    name: str
    state: _OutputTreeState


def verify_official_labeling_authority_smoke(
    payload: bytes,
    *,
    expected_sha256: str,
    expected_release_sha: str,
) -> _VerifiedAuthoritySmoke:
    """Verify the complete provider-free smoke contract from exact raw bytes."""

    smoke_sha256 = hashlib.sha256(payload).hexdigest()
    if smoke_sha256 != _digest(expected_sha256, "authority-smoke SHA-256"):
        raise ProviderCycleCapsMaterializationError(
            "authority-smoke raw bytes differ from the expected SHA-256"
        )
    release_sha = _release_sha(expected_release_sha, "expected smoke release SHA")
    record = _json_object(payload, "authority-smoke receipt")
    _exact_fields(record, _SMOKE_FIELDS, "authority-smoke receipt")
    if record["schema_version"] != AUTHORITY_SMOKE_SCHEMA_VERSION:
        raise ProviderCycleCapsMaterializationError(
            "authority-smoke receipt schema_version differs"
        )
    actual_release = _release_sha(record["release_sha"], "authority-smoke release_sha")
    if actual_release != release_sha:
        raise ProviderCycleCapsMaterializationError(
            "authority-smoke release_sha differs from the expected release"
        )
    identity = _digest(
        record["authority_resource_identity_sha256"],
        "authority-smoke resource identity SHA-256",
    )
    if record["provider_call_made"] is not False:
        raise ProviderCycleCapsMaterializationError(
            "authority-smoke receipt must prove provider_call_made=false"
        )
    _true_boolean_table(record["allowed"], _ALLOWED_FIELDS, "allowed operations")
    _true_boolean_table(record["denied"], _DENIED_FIELDS, "denied operations")
    return _VerifiedAuthoritySmoke(
        byte_count=len(payload),
        sha256=smoke_sha256,
        release_sha=actual_release,
        resource_identity_sha256=identity,
    )


def load_provider_cycle_caps_successor_policy(
    payload: bytes,
    *,
    expected_sha256: str,
) -> _ProviderCycleCapsSuccessorPolicy:
    """Load one exact canonical public alias and authority policy artifact."""

    policy_sha256 = hashlib.sha256(payload).hexdigest()
    if policy_sha256 != _digest(expected_sha256, "provider policy SHA-256"):
        raise ProviderCycleCapsMaterializationError(
            "provider policy raw bytes differ from the expected SHA-256"
        )
    record = _json_object(payload, "provider caps successor policy")
    _exact_fields(record, _POLICY_FIELDS, "provider caps successor policy")
    if record["schema_version"] != SUCCESSOR_POLICY_SCHEMA_VERSION:
        raise ProviderCycleCapsMaterializationError(
            "provider caps successor policy schema_version differs"
        )
    if canonical_json_bytes(record) != payload:
        raise ProviderCycleCapsMaterializationError(
            "provider caps successor policy must use canonical JSON bytes"
        )
    cycle_id = _nonempty_text(record["cycle_id"], "provider policy cycle_id")
    raw_accounts = record["provider_accounts"]
    if not isinstance(raw_accounts, list) or not raw_accounts:
        raise ProviderCycleCapsMaterializationError(
            "provider policy provider_accounts must be a non-empty list"
        )
    accounts: dict[str, str] = {}
    for index, raw_account in enumerate(cast(list[object], raw_accounts)):
        if not isinstance(raw_account, Mapping):
            raise ProviderCycleCapsMaterializationError(
                f"provider policy provider_accounts[{index}] must be an object"
            )
        account_record = cast(Mapping[str, object], raw_account)
        _exact_fields(
            account_record,
            _ACCOUNT_FIELDS,
            f"provider policy provider_accounts[{index}]",
        )
        provider = _lower_identifier(
            account_record["provider"],
            f"provider policy provider_accounts[{index}].provider",
        )
        account = _nonempty_text(
            account_record["account"],
            f"provider policy provider_accounts[{index}].account",
        )
        if provider in accounts:
            raise ProviderCycleCapsMaterializationError(
                f"provider policy contains duplicate provider {provider!r}"
            )
        accounts[provider] = account
    if list(accounts) != sorted(accounts):
        raise ProviderCycleCapsMaterializationError(
            "provider policy provider_accounts must be sorted by provider"
        )
    authority = record["spend_authority"]
    if not isinstance(authority, Mapping):
        raise ProviderCycleCapsMaterializationError(
            "provider policy spend_authority must be an object"
        )
    authority_record = cast(Mapping[str, object], authority)
    _exact_fields(
        authority_record,
        _AUTHORITY_POLICY_FIELDS,
        "provider policy spend_authority",
    )
    if authority_record["backend"] != "dynamodb":
        raise ProviderCycleCapsMaterializationError(
            "provider policy spend_authority.backend must be dynamodb"
        )
    if authority_record["ledger_scope_fields"] != [
        "cycle_id",
        "provider",
        "account",
    ]:
        raise ProviderCycleCapsMaterializationError(
            "provider policy ledger_scope_fields differ"
        )
    return _ProviderCycleCapsSuccessorPolicy(
        byte_count=len(payload),
        sha256=policy_sha256,
        cycle_id=cycle_id,
        provider_accounts=MappingProxyType(accounts),
        max_billable_attempts=_positive_integer(
            authority_record["max_billable_attempts"], "max_billable_attempts"
        ),
        failure_threshold=_positive_integer(
            authority_record["failure_threshold"], "failure_threshold"
        ),
        failure_window_seconds=_positive_integer(
            authority_record["failure_window_seconds"], "failure_window_seconds"
        ),
    )


def _materialize_provider_cycle_caps_successor(
    source_bytes: bytes,
    *,
    expected_source_sha256: str,
    authority_smoke: _VerifiedAuthoritySmoke,
    policy: _ProviderCycleCapsSuccessorPolicy,
) -> MaterializedProviderCycleCaps:
    """Derive one closed authority-enabled caps artifact without I/O."""

    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    expected_sha256 = _digest(expected_source_sha256, "expected source SHA-256")
    if source_sha256 != expected_sha256:
        raise ProviderCycleCapsMaterializationError(
            "provider cycle caps source SHA-256 differs from the expected digest"
        )
    _digest(authority_smoke.sha256, "verified authority-smoke SHA-256")
    _release_sha(authority_smoke.release_sha, "verified authority-smoke release SHA")
    _digest(
        authority_smoke.resource_identity_sha256,
        "verified authority-smoke resource identity SHA-256",
    )
    _digest(policy.sha256, "verified provider policy SHA-256")
    if authority_smoke.byte_count <= 0 or policy.byte_count <= 0:
        raise ProviderCycleCapsMaterializationError(
            "verified authority-smoke and provider policy byte counts must be positive"
        )
    _positive_integer(policy.max_billable_attempts, "max_billable_attempts")
    _positive_integer(policy.failure_threshold, "failure_threshold")
    _positive_integer(policy.failure_window_seconds, "failure_window_seconds")
    _json_object(source_bytes, "legacy provider cycle caps")
    try:
        source_caps = load_provider_cycle_caps_bytes(
            source_bytes,
            source="immutable legacy provider-cycle-caps",
        )
    except ProviderJournalError as exc:
        raise ProviderCycleCapsMaterializationError(
            f"legacy provider cycle caps are invalid: {exc}"
        ) from exc
    if source_caps.spend_authority is not None or any(
        cap.account is not None
        or cap.external_spend_limit_usd is not None
        or cap.external_limit_scope is not None
        or cap.external_limit_source is not None
        or cap.verified_at is not None
        for cap in source_caps.providers.values()
    ):
        raise ProviderCycleCapsMaterializationError(
            "legacy caps source must omit authority, accounts, and annotations"
        )
    if policy.cycle_id != source_caps.cycle_id:
        raise ProviderCycleCapsMaterializationError(
            "provider policy cycle_id differs from the immutable source"
        )
    if set(policy.provider_accounts) != set(source_caps.providers):
        raise ProviderCycleCapsMaterializationError(
            "provider account aliases differ from the immutable source provider set"
        )

    authority: dict[str, object] = {
        "backend": "dynamodb",
        "failure_threshold": policy.failure_threshold,
        "failure_window_seconds": policy.failure_window_seconds,
        "ledger_scope_fields": ["cycle_id", "provider", "account"],
        "max_billable_attempts": policy.max_billable_attempts,
        "resource_identity_sha256": authority_smoke.resource_identity_sha256,
    }
    providers: list[dict[str, object]] = [
        {
            "account": policy.provider_accounts[provider],
            "cycle_reservation_cap_usd": _decimal_text(
                source_caps.providers[provider].cycle_reservation_cap_usd
            ),
            "provider": provider,
        }
        for provider in sorted(source_caps.providers)
    ]
    successor: dict[str, object] = {
        "cycle_id": source_caps.cycle_id,
        "providers": providers,
        "schema_version": PROVIDER_CYCLE_CAPS_SCHEMA_VERSION,
        "spend_authority": authority,
    }
    caps_bytes = canonical_json_bytes(successor)
    try:
        validated = load_provider_cycle_caps_bytes(
            caps_bytes,
            source="materialized provider-cycle-caps successor",
        )
        validated.require_spend_authority()
        for provider in sorted(validated.providers):
            validated.account(provider)
            validated.cap_microusd(provider)
    except ProviderJournalError as exc:
        raise ProviderCycleCapsMaterializationError(
            f"materialized provider cycle caps are invalid: {exc}"
        ) from exc

    caps_sha256 = hashlib.sha256(caps_bytes).hexdigest()
    receipt: dict[str, object] = {
        "schema_version": SUCCESSOR_RECEIPT_SCHEMA_VERSION,
        "status": "complete",
        "cycle_id": source_caps.cycle_id,
        "source": {
            "bytes": len(source_bytes),
            "schema_version": PROVIDER_CYCLE_CAPS_SCHEMA_VERSION,
            "sha256": source_sha256,
        },
        "authority_smoke": {
            "bytes": authority_smoke.byte_count,
            "release_sha": authority_smoke.release_sha,
            "schema_version": AUTHORITY_SMOKE_SCHEMA_VERSION,
            "sha256": authority_smoke.sha256,
        },
        "policy": {
            "bytes": policy.byte_count,
            "schema_version": SUCCESSOR_POLICY_SCHEMA_VERSION,
            "sha256": policy.sha256,
        },
        "successor": {
            "bytes": len(caps_bytes),
            "schema_version": PROVIDER_CYCLE_CAPS_SCHEMA_VERSION,
            "sha256": caps_sha256,
        },
        "spend_authority": authority,
        "provider_account_caps": providers,
    }
    return MaterializedProviderCycleCaps(
        caps_bytes=caps_bytes,
        caps_sha256=caps_sha256,
        receipt=receipt,
    )


def materialize_provider_cycle_caps_successor_files(
    *,
    legacy_caps_path: Path,
    expected_legacy_caps_sha256: str,
    authority_smoke_path: Path,
    expected_authority_smoke_sha256: str,
    expected_smoke_release_sha: str,
    policy_path: Path,
    expected_policy_sha256: str,
    output_root: Path,
) -> PublishedProviderCycleCapsSuccessor:
    """Validate immutable evidence, then publish or exactly resume three outputs."""

    legacy_path = _canonical_input_path(legacy_caps_path, "legacy caps input")
    smoke_path = _canonical_input_path(authority_smoke_path, "authority-smoke input")
    canonical_policy_path = _canonical_input_path(policy_path, "provider policy input")
    target_root = _canonical_output_root(output_root)
    immutable_inputs = (legacy_path, smoke_path, canonical_policy_path)
    if len(set(immutable_inputs)) != len(immutable_inputs):
        raise ProviderCycleCapsMaterializationError(
            "successor inputs must be three distinct files"
        )
    if any(path.is_relative_to(target_root) for path in immutable_inputs):
        raise ProviderCycleCapsMaterializationError(
            "successor inputs must be outside the output root"
        )

    legacy_snapshot = _snapshot_input(legacy_path, "legacy caps input")
    smoke_snapshot = _snapshot_input(smoke_path, "authority-smoke input")
    policy_snapshot = _snapshot_input(canonical_policy_path, "provider policy input")
    input_snapshots = (legacy_snapshot, smoke_snapshot, policy_snapshot)
    legacy_bytes = legacy_snapshot.payload
    smoke_bytes = smoke_snapshot.payload
    policy_bytes = policy_snapshot.payload
    authority_smoke = verify_official_labeling_authority_smoke(
        smoke_bytes,
        expected_sha256=expected_authority_smoke_sha256,
        expected_release_sha=expected_smoke_release_sha,
    )
    policy = load_provider_cycle_caps_successor_policy(
        policy_bytes,
        expected_sha256=expected_policy_sha256,
    )
    materialized = _materialize_provider_cycle_caps_successor(
        legacy_bytes,
        expected_source_sha256=expected_legacy_caps_sha256,
        authority_smoke=authority_smoke,
        policy=policy,
    )
    receipt_bytes = canonical_successor_receipt_bytes(materialized.receipt)
    receipt_sha256 = hashlib.sha256(receipt_bytes).hexdigest()
    caps_path = target_root / SUCCESSOR_CAPS_NAME
    receipt_path = target_root / SUCCESSOR_RECEIPT_NAME
    run_card_path = target_root / "run-cards" / SUCCESSOR_RUN_CARD_NAME
    run_card: dict[str, object] = {
        "schema_version": "legalforecast.acquisition_run_card.v1",
        "stage": SUCCESSOR_STAGE,
        "status": "completed",
        "dry_run": False,
        "execute": True,
        "provider_activity_requested": False,
        "provider_activity_executed": False,
        "paid_activity_requested": False,
        "paid_activity_executed": False,
        "aws_activity_requested": False,
        "aws_activity_executed": False,
        "release_sha": authority_smoke.release_sha,
        "input_paths": [
            str(legacy_path),
            str(smoke_path),
            str(canonical_policy_path),
        ],
        "input_commitments": {
            "legacy_provider_cycle_caps": _file_commitment(legacy_path, legacy_bytes),
            "authority_smoke_receipt": _file_commitment(smoke_path, smoke_bytes),
            "provider_caps_successor_policy": _file_commitment(
                canonical_policy_path, policy_bytes
            ),
        },
        "output_commitments": {
            "provider_cycle_caps": _output_commitment(
                caps_path, materialized.caps_bytes
            ),
            "successor_receipt": _output_commitment(receipt_path, receipt_bytes),
        },
        "output_paths": [str(caps_path), str(receipt_path), str(run_card_path)],
    }
    run_card_bytes = canonical_json_bytes(run_card)
    run_card_sha256 = hashlib.sha256(run_card_bytes).hexdigest()

    parent_fd = _open_output_parent(target_root)
    parent_path = target_root.parent
    parent_identity = _directory_stat_identity(parent_fd)
    staged_tree: _StagedOutputTree | None = None
    try:
        target_name = target_root.name
        _recover_stale_staging_trees(
            parent_fd,
            target_name,
            caps_bytes=materialized.caps_bytes,
            receipt_bytes=receipt_bytes,
            run_card_bytes=run_card_bytes,
        )
        _require_canonical_directory_binding(
            parent_path, parent_fd, parent_identity, "output parent"
        )
        original_state = _preflight_output_tree(
            parent_fd,
            target_name,
            caps_bytes=materialized.caps_bytes,
            receipt_bytes=receipt_bytes,
            run_card_bytes=run_card_bytes,
        )
        if original_state.missing == frozenset():
            _reverify_input_snapshots(input_snapshots)
            _require_canonical_directory_binding(
                parent_path, parent_fd, parent_identity, "output parent"
            )
            _require_output_state(
                parent_fd,
                target_name,
                original_state,
                caps_bytes=materialized.caps_bytes,
                receipt_bytes=receipt_bytes,
                run_card_bytes=run_card_bytes,
            )
        else:
            staged_tree = _stage_complete_output_tree(
                parent_fd,
                target_name,
                caps_bytes=materialized.caps_bytes,
                receipt_bytes=receipt_bytes,
                run_card_bytes=run_card_bytes,
            )
            _commit_staged_output_tree(
                parent_fd,
                target_name,
                staged_tree,
                original_state=original_state,
                parent_path=parent_path,
                parent_identity=parent_identity,
                input_snapshots=input_snapshots,
                caps_bytes=materialized.caps_bytes,
                receipt_bytes=receipt_bytes,
                run_card_bytes=run_card_bytes,
            )
            staged_tree = None
    finally:
        if staged_tree is not None:
            _remove_staging_tree(
                parent_fd,
                staged_tree.name,
                staged_tree.state.root_identity,
            )
        os.close(parent_fd)
    return PublishedProviderCycleCapsSuccessor(
        caps_path=caps_path,
        receipt_path=receipt_path,
        run_card_path=run_card_path,
        caps_sha256=materialized.caps_sha256,
        receipt_sha256=receipt_sha256,
        run_card_sha256=run_card_sha256,
    )


def canonical_successor_receipt_bytes(receipt: Mapping[str, object]) -> bytes:
    """Serialize a successor receipt for deterministic public evidence."""

    return canonical_json_bytes(dict(receipt))


def canonical_json_bytes(record: Mapping[str, object]) -> bytes:
    """Return the repository canonical pretty JSON representation."""

    return (
        json.dumps(
            record,
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode()


def _json_object(payload: bytes, label: str) -> Mapping[str, object]:
    try:
        value: object = json.loads(payload, object_pairs_hook=_unique_json_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProviderCycleCapsMaterializationError(
            f"{label} must contain valid UTF-8 JSON"
        ) from exc
    if not isinstance(value, Mapping):
        raise ProviderCycleCapsMaterializationError(f"{label} must be an object")
    return cast(Mapping[str, object], value)


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    record: dict[str, object] = {}
    for key, value in pairs:
        if key in record:
            raise ProviderCycleCapsMaterializationError(
                f"JSON object contains duplicate key {key!r}"
            )
        record[key] = value
    return record


def _exact_fields(
    record: Mapping[str, object], expected: frozenset[str], label: str
) -> None:
    if frozenset(record) != expected:
        raise ProviderCycleCapsMaterializationError(f"{label} field set differs")


def _true_boolean_table(value: object, expected: frozenset[str], label: str) -> None:
    if not isinstance(value, Mapping):
        raise ProviderCycleCapsMaterializationError(f"{label} must be an object")
    record = cast(Mapping[str, object], value)
    _exact_fields(record, expected, label)
    if any(record[field] is not True for field in expected):
        raise ProviderCycleCapsMaterializationError(
            f"{label} must contain only true values"
        )


def _digest(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != _SHA256_LENGTH
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ProviderCycleCapsMaterializationError(
            f"{label} must be a lowercase SHA-256 digest"
        )
    return value


def _release_sha(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != _RELEASE_SHA_LENGTH
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ProviderCycleCapsMaterializationError(
            f"{label} must be a lowercase commit SHA"
        )
    return value


def _positive_integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ProviderCycleCapsMaterializationError(f"{label} must be positive")
    return value


def _nonempty_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ProviderCycleCapsMaterializationError(
            f"{label} must be a canonical non-empty string"
        )
    return value


def _lower_identifier(value: object, label: str) -> str:
    text = _nonempty_text(value, label)
    if text.lower() != text or any(
        character not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for character in text
    ):
        raise ProviderCycleCapsMaterializationError(
            f"{label} must be a lowercase public identifier"
        )
    return text


def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


def _canonical_input_path(path: Path, label: str) -> Path:
    absolute = Path(os.path.abspath(os.fspath(path)))
    if not path.is_absolute() or path != absolute:
        raise ProviderCycleCapsMaterializationError(
            f"{label} must be an absolute canonical path"
        )
    return absolute


def _canonical_output_root(path: Path) -> Path:
    absolute = Path(os.path.abspath(os.fspath(path)))
    if not path.is_absolute() or path != absolute or path == Path(path.anchor):
        raise ProviderCycleCapsMaterializationError(
            "output root must be an absolute canonical path below the filesystem root"
        )
    return absolute


def _snapshot_input(path: Path, label: str) -> _InputSnapshot:
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None:
        raise ProviderCycleCapsMaterializationError(
            f"{label} cannot be safely read without O_NOFOLLOW"
        )
    try:
        parent_fd = _open_directory_path(path.parent, f"{label} parent")
    except ProviderCycleCapsMaterializationError as exc:
        raise ProviderCycleCapsMaterializationError(
            f"{label} cannot be safely read"
        ) from exc
    file_fd: int | None = None
    try:
        file_fd = os.open(
            path.name,
            os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC | nofollow,
            dir_fd=parent_fd,
        )
        before = os.fstat(file_fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise ProviderCycleCapsMaterializationError(
                f"{label} must be a unique regular file"
            )
        chunks: list[bytes] = []
        while chunk := os.read(file_fd, 1024 * 1024):
            chunks.append(chunk)
        after = os.fstat(file_fd)
        if any(
            getattr(before, field) != getattr(after, field)
            for field in _STABLE_STAT_FIELDS
        ):
            raise ProviderCycleCapsMaterializationError(
                f"{label} changed while being read"
            )
        payload = b"".join(chunks)
        if len(payload) != after.st_size:
            raise ProviderCycleCapsMaterializationError(
                f"{label} changed while being read"
            )
        named = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
        if _stat_identity(named) != _stat_identity(after):
            raise ProviderCycleCapsMaterializationError(
                f"{label} path binding changed while being read"
            )
        live_parent_fd = _open_directory_path(path.parent, f"{label} live parent")
        try:
            if not _same_inode(
                _directory_stat_identity(live_parent_fd),
                _directory_stat_identity(parent_fd),
            ):
                raise ProviderCycleCapsMaterializationError(
                    f"{label} parent path binding changed while being read"
                )
            live_named = os.stat(
                path.name,
                dir_fd=live_parent_fd,
                follow_symlinks=False,
            )
            if _stat_identity(live_named) != _stat_identity(after):
                raise ProviderCycleCapsMaterializationError(
                    f"{label} path binding changed while being read"
                )
        finally:
            os.close(live_parent_fd)
        return _InputSnapshot(
            path=path,
            label=label,
            payload=payload,
            stat_identity=tuple(
                cast(int, getattr(after, field)) for field in _STABLE_STAT_FIELDS
            ),
        )
    except ProviderCycleCapsMaterializationError:
        raise
    except OSError as exc:
        raise ProviderCycleCapsMaterializationError(
            f"{label} cannot be safely read"
        ) from exc
    finally:
        if file_fd is not None:
            os.close(file_fd)
        os.close(parent_fd)


def _reverify_input_snapshots(snapshots: tuple[_InputSnapshot, ...]) -> None:
    for snapshot in snapshots:
        current = _snapshot_input(snapshot.path, snapshot.label)
        if (
            current.stat_identity != snapshot.stat_identity
            or current.payload != snapshot.payload
        ):
            raise ProviderCycleCapsMaterializationError(
                f"{snapshot.label} changed between validation and publication"
            )


def _file_commitment(path: Path, payload: bytes) -> dict[str, object]:
    return {
        "bytes": len(payload),
        "path": str(path),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def _output_commitment(path: Path, payload: bytes) -> dict[str, object]:
    return _file_commitment(path, payload)


def _directory_flags() -> int:
    return os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | _nofollow_flag()


def _nofollow_flag() -> int:
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None:
        raise ProviderCycleCapsMaterializationError(
            "safe output publication requires O_NOFOLLOW"
        )
    return cast(int, nofollow)


def _open_directory_path(path: Path, label: str) -> int:
    parts = path.parts
    flags = _directory_flags()
    directory_fd: int | None = None
    try:
        directory_fd = os.open(parts[0], flags)
        for component in parts[1:]:
            next_fd = os.open(component, flags, dir_fd=directory_fd)
            os.close(directory_fd)
            directory_fd = next_fd
        return directory_fd
    except ProviderCycleCapsMaterializationError:
        if directory_fd is not None:
            os.close(directory_fd)
        raise
    except OSError as exc:
        if directory_fd is not None:
            os.close(directory_fd)
        raise ProviderCycleCapsMaterializationError(
            f"{label} cannot be opened without following links"
        ) from exc


def _open_output_parent(path: Path) -> int:
    return _open_directory_path(path.parent, "output path parent")


def _open_child_directory(parent_fd: int, name: str, *, create: bool) -> int:
    flags = _directory_flags()
    try:
        return os.open(name, flags, dir_fd=parent_fd)
    except FileNotFoundError:
        if not create:
            raise
        try:
            os.mkdir(name, mode=0o700, dir_fd=parent_fd)
            os.fsync(parent_fd)
            return os.open(name, flags, dir_fd=parent_fd)
        except OSError as exc:
            raise ProviderCycleCapsMaterializationError(
                "successor run-card directory cannot be created safely"
            ) from exc
    except OSError as exc:
        raise ProviderCycleCapsMaterializationError(
            "successor run-card output path is unsafe"
        ) from exc


def _open_optional_child_directory(parent_fd: int, name: str) -> int | None:
    try:
        return _open_child_directory(parent_fd, name, create=False)
    except FileNotFoundError:
        return None


def _preflight_output_tree(
    parent_fd: int,
    target_name: str,
    *,
    caps_bytes: bytes,
    receipt_bytes: bytes,
    run_card_bytes: bytes,
) -> _OutputTreeState:
    target_fd = _open_optional_child_directory(parent_fd, target_name)
    if target_fd is None:
        return _OutputTreeState(
            exists=False,
            root_identity=None,
            run_cards_identity=None,
            caps_identity=None,
            receipt_identity=None,
            run_card_identity=None,
            missing=frozenset(
                {
                    SUCCESSOR_CAPS_NAME,
                    SUCCESSOR_RECEIPT_NAME,
                    SUCCESSOR_RUN_CARD_NAME,
                }
            ),
        )
    run_cards_fd: int | None = None
    try:
        root_before = _directory_stat_identity(target_fd)
        root_entries_before = frozenset(os.listdir(target_fd))
        _reject_entry_set(root_entries_before, _ROOT_ENTRIES, "successor output root")
        missing: set[str] = set()
        caps_snapshot = _read_output_snapshot(
            target_fd, SUCCESSOR_CAPS_NAME, caps_bytes
        )
        caps_identity = None if caps_snapshot is None else caps_snapshot[1]
        if caps_snapshot is None:
            missing.add(SUCCESSOR_CAPS_NAME)
        receipt_snapshot = _read_output_snapshot(
            target_fd, SUCCESSOR_RECEIPT_NAME, receipt_bytes
        )
        receipt_identity = None if receipt_snapshot is None else receipt_snapshot[1]
        if receipt_snapshot is None:
            missing.add(SUCCESSOR_RECEIPT_NAME)
        run_cards_fd = _open_optional_child_directory(target_fd, "run-cards")
        run_cards_identity: tuple[int, ...] | None = None
        run_card_identity: tuple[int, ...] | None = None
        run_cards_before: tuple[int, ...] | None = None
        run_cards_entries_before: frozenset[str] | None = None
        if run_cards_fd is None:
            missing.add(SUCCESSOR_RUN_CARD_NAME)
        else:
            run_cards_before = _directory_stat_identity(run_cards_fd)
            run_cards_entries_before = frozenset(os.listdir(run_cards_fd))
            _reject_entry_set(
                run_cards_entries_before,
                _RUN_CARD_ENTRIES,
                "successor run-card root",
            )
            run_card_snapshot = _read_output_snapshot(
                run_cards_fd, SUCCESSOR_RUN_CARD_NAME, run_card_bytes
            )
            if run_card_snapshot is None:
                missing.add(SUCCESSOR_RUN_CARD_NAME)
            else:
                run_card_identity = run_card_snapshot[1]
            run_cards_entries_after = frozenset(os.listdir(run_cards_fd))
            run_cards_after = _directory_stat_identity(run_cards_fd)
            if (
                run_cards_entries_after != run_cards_entries_before
                or run_cards_after != run_cards_before
            ):
                raise ProviderCycleCapsMaterializationError(
                    "successor run-card root changed while being authenticated"
                )
            _require_named_directory_binding(
                target_fd,
                "run-cards",
                run_cards_fd,
                "successor run-card root",
            )
            if (
                frozenset(os.listdir(run_cards_fd)) != run_cards_entries_before
                or _directory_stat_identity(run_cards_fd) != run_cards_before
            ):
                raise ProviderCycleCapsMaterializationError(
                    "successor run-card root changed while being authenticated"
                )
            run_cards_identity = run_cards_before
        root_entries_after = frozenset(os.listdir(target_fd))
        root_after = _directory_stat_identity(target_fd)
        if root_entries_after != root_entries_before or root_after != root_before:
            raise ProviderCycleCapsMaterializationError(
                "successor output root changed while being authenticated"
            )
        _require_named_directory_binding(
            parent_fd,
            target_name,
            target_fd,
            "successor output root",
        )
        if caps_identity is not None:
            _require_named_file_identity(
                target_fd,
                SUCCESSOR_CAPS_NAME,
                caps_identity,
                "successor caps output",
            )
        if receipt_identity is not None:
            _require_named_file_identity(
                target_fd,
                SUCCESSOR_RECEIPT_NAME,
                receipt_identity,
                "successor receipt output",
            )
        if (
            run_cards_fd is not None
            and run_card_identity is not None
            and run_cards_entries_before is not None
            and run_cards_before is not None
        ):
            _require_named_file_identity(
                run_cards_fd,
                SUCCESSOR_RUN_CARD_NAME,
                run_card_identity,
                "successor run-card output",
            )
            if (
                frozenset(os.listdir(run_cards_fd)) != run_cards_entries_before
                or _directory_stat_identity(run_cards_fd) != run_cards_before
            ):
                raise ProviderCycleCapsMaterializationError(
                    "successor run-card root changed while being authenticated"
                )
        if (
            frozenset(os.listdir(target_fd)) != root_entries_before
            or _directory_stat_identity(target_fd) != root_before
        ):
            raise ProviderCycleCapsMaterializationError(
                "successor output root changed while being authenticated"
            )
        return _OutputTreeState(
            exists=True,
            root_identity=root_before,
            run_cards_identity=run_cards_identity,
            caps_identity=caps_identity,
            receipt_identity=receipt_identity,
            run_card_identity=run_card_identity,
            missing=frozenset(missing),
        )
    finally:
        if run_cards_fd is not None:
            os.close(run_cards_fd)
        os.close(target_fd)


def _stage_complete_output_tree(
    parent_fd: int,
    target_name: str,
    *,
    caps_bytes: bytes,
    receipt_bytes: bytes,
    run_card_bytes: bytes,
) -> _StagedOutputTree:
    stage_name = f".{target_name}.{secrets.token_hex(16)}.partial"
    stage_fd: int | None = None
    run_cards_fd: int | None = None
    stage_created = False
    stage_identity: tuple[int, ...] | None = None
    complete = False
    try:
        os.mkdir(stage_name, mode=0o700, dir_fd=parent_fd)
        stage_created = True
        stage_fd = _open_child_directory(parent_fd, stage_name, create=False)
        stage_identity = _directory_stat_identity(stage_fd)
        run_cards_fd = _open_child_directory(stage_fd, "run-cards", create=True)
        _publish_or_verify(stage_fd, SUCCESSOR_CAPS_NAME, caps_bytes)
        _publish_or_verify(stage_fd, SUCCESSOR_RECEIPT_NAME, receipt_bytes)
        _publish_or_verify(run_cards_fd, SUCCESSOR_RUN_CARD_NAME, run_card_bytes)
        _reject_residue(stage_fd, _ROOT_ENTRIES, "staged successor output root")
        _reject_residue(
            run_cards_fd, _RUN_CARD_ENTRIES, "staged successor run-card root"
        )
        os.fsync(run_cards_fd)
        os.fsync(stage_fd)
        os.fsync(parent_fd)
        staged_state = _preflight_output_tree(
            parent_fd,
            stage_name,
            caps_bytes=caps_bytes,
            receipt_bytes=receipt_bytes,
            run_card_bytes=run_card_bytes,
        )
        if not staged_state.exists or staged_state.missing:
            raise ProviderCycleCapsMaterializationError(
                "complete successor output tree was not staged completely"
            )
        complete = True
        return _StagedOutputTree(
            name=stage_name,
            state=staged_state,
        )
    except ProviderCycleCapsMaterializationError:
        raise
    except OSError as exc:
        raise ProviderCycleCapsMaterializationError(
            "complete successor output tree cannot be staged safely"
        ) from exc
    finally:
        if run_cards_fd is not None:
            os.close(run_cards_fd)
        if stage_fd is not None:
            os.close(stage_fd)
        if stage_created and not complete:
            try:
                _remove_staging_tree(parent_fd, stage_name, stage_identity)
            except ProviderCycleCapsMaterializationError:
                pass


def _recover_stale_staging_trees(
    parent_fd: int,
    target_name: str,
    *,
    caps_bytes: bytes,
    receipt_bytes: bytes,
    run_card_bytes: bytes,
) -> None:
    prefix = f".{target_name}."
    suffix = ".partial"
    for name in sorted(os.listdir(parent_fd)):
        if not name.startswith(prefix) or not name.endswith(suffix):
            continue
        token = name[len(prefix) : -len(suffix)]
        if len(token) != 32 or any(
            character not in "0123456789abcdef" for character in token
        ):
            continue
        state = _preflight_output_tree(
            parent_fd,
            name,
            caps_bytes=caps_bytes,
            receipt_bytes=receipt_bytes,
            run_card_bytes=run_card_bytes,
        )
        if not state.exists or state.root_identity is None:
            raise ProviderCycleCapsMaterializationError(
                "stale successor staging tree changed during recovery"
            )
        _remove_staging_tree(parent_fd, name, state.root_identity)
    os.fsync(parent_fd)


def _commit_staged_output_tree(
    parent_fd: int,
    target_name: str,
    staged_tree: _StagedOutputTree,
    *,
    original_state: _OutputTreeState,
    parent_path: Path,
    parent_identity: tuple[int, ...],
    input_snapshots: tuple[_InputSnapshot, ...],
    caps_bytes: bytes,
    receipt_bytes: bytes,
    run_card_bytes: bytes,
) -> None:
    current_state = _preflight_output_tree(
        parent_fd,
        target_name,
        caps_bytes=caps_bytes,
        receipt_bytes=receipt_bytes,
        run_card_bytes=run_card_bytes,
    )
    if current_state.missing == frozenset():
        _reverify_input_snapshots(input_snapshots)
        _require_canonical_directory_binding(
            parent_path, parent_fd, parent_identity, "output parent"
        )
        _require_output_state(
            parent_fd,
            target_name,
            current_state,
            caps_bytes=caps_bytes,
            receipt_bytes=receipt_bytes,
            run_card_bytes=run_card_bytes,
        )
        _require_canonical_directory_binding(
            parent_path, parent_fd, parent_identity, "output parent"
        )
        _remove_staging_tree(
            parent_fd, staged_tree.name, staged_tree.state.root_identity
        )
        return
    if current_state != original_state:
        raise ProviderCycleCapsMaterializationError(
            "successor output tree changed while the complete tree was staged"
        )
    if current_state.missing == frozenset({SUCCESSOR_RUN_CARD_NAME}):
        if current_state.run_cards_identity is None:
            _commit_missing_run_cards_directory(
                parent_fd,
                target_name,
                staged_tree,
                expected_state=current_state,
                parent_path=parent_path,
                parent_identity=parent_identity,
                input_snapshots=input_snapshots,
                caps_bytes=caps_bytes,
                receipt_bytes=receipt_bytes,
                run_card_bytes=run_card_bytes,
            )
        else:
            _commit_missing_run_card(
                parent_fd,
                target_name,
                staged_tree,
                expected_state=current_state,
                parent_path=parent_path,
                parent_identity=parent_identity,
                input_snapshots=input_snapshots,
                caps_bytes=caps_bytes,
                receipt_bytes=receipt_bytes,
                run_card_bytes=run_card_bytes,
            )
        _remove_staging_tree(
            parent_fd, staged_tree.name, staged_tree.state.root_identity
        )
        return
    _reverify_input_snapshots(input_snapshots)
    _require_canonical_directory_binding(
        parent_path, parent_fd, parent_identity, "output parent"
    )
    _require_output_state(
        parent_fd,
        target_name,
        current_state,
        caps_bytes=caps_bytes,
        receipt_bytes=receipt_bytes,
        run_card_bytes=run_card_bytes,
    )
    _require_complete_staged_tree(
        parent_fd,
        staged_tree,
        caps_bytes=caps_bytes,
        receipt_bytes=receipt_bytes,
        run_card_bytes=run_card_bytes,
    )
    if not current_state.exists:
        _renameat2(
            parent_fd,
            staged_tree.name,
            parent_fd,
            target_name,
            flag=1,
            operation="no-replace publication",
        )
        os.fsync(parent_fd)
        _verify_or_rollback_complete_tree(
            parent_fd,
            target_name,
            staged_tree,
            exchanged=False,
            parent_path=parent_path,
            parent_identity=parent_identity,
            input_snapshots=input_snapshots,
            caps_bytes=caps_bytes,
            receipt_bytes=receipt_bytes,
            run_card_bytes=run_card_bytes,
        )
        return
    _renameat2(
        parent_fd,
        staged_tree.name,
        parent_fd,
        target_name,
        flag=2,
        operation="exchange publication",
    )
    os.fsync(parent_fd)
    _verify_or_rollback_complete_tree(
        parent_fd,
        target_name,
        staged_tree,
        exchanged=True,
        parent_path=parent_path,
        parent_identity=parent_identity,
        input_snapshots=input_snapshots,
        caps_bytes=caps_bytes,
        receipt_bytes=receipt_bytes,
        run_card_bytes=run_card_bytes,
    )
    _remove_staging_tree(parent_fd, staged_tree.name, current_state.root_identity)


def _commit_missing_run_card(
    parent_fd: int,
    target_name: str,
    staged_tree: _StagedOutputTree,
    *,
    expected_state: _OutputTreeState,
    parent_path: Path,
    parent_identity: tuple[int, ...],
    input_snapshots: tuple[_InputSnapshot, ...],
    caps_bytes: bytes,
    receipt_bytes: bytes,
    run_card_bytes: bytes,
) -> None:
    _reverify_input_snapshots(input_snapshots)
    _require_canonical_directory_binding(
        parent_path, parent_fd, parent_identity, "output parent"
    )
    _require_complete_staged_tree(
        parent_fd,
        staged_tree,
        caps_bytes=caps_bytes,
        receipt_bytes=receipt_bytes,
        run_card_bytes=run_card_bytes,
    )
    _require_output_state(
        parent_fd,
        target_name,
        expected_state,
        caps_bytes=caps_bytes,
        receipt_bytes=receipt_bytes,
        run_card_bytes=run_card_bytes,
    )
    target_fd = _open_child_directory(parent_fd, target_name, create=False)
    stage_fd = _open_child_directory(parent_fd, staged_tree.name, create=False)
    target_run_cards_fd: int | None = None
    stage_run_cards_fd: int | None = None
    try:
        _require_directory_identity(
            target_fd, expected_state.root_identity, "successor output root"
        )
        _require_directory_identity(
            stage_fd,
            staged_tree.state.root_identity,
            "staged successor output root",
        )
        target_run_cards_fd = _open_child_directory(
            target_fd, "run-cards", create=False
        )
        stage_run_cards_fd = _open_child_directory(stage_fd, "run-cards", create=False)
        _require_directory_identity(
            target_run_cards_fd,
            expected_state.run_cards_identity,
            "successor run-card root",
        )
        _renameat2(
            stage_run_cards_fd,
            SUCCESSOR_RUN_CARD_NAME,
            target_run_cards_fd,
            SUCCESSOR_RUN_CARD_NAME,
            flag=1,
            operation="missing run-card publication",
        )
        os.fsync(target_run_cards_fd)
        os.fsync(target_fd)
        try:
            _require_complete_live_tree(
                parent_fd,
                target_name,
                expected_state=_completed_repair_state(
                    expected_state,
                    staged_tree.state,
                    preserve_run_cards_directory=True,
                ),
                parent_path=parent_path,
                parent_identity=parent_identity,
                caps_bytes=caps_bytes,
                receipt_bytes=receipt_bytes,
                run_card_bytes=run_card_bytes,
            )
            _reverify_input_snapshots(input_snapshots)
        except ProviderCycleCapsMaterializationError:
            _renameat2(
                target_run_cards_fd,
                SUCCESSOR_RUN_CARD_NAME,
                stage_run_cards_fd,
                SUCCESSOR_RUN_CARD_NAME,
                flag=1,
                operation="missing run-card rollback",
            )
            os.fsync(target_run_cards_fd)
            os.fsync(stage_run_cards_fd)
            os.fsync(target_fd)
            os.fsync(stage_fd)
            raise
    finally:
        if stage_run_cards_fd is not None:
            os.close(stage_run_cards_fd)
        if target_run_cards_fd is not None:
            os.close(target_run_cards_fd)
        os.close(stage_fd)
        os.close(target_fd)


def _commit_missing_run_cards_directory(
    parent_fd: int,
    target_name: str,
    staged_tree: _StagedOutputTree,
    *,
    expected_state: _OutputTreeState,
    parent_path: Path,
    parent_identity: tuple[int, ...],
    input_snapshots: tuple[_InputSnapshot, ...],
    caps_bytes: bytes,
    receipt_bytes: bytes,
    run_card_bytes: bytes,
) -> None:
    _reverify_input_snapshots(input_snapshots)
    _require_canonical_directory_binding(
        parent_path, parent_fd, parent_identity, "output parent"
    )
    _require_complete_staged_tree(
        parent_fd,
        staged_tree,
        caps_bytes=caps_bytes,
        receipt_bytes=receipt_bytes,
        run_card_bytes=run_card_bytes,
    )
    _require_output_state(
        parent_fd,
        target_name,
        expected_state,
        caps_bytes=caps_bytes,
        receipt_bytes=receipt_bytes,
        run_card_bytes=run_card_bytes,
    )
    target_fd = _open_child_directory(parent_fd, target_name, create=False)
    stage_fd = _open_child_directory(parent_fd, staged_tree.name, create=False)
    try:
        _require_directory_identity(
            target_fd, expected_state.root_identity, "successor output root"
        )
        _require_directory_identity(
            stage_fd,
            staged_tree.state.root_identity,
            "staged successor output root",
        )
        _renameat2(
            stage_fd,
            "run-cards",
            target_fd,
            "run-cards",
            flag=1,
            operation="missing run-card directory publication",
        )
        os.fsync(target_fd)
        try:
            _require_complete_live_tree(
                parent_fd,
                target_name,
                expected_state=_completed_repair_state(
                    expected_state,
                    staged_tree.state,
                    preserve_run_cards_directory=False,
                ),
                parent_path=parent_path,
                parent_identity=parent_identity,
                caps_bytes=caps_bytes,
                receipt_bytes=receipt_bytes,
                run_card_bytes=run_card_bytes,
            )
            _reverify_input_snapshots(input_snapshots)
        except ProviderCycleCapsMaterializationError:
            _renameat2(
                target_fd,
                "run-cards",
                stage_fd,
                "run-cards",
                flag=1,
                operation="missing run-card directory rollback",
            )
            os.fsync(target_fd)
            os.fsync(stage_fd)
            raise
    finally:
        os.close(stage_fd)
        os.close(target_fd)


def _require_output_state(
    parent_fd: int,
    target_name: str,
    expected: _OutputTreeState,
    *,
    caps_bytes: bytes,
    receipt_bytes: bytes,
    run_card_bytes: bytes,
) -> None:
    try:
        current = _preflight_output_tree(
            parent_fd,
            target_name,
            caps_bytes=caps_bytes,
            receipt_bytes=receipt_bytes,
            run_card_bytes=run_card_bytes,
        )
    except ProviderCycleCapsMaterializationError as exc:
        raise ProviderCycleCapsMaterializationError(
            "successor output root changed while publication was prepared"
        ) from exc
    if current != expected:
        raise ProviderCycleCapsMaterializationError(
            "successor output root changed while publication was prepared"
        )


def _completed_repair_state(
    original: _OutputTreeState,
    staged: _OutputTreeState,
    *,
    preserve_run_cards_directory: bool,
) -> _OutputTreeState:
    return _OutputTreeState(
        exists=True,
        root_identity=original.root_identity,
        run_cards_identity=(
            original.run_cards_identity
            if preserve_run_cards_directory
            else staged.run_cards_identity
        ),
        caps_identity=original.caps_identity,
        receipt_identity=original.receipt_identity,
        run_card_identity=staged.run_card_identity,
        missing=frozenset(),
    )


def _require_complete_staged_tree(
    parent_fd: int,
    staged_tree: _StagedOutputTree,
    *,
    caps_bytes: bytes,
    receipt_bytes: bytes,
    run_card_bytes: bytes,
) -> None:
    try:
        state = _preflight_output_tree(
            parent_fd,
            staged_tree.name,
            caps_bytes=caps_bytes,
            receipt_bytes=receipt_bytes,
            run_card_bytes=run_card_bytes,
        )
    except ProviderCycleCapsMaterializationError as exc:
        raise ProviderCycleCapsMaterializationError(
            "staged successor output tree changed before publication"
        ) from exc
    if not state.exists or state != staged_tree.state:
        raise ProviderCycleCapsMaterializationError(
            "staged successor output tree changed before publication"
        )


def _require_complete_live_tree(
    parent_fd: int,
    target_name: str,
    *,
    expected_state: _OutputTreeState,
    parent_path: Path,
    parent_identity: tuple[int, ...],
    caps_bytes: bytes,
    receipt_bytes: bytes,
    run_card_bytes: bytes,
) -> None:
    _require_canonical_directory_binding(
        parent_path, parent_fd, parent_identity, "output parent"
    )
    try:
        state = _preflight_output_tree(
            parent_fd,
            target_name,
            caps_bytes=caps_bytes,
            receipt_bytes=receipt_bytes,
            run_card_bytes=run_card_bytes,
        )
    except ProviderCycleCapsMaterializationError as exc:
        raise ProviderCycleCapsMaterializationError(
            "successor output root changed during publication"
        ) from exc
    if not state.exists or not _live_tree_matches(expected_state, state):
        raise ProviderCycleCapsMaterializationError(
            "successor output root changed during publication"
        )
    _require_canonical_directory_binding(
        parent_path, parent_fd, parent_identity, "output parent"
    )


def _live_tree_matches(expected: _OutputTreeState, current: _OutputTreeState) -> bool:
    return (
        current.exists == expected.exists
        and current.missing == expected.missing
        and _same_inode(current.root_identity, expected.root_identity)
        and _same_inode(
            current.run_cards_identity,
            expected.run_cards_identity,
        )
        and _same_inode(current.caps_identity, expected.caps_identity)
        and _same_inode(current.receipt_identity, expected.receipt_identity)
        and _same_inode(current.run_card_identity, expected.run_card_identity)
    )


def _same_inode(left: tuple[int, ...] | None, right: tuple[int, ...] | None) -> bool:
    if left is None or right is None:
        return left is right
    return left[:2] == right[:2]


def _verify_or_rollback_complete_tree(
    parent_fd: int,
    target_name: str,
    staged_tree: _StagedOutputTree,
    *,
    exchanged: bool,
    parent_path: Path,
    parent_identity: tuple[int, ...],
    input_snapshots: tuple[_InputSnapshot, ...],
    caps_bytes: bytes,
    receipt_bytes: bytes,
    run_card_bytes: bytes,
) -> None:
    try:
        _require_complete_live_tree(
            parent_fd,
            target_name,
            expected_state=staged_tree.state,
            parent_path=parent_path,
            parent_identity=parent_identity,
            caps_bytes=caps_bytes,
            receipt_bytes=receipt_bytes,
            run_card_bytes=run_card_bytes,
        )
        _reverify_input_snapshots(input_snapshots)
    except ProviderCycleCapsMaterializationError as verification_error:
        try:
            _renameat2(
                parent_fd,
                target_name,
                parent_fd,
                staged_tree.name,
                flag=2 if exchanged else 1,
                operation="successor output rollback",
            )
            os.fsync(parent_fd)
        except ProviderCycleCapsMaterializationError as rollback_error:
            raise ProviderCycleCapsMaterializationError(
                "successor output verification and atomic rollback both failed"
            ) from rollback_error
        raise verification_error


def _stat_identity(value: os.stat_result) -> tuple[int, ...]:
    return tuple(cast(int, getattr(value, field)) for field in _STABLE_STAT_FIELDS)


def _directory_stat_identity(directory_fd: int) -> tuple[int, ...]:
    value = os.fstat(directory_fd)
    if not stat.S_ISDIR(value.st_mode):  # pragma: no cover - O_DIRECTORY invariant
        raise ProviderCycleCapsMaterializationError(
            "directory identity does not refer to a directory"
        )
    return _stat_identity(value)


def _require_named_directory_binding(
    parent_fd: int,
    name: str,
    directory_fd: int,
    label: str,
) -> None:
    try:
        named = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except OSError as exc:
        raise ProviderCycleCapsMaterializationError(
            f"{label} path binding changed"
        ) from exc
    opened = os.fstat(directory_fd)
    if (
        not stat.S_ISDIR(named.st_mode)
        or named.st_dev != opened.st_dev
        or named.st_ino != opened.st_ino
    ):
        raise ProviderCycleCapsMaterializationError(f"{label} path binding changed")


def _require_canonical_directory_binding(
    path: Path,
    directory_fd: int,
    expected_identity: tuple[int, ...],
    label: str,
) -> None:
    live_fd = _open_directory_path(path, f"{label} live path")
    try:
        live_identity = _directory_stat_identity(live_fd)
        held_identity = _directory_stat_identity(directory_fd)
        if not _same_inode(live_identity, expected_identity) or not _same_inode(
            held_identity, expected_identity
        ):
            raise ProviderCycleCapsMaterializationError(
                f"{label} canonical path binding changed"
            )
    finally:
        os.close(live_fd)


def _require_named_file_identity(
    parent_fd: int,
    name: str,
    expected: tuple[int, ...],
    label: str,
) -> None:
    try:
        named = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except OSError as exc:
        raise ProviderCycleCapsMaterializationError(
            f"{label} path binding changed"
        ) from exc
    if _stat_identity(named) != expected:
        raise ProviderCycleCapsMaterializationError(f"{label} path binding changed")


def _require_directory_identity(
    directory_fd: int,
    expected: tuple[int, ...] | None,
    label: str,
) -> None:
    if expected is None or _directory_stat_identity(directory_fd) != expected:
        raise ProviderCycleCapsMaterializationError(
            f"{label} changed while publication was prepared"
        )


def _renameat2(
    source_fd: int,
    source_name: str,
    destination_fd: int,
    destination_name: str,
    *,
    flag: int,
    operation: str,
) -> None:
    renameat2 = getattr(ctypes.CDLL(None, use_errno=True), "renameat2", None)
    if renameat2 is None:
        raise ProviderCycleCapsMaterializationError(
            f"renameat2 is unavailable for atomic {operation}"
        )
    renameat2.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    renameat2.restype = ctypes.c_int
    result = renameat2(
        source_fd,
        os.fsencode(source_name),
        destination_fd,
        os.fsencode(destination_name),
        flag,
    )
    if result == 0:
        return
    error_number = ctypes.get_errno()
    if error_number == errno.EEXIST:
        raise ProviderCycleCapsMaterializationError(
            f"destination appeared during atomic {operation}"
        )
    raise ProviderCycleCapsMaterializationError(
        f"atomic {operation} failed: {os.strerror(error_number)}"
    )


def _remove_staging_tree(
    parent_fd: int,
    stage_name: str,
    expected_identity: tuple[int, ...] | None,
) -> None:
    stage_fd = _open_optional_child_directory(parent_fd, stage_name)
    if stage_fd is None:
        return
    try:
        if not _same_inode(_directory_stat_identity(stage_fd), expected_identity):
            raise ProviderCycleCapsMaterializationError(
                "staging path no longer identifies the owned output tree"
            )
        _remove_directory_contents(stage_fd)
        _require_named_directory_binding(
            parent_fd,
            stage_name,
            stage_fd,
            "owned staging output tree",
        )
    finally:
        os.close(stage_fd)
    try:
        os.rmdir(stage_name, dir_fd=parent_fd)
        os.fsync(parent_fd)
    except OSError as exc:
        raise ProviderCycleCapsMaterializationError(
            "staged successor output tree cannot be removed safely"
        ) from exc


def _remove_directory_contents(directory_fd: int) -> None:
    for name in os.listdir(directory_fd):
        try:
            entry = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            if stat.S_ISDIR(entry.st_mode):
                child_fd = _open_child_directory(directory_fd, name, create=False)
                try:
                    _remove_directory_contents(child_fd)
                finally:
                    os.close(child_fd)
                os.rmdir(name, dir_fd=directory_fd)
            else:
                os.unlink(name, dir_fd=directory_fd)
        except OSError as exc:
            raise ProviderCycleCapsMaterializationError(
                "staged successor output residue cannot be removed safely"
            ) from exc
    os.fsync(directory_fd)


def _reject_residue(directory_fd: int, allowed: frozenset[str], label: str) -> None:
    try:
        entries = set(os.listdir(directory_fd))
    except OSError as exc:
        raise ProviderCycleCapsMaterializationError(
            f"{label} cannot be enumerated safely"
        ) from exc
    _reject_entry_set(frozenset(entries), allowed, label)


def _reject_entry_set(
    entries: frozenset[str], allowed: frozenset[str], label: str
) -> None:
    unexpected = entries - allowed
    if unexpected:
        raise ProviderCycleCapsMaterializationError(
            f"unexpected output residue in {label}: {sorted(unexpected)}"
        )


def _read_output_snapshot(
    directory_fd: int, name: str, expected: bytes
) -> tuple[bytes, tuple[int, ...]] | None:
    flags = os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC | _nofollow_flag()
    try:
        file_fd = os.open(name, flags, dir_fd=directory_fd)
    except OSError as exc:
        if exc.errno == errno.ENOENT:
            return None
        raise ProviderCycleCapsMaterializationError(
            f"output {name} must be a unique regular file"
        ) from exc
    try:
        before = os.fstat(file_fd)
        before_identity = _stat_identity(before)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise ProviderCycleCapsMaterializationError(
                f"output {name} must be a unique regular file"
            )
        chunks: list[bytes] = []
        while chunk := os.read(file_fd, 1024 * 1024):
            chunks.append(chunk)
        payload = b"".join(chunks)
        after_identity = _stat_identity(os.fstat(file_fd))
        named_identity = _stat_identity(
            os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        )
        if before_identity != after_identity or after_identity != named_identity:
            raise ProviderCycleCapsMaterializationError(
                f"output {name} changed while being authenticated"
            )
        if len(payload) != before.st_size:
            raise ProviderCycleCapsMaterializationError(
                f"output {name} changed while being authenticated"
            )
        if payload != expected:
            raise ProviderCycleCapsMaterializationError(
                f"output {name} conflicts with deterministic output"
            )
        return payload, before_identity
    except OSError as exc:
        raise ProviderCycleCapsMaterializationError(
            f"output {name} changed while being authenticated"
        ) from exc
    finally:
        os.close(file_fd)


def _read_output(directory_fd: int, name: str) -> bytes | None:
    flags = (
        os.O_RDONLY
        | os.O_NONBLOCK
        | os.O_CLOEXEC
        | cast(int, getattr(os, "O_NOFOLLOW", 0))
    )
    try:
        file_fd = os.open(name, flags, dir_fd=directory_fd)
    except OSError as exc:
        if exc.errno == errno.ENOENT:
            return None
        raise ProviderCycleCapsMaterializationError(
            f"output {name} must be a unique regular file"
        ) from exc
    try:
        before = os.fstat(file_fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise ProviderCycleCapsMaterializationError(
                f"output {name} must be a unique regular file"
            )
        chunks: list[bytes] = []
        while chunk := os.read(file_fd, 1024 * 1024):
            chunks.append(chunk)
        after = os.fstat(file_fd)
        stable_fields = (
            "st_dev",
            "st_ino",
            "st_mode",
            "st_nlink",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
        )
        if any(
            getattr(before, field) != getattr(after, field) for field in stable_fields
        ):
            raise ProviderCycleCapsMaterializationError(
                f"output {name} changed while being verified"
            )
        payload = b"".join(chunks)
        if len(payload) != after.st_size:
            raise ProviderCycleCapsMaterializationError(
                f"output {name} changed while being verified"
            )
        return payload
    finally:
        os.close(file_fd)


def _publish_or_verify(directory_fd: int, name: str, payload: bytes) -> None:
    existing = _read_output(directory_fd, name)
    if existing is not None:
        if existing != payload:
            raise ProviderCycleCapsMaterializationError(
                f"output {name} conflicts with deterministic output"
            )
        return
    temporary = f".{name}.{secrets.token_hex(8)}.partial"
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | os.O_CLOEXEC
        | cast(int, getattr(os, "O_NOFOLLOW", 0))
    )
    temporary_fd: int | None = None
    try:
        temporary_fd = os.open(temporary, flags, 0o600, dir_fd=directory_fd)
        view = memoryview(payload)
        while view:
            written = os.write(temporary_fd, view)
            if written <= 0:  # pragma: no cover - OS invariant
                raise ProviderCycleCapsMaterializationError(
                    f"short write while publishing {name}"
                )
            view = view[written:]
        os.fsync(temporary_fd)
        os.close(temporary_fd)
        temporary_fd = None
        try:
            os.link(
                temporary,
                name,
                src_dir_fd=directory_fd,
                dst_dir_fd=directory_fd,
                follow_symlinks=False,
            )
        except FileExistsError:
            competing = _read_output(directory_fd, name)
            if competing != payload:
                raise ProviderCycleCapsMaterializationError(
                    f"output {name} conflicts with deterministic output"
                ) from None
        os.fsync(directory_fd)
    except ProviderCycleCapsMaterializationError:
        raise
    except OSError as exc:
        raise ProviderCycleCapsMaterializationError(
            f"output {name} cannot be published atomically"
        ) from exc
    finally:
        if temporary_fd is not None:
            os.close(temporary_fd)
        try:
            os.unlink(temporary, dir_fd=directory_fd)
        except FileNotFoundError:
            pass
        os.fsync(directory_fd)
    final = _read_output(directory_fd, name)
    if final != payload:
        raise ProviderCycleCapsMaterializationError(
            f"output {name} failed final byte verification"
        )


__all__ = [
    "AUTHORITY_SMOKE_SCHEMA_VERSION",
    "SUCCESSOR_POLICY_SCHEMA_VERSION",
    "SUCCESSOR_RECEIPT_SCHEMA_VERSION",
    "SUCCESSOR_STAGE",
    "MaterializedProviderCycleCaps",
    "ProviderCycleCapsMaterializationError",
    "PublishedProviderCycleCapsSuccessor",
    "canonical_json_bytes",
    "canonical_successor_receipt_bytes",
    "load_provider_cycle_caps_successor_policy",
    "materialize_provider_cycle_caps_successor_files",
    "verify_official_labeling_authority_smoke",
]
