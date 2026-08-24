"""Resumable local model runner for frozen Cycle 1 forecast packets.

The default configuration is the completed Luna run; the Gemini entry point
selects the supplementary Google configuration without duplicating this logic.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from legalforecast.contracts.schemas import (
    LOCAL_LUNA_PLAN_V1,
    LOCAL_LUNA_RESULT_V1,
    LOCAL_MODEL_PLAN_V1,
    LOCAL_MODEL_RESULT_V1,
)
from legalforecast.evals.inspect_task import build_inspect_samples, run_inspect_fixture
from legalforecast.evals.live_model_solver import LiveModelSolver
from legalforecast.evals.model_registry import load_model_registry
from legalforecast.evals.per_case_runner import (
    _model_packet_from_record,  # pyright: ignore[reportPrivateUsage]
)
from legalforecast.evals.provider_spend_attempt_handler import (
    CompositeProviderAttemptHandler,
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
from legalforecast.labeling.provider_journal import (
    ProviderAttemptJournal,
    ProviderCallIdentity,
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
FROZEN_RUN_INPUTS_SHA256 = (
    "378acbd9034121c203ad3528aa39c5f6359558b451e09e4add97d710cd3736f6"
)
FROZEN_RUN_RECORD_SHA256 = (
    "46f42378b782361e67e24a13b00282cb15e3b0ef200f7fe9ef790283bd42d124"
)
FROZEN_REGISTRY_SHA256 = (
    "619164614062a0030aacc904feaeacfb93996e3a3e13731b0c2d317c9dccb670"
)


@dataclass(frozen=True, slots=True)
class LocalModelConfig:
    """Runtime policy for one manifest-bound local model run.

    The original Luna command remains the default configuration.  Supplementary
    models can use the same authenticated packet, resumable envelope, replay
    journal, and spend-authority implementation without copying the runner.
    """

    model_key: str
    provider: str
    account: str
    stage: str
    approval_bead: str
    manifest_approval_bead: str
    spend_approval: str
    cap_microusd: int
    expected_registry_sha256: str | None
    plan_schema_version: str = str(LOCAL_LUNA_PLAN_V1)
    result_schema_version: str = str(LOCAL_LUNA_RESULT_V1)
    spend_approval_comment_id: str | None = None
    manifest_approval_comment_id: str | None = None
    extended_commitments: bool = False


LUNA_CONFIG = LocalModelConfig(
    model_key=MODEL_KEY,
    provider="openai",
    account=ACCOUNT,
    stage="cycle-1-local-luna",
    approval_bead="legalforecastbench-3ak.38",
    manifest_approval_bead="legalforecastbench-3ak.38",
    spend_approval=SPEND_APPROVAL,
    cap_microusd=CAP_MICROUSD,
    expected_registry_sha256=FROZEN_REGISTRY_SHA256,
)

# This is deliberately a supplementary, post-freeze configuration.  The
# registry file carries the model release/pricing evidence and its digest is
# supplied by the Gemini wrapper after the file is published.
GEMINI_CONFIG = LocalModelConfig(
    model_key="google:gemini-3.7-flash",
    provider="google",
    account="cycle-1-gemini-3-7-flash",
    stage="cycle-1-local-gemini",
    approval_bead="legalforecastbench-rkjw",
    manifest_approval_bead="legalforecastbench-3ak.38",
    spend_approval=(
        "I approve up to USD 15 for the Gemini 3.7 Flash 200-call Cycle 1 comparison."
    ),
    cap_microusd=15_000_000,
    expected_registry_sha256=(
        "131ece75c82275fc8d47d9cd6bbdf7b39ff45f69568750eb4a777709e1a1be75"
    ),
    plan_schema_version=str(LOCAL_MODEL_PLAN_V1),
    result_schema_version=str(LOCAL_MODEL_RESULT_V1),
    spend_approval_comment_id="9dc0ad0a-de38-5eb8-ae76-a935a3a8f311",
    manifest_approval_comment_id="36e31a09-588e-591c-8898-510f1ccb9d06",
    extended_commitments=True,
)


class LocalLunaRunnerError(RuntimeError):
    """Raised before unsafe, ambiguous, or identity-drifting local execution."""


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _read_json(path: Path) -> object:
    if path.is_symlink() or not path.is_file():
        raise LocalLunaRunnerError(f"input must be a regular non-symlink file: {path}")
    return json.loads(path.read_bytes())


def _owner_approvals(config: LocalModelConfig) -> dict[str, str]:
    evidence: dict[str, str] = {}
    for bead in (config.approval_bead, config.manifest_approval_bead):
        completed = subprocess.run(
            ["bd", "comments", bead, "--json"],
            check=True,
            capture_output=True,
            text=True,
        )
        rows: object = json.loads(completed.stdout)
        if not isinstance(rows, list):
            raise LocalLunaRunnerError("Beads comments response is not an array")
        for raw in cast(list[object], rows):
            if not isinstance(raw, Mapping):
                continue
            row = cast(Mapping[str, object], raw)
            if row.get("author") != "John Hughes":
                continue
            text = row.get("text")
            comment_id = row.get("id")
            expected_comment_id = (
                config.spend_approval_comment_id
                if text == config.spend_approval
                else config.manifest_approval_comment_id
            )
            if (
                text in {config.spend_approval, MANIFEST_APPROVAL}
                and isinstance(comment_id, str)
                and (expected_comment_id is None or comment_id == expected_comment_id)
            ):
                evidence[cast(str, text)] = comment_id
    for required in (config.spend_approval, MANIFEST_APPROVAL):
        if required not in evidence:
            raise LocalLunaRunnerError(f"missing exact owner approval: {required}")
    return evidence


def _authenticate_frozen_chain(
    *,
    run_inputs_path: Path,
    run_record_path: Path,
    registry_path: Path,
    run_inputs: Mapping[str, Any],
    run_record: Mapping[str, Any],
    registry_bytes: bytes,
    config: LocalModelConfig,
) -> Mapping[Path, bytes]:
    """Authenticate the issued manifest inputs before provider authorization."""

    def read_committed(path: Path, expected_sha256: str, label: str) -> bytes:
        if path.is_symlink() or not path.is_file():
            raise LocalLunaRunnerError(
                f"{label} must be a regular non-symlink file: {path}"
            )
        payload = path.read_bytes()
        actual_sha256 = _sha(payload)
        if actual_sha256 != expected_sha256:
            raise LocalLunaRunnerError(
                f"{label} differs from the frozen commitment: "
                f"expected={expected_sha256}, actual={actual_sha256}"
            )
        return payload

    run_input_bytes = read_committed(
        run_inputs_path, FROZEN_RUN_INPUTS_SHA256, "run-inputs"
    )
    run_record_bytes = read_committed(
        run_record_path, FROZEN_RUN_RECORD_SHA256, "run record"
    )
    expected_registry_sha256 = config.expected_registry_sha256
    if expected_registry_sha256 is not None:
        committed_registry_bytes = read_committed(
            registry_path, expected_registry_sha256, "registry"
        )
    else:
        committed_registry_bytes = registry_bytes
        if _sha(committed_registry_bytes) != _sha(registry_bytes):
            raise LocalLunaRunnerError("registry bytes changed during authentication")
    if committed_registry_bytes != registry_bytes:
        raise LocalLunaRunnerError("registry bytes changed during authentication")
    snapshots: dict[Path, bytes] = {
        run_inputs_path: run_input_bytes,
        run_record_path: run_record_bytes,
        registry_path: registry_bytes,
    }
    packets = run_inputs.get("model_packets")
    prompt_commitments = run_record.get("prompt_commitments")
    if not isinstance(packets, list) or not isinstance(prompt_commitments, Mapping):
        raise LocalLunaRunnerError(
            "frozen inputs lack the authenticated packet/prompt commitments"
        )
    prompt_commitment_map = cast(Mapping[str, object], prompt_commitments)
    packet_root = run_inputs_path.parent.resolve()
    for raw in cast(list[object], packets):
        if not isinstance(raw, Mapping):
            raise LocalLunaRunnerError("frozen packet inventory row is not an object")
        row = cast(Mapping[str, object], raw)
        packet_object_key = row.get("packet_object_key")
        packet_sha256 = row.get("packet_sha256")
        candidate_id = row.get("candidate_id")
        ablation = row.get("ablation")
        prompt_sha256 = row.get("prompt_sha256")
        if not all(
            isinstance(value, str)
            for value in (
                packet_object_key,
                packet_sha256,
                candidate_id,
                ablation,
                prompt_sha256,
            )
        ):
            raise LocalLunaRunnerError("frozen packet row has invalid commitments")
        packet_object_key = cast(str, packet_object_key)
        packet_sha256 = cast(str, packet_sha256)
        candidate_id = cast(str, candidate_id)
        ablation = cast(str, ablation)
        prompt_sha256 = cast(str, prompt_sha256)
        identity = f"{candidate_id}:{ablation}"
        if prompt_commitment_map.get(identity) != prompt_sha256:
            raise LocalLunaRunnerError(
                f"prompt commitment differs from frozen replay record: {identity}"
            )
        relative_key = Path(packet_object_key)
        if relative_key.is_absolute():
            raise LocalLunaRunnerError(
                f"frozen packet object key must be relative: {identity}"
            )
        unresolved_packet_path = packet_root / relative_key
        if unresolved_packet_path.is_symlink():
            raise LocalLunaRunnerError(
                f"frozen packet must not be a symlink: {identity}"
            )
        packet_path = unresolved_packet_path.resolve()
        try:
            packet_path.relative_to(packet_root)
        except ValueError as exc:
            raise LocalLunaRunnerError(
                f"frozen packet object key escapes the manifest root: {identity}"
            ) from exc
        snapshots[packet_path] = read_committed(
            packet_path, packet_sha256, f"packet {identity}"
        )
    return snapshots


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


def run(args: argparse.Namespace, config: LocalModelConfig = LUNA_CONFIG) -> int:
    run_inputs_path = Path(args.run_inputs).resolve()
    run_record_path = Path(args.run_record).resolve()
    registry_path = Path(args.registry).resolve()
    packet_root = Path(args.packet_root).resolve()
    output_root = Path(args.output_root).resolve()
    prior_committed_microusd = args.prior_committed_microusd
    if (
        isinstance(prior_committed_microusd, bool)
        or prior_committed_microusd < 0
        or prior_committed_microusd >= config.cap_microusd
    ):
        raise LocalLunaRunnerError(
            "prior_committed_microusd must be between zero and the owner ceiling"
        )
    effective_cap_microusd = config.cap_microusd - prior_committed_microusd
    run_inputs, run_record = _load_inputs(run_inputs_path, run_record_path)
    approvals = _owner_approvals(config)
    registry_bytes = registry_path.read_bytes()
    authenticated_snapshots = _authenticate_frozen_chain(
        run_inputs_path=run_inputs_path,
        run_record_path=run_record_path,
        registry_path=registry_path,
        run_inputs=run_inputs,
        run_record=run_record,
        registry_bytes=registry_bytes,
        config=config,
    )
    if not authenticated_snapshots:
        raise LocalLunaRunnerError("frozen chain authentication captured no inputs")
    registry = load_model_registry(registry_path)
    entries = [
        entry for entry in registry.entries if entry.registry_key == config.model_key
    ]
    if len(entries) != 1:
        raise LocalLunaRunnerError(
            f"registry must contain exactly one {config.model_key} entry"
        )
    entry = entries[0]
    if (
        entry.provider != config.provider
        or not entry.network_disabled
        or not entry.search_disabled
    ):
        raise LocalLunaRunnerError(f"{config.model_key} registry safety fields differ")
    if config.provider == "google" and entry.tool_policy.value != "no_tools":
        raise LocalLunaRunnerError("Gemini supplementary registry must disable tools")
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
    authority_payload: dict[str, object] = {
        "approval": config.spend_approval,
        "manifest": MANIFEST_DIGEST,
        "model_key": config.model_key,
        "owner_cap_microusd": config.cap_microusd,
        "prior_committed_microusd": prior_committed_microusd,
        "registry_sha256": _sha(registry_bytes),
        "run_inputs_sha256": _sha(run_inputs_path.read_bytes()),
    }
    if config.extended_commitments:
        authority_payload["owner_comment_ids"] = sorted(approvals.values())
    authority_identity = _sha(
        json.dumps(
            authority_payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    )
    plan = {
        "schema_version": config.plan_schema_version,
        "manifest_sha256": MANIFEST_DIGEST,
        "model_key": config.model_key,
        "registry_sha256": _sha(registry_bytes),
        "run_inputs_sha256": _sha(run_inputs_path.read_bytes()),
        "run_record_sha256": _sha(run_record_path.read_bytes()),
        "cap_microusd": effective_cap_microusd,
        "owner_cap_microusd": config.cap_microusd,
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
    api_key_name = {
        "openai": "OPENAI_API_KEY",
        "google": "GEMINI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
    }.get(config.provider)
    if api_key_name is None or not os.environ.get(api_key_name):
        raise LocalLunaRunnerError(
            f"{api_key_name or config.provider + ' API key'} is not present in the "
            "runtime environment"
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
        provider=config.provider,
        account=config.account,
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
                    or cast(Mapping[str, object], existing).get("plan_identity_sha256")
                    != authority_identity
                    or (
                        config.extended_commitments
                        and (
                            cast(Mapping[str, object], existing).get("model_key")
                            != config.model_key
                            or cast(Mapping[str, object], existing).get(
                                "schema_version"
                            )
                            != config.result_schema_version
                            or cast(Mapping[str, object], existing).get(
                                "registry_sha256"
                            )
                            != _sha(registry_bytes)
                            or cast(Mapping[str, object], existing).get(
                                "prompt_commitment_identity"
                            )
                            != f"{row['candidate_id']}:{row['ablation']}"
                        )
                    )
                ):
                    raise LocalLunaRunnerError(
                        f"existing result identity differs: {result_path}"
                    )
                continue
            packet_path = packet_root / cast(str, row["packet_object_key"])
            packet_bytes = packet_path.read_bytes()
            if _sha(packet_bytes) != row.get("packet_sha256"):
                raise LocalLunaRunnerError(f"packet SHA-256 mismatch: {identity}")
            authenticated_packet_path = run_inputs_path.parent / cast(
                str, row["packet_object_key"]
            )
            if authenticated_snapshots.get(authenticated_packet_path.resolve()) != (
                packet_bytes
            ):
                raise LocalLunaRunnerError(
                    "packet bytes differ from authenticated manifest packet: "
                    f"{identity}"
                )
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

            reservation_microusd = conservative_reservation_microusd(
                context_limit=entry.context_limit,
                max_output_tokens=entry.max_output_tokens,
                input_token_price=entry.input_token_price,
                output_token_price=entry.output_token_price,
                long_context_surcharge=entry.long_context_surcharge,
            )
            replay_path = (
                output_root
                / "provider-replay"
                / f"{_sha(identity.encode('utf-8'))}.sqlite3"
            )
            replay_path.parent.mkdir(parents=True, exist_ok=True)
            with ProviderAttemptJournal(
                replay_path,
                identity=ProviderCallIdentity(
                    stage=config.stage,
                    candidate_id=identity,
                    model_key=config.model_key,
                    prompt=samples[0].prompt,
                    model_registry_sha256=_sha(registry_bytes),
                    account=config.account,
                    prompt_contract=cast(str, row["prompt_sha256"]),
                ),
                provider=config.provider,
                reservation_usd=reservation_microusd / 1_000_000,
                cycle_cap_usd=effective_cap_microusd / 1_000_000,
                cycle_id=cast(str, run_record["cycle_id"]),
                provider_cycle_caps_sha256=authority_identity,
            ) as replay_journal:

                def handler_factory(
                    request: Any,
                    *,
                    reservation_microusd_for_request: int = reservation_microusd,
                ) -> CompositeProviderAttemptHandler:
                    return CompositeProviderAttemptHandler(
                        replay_handler=replay_journal,
                        spend_handler=ProviderSpendAttemptHandler(
                            authority=authority,
                            key=ProviderSpendKey(
                                cycle_id=cast(str, run_record["cycle_id"]),
                                provider=config.provider,
                                account=config.account,
                                stage=config.stage,
                                model_key=config.model_key,
                                case_id=request.sample.packet.case_id,
                                ablation=request.sample.packet.ablation.value,
                                repeat_index=1,
                            ),
                            reservation_microusd=reservation_microusd_for_request,
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
                if verification["grounding_artifacts_detected"]:
                    raise LocalLunaRunnerError(
                        "provider response included prohibited grounding artifacts: "
                        f"{identity}"
                    )
                if verification["retryable_ops_event_count"]:
                    raise LocalLunaRunnerError(
                        f"provider response requires retry: {identity}"
                    )
                output_statuses = {
                    digest: status.to_record()
                    for digest, status in output_statuses_from_run_records(
                        records
                    ).items()
                }
                record = {
                    "schema_version": config.result_schema_version,
                    "identity": identity,
                    "plan_identity_sha256": authority_identity,
                    "packet_sha256": row["packet_sha256"],
                    "prompt_sha256": row["prompt_sha256"],
                    "response_verification": verification,
                    "output_statuses": output_statuses,
                    "runs": records,
                }
                if config.extended_commitments:
                    record.update(
                        {
                            "model_key": config.model_key,
                            "registry_sha256": _sha(registry_bytes),
                            "provider": config.provider,
                            "prompt_commitment_identity": (
                                f"{row['candidate_id']}:{row['ablation']}"
                            ),
                            "tools": [],
                        }
                    )
                flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
                descriptor = os.open(result_path, flags, 0o600)
                with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                    json.dump(record, handle, sort_keys=True)
                    handle.write("\n")
                    handle.flush()
                    os.fsync(handle.fileno())
    return 0


def main(
    argv: Sequence[str] | None = None,
    *,
    config: LocalModelConfig = LUNA_CONFIG,
) -> int:
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
    return run(parser.parse_args(argv), config=config)


if __name__ == "__main__":
    raise SystemExit(main())
