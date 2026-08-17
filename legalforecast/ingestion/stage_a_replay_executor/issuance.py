"""Canonical issuer for the candidate-scoped Stage A replay spec.

The executor accepts exactly one artifact: a self-hashed replay spec whose
operative fields are covered by a detached owner signature.  This module is the
only supported producer of that artifact's *unsigned* half — the replay
descriptor — and it derives every fact the executor later cross-checks from the
authenticated predecessor run cards rather than re-entering it by hand.  What
the operator supplies is limited to facts no artifact can carry: the authorized
candidate set, the spend ceilings, the successor and repair artifact locations,
and where the outputs go.

Issuance is not execution authority.  Nothing here opens a provider, and the
executor re-authenticates the finished spec from scratch.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import cast

from legalforecast.ingestion.stage_a_replay_executor.contract import (
    StageAReplayExecutorError,
)
from legalforecast.ingestion.stage_a_replay_executor.contract import (
    canonical as _canonical,
)
from legalforecast.ingestion.stage_a_replay_executor.contract import (
    parse_decimal as _parse_decimal,
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
from legalforecast.ingestion.stage_a_replay_executor.executor import (
    current_code_commit,
)
from legalforecast.ingestion.stage_a_replay_executor.issuance_request import (
    decimal_field as _decimal,
)
from legalforecast.ingestion.stage_a_replay_executor.issuance_request import (
    digest_field as _digest,
)
from legalforecast.ingestion.stage_a_replay_executor.issuance_request import (
    load_issuance_request,
)
from legalforecast.ingestion.stage_a_replay_executor.issuance_request import (
    mapping_field as _mapping,
)
from legalforecast.ingestion.stage_a_replay_executor.issuance_request import (
    path_field as _path,
)
from legalforecast.ingestion.stage_a_replay_executor.issuance_request import (
    request_candidate_ids as _candidate_ids,
)
from legalforecast.ingestion.stage_a_replay_executor.issuance_request import (
    text_field as _text,
)
from legalforecast.ingestion.stage_a_replay_executor.run_card_derivation import (
    configuration_block,
    predecessor_block,
    provider_block,
    read_run_card,
    repair_block,
    successor_block,
)
from legalforecast.ingestion.stage_a_replay_executor.spec import (
    REPLAY_SPEC_SCHEMA_VERSION,
)

#: Fixed output filenames under the operator-supplied outputs root.  Output
#: naming is part of the signed descriptor, so it must be derived rather than
#: chosen per invocation.
OUTPUT_FILENAMES: Mapping[str, str] = {
    "plan_path": "replay-plan.json",
    "execution_path": "replay-execution.json",
    "stage_a_receipt_path": "stage-a-receipt.json",
    "invocation_journal_path": "invocation-journal.json",
    "executor_receipt_path": "executor-receipt.json",
    "terminal_evidence_root": "terminal-evidence",
}

_MAXIMUM_PROVIDER_ATTEMPTS = 3


__all__ = (
    "OUTPUT_FILENAMES",
    "ReplaySpecDraft",
    "issue_replay_descriptor",
    "issue_replay_spec_command",
    "load_issuance_request",
    "paste_ready_approval_text",
    "write_replay_descriptor_draft",
)


@dataclass(frozen=True, slots=True)
class ReplaySpecDraft:
    """One issued replay descriptor plus the owner-facing approval material."""

    descriptor: Mapping[str, object]
    descriptor_sha256: str
    candidate_ids: tuple[str, ...]
    estimated_cost_usd: Decimal
    hard_ceiling_usd: Decimal
    approval_text: str
    derivation: Mapping[str, object]


def issue_replay_descriptor(
    request: Mapping[str, object], *, code_commit: str | None = None
) -> ReplaySpecDraft:
    """Derive the closed replay descriptor from authenticated predecessor cards.

    ``code_commit`` defaults to the clean runtime checkout, which is what the
    executor compares against at run time.  Callers pass it only in tests.
    """

    candidate_ids = _candidate_ids(request)
    predecessor_request = _mapping(request, "predecessor")
    unitize_card_path = _path(predecessor_request, "unitization_run_card_path")
    review_card_path = _path(predecessor_request, "structural_review_run_card_path")
    unitize_card = read_run_card(unitize_card_path, "predecessor unitizer run card")
    review_card = read_run_card(review_card_path, "predecessor reviewer run card")

    provider = provider_block(request, unitize_card, review_card)
    configuration = configuration_block(unitize_card, review_card, provider)
    lineage = {
        "mode": "verified_artifacts",
        "cycle_id": _text(request, "cycle_id"),
        "index_path": str(_path(request, "lineage_index_path")),
        "active_root_identity_sha256": _digest(request, "active_root_identity_sha256"),
        "predecessor": predecessor_block(
            predecessor_request,
            unitize_card_path=unitize_card_path,
            review_card_path=review_card_path,
            unitize_card=unitize_card,
            review_card=review_card,
        ),
        "successor": successor_block(_mapping(request, "successor")),
        "repair_receipt": repair_block(_mapping(request, "repair_receipt")),
    }
    spend, estimated = _spend_block(
        _mapping(request, "spend"), candidate_ids, configuration
    )
    descriptor: dict[str, object] = {
        "schema_version": REPLAY_SPEC_SCHEMA_VERSION,
        "candidate_ids": list(candidate_ids),
        "lineage": lineage,
        "configuration": configuration,
        "spend": spend,
        "provider": provider,
        "outputs": _outputs_block(_path(request, "outputs_root")),
        "code_commit": code_commit or current_code_commit(),
    }
    # Round-trip through the executor's own descriptor projection so the hash the
    # owner signs is produced by the verifier's code, never by a local copy.
    descriptor_sha256 = _sha256_bytes(_canonical(_replay_descriptor(descriptor)))
    hard_ceiling = _parse_decimal(spend["aggregate_ceiling_usd"], "hard_ceiling_usd")
    return ReplaySpecDraft(
        descriptor=descriptor,
        descriptor_sha256=descriptor_sha256,
        candidate_ids=candidate_ids,
        estimated_cost_usd=estimated,
        hard_ceiling_usd=hard_ceiling,
        approval_text=paste_ready_approval_text(
            candidate_ids=candidate_ids,
            estimated_cost_usd=estimated,
            hard_ceiling_usd=hard_ceiling,
            descriptor_sha256=descriptor_sha256,
        ),
        derivation={
            "unitization_run_card_path": str(unitize_card_path),
            "unitization_run_card_sha256": _sha256_bytes(
                _read_regular(unitize_card_path, "predecessor unitizer run card")
            ),
            "structural_review_run_card_path": str(review_card_path),
            "structural_review_run_card_sha256": _sha256_bytes(
                _read_regular(review_card_path, "predecessor reviewer run card")
            ),
            "invocation_reservation_floor_usd": {
                stage: format(
                    _parse_decimal(
                        cast(
                            Mapping[str, object],
                            spend["invocation_reservations_usd"],
                        )[stage],
                        stage,
                    ),
                    "f",
                )
                for stage in ("unitizer", "reviewer")
            },
        },
    )


def issue_replay_spec_command(
    *, issuance_request: Path, output_dir: Path, preflight: bool
) -> tuple[dict[str, object], bool]:
    """Run the ``issue-replay-spec`` command and report its operator record.

    The second element is whether the descriptor is executable as issued, so the
    CLI can exit non-zero on a refused rehearsal without the caller restating
    the rule.
    """

    draft = issue_replay_descriptor(load_issuance_request(issuance_request))
    descriptor_path = write_replay_descriptor_draft(draft, output_dir)
    record: dict[str, object] = {
        "replay_descriptor_path": str(descriptor_path),
        "replay_descriptor_sha256": draft.descriptor_sha256,
        "candidate_ids": list(draft.candidate_ids),
        "estimated_cost_usd": format(draft.estimated_cost_usd, "f"),
        "hard_ceiling_usd": format(draft.hard_ceiling_usd, "f"),
        "approval_text": draft.approval_text,
    }
    if not preflight:
        record["preflight"] = {"status": "skipped"}
        return record, True

    from legalforecast.ingestion.stage_a_replay_executor.preflight import (
        preflight_replay_descriptor,
    )

    rehearsal = preflight_replay_descriptor(draft.descriptor)
    record["preflight"] = {
        "status": "accepted" if rehearsal.accepted else "refused",
        "stage": rehearsal.stage,
        "reason": rehearsal.reason,
        "evidence": dict(rehearsal.evidence),
    }
    return record, rehearsal.accepted


def paste_ready_approval_text(
    *,
    candidate_ids: Sequence[str],
    estimated_cost_usd: Decimal,
    hard_ceiling_usd: Decimal,
    descriptor_sha256: str,
) -> str:
    """Return approval text carrying every token the executor demands.

    The executor requires each candidate id and both ``USD x.xx`` amounts to
    appear verbatim.  Naming the descriptor hash is what makes the approval
    specific to one replay rather than to a spend number.
    """

    listed = ", ".join(candidate_ids)
    return (
        f"I approve candidate-scoped Stage A replay bound to replay descriptor "
        f"SHA-256 {descriptor_sha256}: estimated cost USD "
        f"{estimated_cost_usd:.2f}, hard ceiling USD {hard_ceiling_usd:.2f}, for "
        f"candidates {listed}. Spend must be journaled per candidate. A candidate "
        "that exhausts the frozen reconstruction-attempt limit routes to the "
        "terminal qsp attorney-adjudication path; no fourth call is permitted. "
        "Execution must halt on any preflight, receipt, clearance, lineage, or "
        "frozen-contract failure. No PACER activity is authorized."
    )


def write_replay_descriptor_draft(draft: ReplaySpecDraft, output_dir: Path) -> Path:
    """Persist the descriptor and its owner-facing approval block."""

    output_dir.mkdir(parents=True, exist_ok=True)
    descriptor_path = output_dir / "replay-descriptor.json"
    descriptor_path.write_bytes(_canonical(draft.descriptor))
    (output_dir / "approval-block.txt").write_text(
        draft.approval_text + "\n", encoding="utf-8"
    )
    (output_dir / "issuance-evidence.json").write_bytes(
        _canonical(
            {
                "replay_descriptor_sha256": draft.descriptor_sha256,
                "candidate_ids": list(draft.candidate_ids),
                "estimated_cost_usd": format(draft.estimated_cost_usd, "f"),
                "hard_ceiling_usd": format(draft.hard_ceiling_usd, "f"),
                "derivation": dict(draft.derivation),
            }
        )
    )
    return descriptor_path


def _spend_block(
    request: Mapping[str, object],
    candidate_ids: Sequence[str],
    configuration: Mapping[str, object],
) -> tuple[dict[str, object], Decimal]:
    estimated = _decimal(request, "estimated_cost_usd")
    hard_ceiling = _decimal(request, "hard_ceiling_usd")
    if estimated > hard_ceiling:
        raise StageAReplayExecutorError("issuance estimate exceeds its hard ceiling")
    per_candidate = _decimal(request, "per_candidate_ceiling_usd")
    if per_candidate > hard_ceiling:
        raise StageAReplayExecutorError(
            "per-candidate ceiling exceeds the aggregate hard ceiling"
        )
    reservations_raw = _mapping(request, "invocation_reservations_usd")
    if set(reservations_raw) != {"unitizer", "reviewer"}:
        raise StageAReplayExecutorError(
            "invocation reservations must name unitizer and reviewer"
        )
    reservations = {
        stage: _decimal(reservations_raw, stage) for stage in ("unitizer", "reviewer")
    }
    _require_feasible_reservations(
        reservations,
        per_candidate_ceiling=per_candidate,
        configuration=configuration,
    )
    return (
        {
            "aggregate_ceiling_usd": format(hard_ceiling, "f"),
            "per_candidate_ceiling_usd": {
                candidate_id: format(per_candidate, "f")
                for candidate_id in candidate_ids
            },
            "invocation_reservations_usd": {
                stage: format(value, "f") for stage, value in reservations.items()
            },
        },
        estimated,
    )


def _require_feasible_reservations(
    reservations: Mapping[str, Decimal],
    *,
    per_candidate_ceiling: Decimal,
    configuration: Mapping[str, object],
) -> None:
    """Refuse ceilings the executor's reservation guard could never satisfy.

    ``guard.guarded_callback`` reserves ``reservation * maximum_new_attempts``
    before every provider call, and a candidate with no journal history carries
    the full three-attempt allowance.  A ceiling below that product does not
    reduce spend — it produces a deterministic ``halted_at_ceiling`` with no
    provider access, which is worse than declining to issue.

    Only the per-candidate ceiling is checked because the caller has already
    bounded it by the aggregate; a reservation that fits under it fits under the
    aggregate too.
    """

    for stage, reservation in reservations.items():
        model_id = _text(_mapping(configuration, stage), "model_id")
        required = reservation * _MAXIMUM_PROVIDER_ATTEMPTS
        if required > per_candidate_ceiling:
            raise StageAReplayExecutorError(
                f"{stage} reservation USD {reservation:f} for {model_id} needs USD "
                f"{required:f} of per-candidate authority across "
                f"{_MAXIMUM_PROVIDER_ATTEMPTS} attempts, above the per-candidate "
                f"ceiling USD {per_candidate_ceiling:f}"
            )


def _outputs_block(outputs_root: Path) -> dict[str, object]:
    return {field: str(outputs_root / name) for field, name in OUTPUT_FILENAMES.items()}
