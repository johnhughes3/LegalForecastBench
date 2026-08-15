"""Checked-in locations for the CLI characterization corpus."""

from __future__ import annotations

from pathlib import Path
from typing import cast

PACKAGE_DIR = Path("legalforecast/testing/cli_corpus")
DATA_DIR = PACKAGE_DIR / "data"
MANIFEST_PATH = DATA_DIR / "command_manifest.json"
HELP_DIR = DATA_DIR / "help"
IDENTITY_PATH = DATA_DIR / "path_identity.json"
TIMING_PATH = DATA_DIR / "xdist_timing.json"
DIFFERENTIAL_DIR = DATA_DIR / "differential"
PINNED_COLUMNS = 80
MANIFEST_SCHEMA_VERSION = 1
IDENTITY_SCHEMA_VERSION = 1
TIMING_SCHEMA_VERSION = 1
DIFFERENTIAL_SCHEMA_VERSION = 1


def dump_json(path: Path, payload: object) -> None:
    """Write canonical UTF-8 JSON used by the corpus ratchets."""

    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def load_json(path: Path) -> object:
    """Load a checked-in corpus JSON document."""

    import json

    return json.loads(path.read_text(encoding="utf-8"))


def as_object_dict(value: object) -> dict[str, object]:
    """Narrow a JSON object to ``dict[str, object]``."""

    if not isinstance(value, dict):
        raise ValueError("expected a JSON object")
    mapping = cast(dict[object, object], value)
    payload: dict[str, object] = {}
    for key, item in mapping.items():
        if not isinstance(key, str):
            raise ValueError("JSON object keys must be strings")
        payload[key] = item
    return payload


def as_object_list(value: object) -> list[object]:
    """Narrow a JSON array to ``list[object]``."""

    if not isinstance(value, list):
        raise ValueError("expected a JSON array")
    return list(cast(list[object], value))
