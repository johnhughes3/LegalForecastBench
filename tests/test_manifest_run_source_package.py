"""The closed corpus package a FIRST official staging carries to the runner.

The supplementary lane never ships bytes: everything it shares with the official
freeze is already staged, so it rebuilds the tree in the workflow. A first
official staging has an empty prefix by definition, so the 13 frozen artifacts
and the 200 model packets have to travel -- and they cannot travel through this
public repository, because they are the un-run evaluation inputs and the final
labels.

These tests hold that transport to the only property it has to have. age and a
never-published draft release provide confidentiality; integrity comes from
commitments already in the chain, so the tests here are about *closure*: what the
package may contain, what it refuses, and that what comes out the far end is
byte-identical to what went in and is accepted by staging itself.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from legalforecast.evals.corpus_manifest.records import registry_record
from legalforecast.evals.model_registry import load_model_registry_bytes
from legalforecast.protocol.freeze import (
    FreezeBundle,
    FrozenArtifact,
    FrozenArtifactName,
    load_freeze_bundle,
    load_freeze_bundle_bytes,
    write_hash_bundle,
)
from legalforecast.publication.manifest_forecast_stage import (
    ManifestForecastStageConfig,
    stage_manifest_forecast,
)
from legalforecast.publication.manifest_run_source_package import (
    PACKAGE_ARTIFACT_PREFIX,
    PACKAGE_FREEZE_NAME,
    PACKAGE_OUTPUT_PREFIX,
    BuildSourcePackageConfig,
    ManifestRunSourcePackageError,
    OpenSourcePackageConfig,
    build_manifest_run_source_package,
    open_manifest_run_source_package,
)


@pytest.fixture(autouse=True)
def _skip_artifact_content_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the freeze bundle real; skip each artifact's own schema validation.

    ``verify_freeze_bundle_bytes`` re-validates every artifact's *content* --
    execution-policy schema version, labeling policy shape, and so on -- which
    would mean carrying a full synthetic corpus here to test archive handling.
    The structure this module actually depends on is what
    ``load_freeze_bundle_bytes`` builds: real artifact names, real digests, and
    real path resolution against the root. Staging re-runs the full verification
    on the extracted tree in production, and
    ``test_an_opened_package_is_accepted_by_official_staging`` proves the handoff.
    """

    for module in (
        "legalforecast.publication.manifest_run_source_package",
        "legalforecast.publication.manifest_forecast_stage",
    ):
        monkeypatch.setattr(
            f"{module}.verify_freeze_bundle_bytes",
            lambda payload, *, root_path=None, **_: load_freeze_bundle_bytes(
                payload, root_path=root_path
            ),
        )


_MODELS = (("openai", "gpt-5.6-luna"), ("anthropic", "claude-opus-4-8"))
_ANCHOR = "2026-06-26"
_MANIFEST_DIGEST = "a" * 64
_PACKET_KEY = "model-packets/cycle-1/case-1/full_packet.json"


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def _registry_records() -> list[dict[str, object]]:
    return [
        {
            "context_limit": 400000,
            "display_name": f"{provider} {model_id}",
            "input_token_price": 1.25,
            "known_cutoff_publicity_caveats": [],
            "max_output_tokens": 128000,
            "model_id": model_id,
            "model_version_or_snapshot": model_id,
            "network_disabled": True,
            "output_token_price": 10.0,
            "pricing_source": "https://example.invalid/pricing",
            "provider": provider,
            "provider_training_cutoff": None,
            "provider_training_cutoff_status": "unknown",
            "release_timestamp": "2026-06-01T00:00:00Z",
            "release_timestamp_source": "https://example.invalid/release",
            "search_disabled": True,
            "tool_policy": "no_tools",
        }
        for provider, model_id in _MODELS
    ]


def _artifact(path: Path, name: FrozenArtifactName, payload: object) -> FrozenArtifact:
    _write_json(path, payload)
    return FrozenArtifact(
        name=name,
        path=path,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        size_bytes=path.stat().st_size,
    )


def _corpus(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Build one operator-side corpus: artifact root, output dir, freeze bundle.

    The freeze bundle records ABSOLUTE artifact paths, which is what the freeze
    tool actually writes, because the whole point of ``build`` is that those
    machine-specific paths are meaningless on the runner and must be rewritten.
    """

    root = tmp_path / "freeze-inputs"
    output = tmp_path / "output"

    registry = _artifact(
        root / "model-registry.json",
        FrozenArtifactName.MODEL_REGISTRY,
        _registry_records(),
    )
    evaluation_models = registry_record(
        load_model_registry_bytes(
            json.dumps(_registry_records(), sort_keys=True).encode("utf-8")
        ).entries
    )
    artifacts: list[FrozenArtifact] = [registry]
    for artifact_name in FrozenArtifactName:
        if artifact_name is FrozenArtifactName.MODEL_REGISTRY:
            continue
        payload: object = {"cycle_id": "cycle-1", "artifact": artifact_name.value}
        if artifact_name is FrozenArtifactName.PROMPT:
            payload = {
                "cycle_id": "cycle-1",
                "prompt_replay": {
                    "evaluation_models": evaluation_models,
                    "evaluation_release_anchor": _ANCHOR,
                    "model_registry_sha256": registry.sha256,
                },
            }
        artifacts.append(
            _artifact(root / f"{artifact_name.value}.json", artifact_name, payload)
        )

    packet = output / _PACKET_KEY
    _write_json(packet, {"case_id": "case-1", "text": "blind"})
    _write_json(
        output / "run-inputs.json",
        {
            "cycle_id": "cycle-1",
            "model_packets": [
                {
                    "case_id": "case-1",
                    "ablation": "full_packet",
                    "decision_date": "2026-03-04",
                    "packet_object_key": _PACKET_KEY,
                    "packet_sha256": hashlib.sha256(packet.read_bytes()).hexdigest(),
                }
            ],
        },
    )
    _write_json(
        output / "manifest-mode-run-record.json",
        {
            "manifest_sha256": _MANIFEST_DIGEST,
            "evaluation_models": evaluation_models,
            "evaluation_release_anchor": _ANCHOR,
        },
    )

    freeze = tmp_path / "cycle-1.freeze.json"
    write_hash_bundle(
        freeze,
        FreezeBundle(
            cycle_id="cycle-1",
            freeze_timestamp=datetime.now(UTC),
            artifacts=tuple(artifacts),
        ),
    )
    return root, output, freeze


def _build(tmp_path: Path, **overrides: Path) -> tuple[dict[str, object], Path]:
    root, output, freeze = _corpus(tmp_path)
    package = tmp_path / "source.zip"
    record = build_manifest_run_source_package(
        BuildSourcePackageConfig(
            freeze_bundle=overrides.get("freeze_bundle", freeze),
            artifact_root=overrides.get("artifact_root", root),
            output_dir=overrides.get("output_dir", output),
            package_out=package,
        )
    )
    return record, package


def _open_config(
    tmp_path: Path, record: dict[str, object], package: Path
) -> OpenSourcePackageConfig:
    return OpenSourcePackageConfig(
        package=package,
        artifact_root=tmp_path / "runner" / "artifact-root",
        output_dir=tmp_path / "runner" / "output-dir",
        freeze_bundle_out=tmp_path / "runner" / "freeze.json",
        freeze_bundle_sha256=str(record["freeze_bundle_sha256"]),
        run_inputs_sha256=str(record["run_inputs_sha256"]),
        run_record_sha256=str(record["run_record_sha256"]),
    )


def test_build_then_open_round_trips_every_committed_byte(tmp_path: Path) -> None:
    root, _, _ = _corpus(tmp_path / "source")
    record, package = _build(tmp_path / "source")

    opened = open_manifest_run_source_package(_open_config(tmp_path, record, package))

    assert opened["artifact_count"] == len(list(FrozenArtifactName))
    assert record["packet_count"] == 1
    runner_root = tmp_path / "runner" / "artifact-root"
    for original in sorted(root.iterdir()):
        rebuilt = runner_root / original.name
        assert rebuilt.read_bytes() == original.read_bytes()
    assert (tmp_path / "runner" / "output-dir" / _PACKET_KEY).read_bytes() == (
        tmp_path / "source" / "output" / _PACKET_KEY
    ).read_bytes()


def test_packaged_freeze_bundle_carries_no_operator_paths(tmp_path: Path) -> None:
    """The rewrite is not cosmetic.

    The operator's bundle records absolute machine paths. Those are meaningless
    on the runner, they are exactly the local detail this public repository must
    not carry, and staging would refuse them outright as "outside
    --artifact-root". ``build`` rewrites them and recomputes the bundle hash, so
    the digest the dispatch pins is the packaged bundle's, not the local one's.
    """

    record, package = _build(tmp_path)

    with zipfile.ZipFile(package) as archive:
        packaged = json.loads(archive.read(PACKAGE_FREEZE_NAME))

    paths = [str(row["path"]) for row in packaged["artifacts"]]
    assert paths, "packaged bundle records no artifacts"
    for path in paths:
        assert not Path(path).is_absolute()
        assert str(tmp_path) not in path
        # The bh6j trigger shape: staging prepends artifacts/ itself.
        assert not path.startswith("artifacts/")
    assert (
        record["freeze_bundle_sha256"]
        == hashlib.sha256(
            json.dumps(packaged, indent=2, sort_keys=True).encode("utf-8") + b"\n"
        ).hexdigest()
    )


def test_an_opened_package_is_accepted_by_official_staging(tmp_path: Path) -> None:
    """End to end: the package is a staging input, not merely a valid archive.

    Official mode requires the candidate freeze to BE the pinned official bundle,
    so the packaged bundle's own digest pins both sides. If the rewrite, the
    extraction, or any digest were wrong, staging would refuse here rather than
    produce a plan.
    """

    record, package = _build(tmp_path)
    opened = open_manifest_run_source_package(_open_config(tmp_path, record, package))
    freeze = Path(str(opened["freeze_bundle"]))

    result = stage_manifest_forecast(
        ManifestForecastStageConfig(
            output_dir=Path(str(opened["output_dir"])),
            freeze_bundle=freeze,
            artifact_root=Path(str(opened["artifact_root"])),
            manifest_digest=_MANIFEST_DIGEST,
            results_bucket="results-bucket",
            packet_bucket="packet-bucket",
            official_freeze_bundle=freeze,
            official_freeze_bundle_sha256=str(record["freeze_bundle_sha256"]),
            dry_run=True,
        )
    )

    assert result.prefix == f"cycle-1/manifest-runs/{_MANIFEST_DIGEST}"
    keys = [str(row["key"]) for row in result.stage_record["objects"]]  # type: ignore[index]
    assert not any("artifacts/artifacts" in key for key in keys)
    assert not any("/supplementary/" in key for key in keys)


def test_build_refuses_an_artifact_root_one_level_too_high(tmp_path: Path) -> None:
    """The build-time half of the bh6j fence.

    The defect fires when an artifact's path relative to --artifact-root already
    begins with artifacts/, because staging prepends that segment unconditionally.
    A restage is the usual way in and the first-stage precondition covers it; a
    misaimed --artifact-root is the other way, and it is reachable on a genuine
    first stage where nothing else would catch it.
    """

    root = tmp_path / "corpus" / "artifacts"
    root.mkdir(parents=True)
    _, output, _ = _corpus(tmp_path / "unused")
    registry = _artifact(
        root / "model-registry.json",
        FrozenArtifactName.MODEL_REGISTRY,
        _registry_records(),
    )
    artifacts = [registry] + [
        _artifact(
            root / f"{name.value}.json",
            name,
            {"cycle_id": "cycle-1", "artifact": name.value},
        )
        for name in FrozenArtifactName
        if name is not FrozenArtifactName.MODEL_REGISTRY
    ]
    freeze = tmp_path / "high.freeze.json"
    write_hash_bundle(
        freeze,
        FreezeBundle(
            cycle_id="cycle-1",
            freeze_timestamp=datetime.now(UTC),
            artifacts=tuple(artifacts),
        ),
    )

    with pytest.raises(ManifestRunSourcePackageError) as error:
        build_manifest_run_source_package(
            BuildSourcePackageConfig(
                freeze_bundle=freeze,
                # One level too high: every artifact is now under artifacts/.
                artifact_root=tmp_path / "corpus",
                output_dir=output,
                package_out=tmp_path / "high.zip",
            )
        )

    assert "starts with 'artifacts/'" in str(error.value)


def test_build_is_deterministic_so_the_pinned_digest_is_reproducible(
    tmp_path: Path,
) -> None:
    root, output, freeze = _corpus(tmp_path)
    digests = set()
    for index in range(2):
        record = build_manifest_run_source_package(
            BuildSourcePackageConfig(
                freeze_bundle=freeze,
                artifact_root=root,
                output_dir=output,
                package_out=tmp_path / f"source-{index}.zip",
            )
        )
        digests.add(str(record["package_sha256"]))
    assert len(digests) == 1


def test_build_refuses_to_replace_an_existing_package(tmp_path: Path) -> None:
    root, output, freeze = _corpus(tmp_path)
    package = tmp_path / "source.zip"
    package.write_bytes(b"occupied")

    with pytest.raises(ManifestRunSourcePackageError) as error:
        build_manifest_run_source_package(
            BuildSourcePackageConfig(
                freeze_bundle=freeze,
                artifact_root=root,
                output_dir=output,
                package_out=package,
            )
        )

    assert "refusing to replace" in str(error.value)


def test_build_refuses_a_packet_whose_bytes_disagree_with_run_inputs(
    tmp_path: Path,
) -> None:
    root, output, freeze = _corpus(tmp_path)
    (output / _PACKET_KEY).write_text('{"case_id": "case-1"}\n', encoding="utf-8")

    with pytest.raises(ManifestRunSourcePackageError) as error:
        build_manifest_run_source_package(
            BuildSourcePackageConfig(
                freeze_bundle=freeze,
                artifact_root=root,
                output_dir=output,
                package_out=tmp_path / "source.zip",
            )
        )

    assert "hashes to" in str(error.value)


@pytest.mark.parametrize(
    "field",
    ["freeze_bundle_sha256", "run_inputs_sha256", "run_record_sha256"],
)
def test_open_holds_each_pinned_digest(tmp_path: Path, field: str) -> None:
    record, package = _build(tmp_path)
    config = replace(_open_config(tmp_path, record, package), **{field: "b" * 64})

    with pytest.raises(ManifestRunSourcePackageError) as error:
        open_manifest_run_source_package(config)

    assert "not the committed" in str(error.value)


@pytest.mark.parametrize(
    "member",
    [
        f"../{PACKAGE_ARTIFACT_PREFIX}/escape.json",
        f"/{PACKAGE_ARTIFACT_PREFIX}/absolute.json",
        f"{PACKAGE_ARTIFACT_PREFIX}/../../escape.json",
    ],
)
def test_open_refuses_a_member_that_leaves_its_root(
    tmp_path: Path, member: str
) -> None:
    """Refused, never sanitized.

    A traversing member cannot come from ``build``, so silently rewriting it to
    something safe would hide the fact that the package was assembled by
    something else. The ciphertext digest already authenticates the archive; this
    is the layer that says so out loud.
    """

    record, package = _build(tmp_path)
    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(package) as source, zipfile.ZipFile(tampered, "w") as target:
        for info in source.infolist():
            target.writestr(info, source.read(info))
        target.writestr(member, b"{}\n")

    with pytest.raises(ManifestRunSourcePackageError) as error:
        open_manifest_run_source_package(
            replace(_open_config(tmp_path, record, package), package=tampered)
        )

    assert "unsafe archive member name" in str(error.value)


def test_open_refuses_a_member_it_cannot_place(tmp_path: Path) -> None:
    record, package = _build(tmp_path)
    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(package) as source, zipfile.ZipFile(tampered, "w") as target:
        for info in source.infolist():
            target.writestr(info, source.read(info))
        target.writestr("somewhere-else/extra.json", b"{}\n")

    with pytest.raises(ManifestRunSourcePackageError) as error:
        open_manifest_run_source_package(
            replace(_open_config(tmp_path, record, package), package=tampered)
        )

    assert "outside" in str(error.value)


def test_open_refuses_a_directory_entry(tmp_path: Path) -> None:
    record, package = _build(tmp_path)
    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(package) as source, zipfile.ZipFile(tampered, "w") as target:
        for info in source.infolist():
            target.writestr(info, source.read(info))
        target.writestr(f"{PACKAGE_OUTPUT_PREFIX}/nested/", b"")

    with pytest.raises(ManifestRunSourcePackageError) as error:
        open_manifest_run_source_package(
            replace(_open_config(tmp_path, record, package), package=tampered)
        )

    assert "directory entry" in str(error.value)


def test_open_refuses_a_package_that_is_not_an_archive(tmp_path: Path) -> None:
    record, package = _build(tmp_path)
    broken = tmp_path / "broken.zip"
    broken.write_bytes(b"not a zip")

    with pytest.raises(ManifestRunSourcePackageError) as error:
        open_manifest_run_source_package(
            replace(_open_config(tmp_path, record, package), package=broken)
        )

    assert "not a readable archive" in str(error.value)


def test_open_refuses_to_overwrite_an_existing_extraction(tmp_path: Path) -> None:
    """A second open into a populated root is a bug, not a resume.

    The runner extracts into a fresh temporary root every time. Landing on files
    that are already there means two different packages are being mixed, and the
    resulting tree would be neither one.
    """

    record, package = _build(tmp_path)
    config = _open_config(tmp_path, record, package)
    open_manifest_run_source_package(config)

    with pytest.raises(ManifestRunSourcePackageError) as error:
        open_manifest_run_source_package(config)

    assert "refusing to replace" in str(error.value)


def test_packaged_freeze_bundle_loads_against_the_extracted_root(
    tmp_path: Path,
) -> None:
    record, package = _build(tmp_path)
    opened = open_manifest_run_source_package(_open_config(tmp_path, record, package))

    bundle = load_freeze_bundle(
        Path(str(opened["freeze_bundle"])),
        root_path=Path(str(opened["artifact_root"])),
    )

    assert {artifact.name for artifact in bundle.artifacts} == set(FrozenArtifactName)
    for artifact in bundle.artifacts:
        assert artifact.path.is_file()
        assert hashlib.sha256(artifact.path.read_bytes()).hexdigest() == artifact.sha256


def test_open_refuses_a_symlink_member(tmp_path: Path) -> None:
    """A symlink in the archive is how a package escapes its extraction root.

    The name check alone would let ``artifact-root/manifest.json`` through while
    it pointed at ``/etc/passwd`` or back out of the tree, so the file-type bits
    are checked as well.
    """

    record, package = _build(tmp_path)
    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(package) as source, zipfile.ZipFile(tampered, "w") as target:
        for info in source.infolist():
            target.writestr(info, source.read(info))
        link = zipfile.ZipInfo(f"{PACKAGE_ARTIFACT_PREFIX}/link.json")
        link.external_attr = 0o120777 << 16
        target.writestr(link, b"/etc/passwd")

    with pytest.raises(ManifestRunSourcePackageError) as error:
        open_manifest_run_source_package(
            replace(_open_config(tmp_path, record, package), package=tampered)
        )

    assert "not a regular file" in str(error.value)
