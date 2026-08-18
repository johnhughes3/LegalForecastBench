"""Behaviour of the v3 exact-100 successor console script.

Covers evidence-root issuance and reauthentication, predecessor authentication
for both the sealed cohort head and a chained v3 root, and the end-to-end
``project-successor-v3`` run.  Fixtures live in
:mod:`tests.exact100_successor_v3_fixtures`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from legalforecast.ingestion.exact100_successor_v3 import cli as v3_cli
from legalforecast.ingestion.exact100_successor_v3.replacement_evidence_cli import (
    OwnerAdjudicatedReplacementCliError,
    verify_owner_adjudicated_replacement_evidence,
)
from tests.exact100_successor_v3_fixtures import (
    _CARRIED_BYTES,
    _CARRIED_RELATIVE,
    _anchor_root,
    _carried_root,
    _issue_evidence_root,
    _jsonl_rows,
    _owner_judgment_file,
    _run_project,
    _write,
)


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


def test_carried_documents_are_checked_against_the_predecessor_commitments(
    tmp_path: Path,
) -> None:
    root, committed, payload = _carried_root(tmp_path)

    carried = v3_cli._carried_documents(root, committed)  # pyright: ignore[reportPrivateUsage]

    assert carried == {next(iter(committed)): payload}


def test_a_tampered_carried_document_refuses(tmp_path: Path) -> None:
    root, committed, _ = _carried_root(tmp_path)
    (root / next(iter(committed))).write_bytes(b"%PDF-1.7 tampered\n")

    with pytest.raises(
        v3_cli.Exact100SuccessorReplacementV3CliError,
        match="differs from its commitment",
    ):
        v3_cli._carried_documents(root, committed)  # pyright: ignore[reportPrivateUsage]


def test_an_uncommitted_carried_document_refuses(tmp_path: Path) -> None:
    root, committed, _ = _carried_root(tmp_path)
    _write(root / "supplemental-free-source/documents/smuggled.pdf", b"%PDF-1.7\n")

    with pytest.raises(
        v3_cli.Exact100SuccessorReplacementV3CliError, match="uncommitted document"
    ):
        v3_cli._carried_documents(root, committed)  # pyright: ignore[reportPrivateUsage]


def test_a_missing_committed_document_refuses(tmp_path: Path) -> None:
    root, committed, _ = _carried_root(tmp_path)
    (root / next(iter(committed))).unlink()

    with pytest.raises(
        v3_cli.Exact100SuccessorReplacementV3CliError, match="missing a committed"
    ):
        v3_cli._carried_documents(root, committed)  # pyright: ignore[reportPrivateUsage]


def test_a_v3_card_carrying_the_anchor_constant_still_has_to_replay(
    tmp_path: Path,
) -> None:
    """The anchor digest is public, so quoting it authenticates nothing."""

    card = tmp_path / v3_cli._OUTPUT_NAMES["state"]  # pyright: ignore[reportPrivateUsage]
    _write(
        card,
        json.dumps(
            {
                "schema_version": v3_cli.STATE_SCHEMA_VERSION,
                "stage": v3_cli.STAGE,
                "status": "completed",
                "selected_case_count": 100,
                "predecessor_anchor_sha256": v3_cli._ANCHOR_RUN_CARD_SHA256,  # pyright: ignore[reportPrivateUsage]
            }
        ).encode(),
    )

    with pytest.raises(
        v3_cli.Exact100SuccessorReplacementV3CliError, match="input roots"
    ):
        v3_cli._verified_predecessor(tmp_path)  # pyright: ignore[reportPrivateUsage]


# --------------------------------------------------------------------------
# project-successor-v3 end to end
# --------------------------------------------------------------------------


def test_project_successor_v3_publishes_a_complete_successor_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    anchor = _anchor_root(tmp_path, monkeypatch)
    evidence, _ = _issue_evidence_root(tmp_path, "new1", "case000")
    exclusion = _owner_judgment_file(tmp_path, "case000", "exclusion.json")
    output = tmp_path / "successor-1"

    assert (
        _run_project(
            predecessor=anchor, exclusion=exclusion, evidence=evidence, output=output
        )
        == 0
    )

    selection = _jsonl_rows(output / "target-cohort-selection.jsonl")
    ids = [row["candidate_id"] for row in selection]
    assert len(ids) == 100 and len(set(ids)) == 100
    assert "case000" not in ids and "new1" in ids
    # The promoted documents land where the manifest says they do.
    manifest = _jsonl_rows(output / "document-downloads-merged.jsonl")
    promoted = [row for row in manifest if row["candidate_id"] == "new1"]
    assert promoted
    for row in promoted:
        assert (
            output / "owner-adjudicated-source/documents" / str(row["local_path"])
        ).is_file()
    # The cohort head's carried document comes forward untouched.
    assert (output / _CARRIED_RELATIVE).read_bytes() == _CARRIED_BYTES
    disclosure = json.loads((output / "methods-disclosure.json").read_bytes())
    assert disclosure["owner_adjudicated_promotion_count"] == 1


def test_a_second_swap_chains_from_the_first_v3_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The fourth swap must not need a v4; it chains from the previous root."""

    anchor = _anchor_root(tmp_path, monkeypatch)
    first_evidence, _ = _issue_evidence_root(tmp_path, "new1", "case000")
    first = tmp_path / "successor-1"
    assert (
        _run_project(
            predecessor=anchor,
            exclusion=_owner_judgment_file(tmp_path, "case000", "e0.json"),
            evidence=first_evidence,
            output=first,
        )
        == 0
    )

    second_evidence, _ = _issue_evidence_root(tmp_path, "new2", "case001")
    second = tmp_path / "successor-2"
    assert (
        _run_project(
            predecessor=first,
            exclusion=_owner_judgment_file(tmp_path, "case001", "e1.json"),
            evidence=second_evidence,
            output=second,
        )
        == 0
    )

    ids = [
        row["candidate_id"]
        for row in _jsonl_rows(second / "target-cohort-selection.jsonl")
    ]
    assert len(ids) == 100 and len(set(ids)) == 100
    assert {"new1", "new2"} <= set(ids)
    assert {"case000", "case001"}.isdisjoint(ids)
    # Both the head's and the first swap's documents are still carried.
    assert (second / _CARRIED_RELATIVE).is_file()
    assert list((second / "owner-adjudicated-source/documents").iterdir())


def test_a_tampered_carried_document_stops_the_next_swap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    anchor = _anchor_root(tmp_path, monkeypatch)
    first_evidence, _ = _issue_evidence_root(tmp_path, "new1", "case000")
    first = tmp_path / "successor-1"
    assert (
        _run_project(
            predecessor=anchor,
            exclusion=_owner_judgment_file(tmp_path, "case000", "e0.json"),
            evidence=first_evidence,
            output=first,
        )
        == 0
    )
    (first / _CARRIED_RELATIVE).write_bytes(b"%PDF-1.7 swapped for the disposition\n")

    second_evidence, _ = _issue_evidence_root(tmp_path, "new2", "case001")
    assert (
        _run_project(
            predecessor=first,
            exclusion=_owner_judgment_file(tmp_path, "case001", "e1.json"),
            evidence=second_evidence,
            output=tmp_path / "successor-2",
        )
        == 2
    )


def test_projection_is_byte_stable_across_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    anchor = _anchor_root(tmp_path, monkeypatch)
    evidence, _ = _issue_evidence_root(tmp_path, "new1", "case000")
    exclusion = _owner_judgment_file(tmp_path, "case000", "e0.json")
    first, second = tmp_path / "run-a", tmp_path / "run-b"

    assert (
        _run_project(
            predecessor=anchor, exclusion=exclusion, evidence=evidence, output=first
        )
        == 0
    )
    assert (
        _run_project(
            predecessor=anchor, exclusion=exclusion, evidence=evidence, output=second
        )
        == 0
    )

    for name in ("target-cohort-selection.jsonl", "successor-promotions.jsonl"):
        assert (first / name).read_bytes() == (second / name).read_bytes()


def test_a_free_tranche_validation_without_a_finding_for_the_document_refuses() -> None:
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
            "role_findings": {"some-other-document": "synthetic"},
        }
    ).encode()

    with pytest.raises(OwnerAdjudicatedReplacementCliError, match="no role finding"):
        _validation_index((payload,))
