"""The provider cell's own pre-credential execution-scope lane gate.

``legalforecastbench-y4vg``: all ~100 Gemini cells of run 33309284583 died in the
composite action's "Verify frozen provider-cell inputs" step, which called
``verify_execution_scope_runtime`` without ``expected_supplementary`` and did not
even declare ``SUPPLEMENTARY`` in its ``env:`` block.  Nothing tested that step:
PR #1003's end-to-end supplementary test drove ``run_per_case_evaluation``
directly, which the cell reaches only *after* this step passes -- the same blind
spot that hid ``legalforecastbench-xv1r``.

The tests here therefore execute the step's *real* inline Python, extracted from
``action.yml`` and run in a child process under the environment the step's own
``env:`` block resolves, rather than asserting on its source text.

Two structural notes.  This lives beside
``test_supplementary_predispatch_chain.py`` rather than inside it because that
file is already carried in the architecture baseline as ``oversized`` with a
planned-seam disposition (``legalforecastbench-m1pv.7``); growing it further
would ratchet a guard the repository maintains deliberately.  It imports that
module's chain builders because they are the suite's only real supplementary
authorization chain -- a second copy would be a second thing to keep true.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final, cast

import pytest
from legalforecast.protocol.manifest import hash_payload

from test_supplementary_predispatch_chain import (
    CYCLE_ID,
    ROOT,
    SUPPLEMENTARY_MODEL_KEY,
    _chain,
    _parsed,
    _scope,
    _scope_observation,
    _write_json,
)

PROVIDER_CELL_ACTION: Final = (
    ROOT / ".github" / "actions" / "official-provider-cell" / "action.yml"
)
PROVIDER_CELL_VERIFY_STEP: Final = "Verify frozen provider-cell inputs"
# The step reads its artifacts from a fixed runner path.  Tests must not create
# it: the suite runs four xdist workers in a worktree shared with other agents.
PROVIDER_CELL_INPUT_ROOT: Final = '"/tmp/lfb-provider-cell-inputs"'
_STEP_INPUT = re.compile(r"\$\{\{\s*inputs\.([a-z0-9_]+)\s*\}\}")


def _provider_cell_step(name: str) -> str:
    """Return one composite step's YAML block, without a YAML parser.

    ``pyyaml`` is not a dependency of this project and a P0 fix is the wrong
    place to add one, so the block is sliced on the two-space step indentation
    the file uses throughout.
    """

    text = PROVIDER_CELL_ACTION.read_text(encoding="utf-8")
    marker = f"  - name: {name}\n"
    start = text.index(marker)
    following = text.find("\n  - name: ", start + len(marker))
    return text[start:] if following == -1 else text[start : following + 1]


def _provider_cell_step_env(block: str) -> dict[str, str]:
    """Resolve the step's ``env:`` block into ``{env name: input name}``."""

    env_start = block.index("    env:\n") + len("    env:\n")
    env_end = block.index("    run: |\n", env_start)
    resolved: dict[str, str] = {}
    for line in block[env_start:env_end].splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        name, _, expression = line.strip().partition(": ")
        match = _STEP_INPUT.fullmatch(expression.strip())
        if match is not None:
            resolved[name] = match.group(1)
    return resolved


def _provider_cell_verification_script(root: Path) -> str:
    """Extract the step's heredoc Python, rebased onto a per-test input root."""

    block = _provider_cell_step(PROVIDER_CELL_VERIFY_STEP)
    opener = "      uv run python - <<'PY'\n"
    start = block.index(opener) + len(opener)
    end = block.index("\n      PY\n", start)
    body = "\n".join(
        line[6:] if line.startswith("      ") else line
        for line in block[start:end].splitlines()
    )
    assert PROVIDER_CELL_INPUT_ROOT in body, (
        "the provider cell no longer reads /tmp/lfb-provider-cell-inputs; update "
        "this harness rather than letting it silently verify nothing"
    )
    return body.replace(PROVIDER_CELL_INPUT_ROOT, json.dumps(str(root)))


def _run_provider_cell_verification(
    *, inputs: Mapping[str, str], root: Path
) -> subprocess.CompletedProcess[str]:
    """Run the real step against ``root`` with only the env it declares.

    The child sees exactly the variables the step's ``env:`` block resolves, so
    an input the action defines but never threads into this step is unreachable
    here for the same reason it was unreachable on the runner.
    """

    declared = _provider_cell_step_env(_provider_cell_step(PROVIDER_CELL_VERIFY_STEP))
    unreachable = sorted(set(inputs) - set(declared.values()))
    assert not unreachable, (
        f"{PROVIDER_CELL_VERIFY_STEP!r} does not expose inputs {unreachable} in its "
        "env block, so the step cannot read them; a value a step cannot read "
        "cannot gate anything"
    )
    environment = {
        name: inputs[input_name]
        for name, input_name in declared.items()
        if input_name in inputs
    }
    return subprocess.run(
        [sys.executable, "-c", _provider_cell_verification_script(root)],
        capture_output=True,
        check=False,
        cwd=ROOT,
        env={**os.environ, **environment},
        text=True,
    )


def _official_shape(
    scope: Mapping[str, Any], receipt: Mapping[str, Any]
) -> dict[str, Any]:
    """Re-card a supplementary scope as a complete official one.

    Two differences, both inside the hashed ``scope`` object: the official card
    has no ``supplementary_binding``, and its ``owner_evidence`` embeds the whole
    ``bd comments`` payload where the supplementary card publishes only its
    digest.  Rebuilding both is what makes the official-lane cases exercise the
    lane gate rather than stopping at a half-formed card.
    """

    body = {
        key: value
        for key, value in cast(dict[str, Any], scope["scope"]).items()
        if key != "supplementary_binding"
    }
    body["owner_evidence"] = _parsed(_scope_observation(receipt))
    return {
        "schema_version": "legalforecast.execution_scope.v1",
        "scope": body,
        "scope_sha256": hash_payload(body),
    }


def _provider_cell_inputs(
    root: Path,
    *,
    scope: Mapping[str, Any],
    plan: Mapping[str, Any],
    registry: Path,
    supplementary: bool,
) -> dict[str, str]:
    """Write the five frozen artifacts the step requires, plus the scope."""

    root.mkdir(parents=True, exist_ok=True)
    _write_json(root / "lfb-execution-policy.json", plan)
    _write_json(root / "lfb-execution-scope.json", scope)
    # The step hashes the registry file, so its bytes must be the real ones.
    (root / "lfb-model-registry.json").write_bytes(registry.read_bytes())
    (root / "lfb-labels.jsonl").write_text("", encoding="utf-8")
    _write_json(root / "lfb-run-inputs-frozen.json", {"cycle_id": CYCLE_ID})
    policy_sha256 = cast(str, plan["policy_sha256"])
    _write_json(
        root / "lfb-dispatch-provenance.json",
        {"execution_policy_sha256": policy_sha256},
    )
    frozen_inputs = cast(
        dict[str, Any],
        cast(dict[str, Any], scope["scope"])["common_frozen_inputs"],
    )
    return {
        "ablation": "full_packet",
        "cycle_id": CYCLE_ID,
        "execution_policy_sha256": policy_sha256,
        "execution_scope_sha256": cast(str, scope["scope_sha256"]),
        "freeze_bundle_sha256": cast(str, frozen_inputs["freeze_bundle_sha256"]),
        "model_key": SUPPLEMENTARY_MODEL_KEY,
        "supplementary": "true" if supplementary else "false",
    }


def test_provider_cell_step_can_read_the_lane_it_must_gate_on() -> None:
    """The compounding half of y4vg: the value was not reachable from the step.

    The action defines ``supplementary`` and threads it to the runner, so the
    lane looked plumbed; the pre-credential scope gate that runs first never
    received it.
    """

    block = _provider_cell_step(PROVIDER_CELL_VERIFY_STEP)
    assert _provider_cell_step_env(block)["SUPPLEMENTARY"] == "supplementary"
    assert 'expected_supplementary=os.environ["SUPPLEMENTARY"] == "true",' in block


def test_provider_cell_accepts_a_supplementary_scope_on_a_supplementary_cell(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The exact ~100-cell failure of run 33309284583, inverted into a pass."""

    chain = _chain(tmp_path, monkeypatch)
    scope, plan, _receipt = _scope(chain, tmp_path, monkeypatch)
    root = tmp_path / "supplementary-cell"

    result = _run_provider_cell_verification(
        inputs=_provider_cell_inputs(
            root,
            scope=scope,
            plan=plan,
            registry=chain.supplementary_registry,
            supplementary=True,
        ),
        root=root,
    )

    assert result.returncode == 0, result.stderr


def test_provider_cell_refuses_an_official_scope_on_a_supplementary_cell(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The expensive direction.

    A wrong-lane scope accepted here would open provider credentials and surface
    only at the write-once shard receipt, after the run is paid for.
    """

    chain = _chain(tmp_path, monkeypatch)
    scope, plan, receipt = _scope(chain, tmp_path, monkeypatch)
    root = tmp_path / "supplementary-cell-official-scope"

    result = _run_provider_cell_verification(
        inputs=_provider_cell_inputs(
            root,
            scope=_official_shape(scope, receipt),
            plan=plan,
            registry=chain.supplementary_registry,
            supplementary=True,
        ),
        root=root,
    )

    assert result.returncode != 0
    assert "execution scope schema is not the expected lane" in result.stderr
    assert "legalforecast.execution_scope_supplementary.v1" in result.stderr


def test_provider_cell_accepts_an_official_scope_on_an_official_cell(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression guard: the official four's cell behaves exactly as before."""

    chain = _chain(tmp_path, monkeypatch)
    scope, plan, receipt = _scope(chain, tmp_path, monkeypatch)
    root = tmp_path / "official-cell"

    result = _run_provider_cell_verification(
        inputs=_provider_cell_inputs(
            root,
            scope=_official_shape(scope, receipt),
            plan=plan,
            registry=chain.supplementary_registry,
            supplementary=False,
        ),
        root=root,
    )

    assert result.returncode == 0, result.stderr


def test_provider_cell_refuses_a_supplementary_scope_on_an_official_cell(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression guard: the observed production refusal, kept for the official
    lane, where refusing is the correct answer."""

    chain = _chain(tmp_path, monkeypatch)
    scope, plan, _receipt = _scope(chain, tmp_path, monkeypatch)
    root = tmp_path / "official-cell-supplementary-scope"

    result = _run_provider_cell_verification(
        inputs=_provider_cell_inputs(
            root,
            scope=scope,
            plan=plan,
            registry=chain.supplementary_registry,
            supplementary=False,
        ),
        root=root,
    )

    assert result.returncode != 0
    assert "execution scope schema is not the expected lane" in result.stderr
    assert "legalforecast.execution_scope.v1" in result.stderr


def test_shard_receipt_writer_declares_its_lane_inside_its_own_job() -> None:
    """The canonical workflow persists each provider cell's durable receipt."""

    workflow = (ROOT / ".github" / "workflows" / "run-benchmark.yaml").read_text()
    for provider, next_job in (
        ("run-openai", "run-anthropic"),
        ("run-anthropic", "run-gemini"),
        ("run-gemini", "score-and-report"),
    ):
        job = workflow[
            workflow.index(f"\n  {provider}:") : workflow.index(f"\n  {next_job}:")
        ]
        assert "--ledger /tmp/lfb-run/ledger.sqlite3" in job
        assert "--receipts-dir /tmp/lfb-run/receipts" in job
        assert "Persist" in job
        assert "if: ${{ always() }}" in job
