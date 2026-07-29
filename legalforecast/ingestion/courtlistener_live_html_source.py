"""Run-level bot-challenge handling around the frozen CourtListener HTML source."""

from __future__ import annotations

import urllib.error
from dataclasses import dataclass

from legalforecast.ingestion.courtlistener_acquisition import (
    CourtListenerDocketHTMLSource,
)
from legalforecast.ingestion.courtlistener_client import (
    CourtListenerBotChallengeError,
    CourtListenerClientError,
)

_CHALLENGE_BODY_SCAN_LIMIT = 256_000
_CHALLENGE_INTERSTITIAL_MARKERS = (
    b"checking your browser before accessing",
    b"attention required! | cloudflare",
    b"<title>just a moment",
    b"verify you are human",
)
_CHALLENGE_PLATFORM_MARKER = b"challenge-platform"
_CHALLENGE_ELEMENT_MARKER = b"cf-chl-"
_UTF8_PREFIX_CHUNK_CHARACTERS = 4_096


@dataclass(frozen=True, slots=True)
class ChallengeStoppingCourtListenerDocketHTMLSource:
    """Turn marker-confirmed HTML into a legible run-level stop."""

    source: CourtListenerDocketHTMLSource

    def fetch(self, *, docket_id: str, source_url: str) -> str:
        """Fetch one docket while preserving non-challenge source outcomes."""

        try:
            raw_html = self.source.fetch(
                docket_id=docket_id,
                source_url=source_url,
            )
        except CourtListenerClientError as exc:
            cause = exc.__cause__
            if isinstance(cause, urllib.error.HTTPError):
                _raise_for_docket_html_challenge(
                    cause.read(_CHALLENGE_BODY_SCAN_LIMIT),
                    content_type=cause.headers.get("Content-Type"),
                )
            raise
        _raise_for_docket_html_challenge(
            _bounded_utf8_prefix(raw_html, max_bytes=_CHALLENGE_BODY_SCAN_LIMIT),
            content_type=None,
        )
        return raw_html


def _bounded_utf8_prefix(value: str, *, max_bytes: int) -> bytes:
    """Encode no more than ``max_bytes`` without materializing all of ``value``."""

    prefix = bytearray()
    for start in range(0, len(value), _UTF8_PREFIX_CHUNK_CHARACTERS):
        remaining = max_bytes - len(prefix)
        if remaining <= 0:
            break
        chunk = value[start : start + _UTF8_PREFIX_CHUNK_CHARACTERS].encode("utf-8")
        prefix.extend(chunk[:remaining])
        if len(chunk) >= remaining:
            break
    return bytes(prefix)


def _raise_for_docket_html_challenge(
    body: bytes,
    *,
    content_type: str | None,
) -> None:
    """Stop only for marker-confirmed HTML in the bounded response prefix."""

    bounded = body[:_CHALLENGE_BODY_SCAN_LIMIT].lower()
    normalized_content_type = (content_type or "").casefold()
    stripped = bounded.lstrip()
    is_html = normalized_content_type.startswith(
        ("text/html", "application/xhtml+xml")
    ) or stripped.startswith(b"<")
    has_interstitial_marker = any(
        marker in bounded for marker in _CHALLENGE_INTERSTITIAL_MARKERS
    )
    has_conjoined_challenge_signals = (
        _CHALLENGE_PLATFORM_MARKER in bounded and _CHALLENGE_ELEMENT_MARKER in bounded
    )
    if is_html and (has_interstitial_marker or has_conjoined_challenge_signals):
        raise CourtListenerBotChallengeError(
            "CourtListener returned marker-confirmed bot-challenge HTML; stop "
            "this acquisition run with prior candidate state preserved and "
            "treat this event as the Branch C trigger"
        )
