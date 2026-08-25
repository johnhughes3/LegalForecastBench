"""Behaviour of the v3 exact-100 successor console script.

Covers evidence-root issuance and reauthentication, predecessor authentication
for both the sealed cohort head and a chained v3 root, and the end-to-end
``project-successor-v3`` run.  Fixtures live in
:mod:`tests.exact100_successor_v3_fixtures`.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from legalforecast.evals.corpus_manifest import freeze_inputs as freeze_inputs_module
from legalforecast.ingestion.canonical_json import canonical_json_bytes
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


def test_the_free_tranche_shape_never_synthesises_a_role_verdict() -> None:
    """Strict-PDF validation proves the bytes parse, not what role they carry.

    role_findings is keyed by finding topic, and each topic cites several
    documents as corroborating quotes, so a document appearing there says
    nothing about its own role.
    """

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
            "role_findings": {"operative_pleading": {"verdict": "synthetic"}},
        }
    ).encode()

    index = _validation_index((payload,))

    assert index["d1"]["validation_class"] == "free_tranche_strict_pdf_only"
    assert index["d1"]["role_verdict"] == "unverified"


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


def _published_successor_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Produce one real synthetic v3 root for public-authentication tests."""

    anchor = _anchor_root(tmp_path, monkeypatch)
    evidence, _ = _issue_evidence_root(tmp_path, "new1", "case000")
    output = tmp_path / "successor-1"
    assert (
        _run_project(
            predecessor=anchor,
            exclusion=_owner_judgment_file(tmp_path, "case000", "e0.json"),
            evidence=evidence,
            output=output,
        )
        == 0
    )
    return output


def _rewrite_state_card(root: Path, card: dict[str, object]) -> None:
    (root / v3_cli._OUTPUT_NAMES["state"]).write_bytes(  # pyright: ignore[reportPrivateUsage]
        canonical_json_bytes(
            card,
            error_type=ValueError,
            error_message="synthetic state card serialization failed",
        )
    )


def test_public_authentication_refuses_methods_mutation_even_with_updated_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A self-updated methods commitment cannot replace replayed disclosure."""

    root = _published_successor_root(tmp_path, monkeypatch)
    methods_path = root / v3_cli._OUTPUT_NAMES["methods_disclosure"]  # pyright: ignore[reportPrivateUsage]
    methods = json.loads(methods_path.read_bytes())
    methods["disclosure_text"] += " tampered"
    mutated_methods = canonical_json_bytes(
        methods,
        error_type=ValueError,
        error_message="synthetic methods serialization failed",
    )
    methods_path.write_bytes(mutated_methods)

    card_path = root / v3_cli._OUTPUT_NAMES["state"]  # pyright: ignore[reportPrivateUsage]
    card = json.loads(card_path.read_bytes())
    card["output_commitments"][v3_cli._OUTPUT_NAMES["methods_disclosure"]] = (  # pyright: ignore[reportPrivateUsage]
        "sha256:" + hashlib.sha256(mutated_methods).hexdigest()
    )
    _rewrite_state_card(root, card)

    with pytest.raises(
        v3_cli.Exact100SuccessorReplacementV3CliError,
        match="state differs from its replay",
    ):
        v3_cli.authenticate_exact100_successor_v3_root(root)


def test_snapshot_authentication_returns_the_bytes_read_by_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _published_successor_root(tmp_path, monkeypatch)

    receipt, captured = v3_cli.authenticate_exact100_successor_v3_root_with_snapshot(
        root
    )

    assert receipt.root.resolve() == root.resolve()
    state = (root / v3_cli._OUTPUT_NAMES["state"]).absolute()  # pyright: ignore[reportPrivateUsage]
    assert captured[state] == state.read_bytes()
    carried = (root / _CARRIED_RELATIVE).absolute()
    assert captured[carried] == carried.read_bytes()
    assert captured


def test_snapshot_authentication_captures_replacement_bytes_after_nested_return(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The outer freeze recheck sees a source changed after replacement replay."""

    anchor = _anchor_root(tmp_path, monkeypatch)
    evidence, paths = _issue_evidence_root(tmp_path, "new1", "case000")
    output = tmp_path / "successor-1"
    assert (
        _run_project(
            predecessor=anchor,
            exclusion=_owner_judgment_file(tmp_path, "case000", "e0.json"),
            evidence=evidence,
            output=output,
        )
        == 0
    )
    source = Path(json.loads(paths["receipt"].read_text())[0]["path"])
    original = v3_cli.verify_owner_adjudicated_replacement_evidence

    def replay_then_mutate(root: Path) -> object:
        result = original(root)
        if root.absolute() == evidence.absolute():
            source.write_bytes(source.read_bytes() + b"post-replay mutation\n")
        return result

    monkeypatch.setattr(
        v3_cli, "verify_owner_adjudicated_replacement_evidence", replay_then_mutate
    )

    _receipt, captured = v3_cli.authenticate_exact100_successor_v3_root_with_snapshot(
        output
    )

    assert source.absolute() in captured
    with pytest.raises(
        freeze_inputs_module.ManifestFreezeInputsError,
        match="input changed before publication",
    ):
        freeze_inputs_module._require_snapshots_unchanged(captured)


def test_public_authentication_refuses_removed_promoted_document_commitment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _published_successor_root(tmp_path, monkeypatch)
    card_path = root / v3_cli._OUTPUT_NAMES["state"]  # pyright: ignore[reportPrivateUsage]
    card = json.loads(card_path.read_bytes())
    promoted = sorted(
        key
        for key in card["output_commitments"]
        if key.startswith("owner-adjudicated-source/documents/")
    )
    assert promoted
    del card["output_commitments"][promoted[0]]
    _rewrite_state_card(root, card)

    with pytest.raises(
        v3_cli.Exact100SuccessorReplacementV3CliError,
        match="state differs from its replay",
    ):
        v3_cli.authenticate_exact100_successor_v3_root(root)


def test_public_authentication_refuses_added_promoted_document_commitment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _published_successor_root(tmp_path, monkeypatch)
    extra_relative = "owner-adjudicated-source/documents/new1/extra.pdf"
    extra_payload = b"%PDF-1.7 synthetic extra promoted document\n"
    _write(root / extra_relative, extra_payload)

    card_path = root / v3_cli._OUTPUT_NAMES["state"]  # pyright: ignore[reportPrivateUsage]
    card = json.loads(card_path.read_bytes())
    card["output_commitments"][extra_relative] = (
        "sha256:" + hashlib.sha256(extra_payload).hexdigest()
    )
    _rewrite_state_card(root, card)

    with pytest.raises(
        v3_cli.Exact100SuccessorReplacementV3CliError,
        match="state differs from its replay",
    ):
        v3_cli.authenticate_exact100_successor_v3_root(root)


def test_public_authentication_refuses_traversal_commitment_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _published_successor_root(tmp_path, monkeypatch)
    traversal = "../outside-promoted-document.pdf"
    card_path = root / v3_cli._OUTPUT_NAMES["state"]  # pyright: ignore[reportPrivateUsage]
    card = json.loads(card_path.read_bytes())
    card["output_commitments"][traversal] = "sha256:" + "a" * 64
    _rewrite_state_card(root, card)

    with pytest.raises(
        v3_cli.Exact100SuccessorReplacementV3CliError,
        match="state differs from its replay",
    ):
        v3_cli.authenticate_exact100_successor_v3_root(root)


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


def test_a_document_with_only_strict_pdf_validation_refuses_at_the_mint() -> None:
    """The fail-closed half: an unverified role can never reach the packet."""

    from legalforecast.ingestion.exact100_successor_v3.replacement_evidence import (
        OwnerAdjudicatedReplacementError,
        mint_verified_owner_adjudicated_replacement,
    )
    from tests.exact100_successor_v3_fixtures import _replacement_inputs

    inputs = _replacement_inputs("new1", "case000")
    key = next(iter(inputs["byte_role_validation_by_id"]))
    inputs["byte_role_validation_by_id"][key]["role_verdict"] = "unverified"
    inputs["byte_role_validation_by_id"][key]["validation_class"] = (
        "free_tranche_strict_pdf_only"
    )

    with pytest.raises(
        OwnerAdjudicatedReplacementError, match="no per-document byte-role verdict"
    ):
        mint_verified_owner_adjudicated_replacement(**inputs)


def test_the_sealed_anchor_matches_the_real_cohort_head_when_it_is_available() -> None:
    """Catch a stale anchor pin here rather than at execution time.

    The end-to-end tests monkeypatch the anchor constants, which proves the
    authentication logic but says nothing about whether the pinned digests still
    describe the real cohort head.  This closes that gap where the artifacts
    tree is reachable, and skips where it is not, so the check runs for an
    operator and stays out of CI.  The path comes from the environment because
    this repository is public and must not carry local filesystem paths.
    """

    import os

    configured = os.environ.get("LFB_EXACT100_ANCHOR_ROOT")
    if not configured:
        pytest.skip("LFB_EXACT100_ANCHOR_ROOT is not set")
    card = (
        Path(configured)
        / "run-cards/project-exact100-supporting-document-successor.json"
    )
    if not card.is_file():
        pytest.skip("the configured cohort head is not present")

    payload = card.read_bytes()
    assert hashlib.sha256(payload).hexdigest() == v3_cli._ANCHOR_RUN_CARD_SHA256  # pyright: ignore[reportPrivateUsage]
    committed = json.loads(payload)["output_commitments"]
    for key, (relative, expected) in v3_cli._ANCHOR_OUTPUTS.items():  # pyright: ignore[reportPrivateUsage]
        assert str(committed[key]).removeprefix("sha256:") == expected, key
        assert (
            hashlib.sha256((Path(configured) / relative).read_bytes()).hexdigest()
            == expected
        ), relative


# --------------------------------------------------------------------------
# Owner-disposition shapes and the controls that guard them
# --------------------------------------------------------------------------


def _overlay_row(**overrides: object) -> bytes:
    """One record in the shape the owner disposition overlay actually uses."""

    row = {
        "candidate_id": "case000",
        "decision": "exclude_and_promote_replacement",
        "decision_source": "owner-dispositions-synthetic.md",
        "decision_source_sha256": "d" * 64,
        "decision_text": "EXCLUDE AND PROMOTE REPLACEMENT. Synthetic owner text.",
        "exclusion": {
            "replacement_candidate_id": "new1",
            "replacement_approved_by_owner": True,
            "reason": "synthetic recorded ground",
        },
    }
    row.update(overrides)
    return (json.dumps(row) + "\n").encode()


def _disposition(payload: bytes, path: Path) -> object:
    from legalforecast.ingestion.exact100_successor_v3.replacement_evidence_cli import (
        _owner_disposition,  # pyright: ignore[reportPrivateUsage]
    )

    return _owner_disposition(
        payload, path=path, candidate_id="new1", replaces_candidate_id="case000"
    )


def test_the_real_disposition_overlay_shape_is_accepted(tmp_path: Path) -> None:
    """The sitting's own overlay must satisfy the mint, or nothing can.

    Requiring a bespoke artifact instead would be enforcement without issuance,
    which is the failure this lane exists to stop repeating.
    """

    record = _disposition(_overlay_row(), tmp_path / "dispositions.jsonl")

    assert record == {  # pyright: ignore[reportUnknownMemberType]
        "excluded_candidate_id": "case000",
        "replacement_candidate_id": "new1",
        "owner_verbatim": "EXCLUDE AND PROMOTE REPLACEMENT. Synthetic owner text.",
        "signoff_source": "owner-dispositions-synthetic.md",
        "signoff_source_sha256": "d" * 64,
        "owner_stated_ground": "synthetic recorded ground",
    }


def test_a_proposed_but_unapproved_replacement_refuses(tmp_path: Path) -> None:
    """The fourth swap's real state: a proposal is not an approval."""

    payload = _overlay_row(
        exclusion={
            "replacement_candidate_id": None,
            "proposed_replacement_candidate_id": "new1",
            "replacement_approved_by_owner": False,
        }
    )

    with pytest.raises(
        OwnerAdjudicatedReplacementCliError, match="has not approved a replacement"
    ):
        _disposition(payload, tmp_path / "dispositions.jsonl")


def test_an_overlay_naming_a_different_replacement_refuses(tmp_path: Path) -> None:
    payload = _overlay_row(
        exclusion={
            "replacement_candidate_id": "someone-else",
            "replacement_approved_by_owner": True,
        }
    )

    with pytest.raises(
        OwnerAdjudicatedReplacementCliError, match="different replacement candidate"
    ):
        _disposition(payload, tmp_path / "dispositions.jsonl")


def test_an_overlay_that_does_not_exclude_refuses(tmp_path: Path) -> None:
    payload = _overlay_row(decision="accept_existing_audit_repair")

    with pytest.raises(
        OwnerAdjudicatedReplacementCliError, match="does not exclude and promote"
    ):
        _disposition(payload, tmp_path / "dispositions.jsonl")


def test_an_owner_judgment_exclusion_without_a_signoff_source_refuses(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path / "exclusion.json",
        json.dumps(
            {
                "candidate_id": "case000",
                "source_document_id": "case000-doc-2",
                "ground": "owner_adjudicated_rule_41_a_2_voluntary_dismissal",
                "owner_disposition": {
                    "artifact_sha256": "sha256:" + "c" * 64,
                    "owner_verbatim": "synthetic recorded owner text",
                },
            }
        ).encode(),
    )

    with pytest.raises(
        v3_cli.Exact100SuccessorReplacementV3CliError, match="signoff_source"
    ):
        v3_cli._owner_judgment_exclusion(path)  # pyright: ignore[reportPrivateUsage]


def test_an_owner_judgment_exclusion_without_recorded_owner_text_refuses(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path / "exclusion.json",
        json.dumps(
            {
                "candidate_id": "case000",
                "source_document_id": "case000-doc-2",
                "ground": "owner_adjudicated_rule_41_a_2_voluntary_dismissal",
                "owner_disposition": {
                    "artifact_sha256": "sha256:" + "c" * 64,
                    "signoff_source": "synthetic fixture",
                },
            }
        ).encode(),
    )

    with pytest.raises(
        v3_cli.Exact100SuccessorReplacementV3CliError, match="owner_verbatim"
    ):
        v3_cli._owner_judgment_exclusion(path)  # pyright: ignore[reportPrivateUsage]


def test_a_predecessor_chain_longer_than_the_cap_refuses(tmp_path: Path) -> None:
    """A cycle in input_roots must refuse, not exhaust the interpreter stack."""

    with pytest.raises(
        v3_cli.Exact100SuccessorReplacementV3CliError, match="longer than the supported"
    ):
        v3_cli._project(  # pyright: ignore[reportPrivateUsage]
            predecessor_root=tmp_path,
            stipulated_roots=(),
            owner_exclusions=(),
            replacement_roots=(),
            depth=v3_cli._MAX_PREDECESSOR_CHAIN_DEPTH + 1,  # pyright: ignore[reportPrivateUsage]
        )
