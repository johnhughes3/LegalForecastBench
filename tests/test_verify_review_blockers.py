from scripts.verify_review_blockers import check_b1_5, check_v2_8


def test_release_timestamp_check_accepts_non_model_registry_manifests() -> None:
    ok, detail = check_b1_5()

    assert ok, detail


def test_release_timestamp_source_check_accepts_non_model_registry_manifests() -> None:
    ok, detail = check_v2_8()

    assert ok, detail
