from __future__ import annotations

import io
import json
import logging

from legalforecast.logging import configure_logging, get_logger, pipeline_log_extra


def test_json_logging_includes_pipeline_context() -> None:
    stream = io.StringIO()
    configure_logging(stream=stream)
    logger = get_logger("legalforecast.tests")

    logger.info(
        "candidate excluded",
        extra=pipeline_log_extra(
            case_id="cand_2026_05_000481",
            source_hash="sha256:abc123",
            stage="eligibility",
            decision="exclude",
            exclusion_reason="outcome_leakage",
        ),
    )

    payload = json.loads(stream.getvalue())
    assert payload["message"] == "candidate excluded"
    assert payload["case_id"] == "cand_2026_05_000481"
    assert payload["source_hash"] == "sha256:abc123"
    assert payload["stage"] == "eligibility"
    assert payload["decision"] == "exclude"
    assert payload["exclusion_reason"] == "outcome_leakage"


def test_pytest_caplog_receives_structured_context(caplog) -> None:
    logger = get_logger("legalforecast.tests")

    with caplog.at_level(logging.INFO):
        logger.info(
            "packet built",
            extra=pipeline_log_extra(
                case_id="cand_2026_05_000482",
                source_hash="sha256:def456",
                stage="packet_build",
            ),
        )

    record = caplog.records[0]
    assert record.case_id == "cand_2026_05_000482"
    assert record.source_hash == "sha256:def456"
    assert record.stage == "packet_build"
