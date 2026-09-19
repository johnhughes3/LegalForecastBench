from __future__ import annotations

import pytest
from legalforecast.jev.packets import require_request_fits


def _request(
    text: str, questions: dict[str, object] | None = None
) -> dict[str, object]:
    return {
        "model": "typesafe-ai/jev",
        "state": {"text": text},
        "questions": questions
        or {"q": {"type": "boolean", "instructions": "Dismissed?"}},
    }


def test_english_summary_over_old_byte_target_can_fit_without_truncation() -> None:
    text = "The court considers the motion and the parties arguments. " * 1300
    assert len(text.encode()) > 64_000
    request = _request(text)
    require_request_fits(request)
    assert request["state"] == {"text": text}


def test_state_plus_longest_question_has_its_own_token_limit() -> None:
    with pytest.raises(ValueError, match="state plus longest question"):
        require_request_fits(_request(" law" * 22_000))


def test_many_questions_can_exceed_total_without_exceeding_individual_limit() -> None:
    questions = {
        str(i): {"type": "boolean", "instructions": " law" * 1000} for i in range(44)
    }
    with pytest.raises(ValueError, match="total"):
        require_request_fits(_request("Record.", questions))
