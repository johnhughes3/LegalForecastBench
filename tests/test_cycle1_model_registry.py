from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any, cast

from legalforecast.cli import main
from legalforecast.evals.model_registry import (
    earliest_eligible_decision_date,
    load_model_registry,
    require_official_registry_entries,
)
from legalforecast.reporting.result_class import (
    ResultClass,
    classify_registry_entry,
    require_lane_result_classes,
)
from legalforecast.unitization.review import apply_unitization_reviews

ROOT = Path(__file__).resolve().parents[1]
CYCLE_1_REGISTRY = ROOT / "model_registries" / "cycle-1-2026-06-30.json"
SUCCESSOR_REGISTRY = (
    ROOT
    / "model_registries"
    / "cycle-1-2026-06-30-claude-opus-4-8-successor-2026-08-21.json"
)
FABLE_SUCCESSOR_REGISTRY = (
    ROOT
    / "model_registries"
    / "cycle-1-2026-06-30-claude-fable-5-successor-2026-08-31.json"
)
CYCLE_1_CORPUS_ANCHOR = date(2026, 6, 30)
JsonRecord = dict[str, Any]
GENERATED_AT = "2026-07-11T12:00:00Z"


def test_cycle_1_registry_freezes_late_june_model_matrix() -> None:
    registry = load_model_registry(CYCLE_1_REGISTRY)

    assert {entry.registry_key for entry in registry.entries} == {
        "anthropic:claude-sonnet-5",
        "openai:gpt-5.6-luna",
        "openai:gpt-5.6-sol",
        "openai:gpt-5.6-terra",
    }
    assert {
        entry.registry_key: entry.model_version_or_snapshot
        for entry in registry.entries
    } == {
        "anthropic:claude-sonnet-5": "claude-sonnet-5",
        "openai:gpt-5.6-luna": "gpt-5.6-luna",
        "openai:gpt-5.6-sol": "gpt-5.6-sol",
        "openai:gpt-5.6-terra": "gpt-5.6-terra",
    }


def test_cycle_1_registry_is_official_and_anchors_on_june_30() -> None:
    registry = load_model_registry(CYCLE_1_REGISTRY)

    entries = require_official_registry_entries(registry.entries)

    assert earliest_eligible_decision_date(entries) == date(2026, 6, 30)
    assert all(entry.release_timestamp is not None for entry in entries)
    assert all(entry.release_timestamp_source for entry in entries)
    assert all(entry.pricing_source for entry in entries)
    assert all(entry.input_token_price > 0 for entry in entries)
    assert all(entry.output_token_price > 0 for entry in entries)


def test_opus_4_8_successor_replaces_sonnet_without_expanding_matrix() -> None:
    frozen = load_model_registry(CYCLE_1_REGISTRY)
    successor = load_model_registry(SUCCESSOR_REGISTRY)

    assert len(successor.entries) == 4
    assert {entry.registry_key for entry in successor.entries} == {
        "anthropic:claude-opus-4-8",
        "openai:gpt-5.6-luna",
        "openai:gpt-5.6-sol",
        "openai:gpt-5.6-terra",
    }
    assert "anthropic:claude-sonnet-5" not in {
        entry.registry_key for entry in successor.entries
    }
    for model_id in ("gpt-5.6-luna", "gpt-5.6-sol", "gpt-5.6-terra"):
        successor_record = successor.get("openai", model_id).to_record()
        frozen_record = frozen.get("openai", model_id).to_record()
        for field in (
            "max_output_tokens",
            "reasoning_effort",
            "temperature",
            "top_p",
        ):
            successor_record.pop(field, None)
            frozen_record.pop(field, None)
        assert successor_record == frozen_record


def test_opus_4_8_successor_uses_provider_output_limits_and_sampling_defaults() -> None:
    successor = load_model_registry(SUCCESSOR_REGISTRY)

    assert {
        entry.registry_key: entry.max_output_tokens for entry in successor.entries
    } == {
        "anthropic:claude-opus-4-8": 128_000,
        "openai:gpt-5.6-luna": 128_000,
        "openai:gpt-5.6-sol": 128_000,
        "openai:gpt-5.6-terra": 128_000,
    }
    assert all(entry.temperature is None for entry in successor.entries)
    assert all(entry.top_p is None for entry in successor.entries)
    assert {
        entry.registry_key: (
            entry.reasoning_effort.value if entry.reasoning_effort is not None else None
        )
        for entry in successor.entries
    } == {
        "anthropic:claude-opus-4-8": None,
        "openai:gpt-5.6-luna": "high",
        "openai:gpt-5.6-sol": "high",
        "openai:gpt-5.6-terra": "high",
    }


def test_opus_4_8_successor_preserves_corpus_dates_and_release_anchor() -> None:
    successor = load_model_registry(SUCCESSOR_REGISTRY)
    entries = require_official_registry_entries(successor.entries)
    cohort_policy = json.loads(
        (ROOT / "docs/cohort-policy-cycle-1-target-100-2026-07-25.json").read_text(
            encoding="utf-8"
        )
    )["policy"]
    opus = successor.get("anthropic", "claude-opus-4-8")

    assert opus.release_timestamp is not None
    assert opus.release_timestamp.date() == date(2026, 5, 28)
    assert earliest_eligible_decision_date(entries) == date(2026, 6, 26)
    assert cohort_policy["eligibility_anchor"] == "2026-06-30"
    assert cohort_policy["stop_rule"]["search_window_end"] == "2026-07-23"
    assert date.fromisoformat(cohort_policy["eligibility_anchor"]) >= (
        earliest_eligible_decision_date(entries)
    )


def test_fable_5_successor_adds_a_fifth_official_model_without_editing_the_four() -> (
    None
):
    """The Fable 5 successor inherits its predecessor's four entries verbatim.

    Minting a successor rather than editing the frozen registry is how Claude
    Opus 4.8 entered the set, and the byte-for-byte inheritance is what makes
    the addition auditable: nothing about the four models already frozen can
    drift under cover of adding a fifth.
    """

    predecessor = json.loads(SUCCESSOR_REGISTRY.read_text(encoding="utf-8"))
    successor = json.loads(FABLE_SUCCESSOR_REGISTRY.read_text(encoding="utf-8"))

    assert len(successor) == 5
    assert successor[:4] == predecessor

    registry = load_model_registry(FABLE_SUCCESSOR_REGISTRY)
    assert {entry.registry_key for entry in registry.entries} == {
        "anthropic:claude-fable-5",
        "anthropic:claude-opus-4-8",
        "openai:gpt-5.6-luna",
        "openai:gpt-5.6-sol",
        "openai:gpt-5.6-terra",
    }


def test_fable_5_successor_is_official_and_leaves_the_release_anchor_alone() -> None:
    """Fable 5 is pre-anchor, so it joins the official lane and moves nothing.

    Its 2026-06-09 first availability predates both the 2026-06-26 release
    anchor of the frozen four and the 2026-06-30 corpus anchor, so adding it
    neither reclassifies the set nor shifts the earliest eligible decision
    date. A post-anchor model would fail ``require_lane_result_classes`` here.
    """

    registry = load_model_registry(FABLE_SUCCESSOR_REGISTRY)
    entries = require_official_registry_entries(registry.entries)
    fable = registry.get("anthropic", "claude-fable-5")

    assert fable.release_timestamp is not None
    assert fable.release_timestamp.date() == date(2026, 6, 9)
    assert fable.release_timestamp.date() < CYCLE_1_CORPUS_ANCHOR
    assert earliest_eligible_decision_date(entries) == date(2026, 6, 26)

    for entry in registry.entries:
        assert (
            classify_registry_entry(entry, corpus_anchor=CYCLE_1_CORPUS_ANCHOR)
            is ResultClass.OFFICIAL
        )
    require_lane_result_classes(
        list(registry.entries),
        corpus_anchor=CYCLE_1_CORPUS_ANCHOR,
        supplementary=False,
    )


def test_fable_5_entry_pins_its_identity_price_and_execution_parity() -> None:
    """Freeze the researched values so a later edit cannot drift them quietly.

    Anthropic entries carry no ``reasoning_effort``: Fable 5's thinking is
    always on at the provider's default effort of ``high``, and the solver
    publishes that as an adaptive-thinking reasoning policy instead.
    """

    registry = load_model_registry(FABLE_SUCCESSOR_REGISTRY)
    fable = registry.get("anthropic", "claude-fable-5")

    assert fable.model_id == "claude-fable-5"
    assert fable.model_version_or_snapshot == "claude-fable-5"
    assert fable.context_limit == 1_000_000
    assert fable.input_token_price == 10.0
    assert fable.output_token_price == 50.0
    assert fable.network_disabled is True
    assert fable.search_disabled is True
    assert fable.release_timestamp_source
    assert fable.pricing_source

    # Execution parity with the four already-frozen official models.
    assert all(entry.max_output_tokens == 128_000 for entry in registry.entries)
    assert all(entry.temperature is None for entry in registry.entries)
    assert all(entry.top_p is None for entry in registry.entries)
    assert all(
        entry.tool_policy.value == "controlled_docket_tool_only"
        for entry in registry.entries
    )
    assert fable.reasoning_effort is None


def test_fable_5_carries_the_undisclosed_cutoff_asterisk() -> None:
    """Anthropic publishes a month, not a date, so the exact field is unknown.

    That is the same disclosure posture as Claude Opus 4.8, and it is what
    earns Fable 5 the contamination asterisk rather than excluding it.
    """

    registry = load_model_registry(FABLE_SUCCESSOR_REGISTRY)
    fable = registry.get("anthropic", "claude-fable-5")

    assert fable.provider_training_cutoff is None
    assert fable.provider_training_cutoff_status.value == "unknown"
    caveats = " ".join(fable.known_cutoff_publicity_caveats)
    assert "January 2026" in caveats
    assert "pinned snapshot" in caveats


def test_cycle_1_registry_records_provider_limits_and_current_prices() -> None:
    registry = load_model_registry(CYCLE_1_REGISTRY)

    assert {
        entry.registry_key: (
            entry.context_limit,
            entry.max_output_tokens,
            entry.input_token_price,
            entry.output_token_price,
        )
        for entry in registry.entries
    } == {
        "anthropic:claude-sonnet-5": (1_000_000, 16_000, 2.0, 10.0),
        "openai:gpt-5.6-luna": (1_050_000, 16_000, 1.0, 6.0),
        "openai:gpt-5.6-sol": (1_050_000, 16_000, 5.0, 30.0),
        "openai:gpt-5.6-terra": (1_050_000, 16_000, 2.5, 15.0),
    }

    for entry in registry.entries:
        assert entry.network_disabled is True
        assert entry.search_disabled is True
        assert entry.temperature == 0
        assert entry.top_p == 1


def test_cycle_1_registry_structures_gpt_long_context_surcharge_terms() -> None:
    registry = load_model_registry(CYCLE_1_REGISTRY)

    assert {
        entry.registry_key: (
            entry.long_context_surcharge.threshold_input_tokens,
            entry.long_context_surcharge.input_price_multiplier,
            entry.long_context_surcharge.output_price_multiplier,
        )
        for entry in registry.entries
        if entry.long_context_surcharge is not None
    } == {
        "openai:gpt-5.6-luna": (272_000, 2.0, 1.5),
        "openai:gpt-5.6-sol": (272_000, 2.0, 1.5),
        "openai:gpt-5.6-terra": (272_000, 2.0, 1.5),
    }
    assert registry.get("anthropic", "claude-sonnet-5").long_context_surcharge is None


def test_cycle_1_registry_digest_matches_checked_in_acquisition_commitments() -> None:
    registry_sha256 = hashlib.sha256(CYCLE_1_REGISTRY.read_bytes()).hexdigest()

    for relative_path in (
        "manifests/cycle-1-target-100.acquisition-cycle.template.json",
        "manifests/cycle-1-target-100.quarantine-successor.template.json",
        "manifests/cycle-1-target-100.replacement-corpus.template.json",
        "docs/cycle-1-target-100-direct-prerequisites.md",
    ):
        assert registry_sha256 in (ROOT / relative_path).read_text(encoding="utf-8")


def test_plan_packet_inputs_accepts_cycle_1_registry_and_anchor(
    tmp_path: Path,
    authenticated_downstream_fixture: Any,
) -> None:
    output_root = tmp_path / "acquisition"
    document_root = output_root / "documents" / "free"
    document_root.mkdir(parents=True)
    raw_html_dir = tmp_path / "raw-html"
    raw_html_dir.mkdir()
    raw_html_path = raw_html_dir / "cand-1.html"
    raw_html_path.write_text(
        _post_anchor_docket_html(),
        encoding="utf-8",
    )
    raw_html = raw_html_path.read_bytes()
    raw_artifacts_path = tmp_path / "raw-artifacts.jsonl"
    _write_jsonl(
        raw_artifacts_path,
        [
            {
                "candidate_id": "cand-1",
                "path": str(raw_html_path),
                "byte_count": len(raw_html),
                "sha256": hashlib.sha256(raw_html).hexdigest(),
            }
        ],
    )
    selection_path = tmp_path / "selection.jsonl"
    downloads_path = tmp_path / "downloads.jsonl"
    clearance_path = tmp_path / "clearance.jsonl"
    parser_path = tmp_path / "parser.jsonl"
    units_path = tmp_path / "units.jsonl"
    markdown_root = output_root / "markdown" / "cand-1"
    markdown_root.mkdir(parents=True)
    for document_id, markdown in {
        "complaint": "Complaint markdown",
        "mtd-memo": "MTD memorandum markdown",
        "decision": "Decision markdown",
    }.items():
        (markdown_root / f"{document_id}.md").write_text(
            markdown,
            encoding="utf-8",
        )

    _write_jsonl(selection_path, [_selection_record()])
    _write_jsonl(
        downloads_path,
        [
            _download_record("complaint", "complaint", 1),
            _download_record("mtd-memo", "motion_to_dismiss_memorandum", 34),
            _download_record("decision", "decision", 50),
        ],
    )
    _write_jsonl(
        parser_path,
        [
            _parser_record("complaint", "Complaint markdown"),
            _parser_record("mtd-memo", "MTD memorandum markdown"),
            _parser_record("decision", "Decision markdown"),
        ],
    )
    _write_clearance(downloads_path, clearance_path)
    materialization_card = authenticated_downstream_fixture.materialize(
        manifest=downloads_path,
        clearance=clearance_path,
        document_root=document_root,
        selection=selection_path,
        name="cycle-1-registry",
    )
    _write_jsonl(
        units_path,
        list(
            apply_unitization_reviews(
                prediction_unit_records=[
                    {
                        "candidate_id": "cand-1",
                        "case_id": "case-cand-1",
                        "prediction_units": [
                            {
                                "unit_id": "count-i-issuer",
                                "count": "I",
                                "claim_name": "Section 10(b)",
                                "defendant_group": "Issuer",
                                "challenged_by_motion": True,
                                "challenge_scope": "entire_claim",
                                "unit_confidence": 0.95,
                                "source_citations": [
                                    {"document_id": "complaint", "page": 1}
                                ],
                            }
                        ],
                    }
                ],
                review_records=(),
                adjudication_records=(),
            )
        ),
    )

    assert (
        main(
            [
                "acquisition",
                "plan-packet-inputs",
                "--selection",
                str(selection_path),
                "--download-manifest",
                str(downloads_path),
                "--parser-manifest",
                str(parser_path),
                "--disclosure-clearance",
                str(clearance_path),
                "--materialization-run-card",
                str(materialization_card),
                "--document-root",
                str(document_root),
                "--prediction-units",
                str(units_path),
                "--model-registry",
                str(CYCLE_1_REGISTRY),
                "--raw-html-dir",
                str(raw_html_dir),
                "--raw-artifacts-manifest",
                str(raw_artifacts_path),
                "--output-root",
                str(output_root),
                "--generated-at",
                GENERATED_AT,
                "--search-window",
                "2026-06-30..2026-07-11",
                "--execute",
            ]
        )
        == 0
    )

    packet_input = _read_jsonl(output_root / "packet-build-input.jsonl")[0]
    assert packet_input["decision_date"] == "2026-07-01"
    assert packet_input["metadata"]["decision_filed_on_or_after"] == "2026-06-30"


def _selection_record() -> JsonRecord:
    return {
        "candidate_id": "cand-1",
        "case_id": "case-1",
        "case_name": "Example v. Defendant",
        "court": "S.D.N.Y.",
        "docket_number": "1:26-cv-1",
        "decision_date": "2026-07-01",
        "source_url": "https://www.courtlistener.com/docket/cand-1/example/",
        "selected": True,
        "exclusion_reasons": [],
        "target_motion_entry_numbers": [34],
        "decision_entry_numbers": [50],
        "documents": [
            _selection_document("complaint", "complaint", 1, model_visible=True),
            _selection_document(
                "mtd-memo",
                "motion_to_dismiss_memorandum",
                34,
                model_visible=True,
            ),
            _selection_document("decision", "decision", 50, model_visible=False),
        ],
    }


def _selection_document(
    source_document_id: str,
    document_role: str,
    docket_entry_number: int,
    *,
    model_visible: bool,
) -> JsonRecord:
    return {
        "candidate_id": "cand-1",
        "source_document_id": source_document_id,
        "docket_entry_number": docket_entry_number,
        "document_role": document_role,
        "source_url": f"https://storage.courtlistener.com/{source_document_id}.pdf",
        "description": source_document_id,
        "model_visible": model_visible,
        "contains_target_outcome": not model_visible,
    }


def _download_record(
    source_document_id: str,
    document_role: str,
    docket_entry_number: int,
) -> JsonRecord:
    return {
        "candidate_id": "cand-1",
        "source_provider": "courtlistener",
        "source_document_id": source_document_id,
        "docket_entry_number": docket_entry_number,
        "document_role": document_role,
        "source_url": f"https://storage.courtlistener.com/{source_document_id}.pdf",
        "local_path": f"cand-1/courtlistener/{source_document_id}.pdf",
        "sha256": hashlib.sha256(source_document_id.encode()).hexdigest(),
        "byte_count": 10,
        "free_or_purchased": "free",
        "retry_count": 0,
        "rate_limited": False,
        "reused_existing": False,
    }


def _parser_record(source_document_id: str, markdown: str) -> JsonRecord:
    markdown_path = f"cand-1/{source_document_id}.md"
    return {
        "candidate_id": "cand-1",
        "source_document_id": source_document_id,
        "status": "succeeded",
        "input_path": f"/tmp/{source_document_id}.pdf",
        "markdown_path": markdown_path,
        "metadata_path": f"{markdown_path}.metadata.json",
        "parser_config": {"engine": "fixture"},
        "quality_flags": [],
        "source_sha256": hashlib.sha256(source_document_id.encode()).hexdigest(),
        "source_byte_count": 10,
        "extracted_text": {
            "source_document_id": source_document_id,
            "extracted_at": GENERATED_AT,
            "extraction_method": "fixture_markdown",
            "text_sha256": hashlib.sha256(markdown.encode()).hexdigest(),
            "quality_flags": [],
        },
    }


def _write_clearance(manifest_path: Path, output_path: Path) -> None:
    _write_jsonl(
        output_path,
        [
            {
                "schema_version": "legalforecast.disclosure_clearance.v1",
                "candidate_id": row["candidate_id"],
                "source_document_id": row["source_document_id"],
                "sha256": row["sha256"],
                "byte_count": row["byte_count"],
                "status": "cleared",
                "restriction_status": "public",
                "restriction_evidence": ["fixture-public-docket"],
                "reviewer_id": "reviewer:test",
                "controlled_store_provenance": "private-store://fixture/reviews",
                "reviewed_at": "2026-07-12T18:00:00Z",
            }
            for row in _read_jsonl(manifest_path)
        ],
    )


def _post_anchor_docket_html() -> str:
    return """
    <html>
      <body>
        <div id="docket-entry-table">
          <div class="row odd" id="entry-1">
            <div class="col-xs-1"><p>1</p></div>
            <div class="col-xs-3"><p>January 1, 2026</p></div>
            <div class="col-xs-8"><p>COMPLAINT filed by Plaintiff.</p></div>
          </div>
          <div class="row even" id="entry-34">
            <div class="col-xs-1"><p>34</p></div>
            <div class="col-xs-3"><p>February 1, 2026</p></div>
            <div class="col-xs-8"><p>MOTION to Dismiss.</p></div>
          </div>
          <div class="row odd" id="entry-50">
            <div class="col-xs-1"><p>50</p></div>
            <div class="col-xs-3"><p>July 1, 2026</p></div>
            <div class="col-xs-8"><p>ORDER granting 34 Motion to Dismiss.</p></div>
          </div>
        </div>
      </body>
    </html>
    """


def _write_jsonl(path: Path, records: list[JsonRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(f"{json.dumps(record, sort_keys=True)}\n" for record in records),
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[JsonRecord]:
    return [
        cast(JsonRecord, json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
