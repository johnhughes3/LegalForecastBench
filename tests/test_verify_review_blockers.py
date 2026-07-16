import json
from pathlib import Path

from scripts.verify_review_blockers import check_b1_5, check_v2_8


def _write_registry_and_policy_manifest(registry_dir: Path) -> None:
    (registry_dir / "provider-caps.json").write_text(
        json.dumps({"provider": "example", "spend_cap_usd": 10}),
        encoding="utf-8",
    )
    (registry_dir / "models.json").write_text(
        json.dumps(
            [
                {
                    "provider": "example",
                    "model_id": "example-model",
                    "release_timestamp": "2026-01-01T00:00:00Z",
                    "release_timestamp_source": "https://example.invalid/model",
                }
            ]
        ),
        encoding="utf-8",
    )


def test_release_timestamp_check_accepts_non_model_registry_manifests(
    tmp_path: Path,
) -> None:
    _write_registry_and_policy_manifest(tmp_path)

    ok, detail = check_b1_5(tmp_path)

    assert ok, detail


def test_release_timestamp_source_check_accepts_non_model_registry_manifests(
    tmp_path: Path,
) -> None:
    _write_registry_and_policy_manifest(tmp_path)

    ok, detail = check_v2_8(tmp_path)

    assert ok, detail
