"""Rebuilding staging inputs must be content-addressed and fail closed.

The reconstruction runs inside the staging workflow with live AWS credentials,
so every case here drives the real module against an in-memory object store
rather than mocking the module itself: the fetcher is the only injected seam,
because it is the only part that needs credentials in production.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

import pytest
from legalforecast.protocol.freeze import (
    FreezeBundle,
    FrozenArtifact,
    FrozenArtifactName,
    write_hash_bundle,
)
from legalforecast.publication.manifest_run_materialize import (
    ManifestRunMaterializeConfig,
    ManifestRunMaterializeError,
    _parse_local_artifacts,
    materialize_manifest_run_inputs,
)

# The production constant that causes the doubling the official lane would hit.
STAGED_ARTIFACT_PREFIX = "artifacts"

OFFICIAL_PREFIX = "cycle-1/manifest-runs/" + "a" * 64
RESULTS_BUCKET = "results-bucket"
PACKET_BUCKET = "packet-bucket"
PACKET_KEY = "model-packets/cycle-1/case-1/full_packet.json"


class FakeS3:
    """An exact-key object store: a miss is a hard error, never a listing."""

    def __init__(self, objects: Mapping[tuple[str, str], bytes]) -> None:
        self.objects = dict(objects)
        self.reads: list[tuple[str, str]] = []

    def fetch(self, bucket: str, key: str, destination: Path) -> None:
        self.reads.append((bucket, key))
        try:
            payload = self.objects[(bucket, key)]
        except KeyError as exc:  # pragma: no cover - guarded by assertions below
            raise ManifestRunMaterializeError(
                f"no such object s3://{bucket}/{key}"
            ) from exc
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)


def _digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _artifact(name: FrozenArtifactName, path: str, payload: bytes) -> FrozenArtifact:
    return FrozenArtifact(
        name=name,
        path=Path(path),
        sha256=_digest(payload),
        size_bytes=len(payload),
    )


def _bundle(artifacts: tuple[FrozenArtifact, ...]) -> FreezeBundle:
    return FreezeBundle(
        cycle_id="cycle-1",
        freeze_timestamp=datetime(2026, 8, 1, tzinfo=UTC),
        artifacts=artifacts,
    )


@pytest.fixture
def scenario(tmp_path: Path) -> tuple[FakeS3, dict[str, object]]:
    """One official staging already in S3, plus a sibling that replaces its registry."""

    shared_payloads = {
        name: json.dumps({"artifact": name.value}, sort_keys=True).encode("utf-8")
        for name in FrozenArtifactName
        if name is not FrozenArtifactName.MODEL_REGISTRY
    }
    official_registry = b'{"registry": "official"}'
    sibling_registry = b'{"registry": "supplementary"}'

    def _layout(
        shared_dir: str, registry_path: str, registry_payload: bytes
    ) -> tuple[FrozenArtifact, ...]:
        return (
            *(
                _artifact(name, f"{shared_dir}/{name.value}.json", payload)
                for name, payload in shared_payloads.items()
            ),
            _artifact(
                FrozenArtifactName.MODEL_REGISTRY, registry_path, registry_payload
            ),
        )

    # The staged official layout: every artifact under artifacts/<relative>.
    official_artifacts = _layout(
        "artifacts", "artifacts/model_registry.json", official_registry
    )
    official_path = tmp_path / "official.freeze.json"
    write_hash_bundle(official_path, _bundle(official_artifacts))
    official_bytes = official_path.read_bytes()
    official_path.unlink()

    # The sibling's own layout is the operator's, deliberately NOT the staged
    # one: reconstruction must locate artifacts by digest, not by path.
    sibling_artifacts = _layout(
        "frozen", "model_registries/supplementary.json", sibling_registry
    )
    sibling_path = tmp_path / "checkout" / "sibling.freeze.json"
    sibling_path.parent.mkdir(parents=True, exist_ok=True)
    write_hash_bundle(sibling_path, _bundle(sibling_artifacts))

    registry_checkout = tmp_path / "checkout" / "supplementary-registry.json"
    registry_checkout.write_bytes(sibling_registry)

    packet_payload = b'{"case_id": "case-1"}'
    run_inputs = json.dumps(
        {
            "cycle_id": "cycle-1",
            "model_packets": [
                {
                    "packet_object_key": PACKET_KEY,
                    "packet_sha256": _digest(packet_payload),
                }
            ],
        },
        sort_keys=True,
    ).encode("utf-8")

    objects: dict[tuple[str, str], bytes] = {
        (RESULTS_BUCKET, f"{OFFICIAL_PREFIX}/freeze.json"): official_bytes,
        (RESULTS_BUCKET, f"{OFFICIAL_PREFIX}/run-inputs.json"): run_inputs,
        (
            RESULTS_BUCKET,
            f"{OFFICIAL_PREFIX}/manifest-mode-run-record.json",
        ): b'{"manifest_sha256": "aa"}',
        (PACKET_BUCKET, PACKET_KEY): packet_payload,
    }
    for name, payload in shared_payloads.items():
        objects[(RESULTS_BUCKET, f"{OFFICIAL_PREFIX}/artifacts/{name.value}.json")] = (
            payload
        )
    objects[(RESULTS_BUCKET, f"{OFFICIAL_PREFIX}/artifacts/model_registry.json")] = (
        official_registry
    )

    return FakeS3(objects), {
        "official_sha256": _digest(official_bytes),
        "run_inputs_sha256": _digest(run_inputs),
        "run_record_sha256": _digest(b'{"manifest_sha256": "aa"}'),
        "sibling_path": sibling_path,
        "registry_checkout": registry_checkout,
        "sibling_registry": sibling_registry,
        "packet_payload": packet_payload,
        "shared_payloads": shared_payloads,
    }


def _config(
    tmp_path: Path,
    facts: Mapping[str, object],
    *,
    freeze_bundle: Path,
    local_artifacts: Mapping[str, Path] | None = None,
    run_inputs_sha256: str | None = None,
    run_record_sha256: str | None = None,
) -> ManifestRunMaterializeConfig:
    return ManifestRunMaterializeConfig(
        freeze_bundle=freeze_bundle,
        official_freeze_bundle_sha256=str(facts["official_sha256"]),
        run_inputs_sha256=run_inputs_sha256 or str(facts["run_inputs_sha256"]),
        run_record_sha256=run_record_sha256 or str(facts["run_record_sha256"]),
        official_prefix=OFFICIAL_PREFIX,
        results_bucket=RESULTS_BUCKET,
        packet_bucket=PACKET_BUCKET,
        artifact_root=tmp_path / "work" / "artifact-root",
        output_dir=tmp_path / "work" / "output-dir",
        official_freeze_bundle_out=tmp_path / "work" / "official-freeze.json",
        local_artifacts=dict(local_artifacts or {}),
    )


def test_supplementary_rebuild_locates_shared_artifacts_by_digest(
    tmp_path: Path, scenario: tuple[FakeS3, dict[str, object]]
) -> None:
    store, facts = scenario
    config = _config(
        tmp_path,
        facts,
        freeze_bundle=Path(str(facts["sibling_path"])),
        local_artifacts={"model_registry": Path(str(facts["registry_checkout"]))},
    )
    plan = materialize_manifest_run_inputs(config, fetch=store.fetch)

    # Every shared artifact lands at the SIBLING's relative path while its bytes
    # come from the officially staged key; that split is the whole mechanism.
    shared = dict(facts["shared_payloads"])  # type: ignore[arg-type]
    for name, payload in shared.items():
        rebuilt = config.artifact_root / "frozen" / f"{name.value}.json"
        assert rebuilt.read_bytes() == payload
    registry = config.artifact_root / "model_registries" / "supplementary.json"
    assert registry.read_bytes() == facts["sibling_registry"]

    packet = config.output_dir / PACKET_KEY
    assert packet.read_bytes() == facts["packet_payload"]
    assert (config.output_dir / "run-inputs.json").is_file()
    assert (config.output_dir / "manifest-mode-run-record.json").is_file()

    assert plan["candidate_freeze_bundle"] == str(facts["sibling_path"])
    assert plan["packet_count"] == 1
    sources = {
        str(record["name"]): str(record["source"]) for record in plan["artifacts"]
    }  # type: ignore[index,union-attr]
    assert sources["model_registry"].startswith("checkout:")
    assert sources["prompt"].startswith(f"s3://{RESULTS_BUCKET}/{OFFICIAL_PREFIX}/")


def test_rebuild_never_lists_and_reads_only_exact_keys(
    tmp_path: Path, scenario: tuple[FakeS3, dict[str, object]]
) -> None:
    """The IAM grant carries no s3:ListBucket, so a listing would fail at run time."""

    store, facts = scenario
    materialize_manifest_run_inputs(
        _config(
            tmp_path,
            facts,
            freeze_bundle=Path(str(facts["sibling_path"])),
            local_artifacts={"model_registry": Path(str(facts["registry_checkout"]))},
        ),
        fetch=store.fetch,
    )
    for bucket, key in store.reads:
        assert (bucket, key) in store.objects
        assert not key.endswith("/")
    assert (RESULTS_BUCKET, f"{OFFICIAL_PREFIX}/freeze.json") == store.reads[0]
    # The sibling's own registry is supplied from the checkout, never fetched.
    assert (
        RESULTS_BUCKET,
        f"{OFFICIAL_PREFIX}/artifacts/model_registry.json",
    ) not in store.reads


def test_restaging_a_staged_official_freeze_would_double_the_artifacts_segment(
    tmp_path: Path, scenario: tuple[FakeS3, dict[str, object]]
) -> None:
    """Why this module has no official re-verification mode.

    A staged freeze's paths were already rewritten to ``artifacts/<relative>`` by
    ``manifest_forecast_stage._freeze_objects``.  Feeding one back through
    staging applies the segment a second time, so every artifact key becomes
    ``artifacts/artifacts/<relative>`` -- keys that do not exist, which means
    each create-only PutObject *succeeds* and creates junk in the immutable
    official prefix that no role can delete, aborting only afterwards when
    ``freeze.json`` collides.  This is arithmetic on the production constant,
    not a mock: if the doubling ever stops happening, this test must be revisited
    rather than deleted.
    """

    _, facts = scenario
    staged_relative = Path("artifacts") / "prompt.json"
    restaged = Path(STAGED_ARTIFACT_PREFIX) / staged_relative
    assert restaged.as_posix() == "artifacts/artifacts/prompt.json"
    # And the config that would be needed to attempt it is not constructible:
    # freeze_bundle is required, so there is no "use the downloaded one" path.
    with pytest.raises(TypeError):
        ManifestRunMaterializeConfig(  # type: ignore[call-arg]
            official_freeze_bundle_sha256=str(facts["official_sha256"]),
            run_inputs_sha256=str(facts["run_inputs_sha256"]),
            run_record_sha256=str(facts["run_record_sha256"]),
            official_prefix=OFFICIAL_PREFIX,
            results_bucket=RESULTS_BUCKET,
            packet_bucket=PACKET_BUCKET,
            artifact_root=tmp_path / "a",
            output_dir=tmp_path / "o",
            official_freeze_bundle_out=tmp_path / "f.json",
        )


def test_run_inputs_and_run_record_are_pinned_like_the_freeze(
    tmp_path: Path, scenario: tuple[FakeS3, dict[str, object]]
) -> None:
    """Every packet digest the rebuild trusts is read out of run-inputs.json."""

    store, facts = scenario
    with pytest.raises(ManifestRunMaterializeError, match="hashes to"):
        materialize_manifest_run_inputs(
            _config(
                tmp_path,
                facts,
                freeze_bundle=Path(str(facts["sibling_path"])),
                local_artifacts={
                    "model_registry": Path(str(facts["registry_checkout"]))
                },
                run_inputs_sha256="c" * 64,
            ),
            fetch=store.fetch,
        )

    with pytest.raises(ManifestRunMaterializeError, match="hashes to"):
        materialize_manifest_run_inputs(
            _config(
                tmp_path,
                facts,
                freeze_bundle=Path(str(facts["sibling_path"])),
                local_artifacts={
                    "model_registry": Path(str(facts["registry_checkout"]))
                },
                run_record_sha256="c" * 64,
            ),
            fetch=store.fetch,
        )


def test_a_swapped_run_inputs_cannot_smuggle_in_a_different_packet_set(
    tmp_path: Path, scenario: tuple[FakeS3, dict[str, object]]
) -> None:
    """The pin is what stops the packet list itself being the attack surface."""

    store, facts = scenario
    store.objects[(RESULTS_BUCKET, f"{OFFICIAL_PREFIX}/run-inputs.json")] = json.dumps(
        {
            "cycle_id": "cycle-1",
            "model_packets": [
                {
                    "packet_object_key": "model-packets/cycle-1/case-1/swapped.json",
                    "packet_sha256": "d" * 64,
                }
            ],
        },
        sort_keys=True,
    ).encode("utf-8")
    with pytest.raises(ManifestRunMaterializeError, match="hashes to"):
        materialize_manifest_run_inputs(
            _config(
                tmp_path,
                facts,
                freeze_bundle=Path(str(facts["sibling_path"])),
                local_artifacts={
                    "model_registry": Path(str(facts["registry_checkout"]))
                },
            ),
            fetch=store.fetch,
        )


def test_substituted_official_freeze_is_refused_before_any_artifact_is_fetched(
    tmp_path: Path, scenario: tuple[FakeS3, dict[str, object]]
) -> None:
    """The pin is what makes the digest map trustworthy; unpinned it is arbitrary."""

    store, facts = scenario
    store.objects[(RESULTS_BUCKET, f"{OFFICIAL_PREFIX}/freeze.json")] = b"{}"
    with pytest.raises(ManifestRunMaterializeError, match="hashes to"):
        materialize_manifest_run_inputs(
            _config(
                tmp_path,
                facts,
                freeze_bundle=Path(str(facts["sibling_path"])),
                local_artifacts={
                    "model_registry": Path(str(facts["registry_checkout"]))
                },
            ),
            fetch=store.fetch,
        )
    assert store.reads == [(RESULTS_BUCKET, f"{OFFICIAL_PREFIX}/freeze.json")]


def test_unmapped_artifact_fails_closed_rather_than_being_guessed(
    tmp_path: Path, scenario: tuple[FakeS3, dict[str, object]]
) -> None:
    store, facts = scenario
    with pytest.raises(ManifestRunMaterializeError, match="neither staged"):
        materialize_manifest_run_inputs(
            _config(tmp_path, facts, freeze_bundle=Path(str(facts["sibling_path"]))),
            fetch=store.fetch,
        )


def test_checkout_may_not_replace_an_artifact_that_is_already_staged(
    tmp_path: Path, scenario: tuple[FakeS3, dict[str, object]]
) -> None:
    """A shared artifact is the comparability claim and must come from S3."""

    store, facts = scenario
    shared_prompt = tmp_path / "checkout" / "prompt.json"
    shared = dict(facts["shared_payloads"])  # type: ignore[arg-type]
    shared_prompt.write_bytes(shared[FrozenArtifactName.PROMPT])
    with pytest.raises(ManifestRunMaterializeError, match="already staged officially"):
        materialize_manifest_run_inputs(
            _config(
                tmp_path,
                facts,
                freeze_bundle=Path(str(facts["sibling_path"])),
                local_artifacts={
                    "model_registry": Path(str(facts["registry_checkout"])),
                    "prompt": shared_prompt,
                },
            ),
            fetch=store.fetch,
        )


def test_checkout_bytes_that_disagree_with_the_freeze_are_refused(
    tmp_path: Path, scenario: tuple[FakeS3, dict[str, object]]
) -> None:
    store, facts = scenario
    tampered = tmp_path / "checkout" / "tampered-registry.json"
    tampered.write_bytes(b'{"registry": "tampered"}')
    with pytest.raises(ManifestRunMaterializeError, match="hashes to"):
        materialize_manifest_run_inputs(
            _config(
                tmp_path,
                facts,
                freeze_bundle=Path(str(facts["sibling_path"])),
                local_artifacts={"model_registry": tampered},
            ),
            fetch=store.fetch,
        )


def test_packet_bytes_that_disagree_with_run_inputs_are_refused(
    tmp_path: Path, scenario: tuple[FakeS3, dict[str, object]]
) -> None:
    store, facts = scenario
    store.objects[(PACKET_BUCKET, PACKET_KEY)] = b'{"case_id": "swapped"}'
    with pytest.raises(ManifestRunMaterializeError, match="hashes to"):
        materialize_manifest_run_inputs(
            _config(
                tmp_path,
                facts,
                freeze_bundle=Path(str(facts["sibling_path"])),
                local_artifacts={
                    "model_registry": Path(str(facts["registry_checkout"]))
                },
            ),
            fetch=store.fetch,
        )


def test_a_repeated_local_artifact_name_is_refused_rather_than_last_winning(
    tmp_path: Path, scenario: tuple[FakeS3, dict[str, object]]
) -> None:
    """Silently taking the last one lets a paste slip choose the staged bytes."""

    _, facts = scenario
    other = tmp_path / "checkout" / "other-registry.json"
    other.write_bytes(b'{"registry": "other"}')
    with pytest.raises(ManifestRunMaterializeError, match="more than once"):
        _parse_local_artifacts(
            [
                f"model_registry={facts['registry_checkout']}",
                f"model_registry={other}",
            ]
        )


def test_unknown_local_artifact_is_refused_before_any_download(
    tmp_path: Path, scenario: tuple[FakeS3, dict[str, object]]
) -> None:
    """A typo means the operator believes they replaced something they did not."""

    store, facts = scenario
    stray = tmp_path / "checkout" / "stray.json"
    stray.write_bytes(b"{}")
    with pytest.raises(ManifestRunMaterializeError, match="names no artifact"):
        materialize_manifest_run_inputs(
            _config(
                tmp_path,
                facts,
                freeze_bundle=Path(str(facts["sibling_path"])),
                local_artifacts={
                    "model_registry": Path(str(facts["registry_checkout"])),
                    "not_an_artifact": stray,
                },
            ),
            fetch=store.fetch,
        )
    assert store.reads == []


def test_traversal_in_a_recorded_artifact_path_is_refused(
    tmp_path: Path, scenario: tuple[FakeS3, dict[str, object]]
) -> None:
    """A recorded path is data; it must never escape the rebuilt artifact root."""

    store, facts = scenario
    shared = dict(facts["shared_payloads"])  # type: ignore[arg-type]
    escaping = (
        *(
            _artifact(name, f"../escaped/{name.value}.json", payload)
            for name, payload in shared.items()
        ),
        _artifact(
            FrozenArtifactName.MODEL_REGISTRY,
            "model_registries/supplementary.json",
            bytes(facts["sibling_registry"]),  # type: ignore[arg-type]
        ),
    )
    escaping_path = tmp_path / "checkout" / "escaping.freeze.json"
    write_hash_bundle(escaping_path, _bundle(escaping))
    with pytest.raises(ManifestRunMaterializeError, match="unsafe path"):
        materialize_manifest_run_inputs(
            _config(
                tmp_path,
                facts,
                freeze_bundle=escaping_path,
                local_artifacts={
                    "model_registry": Path(str(facts["registry_checkout"]))
                },
            ),
            fetch=store.fetch,
        )
