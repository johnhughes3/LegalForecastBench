"""Prompt construction for the managed official document-tool agent."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Protocol


class _ManagedPromptInput(Protocol):
    @property
    def case_id(self) -> str: ...

    @property
    def unit_descriptions(self) -> Sequence[Mapping[str, str]]: ...

    @property
    def document_descriptions(self) -> Sequence[Mapping[str, str]]: ...


def managed_initial_prompt(managed_case: _ManagedPromptInput) -> str:
    return json.dumps(
        {
            "case_id": managed_case.case_id,
            "task": "forecast_motion_to_dismiss",
            "prediction_units": list(managed_case.unit_descriptions),
            "documents": list(managed_case.document_descriptions),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
