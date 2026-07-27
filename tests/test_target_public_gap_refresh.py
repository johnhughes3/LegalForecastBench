from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any, Never, cast

import pytest
from legalforecast import cli
from legalforecast.ingestion import target_public_gap_refresh as target_gap_module
from legalforecast.ingestion.budgeted_firecrawl import (
    BudgetedFirecrawlRunResult,
    FirecrawlPageRecord,
    FirecrawlTargetSpec,
)
from legalforecast.ingestion.free_document_downloader import (
    FixtureFreeDocumentSource,
    FreeDocumentDownloadError,
    FreeDocumentFetch,
    download_free_docket_documents,
)
from legalforecast.ingestion.target_public_gap_refresh import (
    TargetPublicGapExecutionIdentity,
    TargetPublicGapExecutionResult,
    TargetPublicGapPlan,
    bind_target_public_gap_execution,
    download_target_public_gap_requests,
    execute_target_public_gap_refresh,
    plan_target_public_gaps,
    preflight_target_public_gap_execution,
    publish_target_public_gap_outputs,
    publish_target_public_gap_plan,
    refresh_target_public_gaps,
    require_target_public_gap_sources_unchanged,
    target_public_gap_plan_bytes,
    target_public_gap_terminal_commitments,
    verify_target_public_gap_plan,
)


def test_plan_projects_exact_179_gap_95_docket_target() -> None:
    selections: list[dict[str, object]] = []
    free_manifest: list[dict[str, object]] = []
    gap_count = 0
    for index in range(100):
        candidate_id = str(70_000_000 + index)
        gap_documents = 2 if index < 84 else 1 if index < 95 else 0
        free_documents = 2 if index < 41 else 1
        documents: list[dict[str, object]] = []
        for offset in range(gap_documents):
            gap_count += 1
            documents.append(
                _document(
                    candidate_id,
                    f"gap-{gap_count}",
                    entry_number=offset + 1,
                    role="decision",
                    available=False,
                )
            )
        for offset in range(free_documents):
            source_document_id = f"free-{index}-{offset}"
            documents.append(
                _document(
                    candidate_id,
                    source_document_id,
                    entry_number=gap_documents + offset + 1,
                    role="complaint",
                    available=True,
                )
            )
            free_manifest.append(
                {
                    "candidate_id": candidate_id,
                    "source_document_id": source_document_id,
                }
            )
        selections.append(_selection(candidate_id, documents))
    run_card_bytes = b'{"authenticated":"target-100"}\n'

    verified = _verified_projection(
        root=Path("/immutable/target-100"),
        run_card_bytes=run_card_bytes,
        selections=selections,
        free_manifest=free_manifest,
    )
    plan = plan_target_public_gaps(
        verified_projection=verified,
        target_cohort_root=Path("/immutable/target-100"),
        expected_target_run_card_sha256=hashlib.sha256(run_card_bytes).hexdigest(),
        fresh_credit_cap=500,
        workers=10,
        max_pages_per_docket=10,
        execution_identity=_execution_identity(Path("/immutable/target-100")),
    )

    assert gap_count == 179
    assert len(plan.gaps) == 179
    assert len(plan.ranked_records) == 95
    assert plan.selected_document_count == 320
    assert plan.existing_download_count == 141
    assert plan.provider_activity_requested is False
    assert plan.required_gap_document_ids == tuple(
        f"gap-{index}" for index in range(1, 180)
    )
    assert plan.required_gap_document_ids_sha256 == _semantic_sha256(
        list(plan.required_gap_document_ids)
    )
    summary = cast(dict[str, object], verified["summary"])
    assert (
        plan.selected_candidate_ids_sha256 == summary["selected_candidate_ids_sha256"]
    )
    verified_bytes = cast(dict[str, bytes], verified["verified_artifact_bytes"])
    assert (
        plan.target_selection_file_sha256
        == hashlib.sha256(
            verified_bytes[
                str(Path("/immutable/target-100/target-cohort-selection.jsonl"))
            ]
        ).hexdigest()
    )


def test_refresh_composes_existing_planner_and_free_downloader(tmp_path: Path) -> None:
    candidate_id = "70000000"
    plan = _single_case_plan(tmp_path)
    scheduler = _Scheduler({(candidate_id, 1): _public_docket_html(candidate_id)})

    assert plan.required_entry_numbers_by_docket == {candidate_id: frozenset({2, 3})}
    result = refresh_target_public_gaps(plan=plan, scheduler=scheduler)

    assert scheduler.waves == [[(candidate_id, 1)]]
    assert len(result.transitions) == 2
    assert result.gap_failures == ()
    assert {request.source_document_id for request in result.download_requests} == {
        "mtd-old",
        "decision-old",
    }
    assert all(
        transition["source_page_completeness"] == "required_entries_only"
        for transition in result.transitions
    )
    pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"
    source = FixtureFreeDocumentSource(
        {request.source_url: pdf for request in result.download_requests}
    )
    records = download_free_docket_documents(
        result.download_requests,
        output_root=tmp_path / "downloads",
        source=source,
    )
    assert len(records) == 2
    assert all(record.sha256 == hashlib.sha256(pdf).hexdigest() for record in records)
    commitments = target_public_gap_terminal_commitments(
        plan=plan,
        plan_sha256="1" * 64,
        refresh=result,
        downloads=records,
    )
    assert commitments["terminal_reconciliation"] is True
    assert commitments["plan_sha256"] == "1" * 64
    assert commitments["transition_count"] == 2
    assert commitments["exclusion_count"] == 0
    assert commitments["newly_free_document_count"] == 2
    assert commitments["purchased_document_count"] == 0
    assert commitments["purchased_activity_requested"] is False
    assert commitments["purchased_activity_executed"] is False
    assert commitments["required_gap_document_ids_sha256"] == (
        plan.required_gap_document_ids_sha256
    )


def test_plan_is_immutable_digest_bound_and_replays_source_closure(
    tmp_path: Path,
) -> None:
    root = tmp_path / "target"
    plan = _single_case_plan(root)
    for path, digest in plan.source_artifact_commitments.items():
        source = Path(path)
        source.parent.mkdir(parents=True, exist_ok=True)
        payload = next(
            value
            for value in _verified_projection_bytes(root).values()
            if hashlib.sha256(value).hexdigest() == digest
        )
        source.write_bytes(payload)
    plan_path = tmp_path / "plan.json"

    digest = publish_target_public_gap_plan(plan_path, plan)

    assert publish_target_public_gap_plan(plan_path, plan) == digest
    assert (
        verify_target_public_gap_plan(
            plan_path,
            expected_sha256=digest,
            reconstructed=plan,
        )
        == plan
    )
    changed_lineage = replace(
        plan,
        execution_identity=replace(
            plan.execution_identity,
            run_id="different-run",
        ),
    )
    with pytest.raises(ValueError, match="does not reproduce"):
        verify_target_public_gap_plan(
            plan_path,
            expected_sha256=digest,
            reconstructed=changed_lineage,
        )
    require_target_public_gap_sources_unchanged(plan)
    Path(next(iter(plan.source_artifact_commitments))).write_text("changed")
    with pytest.raises(
        ValueError,
        match="target source artifact changed",
    ):
        require_target_public_gap_sources_unchanged(plan)
    with pytest.raises(ValueError, match="plan SHA-256 mismatch"):
        verify_target_public_gap_plan(
            plan_path,
            expected_sha256="0" * 64,
            reconstructed=plan,
        )


def test_plan_serializes_provider_activity_requested() -> None:
    plan = _single_case_plan(Path("/immutable/target"))
    live_plan = replace(plan, provider_activity_requested=True)

    assert plan.to_record()["provider_activity_requested"] is False
    assert live_plan.to_record()["provider_activity_requested"] is True
    assert target_public_gap_plan_bytes(plan) != target_public_gap_plan_bytes(live_plan)


def test_execution_preflight_and_atomic_output_publication(tmp_path: Path) -> None:
    root = tmp_path / "target"
    plan = _single_case_plan(root)
    for path, payload in _verified_projection_bytes(root).items():
        source = Path(path)
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(payload)
    preflight_target_public_gap_execution(plan)
    payloads = _valid_terminal_payloads(plan, tmp_path=tmp_path)

    with bind_target_public_gap_execution(plan) as binding:
        publish_target_public_gap_outputs(
            plan=plan,
            plan_sha256="1" * 64,
            payloads=payloads,
            execution_binding=binding,
        )
        publish_target_public_gap_outputs(
            plan=plan,
            plan_sha256="1" * 64,
            payloads=payloads,
            execution_binding=binding,
        )
        binding.require_current(plan)

    for relative, payload in payloads.items():
        assert (plan.execution_identity.output_root / relative).read_bytes() == payload
    preflight_target_public_gap_execution(
        plan,
        expected_plan_sha256="1" * 64,
    )
    with pytest.raises(ValueError, match="published output differs"):
        publish_target_public_gap_outputs(
            plan=plan,
            plan_sha256="1" * 64,
            payloads={
                **payloads,
                "target-public-gap-outcomes.jsonl": b"different\n",
            },
        )


def test_public_output_helper_internally_binds_and_rejects_symlink_parent(
    tmp_path: Path,
) -> None:
    plan = _single_case_plan(tmp_path / "target")
    payloads = {"artifact.json": b"{}\n"}
    output_parent = plan.execution_identity.output_root.parent
    outside = tmp_path / "outside"
    outside.mkdir()
    output_parent.parent.mkdir(parents=True, exist_ok=True)
    output_parent.symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="output parent"):
        publish_target_public_gap_outputs(
            plan=plan,
            plan_sha256="1" * 64,
            payloads=payloads,
        )

    assert tuple(outside.iterdir()) == ()


def test_preflight_rejects_recommitted_terminal_plan_mismatch(
    tmp_path: Path,
) -> None:
    plan = _single_case_plan(tmp_path / "target")
    payloads = dict(_valid_terminal_payloads(plan, tmp_path=tmp_path))
    summary_name = "target-public-gap-execution-summary.json"
    receipt_name = "run-cards/execute-target-public-gaps.json"
    log_name = "logs/execute-target-public-gaps.jsonl"
    summary = cast(dict[str, object], json.loads(payloads[summary_name]))
    receipt = cast(dict[str, object], json.loads(payloads[receipt_name]))
    summary_terminal = cast(dict[str, object], summary["terminal_commitments"])
    receipt_terminal = cast(dict[str, object], receipt["terminal_commitments"])
    summary_terminal["plan_sha256"] = "2" * 64
    receipt_terminal["plan_sha256"] = "2" * 64
    payloads[summary_name] = _json_bytes(summary)
    receipt_outputs = cast(dict[str, object], receipt["output_commitments"])
    receipt_outputs[summary_name] = hashlib.sha256(payloads[summary_name]).hexdigest()
    payloads[receipt_name] = _json_bytes(receipt)
    payloads[log_name] = _jsonl_bytes(
        [
            {
                "schema_version": ("legalforecast.target_public_gap_execution_log.v1"),
                "event": "completed",
                "plan_sha256": "1" * 64,
                "run_card_sha256": hashlib.sha256(payloads[receipt_name]).hexdigest(),
            }
        ]
    )

    publish_target_public_gap_outputs(
        plan=plan,
        plan_sha256="1" * 64,
        payloads=payloads,
    )
    with pytest.raises(
        ValueError,
        match="terminal commitments differ from current plan",
    ):
        preflight_target_public_gap_execution(
            plan,
            expected_plan_sha256="1" * 64,
        )


def test_terminal_publication_stays_on_bound_parent_during_rebind(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _single_case_plan(tmp_path / "target")
    payloads = _valid_terminal_payloads(plan, tmp_path=tmp_path)
    runtime_parent = plan.execution_identity.output_root.parent
    moved_parent = tmp_path / "moved-terminal-parent"
    original_rename = os.rename
    rebound = False

    def rebind_before_terminal_rename(
        source: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        destination: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
    ) -> None:
        nonlocal rebound
        if not rebound and str(source).endswith(".partial"):
            rebound = True
            original_rename(runtime_parent, moved_parent)
            runtime_parent.mkdir()
        original_rename(
            source,
            destination,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
        )

    with bind_target_public_gap_execution(plan) as binding:
        monkeypatch.setattr(os, "rename", rebind_before_terminal_rename)
        with pytest.raises(ValueError, match="output parent changed"):
            publish_target_public_gap_outputs(
                plan=plan,
                plan_sha256="1" * 64,
                payloads=payloads,
                execution_binding=binding,
            )

    assert not plan.execution_identity.output_root.exists()
    assert (moved_parent / plan.execution_identity.output_root.name).is_dir()


def test_execution_binding_pins_raw_pages_child_against_symlink_rebind(
    tmp_path: Path,
) -> None:
    plan = _single_case_plan(tmp_path / "target")
    pages = plan.execution_identity.raw_html_root / "pages"
    moved_pages = tmp_path / "moved-pages"
    outside = tmp_path / "outside"
    outside.mkdir()

    with bind_target_public_gap_execution(plan) as binding:
        pages.rename(moved_pages)
        pages.symlink_to(outside, target_is_directory=True)
        (binding.raw_pages_root / "page.html").write_bytes(b"bound")
        with pytest.raises(ValueError, match="raw HTML pages changed"):
            binding.require_current(plan)

    assert (moved_pages / "page.html").read_bytes() == b"bound"
    assert tuple(outside.iterdir()) == ()


def test_terminal_publication_pins_nested_directory_against_symlink_rebind(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _single_case_plan(tmp_path / "target")
    payloads = _valid_terminal_payloads(plan, tmp_path=tmp_path)
    output_parent = plan.execution_identity.output_root.parent
    stage = output_parent / (
        f".{plan.execution_identity.output_root.name}.{'1' * 64}.partial"
    )
    moved_run_cards = tmp_path / "moved-run-cards"
    outside = tmp_path / "outside"
    outside.mkdir()
    original_open = os.open
    injected = False

    def inject_before_nested_file_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal injected
        if (
            not injected
            and Path(os.fsdecode(path)).name == "execute-target-public-gaps.json"
        ):
            injected = True
            (stage / "run-cards").rename(moved_run_cards)
            (stage / "run-cards").symlink_to(outside, target_is_directory=True)
        return original_open(path, flags, mode, dir_fd=dir_fd)

    with bind_target_public_gap_execution(plan) as binding:
        monkeypatch.setattr(os, "open", inject_before_nested_file_open)
        with pytest.raises(ValueError, match=r"unsafe artifact: run-cards"):
            publish_target_public_gap_outputs(
                plan=plan,
                plan_sha256="1" * 64,
                payloads=payloads,
                execution_binding=binding,
            )

    assert (
        moved_run_cards / "execute-target-public-gaps.json"
    ).read_bytes() == payloads["run-cards/execute-target-public-gaps.json"]
    assert tuple(outside.iterdir()) == ()


def test_terminal_publication_rejects_final_name_swap_after_rename(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _single_case_plan(tmp_path / "target")
    payloads = _valid_terminal_payloads(plan, tmp_path=tmp_path)
    output_root = plan.execution_identity.output_root
    moved_output = tmp_path / "moved-output"
    outside = tmp_path / "outside"
    outside.mkdir()
    original_rename = os.rename
    injected = False

    def swap_final_name_after_rename(
        source: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        destination: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
    ) -> None:
        nonlocal injected
        original_rename(
            source,
            destination,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
        )
        if (
            not injected
            and os.fsdecode(destination) == output_root.name
            and dst_dir_fd is not None
        ):
            injected = True
            original_rename(output_root, moved_output)
            output_root.symlink_to(outside, target_is_directory=True)

    with bind_target_public_gap_execution(plan) as binding:
        monkeypatch.setattr(os, "rename", swap_final_name_after_rename)
        with pytest.raises(ValueError, match="published output changed"):
            publish_target_public_gap_outputs(
                plan=plan,
                plan_sha256="1" * 64,
                payloads=payloads,
                execution_binding=binding,
            )

    assert (moved_output / "target-public-gap-outcomes.jsonl").read_bytes() == payloads[
        "target-public-gap-outcomes.jsonl"
    ]
    assert tuple(outside.iterdir()) == ()


def test_terminal_resume_rejects_final_name_swap_after_tree_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _single_case_plan(tmp_path / "target")
    payloads = _valid_terminal_payloads(plan, tmp_path=tmp_path)
    output_root = plan.execution_identity.output_root
    moved_output = tmp_path / "moved-output"
    outside = tmp_path / "outside"
    outside.mkdir()

    with bind_target_public_gap_execution(plan) as binding:
        publish_target_public_gap_outputs(
            plan=plan,
            plan_sha256="1" * 64,
            payloads=payloads,
            execution_binding=binding,
        )

    original_read_tree = target_gap_module._read_directory_tree_at  # pyright: ignore[reportPrivateUsage]
    injected = False

    def swap_final_name_after_tree_read(root_fd: int) -> dict[str, bytes]:
        nonlocal injected
        result = original_read_tree(root_fd)
        if not injected:
            injected = True
            output_root.rename(moved_output)
            output_root.symlink_to(outside, target_is_directory=True)
        return result

    with bind_target_public_gap_execution(plan) as binding:
        monkeypatch.setattr(
            target_gap_module,
            "_read_directory_tree_at",
            swap_final_name_after_tree_read,
        )
        with pytest.raises(ValueError, match="published output changed"):
            publish_target_public_gap_outputs(
                plan=plan,
                plan_sha256="1" * 64,
                payloads=payloads,
                execution_binding=binding,
            )

    assert (moved_output / "target-public-gap-outcomes.jsonl").read_bytes() == payloads[
        "target-public-gap-outcomes.jsonl"
    ]
    assert tuple(outside.iterdir()) == ()


def test_terminal_resume_rejects_nested_directory_swap_after_tree_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _single_case_plan(tmp_path / "target")
    payloads = _valid_terminal_payloads(plan, tmp_path=tmp_path)
    output_root = plan.execution_identity.output_root
    run_cards = output_root / "run-cards"
    moved_run_cards = tmp_path / "moved-run-cards"
    outside = tmp_path / "outside"
    outside.mkdir()

    with bind_target_public_gap_execution(plan) as binding:
        publish_target_public_gap_outputs(
            plan=plan,
            plan_sha256="1" * 64,
            payloads=payloads,
            execution_binding=binding,
        )

    original_read_file = target_gap_module._read_unique_regular_file_at_named  # pyright: ignore[reportPrivateUsage]
    injected = False

    def swap_nested_name_after_file_read(
        parent_fd: int,
        name: str,
        *,
        label: str,
    ) -> bytes:
        nonlocal injected
        result = original_read_file(parent_fd, name, label=label)
        if not injected and label.endswith("run-cards/execute-target-public-gaps.json"):
            injected = True
            run_cards.rename(moved_run_cards)
            run_cards.symlink_to(outside, target_is_directory=True)
        return result

    with bind_target_public_gap_execution(plan) as binding:
        monkeypatch.setattr(
            target_gap_module,
            "_read_unique_regular_file_at_named",
            swap_nested_name_after_file_read,
        )
        with pytest.raises(
            ValueError,
            match="published output directory run-cards changed",
        ):
            publish_target_public_gap_outputs(
                plan=plan,
                plan_sha256="1" * 64,
                payloads=payloads,
                execution_binding=binding,
            )

    assert (
        moved_run_cards / "execute-target-public-gaps.json"
    ).read_bytes() == payloads["run-cards/execute-target-public-gaps.json"]
    assert tuple(outside.iterdir()) == ()


def test_document_download_pins_intermediate_directory_against_symlink_rebind(
    tmp_path: Path,
) -> None:
    plan = _single_case_plan(tmp_path / "target")
    refresh = refresh_target_public_gaps(
        plan=plan,
        scheduler=_Scheduler({("70000000", 1): _public_docket_html("70000000")}),
    )
    request = refresh.download_requests[0]
    candidate_directory = (
        plan.execution_identity.document_output_root / request.candidate_id
    )
    moved_candidate = tmp_path / "moved-candidate"
    outside = tmp_path / "outside"
    outside.mkdir()

    with bind_target_public_gap_execution(plan) as execution_binding:
        with target_gap_module._bind_target_document_directories(  # pyright: ignore[reportPrivateUsage]
            execution_binding,
            refresh.download_requests,
        ) as document_binding:
            candidate_directory.rename(moved_candidate)
            candidate_directory.symlink_to(outside, target_is_directory=True)
            records = download_free_docket_documents(
                (request,),
                output_root=execution_binding.runtime_identity.document_output_root,
                source=FixtureFreeDocumentSource(
                    {request.source_url: b"%PDF-1.7\nbound\n"}
                ),
                bound_output_directories=document_binding.directories_by_request,
            )
            with pytest.raises(ValueError, match="document candidate directory"):
                document_binding.require_current()

    assert len(records) == 1
    assert tuple(outside.iterdir()) == ()
    assert (
        moved_candidate / request.source_provider / Path(records[0].local_path).name
    ).is_file()


def _valid_terminal_payloads(
    plan: TargetPublicGapPlan,
    *,
    tmp_path: Path,
) -> dict[str, bytes]:
    refresh = refresh_target_public_gaps(
        plan=plan,
        scheduler=_Scheduler({("70000000", 1): _public_docket_html("70000000")}),
    )
    pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"
    downloads, outcomes = download_target_public_gap_requests(
        refresh=refresh,
        document_source=FixtureFreeDocumentSource(
            {request.source_url: pdf for request in refresh.download_requests}
        ),
        document_output_root=plan.execution_identity.document_output_root,
        allow_existing_downloads=True,
    )
    execution = TargetPublicGapExecutionResult(
        refresh=refresh,
        downloads=downloads,
        outcomes=outcomes,
        terminal_commitments=target_public_gap_terminal_commitments(
            plan=plan,
            plan_sha256="1" * 64,
            refresh=refresh,
            downloads=downloads,
            outcomes=outcomes,
        ),
    )
    payloads = cli._target_public_gap_terminal_payloads(  # pyright: ignore[reportPrivateUsage]
        plan=plan,
        plan_path=tmp_path / "plan.json",
        plan_sha256="1" * 64,
        execution=execution,
        live_firecrawl=False,
        live_download=False,
    )
    return dict(payloads)


@pytest.mark.parametrize("commitment_mode", ["empty", "omitted"])
def test_preflight_rejects_forged_incomplete_output_commitments(
    tmp_path: Path,
    commitment_mode: str,
) -> None:
    root = tmp_path / "target"
    original = _single_case_plan(root)
    plan = replace(
        original,
        execution_identity=replace(
            original.execution_identity,
            output_root=tmp_path / f"forged-{commitment_mode}",
        ),
    )
    outcome_name = "target-public-gap-outcomes.jsonl"
    run_card_name = "run-cards/execute-target-public-gaps.json"
    log_name = "logs/execute-target-public-gaps.jsonl"
    outcome_bytes = b'{"outcome":"forged"}\n'
    receipt: dict[str, object] = {
        "schema_version": "legalforecast.target_public_gap_execution_receipt.v1",
        "status": "completed",
        "plan_sha256": "1" * 64,
        "execution_identity": dict(plan.execution_identity.to_record()),
        "source_artifact_commitments": dict(plan.source_artifact_commitments),
        "purchased_document_count": 0,
        "output_paths": [
            str(plan.execution_identity.output_root / name)
            for name in (outcome_name, run_card_name, log_name)
        ],
        **_no_authority_flags(),
    }
    if commitment_mode == "empty":
        receipt["output_commitments"] = {}
    run_card_bytes = _json_bytes(receipt)
    publish_target_public_gap_outputs(
        plan=plan,
        plan_sha256="1" * 64,
        payloads={
            outcome_name: outcome_bytes,
            run_card_name: run_card_bytes,
            log_name: _jsonl_bytes(
                [
                    {
                        "plan_sha256": "1" * 64,
                        "run_card_sha256": hashlib.sha256(run_card_bytes).hexdigest(),
                    }
                ]
            ),
        },
    )

    with pytest.raises(
        ValueError,
        match=r"commitment|receipt|tree",
    ):
        preflight_target_public_gap_execution(
            plan,
            expected_plan_sha256="1" * 64,
        )


def test_plan_publication_rejects_symlink_parent_without_writing(
    tmp_path: Path,
) -> None:
    target_root = tmp_path / "target"
    target_root.mkdir()
    plan = _single_case_plan(target_root)
    symlink_parent = tmp_path / "plan-parent"
    symlink_parent.symlink_to(target_root, target_is_directory=True)
    escaped = target_root / "escaped-plan.json"

    with pytest.raises(ValueError, match=r"symlink|overlaps"):
        publish_target_public_gap_plan(symlink_parent / escaped.name, plan)

    assert not escaped.exists()


def test_plan_publication_rejects_parent_rebind(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _single_case_plan(tmp_path / "target")
    parent = tmp_path / "plan-parent"
    parent.mkdir()
    moved_parent = tmp_path / "moved-plan-parent"
    original_link = os.link

    def rebind_before_link(
        source: str,
        destination: str,
        *,
        src_dir_fd: int,
        dst_dir_fd: int,
        follow_symlinks: bool,
    ) -> None:
        parent.rename(moved_parent)
        parent.mkdir()
        original_link(
            source,
            destination,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
            follow_symlinks=follow_symlinks,
        )

    monkeypatch.setattr(os, "link", rebind_before_link)

    with pytest.raises(ValueError, match="parent changed"):
        publish_target_public_gap_plan(parent / "plan.json", plan)

    assert not (parent / "plan.json").exists()


def test_plan_publication_rejects_destination_entry_swap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _single_case_plan(tmp_path / "target")
    destination = tmp_path / "plan.json"
    publish_target_public_gap_plan(destination, plan)
    original_stat = os.stat
    swapped = False

    def swap_before_entry_stat(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes] | int,
        *,
        dir_fd: int | None = None,
        follow_symlinks: bool = True,
    ) -> os.stat_result:
        nonlocal swapped
        if dir_fd is not None and path == destination.name and not swapped:
            swapped = True
            replacement = tmp_path / "replacement"
            replacement.write_bytes(destination.read_bytes())
            os.replace(replacement, destination)
        return original_stat(
            path,
            dir_fd=dir_fd,
            follow_symlinks=follow_symlinks,
        )

    monkeypatch.setattr(os, "stat", swap_before_entry_stat)

    with pytest.raises(ValueError, match="directory entry changed"):
        publish_target_public_gap_plan(destination, plan)


def test_execution_preflight_rejects_source_overlap_and_symlink(
    tmp_path: Path,
) -> None:
    root = tmp_path / "target"
    plan = _single_case_plan(root)
    overlapping = _single_case_plan(
        root,
        execution_identity=TargetPublicGapExecutionIdentity(
            output_root=root / "unsafe-output",
            cycle_store_path=tmp_path / "unsafe/cycle.sqlite3",
            raw_html_root=tmp_path / "unsafe/raw",
            document_output_root=tmp_path / "unsafe/documents",
            batch_id="target-public-gaps",
            run_id="target-public-gaps-001",
            firecrawl_mode="fixture",
            document_mode="fixture",
            firecrawl_proxy="basic",
            force_browser=False,
            max_attempts_per_page=3,
            provider_breaker_threshold=5,
        ),
    )
    with pytest.raises(ValueError, match="overlaps authenticated source"):
        preflight_target_public_gap_execution(overlapping)

    work_parent = plan.execution_identity.raw_html_root.parent
    work_parent.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    plan.execution_identity.raw_html_root.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        preflight_target_public_gap_execution(plan)

    root_two = tmp_path / "target-two"
    hardlinked = _single_case_plan(root_two)
    for path, payload in _verified_projection_bytes(root_two).items():
        source = Path(path)
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(payload)
    cycle_store = hardlinked.execution_identity.cycle_store_path
    cycle_store.parent.mkdir(parents=True, exist_ok=True)
    os.link(next(iter(hardlinked.source_artifact_commitments)), cycle_store)
    with pytest.raises(
        ValueError,
        match=r"hard-link|aliases authenticated source",
    ):
        preflight_target_public_gap_execution(hardlinked)


def test_provider_factories_are_after_final_preflight(tmp_path: Path) -> None:
    root = tmp_path / "target"
    unsafe = _single_case_plan(
        root,
        execution_identity=TargetPublicGapExecutionIdentity(
            output_root=root / "unsafe-output",
            cycle_store_path=tmp_path / "unsafe/cycle.sqlite3",
            raw_html_root=tmp_path / "unsafe/raw",
            document_output_root=tmp_path / "unsafe/documents",
            batch_id="target-public-gaps",
            run_id="target-public-gaps-001",
            firecrawl_mode="fixture",
            document_mode="fixture",
            firecrawl_proxy="basic",
            force_browser=False,
            max_attempts_per_page=3,
            provider_breaker_threshold=5,
        ),
    )
    constructed: list[str] = []

    def construct_firecrawl() -> Never:
        constructed.append("firecrawl")
        raise AssertionError("provider constructed before preflight")

    def construct_document_source() -> Never:
        constructed.append("document")
        raise AssertionError("provider constructed before preflight")

    with pytest.raises(ValueError, match="overlaps authenticated source"):
        execute_target_public_gap_refresh(
            plan=unsafe,
            expected_plan_sha256=_plan_sha256(unsafe),
            firecrawl_source_factory=construct_firecrawl,
            document_source_factory=construct_document_source,
            allow_existing_downloads=True,
        )

    assert constructed == []


def test_execution_rejects_plan_digest_mismatch_before_provider_construction(
    tmp_path: Path,
) -> None:
    plan = _single_case_plan(tmp_path / "target")
    constructed: list[str] = []

    def construct_firecrawl() -> Never:
        constructed.append("firecrawl")
        raise AssertionError("provider constructed before plan digest check")

    def construct_document_source() -> Never:
        constructed.append("document")
        raise AssertionError("provider constructed before plan digest check")

    with pytest.raises(ValueError, match="plan SHA-256 mismatch"):
        execute_target_public_gap_refresh(
            plan=plan,
            expected_plan_sha256="1" * 64,
            firecrawl_source_factory=construct_firecrawl,
            document_source_factory=construct_document_source,
            allow_existing_downloads=True,
        )

    assert constructed == []
    assert not plan.execution_identity.cycle_store_path.exists()


def test_execution_rejects_parent_rebind_before_any_runtime_write(
    tmp_path: Path,
) -> None:
    root = tmp_path / "target"
    plan = _single_case_plan(root)
    for path, payload in _verified_projection_bytes(root).items():
        source = Path(path)
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(payload)
    runtime_parent = plan.execution_identity.output_root.parent
    moved_parent = tmp_path / "moved-runtime-parent"
    constructed: list[str] = []

    def construct_firecrawl() -> Any:
        constructed.append("firecrawl")
        runtime_parent.rename(moved_parent)
        runtime_parent.mkdir()
        return object()

    def construct_document_source() -> FixtureFreeDocumentSource:
        constructed.append("document")
        return FixtureFreeDocumentSource({})

    with pytest.raises(ValueError, match="output parent changed"):
        execute_target_public_gap_refresh(
            plan=plan,
            expected_plan_sha256=_plan_sha256(plan),
            firecrawl_source_factory=construct_firecrawl,
            document_source_factory=construct_document_source,
            allow_existing_downloads=True,
        )

    assert constructed == ["firecrawl"]
    assert not plan.execution_identity.cycle_store_path.exists()
    assert not plan.execution_identity.output_root.exists()


def test_execute_mode_validation_precedes_any_plan_or_output_write(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "must-not-exist"

    status = cli.main(
        [
            "acquisition",
            "execute-target-public-gaps",
            "--output-root",
            str(output_root),
            "--target-cohort-root",
            str(tmp_path / "absent-target"),
            "--expected-target-run-card-sha256",
            "1" * 64,
            "--cycle-store",
            str(tmp_path / "work/cycle.sqlite3"),
            "--batch-id",
            "batch",
            "--run-id",
            "run",
            "--fresh-credit-cap",
            "500",
            "--workers",
            "1",
            "--firecrawl-mode",
            "fixture",
            "--document-mode",
            "fixture",
            "--plan",
            str(tmp_path / "absent-plan.json"),
            "--expected-plan-sha256",
            "2" * 64,
            "--raw-html-dir",
            str(tmp_path / "work/raw"),
            "--document-output-root",
            str(tmp_path / "work/documents"),
        ]
    )

    assert status == 2
    assert not output_root.exists()


@pytest.mark.parametrize(
    "marker",
    ["Document is sealed.", "Document is private and restricted."],
)
def test_refresh_excludes_restricted_or_private_public_rows(
    tmp_path: Path,
    marker: str,
) -> None:
    candidate_id = "70000000"
    html = _public_docket_html(candidate_id).replace(
        "Motion to Dismiss Memorandum in Support",
        f"Motion to Dismiss Memorandum in Support {marker}",
    )

    result = refresh_target_public_gaps(
        plan=_single_case_plan(tmp_path),
        scheduler=_Scheduler({(candidate_id, 1): html}),
    )

    assert result.transitions == ()
    assert len(result.gap_failures) == 2
    assert result.download_requests == ()


def test_refresh_zero_successful_bundles_is_terminal_per_gap(
    tmp_path: Path,
) -> None:
    result = refresh_target_public_gaps(
        plan=_single_case_plan(tmp_path),
        scheduler=_Scheduler({}),
    )

    assert result.transitions == ()
    assert len(result.gap_failures) == 2
    assert {row["outcome"] for row in result.gap_failures} == {"terminal_gap_failure"}
    assert result.download_requests == ()


def test_downloads_terminalize_content_failure_but_not_transport_failure(
    tmp_path: Path,
) -> None:
    candidate_id = "70000000"
    plan = _single_case_plan(tmp_path)
    refresh = refresh_target_public_gaps(
        plan=plan,
        scheduler=_Scheduler({(candidate_id, 1): _public_docket_html(candidate_id)}),
    )
    good_request, bad_request = refresh.download_requests
    downloads, outcomes = download_target_public_gap_requests(
        refresh=refresh,
        document_source=FixtureFreeDocumentSource(
            {
                good_request.source_url: (b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"),
                bad_request.source_url: b"<html>not a pdf</html>",
            }
        ),
        document_output_root=tmp_path / "documents",
        allow_existing_downloads=True,
    )

    assert len(downloads) == 1
    assert {outcome["outcome"] for outcome in outcomes} == {
        "newly_free",
        "terminal_gap_failure",
    }
    with pytest.raises(FreeDocumentDownloadError, match="retry later"):
        download_target_public_gap_requests(
            refresh=refresh,
            document_source=_TransientDocumentSource(),
            document_output_root=tmp_path / "transient-documents",
            allow_existing_downloads=True,
        )


def test_downloads_propagate_checkpoint_and_existing_output_conflicts(
    tmp_path: Path,
) -> None:
    candidate_id = "70000000"
    refresh = refresh_target_public_gaps(
        plan=_single_case_plan(tmp_path / "target"),
        scheduler=_Scheduler({(candidate_id, 1): _public_docket_html(candidate_id)}),
    )
    pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"
    source = FixtureFreeDocumentSource(
        {request.source_url: pdf for request in refresh.download_requests}
    )
    document_root = tmp_path / "documents"
    download_target_public_gap_requests(
        refresh=refresh,
        document_source=source,
        document_output_root=document_root,
        allow_existing_downloads=True,
    )

    with pytest.raises(
        FreeDocumentDownloadError,
        match="existing document artifact",
    ):
        download_target_public_gap_requests(
            refresh=refresh,
            document_source=source,
            document_output_root=document_root,
            allow_existing_downloads=False,
        )

    (document_root / ".download-checkpoint.jsonl").write_text("{not-json}\n")
    with pytest.raises(
        FreeDocumentDownloadError,
        match="checkpoint",
    ):
        download_target_public_gap_requests(
            refresh=refresh,
            document_source=source,
            document_output_root=document_root,
            allow_existing_downloads=True,
        )


def _selection(
    candidate_id: str,
    documents: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "case_id": candidate_id,
        "case_name": f"Fixture {candidate_id}",
        "court": "cand",
        "docket_number": f"1:26-cv-{candidate_id[-4:]}",
        "decision_date": "2026-07-20",
        "case_type_stratum": "district_civil",
        "selected": True,
        "source_url": (
            f"https://www.courtlistener.com/docket/{candidate_id}/fixture-case/"
        ),
        "target_motion_entry_numbers": [2],
        "decision_entry_numbers": [3],
        "documents": documents,
    }


def _plan_sha256(plan: TargetPublicGapPlan) -> str:
    return hashlib.sha256(target_public_gap_plan_bytes(plan)).hexdigest()


def _single_case_plan(
    root: Path,
    *,
    execution_identity: TargetPublicGapExecutionIdentity | None = None,
) -> TargetPublicGapPlan:
    candidate_id = "70000000"
    documents = [
        _document(
            candidate_id,
            "complaint-old",
            entry_number=1,
            role="complaint",
            available=True,
        ),
        _document(
            candidate_id,
            "mtd-old",
            entry_number=2,
            role="motion_to_dismiss_memorandum",
            available=False,
        ),
        _document(
            candidate_id,
            "decision-old",
            entry_number=3,
            role="decision",
            available=False,
        ),
    ]
    run_card_bytes = b'{"authenticated":"single-target"}\n'
    selections = [_selection(candidate_id, documents)]
    free_manifest: list[dict[str, object]] = [
        {
            "candidate_id": candidate_id,
            "source_document_id": "complaint-old",
        }
    ]
    return plan_target_public_gaps(
        verified_projection=_verified_projection(
            root=root,
            run_card_bytes=run_card_bytes,
            selections=selections,
            free_manifest=free_manifest,
        ),
        target_cohort_root=root,
        expected_target_run_card_sha256=hashlib.sha256(run_card_bytes).hexdigest(),
        fresh_credit_cap=10,
        workers=1,
        max_pages_per_docket=3,
        execution_identity=execution_identity or _execution_identity(root),
    )


def _execution_identity(root: Path) -> TargetPublicGapExecutionIdentity:
    base = root.parent / f"{root.name}-refresh"
    return TargetPublicGapExecutionIdentity(
        output_root=base / "published",
        cycle_store_path=base / "work/cycle.sqlite3",
        raw_html_root=base / "work/raw",
        document_output_root=base / "work/documents",
        batch_id="target-public-gaps",
        run_id="target-public-gaps-001",
        firecrawl_mode="fixture",
        document_mode="fixture",
        firecrawl_proxy="basic",
        force_browser=False,
        max_attempts_per_page=3,
        provider_breaker_threshold=5,
    )


def _verified_projection(
    *,
    root: Path,
    run_card_bytes: bytes,
    selections: list[dict[str, object]],
    free_manifest: list[dict[str, object]],
) -> dict[str, object]:
    selection_bytes = _jsonl_bytes(selections)
    free_manifest_bytes = _jsonl_bytes(free_manifest)
    summary = {
        "projection_sha256": "sha256:" + "a" * 64,
        "snapshot_cycle_hash": "b" * 64,
        "selected_case_count": len(selections),
        "selected_candidate_ids_sha256": _semantic_sha256(
            [str(selection["candidate_id"]) for selection in selections]
        ),
    }
    summary_bytes = (json.dumps(summary, indent=2, sort_keys=True) + "\n").encode()
    run_card_path = root / "run-cards/project-target-cohort.json"
    summary_path = root / "target-cohort-projection.json"
    selection_path = root / "target-cohort-selection.jsonl"
    free_manifest_path = root / "free-document-downloads.jsonl"
    return {
        "run_card": {"schema_version": "legalforecast.acquisition_run_card.v1"},
        "run_card_path": run_card_path,
        "run_card_bytes": run_card_bytes,
        "summary": summary,
        "summary_path": summary_path,
        "selection_path": selection_path,
        "selection_records": selections,
        "free_manifest_path": free_manifest_path,
        "free_manifest": free_manifest,
        "verified_artifact_bytes": {
            str(run_card_path.absolute()): run_card_bytes,
            str(summary_path.absolute()): summary_bytes,
            str(selection_path.absolute()): selection_bytes,
            str(free_manifest_path.absolute()): free_manifest_bytes,
        },
    }


def _verified_projection_bytes(root: Path) -> dict[str, bytes]:
    candidate_id = "70000000"
    documents = [
        _document(
            candidate_id,
            "complaint-old",
            entry_number=1,
            role="complaint",
            available=True,
        ),
        _document(
            candidate_id,
            "mtd-old",
            entry_number=2,
            role="motion_to_dismiss_memorandum",
            available=False,
        ),
        _document(
            candidate_id,
            "decision-old",
            entry_number=3,
            role="decision",
            available=False,
        ),
    ]
    verified = _verified_projection(
        root=root,
        run_card_bytes=b'{"authenticated":"single-target"}\n',
        selections=[_selection(candidate_id, documents)],
        free_manifest=[
            {
                "candidate_id": candidate_id,
                "source_document_id": "complaint-old",
            }
        ],
    )
    return cast(dict[str, bytes], verified["verified_artifact_bytes"])


def _semantic_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _jsonl_bytes(records: Sequence[dict[str, object]]) -> bytes:
    return b"".join(
        (json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n").encode()
        for record in records
    )


def _json_bytes(record: dict[str, object]) -> bytes:
    return (
        json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode()


def _no_authority_flags() -> dict[str, object]:
    return {
        "pacer_authorized": False,
        "recap_fetch_authorized": False,
        "document_purchase_authorized": False,
        "model_calls_authorized": False,
        "evaluation_authorized": False,
        "freeze_or_dispatch_authorized": False,
        "purchased_activity_requested": False,
        "purchased_activity_executed": False,
    }


def _document(
    candidate_id: str,
    source_document_id: str,
    *,
    entry_number: int,
    role: str,
    available: bool,
) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "source_document_id": source_document_id,
        "courtlistener_docket_entry_id": str(400_000_000 + entry_number),
        "docket_entry_number": entry_number,
        "document_role": role,
        "description": role.replace("_", " "),
        "availability_status": "available" if available else "unavailable",
        "requires_paid_recovery": not available,
        "source_url": (
            f"https://storage.courtlistener.com/recap/{source_document_id}.pdf"
            if available
            else (
                "https://www.courtlistener.com/api/rest/v4/recap-documents/"
                f"{source_document_id}/"
            )
        ),
    }


def _public_docket_html(docket_id: str) -> str:
    rows = (
        (1, "Complaint", "complaint-old"),
        (2, "Motion to Dismiss Memorandum in Support", "mtd-old"),
        (3, "Order on Motion to Dismiss", "decision-old"),
    )
    body = "".join(
        (
            f'<div id="entry-{400_000_000 + number}" class="row">'
            f'<div class="col-xs-1">{number}</div>'
            '<div class="col-xs-3"><span title="July 20, 2026">'
            "July 20, 2026</span></div>"
            f'<div class="col-xs-8">{description}'
            '<div class="row recap-documents"><div>Main Document</div>'
            f"<div>{description}</div>"
            f'<a href="https://storage.courtlistener.com/recap/{document_id}.pdf">'
            "Download PDF</a></div></div></div>"
        )
        for number, description, document_id in rows
    )
    return (
        f"<html><head><title>Fixture {docket_id}</title></head><body>"
        f'<div id="docket-entry-table">{body}</div>'
        '<a rel="next" href="?order_by=desc&amp;page=2">Next</a>'
        "</body></html>"
    )


class _Scheduler:
    def __init__(self, responses: dict[tuple[str, int], str]) -> None:
        self.responses = responses
        self.waves: list[list[tuple[str, int]]] = []

    def run(
        self,
        targets: Sequence[FirecrawlTargetSpec],
    ) -> BudgetedFirecrawlRunResult:
        wave: list[tuple[str, int]] = []
        pages: list[FirecrawlPageRecord] = []
        for target in targets:
            source_url = target.source_url
            docket_id = source_url.split("/docket/", 1)[1].split("/", 1)[0]
            page_number = target.page_number
            wave.append((docket_id, page_number))
            raw_html = self.responses.get((docket_id, page_number))
            if raw_html is not None:
                pages.append(
                    FirecrawlPageRecord(
                        target_id=target.target_id,
                        target_kind=target.target_kind,
                        source_url=source_url,
                        page_number=page_number,
                        ordinal=target.ordinal,
                        attempt_id=page_number,
                        attempt_number=1,
                        raw_html=raw_html,
                        artifact_path=Path(f"/tmp/{target.target_id}.html"),
                        artifact_sha256=hashlib.sha256(raw_html.encode()).hexdigest(),
                        artifact_byte_count=len(raw_html.encode()),
                        reported_credits=1,
                        proxy_used="basic",
                        target_http_status=200,
                    )
                )
        self.waves.append(wave)
        return BudgetedFirecrawlRunResult(
            pages=tuple(pages),
            summary={"reserved_credits": len(wave)},
        )


class _TransientDocumentSource:
    def fetch(self, source_url: str) -> FreeDocumentFetch:
        try:
            raise TimeoutError("retry later")
        except TimeoutError as exc:
            raise FreeDocumentDownloadError("retry later") from exc
