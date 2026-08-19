"""Accept exactly two conversion provenances into an authenticated lineage.

Reuse matches a prior conversion by candidate, document, source digest and byte
count.  None of that proves the row was produced the way the lineage claims, so
the reuse path additionally pins the record's own provenance.  Until now there
was one acceptable shape: a pinned live-Mistral conversion.

A page-scoped embedded-text-layer repair is the second, and it is pinned just
as tightly.  A loose repair shape would be a weaker second route into the
authenticated lineage — precisely what these checks exist to prevent — so the
repair branch names its engine, its repair revision, the pinned parser revision
it supersedes, the digest it supersedes, and the exact pages it recovered.

Returning a problem string rather than raising keeps this module free of any
dependency on the CLI's error type, so the CLI stays the only place that
decides how a refusal is surfaced.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from legalforecast.ingestion.embedded_text_layer_repair import (
    EMBEDDED_TEXT_LAYER_REPAIR_METHOD,
    embedded_text_layer_repair_record_problem,
)
from legalforecast.ingestion.mistral_markdown_parser import (
    EXPECTED_PARSER_REVISION,
    MistralMarkdownConversionStatus,
)
from legalforecast.ingestion.provenance import sha256_text


def is_embedded_text_layer_repair_record(record: Mapping[str, object]) -> bool:
    """Return whether a conversion record declares the page-repair provenance.

    This is the single place that answers "which of the two provenances is
    this?".  Every validator that used to compare ``extraction_method``
    against one hardcoded string asks here instead, so the accepted set stays
    a property of this module rather than something four files agree on by
    coincidence.
    """

    extracted = record.get("extracted_text")
    if not isinstance(extracted, Mapping):
        return False
    return (
        cast(Mapping[str, object], extracted).get("extraction_method")
        == EMBEDDED_TEXT_LAYER_REPAIR_METHOD
    )


def embedded_text_layer_repair_problem(
    record: Mapping[str, object], *, markdown: str | None = None
) -> str | None:
    """Return why a repaired conversion record is unacceptable, or ``None``.

    ``markdown=None`` checks the record's shape only, for callers that verify
    the published bytes by their own route.
    """

    return embedded_text_layer_repair_record_problem(
        record, markdown=markdown, expected_parser_revision=EXPECTED_PARSER_REVISION
    )


def parse_record_pinned_parser_revision(record: Mapping[str, object]) -> str | None:
    """Return the pinned parser revision a conversion record is bound to.

    Both provenances are bound to the same pinned parser generation; they name
    it differently, because one *is* that parser's output and the other was
    produced alongside it.  Callers that record the revision downstream read it
    from here rather than guessing which key a record carries.
    """

    config = record.get("parser_config")
    if not isinstance(config, Mapping):
        return None
    config_record = cast(Mapping[str, object], config)
    key = (
        "pinned_parser_revision"
        if is_embedded_text_layer_repair_record(record)
        else "parser_revision"
    )
    revision = config_record.get(key)
    return revision if isinstance(revision, str) else None


def live_parse_record_provenance_problem(
    record: Mapping[str, object], *, markdown: str
) -> str | None:
    """Return why a conversion record may not be reused, or ``None``."""

    if record.get("status") != MistralMarkdownConversionStatus.SUCCEEDED.value:
        return "prior conversion did not succeed"
    config = record.get("parser_config")
    extracted = record.get("extracted_text")
    if not isinstance(config, Mapping) or not isinstance(extracted, Mapping):
        return "prior conversion lacks live-Mistral parser provenance"
    extracted_record = cast(Mapping[str, object], extracted)
    if is_embedded_text_layer_repair_record(record):
        return embedded_text_layer_repair_problem(record, markdown=markdown)
    return _live_mistral_record_problem(
        record,
        config=cast(Mapping[str, object], config),
        extracted=extracted_record,
        markdown=markdown,
    )


def _live_mistral_record_problem(
    record: Mapping[str, object],
    *,
    config: Mapping[str, object],
    extracted: Mapping[str, object],
    markdown: str,
) -> str | None:
    command = config.get("command")
    if not isinstance(command, list):
        return "prior conversion has an unclean Mistral parser config"
    command_objects = cast(list[object], command)
    if not all(isinstance(value, str) for value in command_objects):
        return "prior conversion has an unclean Mistral parser config"
    command_values = cast(list[str], command_objects)
    if (
        config.get("engine") != "mistral"
        or config.get("parser_revision") != EXPECTED_PARSER_REVISION
        or config.get("expected_parser_revision") != EXPECTED_PARSER_REVISION
        or config.get("debug") is not False
        or not isinstance(config.get("timeout_seconds"), int)
        or isinstance(config.get("timeout_seconds"), bool)
        or not isinstance(config.get("parser_root"), str)
        or command_values[:3] != ["uv", "run", "parser-pdf"]
        or len(command_values) != 7
        or command_values[3] != "--file"
        or not command_values[4]
        or command_values[5:] != ["--mistral", "--no-ocr"]
    ):
        return "prior conversion has an unclean Mistral parser config"
    quality_flags = record.get("quality_flags")
    if not isinstance(quality_flags, list):
        return "prior conversion Markdown text provenance mismatch"
    quality_flag_objects = cast(list[object], quality_flags)
    if not all(isinstance(flag, str) for flag in quality_flag_objects):
        return "prior conversion Markdown text provenance mismatch"
    quality_flag_values = cast(list[str], quality_flag_objects)
    if (
        quality_flag_values
        or extracted.get("quality_flags") != quality_flag_values
        or extracted.get("source_document_id") != record.get("source_document_id")
        or extracted.get("extraction_method") != "mistral_parser_markdown"
        or extracted.get("text_sha256") != sha256_text(markdown)
    ):
        return "prior conversion Markdown text provenance mismatch"
    return None


__all__ = [
    "embedded_text_layer_repair_problem",
    "is_embedded_text_layer_repair_record",
    "live_parse_record_provenance_problem",
    "parse_record_pinned_parser_revision",
]
