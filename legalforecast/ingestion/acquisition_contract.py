"""Production acquisition contract constants for MTD packet assembly."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final


class SetupRunnerDocumentLabel(StrEnum):
    """Document labels produced by the acquisition setup runner."""

    CORE_MTD = "core_mtd"
    CORE_EXHIBIT = "core_exhibit"
    OTHER_SUBSTANTIVE = "other_substantive"
    PROCEDURAL_MINOR = "procedural_minor"


class AcquisitionPacketRole(StrEnum):
    """How an acquired document participates in benchmark artifacts."""

    MODEL_VISIBLE_CORE = "model_visible_core"
    MODEL_VISIBLE_SUPPORTING = "model_visible_supporting"
    AUDIT_ONLY_SUBSTANTIVE = "audit_only_substantive"
    AUDIT_ONLY_PROCEDURAL = "audit_only_procedural"


@dataclass(frozen=True, slots=True)
class SetupRunnerLabelContract:
    """Deterministic contract for one setup-runner document label."""

    label: SetupRunnerDocumentLabel
    acquisition_role: AcquisitionPacketRole
    packet_section: str | None
    model_visible_by_default: bool
    audit_bundle_required: bool
    clean_packet_relevance: str
    description: str

    def to_record(self) -> dict[str, Any]:
        return {
            "label": self.label.value,
            "acquisition_role": self.acquisition_role.value,
            "packet_section": self.packet_section,
            "model_visible_by_default": self.model_visible_by_default,
            "audit_bundle_required": self.audit_bundle_required,
            "clean_packet_relevance": self.clean_packet_relevance,
            "description": self.description,
        }


SETUP_RUNNER_LABEL_CONTRACTS: Final[
    dict[SetupRunnerDocumentLabel, SetupRunnerLabelContract]
] = {
    SetupRunnerDocumentLabel.CORE_MTD: SetupRunnerLabelContract(
        label=SetupRunnerDocumentLabel.CORE_MTD,
        acquisition_role=AcquisitionPacketRole.MODEL_VISIBLE_CORE,
        packet_section="filings",
        model_visible_by_default=True,
        audit_bundle_required=True,
        clean_packet_relevance=(
            "Required when the document is the operative complaint, target MTD "
            "notice or memorandum, or filed opposition. Reply briefs are optional "
            "but must be recorded when filed."
        ),
        description=(
            "Core MTD pleading or brief used to construct the model-visible "
            "pre-decision packet."
        ),
    ),
    SetupRunnerDocumentLabel.CORE_EXHIBIT: SetupRunnerLabelContract(
        label=SetupRunnerDocumentLabel.CORE_EXHIBIT,
        acquisition_role=AcquisitionPacketRole.MODEL_VISIBLE_SUPPORTING,
        packet_section="exhibits",
        model_visible_by_default=True,
        audit_bundle_required=True,
        clean_packet_relevance=(
            "Included when attached to or incorporated by a core MTD filing and "
            "pre-decision; otherwise demote to audit-only with a reason."
        ),
        description=(
            "Exhibit or attachment that supports a core MTD filing and may be "
            "needed to understand the pleading-stage record."
        ),
    ),
    SetupRunnerDocumentLabel.OTHER_SUBSTANTIVE: SetupRunnerLabelContract(
        label=SetupRunnerDocumentLabel.OTHER_SUBSTANTIVE,
        acquisition_role=AcquisitionPacketRole.AUDIT_ONLY_SUBSTANTIVE,
        packet_section=None,
        model_visible_by_default=False,
        audit_bundle_required=True,
        clean_packet_relevance=(
            "Retained for audit, linkage, and exclusion review; not mounted in "
            "the model packet unless a later protocol explicitly promotes it."
        ),
        description=(
            "Substantive docket material outside the target MTD record, such as "
            "non-target motions, notices, stipulations, or related orders."
        ),
    ),
    SetupRunnerDocumentLabel.PROCEDURAL_MINOR: SetupRunnerLabelContract(
        label=SetupRunnerDocumentLabel.PROCEDURAL_MINOR,
        acquisition_role=AcquisitionPacketRole.AUDIT_ONLY_PROCEDURAL,
        packet_section=None,
        model_visible_by_default=False,
        audit_bundle_required=True,
        clean_packet_relevance=(
            "Retained only to prove docket chronology and omission decisions; "
            "never model-visible by default."
        ),
        description=(
            "Minor procedural docket material that is useful for audit trails but "
            "not for the forecasting packet."
        ),
    ),
}


def normalize_setup_runner_label(
    label: str | SetupRunnerDocumentLabel,
) -> SetupRunnerDocumentLabel:
    """Normalize and validate a setup-runner document label."""

    if isinstance(label, SetupRunnerDocumentLabel):
        return label
    normalized = label.strip().lower()
    try:
        return SetupRunnerDocumentLabel(normalized)
    except ValueError as exc:
        allowed = ", ".join(sorted(item.value for item in SetupRunnerDocumentLabel))
        raise ValueError(
            f"unknown setup-runner document label: {label!r}; expected one of {allowed}"
        ) from exc


def contract_for_setup_runner_label(
    label: str | SetupRunnerDocumentLabel,
) -> SetupRunnerLabelContract:
    """Return the deterministic acquisition contract for a setup-runner label."""

    return SETUP_RUNNER_LABEL_CONTRACTS[normalize_setup_runner_label(label)]


def setup_runner_label_contract_records() -> tuple[dict[str, Any], ...]:
    """Return stable records suitable for docs, JSONL fixtures, or validation."""

    return tuple(
        SETUP_RUNNER_LABEL_CONTRACTS[label].to_record()
        for label in SetupRunnerDocumentLabel
    )
