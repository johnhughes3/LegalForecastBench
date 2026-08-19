# pyright: reportPrivateUsage=false

"""Cycle-neutral adapter for the canonical Stage A replay executor.

Three commands make one operator flow: ``issue-replay-spec`` derives the closed
replay descriptor and the paste-ready approval block naming its hash, the owner
signs against that hash, and ``record-replay-authorization`` binds the paste to
the descriptor and emits the spec ``replay-stage-a`` executes.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, cast


class _ReplayResult(Protocol):
    halted: bool

    def to_record(self) -> dict[str, object]: ...


class _IssuanceCommand(Protocol):
    def __call__(
        self, *, issuance_request: Path, output_dir: Path, preflight: bool
    ) -> tuple[dict[str, object], bool]: ...


class _RecordingCommand(Protocol):
    def __call__(
        self,
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
    ) -> dict[str, object]: ...


# Entry points rather than imports: this adapter must not draw the verifier
# stack into the CLI package's import graph.
_EXECUTOR = importlib.metadata.EntryPoint(
    name="candidate-scoped-stage-a-executor",
    value=(
        "legalforecast.ingestion.stage_a_replay_executor.executor:"
        "execute_canonical_stage_a_replay"
    ),
    group="legalforecast.internal",
)
_ISSUER = importlib.metadata.EntryPoint(
    name="candidate-scoped-stage-a-issuer",
    value=(
        "legalforecast.ingestion.stage_a_replay_executor.issuance:"
        "issue_replay_spec_command"
    ),
    group="legalforecast.internal",
)
_RECORDER = importlib.metadata.EntryPoint(
    name="candidate-scoped-stage-a-recorder",
    value=(
        "legalforecast.ingestion.stage_a_replay_executor.recording:"
        "record_replay_authorization_command"
    ),
    group="legalforecast.internal",
)


def register(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the sole production Stage A replay command."""

    replay = subparsers.add_parser(
        "replay-stage-a",
        help="Execute one authenticated candidate-scoped Stage A replay spec.",
        description=(
            "Execute the signed, hashed candidate-scoped Stage A replay spec "
            "through the frozen claim-ontology-v5 unitizer and v4 reviewer. "
            "All candidates, artifacts, models, ceilings, journal identity, "
            "and output paths come from --replay-spec; no ad-hoc execution "
            "flags are accepted."
        ),
    )
    replay.add_argument(
        "--replay-spec",
        type=Path,
        required=True,
        help=(
            "Self-hashed replay-spec artifact containing signed authorization, "
            "candidate set, frozen v5/v4 configuration, ceilings, lineage, "
            "canonical journal identity, and output paths."
        ),
    )
    replay.set_defaults(handler=run)


def register_issuance(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the supported producers of an executable replay spec."""

    issue = subparsers.add_parser(
        "issue-replay-spec",
        help="Derive the replay descriptor the owner signs against.",
        description=(
            "Derive the closed candidate-scoped Stage A replay descriptor from "
            "the authenticated predecessor run cards plus an issuance request, "
            "and emit its SHA-256 with a paste-ready approval block naming that "
            "hash. Every fact the executor cross-checks against predecessor "
            "artifacts is derived, not re-entered. Issuance opens no provider "
            "and grants no authority; the owner's signature does that. A "
            "refused preflight withholds the approval block entirely and "
            "deletes any block already in the output directory, so no "
            "signable instrument is ever left next to a refusal; the refusal "
            "is recorded in issuance-evidence.json, not only on stdout."
        ),
    )
    issue.add_argument(
        "--issuance-request",
        type=Path,
        required=True,
        help=(
            "Operator issuance request naming the cycle, predecessor run cards, "
            "successor lineage, repair evidence, candidate set, ceilings, "
            "provider accounts, and outputs root."
        ),
    )
    issue.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory receiving the descriptor, approval block, and evidence.",
    )
    issue.add_argument(
        "--skip-preflight",
        action="store_true",
        help=(
            "Skip the provider-free rehearsal of lineage, repair receipt, "
            "planning, and provider binding. Use only when the referenced "
            "artifacts are deliberately absent. Skipping is recorded as "
            "'skipped' and still emits the approval block; it is a deliberate "
            "operator bypass, not a refusal."
        ),
    )
    issue.set_defaults(handler=run_issue)

    record = subparsers.add_parser(
        "record-replay-authorization",
        help="Bind the owner's typed approval to one replay descriptor.",
        description=(
            "Record the owner's verbatim approval text against a replay "
            "descriptor hash: build the canonical authorization artifact, "
            "attach the detached SSH signature the executor verifies against "
            "Git's allowed-signers file, assemble the self-hashed replay spec, "
            "and prove the result by loading it through the executor's own "
            "validator. The approval text is required input; it is never "
            "authored here."
        ),
    )
    record.add_argument(
        "--replay-descriptor",
        type=Path,
        required=True,
        help="Descriptor emitted by issue-replay-spec.",
    )
    record.add_argument(
        "--approval-text-file",
        type=Path,
        required=True,
        help="File holding the owner's pasted approval text, verbatim.",
    )
    record.add_argument(
        "--request-artifact",
        type=Path,
        required=True,
        help="Provider-free spend-request artifact the approval answers.",
    )
    record.add_argument(
        "--expires-at",
        required=True,
        help="Timezone-aware ISO-8601 instant at which the approval lapses.",
    )
    record.add_argument(
        "--estimated-cost-usd",
        required=True,
        help="Estimated cost named in the approval text; the hard ceiling is "
        "derived from the descriptor.",
    )
    record.add_argument(
        "--signer-principal",
        required=True,
        help="Allowed-signers principal that must verify the signature.",
    )
    record.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory receiving the authorization, signature, and replay spec.",
    )
    record.add_argument(
        "--signature",
        type=Path,
        help=(
            "Pre-existing detached SSHSIG over the authorization artifact. "
            "Omit to sign with the Git-configured SSH signing key."
        ),
    )
    record.add_argument(
        "--signing-key",
        type=Path,
        help="SSH key used to produce the detached signature.",
    )
    record.set_defaults(handler=run_record)


def run(args: argparse.Namespace) -> int:
    """Load the heavy verifier stack only after command selection."""

    execute = cast(Callable[[Path], _ReplayResult], _EXECUTOR.load())
    result = execute(cast(Path, args.replay_spec))
    print(json.dumps(result.to_record(), sort_keys=True))
    return 2 if result.halted else 0


def run_issue(args: argparse.Namespace) -> int:
    """Derive one replay descriptor and report its owner-facing hash."""

    issue = cast(_IssuanceCommand, _ISSUER.load())
    record, accepted = issue(
        issuance_request=cast(Path, args.issuance_request),
        output_dir=cast(Path, args.output_dir),
        preflight=not cast(bool, args.skip_preflight),
    )
    print(json.dumps(record, sort_keys=True))
    return 0 if accepted else 2


def run_record(args: argparse.Namespace) -> int:
    """Bind the owner's paste to a descriptor and emit the executable spec."""

    record_authorization = cast(_RecordingCommand, _RECORDER.load())
    print(
        json.dumps(
            record_authorization(
                replay_descriptor=cast(Path, args.replay_descriptor),
                approval_text_file=cast(Path, args.approval_text_file),
                request_artifact=cast(Path, args.request_artifact),
                expires_at=cast(str, args.expires_at),
                estimated_cost_usd=cast(str, args.estimated_cost_usd),
                signer_principal=cast(str, args.signer_principal),
                output_dir=cast(Path, args.output_dir),
                signature=cast("Path | None", args.signature),
                signing_key=cast("Path | None", args.signing_key),
            ),
            sort_keys=True,
        )
    )
    return 0
