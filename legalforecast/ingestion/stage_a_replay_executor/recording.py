"""Canonical recorder binding owner authorization to one replay descriptor.

The owner's typed approval is the authorization event.  This module records it:
it embeds the pasted text verbatim in a canonical authorization artifact that
commits to the replay descriptor hash, attaches the detached SSH signature the
executor verifies against Git's allowed-signers file, assembles the finished
self-hashed replay spec, and then proves the result by loading it through the
executor's own validator.

Nothing here can widen authority.  The recorder refuses to invent approval text,
and a spec it emits is accepted only if ``load_replay_spec`` accepts it.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import cast

from legalforecast.config.registry import repository_root
from legalforecast.ingestion.stage_a_replay_executor.contract import (
    AUTHORIZATION_SCHEMA_VERSION,
    AUTHORIZATION_SIGNATURE_NAMESPACE,
    StageAReplayExecutorError,
    decimal_value,
    trusted_git_environment,
)
from legalforecast.ingestion.stage_a_replay_executor.contract import (
    canonical as _canonical,
)
from legalforecast.ingestion.stage_a_replay_executor.contract import (
    read_regular as _read_regular,
)
from legalforecast.ingestion.stage_a_replay_executor.contract import (
    replay_descriptor as _replay_descriptor,
)
from legalforecast.ingestion.stage_a_replay_executor.contract import (
    sha256_bytes as _sha256_bytes,
)
from legalforecast.ingestion.stage_a_replay_executor.spec import (
    ReplaySpec,
    load_replay_spec,
)

AUTHORIZATION_MODE = "git_allowed_signers_sshsig"

__all__ = (
    "AUTHORIZATION_MODE",
    "RecordedReplaySpec",
    "build_authorization_artifact",
    "record_replay_authorization",
    "record_replay_authorization_command",
    "sign_authorization_artifact",
)


@dataclass(frozen=True, slots=True)
class RecordedReplaySpec:
    """One finished replay spec plus the artifacts the executor re-reads."""

    spec_path: Path
    spec_sha256: str
    authorization_path: Path
    authorization_sha256: str
    signature_path: Path
    signature_sha256: str
    descriptor_sha256: str
    spec: ReplaySpec


def build_authorization_artifact(
    *,
    descriptor_sha256: str,
    approval_text: str,
    request_artifact_path: Path,
    expires_at: datetime,
    candidate_ids: Sequence[str],
    estimated_cost_usd: Decimal,
    hard_ceiling_usd: Decimal,
) -> dict[str, object]:
    """Return the canonical artifact the owner signature covers."""

    if expires_at.tzinfo is None:
        raise StageAReplayExecutorError(
            "authorization expiry must carry a timezone offset"
        )
    if expires_at.astimezone(UTC) <= datetime.now(UTC):
        raise StageAReplayExecutorError("authorization expiry is already past")
    if estimated_cost_usd > hard_ceiling_usd:
        raise StageAReplayExecutorError(
            "authorization estimate exceeds its hard ceiling"
        )
    _require_bound_approval_text(
        approval_text,
        candidate_ids=candidate_ids,
        estimated_cost_usd=estimated_cost_usd,
        hard_ceiling_usd=hard_ceiling_usd,
        descriptor_sha256=descriptor_sha256,
    )
    request_payload = _read_regular(request_artifact_path, "authorization request")
    return {
        "schema_version": AUTHORIZATION_SCHEMA_VERSION,
        "request_artifact_path": str(request_artifact_path),
        "request_artifact_sha256": _sha256_bytes(request_payload),
        "approval_text": approval_text,
        "expires_at": expires_at.isoformat(),
        "candidate_ids": list(candidate_ids),
        "estimated_cost_usd": format(estimated_cost_usd, "f"),
        "hard_ceiling_usd": format(hard_ceiling_usd, "f"),
        "replay_descriptor_sha256": descriptor_sha256,
    }


def sign_authorization_artifact(
    artifact_path: Path, *, signing_key: Path | None = None
) -> Path:
    """Produce the detached SSHSIG the executor verifies, using Git's key."""

    key = signing_key or _git_signing_key()
    signature_path = artifact_path.with_name(f"{artifact_path.name}.sig")
    if signature_path.exists() or signature_path.is_symlink():
        raise StageAReplayExecutorError(
            f"detached signature already exists: {signature_path}"
        )
    try:
        subprocess.run(
            [
                "ssh-keygen",
                "-Y",
                "sign",
                "-f",
                str(key),
                "-n",
                AUTHORIZATION_SIGNATURE_NAMESPACE,
                str(artifact_path),
            ],
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = (
            exc.stderr.decode("utf-8", "replace").strip()
            if isinstance(exc, subprocess.CalledProcessError)
            else str(exc)
        )
        raise StageAReplayExecutorError(
            f"cannot produce the detached authorization signature: {detail}"
        ) from exc
    if not signature_path.is_file():
        raise StageAReplayExecutorError(
            "ssh-keygen did not write the detached authorization signature"
        )
    return signature_path


def record_replay_authorization(
    descriptor: Mapping[str, object],
    *,
    approval_text: str,
    request_artifact_path: Path,
    expires_at: datetime,
    estimated_cost_usd: Decimal,
    hard_ceiling_usd: Decimal,
    signer_principal: str,
    output_dir: Path,
    signature_path: Path | None = None,
    signing_key: Path | None = None,
    now: datetime | None = None,
) -> RecordedReplaySpec:
    """Bind the owner's paste to one descriptor and emit the executable spec."""

    if not approval_text.strip():
        raise StageAReplayExecutorError(
            "owner approval text is required; the recorder never authors it"
        )
    descriptor_sha256 = _sha256_bytes(_canonical(_replay_descriptor(descriptor)))
    candidate_ids = _descriptor_candidate_ids(descriptor)
    artifact = build_authorization_artifact(
        descriptor_sha256=descriptor_sha256,
        approval_text=approval_text,
        request_artifact_path=request_artifact_path,
        expires_at=expires_at,
        candidate_ids=candidate_ids,
        estimated_cost_usd=estimated_cost_usd,
        hard_ceiling_usd=hard_ceiling_usd,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    authorization_path = output_dir / "authorization.json"
    if authorization_path.exists() or authorization_path.is_symlink():
        raise StageAReplayExecutorError(
            f"authorization artifact already exists: {authorization_path}"
        )
    authorization_payload = _canonical(artifact)
    authorization_path.write_bytes(authorization_payload)
    recorded_signature = signature_path or sign_authorization_artifact(
        authorization_path, signing_key=signing_key
    )
    signature_payload = _read_regular(
        recorded_signature, "authorization detached SSH signature"
    )
    spec_record = {
        **dict(descriptor),
        "authorization": {
            "mode": AUTHORIZATION_MODE,
            "artifact_path": str(authorization_path.resolve()),
            "artifact_sha256": _sha256_bytes(authorization_payload),
            "signature_path": str(recorded_signature.resolve()),
            "signature_sha256": _sha256_bytes(signature_payload),
            "signature_namespace": AUTHORIZATION_SIGNATURE_NAMESPACE,
            "signer_principal": signer_principal,
        },
    }
    spec_record.pop("replay_spec_sha256", None)
    spec_sha256 = _sha256_bytes(_canonical(spec_record))
    spec_record["replay_spec_sha256"] = spec_sha256
    spec_path = output_dir / "replay-spec.json"
    if spec_path.exists() or spec_path.is_symlink():
        raise StageAReplayExecutorError(f"replay spec already exists: {spec_path}")
    spec_path.write_bytes(_canonical(spec_record))
    # Prove the artifact through the executor's validator, not a local copy of
    # its rules: signature, expiry, ceilings, lineage shape, and output isolation.
    spec = load_replay_spec(spec_path, now=now)
    if spec.spec_sha256 != spec_sha256:
        raise StageAReplayExecutorError("recorded replay spec hash did not round-trip")
    return RecordedReplaySpec(
        spec_path=spec_path,
        spec_sha256=spec_sha256,
        authorization_path=authorization_path,
        authorization_sha256=_sha256_bytes(authorization_payload),
        signature_path=recorded_signature,
        signature_sha256=_sha256_bytes(signature_payload),
        descriptor_sha256=descriptor_sha256,
        spec=spec,
    )


def record_replay_authorization_command(
    *,
    replay_descriptor: Path,
    approval_text_file: Path,
    request_artifact: Path,
    expires_at: str,
    estimated_cost_usd: str,
    signer_principal: str,
    output_dir: Path,
    signature: Path | None,
    signing_key: Path | None,
) -> dict[str, object]:
    """Run the ``record-replay-authorization`` command over file inputs.

    The hard ceiling is read out of the descriptor rather than retyped, so the
    recorded authorization can never disagree with the spend block the owner is
    signing.
    """

    descriptor = _descriptor_record(replay_descriptor)
    spend = descriptor.get("spend")
    if not isinstance(spend, Mapping):
        raise StageAReplayExecutorError("replay descriptor spend must be an object")
    hard_ceiling = decimal_value(
        cast(Mapping[str, object], spend), "aggregate_ceiling_usd"
    )
    recorded = record_replay_authorization(
        descriptor,
        approval_text=approval_text_file.read_text(encoding="utf-8").strip(),
        request_artifact_path=request_artifact.resolve(),
        expires_at=datetime.fromisoformat(expires_at.replace("Z", "+00:00")),
        estimated_cost_usd=Decimal(estimated_cost_usd),
        hard_ceiling_usd=hard_ceiling,
        signer_principal=signer_principal,
        output_dir=output_dir,
        signature_path=signature,
        signing_key=signing_key,
    )
    return {
        "replay_spec_path": str(recorded.spec_path),
        "replay_spec_sha256": recorded.spec_sha256,
        "replay_descriptor_sha256": recorded.descriptor_sha256,
        "authorization_path": str(recorded.authorization_path),
        "authorization_sha256": recorded.authorization_sha256,
        "signature_path": str(recorded.signature_path),
        "signature_sha256": recorded.signature_sha256,
    }


def _descriptor_record(path: Path) -> Mapping[str, object]:
    payload = _read_regular(path.resolve(), "replay descriptor")
    try:
        loaded: object = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StageAReplayExecutorError("replay descriptor is not valid JSON") from exc
    if not isinstance(loaded, dict):
        raise StageAReplayExecutorError("replay descriptor must be a JSON object")
    return cast(dict[str, object], loaded)


def _require_bound_approval_text(
    approval_text: str,
    *,
    candidate_ids: Sequence[str],
    estimated_cost_usd: Decimal,
    hard_ceiling_usd: Decimal,
    descriptor_sha256: str,
) -> None:
    missing = [
        token
        for token in (
            *candidate_ids,
            f"USD {estimated_cost_usd:.2f}",
            f"USD {hard_ceiling_usd:.2f}",
            descriptor_sha256,
        )
        if token not in approval_text
    ]
    if missing:
        raise StageAReplayExecutorError(
            "owner approval text does not name " + ", ".join(missing)
        )


def _descriptor_candidate_ids(descriptor: Mapping[str, object]) -> tuple[str, ...]:
    value = descriptor.get("candidate_ids")
    if not isinstance(value, list) or not value:
        raise StageAReplayExecutorError(
            "replay descriptor candidate_ids must be a non-empty array"
        )
    ids: list[str] = []
    for item in value:  # pyright: ignore[reportUnknownVariableType]
        if not isinstance(item, str) or not item.strip():
            raise StageAReplayExecutorError(
                "replay descriptor candidate_id must be non-empty text"
            )
        ids.append(item)
    return tuple(ids)


def _git_signing_key() -> Path:
    try:
        configured = subprocess.run(
            ["git", "config", "--path", "--get", "user.signingkey"],
            cwd=repository_root(),
            env=trusted_git_environment(),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise StageAReplayExecutorError(
            "Git SSH signing key configuration is unavailable"
        ) from exc
    key = Path(configured)
    if not key.is_absolute():
        key = repository_root() / key
    if not key.is_file():
        raise StageAReplayExecutorError(f"Git SSH signing key is missing: {key}")
    return key
