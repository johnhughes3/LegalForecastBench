"""Console entry point for the v3 exact-100 successor lane.

Why this is a console script rather than an ``legalforecast acquisition``
subcommand: ``tests/test_architecture.py`` ratchets ``legalforecast/cli.py`` at
a fixed line and handler count, and freezes the exact list of modules allowed
to import it.  The migration note that introduced those ratchets records that
they shrink and never grow.  ``legalforecast-exact100-convergence`` is the
existing precedent for exactly this situation, and this follows it: nothing
here touches ``cli.py`` or imports from it.

Two subcommands ship together, because a fail-closed executor without its
issuance path is an unfinished feature:

``mint-replacement-evidence``
    seals one owner-adjudicated replacement into an evidence root.

``project-successor-v3``
    replays the authenticated cohort head, N terminal exclusions and their
    paired replacements into a new exact-100 successor root.

Predecessor authority follows the v2 pattern rather than a recursive replay of
the whole chain: the sealed map below pins the current head's digests, and each
is additionally cross-checked against the head's own committed
``output_commitments`` so a doctored map alone cannot admit a substituted root.
A v3 root is accepted as a predecessor too, provided its run card chains back to
that same anchor -- which is what lets a later swap execute without a v4.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from legalforecast.contracts import (
    EXACT100_METHODS_DISCLOSURE_V1,
    EXACT100_SUPPORTING_DOCUMENT_SUCCESSOR_V1,
)
from legalforecast.ingestion.canonical_json import canonical_json_bytes
from legalforecast.ingestion.exact100_successor_v3.projector import (
    STAGE,
    STATE_SCHEMA_VERSION,
    Exact100SuccessorReplacementV3,
    Exact100SuccessorReplacementV3Error,
    TerminalExclusionGroundV2,
    is_owner_judgment_ground,
    methods_disclosure_text,
    mint_verified_exact100_v3_base,
    mint_verified_exact100_v3_terminal_exclusions,
    project_exact100_successor_replacement_v3,
)
from legalforecast.ingestion.exact100_successor_v3.replacement_evidence import (
    OwnerAdjudicatedReplacementError,
    VerifiedOwnerAdjudicatedReplacement,
)
from legalforecast.ingestion.exact100_successor_v3.replacement_evidence_cli import (
    OwnerAdjudicatedReplacementCliError,
    verify_owner_adjudicated_replacement_evidence,
)
from legalforecast.ingestion.exact100_successor_v3.replacement_evidence_cli import (
    add_parser as add_mint_parser,
)
from legalforecast.ingestion.exact100_successor_v3.replacement_evidence_cli import (
    run as run_mint,
)

COMMAND = "legalforecast-exact100-successor-v3"

# The cohort head this lane chains from: root 46, the supporting-document
# successor.  Pinned by digest, never by path -- the operator supplies the path
# and these digests decide whether it is the authentic head.
_ANCHOR_RUN_CARD_SHA256 = (
    "61645025ec32d6aa22ee0533028ac210341d4087cb656716c7233bd9c4cc4a8f"
)
_ANCHOR_SCHEMA_VERSION = str(EXACT100_SUPPORTING_DOCUMENT_SUCCESSOR_V1)
_ANCHOR_STAGE = "project-exact100-supporting-document-successor"
# The cohort head commits its outputs under LOGICAL names, not filenames, so
# each entry carries both: the key the run card uses, and the file it names.
_ANCHOR_OUTPUTS: Mapping[str, tuple[str, str]] = {
    "selection": (
        "target-cohort-selection.jsonl",
        "eb780b19fc50733ecf5cbae3dc7e140197b09fdb0e53db065da2183b36ff6834",
    ),
    "relevance": (
        "case-relevance.jsonl",
        "d8bd1ab98c7c61d180dcf5437e5d18d49c7051371bf4bdc7b4687cb71b6c0bbe",
    ),
    "manifest": (
        "document-downloads-merged.jsonl",
        "efdadda36e78f5cc727d56e20ba40508e7e4e1f136c650f40ae519fdaba04daf",
    ),
    "clearance": (
        "disclosure-clearance.jsonl",
        "31db2f59824844eda4fef5312a7bca34e80aff425564bcbd7af7e9f8b651aab7",
    ),
    "restriction": (
        "restriction-evidence.jsonl",
        "bf03406437e995ab13243043ecf2bb52a6b9002cde1a741ec4176b9a30b76c3b",
    ),
    "core_filter": (
        "core-filter-results.jsonl",
        "a4399af0626bcde701345a0d2aec3288071f3e1a805c759d77836bfb18d45c5f",
    ),
}
# The six cohort-surface files a predecessor must supply, whatever it calls them
# in its own run card.  A v3 root keys its commitments by filename directly.
_COHORT_SURFACE_FILES = tuple(
    relative for relative, _digest in _ANCHOR_OUTPUTS.values()
)

# Root 46's own committed inputs, which chain the anchor back to the v2 root by
# commitment without this lane having to replay that chain.
_ANCHOR_INPUT_SHA256: Mapping[str, str] = {
    "bridge_sha256": (
        "sha256:57680ad68c094a72e4cdc03946a488ada7de4ff3aa7bc4cdd3dda7c981007261"
    ),
    "plan_sha256": (
        "sha256:66f7ed7be8e9343ed74ad7437027ce0a09e7fe5078b2503398924524eb64f38a"
    ),
    "v2_selection_sha256": (
        "sha256:f689620e1612a48ef0cf08aa6d7ef3ba61fcb2848a071e3ce0ea0ca2b705a04d"
    ),
}
_CARRIED_SUPPLEMENTAL_ROOT = "supplemental-free-source"
# Chain verification is linear -- run_project replays twice at the top, and each
# hop replays its predecessor once -- so depth is bounded by the real chain, not
# by cost.  The cap exists for a different reason: two roots naming each other in
# input_roots would recurse until the interpreter's own limit and surface a
# traceback instead of a refusal.
#
# The value is therefore derived from stack safety, NOT from how many swaps are
# expected.  This lane exists so later swaps chain without a v4, and there is no
# re-anchoring step, so the legitimate chain grows for the life of the project.
# A cap sized to today's chain would eventually refuse honest work.
_MAX_PREDECESSOR_CHAIN_DEPTH = 256

_OUTPUT_NAMES = {
    "selection": "target-cohort-selection.jsonl",
    "config": "target-cohort-projection.json",
    "case_relevance": "case-relevance.jsonl",
    "download_manifest": "document-downloads-merged.jsonl",
    "clearance": "disclosure-clearance.jsonl",
    "restriction": "restriction-evidence.jsonl",
    "core_filter": "core-filter-results.jsonl",
    "terminal_exclusions": "successor-terminal-exclusions.jsonl",
    "promotions": "successor-promotions.jsonl",
    "methods_disclosure": "methods-disclosure.json",
    "state": "run-cards/project-exact100-successor-replacement-v3.json",
}
_REPLACEMENT_DOCUMENT_ROOT = "owner-adjudicated-source/documents"

StipulatedReplay = Callable[[Path, bytes], tuple[Mapping[str, Any], ...]]


class Exact100SuccessorReplacementV3CliError(ValueError):
    """Raised when the v3 successor cannot be safely published."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=COMMAND,
        description=(
            "Provider-free exact-100 successor v3: mint owner-adjudicated "
            "replacement evidence, and project a cohort head plus N terminal "
            "exclusions into a successor cohort of exactly 100 cases."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    add_mint_parser(subparsers, handler=run_mint)
    add_project_parser(subparsers, handler=run_project)
    return parser


def add_project_parser(subparsers: Any, *, handler: Any) -> None:
    parser = subparsers.add_parser(
        "project-successor-v3",
        help="Project the cohort head and N paired swaps into a successor.",
        description=(
            "Replays the authenticated cohort head, every stipulated "
            "eligibility-audit root supplied, the recorded owner-judgment "
            "exclusions and the sealed replacement evidence roots into a new "
            "exact-100 successor.  It exposes no provider, retrieval, paid, "
            "model, evaluation, freeze or dispatch action."
        ),
    )
    parser.add_argument("--predecessor-root", type=Path, required=True)
    parser.add_argument(
        "--stipulated-evidence-root", type=Path, action="append", default=[]
    )
    parser.add_argument(
        "--owner-judgment-exclusion", type=Path, action="append", default=[]
    )
    parser.add_argument(
        "--replacement-evidence-root",
        type=Path,
        action="append",
        default=[],
        required=True,
    )
    parser.add_argument("--output-root", type=Path, required=True)
    parser.set_defaults(handler=handler)


def run_project(args: argparse.Namespace) -> int:
    """Publish a v3 successor only after two identical authenticated replays."""

    output_root = cast(Path, args.output_root)
    predecessor_root = cast(Path, args.predecessor_root)
    stipulated_roots = tuple(cast(list[Path], args.stipulated_evidence_root))
    owner_exclusions = tuple(cast(list[Path], args.owner_judgment_exclusion))
    replacement_roots = tuple(cast(list[Path], args.replacement_evidence_root))
    if not stipulated_roots and not owner_exclusions:
        raise Exact100SuccessorReplacementV3CliError(
            "v3 successor requires at least one terminal exclusion source"
        )
    inputs = (
        predecessor_root,
        *stipulated_roots,
        *owner_exclusions,
        *replacement_roots,
    )
    for path in inputs:
        if _overlaps(output_root, path):
            raise Exact100SuccessorReplacementV3CliError(
                "v3 successor output overlaps authenticated input evidence"
            )
    _validate_output_root(output_root)

    first, first_documents, anchor = _project(
        predecessor_root=predecessor_root,
        stipulated_roots=stipulated_roots,
        owner_exclusions=owner_exclusions,
        replacement_roots=replacement_roots,
    )
    # The whole authenticated surface is replayed a second time before anything
    # is published, so a concurrent edit to any input root cannot slip between
    # verification and the write.
    second, second_documents, second_anchor = _project(
        predecessor_root=predecessor_root,
        stipulated_roots=stipulated_roots,
        owner_exclusions=owner_exclusions,
        replacement_roots=replacement_roots,
    )
    if (
        _result_payloads(first) != _result_payloads(second)
        or first_documents != second_documents
        or anchor != second_anchor
    ):
        raise Exact100SuccessorReplacementV3CliError(
            "v3 authenticated inputs changed during replay"
        )

    payloads = _result_payloads(first)
    payloads["methods_disclosure"] = _canonical(
        {
            "schema_version": str(EXACT100_METHODS_DISCLOSURE_V1),
            "owner_adjudicated_promotion_count": sum(
                1
                for record in first.promotions
                if record.get("provenance_class") == "owner_adjudicated"
            ),
            "promotions": [
                {
                    "candidate_id": record["candidate_id"],
                    "replaces_candidate_id": record["replaces_candidate_id"],
                    "provenance_class": record["provenance_class"],
                }
                for record in first.promotions
            ],
            "disclosure_text": methods_disclosure_text(first),
        }
    )
    state = {
        **first.state,
        "stage": STAGE,
        "dry_run": False,
        "execute": True,
        "record_count": len(first.selection),
        "predecessor_anchor_sha256": anchor,
        "input_paths": [str(path.absolute()) for path in inputs],
        "input_roots": {
            "predecessor_root": str(predecessor_root.absolute()),
            "stipulated_evidence_roots": [
                str(path.absolute()) for path in stipulated_roots
            ],
            "owner_judgment_exclusions": [
                str(path.absolute()) for path in owner_exclusions
            ],
            "replacement_evidence_roots": [
                str(path.absolute()) for path in replacement_roots
            ],
        },
        "output_paths": [
            str((output_root / relative).absolute())
            for relative in _OUTPUT_NAMES.values()
        ],
        "output_commitments": {
            **cast(Mapping[str, str], first.config["output_commitments"]),
            _OUTPUT_NAMES["config"]: _sha(first.config_bytes),
            _OUTPUT_NAMES["methods_disclosure"]: _sha(payloads["methods_disclosure"]),
            **{
                relative: _sha(payload)
                for relative, payload in sorted(first_documents.items())
            },
        },
    }
    payloads["state"] = _canonical(state)

    for name, payload in payloads.items():
        _write_immutable(output_root / _OUTPUT_NAMES[name], payload)
    for relative, payload in first_documents.items():
        _write_immutable(output_root / relative, payload)
    _validate_output_root(output_root, expected_documents=set(first_documents))
    print(
        json.dumps(
            {
                "schema_version": STATE_SCHEMA_VERSION,
                "status": "completed",
                "selected_case_count": len(first.selection),
                "terminal_candidate_ids": first.state["terminal_candidate_ids"],
                "promoted_candidate_ids": first.state["promoted_candidate_ids"],
                "predecessor_anchor_sha256": anchor,
                "output_root": str(output_root.absolute()),
                "paid_activity_executed": False,
                "provider_activity_executed": False,
            },
            sort_keys=True,
        )
    )
    return 0


def _project(
    *,
    predecessor_root: Path,
    stipulated_roots: Sequence[Path],
    owner_exclusions: Sequence[Path],
    replacement_roots: Sequence[Path],
    depth: int = 0,
) -> tuple[Exact100SuccessorReplacementV3, dict[str, bytes], str]:
    if depth > _MAX_PREDECESSOR_CHAIN_DEPTH:
        raise Exact100SuccessorReplacementV3CliError(
            "v3 predecessor chain is longer than the supported depth"
        )
    base, anchor, carried = _verified_predecessor(predecessor_root, depth=depth)
    exclusions: list[Mapping[str, Any]] = []
    for root in stipulated_roots:
        exclusions.extend(_replay_stipulated_exclusions(root, base.selection_bytes))
    for path in owner_exclusions:
        exclusions.append(_owner_judgment_exclusion(path))
    terminal = mint_verified_exact100_v3_terminal_exclusions(
        selection_bytes=base.selection_bytes, exclusions=exclusions
    )
    replacements: list[VerifiedOwnerAdjudicatedReplacement] = [
        verify_owner_adjudicated_replacement_evidence(root)
        for root in replacement_roots
    ]
    result = project_exact100_successor_replacement_v3(
        base=base, terminal_exclusions=terminal, replacements=replacements
    )
    documents = dict(carried)
    for replacement in replacements:
        for relative, payload in replacement.document_bytes.items():
            # ``relative`` is already documents/<candidate>/<id>.pdf, which is
            # exactly the layout the manifest's local_path resolves against.
            key = f"{_REPLACEMENT_DOCUMENT_ROOT}/{relative.removeprefix('documents/')}"
            documents[key] = payload
    return result, documents, anchor


def _verified_predecessor(
    root: Path, *, depth: int = 0
) -> tuple[Any, str, dict[str, bytes]]:
    """Authenticate the cohort head, whether it is the anchor or a v3 root."""

    anchor_card = root / "run-cards/project-exact100-supporting-document-successor.json"
    v3_card = root / _OUTPUT_NAMES["state"]
    if anchor_card.is_file():
        return _verified_anchor_predecessor(root, anchor_card)
    if v3_card.is_file():
        return _verified_chained_predecessor(root, v3_card, depth=depth)
    raise Exact100SuccessorReplacementV3CliError(
        "predecessor root carries neither the sealed cohort head nor a v3 run card"
    )


def _verified_anchor_predecessor(
    root: Path, card_path: Path
) -> tuple[Any, str, dict[str, bytes]]:
    card_bytes = _read(card_path)
    digest = hashlib.sha256(card_bytes).hexdigest()
    if digest != _ANCHOR_RUN_CARD_SHA256:
        raise Exact100SuccessorReplacementV3CliError(
            "cohort head run card differs from the sealed v3 anchor"
        )
    card = _object(card_bytes, card_path)
    if (
        card.get("schema_version") != _ANCHOR_SCHEMA_VERSION
        or card.get("stage") != _ANCHOR_STAGE
        or card.get("status") != "completed"
        or card.get("selected_case_count") != 100
    ):
        raise Exact100SuccessorReplacementV3CliError(
            "cohort head run card is not a completed 100-case successor"
        )
    committed = _mapping(card.get("output_commitments"), "cohort head commitments")
    if {
        key: str(committed.get(key, "")).removeprefix("sha256:")
        for key in _ANCHOR_OUTPUTS
    } != {key: digest for key, (_relative, digest) in _ANCHOR_OUTPUTS.items()}:
        raise Exact100SuccessorReplacementV3CliError(
            "cohort head commitments differ from the sealed v3 anchor"
        )
    inputs = _mapping(card.get("input_commitments"), "cohort head input commitments")
    if {name: inputs.get(name) for name in _ANCHOR_INPUT_SHA256} != dict(
        _ANCHOR_INPUT_SHA256
    ):
        raise Exact100SuccessorReplacementV3CliError(
            "cohort head does not chain to the sealed predecessor lineage"
        )
    payloads = {
        relative: _require_committed(root / relative, digest)
        for relative, digest in _ANCHOR_OUTPUTS.values()
    }
    base = _mint_base(
        card_bytes=card_bytes,
        schema_version=_ANCHOR_SCHEMA_VERSION,
        stage=_ANCHOR_STAGE,
        payloads=payloads,
        run_card_sha256=digest,
    )
    return (
        base,
        digest,
        _carried_documents(root, _anchor_document_commitments(committed)),
    )


def _anchor_document_commitments(committed: Mapping[str, Any]) -> dict[str, str]:
    """Map the cohort head's supplemental commitments onto its own file paths.

    The head commits its supplemental documents under
    ``supplemental_document:<path-under-documents>`` keys plus two sidecar
    manifests.  Rewriting them to root-relative paths is what lets the carried
    tree be checked rather than trusted.
    """

    expected: dict[str, str] = {}
    for name, value in committed.items():
        if not isinstance(value, str):
            continue
        digest = value.removeprefix("sha256:")
        if name.startswith("supplemental_document:"):
            relative = name.removeprefix("supplemental_document:")
            expected[f"{_CARRIED_SUPPLEMENTAL_ROOT}/documents/{relative}"] = digest
        elif name == "supplemental_manifest":
            expected[f"{_CARRIED_SUPPLEMENTAL_ROOT}/document-downloads.jsonl"] = digest
        elif name == "supplemental_clearance":
            expected[f"{_CARRIED_SUPPLEMENTAL_ROOT}/disclosure-clearance.jsonl"] = (
                digest
            )
    return expected


def _verified_chained_predecessor(
    root: Path, card_path: Path, *, depth: int = 0
) -> tuple[Any, str, dict[str, bytes]]:
    """Accept an earlier v3 root only by replaying the run that produced it.

    Checking a v3 card's self-declared digests would authenticate nothing: the
    anchor constant is public, so a fabricated card naming any structurally
    valid 100-case surface would pass.  The card names the exact roots it was
    minted from, so those are replayed and the result must equal the persisted
    bytes -- the same shape the supporting-document successor uses, and the
    reason a root cannot authorise itself.
    """

    card_bytes = _read(card_path)
    card = _object(card_bytes, card_path)
    if (
        card.get("schema_version") != STATE_SCHEMA_VERSION
        or card.get("stage") != STAGE
        or card.get("status") != "completed"
        or card.get("selected_case_count") != 100
        or card.get("predecessor_anchor_sha256") != _ANCHOR_RUN_CARD_SHA256
    ):
        raise Exact100SuccessorReplacementV3CliError(
            "v3 predecessor run card does not chain to the sealed anchor"
        )
    recorded = _mapping(card.get("input_roots"), "v3 predecessor input roots")
    replayed, replayed_documents, _anchor = _project(
        predecessor_root=Path(_required_str(recorded, "predecessor_root")),
        stipulated_roots=_path_list(recorded, "stipulated_evidence_roots"),
        owner_exclusions=_path_list(recorded, "owner_judgment_exclusions"),
        replacement_roots=_path_list(recorded, "replacement_evidence_roots"),
        depth=depth + 1,
    )
    expected = _result_payloads(replayed)
    payloads: dict[str, bytes] = {}
    for name, relative in _OUTPUT_NAMES.items():
        if name in {"state", "methods_disclosure"}:
            continue
        payload = _read(root / relative)
        if payload != expected[name]:
            raise Exact100SuccessorReplacementV3CliError(
                f"v3 predecessor output differs from its replay: {relative}"
            )
        payloads[relative] = payload
    carried = _carried_documents(
        root,
        {
            relative: hashlib.sha256(payload).hexdigest()
            for relative, payload in replayed_documents.items()
        },
    )
    base = _mint_base(
        card_bytes=card_bytes,
        schema_version=STATE_SCHEMA_VERSION,
        stage=STAGE,
        payloads={name: payloads[name] for name in _COHORT_SURFACE_FILES},
        run_card_sha256=hashlib.sha256(card_bytes).hexdigest(),
    )
    return base, _ANCHOR_RUN_CARD_SHA256, carried


def _mint_base(
    *,
    card_bytes: bytes,
    schema_version: str,
    stage: str,
    payloads: Mapping[str, bytes],
    run_card_sha256: str,
) -> Any:
    return mint_verified_exact100_v3_base(
        predecessor_run_card_bytes=card_bytes,
        predecessor_schema_version=schema_version,
        predecessor_stage=stage,
        selection_rows=_jsonl(payloads["target-cohort-selection.jsonl"]),
        case_relevance_rows=_jsonl(payloads["case-relevance.jsonl"]),
        download_manifest_rows=_jsonl(payloads["document-downloads-merged.jsonl"]),
        disclosure_rows=_jsonl(payloads["disclosure-clearance.jsonl"]),
        restriction_rows=_jsonl(payloads["restriction-evidence.jsonl"]),
        core_filter_rows=_jsonl(payloads["core-filter-results.jsonl"]),
        source_commitments={
            "predecessor_run_card": "sha256:" + run_card_sha256,
            **{
                f"predecessor_{name}": "sha256:" + hashlib.sha256(payload).hexdigest()
                for name, payload in payloads.items()
            },
        },
    )


def _path_list(recorded: Mapping[str, Any], name: str) -> tuple[Path, ...]:
    value = recorded.get(name)
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise Exact100SuccessorReplacementV3CliError(
            f"v3 predecessor run card {name} is malformed"
        )
    paths: list[Path] = []
    for item in cast(Sequence[object], value):
        if not isinstance(item, str) or not item:
            raise Exact100SuccessorReplacementV3CliError(
                f"v3 predecessor run card {name} is malformed"
            )
        paths.append(Path(item))
    return tuple(paths)


def _carried_documents(root: Path, committed: Mapping[str, str]) -> dict[str, bytes]:
    """Carry the predecessor's document trees forward, checked against its card.

    Dropping them would strand the candidates earlier successors added, so the
    successor root stays a complete materialisation surface.  Republishing them
    unchecked would be worse: the next successor's fresh commitments would bless
    whatever bytes happened to be on disk, so byte-role validated evidence could
    silently diverge from what is carried.  Every carried file is therefore
    matched against the predecessor's own committed digest, and every committed
    document must still be present.
    """

    carried: dict[str, bytes] = {}
    for prefix in (_CARRIED_SUPPLEMENTAL_ROOT, _REPLACEMENT_DOCUMENT_ROOT):
        source = root / prefix
        if not source.is_dir():
            continue
        for path in sorted(source.rglob("*")):
            if path.is_symlink():
                raise Exact100SuccessorReplacementV3CliError(
                    "predecessor document tree contains a symlink"
                )
            if not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            payload = path.read_bytes()
            expected = committed.get(relative)
            if expected is None:
                raise Exact100SuccessorReplacementV3CliError(
                    f"predecessor carries an uncommitted document: {relative}"
                )
            if hashlib.sha256(payload).hexdigest() != expected.removeprefix("sha256:"):
                raise Exact100SuccessorReplacementV3CliError(
                    f"predecessor document differs from its commitment: {relative}"
                )
            carried[relative] = payload
    missing = set(committed) - set(carried)
    if missing:
        raise Exact100SuccessorReplacementV3CliError(
            f"predecessor is missing a committed document: {sorted(missing)[0]}"
        )
    return carried


def _replay_stipulated_exclusions(
    root: Path, selection_bytes: bytes
) -> tuple[Mapping[str, Any], ...]:
    """Mint one exclusion per ineligible target in an authenticated audit root.

    v1 narrowed this to exactly one ineligible target, which is precisely why a
    cohort holding three could not be repaired.  v3 admits the whole ineligible
    set from a single audit, because the audit is minted over the entire
    selection and binds those bytes -- it cannot be scoped to one candidate.

    The replay deliberately mirrors the MINT path's detector generation rather
    than v1's frozen-predecessor generation.  A freshly minted audit is
    persisted under today's detector, so replaying it under the frozen
    contemporaneous regime would re-derive a different ineligible set and refuse.
    """

    from legalforecast.ingestion.stage_a_lineage_verification import (
        StageALineageInputs,
        require_stage_a_parse_lineage_unchanged,
        stage_a_markdown_path,
        verify_stage_a_parse_lineage_uncached,
    )
    from legalforecast.ingestion.target_document_eligibility_audit import (
        TargetDocumentEligibilityAuditError,
        _replay_verified_target_document_eligibility_audit,  # pyright: ignore[reportPrivateUsage]
        require_verified_target_document_eligibility_audit,
    )

    audit_path = root / "target-document-eligibility-audit.jsonl"
    card_path = root / "run-cards/audit-stage-a-target-eligibility.json"
    audit_bytes = _read(audit_path)
    card_bytes = _read(card_path)
    card = _object(card_bytes, card_path)
    if (
        card.get("stage") != "audit-stage-a-target-eligibility"
        or card.get("status") != "completed"
    ):
        raise Exact100SuccessorReplacementV3CliError(
            "stipulated eligibility audit run card is not a completed audit"
        )
    lineage_inputs, markdown_root = _lineage_inputs(card, StageALineageInputs)
    # frozen_predecessor_replay stays False on purpose. A freshly minted audit
    # is persisted under today's detector, so the frozen contemporaneous regime
    # would re-derive a different ineligible set and refuse; the verifier's own
    # docstring puts the successor half of a replay on the current gate.
    lineage = verify_stage_a_parse_lineage_uncached(
        lineage_inputs, markdown_root=markdown_root
    )
    if lineage.selection_bytes != selection_bytes:
        raise Exact100SuccessorReplacementV3CliError(
            "stipulated eligibility audit selection differs from the predecessor"
        )
    markdown_by_document: dict[tuple[str, str], bytes] = {}
    for record in lineage.parser_records:
        key = (
            _required_str(record, "candidate_id"),
            _required_str(record, "source_document_id"),
        )
        path = stage_a_markdown_path(record, markdown_root=lineage.markdown_root)
        relative = path.relative_to(lineage.markdown_root.resolve()).as_posix()
        markdown_by_document[key] = lineage.markdown_bytes[relative]
    try:
        audit = _replay_verified_target_document_eligibility_audit(
            persisted_audit_bytes=audit_bytes,
            selection_bytes=lineage.selection_bytes,
            parser_manifest_bytes=lineage.parser_manifest_bytes,
            parser_records=lineage.parser_records,
            markdown_by_document=markdown_by_document,
        )
        require_verified_target_document_eligibility_audit(audit)
    except TargetDocumentEligibilityAuditError as exc:
        raise Exact100SuccessorReplacementV3CliError(str(exc)) from exc
    require_stage_a_parse_lineage_unchanged(lineage)
    if _read(audit_path) != audit_bytes or _read(card_path) != card_bytes:
        raise Exact100SuccessorReplacementV3CliError(
            "stipulated eligibility audit root changed during replay"
        )
    if not audit.ineligible_records:
        raise Exact100SuccessorReplacementV3CliError(
            "stipulated eligibility audit contains no ineligible target"
        )
    citation = _stipulated_audit_citation(card_bytes)
    return tuple(
        {
            "candidate_id": _required_str(record, "candidate_id"),
            "source_document_id": _required_str(record, "source_document_id"),
            "ground": TerminalExclusionGroundV2.STIPULATED_INELIGIBLE.value,
            "evidence_commitments": {
                "selection": audit.selection_sha256,
                "target_eligibility_audit": audit.commitment_sha256,
                "target_eligibility_record": _sha(_canonical(dict(record))),
                **dict(audit.input_commitments),
            },
            "owner_authorization_commitments": citation,
        }
        for record in audit.ineligible_records
    )


def _stipulated_audit_citation(card_bytes: bytes) -> dict[str, str]:
    """Cite the audit run card whose replay produced this exclusion.

    Named for what it is.  A detector-derived exclusion's authority is the
    authenticated audit replay, not an owner signature, and the earlier name
    invited a future auditor to read it as the latter.  A hash of the root's
    path string was also dropped: it committed nothing about content and did not
    survive relocation.
    """

    return {"stipulated_audit_run_card": _sha(card_bytes)}


def _owner_judgment_exclusion(path: Path) -> Mapping[str, Any]:
    """Read one recorded owner-judgment exclusion and its citation."""

    payload = _read(path)
    record = _object(payload, path)
    ground = record.get("ground")
    if not isinstance(ground, str) or not any(
        ground == candidate.value
        for candidate in TerminalExclusionGroundV2
        if is_owner_judgment_ground(candidate)
    ):
        raise Exact100SuccessorReplacementV3CliError(
            "owner-judgment exclusion carries an unsupported ground"
        )
    citation = _mapping(
        record.get("owner_disposition"), "owner-judgment exclusion disposition"
    )
    # Hold the same bar the replacement side already holds: a citation that
    # names no recorded owner text, and no source for it, is not a disposition.
    # This ground is only ever human-verifiable, which is a reason to record it
    # more carefully than a detector-derived one, not less.
    _required_str(citation, "owner_verbatim")
    _required_str(citation, "signoff_source")
    return {
        "candidate_id": _required_str(record, "candidate_id"),
        "source_document_id": _required_str(record, "source_document_id"),
        "ground": ground,
        "evidence_commitments": {},
        "owner_authorization_commitments": {
            "owner_judgment_exclusion": _sha(payload),
            "owner_disposition_artifact": _required_str(citation, "artifact_sha256"),
        },
    }


def _lineage_inputs(card: Mapping[str, Any], inputs_type: Any) -> tuple[Any, Path]:
    """Rebuild the parse-lineage inputs the audit run card already committed.

    Every path comes from the card's own ``input_paths``, so this replays
    digest-committed ancestor evidence rather than caller-selected sources.
    """

    raw = card.get("input_paths")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        raise Exact100SuccessorReplacementV3CliError(
            "stipulated eligibility audit run card lacks input paths"
        )
    values = tuple(cast(Sequence[object], raw))
    if len(values) < 10 or not all(
        isinstance(value, str) and value for value in values
    ):
        raise Exact100SuccessorReplacementV3CliError(
            "stipulated eligibility audit run card input paths differ"
        )
    paths = tuple(Path(cast(str, value)) for value in values)
    replay = _mapping(card.get("replay_paths"), "audit replay paths")
    if set(replay) != {
        "controlled_private_root",
        "purchase_ledger_initialization_receipt",
    }:
        raise Exact100SuccessorReplacementV3CliError(
            "stipulated eligibility audit run card lacks replay paths"
        )

    def optional(name: str) -> Path | None:
        value = replay.get(name)
        if value is None:
            return None
        if not isinstance(value, str) or not value:
            raise Exact100SuccessorReplacementV3CliError(
                "stipulated eligibility audit replay path is invalid"
            )
        return Path(value)

    return (
        inputs_type(
            selection=paths[0],
            selection_run_card=paths[1],
            download_manifest=paths[2],
            disclosure_clearance=paths[3],
            materialization_run_card=paths[4],
            document_root=paths[5],
            parse_requests=paths[6],
            parser_manifest=paths[7],
            parser_run_card=paths[8],
            controlled_private_root=optional("controlled_private_root"),
            purchase_ledger_initialization_receipt=optional(
                "purchase_ledger_initialization_receipt"
            ),
        ),
        paths[9],
    )


def _result_payloads(result: Exact100SuccessorReplacementV3) -> dict[str, bytes]:
    return {
        "selection": result.selection_bytes,
        "config": result.config_bytes,
        "case_relevance": result.case_relevance_bytes,
        "download_manifest": result.download_manifest_bytes,
        "clearance": result.disclosure_clearance_bytes,
        "restriction": result.restriction_evidence_bytes,
        "core_filter": result.core_filter_results_bytes,
        "terminal_exclusions": result.terminal_exclusions_bytes,
        "promotions": result.promotions_bytes,
    }


def _validate_output_root(
    root: Path, *, expected_documents: set[str] | None = None
) -> None:
    if not root.exists():
        return
    if root.is_symlink() or not root.is_dir():
        raise Exact100SuccessorReplacementV3CliError(
            "v3 successor output root must be a regular directory"
        )
    allowed = set(_OUTPUT_NAMES.values()) | (expected_documents or set())
    files: set[str] = set()
    for path in root.rglob("*"):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise Exact100SuccessorReplacementV3CliError(
                "v3 successor output contains a non-regular path"
            )
        if path.is_file():
            files.add(path.relative_to(root).as_posix())
    if expected_documents is None:
        unexpected = {
            name
            for name in files
            if name not in allowed
            and not name.startswith((_CARRIED_SUPPLEMENTAL_ROOT + "/",))
            and not name.startswith(_REPLACEMENT_DOCUMENT_ROOT + "/")
        }
        if unexpected:
            raise Exact100SuccessorReplacementV3CliError(
                "v3 successor output root contains unexpected paths"
            )
        return
    if files != allowed:
        raise Exact100SuccessorReplacementV3CliError(
            "v3 successor output root contains unexpected paths"
        )


def _require_committed(path: Path, expected: str) -> bytes:
    payload = _read(path)
    if hashlib.sha256(payload).hexdigest() != expected:
        raise Exact100SuccessorReplacementV3CliError(
            f"predecessor output differs from its commitment: {path.name}"
        )
    return payload


def _write_immutable(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if _read(path) != payload:
            raise Exact100SuccessorReplacementV3CliError(
                f"immutable v3 successor output differs: {path}"
            )
        return
    path.write_bytes(payload)


def _read(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise Exact100SuccessorReplacementV3CliError(
            f"missing regular evidence file: {path}"
        )
    return path.read_bytes()


def _object(payload: bytes, path: Path) -> dict[str, Any]:
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Exact100SuccessorReplacementV3CliError(f"{path} is not JSON") from exc
    if not isinstance(value, dict):
        raise Exact100SuccessorReplacementV3CliError(f"{path} is not a JSON object")
    return cast(dict[str, Any], value)


def _jsonl(payload: bytes) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for line in payload.splitlines():
        if not line.strip():
            raise Exact100SuccessorReplacementV3CliError("evidence has a blank line")
        value = json.loads(line)
        if not isinstance(value, dict):
            raise Exact100SuccessorReplacementV3CliError(
                "evidence line is not an object"
            )
        rows.append(cast(dict[str, Any], value))
    return tuple(rows)


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise Exact100SuccessorReplacementV3CliError(f"{label} is malformed")
    return cast(Mapping[str, Any], value)


def _required_str(record: Mapping[str, Any], name: str) -> str:
    value = record.get(name)
    if not isinstance(value, str) or not value.strip():
        raise Exact100SuccessorReplacementV3CliError(f"record lacks {name}")
    return value


def _canonical(value: object) -> bytes:
    return canonical_json_bytes(
        value,
        error_type=Exact100SuccessorReplacementV3CliError,
        error_message="v3 successor serialization failed",
    )


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _overlaps(first: Path, second: Path) -> bool:
    left, right = Path(os.path.abspath(first)), Path(os.path.abspath(second))
    return left == right or left in right.parents or right in left.parents


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    handler = cast(Callable[[argparse.Namespace], int], args.handler)
    try:
        return handler(args)
    except (
        Exact100SuccessorReplacementV3CliError,
        Exact100SuccessorReplacementV3Error,
        OwnerAdjudicatedReplacementCliError,
        OwnerAdjudicatedReplacementError,
    ) as exc:
        print(f"{COMMAND}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
