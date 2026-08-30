#!/usr/bin/env python3
"""Make ONE paid provider call and report the exact request and response shape.

**This script spends money.** It is the only thing in this repository that will
knowingly make a billable model call, and it refuses to run without an explicit
owner spend approval recorded on the command line.

Why it exists: two real defects reached the Gemini lane and were caught by
exactly this kind of single call, not by tests. The first was a reasoning
parameter nested differently than the documentation we read suggested -- it
would have returned HTTP 400 on the first paid dispatch of a hundred-case run.
The second was thinking tokens reported in a usage field the accounting never
read, which would have silently under-counted spend against an owner cost cap
and produced a run whose real cost nobody could reconstruct afterwards.

Provider documentation is necessary and not sufficient. For the providers this
adapter serves, the docs are also internally inconsistent in ways that matter:
xAI's REST reference and its capability page disagree about whether ``grok-4.6``
accepts ``reasoning_effort`` at all and about what the unset default is. If the
reference page were right, an unset request would run at ``low`` rather than
``high`` -- invisible in the response body and a large quality and cost swing
across a benchmark. Only a live call settles it.

What to check in the output, in order:

1. ``request_body`` -- did we send the reasoning parameter at the nesting the
   provider actually expects? A provider that ignores an unknown field will not
   tell you; compare ``reasoning_tokens`` across two runs at different efforts
   to prove the field is live rather than decorative.
2. ``usage`` -- every token field, printed verbatim and unfiltered. Reconcile
   the arithmetic yourself: if ``prompt + completion != total``, some billed
   category is missing from the two headline counts, and the adapter's
   ``reasoning_tokens_are_additive`` flag must match what you observe.
3. ``accounting_reconciliation`` -- what this repo's adapter would settle for
   this response, next to the provider's own reported totals. A mismatch here
   is the silent-undercount defect, caught before a paid dispatch rather than
   after one.
4. ``served_model`` -- the version the provider actually served. It must equal
   the registry's frozen ``model_version_or_snapshot`` or the run is not
   reproducible. xAI publishes no dated snapshot for grok-4.6 and has a
   documented precedent for silently rerouting a resolving slug to a different
   model at different pricing, so this field is the only substitution signal.
5. ``finish_reason`` -- ``length`` means the output cap truncated the answer.

Usage:

    uv run scripts/probe_openai_compatible_provider.py \\
        --registry model_registries/<registry>.json \\
        --model-key xai:grok-4.6 \\
        --owner-spend-approval "John 2026-08-30: USD <amount> for shape probes"

The probe sends a deliberately tiny prompt, but reasoning models bill for
thinking tokens regardless of prompt size, so cost is not zero and is not
fully predictable in advance. Run it once per provider, read the output, and
record the findings in the registry entry's caveats before any paid dispatch.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, cast

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from legalforecast.evals.live_model_solver import (  # noqa: E402
    LiveModelSolverError,
    complete_live_prompt,
    urlopen_json,
)
from legalforecast.evals.model_registry import (  # noqa: E402
    ModelRegistryEntry,
    load_model_registry,
)

PROBE_PROMPT = 'Reply with only this JSON object and nothing else: {"probe": "ok"}'


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Make one paid provider call and print its exact request and "
            "response shape. Requires an explicit owner spend approval."
        ),
    )
    parser.add_argument(
        "--registry",
        required=True,
        type=Path,
        help="Path to the model registry JSON containing the entry to probe.",
    )
    parser.add_argument(
        "--model-key",
        required=True,
        help="Registry key to probe, formatted provider:model_id.",
    )
    parser.add_argument(
        "--owner-spend-approval",
        required=True,
        help=(
            "Verbatim owner approval for this spend, including who approved it, "
            "the date, and the approximate dollar amount. Recorded in the "
            "output. This probe makes a BILLABLE provider call."
        ),
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=300.0,
        help="Request timeout. Reasoning models at high effort can be slow.",
    )
    args = parser.parse_args(argv)

    approval = str(args.owner_spend_approval).strip()
    if not approval:
        parser.error("--owner-spend-approval must not be empty")

    registry_path = cast(Path, args.registry)
    entry = _select_entry(registry_path, str(args.model_key))

    request_bodies: list[dict[str, Any]] = []

    def observe_request_body(body: bytes) -> None:
        request_bodies.append(cast(dict[str, Any], json.loads(body.decode("utf-8"))))

    raw_payloads: list[dict[str, Any]] = []

    def observing_transport(request: Any, timeout_seconds: float) -> Any:
        # Wraps the real network transport so the unfiltered provider payload is
        # captured even when a later validation step rejects the response. The
        # rejected body is usually the most informative part of a probe.
        payload = urlopen_json(request, timeout_seconds)
        raw_payloads.append(cast(dict[str, Any], dict(payload)))
        return payload

    report: dict[str, Any] = {
        "owner_spend_approval": approval,
        "registry": str(registry_path),
        "model_key": entry.registry_key,
        "frozen_model_version_or_snapshot": entry.model_version_or_snapshot,
        "requested_reasoning_effort": (
            entry.reasoning_effort.value if entry.reasoning_effort else None
        ),
        "requested_max_output_tokens": entry.max_output_tokens,
    }

    try:
        response = complete_live_prompt(
            entry,
            PROBE_PROMPT,
            transport=observing_transport,
            timeout_seconds=float(args.timeout_seconds),
            max_attempts=1,
            request_body_observer=observe_request_body,
        )
    except LiveModelSolverError as exc:
        report["outcome"] = "failed"
        report["error_type"] = type(exc).__name__
        report["error"] = str(exc)
        report["request_body"] = request_bodies[-1] if request_bodies else None
        report["raw_response"] = raw_payloads[-1] if raw_payloads else None
        _emit(report)
        return 1

    raw = raw_payloads[-1] if raw_payloads else {}
    report["outcome"] = "succeeded"
    report["request_body"] = request_bodies[-1] if request_bodies else None
    metadata: dict[str, str] = dict(response.metadata or {})
    report["usage"] = raw.get("usage")
    report["served_model"] = metadata.get("served_model_version")
    report["finish_reason"] = metadata.get("response_finish_reason")
    report["raw_output"] = response.raw_output
    report["accounting_reconciliation"] = _reconcile(response, raw)
    report["raw_response"] = raw
    _emit(report)
    return 0


def _reconcile(response: Any, raw: dict[str, Any]) -> dict[str, Any]:
    """Compare what this repo would bill against what the provider reported.

    The headline check is whether the adapter's output-token count exceeds the
    provider's visible ``completion_tokens``. If a provider reports reasoning
    tokens additively and the adapter does not add them, this is where the
    undercount shows up -- before a paid dispatch instead of after one.
    """

    raw_usage: object = raw.get("usage")
    usage_record: dict[str, Any] = (
        cast(dict[str, Any], raw_usage) if isinstance(raw_usage, dict) else {}
    )
    prompt_tokens = _int_or_none(usage_record.get("prompt_tokens"))
    completion_tokens = _int_or_none(usage_record.get("completion_tokens"))
    total_tokens = _int_or_none(usage_record.get("total_tokens"))
    arithmetic: dict[str, Any] = {"reported_total": total_tokens}
    if prompt_tokens is not None and completion_tokens is not None:
        prompt_plus_completion = prompt_tokens + completion_tokens
        arithmetic["prompt_plus_completion"] = prompt_plus_completion
        if total_tokens is not None:
            arithmetic["unaccounted_tokens"] = total_tokens - prompt_plus_completion
            arithmetic["interpretation"] = (
                "reasoning tokens appear ADDITIVE: total exceeds "
                "prompt+completion, so reasoning_tokens_are_additive must be True"
                if total_tokens > prompt_plus_completion
                else "reasoning tokens appear INCLUDED in completion_tokens"
            )
    return {
        "provider_reported_usage": usage_record,
        "adapter_settled_input_tokens": response.input_tokens,
        "adapter_settled_output_tokens": response.output_tokens,
        "adapter_settled_cost_usd": response.estimated_cost,
        "arithmetic": arithmetic,
    }


def _int_or_none(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _select_entry(registry_path: Path, model_key: str) -> ModelRegistryEntry:
    registry = load_model_registry(registry_path)
    for entry in registry.entries:
        if entry.registry_key == model_key:
            return entry
    available = sorted(entry.registry_key for entry in registry.entries)
    raise SystemExit(
        f"model key {model_key!r} is not in {registry_path}; available: {available}"
    )


def _emit(report: dict[str, Any]) -> None:
    json.dump(report, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    if os.environ.get("LFB_PROBE_DRY_RUN"):
        # Escape hatch for CI and for anyone verifying the script imports and
        # parses arguments without making a billable call.
        print("LFB_PROBE_DRY_RUN set: refusing to make a paid provider call")
        raise SystemExit(0)
    raise SystemExit(main())
