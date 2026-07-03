from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import legalforecast.labeling.llm_pipeline as llm_pipeline
from legalforecast.cli import main
from legalforecast.evals.inspect_task import SolverResponse
from legalforecast.unitization import ChallengeScope, PredictionUnit, SourceCitation
from pytest import MonkeyPatch

JsonRecord = dict[str, Any]


def test_acquisition_llm_unitize_and_label_validate_registry_outputs(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    output_root = tmp_path / "acquisition"
    markdown_root = output_root / "markdown"
    _write_markdown(markdown_root / "cand-1" / "complaint.md", "Count I: 10(b).")
    _write_markdown(
        markdown_root / "cand-1" / "mtd.md",
        "Defendants move to dismiss Count I under Rule 12(b)(6).",
    )
    _write_markdown(
        markdown_root / "cand-1" / "decision.md",
        "The motion to dismiss Count I is granted without leave to amend.",
    )
    selection_path = tmp_path / "selection.jsonl"
    parser_path = tmp_path / "parser.jsonl"
    registry_path = tmp_path / "registry.json"
    _write_jsonl(selection_path, [_selection_record()])
    _write_jsonl(
        parser_path,
        [
            _parser_record("complaint", "complaint.md"),
            _parser_record("mtd", "mtd.md"),
            _parser_record("decision", "decision.md"),
        ],
    )
    _write_json(registry_path, [_registry_record()])

    monkeypatch.setattr(llm_pipeline, "complete_live_prompt", _fake_completion)

    assert (
        main(
            [
                "acquisition",
                "llm-unitize",
                "--selection",
                str(selection_path),
                "--parser-manifest",
                str(parser_path),
                "--output-root",
                str(output_root),
                "--model-registry",
                str(registry_path),
                "--model-key",
                "openai:gpt-test",
                "--execute",
            ]
        )
        == 0
    )

    units = _read_jsonl(output_root / "prediction-units.jsonl")
    assert units[0]["candidate_id"] == "cand-1"
    assert units[0]["prediction_units"][0]["unit_id"] == "unit-1"
    unit_audit = _read_jsonl(output_root / "llm-unitization-audit.jsonl")[0]
    assert unit_audit["model_key"] == "openai:gpt-test"
    assert unit_audit["human_verified"] is False
    assert unit_audit["estimated_cost"] > 0

    assert (
        main(
            [
                "acquisition",
                "llm-label",
                "--selection",
                str(selection_path),
                "--parser-manifest",
                str(parser_path),
                "--prediction-units",
                str(output_root / "prediction-units.jsonl"),
                "--output-root",
                str(output_root),
                "--model-registry",
                str(registry_path),
                "--model-key",
                "openai:gpt-test",
                "--execute",
            ]
        )
        == 0
    )

    labels = _read_jsonl(output_root / "labels.jsonl")
    assert labels[0]["unit_id"] == "unit-1"
    assert labels[0]["fully_dismissed"] is True
    label_audit = _read_jsonl(output_root / "llm-label-audit.jsonl")[0]
    assert label_audit["consensus_policy"] == "unanimous"
    assert label_audit["human_verified"] is False
    assert label_audit["model_outputs"][0]["model_key"] == "openai:gpt-test"


def test_acquisition_llm_unitize_accepts_singleton_string_list_fields(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    output_root = tmp_path / "acquisition"
    markdown_root = output_root / "markdown"
    _write_markdown(markdown_root / "cand-1" / "complaint.md", "Count I: 10(b).")
    _write_markdown(
        markdown_root / "cand-1" / "mtd.md",
        "Defendants move to dismiss Count I under Rule 12(b)(6).",
    )
    selection_path = tmp_path / "selection.jsonl"
    parser_path = tmp_path / "parser.jsonl"
    registry_path = tmp_path / "registry.json"
    _write_jsonl(selection_path, [_selection_record()])
    _write_jsonl(
        parser_path,
        [
            _parser_record("complaint", "complaint.md"),
            _parser_record("mtd", "mtd.md"),
            _parser_record("decision", "decision.md"),
        ],
    )
    _write_json(registry_path, [_registry_record()])

    def fake_completion(*args: Any, **kwargs: Any) -> SolverResponse:
        return SolverResponse(
            raw_output=json.dumps(
                {
                    "unit_seeds": [
                        {
                            "unit_id": "unit-1",
                            "count": "Count I",
                            "claim_name": "Section 10(b)",
                            "defendant_names": "Issuer",
                            "source_document_ids": "mtd",
                            "challenged_by_motion": True,
                            "challenge_scope": "entire_claim",
                            "unit_confidence": 0.92,
                            "grouping": "individual",
                            "citation_excerpt": "dismiss Count I",
                        }
                    ]
                }
            ),
            input_tokens=100,
            output_tokens=50,
            estimated_cost=0.01,
            metadata={"provider": "openai", "model_id": "gpt-test"},
        )

    monkeypatch.setattr(llm_pipeline, "complete_live_prompt", fake_completion)

    assert (
        main(
            [
                "acquisition",
                "llm-unitize",
                "--selection",
                str(selection_path),
                "--parser-manifest",
                str(parser_path),
                "--output-root",
                str(output_root),
                "--model-registry",
                str(registry_path),
                "--model-key",
                "openai:gpt-test",
                "--execute",
            ]
        )
        == 0
    )

    unit = _read_jsonl(output_root / "prediction-units.jsonl")[0]["prediction_units"][0]
    assert unit["source_citations"][0]["document_id"] == "mtd"
    assert unit["defendant_group"] == "Issuer"


def test_acquisition_llm_unitize_accepts_top_level_seed_array(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    output_root = tmp_path / "acquisition"
    markdown_root = output_root / "markdown"
    _write_markdown(markdown_root / "cand-1" / "complaint.md", "Count I: 10(b).")
    _write_markdown(
        markdown_root / "cand-1" / "mtd.md",
        "Defendants move to dismiss Count I under Rule 12(b)(6).",
    )
    selection_path = tmp_path / "selection.jsonl"
    parser_path = tmp_path / "parser.jsonl"
    registry_path = tmp_path / "registry.json"
    _write_jsonl(selection_path, [_selection_record()])
    _write_jsonl(
        parser_path,
        [
            _parser_record("complaint", "complaint.md"),
            _parser_record("mtd", "mtd.md"),
        ],
    )
    _write_json(registry_path, [_registry_record()])

    def fake_completion(*args: Any, **kwargs: Any) -> SolverResponse:
        return SolverResponse(
            raw_output=json.dumps(
                [
                    {
                        "unit_id": "unit-1",
                        "count": "Count I",
                        "claim_name": "Section 10(b)",
                        "defendant_names": ["Issuer"],
                        "source_document_ids": ["mtd"],
                        "challenged_by_motion": True,
                        "challenge_scope": "entire_claim",
                        "unit_confidence": 0.92,
                        "grouping": "individual",
                        "citation_excerpt": "dismiss Count I",
                    }
                ]
            ),
            input_tokens=100,
            output_tokens=50,
            estimated_cost=0.01,
            metadata={"provider": "openai", "model_id": "gpt-test"},
        )

    monkeypatch.setattr(llm_pipeline, "complete_live_prompt", fake_completion)

    assert (
        main(
            [
                "acquisition",
                "llm-unitize",
                "--selection",
                str(selection_path),
                "--parser-manifest",
                str(parser_path),
                "--output-root",
                str(output_root),
                "--model-registry",
                str(registry_path),
                "--model-key",
                "openai:gpt-test",
                "--execute",
            ]
        )
        == 0
    )

    unit = _read_jsonl(output_root / "prediction-units.jsonl")[0]["prediction_units"][0]
    assert unit["unit_id"] == "unit-1"


def test_acquisition_llm_unitize_rejects_missing_required_unit_fields(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    output_root = tmp_path / "acquisition"
    markdown_root = output_root / "markdown"
    _write_markdown(markdown_root / "cand-1" / "complaint.md", "Count I: 10(b).")
    _write_markdown(
        markdown_root / "cand-1" / "mtd.md",
        "Defendants move to dismiss Count I under Rule 12(b)(6).",
    )
    selection_path = tmp_path / "selection.jsonl"
    parser_path = tmp_path / "parser.jsonl"
    registry_path = tmp_path / "registry.json"
    _write_jsonl(selection_path, [_selection_record()])
    _write_jsonl(
        parser_path,
        [
            _parser_record("complaint", "complaint.md"),
            _parser_record("mtd", "mtd.md"),
        ],
    )
    _write_json(registry_path, [_registry_record()])

    def incomplete_completion(*args: Any, **kwargs: Any) -> SolverResponse:
        return SolverResponse(
            raw_output=json.dumps(
                {
                    "unit_seeds": [
                        {
                            "unit_id": "unit-1",
                            "count": "Count I",
                            "claim_name": "Section 10(b)",
                            "defendant_names": ["Issuer"],
                            "source_document_ids": ["mtd"],
                            "unit_confidence": 0.92,
                            "grouping": "individual",
                            "citation_excerpt": "dismiss Count I",
                        }
                    ]
                }
            ),
            input_tokens=100,
            output_tokens=50,
            estimated_cost=0.01,
            metadata={"provider": "openai", "model_id": "gpt-test"},
        )

    monkeypatch.setattr(llm_pipeline, "complete_live_prompt", incomplete_completion)

    assert (
        main(
            [
                "acquisition",
                "llm-unitize",
                "--selection",
                str(selection_path),
                "--parser-manifest",
                str(parser_path),
                "--output-root",
                str(output_root),
                "--model-registry",
                str(registry_path),
                "--model-key",
                "openai:gpt-test",
                "--continue-on-error",
                "--execute",
            ]
        )
        == 0
    )

    assert _read_jsonl(output_root / "prediction-units.jsonl") == []
    audit = _read_jsonl(output_root / "llm-unitization-audit.jsonl")[0]
    assert audit["status"] == "failed"
    assert "challenged_by_motion" in audit["error_message"]
    assert audit["exclusion_ledger_entries"][0]["stage"] == "labeling"


def test_acquisition_llm_unitize_accepts_first_balanced_json_object(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    output_root = tmp_path / "acquisition"
    markdown_root = output_root / "markdown"
    _write_markdown(markdown_root / "cand-1" / "complaint.md", "Count I: 10(b).")
    _write_markdown(
        markdown_root / "cand-1" / "mtd.md",
        "Defendants move to dismiss Count I under Rule 12(b)(6).",
    )
    selection_path = tmp_path / "selection.jsonl"
    parser_path = tmp_path / "parser.jsonl"
    registry_path = tmp_path / "registry.json"
    _write_jsonl(selection_path, [_selection_record()])
    _write_jsonl(
        parser_path,
        [
            _parser_record("complaint", "complaint.md"),
            _parser_record("mtd", "mtd.md"),
        ],
    )
    _write_json(registry_path, [_registry_record()])

    payload = {
        "unit_seeds": [
            {
                "unit_id": "unit-1",
                "count": "Count I",
                "claim_name": "Section 10(b)",
                "defendant_names": ["Issuer"],
                "source_document_ids": ["mtd"],
                "challenged_by_motion": True,
                "challenge_scope": "entire_claim",
                "unit_confidence": 0.92,
                "grouping": "individual",
                "citation_excerpt": "dismiss Count I",
            }
        ]
    }

    def fake_completion(*args: Any, **kwargs: Any) -> SolverResponse:
        return SolverResponse(
            raw_output=f'{json.dumps(payload)}\n{{"debug": true}}',
            input_tokens=100,
            output_tokens=50,
            estimated_cost=0.01,
            metadata={"provider": "openai", "model_id": "gpt-test"},
        )

    monkeypatch.setattr(llm_pipeline, "complete_live_prompt", fake_completion)

    assert (
        main(
            [
                "acquisition",
                "llm-unitize",
                "--selection",
                str(selection_path),
                "--parser-manifest",
                str(parser_path),
                "--output-root",
                str(output_root),
                "--model-registry",
                str(registry_path),
                "--model-key",
                "openai:gpt-test",
                "--execute",
            ]
        )
        == 0
    )

    unit = _read_jsonl(output_root / "prediction-units.jsonl")[0]["prediction_units"][0]
    assert unit["unit_id"] == "unit-1"


def test_llm_label_excerpt_coercion_uses_verbatim_near_match() -> None:
    decision_text = (
        "Defendants' Motion as to Claim One is GRANTED, and the Claim is "
        "DISMISSED WITH LEAVE TO AMEND."
    )

    coerce_excerpt = cast(Any, llm_pipeline)._coerced_excerpt
    excerpt = coerce_excerpt(
        decision_text,
        "Defendants Motion as to Claim One is granted and the claim is dismissed "
        "with leave to amend.",
    )

    assert excerpt == decision_text


def test_labeling_prompt_explains_not_addressed_resolution() -> None:
    prompt = json.loads(
        cast(Any, llm_pipeline)._labeling_prompt(
            _selection_record(),
            llm_pipeline.StageBDecisionText(
                document_id="decision",
                entered_date="2026-05-18",
                text="The motion is granted as to Count I.",
            ),
            (_prediction_unit(),),
        )
    )

    rules = "\n".join(prompt["rules"])

    assert "not_addressed_by_this_disposition" in rules
    assert "amendment_signal not_applicable" in rules
    assert "do not infer an outcome from silence" in rules


def test_labeling_failure_ledger_uses_specific_reason_codes() -> None:
    response = SolverResponse(
        raw_output='{"unit_findings": "bad"}',
        input_tokens=1,
        output_tokens=1,
        estimated_cost=0.01,
    )
    cases = [
        (
            llm_pipeline.LlmResponseValidationError(
                "unit_findings must be a list",
                response=response,
            ),
            "parse_error",
        ),
        (
            llm_pipeline.LlmPipelineError(
                "LLM labels require lawyer adjudication for units: ['unit-1']"
            ),
            "adjudication_pending",
        ),
        (
            llm_pipeline.LlmPipelineError("LLM judges were not unanimous for unit-1"),
            "judge_disagreement",
        ),
        (
            llm_pipeline.LlmPipelineError(
                "LLM-only labels include ambiguous units: ['unit-1']"
            ),
            "ambiguous",
        ),
    ]

    entries_for = cast(Any, llm_pipeline)._labeling_exclusion_entries

    for error, reason in cases:
        [entry] = entries_for(_selection_record(), error)
        assert entry["primary_exclusion_reason"] == reason
        assert entry["reason"] == reason


def test_acquisition_llm_unitize_failure_audit_keeps_model_accounting(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    output_root = tmp_path / "acquisition"
    markdown_root = output_root / "markdown"
    _write_markdown(markdown_root / "cand-1" / "complaint.md", "Count I: 10(b).")
    _write_markdown(
        markdown_root / "cand-1" / "mtd.md",
        "Defendants move to dismiss Count I under Rule 12(b)(6).",
    )
    selection_path = tmp_path / "selection.jsonl"
    parser_path = tmp_path / "parser.jsonl"
    registry_path = tmp_path / "registry.json"
    _write_jsonl(selection_path, [_selection_record()])
    _write_jsonl(
        parser_path,
        [
            _parser_record("complaint", "complaint.md"),
            _parser_record("mtd", "mtd.md"),
        ],
    )
    _write_json(registry_path, [_registry_record()])

    def invalid_completion(*args: Any, **kwargs: Any) -> SolverResponse:
        return SolverResponse(
            raw_output=json.dumps(
                {
                    "unit_seeds": [
                        {
                            "unit_id": "unit-1",
                            "count": "Count I",
                            "claim_name": "Section 10(b)",
                            "defendant_names": ["Issuer"],
                            "source_document_ids": {"document_id": "mtd"},
                            "challenged_by_motion": True,
                            "challenge_scope": "entire_claim",
                            "unit_confidence": 0.92,
                            "grouping": "individual",
                            "citation_excerpt": "dismiss Count I",
                        }
                    ]
                }
            ),
            input_tokens=123,
            output_tokens=45,
            estimated_cost=0.12,
            metadata={"provider": "openai", "model_id": "gpt-test"},
        )

    monkeypatch.setattr(llm_pipeline, "complete_live_prompt", invalid_completion)

    assert (
        main(
            [
                "acquisition",
                "llm-unitize",
                "--selection",
                str(selection_path),
                "--parser-manifest",
                str(parser_path),
                "--output-root",
                str(output_root),
                "--model-registry",
                str(registry_path),
                "--model-key",
                "openai:gpt-test",
                "--continue-on-error",
                "--execute",
            ]
        )
        == 0
    )

    assert _read_jsonl(output_root / "prediction-units.jsonl") == []
    audit = _read_jsonl(output_root / "llm-unitization-audit.jsonl")[0]
    assert audit["status"] == "failed"
    assert audit["estimated_cost"] == 0.12
    assert audit["input_tokens"] == 123
    assert audit["output_tokens"] == 45
    assert str(audit["raw_output_sha256"]).startswith("sha256:")
    assert audit["metadata"]["model_id"] == "gpt-test"


def test_acquisition_llm_label_failure_audit_keeps_model_accounting(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    output_root = tmp_path / "acquisition"
    markdown_root = output_root / "markdown"
    _write_markdown(markdown_root / "cand-1" / "decision.md", "Count I is dismissed.")
    selection_path = tmp_path / "selection.jsonl"
    parser_path = tmp_path / "parser.jsonl"
    units_path = tmp_path / "prediction-units.jsonl"
    registry_path = tmp_path / "registry.json"
    _write_jsonl(selection_path, [_selection_record()])
    _write_jsonl(parser_path, [_parser_record("decision", "decision.md")])
    _write_jsonl(
        units_path,
        [
            {
                "candidate_id": "cand-1",
                "case_id": "case-1",
                "prediction_units": [
                    {
                        "unit_id": "unit-1",
                        "count": "Count I",
                        "claim_name": "Section 10(b)",
                        "defendant_group": "Issuer",
                        "challenged_by_motion": True,
                        "challenge_scope": "entire_claim",
                        "unit_confidence": 0.9,
                        "source_citations": [{"document_id": "mtd"}],
                        "grouping": "individual",
                        "grouping_rationale": None,
                        "separable_subclaim": None,
                        "uncertainty_notes": None,
                    }
                ],
            }
        ],
    )
    _write_json(registry_path, [_registry_record()])

    def invalid_label_completion(*args: Any, **kwargs: Any) -> SolverResponse:
        return SolverResponse(
            raw_output=json.dumps(
                {
                    "unit_findings": [
                        {
                            "unit_id": "unit-1",
                            "resolution": "fully_dismissed",
                            "amendment_signal": "express_denial_of_leave",
                            "supporting_excerpt": "The motion is granted.",
                            "labeler_confidence": 0.91,
                        }
                    ],
                    "missing_unit_flags": [],
                }
            ),
            input_tokens=234,
            output_tokens=56,
            estimated_cost=0.23,
            metadata={"provider": "openai", "model_id": "gpt-test"},
        )

    monkeypatch.setattr(llm_pipeline, "complete_live_prompt", invalid_label_completion)

    assert (
        main(
            [
                "acquisition",
                "llm-label",
                "--selection",
                str(selection_path),
                "--parser-manifest",
                str(parser_path),
                "--prediction-units",
                str(units_path),
                "--output-root",
                str(output_root),
                "--model-registry",
                str(registry_path),
                "--model-key",
                "openai:gpt-test",
                "--continue-on-error",
                "--execute",
            ]
        )
        == 0
    )

    assert _read_jsonl(output_root / "labels.jsonl") == []
    audit = _read_jsonl(output_root / "llm-label-audit.jsonl")[0]
    assert audit["status"] == "failed"
    assert audit["estimated_cost"] == 0.23
    assert audit["input_tokens"] == 234
    assert audit["output_tokens"] == 56
    assert str(audit["raw_output_sha256"]).startswith("sha256:")
    assert audit["metadata"]["model_id"] == "gpt-test"


def test_acquisition_llm_label_missing_unit_flags_gate_frozen_unit_workflow(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    output_root = tmp_path / "acquisition"
    markdown_root = output_root / "markdown"
    _write_markdown(
        markdown_root / "cand-1" / "decision.md",
        "Count I is dismissed. The court also dismisses Count II.",
    )
    selection_path = tmp_path / "selection.jsonl"
    parser_path = tmp_path / "parser.jsonl"
    units_path = tmp_path / "prediction-units.jsonl"
    registry_path = tmp_path / "registry.json"
    _write_jsonl(selection_path, [_selection_record()])
    _write_jsonl(parser_path, [_parser_record("decision", "decision.md")])
    _write_jsonl(
        units_path,
        [
            {
                "candidate_id": "cand-1",
                "case_id": "case-1",
                "prediction_units": [
                    {
                        "unit_id": "unit-1",
                        "count": "Count I",
                        "claim_name": "Section 10(b)",
                        "defendant_group": "Issuer",
                        "challenged_by_motion": True,
                        "challenge_scope": "entire_claim",
                        "unit_confidence": 0.9,
                        "source_citations": [{"document_id": "mtd"}],
                        "grouping": "individual",
                        "grouping_rationale": None,
                        "separable_subclaim": None,
                        "uncertainty_notes": None,
                    }
                ],
            }
        ],
    )
    _write_json(registry_path, [_registry_record()])

    def missing_unit_completion(*args: Any, **kwargs: Any) -> SolverResponse:
        return SolverResponse(
            raw_output=json.dumps(
                {
                    "unit_findings": [
                        {
                            "unit_id": "unit-1",
                            "resolution": "fully_dismissed",
                            "amendment_signal": "express_denial_of_leave",
                            "supporting_excerpt": "Count I is dismissed.",
                            "labeler_confidence": 0.91,
                        }
                    ],
                    "missing_unit_flags": [
                        {
                            "missing_unit_description": (
                                "Decision resolved Count II, which was absent from "
                                "frozen Stage A units."
                            ),
                            "supporting_excerpt": (
                                "The court also dismisses Count II."
                            ),
                        }
                    ],
                }
            ),
            input_tokens=345,
            output_tokens=67,
            estimated_cost=0.34,
            metadata={"provider": "openai", "model_id": "gpt-test"},
        )

    monkeypatch.setattr(llm_pipeline, "complete_live_prompt", missing_unit_completion)

    assert (
        main(
            [
                "acquisition",
                "llm-label",
                "--selection",
                str(selection_path),
                "--parser-manifest",
                str(parser_path),
                "--prediction-units",
                str(units_path),
                "--output-root",
                str(output_root),
                "--model-registry",
                str(registry_path),
                "--model-key",
                "openai:gpt-test",
                "--continue-on-error",
                "--execute",
            ]
        )
        == 0
    )

    assert _read_jsonl(output_root / "labels.jsonl") == []
    audit = _read_jsonl(output_root / "llm-label-audit.jsonl")[0]
    assert audit["status"] == "failed"
    assert audit["error_type"] == "FrozenUnitWorkflowRequiredError"
    assert audit["requires_frozen_unit_workflow"] is True
    assert audit["missing_unit_flag_count"] == 1
    assert audit["frozen_unit_excluded_count"] == 1
    assert audit["frozen_unit_repaired_count"] == 0
    assert audit["frozen_unit_workflow"]["frozen_unit_status"] == "excluded"
    assert audit["estimated_cost"] == 0.34
    [entry] = audit["exclusion_ledger_entries"]
    assert entry["stage"] == "unitization"
    assert entry["primary_exclusion_reason"] == "unit_missing_from_stage_a"


def _fake_completion(*args: Any, **kwargs: Any) -> SolverResponse:
    prompt = cast(str, args[1])
    if "Construct frozen Stage A" in prompt:
        raw_output = {
            "unit_seeds": [
                {
                    "unit_id": "unit-1",
                    "count": "Count I",
                    "claim_name": "Section 10(b)",
                    "defendant_names": ["Issuer"],
                    "source_document_ids": ["complaint", "mtd"],
                    "challenged_by_motion": True,
                    "challenge_scope": "entire_claim",
                    "unit_confidence": 0.92,
                    "grouping": "individual",
                    "citation_excerpt": "Count I: 10(b).",
                }
            ]
        }
    elif "Create Stage B outcome labels" in prompt:
        raw_output = {
            "unit_findings": [
                {
                    "unit_id": "unit-1",
                    "resolution": "fully_dismissed",
                    "amendment_signal": "express_denial_of_leave",
                    "supporting_excerpt": (
                        "motion to dismiss Count I is granted without leave"
                    ),
                    "labeler_confidence": 0.91,
                    "notes": "The court dismissed the only challenged claim.",
                }
            ],
            "missing_unit_flags": [],
        }
    else:
        raise AssertionError("unexpected prompt")
    return SolverResponse(
        raw_output=json.dumps(raw_output),
        input_tokens=100,
        output_tokens=50,
        estimated_cost=0.01,
        metadata={"provider": "openai", "model_id": "gpt-test"},
    )


def _selection_record() -> JsonRecord:
    return {
        "candidate_id": "cand-1",
        "case_id": "case-1",
        "case_name": "Example v. Issuer",
        "court": "S.D.N.Y.",
        "docket_number": "1:26-cv-1",
        "target_motion_entry_numbers": [5],
        "decision_entry_numbers": [16],
        "documents": [
            _selection_document("complaint", "complaint", 1, True, False),
            _selection_document("mtd", "motion_to_dismiss_notice", 5, True, False),
            _selection_document("decision", "decision", 16, False, True),
        ],
    }


def _selection_document(
    source_document_id: str,
    role: str,
    docket_entry_number: int,
    model_visible: bool,
    contains_target_outcome: bool,
) -> JsonRecord:
    return {
        "candidate_id": "cand-1",
        "source_document_id": source_document_id,
        "docket_entry_number": docket_entry_number,
        "document_role": role,
        "description": role,
        "model_visible": model_visible,
        "contains_target_outcome": contains_target_outcome,
    }


def _prediction_unit() -> PredictionUnit:
    return PredictionUnit(
        unit_id="unit-1",
        count="Count I",
        claim_name="Section 10(b)",
        defendant_group="Issuer",
        challenged_by_motion=True,
        challenge_scope=ChallengeScope.ENTIRE_CLAIM,
        unit_confidence=0.9,
        source_citations=(
            SourceCitation(
                document_id="mtd",
                docket_entry_number=5,
                excerpt="Defendants move to dismiss Count I.",
            ),
        ),
    )


def _parser_record(source_document_id: str, filename: str) -> JsonRecord:
    return {
        "candidate_id": "cand-1",
        "source_document_id": source_document_id,
        "status": "succeeded",
        "markdown_path": f"cand-1/{filename}",
    }


def _registry_record() -> JsonRecord:
    return {
        "provider": "openai",
        "model_id": "gpt-test",
        "display_name": "GPT Test",
        "model_version_or_snapshot": "gpt-test",
        "release_timestamp": "2026-05-18T00:00:00Z",
        "release_timestamp_source": "fixture release note",
        "provider_training_cutoff_status": "known",
        "provider_training_cutoff": "2026-04-01",
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
        "known_cutoff_publicity_caveats": [],
    }


def _write_markdown(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_jsonl(path: Path, records: list[JsonRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(f"{json.dumps(record, sort_keys=True)}\n" for record in records),
        encoding="utf-8",
    )


def _write_json(path: Path, record: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")


def _read_jsonl(path: Path) -> list[JsonRecord]:
    return [
        cast(JsonRecord, json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
