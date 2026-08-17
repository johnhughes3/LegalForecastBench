"""Attack tests: requested CLI scheduling must match what receipts prove."""

from __future__ import annotations

import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
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
    SchedulingEvidence,
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
    for record in records:
        peak = record["peak_concurrency"]
        assert isinstance(peak, int)
        assert peak <= 2


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


def test_parallel_cannot_join_inflight_serial(tmp_path: Path) -> None:
    scheduler = LocalCliScheduler(max_concurrency=2)
    script = _write_sleeper(tmp_path)
    serial_done = threading.Event()

    def _serial() -> None:
        try:
            execute_local_cli(
                _spec(script, spec_id="serial", max_concurrency=1),
                tmp_path / "scratch-serial",
                scheduler=scheduler,
                parent_env=_CANARY_ENV,
            )
        finally:
            serial_done.set()

    worker = threading.Thread(target=_serial)
    worker.start()
    try:
        deadline = time.monotonic() + 2
        while scheduler.peak_concurrency < 1:
            if time.monotonic() > deadline:
                raise AssertionError("serial run did not acquire a slot")
            time.sleep(0.01)
        with pytest.raises(LocalCliRuntimeError, match="over-subscribe"):
            execute_local_cli(
                _spec(
                    script,
                    spec_id="parallel",
                    max_concurrency=2,
                    ordering=ORDERING_PARALLEL,
                ),
                tmp_path / "scratch-parallel",
                scheduler=scheduler,
                parent_env=_CANARY_ENV,
            )
    finally:
        worker.join(timeout=5)
    assert serial_done.is_set()


@dataclass(frozen=True, slots=True)
class _StubSpec:
    """Minimal duck-typed spec so scheduler windows can be sequenced exactly."""

    spec_id: str
    max_concurrency: int
    ordering: str


def _hold(
    scheduler: LocalCliScheduler,
    spec: _StubSpec,
    *,
    acquired: threading.Event,
    release: threading.Event,
    observed: dict[str, SchedulingEvidence],
) -> None:
    """Acquire a slot, announce it, wait, then release on the same thread."""

    scheduler.before_execute(spec)
    acquired.set()
    assert release.wait(timeout=5)
    observed[spec.spec_id] = scheduler.after_execute(spec, None)


def test_higher_request_neighbor_diverges_the_lower_request_receipt() -> None:
    """An uncapped scheduler must disclose a window hotter than the request."""

    scheduler = LocalCliScheduler()
    observed: dict[str, SchedulingEvidence] = {}
    lower_acquired = threading.Event()
    higher_acquired = threading.Event()
    release = threading.Event()
    lower = _StubSpec("lower", 1, ORDERING_PARALLEL)
    higher = _StubSpec("higher", 2, ORDERING_PARALLEL)

    lower_worker = threading.Thread(
        target=_hold,
        args=(scheduler, lower),
        kwargs={
            "acquired": lower_acquired,
            "release": release,
            "observed": observed,
        },
    )
    higher_worker = threading.Thread(
        target=_hold,
        args=(scheduler, higher),
        kwargs={
            "acquired": higher_acquired,
            "release": release,
            "observed": observed,
        },
    )
    lower_worker.start()
    try:
        assert lower_acquired.wait(timeout=5)
        higher_worker.start()
        assert higher_acquired.wait(timeout=5)
    finally:
        release.set()
        lower_worker.join(timeout=5)
        higher_worker.join(timeout=5)

    assert observed["lower"].peak_concurrency == 2
    assert observed["lower"].divergence == "observed_concurrency_exceeds_requested"
    assert observed["higher"].peak_concurrency == 2
    assert observed["higher"].divergence is None


def test_an_earlier_unrelated_burst_does_not_diverge_a_later_solo_run() -> None:
    """Peak is measured over a run's own window, never the scheduler lifetime."""

    scheduler = LocalCliScheduler()
    observed: dict[str, SchedulingEvidence] = {}
    first_acquired = threading.Event()
    second_acquired = threading.Event()
    release = threading.Event()
    workers = [
        threading.Thread(
            target=_hold,
            args=(scheduler, _StubSpec(spec_id, 2, ORDERING_PARALLEL)),
            kwargs={"acquired": acquired, "release": release, "observed": observed},
        )
        for spec_id, acquired in (
            ("burst-a", first_acquired),
            ("burst-b", second_acquired),
        )
    ]
    workers[0].start()
    try:
        assert first_acquired.wait(timeout=5)
        workers[1].start()
        assert second_acquired.wait(timeout=5)
    finally:
        release.set()
        for worker in workers:
            worker.join(timeout=5)
    assert scheduler.peak_concurrency == 2

    solo = _StubSpec("solo", 1, ORDERING_PARALLEL)
    scheduler.before_execute(solo)
    evidence = scheduler.after_execute(solo, None)

    assert evidence.peak_concurrency == 1
    assert evidence.divergence is None


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
