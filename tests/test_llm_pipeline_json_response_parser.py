from __future__ import annotations

import pytest
from legalforecast.labeling.llm_pipeline import (
    LlmPipelineError,
    _json_object_from_response,
)


def test_json_response_parser_leaves_valid_json_unchanged() -> None:
    raw_output = '{"unit_seeds": [{"claim_name": "Count I"}]}'

    assert _json_object_from_response(raw_output) == {
        "unit_seeds": [{"claim_name": "Count I"}]
    }


def test_json_response_parser_leaves_fenced_json_unchanged() -> None:
    raw_output = '```json\n{"unit_seeds": [{"claim_name": "Count I"}]}\n```'

    assert _json_object_from_response(raw_output) == {
        "unit_seeds": [{"claim_name": "Count I"}]
    }


def test_json_response_parser_repairs_unambiguous_embedded_quotes() -> None:
    raw_output = '{"unit_seeds": [{"claim_name": "Rule "12(b)(6)" theory"}]}'

    assert _json_object_from_response(raw_output) == {
        "unit_seeds": [{"claim_name": 'Rule "12(b)(6)" theory'}]
    }


@pytest.mark.parametrize(
    "raw_output",
    [
        '{"text": "a "quoted", term"}',
        '{"text": "a "quoted" term}',
        '{"text": "valid",}',
    ],
)
def test_json_response_parser_rejects_ambiguous_or_other_malformed_json(
    raw_output: str,
) -> None:
    with pytest.raises(LlmPipelineError):
        _json_object_from_response(raw_output)
