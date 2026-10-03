"""Check that official interrupted-summary recovery names a stopped producer."""

import os
import re
from collections.abc import Mapping

from legalforecast.artifact_archive import json_command, metadata_object


def require_terminal_summary_source(
    metadata: Mapping[str, object], run_id: int
) -> None:
    """Reject a live, successful, unrelated or mismatched predecessor run."""
    if (
        type(run_id) is not int
        or run_id <= 0
        or type(metadata.get("id")) is not int
        or metadata.get("id") != run_id
        or metadata.get("path") != ".github/workflows/prepare-jev-summaries.yaml"
        or metadata.get("status") != "completed"
        or metadata.get("conclusion") not in {"cancelled", "timed_out", "failure"}
    ):
        raise ValueError(
            "interrupted retry requires the exact terminal unsuccessful "
            "summary workflow"
        )


def require_terminal_summary_run(run_id: int | None) -> None:
    """Read current brokered GitHub state before any interrupted retry spends."""
    if type(run_id) is not int or run_id <= 0:
        raise ValueError("interrupted retry requires its exact prior summary run ID")
    repository = os.environ.get("GITHUB_REPOSITORY")
    if repository is None:
        repository = metadata_object(
            json_command(["gh", "repo", "view", "--json", "nameWithOwner"])
        ).get("nameWithOwner")
    if not isinstance(repository, str) or not re.fullmatch(
        r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository
    ):
        raise ValueError("interrupted retry requires the source repository")
    metadata = metadata_object(
        json_command(["gh", "api", f"repos/{repository}/actions/runs/{run_id}"])
    )
    require_terminal_summary_source(metadata, run_id)
