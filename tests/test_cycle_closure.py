from __future__ import annotations

import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import legalforecast.publication.cycle_closure as cycle_closure
import pytest


def test_deterministic_paths_and_payloads() -> None:
    identity = cycle_closure.MutationIdentity(
        cycle_id="cycle-2026.1",
        run_id="run_42",
        run_attempt=3,
    )

    assert cycle_closure.seal_key(identity.cycle_id) == (
        "cycle-publication-state/cycle-2026.1/seal.json"
    )
    assert cycle_closure.intent_key(identity) == (
        "cycle-publication-state/cycle-2026.1/runs/run_42/3/intent.json"
    )
    assert cycle_closure.done_key(identity) == (
        "cycle-publication-state/cycle-2026.1/runs/run_42/3/done.json"
    )
    assert cycle_closure.seal_payload(identity.cycle_id) == (
        b'{"cycle_id":"cycle-2026.1","record_type":"seal",'
        b'"schema_version":"legalforecast.cycle_mutation_closure.v1"}\n'
    )
    assert cycle_closure.intent_payload(identity) == (
        b'{"cycle_id":"cycle-2026.1","record_type":"intent",'
        b'"run_attempt":3,"run_id":"run_42",'
        b'"schema_version":"legalforecast.cycle_mutation_closure.v1"}\n'
    )
    assert cycle_closure.done_payload(identity) == (
        b'{"cycle_id":"cycle-2026.1","record_type":"done",'
        b'"run_attempt":3,"run_id":"run_42",'
        b'"schema_version":"legalforecast.cycle_mutation_closure.v1"}\n'
    )


def test_local_happy_path(tmp_path: Path) -> None:
    identity = cycle_closure.begin(
        tmp_path,
        cycle_id="cycle-1",
        run_id="run-1",
        run_attempt=1,
    )
    cycle_closure.finish(tmp_path, identity=identity)
    result = cycle_closure.seal_wait(
        tmp_path,
        cycle_id="cycle-1",
        timeout_seconds=1,
        poll_interval_seconds=0.01,
    )

    assert result.seal_location == str(tmp_path / cycle_closure.seal_key("cycle-1"))
    assert result.observed_mutations == (identity,)
    assert (tmp_path / cycle_closure.intent_key(identity)).is_file()
    assert (tmp_path / cycle_closure.done_key(identity)).is_file()


def test_sealed_late_begin_writes_done_then_rejects(tmp_path: Path) -> None:
    cycle_closure.seal_wait(
        tmp_path,
        cycle_id="cycle-1",
        timeout_seconds=1,
        poll_interval_seconds=0.01,
    )
    identity = cycle_closure.MutationIdentity("cycle-1", "late-run", 2)

    with pytest.raises(cycle_closure.CycleSealedError, match="cycle-1"):
        cycle_closure.begin(
            tmp_path,
            cycle_id=identity.cycle_id,
            run_id=identity.run_id,
            run_attempt=identity.run_attempt,
        )

    assert (tmp_path / cycle_closure.intent_key(identity)).is_file()
    assert (tmp_path / cycle_closure.done_key(identity)).is_file()


def test_seal_wait_drains_concurrent_preexisting_intent(tmp_path: Path) -> None:
    identity = cycle_closure.begin(
        tmp_path,
        cycle_id="cycle-1",
        run_id="running",
        run_attempt=1,
    )

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            cycle_closure.seal_wait,
            tmp_path,
            cycle_id="cycle-1",
            timeout_seconds=2,
            poll_interval_seconds=0.01,
        )
        seal_path = tmp_path / cycle_closure.seal_key("cycle-1")
        deadline = time.monotonic() + 1
        while not seal_path.exists() and time.monotonic() < deadline:
            time.sleep(0.005)
        assert seal_path.is_file()
        assert not future.done()

        cycle_closure.finish(tmp_path, identity=identity)
        result = future.result(timeout=1)

    assert result.observed_mutations == (identity,)


def test_operations_are_idempotent_for_identical_objects(tmp_path: Path) -> None:
    first = cycle_closure.begin(
        tmp_path,
        cycle_id="cycle-1",
        run_id="run-1",
        run_attempt=1,
    )
    second = cycle_closure.begin(
        tmp_path,
        cycle_id="cycle-1",
        run_id="run-1",
        run_attempt=1,
    )
    cycle_closure.finish(tmp_path, identity=first)
    cycle_closure.finish(tmp_path, identity=second)

    one = cycle_closure.seal_wait(
        tmp_path,
        cycle_id="cycle-1",
        timeout_seconds=1,
        poll_interval_seconds=0.01,
    )
    two = cycle_closure.seal_wait(
        tmp_path,
        cycle_id="cycle-1",
        timeout_seconds=1,
        poll_interval_seconds=0.01,
    )

    assert first == second
    assert one == two


def test_conflicting_existing_object_fails_closed(tmp_path: Path) -> None:
    identity = cycle_closure.MutationIdentity("cycle-1", "run-1", 1)
    intent_path = tmp_path / cycle_closure.intent_key(identity)
    intent_path.parent.mkdir(parents=True)
    intent_path.write_text('{"not":"the deterministic intent"}\n', encoding="utf-8")

    with pytest.raises(cycle_closure.CycleClosureConflictError, match=r"intent\.json"):
        cycle_closure.begin(
            tmp_path,
            cycle_id="cycle-1",
            run_id="run-1",
            run_attempt=1,
        )


def test_finish_requires_matching_intent_identity(tmp_path: Path) -> None:
    missing = cycle_closure.MutationIdentity("cycle-1", "missing", 1)
    with pytest.raises(cycle_closure.CycleClosureError, match="matching intent"):
        cycle_closure.finish(tmp_path, identity=missing)

    actual = cycle_closure.begin(
        tmp_path,
        cycle_id="cycle-1",
        run_id="actual",
        run_attempt=1,
    )
    wrong = cycle_closure.MutationIdentity("cycle-1", "actual", 2)
    with pytest.raises(cycle_closure.CycleClosureError, match="matching intent"):
        cycle_closure.finish(tmp_path, identity=wrong)
    assert not (tmp_path / cycle_closure.done_key(wrong)).exists()
    cycle_closure.finish(tmp_path, identity=actual)


@pytest.mark.parametrize(
    ("cycle_id", "run_id", "run_attempt"),
    [
        ("../cycle", "run", 1),
        ("cycle", "run/child", 1),
        ("cycle", "run", 0),
        ("cycle", "run", -1),
        ("cycle", "run", True),
    ],
)
def test_invalid_mutation_identities_are_rejected(
    tmp_path: Path,
    cycle_id: str,
    run_id: str,
    run_attempt: int,
) -> None:
    with pytest.raises(ValueError):
        cycle_closure.begin(
            tmp_path,
            cycle_id=cycle_id,
            run_id=run_id,
            run_attempt=run_attempt,
        )


def test_seal_wait_times_out_with_pending_identity(tmp_path: Path) -> None:
    identity = cycle_closure.begin(
        tmp_path,
        cycle_id="cycle-1",
        run_id="running",
        run_attempt=1,
    )

    with pytest.raises(cycle_closure.CycleDrainTimeoutError) as caught:
        cycle_closure.seal_wait(
            tmp_path,
            cycle_id="cycle-1",
            timeout_seconds=0,
            poll_interval_seconds=0.01,
        )

    assert caught.value.pending == (identity,)


def test_s3_uses_create_only_puts_and_idempotent_reads() -> None:
    aws = FakeAws()
    identity = cycle_closure.begin(
        "s3://official-results/root",
        cycle_id="cycle-1",
        run_id="run-1",
        run_attempt=1,
        run_command=aws,
    )
    cycle_closure.begin(
        "s3://official-results/root",
        cycle_id="cycle-1",
        run_id="run-1",
        run_attempt=1,
        run_command=aws,
    )
    cycle_closure.finish(
        "s3://official-results/root", identity=identity, run_command=aws
    )
    result = cycle_closure.seal_wait(
        "s3://official-results/root",
        cycle_id="cycle-1",
        timeout_seconds=1,
        poll_interval_seconds=0.01,
        run_command=aws,
    )

    put_commands = [command for command in aws.commands if "put-object" in command]
    assert put_commands
    assert all(
        command[command.index("--if-none-match") + 1] == "*" for command in put_commands
    )
    assert result.observed_mutations == (identity,)


def test_s3_conflicting_existing_object_fails_closed() -> None:
    aws = FakeAws()
    identity = cycle_closure.MutationIdentity("cycle-1", "run-1", 1)
    aws.objects[("official-results", f"root/{cycle_closure.intent_key(identity)}")] = (
        b"conflict\n"
    )

    with pytest.raises(cycle_closure.CycleClosureConflictError, match=r"intent\.json"):
        cycle_closure.begin(
            "s3://official-results/root",
            cycle_id="cycle-1",
            run_id="run-1",
            run_attempt=1,
            run_command=aws,
        )


def test_cli_subcommands_use_explicit_identity_and_polling_args(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = str(tmp_path)
    assert (
        cycle_closure.main(
            [
                "begin",
                "--root",
                root,
                "--cycle-id",
                "cycle-1",
                "--writer-id",
                "run-1",
                "--run-attempt",
                "1",
            ]
        )
        == 0
    )
    assert (
        cycle_closure.main(
            [
                "finish",
                "--root",
                root,
                "--cycle-id",
                "cycle-1",
                "--run-id",
                "run-1",
                "--run-attempt",
                "1",
            ]
        )
        == 0
    )
    assert (
        cycle_closure.main(
            [
                "seal-wait",
                "--root",
                root,
                "--cycle-id",
                "cycle-1",
                "--timeout-seconds",
                "1",
                "--poll-interval-seconds",
                "0.01",
            ]
        )
        == 0
    )

    records = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [record["status"] for record in records] == [
        "mutation-open",
        "mutation-finished",
        "cycle-sealed",
    ]


class FakeAws:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}
        self.commands: list[list[str]] = []

    def __call__(
        self,
        command: list[str],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
    ) -> subprocess.CompletedProcess[str]:
        del check, capture_output, text
        self.commands.append(command)
        operation = command[2]
        bucket = _option(command, "--bucket")
        if operation == "put-object":
            key = _option(command, "--key")
            identity = (bucket, key)
            if identity in self.objects:
                return subprocess.CompletedProcess(
                    command, 1, "", "PreconditionFailed (412)"
                )
            self.objects[identity] = Path(_option(command, "--body")).read_bytes()
            return subprocess.CompletedProcess(command, 0, "{}", "")
        if operation == "get-object":
            key = _option(command, "--key")
            payload = self.objects.get((bucket, key))
            if payload is None:
                return subprocess.CompletedProcess(command, 1, "", "NoSuchKey (404)")
            Path(command[-1]).write_bytes(payload)
            return subprocess.CompletedProcess(command, 0, "{}", "")
        if operation == "list-objects-v2":
            prefix = _option(command, "--prefix")
            contents = [
                {"Key": key}
                for object_bucket, key in sorted(self.objects)
                if object_bucket == bucket and key.startswith(prefix)
            ]
            return subprocess.CompletedProcess(
                command, 0, json.dumps({"Contents": contents}), ""
            )
        raise AssertionError(f"unexpected AWS operation: {operation}")


def _option(command: list[str], name: str) -> str:
    return command[command.index(name) + 1]
