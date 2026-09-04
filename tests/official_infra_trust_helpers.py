"""Production-byte parsers for the OIDC trust satisfiability fences.

The satisfiability tests in ``test_official_eval_infra.py`` and
``test_official_eval_bootstrap_infra.py`` must discriminate on the deployed
inputs -- the Terraform locals and variable defaults that render
``github-oidc-trust.json.tftpl``, plus the exact workflow job that assumes the
role -- never on test-owned copies of those values. These helpers extract the
production values, and the mutation helper edits the same production bytes so
each fence can prove in-suite that it reddens when the real inputs drift.

Every extractor asserts it matched exactly once: a zero or multiple match means
the production file changed shape, and the fence must fail loudly instead of
validating the wrong text.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import cast


def render_policy_template(path: Path, **values: str) -> dict[str, object]:
    """Render one ``.json.tftpl`` policy template the way ``templatefile`` would.

    Shared by every policy fence so the templates are exercised as JSON rather
    than matched as text. The unresolved-placeholder guard is the point: a fence
    that silently rendered a stale placeholder set would assert on a document
    Terraform never produces.
    """
    rendered = path.read_text(encoding="utf-8")
    for name, value in values.items():
        rendered = rendered.replace(f"${{{name}}}", value)
    unresolved = re.findall(r"\$\{[^}]+\}", rendered)
    assert unresolved == [], f"unrendered placeholders in {path.name}: {unresolved}"
    loaded: object = json.loads(rendered)
    assert isinstance(loaded, dict)
    return cast(dict[str, object], loaded)


def terraform_local_string(locals_text: str, name: str) -> str:
    """Return the single string literal assigned to a Terraform local."""
    matches: list[str] = re.findall(
        rf'^\s*{re.escape(name)}\s*=\s*"([^"]*)"\s*$',
        locals_text,
        flags=re.MULTILINE,
    )
    assert len(matches) == 1, (
        f"expected exactly one string assignment for local {name!r}, "
        f"found {len(matches)}"
    )
    return matches[0]


def terraform_variable_default(variables_text: str, name: str) -> str:
    """Return the single string default of a Terraform variable block."""
    blocks: list[str] = re.findall(
        rf'^variable "{re.escape(name)}" {{\n(.*?)^}}',
        variables_text,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert len(blocks) == 1, f"expected exactly one variable block for {name!r}"
    defaults: list[str] = re.findall(
        r'^\s*default\s*=\s*"([^"]*)"\s*$',
        blocks[0],
        flags=re.MULTILINE,
    )
    assert len(defaults) == 1, f"expected exactly one string default for {name!r}"
    return defaults[0]


def replace_terraform_local(locals_text: str, name: str, new_value: str) -> str:
    """Repoint a Terraform local's string literal, proving the edit landed.

    Used by the mutation tests to drift the *real* production bytes. The
    exactly-one guard keeps the mutation honest: if the production assignment
    changes shape, the mutation silently becoming a no-op must fail the test
    rather than let the fence pass vacuously.
    """
    mutated, count = re.subn(
        rf'^(\s*{re.escape(name)}\s*=\s*")[^"]*("\s*)$',
        lambda match: f"{match.group(1)}{new_value}{match.group(2)}",
        locals_text,
        flags=re.MULTILINE,
    )
    assert count == 1, f"expected exactly one assignment to mutate for {name!r}"
    assert mutated != locals_text, f"mutation of {name!r} did not change the text"
    return mutated


def workflow_jobs(workflow_text: str) -> dict[str, str]:
    """Split a GitHub Actions workflow into ``{job_id: job_block_text}``.

    Indentation-based on purpose: the suite has no YAML dependency, and job
    ids are exactly the two-space-indented keys under the sole top-level
    ``jobs:`` mapping. Column-zero comments stay inside the current job;
    any other column-zero line ends the mapping.
    """
    lines = workflow_text.splitlines()
    starts = [index for index, line in enumerate(lines) if line == "jobs:"]
    assert len(starts) == 1, "expected exactly one top-level jobs mapping"

    jobs: dict[str, str] = {}
    current: str | None = None
    block: list[str] = []
    for line in lines[starts[0] + 1 :]:
        if line and not line[0].isspace() and not line.startswith("#"):
            break
        matched = re.fullmatch(r"  ([A-Za-z0-9_-]+):", line)
        if matched is not None:
            if current is not None:
                jobs[current] = "\n".join(block)
            current = matched.group(1)
            block = []
            continue
        block.append(line)
    if current is not None:
        jobs[current] = "\n".join(block)
    assert jobs, "workflow declares no jobs"
    return jobs


def role_assuming_jobs(workflow_text: str) -> dict[str, str]:
    """The jobs that exchange the OIDC token for AWS credentials.

    These are the only jobs whose GitHub token claims AWS evaluates, so the
    environment and ``id-token`` fences must hold on exactly these blocks --
    a workflow-wide substring cannot see which job carries the binding.
    """
    return {
        job_id: block
        for job_id, block in workflow_jobs(workflow_text).items()
        if "role-to-assume" in block
    }


def job_environment(job_block: str) -> str:
    """Return the job-level ``environment:`` binding of one job block."""
    environments: list[str] = re.findall(
        r"^    environment: (.+?)\s*$",
        job_block,
        flags=re.MULTILINE,
    )
    assert len(environments) == 1, (
        f"expected exactly one job-level environment binding, found {len(environments)}"
    )
    return environments[0]


def job_grants_id_token_write(job_block: str) -> bool:
    """Whether one job block grants itself ``id-token: write``."""
    return (
        re.search(r"^\s+id-token: write\s*$", job_block, flags=re.MULTILINE) is not None
    )
