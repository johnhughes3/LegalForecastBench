"""Stop new Jev calls after three failed case executions in this run attempt."""

from __future__ import annotations

import json
import sys
from pathlib import Path

JOB_PREFIX = "Vercel AI Gateway and TypeSafe Jev resumable forecast cells"
EXECUTE_STEP = "Execute exact Gateway or TypeSafe Jev forecast cell"
FAILURE_LIMIT = 3


def main(path: Path) -> int:
    """Read all pages from the attempt-specific GitHub jobs endpoint."""
    pages = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(pages, list) or not pages:
        raise ValueError("expected nonempty GitHub jobs pages")
    failed_ids: set[int] = set()
    for page in pages:
        for job in page["jobs"]:
            if not job["name"].startswith(JOB_PREFIX):
                continue
            # Guard-blocked jobs, cancellations and upload failures did not
            # fail a provider execution. Do not count them toward the limit.
            if any(
                step["name"] == EXECUTE_STEP and step["conclusion"] == "failure"
                for step in job["steps"]
            ):
                failed_ids.add(job["id"])
    failures = len(failed_ids)
    print(f"Jev failed case executions: {failures}/{FAILURE_LIMIT}")
    if failures >= FAILURE_LIMIT:
        print("Jev failure allowance reached; leaving this case for recovery.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1])))
