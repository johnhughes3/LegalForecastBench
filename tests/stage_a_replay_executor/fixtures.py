"""Synthetic artifacts and spend evidence for Stage A executor tests."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import cast

from legalforecast.contracts import ARTIFACT_CANONICAL_JSON_V1
from legalforecast.ingestion.candidate_scoped_stage_a_replay import (
    CandidateScopedStageARerunRequest,
    StageAStageOutcome,
)
from legalforecast.ingestion.stage_a_replay_executor.contract import (
    AUTHORIZATION_SCHEMA_VERSION,
    AUTHORIZATION_SIGNATURE_NAMESPACE,
)
from legalforecast.ingestion.stage_a_replay_executor.executor import (
    REPLAY_SPEC_SCHEMA_VERSION,
    load_replay_spec,
)
from legalforecast.ingestion.stage_a_replay_executor.journal import (
    StageSpend,
    StageSpendSnapshot,
)

CAPS_SHA256 = "a" * 64
PREDECESSOR_SHA256 = "b" * 64
SUCCESSOR_SHA256 = "c" * 64
REGISTRY_SHA256 = "d" * 64


class FakeSpendMeter:
    """Deterministic per-stage spend and attempt evidence."""

    def __init__(
        self,
        *,
        actual_usd: str = "0.10",
        actual_by_call: Mapping[tuple[str, str], str] | None = None,
        attempts_by_call: Mapping[tuple[str, str], int] | None = None,
        preexisting_attempts_by_call: Mapping[tuple[str, str], int] | None = None,
        preexisting_committed_by_call: Mapping[tuple[str, str], str] | None = None,
        maximum_new_attempts_by_call: Mapping[tuple[str, str], int] | None = None,
        after_error: Exception | None = None,
    ) -> None:
        self.actual_usd = actual_usd
        self.actual_by_call = dict(actual_by_call or {})
        self.attempts_by_call = dict(attempts_by_call or {})
        self.preexisting_attempts_by_call = dict(preexisting_attempts_by_call or {})
        self.preexisting_committed_by_call = dict(preexisting_committed_by_call or {})
        self.maximum_new_attempts_by_call = dict(maximum_new_attempts_by_call or {})
        self.after_error = after_error
        self.attempts: dict[tuple[str, str], int] = {}

    def before(
        self,
        request: CandidateScopedStageARerunRequest,
        *,
        stage: str,
        unitize: StageAStageOutcome | None,
    ) -> StageSpendSnapshot:
        del unitize
        key = (request.candidate_id, stage)
        prior_attempts = self.preexisting_attempts_by_call.get(key, 0)
        attempt_count = prior_attempts + self.attempts.get(key, 0)
        actual = Decimal(self.actual_by_call.get(key, self.actual_usd))
        committed = Decimal(
            self.preexisting_committed_by_call.get(
                key, format(actual * prior_attempts, "f")
            )
        ) + actual * self.attempts.get(key, 0)
        return StageSpendSnapshot(
            logical_call_key=f"fixture:{request.candidate_id}:{stage}",
            provider_stage=f"fixture:{stage}",
            candidate_id=request.candidate_id,
            stage=stage,
            model_key=f"fixture:{stage}",
            provider="fixture",
            account="fixture",
            prompt=f"prompt:{request.candidate_id}:{stage}",
            prompt_sha256="f" * 64,
            committed_usd=committed,
            attempt_count=attempt_count,
            maximum_new_attempts=self.maximum_new_attempts_by_call.get(key, 1),
        )

    def after(self, before: StageSpendSnapshot) -> StageSpend:
        if self.after_error is not None:
            raise self.after_error
        key = (before.candidate_id, before.stage)
        new_attempts = self.attempts_by_call.get(key, 1)
        attempt_count = before.attempt_count + new_attempts
        self.attempts[key] = self.attempts.get(key, 0) + new_attempts
        actual = Decimal(self.actual_by_call.get(key, self.actual_usd))
        return StageSpend(
            actual_usd=actual,
            attempt_count=attempt_count,
            new_attempt_count=new_attempts,
            logical_call_key=before.logical_call_key,
            provider_stage=before.provider_stage,
            prompt_sha256=before.prompt_sha256,
            attempts=tuple(
                {
                    "attempt_ordinal": ordinal,
                    "status": "settled",
                }
                for ordinal in range(1, attempt_count + 1)
            ),
        )


def settled_unitizer(
    request: CandidateScopedStageARerunRequest,
) -> StageAStageOutcome:
    return StageAStageOutcome(
        candidate_id=request.candidate_id,
        records=(
            {
                "candidate_id": request.candidate_id,
                "case_id": request.packet.case_id,
                "prediction_units": [f"unit-{request.candidate_id}"],
            },
        ),
        audit={
            "candidate_id": request.candidate_id,
            "case_id": request.packet.case_id,
            "status": "settled",
            "actual_cost_usd": "0.10",
        },
        status="settled",
        request_sha256=request.request_sha256,
    )


def settled_reviewer(
    request: CandidateScopedStageARerunRequest,
    _unitize: StageAStageOutcome,
) -> StageAStageOutcome:
    return StageAStageOutcome(
        candidate_id=request.candidate_id,
        records=(),
        audit={
            "candidate_id": request.candidate_id,
            "case_id": request.packet.case_id,
            "status": "settled",
            "actual_cost_usd": "0.10",
        },
        status="settled",
        request_sha256=request.request_sha256,
    )


def terminal_outcome(
    request: CandidateScopedStageARerunRequest,
    *,
    attempt_count: int,
) -> StageAStageOutcome:
    return StageAStageOutcome(
        candidate_id=request.candidate_id,
        records=(),
        audit={
            "candidate_id": request.candidate_id,
            "case_id": request.packet.case_id,
            "status": "terminal_escalation",
            "attempt_count": attempt_count,
            "actual_cost_usd": "0.10",
            "terminal_escalation_sha256": "9" * 64,
        },
        status="terminal_escalation",
        request_sha256=request.request_sha256,
    )


def write_spec(
    root: Path,
    *,
    aggregate_ceiling: str = "0.30",
    per_candidate_ceiling: str | None = None,
    candidate_ids: tuple[str, ...] = ("cand-a", "cand-b", "cand-c"),
    changed_candidate_ids: tuple[str, ...] | None = None,
    code_commit: str = "0" * 40,
    expires_at: datetime | None = None,
    production: bool = False,
) -> Path:
    """Write a closed synthetic or descriptor-only production replay spec."""

    journal = root / "provider.sqlite3"
    registry = root / "registry.json"
    caps = root / "caps.json"
    request = root / "request.md"
    registry.write_bytes(b"{}")
    caps.write_bytes(b"{}")
    request.write_bytes(b"Synthetic request for fake-provider testing.\n")
    changed = set(
        candidate_ids if changed_candidate_ids is None else changed_candidate_ids
    )
    approval_text = (
        "Synthetic approval for fake-provider test only."
        if not production
        else (
            "I approve candidates "
            + ", ".join(candidate_ids)
            + f" at estimated cost USD {Decimal(aggregate_ceiling):.2f} "
            + f"and hard ceiling USD {Decimal(aggregate_ceiling):.2f}."
        )
    )
    record: dict[str, object] = {
        "schema_version": REPLAY_SPEC_SCHEMA_VERSION,
        "authorization": {},
        "candidate_ids": list(candidate_ids),
        "lineage": (
            _production_lineage(root)
            if production
            else _fixture_lineage(candidate_ids, changed)
        ),
        "configuration": {
            "unitizer": configuration("unitizer", "claim-ontology-v5"),
            "reviewer": configuration("reviewer", "claim-ontology-v4"),
        },
        "spend": {
            "aggregate_ceiling_usd": aggregate_ceiling,
            "per_candidate_ceiling_usd": {
                candidate_id: per_candidate_ceiling or aggregate_ceiling
                for candidate_id in candidate_ids
            },
            "invocation_reservations_usd": {
                "unitizer": "0.10",
                "reviewer": "0.10",
            },
        },
        "provider": {
            "model_registry_path": str(registry.resolve()),
            "model_registry_sha256": REGISTRY_SHA256,
            "provider_cycle_caps_path": str(caps.resolve()),
            "journal_path": str(journal.resolve()),
            "provider_caps_sha256": CAPS_SHA256,
            "provider_accounts": {"fixture": "fixture-account"},
        },
        "outputs": {
            "plan_path": str((root / "plan.json").resolve()),
            "execution_path": str((root / "execution.json").resolve()),
            "stage_a_receipt_path": str((root / "stage-a-receipt.json").resolve()),
            "invocation_journal_path": str((root / "invocations.json").resolve()),
            "executor_receipt_path": str((root / "receipt.json").resolve()),
            "terminal_evidence_root": str((root / "terminal-evidence").resolve()),
        },
        "code_commit": code_commit,
    }
    descriptor = replay_descriptor(record)
    authorization_artifact = {
        "schema_version": AUTHORIZATION_SCHEMA_VERSION,
        "request_artifact_path": str(request.resolve()),
        "request_artifact_sha256": hashlib.sha256(request.read_bytes()).hexdigest(),
        "approval_text": approval_text,
        "expires_at": (expires_at or datetime.now(UTC) + timedelta(days=1)).isoformat(),
        "candidate_ids": list(candidate_ids),
        "estimated_cost_usd": aggregate_ceiling,
        "hard_ceiling_usd": aggregate_ceiling,
        "replay_descriptor_sha256": record_sha256(descriptor),
    }
    approval_path = root / "authorization.json"
    approval_path.write_bytes(ARTIFACT_CANONICAL_JSON_V1.encode(authorization_artifact))
    signature_path = root / "authorization.json.sig"
    if production:
        signature_path.write_bytes(b"synthetic invalid SSHSIG fixture\n")
    record["authorization"] = {
        "mode": "git_allowed_signers_sshsig" if production else "synthetic_fixture",
        "artifact_path": str(approval_path.resolve()),
        "artifact_sha256": hashlib.sha256(approval_path.read_bytes()).hexdigest(),
        "signature_path": str(signature_path.resolve()) if production else None,
        "signature_sha256": (
            hashlib.sha256(signature_path.read_bytes()).hexdigest()
            if production
            else None
        ),
        "signature_namespace": AUTHORIZATION_SIGNATURE_NAMESPACE,
        "signer_principal": "owner@example.invalid" if production else "synthetic:true",
    }
    return write_spec_record(root / "replay.json", record, validate=not production)


def read_spec(path: Path) -> dict[str, object]:
    value: object = json.loads(path.read_text())
    assert isinstance(value, dict)
    return cast(dict[str, object], value)


def write_spec_record(
    path: Path, record: dict[str, object], *, validate: bool = True
) -> Path:
    record.pop("replay_spec_sha256", None)
    record["replay_spec_sha256"] = record_sha256(record)
    path.write_bytes(ARTIFACT_CANONICAL_JSON_V1.encode(record))
    if validate:
        assert load_replay_spec(path).spec_sha256 == record["replay_spec_sha256"]
    return path


def record_sha256(record: object) -> str:
    return hashlib.sha256(ARTIFACT_CANONICAL_JSON_V1.encode(record)).hexdigest()


def replay_descriptor(record: Mapping[str, object]) -> dict[str, object]:
    """Return the exact spec fields committed by the signed authorization."""

    return {
        name: record[name]
        for name in (
            "schema_version",
            "candidate_ids",
            "lineage",
            "configuration",
            "spend",
            "provider",
            "outputs",
            "code_commit",
        )
    }


def configuration(stage: str, namespace: str) -> dict[str, object]:
    content = {
        "namespace": namespace,
        "prompt_contract": namespace,
        "model_id": f"fixture:{stage}",
        "model_registry_sha256": REGISTRY_SHA256,
        "model_entry_sha256": ("e" if stage == "unitizer" else "f") * 64,
        "provider_caps_sha256": CAPS_SHA256,
    }
    return {**content, "config_sha256": record_sha256(content)}


def _fixture_lineage(
    candidate_ids: tuple[str, ...], changed: set[str]
) -> dict[str, object]:
    return {
        "mode": "synthetic_fixture",
        "cycle_id": "cycle-fixture",
        "synthetic": True,
        "predecessor": [predecessor(candidate_id) for candidate_id in candidate_ids],
        "successor": [
            packet(
                candidate_id,
                digest="2" * 64 if candidate_id in changed else "1" * 64,
            )
            for candidate_id in candidate_ids
        ],
        "predecessor_selection_sha256": PREDECESSOR_SHA256,
        "predecessor_materialization_sha256": PREDECESSOR_SHA256,
        "predecessor_parser_sha256": PREDECESSOR_SHA256,
        "successor_selection_sha256": SUCCESSOR_SHA256,
        "successor_materialization_sha256": SUCCESSOR_SHA256,
        "successor_parser_sha256": SUCCESSOR_SHA256,
    }


def _production_lineage(root: Path) -> dict[str, object]:
    def input_path(name: str) -> str:
        return str((root / "inputs" / name).resolve())

    predecessor_fields = {
        "raw_prediction_units_path": "raw.jsonl",
        "unitization_audit_path": "unit-audit.jsonl",
        "unitization_run_card_path": "unit-card.json",
        "original_review_path": "review.jsonl",
        "structural_flags_path": "flags.jsonl",
        "structural_review_audit_path": "review-audit.jsonl",
        "structural_review_run_card_path": "review-card.json",
        "structural_review_registry_path": "review-registry.json",
        "merged_review_path": "merged.jsonl",
        "finalized_prediction_units_path": "finalized.jsonl",
        "adjudications_path": "adjudications.jsonl",
        "apply_unitization_run_card_path": "apply-card.json",
    }
    successor_fields = {
        "selection_path": "selection.jsonl",
        "selection_run_card_path": "selection-card.json",
        "download_manifest_path": "download.jsonl",
        "disclosure_clearance_path": "clearance.jsonl",
        "materialization_run_card_path": "materialization-card.json",
        "document_root": "documents",
        "parse_requests_path": "parse-requests.jsonl",
        "parser_manifest_path": "parser.jsonl",
        "parser_run_card_path": "parser-card.json",
        "markdown_root": "markdown",
    }
    repair_fields = {
        "acquired_documents_path": "acquired-documents.json",
        "manifest_path": "repair-manifest.json",
        "approval_path": "repair-approval.json",
        "snapshot_manifest_path": "snapshot-manifest.json",
        "source_lineage_path": "source-lineage.json",
        "snapshots_root": "snapshots",
        "execution_path": "repair-execution.json",
        "receipt_path": "repair-receipt.json",
    }
    return {
        "mode": "verified_artifacts",
        "cycle_id": "cycle-fixture",
        "index_path": input_path("cycle-index.json"),
        "active_root_identity_sha256": "7" * 64,
        "predecessor": {
            **{field: input_path(name) for field, name in predecessor_fields.items()},
            "structural_review_model_key": "fixture:reviewer",
            "controlled_private_root": None,
            "initialization_receipt_path": None,
        },
        "successor": {
            **{field: input_path(name) for field, name in successor_fields.items()},
            "controlled_private_root": None,
            "initialization_receipt_path": None,
        },
        "repair_receipt": {
            **{field: input_path(name) for field, name in repair_fields.items()},
            "acquired_documents_sha256": "8" * 64,
            "source_lineage_sha256": "6" * 64,
            "execution_artifact_sha256": "5" * 64,
            "receipt_artifact_sha256": "4" * 64,
            "expected_receipt_sha256": "3" * 64,
        },
    }


def predecessor(candidate_id: str) -> dict[str, object]:
    value = packet(candidate_id, digest="1" * 64)
    value.update(
        {
            "unitize_record": {
                "candidate_id": candidate_id,
                "case_id": f"case-{candidate_id}",
                "prediction_units": [f"old-{candidate_id}"],
            },
            "unitize_audit": {"candidate_id": candidate_id, "status": "settled"},
            "review_flags": [],
            "review_audit": {"candidate_id": candidate_id, "status": "settled"},
            "unitizer_status": "settled",
            "reviewer_status": "settled",
        }
    )
    return value


def packet(candidate_id: str, *, digest: str) -> dict[str, object]:
    document_id = f"doc-{candidate_id}"
    return {
        "candidate_id": candidate_id,
        "case_id": f"case-{candidate_id}",
        "selection_record": {
            "candidate_id": candidate_id,
            "case_id": f"case-{candidate_id}",
        },
        "documents": [
            {
                "source_document_id": document_id,
                "document_role": "complaint",
                "sha256": digest,
                "byte_count": 10,
            }
        ],
        "parser_outputs": [
            {
                "source_document_id": document_id,
                "markdown_sha256": digest,
                "parser_reuse_identity_sha256": digest,
            }
        ],
    }
