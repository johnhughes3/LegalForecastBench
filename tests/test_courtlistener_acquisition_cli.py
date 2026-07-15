from __future__ import annotations

import hashlib
import json
import shutil
import urllib.request
from datetime import date
from email.message import Message
from pathlib import Path
from typing import Any, cast

import pytest
from legalforecast.cli import main
from legalforecast.ingestion.courtlistener_acquisition import (
    CourtListenerClientError,
    _CourtListenerRedirectHandler,
    courtlistener_search_hit_id,
    screen_courtlistener_docket_page,
)
from legalforecast.ingestion.courtlistener_client import CourtListenerDocket
from legalforecast.ingestion.courtlistener_snapshot_materialization import (
    CourtListenerSnapshotMaterializationError,
    _validate_frozen_identity,
)
from legalforecast.ingestion.courtlistener_web import parse_courtlistener_docket_html
from legalforecast.ingestion.cycle_acquisition_store import (
    CycleAcquisitionStore,
    verify_snapshot,
)
from legalforecast.ingestion.discovery_scheduler import (
    DiscoveryHit,
    TermTerminalStatus,
)
from legalforecast.ingestion.mtd_acquisition_screen import (
    screen_case_dev_docket_metadata,
)
from legalforecast.ingestion.screening_snapshot_union import (
    ScreeningSnapshotUnionError,
    load_screening_snapshot_union,
)


def test_docket_html_refuses_off_allowlist_redirect_hop() -> None:
    handler = _CourtListenerRedirectHandler()
    with pytest.raises(CourtListenerClientError, match="host allowlist"):
        handler.redirect_request(
            urllib.request.Request("https://www.courtlistener.com/docket/1/"),
            object(),
            302,
            "Found",
            Message(),
            "https://evil.example/docket/1/",
        )


def test_discover_courtlistener_help_documents_live_authority(
    capsys: Any,
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["acquisition", "discover-courtlistener", "--help"])
    assert exc_info.value.code == 0

    output = capsys.readouterr().out
    assert "--eligibility-anchor" in output
    assert "--search-window-start" in output
    assert "--search-window-end" in output
    assert "--live" in output
    assert "--live-firecrawl-docket-html" in output
    assert "--courtlistener-fixture" in output
    assert "--docket-html-fixture-dir" in output
    assert "--screened-cases-output" in output
    assert "--exclusions-output" in output


def test_materialize_courtlistener_snapshot_help_documents_source_binding(
    capsys: Any,
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["acquisition", "materialize-courtlistener-snapshot", "--help"])
    assert exc_info.value.code == 0

    output = capsys.readouterr().out
    assert "--cycle-store" in output
    assert "--batch-id" in output
    assert "--discovery-run-card" in output
    assert "--expected-discovery-run-card-sha256" in output
    assert "--snapshot-root" in output
    assert "--snapshot-id" in output


def test_snapshot_identity_allows_legacy_source_omission_only_on_both_sides() -> None:
    summary: dict[str, Any] = {
        "schema_version": "legalforecast.courtlistener_discovery_summary.v1",
        "dry_run": False,
        "anchor_date": "2026-06-30",
        "search_window_start": "2026-06-30",
        "search_window_end": "2026-07-12",
        "query_terms": ["order on motion to dismiss"],
        "target_clean_cases": 2,
        "max_candidates": 5,
        "search_page_size": 50,
        "target_met": False,
        "candidate_limit_reached": False,
        "per_term": {
            "order on motion to dismiss": {
                "terminal_status": "exhausted",
                "limit_bound": False,
            }
        },
    }
    run_card = {"anchor_date": "2026-06-30"}
    cycle_policy = {"eligibility_anchor": "2026-06-30"}
    legacy_batch = {
        "provider": "courtlistener",
        "search_window_start": "2026-06-30",
        "search_window_end": "2026-07-12",
        "query_terms": ["order on motion to dismiss"],
        "target_clean_cases": 2,
        "max_candidates": 5,
        "search_page_size": 50,
    }

    assert _validate_frozen_identity(
        run_card=run_card,
        summary=summary,
        cycle_policy=cycle_policy,
        batch_config=legacy_batch,
    ) == date(2026, 6, 30)

    with pytest.raises(
        CourtListenerSnapshotMaterializationError,
        match="frozen batch configuration",
    ):
        _validate_frozen_identity(
            run_card=run_card,
            summary={**summary, "docket_html_source": "firecrawl"},
            cycle_policy=cycle_policy,
            batch_config=legacy_batch,
        )


def test_materialize_courtlistener_snapshot_publishes_saturated_source_lineage(
    tmp_path: Path,
) -> None:
    discovery_root, cycle_store = _run_saturated_discovery(tmp_path)
    run_card = discovery_root / "run-cards" / "discover-courtlistener.json"
    snapshot_root = tmp_path / "snapshots"
    materialization_root = tmp_path / "materialization"

    command = [
        "acquisition",
        "materialize-courtlistener-snapshot",
        "--cycle-store",
        str(cycle_store),
        "--batch-id",
        "batch-001",
        "--discovery-run-card",
        str(run_card),
        "--expected-discovery-run-card-sha256",
        hashlib.sha256(run_card.read_bytes()).hexdigest(),
        "--snapshot-root",
        str(snapshot_root),
        "--snapshot-id",
        "courtlistener-complete",
        "--output-root",
        str(materialization_root),
        "--execute",
    ]
    assert main(command) == 0

    snapshot = snapshot_root / "courtlistener-complete"
    with CycleAcquisitionStore(cycle_store) as store:
        cycle_hash = store.cycle_hash
    manifest = verify_snapshot(
        snapshot,
        expected_cycle_hash=cycle_hash,
        require_complete=True,
        require_saturated=True,
    )
    assert manifest["complete"] is True
    assert manifest["saturated"] is True
    lineage = manifest["stage_commitments"]["courtlistener_discovery_inputs"]
    assert (
        lineage["discovery_run_card_sha256"]
        == hashlib.sha256(run_card.read_bytes()).hexdigest()
    )
    assert lineage["eligibility_anchor"] == "2026-06-30"
    assert lineage["source_saturated"] is True
    assert _read_json(snapshot / "summary.json") == {
        "accepted_count": 1,
        "batch_id": "batch-001",
        "excluded_count": 0,
        "processed_count": 1,
        "reconciliation_complete": True,
    }
    [screened] = _read_jsonl(snapshot / "screened-cases.jsonl")
    assert screened["first_written_mtd_disposition_date"] == "2026-06-30"
    first_manifest_bytes = (snapshot / "manifest.json").read_bytes()

    assert main(command) == 0
    assert (snapshot / "manifest.json").read_bytes() == first_manifest_bytes


def test_materialized_courtlistener_snapshot_is_prepare_target_cohort_input(
    tmp_path: Path,
) -> None:
    discovery_root, cycle_store = _run_saturated_discovery(tmp_path)
    snapshot = _materialize_discovery(
        tmp_path=tmp_path,
        discovery_root=discovery_root,
        cycle_store=cycle_store,
    )
    fixture_documents = tmp_path / "free-documents.json"
    fixture_documents.write_text(
        json.dumps(
            {
                f"https://storage.courtlistener.com/{name}": _fixture_pdf_text(
                    "Benign public court filing"
                )
                for name in ("1.pdf", "5.pdf", "5-memo.pdf", "16.pdf")
            }
        ),
        encoding="utf-8",
    )
    courtlistener_fixture = tmp_path / "bridge-courtlistener.jsonl"
    courtlistener_fixture.write_text("", encoding="utf-8")
    with CycleAcquisitionStore(cycle_store) as store:
        cycle_hash = store.cycle_hash

    assert (
        main(
            [
                "acquisition",
                "prepare-target-cohort",
                "--output-root",
                str(tmp_path / "prepared"),
                "--snapshot",
                str(snapshot),
                "--expected-cycle-hash",
                cycle_hash,
                "--target-case-count",
                "1",
                "--fixture-documents",
                str(fixture_documents),
                "--courtlistener-fixture",
                str(courtlistener_fixture),
                "--use-embedded-entries",
                "--execute",
            ]
        )
        == 0
    )
    prepared = _read_json(
        tmp_path / "prepared" / "target-cohort-preparation-summary.json"
    )
    assert prepared["selected_case_count"] == 1


def test_old_and_direct_snapshots_union_provider_free_then_prepare(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    discovery_root, cycle_store = _run_saturated_discovery(tmp_path)
    direct_snapshot = _materialize_discovery(
        tmp_path=tmp_path,
        discovery_root=discovery_root,
        cycle_store=cycle_store,
        snapshot_id="fresh-direct",
    )
    old_snapshot = _create_old_replay_snapshot(
        tmp_path=tmp_path,
        discovery_root=discovery_root,
        cycle_store=cycle_store,
    )
    with CycleAcquisitionStore(cycle_store) as store:
        cycle_hash = store.cycle_hash

    def unexpected_provider(*args: object, **kwargs: object) -> object:
        raise AssertionError("snapshot union must not construct a provider client")

    monkeypatch.setattr(
        "legalforecast.cli.CourtListenerClient",
        unexpected_provider,
    )
    union_root = tmp_path / "union-snapshots"
    union_command = [
        "acquisition",
        "union-screening-snapshots",
        "--cycle-store",
        str(cycle_store),
        "--batch-id",
        "old-plus-direct",
        "--expected-cycle-hash",
        cycle_hash,
        "--source-snapshot",
        str(old_snapshot),
        "--source-snapshot",
        str(direct_snapshot),
        "--expected-source-snapshot-manifest-sha256",
        _manifest_sha256(old_snapshot),
        "--expected-source-snapshot-manifest-sha256",
        _manifest_sha256(direct_snapshot),
        "--snapshot-root",
        str(union_root),
        "--snapshot-id",
        "complete-union",
        "--output-root",
        str(tmp_path / "union-output"),
        "--execute",
    ]
    assert main(union_command) == 0
    union_snapshot = union_root / "complete-union"
    manifest = verify_snapshot(
        union_snapshot,
        expected_cycle_hash=cycle_hash,
        require_complete=True,
        require_saturated=True,
    )
    sources = manifest["stage_commitments"]["screening_snapshot_union_inputs"][
        "sources"
    ]
    assert [source["manifest_path"] for source in sources] == [
        str(old_snapshot / "manifest.json"),
        str(direct_snapshot / "manifest.json"),
    ]
    assert len(_read_jsonl(union_snapshot / "screened-cases.jsonl")) == 2
    first_manifest = (union_snapshot / "manifest.json").read_bytes()
    auxiliary_manifest = tmp_path / "union-output" / "union-raw-artifacts.jsonl"
    auxiliary_manifest.unlink()
    assert main(union_command) == 0
    assert (union_snapshot / "manifest.json").read_bytes() == first_manifest
    assert auxiliary_manifest.is_file()
    monkeypatch.undo()
    shutil.rmtree(old_snapshot)
    shutil.rmtree(direct_snapshot)
    shutil.rmtree(discovery_root / "raw-courtlistener-html")
    shutil.rmtree(tmp_path / "old-raw")
    verify_snapshot(
        union_snapshot,
        expected_cycle_hash=cycle_hash,
        require_complete=True,
        require_saturated=True,
    )

    fixture_documents = tmp_path / "union-free-documents.json"
    fixture_documents.write_text(
        json.dumps(
            {
                f"https://storage.courtlistener.com/{name}": _fixture_pdf_text(
                    "Benign public court filing"
                )
                for name in ("1.pdf", "5.pdf", "5-memo.pdf", "16.pdf")
            }
        ),
        encoding="utf-8",
    )
    empty_courtlistener = tmp_path / "union-courtlistener.jsonl"
    empty_courtlistener.write_text("", encoding="utf-8")
    assert (
        main(
            [
                "acquisition",
                "prepare-target-cohort",
                "--output-root",
                str(tmp_path / "union-prepared"),
                "--snapshot",
                str(union_snapshot),
                "--expected-cycle-hash",
                cycle_hash,
                "--target-case-count",
                "2",
                "--fixture-documents",
                str(fixture_documents),
                "--courtlistener-fixture",
                str(empty_courtlistener),
                "--use-embedded-entries",
                "--execute",
            ]
        )
        == 0
    )
    prepared = _read_json(
        tmp_path / "union-prepared" / "target-cohort-preparation-summary.json"
    )
    assert prepared["selected_case_count"] == 2


def test_snapshot_union_rejects_copied_identical_source(tmp_path: Path) -> None:
    discovery_root, cycle_store = _run_saturated_discovery(tmp_path)
    direct_snapshot = _materialize_discovery(
        tmp_path=tmp_path,
        discovery_root=discovery_root,
        cycle_store=cycle_store,
    )
    copied_snapshot = tmp_path / "copied-snapshot"
    shutil.copytree(direct_snapshot, copied_snapshot)
    with CycleAcquisitionStore(cycle_store) as store:
        cycle_hash = store.cycle_hash

    with pytest.raises(ScreeningSnapshotUnionError, match="duplicate source manifest"):
        load_screening_snapshot_union(
            (direct_snapshot, copied_snapshot),
            expected_manifest_sha256=(
                _manifest_sha256(direct_snapshot),
                _manifest_sha256(copied_snapshot),
            ),
            expected_cycle_hash=cycle_hash,
        )


def test_snapshot_union_rejects_symlinked_source_metadata(tmp_path: Path) -> None:
    discovery_root, cycle_store = _run_saturated_discovery(tmp_path)
    direct_snapshot = _materialize_discovery(
        tmp_path=tmp_path,
        discovery_root=discovery_root,
        cycle_store=cycle_store,
    )
    old_snapshot = _create_old_replay_snapshot(
        tmp_path=tmp_path,
        discovery_root=discovery_root,
        cycle_store=cycle_store,
    )
    candidates = old_snapshot / "candidates.jsonl"
    real_candidates = tmp_path / "old-candidates.jsonl"
    candidates.rename(real_candidates)
    candidates.symlink_to(real_candidates)
    with CycleAcquisitionStore(cycle_store) as store:
        cycle_hash = store.cycle_hash

    with pytest.raises(ScreeningSnapshotUnionError, match="not a regular file"):
        load_screening_snapshot_union(
            (old_snapshot, direct_snapshot),
            expected_manifest_sha256=(
                _manifest_sha256(old_snapshot),
                _manifest_sha256(direct_snapshot),
            ),
            expected_cycle_hash=cycle_hash,
        )


def test_snapshot_union_rejects_noncanonical_raw_path(tmp_path: Path) -> None:
    discovery_root, cycle_store = _run_saturated_discovery(tmp_path)
    direct_snapshot = _materialize_discovery(
        tmp_path=tmp_path,
        discovery_root=discovery_root,
        cycle_store=cycle_store,
    )
    old_snapshot = _create_old_replay_snapshot(
        tmp_path=tmp_path,
        discovery_root=discovery_root,
        cycle_store=cycle_store,
    )
    [raw_record] = _read_jsonl(old_snapshot / "raw-artifacts.jsonl")
    canonical = Path(cast(str, raw_record["path"]))
    (canonical.parent / "nested").mkdir()
    raw_record["path"] = str(canonical.parent / "nested" / ".." / canonical.name)
    _rewrite_snapshot_jsonl(old_snapshot, "raw-artifacts.jsonl", [raw_record])
    with CycleAcquisitionStore(cycle_store) as store:
        cycle_hash = store.cycle_hash

    with pytest.raises(ScreeningSnapshotUnionError, match="canonical absolute path"):
        load_screening_snapshot_union(
            (old_snapshot, direct_snapshot),
            expected_manifest_sha256=(
                _manifest_sha256(old_snapshot),
                _manifest_sha256(direct_snapshot),
            ),
            expected_cycle_hash=cycle_hash,
        )


def test_snapshot_union_rejects_raw_path_through_symlinked_parent(
    tmp_path: Path,
) -> None:
    discovery_root, cycle_store = _run_saturated_discovery(tmp_path)
    direct_snapshot = _materialize_discovery(
        tmp_path=tmp_path,
        discovery_root=discovery_root,
        cycle_store=cycle_store,
    )
    old_snapshot = _create_old_replay_snapshot(
        tmp_path=tmp_path,
        discovery_root=discovery_root,
        cycle_store=cycle_store,
    )
    raw_parent = tmp_path / "old-raw"
    real_parent = tmp_path / "old-raw-real"
    raw_parent.rename(real_parent)
    raw_parent.symlink_to(real_parent, target_is_directory=True)
    with CycleAcquisitionStore(cycle_store) as store:
        cycle_hash = store.cycle_hash

    with pytest.raises(ScreeningSnapshotUnionError, match="canonical absolute path"):
        load_screening_snapshot_union(
            (old_snapshot, direct_snapshot),
            expected_manifest_sha256=(
                _manifest_sha256(old_snapshot),
                _manifest_sha256(direct_snapshot),
            ),
            expected_cycle_hash=cycle_hash,
        )


def test_snapshot_union_rejects_symlinked_source_root(tmp_path: Path) -> None:
    discovery_root, cycle_store = _run_saturated_discovery(tmp_path)
    direct_snapshot = _materialize_discovery(
        tmp_path=tmp_path,
        discovery_root=discovery_root,
        cycle_store=cycle_store,
    )
    old_snapshot = _create_old_replay_snapshot(
        tmp_path=tmp_path,
        discovery_root=discovery_root,
        cycle_store=cycle_store,
    )
    old_alias = tmp_path / "old-snapshot-alias"
    old_alias.symlink_to(old_snapshot, target_is_directory=True)
    with CycleAcquisitionStore(cycle_store) as store:
        cycle_hash = store.cycle_hash

    with pytest.raises(ScreeningSnapshotUnionError, match="without symlinks"):
        load_screening_snapshot_union(
            (old_alias, direct_snapshot),
            expected_manifest_sha256=(
                _manifest_sha256(old_snapshot),
                _manifest_sha256(direct_snapshot),
            ),
            expected_cycle_hash=cycle_hash,
        )


def test_snapshot_union_rejects_unpinned_manifest_substitution(tmp_path: Path) -> None:
    discovery_root, cycle_store = _run_saturated_discovery(tmp_path)
    direct_snapshot = _materialize_discovery(
        tmp_path=tmp_path,
        discovery_root=discovery_root,
        cycle_store=cycle_store,
    )
    old_snapshot = _create_old_replay_snapshot(
        tmp_path=tmp_path,
        discovery_root=discovery_root,
        cycle_store=cycle_store,
    )
    with CycleAcquisitionStore(cycle_store) as store:
        cycle_hash = store.cycle_hash

    with pytest.raises(ScreeningSnapshotUnionError, match="SHA-256 mismatch"):
        load_screening_snapshot_union(
            (old_snapshot, direct_snapshot),
            expected_manifest_sha256=("0" * 64, _manifest_sha256(direct_snapshot)),
            expected_cycle_hash=cycle_hash,
        )


def test_materialize_courtlistener_snapshot_rejects_limit_bound_discovery(
    tmp_path: Path,
    capsys: Any,
) -> None:
    discovery_root, cycle_store = _run_saturated_discovery(
        tmp_path,
        target_clean_cases=1,
    )
    run_card = discovery_root / "run-cards" / "discover-courtlistener.json"

    assert (
        main(
            [
                "acquisition",
                "materialize-courtlistener-snapshot",
                "--cycle-store",
                str(cycle_store),
                "--batch-id",
                "batch-001",
                "--discovery-run-card",
                str(run_card),
                "--expected-discovery-run-card-sha256",
                hashlib.sha256(run_card.read_bytes()).hexdigest(),
                "--snapshot-root",
                str(tmp_path / "snapshots"),
                "--snapshot-id",
                "must-not-publish",
                "--output-root",
                str(tmp_path / "materialization"),
                "--execute",
            ]
        )
        == 2
    )
    assert "not saturated" in capsys.readouterr().err
    assert not (tmp_path / "snapshots" / "must-not-publish").exists()


def test_limit_bound_transcript_preserves_provider_next_cursor(tmp_path: Path) -> None:
    discovery_root, _cycle_store = _run_saturated_discovery(
        tmp_path,
        target_clean_cases=1,
        next_cursor="provider-cursor-2",
    )

    [page] = _read_jsonl(discovery_root / "courtlistener-search-pages.jsonl")
    assert page["terminal_status"] == "limit_bound:target_clean_cases"
    assert page["next_cursor"] == "provider-cursor-2"


def test_target_stop_reason_wins_when_target_and_max_are_simultaneous(
    tmp_path: Path,
) -> None:
    discovery_root, _cycle_store = _run_saturated_discovery(
        tmp_path,
        target_clean_cases=1,
        max_candidates=1,
    )

    [page] = _read_jsonl(discovery_root / "courtlistener-search-pages.jsonl")
    assert page["terminal_status"] == "limit_bound:target_clean_cases"
    summary = _read_json(discovery_root / "courtlistener-discovery-summary.json")
    assert summary["per_term"]["order on motion to dismiss"]["terminal_status"] == (
        "limit_bound:target_clean_cases"
    )


def test_discovery_raw_manifest_is_stable_across_resume(tmp_path: Path) -> None:
    discovery_root, _cycle_store = _run_saturated_discovery(tmp_path)
    manifest = discovery_root / "courtlistener-raw-artifacts.jsonl"
    first_bytes = manifest.read_bytes()

    _run_saturated_discovery(tmp_path, reuse_fixtures=True)

    assert manifest.read_bytes() == first_bytes
    [record] = _read_jsonl(manifest)
    assert "retrieved_at" not in record


def test_fallback_search_hit_identity_includes_page_context() -> None:
    record = {"docket_id": 123, "description": "Order"}

    first = courtlistener_search_hit_id(
        record, term="order", request_cursor=None, index=0
    )
    second = courtlistener_search_hit_id(
        record,
        term="order",
        request_cursor="provider-cursor-2",
        index=0,
    )

    assert first != second


def test_materializer_rejects_missing_raw_html(tmp_path: Path, capsys: Any) -> None:
    discovery_root, cycle_store = _run_saturated_discovery(tmp_path)
    (discovery_root / "raw-courtlistener-html" / "123.html").unlink()

    assert (
        main(
            _materialize_command(
                tmp_path=tmp_path,
                discovery_root=discovery_root,
                cycle_store=cycle_store,
            )
        )
        == 2
    )
    assert "not a regular file" in capsys.readouterr().err


def test_materializer_rejects_changed_committed_output(
    tmp_path: Path, capsys: Any
) -> None:
    discovery_root, cycle_store = _run_saturated_discovery(tmp_path)
    screened = discovery_root / "courtlistener-screened-cases.jsonl"
    screened.write_bytes(screened.read_bytes() + b"\n")

    assert (
        main(
            _materialize_command(
                tmp_path=tmp_path,
                discovery_root=discovery_root,
                cycle_store=cycle_store,
            )
        )
        == 2
    )
    assert "output commitment mismatch" in capsys.readouterr().err


@pytest.mark.parametrize("path_kind", ["traversal", "symlink-parent"])
def test_materializer_rejects_noncanonical_committed_output_path(
    tmp_path: Path,
    capsys: Any,
    path_kind: str,
) -> None:
    discovery_root, cycle_store = _run_saturated_discovery(tmp_path)
    run_card_path = discovery_root / "run-cards" / "discover-courtlistener.json"
    run_card = _read_json(run_card_path)
    output_paths = cast(list[str], run_card["output_paths"])
    canonical = Path(output_paths[0])
    if path_kind == "traversal":
        (canonical.parent / "nested").mkdir()
        output_paths[0] = str(canonical.parent / "nested" / ".." / canonical.name)
    else:
        alias = tmp_path / "discovery-alias"
        alias.symlink_to(discovery_root, target_is_directory=True)
        output_paths[0] = str(alias / canonical.relative_to(discovery_root))
    run_card_path.write_text(
        json.dumps(run_card, sort_keys=True) + "\n", encoding="utf-8"
    )

    assert (
        main(
            _materialize_command(
                tmp_path=tmp_path,
                discovery_root=discovery_root,
                cycle_store=cycle_store,
                snapshot_id=f"must-not-publish-{path_kind}",
            )
        )
        == 2
    )
    assert "canonical absolute path" in capsys.readouterr().err
    assert not (tmp_path / "snapshots" / f"must-not-publish-{path_kind}").exists()


def test_discover_courtlistener_produces_plan_public_downloads_input(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "acquisition"
    fixture_path = tmp_path / "courtlistener.jsonl"
    html_fixture_dir = tmp_path / "html-fixtures"
    html_fixture_dir.mkdir()
    (html_fixture_dir / "123.html").write_text(
        _docket_html(decision_dates=("June 30, 2026",)),
        encoding="utf-8",
    )
    _write_jsonl(
        fixture_path,
        [
            _response(
                path="/search/",
                params={
                    "q": (
                        '"order on motion to dismiss" AND '
                        "entry_date_filed:[2026-06-30 TO 2026-07-12]"
                    ),
                    "type": "r",
                    "order_by": "score desc",
                    "available_only": "on",
                    "page_size": 50,
                },
                payload={
                    "results": [
                        {
                            "docket_id": 123,
                            "docket_entry_id": 16,
                            "description": "Order on motion to dismiss",
                            "entry_date_filed": "2026-06-30",
                        }
                    ],
                    "next": None,
                },
            ),
            _response(
                path="/dockets/123/",
                payload={
                    "id": 123,
                    "court": ("https://www.courtlistener.com/api/rest/v4/courts/nysd/"),
                    "docket_number": "1:26-cv-00001",
                    "case_name": "Fixture v. Example",
                    "nature_of_suit": "Civil Rights",
                    "nos_macro_category": "civil_rights",
                    "related_family_id": "related-fixture",
                    "mdl_family_id": "mdl-fixture",
                    "date_filed": "2026-01-01",
                    "absolute_url": (
                        "https://www.courtlistener.com/docket/123/fixture-v-example/"
                    ),
                },
            ),
        ],
    )

    assert (
        main(
            [
                "acquisition",
                "discover-courtlistener",
                "--eligibility-anchor",
                "2026-06-30",
                "--search-window-start",
                "2026-06-30",
                "--search-window-end",
                "2026-07-12",
                "--cycle-store",
                str(tmp_path / "cycle.sqlite3"),
                "--batch-id",
                "batch-001",
                "--query-term",
                "order on motion to dismiss",
                "--target-clean-cases",
                "1",
                "--max-candidates",
                "5",
                "--courtlistener-fixture",
                str(fixture_path),
                "--docket-html-fixture-dir",
                str(html_fixture_dir),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )

    [screened] = _read_jsonl(output_root / "courtlistener-screened-cases.jsonl")
    assert screened["candidate"]["docket_id"] == "123"
    assert screened["candidate"]["metadata"]["court"] == "nysd"
    assert screened["candidate"]["metadata"]["nature_of_suit"] == "Civil Rights"
    assert screened["candidate"]["metadata"]["nos_macro_category"] == "civil_rights"
    assert screened["candidate"]["metadata"]["related_family_id"] == ("related-fixture")
    assert screened["candidate"]["metadata"]["mdl_family_id"] == "mdl-fixture"
    assert screened["ai"] == {
        "target_motion_entry_numbers": ["5"],
        "decision_entry_numbers": ["16"],
    }
    assert screened["first_written_mtd_disposition_date"] == "2026-06-30"
    assert len(screened["selected_entries"]) == 3
    assert _read_jsonl(output_root / "courtlistener-discovery-exclusions.jsonl") == []
    assert (output_root / "raw-courtlistener-html" / "123.html").is_file()

    summary = _read_json(output_root / "courtlistener-discovery-summary.json")
    assert summary["accepted_case_count"] == 1
    assert summary["excluded_case_count"] == 0
    assert summary["anchor_date"] == "2026-06-30"
    with CycleAcquisitionStore(tmp_path / "cycle.sqlite3") as store:
        assert store.cycle_policy["eligibility_anchor"] == "2026-06-30"
        assert store.batch_digest("batch-001")

    snapshot_path, cycle_hash = _complete_snapshot(
        tmp_path / "cycle",
        [screened],
        raw_html_dir=output_root / "raw-courtlistener-html",
    )

    assert (
        main(
            [
                "acquisition",
                "plan-public-downloads",
                "--snapshot",
                str(snapshot_path),
                "--expected-cycle-hash",
                cycle_hash,
                "--screened-cases",
                str(snapshot_path / "screened-cases.jsonl"),
                "--raw-html-dir",
                str(output_root / "raw-courtlistener-html"),
                "--target-clean-cases",
                "1",
                "--output-root",
                str(output_root / "public-downloads"),
                "--execute",
            ]
        )
        == 0
    )
    [selected] = _read_jsonl(
        output_root / "public-downloads" / "public-packet-selection.jsonl"
    )
    assert selected["candidate_id"] == "123"
    assert selected["decision_date"] == "2026-06-30"
    assert selected["nature_of_suit"] == "Civil Rights"
    assert selected["nos_macro_category"] == "civil_rights"
    assert selected["related_family_id"] == "related-fixture"
    assert selected["mdl_family_id"] == "mdl-fixture"
    assert selected["target_motion_entry_numbers"] == [5]
    assert selected["decision_entry_numbers"] == [16]


@pytest.mark.parametrize(
    ("first_disposition_date", "expected_reason", "notes_fragment"),
    (
        (
            "June 29, 2026",
            "decision_before_release_anchor",
            "first written MTD disposition",
        ),
        ("", "parse_error", "date could not be parsed"),
    ),
)
def test_discover_courtlistener_excludes_unproven_or_preanchor_first_disposition(
    tmp_path: Path,
    first_disposition_date: str,
    expected_reason: str,
    notes_fragment: str,
) -> None:
    output_root = tmp_path / "acquisition"
    fixture_path = tmp_path / "courtlistener.jsonl"
    html_fixture_dir = tmp_path / "html-fixtures"
    html_fixture_dir.mkdir()
    (html_fixture_dir / "123.html").write_text(
        _docket_html(decision_dates=(first_disposition_date, "July 1, 2026")),
        encoding="utf-8",
    )
    _write_jsonl(
        fixture_path,
        [
            _response(
                path="/search/",
                params={
                    "q": (
                        '"order on motion to dismiss" AND '
                        "entry_date_filed:[2026-06-30 TO 2026-07-12]"
                    ),
                    "type": "r",
                    "order_by": "score desc",
                    "available_only": "on",
                    "page_size": 50,
                },
                payload={
                    "results": [{"docket_id": 123, "docket_entry_id": 17}],
                    "next": None,
                },
            ),
            _response(
                path="/dockets/123/",
                payload={
                    "id": 123,
                    "court": "nysd",
                    "docket_number": "1:26-cv-00001",
                    "case_name": "Fixture v. Example",
                    "absolute_url": (
                        "https://www.courtlistener.com/docket/123/fixture-v-example/"
                    ),
                },
            ),
        ],
    )

    assert (
        main(
            [
                "acquisition",
                "discover-courtlistener",
                "--eligibility-anchor",
                "2026-06-30",
                "--search-window-start",
                "2026-06-30",
                "--search-window-end",
                "2026-07-12",
                "--query-term",
                "order on motion to dismiss",
                "--courtlistener-fixture",
                str(fixture_path),
                "--docket-html-fixture-dir",
                str(html_fixture_dir),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )

    assert _read_jsonl(output_root / "courtlistener-screened-cases.jsonl") == []
    [exclusion] = _read_jsonl(output_root / "courtlistener-discovery-exclusions.jsonl")
    assert exclusion["stage"] == "eligibility"
    assert exclusion["primary_exclusion_reason"] == expected_reason
    assert notes_fragment in exclusion["notes"]
    assert (output_root / "raw-courtlistener-html" / "123.html").is_file()


@pytest.mark.parametrize(
    "preanchor_entry",
    (
        (16, "June 10, 2026", "Order on Motion to Dismiss"),
        (
            16,
            "October 23, 2025",
            "ELECTRONIC ORDER: motion to dismiss 5 is denied as moot",
        ),
        (16, "June 9, 2026", "ORDER regarding 5 motion to dismiss"),
    ),
)
def test_canonical_screen_excludes_preanchor_generic_or_moot_mtd_disposition(
    preanchor_entry: tuple[int, str, str],
) -> None:
    screened, exclusion = _screen_custom_docket(
        entries=(
            (1, "January 2, 2026", "COMPLAINT filed by Plaintiff"),
            (5, "February 2, 2026", "MOTION to Dismiss filed by Defendant"),
            preanchor_entry,
            (40, "July 2, 2026", "ORDER granting 5 Motion to Dismiss"),
        )
    )

    assert screened is None
    assert exclusion is not None
    assert exclusion.reason == "decision_before_release_anchor"


def test_canonical_screen_excludes_preanchor_recommendation_later_adopted() -> None:
    screened, exclusion = _screen_custom_docket(
        entries=(
            (1, "January 2, 2026", "COMPLAINT filed by Plaintiff"),
            (18, "January 5, 2026", "MOTION to Dismiss filed by Defendant"),
            (31, "January 29, 2026", "Report & Recommendation"),
            (
                33,
                "July 9, 2026",
                "MEMORANDUM ORDER adopting 31 Report & Recommendation; "
                "granting 18 Motion to Dismiss",
            ),
        )
    )

    assert screened is None
    assert exclusion is not None
    assert exclusion.reason == "decision_before_release_anchor"


def test_canonical_screen_excludes_earlier_unreferenced_preanchor_recommendation() -> (
    None
):
    screened, exclusion = _screen_custom_docket(
        entries=(
            (1, "January 2, 2026", "COMPLAINT filed by Plaintiff"),
            (18, "January 5, 2026", "MOTION to Dismiss filed by Defendant"),
            (25, "June 29, 2026", "Report & Recommendation"),
            (31, "July 1, 2026", "Report & Recommendation"),
            (
                33,
                "July 9, 2026",
                "MEMORANDUM ORDER adopting 31 Report & Recommendation; "
                "granting 18 Motion to Dismiss",
            ),
        )
    )

    assert screened is None
    assert exclusion is not None
    assert exclusion.reason == "decision_before_release_anchor"
    assert exclusion.source_entry_ids == ("entry-25", "entry-31", "entry-33")


@pytest.mark.parametrize("relation", ("re", "regarding"))
def test_canonical_screen_accepts_genuinely_first_postanchor_disposition(
    relation: str,
) -> None:
    screened, exclusion = _screen_custom_docket(
        entries=(
            (1, "January 2, 2026", "COMPLAINT filed by Plaintiff"),
            (5, "February 2, 2026", "MOTION to Dismiss filed by Defendant"),
            (
                16,
                "June 20, 2026",
                f"Order {relation} Rule 12(b) Motions AND ~Util - Set Deadlines",
            ),
            (20, "July 1, 2026", "Order on Motion to Dismiss"),
            (21, "July 2, 2026", "ORDER granting 5 Motion to Dismiss"),
        )
    )

    assert exclusion is None
    assert screened is not None
    assert screened["first_written_mtd_disposition_date"] == "2026-07-01"


def test_discover_courtlistener_execute_requires_live_or_complete_fixture_pair(
    tmp_path: Path,
    capsys: Any,
) -> None:
    assert (
        main(
            [
                "acquisition",
                "discover-courtlistener",
                "--eligibility-anchor",
                "2026-06-30",
                "--search-window-start",
                "2026-06-30",
                "--search-window-end",
                "2026-07-12",
                "--output-root",
                str(tmp_path / "output"),
                "--execute",
            ]
        )
        == 2
    )
    assert "requires --live or both" in capsys.readouterr().err


def test_discovery_anchor_stays_fixed_while_search_window_advances(
    tmp_path: Path,
) -> None:
    summaries: list[dict[str, Any]] = []
    for batch, start, end in (
        ("001", "2026-06-30", "2026-07-12"),
        ("002", "2026-07-05", "2026-07-19"),
    ):
        output_root = tmp_path / batch
        assert (
            main(
                [
                    "acquisition",
                    "discover-courtlistener",
                    "--eligibility-anchor",
                    "2026-06-30",
                    "--search-window-start",
                    start,
                    "--search-window-end",
                    end,
                    "--output-root",
                    str(output_root),
                ]
            )
            == 0
        )
        summaries.append(
            _read_json(output_root / "courtlistener-discovery-summary.json")
        )

    assert [summary["anchor_date"] for summary in summaries] == [
        "2026-06-30",
        "2026-06-30",
    ]
    assert summaries[1]["search_window_start"] == "2026-07-05"
    assert summaries[1]["search_window_end"] == "2026-07-19"


def test_discovery_rejects_reversed_search_window(tmp_path: Path, capsys: Any) -> None:
    assert (
        main(
            [
                "acquisition",
                "discover-courtlistener",
                "--eligibility-anchor",
                "2026-06-30",
                "--search-window-start",
                "2026-07-12",
                "--search-window-end",
                "2026-07-11",
                "--output-root",
                str(tmp_path / "output"),
            ]
        )
        == 2
    )
    assert "cannot precede" in capsys.readouterr().err


def test_discover_courtlistener_live_requires_token(
    tmp_path: Path,
    capsys: Any,
    monkeypatch: Any,
) -> None:
    monkeypatch.delenv("COURTLISTENER_API_TOKEN", raising=False)

    assert (
        main(
            [
                "acquisition",
                "discover-courtlistener",
                "--eligibility-anchor",
                "2026-06-30",
                "--search-window-start",
                "2026-06-30",
                "--search-window-end",
                "2026-07-12",
                "--output-root",
                str(tmp_path / "output"),
                "--live",
                "--execute",
            ]
        )
        == 2
    )
    assert "COURTLISTENER_API_TOKEN is required" in capsys.readouterr().err


def test_discover_courtlistener_firecrawl_html_requires_live_search(
    tmp_path: Path,
    capsys: Any,
) -> None:
    assert (
        main(
            [
                "acquisition",
                "discover-courtlistener",
                "--eligibility-anchor",
                "2026-06-30",
                "--search-window-start",
                "2026-07-11",
                "--search-window-end",
                "2026-07-14",
                "--output-root",
                str(tmp_path / "output"),
                "--live-firecrawl-docket-html",
                "--execute",
            ]
        )
        == 2
    )
    assert "--live-firecrawl-docket-html requires --live" in capsys.readouterr().err


def test_discover_courtlistener_firecrawl_html_requires_key(
    tmp_path: Path,
    capsys: Any,
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("COURTLISTENER_API_TOKEN", "fixture-token")
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)

    assert (
        main(
            [
                "acquisition",
                "discover-courtlistener",
                "--eligibility-anchor",
                "2026-06-30",
                "--search-window-start",
                "2026-07-11",
                "--search-window-end",
                "2026-07-14",
                "--output-root",
                str(tmp_path / "output"),
                "--live",
                "--live-firecrawl-docket-html",
                "--execute",
            ]
        )
        == 2
    )
    assert "FIRECRAWL_API_KEY" in capsys.readouterr().err


def test_discover_courtlistener_records_local_validation_failure(
    tmp_path: Path,
    capsys: Any,
) -> None:
    output_root = tmp_path / "output"
    fixture_path = tmp_path / "courtlistener.jsonl"
    fixture_path.write_text("", encoding="utf-8")
    html_fixture_dir = tmp_path / "html-fixtures"
    html_fixture_dir.mkdir()

    assert (
        main(
            [
                "acquisition",
                "discover-courtlistener",
                "--eligibility-anchor",
                "2026-06-30",
                "--search-window-start",
                "2026-06-30",
                "--search-window-end",
                "2026-07-12",
                "--search-page-size",
                "101",
                "--courtlistener-fixture",
                str(fixture_path),
                "--docket-html-fixture-dir",
                str(html_fixture_dir),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 2
    )

    expected_reason = "search_page_size must be between 1 and 100"
    assert expected_reason in capsys.readouterr().err
    failure = _read_json(output_root / "run-cards" / "discover-courtlistener.json")
    assert failure["status"] == "failed"
    assert failure["failure_reason"] == expected_reason
    assert failure["paid_activity_executed"] is False


@pytest.mark.parametrize(
    ("changed_flag", "changed_value"),
    (
        ("--target-clean-cases", "2"),
        ("--max-candidates", "10"),
    ),
)
def test_discover_courtlistener_rejects_batch_limit_drift(
    tmp_path: Path,
    capsys: Any,
    changed_flag: str,
    changed_value: str,
) -> None:
    args = _cycle_store_discovery_args(tmp_path)
    assert main(args) == 0

    changed_args = [*args]
    changed_args[changed_args.index(changed_flag) + 1] = changed_value
    assert main(changed_args) == 2
    assert "batch config mismatch" in capsys.readouterr().err


def test_discover_courtlistener_invalid_limits_do_not_freeze_batch(
    tmp_path: Path,
    capsys: Any,
) -> None:
    args = _cycle_store_discovery_args(tmp_path)
    invalid_args = [*args]
    invalid_args[invalid_args.index("--search-page-size") + 1] = "101"

    assert main(invalid_args) == 2
    assert "search_page_size must be between 1 and 100" in capsys.readouterr().err

    assert main(args) == 0


def _cycle_store_discovery_args(tmp_path: Path) -> list[str]:
    fixture_path = tmp_path / "courtlistener.jsonl"
    _write_jsonl(
        fixture_path,
        [
            _response(
                path="/search/",
                params={
                    "q": '"test" AND entry_date_filed:[2026-06-30 TO 2026-07-12]',
                    "type": "r",
                    "order_by": "score desc",
                    "available_only": "on",
                    "page_size": 50,
                },
                payload={"results": [], "next": None},
            )
        ],
    )
    html_fixture_dir = tmp_path / "html-fixtures"
    html_fixture_dir.mkdir(exist_ok=True)
    return [
        "acquisition",
        "discover-courtlistener",
        "--eligibility-anchor",
        "2026-06-30",
        "--search-window-start",
        "2026-06-30",
        "--search-window-end",
        "2026-07-12",
        "--cycle-store",
        str(tmp_path / "cycle.sqlite3"),
        "--batch-id",
        "batch-001",
        "--query-term",
        "test",
        "--target-clean-cases",
        "1",
        "--max-candidates",
        "5",
        "--search-page-size",
        "50",
        "--courtlistener-fixture",
        str(fixture_path),
        "--docket-html-fixture-dir",
        str(html_fixture_dir),
        "--output-root",
        str(tmp_path / "output"),
        "--execute",
    ]


def _response(
    *,
    path: str,
    payload: dict[str, object],
    params: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "method": "GET",
        "path": path,
        "params": {} if params is None else params,
        "status_code": 200,
        "payload": payload,
    }


def _docket_html(*, decision_dates: tuple[str, ...]) -> str:
    decision_rows = "".join(
        _entry_html(
            number=16 + index,
            filed_at=filed_at,
            text="ORDER granting in part and denying in part Motion to Dismiss",
            description="Order on Motion to Dismiss",
        )
        for index, filed_at in enumerate(decision_dates)
    )
    return (
        "<html><head><title>Fixture v. Example</title></head><body>"
        '<div id="docket-entry-table">'
        + _entry_html(
            number=1,
            filed_at="January 2, 2026",
            text="COMPLAINT filed by Plaintiff",
            description="Complaint",
        )
        + _entry_html(
            number=5,
            filed_at="February 2, 2026",
            text="MOTION to Dismiss filed by Defendant",
            description="Motion to Dismiss",
            extra_document_description="Memorandum in Support of Motion to Dismiss",
        )
        + decision_rows
        + "</div></body></html>"
    )


def _entry_html(
    *,
    number: int,
    filed_at: str,
    text: str,
    description: str,
    extra_document_description: str | None = None,
) -> str:
    extra_document = (
        ""
        if extra_document_description is None
        else (
            '<div class="row recap-documents"><div>Attachment 1</div>'
            f"<div>{extra_document_description}</div>"
            f'<a href="https://storage.courtlistener.com/{number}-memo.pdf">'
            "Download PDF</a></div>"
        )
    )
    return (
        f'<div class="row" id="entry-{number}">'
        f'<div class="col-xs-1">{number}</div>'
        f'<div class="col-xs-3"><span title="{filed_at}">{filed_at}</span></div>'
        f'<div class="col-xs-8">{text}'
        '<div class="recap-documents">'
        "<div>Main Document</div>"
        f"<div>{description}</div>"
        f'<a href="https://storage.courtlistener.com/{number}.pdf">Download PDF</a>'
        f"</div>{extra_document}</div></div>"
    )


def _screen_custom_docket(
    *,
    entries: tuple[tuple[int, str, str], ...],
) -> tuple[dict[str, Any] | None, Any]:
    html = (
        "<html><head><title>Fixture v. Example</title></head><body>"
        '<div id="docket-entry-table">'
        + "".join(
            _entry_html(
                number=number,
                filed_at=filed_at,
                text=text,
                description=text,
            )
            for number, filed_at, text in entries
        )
        + "</div></body></html>"
    )
    docket = CourtListenerDocket(
        docket_id="123",
        court_id="nysd",
        docket_number="1:26-cv-00001",
        case_name="Fixture v. Example",
        date_filed="2026-01-02",
        source_url="https://www.courtlistener.com/docket/123/fixture-v-example/",
        raw={},
    )
    metadata_screen = screen_case_dev_docket_metadata(
        {
            "id": "123",
            "courtId": "nysd",
            "court": "District Court, S.D. New York",
            "docketNumber": "1:26-cv-00001",
            "caseName": "Fixture v. Example",
        }
    )
    page = parse_courtlistener_docket_html(
        html,
        source_url=docket.source_url,
        docket_id=docket.docket_id,
    )
    screened, exclusion = screen_courtlistener_docket_page(
        docket=docket,
        metadata_screen=metadata_screen,
        page=page,
        decision_filed_on_or_after=date(2026, 6, 30),
    )
    return (None if screened is None else dict(screened)), exclusion


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _rewrite_snapshot_jsonl(
    snapshot: Path, filename: str, records: list[dict[str, object]]
) -> None:
    payload = b"".join(
        json.dumps(record, sort_keys=True, separators=(",", ":")).encode() + b"\n"
        for record in records
    )
    (snapshot / filename).write_bytes(payload)
    manifest_path = snapshot / "manifest.json"
    manifest = _read_json(manifest_path)
    files = cast(dict[str, object], manifest["files"])
    files[filename] = {
        "sha256": hashlib.sha256(payload).hexdigest(),
        "byte_count": len(payload),
        "row_count": len(records),
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")


def _run_saturated_discovery(
    tmp_path: Path,
    *,
    target_clean_cases: int = 2,
    max_candidates: int = 5,
    next_cursor: str | None = None,
    reuse_fixtures: bool = False,
) -> tuple[Path, Path]:
    output_root = tmp_path / "discovery"
    cycle_store = tmp_path / "cycle.sqlite3"
    fixture_path = tmp_path / "courtlistener.jsonl"
    html_fixture_dir = tmp_path / "html-fixtures"
    html_fixture_dir.mkdir(exist_ok=reuse_fixtures)
    (html_fixture_dir / "123.html").write_text(
        _docket_html(decision_dates=("June 30, 2026",)),
        encoding="utf-8",
    )
    _write_jsonl(
        fixture_path,
        [
            _response(
                path="/search/",
                params={
                    "q": (
                        '"order on motion to dismiss" AND '
                        "entry_date_filed:[2026-06-30 TO 2026-07-12]"
                    ),
                    "type": "r",
                    "order_by": "score desc",
                    "available_only": "on",
                    "page_size": 50,
                },
                payload={
                    "results": [
                        {
                            "docket_id": 123,
                            "docket_entry_id": 16,
                            "description": "Order on motion to dismiss",
                            "entry_date_filed": "2026-06-30",
                        }
                    ],
                    "next": next_cursor,
                },
            ),
            _response(
                path="/dockets/123/",
                payload={
                    "id": 123,
                    "court": "nysd",
                    "docket_number": "1:26-cv-00001",
                    "case_name": "Fixture v. Example",
                    "absolute_url": (
                        "https://www.courtlistener.com/docket/123/fixture-v-example/"
                    ),
                },
            ),
        ],
    )
    assert (
        main(
            [
                "acquisition",
                "discover-courtlistener",
                "--eligibility-anchor",
                "2026-06-30",
                "--search-window-start",
                "2026-06-30",
                "--search-window-end",
                "2026-07-12",
                "--cycle-store",
                str(cycle_store),
                "--batch-id",
                "batch-001",
                "--query-term",
                "order on motion to dismiss",
                "--target-clean-cases",
                str(target_clean_cases),
                "--max-candidates",
                str(max_candidates),
                "--courtlistener-fixture",
                str(fixture_path),
                "--docket-html-fixture-dir",
                str(html_fixture_dir),
                "--output-root",
                str(output_root),
                "--execute",
            ]
        )
        == 0
    )
    return output_root, cycle_store


def _materialize_discovery(
    *,
    tmp_path: Path,
    discovery_root: Path,
    cycle_store: Path,
    snapshot_id: str = "courtlistener-complete",
) -> Path:
    snapshot_root = tmp_path / "snapshots"
    assert (
        main(
            _materialize_command(
                tmp_path=tmp_path,
                discovery_root=discovery_root,
                cycle_store=cycle_store,
                snapshot_id=snapshot_id,
            )
        )
        == 0
    )
    return snapshot_root / snapshot_id


def _materialize_command(
    *,
    tmp_path: Path,
    discovery_root: Path,
    cycle_store: Path,
    snapshot_id: str = "courtlistener-complete",
) -> list[str]:
    run_card = discovery_root / "run-cards" / "discover-courtlistener.json"
    return [
        "acquisition",
        "materialize-courtlistener-snapshot",
        "--cycle-store",
        str(cycle_store),
        "--batch-id",
        "batch-001",
        "--discovery-run-card",
        str(run_card),
        "--expected-discovery-run-card-sha256",
        hashlib.sha256(run_card.read_bytes()).hexdigest(),
        "--snapshot-root",
        str(tmp_path / "snapshots"),
        "--snapshot-id",
        snapshot_id,
        "--output-root",
        str(tmp_path / "materialization"),
        "--execute",
    ]


def _create_old_replay_snapshot(
    *,
    tmp_path: Path,
    discovery_root: Path,
    cycle_store: Path,
) -> Path:
    [source_record] = _read_jsonl(discovery_root / "courtlistener-screened-cases.jsonl")
    record = json.loads(json.dumps(source_record))
    record["candidate"]["docket_id"] = "124"
    record["candidate"]["candidate_key"] = "124"
    record["candidate"]["metadata"]["case_id"] = "124"
    record["candidate"]["metadata"]["docket_number"] = "1:26-cv-00002"
    record["candidate"]["url"] = (
        "https://www.courtlistener.com/docket/124/old-v-example/"
    )
    record["candidate_id"] = "124"
    raw_path = tmp_path / "old-raw" / "124.html"
    raw_path.parent.mkdir()
    raw_path.write_bytes(
        (discovery_root / "raw-courtlistener-html" / "123.html").read_bytes()
    )
    snapshot_root = tmp_path / "old-snapshots"
    with CycleAcquisitionStore(cycle_store) as store:
        store.ensure_batch("old-replay", {"provider": "provider-free-old-replay"})
        store.ensure_terms("old-replay", ("old-replay",))
        store.commit_search_page(
            "old-replay",
            "old-replay",
            None,
            [
                DiscoveryHit(
                    provider_hit_id="old:124",
                    candidate_id="124",
                    payload={"source": "old-replay"},
                )
            ],
            next_cursor=None,
            terminal_status=TermTerminalStatus.EXHAUSTED,
        )
        store.write_raw_artifact(
            "124",
            raw_path,
            raw_path.read_bytes(),
            retrieved_at="2026-07-14T00:00:00Z",
        )
        store.record_observation(
            "124",
            batch_id="old-replay",
            state="accepted",
            reason_code="strict_clean_screen_passed",
            evidence=record,
            observed_at="2026-06-30T00:00:00Z",
        )
        return store.export_snapshot(
            snapshot_root,
            snapshot_id="old-replay",
            batch_id="old-replay",
            complete=True,
        )


def _fixture_pdf_text(text: str) -> str:
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET"
    body = stream.encode("utf-8")
    objects = [
        "1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj",
        "2 0 obj << /Type /Pages /Count 1 /Kids [] >> endobj",
        "3 0 obj << /Type /Page /Contents 23 0 R >> endobj",
        f"23 0 obj << /Length {len(body)} >> stream\n{stream}\nendstream endobj",
    ]
    return "%PDF-1.4\n" + "\n".join(objects) + "\n%%EOF"


def _manifest_sha256(snapshot: Path) -> str:
    return hashlib.sha256((snapshot / "manifest.json").read_bytes()).hexdigest()


def _complete_snapshot(
    root: Path,
    screened_records: list[dict[str, object]],
    *,
    raw_html_dir: Path,
) -> tuple[Path, str]:
    batch_id = "courtlistener-fixture"
    term = "fixture-term"
    with CycleAcquisitionStore(root / "cycle-acquisition.sqlite3") as store:
        cycle_hash = store.ensure_cycle(
            {"eligibility_anchor": "2026-06-30", "fixture": True}
        )
        store.ensure_batch(batch_id, {"fixture": "courtlistener"})
        store.ensure_terms(batch_id, [term])
        hits_list: list[DiscoveryHit] = []
        for index, record in enumerate(screened_records):
            candidate = cast(dict[str, object], record["candidate"])
            candidate_id = candidate["docket_id"]
            assert isinstance(candidate_id, str)
            hits_list.append(
                DiscoveryHit(
                    provider_hit_id=f"fixture-hit-{index}",
                    candidate_id=candidate_id,
                    payload={"fixture_index": index},
                )
            )
        hits = tuple(hits_list)
        store.commit_search_page(
            batch_id,
            term,
            None,
            hits,
            next_cursor=None,
            terminal_status=TermTerminalStatus.EXHAUSTED,
        )
        for hit, record in zip(hits, screened_records, strict=True):
            store.record_observation(
                hit.candidate_id,
                batch_id=batch_id,
                state="accepted",
                reason_code="strict_clean_screen_passed",
                evidence=record,
            )
            raw_html_path = raw_html_dir / f"{hit.candidate_id}.html"
            store.write_raw_artifact(
                hit.candidate_id,
                raw_html_path,
                raw_html_path.read_bytes(),
                retrieved_at="2026-07-12T12:00:00Z",
            )
        snapshot_path = store.export_snapshot(
            root / "snapshots",
            snapshot_id="complete-fixture",
            batch_id=batch_id,
            complete=True,
        )
    return snapshot_path, cycle_hash


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
