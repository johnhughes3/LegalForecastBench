from __future__ import annotations

from pathlib import Path

from legalforecast.testing.cli_corpus.command_manifest import (
    build_command_manifest,
    command_paths,
    handler_ids,
    preparser_bypass_paths_from_source,
)
from legalforecast.testing.cli_corpus.help_snapshots import (
    capture_help,
    load_help_snapshots,
)
from legalforecast.testing.cli_corpus.paths import MANIFEST_PATH, load_json

ROOT = Path(__file__).resolve().parents[1]


def test_command_manifest_is_deterministic_and_checked_in() -> None:
    generated = build_command_manifest()
    assert generated == build_command_manifest()
    assert generated == load_json(ROOT / MANIFEST_PATH)


def test_manifest_contains_only_supported_public_families() -> None:
    manifest = build_command_manifest()
    paths = set(command_paths(manifest))
    for required in (
        (),
        ("manifest",),
        ("manifest", "validate"),
        ("release", "validate"),
        ("run", "execute"),
        ("score",),
        ("report",),
        ("publish", "aggregate"),
        ("publish", "site"),
        ("multiharness", "run"),
    ):
        assert required in paths
    for retired in ("acquisition", "batch-002", "discover", "freeze", "eval"):
        assert not any(path and path[0] == retired for path in paths)
    ids = set(handler_ids(manifest))
    assert "manifest.validate" in ids
    assert "publish.site" in ids


def test_only_publication_aggregate_keeps_a_preparser_bypass() -> None:
    assert preparser_bypass_paths_from_source(ROOT) == (("publish", "aggregate"),)


def test_help_snapshots_are_current_and_byte_stable() -> None:
    generated = {
        name: capture_help(argv)
        for name, argv in (
            ("root", ("--help",)),
            ("manifest", ("manifest", "--help")),
            ("release", ("release", "--help")),
            ("run", ("run", "--help")),
            ("score", ("score", "--help")),
            ("report", ("report", "--help")),
            ("publish-aggregate", ("publish", "aggregate", "--help")),
            ("multiharness", ("multiharness", "--help")),
        )
    }
    assert generated == load_help_snapshots(ROOT)
    assert "LegalForecast-MTD benchmark utilities" in generated["root"]
    assert "acquisition" not in generated["root"]


def test_manifest_registration_indexes_are_contiguous() -> None:
    records = [
        record
        for record in build_command_manifest()["commands"]
        if isinstance(record, dict) and record["path"]
    ]
    assert [int(record["registration_index"]) for record in records] == list(
        range(1, len(records) + 1)
    )
