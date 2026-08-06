"""Narrow CLI adapter for provider-free corpus completion summaries."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Any, cast

from legalforecast.ingestion.cohort_document_materializer import (
    CohortDocumentMaterializationError,
    prepare_non_symlink_directory,
)
from legalforecast.ingestion.corpus_completion_summary import (
    CorpusCompletionSummaryError,
    CorpusCompletionSummaryInputs,
    build_corpus_completion_summary,
    completion_summary_run_card,
    require_completion_inputs_unchanged,
    summary_json_bytes,
)
from legalforecast.ingestion.disclosure_review_bundle import (
    ReviewBundleError,
    read_unique_regular_file,
)


def add_acquisition_completion_summary_parser(subparsers: Any) -> None:
    """Register ``acquisition summarize-corpus`` on the shared parser."""

    parser = subparsers.add_parser(
        "summarize-corpus",
        help="Publish the closed, hash-bound Cycle corpus completion summary.",
        description=(
            "Provider-free verification and publication of terminal acquisition, "
            "adjudication, case-mix, exclusion, and canonical spend evidence. "
            "This command makes no provider, PACER, AWS, evaluation, freeze, or "
            "dispatch call."
        ),
    )
    parser.add_argument("--finalize-run-card", type=Path, required=True)
    parser.add_argument("--corpus-readiness", type=Path, required=True)
    parser.add_argument("--complete-exclusion-ledger", type=Path, required=True)
    parser.add_argument("--materialization-summary", type=Path, required=True)
    parser.add_argument("--materialization-run-card", type=Path, required=True)
    parser.add_argument("--purchase-policy", type=Path, required=True)
    parser.add_argument("--cohort-policy", type=Path, required=True)
    parser.add_argument("--purchase-ledger", type=Path, required=True)
    parser.add_argument(
        "--purchase-ledger-initialization-receipt",
        type=Path,
        required=True,
    )
    parser.add_argument("--model-registry", type=Path, required=True)
    parser.add_argument("--unitization-review-queue", type=Path, required=True)
    parser.add_argument("--unitization-adjudications", type=Path, required=True)
    parser.add_argument("--lawyer-review-queue", type=Path, required=True)
    parser.add_argument("--lawyer-review-audit", type=Path, required=True)
    parser.add_argument(
        "--adjudication-bead",
        action="append",
        default=[],
        help=(
            "Bead covering pending operator adjudications. Repeat when pending rows "
            "span multiple beads; omit only when both queues are fully resolved."
        ),
    )
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--execute",
        action="store_true",
        help=(
            "Publish the summary and run card. Without this flag, validate and "
            "print the deterministic summary without writing any output."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Also print the canonical summary JSON to standard output.",
    )
    parser.set_defaults(handler=_cmd_summarize_corpus)


def _cmd_summarize_corpus(args: argparse.Namespace) -> int:
    inputs = CorpusCompletionSummaryInputs(
        finalize_run_card=cast(Path, args.finalize_run_card),
        corpus_readiness=cast(Path, args.corpus_readiness),
        complete_exclusion_ledger=cast(Path, args.complete_exclusion_ledger),
        materialization_summary=cast(Path, args.materialization_summary),
        materialization_run_card=cast(Path, args.materialization_run_card),
        purchase_policy=cast(Path, args.purchase_policy),
        cohort_policy=cast(Path, args.cohort_policy),
        purchase_ledger=cast(Path, args.purchase_ledger),
        purchase_ledger_initialization_receipt=cast(
            Path, args.purchase_ledger_initialization_receipt
        ),
        model_registry=cast(Path, args.model_registry),
        unitization_review_queue=cast(Path, args.unitization_review_queue),
        unitization_adjudications=cast(Path, args.unitization_adjudications),
        lawyer_review_queue=cast(Path, args.lawyer_review_queue),
        lawyer_review_audit=cast(Path, args.lawyer_review_audit),
        adjudication_beads=tuple(cast(list[str], args.adjudication_bead)),
    )
    summary = build_corpus_completion_summary(inputs)
    summary_payload = summary_json_bytes(summary)
    if not cast(bool, args.execute):
        require_completion_inputs_unchanged(inputs, summary=summary)
        print(summary_payload.decode("utf-8"), end="")
        return 0
    output_root = cast(Path, args.output_root)
    try:
        prepared_root = prepare_non_symlink_directory(output_root)
    except CohortDocumentMaterializationError as exc:
        raise CorpusCompletionSummaryError(str(exc)) from exc
    summary_path = prepared_root / "corpus-completion-summary.json"
    run_card_path = prepared_root / "run-cards" / "summarize-corpus.json"
    run_card = completion_summary_run_card(
        inputs=inputs,
        summary_path=summary_path,
        summary_payload=summary_payload,
        input_commitments=cast(dict[str, object], summary["input_commitments"]),
        execute=True,
    )
    run_card_payload = _json_bytes(run_card)
    _reject_unexpected_outputs(
        prepared_root,
        summary_path=summary_path,
        run_card_path=run_card_path,
    )
    require_completion_inputs_unchanged(inputs, summary=summary)
    _publish_exact(summary_path, summary_payload)
    require_completion_inputs_unchanged(inputs, summary=summary)
    _publish_exact(run_card_path, run_card_payload)
    require_completion_inputs_unchanged(inputs, summary=summary)
    _reject_unexpected_outputs(
        prepared_root,
        summary_path=summary_path,
        run_card_path=run_card_path,
    )
    if cast(bool, args.json):
        print(summary_payload.decode("utf-8"), end="")
    else:
        print(summary_path)
    return 0


def _publish_exact(path: Path, payload: bytes) -> None:
    try:
        prepare_non_symlink_directory(path.parent)
        if path.exists() or path.is_symlink():
            if read_unique_regular_file(path) != payload:
                raise CorpusCompletionSummaryError(
                    f"summarize-corpus output already differs: {path}"
                )
            return
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary = Path(handle.name)
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary, path, follow_symlinks=False)
            except FileExistsError:
                if read_unique_regular_file(path) != payload:
                    raise CorpusCompletionSummaryError(
                        f"summarize-corpus output was concurrently replaced: {path}"
                    ) from None
            finally:
                temporary.unlink(missing_ok=True)
            directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    except (CohortDocumentMaterializationError, ReviewBundleError) as exc:
        raise CorpusCompletionSummaryError(str(exc)) from exc


def _reject_unexpected_outputs(
    output_root: Path,
    *,
    summary_path: Path,
    run_card_path: Path,
) -> None:
    expected_root = {summary_path.resolve(), run_card_path.parent.resolve()}
    actual_root = {path.resolve() for path in output_root.iterdir()}
    if actual_root - expected_root:
        raise CorpusCompletionSummaryError(
            "summarize-corpus output root contains unexpected entries"
        )
    if run_card_path.parent.exists():
        if run_card_path.parent.is_symlink() or not run_card_path.parent.is_dir():
            raise CorpusCompletionSummaryError(
                "summarize-corpus run-card root is unsafe"
            )
        unexpected_cards = {
            path.resolve() for path in run_card_path.parent.iterdir()
        } - {run_card_path.resolve()}
        if unexpected_cards:
            raise CorpusCompletionSummaryError(
                "summarize-corpus run-card root contains unexpected entries"
            )


def _json_bytes(value: object) -> bytes:
    try:
        return (
            json.dumps(
                value,
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, UnicodeError, ValueError) as exc:
        raise CorpusCompletionSummaryError(
            "summarize-corpus run card is not canonical JSON"
        ) from exc


__all__ = ["add_acquisition_completion_summary_parser"]
