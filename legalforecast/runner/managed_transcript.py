"""Write SDK-native conversations for credential-free recovery."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from openai import APIConnectionError, APITimeoutError
from pydantic_ai import ModelAPIError, ModelHTTPError, ModelMessagesTypeAdapter
from pydantic_ai.messages import ModelMessage

from legalforecast.immutable_io import write_file_replace_safe
from legalforecast.runner.provider_auth import ProviderAuthentication


def write_managed_transcript(
    transcript_path: Path | None,
    *,
    model: str,
    cell: str,
    status: str,
    messages: Sequence[ModelMessage],
    authentication: ProviderAuthentication | None = None,
    error: BaseException | None = None,
) -> None:
    """Persist SDK-native message history without serializing exception state."""

    if transcript_path is None or not messages:
        return
    encoded_messages = ModelMessagesTypeAdapter.dump_json(list(messages))
    envelope = {
        "model": model,
        "cell": cell,
        "agent_status": status,
        "messages": json.loads(encoded_messages),
        **({"authentication": authentication.provenance()} if authentication else {}),
    }
    if isinstance(error, ModelAPIError):
        envelope["provider_failure"] = {
            "category": provider_error_category(error),
            "status_code": error.status_code
            if isinstance(error, ModelHTTPError)
            else None,
        }
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    write_file_replace_safe(
        transcript_path,
        (
            json.dumps(
                envelope,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8"),
        mode=0o600,
    )


def provider_error_category(
    error: ModelAPIError,
) -> Literal["timeout", "connection", "http", "other"]:
    """Classify SDK exceptions without copying their sensitive diagnostic text."""

    if isinstance(error, ModelHTTPError):
        return "http"
    cause: BaseException | None = error
    # SDK wrappers preserve their underlying exception as the explicit cause.
    # Bound traversal, including deliberately cyclic exception chains.
    for _ in range(8):
        if isinstance(cause, APITimeoutError):
            return "timeout"
        if isinstance(cause, APIConnectionError):
            return "connection"
        if cause is None:
            break
        cause = cause.__cause__
    return "other"
