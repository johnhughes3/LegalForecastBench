"""Contract tests keeping the documentation index and the docs set in sync.

Every tracked document under ``docs/`` must be linked from ``docs/README.md``,
and every link in that index must resolve. The index is the only navigation
surface for the docs set, so an unlisted document is effectively invisible:
reachable only by someone who already knows its path. Both directions are
enforced mechanically because they drift silently — adding or removing a
document is a normal part of landing a feature, and nothing about that change
surfaces the stale index.

Coverage is decided by exact path match against the index's actual Markdown
link targets, never by substring search over the file text. Substring matching
silently passes a document whose path is contained in another entry —
``audit.md`` inside ``reproduce-or-audit.md``, ``change-control.md`` inside
``cycle-1-change-control.md`` — and also counts a path merely mentioned in
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


def _resolve_in_repo(path_part: str) -> str | None:
    """Resolve an index link to a repo-relative path, or None if out of bounds.

    Absolute targets and ``..`` traversal that escapes the repository are
    rejected rather than resolved. ``Path("/docs") / "/tmp/x"`` yields
    ``/tmp/x`` — pathlib discards the left operand for an absolute right
    operand — so an unchecked join would validate paths outside the tree
    whenever they happen to exist on the machine running the tests.
    """

    if PurePosixPath(path_part).is_absolute():
        return None
    resolved = (DOCS_DIR / path_part).resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return None


def test_every_tracked_doc_is_linked_from_the_index() -> None:
    index = INDEX_PATH.read_text(encoding="utf-8")
    linked = {
        resolved
        for target in _link_targets(index)
        if (resolved := _resolve_in_repo(target)) is not None
    }

    unlisted = [path for path in _tracked_docs() if path not in linked]

    assert not unlisted, (
        f"{INDEX_RELATIVE} does not link {len(unlisted)} tracked document(s): "
        f"{', '.join(unlisted)}. Add each under the section matching its "
        "audience, with a one-line summary, so the docs set stays reachable."
    )


def test_index_links_all_resolve() -> None:
    index = INDEX_PATH.read_text(encoding="utf-8")

    broken: list[str] = []
    for target in _link_targets(index):
        resolved = _resolve_in_repo(target)
        if resolved is None:
            broken.append(f"{target} (outside the repository)")
        elif not (ROOT / resolved).exists():
            broken.append(target)

    assert not broken, (
        f"{INDEX_RELATIVE} links {len(broken)} path(s) that do not resolve "
        f"inside the repository: {', '.join(broken)}. Remove or repoint "
        "entries when a document moves."
    )


def test_coverage_requires_an_exact_link_not_a_substring() -> None:
    """A document whose path is a substring of another entry is still unlisted."""

    index = "- [Cycle 1 change control](cycle-1-change-control.md): adopted rules.\n"
    linked = {
        resolved
        for target in _link_targets(index)
        if (resolved := _resolve_in_repo(target)) is not None
    }

    assert "docs/cycle-1-change-control.md" in linked
    assert "docs/change-control.md" not in linked


def test_out_of_tree_link_targets_are_rejected() -> None:
    """Absolute and escaping targets never resolve, however the machine looks."""

    assert _resolve_in_repo("/etc/hostname") is None
    assert _resolve_in_repo("../../../../etc/hostname") is None
    assert _resolve_in_repo("METHODS.md") == "docs/METHODS.md"
    assert _resolve_in_repo("../README.md") == "README.md"


def test_prose_mentions_do_not_count_as_links() -> None:
    """A path named in prose or a code block is not a Markdown link."""

    index = "See `cycle-1-change-control.md` and docs/METHODS.md for detail.\n"

    assert _link_targets(index) == []


def test_tracked_docs_query_finds_the_docs_set() -> None:
    """Guard the git query itself, so the coverage checks cannot pass vacuously."""

    tracked = _tracked_docs()

    assert len(tracked) > 20
    assert "docs/METHODS.md" in tracked
    assert "docs/schemas/cohort-policy-v1.md" in tracked
