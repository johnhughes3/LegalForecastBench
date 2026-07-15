from __future__ import annotations

import json
import os
import socket
from pathlib import Path

import legalforecast.cli as cli
import legalforecast.ingestion.case_dev_purchase as purchase_module
import pytest
from legalforecast.cli import main
from legalforecast.ingestion.case_dev_purchase import (
    CaseDevPurchaseJournal,
    CaseDevPurchaseLedgerBusyError,
    CaseDevPurchaseLedgerError,
    initialize_case_dev_purchase_journal,
    verify_case_dev_purchase_journal_initialization,
    verify_case_dev_purchase_policy,
)


def test_init_purchase_ledger_help_describes_nonprovider_command(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit, match="0"):
        main(["acquisition", "init-purchase-ledger", "--help"])

    output = capsys.readouterr().out
    assert "--purchase-policy" in output
    assert "--cohort-policy" in output
    assert "--purchase-ledger" in output
    assert "--initialization-receipt-output" in output
    assert "no provider" in output.casefold()


def test_init_purchase_ledger_creates_and_authenticates_pristine_ledger(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_network(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise AssertionError("init-purchase-ledger must not access the network")

    monkeypatch.setattr(socket, "create_connection", forbidden_network)
    output_root, policy_path, cohort_path, ledger_path = _inputs(tmp_path)
    args = _args(output_root, policy_path, cohort_path, ledger_path)

    assert main(args) == 0
    receipt_path = output_root / "purchase-ledger-initialization.json"
    receipt = _read_json(receipt_path)
    assert receipt["schema_version"] == (
        "legalforecast.purchase_ledger_initialization.v1"
    )
    assert receipt["canonical_ledger_path"] == str(ledger_path)
    assert receipt["ledger_byte_count"] == ledger_path.stat().st_size
    assert len(str(receipt["ledger_file_sha256"])) == 64
    assert len(str(receipt["purchase_state_sha256"])) == 64
    assert receipt["paid_activity_requested"] is False
    assert receipt["paid_activity_executed"] is False

    policy = verify_case_dev_purchase_policy(_read_json(policy_path))
    with CaseDevPurchaseJournal(ledger_path, policy=policy) as journal:
        assert journal.statuses() == {}
        assert journal.purchase_state_sha256() == receipt["purchase_state_sha256"]

    run_card = _read_json(output_root / "run-cards/init-purchase-ledger.json")
    assert run_card["status"] == "completed"
    assert run_card["record_count"] == 1
    assert run_card["paid_activity_requested"] is False
    assert run_card["paid_activity_executed"] is False


def test_init_purchase_ledger_completed_resume_is_read_only(tmp_path: Path) -> None:
    output_root, policy_path, cohort_path, ledger_path = _inputs(tmp_path)
    args = _args(output_root, policy_path, cohort_path, ledger_path)
    assert main(args) == 0
    receipt_path = output_root / "purchase-ledger-initialization.json"
    ledger_before = ledger_path.read_bytes()
    receipt_before = receipt_path.read_bytes()

    assert main(args) == 0

    assert ledger_path.read_bytes() == ledger_before
    assert receipt_path.read_bytes() == receipt_before


@pytest.mark.parametrize("alias_kind", ["receipt", "parent"])
def test_initialize_purchase_ledger_rejects_symlinked_receipt_namespace_before_creation(
    tmp_path: Path,
    alias_kind: str,
) -> None:
    _, policy_path, _, ledger_path = _inputs(tmp_path)
    policy = verify_case_dev_purchase_policy(_read_json(policy_path))
    target_root = tmp_path / "receipt-target"
    target_root.mkdir()
    if alias_kind == "receipt":
        target = target_root / "existing-receipt.json"
        target.write_bytes(b"preserve")
        receipt_path = tmp_path / "receipt-link.json"
        receipt_path.symlink_to(target)
    else:
        receipt_parent = tmp_path / "receipt-parent-link"
        receipt_parent.symlink_to(target_root, target_is_directory=True)
        receipt_path = receipt_parent / "initialization.json"

    with pytest.raises(CaseDevPurchaseLedgerError, match="symlink"):
        initialize_case_dev_purchase_journal(
            ledger_path,
            policy=policy,
            receipt_path=receipt_path,
            purchase_policy_file_sha256="sha256:" + "a" * 64,
            cohort_policy_file_sha256="sha256:" + "b" * 64,
            initialized_at="2026-07-15T00:00:00Z",
        )

    assert not ledger_path.exists()
    if alias_kind == "receipt":
        assert target.read_bytes() == b"preserve"
    else:
        assert not (target_root / "initialization.json").exists()


@pytest.mark.parametrize("alias_kind", ["receipt", "parent"])
def test_verify_purchase_ledger_rejects_symlinked_receipt_namespace(
    tmp_path: Path,
    alias_kind: str,
) -> None:
    output_root, policy_path, cohort_path, ledger_path = _inputs(tmp_path)
    assert main(_args(output_root, policy_path, cohort_path, ledger_path)) == 0
    policy = verify_case_dev_purchase_policy(_read_json(policy_path))
    canonical_receipt = output_root / "purchase-ledger-initialization.json"
    canonical_record = _read_json(canonical_receipt)
    ledger_before = ledger_path.read_bytes()
    if alias_kind == "receipt":
        receipt_path = tmp_path / "receipt-link.json"
        receipt_path.symlink_to(canonical_receipt)
    else:
        receipt_parent = tmp_path / "receipt-parent-link"
        receipt_parent.symlink_to(output_root, target_is_directory=True)
        receipt_path = receipt_parent / canonical_receipt.name

    with pytest.raises(CaseDevPurchaseLedgerError, match="symlink"):
        verify_case_dev_purchase_journal_initialization(
            ledger_path,
            policy=policy,
            receipt_path=receipt_path,
            purchase_policy_file_sha256=str(
                canonical_record["purchase_policy_file_sha256"]
            ),
            cohort_policy_file_sha256=str(
                canonical_record["cohort_policy_file_sha256"]
            ),
        )

    assert ledger_path.read_bytes() == ledger_before


def test_init_purchase_ledger_dry_run_does_not_create_ledger(tmp_path: Path) -> None:
    output_root, policy_path, cohort_path, ledger_path = _inputs(tmp_path)
    args = _args(output_root, policy_path, cohort_path, ledger_path)
    args.remove("--execute")

    assert main(args) == 0

    assert not ledger_path.exists()
    assert not (output_root / "purchase-ledger-initialization.json").exists()
    run_card = _read_json(output_root / "run-cards/init-purchase-ledger.json")
    assert run_card["dry_run"] is True
    assert run_card["initialized_or_verified"] is False


@pytest.mark.parametrize("existing_kind", ["empty", "truncated", "directory"])
def test_init_purchase_ledger_refuses_unreceipted_existing_path(
    tmp_path: Path,
    existing_kind: str,
) -> None:
    output_root, policy_path, cohort_path, ledger_path = _inputs(tmp_path)
    ledger_path.parent.mkdir(parents=True)
    if existing_kind == "empty":
        ledger_path.touch()
    elif existing_kind == "truncated":
        ledger_path.write_bytes(b"not sqlite")
    else:
        ledger_path.mkdir()
    original = ledger_path.read_bytes() if ledger_path.is_file() else None

    assert main(_args(output_root, policy_path, cohort_path, ledger_path)) == 2

    if original is not None:
        assert ledger_path.read_bytes() == original


def test_init_purchase_ledger_refuses_symlink_and_hard_link_paths(
    tmp_path: Path,
) -> None:
    for kind in ("symlink", "hardlink"):
        root = tmp_path / kind
        output_root, policy_path, cohort_path, ledger_path = _inputs(root)
        ledger_path.parent.mkdir(parents=True)
        target = root / "target.sqlite3"
        target.write_bytes(b"do not touch")
        if kind == "symlink":
            ledger_path.symlink_to(target)
        else:
            os.link(target, ledger_path)

        assert main(_args(output_root, policy_path, cohort_path, ledger_path)) == 2
        assert target.read_bytes() == b"do not touch"


def test_init_purchase_ledger_refuses_noncanonical_cli_path(tmp_path: Path) -> None:
    output_root, policy_path, cohort_path, ledger_path = _inputs(tmp_path)
    other = (tmp_path / "other.sqlite3").resolve()

    assert main(_args(output_root, policy_path, cohort_path, other)) == 2
    assert not other.exists()
    assert not ledger_path.exists()


def test_init_purchase_ledger_refuses_existing_ledger_without_receipt(
    tmp_path: Path,
) -> None:
    output_root, policy_path, cohort_path, ledger_path = _inputs(tmp_path)
    policy = verify_case_dev_purchase_policy(_read_json(policy_path))
    with CaseDevPurchaseJournal(ledger_path, policy=policy, allow_create=True):
        pass
    before = ledger_path.read_bytes()

    assert main(_args(output_root, policy_path, cohort_path, ledger_path)) == 2
    assert ledger_path.read_bytes() == before


def test_init_purchase_ledger_no_resume_refuses_authenticated_existing_ledger(
    tmp_path: Path,
) -> None:
    output_root, policy_path, cohort_path, ledger_path = _inputs(tmp_path)
    args = _args(output_root, policy_path, cohort_path, ledger_path)
    assert main(args) == 0
    args.append("--no-resume")

    assert main(args) == 2


def test_init_purchase_ledger_resume_rejects_tampered_receipt(tmp_path: Path) -> None:
    output_root, policy_path, cohort_path, ledger_path = _inputs(tmp_path)
    args = _args(output_root, policy_path, cohort_path, ledger_path)
    assert main(args) == 0
    receipt_path = output_root / "purchase-ledger-initialization.json"
    receipt = _read_json(receipt_path)
    receipt["ledger_file_sha256"] = "0" * 64
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    ledger_before = ledger_path.read_bytes()

    assert main(args) == 2
    assert ledger_path.read_bytes() == ledger_before
    assert _read_json(receipt_path)["ledger_file_sha256"] == "0" * 64


@pytest.mark.parametrize("surface", ["receipt", "run_card", "log"])
def test_init_purchase_ledger_refuses_hardlinked_writable_surfaces_without_touching(
    tmp_path: Path,
    surface: str,
) -> None:
    output_root, policy_path, cohort_path, ledger_path = _inputs(tmp_path)
    target = tmp_path / f"{surface}-target"
    target.write_bytes(b"preserve")
    paths = {
        "receipt": output_root / "purchase-ledger-initialization.json",
        "run_card": output_root / "run-cards/init-purchase-ledger.json",
        "log": output_root / "logs/init-purchase-ledger.jsonl",
    }
    path = paths[surface]
    path.parent.mkdir(parents=True, exist_ok=True)
    os.link(target, path)

    assert main(_args(output_root, policy_path, cohort_path, ledger_path)) == 2
    assert target.read_bytes() == b"preserve"
    assert not ledger_path.exists()


@pytest.mark.parametrize(
    ("flag", "reserved_suffix"),
    [
        ("--initialization-receipt-output", ".lock"),
        ("--initialization-receipt-output", "-wal"),
        ("--initialization-receipt-output", "-shm"),
        ("--initialization-receipt-output", "-journal"),
        ("--run-card-output", ".lock"),
        ("--log-output", ".lock"),
    ],
)
def test_init_purchase_ledger_rejects_reserved_sqlite_and_lock_namespaces(
    tmp_path: Path,
    flag: str,
    reserved_suffix: str,
) -> None:
    output_root, policy_path, cohort_path, ledger_path = _inputs(tmp_path)
    args = _args(output_root, policy_path, cohort_path, ledger_path)
    args.extend([flag, f"{ledger_path}{reserved_suffix}"])

    assert main(args) == 2
    assert not ledger_path.exists()
    assert not Path(f"{ledger_path}{reserved_suffix}").exists()


@pytest.mark.parametrize("suffix", ["-wal", "-shm", "-journal"])
def test_init_purchase_ledger_preserves_preexisting_sidecar_and_refuses_creation(
    tmp_path: Path,
    suffix: str,
) -> None:
    output_root, policy_path, cohort_path, ledger_path = _inputs(tmp_path)
    ledger_path.parent.mkdir(parents=True)
    sidecar = Path(f"{ledger_path}{suffix}")
    sidecar.write_bytes(b"preserve")

    assert main(_args(output_root, policy_path, cohort_path, ledger_path)) == 2
    assert sidecar.read_bytes() == b"preserve"
    assert not ledger_path.exists()


def test_init_purchase_ledger_refuses_broken_sidecar_symlink(tmp_path: Path) -> None:
    output_root, policy_path, cohort_path, ledger_path = _inputs(tmp_path)
    ledger_path.parent.mkdir(parents=True)
    sidecar = Path(f"{ledger_path}-wal")
    sidecar.symlink_to(tmp_path / "missing-target")

    assert main(_args(output_root, policy_path, cohort_path, ledger_path)) == 2
    assert sidecar.is_symlink()
    assert not ledger_path.exists()


def test_init_purchase_ledger_rejects_output_root_or_receipt_below_ledger(
    tmp_path: Path,
) -> None:
    output_root, policy_path, cohort_path, ledger_path = _inputs(tmp_path)
    args = _args(ledger_path, policy_path, cohort_path, ledger_path)
    assert main(args) == 2
    assert not ledger_path.exists()

    args = _args(output_root, policy_path, cohort_path, ledger_path)
    args.extend(["--initialization-receipt-output", str(ledger_path / "receipt.json")])
    assert main(args) == 2
    assert not ledger_path.exists()


def test_init_purchase_ledger_rejects_output_root_below_ledger_with_safe_overrides(
    tmp_path: Path,
) -> None:
    _, policy_path, cohort_path, ledger_path = _inputs(tmp_path)
    output_root = ledger_path / "output"
    safe_root = tmp_path / "safe-outputs"
    receipt_path = safe_root / "purchase-ledger-initialization.json"
    run_card_path = safe_root / "init-purchase-ledger.json"
    log_path = safe_root / "init-purchase-ledger.jsonl"
    args = _args(output_root, policy_path, cohort_path, ledger_path)
    args.extend(
        [
            "--initialization-receipt-output",
            str(receipt_path),
            "--run-card-output",
            str(run_card_path),
            "--log-output",
            str(log_path),
        ]
    )

    assert main(args) == 2
    assert not ledger_path.exists()
    assert not receipt_path.exists()
    assert not run_card_path.exists()
    assert not log_path.exists()


def test_init_purchase_ledger_accepts_safe_output_root_ancestor(
    tmp_path: Path,
) -> None:
    _, policy_path, cohort_path, ledger_path = _inputs(tmp_path)

    assert main(_args(tmp_path, policy_path, cohort_path, ledger_path)) == 0

    assert ledger_path.is_file()
    assert (tmp_path / "purchase-ledger-initialization.json").is_file()


def test_init_purchase_ledger_holds_lock_through_receipt_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root, policy_path, cohort_path, ledger_path = _inputs(tmp_path)
    policy = verify_case_dev_purchase_policy(_read_json(policy_path))
    original = purchase_module._write_immutable_purchase_ledger_receipt
    lock_was_held = False

    def asserting_writer(path: Path, record: dict[str, object]) -> None:
        nonlocal lock_was_held
        with pytest.raises(CaseDevPurchaseLedgerBusyError):
            CaseDevPurchaseJournal(ledger_path, policy=policy)
        lock_was_held = True
        original(path, record)

    monkeypatch.setattr(
        purchase_module,
        "_write_immutable_purchase_ledger_receipt",
        asserting_writer,
    )
    assert main(_args(output_root, policy_path, cohort_path, ledger_path)) == 0
    assert lock_was_held


@pytest.mark.parametrize("alias_kind", ["symlink", "hardlink"])
def test_runtime_journal_rejects_replaced_canonical_lock(
    tmp_path: Path,
    alias_kind: str,
) -> None:
    output_root, policy_path, cohort_path, ledger_path = _inputs(tmp_path)
    assert main(_args(output_root, policy_path, cohort_path, ledger_path)) == 0
    policy = verify_case_dev_purchase_policy(_read_json(policy_path))
    lock_path = Path(f"{ledger_path}.lock")
    lock_path.unlink()
    target = tmp_path / f"{alias_kind}-lock-target"
    target.write_bytes(b"preserve")
    if alias_kind == "symlink":
        lock_path.symlink_to(target)
    else:
        os.link(target, lock_path)

    with pytest.raises(CaseDevPurchaseLedgerError):
        CaseDevPurchaseJournal(ledger_path, policy=policy)

    assert target.read_bytes() == b"preserve"


def test_runtime_journal_rejects_lock_path_inode_replaced_during_flock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root, policy_path, cohort_path, ledger_path = _inputs(tmp_path)
    assert main(_args(output_root, policy_path, cohort_path, ledger_path)) == 0
    policy = verify_case_dev_purchase_policy(_read_json(policy_path))
    lock_path = Path(f"{ledger_path}.lock")
    original_flock = purchase_module.fcntl.flock
    replaced = False

    def replacing_flock(fd: int, operation: int) -> None:
        nonlocal replaced
        if operation & purchase_module.fcntl.LOCK_EX and not replaced:
            replaced = True
            replacement = lock_path.with_name("replacement-lock")
            replacement.write_bytes(b"")
            os.replace(replacement, lock_path)
        original_flock(fd, operation)

    monkeypatch.setattr(purchase_module.fcntl, "flock", replacing_flock)

    with pytest.raises(CaseDevPurchaseLedgerError, match="lock path changed"):
        CaseDevPurchaseJournal(ledger_path, policy=policy)

    assert replaced
    with CaseDevPurchaseJournal(ledger_path, policy=policy):
        pass


def test_init_purchase_ledger_create_rejects_receipt_replaced_after_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root, policy_path, cohort_path, ledger_path = _inputs(tmp_path)
    args = _args(output_root, policy_path, cohort_path, ledger_path)
    receipt_path = output_root / "purchase-ledger-initialization.json"
    original_reader = purchase_module._read_purchase_ledger_initialization_receipt
    replaced = False

    def replacing_reader(path: Path) -> dict[str, object]:
        nonlocal replaced
        record = original_reader(path)
        if not replaced:
            replaced = True
            tampered = {**record, "ledger_file_sha256": "0" * 64}
            replacement = path.with_name("replacement-receipt.json")
            replacement.write_text(json.dumps(tampered), encoding="utf-8")
            os.replace(replacement, path)
        return record

    monkeypatch.setattr(
        purchase_module,
        "_read_purchase_ledger_initialization_receipt",
        replacing_reader,
    )

    assert main(args) == 2
    assert replaced
    assert ledger_path.is_file()
    assert _read_json(receipt_path)["ledger_file_sha256"] == "0" * 64


def test_init_purchase_ledger_resume_rejects_receipt_replaced_after_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root, policy_path, cohort_path, ledger_path = _inputs(tmp_path)
    args = _args(output_root, policy_path, cohort_path, ledger_path)
    assert main(args) == 0
    receipt_path = output_root / "purchase-ledger-initialization.json"
    ledger_before = ledger_path.read_bytes()
    original_reader = purchase_module._read_purchase_ledger_initialization_receipt

    def replacing_reader(path: Path) -> dict[str, object]:
        record = original_reader(path)
        tampered = {**record, "ledger_file_sha256": "0" * 64}
        replacement = path.with_name("replacement-receipt.json")
        replacement.write_text(json.dumps(tampered), encoding="utf-8")
        os.replace(replacement, path)
        return record

    monkeypatch.setattr(
        purchase_module,
        "_read_purchase_ledger_initialization_receipt",
        replacing_reader,
    )

    assert main(args) == 2
    assert ledger_path.read_bytes() == ledger_before
    assert _read_json(receipt_path)["ledger_file_sha256"] == "0" * 64


def test_init_purchase_ledger_resume_rejects_receipt_replaced_during_final_ledger_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root, policy_path, cohort_path, ledger_path = _inputs(tmp_path)
    args = _args(output_root, policy_path, cohort_path, ledger_path)
    assert main(args) == 0
    receipt_path = output_root / "purchase-ledger-initialization.json"
    ledger_before = ledger_path.read_bytes()
    original_identity = purchase_module._purchase_ledger_initialization_identity
    identity_calls = 0

    def replacing_during_final_identity(
        path: Path,
        *,
        policy: purchase_module.CaseDevPurchasePolicy,
        require_pristine: bool,
    ) -> purchase_module.PurchaseLedgerInitialization:
        nonlocal identity_calls
        identity_calls += 1
        identity = original_identity(
            path,
            policy=policy,
            require_pristine=require_pristine,
        )
        if identity_calls == 2:
            tampered = {
                **_read_json(receipt_path),
                "ledger_file_sha256": "0" * 64,
            }
            replacement = receipt_path.with_name("replacement-receipt.json")
            replacement.write_text(json.dumps(tampered), encoding="utf-8")
            os.replace(replacement, receipt_path)
        return identity

    monkeypatch.setattr(
        purchase_module,
        "_purchase_ledger_initialization_identity",
        replacing_during_final_identity,
    )

    assert main(args) == 2
    assert identity_calls == 2
    assert ledger_path.read_bytes() == ledger_before
    assert _read_json(receipt_path)["ledger_file_sha256"] == "0" * 64


def test_runtime_journal_refuses_implicit_initialization(tmp_path: Path) -> None:
    _, policy_path, _, ledger_path = _inputs(tmp_path)
    policy = verify_case_dev_purchase_policy(_read_json(policy_path))

    with pytest.raises(CaseDevPurchaseLedgerError, match="init-purchase-ledger"):
        CaseDevPurchaseJournal(ledger_path, policy=policy)

    assert not ledger_path.exists()
    assert not Path(f"{ledger_path}.lock").exists()


def _inputs(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    output_root = tmp_path / "output"
    ledger_path = (tmp_path / "ledger/cycle-purchases.sqlite3").resolve()
    cohort_decisions = cli._fixture_cohort_policy_decisions()
    cohort_decisions["purchase_policy"] = {
        "rule": "buy_cheapest_complete",
        "cycle_budget_usd": "9.15",
        "max_per_case_usd": "9.15",
        "reservation_headroom_required": True,
    }
    cohort = cli.generate_cohort_policy(cohort_decisions)
    cohort_path = tmp_path / "cohort-policy.json"
    cohort_path.parent.mkdir(parents=True, exist_ok=True)
    cohort_path.write_text(json.dumps(cohort), encoding="utf-8")
    decisions = {
        "cycle_id": "cycle-1",
        "cohort_policy_sha256": cohort["policy_sha256"],
        "canonical_ledger_path": str(ledger_path),
        "hard_cap_usd": "9.15",
        "opening_committed_spend_usd": "0.00",
        "opening_case_committed_spend_usd": {},
        "max_per_case_usd": "9.15",
        "per_document_reservation_usd": "3.05",
        "fee_schedule": {
            "includes_pacer_fees": True,
            "includes_service_fees": True,
            "includes_rounding": True,
            "source_citation": "fixture fee schedule",
            "verified_at_utc": "2026-07-14T00:00:00Z",
        },
    }
    policy = cli.generate_case_dev_purchase_policy(decisions)
    policy_path = tmp_path / "purchase-policy.json"
    policy_path.write_text(json.dumps(policy), encoding="utf-8")
    return output_root, policy_path, cohort_path, ledger_path


def _args(
    output_root: Path,
    policy_path: Path,
    cohort_path: Path,
    ledger_path: Path,
) -> list[str]:
    return [
        "acquisition",
        "init-purchase-ledger",
        "--output-root",
        str(output_root),
        "--purchase-policy",
        str(policy_path),
        "--cohort-policy",
        str(cohort_path),
        "--purchase-ledger",
        str(ledger_path),
        "--execute",
    ]


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value
