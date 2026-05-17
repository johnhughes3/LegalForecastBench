"""Markdown rendering for controlled docket packet and audit views."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DocketMarkdownMetadata:
    """Case and discovery metadata shown above controlled docket entries."""

    candidate_id: str
    case_id: str
    case_name: str
    court: str
    docket_number: str
    source_provider: str
    source_case_id: str
    source_url: str
    search_query: str
    search_window: str
    discovered_at: str


@dataclass(frozen=True, slots=True)
class ControlledDocketMarkdownEntry:
    """One docket entry rendered into model-visible or audit markdown."""

    docket_entry_id: str
    entry_number: str | None
    filed_at: str | None
    entry_text: str
    packet_section: str
    source_url: str | None = None
    source_document_ids: tuple[str, ...] = ()
    is_predecision_material: bool = True
    contains_target_outcome: bool = False
    free_text_available: bool = True

    @property
    def model_visible(self) -> bool:
        return (
            self.free_text_available
            and self.is_predecision_material
            and not self.contains_target_outcome
            and self.packet_section not in {"post_decision", "labels", "audit_only"}
        )


@dataclass(frozen=True, slots=True)
class ControlledDocketMarkdownArtifacts:
    """Rendered model-visible and complete audit docket markdown."""

    model_visible_markdown: str
    audit_markdown: str


def render_controlled_docket_markdown(
    metadata: DocketMarkdownMetadata,
    entries: Iterable[ControlledDocketMarkdownEntry],
) -> ControlledDocketMarkdownArtifacts:
    """Render outcome-safe model markdown plus a complete audit docket view."""

    docket_entries = tuple(entries)
    return ControlledDocketMarkdownArtifacts(
        model_visible_markdown=_render_markdown(
            metadata,
            tuple(entry for entry in docket_entries if entry.model_visible),
            title="Model-Visible Docket Entries",
            include_audit_flags=False,
        ),
        audit_markdown=_render_markdown(
            metadata,
            docket_entries,
            title="Audit Docket Entries",
            include_audit_flags=True,
        ),
    )


def _render_markdown(
    metadata: DocketMarkdownMetadata,
    entries: tuple[ControlledDocketMarkdownEntry, ...],
    *,
    title: str,
    include_audit_flags: bool,
) -> str:
    lines = [
        f"# Controlled Docket: {metadata.case_name}",
        "",
        "## Docket Metadata",
        f"- Candidate ID: {metadata.candidate_id}",
        f"- Case ID: {metadata.case_id}",
        f"- Case name: {metadata.case_name}",
        f"- Court: {metadata.court}",
        f"- Docket number: {metadata.docket_number}",
        f"- Source provider: {metadata.source_provider}",
        f"- Source case ID: {metadata.source_case_id}",
        f"- Source URL: {metadata.source_url}",
        f"- Search query: {metadata.search_query}",
        f"- Search window: {metadata.search_window}",
        f"- Discovered at: {metadata.discovered_at}",
        "",
        f"## {title}",
        "",
    ]
    if not entries:
        lines.append("_No docket entries in this view._")
        return "\n".join(lines)
    for entry in entries:
        lines.extend(_entry_lines(entry, include_audit_flags=include_audit_flags))
    return "\n".join(lines)


def _entry_lines(
    entry: ControlledDocketMarkdownEntry,
    *,
    include_audit_flags: bool,
) -> list[str]:
    heading_parts = [
        f"Entry {entry.entry_number}" if entry.entry_number else "Entry",
        entry.filed_at or "date unknown",
        f"packet_section={entry.packet_section}",
    ]
    lines = [
        f"### {' | '.join(heading_parts)}",
        f"- Docket entry ID: {entry.docket_entry_id}",
    ]
    if entry.source_url is not None:
        lines.append(f"- Source URL: {entry.source_url}")
    if entry.source_document_ids:
        lines.append(f"- Source documents: {', '.join(entry.source_document_ids)}")
    if include_audit_flags:
        lines.extend(
            [
                f"- is_predecision_material={_bool(entry.is_predecision_material)}",
                f"- contains_target_outcome={_bool(entry.contains_target_outcome)}",
                f"- free_text_available={_bool(entry.free_text_available)}",
            ]
        )
    lines.extend(["", entry.entry_text, ""])
    return lines


def _bool(value: bool) -> str:
    return "true" if value else "false"
