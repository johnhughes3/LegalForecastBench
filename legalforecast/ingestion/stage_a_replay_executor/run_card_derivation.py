"""Derive replay-descriptor blocks from the authenticated predecessor run cards.

Every fact the executor later cross-checks against predecessor artifacts is read
out of those run cards here — frozen namespaces, model ids, model-entry digests,
registry and caps pins, the canonical journal — so a descriptor cannot disagree
with the lineage it claims.  The operator contributes only paths and identities
no artifact carries.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from legalforecast.ingestion.stage_a_replay_executor.contract import (
    StageAReplayExecutorError,
)
from legalforecast.ingestion.stage_a_replay_executor.contract import (
    read_regular as _read_regular,
)
from legalforecast.ingestion.stage_a_replay_executor.contract import (
    sha256_bytes as _sha256_bytes,
)
from legalforecast.ingestion.stage_a_replay_executor.issuance_request import (
    REQUEST_REPAIR_FIELDS as _REQUEST_REPAIR_FIELDS,
)
from legalforecast.ingestion.stage_a_replay_executor.issuance_request import (
    REQUEST_SUCCESSOR_FIELDS as _REQUEST_SUCCESSOR_FIELDS,
)
from legalforecast.ingestion.stage_a_replay_executor.issuance_request import (
    digest_field as _digest,
)
from legalforecast.ingestion.stage_a_replay_executor.issuance_request import (
    mapping_field as _mapping,
)
from legalforecast.ingestion.stage_a_replay_executor.issuance_request import (
    optional_path_text as _optional_path_text,
)
from legalforecast.ingestion.stage_a_replay_executor.issuance_request import (
    path_field as _path,
)
from legalforecast.ingestion.stage_a_replay_executor.issuance_request import (
    text_field as _text,
)
from legalforecast.ingestion.stage_a_replay_executor.spec import (
    REVIEWER_CONFIG_NAMESPACE,
    UNITIZER_CONFIG_NAMESPACE,
    configuration_digest,
)

__all__ = (
    "configuration_block",
    "predecessor_block",
    "provider_block",
    "read_run_card",
    "repair_block",
    "successor_block",
)


def predecessor_block(
    request: Mapping[str, object],
    *,
    unitize_card_path: Path,
    review_card_path: Path,
    unitize_card: Mapping[str, object],
    review_card: Mapping[str, object],
) -> dict[str, object]:
    return {
        "raw_prediction_units_path": _commitment_path(
            unitize_card, "output_commitments", "prediction_units"
        ),
        "unitization_audit_path": _commitment_path(
            unitize_card, "output_commitments", "llm_unitization_audit"
        ),
        "unitization_run_card_path": str(unitize_card_path),
        "original_review_path": _commitment_path(
            unitize_card, "output_commitments", "unitization_review_queue"
        ),
        "structural_flags_path": _commitment_path(
            review_card, "output_commitments", "structural_flags"
        ),
        "structural_review_audit_path": _commitment_path(
            review_card, "output_commitments", "audit"
        ),
        "structural_review_run_card_path": str(review_card_path),
        "structural_review_registry_path": _commitment_path(
            review_card, "source_commitments", "model_registry"
        ),
        "structural_review_model_key": _text(
            _mapping(review_card, "model_execution"), "model_key"
        ),
        "merged_review_path": _commitment_path(
            review_card, "output_commitments", "review_queue"
        ),
        "finalized_prediction_units_path": str(
            _path(request, "finalized_prediction_units_path")
        ),
        "adjudications_path": str(_path(request, "adjudications_path")),
        "apply_unitization_run_card_path": str(
            _path(request, "apply_unitization_run_card_path")
        ),
        "controlled_private_root": _optional_path_text(
            request, "controlled_private_root"
        ),
        "initialization_receipt_path": _optional_path_text(
            request, "initialization_receipt_path"
        ),
    }


def successor_block(request: Mapping[str, object]) -> dict[str, object]:
    block: dict[str, object] = {}
    for field in sorted(_REQUEST_SUCCESSOR_FIELDS):
        if field in {"controlled_private_root", "initialization_receipt_path"}:
            block[field] = _optional_path_text(request, field)
        else:
            block[field] = str(_path(request, field))
    return block


def repair_block(request: Mapping[str, object]) -> dict[str, object]:
    """Bind repair evidence paths to the exact bytes present at issuance."""

    paths = {
        field: _path(request, field)
        for field in sorted(_REQUEST_REPAIR_FIELDS)
        if field != "expected_receipt_sha256"
    }
    block: dict[str, object] = {field: str(value) for field, value in paths.items()}
    block["expected_receipt_sha256"] = _digest(request, "expected_receipt_sha256")
    for field, digest_field in (
        ("acquired_documents_path", "acquired_documents_sha256"),
        ("source_lineage_path", "source_lineage_sha256"),
        ("execution_path", "execution_artifact_sha256"),
        ("receipt_path", "receipt_artifact_sha256"),
    ):
        block[digest_field] = _sha256_bytes(
            _read_regular(paths[field], f"repair {field}")
        )
    return block


def provider_block(
    request: Mapping[str, object],
    unitize_card: Mapping[str, object],
    review_card: Mapping[str, object],
) -> dict[str, object]:
    accounts_raw = _mapping(request, "provider_accounts")
    accounts = {name: _text(accounts_raw, name) for name in sorted(accounts_raw)}
    if not accounts:
        raise StageAReplayExecutorError("issuance request names no provider accounts")
    return {
        "model_registry_path": _commitment_path(
            review_card, "source_commitments", "model_registry"
        ),
        "model_registry_sha256": _commitment_digest(
            review_card, "source_commitments", "model_registry"
        ),
        "provider_cycle_caps_path": _commitment_path(
            review_card, "source_commitments", "provider_cycle_caps"
        ),
        "provider_caps_sha256": _commitment_digest(
            review_card, "source_commitments", "provider_cycle_caps"
        ),
        "journal_path": _text(
            _mapping(unitize_card, "lineage_roots"), "provider_journal"
        ),
        "provider_accounts": accounts,
    }


def configuration_block(
    unitize_card: Mapping[str, object],
    review_card: Mapping[str, object],
    provider: Mapping[str, object],
) -> dict[str, object]:
    registry_sha256 = cast(str, provider["model_registry_sha256"])
    caps_sha256 = cast(str, provider["provider_caps_sha256"])
    configuration: dict[str, object] = {}
    for stage, card, namespace in (
        ("unitizer", unitize_card, UNITIZER_CONFIG_NAMESPACE),
        ("reviewer", review_card, REVIEWER_CONFIG_NAMESPACE),
    ):
        execution = _mapping(card, "model_execution")
        card_namespace = _text(execution, "provider_attempt_namespace")
        if card_namespace != namespace:
            raise StageAReplayExecutorError(
                f"predecessor {stage} run card namespace is {card_namespace!r}, "
                f"not frozen {namespace}"
            )
        card_registry = _digest(execution, "model_registry_sha256")
        if card_registry != registry_sha256:
            raise StageAReplayExecutorError(
                f"predecessor {stage} run card pins a different model registry"
            )
        content = {
            "namespace": namespace,
            "prompt_contract": namespace,
            "model_id": _text(execution, "model_key"),
            "model_registry_sha256": registry_sha256,
            "model_entry_sha256": _digest(execution, "model_entry_sha256"),
            "provider_caps_sha256": caps_sha256,
        }
        configuration[stage] = {
            **content,
            "config_sha256": configuration_digest(content),
        }
    return configuration


def read_run_card(path: Path, label: str) -> Mapping[str, object]:
    payload = _read_regular(path, label)
    try:
        loaded: object = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StageAReplayExecutorError(f"{label} is not valid JSON") from exc
    if not isinstance(loaded, dict):
        raise StageAReplayExecutorError(f"{label} must be a JSON object")
    return cast(dict[str, object], loaded)


def _commitment(
    card: Mapping[str, object], section: str, name: str
) -> Mapping[str, object]:
    commitments = _mapping(card, section)
    value = commitments.get(name)
    if not isinstance(value, Mapping):
        raise StageAReplayExecutorError(
            f"predecessor run card {section} lacks commitment {name}"
        )
    return cast(Mapping[str, object], value)


def _commitment_path(card: Mapping[str, object], section: str, name: str) -> str:
    return _text(_commitment(card, section, name), "path")


def _commitment_digest(card: Mapping[str, object], section: str, name: str) -> str:
    return _digest(_commitment(card, section, name), "sha256")
