"""Behaviour of the v3 exact-100 successor lane.

Every fixture here is synthetic: no real case, document, digest or filesystem
path from the production cohort appears, and no test reads the artifacts tree.
The synthetic packets are hand-authored (``synthetic: true``) and are generated
by :func:`_cohort` and :func:`_replacement_inputs` in this module.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from legalforecast.ingestion.exact100_successor_v3 import cli as v3_cli
from legalforecast.ingestion.exact100_successor_v3.projector import (
    Exact100SuccessorReplacementV3Error,
    PromotionProvenanceClass,
    TerminalExclusionGroundV2,
    methods_disclosure_text,
    mint_verified_exact100_v3_base,
    mint_verified_exact100_v3_terminal_exclusions,
    project_exact100_successor_replacement_v3,
)
from legalforecast.ingestion.exact100_successor_v3.replacement_evidence import (
    OwnerAdjudicatedReplacementError,
    VerifiedOwnerAdjudicatedReplacement,
    mint_verified_owner_adjudicated_replacement,
)
from legalforecast.ingestion.exact100_successor_v3.replacement_evidence_cli import (
    OwnerAdjudicatedReplacementCliError,
    verify_owner_adjudicated_replacement_evidence,
)

_ROLES = (
    ("complaint", "operative_pleading", 1),
    ("motion_to_dismiss_memorandum", "target_motion", 2),
    ("opposition", "opposition", 3),
    ("reply", "reply", 4),
    ("decision", "decision", 5),
)


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _pdf_bytes(candidate_id: str, source_document_id: str) -> bytes:
    return f"%PDF-1.7 synthetic {candidate_id} {source_document_id}\n".encode()


def _documents(candidate_id: str) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for role, _receipt_role, entry in _ROLES:
        source_document_id = f"{candidate_id}-doc-{entry}"
        documents.append(
            {
                "candidate_id": candidate_id,
                "contains_target_outcome": role == "decision",
                "description": role,
                "docket_entry_number": entry,
                "document_role": role,
                "is_private": False,
                "is_sealed": False,
                "model_visible": role != "decision",
                "redaction_or_seal_status": "public",
                "restriction_evidence": [
                    "courtlistener_public_download_record_checked"
                ],
                "setup_runner_label": (
                    "other_substantive" if role == "decision" else "core_mtd"
                ),
                "source_document_id": source_document_id,
                "source_url": None,
            }
        )
    return documents


def _selection_row(candidate_id: str) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "case_id": candidate_id,
        "case_name": f"Synthetic {candidate_id}",
        "court": "xxd",
        "documents": _documents(candidate_id),
        "selected": True,
    }


def _evidence_rows(candidate_id: str) -> tuple[list[dict[str, Any]], ...]:
    manifest: list[dict[str, Any]] = []
    clearance: list[dict[str, Any]] = []
    restriction: list[dict[str, Any]] = []
    for role, _receipt_role, entry in _ROLES:
        source_document_id = f"{candidate_id}-doc-{entry}"
        payload = _pdf_bytes(candidate_id, source_document_id)
        digest = hashlib.sha256(payload).hexdigest()
        manifest.append(
            {
                "byte_count": len(payload),
                "candidate_id": candidate_id,
                "document_role": role,
                "free_or_purchased": "free",
                "sha256": digest,
                "source_document_id": source_document_id,
            }
        )
        clearance.append(
            {
                "byte_count": len(payload),
                "candidate_id": candidate_id,
                "sha256": digest,
                "source_document_id": source_document_id,
                "status": "cleared",
            }
        )
        restriction.append(
            {
                "candidate_id": candidate_id,
                "is_private": False,
                "is_sealed": False,
                "restriction_status": "public",
                "source_document_id": source_document_id,
            }
        )
    return manifest, clearance, restriction


def _cohort(count: int = 100) -> dict[str, Any]:
    """Build a synthetic exact-100 predecessor cohort surface."""

    selection = [_selection_row(f"case{index:03d}") for index in range(count)]
    relevance = [dict(row) for row in selection]
    manifest: list[dict[str, Any]] = []
    clearance: list[dict[str, Any]] = []
    restriction: list[dict[str, Any]] = []
    for row in selection:
        rows = _evidence_rows(str(row["candidate_id"]))
        manifest.extend(rows[0])
        clearance.extend(rows[1])
        restriction.extend(rows[2])
    from legalforecast.ingestion.core_document_filter import filter_core_documents

    core = [result.to_record() for result in filter_core_documents(relevance)]
    return {
        "selection": selection,
        "case_relevance": relevance,
        "download_manifest": manifest,
        "disclosure_clearance": clearance,
        "restriction_evidence": restriction,
        "core_filter_results": core,
    }


def _base(cohort: dict[str, Any] | None = None) -> Any:
    surface = cohort or _cohort()
    return mint_verified_exact100_v3_base(
        predecessor_run_card_bytes=b'{"synthetic": true}',
        predecessor_schema_version="legalforecast.synthetic_predecessor.v1",
        predecessor_stage="synthetic-predecessor",
        selection_rows=surface["selection"],
        case_relevance_rows=surface["case_relevance"],
        download_manifest_rows=surface["download_manifest"],
        disclosure_rows=surface["disclosure_clearance"],
        restriction_rows=surface["restriction_evidence"],
        core_filter_rows=surface["core_filter_results"],
        source_commitments={"predecessor": _sha(b"synthetic")},
    )


def _replacement_inputs(
    candidate_id: str,
    replaces: str,
    *,
    roles: tuple[tuple[str, str, int], ...] = _ROLES,
) -> dict[str, Any]:
    documents: list[dict[str, Any]] = []
    payloads: dict[str, bytes] = {}
    validations: dict[str, dict[str, Any]] = {}
    entries: dict[int, dict[str, Any]] = {}
    for _role, receipt_role, entry in roles:
        source_document_id = f"{candidate_id}-doc-{entry}"
        payload = _pdf_bytes(candidate_id, source_document_id)
        digest = hashlib.sha256(payload).hexdigest()
        payloads[source_document_id] = payload
        documents.append(
            {
                "byte_count": len(payload),
                "candidate_id": candidate_id,
                "docket_entry_number": entry,
                "document_role": receipt_role,
                "free_or_purchased": "purchased" if entry in {3, 4} else "free",
                "sha256": digest,
                "source_document_id": source_document_id,
                "source_url": None,
            }
        )
        validations[source_document_id] = {
            "encrypted": False,
            "pdf_byte_count": len(payload),
            "pdf_sha256": digest,
            "role_verdict": "match",
            "source_document_id": source_document_id,
            "strict_parse": "pass",
            "structural_defects": [],
            "validation_class": "document_repair_byte_role_verdict",
        }
        entries[entry] = {
            "entry_number": entry,
            "recap_documents": [{"id": source_document_id}],
        }
    return {
        "candidate_id": candidate_id,
        "replaces_candidate_id": replaces,
        "documents": documents,
        "document_bytes_by_id": payloads,
        "byte_role_validation_by_id": validations,
        "docket_entries_by_number": entries,
        "case_identity": {
            "case_name": f"Synthetic {candidate_id}",
            "court": "xxd",
            "docket_number": "1:26-cv-00001",
            "decision_date": "2026-07-01",
            "source_url": f"https://example.invalid/docket/{candidate_id}/",
        },
        "owner_disposition": {
            "excluded_candidate_id": replaces,
            "replacement_candidate_id": candidate_id,
            "owner_verbatim": "synthetic recorded owner text",
            "signoff_source": "synthetic fixture",
        },
        "field_provenance": {
            "case_name": "synthetic fixture",
            "court": "synthetic fixture",
            "docket_number": "synthetic fixture",
            "decision_date": "synthetic fixture",
            "source_url": "synthetic fixture",
        },
        "source_commitments": {"fixture": _sha(b"synthetic")},
    }


def _replacement(
    candidate_id: str, replaces: str
) -> VerifiedOwnerAdjudicatedReplacement:
    return mint_verified_owner_adjudicated_replacement(
        **_replacement_inputs(candidate_id, replaces)
    )


def _exclusion(
    candidate_id: str,
    *,
    selection_bytes: bytes,
    ground: TerminalExclusionGroundV2 = (
        TerminalExclusionGroundV2.STIPULATED_INELIGIBLE
    ),
) -> dict[str, Any]:
    detector = ground is not (
        TerminalExclusionGroundV2.OWNER_ADJUDICATED_RULE_41_A_2_VOLUNTARY_DISMISSAL
    )
    return {
        "candidate_id": candidate_id,
        "source_document_id": f"{candidate_id}-doc-2",
        "ground": ground.value,
        "evidence_commitments": (
            {"selection": _sha(selection_bytes), "audit": _sha(b"audit")}
            if detector
            else {}
        ),
        "owner_authorization_commitments": {"owner": _sha(b"owner")},
    }


# --------------------------------------------------------------------------
# Replacement evidence
# --------------------------------------------------------------------------


def test_replacement_evidence_seals_a_complete_owner_adjudicated_packet() -> None:
    replacement = _replacement("new1", "case000")

    assert replacement.candidate_id == "new1"
    assert replacement.replaces_candidate_id == "case000"
    assert len(replacement.download_manifest) == len(_ROLES)
    assert set(replacement.field_provenance) >= {"case_name", "court", "docket_number"}


def test_replacement_evidence_withholds_the_disposition_from_the_model() -> None:
    """Outcome leakage: the disposition is the one document the model must not see."""

    replacement = _replacement("new1", "case000")
    documents = {
        str(document["document_role"]): document
        for document in replacement.selection_row["documents"]
    }

    assert documents["decision"]["model_visible"] is False
    assert documents["decision"]["contains_target_outcome"] is True
    assert all(
        document["model_visible"] is True
        for role, document in documents.items()
        if role != "decision"
    )


def test_replacement_evidence_refuses_bytes_that_differ_from_the_receipt() -> None:
    inputs = _replacement_inputs("new1", "case000")
    key = next(iter(inputs["document_bytes_by_id"]))
    inputs["document_bytes_by_id"][key] = b"%PDF-1.7 tampered\n"

    with pytest.raises(
        OwnerAdjudicatedReplacementError, match="differ from the receipt"
    ):
        mint_verified_owner_adjudicated_replacement(**inputs)


def test_replacement_evidence_refuses_a_document_without_byte_role_validation() -> None:
    inputs = _replacement_inputs("new1", "case000")
    inputs["byte_role_validation_by_id"].pop(
        next(iter(inputs["byte_role_validation_by_id"]))
    )

    with pytest.raises(
        OwnerAdjudicatedReplacementError, match="no byte-role validation"
    ):
        mint_verified_owner_adjudicated_replacement(**inputs)


def test_replacement_evidence_refuses_a_role_verdict_that_is_not_a_match() -> None:
    inputs = _replacement_inputs("new1", "case000")
    key = next(iter(inputs["byte_role_validation_by_id"]))
    inputs["byte_role_validation_by_id"][key]["role_verdict"] = "mismatch"

    with pytest.raises(OwnerAdjudicatedReplacementError, match="not an exact match"):
        mint_verified_owner_adjudicated_replacement(**inputs)


def test_replacement_evidence_refuses_an_unrecorded_validation_regime() -> None:
    inputs = _replacement_inputs("new1", "case000")
    key = next(iter(inputs["byte_role_validation_by_id"]))
    inputs["byte_role_validation_by_id"][key].pop("validation_class")

    with pytest.raises(OwnerAdjudicatedReplacementError, match="validation regime"):
        mint_verified_owner_adjudicated_replacement(**inputs)


def test_replacement_evidence_refuses_an_incomplete_packet() -> None:
    roles = tuple(item for item in _ROLES if item[0] != "decision")
    inputs = _replacement_inputs("new1", "case000", roles=roles)

    with pytest.raises(OwnerAdjudicatedReplacementError, match="packet is incomplete"):
        mint_verified_owner_adjudicated_replacement(**inputs)


def test_replacement_evidence_refuses_a_role_outside_the_closed_map() -> None:
    inputs = _replacement_inputs("new1", "case000")
    inputs["documents"][0]["document_role"] = "some_new_tranche_label"

    with pytest.raises(OwnerAdjudicatedReplacementError, match="closed map"):
        mint_verified_owner_adjudicated_replacement(**inputs)


def test_replacement_evidence_refuses_a_disposition_naming_another_slot() -> None:
    inputs = _replacement_inputs("new1", "case000")
    inputs["owner_disposition"]["excluded_candidate_id"] = "case099"

    with pytest.raises(
        OwnerAdjudicatedReplacementError, match="does not name the excluded slot"
    ):
        mint_verified_owner_adjudicated_replacement(**inputs)


def test_replacement_evidence_refuses_a_document_absent_from_the_docket() -> None:
    inputs = _replacement_inputs("new1", "case000")
    inputs["docket_entries_by_number"].pop(1)

    with pytest.raises(OwnerAdjudicatedReplacementError, match="docket snapshot lacks"):
        mint_verified_owner_adjudicated_replacement(**inputs)


def test_replacement_evidence_refuses_missing_identity_provenance() -> None:
    inputs = _replacement_inputs("new1", "case000")
    inputs["field_provenance"].pop("case_name")

    with pytest.raises(
        OwnerAdjudicatedReplacementError, match="lack recorded provenance"
    ):
        mint_verified_owner_adjudicated_replacement(**inputs)


# --------------------------------------------------------------------------
# Terminal exclusions
# --------------------------------------------------------------------------


def test_terminal_exclusions_admit_more_than_one_candidate() -> None:
    base = _base()
    exclusions = mint_verified_exact100_v3_terminal_exclusions(
        selection_bytes=base.selection_bytes,
        exclusions=[
            _exclusion("case000", selection_bytes=base.selection_bytes),
            _exclusion("case001", selection_bytes=base.selection_bytes),
            _exclusion("case002", selection_bytes=base.selection_bytes),
        ],
    )

    assert exclusions.candidate_ids == ("case000", "case001", "case002")


def test_terminal_exclusions_admit_the_owner_judgment_ground() -> None:
    base = _base()
    exclusions = mint_verified_exact100_v3_terminal_exclusions(
        selection_bytes=base.selection_bytes,
        exclusions=[
            _exclusion(
                "case000",
                selection_bytes=base.selection_bytes,
                ground=(
                    TerminalExclusionGroundV2.OWNER_ADJUDICATED_RULE_41_A_2_VOLUNTARY_DISMISSAL
                ),
            )
        ],
    )

    record = exclusions.records[0]
    assert record["evidence_class"] == "recorded_owner_adjudication"
    assert record["evidence_commitments"] == {}


def test_terminal_exclusion_requires_an_owner_authorization_citation() -> None:
    base = _base()
    entry = _exclusion("case000", selection_bytes=base.selection_bytes)
    entry["owner_authorization_commitments"] = {}

    with pytest.raises(
        Exact100SuccessorReplacementV3Error, match="owner authorization citation"
    ):
        mint_verified_exact100_v3_terminal_exclusions(
            selection_bytes=base.selection_bytes, exclusions=[entry]
        )


def test_detector_exclusion_must_bind_the_predecessor_selection() -> None:
    base = _base()
    entry = _exclusion("case000", selection_bytes=base.selection_bytes)
    entry["evidence_commitments"]["selection"] = _sha(b"another selection")

    with pytest.raises(
        Exact100SuccessorReplacementV3Error, match="different exact selection"
    ):
        mint_verified_exact100_v3_terminal_exclusions(
            selection_bytes=base.selection_bytes, exclusions=[entry]
        )


def test_owner_judgment_exclusion_may_not_claim_detector_evidence() -> None:
    base = _base()
    entry = _exclusion(
        "case000",
        selection_bytes=base.selection_bytes,
        ground=(
            TerminalExclusionGroundV2.OWNER_ADJUDICATED_RULE_41_A_2_VOLUNTARY_DISMISSAL
        ),
    )
    entry["evidence_commitments"] = {"selection": _sha(base.selection_bytes)}

    with pytest.raises(
        Exact100SuccessorReplacementV3Error, match="must not claim detector evidence"
    ):
        mint_verified_exact100_v3_terminal_exclusions(
            selection_bytes=base.selection_bytes, exclusions=[entry]
        )


# --------------------------------------------------------------------------
# Projection
# --------------------------------------------------------------------------


def _projected(count: int = 3) -> Any:
    base = _base()
    slots = [f"case{index:03d}" for index in range(count)]
    exclusions = mint_verified_exact100_v3_terminal_exclusions(
        selection_bytes=base.selection_bytes,
        exclusions=[
            _exclusion(slot, selection_bytes=base.selection_bytes) for slot in slots
        ],
    )
    replacements = [
        _replacement(f"new{index}", slot) for index, slot in enumerate(slots)
    ]
    return project_exact100_successor_replacement_v3(
        base=base, terminal_exclusions=exclusions, replacements=replacements
    )


def test_three_paired_swaps_keep_the_cohort_at_exactly_100_unique_cases() -> None:
    result = _projected()
    ids = [row["candidate_id"] for row in result.selection]

    assert len(ids) == 100
    assert len(set(ids)) == 100
    assert {"case000", "case001", "case002"}.isdisjoint(ids)
    assert {"new0", "new1", "new2"} <= set(ids)
    assert result.state["selected_case_count"] == 100
    assert result.state["terminal_exclusion_count"] == 3
    assert result.state["promotion_count"] == 3


def test_every_promotion_records_its_provenance_class_explicitly() -> None:
    result = _projected()

    assert all(
        record["provenance_class"] == PromotionProvenanceClass.OWNER_ADJUDICATED.value
        for record in result.promotions
    )
    assert all(record["wider_rank"] is None for record in result.promotions)
    assert {record["replaces_candidate_id"] for record in result.promotions} == {
        "case000",
        "case001",
        "case002",
    }


def test_an_exclusion_without_its_paired_replacement_refuses() -> None:
    base = _base()
    exclusions = mint_verified_exact100_v3_terminal_exclusions(
        selection_bytes=base.selection_bytes,
        exclusions=[
            _exclusion("case000", selection_bytes=base.selection_bytes),
            _exclusion("case001", selection_bytes=base.selection_bytes),
        ],
    )

    with pytest.raises(
        Exact100SuccessorReplacementV3Error, match="exactly one paired replacement"
    ):
        project_exact100_successor_replacement_v3(
            base=base,
            terminal_exclusions=exclusions,
            replacements=[_replacement("new0", "case000")],
        )


def test_one_replacement_cannot_fill_two_slots() -> None:
    base = _base()
    exclusions = mint_verified_exact100_v3_terminal_exclusions(
        selection_bytes=base.selection_bytes,
        exclusions=[
            _exclusion("case000", selection_bytes=base.selection_bytes),
            _exclusion("case001", selection_bytes=base.selection_bytes),
        ],
    )

    with pytest.raises(
        Exact100SuccessorReplacementV3Error, match="promoted into two slots"
    ):
        project_exact100_successor_replacement_v3(
            base=base,
            terminal_exclusions=exclusions,
            replacements=[
                _replacement("new0", "case000"),
                _replacement("new0", "case001"),
            ],
        )


def test_a_replacement_already_in_the_cohort_refuses() -> None:
    base = _base()
    exclusions = mint_verified_exact100_v3_terminal_exclusions(
        selection_bytes=base.selection_bytes,
        exclusions=[_exclusion("case000", selection_bytes=base.selection_bytes)],
    )

    with pytest.raises(
        Exact100SuccessorReplacementV3Error, match="already inside the predecessor"
    ):
        project_exact100_successor_replacement_v3(
            base=base,
            terminal_exclusions=exclusions,
            replacements=[_replacement("case099", "case000")],
        )


def test_exclusions_bound_to_another_selection_refuse() -> None:
    base = _base()
    other = _base(_cohort(100))
    exclusions = mint_verified_exact100_v3_terminal_exclusions(
        selection_bytes=other.selection_bytes,
        exclusions=[_exclusion("case000", selection_bytes=other.selection_bytes)],
    )
    object.__setattr__(exclusions, "selection_sha256", _sha(b"forged"))

    with pytest.raises(
        Exact100SuccessorReplacementV3Error, match="different predecessor selection"
    ):
        project_exact100_successor_replacement_v3(
            base=base,
            terminal_exclusions=exclusions,
            replacements=[_replacement("new0", "case000")],
        )


def test_a_caller_constructed_replacement_is_rejected() -> None:
    base = _base()
    exclusions = mint_verified_exact100_v3_terminal_exclusions(
        selection_bytes=base.selection_bytes,
        exclusions=[_exclusion("case000", selection_bytes=base.selection_bytes)],
    )
    forged = object.__new__(VerifiedOwnerAdjudicatedReplacement)

    with pytest.raises(
        OwnerAdjudicatedReplacementError, match="not produced by verified minting"
    ):
        project_exact100_successor_replacement_v3(
            base=base, terminal_exclusions=exclusions, replacements=[forged]
        )


def test_methods_disclosure_names_the_owner_adjudicated_count_and_pairs() -> None:
    text = methods_disclosure_text(_projected())

    assert text.startswith("3 exact-100 replacements entered the cohort")
    assert "owner adjudication" in text
    assert "new0 for case000" in text


# --------------------------------------------------------------------------
# Evidence-root issuance and reauthentication
# --------------------------------------------------------------------------


def _write(path: Path, payload: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


def _issue_evidence_root(
    tmp_path: Path, candidate_id: str, replaces: str
) -> tuple[Path, dict[str, Path]]:
    """Write the synthetic receipts and mint one evidence root through the CLI."""

    inputs = _replacement_inputs(candidate_id, replaces)
    home = tmp_path / candidate_id
    documents_dir = home / "acquired"
    receipt_rows: list[dict[str, Any]] = []
    validation_rows: list[dict[str, Any]] = []
    for document in inputs["documents"]:
        source_document_id = str(document["source_document_id"])
        payload = inputs["document_bytes_by_id"][source_document_id]
        pdf_path = _write(documents_dir / f"{source_document_id}.pdf", payload)
        receipt_rows.append(
            {
                "candidate_id": candidate_id,
                "disposition": "included",
                "docket_entry_number": document["docket_entry_number"],
                "document_role": document["document_role"],
                "path": str(pdf_path),
                "sha256": document["sha256"],
                "source": (
                    "pacer_purchase"
                    if document["free_or_purchased"] == "purchased"
                    else "courtlistener_public"
                ),
                "source_document_id": source_document_id,
                "source_url": None,
            }
        )
        validation_rows.append(inputs["byte_role_validation_by_id"][source_document_id])
    receipt = _write(
        home / "acquired-documents.json", json.dumps(receipt_rows).encode()
    )
    validation = _write(
        home / "byte-role-validation.json",
        json.dumps({"records": validation_rows}).encode(),
    )
    snapshot = _write(
        home / "docket-snapshot.json",
        json.dumps(
            {
                "candidate_id": candidate_id,
                "docket_id": candidate_id,
                "entries": list(inputs["docket_entries_by_number"].values()),
            }
        ).encode(),
    )
    disposition = _write(
        home / "owner-disposition.json",
        json.dumps({"swaps": [inputs["owner_disposition"]]}).encode(),
    )
    plan = _write(
        home / "plan.json",
        json.dumps(
            {
                "schema_version": "legalforecast.owner_adjudicated_replacement_plan.v1",
                "candidate_id": candidate_id,
                "replaces_candidate_id": replaces,
                "case_identity": inputs["case_identity"],
                "field_provenance": inputs["field_provenance"],
                "documents": [
                    {"source_document_id": row["source_document_id"]}
                    for row in inputs["documents"]
                ],
            }
        ).encode(),
    )
    output_root = home / "evidence"
    exit_code = v3_cli.main(
        [
            "mint-replacement-evidence",
            "--plan",
            str(plan),
            "--docket-snapshot",
            str(snapshot),
            "--owner-disposition",
            str(disposition),
            "--acquisition-receipt",
            str(receipt),
            "--byte-role-validation",
            str(validation),
            "--output-root",
            str(output_root),
        ]
    )
    assert exit_code == 0
    return output_root, {"receipt": receipt, "plan": plan}


def test_minted_evidence_root_reauthenticates_from_its_own_run_card(
    tmp_path: Path,
) -> None:
    root, _ = _issue_evidence_root(tmp_path, "new1", "case000")

    replacement = verify_owner_adjudicated_replacement_evidence(root)

    assert replacement.candidate_id == "new1"
    assert replacement.replaces_candidate_id == "case000"


def test_reauthentication_refuses_when_a_source_document_changed(
    tmp_path: Path,
) -> None:
    root, paths = _issue_evidence_root(tmp_path, "new1", "case000")
    rows = json.loads(paths["receipt"].read_text())
    Path(rows[0]["path"]).write_bytes(b"%PDF-1.7 replaced after the mint\n")

    with pytest.raises(
        OwnerAdjudicatedReplacementCliError, match="differ from the receipt"
    ):
        verify_owner_adjudicated_replacement_evidence(root)


def test_reauthentication_refuses_a_stray_file_in_the_evidence_root(
    tmp_path: Path,
) -> None:
    root, _ = _issue_evidence_root(tmp_path, "new1", "case000")
    (root / "stray.json").write_bytes(b"{}")

    with pytest.raises(OwnerAdjudicatedReplacementCliError, match="unexpected paths"):
        verify_owner_adjudicated_replacement_evidence(root)


def test_the_console_script_reports_a_refusal_instead_of_raising(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = v3_cli.main(
        [
            "mint-replacement-evidence",
            "--plan",
            str(tmp_path / "absent.json"),
            "--docket-snapshot",
            str(tmp_path / "absent.json"),
            "--owner-disposition",
            str(tmp_path / "absent.json"),
            "--acquisition-receipt",
            str(tmp_path / "absent.json"),
            "--byte-role-validation",
            str(tmp_path / "absent.json"),
            "--output-root",
            str(tmp_path / "out"),
        ]
    )

    assert exit_code == 2
    assert "missing regular evidence file" in capsys.readouterr().err


def test_the_free_tranche_validation_shape_is_accepted_and_labelled(
    tmp_path: Path,
) -> None:
    """Free documents were cleared under a different regime; both are admitted."""

    from legalforecast.ingestion.exact100_successor_v3.replacement_evidence_cli import (
        _validation_index,  # pyright: ignore[reportPrivateUsage]
    )

    payload = json.dumps(
        {
            "strict_pdf_validation": {
                "all_pages_parsed": True,
                "all_documents_unencrypted": True,
                "documents": [
                    {
                        "source_document_id": "d1",
                        "role": "operative_pleading",
                        "sha256": "a" * 64,
                        "byte_count": 10,
                    }
                ],
            },
            "visual_validation": {"result": "pass"},
            "role_findings": {"d1": "synthetic"},
        }
    ).encode()

    index = _validation_index((payload,))

    assert index["d1"]["validation_class"] == (
        "free_tranche_strict_pdf_and_role_findings"
    )
    assert index["d1"]["role_verdict"] == "match"


def test_a_free_tranche_validation_that_did_not_clear_refuses() -> None:
    from legalforecast.ingestion.exact100_successor_v3.replacement_evidence_cli import (
        _validation_index,  # pyright: ignore[reportPrivateUsage]
    )

    payload = json.dumps(
        {
            "strict_pdf_validation": {
                "all_pages_parsed": False,
                "all_documents_unencrypted": True,
                "documents": [],
            },
            "visual_validation": {"result": "pass"},
            "role_findings": {},
        }
    ).encode()

    with pytest.raises(
        OwnerAdjudicatedReplacementCliError, match="does not clear every document"
    ):
        _validation_index((payload,))


# --------------------------------------------------------------------------
# Predecessor authentication
# --------------------------------------------------------------------------


def test_a_predecessor_root_without_a_recognised_run_card_refuses(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        v3_cli.Exact100SuccessorReplacementV3CliError, match="neither the sealed"
    ):
        v3_cli._verified_predecessor(tmp_path)  # pyright: ignore[reportPrivateUsage]


def test_a_cohort_head_whose_run_card_differs_from_the_anchor_refuses(
    tmp_path: Path,
) -> None:
    card = tmp_path / "run-cards/project-exact100-supporting-document-successor.json"
    _write(card, b'{"schema_version": "wrong"}')

    with pytest.raises(
        v3_cli.Exact100SuccessorReplacementV3CliError, match="sealed v3 anchor"
    ):
        v3_cli._verified_predecessor(tmp_path)  # pyright: ignore[reportPrivateUsage]


def test_a_v3_root_that_does_not_chain_to_the_anchor_refuses(tmp_path: Path) -> None:
    card = tmp_path / v3_cli._OUTPUT_NAMES["state"]  # pyright: ignore[reportPrivateUsage]
    _write(
        card,
        json.dumps(
            {
                "schema_version": v3_cli.STATE_SCHEMA_VERSION,
                "stage": v3_cli.STAGE,
                "status": "completed",
                "selected_case_count": 100,
                "predecessor_anchor_sha256": "b" * 64,
            }
        ).encode(),
    )

    with pytest.raises(
        v3_cli.Exact100SuccessorReplacementV3CliError,
        match="chain to the sealed anchor",
    ):
        v3_cli._verified_predecessor(tmp_path)  # pyright: ignore[reportPrivateUsage]


def test_the_lane_never_imports_the_monolithic_cli() -> None:
    """The architecture ratchet freezes the upward-import allowlist; stay off it."""

    package = Path(v3_cli.__file__).parent
    for module in sorted(package.glob("*.py")):
        source = module.read_text(encoding="utf-8")
        assert "legalforecast.cli" not in source, module.name


def test_the_audit_replay_uses_the_current_detector_generation() -> None:
    """The regime trap: a freshly minted audit must not replay as frozen.

    A fresh audit is persisted under today's detector, so selecting the
    contemporaneous frozen regime would re-derive a different ineligible set and
    refuse.  The replay must therefore leave ``frozen_predecessor_replay`` at its
    default.
    """

    source = Path(v3_cli.__file__).read_text(encoding="utf-8")
    replay_call = source[source.index("verify_stage_a_parse_lineage_uncached(") :]
    replay_call = replay_call[: replay_call.index(")")]

    assert "frozen_predecessor_replay" not in replay_call
