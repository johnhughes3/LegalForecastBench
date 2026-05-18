"""HTTP configuration validation for live ingestion clients."""

from __future__ import annotations

import urllib.parse
from collections.abc import Collection


def validate_https_base_url(
    value: str,
    *,
    field_name: str,
    allowed_hosts: Collection[str],
    error_type: type[Exception] = ValueError,
) -> str:
    """Validate and normalize a token-bearing API base URL."""

    base_url = value.strip().rstrip("/")
    parsed = urllib.parse.urlparse(base_url)
    if parsed.scheme.lower() != "https":
        raise error_type(f"{field_name} must use https")
    if parsed.hostname is None:
        raise error_type(f"{field_name} must include a host")
    if parsed.username is not None or parsed.password is not None:
        raise error_type(f"{field_name} must not include credentials")
    if parsed.params or parsed.query or parsed.fragment:
        raise error_type(f"{field_name} must not include params, query, or fragment")

    try:
        port = parsed.port
    except ValueError as exc:
        raise error_type(f"{field_name} port must be valid") from exc
    if port not in {None, 443}:
        raise error_type(f"{field_name} must not specify a non-default port")

    normalized_host = parsed.hostname.lower()
    allowed = {host.lower() for host in allowed_hosts}
    if normalized_host not in allowed:
        joined_hosts = ", ".join(sorted(allowed))
        raise error_type(f"{field_name} host must be one of: {joined_hosts}")

    path = parsed.path.rstrip("/")
    return urllib.parse.urlunparse(("https", normalized_host, path, "", "", ""))
