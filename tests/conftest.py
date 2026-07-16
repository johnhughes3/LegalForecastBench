from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import legalforecast.cli as cli
import pytest
from legalforecast.ingestion.case_dev_config import case_dev_live_skip_reason

COURTLISTENER_LIVE_ENV = "LFB_COURTLISTENER_LIVE"
_MATERIALIZATION_SCHEMA = "legalforecast.cohort_document_materialization.v1"


@dataclass(frozen=True)
class _MaterializationBinding:
    run_card: Path
    manifest: Path
    clearance: Path
    document_root: Path
    selection: Path | None


class AuthenticatedDownstreamFixture:
    """Narrow unit fixture for gates covered by the target-100 materializer E2E.

    The fixture does not imitate the canonical materializer. It adds the real
    materialization markers, commits the exact files used by the downstream
    test, and replaces only the expensive source-chain replay with an exact
    path-binding check. The target-100 materializer E2E exercises that replay.
    """

    def __init__(self, *, monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
        self._root = root
        self._bindings: list[_MaterializationBinding] = []
        monkeypatch.setattr(
            cli,
            "_verify_materialized_downstream_lineage",
            self._verify_binding,
        )
        monkeypatch.setattr(
            cli,
            "_validate_packet_input_run_card",
            lambda *args, **kwargs: cli._PacketPlannerReplay(
                packet_build_records=tuple(
                    _read_jsonl(kwargs["packet_build_input_path"])
                ),
                packet_build_input_sha256=cli._path_sha256(
                    kwargs["packet_build_input_path"]
                ),
                selection_records=tuple(_read_jsonl(kwargs["selection_path"])),
                download_records=tuple(_read_jsonl(kwargs["download_manifest_path"])),
                parser_records=tuple(_read_jsonl(kwargs["parser_manifest_path"])),
                clearance_records=tuple(_read_jsonl(kwargs["clearance_path"])),
                clearance_sha256=cli._path_sha256(kwargs["clearance_path"]),
                parser_manifest_sha256=cli._path_sha256(kwargs["parser_manifest_path"]),
                parser_record_count=len(_read_jsonl(kwargs["parser_manifest_path"])),
                prediction_unit_records=tuple(
                    _read_jsonl(kwargs["prediction_units_path"])
                ),
                model_registry=cli.load_model_registry(kwargs["model_registry_path"]),
                model_registry_sha256=cli._path_sha256(kwargs["model_registry_path"]),
            ),
        )
        monkeypatch.setattr(
            cli,
            "_verify_packet_raw_artifacts_snapshot_binding",
            lambda **kwargs: None,
        )
        monkeypatch.setattr(
            cli,
            "_authenticated_materialization_snapshot_manifest_path",
            lambda *args, **kwargs: self._bindings[-1].run_card,
        )
        monkeypatch.setattr(
            cli,
            "_verify_parser_packet_authority",
            lambda **kwargs: None,
        )
        monkeypatch.setattr(
            cli,
            "_verify_stage_a_packet_authority",
            lambda **kwargs: cli._StageAReplay(
                raw_prediction_unit_records=tuple(
                    _read_jsonl(kwargs["raw_prediction_units_path"])
                ),
                unitization_audit_records=tuple(
                    _read_jsonl(kwargs["unitization_audit_path"])
                ),
                original_review_records=tuple(
                    _read_jsonl(kwargs["original_review_path"])
                ),
                structural_flag_records=tuple(
                    _read_jsonl(kwargs["structural_flags_path"])
                ),
                structural_review_audit_records=tuple(
                    _read_jsonl(kwargs["structural_review_audit_path"])
                ),
                merged_review_records=tuple(_read_jsonl(kwargs["merged_review_path"])),
                adjudication_records=tuple(_read_jsonl(kwargs["adjudications_path"])),
            ),
        )

    def materialize(
        self,
        *,
        manifest: Path,
        clearance: Path,
        document_root: Path,
        name: str,
        selection: Path | None = None,
    ) -> Path:
        """Mark exact fixture records and bind their downstream lineage paths."""

        for path in (manifest, clearance):
            records = _read_jsonl(path)
            _write_jsonl(
                path,
                [
                    {
                        **record,
                        "materialization_schema_version": _MATERIALIZATION_SCHEMA,
                    }
                    for record in records
                ],
            )
        lineage_root = self._root / "authenticated-downstream" / name
        lineage_root.mkdir(parents=True, exist_ok=True)
        restrictions = lineage_root / "restriction-evidence.jsonl"
        derivations = lineage_root / "materialization-derivations.jsonl"
        summary = lineage_root / "cohort-document-materialization.json"
        restrictions.write_text("\n", encoding="utf-8")
        derivations.write_text("\n", encoding="utf-8")
        summary.write_text("{}\n", encoding="utf-8")
        run_card = lineage_root / "materialize-cohort-documents.json"
        run_card.write_text(
            json.dumps(
                {
                    "schema_version": "legalforecast.acquisition_run_card.v1",
                    "stage": "materialize-cohort-documents",
                    "status": "completed",
                    "output_paths": [
                        str(manifest.resolve()),
                        str(clearance.resolve()),
                        str(restrictions.resolve()),
                        str(derivations.resolve()),
                        str(summary.resolve()),
                        str(document_root.resolve()),
                    ],
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        self._bindings.append(
            _MaterializationBinding(
                run_card=run_card.resolve(),
                manifest=manifest.resolve(),
                clearance=clearance.resolve(),
                document_root=document_root.resolve(),
                selection=selection.resolve() if selection is not None else None,
            )
        )
        return run_card

    def write_packet_planner_card(
        self,
        path: Path,
        *,
        packet_input: Path,
        selection: Path,
        manifest: Path,
        clearance: Path,
        document_root: Path,
        materialization_run_card: Path,
    ) -> None:
        """Commit reviewed packet-input bytes with the production card schema."""

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "schema_version": "legalforecast.acquisition_run_card.v1",
                    "stage": "plan-packet-inputs",
                    "status": "completed",
                    "dry_run": False,
                    "execute": True,
                    "paid_activity_requested": False,
                    "paid_activity_executed": False,
                    "authenticated_materialization_lineage": (
                        cli._packet_materialization_lineage_commitments(
                            selection_path=selection,
                            download_manifest_path=manifest,
                            clearance_path=clearance,
                            document_root=document_root,
                            materialization_run_card_path=materialization_run_card,
                        )
                    ),
                    "output_commitments": {
                        "packet_build_input": {
                            "path": str(packet_input.resolve()),
                            "sha256": "sha256:"
                            + hashlib.sha256(packet_input.read_bytes()).hexdigest(),
                        }
                    },
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    def _verify_binding(self, **kwargs: Any) -> tuple[Path, ...]:
        requested = _MaterializationBinding(
            run_card=Path(kwargs["run_card_path"]).resolve(),
            manifest=Path(kwargs["manifest_path"]).resolve(),
            clearance=Path(kwargs["clearance_path"]).resolve(),
            document_root=Path(kwargs["document_root"]).resolve(),
            selection=(
                Path(kwargs["selection_path"]).resolve()
                if kwargs.get("selection_path") is not None
                else None
            ),
        )
        if requested not in self._bindings:
            raise AssertionError(
                f"unbound materialization fixture request: {requested}"
            )
        return (requested.run_card,)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


@pytest.fixture
def authenticated_downstream_fixture(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> AuthenticatedDownstreamFixture:
    return AuthenticatedDownstreamFixture(monkeypatch=monkeypatch, root=tmp_path)


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "case_dev_live: marks tests that call the live case.dev API",
    )
    config.addinivalue_line(
        "markers",
        "courtlistener_live: marks tests that call the live CourtListener REST API",
    )


def courtlistener_live_skip_reason() -> str | None:
    """Return a skip reason unless live CourtListener API access is opted in.

    CI never sets ``LFB_COURTLISTENER_LIVE``, so these network-touching smoke
    tests are skipped by default and only run when an operator explicitly opts
    in for a bounded, hand-spaced anonymous validation.
    """

    if os.environ.get(COURTLISTENER_LIVE_ENV, "").strip().lower() in {
        "1",
        "true",
        "yes",
    }:
        return None
    return f"set {COURTLISTENER_LIVE_ENV}=1 to run live CourtListener smoke tests"


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    case_dev_reason = case_dev_live_skip_reason()
    courtlistener_reason = courtlistener_live_skip_reason()
    for item in items:
        if case_dev_reason is not None and "case_dev_live" in item.keywords:
            item.add_marker(pytest.mark.skip(reason=case_dev_reason))
        if courtlistener_reason is not None and "courtlistener_live" in item.keywords:
            item.add_marker(pytest.mark.skip(reason=courtlistener_reason))
