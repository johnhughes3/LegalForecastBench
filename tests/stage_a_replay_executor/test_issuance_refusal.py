"""A refused preflight must leave nothing behind that anyone could sign.

The hazard these tests close was found by driving the real issuer to a truthful
stop: its preflight refused at the lineage stage, and it still wrote a clean,
paste-ready ``approval-block.txt`` with no trace of the refusal, while
``issuance-evidence.json`` carried no preflight result at all.  The refusal
survived only on stdout.  Anyone who later found that output directory would
have seen an approval block indistinguishable from a good one and could have
signed it -- binding an owner authorization to a descriptor whose execution
rehearsal had refused, which is precisely the harm ``--skip-preflight`` exists
to make deliberate.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import cast

import pytest
from legalforecast.cli_commands.stage_a_replay import (
    register_issuance as register_issuance_cli,
)
from legalforecast.ingestion.stage_a_replay_executor import (
    issuance as issuance_module,
)
from legalforecast.ingestion.stage_a_replay_executor.contract import (
    StageAReplayExecutorError,
)
from legalforecast.ingestion.stage_a_replay_executor.issuance import (
    ACCEPTED,
    APPROVAL_BLOCK_FILENAME,
    REFUSED,
    SKIPPED,
    issue_replay_descriptor,
    write_replay_descriptor_draft,
)
from legalforecast.ingestion.stage_a_replay_executor.issuance_request import (
    load_issuance_request,
)
from tests.stage_a_replay_executor.issuance_fixtures import (
    build_issuance_inputs,
    read_json,
)

FIXTURE_COMMIT = "0" * 40


def test_a_refused_preflight_writes_no_approval_block(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """No signable instrument reaches disk, and the refusal is recorded."""

    output_dir = _issue_refused(tmp_path, monkeypatch)
    record = json.loads(capsys.readouterr().out)

    preflight = record["preflight"]
    assert preflight["status"] == REFUSED
    assert preflight["stage"] == "lineage"
    assert "lineage" in str(preflight["reason"]).lower()

    assert not (output_dir / APPROVAL_BLOCK_FILENAME).exists()
    assert record["approval_block_withheld"] is True
    # Withheld from the operator record too: a captured stdout log is another
    # place a paste-ready approval can be found and reused.
    assert "approval_text" not in record

    evidence = read_json(output_dir / "issuance-evidence.json")
    assert evidence["preflight"] == preflight
    assert evidence["approval_block_written"] is False
    # The descriptor still lands.  It is inert without an approval, the
    # executor re-authenticates it from bytes, and the recorded refusal names
    # it.
    assert (output_dir / "replay-descriptor.json").exists()


def test_a_refusal_deletes_an_approval_block_an_earlier_run_left(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Re-issuing into a directory that already holds a block clears it.

    Issuing repeatedly into one output directory is the ordinary operator loop.
    Withholding only the new block would leave a previous run's clean one
    sitting beside a refusal -- the same trap by a slower route.
    """

    output_dir = tmp_path / "issued"
    output_dir.mkdir(parents=True)
    stale = output_dir / APPROVAL_BLOCK_FILENAME
    stale.write_text(
        "I approve candidate-scoped Stage A replay bound to replay descriptor "
        "SHA-256 " + "b" * 64 + ": estimated cost USD 6.00 ...\n",
        encoding="utf-8",
    )

    _issue_refused(tmp_path, monkeypatch)
    capsys.readouterr()

    assert not stale.exists()


def test_a_skipped_preflight_is_recorded_and_still_emits_the_block(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--skip-preflight`` is a deliberate operator bypass, not a refusal.

    Conflating the two would either withhold the block from the one flow whose
    whole purpose is issuing against deliberately absent artifacts, or leave
    the evidence silent about which of the two happened.
    """

    monkeypatch.setattr(
        issuance_module, "current_code_commit", lambda **_kwargs: FIXTURE_COMMIT
    )
    parser = argparse.ArgumentParser()
    register_issuance_cli(parser.add_subparsers(dest="command"))
    output_dir = tmp_path / "issued"
    issued = parser.parse_args(
        [
            "issue-replay-spec",
            "--issuance-request",
            str(build_issuance_inputs(tmp_path)),
            "--output-dir",
            str(output_dir),
            "--skip-preflight",
        ]
    )

    assert issued.handler(issued) == 0

    record = json.loads(capsys.readouterr().out)
    assert record["preflight"] == {"status": SKIPPED}
    assert record["approval_block_path"] == str(output_dir / APPROVAL_BLOCK_FILENAME)
    block = (output_dir / APPROVAL_BLOCK_FILENAME).read_text(encoding="utf-8")
    assert block.strip() == record["approval_text"]

    evidence = read_json(output_dir / "issuance-evidence.json")
    assert evidence["preflight"] == {"status": SKIPPED}
    assert evidence["approval_block_written"] is True


def test_the_draft_writer_requires_the_preflight_outcome_it_gates_on(
    tmp_path: Path,
) -> None:
    """The gating argument is required so no caller can re-open the hazard."""

    request = load_issuance_request(build_issuance_inputs(tmp_path))
    draft = issue_replay_descriptor(request, code_commit=FIXTURE_COMMIT)

    with pytest.raises(TypeError):
        write_replay_descriptor_draft(draft, tmp_path / "issued")  # type: ignore[call-arg]


def test_an_interrupted_write_can_never_leave_a_stale_block(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every interruption window fails closed, not just the happy path.

    A descriptor is deterministic in the fields that fix its hash, so re-issuing
    the same request reproduces the same ``descriptor_sha256``.  If the block
    were cleared *after* the descriptor were rewritten, a crash in between would
    leave a previous run's block still validly bound to the descriptor beside
    it -- the exact hazard this module exists to close, reopened by a SIGKILL.
    Clearing first means the worst outcome is a missing block.
    """

    request = load_issuance_request(build_issuance_inputs(tmp_path))
    draft = issue_replay_descriptor(request, code_commit=FIXTURE_COMMIT)
    output_dir = tmp_path / "issued"
    output_dir.mkdir(parents=True)
    stale = output_dir / APPROVAL_BLOCK_FILENAME
    stale.write_text("previous run's block, same descriptor hash\n", encoding="utf-8")

    class _Interrupted(BaseException):
        """Stands in for a signal: not caught by ordinary error handling."""

    def _die(*_args: object, **_kwargs: object) -> None:
        raise _Interrupted

    descriptor_path = output_dir / "replay-descriptor.json"
    # Fail on the very first byte-write of the run, which is the descriptor.
    monkeypatch.setattr(Path, "write_bytes", _die)
    with pytest.raises(_Interrupted):
        write_replay_descriptor_draft(draft, output_dir, preflight={"status": REFUSED})

    assert not stale.exists()
    assert not descriptor_path.exists()


def test_the_evidence_lands_before_the_block_it_describes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An accepted run records the evidence first, then emits the instrument.

    Writing the block first would let a failed evidence write leave a signable
    instrument with no durable record of the run that produced it.
    """

    request = load_issuance_request(build_issuance_inputs(tmp_path))
    draft = issue_replay_descriptor(request, code_commit=FIXTURE_COMMIT)
    output_dir = tmp_path / "issued"
    original = Path.write_text

    def _fail_on_block(self: Path, *args: object, **kwargs: object) -> int:
        if self.name == APPROVAL_BLOCK_FILENAME:
            raise OSError("disk full")
        return cast(int, original(self, *args, **kwargs))  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "write_text", _fail_on_block)
    with pytest.raises(OSError):
        write_replay_descriptor_draft(draft, output_dir, preflight={"status": ACCEPTED})
    monkeypatch.undo()

    assert not (output_dir / APPROVAL_BLOCK_FILENAME).exists()
    evidence = read_json(output_dir / "issuance-evidence.json")
    assert evidence["replay_descriptor_sha256"] == draft.descriptor_sha256


def test_a_refusal_then_an_acceptance_in_one_directory_recovers(
    tmp_path: Path,
) -> None:
    """The withheld block reappears once a rehearsal accepts, evidence with it."""

    request = load_issuance_request(build_issuance_inputs(tmp_path))
    draft = issue_replay_descriptor(request, code_commit=FIXTURE_COMMIT)
    output_dir = tmp_path / "issued"

    write_replay_descriptor_draft(draft, output_dir, preflight={"status": REFUSED})
    assert not (output_dir / APPROVAL_BLOCK_FILENAME).exists()
    assert (
        read_json(output_dir / "issuance-evidence.json")["approval_block_written"]
        is False
    )

    write_replay_descriptor_draft(draft, output_dir, preflight={"status": ACCEPTED})
    block = (output_dir / APPROVAL_BLOCK_FILENAME).read_text(encoding="utf-8")
    assert block.strip() == draft.approval_text
    assert (
        read_json(output_dir / "issuance-evidence.json")["approval_block_written"]
        is True
    )


def test_the_issuer_refuses_to_write_through_a_symlinked_approval_path(
    tmp_path: Path,
) -> None:
    """A symlink at the block path would land the instrument somewhere else."""

    request = load_issuance_request(build_issuance_inputs(tmp_path))
    draft = issue_replay_descriptor(request, code_commit=FIXTURE_COMMIT)
    output_dir = tmp_path / "issued"
    output_dir.mkdir(parents=True)
    elsewhere = tmp_path / "elsewhere.txt"
    elsewhere.write_text("untouched\n", encoding="utf-8")
    (output_dir / APPROVAL_BLOCK_FILENAME).symlink_to(elsewhere)

    with pytest.raises(StageAReplayExecutorError) as error:
        write_replay_descriptor_draft(draft, output_dir, preflight={"status": ACCEPTED})

    assert "not a regular file" in str(error.value)
    assert elsewhere.read_text(encoding="utf-8") == "untouched\n"


def _issue_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Drive the CLI to a refused lineage preflight; return its output dir.

    The fixture issuance request names lineage artifacts that do not exist, so
    the rehearsal refuses at the lineage stage without any provider access --
    the same stage the production issuer refused at.
    """

    monkeypatch.setattr(
        issuance_module, "current_code_commit", lambda **_kwargs: FIXTURE_COMMIT
    )
    parser = argparse.ArgumentParser()
    register_issuance_cli(parser.add_subparsers(dest="command"))
    output_dir = tmp_path / "issued"
    issued = parser.parse_args(
        [
            "issue-replay-spec",
            "--issuance-request",
            str(build_issuance_inputs(tmp_path)),
            "--output-dir",
            str(output_dir),
        ]
    )

    assert issued.handler(issued) == 2
    return output_dir
