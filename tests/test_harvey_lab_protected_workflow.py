"""Structural production-wiring checks for clean-native Harvey LAB."""

from pathlib import Path

WORKFLOW_PATH = Path(".github/workflows/run-harvey-lab-clean-native.yaml").resolve()
WORKFLOW = WORKFLOW_PATH.read_text(encoding="utf-8")


def test_workflow_uses_native_lab_inputs_instead_of_forecast_release_descriptor() -> (
    None
):
    assert "workflow_dispatch:" in WORKFLOW
    assert "model_registry_path:" in WORKFLOW
    assert "forecast_release_uri:" not in WORKFLOW
    assert "manifest_uri:" not in WORKFLOW
    assert "legalforecast.multiharness.harvey_lab_paid_gateway_descriptor" in WORKFLOW
    assert "legalforecast.multiharness.paid_gateway_descriptor" not in WORKFLOW


def test_workflow_runs_real_clean_native_producers_and_consumer_in_order() -> None:
    checkout = "Checkout pinned Harvey LAB v1.1.0 source"
    prepare = "legalforecast harvey-lab prepare-clean-native"
    install = "legalforecast multiharness tier0 install-evaluator-wrapper"
    issue = "Issue native Harvey LAB paid descriptor"
    execute = "legalforecast harvey-lab run-clean-native"
    assert WORKFLOW.index(checkout) < WORKFLOW.index(prepare)
    assert WORKFLOW.index(prepare) < WORKFLOW.index(install)
    assert WORKFLOW.index(install) < WORKFLOW.index(issue)
    assert WORKFLOW.index(issue) < WORKFLOW.index(execute)
    assert "1dd81403b2fbb60596f7aea3fcecafad7bf73143" in WORKFLOW
    assert "bc7e16d2b5b794b86624288506a5d0be17c1052b" in WORKFLOW


def test_workflow_pins_images_and_reuses_one_protected_ceiling_journal() -> None:
    assert "environment: legalforecastbench-official-eval" in WORKFLOW
    assert "id-token: write" in WORKFLOW
    assert "LFB_PROVIDER_AUTHORITY_TABLE" in WORKFLOW
    assert "LFB_PROVIDER_AUTHORITY_RESOURCE_IDENTITY_SHA256" in WORKFLOW
    assert WORKFLOW.count("ceiling_microusd:") == 1
    assert '--ceiling-microusd "${CEILING_MICROUSD}"' in WORKFLOW
    assert "infra/claude-code-runtime/Containerfile" in WORKFLOW
    assert "infra/model-gateway-runtime/Containerfile" in WORKFLOW
    assert '--solver-image "${LFB_HARVEY_LAB_SOLVER_IMAGE}"' in WORKFLOW
    assert '--gateway-image "${LFB_HARVEY_LAB_GATEWAY_IMAGE}"' in WORKFLOW
    assert WORKFLOW.count("secrets.ANTHROPIC_API_KEY") == 1


def test_workflow_does_not_reintroduce_native_thin_or_signature_machinery() -> None:
    assert "native-thin" not in WORKFLOW
    assert "podman.sock" not in WORKFLOW
    assert "docker.sock" not in WORKFLOW
    assert "private_key" not in WORKFLOW
    assert "approval_reference" not in WORKFLOW
    assert "signature" not in WORKFLOW.casefold()
    assert "ed25519" not in WORKFLOW.casefold()


def test_workflow_never_uploads_evaluator_private_or_judge_attempts() -> None:
    upload = WORKFLOW.split("- name: Upload non-rubric run evidence", maxsplit=1)[1]
    assert "/tmp/lfb-harvey-lab/input/paid-gateway.json" not in upload
    assert "/tmp/lfb-harvey-lab/input/evaluator-private" not in upload
    assert "/tmp/lfb-harvey-lab/run/evaluator-overlay" not in upload
    assert "/tmp/lfb-harvey-lab/run/evaluator-work" not in upload
    assert "/tmp/lfb-harvey-lab/run/judge-attempts" not in upload
    assert "/tmp/lfb-harvey-lab/run/container-results/*/package" in upload
    assert "/tmp/lfb-harvey-lab/run/container-results\n" not in upload
    assert "/tmp/lfb-harvey-lab/run/sealed" in upload

    path_block = upload.split("path: |", maxsplit=1)[1].split(
        "if-no-files-found:", maxsplit=1
    )[0]
    assert tuple(line.strip() for line in path_block.splitlines() if line.strip()) == (
        "/tmp/lfb-harvey-lab/run-summary.json",
        "/tmp/lfb-harvey-lab/input/wrapper-install.json",
        "/tmp/lfb-harvey-lab/run/container-results/*/package",
        "/tmp/lfb-harvey-lab/run/sealed",
    )
