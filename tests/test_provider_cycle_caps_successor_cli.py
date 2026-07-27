from __future__ import annotations

import fcntl
import hashlib
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest
from legalforecast.cli import main
from legalforecast.labeling import provider_cycle_caps_materializer as caps_materializer


def _canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode()


def _legacy_caps() -> dict[str, object]:
    return {
        "schema_version": "legalforecast.provider_cycle_caps.v1",
        "cycle_id": "cycle-1",
        "providers": [
            {
                "provider": "openai",
                "cycle_reservation_cap_usd": "50.00",
            },
            {
                "provider": "anthropic",
                "cycle_reservation_cap_usd": "100.00",
            },
            {
                "provider": "google",
                "cycle_reservation_cap_usd": "50.00",
            },
        ],
    }


def _smoke(*, release_sha: str = "a" * 40) -> dict[str, object]:
    return {
        "schema_version": "legalforecast.official_labeling_authority_smoke.v1",
        "release_sha": release_sha,
        "authority_resource_identity_sha256": "b" * 64,
        "provider_call_made": False,
        "allowed": {
            "describe_table": True,
            "describe_time_to_live": True,
            "get_item": True,
            "put_item": True,
            "update_item": True,
            "condition_check_item": True,
            "transact_write_items": True,
        },
        "denied": {
            "scan": True,
            "delete_item": True,
            "outside_table_describe": True,
            "outside_table_get_item": True,
            "outside_table_put_item": True,
            "outside_table_update_item": True,
            "outside_table_transact_write_items": True,
            "list_tables": True,
        },
    }


def _policy(*, openai_alias: str = "cycle1-openai") -> dict[str, object]:
    return {
        "schema_version": "legalforecast.provider_cycle_caps_successor_policy.v1",
        "cycle_id": "cycle-1",
        "provider_accounts": [
            {"provider": "anthropic", "account": "cycle1-anthropic"},
            {"provider": "google", "account": "cycle1-google"},
            {"provider": "openai", "account": openai_alias},
        ],
        "spend_authority": {
            "backend": "dynamodb",
            "ledger_scope_fields": ["cycle_id", "provider", "account"],
            "max_billable_attempts": 2,
            "failure_threshold": 3,
            "failure_window_seconds": 300,
        },
    }


def _write_inputs(
    root: Path,
    *,
    smoke: dict[str, object] | None = None,
    policy: dict[str, object] | None = None,
    canonical_policy: bool = True,
) -> tuple[Path, Path, Path, dict[str, bytes]]:
    root.mkdir()
    paths = (
        root / "legacy-provider-cycle-caps.json",
        root / "authority-smoke.json",
        root / "provider-caps-successor-policy.json",
    )
    payloads = {
        "legacy": _canonical_json_bytes(_legacy_caps()),
        "smoke": _canonical_json_bytes(smoke or _smoke()),
        "policy": (
            _canonical_json_bytes(policy or _policy())
            if canonical_policy
            else json.dumps(policy or _policy()).encode()
        ),
    }
    for path, payload in zip(paths, payloads.values(), strict=True):
        path.write_bytes(payload)
    return (*paths, payloads)


def _args(
    *,
    legacy: Path,
    smoke: Path,
    policy: Path,
    output_root: Path,
    payloads: dict[str, bytes],
    expected_release_sha: str = "a" * 40,
    expected_smoke_sha256: str | None = None,
    expected_policy_sha256: str | None = None,
) -> list[str]:
    return [
        "acquisition",
        "materialize-provider-cycle-caps-successor",
        "--legacy-provider-cycle-caps",
        str(legacy),
        "--expected-legacy-caps-sha256",
        hashlib.sha256(payloads["legacy"]).hexdigest(),
        "--authority-smoke-receipt",
        str(smoke),
        "--expected-authority-smoke-sha256",
        expected_smoke_sha256 or hashlib.sha256(payloads["smoke"]).hexdigest(),
        "--expected-smoke-release-sha",
        expected_release_sha,
        "--provider-caps-successor-policy",
        str(policy),
        "--expected-provider-policy-sha256",
        expected_policy_sha256 or hashlib.sha256(payloads["policy"]).hexdigest(),
        "--output-root",
        str(output_root),
    ]


def _invoke(tmp_path: Path) -> tuple[int, Path, tuple[Path, Path, Path]]:
    legacy, smoke, policy, payloads = _write_inputs(tmp_path / "inputs")
    output_root = tmp_path / "outputs"
    result = main(
        _args(
            legacy=legacy,
            smoke=smoke,
            policy=policy,
            output_root=output_root,
            payloads=payloads,
        )
    )
    outputs = (
        output_root / "provider-cycle-caps.json",
        output_root / "provider-cycle-caps-successor-receipt.json",
        output_root / "run-cards" / "materialize-provider-cycle-caps-successor.json",
    )
    return result, output_root, outputs


def _add_smoke_extra(value: dict[str, object]) -> None:
    value["extra"] = True


def _remove_smoke_allowed(value: dict[str, object]) -> None:
    del value["allowed"]


def _set_smoke_table_value(
    value: dict[str, object], table: str, field: str, replacement: bool
) -> None:
    nested = cast(dict[str, object], value[table])
    nested[field] = replacement


def _set_smoke_get_item_false(value: dict[str, object]) -> None:
    _set_smoke_table_value(value, "allowed", "get_item", False)


def _set_smoke_scan_false(value: dict[str, object]) -> None:
    _set_smoke_table_value(value, "denied", "scan", False)


def _set_smoke_provider_call_true(value: dict[str, object]) -> None:
    value["provider_call_made"] = True


def _set_smoke_identity_uppercase(value: dict[str, object]) -> None:
    value["authority_resource_identity_sha256"] = "B" * 64


def _set_smoke_release_uppercase(value: dict[str, object]) -> None:
    value["release_sha"] = "A" * 40


_SMOKE_MUTATIONS: tuple[tuple[Callable[[dict[str, object]], None], str], ...] = (
    (_add_smoke_extra, "field set"),
    (_remove_smoke_allowed, "field set"),
    (_set_smoke_get_item_false, "allowed operations"),
    (_set_smoke_scan_false, "denied operations"),
    (_set_smoke_provider_call_true, "provider_call_made=false"),
    (_set_smoke_identity_uppercase, "lowercase SHA-256"),
    (_set_smoke_release_uppercase, "lowercase commit SHA"),
)


def test_cli_help_documents_provider_free_successor(capsys: Any) -> None:
    with pytest.raises(SystemExit, match="0"):
        main(
            [
                "acquisition",
                "materialize-provider-cycle-caps-successor",
                "--help",
            ]
        )

    output = capsys.readouterr().out.lower()
    assert "provider-free" in output
    assert "authority-smoke" in output
    assert "provider call" in output


def test_cli_publishes_hash_bound_successor_receipt_and_run_card(
    tmp_path: Path,
) -> None:
    result, output_root, outputs = _invoke(tmp_path)

    assert result == 0
    caps_path, receipt_path, run_card_path = outputs
    caps_bytes = caps_path.read_bytes()
    receipt = json.loads(receipt_path.read_bytes())
    run_card = json.loads(run_card_path.read_bytes())
    caps = json.loads(caps_bytes)
    assert caps["spend_authority"]["resource_identity_sha256"] == "b" * 64
    assert receipt["authority_smoke"] == {
        "bytes": len(_canonical_json_bytes(_smoke())),
        "release_sha": "a" * 40,
        "schema_version": "legalforecast.official_labeling_authority_smoke.v1",
        "sha256": hashlib.sha256(_canonical_json_bytes(_smoke())).hexdigest(),
    }
    assert receipt["policy"]["schema_version"] == (
        "legalforecast.provider_cycle_caps_successor_policy.v1"
    )
    assert receipt["successor"]["sha256"] == hashlib.sha256(caps_bytes).hexdigest()
    assert run_card["schema_version"] == (
        "legalforecast.provider_cycle_caps_successor_run_card.v1"
    )
    assert set(run_card) == {
        "aws_activity_executed",
        "aws_activity_requested",
        "dry_run",
        "execute",
        "input_commitments",
        "input_paths",
        "output_commitments",
        "output_paths",
        "paid_activity_executed",
        "paid_activity_requested",
        "provider_activity_executed",
        "provider_activity_requested",
        "release_sha",
        "schema_version",
        "stage",
        "status",
    }
    assert "generated_at" not in run_card
    assert run_card["stage"] == "materialize-provider-cycle-caps-successor"
    assert run_card["status"] == "completed"
    assert run_card["provider_activity_requested"] is False
    assert run_card["provider_activity_executed"] is False
    assert run_card["paid_activity_requested"] is False
    assert run_card["paid_activity_executed"] is False
    assert run_card["aws_activity_requested"] is False
    assert run_card["aws_activity_executed"] is False
    assert run_card["output_commitments"]["provider_cycle_caps"]["sha256"] == (
        hashlib.sha256(caps_bytes).hexdigest()
    )
    assert set(output_root.iterdir()) == {
        caps_path,
        receipt_path,
        output_root / "run-cards",
    }


def test_cli_resume_is_byte_and_inode_idempotent_and_repairs_only_missing_output(
    tmp_path: Path,
) -> None:
    result, _, outputs = _invoke(tmp_path)
    assert result == 0
    snapshots = {path: (path.read_bytes(), path.stat().st_ino) for path in outputs}
    legacy, smoke, policy = (
        tmp_path / "inputs" / name
        for name in (
            "legacy-provider-cycle-caps.json",
            "authority-smoke.json",
            "provider-caps-successor-policy.json",
        )
    )
    payloads = {
        "legacy": legacy.read_bytes(),
        "smoke": smoke.read_bytes(),
        "policy": policy.read_bytes(),
    }
    args = _args(
        legacy=legacy,
        smoke=smoke,
        policy=policy,
        output_root=tmp_path / "outputs",
        payloads=payloads,
    )

    assert main(args) == 0
    assert snapshots == {
        path: (path.read_bytes(), path.stat().st_ino) for path in outputs
    }

    outputs[-1].unlink()
    assert main(args) == 0
    assert outputs[-1].read_bytes() == snapshots[outputs[-1]][0]
    assert {path: (path.read_bytes(), path.stat().st_ino) for path in outputs[:-1]} == {
        path: snapshots[path] for path in outputs[:-1]
    }


@pytest.mark.parametrize(
    ("mutation", "message"),
    _SMOKE_MUTATIONS,
)
def test_cli_rejects_partial_or_noncanonical_smoke_before_output(
    tmp_path: Path,
    mutation: Callable[[dict[str, object]], None],
    message: str,
    capsys: Any,
) -> None:
    smoke_record = _smoke()
    mutation(smoke_record)
    legacy, smoke, policy, payloads = _write_inputs(
        tmp_path / "inputs", smoke=smoke_record
    )
    output_root = tmp_path / "outputs"

    assert (
        main(
            _args(
                legacy=legacy,
                smoke=smoke,
                policy=policy,
                output_root=output_root,
                payloads=payloads,
            )
        )
        == 2
    )
    assert message in capsys.readouterr().err
    assert not output_root.exists()


@pytest.mark.parametrize(
    ("argument", "value", "message"),
    [
        ("expected_release_sha", "A" * 40, "lowercase commit SHA"),
        ("expected_smoke_sha256", "C" * 64, "lowercase SHA-256"),
        ("expected_policy_sha256", "D" * 64, "lowercase SHA-256"),
        ("expected_release_sha", "c" * 40, "differs from the expected release"),
        ("expected_smoke_sha256", "c" * 64, "raw bytes differ"),
        ("expected_policy_sha256", "d" * 64, "raw bytes differ"),
    ],
)
def test_cli_rejects_noncanonical_expected_digests(
    tmp_path: Path,
    argument: str,
    value: str,
    message: str,
    capsys: Any,
) -> None:
    legacy, smoke, policy, payloads = _write_inputs(tmp_path / "inputs")
    kwargs: dict[str, str] = {argument: value}

    assert (
        main(
            _args(
                legacy=legacy,
                smoke=smoke,
                policy=policy,
                output_root=tmp_path / "outputs",
                payloads=payloads,
                **kwargs,
            )
        )
        == 2
    )
    assert message in capsys.readouterr().err
    assert not (tmp_path / "outputs").exists()


@pytest.mark.parametrize(
    "alias",
    [
        "123456789012",
        "arn:aws:iam::123456789012:role/labeling",
        "cycle1-credential",
        "AKIAIOSFODNN7EXAMPLE",
    ],
)
def test_cli_rejects_private_or_credential_like_aliases(
    tmp_path: Path,
    alias: str,
    capsys: Any,
) -> None:
    legacy, smoke, policy, payloads = _write_inputs(
        tmp_path / "inputs", policy=_policy(openai_alias=alias)
    )

    assert (
        main(
            _args(
                legacy=legacy,
                smoke=smoke,
                policy=policy,
                output_root=tmp_path / "outputs",
                payloads=payloads,
            )
        )
        == 2
    )
    assert "public account alias" in capsys.readouterr().err
    assert not (tmp_path / "outputs").exists()


def test_cli_rejects_noncanonical_policy_bytes(tmp_path: Path, capsys: Any) -> None:
    legacy, smoke, policy, payloads = _write_inputs(
        tmp_path / "inputs", canonical_policy=False
    )

    assert (
        main(
            _args(
                legacy=legacy,
                smoke=smoke,
                policy=policy,
                output_root=tmp_path / "outputs",
                payloads=payloads,
            )
        )
        == 2
    )
    assert "canonical JSON" in capsys.readouterr().err


@pytest.mark.parametrize("drift", ["extra", "missing", "wrong-cycle", "unsorted"])
def test_cli_rejects_closed_policy_drift_before_output(
    tmp_path: Path,
    drift: str,
    capsys: Any,
) -> None:
    policy_record = _policy()
    if drift == "extra":
        policy_record["extra"] = True
    elif drift == "missing":
        del policy_record["spend_authority"]
    elif drift == "wrong-cycle":
        policy_record["cycle_id"] = "cycle-2"
    else:
        accounts = cast(list[object], policy_record["provider_accounts"])
        policy_record["provider_accounts"] = list(reversed(accounts))
    legacy, smoke, policy, payloads = _write_inputs(
        tmp_path / "inputs", policy=policy_record
    )

    assert (
        main(
            _args(
                legacy=legacy,
                smoke=smoke,
                policy=policy,
                output_root=tmp_path / "outputs",
                payloads=payloads,
            )
        )
        == 2
    )
    assert "provider" in capsys.readouterr().err
    assert not (tmp_path / "outputs").exists()


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "fifo"])
def test_cli_rejects_unsafe_input_files(
    tmp_path: Path,
    kind: str,
    capsys: Any,
) -> None:
    legacy, smoke, policy, payloads = _write_inputs(tmp_path / "inputs")
    unsafe = tmp_path / f"unsafe-{kind}.json"
    if kind == "symlink":
        unsafe.symlink_to(smoke)
    elif kind == "hardlink":
        unsafe.hardlink_to(smoke)
    else:
        os.mkfifo(unsafe)

    assert (
        main(
            _args(
                legacy=legacy,
                smoke=unsafe,
                policy=policy,
                output_root=tmp_path / "outputs",
                payloads=payloads,
            )
        )
        == 2
    )
    assert "authority-smoke input" in capsys.readouterr().err
    assert not (tmp_path / "outputs").exists()


def test_cli_rejects_symlinked_input_parent(tmp_path: Path, capsys: Any) -> None:
    legacy, smoke, policy, payloads = _write_inputs(tmp_path / "inputs")
    linked_parent = tmp_path / "linked-inputs"
    linked_parent.symlink_to(tmp_path / "inputs", target_is_directory=True)

    assert (
        main(
            _args(
                legacy=legacy,
                smoke=linked_parent / smoke.name,
                policy=policy,
                output_root=tmp_path / "outputs",
                payloads=payloads,
            )
        )
        == 2
    )
    assert "safely read" in capsys.readouterr().err
    assert not (tmp_path / "outputs").exists()


def test_cli_rejects_conflicting_or_unexpected_output_residue(
    tmp_path: Path,
    capsys: Any,
) -> None:
    result, output_root, outputs = _invoke(tmp_path)
    assert result == 0
    outputs[0].write_bytes(b"changed\n")
    legacy, smoke, policy = (
        tmp_path / "inputs" / name
        for name in (
            "legacy-provider-cycle-caps.json",
            "authority-smoke.json",
            "provider-caps-successor-policy.json",
        )
    )
    payloads = {
        "legacy": legacy.read_bytes(),
        "smoke": smoke.read_bytes(),
        "policy": policy.read_bytes(),
    }
    args = _args(
        legacy=legacy,
        smoke=smoke,
        policy=policy,
        output_root=output_root,
        payloads=payloads,
    )

    assert main(args) == 2
    assert "conflicts with deterministic output" in capsys.readouterr().err

    outputs[0].write_bytes(b"changed again\n")
    (output_root / "unexpected").write_text("residue", encoding="utf-8")
    assert main(args) == 2
    assert "unexpected output residue" in capsys.readouterr().err


def test_cli_rejects_symlink_and_hardlink_output_tampering(
    tmp_path: Path,
    capsys: Any,
) -> None:
    result, _, outputs = _invoke(tmp_path)
    assert result == 0
    caps_path = outputs[0]
    original = caps_path.read_bytes()
    caps_path.unlink()
    external = tmp_path / "external"
    external.write_bytes(original)
    caps_path.symlink_to(external)

    legacy, smoke, policy = (
        tmp_path / "inputs" / name
        for name in (
            "legacy-provider-cycle-caps.json",
            "authority-smoke.json",
            "provider-caps-successor-policy.json",
        )
    )
    payloads = {
        "legacy": legacy.read_bytes(),
        "smoke": smoke.read_bytes(),
        "policy": policy.read_bytes(),
    }
    args = _args(
        legacy=legacy,
        smoke=smoke,
        policy=policy,
        output_root=tmp_path / "outputs",
        payloads=payloads,
    )

    assert main(args) == 2
    assert "unique regular file" in capsys.readouterr().err

    caps_path.unlink()
    caps_path.hardlink_to(external)
    assert main(args) == 2
    assert "unique regular file" in capsys.readouterr().err


def test_cli_rejects_special_output_without_blocking(
    tmp_path: Path,
    capsys: Any,
) -> None:
    legacy, smoke, policy, payloads = _write_inputs(tmp_path / "inputs")
    output_root = tmp_path / "outputs"
    output_root.mkdir()
    os.mkfifo(output_root / "provider-cycle-caps.json")

    assert (
        main(
            _args(
                legacy=legacy,
                smoke=smoke,
                policy=policy,
                output_root=output_root,
                payloads=payloads,
            )
        )
        == 2
    )
    assert "unique regular file" in capsys.readouterr().err
    assert set(output_root.iterdir()) == {output_root / "provider-cycle-caps.json"}


def test_cli_preflights_conflicting_run_card_before_publishing_missing_outputs(
    tmp_path: Path,
    capsys: Any,
) -> None:
    legacy, smoke, policy, payloads = _write_inputs(tmp_path / "inputs")
    output_root = tmp_path / "outputs"
    run_cards = output_root / "run-cards"
    run_cards.mkdir(parents=True)
    conflict = run_cards / "materialize-provider-cycle-caps-successor.json"
    conflict.write_bytes(b"conflict\n")

    assert (
        main(
            _args(
                legacy=legacy,
                smoke=smoke,
                policy=policy,
                output_root=output_root,
                payloads=payloads,
            )
        )
        == 2
    )
    assert "conflicts with deterministic output" in capsys.readouterr().err
    assert set(output_root.iterdir()) == {run_cards}
    assert set(run_cards.iterdir()) == {conflict}
    assert conflict.read_bytes() == b"conflict\n"


@pytest.mark.parametrize("mutation", ["in-place", "atomic-replace"])
def test_cli_rechecks_input_path_inode_and_bytes_immediately_before_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: Any,
    mutation: str,
) -> None:
    legacy, smoke, policy, payloads = _write_inputs(tmp_path / "inputs")
    output_root = tmp_path / "outputs"
    original_publish = caps_materializer._publish_or_verify  # pyright: ignore[reportPrivateUsage]
    publication_calls = 0

    def mutate_after_initial_validation(
        directory_fd: int, name: str, payload: bytes
    ) -> None:
        nonlocal publication_calls
        original_publish(directory_fd, name, payload)
        publication_calls += 1
        if publication_calls != 1:
            return
        if mutation == "in-place":
            smoke.write_bytes(b"{}\n")
            return
        replacement = smoke.with_suffix(".replacement")
        replacement.write_bytes(payloads["smoke"])
        os.replace(replacement, smoke)

    monkeypatch.setattr(
        caps_materializer,
        "_publish_or_verify",
        mutate_after_initial_validation,
    )

    assert (
        main(
            _args(
                legacy=legacy,
                smoke=smoke,
                policy=policy,
                output_root=output_root,
                payloads=payloads,
            )
        )
        == 2
    )
    assert "changed between validation and publication" in capsys.readouterr().err
    assert not output_root.exists()
    assert set(tmp_path.iterdir()) == {tmp_path / "inputs"}


@pytest.mark.parametrize("failed_publication", [2, 3])
def test_cli_publishes_no_final_tree_when_staging_a_set_member_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: Any,
    failed_publication: int,
) -> None:
    legacy, smoke, policy, payloads = _write_inputs(tmp_path / "inputs")
    output_root = tmp_path / "outputs"
    original_publish = caps_materializer._publish_or_verify  # pyright: ignore[reportPrivateUsage]
    publication_calls = 0

    def fail_one_staged_publication(
        directory_fd: int, name: str, payload: bytes
    ) -> None:
        nonlocal publication_calls
        publication_calls += 1
        if publication_calls == failed_publication:
            raise caps_materializer.ProviderCycleCapsMaterializationError(
                f"injected publication {failed_publication} failure"
            )
        original_publish(directory_fd, name, payload)

    monkeypatch.setattr(
        caps_materializer,
        "_publish_or_verify",
        fail_one_staged_publication,
    )

    assert (
        main(
            _args(
                legacy=legacy,
                smoke=smoke,
                policy=policy,
                output_root=output_root,
                payloads=payloads,
            )
        )
        == 2
    )
    assert (
        f"injected publication {failed_publication} failure" in capsys.readouterr().err
    )
    assert not output_root.exists()
    assert set(tmp_path.iterdir()) == {tmp_path / "inputs"}


def test_cli_rejects_output_root_swap_during_missing_card_reauthentication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: Any,
) -> None:
    result, output_root, outputs = _invoke(tmp_path)
    assert result == 0
    outputs[-1].unlink()
    legacy, smoke, policy = (
        tmp_path / "inputs" / name
        for name in (
            "legacy-provider-cycle-caps.json",
            "authority-smoke.json",
            "provider-caps-successor-policy.json",
        )
    )
    payloads = {
        "legacy": legacy.read_bytes(),
        "smoke": smoke.read_bytes(),
        "policy": policy.read_bytes(),
    }
    original_reverify = caps_materializer._reverify_input_snapshots  # pyright: ignore[reportPrivateUsage]
    detached_root = tmp_path / "detached-output"

    def swap_root_then_reverify(snapshots: object) -> None:
        output_root.rename(detached_root)
        output_root.mkdir()
        (output_root / "attacker-marker").write_text("marker", encoding="utf-8")
        original_reverify(cast(Any, snapshots))

    monkeypatch.setattr(
        caps_materializer,
        "_reverify_input_snapshots",
        swap_root_then_reverify,
    )

    assert (
        main(
            _args(
                legacy=legacy,
                smoke=smoke,
                policy=policy,
                output_root=output_root,
                payloads=payloads,
            )
        )
        == 2
    )
    assert "output root changed" in capsys.readouterr().err
    assert set(output_root.iterdir()) == {output_root / "attacker-marker"}
    assert not (
        detached_root / "run-cards" / "materialize-provider-cycle-caps-successor.json"
    ).exists()


def test_cli_atomically_populates_an_existing_empty_output_root(
    tmp_path: Path,
) -> None:
    legacy, smoke, policy, payloads = _write_inputs(tmp_path / "inputs")
    output_root = tmp_path / "outputs"
    output_root.mkdir()

    assert (
        main(
            _args(
                legacy=legacy,
                smoke=smoke,
                policy=policy,
                output_root=output_root,
                payloads=payloads,
            )
        )
        == 0
    )
    assert set(output_root.iterdir()) == {
        output_root / "provider-cycle-caps.json",
        output_root / "provider-cycle-caps-successor-receipt.json",
        output_root / "run-cards",
    }


def test_cli_repairs_missing_run_card_directory_without_replacing_valid_members(
    tmp_path: Path,
) -> None:
    result, output_root, outputs = _invoke(tmp_path)
    assert result == 0
    preserved = {path: (path.read_bytes(), path.stat().st_ino) for path in outputs[:-1]}
    outputs[-1].unlink()
    outputs[-1].parent.rmdir()
    legacy, smoke, policy = (
        tmp_path / "inputs" / name
        for name in (
            "legacy-provider-cycle-caps.json",
            "authority-smoke.json",
            "provider-caps-successor-policy.json",
        )
    )
    payloads = {
        "legacy": legacy.read_bytes(),
        "smoke": smoke.read_bytes(),
        "policy": policy.read_bytes(),
    }

    assert (
        main(
            _args(
                legacy=legacy,
                smoke=smoke,
                policy=policy,
                output_root=output_root,
                payloads=payloads,
            )
        )
        == 0
    )
    assert preserved == {
        path: (path.read_bytes(), path.stat().st_ino) for path in outputs[:-1]
    }
    assert outputs[-1].is_file()


def test_cli_reauthenticates_staged_tree_after_input_reauthentication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: Any,
) -> None:
    legacy, smoke, policy, payloads = _write_inputs(tmp_path / "inputs")
    output_root = tmp_path / "outputs"
    original_reverify = caps_materializer._reverify_input_snapshots  # pyright: ignore[reportPrivateUsage]

    def corrupt_staging_after_input_reauthentication(snapshots: object) -> None:
        original_reverify(cast(Any, snapshots))
        staged = [
            path
            for path in tmp_path.iterdir()
            if path.name.startswith(".outputs.") and path.name.endswith(".partial")
        ]
        assert len(staged) == 1
        (staged[0] / "provider-cycle-caps.json").write_bytes(b"corrupt\n")

    monkeypatch.setattr(
        caps_materializer,
        "_reverify_input_snapshots",
        corrupt_staging_after_input_reauthentication,
    )

    assert (
        main(
            _args(
                legacy=legacy,
                smoke=smoke,
                policy=policy,
                output_root=output_root,
                payloads=payloads,
            )
        )
        == 2
    )
    assert "staged successor" in capsys.readouterr().err
    assert not output_root.exists()
    assert set(tmp_path.iterdir()) == {tmp_path / "inputs"}


def test_cli_rejects_output_parent_swap_before_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: Any,
) -> None:
    legacy, smoke, policy, payloads = _write_inputs(tmp_path / "inputs")
    output_root = tmp_path / "outputs"
    detached_parent = tmp_path.with_name(f"{tmp_path.name}-detached")
    original_reverify = caps_materializer._reverify_input_snapshots  # pyright: ignore[reportPrivateUsage]

    def swap_parent_after_input_reauthentication(snapshots: object) -> None:
        original_reverify(cast(Any, snapshots))
        tmp_path.rename(detached_parent)
        tmp_path.mkdir()

    monkeypatch.setattr(
        caps_materializer,
        "_reverify_input_snapshots",
        swap_parent_after_input_reauthentication,
    )

    assert (
        main(
            _args(
                legacy=legacy,
                smoke=smoke,
                policy=policy,
                output_root=output_root,
                payloads=payloads,
            )
        )
        == 2
    )
    assert "output parent" in capsys.readouterr().err
    assert not output_root.exists()
    assert (detached_parent / "inputs").is_dir()


def test_cli_reconciles_authenticated_stale_exchange_tree_on_resume(
    tmp_path: Path,
) -> None:
    result, output_root, outputs = _invoke(tmp_path)
    assert result == 0
    snapshots = {path: (path.read_bytes(), path.stat().st_ino) for path in outputs}
    stale = output_root.parent / f".{output_root.name}.{'c' * 32}.partial"
    stale.mkdir()
    legacy, smoke, policy = (
        tmp_path / "inputs" / name
        for name in (
            "legacy-provider-cycle-caps.json",
            "authority-smoke.json",
            "provider-caps-successor-policy.json",
        )
    )
    payloads = {
        "legacy": legacy.read_bytes(),
        "smoke": smoke.read_bytes(),
        "policy": policy.read_bytes(),
    }

    assert (
        main(
            _args(
                legacy=legacy,
                smoke=smoke,
                policy=policy,
                output_root=output_root,
                payloads=payloads,
            )
        )
        == 0
    )
    assert not stale.exists()
    assert snapshots == {
        path: (path.read_bytes(), path.stat().st_ino) for path in outputs
    }


def test_cli_removes_crash_left_per_file_temporary_and_publishes(
    tmp_path: Path,
) -> None:
    legacy, smoke, policy, payloads = _write_inputs(tmp_path / "inputs")
    output_root = tmp_path / "outputs"
    stale = output_root.parent / f".{output_root.name}.{'c' * 32}.partial"
    stale.mkdir()
    temporary = stale / f".provider-cycle-caps.json.{'d' * 16}.partial"
    temporary.write_bytes(b"partial")

    assert (
        main(
            _args(
                legacy=legacy,
                smoke=smoke,
                policy=policy,
                output_root=output_root,
                payloads=payloads,
            )
        )
        == 0
    )
    assert not stale.exists()
    assert (output_root / "provider-cycle-caps.json").is_file()
    assert (output_root / "provider-cycle-caps-successor-receipt.json").is_file()
    assert (
        output_root / "run-cards" / "materialize-provider-cycle-caps-successor.json"
    ).is_file()


def test_cli_rejects_stale_staging_root_rebinding_before_preflight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: Any,
) -> None:
    legacy, smoke, policy, payloads = _write_inputs(tmp_path / "inputs")
    output_root = tmp_path / "outputs"
    stale = output_root.parent / f".{output_root.name}.{'c' * 32}.partial"
    detached_stale = tmp_path / "detached-stale"
    stale.mkdir()
    original_preflight = caps_materializer._preflight_output_tree  # pyright: ignore[reportPrivateUsage]
    rebound = False

    def rebind_stale_root_before_preflight(
        parent_fd: int,
        target_name: str,
        *,
        caps_bytes: bytes,
        receipt_bytes: bytes,
        run_card_bytes: bytes,
        expected_root_identity: tuple[int, ...] | None = None,
    ) -> Any:
        nonlocal rebound
        if target_name == stale.name and not rebound:
            stale.rename(detached_stale)
            stale.mkdir()
            rebound = True
        return original_preflight(
            parent_fd,
            target_name,
            caps_bytes=caps_bytes,
            receipt_bytes=receipt_bytes,
            run_card_bytes=run_card_bytes,
            expected_root_identity=expected_root_identity,
        )

    monkeypatch.setattr(
        caps_materializer,
        "_preflight_output_tree",
        rebind_stale_root_before_preflight,
    )

    def reject_replacement_inspection(
        _entries: frozenset[str],
        _allowed: frozenset[str],
        _label: str,
    ) -> None:
        pytest.fail(
            "replacement staging tree was inspected before identity authentication"
        )

    monkeypatch.setattr(
        caps_materializer,
        "_reject_entry_set",
        reject_replacement_inspection,
    )

    assert (
        main(
            _args(
                legacy=legacy,
                smoke=smoke,
                policy=policy,
                output_root=output_root,
                payloads=payloads,
            )
        )
        == 2
    )
    assert "changed during recovery" in capsys.readouterr().err
    assert detached_stale.is_dir()
    assert stale.is_dir()
    assert not output_root.exists()


def test_cli_does_not_reclaim_live_publishers_active_staging_tree(
    tmp_path: Path,
    capsys: Any,
) -> None:
    legacy, smoke, policy, payloads = _write_inputs(tmp_path / "inputs")
    output_root = tmp_path / "outputs"
    active_stage = tmp_path / f".{output_root.name}.{'d' * 32}.partial"
    active_stage.mkdir()
    owner_fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        fcntl.flock(owner_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

        assert (
            main(
                _args(
                    legacy=legacy,
                    smoke=smoke,
                    policy=policy,
                    output_root=output_root,
                    payloads=payloads,
                )
            )
            == 2
        )
        assert "another live successor publisher" in capsys.readouterr().err
        assert active_stage.is_dir()
        assert not output_root.exists()
    finally:
        os.close(owner_fd)


def test_cli_rejects_relative_or_symlinked_output_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: Any,
) -> None:
    legacy, smoke, policy, payloads = _write_inputs(tmp_path / "inputs")
    monkeypatch.chdir(tmp_path)
    relative_root = Path("outputs")

    assert (
        main(
            _args(
                legacy=legacy,
                smoke=smoke,
                policy=policy,
                output_root=relative_root,
                payloads=payloads,
            )
        )
        == 2
    )
    assert "absolute canonical path" in capsys.readouterr().err

    external = tmp_path / "external-output"
    external.mkdir()
    linked = tmp_path / "linked-output"
    linked.symlink_to(external, target_is_directory=True)
    assert (
        main(
            _args(
                legacy=legacy,
                smoke=smoke,
                policy=policy,
                output_root=linked,
                payloads=payloads,
            )
        )
        == 2
    )
    assert "output path" in capsys.readouterr().err
    assert not tuple(external.iterdir())

    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(external, target_is_directory=True)
    assert (
        main(
            _args(
                legacy=legacy,
                smoke=smoke,
                policy=policy,
                output_root=linked_parent / "nested-output",
                payloads=payloads,
            )
        )
        == 2
    )
    assert "output path" in capsys.readouterr().err
    assert not (external / "nested-output").exists()


def test_cli_rejects_identity_only_substitute_for_smoke(
    tmp_path: Path,
    capsys: Any,
) -> None:
    legacy, smoke, policy, payloads = _write_inputs(tmp_path / "inputs")
    payloads["smoke"] = _canonical_json_bytes(
        {"authority_resource_identity_sha256": "b" * 64}
    )
    smoke.write_bytes(payloads["smoke"])

    assert (
        main(
            _args(
                legacy=legacy,
                smoke=smoke,
                policy=policy,
                output_root=tmp_path / "outputs",
                payloads=payloads,
            )
        )
        == 2
    )
    assert "field set" in capsys.readouterr().err
    assert not (tmp_path / "outputs").exists()


def test_cli_rejects_duplicate_smoke_keys_before_output(
    tmp_path: Path,
    capsys: Any,
) -> None:
    legacy, smoke, policy, payloads = _write_inputs(tmp_path / "inputs")
    original = payloads["smoke"].decode()
    payloads["smoke"] = original.replace(
        '  "provider_call_made": false,',
        '  "provider_call_made": true,\n  "provider_call_made": false,',
    ).encode()
    smoke.write_bytes(payloads["smoke"])

    assert (
        main(
            _args(
                legacy=legacy,
                smoke=smoke,
                policy=policy,
                output_root=tmp_path / "outputs",
                payloads=payloads,
            )
        )
        == 2
    )
    assert "duplicate key 'provider_call_made'" in capsys.readouterr().err
    assert not (tmp_path / "outputs").exists()
