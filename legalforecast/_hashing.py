"""Internal hashing predicate helpers."""

_HEX_DIGITS = "0123456789abcdef"
_SHA256_HEX_LENGTH = 64
_SHA256_PREFIX = "sha256:"


def is_lowercase_sha256(value: str) -> bool:
    """Return whether value is a lowercase raw SHA-256 hex digest."""
    return len(value) == _SHA256_HEX_LENGTH and all(
        character in _HEX_DIGITS for character in value
    )


def is_sha256_digest(value: str, *, allow_prefix: bool = False) -> bool:
    """Return whether value is a SHA-256 digest, optionally allowing sha256: prefix."""
    candidate = value
    if allow_prefix and candidate.startswith(_SHA256_PREFIX):
        candidate = candidate.removeprefix(_SHA256_PREFIX)
    return is_lowercase_sha256(candidate)
