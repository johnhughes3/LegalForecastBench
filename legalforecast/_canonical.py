"""Small canonical JSON and payload-digest helpers shared by public code."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def canonical_json(payload: Any) -> str:
    """Serialize a JSON-compatible value with stable key ordering."""

    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


# contract-ratchet: allow shared public-release digest helper
def sha256_file(path: str | Path) -> str:
    """Return the digest of a file used as a public release artifact."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
