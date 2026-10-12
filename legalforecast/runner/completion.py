"""Follow one native forecast through bounded protected recovery and scoring."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol

from legalforecast.runner.completion_artifacts import (
    artifact_record,
    dispatched_run_id,
    exact_artifact,
)
from legalforecast.runner.completion_scoring import save_scored_artifact, scoring_inputs
from legalforecast.runner.recovery import (
    RECOVERY_WORKFLOW,
    SOURCE_WORKFLOW,
    RecoveryClient,
    RecoveryPlan,
    build_recovery_plan,
)
from legalforecast.runner.recovery_client import RecoveryError

SCORE_WORKFLOW = ".github/workflows/fan-in-publish.yaml"


class CompletionClient(RecoveryClient, Protocol):
    """Existing recovery access plus GitHub's native workflow watcher."""

    def watch_run(self, repo: str, run_id: int) -> Mapping[str, object]: ...


def _terminal(
    client: CompletionClient, repo: str, run_id: int, workflow: str
) -> Mapping[str, object]:
    run = client.watch_run(repo, run_id)
    if (
        run.get("id") != run_id
        or run.get("path") != workflow
        or run.get("event") != "workflow_dispatch"
        or run.get("head_branch") != "main"
    ):
        raise RecoveryError(
            "completion workflow identity differs from exact requested run"
        )
    if run.get("status") != "completed":
        raise RecoveryError(
            "watch_interrupted: workflow remains active or awaiting device admission"
        )
    return run


def _protected_child(
    client: CompletionClient,
    repo: str,
    recovery_id: int,
    recovery: Mapping[str, object],
    plan: RecoveryPlan,
) -> int | None:
    attempt = recovery.get("run_attempt")
    if type(attempt) is not int or attempt <= 0:
        raise RecoveryError("protected recovery attempt is invalid")
    result = artifact_record(
        exact_artifact(
            client,
            repo,
            recovery_id,
            f"protected-recovery-result-{recovery_id}-{attempt}",
        ),
        "lfb-protected-recovery-result.json",
    )
    if (
        result.get("source_run_id") != plan.source_run_id
        or result.get("source_run_attempt") != plan.source_run_attempt
        or result.get("dispatch_safe") is not True
        or result.get("cap_microusd") != plan.frozen_identity.ceiling_microusd
        or result.get("blocked_reasons") != []
    ):
        raise RecoveryError(
            "protected recovery is blocked or differs from original budget identity"
        )
    projected = result.get("projected_committed_microusd")
    if (
        type(projected) is not int
        or not 0 <= projected <= plan.frozen_identity.ceiling_microusd
    ):
        raise RecoveryError(
            "protected recovery budget remains uncertain or exceeds cap"
        )
    child = artifact_record(
        exact_artifact(
            client,
            repo,
            recovery_id,
            f"recovery-child-dispatch-{recovery_id}-{attempt}",
        ),
        "lfb-child-dispatch.json",
    )
    if (
        child.get("source_run_id") != plan.source_run_id
        or child.get("source_run_attempt") != plan.source_run_attempt
        or child.get("recovery_run_id") != recovery_id
        or child.get("recovery_run_attempt") != attempt
    ):
        raise RecoveryError(
            "protected child handoff differs from exact source/recovery attempt"
        )
    return dispatched_run_id(child, repo, SOURCE_WORKFLOW)


def complete_native_run(
    client: CompletionClient,
    *,
    repo: str,
    run_id: int,
    cycle_id: str,
    labels_release_uri: str,
    output_dir: Path,
    publish: bool = False,
    max_recoveries: int = 1,
    max_parallel: int = 8,
) -> dict[str, object]:
    """Run the supported protected stages; stop honestly on unresolved handoffs."""
    if (
        output_dir.exists()
        or not output_dir.parent.is_dir()
        or not 0 <= max_recoveries <= 8
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", cycle_id)
        or not re.fullmatch(r"s3://[A-Za-z0-9.-]+/[^\s]+", labels_release_uri)
    ):
        raise RecoveryError(
            "completion requires a new output directory, valid cycle/labels URI "
            "and bounded recovery limit"
        )
    if run_id <= 0 or not 1 <= max_parallel <= 32:
        raise RecoveryError(
            "positive workflow ID and concurrency between 1 and 32 required"
        )
    result: dict[str, object] = {
        "status": "following",
        "forecast_run_id": run_id,
        "recoveries": [],
        "website_integrated": False,
        "paper_integrated": False,
    }
    recoveries: list[dict[str, object]] = []
    result["recoveries"] = recoveries
    plan: RecoveryPlan | None = None
    original: dict[str, object] | None = None
    previous_census: tuple[int, int] | None = None
    no_progress = 0
    try:
        for round_index in range(max_recoveries + 1):
            _terminal(client, repo, run_id, SOURCE_WORKFLOW)
            plan = build_recovery_plan(
                client, repo=repo, run_id=run_id, ref="main", max_parallel=max_parallel
            )
            frozen = plan.frozen_identity.to_record()
            stable = {
                key: value
                for key, value in frozen.items()
                if key not in {"release_sha", "artifact_retention_days"}
            }
            if original is not None and stable != original:
                raise RecoveryError(
                    "recovered child changed the original model, corpus "
                    "or spend identity"
                )
            original = stable
            if plan.frozen_identity.jev_summaries_uri:
                raise RecoveryError(
                    "run complete supports only regular native full-document forecasts"
                )
            blocks = [
                reason
                for reason in plan.blocked_reasons
                if reason != "source run has no incomplete cells"
            ]
            if blocks:
                raise RecoveryError("; ".join(blocks))
            if plan.incomplete_cells == 0:
                if plan.identity_source_attempt != plan.source_run_attempt:
                    raise RecoveryError(
                        "complete forecast identity belongs to an older attempt"
                    )
                break
            census = (plan.completed_cells, plan.incomplete_cells)
            no_progress = no_progress + 1 if census == previous_census else 0
            previous_census = census
            if no_progress >= 3:
                raise RecoveryError(
                    "three recoveries made no progress; inspect repeated failures"
                )
            if round_index == max_recoveries:
                raise RecoveryError(
                    "bounded recovery limit reached with incomplete forecast cells"
                )
            dispatch = client.dispatch(
                repo, RECOVERY_WORKFLOW, "main", plan.dispatch_inputs
            )
            handoff: dict[str, object] = (
                dict(dispatch)
                if dispatch is not None
                else {"dispatched": True, "status": "dispatched_unresolved"}
            )
            recoveries.append(handoff)
            recovery_id = dispatched_run_id(dispatch, repo, RECOVERY_WORKFLOW)
            if recovery_id is None:
                result["status"] = "dispatched_unresolved"
                return result
            recovery = _terminal(client, repo, recovery_id, RECOVERY_WORKFLOW)
            if recovery.get("conclusion") != "success":
                raise RecoveryError(
                    "protected recovery failed; budget or admission requires inspection"
                )
            child_id = _protected_child(client, repo, recovery_id, recovery, plan)
            if child_id is None:
                result.update(
                    status="dispatched_unresolved", recovery_run_id=recovery_id
                )
                return result
            run_id = child_id
            result["forecast_run_id"] = run_id
        assert plan is not None
        dispatch = client.dispatch(
            repo,
            SCORE_WORKFLOW,
            "main",
            scoring_inputs(plan, cycle_id, labels_release_uri, publish),
        )
        result["scoring_dispatch"] = dispatch or {
            "dispatched": True,
            "status": "dispatched_unresolved",
        }
        score_id = dispatched_run_id(dispatch, repo, SCORE_WORKFLOW)
        if score_id is None:
            result["status"] = "dispatched_unresolved"
            return result
        result["scoring_run_id"] = score_id
        scored = _terminal(client, repo, score_id, SCORE_WORKFLOW)
        if scored.get("conclusion") != "success":
            raise RecoveryError("protected scoring/publication failed")
        payload = exact_artifact(
            client, repo, score_id, f"protected-labels-fan-in-{cycle_id}-{score_id}"
        )
        cases, units = save_scored_artifact(payload, output_dir, plan)
        result.update(
            status="scored",
            case_count=cases,
            scored_unit_count=units,
            output_dir=str(output_dir),
            published=publish,
        )
    except RecoveryError as exc:
        result.update(status="blocked", reason=str(exc))
    return result
