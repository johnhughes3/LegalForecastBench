from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from typing import cast

import pytest
from legalforecast.contracts import ARTIFACT_CANONICAL_JSON_V1
from legalforecast.release import ForecastExecution
from legalforecast.runner import RunValidationError, validate_executable_packets


def executable_packet_bytes(*, case_id: str, unit_id: str, decision_date: str) -> bytes:
    """Return one complete synthetic runner packet for focused tests."""

    return ARTIFACT_CANONICAL_JSON_V1.encode(
        {
            "case_id": case_id,
            "claim_name": unit_id,
            "count": "Count I",
            "decision_date": decision_date,
            "defendant_group": "defendants",
            "model_visible_document_ids": [f"{case_id}-motion"],
            "policy_digest": "1" * 64,
            "unit_id": unit_id,
        }
    )


def test_executable_packet_rejects_unit_binding_mismatch() -> None:
    unit = SimpleNamespace(case_id="case-001", unit_id="unit-001")
    release = SimpleNamespace(
        cases=(SimpleNamespace(case_id="case-001"),),
        prediction_units=(unit,),
    )

    class MismatchedExecution:
        def __init__(self) -> None:
            self.release = release

        def packet_bytes(self, unit_id: str) -> bytes:
            assert unit_id == "unit-001"
            return executable_packet_bytes(
                case_id="case-001",
                unit_id="unit-other",
                decision_date="2026-08-23",
            )

    with pytest.raises(RunValidationError, match="unit_id differs for unit unit-001"):
        validate_executable_packets(
            cast(ForecastExecution, MismatchedExecution()),
            release_anchor=date(2026, 8, 23),
        )
