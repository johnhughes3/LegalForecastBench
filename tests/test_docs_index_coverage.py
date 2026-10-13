"""Contract tests keeping the documentation index and the docs set in sync.

Every tracked document under ``docs/`` must be linked from ``docs/README.md``,
and every link in that index must resolve. A self-indexed subtree (the planned
multi-harness track and the generated Harvey LAB audit) is linked once from the
top index, and each document inside it must be linked from that subtree's own
``README.md`` instead. The index is the only navigation
surface for the docs set, so an unlisted document is effectively invisible:
reachable only by someone who already knows its path. Both directions are
enforced mechanically because they drift silently — adding or removing a
document is a normal part of landing a feature, and nothing about that change
surfaces the stale index.

Coverage is decided by exact path match against the index's actual Markdown
link targets, never by substring search over the file text. Substring matching
silently passes a document whose path is contained in another entry —
``audit.md`` inside ``reproduce-or-audit.md``, ``change-control.md`` inside
``current-change-control.md`` — and also counts a path merely mentioned in
prose or a code block as linked. Those false passes would defeat the drift
protection these tests exist to provide.

Entries are written by hand on purpose. The index groups documents by reader
intent and gives each a one-line summary, which is judgment these tests cannot
supply; they only insist the entry exists and points somewhere real.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "docs"
INDEX_PATH = DOCS_DIR / "README.md"
INDEX_RELATIVE = "docs/README.md"

SELF_INDEXED_DIRS = (
    "docs/multiharness",
    "docs/harvey-lab-audit/litigation-dispute-resolution",
)

MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "#")


def _tracked_docs() -> list[str]:
    """Return repo-relative paths of tracked markdown under docs/, sans index."""

    completed = subprocess.run(
        ["git", "ls-files", "-z", "--", "docs"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return sorted(
        path
        for path in completed.stdout.split("\0")
        if path.endswith(".md") and path != INDEX_RELATIVE
    )


def _link_targets(index: str) -> list[str]:
    """Return the raw in-repository link targets the index declares."""

    targets: list[str] = []
    for raw in MARKDOWN_LINK.findall(index):
        target = raw.strip()
        if target.startswith(EXTERNAL_PREFIXES):
            continue
        path_part = target.split("#", 1)[0]
        if path_part:
            targets.append(path_part)
    return targets


def _owning_index(path: str) -> str:
    """Return the index that must link ``path``: its subtree README or the top one."""

    for directory in SELF_INDEXED_DIRS:
        if path.startswith(f"{directory}/"):
            return f"{directory}/README.md"
    return INDEX_RELATIVE


def _linked_from(index_relative: str) -> set[str]:
    """Return the repo-relative paths an index file links to."""

    index_path = ROOT / index_relative
    text = index_path.read_text(encoding="utf-8")
    return {
        resolved
        for target in _link_targets(text)
        if (resolved := _resolve_in_repo(target, base=index_path.parent)) is not None
    }


def _resolve_in_repo(path_part: str, base: Path = DOCS_DIR) -> str | None:
    """Resolve an index link to a repo-relative path, or None if out of bounds.

    Absolute targets and ``..`` traversal that escapes the repository are
    rejected rather than resolved. ``Path("/docs") / "/tmp/x"`` yields
    ``/tmp/x`` — pathlib discards the left operand for an absolute right
    operand — so an unchecked join would validate paths outside the tree
    whenever they happen to exist on the machine running the tests.
    """

    if PurePosixPath(path_part).is_absolute():
        return None
    resolved = (base / path_part).resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return None


def test_every_tracked_doc_is_linked_from_the_index() -> None:
    linked: dict[str, set[str]] = {}
    unlisted: list[str] = []
    for path in _tracked_docs():
        index = _owning_index(path)
        if path == index:
            index = INDEX_RELATIVE
        if index not in linked:
            linked[index] = _linked_from(index)
        if path not in linked[index]:
            unlisted.append(f"{path} (expected in {index})")

    assert not unlisted, (
        f"{len(unlisted)} tracked document(s) are not linked from their index: "
        f"{', '.join(unlisted)}. Add each under the section matching its "
        "audience, with a one-line summary, so the docs set stays reachable."
    )


def test_index_links_all_resolve() -> None:
    broken: list[str] = []
    for index_relative in (
        INDEX_RELATIVE,
        *(f"{d}/README.md" for d in SELF_INDEXED_DIRS),
    ):
        index_path = ROOT / index_relative
        for target in _link_targets(index_path.read_text(encoding="utf-8")):
            resolved = _resolve_in_repo(target, base=index_path.parent)
            if resolved is None:
                broken.append(f"{index_relative}: {target} (outside the repository)")
            elif not (ROOT / resolved).exists():
                broken.append(f"{index_relative}: {target}")

    assert not broken, (
        f"{len(broken)} index link(s) do not resolve inside the repository: "
        f"{', '.join(broken)}. Remove or repoint entries when a document moves."
    )


def test_coverage_requires_an_exact_link_not_a_substring() -> None:
    """A document whose path is a substring of another entry is still unlisted."""

    index = "- [Current change control](current-change-control.md): adopted rules.\n"
    linked = {
        resolved
        for target in _link_targets(index)
        if (resolved := _resolve_in_repo(target)) is not None
    }

    assert "docs/current-change-control.md" in linked
    assert "docs/change-control.md" not in linked


def test_out_of_tree_link_targets_are_rejected() -> None:
    """Absolute and escaping targets never resolve, however the machine looks."""

    assert _resolve_in_repo("/etc/hostname") is None
    assert _resolve_in_repo("../../../../etc/hostname") is None
    assert _resolve_in_repo("METHODS.md") == "docs/METHODS.md"
    assert _resolve_in_repo("../README.md") == "README.md"


def test_prose_mentions_do_not_count_as_links() -> None:
    """A path named in prose or a code block is not a Markdown link."""

    index = "See `current-change-control.md` and docs/METHODS.md for detail.\n"

    assert _link_targets(index) == []


def test_tracked_docs_query_finds_the_docs_set() -> None:
    """Guard the git query itself, so the coverage checks cannot pass vacuously."""

    tracked = _tracked_docs()

    assert tracked
    assert "docs/METHODS.md" in tracked
    assert "docs/release-inputs.md" in tracked


def test_reader_documentation_lives_under_docs() -> None:
    """Keep narrative docs together; agent instructions and fixtures are tooling."""
    tracked = subprocess.run(
        ["git", "ls-files", "-z", "--", "*.md"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split("\0")
    tooling_files = {
        "AGENTS.md",
        ".agents/AGENTS.md",
        "scripts/AGENTS.md",
        "tests/fixtures/multiharness-artifact-characterization/reports/community-comparison.md",
        "tests/fixtures/vercel_ai_gateway/PROVENANCE.md",
    }
    misplaced = [
        path
        for path in tracked
        if path
        and not path.startswith("docs/")
        and PurePosixPath(path).name != "README.md"
        and path not in tooling_files
        and not (path.startswith(".agents/skills/") and path.endswith("/SKILL.md"))
    ]
    assert not misplaced, f"Move reader documentation into docs/: {misplaced}"
