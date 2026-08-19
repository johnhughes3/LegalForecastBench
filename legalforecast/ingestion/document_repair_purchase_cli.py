"""Operator commands that issue document-repair purchase authority.

Three commands, in the one order that works:

1. ``record-document-repair-purchase-approval`` -- replay the tranche, show the
   reviewer facts this recorder derived, and record the typed confirmation at a
   real TTY. Writes private evidence only.
2. ``verify-document-repair-purchase-approval`` -- replay that evidence and
   publish the approved ``legalforecast.case_dev_purchase_policy.v2`` artifact.
3. ``verify-document-repair-purchase-policy`` -- prove the published policy
   binds the execution. Repeatable, consumes nothing, mints nothing.

There is deliberately **no** command that initializes the purchase ledger.
Authority can be minted only while the canonical ledger is absent, and the
runtime verifier requires it present, so initialization belongs to the paid
execution process and is exposed only as
:func:`~legalforecast.ingestion.document_repair_purchase_approval.initialize_document_repair_purchase_runtime`.
Initializing the ledger from a separate step leaves the tranche permanently
unable to mint authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from legalforecast.ingestion.document_repair_purchase_approval import (
    DocumentRepairPurchaseApprovalError,
    DocumentRepairPurchaseInputs,
    DocumentRepairPurchaseProjection,
    build_document_repair_purchase_approval_request,
    generate_approved_document_repair_purchase_policy,
    read_approved_document_repair_purchase_policy,
    verify_document_repair_purchase_approval,
    verify_document_repair_purchase_policy_binds,
)
from legalforecast.ingestion.purchase_approval import (
    record_purchase_approval,
    resume_purchase_approval_recording,
)

_CHECKPOINT_NAME = "purchase-approval-checkpoint.json"
_RUN_CARD_NAME = "run-cards/record-purchase-approval.json"

_PREAMBLE = (
    "Every figure above was derived from bytes this recorder read and digested "
    "itself.\nA confirmation phrase circulated in chat is NOT authoritative. "
    "Type the phrase\nprinted below, exactly as printed, from this terminal."
)


def add_parsers(subparsers: Any) -> None:
    """Register the repair-tranche purchase issuance commands."""

    record = subparsers.add_parser(
        "record-document-repair-purchase-approval",
        help=(
            "Interactively record approve, reject, or free-only for one exact "
            "document-repair purchase tranche without provider activity."
        ),
        description=(
            "TTY-only provider-free recorder for a replay-minted document-repair "
            "execution. The recorder mints the execution from authenticated bytes "
            "and displays the authoritative typed-confirmation string; the "
            "displayed string is the only signing material. The controlled "
            "private root receives the sole checkpoint and run card. No public "
            "approval artifact, provider request, purchase, ledger, freeze, or "
            "dispatch occurs."
        ),
    )
    _add_source_arguments(record)
    record.add_argument(
        "--controlled-private-root",
        type=Path,
        required=True,
        help=(
            "Absolute controlled private root receiving the checkpoint and run "
            "card. Never placed in packet or freeze artifacts."
        ),
    )
    record.add_argument(
        "--execute",
        action="store_true",
        help="Prompt and record. Omitted prints the projection and stops.",
    )
    record.add_argument(
        "--resume",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=(
            "Rebuild only a missing run card from an existing durable checkpoint "
            "instead of prompting again."
        ),
    )
    record.set_defaults(handler=run_record)

    verify = subparsers.add_parser(
        "verify-document-repair-purchase-approval",
        help=(
            "Replay private document-repair approval evidence and publish the "
            "approved v2 purchase policy."
        ),
        description=(
            "Replays the checkpoint, run card, repair tranche, cohort policy, fee "
            "schedule, and fresh-ledger boundary, then writes the approved v2 "
            "purchase policy artifact. The canonical ledger must remain absent "
            "until the paid execution process initializes it."
        ),
    )
    _add_source_arguments(verify)
    verify.add_argument("--controlled-private-root", type=Path, required=True)
    verify.add_argument("--checkpoint", type=Path, required=True)
    verify.add_argument("--approval-run-card", type=Path, required=True)
    verify.add_argument(
        "--purchase-policy-output",
        type=Path,
        required=True,
        help="Destination for the approved v2 purchase policy artifact.",
    )
    verify.set_defaults(handler=run_verify)

    binds = subparsers.add_parser(
        "verify-document-repair-purchase-policy",
        help=(
            "Prove an issued v2 purchase policy binds one document-repair "
            "execution, consuming nothing."
        ),
        description=(
            "Runs the executor's own purchase-policy compatibility check against a "
            "freshly replayed execution. Safe to repeat: it neither creates the "
            "canonical ledger nor mints purchase authority, so it is the preflight "
            "to run before booking the execution sitting."
        ),
    )
    _add_source_arguments(binds)
    binds.add_argument("--purchase-policy", type=Path, required=True)
    binds.set_defaults(handler=run_verify_policy)


def _add_source_arguments(parser: argparse.ArgumentParser) -> None:
    add_repair_source_arguments(
        parser,
        canonical_ledger_help=(
            "Canonical purchase ledger this authority will bind. It must not yet "
            "exist; the paid execution process initializes it."
        ),
    )


def add_repair_source_arguments(
    parser: argparse.ArgumentParser, *, canonical_ledger_help: str
) -> None:
    """Register the tranche inputs every repair purchase command reads.

    Shared with the resume command so the two cannot drift on which paths make
    up a tranche, what each one means, or how the externally supplied lineage
    pin is justified. Only the canonical-ledger help differs, because issuance
    requires that ledger absent and a resume requires it present.
    """

    parser.add_argument(
        "--repair-execution-root",
        type=Path,
        required=True,
        help=(
            "Absolute tranche root. Every other repair input must live inside it, "
            "so the recorded root is a complete pointer to what was signed."
        ),
    )
    parser.add_argument(
        "--repair-manifest",
        type=Path,
        required=True,
        help="Observational repair manifest (JSONL) the plan approval covers.",
    )
    parser.add_argument(
        "--repair-plan-approval",
        type=Path,
        required=True,
        help="Approved legalforecast.repair_manifest_approval.v2 record.",
    )
    parser.add_argument(
        "--docket-snapshot-manifest",
        type=Path,
        required=True,
        help="Docket snapshot manifest committing each candidate's SHA-256.",
    )
    parser.add_argument(
        "--source-lineage",
        type=Path,
        required=True,
        help="Source lineage pinning the snapshot manifest and cohort policy.",
    )
    parser.add_argument(
        "--source-lineage-sha256",
        required=True,
        help=(
            "External pin for the source lineage, supplied here rather than read "
            "from the tranche: a pin read from what it pins proves nothing."
        ),
    )
    parser.add_argument(
        "--docket-snapshot-dir",
        type=Path,
        required=True,
        help="Directory holding one <candidate_id>.json authenticated snapshot.",
    )
    parser.add_argument("--cohort-policy", type=Path, required=True)
    parser.add_argument("--fee-schedule", type=Path, required=True)
    parser.add_argument(
        "--canonical-ledger-path",
        type=Path,
        required=True,
        help=canonical_ledger_help,
    )


def _projection(args: argparse.Namespace) -> DocumentRepairPurchaseProjection:
    return build_document_repair_purchase_approval_request(
        inputs=DocumentRepairPurchaseInputs(
            repair_execution_root=cast(Path, args.repair_execution_root),
            repair_manifest_path=cast(Path, args.repair_manifest),
            repair_plan_approval_path=cast(Path, args.repair_plan_approval),
            docket_snapshot_manifest_path=cast(Path, args.docket_snapshot_manifest),
            source_lineage_path=cast(Path, args.source_lineage),
            source_lineage_sha256=cast(str, args.source_lineage_sha256),
            docket_snapshot_dir=cast(Path, args.docket_snapshot_dir),
        ),
        cohort_policy_path=cast(Path, args.cohort_policy),
        fee_schedule_path=cast(Path, args.fee_schedule),
        canonical_ledger_path=cast(Path, args.canonical_ledger_path),
    )


def run_record(args: argparse.Namespace) -> int:
    """Record one document-repair purchase decision at a real TTY."""

    private_root = cast(Path, args.controlled_private_root)
    projection = _projection(args)
    request = projection.request
    print(json.dumps({"approval_request": request.to_record()}, sort_keys=True))
    print()
    print("=== document-repair purchase approval ===")
    for line in projection.display_lines():
        print(f"  {line}")
    print()
    if not cast(bool, args.execute):
        print("Dry run: nothing recorded. Re-run with --execute to confirm.")
        return 0
    checkpoint_path = private_root / _CHECKPOINT_NAME
    if cast(bool, args.resume) and (
        checkpoint_path.exists() or checkpoint_path.is_symlink()
    ):
        # Repair only a missing run card from the durable checkpoint. Re-running
        # the prompt could not resume: a second recording stamps a new
        # ``recorded_at_utc``, so its checkpoint bytes would differ from the
        # durable ones and the immutable write would refuse them.
        resumed_checkpoint, resumed_run_card = resume_purchase_approval_recording(
            request=request,
            controlled_private_root=private_root,
        )
        print(
            json.dumps(
                {
                    "resumed": True,
                    "repair_execution_sha256": projection.execution.execution_sha256,
                    "checkpoint_sha256": _file_sha256(resumed_checkpoint),
                    "run_card_sha256": _file_sha256(resumed_run_card),
                    "provider_activity_requested": False,
                    "provider_activity_executed": False,
                    "paid_activity_requested": False,
                    "paid_activity_executed": False,
                },
                sort_keys=True,
            )
        )
        return 0
    if not sys.stdin.isatty():
        raise DocumentRepairPurchaseApprovalError(
            "record-document-repair-purchase-approval requires an interactive TTY"
        )
    print(_PREAMBLE)
    print()
    decision = input("Decision [approve/reject/free_only]: ").strip()
    required = request.required_confirmation(decision)
    print(f"Type exactly: {required}")
    confirmation = input("Exact confirmation: ")
    recorded_checkpoint, recorded_run_card = record_purchase_approval(
        request=request,
        controlled_private_root=private_root,
        decision=decision,
        typed_confirmation=confirmation,
        reviewer_id="John Hughes",
        recorded_at_utc=_utc_now(),
        resume=cast(bool, args.resume),
    )
    print(
        json.dumps(
            {
                "decision": decision,
                "repair_execution_sha256": projection.execution.execution_sha256,
                "checkpoint_sha256": _file_sha256(recorded_checkpoint),
                "run_card_sha256": _file_sha256(recorded_run_card),
                "provider_activity_requested": False,
                "provider_activity_executed": False,
                "paid_activity_requested": False,
                "paid_activity_executed": False,
            },
            sort_keys=True,
        )
    )
    print(
        "Next: verify-document-repair-purchase-approval to publish the v2 policy. "
        "Leave the canonical ledger absent until the paid execution runs."
    )
    return 0


def run_verify(args: argparse.Namespace) -> int:
    """Publish the approved v2 purchase policy from private repair evidence."""

    approval = verify_document_repair_purchase_approval(
        controlled_private_root=cast(Path, args.controlled_private_root),
        checkpoint_path=cast(Path, args.checkpoint),
        run_card_path=cast(Path, args.approval_run_card),
        inputs=DocumentRepairPurchaseInputs(
            repair_execution_root=cast(Path, args.repair_execution_root),
            repair_manifest_path=cast(Path, args.repair_manifest),
            repair_plan_approval_path=cast(Path, args.repair_plan_approval),
            docket_snapshot_manifest_path=cast(Path, args.docket_snapshot_manifest),
            source_lineage_path=cast(Path, args.source_lineage),
            source_lineage_sha256=cast(str, args.source_lineage_sha256),
            docket_snapshot_dir=cast(Path, args.docket_snapshot_dir),
        ),
        cohort_policy_path=cast(Path, args.cohort_policy),
        fee_schedule_path=cast(Path, args.fee_schedule),
        canonical_ledger_path=cast(Path, args.canonical_ledger_path),
    )
    artifact = generate_approved_document_repair_purchase_policy(approval)
    payload = (json.dumps(artifact, indent=2, sort_keys=True) + "\n").encode()
    output = cast(Path, args.purchase_policy_output)
    _publish(output, payload)
    print(
        json.dumps(
            {
                "purchase_policy_path": str(output),
                "purchase_policy_sha256": artifact.get("policy_sha256"),
                "purchase_policy_file_sha256": hashlib.sha256(payload).hexdigest(),
                "repair_execution_sha256": approval.execution_sha256,
                "request_sha256": approval.request.request_sha256,
                "paid_activity_requested": False,
                "paid_activity_executed": False,
            },
            sort_keys=True,
        )
    )
    print(
        "Next: verify-document-repair-purchase-policy to prove the binding. The "
        "canonical ledger must stay absent until the paid execution initializes it."
    )
    return 0


def run_verify_policy(args: argparse.Namespace) -> int:
    """Prove an issued policy binds a freshly replayed repair execution."""

    projection = _projection(args)
    artifact, _typed = read_approved_document_repair_purchase_policy(
        cast(Path, args.purchase_policy)
    )
    policy = verify_document_repair_purchase_policy_binds(
        execution=projection.execution,
        purchase_policy_artifact=artifact,
    )
    print(
        json.dumps(
            {
                "binds": True,
                "purchase_policy_sha256": policy.policy_sha256,
                "repair_execution_sha256": projection.execution.execution_sha256,
                "purchase_document_count": projection.request.purchase_document_count,
                "projected_cost_usd": projection.request.projected_cost_usd,
                "canonical_ledger_path": str(policy.canonical_ledger_path),
                "canonical_ledger_present": policy.canonical_ledger_path.exists(),
                "paid_activity_requested": False,
                "paid_activity_executed": False,
            },
            sort_keys=True,
        )
    )
    return 0


def _publish(path: Path, payload: bytes) -> None:
    """Create the policy artifact exclusively, accepting an identical rerun."""

    if not path.is_absolute():
        raise DocumentRepairPurchaseApprovalError(
            "--purchase-policy-output must be an absolute path"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags | nofollow, 0o600)
    except FileExistsError as exc:
        if path.read_bytes() == payload:
            return
        raise DocumentRepairPurchaseApprovalError(
            f"a different purchase policy already exists at {path}"
        ) from exc
    try:
        view = memoryview(payload)
        while view:
            view = view[os.write(descriptor, view) :]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


# contract-ratchet: allow raw digest reports bytes already written to disk.
def _file_sha256(path: Path) -> str:
    """Report the raw digest of an artifact this command just published.

    Non-persisted: the value is printed for the operator and never becomes part
    of an authenticated artifact. ``RAW_BYTES_RAW_SHA256_V1`` is the blessed
    profile for raw bytes, but committing requires a schema domain, and these
    digests identify a file rather than an instance of a schema.
    """

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_evidence_paths(private_root: Path) -> tuple[Path, Path]:
    """Return the only checkpoint and run-card locations this path accepts."""

    return private_root / _CHECKPOINT_NAME, private_root / _RUN_CARD_NAME
