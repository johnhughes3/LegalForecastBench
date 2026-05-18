from __future__ import annotations

import pytest
from legalforecast.path_safety import safe_path_component


@pytest.mark.parametrize("value", ["doc-1", "gov.uscourts.nysd.123.12.0", "abc_123"])
def test_safe_path_component_accepts_artifact_ids(value: str) -> None:
    assert safe_path_component(value, field_name="source_document_id") == value


@pytest.mark.parametrize(
    "value",
    ["", ".", "..", "../escape", "nested/doc", "nested\\doc", "doc:1"],
)
def test_safe_path_component_rejects_path_like_or_unsafe_ids(value: str) -> None:
    with pytest.raises(ValueError, match="source_document_id"):
        safe_path_component(value, field_name="source_document_id")
