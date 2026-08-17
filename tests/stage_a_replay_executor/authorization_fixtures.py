"""Synthetic authorization rewrites for fail-closed replay-spec tests."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from legalforecast.contracts import ARTIFACT_CANONICAL_JSON_V1
from tests.stage_a_replay_executor.fixtures import (
    read_spec,
    record_sha256,
    replay_descriptor,
    write_spec_record,
)


def refresh_authorization_descriptor(
    path: Path, record: dict[str, object], *, validate: bool = True
) -> Path:
    """Refresh the synthetic authorization after an intentional spec mutation."""

    authorization = cast(dict[str, object], record["authorization"])
    artifact_path = Path(cast(str, authorization["artifact_path"]))
    artifact = cast(dict[str, object], json.loads(artifact_path.read_text()))
    artifact["replay_descriptor_sha256"] = record_sha256(replay_descriptor(record))
    artifact_path.write_bytes(ARTIFACT_CANONICAL_JSON_V1.encode(artifact))
    authorization["artifact_sha256"] = hashlib.sha256(
        artifact_path.read_bytes()
    ).hexdigest()
    return write_spec_record(path, record, validate=validate)


def rewrite_authorization_artifact(
    path: Path, updates: Mapping[str, object], *, validate: bool = False
) -> Path:
    """Rewrite the fixture authorization artifact and refresh only its byte pin."""

    record = read_spec(path)
    authorization = cast(dict[str, object], record["authorization"])
    artifact_path = Path(cast(str, authorization["artifact_path"]))
    artifact = cast(dict[str, object], json.loads(artifact_path.read_text()))
    artifact.update(updates)
    artifact_path.write_bytes(ARTIFACT_CANONICAL_JSON_V1.encode(artifact))
    authorization["artifact_sha256"] = hashlib.sha256(
        artifact_path.read_bytes()
    ).hexdigest()
    return write_spec_record(path, record, validate=validate)
