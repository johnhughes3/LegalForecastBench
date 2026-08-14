"""Mechanical pass-1 blindness: decision bytes are unreadable by the process."""

from __future__ import annotations

import json

from legalforecast.document_need.types import BlindBundle, DecisionText


class BlindnessError(ValueError):
    """Raised when pass 1 would be able to read decision bytes."""


class Pass1Process:
    """Workspace that can only hold a blind bundle.

    Attaching decision bytes is a hard error so a caller cannot accidentally
    feed the disposition into pass 1.
    """

    def __init__(self, bundle: BlindBundle) -> None:
        self._bundle = bundle

    @property
    def bundle(self) -> BlindBundle:
        return self._bundle

    def attach_decision(self, _text: str) -> None:
        """Refuse decision bytes. The blindness test asserts this raises."""

        raise BlindnessError("pass 1 must not receive decision bytes")


def assert_pass1_cannot_read_decision(prompt: str, decision: DecisionText) -> None:
    """Fail if the pass-1 prompt contains the sequestered decision body or digest."""

    if type(prompt) is not str:
        raise BlindnessError("pass-1 prompt must be a string")
    needles = (decision.text, json.dumps(decision.text)[1:-1])
    if any(needle and needle in prompt for needle in needles):
        raise BlindnessError(
            f"pass-1 prompt contains decision bytes for {decision.candidate_id}"
        )
    if decision.sha256 in prompt:
        raise BlindnessError(
            f"pass-1 prompt contains the decision digest for {decision.candidate_id}"
        )


def collect_blind_payload_text(bundle: BlindBundle) -> str:
    """Concatenate every pass-1 visible string for leakage checks."""

    parts = [
        bundle.chronology.candidate_id,
        bundle.chronology.case_name or "",
        bundle.chronology.court or "",
        bundle.chronology.docket_number or "",
    ]
    for entry in bundle.chronology.entries:
        parts.append(entry.text)
        for document in entry.documents:
            parts.append(document.description)
    for body in bundle.motion_markdown.values():
        parts.append(body)
    return "\n".join(parts)
