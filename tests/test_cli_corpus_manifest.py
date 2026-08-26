from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import pytest
from legalforecast import cli as cli_module
from legalforecast.cli_commands import corpus_manifest as corpus_manifest_cli
from legalforecast.testing.cli_corpus.command_manifest import (
    build_command_manifest,
    command_paths,
    handler_ids,
    preparser_bypass_paths_from_source,
)
from legalforecast.testing.cli_corpus.help_snapshots import (
    HELP_SNAPSHOTS,
    capture_help,
    load_help_snapshots,
)
from legalforecast.testing.cli_corpus.paths import MANIFEST_PATH, load_json

ROOT = Path(__file__).resolve().parents[1]


def test_command_manifest_is_deterministic() -> None:
    first = build_command_manifest()
    second = build_command_manifest()
    assert first == second


def test_command_manifest_matches_checked_in_fixture() -> None:
    generated = build_command_manifest()
    checked_in = load_json(ROOT / MANIFEST_PATH)
    assert generated == checked_in


def test_command_manifest_covers_documented_families() -> None:
    manifest = build_command_manifest()
    paths = {path for path in command_paths(manifest)}
    for required in (
        (),
        ("discover",),
        ("acquisition",),
        ("batch-002",),
        ("packet", "build"),
        ("packet-build",),
        ("eval", "run"),
        ("multiharness", "run"),
        ("freeze",),
        ("freeze", "verify"),
        ("publish", "aggregate"),
        ("publish", "site"),
    ):
        assert required in paths
    assert "discover" in handler_ids(manifest)
    assert "publish.aggregate" in handler_ids(manifest)
    assert "freeze.verify" in handler_ids(manifest)


def test_hyphenated_aliases_share_logical_handlers() -> None:
    manifest = build_command_manifest()
    commands = {
        tuple(record["path"]): record
        for record in manifest["commands"]
        if isinstance(record, dict)
    }
    packet_build = commands[("packet-build",)]["handler"]
    nested = commands[("packet", "build")]["handler"]
    assert packet_build == nested
    fixture = commands[("fixture-e2e",)]["handler"]
    nested_fixture = commands[("fixture", "e2e")]["handler"]
    assert fixture == nested_fixture


def test_preparser_bypasses_remain_in_cli_main() -> None:
    assert preparser_bypass_paths_from_source(ROOT) == (
        ("freeze",),
        ("publish", "aggregate"),
    )


def test_help_snapshots_are_byte_stable_at_pinned_width() -> None:
    generated = {name: capture_help(argv) for name, argv in HELP_SNAPSHOTS}
    checked_in = load_help_snapshots(ROOT)
    assert generated == checked_in
    assert capture_help(("--help",)) == capture_help(("--help",))
    assert "LegalForecast-MTD benchmark utilities" in generated["root"]
    assert "--model-registry" in generated["publish-aggregate"]
    assert "cycle_id" in generated["freeze"]


def test_manifest_records_registration_order_and_dest_values() -> None:
    manifest = build_command_manifest()
    commands = [
        record
        for record in manifest["commands"]
        if isinstance(record, dict) and record["path"]
    ]
    indexes = [int(record["registration_index"]) for record in commands]
    assert indexes == list(range(1, len(commands) + 1))
    discover = next(record for record in commands if record["path"] == ["discover"])
    option_dests = {option["dest"] for option in discover["options"]}
    assert {"input", "output", "dry_run"} <= option_dests
    assert discover["group_dest"] == "command"
    assert discover["logical_handler_id"] == "discover"
    handler = discover["handler"]
    assert handler["name"] == "_cmd_discover"
    payload = json.dumps(discover, sort_keys=True)
    assert "dest" in payload


def test_execution_scope_verify_cli_uses_frozen_sources_without_authority_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scope_path = tmp_path / "scope.json"
    scope_path.write_text("{}\n", encoding="utf-8")
    paths = {
        "scope": scope_path,
        "plan": tmp_path / "plan.json",
        "freeze_bundle": tmp_path / "freeze.json",
        "model_registry": tmp_path / "registry.json",
        "cost_projection": tmp_path / "cost.json",
        "run_input_manifest": tmp_path / "run-inputs.json",
        "owner_evidence": tmp_path / "owner.json",
        "provider_cycle_caps": tmp_path / "caps.json",
    }
    argv = [
        "acquisition",
        "verify-manifest-execution-scope",
        "--scope",
        str(paths["scope"]),
        "--plan",
        str(paths["plan"]),
        "--freeze-bundle",
        str(paths["freeze_bundle"]),
        "--model-registry",
        str(paths["model_registry"]),
        "--cost-projection",
        str(paths["cost_projection"]),
        "--run-input-manifest",
        str(paths["run_input_manifest"]),
        "--owner-evidence",
        str(paths["owner_evidence"]),
        "--provider-cycle-caps",
        str(paths["provider_cycle_caps"]),
        "--model-key",
        "openai:test-2026",
    ]
    parsed = cli_module.build_parser().parse_args(argv)
    assert not hasattr(parsed, "provider_authority")

    calls: dict[str, object] = {}

    def fake_verify(artifact: Mapping[str, Any], **kwargs: Any) -> str:
        calls["artifact"] = artifact
        calls["kwargs"] = kwargs
        return "a" * 64

    class _EntryPoint:
        def load(self) -> Any:
            return fake_verify

    monkeypatch.setattr(corpus_manifest_cli, "_VERIFY_EXECUTION_SCOPE", _EntryPoint())
    assert cast(Any, parsed.handler)(parsed) == 0
    assert calls["artifact"] == {}
    assert "provider_authority" not in cast(dict[str, Any], calls["kwargs"])
    assert (
        cast(dict[str, Any], calls["kwargs"])["provider_cycle_caps"]
        == paths["provider_cycle_caps"]
    )

    with pytest.raises(SystemExit):
        cli_module.build_parser().parse_args([*argv, "--provider-authority", "{}"])
