"""Shared validation primitives for the non-authoritative replay spec."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, cast

from legalforecast.contracts import ARTIFACT_CANONICAL_JSON_V1

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")

AUTHORIZATION_SCHEMA_VERSION = (
    # contract-ratchet: allow non-authoritative Stage A spend authorization sidecar
    "legalforecast.candidate_scoped_stage_a_authorization.v1"
)
AUTHORIZATION_SIGNATURE_NAMESPACE = "legalforecast-stage-a-replay"


class StageAReplayExecutorError(ValueError):
    """Raised when executor authority or persisted evidence is invalid."""


class ReplaySpendCeilingError(StageAReplayExecutorError):
    """Raised when a provider invocation reaches signed spend authority."""

    def __init__(self, message: str, *, candidate_id: str | None = None) -> None:
        super().__init__(message)
        self.candidate_id = candidate_id


class ReplayOutputClaimError(StageAReplayExecutorError):
    """Raised when another executor already owns the spec's output paths."""


def validate_authorization(
    authorization: Mapping[str, object],
    candidate_ids: tuple[str, ...],
    *,
    replay_descriptor_sha256: str,
    now: datetime | None,
) -> tuple[Path, Mapping[str, object], bool]:
    required = {
        "mode",
        "artifact_path",
        "artifact_sha256",
        "signature_path",
        "signature_sha256",
        "signature_namespace",
        "signer_principal",
    }
    if set(authorization) != required:
        raise StageAReplayExecutorError("authorization descriptor fields differ")
    mode = text_value(authorization, "mode")
    if mode not in {"git_allowed_signers_sshsig", "synthetic_fixture"}:
        raise StageAReplayExecutorError("authorization mode is unsupported")
    synthetic = mode == "synthetic_fixture"
    artifact_path = path_value(authorization, "artifact_path")
    artifact_payload = read_regular(artifact_path, "authorization artifact")
    if hashlib.sha256(artifact_payload).hexdigest() != digest(
        authorization, "artifact_sha256"
    ):
        raise StageAReplayExecutorError(
            "authorization artifact differs from its SHA-256 pin"
        )
    try:
        loaded: object = json.loads(artifact_payload)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise StageAReplayExecutorError(
            "authorization artifact is not valid JSON"
        ) from exc
    if not isinstance(loaded, Mapping):
        raise StageAReplayExecutorError("authorization artifact must be an object")
    artifact = cast(Mapping[str, object], loaded)
    if canonical(artifact) != artifact_payload:
        raise StageAReplayExecutorError("authorization artifact is not canonical JSON")
    artifact_fields = {
        "schema_version",
        "request_artifact_path",
        "request_artifact_sha256",
        "approval_text",
        "expires_at",
        "candidate_ids",
        "estimated_cost_usd",
        "hard_ceiling_usd",
        "replay_descriptor_sha256",
    }
    if (
        set(artifact) != artifact_fields
        or artifact.get("schema_version") != AUTHORIZATION_SCHEMA_VERSION
    ):
        raise StageAReplayExecutorError(
            "authorization artifact fields or schema_version differ"
        )
    if digest(artifact, "replay_descriptor_sha256") != replay_descriptor_sha256:
        raise StageAReplayExecutorError(
            "signed authorization replay descriptor differs from replay-spec"
        )

    request_path = path_value(artifact, "request_artifact_path")
    request_payload = read_regular(request_path, "authorization request artifact")
    request_sha256 = digest(artifact, "request_artifact_sha256")
    if hashlib.sha256(request_payload).hexdigest() != request_sha256:
        raise StageAReplayExecutorError(
            "authorization request artifact differs from its SHA-256 pin"
        )
    approval = text_value(artifact, "approval_text")
    expiry_text = text_value(artifact, "expires_at")
    try:
        expiry = datetime.fromisoformat(expiry_text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise StageAReplayExecutorError(
            "signed authorization expiry is invalid"
        ) from exc
    if expiry.tzinfo is None:
        raise StageAReplayExecutorError(
            "signed authorization expiry must include timezone"
        )
    if (now or datetime.now(UTC)) >= expiry.astimezone(UTC):
        raise StageAReplayExecutorError("signed authorization has expired")
    if candidate_ids_value(artifact.get("candidate_ids"), "authorization") != (
        candidate_ids
    ):
        raise StageAReplayExecutorError("signed authorization candidate set differs")
    estimated = decimal_value(artifact, "estimated_cost_usd")
    hard_ceiling = decimal_value(artifact, "hard_ceiling_usd")
    if estimated > hard_ceiling:
        raise StageAReplayExecutorError(
            "signed authorization estimate exceeds its hard ceiling"
        )
    approval_tokens = (
        *candidate_ids,
        f"USD {estimated:.2f}",
        f"USD {hard_ceiling:.2f}",
    )
    if not synthetic and any(token not in approval for token in approval_tokens):
        raise StageAReplayExecutorError(
            "signed authorization text does not bind candidates and spend ceilings"
        )
    namespace = text_value(authorization, "signature_namespace")
    if namespace != AUTHORIZATION_SIGNATURE_NAMESPACE:
        raise StageAReplayExecutorError("authorization signature namespace differs")
    principal = text_value(authorization, "signer_principal")
    signature_path = optional_path(authorization, "signature_path")
    signature_sha256 = authorization.get("signature_sha256")
    if synthetic:
        if (
            signature_path is not None
            or signature_sha256 is not None
            or principal != "synthetic:true"
        ):
            raise StageAReplayExecutorError(
                "synthetic authorization may not carry signer authority"
            )
    else:
        if signature_path is None:
            raise StageAReplayExecutorError(
                "production authorization requires a detached SSH signature"
            )
        signature_payload = read_regular(
            signature_path, "authorization detached SSH signature"
        )
        if hashlib.sha256(signature_payload).hexdigest() != digest(
            authorization, "signature_sha256"
        ):
            raise StageAReplayExecutorError(
                "authorization detached signature differs from its SHA-256 pin"
            )
        verify_authorization_signature(
            artifact_payload,
            signature_path=signature_path,
            signer_principal=principal,
            namespace=namespace,
        )
    return request_path, artifact, synthetic


def verify_authorization_signature(
    artifact_payload: bytes,
    *,
    signature_path: Path,
    signer_principal: str,
    namespace: str,
) -> None:
    """Verify owner authority against Git's configured SSH allowed-signers file."""

    try:
        configured = subprocess.run(
            ["git", "config", "--path", "--get", "gpg.ssh.allowedSignersFile"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise StageAReplayExecutorError(
            "Git SSH allowed-signers configuration is unavailable"
        ) from exc
    allowed_signers = Path(configured).expanduser()
    read_regular(allowed_signers, "Git SSH allowed-signers file")
    try:
        subprocess.run(
            [
                "ssh-keygen",
                "-Y",
                "verify",
                "-f",
                str(allowed_signers),
                "-I",
                signer_principal,
                "-n",
                namespace,
                "-s",
                str(signature_path),
            ],
            input=artifact_payload,
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise StageAReplayExecutorError(
            "authorization detached SSH signature is invalid for the configured signer"
        ) from exc


def validate_spend(
    spend: Mapping[str, object],
    authorization_artifact: Mapping[str, object],
    candidate_ids: tuple[str, ...],
) -> tuple[Decimal, dict[str, Decimal], dict[str, Decimal]]:
    if set(spend) != {
        "aggregate_ceiling_usd",
        "per_candidate_ceiling_usd",
        "invocation_reservations_usd",
    }:
        raise StageAReplayExecutorError("spend descriptor fields differ")
    aggregate = decimal_value(spend, "aggregate_ceiling_usd")
    if aggregate != decimal_value(authorization_artifact, "hard_ceiling_usd"):
        raise StageAReplayExecutorError(
            "spend aggregate ceiling differs from signed authorization hard ceiling"
        )
    per_raw = mapping_value(spend, "per_candidate_ceiling_usd")
    if set(per_raw) != set(candidate_ids):
        raise StageAReplayExecutorError(
            "spend per_candidate_ceiling_usd must cover exactly the candidate set"
        )
    per = {
        candidate: parse_decimal(per_raw[candidate], candidate)
        for candidate in candidate_ids
    }
    if any(value > aggregate for value in per.values()):
        raise StageAReplayExecutorError(
            "a per-candidate ceiling exceeds the aggregate ceiling"
        )
    reservations_raw = mapping_value(spend, "invocation_reservations_usd")
    if set(reservations_raw) != {"unitizer", "reviewer"}:
        raise StageAReplayExecutorError(
            "invocation reservations must name unitizer and reviewer"
        )
    reservations = {
        stage: parse_decimal(reservations_raw[stage], stage)
        for stage in ("unitizer", "reviewer")
    }
    return aggregate, per, reservations


def candidate_ids_value(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise StageAReplayExecutorError(
            f"{label} candidate_ids must be a non-empty array"
        )
    result: list[str] = []
    for item in cast(list[object], value):
        if not isinstance(item, str) or not item.strip():
            raise StageAReplayExecutorError(
                f"{label} candidate_id must be non-empty text"
            )
        if item in result:
            raise StageAReplayExecutorError(f"{label} repeats candidate {item}")
        result.append(item)
    return tuple(result)


def read_regular(path: Path, label: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise StageAReplayExecutorError(f"{label} is not a regular file: {path}")
    try:
        return path.read_bytes()
    except OSError as exc:
        raise StageAReplayExecutorError(f"cannot read {label}: {path}") from exc


def parse_strict_jsonl(payload: bytes) -> tuple[Mapping[str, Any], ...]:
    """Decode non-empty object rows with an exact trailing newline."""

    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise StageAReplayExecutorError("Stage A JSONL is not UTF-8") from exc
    if not text.endswith("\n"):
        raise StageAReplayExecutorError("Stage A JSONL lacks its trailing newline")
    lines = text[:-1].split("\n")
    if any(not line for line in lines):
        raise StageAReplayExecutorError("Stage A JSONL contains a blank row")
    records: list[Mapping[str, Any]] = []
    for line in lines:
        value = json.loads(line)
        if not isinstance(value, Mapping):
            raise StageAReplayExecutorError("Stage A JSONL row is not an object")
        records.append(cast(Mapping[str, Any], value))
    if not records:
        raise StageAReplayExecutorError("Stage A JSONL is empty")
    return tuple(records)


def path_value(record: Mapping[str, object], field: str) -> Path:
    value = text_value(record, field)
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts or path.resolve() != path:
        raise StageAReplayExecutorError(f"{field} must be an absolute canonical path")
    return path


def optional_path(record: Mapping[str, object], field: str) -> Path | None:
    return None if record.get(field) is None else path_value(record, field)


def mapping_value(record: Mapping[str, object], field: str) -> Mapping[str, object]:
    value = record.get(field)
    if not isinstance(value, Mapping):
        raise StageAReplayExecutorError(f"{field} must be an object")
    return cast(Mapping[str, object], value)


def text_value(record: Mapping[str, object], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise StageAReplayExecutorError(f"{field} must be non-empty text")
    return value


def digest(record: Mapping[str, object], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise StageAReplayExecutorError(f"{field} must be a lowercase SHA-256 digest")
    return value


def decimal_value(record: Mapping[str, object], field: str) -> Decimal:
    return parse_decimal(record.get(field), field)


def parse_decimal(value: object, field: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise StageAReplayExecutorError(f"{field} must be a non-negative decimal")
    try:
        parsed = Decimal(str(value))
    except InvalidOperation as exc:
        raise StageAReplayExecutorError(
            f"{field} must be a non-negative decimal"
        ) from exc
    if not parsed.is_finite() or parsed < 0:
        raise StageAReplayExecutorError(f"{field} must be a non-negative decimal")
    return parsed


def canonical(value: object) -> bytes:
    return ARTIFACT_CANONICAL_JSON_V1.encode(value)


def replay_descriptor(record: Mapping[str, object]) -> dict[str, object]:
    """Return the exact operative replay fields covered by owner authority."""

    fields = (
        "schema_version",
        "candidate_ids",
        "lineage",
        "configuration",
        "spend",
        "provider",
        "outputs",
        "code_commit",
    )
    try:
        return {field: record[field] for field in fields}
    except KeyError as exc:
        raise StageAReplayExecutorError(
            f"replay-spec lacks authorized field {exc.args[0]}"
        ) from exc


# contract-ratchet: allow non-persisted replay-sidecar digest
def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
