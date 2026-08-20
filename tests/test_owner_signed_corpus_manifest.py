"""Tests for the owner-directed corpus manifest and manifest-mode forecast.

Every fixture here is hand-authored (``synthetic: true``); no fixture in this
file is derived from a real corpus artifact, and no test touches a provider.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from legalforecast.evals.corpus_manifest.commands import (
    build_manifest_forecast_command,
    freeze_corpus_manifest_command,
)
from legalforecast.evals.corpus_manifest.forecast_entry import (
    FORECAST_ABLATIONS,
    REQUIRED_RUN_CASE_FLAGS,
    USE_DOCKET_TOOL,
    ManifestForecastError,
)
from legalforecast.evals.corpus_manifest.freeze import VERDICT_ROLE_COMPATIBILITY
from legalforecast.evals.corpus_manifest.schema import (
    AUDIT_ONLY_DOCUMENT_ROLES,
    MODEL_VISIBLE_DOCUMENT_ROLES,
    REQUIRED_CLAIM_BEARING_ROLES,
    REQUIRED_TARGET_MOTION_ROLES,
    CorpusManifestError,
    ManifestDocument,
    load_signed_manifest,
    manifest_digest,
)
from legalforecast.evals.corpus_manifest.stores import (
    CorpusStoreError,
    index_verdicts,
)
from legalforecast.evals.inspect_task import build_inspect_samples, render_model_prompt
from legalforecast.evals.packet_builder import PacketAblation, build_model_packet
from legalforecast.evals.per_case_runner import (
    PacketManifestError,
    _packet_object_from_record,
    _require_committed_prompt,
)
from legalforecast.evals.per_case_runner import (
    _model_packet_from_record as _packet_from_record,
)
from legalforecast.ingestion import model_packet_assembly
from legalforecast.ingestion.provenance import (
    CasePacketSchema,
    DocumentRole,
    SourceDocumentProvenance,
    sha256_text,
)

_GENERATED_AT = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
_DECISION_TEXT = "GRANTED. Every claim is dismissed with prejudice."
_APPROVAL = "I approve the corpus manifest {digest} for the Cycle 1 forecast run."


# --------------------------------------------------------------------------- #
# Fixture construction (synthetic: true)
# --------------------------------------------------------------------------- #


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", "utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _document_row(
    document_id: str,
    role: str,
    *,
    model_visible: bool,
    entry: int,
) -> dict[str, Any]:
    return {
        "source_document_id": document_id,
        "document_role": role,
        "model_visible": model_visible,
        "docket_entry_number": entry,
        "source_url": f"https://example.invalid/{document_id}.pdf",
    }


def _complaint_id(candidate_id: str) -> str:
    return f"{candidate_id}-complaint"


def _mtd_id(candidate_id: str) -> str:
    return f"{candidate_id}-mtd"


def _decision_id(candidate_id: str) -> str:
    return f"{candidate_id}-decision"


def _case_documents(candidate_id: str) -> list[dict[str, Any]]:
    return [
        _document_row(
            _complaint_id(candidate_id),
            "complaint",
            model_visible=True,
            entry=1,
        ),
        _document_row(
            _mtd_id(candidate_id),
            "motion_to_dismiss_memorandum",
            model_visible=True,
            entry=2,
        ),
        _document_row(
            _decision_id(candidate_id),
            "decision",
            model_visible=False,
            entry=9,
        ),
    ]


def _unit_row(candidate_id: str) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "case_id": candidate_id,
        "prediction_units": [
            {
                "unit_id": f"{candidate_id}-u1",
                "count": "Count 1",
                "claim_name": "Breach of contract",
                "defendant_group": "All Defendants",
                "challenged_by_motion": True,
                "challenge_scope": "entire_claim",
                "unit_confidence": 1.0,
                "should_score": True,
                "source_citations": [
                    {
                        "document_id": _complaint_id(candidate_id),
                        "excerpt": "Count 1",
                    }
                ],
            }
        ],
    }


def _write_store(root: Path, *, candidate_id: str, texts: dict[str, str]) -> None:
    """Write a parser-sidecar document store; synthetic: true."""

    for document_id, text in texts.items():
        pdf_path = root / "documents" / f"{document_id}.pdf"
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        pdf_path.write_bytes(f"%PDF-1.7 {document_id}".encode())
        markdown_path = root / "markdown" / candidate_id / f"{document_id}.md"
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(text, encoding="utf-8")
        _write_json(
            markdown_path.with_suffix(".metadata.json"),
            {
                "candidate_id": candidate_id,
                "source_document_id": document_id,
                "status": "succeeded",
                "input_path": str(pdf_path),
                "markdown_path": f"{candidate_id}/{document_id}.md",
                "source_sha256": "0" * 64,
                "quality_flags": [],
            },
        )


def _write_verdicts(path: Path, rows: list[dict[str, Any]]) -> None:
    _write_jsonl(path, rows)


def _write_registry(path: Path) -> None:
    """Registry fixture with an early release anchor; synthetic: true."""

    _write_json(
        path,
        [
            {
                "provider": "example-provider",
                "model_id": model_id,
                "display_name": model_id,
                "model_version_or_snapshot": f"{model_id}-2026-01-05",
                "release_timestamp": "2026-01-05T00:00:00Z",
                "release_timestamp_source": "fixture release note",
                "provider_training_cutoff_status": "not_disclosed",
                "temperature": 0,
                "top_p": 1,
                "max_output_tokens": 4096,
                "network_disabled": True,
                "search_disabled": True,
                "tool_policy": "controlled_docket_tool_only",
                "context_limit": 200000,
                "pricing_source": "fixture",
                "input_token_price": 1.0,
                "output_token_price": 2.0,
            }
            for model_id in ("fixture-model-a", "fixture-model-b")
        ],
    )


@pytest.fixture
def corpus(tmp_path: Path) -> dict[str, Path]:
    """A two-case corpus that freezes cleanly; synthetic: true."""

    selection = tmp_path / "selection.jsonl"
    units = tmp_path / "prediction-units.jsonl"
    store = tmp_path / "store"
    verdicts = tmp_path / "verdicts.jsonl"
    registry = tmp_path / "registry.json"

    selection_rows: list[dict[str, Any]] = []
    verdict_rows: list[dict[str, Any]] = []
    unit_rows: list[dict[str, Any]] = []
    for index in (1, 2):
        candidate_id = f"cand-{index}"
        selection_rows.append(
            {
                "candidate_id": candidate_id,
                "case_id": candidate_id,
                "court": "D. Example",
                "docket_number": f"1:26-cv-0000{index}",
                "decision_date": "2026-06-01",
                "selected": True,
                "target_motion_entry_numbers": [2],
                "documents": _case_documents(candidate_id),
            }
        )
        unit_rows.append(_unit_row(candidate_id))
        _write_store(
            store,
            candidate_id=candidate_id,
            texts={
                _complaint_id(candidate_id): (
                    f"# Complaint for {candidate_id}\n\nCount 1."
                ),
                _mtd_id(candidate_id): (
                    f"# Motion to dismiss {candidate_id}\n\nArgument."
                ),
                _decision_id(candidate_id): _DECISION_TEXT,
            },
        )
        for document_id, role in (
            (_complaint_id(candidate_id), "complaint"),
            (_mtd_id(candidate_id), "motion_memorandum"),
        ):
            verdict_rows.append(
                {
                    "source_document_id": document_id,
                    "byte_role_verdict": "match",
                    "role": role,
                    "validation_basis": "heuristic_title",
                }
            )

    _write_jsonl(selection, selection_rows)
    _write_jsonl(units, unit_rows)
    _write_verdicts(verdicts, verdict_rows)
    _write_registry(registry)
    return {
        "selection": selection,
        "units": units,
        "store": store,
        "verdicts": verdicts,
        "registry": registry,
        "manifest": tmp_path / "manifest.json",
        "output": tmp_path / "out",
    }


def _freeze(corpus: dict[str, Path]) -> tuple[dict[str, Any], bool]:
    return freeze_corpus_manifest_command(
        selection=corpus["selection"],
        prediction_units=corpus["units"],
        document_store_roots=(corpus["store"],),
        verdict_sources=(corpus["verdicts"],),
        cycle_id="cycle-1",
        output=corpus["manifest"],
        generated_at=_GENERATED_AT,
    )


def _build(corpus: dict[str, Path], digest: str) -> dict[str, Any]:
    return build_manifest_forecast_command(
        manifest=corpus["manifest"],
        expected_manifest_digest=digest,
        owner_signature_bead="legalforecastbench-3ak.38",
        owner_approval_line=_APPROVAL.format(digest=digest),
        model_registry=corpus["registry"],
        output_dir=corpus["output"],
        generated_at=_GENERATED_AT,
    )


# --------------------------------------------------------------------------- #
# Partition and drift fences
# --------------------------------------------------------------------------- #


def test_visibility_partition_covers_every_document_role_exactly_once() -> None:
    assert not (MODEL_VISIBLE_DOCUMENT_ROLES & AUDIT_ONLY_DOCUMENT_ROLES)
    assert (MODEL_VISIBLE_DOCUMENT_ROLES | AUDIT_ONLY_DOCUMENT_ROLES) == set(
        DocumentRole
    )


def test_outcome_roles_are_classified_audit_only() -> None:
    assert DocumentRole.DECISION in AUDIT_ONLY_DOCUMENT_ROLES
    assert DocumentRole.ORDER in AUDIT_ONLY_DOCUMENT_ROLES


def test_required_role_sets_match_the_packet_assembly_requirement() -> None:
    """Fence the duplication: drift in either module fails here, not in prod."""

    assert REQUIRED_CLAIM_BEARING_ROLES == model_packet_assembly._COMPLAINT_ROLES
    assert REQUIRED_TARGET_MOTION_ROLES == model_packet_assembly._TARGET_MTD_ROLES


# --------------------------------------------------------------------------- #
# Freeze
# --------------------------------------------------------------------------- #


def test_freeze_emits_a_self_hashed_manifest_over_fresh_disk_bytes(
    corpus: dict[str, Path],
) -> None:
    record, accepted = _freeze(corpus)

    assert accepted
    assert record["status"] == "frozen"
    assert record["case_count"] == 2
    assert record["document_count"] == 6
    assert record["model_visible_document_count"] == 4
    payload = json.loads(corpus["manifest"].read_text(encoding="utf-8"))
    assert payload["manifest_sha256"] == record["manifest_sha256"]
    assert manifest_digest(payload) == record["manifest_sha256"]


def test_freeze_marks_decisions_audit_only_and_never_model_visible(
    corpus: dict[str, Path],
) -> None:
    _freeze(corpus)

    payload = json.loads(corpus["manifest"].read_text(encoding="utf-8"))
    decisions = [
        document
        for case in payload["cases"]
        for document in case["documents"]
        if document["document_role"] == "decision"
    ]
    assert decisions
    assert all(document["model_visible"] is False for document in decisions)


def test_freeze_refuses_and_writes_nothing_when_markdown_is_absent(
    corpus: dict[str, Path],
) -> None:
    (corpus["store"] / "markdown" / "cand-2" / "cand-2-mtd.md").unlink()

    record, accepted = _freeze(corpus)

    assert not accepted
    assert record["status"] == "refused"
    assert not corpus["manifest"].exists()
    assert any("cand-2-mtd" in blocker for blocker in record["blockers"])


def test_freeze_records_an_unparsed_audit_only_document_without_blocking(
    corpus: dict[str, Path],
) -> None:
    """A decision the corpus never parsed is recorded, not silently dropped."""

    for name in ("cand-1-decision.md", "cand-1-decision.metadata.json"):
        (corpus["store"] / "markdown" / "cand-1" / name).unlink()

    record, accepted = _freeze(corpus)

    assert accepted
    payload = json.loads(corpus["manifest"].read_text(encoding="utf-8"))
    case = next(c for c in payload["cases"] if c["candidate_id"] == "cand-1")
    assert case["unresolved_audit_only_document_ids"] == [_decision_id("cand-1")]
    assert record["document_count"] == 5


def test_freeze_still_refuses_an_unparsed_model_visible_document(
    corpus: dict[str, Path],
) -> None:
    """The audit-only allowance must not extend to model-visible documents."""

    for name in ("cand-1-mtd.md", "cand-1-mtd.metadata.json"):
        (corpus["store"] / "markdown" / "cand-1" / name).unlink()

    record, accepted = _freeze(corpus)

    assert not accepted
    assert any(
        "has no parsed document in any store" in blocker
        for blocker in record["blockers"]
    )


def test_freeze_refuses_a_model_visible_document_with_no_verdict(
    corpus: dict[str, Path],
) -> None:
    _write_verdicts(
        corpus["verdicts"],
        [
            {
                "source_document_id": _complaint_id("cand-1"),
                "byte_role_verdict": "match",
                "role": "complaint",
            }
        ],
    )

    record, accepted = _freeze(corpus)

    assert not accepted
    assert any(
        "no byte-role validation verdict" in blocker for blocker in record["blockers"]
    )


def test_freeze_refuses_a_document_whose_verdict_certifies_another_role(
    corpus: dict[str, Path],
) -> None:
    """The adjudicated-away-role defect: bytes are a cover sheet, not a complaint."""

    _write_verdicts(
        corpus["verdicts"],
        [
            {
                "source_document_id": _complaint_id("cand-1"),
                "byte_role_verdict": "match",
                "role": "cover_sheet",
                "validation_basis": "adjudicated_text",
            },
            {
                "source_document_id": _mtd_id("cand-1"),
                "byte_role_verdict": "match",
                "role": "motion_memorandum",
            },
        ],
    )

    record, accepted = _freeze(corpus)

    assert not accepted
    assert any("certifies 'cover_sheet'" in blocker for blocker in record["blockers"])


@pytest.mark.parametrize("role_field", ["omitted", "null"])
def test_freeze_refuses_a_roleless_verdict_on_a_model_visible_document(
    corpus: dict[str, Path],
    role_field: str,
) -> None:
    """The reviewer's C1 attack, as a regression test.

    Relabel the outcome document as a model-visible role in the selection and
    back it with a verdict carrying no readable role.  The visibility partition
    cannot catch it (``reply`` is legitimately model-visible) and the verdict
    exists and says ``match``, so the ROLE CROSS-CHECK is the only thing left
    standing between a mislabelled corpus and outcome bytes in a packet.  A
    roleless verdict must therefore refuse, not skip.
    """

    rows = [
        json.loads(line)
        for line in corpus["selection"].read_text(encoding="utf-8").splitlines()
    ]
    for document in rows[0]["documents"]:
        if document["document_role"] == "decision":
            document["document_role"] = "reply"
            document["model_visible"] = True
    _write_jsonl(corpus["selection"], rows)

    verdicts = [
        json.loads(line)
        for line in corpus["verdicts"].read_text(encoding="utf-8").splitlines()
    ]
    attack: dict[str, Any] = {
        "source_document_id": _decision_id("cand-1"),
        "byte_role_verdict": "match",
    }
    if role_field == "null":
        attack["role"] = None
    verdicts.append(attack)
    _write_verdicts(corpus["verdicts"], verdicts)

    record, accepted = _freeze(corpus)

    assert not accepted
    assert any(
        "no readable role" in blocker and _decision_id("cand-1") in blocker
        for blocker in record["blockers"]
    ), record["blockers"]
    assert not corpus["manifest"].exists()


def test_every_model_visible_role_is_reachable_from_some_verdict_spelling() -> None:
    """Fence the second half of the partition.

    Closing the roleless fail-open makes an unmapped packet role the next
    silent blocker, so every role the manifest may mount must be certifiable by
    at least one verdict-store spelling.
    """

    reachable: set[DocumentRole] = set()
    for roles in VERDICT_ROLE_COMPATIBILITY.values():
        reachable |= roles
    assert MODEL_VISIBLE_DOCUMENT_ROLES <= reachable, sorted(
        role.value for role in MODEL_VISIBLE_DOCUMENT_ROLES - reachable
    )


def test_verdict_reader_reads_the_results_container_key(tmp_path: Path) -> None:
    """The sixth-successor purchase gate spells its rows under ``results``."""

    path = tmp_path / "byte-role-validation.json"
    _write_json(
        path,
        {
            "results": [
                {
                    "source_document_id": "doc-a",
                    "verdict": "match",
                    "role": "complaint",
                }
            ]
        },
    )

    index = index_verdicts((path,))

    assert index["doc-a"][0].verdict == "match"
    assert index["doc-a"][0].certified_role == "complaint"


def test_verdict_reader_certifies_the_expected_role_not_the_claimed_role(
    tmp_path: Path,
) -> None:
    """The bulk validator records the claim and the certification separately.

    ``manifest_role`` is what the corpus CLAIMED when the act ran;
    ``expected_role`` is what the validator CERTIFIED the bytes to be, and
    ``verdict: match`` is a statement about ``expected_role``.  Reading the
    claim as if it were the certification makes the cross-check compare the
    corpus against its own earlier belief, which certifies nothing.
    """

    path = tmp_path / "vb-byte-role-validation.json"
    _write_json(
        path,
        {
            "records": [
                {
                    "source_document_id": "doc-a",
                    "verdict": "match",
                    "manifest_role": "complaint",
                    "expected_role": "amended_complaint",
                    "validation_basis": "adjudicated_text",
                }
            ]
        },
    )

    record = index_verdicts((path,))["doc-a"][0]

    assert record.certified_role == "amended_complaint"
    assert record.claimed_role == "complaint"


def test_verdict_reader_never_certifies_from_a_claim_alone(tmp_path: Path) -> None:
    """A record carrying only the claim certifies nothing and must refuse."""

    path = tmp_path / "claim-only.json"
    _write_json(
        path,
        {
            "records": [
                {
                    "source_document_id": "doc-a",
                    "verdict": "match",
                    "manifest_role": "complaint",
                }
            ]
        },
    )

    record = index_verdicts((path,))["doc-a"][0]

    assert record.certified_role is None
    assert record.claimed_role == "complaint"


def test_freeze_trusts_the_certified_role_over_the_selection_claim(
    corpus: dict[str, Path],
) -> None:
    """A selection relabelled to match the certification must freeze clean.

    This is the shape of the 69066691 cure: the adjudicator certified the
    bytes as an amended complaint, so relabelling the selection to agree is
    the fix, and the freeze must then accept rather than flip the refusal to
    the other side.
    """

    rows = [
        json.loads(line)
        for line in corpus["selection"].read_text(encoding="utf-8").splitlines()
    ]
    for document in rows[0]["documents"]:
        if document["source_document_id"] == _complaint_id("cand-1"):
            document["document_role"] = "amended_complaint"
    _write_jsonl(corpus["selection"], rows)

    verdicts = [
        json.loads(line)
        for line in corpus["verdicts"].read_text(encoding="utf-8").splitlines()
    ]
    for verdict in verdicts:
        if verdict["source_document_id"] == _complaint_id("cand-1"):
            # The bulk-validator shape: stale claim beside the certification.
            verdict.pop("role")
            verdict["manifest_role"] = "complaint"
            verdict["expected_role"] = "amended_complaint"
            verdict["validation_basis"] = "adjudicated_text"
    _write_verdicts(corpus["verdicts"], verdicts)

    record, accepted = _freeze(corpus)

    assert accepted, record.get("blockers")


def test_freeze_refuses_when_the_selection_contradicts_the_certified_role(
    corpus: dict[str, Path],
) -> None:
    """The stale claim must never rescue a selection the bytes contradict."""

    verdicts = [
        json.loads(line)
        for line in corpus["verdicts"].read_text(encoding="utf-8").splitlines()
    ]
    for verdict in verdicts:
        if verdict["source_document_id"] == _complaint_id("cand-1"):
            verdict.pop("role")
            # The claim agrees with the selection; the certification does not.
            verdict["manifest_role"] = "complaint"
            verdict["expected_role"] = "amended_complaint"
            verdict["validation_basis"] = "adjudicated_text"
    _write_verdicts(corpus["verdicts"], verdicts)

    record, accepted = _freeze(corpus)

    assert not accepted
    assert any(
        "certifies 'amended_complaint'" in blocker for blocker in record["blockers"]
    ), record["blockers"]


def test_freeze_refuses_a_mismatch_verdict(corpus: dict[str, Path]) -> None:
    rows = [
        json.loads(line)
        for line in corpus["verdicts"].read_text(encoding="utf-8").splitlines()
    ]
    rows[0]["byte_role_verdict"] = "mismatch"
    _write_verdicts(corpus["verdicts"], rows)

    record, accepted = _freeze(corpus)

    assert not accepted
    assert any("refuses this document" in blocker for blocker in record["blockers"])


def test_freeze_accepts_an_adjudicated_unverifiable_verdict(
    corpus: dict[str, Path],
) -> None:
    rows = [
        json.loads(line)
        for line in corpus["verdicts"].read_text(encoding="utf-8").splitlines()
    ]
    rows[0]["byte_role_verdict"] = "unverifiable"
    rows[0]["validation_basis"] = "adjudicated_text"
    _write_verdicts(corpus["verdicts"], rows)

    _record, accepted = _freeze(corpus)

    assert accepted


def test_freeze_refuses_an_unverifiable_verdict_without_adjudication(
    corpus: dict[str, Path],
) -> None:
    rows = [
        json.loads(line)
        for line in corpus["verdicts"].read_text(encoding="utf-8").splitlines()
    ]
    rows[0]["byte_role_verdict"] = "unverifiable"
    rows[0]["validation_basis"] = "heuristic_title"
    _write_verdicts(corpus["verdicts"], rows)

    record, accepted = _freeze(corpus)

    assert not accepted
    assert any("match or adjudicated" in blocker for blocker in record["blockers"])


def test_freeze_refuses_a_case_without_prediction_units(
    corpus: dict[str, Path],
) -> None:
    rows = [
        json.loads(line)
        for line in corpus["units"].read_text(encoding="utf-8").splitlines()
    ]
    _write_jsonl(corpus["units"], rows[:1])

    record, accepted = _freeze(corpus)

    assert not accepted
    assert any(
        "no scorable prediction units" in blocker for blocker in record["blockers"]
    )


def test_freeze_refuses_a_case_whose_units_are_all_unscorable(
    corpus: dict[str, Path],
) -> None:
    rows = [
        json.loads(line)
        for line in corpus["units"].read_text(encoding="utf-8").splitlines()
    ]
    for unit in rows[0]["prediction_units"]:
        unit["should_score"] = False
    _write_jsonl(corpus["units"], rows)

    record, accepted = _freeze(corpus)

    assert not accepted
    assert any(
        "no scorable prediction units" in blocker for blocker in record["blockers"]
    )


def test_freeze_refuses_a_case_missing_its_required_roles(
    corpus: dict[str, Path],
) -> None:
    rows = [
        json.loads(line)
        for line in corpus["selection"].read_text(encoding="utf-8").splitlines()
    ]
    rows[0]["documents"] = [
        document
        for document in rows[0]["documents"]
        if document["document_role"] != "motion_to_dismiss_memorandum"
    ]
    _write_jsonl(corpus["selection"], rows)

    record, accepted = _freeze(corpus)

    assert not accepted
    assert any(
        "no model-visible target motion-to-dismiss paper" in blocker
        for blocker in record["blockers"]
    )


def test_freeze_refuses_a_decision_marked_model_visible(
    corpus: dict[str, Path],
) -> None:
    rows = [
        json.loads(line)
        for line in corpus["selection"].read_text(encoding="utf-8").splitlines()
    ]
    for document in rows[0]["documents"]:
        if document["document_role"] == "decision":
            document["model_visible"] = True
    _write_jsonl(corpus["selection"], rows)

    record, accepted = _freeze(corpus)

    assert not accepted
    assert any(
        "audit-only and may never be model-visible" in blocker
        for blocker in record["blockers"]
    )


def test_freeze_reports_every_blocker_in_one_run(corpus: dict[str, Path]) -> None:
    """One refusal enumerates the whole cure list, not the first problem."""

    (corpus["store"] / "markdown" / "cand-1" / "cand-1-mtd.md").unlink()
    (corpus["store"] / "markdown" / "cand-2" / "cand-2-complaint.md").unlink()
    _write_jsonl(corpus["units"], [])

    record, accepted = _freeze(corpus)

    assert not accepted
    assert record["blocker_count"] >= 4


def test_verdict_reader_refuses_an_unknown_verdict_spelling(
    tmp_path: Path,
) -> None:
    path = tmp_path / "verdicts.jsonl"
    _write_jsonl(
        path,
        [{"source_document_id": "doc-a", "byte_role_verdict": "probably_fine"}],
    )

    with pytest.raises(CorpusStoreError, match="unknown byte-role verdict"):
        index_verdicts((path,))


def test_verdict_reader_reads_the_tranche_role_verdict_spelling(
    tmp_path: Path,
) -> None:
    path = tmp_path / "role-verdicts.json"
    _write_json(
        path,
        {
            "verdicts": [
                {
                    "source_document_id": "doc-a",
                    "role_verdict": "match",
                    "role": "complaint",
                    "basis": "adjudicated_text",
                }
            ]
        },
    )

    index = index_verdicts((path,))

    assert index["doc-a"][0].verdict == "match"
    assert index["doc-a"][0].is_accepted


def test_verdict_reader_treats_an_explicit_null_verdict_as_absent(
    tmp_path: Path,
) -> None:
    """A recorded null is an absent verdict, not a new spelling to refuse."""

    path = tmp_path / "verdicts.jsonl"
    _write_jsonl(
        path,
        [{"source_document_id": "doc-a", "byte_role_verdict": None, "role": "reply"}],
    )

    assert index_verdicts((path,)) == {}


def test_verdict_reader_refuses_a_row_with_no_known_verdict_spelling(
    tmp_path: Path,
) -> None:
    path = tmp_path / "verdicts.jsonl"
    _write_jsonl(path, [{"source_document_id": "doc-a", "outcome": "match"}])

    with pytest.raises(CorpusStoreError, match="known verdict spellings"):
        index_verdicts((path,))


# --------------------------------------------------------------------------- #
# Signed loading
# --------------------------------------------------------------------------- #


def test_signed_manifest_load_refuses_tampered_bytes(
    corpus: dict[str, Path],
) -> None:
    record, _ = _freeze(corpus)
    payload = json.loads(corpus["manifest"].read_text(encoding="utf-8"))
    payload["cases"][0]["court"] = "D. Elsewhere"
    _write_json(corpus["manifest"], payload)

    with pytest.raises(CorpusManifestError, match="do not match the digest"):
        load_signed_manifest(
            corpus["manifest"],
            expected_digest=str(record["manifest_sha256"]),
        )


def test_signed_manifest_load_refuses_a_resigned_manifest(
    corpus: dict[str, Path],
) -> None:
    """Re-signing tampered bytes still fails: the operator's digest disagrees."""

    record, _ = _freeze(corpus)
    payload = json.loads(corpus["manifest"].read_text(encoding="utf-8"))
    payload["cases"][0]["court"] = "D. Elsewhere"
    payload["manifest_sha256"] = manifest_digest(payload)
    _write_json(corpus["manifest"], payload)

    with pytest.raises(CorpusManifestError, match="expected digest"):
        load_signed_manifest(
            corpus["manifest"],
            expected_digest=str(record["manifest_sha256"]),
        )


# --------------------------------------------------------------------------- #
# Manifest-mode forecast build
# --------------------------------------------------------------------------- #


def test_build_produces_packets_prompts_and_a_reproducible_run_record(
    corpus: dict[str, Path],
) -> None:
    frozen, _ = _freeze(corpus)
    digest = str(frozen["manifest_sha256"])

    result = _build(corpus, digest)

    assert result["status"] == "built"
    assert result["provider_calls_made"] == 0
    assert result["packet_count"] == 2 * len(FORECAST_ABLATIONS)
    assert result["model_ids"] == ["fixture-model-a", "fixture-model-b"]

    run_record = json.loads(Path(str(result["run_record"])).read_text("utf-8"))
    assert run_record["manifest_sha256"] == digest
    assert run_record["owner_signature_reference"]["bead_id"] == (
        "legalforecastbench-3ak.38"
    )
    assert digest in run_record["owner_signature_reference"]["approval_line"]
    assert run_record["docket_tool_enabled"] is USE_DOCKET_TOOL
    assert run_record["provider_calls_made"] == 0
    assert len(run_record["prompt_commitments"]) == 2 * len(FORECAST_ABLATIONS)
    assert [entry["model_id"] for entry in run_record["evaluation_models"]] == [
        "fixture-model-a",
        "fixture-model-b",
    ]


def test_build_emits_packet_objects_the_existing_runner_can_consume(
    corpus: dict[str, Path],
) -> None:
    frozen, _ = _freeze(corpus)
    result = _build(corpus, str(frozen["manifest_sha256"]))

    run_inputs = json.loads(Path(str(result["run_inputs_manifest"])).read_text("utf-8"))
    assert run_inputs["cycle_id"] == "cycle-1"
    for row in run_inputs["model_packets"]:
        assert row["packet_object_key"].startswith("model-packets/")
        assert len(row["packet_sha256"]) == 64
        assert row["packet_size_bytes"] > 0
        assert row["decision_date"] == "2026-06-01"
        packet_path = corpus["output"] / row["packet_object_key"]
        assert packet_path.is_file()
        assert row["packet_size_bytes"] == len(packet_path.read_bytes())


def test_recorded_prompt_hashes_match_the_runner_flags_the_record_names(
    corpus: dict[str, Path],
) -> None:
    """The committed prompt hash must be the one the named flags reproduce.

    ``eval run-case`` defaults the docket tool on, so a hash rendered with it
    off only describes the executed prompt when --no-docket-tool is passed.
    This asserts the record names that flag and that the flag is load-bearing:
    the tool-on rendering hashes differently.
    """

    frozen, _ = _freeze(corpus)
    result = _build(corpus, str(frozen["manifest_sha256"]))
    run_record = json.loads(Path(str(result["run_record"])).read_text("utf-8"))

    assert run_record["required_eval_run_case_flags"] == list(REQUIRED_RUN_CASE_FLAGS)
    assert "--no-docket-tool" in run_record["required_eval_run_case_flags"]

    run_inputs = json.loads(Path(str(result["run_inputs_manifest"])).read_text("utf-8"))
    row = run_inputs["model_packets"][0]
    packet = _packet_from_record(
        json.loads((corpus["output"] / row["packet_object_key"]).read_text("utf-8"))
    )
    committed = run_record["prompt_commitments"][
        f"{row['candidate_id']}:{row['ablation']}"
    ]
    assert committed == sha256_text(
        render_model_prompt(packet, use_docket_tool=USE_DOCKET_TOOL)
    )
    # The flag is load-bearing: the runner default renders a different prompt.
    assert committed != sha256_text(render_model_prompt(packet, use_docket_tool=True))


def test_run_inputs_rows_carry_the_prompt_commitment_the_runner_enforces(
    corpus: dict[str, Path],
) -> None:
    """The commitment must reach the manifest the runner reads, not just the record."""

    frozen, _ = _freeze(corpus)
    result = _build(corpus, str(frozen["manifest_sha256"]))

    run_record = json.loads(Path(str(result["run_record"])).read_text("utf-8"))
    run_inputs = json.loads(Path(str(result["run_inputs_manifest"])).read_text("utf-8"))
    for row in run_inputs["model_packets"]:
        committed = run_record["prompt_commitments"][
            f"{row['candidate_id']}:{row['ablation']}"
        ]
        assert row["prompt_sha256"] == committed
        # And the runner parses it off the record it actually reads.
        assert (
            _packet_object_from_record(row, manifest=run_inputs).prompt_sha256
            == committed
        )


def test_runner_refuses_a_prompt_that_differs_from_its_commitment(
    corpus: dict[str, Path],
) -> None:
    """Self-enforcement: a prompt rendered under other flags cannot execute.

    This is what retires the operator-memory problem. The committed hash is
    the tool-off rendering; the runner default renders with the tool on, and
    that prompt is refused rather than silently executed.
    """

    frozen, _ = _freeze(corpus)
    result = _build(corpus, str(frozen["manifest_sha256"]))
    run_inputs = json.loads(Path(str(result["run_inputs_manifest"])).read_text("utf-8"))
    row = run_inputs["model_packets"][0]
    packet = _packet_from_record(
        json.loads((corpus["output"] / row["packet_object_key"]).read_text("utf-8"))
    )
    packet_object = _packet_object_from_record(row, manifest=run_inputs)

    committed_samples = build_inspect_samples(
        (packet,), use_docket_tool=USE_DOCKET_TOOL
    )
    _require_committed_prompt(committed_samples, packet_object=packet_object)

    wrong_samples = build_inspect_samples((packet,), use_docket_tool=True)
    with pytest.raises(PacketManifestError, match="does not match the prompt_sha256"):
        _require_committed_prompt(wrong_samples, packet_object=packet_object)


def test_runner_prompt_enforcement_is_inert_without_a_commitment(
    corpus: dict[str, Path],
) -> None:
    """Manifests that carry no commitment keep the previous behaviour exactly."""

    frozen, _ = _freeze(corpus)
    result = _build(corpus, str(frozen["manifest_sha256"]))
    run_inputs = json.loads(Path(str(result["run_inputs_manifest"])).read_text("utf-8"))
    row = dict(run_inputs["model_packets"][0])
    row.pop("prompt_sha256")
    packet = _packet_from_record(
        json.loads((corpus["output"] / row["packet_object_key"]).read_text("utf-8"))
    )
    packet_object = _packet_object_from_record(row, manifest=run_inputs)

    assert packet_object.prompt_sha256 is None
    _require_committed_prompt(
        build_inspect_samples((packet,), use_docket_tool=True),
        packet_object=packet_object,
    )


def test_run_inputs_manifest_does_not_reuse_the_manifest_schema_id(
    corpus: dict[str, Path],
) -> None:
    """One schema id must not label two different byte shapes."""

    frozen, _ = _freeze(corpus)
    result = _build(corpus, str(frozen["manifest_sha256"]))

    run_inputs = json.loads(Path(str(result["run_inputs_manifest"])).read_text("utf-8"))
    assert "schema_version" not in run_inputs
    # The runner's own validator needs exactly these two.
    assert run_inputs["cycle_id"] and run_inputs["model_packets"]


def test_build_refuses_when_markdown_bytes_drift_after_the_freeze(
    corpus: dict[str, Path],
) -> None:
    frozen, _ = _freeze(corpus)
    markdown = corpus["store"] / "markdown" / "cand-1" / "cand-1-complaint.md"
    markdown.write_text("# Complaint\n\nSubstituted after signing.", encoding="utf-8")

    with pytest.raises(ManifestForecastError, match="differ from the digest"):
        _build(corpus, str(frozen["manifest_sha256"]))


def test_build_refuses_an_approval_line_that_does_not_quote_the_digest(
    corpus: dict[str, Path],
) -> None:
    frozen, _ = _freeze(corpus)
    digest = str(frozen["manifest_sha256"])

    with pytest.raises(ManifestForecastError, match="does not quote the manifest"):
        build_manifest_forecast_command(
            manifest=corpus["manifest"],
            expected_manifest_digest=digest,
            owner_signature_bead="legalforecastbench-3ak.38",
            owner_approval_line="Approved, go ahead.",
            model_registry=corpus["registry"],
            output_dir=corpus["output"],
            generated_at=_GENERATED_AT,
        )


def test_build_refuses_a_case_decided_before_the_release_anchor(
    corpus: dict[str, Path],
) -> None:
    rows = [
        json.loads(line)
        for line in corpus["selection"].read_text(encoding="utf-8").splitlines()
    ]
    rows[0]["decision_date"] = "2025-01-01"
    _write_jsonl(corpus["selection"], rows)
    frozen, accepted = _freeze(corpus)
    assert accepted

    with pytest.raises(ManifestForecastError, match="precedes the evaluation"):
        _build(corpus, str(frozen["manifest_sha256"]))


def test_build_refuses_prediction_units_that_changed_after_signing(
    corpus: dict[str, Path],
) -> None:
    frozen, _ = _freeze(corpus)
    rows = [
        json.loads(line)
        for line in corpus["units"].read_text(encoding="utf-8").splitlines()
    ]
    rows[0]["prediction_units"][0]["claim_name"] = "Substituted claim"
    _write_jsonl(corpus["units"], rows)

    with pytest.raises(ManifestForecastError, match="prediction unit bytes differ"):
        _build(corpus, str(frozen["manifest_sha256"]))


# --------------------------------------------------------------------------- #
# Blinding
# --------------------------------------------------------------------------- #


def test_no_decision_text_reaches_any_packet_or_prompt(
    corpus: dict[str, Path],
) -> None:
    """The headline blinding proof, over the real emitted artifacts."""

    frozen, _ = _freeze(corpus)
    result = _build(corpus, str(frozen["manifest_sha256"]))

    run_inputs = json.loads(Path(str(result["run_inputs_manifest"])).read_text("utf-8"))
    assert run_inputs["model_packets"]
    for row in run_inputs["model_packets"]:
        packet_bytes = (corpus["output"] / row["packet_object_key"]).read_text("utf-8")
        # No decision text anywhere in the packet bytes, in any field.
        assert _DECISION_TEXT not in packet_bytes
        packet = json.loads(packet_bytes)
        mounted = {document["source_document_id"] for document in packet["documents"]}
        roles = {document["document_role"] for document in packet["documents"]}
        assert not roles & {"decision", "order"}
        assert not mounted & {_decision_id("cand-1"), _decision_id("cand-2")}
        # The decision is recorded as excluded, which is audit provenance and
        # carries no outcome bytes.
        assert _decision_id(row["candidate_id"]) in packet["excluded_document_ids"]
        # And no document the packet does mount hashes to the decision text.
        for document in packet["documents"]:
            assert document["text"] != _DECISION_TEXT


def test_the_manifest_refuses_to_describe_a_model_visible_decision() -> None:
    """First blinding layer: the manifest schema itself will not express it."""

    with pytest.raises(CorpusManifestError, match="may never be model-visible"):
        ManifestDocument(
            source_document_id="doc-decision",
            document_role=DocumentRole.DECISION,
            model_visible=True,
            pdf_path="/synthetic/doc-decision.pdf",
            pdf_sha256="0" * 64,
            source_url="https://example.invalid/doc-decision.pdf",
            markdown_path="/synthetic/doc-decision.md",
            markdown_sha256="1" * 64,
        )


def test_the_packet_builder_still_excludes_a_forcibly_mounted_decision() -> None:
    """Second blinding layer, proved independently of the manifest schema.

    Even if the manifest guard were bypassed entirely, the packet builder this
    entry reuses refuses to mount an outcome role, so the decision text cannot
    reach the packet or the rendered prompt.
    """

    generated_at = _GENERATED_AT
    documents = (
        SourceDocumentProvenance(
            source_provider="synthetic",
            source_case_id="cand-1",
            source_document_id="doc-complaint",
            court="D. Example",
            docket_number="1:26-cv-00001",
            document_role=DocumentRole.COMPLAINT,
            retrieved_at=generated_at,
            source_url_or_reference="https://example.invalid/doc-complaint.pdf",
            sha256="0" * 64,
            is_predecision_material=True,
            is_mounted_for_model=True,
            docket_entry_number=1,
        ),
        SourceDocumentProvenance(
            source_provider="synthetic",
            source_case_id="cand-1",
            source_document_id="doc-mtd",
            court="D. Example",
            docket_number="1:26-cv-00001",
            document_role=DocumentRole.MTD_MEMORANDUM,
            retrieved_at=generated_at,
            source_url_or_reference="https://example.invalid/doc-mtd.pdf",
            sha256="1" * 64,
            is_predecision_material=True,
            is_mounted_for_model=True,
            docket_entry_number=2,
        ),
        # Forcibly mounted, and deliberately not flagged as outcome-bearing so
        # the provenance guard cannot be what stops it.
        SourceDocumentProvenance(
            source_provider="synthetic",
            source_case_id="cand-1",
            source_document_id="doc-decision",
            court="D. Example",
            docket_number="1:26-cv-00001",
            document_role=DocumentRole.DECISION,
            retrieved_at=generated_at,
            source_url_or_reference="https://example.invalid/doc-decision.pdf",
            sha256="2" * 64,
            is_predecision_material=True,
            is_mounted_for_model=True,
            docket_entry_number=9,
        ),
    )
    case_packet = CasePacketSchema(
        candidate_id="cand-1",
        case_id="cand-1",
        court="D. Example",
        docket_number="1:26-cv-00001",
        generated_at=generated_at,
        documents=documents,
    )
    units = _unit_row("cand-1")["prediction_units"]
    from legalforecast.unitization.schemas import prediction_unit_from_record

    packet = build_model_packet(
        case_packet=case_packet,
        prediction_units=tuple(prediction_unit_from_record(u) for u in units),
        texts=_texts_for_blinding_probe(),
        ablation=PacketAblation.FULL_PACKET,
    )

    mounted = {document.source_document_id for document in packet.documents}
    assert "doc-decision" not in mounted
    assert "doc-decision" in packet.excluded_document_ids
    prompt = render_model_prompt(packet, use_docket_tool=False)
    assert _DECISION_TEXT not in prompt


def _texts_for_blinding_probe() -> tuple[Any, ...]:
    from legalforecast.evals.packet_builder import PacketText

    return (
        PacketText(source_document_id="doc-complaint", text="Complaint text."),
        PacketText(source_document_id="doc-mtd", text="Motion text."),
        PacketText(source_document_id="doc-decision", text=_DECISION_TEXT),
    )
