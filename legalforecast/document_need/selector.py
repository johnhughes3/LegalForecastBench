"""Fixture-first selector; optional live model behind LFB_LIVE_SMOKE=1."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

from legalforecast.document_need.protocol import (
    DocumentNeedProtocolError,
    parse_pass1_verdict,
    parse_pass2_verdict,
)
from legalforecast.document_need.types import Pass1Verdict, Pass2Verdict

_JSON_FENCE = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.DOTALL)
LIVE_SMOKE_ENV = "LFB_LIVE_SMOKE"
CLEARED_LIVE_MODEL = "claude-haiku-4-5-20251001"


class DocumentNeedSelectorError(ValueError):
    """Raised when a selector verdict cannot be parsed."""


@dataclass(frozen=True, slots=True)
class FixtureClassifier:
    """Deterministic classifier for tests. Keys are candidate_id."""

    pass1: Mapping[str, Pass1Verdict]
    pass2: Mapping[str, Pass2Verdict]
    model_id: str = "fixture:document-need-v1"

    def classify_pass1(self, prompt: str, *, candidate_id: str) -> Pass1Verdict:
        del prompt
        try:
            return self.pass1[candidate_id]
        except KeyError as exc:
            raise DocumentNeedSelectorError(
                f"fixture has no pass-1 verdict for {candidate_id}"
            ) from exc

    def classify_pass2(self, prompt: str, *, candidate_id: str) -> Pass2Verdict:
        del prompt
        try:
            return self.pass2[candidate_id]
        except KeyError as exc:
            raise DocumentNeedSelectorError(
                f"fixture has no pass-2 verdict for {candidate_id}"
            ) from exc


def live_smoke_enabled(environ: Mapping[str, str] | None = None) -> bool:
    """Return whether the authorized live Haiku smoke may run."""

    source = os.environ if environ is None else environ
    return source.get(LIVE_SMOKE_ENV, "").strip() == "1"


def parse_json_object(raw_output: str) -> dict[str, object]:
    """Extract one JSON object from a model response, including fenced blocks."""

    text = raw_output.strip()
    fenced = _JSON_FENCE.search(text)
    if fenced is not None:
        text = fenced.group(1).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise DocumentNeedSelectorError("selector output is not JSON") from exc
    if not isinstance(parsed, dict):
        raise DocumentNeedSelectorError("selector output must be a JSON object")
    return cast(dict[str, object], parsed)


def verdict_from_pass1_output(raw_output: str, *, model_id: str) -> Pass1Verdict:
    """Parse pass-1 JSON from a fixture or live model."""

    try:
        return parse_pass1_verdict(parse_json_object(raw_output), model_id=model_id)
    except DocumentNeedProtocolError as exc:
        raise DocumentNeedSelectorError(str(exc)) from exc


def verdict_from_pass2_output(raw_output: str, *, model_id: str) -> Pass2Verdict:
    """Parse pass-2 JSON from a fixture or live model."""

    try:
        return parse_pass2_verdict(parse_json_object(raw_output), model_id=model_id)
    except DocumentNeedProtocolError as exc:
        raise DocumentNeedSelectorError(str(exc)) from exc
