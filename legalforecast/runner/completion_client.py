"""Native GitHub watcher for the bounded benchmark completion command."""

from __future__ import annotations

import subprocess
import sys
import time
from collections.abc import Mapping

from legalforecast.runner.recovery_client import GhRecoveryClient, RecoveryError


class GhCompletionClient(GhRecoveryClient):
    """Keep device admission visible while GitHub's native watcher waits."""

    def watch_run(self, repo: str, run_id: int) -> Mapping[str, object]:
        run = self.get_run(repo, run_id)
        immediate_failures = 0
        while run.get("status") != "completed":
            print(
                f"Following https://github.com/{repo}/actions/runs/{run_id}",
                file=sys.stderr,
            )
            started = time.monotonic()
            try:
                subprocess.run(
                    [
                        "gh",
                        "run",
                        "watch",
                        str(run_id),
                        "--repo",
                        repo,
                        "--exit-status",
                    ],
                    check=False,
                    stdout=sys.stderr,
                    stderr=sys.stderr,
                )
            except OSError as exc:
                raise RecoveryError("native workflow watcher could not launch") from exc
            # Watcher token expiry does not establish provider failure. A fresh
            # brokered read restarts monitoring of this exact run, never its work.
            # A denied fresh read (403/missing grant) propagates without widening auth.
            run = self.get_run(repo, run_id)
            if run.get("status") == "completed":
                break
            immediate_failures = (
                immediate_failures + 1 if time.monotonic() - started < 30 else 0
            )
            if immediate_failures >= 3:
                break
            print(
                "Workflow remains active; restarting its native watcher "
                "with fresh broker access.",
                file=sys.stderr,
            )
        return run
