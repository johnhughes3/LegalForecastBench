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
from typing import Protocol, cast

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
