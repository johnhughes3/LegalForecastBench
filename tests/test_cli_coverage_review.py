from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from legalforecast.cli import main

JsonRecord = dict[str, Any]
DOCUMENT_TEXTS = {
    "doc-1": "Complaint alleges Count I for breach of contract.",
    "doc-12": "Defendant moves to dismiss Count I.",
    "doc-18": "Plaintiff opposes dismissal of Count I.",
    "doc-35": "The Court denies dismissal of Count I as to Example LLC.",
}


def test_fixture_backed_non_dry_run_cli_stage_success_paths(
    tmp_path: Path,
) -> None:
    case_dev_fixture = tmp_path / "case-dev-responses.jsonl"
    _write_jsonl(case_dev_fixture, _case_dev_response_records())
    candidates = tmp_path / "candidates.jsonl"
    _write_jsonl(candidates, [{"candidate_id": "cand-case-1", "case_id": "case-1"}])

    retrievals = tmp_path / "retrievals.jsonl"
    assert (
        main(
            [
                "retrieve",
                "--candidates",
                str(candidates),
                "--output",
                str(retrievals),
                "--case-dev-fixture",
                str(case_dev_fixture),
            ]
        )
        == 0
    )
    retrieval = _read_jsonl(retrievals)[0]
    assert retrieval["case_id"] == "case-1"
    assert len(retrieval["filings"]) == 4

    documents = tmp_path / "documents.jsonl"
    document_dir = tmp_path / "documents"
    document_records: list[JsonRecord] = []
    for document_id, text in DOCUMENT_TEXTS.items():
        path = document_dir / f"{document_id}.pdf"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_fixture_pdf(text))
        document_records.append({"source_document_id": document_id, "path": str(path)})
    _write_jsonl(documents, document_records)

    extracted = tmp_path / "extracted-texts.jsonl"
    text_output_dir = tmp_path / "texts"
    assert (
        main(
            [
                "extract",
                "--documents",
                str(documents),
                "--output",
                str(extracted),
                "--text-output-dir",
                str(text_output_dir),
            ]
        )
        == 0
    )
    extracted_texts = _read_jsonl(extracted)
    assert len(extracted_texts) == 4
    assert "Complaint alleges Count I" in (text_output_dir / "doc-1.txt").read_text(
        encoding="utf-8"
    )

    linkage = tmp_path / "linkage.jsonl"
    assert (
        main(["link", "--retrievals", str(retrievals), "--output", str(linkage)]) == 0
    )
    link_record = _read_jsonl(linkage)[0]
    assert link_record["is_clean"] is True
    assert link_record["links"][0]["motion_entry_ids"] == ["entry-12"]

    stage_a_input = tmp_path / "stage-a-input.jsonl"
    _write_jsonl(stage_a_input, [_stage_a_input_record()])
    units_path = tmp_path / "units.jsonl"
    assert (
        main(["unitize", "--input", str(stage_a_input), "--output", str(units_path)])
        == 0
    )
    units = _read_jsonl(units_path)
    assert [unit["unit_id"] for unit in units] == ["unit-count-i"]

    label_input = tmp_path / "label-input.jsonl"
    _write_jsonl(label_input, [_stage_b_input_record(units)])
    labels_path = tmp_path / "labels.jsonl"
    assert (
        main(["label", "--input", str(label_input), "--output", str(labels_path)]) == 0
    )
    labels = _read_jsonl(labels_path)
    assert labels[0]["fully_dismissed"] is False

    packet_input = tmp_path / "packet-input.jsonl"
    text_by_document_id = {
        document_id: (text_output_dir / f"{document_id}.txt").read_text(
            encoding="utf-8"
        )
        for document_id in DOCUMENT_TEXTS
    }
    _write_jsonl(
        packet_input,
        [
            _packet_input_record(
                retrieval,
                extracted_texts=extracted_texts,
                units=units,
                texts=text_by_document_id,
            )
        ],
    )
    packets_path = tmp_path / "packets.jsonl"
    assert (
        main(
            [
                "packet",
                "build",
                "--input",
                str(packet_input),
                "--output",
                str(packets_path),
            ]
        )
        == 0
    )
    packet = _read_jsonl(packets_path)[0]
    assert [document["source_document_id"] for document in packet["documents"]] == [
        "doc-1",
        "doc-12",
    ]
    assert packet["related_family_id"] == "fixture-family"
    assert packet["mdl_family_id"] == "fixture-mdl"
    assert packet["excluded_document_ids"] == ["doc-18", "doc-35"]

    runs_path = tmp_path / "runs.jsonl"
    accounting_path = tmp_path / "accounting.jsonl"
    assert (
        main(
            [
                "eval",
                "run",
                "--packets",
                str(packets_path),
                "--output",
                str(runs_path),
                "--accounting-output",
                str(accounting_path),
                "--solver-id",
                "offline:test",
                "--mock-output",
                _mock_output("unit-count-i"),
            ]
        )
        == 0
    )
    run = _read_jsonl(runs_path)[0]
    assert run["case_id"] == "case-1"
    assert run["related_family_id"] == "fixture-family"
    assert run["mdl_family_id"] == "fixture-mdl"
    assert run["required_unit_ids"] == ["unit-count-i"]
    assert _read_jsonl(accounting_path)[0]["solver_id"] == "offline:test"

    scores_path = tmp_path / "scores.json"
    unit_scores_path = tmp_path / "unit-scores.jsonl"
    assert (
        main(
            [
                "score",
                "--runs",
                str(runs_path),
                "--labels",
                str(labels_path),
                "--output",
                str(scores_path),
                "--unit-scores-output",
                str(unit_scores_path),
            ]
        )
        == 0
    )
    score_payload = json.loads(scores_path.read_text(encoding="utf-8"))
    summary_unit_score = score_payload["summaries"][0]["unit_scores"][0]
    assert summary_unit_score["related_family_id"] == "fixture-family"
    assert summary_unit_score["mdl_family_id"] == "fixture-mdl"
    unit_score = _read_jsonl(unit_scores_path)[0]
    assert unit_score["related_family_id"] == "fixture-family"
    assert unit_score["mdl_family_id"] == "fixture-mdl"


def test_extract_rejects_path_like_source_document_id(tmp_path: Path) -> None:
    document_path = tmp_path / "source.pdf"
    document_path.write_bytes(_fixture_pdf("Complaint text"))
    documents = tmp_path / "documents.jsonl"
    _write_jsonl(
        documents,
        [{"source_document_id": "../escape", "path": str(document_path)}],
    )
    text_output_dir = tmp_path / "texts"

    assert (
        main(
            [
                "extract",
                "--documents",
                str(documents),
                "--output",
                str(tmp_path / "extracted.jsonl"),
                "--text-output-dir",
                str(text_output_dir),
            ]
        )
        == 2
    )
    assert not (tmp_path / "escape.txt").exists()


def test_retrieve_cli_requires_explicit_fixture_or_live_mode(
    tmp_path: Path,
    capsys,
) -> None:
    candidates = tmp_path / "candidates.jsonl"
    output = tmp_path / "retrievals.jsonl"
    candidates.write_text(
        json.dumps(
            {
                "case_id": "case-1",
                "candidate_id": "candidate-1",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    assert (
        main(
            [
                "retrieve",
                "--candidates",
                str(candidates),
                "--output",
                str(output),
            ]
        )
        == 2
    )

    captured = capsys.readouterr()
    assert "retrieve requires --case-dev-fixture" in captured.err
    assert not output.exists()


def test_packet_build_cli_reports_missing_mounted_text_value_error(
    tmp_path: Path,
    capsys,
) -> None:
    case_dev_fixture = tmp_path / "case-dev-responses.jsonl"
    _write_jsonl(case_dev_fixture, _case_dev_response_records())
    candidates = tmp_path / "candidates.jsonl"
    _write_jsonl(candidates, [{"candidate_id": "cand-case-1", "case_id": "case-1"}])
    retrievals = tmp_path / "retrievals.jsonl"
    assert (
        main(
            [
                "retrieve",
                "--candidates",
                str(candidates),
                "--output",
                str(retrievals),
                "--case-dev-fixture",
                str(case_dev_fixture),
            ]
        )
        == 0
    )
    packet_input = tmp_path / "packet-input.jsonl"
    _write_jsonl(
        packet_input,
        [
            _packet_input_record(
                _read_jsonl(retrievals)[0],
                extracted_texts=(),
                units=[_unit_record()],
                texts={"doc-1": DOCUMENT_TEXTS["doc-1"]},
            )
        ],
    )

    assert (
        main(
            [
                "packet-build",
                "--input",
                str(packet_input),
                "--output",
                str(tmp_path / "packets.jsonl"),
            ]
        )
        == 2
    )

    assert "missing extracted text for mounted source document: doc-12" in (
        capsys.readouterr().err
    )


def _case_dev_response_records() -> tuple[JsonRecord, ...]:
    return (
        {
            "method": "POST",
            "path": "/legal/v1/docket",
            "params": {"type": "lookup", "docketId": "case-1"},
            "status_code": 200,
            "payload": {
                "docket": {
                    "id": "case-1",
                    "caseName": "Fixture v. Example",
                    "court": "S.D.N.Y.",
                    "docketNumber": "1:26-cv-00001",
                },
            },
        },
        {
            "method": "POST",
            "path": "/legal/v1/docket",
            "params": {
                "type": "lookup",
                "docketId": "case-1",
                "includeEntries": True,
            },
            "status_code": 200,
            "payload": {
                "docket": {
                    "id": "case-1",
                    "entries": [
                        _docket_payload(1, "Complaint", "doc-1"),
                        _docket_payload(12, "Motion to dismiss complaint", "doc-12"),
                        _docket_payload(
                            18,
                            "Opposition to motion to dismiss",
                            "doc-18",
                        ),
                        _docket_payload(
                            35,
                            "Opinion and order denying motion to dismiss at ECF No. 12",
                            "doc-35",
                        ),
                    ],
                }
            },
        },
        *(
            {
                "method": "GET",
                "path": f"/v1/documents/{document_id}",
                "params": {},
                "status_code": 200,
                "payload": {
                    "document_id": document_id,
                    "case_id": "case-1",
                    "text": text,
                },
            }
            for document_id, text in DOCUMENT_TEXTS.items()
        ),
    )


def _docket_payload(entry_number: int, text: str, document_id: str) -> JsonRecord:
    return {
        "entryNumber": entry_number,
        "description": text,
        "date": "2026-05-14",
        "documents": [{"id": document_id}],
    }


def _stage_a_input_record() -> JsonRecord:
    return {
        "candidate_id": "cand-case-1",
        "case_id": "case-1",
        "source_documents": [
            {
                "document_id": "doc-1",
                "role": "complaint",
                "docket_entry_number": 1,
                "title": "Complaint",
            },
            {
                "document_id": "doc-12",
                "role": "motion_to_dismiss_notice",
                "docket_entry_number": 12,
                "title": "Motion to dismiss",
            },
        ],
        "unit_seeds": [
            {
                "unit_id": "unit-count-i",
                "count": "Count I",
                "claim_name": "Breach of contract",
                "defendant_names": ["Example LLC"],
                "source_document_ids": ["doc-1", "doc-12"],
                "citation_page": 1,
            }
        ],
    }


def _stage_b_input_record(units: list[JsonRecord]) -> JsonRecord:
    return {
        "candidate_id": "cand-case-1",
        "case_id": "case-1",
        "frozen_units": units,
        "decision_text": {
            "document_id": "doc-35",
            "entered_date": "2026-05-18",
            "text": DOCUMENT_TEXTS["doc-35"],
        },
        "unit_findings": [
            {
                "unit_id": "unit-count-i",
                "resolution": "survives_in_material_respect",
                "amendment_signal": "not_applicable",
                "supporting_excerpt": "denies dismissal of Count I",
                "labeler_confidence": 0.97,
                "page": 1,
            }
        ],
    }


def _packet_input_record(
    retrieval: JsonRecord,
    *,
    extracted_texts: list[JsonRecord] | tuple[()],
    units: list[JsonRecord],
    texts: dict[str, str],
) -> JsonRecord:
    return {
        "case_packet": {
            "candidate_id": retrieval["candidate_id"],
            "case_id": retrieval["case_id"],
            "court": retrieval["court"],
            "docket_number": retrieval["docket_number"],
            "generated_at": "2026-05-14T12:00:00Z",
            "documents": [
                filing["provenance"]
                for filing in cast(list[JsonRecord], retrieval["filings"])
            ],
            "extracted_texts": list(extracted_texts),
        },
        "prediction_units": units,
        "texts": texts,
        "metadata": {"judge": "Judge Fixture", "nos_macro_category": "contract"},
        "target_docket_entry_numbers": [12],
        "related_family_id": "fixture-family",
        "mdl_family_id": "fixture-mdl",
    }


def _unit_record() -> JsonRecord:
    return {
        "unit_id": "unit-count-i",
        "count": "Count I",
        "claim_name": "Breach of contract",
        "defendant_group": "Example LLC",
        "challenged_by_motion": True,
        "challenge_scope": "entire_claim",
        "unit_confidence": 0.8,
        "grouping": "individual",
        "source_citations": [
            {
                "document_id": "doc-1",
                "docket_entry_number": 1,
                "page": 1,
                "paragraph": None,
                "excerpt": None,
            }
        ],
    }


def _mock_output(unit_id: str) -> str:
    return json.dumps(
        {
            "case_assessment": "Fixture prediction.",
            "predictions": [
                {
                    "unit_id": unit_id,
                    "probability_fully_dismissed": 0.25,
                }
            ],
        },
        sort_keys=True,
    )


def _fixture_pdf(text: str) -> bytes:
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET"
    body = stream.encode("utf-8")
    objects = [
        "1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj",
        "2 0 obj << /Type /Pages /Count 1 /Kids [3 0 R] >> endobj",
        "3 0 obj << /Type /Page /Contents 4 0 R >> endobj",
        f"4 0 obj << /Length {len(body)} >> stream\n{stream}\nendstream endobj",
    ]
    return ("%PDF-1.4\n" + "\n".join(objects) + "\n%%EOF").encode()


def _write_jsonl(
    path: Path, records: list[JsonRecord] | tuple[JsonRecord, ...]
) -> None:
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
