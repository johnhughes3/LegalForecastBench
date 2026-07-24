from __future__ import annotations

import base64
import hashlib
import json
import os
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast

import pytest
from legalforecast.cli import main
from legalforecast.ingestion.disclosure_review_authority import (
    CYCLE_1_DISCLOSURE_AUTHORITY_IDENTITY,
    MAIN_DISCLOSURE_REVIEW_AUTHORITY_REGISTRY,
    DisclosureReviewAuthorityError,
    DisclosureReviewAuthorityIdentity,
    DisclosureReviewAuthorityRegistryEntry,
    _load_registered_disclosure_review_authority,  # pyright: ignore[reportPrivateUsage]
    authority_artifact_bytes,
    disclosure_authority_identity_from_cohort_policy,
    generate_disclosure_review_authority,
    load_main_disclosure_review_authority,
    verify_disclosure_review_authority,
    write_disclosure_review_authority,
)


def _ssh_string(value: bytes) -> bytes:
    return len(value).to_bytes(4, "big") + value


def _reviewer_policy(*, reviewer_id: str = "john-hughes") -> bytes:
    algorithm = b"sk-ssh-ed25519@openssh.com"
    public_key = b"K" * 32
    application = b"ssh:legalforecastbench"
    blob = _ssh_string(algorithm) + _ssh_string(public_key) + _ssh_string(application)
    payload = {
        "schema_version": "legalforecast.disclosure_reviewer_policy.v1",
        "reviewer_id": reviewer_id,
        "ssh_principal": "john-hughes",
        "ssh_public_key": f"{algorithm.decode()} {base64.b64encode(blob).decode()}",
        "identity_kind": "human_hardware",
        "controlled_store_uri_prefix": "private-store://legalforecast/cycle-1",
        "signature_namespace": "legalforecast-disclosure-review-v1",
    }
    return (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _cohort_policy() -> dict[str, object]:
    return {
        "schema_version": "legalforecast.cohort_policy.v1",
        "policy": {
            "cycle_id": CYCLE_1_DISCLOSURE_AUTHORITY_IDENTITY.cycle_id,
            "eligibility_anchor": "2026-06-30",
        },
        "policy_sha256": CYCLE_1_DISCLOSURE_AUTHORITY_IDENTITY.cohort_policy_sha256,
    }


def _identity() -> DisclosureReviewAuthorityIdentity:
    return DisclosureReviewAuthorityIdentity(
        cycle_id="test-cycle",
        cohort_policy_sha256="a" * 64,
        eligibility_anchor=date(2026, 6, 30),
    )


def _artifact() -> dict[str, object]:
    return generate_disclosure_review_authority(_identity(), _reviewer_policy())


def test_generate_and_verify_authority_round_trip() -> None:
    artifact = _artifact()

    authority = verify_disclosure_review_authority(
        authority_artifact_bytes(artifact),
        expected_identity=_identity(),
        reviewer_policy_bytes=_reviewer_policy(),
    )

    assert authority.identity == _identity()
    assert authority.reviewer_id == "john-hughes"
    assert authority.identity_kind == "human_hardware"
    assert authority.ssh_key_type == "sk-ssh-ed25519@openssh.com"
    assert authority.ssh_public_key_fingerprint.startswith("SHA256:")
    assert (
        authority.reviewer_policy_sha256
        == hashlib.sha256(_reviewer_policy()).hexdigest()
    )


def test_write_authority_is_immutable_and_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "authority.json"
    artifact = _artifact()

    write_disclosure_review_authority(
        path, artifact, reviewer_policy_bytes=_reviewer_policy()
    )
    first = path.read_bytes()
    write_disclosure_review_authority(
        path, artifact, reviewer_policy_bytes=_reviewer_policy()
    )

    assert path.read_bytes() == authority_artifact_bytes(artifact)
    assert path.read_bytes() == first

    changed = generate_disclosure_review_authority(
        _identity(), _reviewer_policy(reviewer_id="other-reviewer")
    )
    with pytest.raises(DisclosureReviewAuthorityError, match="immutable content"):
        write_disclosure_review_authority(
            path,
            changed,
            reviewer_policy_bytes=_reviewer_policy(reviewer_id="other-reviewer"),
        )


def test_authority_artifact_cli_round_trip(tmp_path: Path) -> None:
    cohort_fixture = json.loads(
        Path("tests/fixtures/recap_fetch_broker_policy/cohort-policy.json").read_text()
    )
    cohort_fixture["policy"]["eligibility_anchor"] = "2026-06-30"
    cohort_fixture["policy"]["stop_rule"]["search_window_end"] = "2026-07-23"
    cohort_fixture["policy_sha256"] = hashlib.sha256(
        json.dumps(
            cohort_fixture["policy"], sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()
    cohort_policy = tmp_path / "cohort-policy.json"
    cohort_policy.write_text(
        json.dumps(cohort_fixture, sort_keys=True, separators=(",", ":")) + "\n"
    )
    reviewer_policy = tmp_path / "reviewer-policy.json"
    reviewer_policy.write_bytes(_reviewer_policy())
    authority_path = tmp_path / "authority.json"

    assert (
        main(
            [
                "acquisition",
                "generate-disclosure-review-authority",
                "--cohort-policy",
                str(cohort_policy),
                "--reviewer-policy",
                str(reviewer_policy),
                "--output",
                str(authority_path),
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "acquisition",
                "verify-disclosure-review-authority",
                "--cohort-policy",
                str(cohort_policy),
                "--reviewer-policy",
                str(reviewer_policy),
                "--authority",
                str(authority_path),
            ]
        )
        == 0
    )


@pytest.mark.parametrize(
    "command",
    [
        "generate-disclosure-review-authority",
        "verify-disclosure-review-authority",
    ],
)
def test_authority_artifact_cli_help_is_explicit(
    command: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["acquisition", command, "--help"])
    assert exc.value.code == 0
    help_text = capsys.readouterr().out
    assert "--cohort-policy" in help_text
    assert "--reviewer-policy" in help_text


@pytest.mark.parametrize("field", ["schema_version", "authority", "authority_sha256"])
def test_verify_rejects_missing_top_level_field(field: str) -> None:
    artifact = _artifact()
    del artifact[field]

    with pytest.raises(DisclosureReviewAuthorityError, match="exact fields"):
        verify_disclosure_review_authority(
            authority_artifact_bytes(artifact),
            expected_identity=_identity(),
            reviewer_policy_bytes=_reviewer_policy(),
        )


def test_verify_rejects_extra_field_and_noncanonical_bytes() -> None:
    artifact = _artifact()
    artifact["extra"] = True
    with pytest.raises(DisclosureReviewAuthorityError, match="exact fields"):
        verify_disclosure_review_authority(
            authority_artifact_bytes(artifact),
            expected_identity=_identity(),
            reviewer_policy_bytes=_reviewer_policy(),
        )

    canonical = authority_artifact_bytes(_artifact())
    with pytest.raises(DisclosureReviewAuthorityError, match="canonical"):
        verify_disclosure_review_authority(
            canonical.replace(b'"authority":', b'"authority": '),
            expected_identity=_identity(),
            reviewer_policy_bytes=_reviewer_policy(),
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("cycle_id", "other-cycle", "cycle_id"),
        ("cohort_policy_sha256", "b" * 64, "cohort policy"),
        ("eligibility_anchor", "2026-07-01", "eligibility anchor"),
        ("reviewer_id", "substitute-reviewer", "reviewer"),
        ("identity_kind", "controlled_store_service", "human_hardware"),
        ("ssh_key_type", "ssh-ed25519", "key"),
        ("ssh_public_key_fingerprint", "SHA256:substitute", "fingerprint"),
        ("reviewer_policy_sha256", "c" * 64, "reviewer policy"),
        ("signature_namespace", "other-namespace", "namespace"),
        ("controlled_store_uri_prefix", "private-store://other/root", "store"),
    ],
)
def test_verify_rejects_authority_substitutions(
    field: str, value: str, message: str
) -> None:
    artifact = _artifact()
    authority = artifact["authority"]
    assert isinstance(authority, dict)
    authority[field] = value
    artifact["authority_sha256"] = hashlib.sha256(
        (json.dumps(authority, sort_keys=True, separators=(",", ":")) + "\n").encode()
    ).hexdigest()

    with pytest.raises(DisclosureReviewAuthorityError, match=message):
        verify_disclosure_review_authority(
            authority_artifact_bytes(artifact),
            expected_identity=_identity(),
            reviewer_policy_bytes=_reviewer_policy(),
        )


def test_verify_rejects_authority_hash_drift() -> None:
    artifact = _artifact()
    artifact["authority_sha256"] = "d" * 64

    with pytest.raises(DisclosureReviewAuthorityError, match="hash"):
        verify_disclosure_review_authority(
            authority_artifact_bytes(artifact),
            expected_identity=_identity(),
            reviewer_policy_bytes=_reviewer_policy(),
        )


def test_generate_rejects_noncanonical_or_non_hardware_reviewer_policy() -> None:
    policy = json.loads(_reviewer_policy())
    policy["extra"] = True
    with pytest.raises(DisclosureReviewAuthorityError, match="exact fields"):
        generate_disclosure_review_authority(
            _identity(),
            (json.dumps(policy, sort_keys=True, separators=(",", ":")) + "\n").encode(),
        )

    policy = json.loads(_reviewer_policy())
    policy["identity_kind"] = "controlled_store_service"
    with pytest.raises(DisclosureReviewAuthorityError, match="human_hardware"):
        generate_disclosure_review_authority(
            _identity(),
            (json.dumps(policy, sort_keys=True, separators=(",", ":")) + "\n").encode(),
        )


def test_identity_derivation_checks_loaded_policy_semantics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import legalforecast.ingestion.disclosure_review_authority as module

    def verify_test_policy(artifact: Mapping[str, Any]) -> str:
        del artifact
        return "a" * 64

    monkeypatch.setattr(module, "verify_cohort_policy", verify_test_policy)
    artifact = {
        "policy": {"cycle_id": "test-cycle", "eligibility_anchor": "2026-06-30"}
    }
    assert disclosure_authority_identity_from_cohort_policy(artifact) == _identity()

    artifact["policy"] = {"cycle_id": "test-cycle", "eligibility_anchor": "2026-07-01"}
    with pytest.raises(DisclosureReviewAuthorityError, match="anchor"):
        disclosure_authority_identity_from_cohort_policy(artifact)


def test_main_registry_is_immutable_and_official_entry_is_unprovisioned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import legalforecast.ingestion.disclosure_review_authority as module

    with pytest.raises(TypeError):
        cast(
            dict[
                DisclosureReviewAuthorityIdentity,
                DisclosureReviewAuthorityRegistryEntry,
            ],
            MAIN_DISCLOSURE_REVIEW_AUTHORITY_REGISTRY,
        )[
            CYCLE_1_DISCLOSURE_AUTHORITY_IDENTITY
        ] = DisclosureReviewAuthorityRegistryEntry(
            status="unprovisioned",
            blocker_bead="other",
        )

    with pytest.raises(
        DisclosureReviewAuthorityError,
        match=r"LegalForecastBench-5qd6\.39\.7\.1",
    ):

        def verify_official_policy(artifact: Mapping[str, Any]) -> str:
            del artifact
            return CYCLE_1_DISCLOSURE_AUTHORITY_IDENTITY.cohort_policy_sha256

        monkeypatch.setattr(
            module,
            "verify_cohort_policy",
            verify_official_policy,
        )
        load_main_disclosure_review_authority(
            _cohort_policy(), reviewer_policy_bytes=_reviewer_policy()
        )


def _provisioned_registry(
    root: Path,
) -> tuple[
    MappingProxyType[
        DisclosureReviewAuthorityIdentity, DisclosureReviewAuthorityRegistryEntry
    ],
    Path,
]:
    artifact_path = root / "test-authority.json"
    payload = authority_artifact_bytes(_artifact())
    artifact_path.write_bytes(payload)
    registry = MappingProxyType(
        {
            _identity(): DisclosureReviewAuthorityRegistryEntry(
                status="provisioned",
                blocker_bead=None,
                resource_name=artifact_path.name,
                resource_sha256=hashlib.sha256(payload).hexdigest(),
            )
        }
    )
    return registry, artifact_path


def test_injected_registry_loads_exact_resource(tmp_path: Path) -> None:
    registry, _ = _provisioned_registry(tmp_path)

    authority = _load_registered_disclosure_review_authority(
        _identity(),
        reviewer_policy_bytes=_reviewer_policy(),
        registry=registry,
        resource_root=tmp_path,
    )

    assert authority.identity == _identity()


def test_registered_load_rejects_missing_identity_and_resource_drift(
    tmp_path: Path,
) -> None:
    registry, path = _provisioned_registry(tmp_path)
    with pytest.raises(DisclosureReviewAuthorityError, match="not registered"):
        _load_registered_disclosure_review_authority(
            DisclosureReviewAuthorityIdentity("other", "a" * 64, date(2026, 6, 30)),
            reviewer_policy_bytes=_reviewer_policy(),
            registry=registry,
            resource_root=tmp_path,
        )

    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(DisclosureReviewAuthorityError, match="resource hash"):
        _load_registered_disclosure_review_authority(
            _identity(),
            reviewer_policy_bytes=_reviewer_policy(),
            registry=registry,
            resource_root=tmp_path,
        )


def test_registered_load_rejects_symlink_and_hardlink(tmp_path: Path) -> None:
    registry, path = _provisioned_registry(tmp_path)
    real = tmp_path / "real.json"
    path.rename(real)
    path.symlink_to(real)
    with pytest.raises(DisclosureReviewAuthorityError, match="symlink"):
        _load_registered_disclosure_review_authority(
            _identity(),
            reviewer_policy_bytes=_reviewer_policy(),
            registry=registry,
            resource_root=tmp_path,
        )

    path.unlink()
    os.link(real, path)
    with pytest.raises(DisclosureReviewAuthorityError, match="hardlink"):
        _load_registered_disclosure_review_authority(
            _identity(),
            reviewer_policy_bytes=_reviewer_policy(),
            registry=registry,
            resource_root=tmp_path,
        )


@pytest.mark.parametrize("resource_name", ["../authority.json", "a/b.json", ".json"])
def test_registered_load_rejects_unsafe_resource_names(
    resource_name: str,
) -> None:
    with pytest.raises(DisclosureReviewAuthorityError, match="resource name"):
        DisclosureReviewAuthorityRegistryEntry(
            status="provisioned",
            blocker_bead=None,
            resource_name=resource_name,
            resource_sha256="a" * 64,
        )
