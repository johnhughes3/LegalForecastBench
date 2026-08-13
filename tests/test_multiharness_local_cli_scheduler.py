"""Attack tests: requested CLI scheduling must match what receipts prove."""

from __future__ import annotations

import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pytest
from legalforecast.multiharness.auth_profiles import FIXTURE_NONE
from legalforecast.multiharness.local_cli_identity import executable_pin_for
from legalforecast.multiharness.local_cli_runtime import (
    LocalCliAdapterManifest,
    LocalCliRunSpec,
    LocalCliRuntimeError,
    execute_local_cli,
)
from legalforecast.multiharness.local_cli_scheduler import (
    ORDERING_PARALLEL,
    ORDERING_SERIAL,
    OVERSUBSCRIBE_RECORD,
    LocalCliScheduler,
)

_CANARY_ENV = {
    "PATH": "/usr/bin",
    "LC_CTYPE": "C.UTF-8",
    "HOME": "/private/operator-home",
}


def test_enforced_scheduler_refuses_serial_over_subscribe(tmp_path: Path) -> None:
    scheduler = LocalCliScheduler(max_concurrency=1)
    script = _write_sleeper(tmp_path)
    outcomes: list[str] = []
    barrier = threading.Barrier(2)

    def _run(index: int) -> None:
        barrier.wait()
        try:
            result = execute_local_cli(
                _spec(script, spec_id=f"cap-{index}", max_concurrency=1),
                tmp_path / f"scratch-{index}",
                scheduler=scheduler,
                parent_env=_CANARY_ENV,
            )
            outcomes.append(f"ok:{result.scheduling.peak_concurrency}")
        except LocalCliRuntimeError as exc:
            outcomes.append(f"err:{exc}")

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(_run, index) for index in range(2)]
        for future in as_completed(futures):
            future.result()

    assert sum(item.startswith("ok:") for item in outcomes) == 1
    assert any("over-subscribe" in item for item in outcomes)
    assert any(item == "ok:1" for item in outcomes)


def test_recording_scheduler_discloses_over_subscribe(tmp_path: Path) -> None:
    scheduler = LocalCliScheduler(
        max_concurrency=8,
        on_oversubscribe=OVERSUBSCRIBE_RECORD,
    )
    script = _write_sleeper(tmp_path)
    barrier = threading.Barrier(2)

    def _run(index: int) -> str | None:
        barrier.wait()
        result = execute_local_cli(
            _spec(script, spec_id=f"over-{index}", max_concurrency=1),
            tmp_path / f"scratch-{index}",
            scheduler=scheduler,
            parent_env=_CANARY_ENV,
        )
        return result.scheduling.divergence

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(_run, index) for index in range(2)]
        observed = [future.result() for future in as_completed(futures)]

    assert any(
        item
        in {
            "serial_overlap",
            "observed_concurrency_exceeds_requested",
            "observed_concurrency_exceeds_cap",
        }
        for item in observed
    )


def test_parallel_cap_allows_requested_concurrency(tmp_path: Path) -> None:
    scheduler = LocalCliScheduler(max_concurrency=2)
    script = _write_sleeper(tmp_path)

    def _run(index: int) -> dict[str, object]:
        result = execute_local_cli(
            _spec(
                script,
                spec_id=f"par-{index}",
                max_concurrency=2,
                ordering=ORDERING_PARALLEL,
            ),
            tmp_path / f"scratch-{index}",
            scheduler=scheduler,
            parent_env=_CANARY_ENV,
        )
        return result.scheduling.to_public_record()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(_run, index) for index in range(2)]
        records = [future.result() for future in as_completed(futures)]

    assert all(
        record["divergence"]
        not in {
            "observed_concurrency_exceeds_cap",
            "observed_concurrency_exceeds_requested",
            "serial_overlap",
        }
        for record in records
    )
    assert all(int(record["peak_concurrency"]) <= 2 for record in records)


def test_hard_cap_refuses_before_spawn(tmp_path: Path) -> None:
    sentinel = tmp_path / "ran"
    script = tmp_path / "cli.py"
    script.write_text(
        f"from pathlib import Path\nPath({str(sentinel)!r}).write_text('ran')\n",
        encoding="utf-8",
    )
    scheduler = LocalCliScheduler(max_concurrency=2)
    with pytest.raises(LocalCliRuntimeError, match="exceeds scheduler cap"):
        execute_local_cli(
            _spec(
                script,
                spec_id="cap",
                max_concurrency=8,
                ordering=ORDERING_PARALLEL,
            ),
            tmp_path / "scratch",
            scheduler=scheduler,
            parent_env=_CANARY_ENV,
        )
    assert not sentinel.exists()


def test_receipt_records_requested_schedule(tmp_path: Path) -> None:
    script = tmp_path / "cli.py"
    script.write_text("print('ok')\n", encoding="utf-8")
    result = execute_local_cli(
        _spec(script, spec_id="one", max_concurrency=1, ordering=ORDERING_SERIAL),
        tmp_path / "scratch",
        parent_env=_CANARY_ENV,
    )
    public = result.to_public_record()["scheduling"]
    assert isinstance(public, dict)
    assert public["requested_max_concurrency"] == 1
    assert public["requested_ordering"] == ORDERING_SERIAL
    assert public["observed_concurrency"] == 1
    assert public["peak_concurrency"] == 1
    assert public["divergence"] is None


def _spec(
    script: Path,
    *,
    spec_id: str,
    max_concurrency: int = 1,
    ordering: str = ORDERING_SERIAL,
) -> LocalCliRunSpec:
    path = script.resolve()
    return LocalCliRunSpec(
        spec_id=spec_id,
        manifest=LocalCliAdapterManifest(
            adapter_id="fixture-cli",
            display_name="Fixture CLI",
            adapter_version="0.1.0",
            command=(sys.executable, str(path)),
            executable=executable_pin_for(path, version="0.1.0"),
            supported_auth_profiles=(FIXTURE_NONE,),
        ),
        auth_profile=FIXTURE_NONE,
        max_concurrency=max_concurrency,
        ordering=ordering,
        timeout_seconds=5,
    )


def _write_sleeper(tmp_path: Path) -> Path:
    path = tmp_path / "sleeper.py"
    path.write_text("import time\ntime.sleep(0.4)\n", encoding="utf-8")
    return path
