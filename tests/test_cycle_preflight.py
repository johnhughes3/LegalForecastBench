from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import cast

import pytest
from legalforecast.ingestion import cycle_preflight
from legalforecast.ingestion.cycle_preflight import main, verify_cycle_manifest

_CAPSULE = Path("tests/fixtures/cycle-preflight/manifest.json")


def _recommit_manifest_artifact(capsule: Path, node_id: str, name: str) -> None:
    manifest_path = capsule / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    node = next(item for item in manifest["nodes"] if item["id"] == node_id)
    artifact = next(item for item in node["artifacts"] if item["name"] == name)
    digest = hashlib.sha256((capsule / artifact["path"]).read_bytes()).hexdigest()
    for candidate_node in manifest["nodes"]:
        for candidate in candidate_node["artifacts"]:
            if candidate["path"] == artifact["path"]:
                candidate["sha256"] = digest
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n")


def test_public_capsule_passes_with_stable_json_and_text(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--manifest", str(_CAPSULE), "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert [node["id"] for node in payload["nodes"]] == [
        "recovery",
        "purchase-baseline",
        "clearance",
        "resolution",
        "replacement-recovery-source",
    ]
    assert {node["status"] for node in payload["nodes"]} == {"PASSED"}

    assert main(["--manifest", str(_CAPSULE), "--format", "text"]) == 0
    assert capsys.readouterr().out == (
        "PASS recovery\n"
        "PASS purchase-baseline\n"
        "PASS clearance\n"
        "PASS resolution\n"
        "PASS replacement-recovery-source\n"
        "VERDICT PASS nodes=5 issues=0\n"
    )


def test_collect_all_reports_independent_defects_and_blocks_descendants(
    tmp_path: Path,
) -> None:
    capsule = tmp_path / "capsule"
    shutil.copytree(_CAPSULE.parent, capsule)
    (capsule / "selection.jsonl").write_text('{"candidate_id":"changed"}\n')
    before = json.loads((capsule / "purchase-before.json").read_text())
    before["purchase_state_sha256"] = "0" * 64
    (capsule / "purchase-before.json").write_text(
        json.dumps(before, sort_keys=True) + "\n"
    )

    result = verify_cycle_manifest(capsule / "manifest.json")

    assert result.ok is False
    assert [(node.node_id, node.status) for node in result.nodes] == [
        ("recovery", "FAILED"),
        ("purchase-baseline", "FAILED"),
        ("clearance", "NOT_EVALUATED"),
        ("resolution", "NOT_EVALUATED"),
        ("replacement-recovery-source", "NOT_EVALUATED"),
    ]
    assert result.nodes[2].blocked_by == ("recovery",)
    assert result.nodes[3].blocked_by == ("clearance", "purchase-baseline")
    assert result.nodes[4].blocked_by == ("resolution",)
    failed = [issue.code for issue in result.issues if issue.status == "FAILED"]
    assert failed == ["ARTIFACT_SHA256_MISMATCH", "ARTIFACT_SHA256_MISMATCH"]


def test_purchase_snapshot_rejects_prefixed_state_digest(tmp_path: Path) -> None:
    capsule = tmp_path / "capsule"
    shutil.copytree(_CAPSULE.parent, capsule)
    before_path = capsule / "purchase-before.json"
    before = json.loads(before_path.read_text())
    before["purchase_state_sha256"] = "sha256:" + before["purchase_state_sha256"]
    before_path.write_text(json.dumps(before, sort_keys=True) + "\n")
    _recommit_manifest_artifact(capsule, "purchase-baseline", "purchase-before-json")

    result = verify_cycle_manifest(capsule / "manifest.json")

    purchase = result.nodes[1]
    assert purchase.status == "FAILED"
    assert purchase.issues[0].message == (
        "purchase baseline state is not a bare SHA-256 digest"
    )


def test_preflight_is_read_only_and_rejects_manifest_ambiguity(
    tmp_path: Path,
) -> None:
    capsule = tmp_path / "capsule"
    shutil.copytree(_CAPSULE.parent, capsule)
    before = {
        path.relative_to(capsule): path.read_bytes()
        for path in capsule.rglob("*")
        if path.is_file()
    }

    first = verify_cycle_manifest(capsule / "manifest.json").to_record()
    second = verify_cycle_manifest(capsule / "manifest.json").to_record()

    assert first == second
    assert before == {
        path.relative_to(capsule): path.read_bytes()
        for path in capsule.rglob("*")
        if path.is_file()
    }

    manifest = json.loads((capsule / "manifest.json").read_text())
    manifest["nodes"][1]["depends_on"] = ["replacement-recovery-source"]
    (capsule / "manifest.json").write_text(json.dumps(manifest, sort_keys=True) + "\n")
    assert main(["--manifest", str(capsule / "manifest.json")]) == 1


def test_card_commitment_must_match_manifest_authenticated_bytes(
    tmp_path: Path,
) -> None:
    capsule = tmp_path / "capsule"
    shutil.copytree(_CAPSULE.parent, capsule)
    card_path = capsule / "recovery-card.json"
    card = json.loads(card_path.read_text())
    card["source_commitments"]["selection"]["sha256"] = "sha256:" + "0" * 64
    card_path.write_text(json.dumps(card, sort_keys=True, separators=(",", ":")) + "\n")
    manifest_path = capsule / "manifest.json"
    _recommit_manifest_artifact(capsule, "recovery", "recovery-card-json")

    result = verify_cycle_manifest(manifest_path)

    assert result.nodes[0].status == "FAILED"
    assert result.nodes[0].issues[0].code == "SEMANTIC_REPLAY_FAILED"
    assert "selection commitment differs" in result.nodes[0].issues[0].message


def test_manifest_order_does_not_override_dependency_order(tmp_path: Path) -> None:
    capsule = tmp_path / "capsule"
    shutil.copytree(_CAPSULE.parent, capsule)
    manifest_path = capsule / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["nodes"].reverse()
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n")

    result = verify_cycle_manifest(manifest_path)

    assert result.ok is True

    positions = {node.node_id: index for index, node in enumerate(result.nodes)}
    assert positions["recovery"] < positions["clearance"] < positions["resolution"]
    assert positions["purchase-baseline"] < positions["resolution"]
    assert positions["resolution"] < positions["replacement-recovery-source"]


def test_stage_contract_rejects_unknown_validator_before_evaluation(
    tmp_path: Path,
) -> None:
    capsule = tmp_path / "capsule"
    shutil.copytree(_CAPSULE.parent, capsule)
    manifest_path = capsule / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["nodes"][0]["validator"]["kind"] = "future_validator"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n")

    assert main(["--manifest", str(manifest_path)]) == 1


@pytest.mark.parametrize("retained", [0, 4])
def test_manifest_requires_the_complete_recovery_slice(
    tmp_path: Path, retained: int
) -> None:
    capsule = tmp_path / "capsule"
    shutil.copytree(_CAPSULE.parent, capsule)
    manifest_path = capsule / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["nodes"] = manifest["nodes"][:retained]
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n")

    assert main(["--manifest", str(manifest_path)]) == 1


def test_malformed_declared_commitment_fails_closed(tmp_path: Path) -> None:
    capsule = tmp_path / "capsule"
    shutil.copytree(_CAPSULE.parent, capsule)
    card_path = capsule / "recovery-card.json"
    card = json.loads(card_path.read_text())
    card["source_commitments"]["selection"] = "not-a-commitment"
    card_path.write_text(json.dumps(card, sort_keys=True) + "\n")
    _recommit_manifest_artifact(capsule, "recovery", "recovery-card-json")

    result = verify_cycle_manifest(capsule / "manifest.json")

    assert result.nodes[0].status == "FAILED"
    assert "selection is malformed" in result.nodes[0].issues[0].message


def test_uncommitted_declared_input_fails_closed(tmp_path: Path) -> None:
    capsule = tmp_path / "capsule"
    shutil.copytree(_CAPSULE.parent, capsule)
    manifest_path = capsule / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    del manifest["nodes"][0]["validator"]["input_commitments"]
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n")

    result = verify_cycle_manifest(manifest_path)

    assert result.nodes[0].status == "FAILED"
    assert "input_paths contains uncommitted paths" in result.nodes[0].issues[0].message


def test_nonempty_terminal_partition_requires_authoritative_replay(
    tmp_path: Path,
) -> None:
    capsule = tmp_path / "capsule"
    shutil.copytree(_CAPSULE.parent, capsule)
    terminal_path = capsule / "empty-terminal.jsonl"
    terminal_path.write_text('{"source_document_id":"terminal-document"}\n')
    disposition_names = {
        "selection": "terminal-selection.jsonl",
        "snapshot_manifest": "terminal-snapshot.json",
        "purchase_result": "terminal-result.json",
        "purchase_run_card": "terminal-card.json",
    }
    for path in disposition_names.values():
        (capsule / path).write_text("{}\n")

    card_path = capsule / "resolution-card.json"
    card = json.loads(card_path.read_text())
    extra_paths = ["empty-terminal.jsonl", *disposition_names.values()]
    for path in extra_paths:
        index = len(card["input_paths"])
        card["input_paths"].append(path)
        commitment = {
            "path": path,
            "sha256": "sha256:"
            + hashlib.sha256((capsule / path).read_bytes()).hexdigest(),
        }
        card["source_commitments"][f"input_{index:02d}"] = commitment
    terminal_sha256 = "sha256:" + hashlib.sha256(terminal_path.read_bytes()).hexdigest()
    card["terminal_unavailable_partition"] = {
        "path": "empty-terminal.jsonl",
        "sha256": terminal_sha256,
        "record_count": 1,
    }
    card["terminal_disposition_sources"] = disposition_names
    card_path.write_text(json.dumps(card, sort_keys=True) + "\n")

    manifest_path = capsule / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    node = next(item for item in manifest["nodes"] if item["id"] == "resolution")
    node["validator"]["terminal_disposition_paths"] = disposition_names
    known_paths = {artifact["path"] for artifact in node["artifacts"]}
    for path in extra_paths:
        if path not in known_paths:
            node["artifacts"].append(
                {
                    "name": path.replace(".", "-"),
                    "path": path,
                    "sha256": hashlib.sha256((capsule / path).read_bytes()).hexdigest(),
                }
            )
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n")
    _recommit_manifest_artifact(capsule, "resolution", "resolution-card-json")
    _recommit_manifest_artifact(capsule, "resolution", "empty-terminal-jsonl")

    result = verify_cycle_manifest(manifest_path)

    resolution = next(node for node in result.nodes if node.node_id == "resolution")
    assert resolution.status == "FAILED"
    assert resolution.issues[0].message == (
        "nonempty terminal partition requires authoritative disposition replay"
    )


def test_terminal_bytes_cannot_hide_behind_legacy_empty_semantics(
    tmp_path: Path,
) -> None:
    capsule = tmp_path / "capsule"
    shutil.copytree(_CAPSULE.parent, capsule)
    terminal_path = capsule / "empty-terminal.jsonl"
    terminal_path.write_text('{"source_document_id":"unexpected-terminal"}\n')
    _recommit_manifest_artifact(capsule, "resolution", "empty-terminal-jsonl")

    result = verify_cycle_manifest(capsule / "manifest.json")

    resolution = next(node for node in result.nodes if node.node_id == "resolution")
    assert resolution.status == "FAILED"
    assert resolution.issues[0].message == (
        "nonempty terminal partition requires authoritative disposition replay"
    )


def test_undeclared_validator_artifact_has_named_redacted_error(
    tmp_path: Path,
) -> None:
    capsule = tmp_path / "capsule"
    shutil.copytree(_CAPSULE.parent, capsule)
    manifest_path = capsule / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["nodes"][0]["validator"]["card"] = "missing-card"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n")

    result = verify_cycle_manifest(manifest_path)

    assert result.nodes[0].issues[0].message == (
        "validator card names an undeclared artifact: missing-card"
    )


def test_semantic_library_errors_do_not_leak_artifact_identifiers(
    tmp_path: Path,
) -> None:
    capsule = tmp_path / "capsule"
    shutil.copytree(_CAPSULE.parent, capsule)
    resolved_path = capsule / "resolved.jsonl"
    record = json.loads(resolved_path.read_text())
    record["candidate_id"] = "secret-candidate-identifier"
    resolved_path.write_text(json.dumps(record, sort_keys=True) + "\n")
    _recommit_manifest_artifact(capsule, "purchase-baseline", "resolved-jsonl")
    _recommit_manifest_artifact(capsule, "resolution", "resolved-jsonl")

    result = verify_cycle_manifest(capsule / "manifest.json")

    issue = result.nodes[1].issues[0]
    assert issue.message == (
        "semantic replay rejected authenticated inputs (ResolvedPostRecoveryError)"
    )
    assert "secret-candidate-identifier" not in json.dumps(result.to_record())


@pytest.mark.parametrize("unsafe_path", ["/etc/passwd", "../outside.jsonl"])
def test_manifest_rejects_absolute_and_parent_paths(
    tmp_path: Path, unsafe_path: str
) -> None:
    capsule = tmp_path / "capsule"
    shutil.copytree(_CAPSULE.parent, capsule)
    manifest_path = capsule / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["nodes"][0]["artifacts"][1]["path"] = unsafe_path
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n")

    assert main(["--manifest", str(manifest_path)]) == 1


def test_manifest_rejects_symlinked_parent_escape(tmp_path: Path) -> None:
    capsule = tmp_path / "capsule"
    shutil.copytree(_CAPSULE.parent, capsule)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "selection.jsonl").write_text('{"candidate_id":"outside"}\n')
    (capsule / "escape").symlink_to(outside, target_is_directory=True)
    manifest_path = capsule / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["nodes"][0]["artifacts"][1]["path"] = "escape/selection.jsonl"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n")

    assert main(["--manifest", str(manifest_path)]) == 1


def test_dependency_edges_bind_the_same_artifact_paths_and_bytes(
    tmp_path: Path,
) -> None:
    capsule = tmp_path / "capsule"
    shutil.copytree(_CAPSULE.parent, capsule)
    duplicate = capsule / "duplicate-resolved.jsonl"
    duplicate.write_bytes((capsule / "resolved.jsonl").read_bytes())
    manifest_path = capsule / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    resolution = next(node for node in manifest["nodes"] if node["id"] == "resolution")
    artifact = next(
        item for item in resolution["artifacts"] if item["name"] == "resolved-jsonl"
    )
    artifact["path"] = "duplicate-resolved.jsonl"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n")

    assert main(["--manifest", str(manifest_path)]) == 1


def test_clearance_edge_binds_recovery_lineage_artifacts(tmp_path: Path) -> None:
    capsule = tmp_path / "capsule"
    shutil.copytree(_CAPSULE.parent, capsule)
    duplicate = capsule / "duplicate-selection.jsonl"
    duplicate.write_bytes((capsule / "selection.jsonl").read_bytes())
    manifest_path = capsule / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    clearance = next(node for node in manifest["nodes"] if node["id"] == "clearance")
    selection = next(
        item for item in clearance["artifacts"] if item["name"] == "selection-jsonl"
    )
    selection["path"] = "duplicate-selection.jsonl"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n")

    assert main(["--manifest", str(manifest_path)]) == 1


def test_shared_edge_rejects_symlink_alias_path(tmp_path: Path) -> None:
    capsule = tmp_path / "capsule"
    shutil.copytree(_CAPSULE.parent, capsule)
    (capsule / "alias").symlink_to(capsule, target_is_directory=True)
    manifest_path = capsule / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    clearance = next(node for node in manifest["nodes"] if node["id"] == "clearance")
    selection = next(
        item for item in clearance["artifacts"] if item["name"] == "selection-jsonl"
    )
    selection["path"] = "alias/selection.jsonl"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n")

    assert main(["--manifest", str(manifest_path)]) == 1


def test_terminal_config_path_matches_authenticated_artifact(tmp_path: Path) -> None:
    capsule = tmp_path / "capsule"
    shutil.copytree(_CAPSULE.parent, capsule)
    manifest_path = capsule / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    resolution = next(node for node in manifest["nodes"] if node["id"] == "resolution")
    resolution["validator"]["terminal_path"] = "selection.jsonl"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n")

    result = verify_cycle_manifest(manifest_path)

    assert result.nodes[-2].status == "FAILED"
    assert result.nodes[-2].issues[0].message == (
        "terminal partition artifact path differs"
    )


def test_post_open_path_race_is_a_stable_preflight_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact = tmp_path / "artifact.json"
    artifact.write_text("{}\n")

    def unavailable_path(*_args: object, **_kwargs: object) -> object:
        raise FileNotFoundError("concurrent unlink")

    monkeypatch.setattr(cycle_preflight.os, "stat", unavailable_path)

    with pytest.raises(
        cycle_preflight.CyclePreflightError,
        match="artifact is unavailable or changed",
    ):
        cycle_preflight._read_stable(  # pyright: ignore[reportPrivateUsage]
            artifact, label="artifact"
        )


def test_successor_descriptor_requires_closed_producer_card(tmp_path: Path) -> None:
    capsule = tmp_path / "capsule"
    shutil.copytree(_CAPSULE.parent, capsule)
    card_path = capsule / "replacement-source-card.json"
    card = json.loads(card_path.read_text())
    card["status"] = "failed"
    card_path.write_text(json.dumps(card, sort_keys=True) + "\n")
    _recommit_manifest_artifact(
        capsule,
        "replacement-recovery-source",
        "replacement-source-card-json",
    )

    result = verify_cycle_manifest(capsule / "manifest.json")

    replacement = result.nodes[-1]
    assert replacement.status == "FAILED"
    assert replacement.issues[0].message == (
        "replacement source producer card is not closed"
    )


def test_successor_producer_requires_exact_manifest_evidence_set(
    tmp_path: Path,
) -> None:
    capsule = tmp_path / "capsule"
    shutil.copytree(_CAPSULE.parent, capsule)
    manifest_path = capsule / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    replacement = next(
        node
        for node in manifest["nodes"]
        if node["id"] == "replacement-recovery-source"
    )
    replacement["validator"]["expected_producer_inputs"].pop()
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n")

    result = verify_cycle_manifest(manifest_path)

    assert result.nodes[-1].status == "FAILED"
    assert result.nodes[-1].issues[0].message == (
        "replacement producer evidence set differs"
    )


def test_resolution_selection_must_match_recovery_selection(tmp_path: Path) -> None:
    capsule = tmp_path / "capsule"
    shutil.copytree(_CAPSULE.parent, capsule)
    alternate = capsule / "alternate-selection.jsonl"
    alternate.write_bytes((capsule / "selection.jsonl").read_bytes())
    manifest_path = capsule / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    resolution = next(node for node in manifest["nodes"] if node["id"] == "resolution")
    selection = next(
        artifact
        for artifact in resolution["artifacts"]
        if artifact["name"] == "selection-jsonl"
    )
    selection["path"] = "alternate-selection.jsonl"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n")

    with pytest.raises(
        cycle_preflight.CyclePreflightError,
        match="dependency artifact differs: selection-jsonl",
    ):
        verify_cycle_manifest(manifest_path)


@pytest.mark.parametrize("node_id", ["purchase-baseline", "resolution"])
def test_purchase_policy_is_bound_across_recovery_and_resolution(
    tmp_path: Path, node_id: str
) -> None:
    capsule = tmp_path / "capsule"
    shutil.copytree(_CAPSULE.parent, capsule)
    alternate = capsule / "alternate-purchase-policy.json"
    alternate.write_bytes((capsule / "purchase-policy.json").read_bytes())
    manifest_path = capsule / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    node = next(item for item in manifest["nodes"] if item["id"] == node_id)
    policy = next(
        artifact
        for artifact in node["artifacts"]
        if artifact["name"] == "purchase-policy-json"
    )
    policy["path"] = "alternate-purchase-policy.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n")

    with pytest.raises(
        cycle_preflight.CyclePreflightError,
        match="dependency artifact differs: purchase-policy-json",
    ):
        verify_cycle_manifest(manifest_path)


def test_successor_descriptor_artifact_must_match_producer_coordinate(
    tmp_path: Path,
) -> None:
    capsule = tmp_path / "capsule"
    shutil.copytree(_CAPSULE.parent, capsule)
    alternate = capsule / "alternate-replacement-source.json"
    alternate.write_bytes((capsule / "replacement-source.json").read_bytes())
    manifest_path = capsule / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    replacement = next(
        node
        for node in manifest["nodes"]
        if node["id"] == "replacement-recovery-source"
    )
    descriptor = next(
        artifact
        for artifact in replacement["artifacts"]
        if artifact["name"] == "replacement-source-json"
    )
    descriptor["path"] = "alternate-replacement-source.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n")

    result = verify_cycle_manifest(manifest_path)

    assert result.nodes[-1].status == "FAILED"
    assert result.nodes[-1].issues[0].message == (
        "replacement producer descriptor coordinate differs"
    )


def test_real_producer_tree_commitments_are_manifest_authenticated(
    tmp_path: Path,
) -> None:
    capsule = tmp_path / "capsule"
    shutil.copytree(_CAPSULE.parent, capsule)
    document_path = capsule / "documents/case-1/document.pdf"
    document_path.parent.mkdir(parents=True)
    document_path.write_bytes(b"authenticated document")
    digest = hashlib.sha256(document_path.read_bytes()).hexdigest()
    tree_digest = hashlib.sha256(
        json.dumps(
            {"case-1/document.pdf": "sha256:" + digest},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    manifest_path = capsule / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    tree_root = str((capsule / "documents").resolve())
    tree_contracts = {
        "recovery": (
            "output_commitments/document_tree",
            {"case-1/document.pdf": "sha256:" + digest},
        ),
        "clearance": (
            "source_commitments/document_root",
            {
                "path": tree_root,
                "tree_sha256": "sha256:" + tree_digest,
                "document_count": 1,
            },
        ),
    }
    for node_id, (contract_name, commitment) in tree_contracts.items():
        node = next(item for item in manifest["nodes"] if item["id"] == node_id)
        node["artifacts"].append(
            {
                "name": "recovered-document",
                "path": "documents/case-1/document.pdf",
                "sha256": digest,
            }
        )
        node["validator"]["tree_commitments"] = {
            contract_name: {
                "root": "documents",
                "files": {"case-1/document.pdf": "recovered-document"},
            }
        }
        card_artifact_name = node["validator"]["card"]
        card_artifact = next(
            artifact
            for artifact in node["artifacts"]
            if artifact["name"] == card_artifact_name
        )
        card_path = capsule / card_artifact["path"]
        card = json.loads(card_path.read_text())
        field, name = contract_name.split("/")
        if card.get(field) is None:
            card[field] = {}
        card[field][name] = commitment
        path_field = "output_paths" if field == "output_commitments" else "input_paths"
        card[path_field] = [*(card.get(path_field) or []), tree_root]
        card_path.write_text(json.dumps(card, sort_keys=True) + "\n")

    for card_name in ("resolution-card.json", "replacement-source-card.json"):
        card_path = capsule / card_name
        card = cast(dict[str, object], json.loads(card_path.read_text()))
        for field in ("source_commitments", "output_commitments"):
            commitments = card.get(field)
            if not isinstance(commitments, dict):
                continue
            typed_commitments = cast(dict[str, object], commitments)
            for name, value in typed_commitments.items():
                if isinstance(value, dict):
                    typed_value = cast(dict[str, object], value)
                    raw_path = typed_value.get("path")
                    if not isinstance(raw_path, str):
                        continue
                    path = capsule / raw_path
                    typed_value["sha256"] = (
                        "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
                    )
                elif isinstance(value, str) and name != "purchase_state_sha256":
                    path = capsule / name
                    typed_commitments[name] = (
                        "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
                    )
        card_path.write_text(json.dumps(card, sort_keys=True) + "\n")

    for node in manifest["nodes"]:
        for artifact in node["artifacts"]:
            artifact_path = capsule / artifact["path"]
            artifact["sha256"] = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n")

    assert verify_cycle_manifest(manifest_path).ok is True

    document_path.write_bytes(b"tampered document")
    tampered = verify_cycle_manifest(manifest_path)
    assert tampered.ok is False
    assert any(issue.code == "ARTIFACT_SHA256_MISMATCH" for issue in tampered.issues)

    document_path.write_bytes(b"authenticated document")
    (capsule / "documents/uncommitted.pdf").write_bytes(b"uncommitted")
    extra = verify_cycle_manifest(manifest_path)
    assert extra.nodes[0].status == "FAILED"
    assert extra.nodes[0].issues[0].message == (
        "validator tree commitment output_commitments/document_tree file set differs"
    )


def test_successor_producer_rejects_resolved_path_aliases(tmp_path: Path) -> None:
    capsule = tmp_path / "capsule"
    shutil.copytree(_CAPSULE.parent, capsule)
    card_path = capsule / "replacement-source-card.json"
    card = json.loads(card_path.read_text())
    card["input_paths"].append("./recovery-card.json")
    card["source_commitments"]["./recovery-card.json"] = card["source_commitments"][
        "recovery-card.json"
    ]
    card_path.write_text(json.dumps(card, sort_keys=True) + "\n")
    _recommit_manifest_artifact(
        capsule,
        "replacement-recovery-source",
        "replacement-source-card-json",
    )

    result = verify_cycle_manifest(capsule / "manifest.json")

    assert result.nodes[-1].status == "FAILED"
    assert result.nodes[-1].issues[0].message == (
        "replacement producer input commitments differ"
    )


def test_successor_producer_rejects_historical_v2_card(tmp_path: Path) -> None:
    capsule = tmp_path / "capsule"
    shutil.copytree(_CAPSULE.parent, capsule)
    card_path = capsule / "replacement-source-card.json"
    card = json.loads(card_path.read_text())
    card["schema_version"] = "legalforecast.replacement_recovery_source_run_card.v2"
    card["replayed_purchase_state_sha256"] = "tampered-state"
    card_path.write_text(json.dumps(card, sort_keys=True) + "\n")
    _recommit_manifest_artifact(
        capsule,
        "replacement-recovery-source",
        "replacement-source-card-json",
    )

    result = verify_cycle_manifest(capsule / "manifest.json")

    assert result.nodes[-1].status == "FAILED"
    assert result.nodes[-1].issues[0].message == (
        "replacement source producer card is not closed"
    )


def test_preflight_accepts_real_producer_absolute_card_paths(tmp_path: Path) -> None:
    capsule = tmp_path / "capsule"
    shutil.copytree(_CAPSULE.parent, capsule)
    card_artifacts = (
        ("recovery", "recovery-card-json"),
        ("clearance", "clearance-card-json"),
        ("resolution", "resolution-card-json"),
        ("replacement-recovery-source", "replacement-source-card-json"),
    )
    direct_path_fields = {
        "path",
        "selection",
        "recovery_root",
        "purchased_clearance",
        "purchased_clearance_run_card",
        "resolved_post_recovery_documents",
        "replacement_purchase_authority",
        "replacement_controlled_private_root",
        "replacement_budget_plan",
    }

    def absolute_card_paths(value: object) -> object:
        if isinstance(value, list):
            return [absolute_card_paths(item) for item in cast(list[object], value)]
        if not isinstance(value, dict):
            return value
        rewritten: dict[str, object] = {}
        for key, item in cast(dict[str, object], value).items():
            if key in direct_path_fields and isinstance(item, str):
                rewritten[key] = str((capsule / item).resolve())
            elif key in {"input_paths", "output_paths"} and isinstance(item, list):
                rewritten[key] = [
                    str((capsule / path).resolve()) if isinstance(path, str) else path
                    for path in cast(list[object], item)
                ]
            elif key in {"source_commitments", "output_commitments"} and isinstance(
                item, dict
            ):
                rewritten_commitments: dict[str, object] = {}
                for name, commitment in cast(dict[str, object], item).items():
                    if isinstance(commitment, dict):
                        rewritten_value = absolute_card_paths(
                            cast(dict[str, object], commitment)
                        )
                        assert isinstance(rewritten_value, dict)
                        rewritten_commitment = cast(dict[str, object], rewritten_value)
                        path = rewritten_commitment.get("path")
                        if isinstance(path, str):
                            rewritten_commitment["sha256"] = (
                                "sha256:"
                                + hashlib.sha256(Path(path).read_bytes()).hexdigest()
                            )
                        rewritten_commitments[name] = rewritten_commitment
                    elif name != "purchase_state_sha256":
                        path = (capsule / name).resolve()
                        rewritten_commitments[str(path)] = (
                            "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
                        )
                    else:
                        rewritten_commitments[name] = commitment
                rewritten[key] = rewritten_commitments
            else:
                rewritten[key] = absolute_card_paths(item)
        return rewritten

    manifest = json.loads((capsule / "manifest.json").read_text())
    for node_id, artifact_name in card_artifacts:
        node = next(item for item in manifest["nodes"] if item["id"] == node_id)
        artifact = next(
            item for item in node["artifacts"] if item["name"] == artifact_name
        )
        card_path = capsule / artifact["path"]
        raw_card: object = json.loads(card_path.read_text())
        card = absolute_card_paths(raw_card)
        card_path.write_text(json.dumps(card, sort_keys=True) + "\n")
        _recommit_manifest_artifact(capsule, node_id, artifact_name)

    assert verify_cycle_manifest(capsule / "manifest.json").ok is True
