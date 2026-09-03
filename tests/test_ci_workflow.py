from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/ci.yaml").read_text(encoding="utf-8")
CI_RUNNER_CLAMP = (
    "runs-on: ${{ (vars.CI_RUNNER == 'ubuntu-latest' || "
    "startsWith(vars.CI_RUNNER, 'ubicloud-')) && vars.CI_RUNNER || "
    "'ubicloud-standard-2' }}"
)


def test_ci_workflow_uses_ci_runner_clamp_with_ubicloud_fallback() -> None:
    assert CI_RUNNER_CLAMP in WORKFLOW
    assert "runs-on: ubuntu-latest" not in WORKFLOW
    assert "runs-on: ${{ vars.CI_RUNNER }}" not in WORKFLOW


def test_ci_workflow_runs_contract_ratchet_before_typecheck() -> None:
    ratchet_step = (
        "- name: Contract ratchet\n"
        "        run: uv run python -m legalforecast.contracts.ratchet"
    )
    assert ratchet_step in WORKFLOW
    assert WORKFLOW.index(ratchet_step) < WORKFLOW.index(
        "- name: Type-check\n        run: uv run pyright"
    )


def test_ci_workflow_fetches_origin_main_before_acquisition_config_fence() -> None:
    """The fence needs origin/main present, and the checkout must supply it.

    The property under test is that ``origin/main`` is resolvable by the time
    the acquisition-config fence runs.  It is deliberately NOT satisfied by a
    separate ``git fetch``: the checkout sets ``persist-credentials: false``
    so no later step holds a token, and a bare fetch against this private
    repository dies with ``could not read Username for 'https://github.com'``
    (legalforecastbench-58v3).  ``fetch-depth: 0`` makes the checkout action
    fetch full history and refs under its own credentials instead.
    """

    checkout_step = "uses: actions/checkout@"
    fence_step = (
        "- name: Acquisition config fence\n"
        "        run: uv run python -m legalforecast.config.fence"
    )
    assert "fetch-depth: 0" in WORKFLOW
    assert "persist-credentials: false" in WORKFLOW
    assert WORKFLOW.index(checkout_step) < WORKFLOW.index("fetch-depth: 0")
    assert WORKFLOW.index("fetch-depth: 0") < WORKFLOW.index(fence_step)
    # The unauthenticated fetch this replaced must not come back.
    assert "git fetch --no-tags origin main" not in WORKFLOW
