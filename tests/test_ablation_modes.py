from __future__ import annotations

from legalforecast.evals.ablation_modes import (
    AblationRunMode,
    get_ablation_run_mode,
    list_ablation_run_modes,
)
from legalforecast.evals.packet_builder import PacketAblation


def test_all_required_ablation_modes_have_stable_run_labels() -> None:
    specs = list_ablation_run_modes()

    assert [spec.mode for spec in specs] == list(AblationRunMode)
    assert [spec.run_label for spec in specs] == [
        "metadata_only",
        "briefs_only_redacted",
        "judge_removed",
        "full_packet",
        "full_packet_without_tool",
        "full_packet_with_tool",
    ]
    assert all(spec.to_record()["run_label"] == spec.run_label for spec in specs)


def test_tool_modes_share_full_packet_but_have_distinct_tool_policy() -> None:
    without_tool = get_ablation_run_mode(AblationRunMode.FULL_PACKET_WITHOUT_TOOL)
    with_tool = get_ablation_run_mode("full_packet_with_tool")

    assert without_tool.packet_ablation is PacketAblation.FULL_PACKET
    assert with_tool.packet_ablation is PacketAblation.FULL_PACKET
    assert without_tool.use_docket_tool is False
    assert with_tool.use_docket_tool is True
    assert with_tool.max_tool_calls == 10
