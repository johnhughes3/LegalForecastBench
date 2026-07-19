"""Close an official cycle to new result mutations before publication."""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast
from urllib.parse import urlparse

from legalforecast.path_safety import safe_path_component

CYCLE_MUTATION_SCHEMA_VERSION = "legalforecast.cycle_mutation_closure.v1"
_STATE_NAMESPACE = "cycle-publication-state"
_MAX_SLEEP_SECONDS = 60.0


class CycleClosureError(ValueError):
    """Raised when the cycle mutation protocol cannot proceed safely."""


class CycleClosureConflictError(CycleClosureError):
    """Raised when an immutable protocol object has conflicting content."""


class CycleSealedError(CycleClosureError):
    """Raised after a late mutation has self-aborted against a cycle seal."""


class CycleDrainTimeoutError(CycleClosureError):
    """Raised when pre-seal mutations do not finish within the polling bound."""

    def __init__(self, cycle_id: str, pending: tuple[MutationIdentity, ...]) -> None:
        self.cycle_id = cycle_id
        self.pending = pending
        identities = ", ".join(
            f"{identity.run_id}/{identity.run_attempt}" for identity in pending
        )
        super().__init__(
            f"timed out waiting for cycle {cycle_id} mutations to finish: {identities}"
        )


@dataclass(frozen=True, order=True, slots=True)
class MutationIdentity:
    """Stable identity for one result-writing workflow run attempt."""

    cycle_id: str
    run_id: str
    run_attempt: int

    def __post_init__(self) -> None:
        _safe_id(self.cycle_id, field_name="cycle_id")
        _safe_id(self.run_id, field_name="run_id")
        _positive_attempt(self.run_attempt)


@dataclass(frozen=True, slots=True)
class SealWaitResult:
    """Evidence that a permanent seal exists and all observed intents drained."""

    seal_location: str
    observed_mutations: tuple[MutationIdentity, ...]


class CommandRunner(Protocol):
    """Callable shape used for unit-testable AWS CLI execution."""

    def __call__(
        self,
        command: list[str],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
    ) -> subprocess.CompletedProcess[str]: ...


class _ObjectStore(Protocol):
    def create(self, key: str, payload: bytes) -> str: ...

    def read(self, key: str) -> bytes | None: ...

    def list_keys(self, prefix: str) -> tuple[str, ...]: ...


@dataclass(slots=True)
class _LocalObjectStore:
    root: Path

    def create(self, key: str, payload: bytes) -> str:
        destination = self.root / key
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=destination.parent,
                prefix=f".{destination.name}.",
                delete=False,
            ) as handle:
                temporary_path = Path(handle.name)
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary_path, destination)
            except FileExistsError:
                existing = destination.read_bytes()
                if existing == payload:
                    return str(destination)
                raise CycleClosureConflictError(
                    f"immutable cycle closure object conflicts: {destination}"
                ) from None
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
        return str(destination)

    def read(self, key: str) -> bytes | None:
        path = self.root / key
        try:
            return path.read_bytes()
        except FileNotFoundError:
            return None

    def list_keys(self, prefix: str) -> tuple[str, ...]:
        base = self.root / prefix
        if not base.exists():
            return ()
        return tuple(
            sorted(
                path.relative_to(self.root).as_posix()
                for path in base.rglob("*")
                if path.is_file()
            )
        )


@dataclass(slots=True)
class _S3ObjectStore:
    bucket: str
    root_prefix: str
    run_command: CommandRunner

    def create(self, key: str, payload: bytes) -> str:
        object_key = self._object_key(key)
        with tempfile.NamedTemporaryFile(prefix="lfb-cycle-closure-") as handle:
            handle.write(payload)
            handle.flush()
            result = self._run(
                [
                    "aws",
                    "s3api",
                    "put-object",
                    "--bucket",
                    self.bucket,
                    "--key",
                    object_key,
                    "--body",
                    handle.name,
                    "--content-type",
                    "application/json",
                    "--if-none-match",
                    "*",
                ]
            )
        if result.returncode == 0:
            return f"s3://{self.bucket}/{object_key}"
        if not _is_create_conflict(result):
            raise CycleClosureError(
                f"cycle closure S3 create failed for {object_key}: "
                f"{_command_error(result)}"
            )
        existing = self.read(key)
        if existing == payload:
            return f"s3://{self.bucket}/{object_key}"
        if existing is None:
            raise CycleClosureError(
                f"cycle closure S3 create conflicted but object is unreadable: "
                f"{object_key}"
            )
        raise CycleClosureConflictError(
            f"immutable cycle closure object conflicts: s3://{self.bucket}/{object_key}"
        )

    def read(self, key: str) -> bytes | None:
        object_key = self._object_key(key)
        with tempfile.TemporaryDirectory(prefix="lfb-cycle-closure-read-") as directory:
            destination = Path(directory) / "object"
            result = self._run(
                [
                    "aws",
                    "s3api",
                    "get-object",
                    "--bucket",
                    self.bucket,
                    "--key",
                    object_key,
                    str(destination),
                ]
            )
            if result.returncode == 0:
                return destination.read_bytes()
        if _is_missing_object(result):
            return None
        raise CycleClosureError(
            f"cycle closure S3 read failed for {object_key}: {_command_error(result)}"
        )

    def list_keys(self, prefix: str) -> tuple[str, ...]:
        object_prefix = self._object_key(prefix)
        keys: list[str] = []
        continuation_token: str | None = None
        while True:
            command = [
                "aws",
                "s3api",
                "list-objects-v2",
                "--bucket",
                self.bucket,
                "--prefix",
                object_prefix,
                "--output",
                "json",
            ]
            if continuation_token is not None:
                command.extend(["--continuation-token", continuation_token])
            result = self._run(command)
            if result.returncode != 0:
                raise CycleClosureError(
                    f"cycle closure S3 list failed for {object_prefix}: "
                    f"{_command_error(result)}"
                )
            page = _json_mapping(result.stdout, label="S3 list response")
            contents = page.get("Contents", [])
            if not isinstance(contents, list):
                raise CycleClosureError("S3 list response Contents must be an array")
            for raw in cast(list[object], contents):
                item = _mapping(raw, label="S3 list object")
                object_key = item.get("Key")
                if not isinstance(object_key, str):
                    raise CycleClosureError("S3 list object requires a string Key")
                relative = self._relative_key(object_key)
                if relative is not None:
                    keys.append(relative)
            if not page.get("IsTruncated", False):
                break
            next_token = page.get("NextContinuationToken")
            if not isinstance(next_token, str) or not next_token:
                raise CycleClosureError(
                    "truncated S3 list response requires NextContinuationToken"
                )
            continuation_token = next_token
        return tuple(sorted(set(keys)))

    def _run(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        try:
            return self.run_command(
                command,
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError as exc:
            raise CycleClosureError(f"could not execute AWS CLI: {exc}") from exc

    def _object_key(self, key: str) -> str:
        return f"{self.root_prefix}/{key}" if self.root_prefix else key

    def _relative_key(self, object_key: str) -> str | None:
        if not self.root_prefix:
            return object_key
        prefix = f"{self.root_prefix}/"
        return object_key[len(prefix) :] if object_key.startswith(prefix) else None


def seal_key(cycle_id: str) -> str:
    """Return the permanent seal key outside shard-receipt discovery."""

    cycle = _safe_id(cycle_id, field_name="cycle_id")
    return f"{_STATE_NAMESPACE}/{cycle}/seal.json"


def intent_key(identity: MutationIdentity) -> str:
    """Return the immutable intent key for one mutation identity."""

    prefix = _runs_prefix(identity.cycle_id)
    return f"{prefix}{identity.run_id}/{identity.run_attempt}/intent.json"


def done_key(identity: MutationIdentity) -> str:
    """Return the immutable completion key for one mutation identity."""

    prefix = _runs_prefix(identity.cycle_id)
    return f"{prefix}{identity.run_id}/{identity.run_attempt}/done.json"


def seal_payload(cycle_id: str) -> bytes:
    """Build the canonical deterministic seal payload."""

    cycle = _safe_id(cycle_id, field_name="cycle_id")
    return _payload({"cycle_id": cycle, "record_type": "seal"})


def intent_payload(identity: MutationIdentity) -> bytes:
    """Build the canonical deterministic intent payload."""

    return _mutation_payload(identity, record_type="intent")


def done_payload(identity: MutationIdentity) -> bytes:
    """Build the canonical deterministic completion payload."""

    return _mutation_payload(identity, record_type="done")


def begin(
    root: str | Path,
    *,
    cycle_id: str,
    run_id: str,
    run_attempt: int,
    run_command: CommandRunner | None = None,
) -> MutationIdentity:
    """Declare a mutation before checking whether the cycle has been sealed."""

    identity = MutationIdentity(cycle_id, run_id, run_attempt)
    store = _object_store(root, run_command=run_command)
    store.create(intent_key(identity), intent_payload(identity))
    existing_seal = store.read(seal_key(identity.cycle_id))
    if existing_seal is None:
        return identity
    _require_exact_payload(
        existing_seal,
        seal_payload(identity.cycle_id),
        key=seal_key(identity.cycle_id),
    )
    _finish(store, identity)
    raise CycleSealedError(
        f"cycle {identity.cycle_id} is sealed; mutation "
        f"{identity.run_id}/{identity.run_attempt} was aborted"
    )


def finish(
    root: str | Path,
    *,
    identity: MutationIdentity | None = None,
    cycle_id: str | None = None,
    run_id: str | None = None,
    run_attempt: int | None = None,
    run_command: CommandRunner | None = None,
) -> MutationIdentity:
    """Mark one declared mutation done after validating its exact intent."""

    resolved = _resolve_identity(
        identity,
        cycle_id=cycle_id,
        run_id=run_id,
        run_attempt=run_attempt,
    )
    store = _object_store(root, run_command=run_command)
    _finish(store, resolved)
    return resolved


def seal_wait(
    root: str | Path,
    *,
    cycle_id: str,
    timeout_seconds: float = 300.0,
    poll_interval_seconds: float = 1.0,
    run_command: CommandRunner | None = None,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> SealWaitResult:
    """Permanently seal a cycle and wait for every observed intent to finish."""

    cycle = _safe_id(cycle_id, field_name="cycle_id")
    timeout = _nonnegative_finite(timeout_seconds, field_name="timeout_seconds")
    poll_interval = _positive_poll_interval(poll_interval_seconds)
    store = _object_store(root, run_command=run_command)
    location = store.create(seal_key(cycle), seal_payload(cycle))
    deadline = monotonic() + timeout
    observed: set[MutationIdentity] = set()
    while True:
        pending, current = _pending_mutations(store, cycle)
        observed.update(current)
        if not pending:
            return SealWaitResult(location, tuple(sorted(observed)))
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise CycleDrainTimeoutError(cycle, pending)
        sleep(min(poll_interval, remaining, _MAX_SLEEP_SECONDS))


def build_parser() -> argparse.ArgumentParser:
    """Build the cycle mutation closure command-line interface."""

    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("begin", "finish"):
        operation = subparsers.add_parser(command)
        _add_root_and_cycle_arguments(operation)
        operation.add_argument("--writer-id", "--run-id", dest="run_id", required=True)
        operation.add_argument("--run-attempt", required=True, type=int)
    seal = subparsers.add_parser("seal-wait")
    _add_root_and_cycle_arguments(seal)
    seal.add_argument("--timeout-seconds", type=float, default=300.0)
    seal.add_argument("--poll-interval-seconds", type=float, default=1.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Execute one mutation-closure operation and emit machine-readable evidence."""

    args = build_parser().parse_args(argv)
    root = cast(str, args.root)
    cycle_id = cast(str, args.cycle_id)
    if args.command == "begin":
        identity = begin(
            root,
            cycle_id=cycle_id,
            run_id=cast(str, args.run_id),
            run_attempt=cast(int, args.run_attempt),
        )
        record = _identity_record(identity, status="mutation-open")
    elif args.command == "finish":
        identity = finish(
            root,
            cycle_id=cycle_id,
            run_id=cast(str, args.run_id),
            run_attempt=cast(int, args.run_attempt),
        )
        record = _identity_record(identity, status="mutation-finished")
    elif args.command == "seal-wait":
        result = seal_wait(
            root,
            cycle_id=cycle_id,
            timeout_seconds=cast(float, args.timeout_seconds),
            poll_interval_seconds=cast(float, args.poll_interval_seconds),
        )
        record = {
            "cycle_id": cycle_id,
            "observed_mutation_count": len(result.observed_mutations),
            "seal_location": result.seal_location,
            "status": "cycle-sealed",
        }
    else:  # pragma: no cover - argparse enforces the command set.
        raise CycleClosureError(f"unsupported cycle closure operation: {args.command}")
    print(json.dumps(record, sort_keys=True, separators=(",", ":")))
    return 0


def _finish(store: _ObjectStore, identity: MutationIdentity) -> None:
    expected_intent = intent_payload(identity)
    existing_intent = store.read(intent_key(identity))
    if existing_intent is None:
        raise CycleClosureError(
            f"finish requires matching intent identity: {identity.run_id}/"
            f"{identity.run_attempt}"
        )
    _require_exact_payload(
        existing_intent,
        expected_intent,
        key=intent_key(identity),
    )
    store.create(done_key(identity), done_payload(identity))


def _pending_mutations(
    store: _ObjectStore, cycle_id: str
) -> tuple[tuple[MutationIdentity, ...], tuple[MutationIdentity, ...]]:
    prefix = _runs_prefix(cycle_id)
    identities: set[MutationIdentity] = set()
    for key in store.list_keys(prefix):
        if not key.endswith("/intent.json"):
            continue
        suffix = key.removeprefix(prefix)
        parts = suffix.split("/")
        if len(parts) != 3 or parts[2] != "intent.json":
            raise CycleClosureError(f"invalid mutation intent key: {key}")
        try:
            attempt = int(parts[1])
        except ValueError as exc:
            raise CycleClosureError(f"invalid mutation intent key: {key}") from exc
        try:
            identity = MutationIdentity(cycle_id, parts[0], attempt)
        except ValueError as exc:
            raise CycleClosureError(f"invalid mutation intent key: {key}") from exc
        if intent_key(identity) != key:
            raise CycleClosureError(f"invalid mutation intent key: {key}")
        existing_intent = store.read(key)
        if existing_intent is None:
            raise CycleClosureError(f"listed mutation intent disappeared: {key}")
        _require_exact_payload(existing_intent, intent_payload(identity), key=key)
        identities.add(identity)
    pending: list[MutationIdentity] = []
    for identity in sorted(identities):
        completion = store.read(done_key(identity))
        if completion is None:
            pending.append(identity)
            continue
        _require_exact_payload(
            completion,
            done_payload(identity),
            key=done_key(identity),
        )
    return tuple(pending), tuple(sorted(identities))


def _resolve_identity(
    identity: MutationIdentity | None,
    *,
    cycle_id: str | None,
    run_id: str | None,
    run_attempt: int | None,
) -> MutationIdentity:
    supplied_fields = (cycle_id, run_id, run_attempt)
    if identity is not None:
        if any(field is not None for field in supplied_fields):
            raise ValueError("provide identity or cycle/run/attempt fields, not both")
        return identity
    if cycle_id is None or run_id is None or run_attempt is None:
        raise ValueError("cycle_id, run_id, and run_attempt are required")
    return MutationIdentity(cycle_id, run_id, run_attempt)


def _object_store(
    root: str | Path, *, run_command: CommandRunner | None
) -> _ObjectStore:
    if isinstance(root, str) and root.startswith("s3://"):
        parsed = urlparse(root)
        if parsed.scheme != "s3" or not parsed.netloc:
            raise ValueError("S3 root must include a bucket")
        if parsed.params or parsed.query or parsed.fragment:
            raise ValueError("S3 root must not include params, query, or fragment")
        runner = run_command or cast(CommandRunner, subprocess.run)
        return _S3ObjectStore(
            bucket=parsed.netloc,
            root_prefix=parsed.path.strip("/"),
            run_command=runner,
        )
    if run_command is not None:
        raise ValueError("run_command is only valid for an S3 root")
    return _LocalObjectStore(Path(root))


def _runs_prefix(cycle_id: str) -> str:
    cycle = _safe_id(cycle_id, field_name="cycle_id")
    return f"{_STATE_NAMESPACE}/{cycle}/runs/"


def _mutation_payload(identity: MutationIdentity, *, record_type: str) -> bytes:
    return _payload(
        {
            "cycle_id": identity.cycle_id,
            "record_type": record_type,
            "run_attempt": identity.run_attempt,
            "run_id": identity.run_id,
        }
    )


def _payload(record: Mapping[str, Any]) -> bytes:
    complete = {**record, "schema_version": CYCLE_MUTATION_SCHEMA_VERSION}
    return (json.dumps(complete, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _require_exact_payload(actual: bytes, expected: bytes, *, key: str) -> None:
    if actual != expected:
        raise CycleClosureConflictError(
            f"immutable cycle closure object conflicts: {key}"
        )


def _safe_id(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    return safe_path_component(value, field_name=field_name)


def _positive_attempt(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("run_attempt must be a positive integer")
    return value


def _nonnegative_finite(value: object, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a finite nonnegative number")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{field_name} must be a finite nonnegative number")
    return number


def _positive_poll_interval(value: float) -> float:
    number = _nonnegative_finite(value, field_name="poll_interval_seconds")
    if number <= 0 or number > _MAX_SLEEP_SECONDS:
        raise ValueError("poll_interval_seconds must be greater than 0 and at most 60")
    return number


def _identity_record(identity: MutationIdentity, *, status: str) -> dict[str, Any]:
    return {
        "cycle_id": identity.cycle_id,
        "run_attempt": identity.run_attempt,
        "run_id": identity.run_id,
        "status": status,
    }


def _add_root_and_cycle_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", required=True)
    parser.add_argument("--cycle-id", required=True)


def _is_create_conflict(result: subprocess.CompletedProcess[str]) -> bool:
    message = _command_error(result)
    return any(
        marker in message
        for marker in ("PreconditionFailed", "ConditionalRequestConflict", "412", "409")
    )


def _is_missing_object(result: subprocess.CompletedProcess[str]) -> bool:
    message = _command_error(result)
    return any(
        marker in message for marker in ("NoSuchKey", "Not Found", "NotFound", "404")
    )


def _command_error(result: subprocess.CompletedProcess[str]) -> str:
    return (result.stderr or result.stdout or f"exit {result.returncode}").strip()


def _json_mapping(payload: str, *, label: str) -> Mapping[str, Any]:
    try:
        value: object = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise CycleClosureError(f"{label} is not valid JSON") from exc
    return _mapping(value, label=label)


def _mapping(value: object, *, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise CycleClosureError(f"{label} must be a JSON object")
    return cast(Mapping[str, Any], value)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
