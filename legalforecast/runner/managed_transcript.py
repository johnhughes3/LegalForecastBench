"""Write SDK-native conversations for credential-free recovery."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from pydantic_ai import ModelMessagesTypeAdapter
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
