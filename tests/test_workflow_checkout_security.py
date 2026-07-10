from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_ROOT = ROOT / ".github" / "workflows"


def test_checkout_steps_disable_credential_persistence() -> None:
    checkout_steps: list[tuple[Path, int]] = []
    unsecured_steps: list[str] = []

    for workflow_path in sorted(WORKFLOW_ROOT.glob("*.y*ml")):
        lines = workflow_path.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            if "uses: actions/checkout@" not in line:
                continue
            checkout_steps.append((workflow_path, index + 1))
            step_indent = len(line) - len(line.lstrip()) - 2
            step_block: list[str] = []
            for candidate in lines[index + 1 :]:
                candidate_indent = len(candidate) - len(candidate.lstrip())
                if (
                    candidate.lstrip().startswith("- ")
                    and candidate_indent <= step_indent
                ):
                    break
                step_block.append(candidate)
            if not any(
                candidate.strip() == "persist-credentials: false"
                for candidate in step_block
            ):
                unsecured_steps.append(f"{workflow_path.name}:{index + 1}")

    assert checkout_steps, "expected at least one actions/checkout step"
    assert not unsecured_steps, (
        "actions/checkout steps must set persist-credentials: false: "
        + ", ".join(unsecured_steps)
    )
