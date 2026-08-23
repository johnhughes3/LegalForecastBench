"""Resumable local Luna-only runner for the frozen Cycle 1 forecast packets."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from legalforecast.evals.inspect_task import build_inspect_samples, run_inspect_fixture
from legalforecast.evals.live_model_solver import LiveModelSolver
from legalforecast.evals.model_registry import load_model_registry
from legalforecast.evals.per_case_runner import (
    _model_packet_from_record,  # pyright: ignore[reportPrivateUsage]
)
from legalforecast.evals.provider_spend_attempt_handler import (
    ProviderSpendAttemptHandler,
    conservative_reservation_microusd,
)
from legalforecast.evals.provider_spend_control import (
    FrozenAttemptPolicy,
    ProviderSpendKey,
    SqliteProviderSpendAuthority,
)
from legalforecast.evals.response_verification import (
    output_statuses_from_run_records,
    response_verification_summary_from_run_records,
)

MODEL_KEY = "openai:gpt-5.6-luna"
MANIFEST_DIGEST = "8e1c2b2d428f8be9cb53ea4a41fc24571617306effdc72fac5b47e791d5889b1"
SPEND_APPROVAL = (
    "OK I approve up to USD 100 of provider spend for Cycle 1 run on Luna ONLY "
    "please -- skip others for now."
)
MANIFEST_APPROVAL = (
    f"I approve corpus manifest {MANIFEST_DIGEST} as the frozen Cycle 1 forecast "
    "corpus."
)
CAP_MICROUSD = 100_000_000
ACCOUNT = "cycle-1-local-luna"


class LocalLunaRunnerError(RuntimeError):
    """Raised before unsafe, ambiguous, or identity-drifting local execution."""


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _read_json(path: Path) -> object:
    if path.is_symlink() or not path.is_file():
        raise LocalLunaRunnerError(f"input must be a regular non-symlink file: {path}")
    return json.loads(path.read_bytes())


def _owner_approvals() -> dict[str, str]:
    completed = subprocess.run(
        ["bd", "comments", "legalforecastbench-3ak.38", "--json"],
        check=True,
        capture_output=True,
        text=True,
    )
    rows: object = json.loads(completed.stdout)
    if not isinstance(rows, list):
        raise LocalLunaRunnerError("Beads comments response is not an array")
    evidence: dict[str, str] = {}
    for raw in cast(list[object], rows):
        if not isinstance(raw, Mapping):
            continue
        row = cast(Mapping[str, object], raw)
        if row.get("author") != "John Hughes":
            continue
        text = row.get("text")
        comment_id = row.get("id")
        if text in {SPEND_APPROVAL, MANIFEST_APPROVAL} and isinstance(comment_id, str):
            evidence[cast(str, text)] = comment_id
    for required in (SPEND_APPROVAL, MANIFEST_APPROVAL):
        if required not in evidence:
            raise LocalLunaRunnerError(f"missing exact owner approval: {required}")
    return evidence


def _load_inputs(
    run_inputs_path: Path, run_record_path: Path
) -> tuple[dict[str, Any], dict[str, Any]]:
    run_inputs = _read_json(run_inputs_path)
    run_record = _read_json(run_record_path)
    if not isinstance(run_inputs, Mapping) or not isinstance(run_record, Mapping):
        raise LocalLunaRunnerError("run inputs and run record must be JSON objects")
    run_inputs = cast(Mapping[str, object], run_inputs)
    run_record = cast(Mapping[str, object], run_record)
    if run_record.get("manifest_sha256") != MANIFEST_DIGEST:
        raise LocalLunaRunnerError(
            "run record manifest digest differs from owner approval"
        )
    owner = run_record.get("owner_signature_reference")
    if (
        not isinstance(owner, Mapping)
        or cast(Mapping[str, object], owner).get("approval_line") != MANIFEST_APPROVAL
    ):
        raise LocalLunaRunnerError("run record lacks the exact manifest approval line")
    if run_record.get("docket_tool_enabled") is not False:
        raise LocalLunaRunnerError("run record does not disable the docket tool")
    if run_record.get("provider_calls_made") != 0:
        raise LocalLunaRunnerError(
            "forecast packet build unexpectedly made provider calls"
        )
    packets = run_inputs.get("model_packets")
    if not isinstance(packets, list) or len(cast(list[object], packets)) != 200:
        raise LocalLunaRunnerError("run inputs must contain exactly 200 packets")
    return dict(run_inputs), dict(run_record)


def _select_rows(
    run_inputs: Mapping[str, Any], selectors: Sequence[str]
) -> list[dict[str, Any]]:
    requested = set(selectors)
    select_all = not requested
    selected: list[dict[str, Any]] = []
    for raw in cast(list[object], run_inputs["model_packets"]):
        if not isinstance(raw, Mapping):
            raise LocalLunaRunnerError("packet inventory row is not an object")
        row = cast(Mapping[str, object], raw)
        identity = f"{row.get('case_id')}:{row.get('ablation')}"
        if select_all or identity in requested:
            selected.append(dict(row))
            requested.discard(identity)
    if requested:
        raise LocalLunaRunnerError(f"unknown packet selectors: {sorted(requested)}")
    return selected


def run(args: argparse.Namespace) -> int:
    run_inputs_path = Path(args.run_inputs).resolve()
    run_record_path = Path(args.run_record).resolve()
    registry_path = Path(args.registry).resolve()
    packet_root = Path(args.packet_root).resolve()
    output_root = Path(args.output_root).resolve()
    prior_committed_microusd = args.prior_committed_microusd
    if (
        isinstance(prior_committed_microusd, bool)
        or prior_committed_microusd < 0
        or prior_committed_microusd >= CAP_MICROUSD
    ):
        raise LocalLunaRunnerError(
            "prior_committed_microusd must be between zero and the owner ceiling"
        )
    effective_cap_microusd = CAP_MICROUSD - prior_committed_microusd
    run_inputs, run_record = _load_inputs(run_inputs_path, run_record_path)
    approvals = _owner_approvals()
    registry_bytes = registry_path.read_bytes()
    registry = load_model_registry(registry_path)
    entries = [entry for entry in registry.entries if entry.registry_key == MODEL_KEY]
    if len(entries) != 1:
        raise LocalLunaRunnerError("registry must contain exactly one Luna entry")
    entry = entries[0]
    if (
        entry.provider != "openai"
        or not entry.network_disabled
        or not entry.search_disabled
    ):
        raise LocalLunaRunnerError("Luna registry safety fields differ")
    rows = _select_rows(run_inputs, args.packet)
    if args.shard_count <= 0:
        raise LocalLunaRunnerError("shard_count must be positive")
    if args.shard_index < 0 or args.shard_index >= args.shard_count:
        raise LocalLunaRunnerError("shard_index must be in [0, shard_count)")
    rows = rows[args.shard_index :: args.shard_count]
    if args.max_calls is not None:
        rows = rows[: args.max_calls]
    if not rows:
        raise LocalLunaRunnerError("no packet rows selected")
    authority_identity = _sha(
        json.dumps(
            {
                "approval": SPEND_APPROVAL,
                "manifest": MANIFEST_DIGEST,
                "model_key": MODEL_KEY,
                "owner_cap_microusd": CAP_MICROUSD,
                "prior_committed_microusd": prior_committed_microusd,
                "registry_sha256": _sha(registry_bytes),
                "run_inputs_sha256": _sha(run_inputs_path.read_bytes()),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    )
    plan = {
        "schema_version": "legalforecast.local_luna_plan.v1",
        "manifest_sha256": MANIFEST_DIGEST,
        "model_key": MODEL_KEY,
        "registry_sha256": _sha(registry_bytes),
        "run_inputs_sha256": _sha(run_inputs_path.read_bytes()),
        "run_record_sha256": _sha(run_record_path.read_bytes()),
        "cap_microusd": effective_cap_microusd,
        "owner_cap_microusd": CAP_MICROUSD,
        "prior_committed_microusd": prior_committed_microusd,
        "packet_count": len(rows),
        "packets": [f"{row['case_id']}:{row['ablation']}" for row in rows],
        "shard_count": args.shard_count,
        "shard_index": args.shard_index,
        "owner_comment_ids": sorted(approvals.values()),
        "dry_run": bool(args.dry_run),
    }
    print(json.dumps(plan, sort_keys=True))
    if args.dry_run:
        return 0
    if "OPENAI_API_KEY" not in os.environ or not os.environ["OPENAI_API_KEY"]:
        raise LocalLunaRunnerError(
            "OPENAI_API_KEY is not present in the runtime environment"
        )
    output_root.mkdir(parents=True, exist_ok=True)
    policy = FrozenAttemptPolicy(
        reservation_ledger_sha256=authority_identity,
        max_billable_attempts=2,
        failure_threshold=5,
        failure_window_seconds=86_400,
    )
    with SqliteProviderSpendAuthority(
        output_root / f"provider-spend-{prior_committed_microusd}.sqlite3",
        authority_identity_sha256=authority_identity,
        cycle_id=cast(str, run_record["cycle_id"]),
        provider="openai",
        account=ACCOUNT,
        cap_microusd=effective_cap_microusd,
        policy=policy,
    ) as authority:
        for row in rows:
            identity = f"{row['case_id']}:{row['ablation']}"
            result_path = output_root / f"{row['case_id']}--{row['ablation']}.json"
            if result_path.exists():
                existing = _read_json(result_path)
                if (
                    not isinstance(existing, Mapping)
                    or cast(Mapping[str, object], existing).get("identity") != identity
                    or cast(Mapping[str, object], existing).get("packet_sha256")
                    != row["packet_sha256"]
                    or cast(Mapping[str, object], existing).get("prompt_sha256")
                    != row["prompt_sha256"]
                ):
                    raise LocalLunaRunnerError(
                        f"existing result identity differs: {result_path}"
                    )
                continue
            packet_path = packet_root / cast(str, row["packet_object_key"])
            packet_bytes = packet_path.read_bytes()
            if _sha(packet_bytes) != row.get("packet_sha256"):
                raise LocalLunaRunnerError(f"packet SHA-256 mismatch: {identity}")
            loaded_packet: object = json.loads(packet_bytes)
            if not isinstance(loaded_packet, Mapping):
                raise LocalLunaRunnerError(f"packet is not an object: {identity}")
            packet = _model_packet_from_record(
                dict(cast(Mapping[str, Any], loaded_packet))
            )
            samples = build_inspect_samples(
                (packet,),
                run_label=cast(str, row["ablation"]),
                use_docket_tool=False,
                committed_prompt_sha256=cast(str, row["prompt_sha256"]),
            )

            def handler_factory(request: Any) -> ProviderSpendAttemptHandler:
                return ProviderSpendAttemptHandler(
                    authority=authority,
                    key=ProviderSpendKey(
                        cycle_id=cast(str, run_record["cycle_id"]),
                        provider="openai",
                        account=ACCOUNT,
                        stage="cycle-1-local-luna",
                        model_key=MODEL_KEY,
                        case_id=request.sample.packet.case_id,
                        ablation=request.sample.packet.ablation.value,
                        repeat_index=1,
                    ),
                    reservation_microusd=conservative_reservation_microusd(
                        context_limit=entry.context_limit,
                        max_output_tokens=entry.max_output_tokens,
                        input_token_price=entry.input_token_price,
                        output_token_price=entry.output_token_price,
                    ),
                )

            solver = LiveModelSolver(
                registry_entry=entry,
                model_registry_sha256=_sha(registry_bytes),
                max_attempts=2,
                attempt_handler_factory=handler_factory,
            )
            records = run_inspect_fixture(samples, (solver,)).to_records()
            verification = response_verification_summary_from_run_records(records)
            output_statuses = {
                digest: status.to_record()
                for digest, status in output_statuses_from_run_records(records).items()
            }
            record = {
                "schema_version": "legalforecast.local_luna_result.v1",
                "identity": identity,
                "plan_identity_sha256": authority_identity,
                "packet_sha256": row["packet_sha256"],
                "prompt_sha256": row["prompt_sha256"],
                "response_verification": verification,
                "output_statuses": output_statuses,
                "runs": records,
            }
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            descriptor = os.open(result_path, flags, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(record, handle, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-inputs", required=True)
    parser.add_argument("--run-record", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--packet-root", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--packet", action="append", default=[])
    parser.add_argument("--max-calls", type=int)
    parser.add_argument(
        "--prior-committed-microusd",
        "--prior-reserved-microusd",
        dest="prior_committed_microusd",
        type=int,
        default=0,
    )
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
