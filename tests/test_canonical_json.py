from __future__ import annotations

import pytest
from legalforecast.ingestion.canonical_json import canonical_json_bytes


class CanonicalJsonError(ValueError):
    pass


def test_canonical_json_bytes_is_deterministic() -> None:
    assert (
        canonical_json_bytes(
            {"z": "é", "a": 1},
            error_type=CanonicalJsonError,
            error_message="invalid artifact",
        )
        == '{"a":1,"z":"é"}\n'.encode()
    )


@pytest.mark.parametrize("value", (float("nan"), float("inf"), "\ud800", object()))
def test_canonical_json_bytes_maps_serialization_errors(value: object) -> None:
    with pytest.raises(CanonicalJsonError, match="invalid artifact"):
        canonical_json_bytes(
            {"value": value},
            error_type=CanonicalJsonError,
            error_message="invalid artifact",
        )
