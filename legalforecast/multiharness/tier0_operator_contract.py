"""Caller-facing Tier-0 operator contract: empty roots and Infisical signer."""

from __future__ import annotations

import os
from pathlib import Path

from legalforecast.multiharness.auth_profiles import AuthProfileError
from legalforecast.multiharness.local_cli_environment import (
    fetch_named_infisical_secret,
)
from legalforecast.multiharness.receipt_authority import (
    EVALUATOR_ISSUER_INFISICAL_ENVIRONMENT,
    EVALUATOR_ISSUER_INFISICAL_PATH,
    EVALUATOR_ISSUER_PRIVATE_KEY_NAME,
    ReceiptAuthorityError,
)

TIER0_SOURCE_ROOT_ENV = "LFB_TIER0_SOURCE_ROOT"
TIER0_PRIVATE_ROOT_ENV = "LFB_TIER0_PRIVATE_ROOT"
TIER0_ARCHIVE_ROOT_ENV = "LFB_TIER0_ARCHIVE_ROOT"


def _require_env_path(name: str) -> Path:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        raise ValueError(
            f"{name} must be supplied by the caller; the command does not invent roots"
        )
    return Path(raw)


def _paths_overlap(first: Path, second: Path) -> bool:
    a, b = first.resolve(strict=False), second.resolve(strict=False)
    return a == b or a.is_relative_to(b) or b.is_relative_to(a)


def caller_tier0_roots() -> tuple[Path, Path, Path]:
    """Honor the frozen caller-supplied empty-root contract."""

    source_root = _require_env_path(TIER0_SOURCE_ROOT_ENV)
    private_root = _require_env_path(TIER0_PRIVATE_ROOT_ENV)
    archive_root = _require_env_path(TIER0_ARCHIVE_ROOT_ENV)
    if source_root.is_symlink() or not source_root.is_dir():
        raise ValueError(f"{TIER0_SOURCE_ROOT_ENV} must be a real directory")
    if private_root.exists() or private_root.is_symlink():
        raise ValueError(f"{TIER0_PRIVATE_ROOT_ENV} must be a fresh empty path")
    if archive_root.exists() or archive_root.is_symlink():
        raise ValueError(f"{TIER0_ARCHIVE_ROOT_ENV} must be a fresh empty path")
    if private_root.parent.is_symlink() or not private_root.parent.is_dir():
        raise ValueError(f"{TIER0_PRIVATE_ROOT_ENV} parent must be a real directory")
    if archive_root.parent.is_symlink() or not archive_root.parent.is_dir():
        raise ValueError(f"{TIER0_ARCHIVE_ROOT_ENV} parent must be a real directory")
    if (
        _paths_overlap(source_root, private_root)
        or _paths_overlap(source_root, archive_root)
        or _paths_overlap(private_root, archive_root)
    ):
        raise ValueError("Tier-0 source, private, and archive roots must be disjoint")
    return source_root, private_root, archive_root


def infisical_evaluator_issuer_secret_loader(
    environment: str, path: str, name: str
) -> str:
    """Load the evaluator signer only through the sanctioned Infisical wrapper.

    The callback is attached at the CLI process boundary and is not invoked
    until a receipt is actually signed.  Pending public configuration refuses
    before this function can run.  Tests must never call this against a live
    Infisical path.
    """

    if environment != EVALUATOR_ISSUER_INFISICAL_ENVIRONMENT:
        raise ReceiptAuthorityError(
            "evaluator issuer private key must use Infisical dev"
        )
    if path != EVALUATOR_ISSUER_INFISICAL_PATH:
        raise ReceiptAuthorityError(
            "evaluator issuer private key path is outside the sanctioned namespace"
        )
    if name != EVALUATOR_ISSUER_PRIVATE_KEY_NAME:
        raise ReceiptAuthorityError("evaluator issuer private key name is not approved")
    try:
        return fetch_named_infisical_secret(
            environment=environment,
            path=path,
            name=name,
        )
    except AuthProfileError as exc:
        raise ReceiptAuthorityError(
            "evaluator issuer secret is unavailable from the Infisical wrapper"
        ) from exc
