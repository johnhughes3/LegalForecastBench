#!/usr/bin/env python3
# pyright: reportPrivateUsage=false
"""Plan or apply protected provider-authority recovery from frozen artifacts."""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import tempfile
from collections.abc import Mapping
from contextlib import closing
from pathlib import Path, PurePosixPath
from typing import Any, cast
from zipfile import BadZipFile, ZipFile

from legalforecast.evals.model_registry import (
    load_model_registry_bytes,
    model_registry_entry_sha256,
    model_registry_sha256,
)
from legalforecast.evals.provider_spend_attempt_handler import (
    conservative_reservation_microusd,
)
from legalforecast.evals.provider_spend_dynamodb import AwsCliDynamoCommandRunner
from legalforecast.release.consumer import load_forecast_run_inputs
from legalforecast.runner.ledger import RunnerLedger, RunValidationError
from legalforecast.runner.managed_transcript_recovery import (
    managed_result_from_transcript,
)
from legalforecast.runner.protected_recovery import (
    RecoveryCell,
    RecoveryRun,
    apply_protected_recovery,
    build_protected_recovery_plan,
    canonical_json,
    terminal_response_evidence,
)
from legalforecast.runner.recovery import GhRecoveryClient
from legalforecast.runner.transcript_candidate import has_terminal_transcript_candidate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--checkout", type=Path, default=Path.cwd())
    parser.add_argument("--table-name", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--resource-identity-sha256", required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    metadata = _read_object(args.metadata)
    workspace = args.workspace
    if args.execute:
        if not workspace.is_dir():
            raise SystemExit("materialized recovery workspace is missing")
    else:
        _materialize(metadata, workspace)
    run, cells, reservation = _load_evidence(
        metadata,
        workspace,
        table_name=args.table_name,
        region=args.region,
        resource_identity_sha256=args.resource_identity_sha256,
        checkout=args.checkout,
    )
    runner = AwsCliDynamoCommandRunner(region=args.region)
    if args.execute:
        protected = apply_protected_recovery(
            run,
            cells,
            reservation_microusd=reservation,
            runner=runner,
        )
    else:
        protected = build_protected_recovery_plan(
            run,
            cells,
            reservation_microusd=reservation,
            runner=runner,
        )
    record = protected.to_record()
    record["execute_requested"] = args.execute
    args.output.write_text(canonical_json(record), encoding="utf-8")
    print(canonical_json(record), end="")
    if not protected.dispatch_safe:
        return 2
    return 0


def _materialize(metadata: Mapping[str, Any], workspace: Path) -> None:
    if workspace.exists():
        raise SystemExit("recovery workspace already exists")
    workspace.mkdir(parents=True)
    source = _object(metadata.get("source"), "recovery source")
    repo = _text(metadata.get("repo"), "repository")
    inputs = _object(source.get("locked_inputs_artifact"), "locked inputs artifact")
    artifacts = source.get("state_artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise SystemExit("recovery plan has no state artifacts")
    client = GhRecoveryClient()
    _extract_zip(
        client.download_artifact(
            repo, _positive_int(inputs.get("id"), "input artifact")
        ),
        workspace / "inputs",
    )
    states = workspace / "states"
    states.mkdir()
    for raw in artifacts:
        locator = _object(raw, "state artifact")
        name = _text(locator.get("name"), "state artifact name")
        destination = states / name
        _extract_zip(
            client.download_artifact(
                repo, _positive_int(locator.get("id"), "state artifact")
            ),
            destination,
        )


def _extract_zip(payload: bytes, destination: Path) -> None:
    destination.mkdir()
    try:
        with tempfile.NamedTemporaryFile() as archive_file:
            archive_file.write(payload)
            archive_file.flush()
            with ZipFile(archive_file.name) as archive:
                seen: set[str] = set()
                for info in archive.infolist():
                    path = PurePosixPath(info.filename)
                    if (
                        not info.filename
                        or path.is_absolute()
                        or ".." in path.parts
                        or info.filename in seen
                    ):
                        raise SystemExit("workflow artifact contains an unsafe path")
                    seen.add(info.filename)
                    target = destination.joinpath(*path.parts)
                    if info.is_dir():
                        target.mkdir(parents=True, exist_ok=True)
                    else:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with archive.open(info) as source, target.open("xb") as output:
                            shutil.copyfileobj(source, output)
    except BadZipFile as exc:
        raise SystemExit("workflow artifact is not a ZIP archive") from exc


def _load_evidence(
    metadata: Mapping[str, Any],
    workspace: Path,
    *,
    table_name: str,
    region: str,
    resource_identity_sha256: str,
    checkout: Path,
) -> tuple[RecoveryRun, tuple[RecoveryCell, ...], int]:
    source = _object(metadata.get("source"), "recovery source")
    frozen = _object(metadata.get("frozen_identity"), "frozen identity")
    recovery = _object(metadata.get("recovery"), "recovery metadata")
    run_id = _positive_int(source.get("run_id"), "source run ID")
    run_attempt = _positive_int(source.get("run_attempt"), "source run attempt")
    model_key = _text(frozen.get("model_key"), "model key")
    provider, separator, _model = model_key.partition(":")
    if not separator:
        raise SystemExit("frozen model key is invalid")
    inputs = workspace / "inputs"
    registry_path = inputs / "model-registry.json"
    registry_bytes = registry_path.read_bytes()
    registry_digest = model_registry_sha256(registry_bytes)
    if registry_digest != _text(
        frozen.get("model_registry_sha256"), "model registry digest"
    ):
        raise SystemExit("materialized model registry differs from frozen identity")
    registry_uri = _text(frozen.get("model_registry_uri"), "model registry URI")
    if "://" not in registry_uri:
        relative = Path(registry_uri)
        if relative.is_absolute() or ".." in relative.parts:
            raise SystemExit("relative model registry URI is unsafe")
        current_registry = checkout / relative
        if current_registry.read_bytes() != registry_bytes:
            raise SystemExit(
                "current recovery source changed the frozen model registry bytes"
            )
    registry = load_model_registry_bytes(registry_bytes)
    try:
        entry = registry.get(provider, model_key.split(":", 1)[1])
    except KeyError as exc:
        raise SystemExit("frozen model is absent from materialized registry") from exc
    identity_sha256 = _text(frozen.get("run_identity_sha256"), "run identity")
    account = _text(frozen.get("account"), "provider account")
    ceiling = _positive_int(frozen.get("ceiling_microusd"), "provider ceiling")
    frozen_inputs = load_forecast_run_inputs(
        inputs / "run-manifest.json",
        inputs / "forecast-release.json",
        artifact_root=inputs / "artifacts",
    )
    cycle_id = frozen_inputs.execution.release.release_id
    run = RecoveryRun(
        source_run_id=run_id,
        source_run_attempt=run_attempt,
        cycle_id=cycle_id,
        model_key=model_key,
        provider=provider,
        account=account,
        run_identity_sha256=identity_sha256,
        ceiling_microusd=ceiling,
        table_name=table_name,
        region=region,
        resource_identity_sha256=resource_identity_sha256,
        owner_reference=f"recover-run-{run_id}-attempt-{run_attempt}",
    )
    expected_count = _positive_int(
        _object(source.get("census"), "source census").get("declared_state_count"),
        "declared cell count",
    )
    cells = _load_cells(
        workspace / "states",
        registry_path=registry_path,
        registry_digest=registry_digest,
        registry_entry_digest=model_registry_entry_sha256(entry),
        entry=entry,
        run_identity_sha256=identity_sha256,
        model_key=model_key,
        account=account,
        ceiling=ceiling,
        release_digest=frozen_inputs.execution.release.release_digest,
    )
    if len(cells) != expected_count:
        raise SystemExit(
            f"recovery cell census differs: expected {expected_count}, got {len(cells)}"
        )
    if _positive_int(
        recovery.get("completed_cells"), "completed cell count", zero=True
    ) != sum(cell.completed for cell in cells):
        raise SystemExit("recovery completed-cell census differs from artifacts")
    reservation = conservative_reservation_microusd(
        context_limit=entry.context_limit,
        max_output_tokens=entry.max_output_tokens,
        input_token_price=entry.input_token_price,
        output_token_price=entry.output_token_price,
        long_context_surcharge=entry.long_context_surcharge,
    )
    return run, cells, reservation


def _load_cells(
    state_root: Path,
    *,
    registry_path: Path,
    registry_digest: str,
    registry_entry_digest: str,
    entry: Any,
    run_identity_sha256: str,
    model_key: str,
    account: str,
    ceiling: int,
    release_digest: str,
) -> tuple[RecoveryCell, ...]:
    # Setup failures legitimately have no runner ledger. Recover their settings
    # from a validated sibling instead of inventing a harness or creating a DB.
    directories = sorted(
        state_root.iterdir(),
        key=lambda path: int(path.name.rsplit("-attempt-", 1)[-1]),
        reverse=True,
    )
    stage: str | None = None
    ablation: str | None = None
    for directory in directories:
        ledger_path = directory / "ledger.sqlite3"
        if not ledger_path.is_file() or ledger_path.is_symlink():
            continue
        try:
            with RunnerLedger(ledger_path, state_only_provider_attempts=True) as ledger:
                binding = ledger.read_run_binding()
        except (ValueError, sqlite3.Error):
            continue
        if (
            binding.identity_sha256 != run_identity_sha256
            or binding.model_key != model_key
            or binding.model_registry_sha256 != registry_digest
            or binding.model_registry_entry_sha256 != registry_entry_digest
            or binding.ceiling_microusd != ceiling
            or binding.release_digest != release_digest
        ):
            raise SystemExit("source ledger differs from frozen run")
        identity = _object(json.loads(binding.identity_json), "run identity")
        if identity.get("account") != account:
            raise SystemExit("source ledger account differs from frozen run")
        stage = binding.harness
        ablation = _text(identity.get("ablation"), "run ablation")
        break
    if stage is None or ablation is None:
        raise SystemExit("no source ledger establishes the frozen harness")
    candidates: dict[str, list[RecoveryCell]] = {}
    for directory in directories:
        if not directory.is_dir() or directory.is_symlink():
            raise SystemExit("materialized state artifact is unsafe")
        state = _read_object(directory / "state.json")
        cell_id = _text(state.get("cell_id"), "state cell ID")
        status = state.get("status")
        failure_path = directory / "failure-summary.json"
        failure = _read_object(failure_path) if failure_path.is_file() else state
        ledger_path = directory / "ledger.sqlite3"
        transcript = directory / "transcripts" / f"{cell_id}.json"
        # A missing ledger, or the workflow's minimal failure-only ledger,
        # means no local provider attempt was created. Remote state is checked
        # by the protected planner before it permits any new call.
        has_run_binding = False
        if ledger_path.is_file() and not ledger_path.is_symlink():
            with closing(
                sqlite3.connect(f"file:{ledger_path}?mode=ro", uri=True)
            ) as connection:
                has_run_binding = (
                    connection.execute(
                        "SELECT 1 FROM sqlite_master WHERE type='table' "
                        "AND name='public_runner_run'"
                    ).fetchone()
                    is not None
                )
                if has_run_binding:
                    has_run_binding = (
                        connection.execute(
                            "SELECT 1 FROM public_runner_run LIMIT 1"
                        ).fetchone()
                        is not None
                    )
        if not has_run_binding and not transcript.exists() and status != "completed":
            candidates.setdefault(cell_id, []).append(
                RecoveryCell(
                    cell_id,
                    stage,
                    ablation,
                    _positive_int(
                        failure.get("repeat_index", 1), "failure repeat index"
                    ),
                )
            )
            continue
        try:
            with RunnerLedger(ledger_path, state_only_provider_attempts=True) as ledger:
                binding = ledger.read_run_binding()
                if (
                    binding.identity_sha256 != run_identity_sha256
                    or binding.model_key != model_key
                    or binding.model_registry_sha256 != registry_digest
                    or binding.model_registry_entry_sha256 != registry_entry_digest
                    or binding.ceiling_microusd != ceiling
                    or binding.release_digest != release_digest
                ):
                    raise RunValidationError("cell ledger differs from frozen identity")
                identity = _object(json.loads(binding.identity_json), "run identity")
                if identity.get("account") != account:
                    raise RunValidationError("cell ledger account differs")
                try:
                    cell = ledger.read_cell_for_recovery(cell_id)
                except RunValidationError:
                    if not transcript.exists() and status != "completed":
                        candidates.setdefault(cell_id, []).append(
                            RecoveryCell(
                                cell_id,
                                stage,
                                ablation,
                                _positive_int(
                                    failure.get("repeat_index", 1),
                                    "failure repeat index",
                                ),
                            )
                        )
                        continue
                    raise
                terminal = None
                if transcript.is_file() and not transcript.is_symlink():
                    try:
                        result = managed_result_from_transcript(
                            transcript, entry=entry, cell=cell
                        )
                    except ValueError as exc:
                        if has_terminal_transcript_candidate(transcript.read_bytes()):
                            raise RunValidationError(
                                f"terminal transcript requires repair: {exc}"
                            ) from exc
                        result = None  # Interrupted histories can safely be retried.
                    # Use the same shared cost projection as live settlement.
                    from legalforecast.runner.managed_execution import (
                        _managed_result_cost,
                    )

                    if result is not None:
                        terminal = terminal_response_evidence(
                            transcript_bytes=transcript.read_bytes(),
                            input_tokens=result.input_tokens,
                            output_tokens=result.output_tokens,
                            estimated_cost_usd=_managed_result_cost(
                                entry, result=result
                            ),
                            raw_output=result.raw_output,
                        )
                candidates.setdefault(cell_id, []).append(
                    RecoveryCell(
                        cell_id=cell_id,
                        stage=binding.harness,
                        ablation=_text(identity.get("ablation"), "run ablation"),
                        repeat_index=cell.repeat_index,
                        local_attempt_id=cell.provider_attempt_id,
                        terminal_response=terminal,
                        completed=status == "completed" and cell.status == "completed",
                    )
                )
        except (OSError, ValueError, sqlite3.Error, RunValidationError) as exc:
            candidates.setdefault(cell_id, []).append(
                RecoveryCell(
                    cell_id=cell_id,
                    stage=stage,
                    ablation=ablation,
                    repeat_index=_positive_int(
                        failure.get("repeat_index", 1), "failure repeat index"
                    ),
                    evidence_error=str(exc),
                )
            )
    selected: list[RecoveryCell] = []
    for _cell_id, versions in candidates.items():
        usable = next(
            (
                cell
                for cell in versions
                if cell.completed or cell.terminal_response is not None
            ),
            versions[0],
        )
        selected.append(usable)
    return tuple(sorted(selected, key=lambda cell: cell.cell_id))


def _read_object(path: Path) -> dict[str, Any]:
    try:
        value: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"could not read JSON object: {path}") from exc
    return dict(_object(value, path.name))


def _object(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SystemExit(f"{label} must be an object")
    return cast(Mapping[str, Any], value)


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SystemExit(f"{label} is missing")
    return value.strip()


def _positive_int(value: object, label: str, *, zero: bool = False) -> int:
    if isinstance(value, bool):
        raise SystemExit(f"{label} is invalid")
    try:
        result = int(cast(str | int, value))
    except (TypeError, ValueError) as exc:
        raise SystemExit(f"{label} is invalid") from exc
    if result < (0 if zero else 1):
        raise SystemExit(f"{label} is invalid")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
