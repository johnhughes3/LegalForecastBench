"""Deterministic, identity-preserving Case.dev enrichment scheduling."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import cast

_RESOLUTION_SIGNAL = re.compile(
    r"\b(?:grant(?:ed|ing)|den(?:ied|ying)|dismiss(?:ed|ing|al))\b",
    re.IGNORECASE,
)
_DECISION_SIGNAL = re.compile(
    r"\b(?:order|disposition)\b|\bmemorandum\s+opinion\b|"
    r"\breport\s+and\s+recommendation\b",
    re.IGNORECASE,
)
_MOTION_TO_DISMISS_SIGNAL = re.compile(
    r"\bmotions?\s+to\s+dismiss\b|\bjudgment\s+on\s+the\s+pleadings\b",
    re.IGNORECASE,
)
_RULE_12_SIGNAL = re.compile(
    r"\brule\s+(?:12|7012)\b|\b12\s*\(\s*[bc]\s*\)",
    re.IGNORECASE,
)


def case_dev_enrichment_schedule_key(
    *,
    input_index: int,
    record: Mapping[str, object],
) -> tuple[int, int, int]:
    """Return a scheduling-only priority with the durable index as tie-break.

    The key deliberately excludes docket identity and all Case.dev output.  It
    changes only which pending record starts next; ``input_index`` remains the
    checkpoint identity, and downstream ranking remains independent of this
    execution order.
    """

    evidence = _authenticated_decision_evidence(record)
    evidence_priority = 0 if evidence is not None else 1
    text_fragments = list(_source_query_terms(record))
    if evidence is not None and isinstance(evidence.get("description"), str):
        text_fragments.append(cast(str, evidence["description"]))
    text = "\n".join(text_fragments)
    if _RESOLUTION_SIGNAL.search(text) or _DECISION_SIGNAL.search(text):
        signal_priority = 0
    elif _MOTION_TO_DISMISS_SIGNAL.search(text):
        signal_priority = 1
    elif _RULE_12_SIGNAL.search(text):
        signal_priority = 2
    else:
        signal_priority = 3
    return (evidence_priority, signal_priority, input_index)


def _authenticated_decision_evidence(
    record: Mapping[str, object],
) -> Mapping[str, object] | None:
    lineage = record.get("source_lineage")
    if not isinstance(lineage, Mapping):
        return None
    typed_lineage = cast(Mapping[str, object], lineage)
    lead = typed_lineage.get("lead_commitment")
    if not isinstance(lead, Mapping):
        return None
    typed_lead = cast(Mapping[str, object], lead)
    evidence = typed_lead.get("decision_entry_evidence")
    if not isinstance(evidence, Mapping) or not evidence:
        return None
    return cast(Mapping[str, object], evidence)


def _source_query_terms(record: Mapping[str, object]) -> tuple[str, ...]:
    terms: list[str] = []
    _extend_strings(terms, record.get("matched_terms"))
    lineage = record.get("source_lineage")
    if not isinstance(lineage, Mapping):
        return tuple(terms)
    typed_lineage = cast(Mapping[str, object], lineage)
    _extend_hit_terms(terms, typed_lineage.get("source_hits"))
    lead = typed_lineage.get("lead_commitment")
    if isinstance(lead, Mapping):
        typed_lead = cast(Mapping[str, object], lead)
        _extend_hit_terms(terms, typed_lead.get("source_hits"))
    return tuple(terms)


def _extend_strings(target: list[str], raw: object) -> None:
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return
    values = cast(Sequence[object], raw)
    target.extend(value for value in values if isinstance(value, str))


def _extend_hit_terms(target: list[str], raw: object) -> None:
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return
    for hit in cast(Sequence[object], raw):
        if not isinstance(hit, Mapping):
            continue
        typed_hit = cast(Mapping[str, object], hit)
        query_term = typed_hit.get("query_term")
        if isinstance(query_term, str):
            target.append(query_term)
