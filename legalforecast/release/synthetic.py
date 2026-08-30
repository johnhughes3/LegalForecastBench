"""Deterministic three-case release fixture issuer."""

from __future__ import annotations

import hashlib
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from legalforecast.contracts import ARTIFACT_CANONICAL_JSON_V1
from legalforecast.immutable_io import publish_tree_create_only

from .models import (
    CaseDraft,
    DocumentDraft,
    ForecastDraft,
    ForecastManifestBinding,
    LabelsDraft,
    ModelVisibleRole,
    PredictionUnitDraft,
    ScoringPolicy,
    UnitOutcome,
)
from .run_manifest import (
    BenchmarkRunManifest,
    DocumentRole,
    OpaqueObjectLocator,
    OppositionStatus,
    QCStatus,
    RoleObjectLocator,
    SelectedCase,
    serialize_run_manifest,
)
from .service import IssuedRelease, issue_release


def issue_synthetic_release(output_dir: Path) -> IssuedRelease:
    """Issue and publish the complete provider-free three-case fixture."""

    payloads, forecast_draft, labels_draft = _synthetic_inputs()
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="legalforecast-release-", dir=output_dir.parent
    ) as temporary:
        artifact_root = Path(temporary)
        for relative_path, payload in payloads.items():
            path = artifact_root / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
        issued = issue_release(
            forecast_draft,
            labels_draft,
            artifact_root=artifact_root,
        )
    publish_tree_create_only(output_dir, {**payloads, **issued.payloads})
    return issued


def _synthetic_inputs() -> tuple[dict[str, bytes], ForecastDraft, LabelsDraft]:
    roles: tuple[ModelVisibleRole, ...] = (
        "amended_complaint",
        "complaint",
        "counterclaim",
        "crossclaim",
        "interpleader_complaint",
        "motion_to_dismiss_memorandum",
        "motion_to_dismiss_notice",
        "opposition",
        "other_claim_bearing_filing",
        "reply",
        "supplemental_brief",
        "surreply",
        "third_party_complaint",
    )
    documents_by_case = {
        "case-001": tuple(
            DocumentDraft(
                document_id=f"full-{index:02d}-{role}",
                role=role,
                path=f"documents/case-001/full-{index:02d}-{role}.txt",
            )
            for index, role in enumerate(roles, start=1)
        ),
        "case-002": (
            DocumentDraft(
                document_id="case-002-complaint",
                role="complaint",
                path="documents/case-002/complaint.txt",
            ),
            DocumentDraft(
                document_id="case-002-memorandum",
                role="motion_to_dismiss_memorandum",
                path="documents/case-002/memorandum.txt",
            ),
        ),
        "case-003": (
            DocumentDraft(
                document_id="case-003-counterclaim",
                role="counterclaim",
                path="documents/case-003/counterclaim.txt",
            ),
            DocumentDraft(
                document_id="case-003-reply",
                role="reply",
                path="documents/case-003/reply.txt",
            ),
        ),
    }
    payloads: dict[str, bytes] = {}
    for case_id, documents in documents_by_case.items():
        for document in documents:
            payloads[document.path] = (
                f"Synthetic predecision material for {case_id}: {document.role}.\n"
            ).encode()

    units: list[PredictionUnitDraft] = []
    count_labels = ("Count I", "Count II", "Count III")
    for index, (case_id, documents) in enumerate(documents_by_case.items(), start=1):
        unit_id = f"unit-{index:03d}"
        packet_path = f"packets/{unit_id}.json"
        prompt_path = f"prompts/{unit_id}.txt"
        payloads[packet_path] = ARTIFACT_CANONICAL_JSON_V1.encode(
            {
                "case_id": case_id,
                "decision_date": "2026-08-23",
                "documents": [
                    {"document_id": document.document_id, "role": document.role}
                    for document in documents
                ],
                "unit_id": unit_id,
            }
        )
        payloads[prompt_path] = (
            f"Forecast whether {unit_id} will be granted or denied using only "
            f"the committed predecision packet.\n"
        ).encode()
        units.append(
            PredictionUnitDraft(
                unit_id=unit_id,
                case_id=case_id,
                claim_name=f"Synthetic claim {index}",
                defendant_group=f"Synthetic defendants {index}",
                count=count_labels[index - 1],
                should_score=index < 3,
                model_visible_document_ids=tuple(
                    document.document_id for document in documents
                ),
                packet_path=packet_path,
                prompt_path=prompt_path,
            )
        )

    forecast = ForecastDraft(
        release_id="synthetic-three-case-v1",
        policy_digest="1" * 64,
        code_version="synthetic-code-v1",
        packet_builder_version="synthetic-packet-builder-v1",
        run_manifest_binding=_synthetic_manifest_binding(),
        cases=tuple(
            CaseDraft(case_id=case_id, documents=documents)
            for case_id, documents in documents_by_case.items()
        ),
        prediction_units=tuple(units),
    )
    labels = LabelsDraft(
        release_id=forecast.release_id,
        scoring_policy=ScoringPolicy(policy_id="synthetic-micro-brier-v1"),
        unit_outcomes=(
            UnitOutcome(unit_id="unit-001", outcome=0),
            UnitOutcome(unit_id="unit-002", outcome=1),
        ),
    )
    return payloads, forecast, labels


def _synthetic_manifest_binding() -> ForecastManifestBinding:
    """Bind the provider-free fixture to its stable locked manifest sample."""

    manifest = BenchmarkRunManifest(
        run_id=UUID("12345678-1234-5678-1234-567812345678"),
        selected_cases=tuple(
            SelectedCase(
                case_id=case_id,
                provider_id="corpus-store",
                qc_status=QCStatus.ACCEPTED,
                role_locators=tuple(
                    RoleObjectLocator(
                        role=role,
                        locator=OpaqueObjectLocator(
                            provider_id="object-store",
                            object_locator=f"cases/{case_id}/{role.value}",
                            version_id=f"version-{case_id}-{role.value}",
                        ),
                    )
                    for role in (
                        DocumentRole.DECISION,
                        DocumentRole.MOTION,
                        DocumentRole.COMPLAINT,
                    )
                ),
                opposition_status=OppositionStatus.CONFIRMED_UNOPPOSED,
            )
            for case_id in ("case-001", "case-002", "case-003")
        ),
        policy_version="federal-mtd-v1",
        code_revision="a" * 40,
        created_at=datetime(2026, 8, 30, 12, tzinfo=UTC),
        locked_at=datetime(2026, 8, 30, 12, 1, tzinfo=UTC),
    )
    return ForecastManifestBinding(
        release_id="synthetic-three-case-v1",
        run_id=manifest.run_id,
        policy_version=manifest.policy_version,
        code_revision=manifest.code_revision,
        manifest_sha256=hashlib.sha256(serialize_run_manifest(manifest)).hexdigest(),
    )
