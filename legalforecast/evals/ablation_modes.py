"""Ablation run-mode definitions for model and baseline evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from legalforecast.evals.packet_builder import PacketAblation

DEFAULT_ABLATION_TOOL_CALL_CAP = 10


class AblationRunMode(StrEnum):
    """Named conditions used to explain model signal sources."""

    METADATA_ONLY = "metadata_only"
    BRIEFS_ONLY_REDACTED = "briefs_only_redacted"
    JUDGE_REMOVED = "judge_removed"
    FULL_PACKET = "full_packet"
    FULL_PACKET_WITHOUT_TOOL = "full_packet_without_tool"
    FULL_PACKET_WITH_TOOL = "full_packet_with_tool"


@dataclass(frozen=True, slots=True)
class AblationRunModeSpec:
    """Deterministic packet/tool configuration for one ablation condition."""

    mode: AblationRunMode
    packet_ablation: PacketAblation
    use_docket_tool: bool
    run_label: str
    purpose: str
    max_tool_calls: int = DEFAULT_ABLATION_TOOL_CALL_CAP

    def __post_init__(self) -> None:
        if not self.run_label.strip():
            raise ValueError("run_label is required")
        if not self.purpose.strip():
            raise ValueError("purpose is required")
        if self.max_tool_calls <= 0:
            raise ValueError("max_tool_calls must be positive")

    def to_record(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "packet_ablation": self.packet_ablation.value,
            "use_docket_tool": self.use_docket_tool,
            "run_label": self.run_label,
            "purpose": self.purpose,
            "max_tool_calls": self.max_tool_calls,
        }


_SPECS = {
    AblationRunMode.METADATA_ONLY: AblationRunModeSpec(
        mode=AblationRunMode.METADATA_ONLY,
        packet_ablation=PacketAblation.METADATA_ONLY,
        use_docket_tool=False,
        run_label="metadata_only",
        purpose="institutional and docket priors without document text",
    ),
    AblationRunMode.BRIEFS_ONLY_REDACTED: AblationRunModeSpec(
        mode=AblationRunMode.BRIEFS_ONLY_REDACTED,
        packet_ablation=PacketAblation.BRIEFS_ONLY_REDACTED,
        use_docket_tool=False,
        run_label="briefs_only_redacted",
        purpose="argument and legal-merits signal with judge metadata redacted",
    ),
    AblationRunMode.JUDGE_REMOVED: AblationRunModeSpec(
        mode=AblationRunMode.JUDGE_REMOVED,
        packet_ablation=PacketAblation.JUDGE_REMOVED,
        use_docket_tool=True,
        run_label="judge_removed",
        purpose="sensitivity to judge-specific prior signal",
    ),
    AblationRunMode.FULL_PACKET: AblationRunModeSpec(
        mode=AblationRunMode.FULL_PACKET,
        packet_ablation=PacketAblation.FULL_PACKET,
        use_docket_tool=False,
        run_label="full_packet",
        purpose="headline packet content without additional docket exploration",
    ),
    AblationRunMode.FULL_PACKET_WITHOUT_TOOL: AblationRunModeSpec(
        mode=AblationRunMode.FULL_PACKET_WITHOUT_TOOL,
        packet_ablation=PacketAblation.FULL_PACKET,
        use_docket_tool=False,
        run_label="full_packet_without_tool",
        purpose="isolate value of docket exploration from default packet content",
    ),
    AblationRunMode.FULL_PACKET_WITH_TOOL: AblationRunModeSpec(
        mode=AblationRunMode.FULL_PACKET_WITH_TOOL,
        packet_ablation=PacketAblation.FULL_PACKET,
        use_docket_tool=True,
        run_label="full_packet_with_tool",
        purpose="main agentic condition with controlled docket tool access",
    ),
}


def get_ablation_run_mode(mode: AblationRunMode | str) -> AblationRunModeSpec:
    """Return the frozen run-mode specification for a named ablation."""

    return _SPECS[AblationRunMode(mode)]


def list_ablation_run_modes() -> tuple[AblationRunModeSpec, ...]:
    """Return all required v1.0 ablation run modes in reporting order."""

    return tuple(_SPECS[mode] for mode in AblationRunMode)
