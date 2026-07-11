from __future__ import annotations

import json
from pathlib import Path

from legalforecast.cli import main

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "model_registries" / "cycle-1-2026-06-30.json"


def test_acquisition_finalize_corpus_writes_complete_ledger_and_readiness(
    tmp_path: Path,
) -> None:
    inputs = tmp_path / "inputs"
    output_root = tmp_path / "out"
    markdown_root = tmp_path / "markdown"
    inputs.mkdir()
    markdown_root.mkdir()
    (markdown_root / "decision-1.md").write_text(
        "The Court rules. Count I is dismissed.",
        encoding="utf-8",
    )
    _write_jsonl(
        inputs / "selection.jsonl",
        [
            {
                "candidate_id": "cand-1",
                "case_id": "case-1",
                "court": "S.D.N.Y.",
                "documents": [
                    {
                        "source_document_id": "complaint-1",
                        "document_role": "operative_complaint",
                        "contains_target_outcome": False,
                    },
                    {
                        "source_document_id": "decision-1",
                        "document_role": "decision",
                        "contains_target_outcome": True,
                    },
                ],
            },
            {
                "candidate_id": "cand-incomplete",
                "case_id": "case-incomplete",
                "court": "D. Del.",
                "documents": [
                    {
                        "source_document_id": "missing-decision",
                        "document_role": "decision",
                        "contains_target_outcome": True,
                    }
                ],
            },
        ],
    )
    _write_jsonl(
        inputs / "parser.jsonl",
        [
            {
                "candidate_id": "cand-1",
                "source_document_id": document_id,
                "status": "succeeded",
                "markdown_path": (
                    "decision-1.md" if document_id == "decision-1" else "complaint.md"
                ),
            }
            for document_id in ("complaint-1", "decision-1")
        ],
    )
    _write_jsonl(
        inputs / "units.jsonl",
        [
            {
                "candidate_id": "cand-1",
                "prediction_units": [{"unit_id": "unit-1", "should_score": True}],
            }
        ],
    )
    _write_jsonl(
        inputs / "labels.jsonl",
        [
            {
                "unit_id": "unit-1",
                "fully_dismissed": True,
                "amendment_class": ("dismissed_without_express_amendment_opportunity"),
                "ambiguous": False,
                "label_confidence": 0.95,
                "first_written_disposition_id": "decision-1",
                "first_written_disposition_date": "2026-06-30",
                "first_written_disposition_locked": True,
                "later_procedural_changes": [],
                "supporting_citations": [
                    {
                        "document_id": "decision-1",
                        "excerpt": "Count I is dismissed.",
                    }
                ],
            }
        ],
    )
    _write_jsonl(
        inputs / "label-audit.jsonl",
        [{"candidate_id": "cand-1", "status": "succeeded"}],
    )
    _write_jsonl(inputs / "review-queue.jsonl", [])
    _write_jsonl(inputs / "packet-input.jsonl", [{"candidate_id": "cand-1"}])
    _write_jsonl(
        inputs / "packets.jsonl",
        [
            {
                "candidate_id": "cand-1",
                "court": "S.D.N.Y.",
                "related_family_id": "related-fixture",
                "mdl_family_id": "mdl-fixture",
                "metadata": {
                    "nature_of_suit": "Contract",
                    "nos_macro_category": "contract",
                },
            }
        ],
    )
    _write_jsonl(inputs / "public-exclusions.jsonl", [])
    _write_jsonl(inputs / "packet-exclusions.jsonl", [])
    _write_jsonl(
        inputs / "screened-cases.jsonl",
        [
            {"candidate": {"docket_id": "cand-1"}},
            {"candidate": {"docket_id": "cand-incomplete"}},
        ],
    )
    (inputs / "discovery-summary.json").write_text(
        json.dumps(
            {
                "processed_candidate_count": 2,
                "accepted_case_count": 2,
                "excluded_case_count": 0,
            }
        ),
        encoding="utf-8",
    )
    _write_jsonl(inputs / "discovery-exclusions.jsonl", [])

    assert (
        main(
            [
                "acquisition",
                "finalize-corpus",
                "--selection",
                str(inputs / "selection.jsonl"),
                "--parser-manifest",
                str(inputs / "parser.jsonl"),
                "--markdown-root",
                str(markdown_root),
                "--prediction-units",
                str(inputs / "units.jsonl"),
                "--labels",
                str(inputs / "labels.jsonl"),
                "--llm-label-audit",
                str(inputs / "label-audit.jsonl"),
                "--lawyer-review-queue",
                str(inputs / "review-queue.jsonl"),
                "--packet-build-input",
                str(inputs / "packet-input.jsonl"),
                "--packets",
                str(inputs / "packets.jsonl"),
                "--model-registry",
                str(REGISTRY),
                "--screened-cases",
                str(inputs / "screened-cases.jsonl"),
                "--discovery-summary",
                str(inputs / "discovery-summary.json"),
                "--discovery-exclusions",
                str(inputs / "discovery-exclusions.jsonl"),
                "--exclusion-source",
                str(inputs / "public-exclusions.jsonl"),
                "--exclusion-source",
                str(inputs / "packet-exclusions.jsonl"),
                "--target-clean-cases",
                "1",
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )

    ledger = _read_jsonl(output_root / "complete-exclusion-ledger.jsonl")
    assert len(ledger) == 1
    assert ledger[0]["candidate_id"] == "cand-incomplete"
    assert ledger[0]["primary_exclusion_reason"] == (
        "required_document_parse_incomplete"
    )
    assert ledger[0]["secondary_exclusion_reasons"] == [
        "stage_a_units_missing",
        "label_audit_missing",
        "packet_build_input_missing",
        "built_packet_missing",
    ]
    readiness = json.loads(
        (output_root / "corpus-readiness.json").read_text(encoding="utf-8")
    )
    assert readiness["clean_count"] == 1
    assert readiness["meets_target"] is True
    assert readiness["case_mix"]["court"] == {"S.D.N.Y.": 1}
    assert readiness["case_mix"]["nature_of_suit"] == {"Contract": 1}
    assert readiness["case_mix"]["nos_macro_category"] == {"contract": 1}
    assert readiness["case_mix"]["related_family_id"] == {"related-fixture": 1}
    assert readiness["case_mix"]["mdl_family_id"] == {"mdl-fixture": 1}
    assert all(
        sum(buckets.values()) == readiness["clean_count"]
        for buckets in readiness["case_mix"].values()
    )


def test_acquisition_finalize_corpus_rejects_unreconciled_screened_candidate(
    tmp_path: Path,
    capsys,
) -> None:
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    _write_jsonl(
        inputs / "screened-cases.jsonl",
        [
            {"candidate": {"docket_id": "cand-selected"}},
            {"candidate": {"docket_id": "cand-dropped"}},
        ],
    )
    (inputs / "discovery-summary.json").write_text(
        json.dumps(
            {
                "processed_candidate_count": 2,
                "accepted_case_count": 2,
                "excluded_case_count": 0,
            }
        ),
        encoding="utf-8",
    )
    _write_jsonl(inputs / "discovery-exclusions.jsonl", [])
    for name in (
        "selection",
        "parser",
        "units",
        "labels",
        "label-audit",
        "review-queue",
        "packet-input",
        "packets",
    ):
        _write_jsonl(inputs / f"{name}.jsonl", [])

    result = main(
        [
            "acquisition",
            "finalize-corpus",
            "--selection",
            str(inputs / "selection.jsonl"),
            "--parser-manifest",
            str(inputs / "parser.jsonl"),
            "--markdown-root",
            str(tmp_path / "markdown"),
            "--prediction-units",
            str(inputs / "units.jsonl"),
            "--labels",
            str(inputs / "labels.jsonl"),
            "--llm-label-audit",
            str(inputs / "label-audit.jsonl"),
            "--lawyer-review-queue",
            str(inputs / "review-queue.jsonl"),
            "--packet-build-input",
            str(inputs / "packet-input.jsonl"),
            "--packets",
            str(inputs / "packets.jsonl"),
            "--model-registry",
            str(REGISTRY),
            "--screened-cases",
            str(inputs / "screened-cases.jsonl"),
            "--discovery-summary",
            str(inputs / "discovery-summary.json"),
            "--discovery-exclusions",
            str(inputs / "discovery-exclusions.jsonl"),
            "--target-clean-cases",
            "1",
            "--output-root",
            str(tmp_path / "out"),
            "--execute",
        ]
    )

    assert result == 2
    assert "unreconciled screened candidates: cand-dropped" in capsys.readouterr().err


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(f"{json.dumps(record, sort_keys=True)}\n" for record in records),
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
