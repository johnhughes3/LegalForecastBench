"""Metadata contract shared by benchmark-output and scoring workflow checks.

CI statically checks the embedded workflow producer and consumer against these
fields, including the legacy shape that predates recovery budget metadata.
"""

from typing import Literal, NotRequired, TypedDict


class ForecastRunMetadata(TypedDict):
    """Persisted forecast-run.json; budget fields are an all-or-none extension."""

    schema_version: Literal[
        "legalforecast.forecast-run.v1"  # contract-ratchet: allow typing Literal
    ]
    workflow_run_id: int
    workflow_run_attempt: int
    release_sha: str
    manifest_uri: str
    forecast_release_uri: str
    artifact_root_uri: str
    model_registry_uri: str
    model_key: str
    run_identity_sha256: str
    forecast_release_digest: str
    model_registry_sha256: str
    repeat_count: int
    account: NotRequired[str]
    ceiling_microusd: NotRequired[int]
