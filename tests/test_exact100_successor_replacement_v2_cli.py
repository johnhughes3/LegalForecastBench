# pyright: reportPrivateUsage=false
"""Focused regression coverage for the closed exact-100 successor v2 CLI."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

import pytest
from legalforecast.ingestion import (
    exact100_successor_replacement_v2_cli as successor_v2_cli,
)
from tests.test_exact100_successor_replacement_v2 import _fixture


def _args(
    tmp_path: Path,
    *,
    output_root: Path | None = None,
    replay: successor_v2_cli.V2InputReplay | None = None,
) -> argparse.Namespace:
    roots = {
        name: tmp_path / name.replace("_", "-")
        for name in (
            "predecessor_root",
            "complete_materialization_root",
            "stipulated_evidence_root",
            "final153_snapshot",
            "wider_plan_root",
            "wider_exclusion_root",
            "historical_packet_root",
        )
    }
    return argparse.Namespace(
        **roots,
        output_root=output_root or tmp_path / "successor-v2",
        resume=True,
        _replay_v2_inputs=replay,
    )


def _authenticated_replay() -> successor_v2_cli.V2InputReplay:
    inputs = _fixture()

    def replay(_: argparse.Namespace) -> tuple[Any, Any, Any, Any]:
        return (
            inputs["base"],
            inputs["terminals"],
            inputs["repairs"],
            inputs["wider"],
        )

    return replay


def test_v2_parser_exposes_only_authenticated_replay_roots() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    successor_v2_cli.add_parser(subparsers, handler=successor_v2_cli.run)
    command = subparsers.choices["project-exact100-successor-replacement-v2"]
    options = {
        option for action in command._actions for option in action.option_strings
    }

    assert {
        "--predecessor-root",
        "--complete-materialization-root",
        "--stipulated-evidence-root",
        "--final153-snapshot",
        "--wider-plan-root",
        "--wider-exclusion-root",
        "--historical-packet-root",
        "--output-root",
        "--resume",
        "--no-resume",
    } <= options
    for forbidden in (
        "candidate",
        "provider",
        "pacer",
        "paid",
        "model",
        "freeze",
        "evaluation",
        "dispatch",
    ):
        assert not any(forbidden in option.lower() for option in options)


def test_v2_run_requires_authenticated_integration_replay(tmp_path: Path) -> None:
    output_root = tmp_path / "successor-v2"
    args = _args(tmp_path, output_root=output_root)

    with pytest.raises(
        successor_v2_cli.Exact100SuccessorReplacementV2CliError,
        match="requires authenticated integration replay",
    ):
        successor_v2_cli.run(args)

    assert not output_root.exists()


def test_v2_run_resumes_only_byte_identical_projection(tmp_path: Path) -> None:
    calls = 0

    def replay(args: argparse.Namespace) -> tuple[Any, Any, Any, Any]:
        nonlocal calls
        calls += 1
        return authenticated_replay(args)

    authenticated_replay = _authenticated_replay()
    output_root = tmp_path / "successor-v2"
    args = _args(tmp_path, output_root=output_root, replay=replay)
    assert successor_v2_cli.run(args) == 0
    first_payloads = {
        path.relative_to(output_root): path.read_bytes()
        for path in output_root.rglob("*")
        if path.is_file()
    }

    assert successor_v2_cli.run(args) == 0
    second_payloads = {
        path.relative_to(output_root): path.read_bytes()
        for path in output_root.rglob("*")
        if path.is_file()
    }

    assert calls == 4
    assert second_payloads == first_payloads


def test_v2_run_rejects_output_overlapping_authenticated_input(tmp_path: Path) -> None:
    output_root = tmp_path / "predecessor-root"
    output_root.mkdir()
    args = _args(tmp_path, output_root=output_root, replay=_authenticated_replay())

    with pytest.raises(
        successor_v2_cli.Exact100SuccessorReplacementV2CliError,
        match="output overlaps authenticated input evidence",
    ):
        successor_v2_cli.run(args)


def test_v2_specialized_verifier_rejects_tampered_output(tmp_path: Path) -> None:
    replay = _authenticated_replay()
    output_root = tmp_path / "successor-v2"
    args = _args(tmp_path, output_root=output_root, replay=replay)
    assert successor_v2_cli.run(args) == 0
    output_root.joinpath("target-cohort-selection.jsonl").write_bytes(b"{}\n")

    with pytest.raises(
        successor_v2_cli.Exact100SuccessorReplacementV2CliError,
        match="completed v2 successor differs from authenticated replay",
    ):
        successor_v2_cli.verify_exact100_successor_replacement_v2_projection(
            output_root,
            replay=replay,
            args=args,
        )


def test_v2_writer_cannot_be_redirected_by_output_root_swap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_root = tmp_path / "successor-v2"
    detached_root = tmp_path / "detached-successor-v2"
    external_root = tmp_path / "external-target"
    external_root.mkdir()
    args = _args(
        tmp_path,
        output_root=output_root,
        replay=_authenticated_replay(),
    )
    original = successor_v2_cli._write_immutable_at
    swapped = False

    def write_then_swap(
        root_fd: int, relative: Path, payload: bytes, *, resume: bool
    ) -> None:
        nonlocal swapped
        original(root_fd, relative, payload, resume=resume)
        if not swapped:
            output_root.rename(detached_root)
            output_root.symlink_to(external_root, target_is_directory=True)
            swapped = True

    monkeypatch.setattr(successor_v2_cli, "_write_immutable_at", write_then_swap)

    with pytest.raises(
        successor_v2_cli.Exact100SuccessorReplacementV2CliError,
        match="output root",
    ):
        successor_v2_cli.run(args)

    assert swapped is True
    assert not any(external_root.iterdir())
    assert detached_root.joinpath("target-cohort-selection.jsonl").is_file()


def test_v2_writer_rejects_regular_output_root_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_root = tmp_path / "successor-v2"
    detached_root = tmp_path / "detached-successor-v2"
    args = _args(
        tmp_path,
        output_root=output_root,
        replay=_authenticated_replay(),
    )
    original = successor_v2_cli._write_immutable_at
    swapped = False

    def write_then_swap(
        root_fd: int, relative: Path, payload: bytes, *, resume: bool
    ) -> None:
        nonlocal swapped
        original(root_fd, relative, payload, resume=resume)
        if not swapped:
            output_root.rename(detached_root)
            output_root.mkdir()
            swapped = True

    monkeypatch.setattr(successor_v2_cli, "_write_immutable_at", write_then_swap)

    with pytest.raises(
        successor_v2_cli.Exact100SuccessorReplacementV2CliError,
        match="output root changed during publication",
    ):
        successor_v2_cli.run(args)

    assert swapped is True
    assert not any(output_root.iterdir())
    assert detached_root.joinpath("target-cohort-selection.jsonl").is_file()


def test_v2_verifier_rejects_symlinked_target_root(tmp_path: Path) -> None:
    replay = _authenticated_replay()
    real_root = tmp_path / "real-successor-v2"
    args = _args(tmp_path, output_root=real_root, replay=replay)
    assert successor_v2_cli.run(args) == 0
    linked_root = tmp_path / "linked-successor-v2"
    linked_root.symlink_to(real_root, target_is_directory=True)

    with pytest.raises(
        successor_v2_cli.Exact100SuccessorReplacementV2CliError,
        match="symlink in trusted root path",
    ):
        successor_v2_cli.verify_exact100_successor_replacement_v2_projection(
            linked_root,
            replay=replay,
            args=args,
        )


def test_v2_resume_and_verifier_reject_hardlinked_output(tmp_path: Path) -> None:
    replay = _authenticated_replay()
    output_root = tmp_path / "successor-v2"
    args = _args(tmp_path, output_root=output_root, replay=replay)
    assert successor_v2_cli.run(args) == 0
    selection = output_root / "target-cohort-selection.jsonl"
    os.link(selection, tmp_path / "selection-hardlink.jsonl")

    with pytest.raises(
        successor_v2_cli.Exact100SuccessorReplacementV2CliError,
        match="singly linked file",
    ):
        successor_v2_cli.run(args)
    with pytest.raises(
        successor_v2_cli.Exact100SuccessorReplacementV2CliError,
        match="must not be hardlinked",
    ):
        successor_v2_cli.verify_exact100_successor_replacement_v2_projection(
            output_root,
            replay=replay,
            args=args,
        )


def test_v2_resume_rejects_fifo_without_blocking(tmp_path: Path) -> None:
    replay = _authenticated_replay()
    output_root = tmp_path / "successor-v2"
    args = _args(tmp_path, output_root=output_root, replay=replay)
    assert successor_v2_cli.run(args) == 0
    selection = output_root / "target-cohort-selection.jsonl"
    selection.unlink()
    os.mkfifo(selection)

    with pytest.raises(
        successor_v2_cli.Exact100SuccessorReplacementV2CliError,
        match="regular non-symlink file",
    ):
        successor_v2_cli.verify_exact100_successor_replacement_v2_projection(
            output_root,
            replay=replay,
            args=args,
        )
    with pytest.raises(
        successor_v2_cli.Exact100SuccessorReplacementV2CliError,
        match="contains a non-regular path",
    ):
        successor_v2_cli.run(args)
