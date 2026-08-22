# pyright: reportPrivateUsage=false

"""CLI adapter for the owner-directed corpus-manifest forecast path.

Two commands make one operator flow: ``freeze-corpus-manifest`` hashes the
corpus as it stands and prints the digest the owner signs, and
``build-manifest-forecast`` turns that signed manifest into the packets and
prompts the existing ``eval run-case`` executor consumes.

Like the Stage A replay adapter beside it, this module reaches the
implementation through entry points rather than imports, so the CLI package's
import graph never grows a dependency on the evals or ingestion stacks.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, cast

from legalforecast.publication.manifest_forecast_stage import (
    add_manifest_forecast_stage_arguments,
    run_manifest_forecast_stage,
)


class _FreezeCommand(Protocol):
    def __call__(
        self,
        *,
        selection: Path,
        prediction_units: Path,
        document_store_roots: Sequence[Path],
        verdict_sources: Sequence[Path],
        cycle_id: str,
        output: Path,
        generated_at: datetime,
    ) -> tuple[dict[str, object], bool]: ...


class _BuildCommand(Protocol):
    def __call__(
        self,
        *,
        manifest: Path,
        expected_manifest_digest: str,
        owner_signature_bead: str,
        owner_approval_line: str,
        model_registry: Path,
        output_dir: Path,
        generated_at: datetime,
    ) -> dict[str, object]: ...


class _FreezeInputsBuild(Protocol):
    run_card: dict[str, object]


class _FreezeInputsCommand(Protocol):
    def __call__(self, **kwargs: Any) -> _FreezeInputsBuild:
        raise NotImplementedError


_FREEZE = importlib.metadata.EntryPoint(
    name="owner-signed-corpus-manifest-freeze",
    value="legalforecast.evals.corpus_manifest.commands:freeze_corpus_manifest_command",
    group="legalforecast.internal",
)
_BUILD = importlib.metadata.EntryPoint(
    name="owner-signed-corpus-manifest-build",
    value=(
        "legalforecast.evals.corpus_manifest.commands:build_manifest_forecast_command"
    ),
    group="legalforecast.internal",
)
_ISSUE_FREEZE_INPUTS = importlib.metadata.EntryPoint(
    name="manifest-freeze-inputs-issue",
    value=(
        "legalforecast.evals.corpus_manifest.freeze_inputs:"
        "issue_manifest_freeze_inputs_command"
    ),
    group="legalforecast.internal",
)
_VERIFY_FREEZE_INPUTS = importlib.metadata.EntryPoint(
    name="manifest-freeze-inputs-verify",
    value=(
        "legalforecast.evals.corpus_manifest.freeze_inputs:"
        "verify_manifest_freeze_inputs_command"
    ),
    group="legalforecast.internal",
)
_HISTORICAL_EXCLUSION_AUTHENTICATOR = importlib.metadata.EntryPoint(
    name="manifest-freeze-historical-exclusion-authenticator",
    value="legalforecast.cli:_verify_replacement_exclusion_card",
    group="legalforecast.internal",
)
_V2_VERIFIER = importlib.metadata.EntryPoint(
    name="manifest-freeze-v2-verifier",
    value="legalforecast.cli:verify_exact100_successor_replacement_v2_projection",
    group="legalforecast.internal",
)
_V2_REPLAY_ARGS = importlib.metadata.EntryPoint(
    name="manifest-freeze-v2-replay-args",
    value="legalforecast.cli:_exact100_successor_v2_replay_args",
    group="legalforecast.internal",
)
_V2_REPLAY = importlib.metadata.EntryPoint(
    name="manifest-freeze-v2-replay",
    value="legalforecast.cli:_replay_exact100_successor_replacement_v2_inputs",
    group="legalforecast.internal",
)
_ISSUE_BUNDLE = importlib.metadata.EntryPoint(
    name="manifest-forecast-bundle-issue",
    value=("legalforecast.evals.corpus_manifest.deferred_bundle:issue_bundle"),
    group="legalforecast.internal",
)
_VERIFY_BUNDLE = importlib.metadata.EntryPoint(
    name="manifest-forecast-bundle-verify",
    value=("legalforecast.evals.corpus_manifest.deferred_bundle:verify_bundle"),
    group="legalforecast.internal",
)
_ISSUE_EXECUTION_DECISIONS = importlib.metadata.EntryPoint(
    name="manifest-execution-decisions-issue",
    value=(
        "legalforecast.evals.corpus_manifest.execution_decisions:"
        "issue_execution_decisions"
    ),
    group="legalforecast.internal",
)
_VERIFY_EXECUTION_DECISIONS = importlib.metadata.EntryPoint(
    name="manifest-execution-decisions-verify",
    value=(
        "legalforecast.evals.corpus_manifest.execution_decisions:"
        "verify_execution_decisions"
    ),
    group="legalforecast.internal",
)
_ISSUE_BEADS_OBSERVATION = importlib.metadata.EntryPoint(
    name="manifest-execution-decisions-beads-observation-issue",
    value=(
        "legalforecast.evals.corpus_manifest.execution_decisions:"
        "issue_beads_observation"
    ),
    group="legalforecast.internal",
)


def register(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the freeze and manifest-mode forecast commands."""

    freeze = subparsers.add_parser(
        "freeze-corpus-manifest",
        help="Freeze the corpus into one owner-signable manifest and digest.",
        description=(
            "Read the corpus selection, the prediction units, the parsed "
            "document stores, and the existing byte-role validation verdicts, "
            "and emit one flat manifest naming every case, every document, and "
            "the exact bytes behind each one. Every hash is computed fresh from "
            "the bytes on disk. The freeze fails closed and reports every "
            "blocker it found in a single run rather than one at a time. It "
            "opens no provider, buys nothing, and grants no authority; the "
            "printed manifest digest is the value the owner signs."
        ),
    )
    freeze.add_argument(
        "--selection",
        type=Path,
        required=True,
        help="Corpus selection JSONL naming the cases and their documents.",
    )
    freeze.add_argument(
        "--prediction-units",
        type=Path,
        required=True,
        help="Prediction units JSONL; bound into the manifest by digest.",
    )
    freeze.add_argument(
        "--document-store-root",
        type=Path,
        action="append",
        required=True,
        dest="document_store_roots",
        help=(
            "Parsed document store to draw bytes from. Repeatable; later roots "
            "supersede earlier ones, so pass repair tranches after the lineage "
            "parse tree."
        ),
    )
    freeze.add_argument(
        "--verdict-source",
        type=Path,
        action="append",
        required=True,
        dest="verdict_sources",
        help=(
            "Existing byte-role validation artifact to read verdicts from. "
            "Repeatable. Verdicts are read, never recomputed."
        ),
    )
    freeze.add_argument(
        "--cycle-id",
        required=True,
        help="Cycle identifier recorded in the manifest.",
    )
    freeze.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path receiving the self-hashed manifest.",
    )
    freeze.set_defaults(handler=run_freeze)

    build = subparsers.add_parser(
        "build-manifest-forecast",
        help="Build forecast packets and prompts from a signed corpus manifest.",
        description=(
            "Take the owner-signed manifest, the digest the owner signed, and "
            "the bead line recording that signature, and build every forecast "
            "packet and prompt through the existing packet builder. Markdown is "
            "re-hashed against the manifest as it is read and any drift is "
            "refused. Outcome-bearing documents cannot enter a packet. Models "
            "are resolved from the evaluation registry and recorded, but no "
            "provider call is made here: this command produces the inputs the "
            "existing eval run-case executor consumes."
        ),
    )
    build.add_argument(
        "--manifest",
        type=Path,
        required=True,
        help="The owner-signed corpus manifest.",
    )
    build.add_argument(
        "--expected-manifest-digest",
        required=True,
        help="The manifest digest the owner signed; must match the bytes.",
    )
    build.add_argument(
        "--owner-signature-bead",
        required=True,
        help="Bead identifier where the owner's signature is recorded.",
    )
    build.add_argument(
        "--owner-approval-line",
        required=True,
        help=(
            "The owner's approval line, verbatim. It must quote the manifest "
            "digest, so the signature is bound to these exact bytes."
        ),
    )
    build.add_argument(
        "--model-registry",
        type=Path,
        required=True,
        help="Evaluation model registry for this cycle.",
    )
    build.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory receiving the packet store, run inputs, and run record.",
    )
    build.set_defaults(handler=run_build)

    issue_inputs = subparsers.add_parser(
        "issue-manifest-freeze-inputs",
        help="Issue authenticated generic inputs for a manifest freeze bundle.",
        description=(
            "Replay the signed 100-case manifest forecast, all 200 prompt "
            "commitments, the reviewed release bytes, and the complete "
            "screened/excluded partition. Create-only emit the three runtime "
            "contracts, Cycle 1 no-baselines sentinel, 57-row exclusion "
            "ledger, and completed run card. This command calls no provider."
        ),
    )
    issue_inputs.add_argument("--cycle-id", required=True)
    issue_inputs.add_argument("--release-sha", required=True)
    issue_inputs.add_argument("--repository-root", type=Path, required=True)
    issue_inputs.add_argument("--owner-manifest", type=Path, required=True)
    issue_inputs.add_argument("--model-registry", type=Path, required=True)
    issue_inputs.add_argument("--forecast-output-dir", type=Path, required=True)
    issue_inputs.add_argument("--screened-pool", type=Path, required=True)
    issue_inputs.add_argument("--historical-exclusion-ledger", type=Path, required=True)
    issue_inputs.add_argument(
        "--historical-exclusion-run-card", type=Path, required=True
    )
    issue_inputs.add_argument("--v2-root", type=Path, required=True)
    issue_inputs.add_argument(
        "--v3-root",
        type=Path,
        action="append",
        required=True,
        dest="v3_roots",
        help="Authenticated successor v3 root; repeat exactly three times.",
    )
    issue_inputs.add_argument("--output-root", type=Path, required=True)
    issue_inputs.set_defaults(handler=run_issue_freeze_inputs)

    verify_inputs = subparsers.add_parser(
        "verify-manifest-freeze-inputs",
        help="Replay and verify issued manifest freeze inputs.",
    )
    verify_inputs.add_argument("--output-root", type=Path, required=True)
    verify_inputs.set_defaults(handler=run_verify_freeze_inputs)

    issue_bundle = subparsers.add_parser(
        "issue-manifest-forecast-bundle-v2",
        help="Issue a create-only labels-deferred manifest forecast bundle.",
        description=(
            "Bind the authenticated generic freeze inputs, owner-signed manifest "
            "forecast packets, successor registry, provider caps, execution "
            "policy, and the schedule derived from that verified policy. This "
            "command is provider-free; any later provider receipts remain "
            "private, non-scoreable, and non-publishable."
        ),
    )
    issue_bundle.add_argument("--cycle-id", required=True)
    issue_bundle.add_argument("--freeze-inputs-root", type=Path, required=True)
    issue_bundle.add_argument("--owner-manifest", type=Path, required=True)
    issue_bundle.add_argument("--forecast-output-dir", type=Path, required=True)
    issue_bundle.add_argument("--model-registry", type=Path, required=True)
    issue_bundle.add_argument("--provider-cycle-caps", type=Path, required=True)
    issue_bundle.add_argument("--execution-policy", type=Path, required=True)
    issue_bundle.add_argument("--output-root", type=Path, required=True)
    issue_bundle.set_defaults(handler=run_issue_bundle)

    verify_bundle = subparsers.add_parser(
        "verify-manifest-forecast-bundle-v2",
        help="Replay and verify a labels-deferred manifest forecast bundle.",
    )
    verify_bundle.add_argument("--output-root", type=Path, required=True)
    verify_bundle.set_defaults(handler=run_verify_bundle)

    issue_decisions = subparsers.add_parser(
        "issue-manifest-execution-decisions-v2",
        help="Issue provider-free authenticated execution decisions and policy.",
        description=(
            "Derive the Cycle 1 execution decisions from the signed manifest, "
            "no-docket forecast, official model registry, provider caps, "
            "labeling/cohort artifacts, observation chain, and a fresh Beads "
            "observation and canonical labeling journal. Create-only emit "
            "execution-decisions-v2.json, execution-policy-v2.json, the "
            "authenticated Beads wrapper, and a v2 run card. No lifecycle "
            "timestamp is accepted from the operator."
        ),
    )
    issue_decisions.add_argument("--owner-manifest", type=Path, required=True)
    issue_decisions.add_argument("--forecast-output-dir", type=Path, required=True)
    issue_decisions.add_argument("--model-registry", type=Path, required=True)
    issue_decisions.add_argument("--provider-cycle-caps", type=Path, required=True)
    issue_decisions.add_argument(
        "--labeling-provider-cycle-caps", type=Path, required=True
    )
    issue_decisions.add_argument("--provider-journal", type=Path, required=True)
    issue_decisions.add_argument("--labeling-policy", type=Path, required=True)
    issue_decisions.add_argument("--cohort-policy", type=Path, required=True)
    issue_decisions.add_argument(
        "--cohort-observation-manifest", type=Path, required=True
    )
    issue_decisions.add_argument("--freeze-inputs-root", type=Path, required=True)
    issue_decisions.add_argument("--output-root", type=Path, required=True)
    issue_decisions.set_defaults(handler=run_issue_execution_decisions)

    verify_decisions = subparsers.add_parser(
        "verify-manifest-execution-decisions-v2",
        help="Replay and verify issued execution decisions and policy.",
    )
    verify_decisions.add_argument("--output-root", type=Path, required=True)
    verify_decisions.set_defaults(handler=run_verify_execution_decisions)

    issue_beads = subparsers.add_parser(
        "issue-manifest-execution-decisions-beads-observation-v2",
        help="Capture live Beads comments and issue a hash-pinned wrapper.",
    )
    issue_beads.add_argument("--model-registry", type=Path, required=True)
    issue_beads.add_argument("--output", type=Path, required=True)
    issue_beads.set_defaults(handler=run_issue_beads_observation)

    stage = subparsers.add_parser(
        "stage-manifest-forecast",
        help="Stage manifest-mode forecast inputs into immutable S3 prefixes.",
        description=(
            "Authenticate the manifest forecast output and the complete frozen "
            "artifact bundle, then write them under the immutable "
            "cycle-1/manifest-runs/<manifest-digest>/ prefix. No provider call "
            "is made. Existing S3 objects are accepted only when their bytes "
            "match the same commitments."
        ),
    )
    add_manifest_forecast_stage_arguments(stage)
    stage.set_defaults(handler=run_manifest_forecast_stage)


def run_freeze(args: argparse.Namespace) -> int:
    """Freeze the corpus, printing the digest or every blocker found."""

    freeze = cast(_FreezeCommand, _FREEZE.load())
    record, accepted = freeze(
        selection=cast(Path, args.selection),
        prediction_units=cast(Path, args.prediction_units),
        document_store_roots=cast("Sequence[Path]", args.document_store_roots),
        verdict_sources=cast("Sequence[Path]", args.verdict_sources),
        cycle_id=cast(str, args.cycle_id),
        output=cast(Path, args.output),
        generated_at=datetime.now(UTC),
    )
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0 if accepted else 2


def run_build(args: argparse.Namespace) -> int:
    """Build the manifest-mode forecast inputs without calling any provider."""

    build = cast(_BuildCommand, _BUILD.load())
    print(
        json.dumps(
            build(
                manifest=cast(Path, args.manifest),
                expected_manifest_digest=cast(str, args.expected_manifest_digest),
                owner_signature_bead=cast(str, args.owner_signature_bead),
                owner_approval_line=cast(str, args.owner_approval_line),
                model_registry=cast(Path, args.model_registry),
                output_dir=cast(Path, args.output_dir),
                generated_at=datetime.now(UTC),
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_issue_freeze_inputs(args: argparse.Namespace) -> int:
    """Issue the six generic freeze inputs without provider activity."""

    issue = cast(_FreezeInputsCommand, _ISSUE_FREEZE_INPUTS.load())
    build = issue(
        cycle_id=cast(str, args.cycle_id),
        release_sha=cast(str, args.release_sha),
        repository_root=cast(Path, args.repository_root),
        owner_manifest=cast(Path, args.owner_manifest),
        model_registry=cast(Path, args.model_registry),
        forecast_output_dir=cast(Path, args.forecast_output_dir),
        screened_pool=cast(Path, args.screened_pool),
        historical_exclusion_ledger=cast(Path, args.historical_exclusion_ledger),
        historical_exclusion_run_card=cast(Path, args.historical_exclusion_run_card),
        v2_root=cast(Path, args.v2_root),
        v3_roots=tuple(cast("Sequence[Path]", args.v3_roots)),
        output_root=cast(Path, args.output_root),
        legacy_historical_authenticator=_HISTORICAL_EXCLUSION_AUTHENTICATOR.load(),
        legacy_v2_verifier=_V2_VERIFIER.load(),
        legacy_v2_replay_args=_V2_REPLAY_ARGS.load(),
        legacy_v2_replay=_V2_REPLAY.load(),
    )
    print(json.dumps(build.run_card, indent=2, sort_keys=True))
    return 0


def run_verify_freeze_inputs(args: argparse.Namespace) -> int:
    """Replay one completed generic freeze-input issuance."""

    verify = cast(_FreezeInputsCommand, _VERIFY_FREEZE_INPUTS.load())
    build = verify(
        output_root=cast(Path, args.output_root),
        legacy_historical_authenticator=_HISTORICAL_EXCLUSION_AUTHENTICATOR.load(),
        legacy_v2_verifier=_V2_VERIFIER.load(),
        legacy_v2_replay_args=_V2_REPLAY_ARGS.load(),
        legacy_v2_replay=_V2_REPLAY.load(),
    )
    print(json.dumps(build.run_card, indent=2, sort_keys=True))
    return 0


def _verify_freeze_inputs_complete(output_root: Path) -> _FreezeInputsBuild:
    """Replay the complete generic-freeze issuer with its authentic verifiers."""

    verify = cast(_FreezeInputsCommand, _VERIFY_FREEZE_INPUTS.load())
    return verify(
        output_root=output_root,
        legacy_historical_authenticator=_HISTORICAL_EXCLUSION_AUTHENTICATOR.load(),
        legacy_v2_verifier=_V2_VERIFIER.load(),
        legacy_v2_replay_args=_V2_REPLAY_ARGS.load(),
        legacy_v2_replay=_V2_REPLAY.load(),
    )


def run_issue_bundle(args: argparse.Namespace) -> int:
    """Issue the additive labels-deferred forecast bundle without providers."""

    issue = _ISSUE_BUNDLE.load()
    result = issue(
        cycle_id=args.cycle_id,
        freeze_inputs_root=args.freeze_inputs_root,
        owner_manifest=args.owner_manifest,
        forecast_output_dir=args.forecast_output_dir,
        model_registry=args.model_registry,
        provider_cycle_caps=args.provider_cycle_caps,
        execution_policy=args.execution_policy,
        output_root=cast(Path, args.output_root),
        verify_freeze_inputs=_verify_freeze_inputs_complete,
    )
    print(json.dumps(dict(result.bundle), indent=2, sort_keys=True))
    return 0


def run_verify_bundle(args: argparse.Namespace) -> int:
    """Verify the bundle and all of its committed source bytes."""

    verify = _VERIFY_BUNDLE.load()
    print(
        json.dumps(
            dict(
                verify(
                    args.output_root,
                    verify_freeze_inputs=_verify_freeze_inputs_complete,
                )
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_issue_execution_decisions(args: argparse.Namespace) -> int:
    """Issue execution decisions and the derived policy without providers."""

    issue = _ISSUE_EXECUTION_DECISIONS.load()
    result = issue(
        owner_manifest=cast(Path, args.owner_manifest),
        forecast_output_dir=cast(Path, args.forecast_output_dir),
        model_registry=cast(Path, args.model_registry),
        provider_cycle_caps=cast(Path, args.provider_cycle_caps),
        labeling_provider_cycle_caps=cast(Path, args.labeling_provider_cycle_caps),
        provider_journal=cast(Path, args.provider_journal),
        labeling_policy=cast(Path, args.labeling_policy),
        cohort_policy=cast(Path, args.cohort_policy),
        cohort_observation_manifest=cast(Path, args.cohort_observation_manifest),
        freeze_inputs_root=cast(Path, args.freeze_inputs_root),
        output_root=cast(Path, args.output_root),
        verify_freeze_inputs=_verify_freeze_inputs_complete,
    )
    print(json.dumps(dict(result.run_card), indent=2, sort_keys=True))
    return 0


def run_verify_execution_decisions(args: argparse.Namespace) -> int:
    """Replay one completed execution-decision issuance."""

    verify = _VERIFY_EXECUTION_DECISIONS.load()
    result = verify(
        cast(Path, args.output_root),
        verify_freeze_inputs=_verify_freeze_inputs_complete,
    )
    print(json.dumps(dict(result.run_card), indent=2, sort_keys=True))
    return 0


def run_issue_beads_observation(args: argparse.Namespace) -> int:
    """Capture live Beads comments and issue their hash-pinned wrapper."""

    issue = _ISSUE_BEADS_OBSERVATION.load()
    result = issue(
        model_registry=cast(Path, args.model_registry),
        output=cast(Path, args.output),
    )
    print(json.dumps(dict(result), indent=2, sort_keys=True))
    return 0
