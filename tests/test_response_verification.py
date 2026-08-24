from __future__ import annotations

import pytest
from legalforecast.evals.response_verification import (
    RESPONSE_VERIFICATION_SCHEMA_FIELD,
    ResponseVerification,
    require_publishable_response_metadata,
)


def test_publishable_response_metadata_accepts_clean_schema() -> None:
    require_publishable_response_metadata(ResponseVerification(()).to_metadata())


def test_publishable_response_metadata_requires_schema() -> None:
    metadata = ResponseVerification(()).to_metadata()
    metadata.pop(RESPONSE_VERIFICATION_SCHEMA_FIELD)

    with pytest.raises(ValueError, match="schema"):
        require_publishable_response_metadata(metadata)


@pytest.mark.parametrize(
    ("verification", "message"),
    (
        (
            ResponseVerification(("$.groundingMetadata",)),
            "grounding or search",
        ),
        (
            ResponseVerification((), finish_reason="max_output_tokens", truncated=True),
            "requires retry",
        ),
        (
            ResponseVerification(
                (),
                finish_reason="content_filter",
                content_filter=True,
            ),
            "content filter",
        ),
    ),
)
def test_publishable_response_metadata_rejects_unpublishable_flags(
    verification: ResponseVerification,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        require_publishable_response_metadata(verification.to_metadata())


def test_publishable_response_metadata_rejects_inconsistent_flags() -> None:
    metadata = ResponseVerification(()).to_metadata()
    metadata["response_truncated"] = "true"

    with pytest.raises(ValueError, match="disagree"):
        require_publishable_response_metadata(metadata)
