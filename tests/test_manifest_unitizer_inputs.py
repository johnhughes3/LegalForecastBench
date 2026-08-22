# pyright: reportPrivateUsage=false
"""Provider-free tests for the manifest/document-store unitizer adapter."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from legalforecast.evals.corpus_manifest import unitizer as unitizer_module
from legalforecast.evals.corpus_manifest.stage51_r2 import (
    _file_commitment,
    _preflight_r2_outputs,
    _write_jsonl_output,
)
from legalforecast.evals.corpus_manifest.unitizer import (
    AuthenticatedFinalizedOverlay,
    ManifestUnitizerCommandError,
    ManifestUnitizerInputError,
    PreparedManifestUnitizerInputs,
    _provider_account,
    authenticate_finalized_overlay,
    prepare_manifest_unitizer_inputs,
)
from legalforecast.evals.corpus_manifest.unitizer_publication import _write_stage_card
from legalforecast.evals.corpus_manifest.unitizer_shared import _citation_span_pages
from legalforecast.labeling.llm_pipeline import LlmBatchResult
from legalforecast.labeling.provider_journal import (
    load_provider_cycle_caps,
    load_provider_cycle_caps_bytes,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

_UNITS_APPROVAL = "units: approved — ceiling USD 5.00 extends to the fifth fresh case"
_PROMPT_CONTRACT = unitizer_module.STAGE_A_CLAIM_ONTOLOGY_V5_PROMPT_CONTRACT
_FRESH_IDS = tuple(f"synthetic-fresh-{number}" for number in range(1, 6))
_CHANGED_ID = "synthetic-changed-material"


@pytest.fixture(autouse=True)
def _use_synthetic_frozen_fresh_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        unitizer_module, "_CYCLE1_FRESH_CANDIDATE_IDS", frozenset(_FRESH_IDS)
    )
    monkeypatch.setattr(
        unitizer_module,
        "_CYCLE1_REPROCESSED_CANDIDATE_IDS",
        frozenset({_CHANGED_ID}),
    )


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _fixture(
    tmp_path: Path,
    *,
    count: int = 2,
    candidate_ids: tuple[str, ...] | None = None,
) -> tuple[Path, Path, Path]:
    selection_path = tmp_path / "selection.jsonl"
    store = tmp_path / "store"
    verdict_path = tmp_path / "verdicts.jsonl"
    verdicts: list[dict[str, object]] = []
    selection: list[dict[str, object]] = []
    candidates = candidate_ids or tuple(
        f"synthetic-candidate-{number}" for number in range(1, count + 1)
    )
    for number, candidate in enumerate(candidates, start=1):
        complaint = f"{candidate}-complaint"
        motion = f"{candidate}-motion"
        claim_role = "crossclaim" if number == 1 else "complaint"
        documents: list[dict[str, object]] = []
        for document_id, role, entry, text in (
            (complaint, claim_role, 1, "Count I\nThe complaint alleges a claim."),
            (
                motion,
                "motion_to_dismiss_memorandum",
                2,
                "The motion challenges Count I.",
            ),
        ):
            pdf_path = store / candidate / f"{document_id}.pdf"
            markdown_path = store / candidate / f"{document_id}.md"
            pdf_path.parent.mkdir(parents=True, exist_ok=True)
            pdf_bytes = f"%PDF synthetic {document_id}".encode()
            pdf_path.write_bytes(pdf_bytes)
            markdown_path.write_text(text, encoding="utf-8")
            markdown_path.with_suffix(".metadata.json").write_text(
                json.dumps(
                    {
                        "candidate_id": candidate,
                        "source_document_id": document_id,
                        "status": "succeeded",
                        "input_path": str(pdf_path),
                        "markdown_path": markdown_path.name,
                        "source_sha256": hashlib.sha256(pdf_bytes).hexdigest(),
                        "extracted_text": {
                            "text_sha256": hashlib.sha256(
                                markdown_path.read_bytes()
                            ).hexdigest()
                        },
                    }
                ),
                encoding="utf-8",
            )
            documents.append(
                {
                    "source_document_id": document_id,
                    "document_role": role,
                    "model_visible": True,
                    "is_predecision_material": True,
                    "contains_target_outcome": False,
                    "docket_entry_number": entry,
                }
            )
            verdicts.append(
                {
                    "source_document_id": document_id,
                    "verdict": "match",
                    "expected_role": role,
                }
            )
        selection.append(
            {
                "candidate_id": candidate,
                "case_id": f"case-{number}",
                "court": "D. Synthetic",
                "docket_number": f"1:26-cv-{number:05d}",
                "target_motion_entry_numbers": [2],
                "decision_entry_numbers": [9],
                "selected": True,
                "documents": documents,
            }
        )
    selection_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in selection),
        encoding="utf-8",
    )
    _write_jsonl(verdict_path, verdicts)
    return selection_path, store, verdict_path


def test_manifest_unitizer_uses_default_account_for_legacy_caps() -> None:
    caps = load_provider_cycle_caps(
        REPO_ROOT
        / "model_registries/cycle-1-target-100-provider-caps-base-2026-07-28.json"
    )

    assert _provider_account(caps, "anthropic") == "default"


def test_prepare_manifest_unitizer_inputs_binds_exact_selection_and_bytes(
    tmp_path: Path,
) -> None:
    selection, store, verdicts = _fixture(tmp_path)

    prepared = prepare_manifest_unitizer_inputs(
        selection_path=selection,
        document_store_roots=(store,),
        verdict_sources=(verdicts,),
        expected_verdict_source_sha256=(
            hashlib.sha256(verdicts.read_bytes()).hexdigest(),
        ),
        target_case_count=2,
    )

    assert [row["candidate_id"] for row in prepared.selection_records] == [
        "synthetic-candidate-1",
        "synthetic-candidate-2",
    ]
    assert len(prepared.parser_records) == 4
    assert len(prepared.markdown_bytes) == 4
    assert all(
        document["is_predecision_material"] is True
        and document["contains_target_outcome"] is False
        for row in prepared.selection_records
        for document in row["documents"]
    )
    assert (
        prepared.selection_sha256 == hashlib.sha256(selection.read_bytes()).hexdigest()
    )
    assert all(
        commitment["pdf_sha256"]
        for commitment in prepared.document_commitments.values()
    )


def test_prepare_manifest_unitizer_inputs_refuses_markdown_digest_drift(
    tmp_path: Path,
) -> None:
    selection, store, verdicts = _fixture(tmp_path)
    markdown = next(store.rglob("*.md"))
    markdown.write_text("tampered markdown", encoding="utf-8")

    with pytest.raises(ManifestUnitizerInputError, match="text_sha256"):
        prepare_manifest_unitizer_inputs(
            selection_path=selection,
            document_store_roots=(store,),
            verdict_sources=(verdicts,),
            expected_verdict_source_sha256=(
                hashlib.sha256(verdicts.read_bytes()).hexdigest(),
            ),
            target_case_count=2,
        )


def test_prepare_manifest_unitizer_inputs_refuses_verdict_digest_drift(
    tmp_path: Path,
) -> None:
    selection, store, verdicts = _fixture(tmp_path)

    with pytest.raises(ManifestUnitizerInputError, match="verdict source digest"):
        prepare_manifest_unitizer_inputs(
            selection_path=selection,
            document_store_roots=(store,),
            verdict_sources=(verdicts,),
            expected_verdict_source_sha256=("0" * 64,),
            target_case_count=2,
        )


def test_prepare_manifest_unitizer_inputs_trusts_certified_not_claimed_role(
    tmp_path: Path,
) -> None:
    selection, store, verdicts = _fixture(tmp_path)
    rows = [json.loads(line) for line in verdicts.read_text().splitlines()]
    rows[0]["manifest_role"] = "complaint"
    rows[0]["expected_role"] = "cover_sheet"
    _write_jsonl(verdicts, rows)

    with pytest.raises(ManifestUnitizerInputError, match="certified role"):
        prepare_manifest_unitizer_inputs(
            selection_path=selection,
            document_store_roots=(store,),
            verdict_sources=(verdicts,),
            expected_verdict_source_sha256=(
                hashlib.sha256(verdicts.read_bytes()).hexdigest(),
            ),
            target_case_count=2,
        )


def _canonical_sha256(record: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            record, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()


def _write_text(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def _prediction_unit(candidate_id: str, *, claim_document: str) -> dict[str, Any]:
    return {
        "unit_id": f"{candidate_id}-count-i",
        "count": "Count I",
        "claim_name": "synthetic claim",
        "defendant_group": "Synthetic Defendant",
        "challenged_by_motion": True,
        "challenge_scope": "entire_claim",
        "unit_confidence": 0.95,
        "source_citations": [
            {
                "document_id": claim_document,
                "docket_entry_number": 1,
                "page": None,
                "paragraph": None,
                "excerpt": "Count I\nThe complaint alleges a claim.",
            },
            {
                "document_id": f"{candidate_id}-motion",
                "docket_entry_number": 2,
                "page": None,
                "paragraph": None,
                "excerpt": "The motion challenges Count I.",
            },
        ],
        "grouping": "individual",
        "grouping_rationale": None,
        "separable_subclaim": None,
        "uncertainty_notes": None,
        "should_score": True,
    }


def _overlay_fixture(
    tmp_path: Path,
    *,
    fresh_ids: tuple[str, ...] | None = None,
) -> tuple[
    PreparedManifestUnitizerInputs,
    Path,
    Path,
    tuple[str, ...],
    dict[str, Any],
]:
    current_candidates = (
        *tuple(f"synthetic-candidate-{number}" for number in range(1, 95)),
        _CHANGED_ID,
        *_FRESH_IDS,
    )
    selection_path, store, verdicts = _fixture(
        tmp_path, candidate_ids=current_candidates
    )
    prepared = prepare_manifest_unitizer_inputs(
        selection_path=selection_path,
        document_store_roots=(store,),
        verdict_sources=(verdicts,),
        expected_verdict_source_sha256=(
            hashlib.sha256(verdicts.read_bytes()).hexdigest(),
        ),
        target_case_count=100,
    )
    if fresh_ids is None:
        fresh_ids = _FRESH_IDS
    selection_by_candidate = {
        str(row["candidate_id"]): row for row in prepared.selection_records
    }
    prior_candidates = [
        *[f"synthetic-candidate-{number}" for number in range(1, 95)],
        _CHANGED_ID,
        *[f"synthetic-predecessor-{number}" for number in range(1, 6)],
    ]
    retained: list[dict[str, Any]] = []
    for candidate_id in prior_candidates:
        selection = selection_by_candidate.get(candidate_id)
        claim_document = f"{candidate_id}-complaint"
        unit = _prediction_unit(candidate_id, claim_document=claim_document)
        retained.append(
            {
                "candidate_id": candidate_id,
                "case_id": (
                    selection["case_id"]
                    if selection is not None
                    else f"case-{candidate_id}"
                ),
                "prediction_units": [unit],
            }
        )

    base_records = json.loads(json.dumps(retained))
    base_by_candidate = {row["candidate_id"]: row for row in base_records}
    overlay_by_candidate = {row["candidate_id"]: row for row in retained}
    packet_candidate_ids = tuple(
        f"synthetic-candidate-{number}" for number in range(1, 4)
    )
    sole_candidate_id = "synthetic-candidate-4"
    packet_candidates: list[dict[str, Any]] = []
    packet_unit_sha256: dict[str, str] = {}
    for candidate_id in packet_candidate_ids:
        replacement = json.loads(
            json.dumps(base_by_candidate[candidate_id]["prediction_units"][0])
        )
        replacement["uncertainty_notes"] = "Owner-approved packet replacement."
        overlay_by_candidate[candidate_id]["prediction_units"] = [replacement]
        digest = _canonical_sha256(replacement)
        packet_unit_sha256[replacement["unit_id"]] = digest
        packet_candidates.append(
            {
                "candidate_id": candidate_id,
                "prediction_units": [replacement],
                "prediction_unit_sha256": {replacement["unit_id"]: digest},
            }
        )
    sole_unit = json.loads(
        json.dumps(base_by_candidate[sole_candidate_id]["prediction_units"][0])
    )
    sole_unit["uncertainty_notes"] = "Owner-approved sole-unit replacement."
    overlay_by_candidate[sole_candidate_id]["prediction_units"] = [sole_unit]

    overlay_path = _write_text(
        tmp_path / "finalized-overlay.jsonl",
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in retained),
    )
    packet = {
        "candidate_order": list(packet_candidate_ids),
        "candidates": packet_candidates,
    }
    worksheet = (
        "candidate_id\tdecision_status\tfinalized_units_json\n"
        f"{sole_candidate_id}\tfinal\t"
        f"{json.dumps([sole_unit], separators=(',', ':'))}\n"
    )
    source_paths = {
        "base_prediction_units": _write_text(
            tmp_path / "base.jsonl",
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in base_records),
        ),
        "packet": _write_text(
            tmp_path / "packet.json", json.dumps(packet, sort_keys=True) + "\n"
        ),
        "owner_ruling_source": _write_text(
            tmp_path / "ruling.txt",
            f"{sole_candidate_id}: approved as the sole frozen prediction unit.\n",
        ),
        "worksheet_source": _write_text(tmp_path / "worksheet.tsv", worksheet),
    }
    overlay_sha256 = hashlib.sha256(overlay_path.read_bytes()).hexdigest()
    packet_sha256 = hashlib.sha256(source_paths["packet"].read_bytes()).hexdigest()
    integration = {
        "artifact": "legalforecast.cycle1.stage51_finalized_units_integration.v1",
        "output": str(overlay_path.resolve()),
        "output_sha256": overlay_sha256,
        "candidate_count": 100,
        "unit_count": 100,
        "scorable_unit_count": 100,
        "base_prediction_units": str(source_paths["base_prediction_units"].resolve()),
        "base_sha256": hashlib.sha256(
            source_paths["base_prediction_units"].read_bytes()
        ).hexdigest(),
        "packet": str(source_paths["packet"].resolve()),
        "packet_sha256": packet_sha256,
        "owner_ruling_source": str(source_paths["owner_ruling_source"].resolve()),
        "owner_ruling_sha256": hashlib.sha256(
            source_paths["owner_ruling_source"].read_bytes()
        ).hexdigest(),
        "worksheet_source": str(source_paths["worksheet_source"].resolve()),
        "worksheet_sha256": hashlib.sha256(
            source_paths["worksheet_source"].read_bytes()
        ).hexdigest(),
        "replaced_candidates": {
            **{candidate_id: 1 for candidate_id in packet_candidate_ids},
            sole_candidate_id: 1,
        },
        "packet_unit_sha256": packet_unit_sha256,
        f"{sole_candidate_id}_finalized_unit_sha256": _canonical_sha256(sole_unit),
    }
    integration_path = _write_text(
        tmp_path / "integration-manifest.json",
        json.dumps(integration, sort_keys=True) + "\n",
    )
    return prepared, overlay_path, integration_path, fresh_ids, integration


def _authenticate_fixture(
    tmp_path: Path,
) -> tuple[
    AuthenticatedFinalizedOverlay,
    PreparedManifestUnitizerInputs,
    Path,
    Path,
    tuple[str, ...],
    dict[str, Any],
]:
    prepared, overlay, integration_path, fresh_ids, integration = _overlay_fixture(
        tmp_path
    )
    authenticated = authenticate_finalized_overlay(
        finalized_units_path=overlay,
        integration_manifest_path=integration_path,
        prepared=prepared,
        expected_selection_sha256=prepared.selection_sha256,
        expected_overlay_sha256=hashlib.sha256(overlay.read_bytes()).hexdigest(),
        expected_integration_manifest_sha256=hashlib.sha256(
            integration_path.read_bytes()
        ).hexdigest(),
        owner_approval_reference="legalforecastbench-3ak.38",
        stage51_packet_approval=(
            f"stage51-terminal-units: approved — packet {integration['packet_sha256']}"
        ),
        units_spend_approval=_UNITS_APPROVAL,
    )
    return authenticated, prepared, overlay, integration_path, fresh_ids, integration


def test_authenticate_finalized_overlay_accepts_exact_94_retained_5_fresh_1_reprocessed(
    tmp_path: Path,
) -> None:
    authenticated, prepared, _, _, fresh_ids, _ = _authenticate_fixture(tmp_path)

    assert len(authenticated.retained_records) == 94
    assert len(authenticated.fresh_selection_records) == 5
    assert len(authenticated.reprocessed_records) == 1
    assert authenticated.reprocessed_candidate_ids == (_CHANGED_ID,)
    assert [row["candidate_id"] for row in authenticated.retained_records] == [
        row["candidate_id"]
        for row in prepared.selection_records
        if row["candidate_id"] not in fresh_ids and row["candidate_id"] != _CHANGED_ID
    ]
    assert [
        row["candidate_id"] for row in authenticated.fresh_selection_records
    ] == list(fresh_ids)


@pytest.mark.parametrize("mutation", ("extra", "missing", "mismatched"))
def test_authenticate_finalized_overlay_refuses_partition_tampering(
    tmp_path: Path, mutation: str
) -> None:
    _, prepared, overlay, integration_path, _, integration = _authenticate_fixture(
        tmp_path
    )
    rows = [json.loads(line) for line in overlay.read_text().splitlines()]
    if mutation == "extra":
        candidate_id = "synthetic-extra"
        unit = _prediction_unit(
            candidate_id, claim_document="synthetic-candidate-1-complaint"
        )
        rows.append(
            {
                "candidate_id": candidate_id,
                "case_id": "extra",
                "prediction_units": [unit],
            }
        )
        integration["candidate_count"] = 95
        integration["unit_count"] = 95
        integration["scorable_unit_count"] = 95
    elif mutation == "missing":
        rows.pop()
        integration["candidate_count"] = 93
        integration["unit_count"] = 93
        integration["scorable_unit_count"] = 93
    else:
        rows[0]["case_id"] = "wrong-case-id"
    overlay.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
    integration["output_sha256"] = hashlib.sha256(overlay.read_bytes()).hexdigest()
    integration_path.write_text(json.dumps(integration, sort_keys=True) + "\n")

    with pytest.raises(ManifestUnitizerCommandError):
        authenticate_finalized_overlay(
            finalized_units_path=overlay,
            integration_manifest_path=integration_path,
            prepared=prepared,
            expected_selection_sha256=prepared.selection_sha256,
            expected_overlay_sha256=hashlib.sha256(overlay.read_bytes()).hexdigest(),
            expected_integration_manifest_sha256=hashlib.sha256(
                integration_path.read_bytes()
            ).hexdigest(),
            owner_approval_reference="legalforecastbench-3ak.38",
            stage51_packet_approval=(
                "stage51-terminal-units: approved — packet "
                f"{integration['packet_sha256']}"
            ),
            units_spend_approval=_UNITS_APPROVAL,
        )


def test_authenticate_finalized_overlay_rejects_rehashed_retained_unit_drift(
    tmp_path: Path,
) -> None:
    _, prepared, overlay, integration_path, _, integration = _authenticate_fixture(
        tmp_path
    )
    rows = [json.loads(line) for line in overlay.read_text().splitlines()]
    retained = next(
        row for row in rows if row["candidate_id"] == "synthetic-candidate-10"
    )
    retained["prediction_units"][0]["claim_name"] = "Operator-mutated claim"
    overlay.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
    integration["output_sha256"] = hashlib.sha256(overlay.read_bytes()).hexdigest()
    integration_path.write_text(json.dumps(integration, sort_keys=True) + "\n")

    with pytest.raises(ManifestUnitizerCommandError, match="not derived"):
        authenticate_finalized_overlay(
            finalized_units_path=overlay,
            integration_manifest_path=integration_path,
            prepared=prepared,
            expected_selection_sha256=prepared.selection_sha256,
            expected_overlay_sha256=hashlib.sha256(overlay.read_bytes()).hexdigest(),
            expected_integration_manifest_sha256=hashlib.sha256(
                integration_path.read_bytes()
            ).hexdigest(),
            owner_approval_reference="legalforecastbench-3ak.38",
            stage51_packet_approval=(
                "stage51-terminal-units: approved — packet "
                f"{integration['packet_sha256']}"
            ),
            units_spend_approval=_UNITS_APPROVAL,
        )


def test_authenticate_finalized_overlay_rejects_outcome_or_predecision_drift(
    tmp_path: Path,
) -> None:
    _, prepared, overlay, integration_path, _, integration = _authenticate_fixture(
        tmp_path
    )
    rows = [dict(row) for row in prepared.selection_records]
    documents = [dict(document) for document in rows[0]["documents"]]
    documents[0]["contains_target_outcome"] = True
    rows[0]["documents"] = documents
    tampered_prepared = PreparedManifestUnitizerInputs(
        selection_records=tuple(rows),
        parser_records=prepared.parser_records,
        markdown_root=prepared.markdown_root,
        markdown_bytes=prepared.markdown_bytes,
        selection_sha256=prepared.selection_sha256,
        verdict_source_sha256=prepared.verdict_source_sha256,
        document_commitments=prepared.document_commitments,
    )
    with pytest.raises(ManifestUnitizerCommandError, match="outcome-free"):
        authenticate_finalized_overlay(
            finalized_units_path=overlay,
            integration_manifest_path=integration_path,
            prepared=tampered_prepared,
            expected_selection_sha256=prepared.selection_sha256,
            expected_overlay_sha256=hashlib.sha256(overlay.read_bytes()).hexdigest(),
            expected_integration_manifest_sha256=hashlib.sha256(
                integration_path.read_bytes()
            ).hexdigest(),
            owner_approval_reference="legalforecastbench-3ak.38",
            stage51_packet_approval=(
                "stage51-terminal-units: approved — packet "
                f"{integration['packet_sha256']}"
            ),
            units_spend_approval=_UNITS_APPROVAL,
        )


def test_citation_mismatch_requires_moving_case_to_fresh_set(
    tmp_path: Path,
) -> None:
    (
        _,
        alternate_prepared,
        alternate_overlay,
        alternate_manifest,
        _,
        alternate_integration,
    ) = _authenticate_fixture(tmp_path)
    # A changed retained citation requires the corrected Stage-51 overlay; it
    # must not be silently converted into an owner-authorized fresh case.
    rows = [json.loads(line) for line in alternate_overlay.read_text().splitlines()]
    retained_94 = next(
        row for row in rows if row["candidate_id"] == "synthetic-candidate-94"
    )
    retained_94["prediction_units"][0]["source_citations"][0]["excerpt"] = (
        "Count I\nA different pleading was substituted."
    )
    alternate_overlay.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
    )
    alternate_integration["output_sha256"] = hashlib.sha256(
        alternate_overlay.read_bytes()
    ).hexdigest()
    alternate_manifest.write_text(
        json.dumps(alternate_integration, sort_keys=True) + "\n"
    )

    with pytest.raises(ManifestUnitizerCommandError, match="not derived"):
        authenticate_finalized_overlay(
            finalized_units_path=alternate_overlay,
            integration_manifest_path=alternate_manifest,
            prepared=alternate_prepared,
            expected_selection_sha256=alternate_prepared.selection_sha256,
            expected_overlay_sha256=hashlib.sha256(
                alternate_overlay.read_bytes()
            ).hexdigest(),
            expected_integration_manifest_sha256=hashlib.sha256(
                alternate_manifest.read_bytes()
            ).hexdigest(),
            owner_approval_reference="legalforecastbench-3ak.38",
            stage51_packet_approval=(
                "stage51-terminal-units: approved — packet "
                f"{alternate_integration['packet_sha256']}"
            ),
            units_spend_approval=_UNITS_APPROVAL,
        )


def test_authenticate_finalized_overlay_uses_one_markdown_snapshot(
    tmp_path: Path,
) -> None:
    authenticated, prepared, overlay, integration_path, _, integration = (
        _authenticate_fixture(tmp_path)
    )
    # The on-disk source can change after preparation; authentication must use
    # the exact bytes captured in ``prepared`` for the entire operation.
    markdown_path = next(iter(prepared.markdown_bytes))
    (prepared.markdown_root / markdown_path).write_text("TOCTOU replacement\n")

    again = authenticate_finalized_overlay(
        finalized_units_path=overlay,
        integration_manifest_path=integration_path,
        prepared=prepared,
        expected_selection_sha256=prepared.selection_sha256,
        expected_overlay_sha256=hashlib.sha256(overlay.read_bytes()).hexdigest(),
        expected_integration_manifest_sha256=hashlib.sha256(
            integration_path.read_bytes()
        ).hexdigest(),
        owner_approval_reference="legalforecastbench-3ak.38",
        stage51_packet_approval=(
            f"stage51-terminal-units: approved — packet {integration['packet_sha256']}"
        ),
        units_spend_approval=_UNITS_APPROVAL,
    )
    assert again == authenticated


def test_manifest_unitizer_replays_only_the_approved_five(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, prepared, overlay, integration_path, fresh_ids, integration = (
        _authenticate_fixture(tmp_path)
    )
    calls: list[tuple[str, ...]] = []

    class _Cap:
        account = None

    class _Caps:
        def __init__(self) -> None:
            self.cycle_id = "synthetic-cycle"
            self.providers = {"synthetic": _Cap()}

        @staticmethod
        def cap_usd(provider: str) -> float:
            assert provider == "synthetic"
            return 5.0

    class _RegistryEntry:
        registry_key = "synthetic-model"
        provider = "synthetic"

    class _Registry:
        entries = (_RegistryEntry(),)

    def fake_load_caps(payload: bytes, *, source: Path | str) -> _Caps:
        assert payload == b"{}"
        assert source == args.provider_cycle_caps
        return _Caps()

    def fake_load_registry(payload: bytes) -> _Registry:
        assert payload == b"[]"
        return _Registry()

    def fake_verify_identity(*args: object, **kwargs: object) -> None:
        return None

    def fake_adopt(**kwargs: Any) -> LlmBatchResult:
        selected = tuple(
            str(row["candidate_id"]) for row in kwargs["selection_records"]
        )
        calls.append(selected)
        return LlmBatchResult(
            records=tuple(
                {
                    "candidate_id": candidate_id,
                    "case_id": f"case-{candidate_id.rsplit('-', 1)[-1]}",
                    "prediction_units": [],
                }
                for candidate_id in selected
            ),
            audit_records=tuple(
                {
                    "candidate_id": candidate_id,
                    "status": "succeeded",
                    "unitization_review_queue": [],
                    "estimated_cost": 0.0,
                }
                for candidate_id in selected
            ),
        )

    monkeypatch.setattr(
        unitizer_module,
        "load_provider_cycle_caps_bytes",
        fake_load_caps,
    )
    monkeypatch.setattr(
        unitizer_module,
        "load_model_registry_bytes",
        fake_load_registry,
    )
    monkeypatch.setattr(
        unitizer_module,
        "verify_provider_journal_identity",
        fake_verify_identity,
    )
    monkeypatch.setattr(
        unitizer_module,
        "_LABELING_MODEL_REGISTRY_SHA256",
        hashlib.sha256(b"[]").hexdigest(),
    )
    monkeypatch.setattr(
        unitizer_module,
        "_PROVIDER_CAPS_SHA256",
        hashlib.sha256(b"{}").hexdigest(),
    )
    monkeypatch.setattr(unitizer_module, "_LABELING_MODEL_KEY", "synthetic-model")
    monkeypatch.setattr(
        unitizer_module,
        "_adopt_authenticated_unitization_replays",
        fake_adopt,
    )

    args = argparse.Namespace(
        output_root=tmp_path / "output",
        selection=tmp_path / "selection-unused.jsonl",
        document_store_roots=(),
        verdict_sources=(),
        expected_verdict_source_sha256=(),
        target_case_count=100,
        finalized_units=overlay,
        finalized_integration_manifest=integration_path,
        expected_selection_sha256=prepared.selection_sha256,
        expected_finalized_units_sha256=hashlib.sha256(
            overlay.read_bytes()
        ).hexdigest(),
        expected_finalized_integration_manifest_sha256=hashlib.sha256(
            integration_path.read_bytes()
        ).hexdigest(),
        owner_approval_reference="legalforecastbench-3ak.38",
        stage51_packet_approval=(
            f"stage51-terminal-units: approved — packet {integration['packet_sha256']}"
        ),
        units_spend_approval=_UNITS_APPROVAL,
        model_registry=tmp_path / "registry.json",
        model_key="synthetic-model",
        provider_cycle_caps=tmp_path / "caps.json",
        provider_journal=tmp_path / "journal.sqlite3",
        local_provider_journal_only=True,
        provider_attempt_namespace=_PROMPT_CONTRACT,
        terminal_escalation=[],
        execute=True,
        continue_on_error=False,
        resume=False,
        prediction_units_output=None,
        audit_output=None,
        unitization_review_queue_output=None,
        unitizer_terminal_review_queue_output=None,
        run_card_output=None,
        log_output=None,
        timeout_seconds=1.0,
    )
    args.selection = tmp_path / "selection.jsonl"
    args.selection.write_bytes(
        b"".join(
            json.dumps(row, sort_keys=True).encode() + b"\n"
            for row in prepared.selection_records
        )
    )
    args.document_store_roots = (tmp_path / "store",)
    args.verdict_sources = (tmp_path / "verdicts.jsonl",)
    args.expected_verdict_source_sha256 = (
        hashlib.sha256(args.verdict_sources[0].read_bytes()).hexdigest(),
    )
    # The execution adapter reads these paths before the patched authority loaders.
    args.model_registry.write_text("[]")
    args.provider_cycle_caps.write_text("{}")
    args.provider_journal.write_bytes(b"journal")

    args.execute = False
    unitizer_module.run_manifest_unitizer(args)
    assert calls == []
    run_card_path = args.output_root / "run-cards" / "llm-unitize-manifest.json"
    metadata_path = (
        args.output_root / "run-cards" / "llm-unitize-manifest.metadata.json"
    )
    frozen_run_card_fields = {
        "schema_version",
        "stage",
        "status",
        "dry_run",
        "execute",
        "resume",
        "record_count",
        "input_paths",
        "output_paths",
        "paid_activity_requested",
        "paid_activity_executed",
        "generated_at",
    }
    assert set(json.loads(run_card_path.read_text())) == frozen_run_card_fields
    dry_run_metadata = json.loads(metadata_path.read_text())
    assert dry_run_metadata["authoritative"] is False
    assert (
        dry_run_metadata["finalized_overlay_sha256"]
        == hashlib.sha256(overlay.read_bytes()).hexdigest()
    )

    args.execute = True
    unitizer_module.run_manifest_unitizer(args)

    assert calls == [fresh_ids]
    assert set(json.loads(run_card_path.read_text())) == frozen_run_card_fields
    execute_metadata = json.loads(metadata_path.read_text())
    assert execute_metadata["authoritative"] is False
    assert execute_metadata["provider_spend_cap_usd"] == 5.0
    assert execute_metadata["provider_execution"] == {
        "provider_called": False,
        "historical_replay_only": True,
        "authority_ordinals_created": False,
        "new_paid_activity": False,
    }
    execute_run_card = json.loads(run_card_path.read_text())
    assert execute_run_card["paid_activity_requested"] is False
    assert execute_run_card["paid_activity_executed"] is False

    args.model_key = "openai:gpt-5.6-sol"
    with pytest.raises(ManifestUnitizerCommandError, match="labeling model"):
        unitizer_module.run_manifest_unitizer(args)
    assert calls == [fresh_ids]


def test_manifest_unitizer_defaults_accountless_caps_to_default() -> None:
    caps = load_provider_cycle_caps_bytes(
        json.dumps(
            {
                "schema_version": "legalforecast.provider_cycle_caps.v1",
                "cycle_id": "synthetic-cycle",
                "providers": [
                    {"provider": "synthetic", "cycle_reservation_cap_usd": "5.00"}
                ],
            }
        ).encode(),
        source="synthetic-caps.json",
    )

    assert _provider_account(caps, "synthetic") == "default"


def test_r2_stage_card_is_create_only_and_binds_authority_sidecar(
    tmp_path: Path,
) -> None:
    authenticated, prepared, _, _, fresh_ids, integration = _authenticate_fixture(
        tmp_path
    )
    approval = _write_text(
        tmp_path / "approval.json",
        json.dumps(
            {
                "reference": "legalforecastbench-3ak.38",
                "packet": (
                    "stage51-terminal-units: approved — packet "
                    f"{integration['packet_sha256']}"
                ),
                "spend": _UNITS_APPROVAL,
            },
            sort_keys=True,
        )
        + "\n",
    )
    approval_commitment = _file_commitment(approval, "owner_approval_observation")
    r2_overlay = replace(
        authenticated,
        authority_mode=unitizer_module._R2_AUTHORITY_MODE,
        authority_input_commitments=(approval_commitment,),
    )
    output_root = tmp_path / "r2-output"
    output_paths = (
        output_root / "prediction-units.jsonl",
        output_root / "llm-unitization-audit.jsonl",
        output_root / "unitization-review-queue.jsonl",
        output_root / "unitizer-terminal-review-queue.jsonl",
    )
    for path in output_paths:
        _write_jsonl_output(path, [], immutable=True)
    replay_audits = tuple(
        {
            "candidate_id": candidate_id,
            "case_id": f"case-{candidate_id}",
            "provider_prompt_sha256": "sha256:" + "1" * 64,
            "raw_output_sha256": "sha256:" + "2" * 64,
            "historical_provider_attempt_ordinal": index,
            "input_tokens": 10,
            "output_tokens": 20,
            "estimated_cost": 0.01,
            "unit_count": 1,
            "scorable_unit_count": 1,
            "metadata": {
                "provider_response_sha256": "3" * 64,
                "normalized_response_sha256": "4" * 64,
            },
        }
        for index, candidate_id in enumerate(fresh_ids, start=1)
    )
    args = argparse.Namespace(
        run_card_output=None,
        log_output=None,
        resume=False,
        owner_approval_reference="legalforecastbench-3ak.38",
        stage51_packet_approval=(
            f"stage51-terminal-units: approved — packet {integration['packet_sha256']}"
        ),
        units_spend_approval=_UNITS_APPROVAL,
        provider_journal=tmp_path / "provider-attempts.sqlite3",
    )

    _write_stage_card(
        args,
        output_root=output_root,
        input_paths=(approval,),
        output_paths=output_paths,
        record_count=100,
        paid=False,
        extra={"selection_sha256": prepared.selection_sha256},
        dry_run=False,
        immutable=True,
        authority_overlay=r2_overlay,
        prepared=prepared,
        replay_audits=replay_audits,
    )

    run_card_path = output_root / "run-cards" / "llm-unitize-manifest.json"
    authority_path = (
        output_root / "run-cards" / "llm-unitize-manifest.r2-authority.json"
    )
    run_card = json.loads(run_card_path.read_text())
    authority = json.loads(authority_path.read_text())
    assert set(run_card) == {
        "schema_version",
        "stage",
        "status",
        "dry_run",
        "execute",
        "resume",
        "record_count",
        "input_paths",
        "output_paths",
        "paid_activity_requested",
        "paid_activity_executed",
        "generated_at",
    }
    assert str(authority_path) in run_card["output_paths"]
    assert authority["schema_version"] == (
        "legalforecast.cycle1.manifest_unitizer_r2_authority.v1"
    )
    assert authority["selection"]["candidate_order"] == [
        row["candidate_id"] for row in prepared.selection_records
    ]
    assert [
        row["candidate_id"] for row in authority["journal_reconstruction"]["candidates"]
    ] == list(fresh_ids)
    assert authority["provider_called"] is False
    assert authority["historical_replay_only"] is True
    assert authority["journal_mutated"] is False
    assert authority["owner_approval"]["observation_role"] == (
        "hash-pinned observational evidence; not identity authentication"
    )

    with pytest.raises(ManifestUnitizerCommandError, match="already exists"):
        _write_stage_card(
            args,
            output_root=output_root,
            input_paths=(approval,),
            output_paths=output_paths,
            record_count=100,
            paid=False,
            extra={"selection_sha256": prepared.selection_sha256},
            dry_run=False,
            immutable=True,
            authority_overlay=r2_overlay,
            prepared=prepared,
            replay_audits=replay_audits,
        )


def test_r2_preflight_refuses_input_alias_and_existing_output(tmp_path: Path) -> None:
    input_path = _write_text(tmp_path / "input.json", "{}\n")
    args = argparse.Namespace(run_card_output=None, log_output=None)

    with pytest.raises(ManifestUnitizerCommandError, match="aliases"):
        _preflight_r2_outputs(
            args,
            output_root=tmp_path / "output",
            input_paths=(input_path,),
            primary_outputs=(input_path,),
        )

    existing = _write_text(tmp_path / "existing.jsonl", "")
    with pytest.raises(ManifestUnitizerCommandError, match="already exists"):
        _preflight_r2_outputs(
            args,
            output_root=tmp_path / "other-output",
            input_paths=(input_path,),
            primary_outputs=(existing,),
        )


def test_citation_span_accepts_exact_terminal_newline() -> None:
    markdown = "##### Page 9\n\nCount I\nThe complaint alleges a claim.\n"

    assert _citation_span_pages(
        markdown, "Count I\nThe complaint alleges a claim.\n"
    ) == {9}
    assert _citation_span_pages(
        markdown, "Count I\nThe complaint alleges a claim."
    ) == {9}
