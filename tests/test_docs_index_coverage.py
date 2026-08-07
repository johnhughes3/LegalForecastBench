"""Contract tests keeping the documentation index and the docs set in sync.

Every tracked document under ``docs/`` must be linked from ``docs/README.md``,
and every link in that index must resolve. The index is the only navigation
surface for the docs set, so an unlisted document is effectively invisible:
reachable only by someone who already knows its path. Both directions are
enforced mechanically because they drift silently — adding or removing a
document is a normal part of landing a feature, and nothing about that change
surfaces the stale index.

Entries are written by hand on purpose. The index groups documents by reader
intent and gives each a one-line summary, which is judgment these tests cannot
supply; they only insist the entry exists and points somewhere real.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "docs"
INDEX_PATH = DOCS_DIR / "README.md"
INDEX_RELATIVE = "docs/README.md"

MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")


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


def test_every_tracked_doc_is_linked_from_the_index() -> None:
    index = INDEX_PATH.read_text(encoding="utf-8")
    tracked = _tracked_docs()

    # The index lives in docs/, so it links by path relative to that directory.
    unlisted = [path for path in tracked if path.removeprefix("docs/") not in index]

    assert not unlisted, (
        f"{INDEX_RELATIVE} does not link {len(unlisted)} tracked document(s): "
        f"{', '.join(unlisted)}. Add each under the section matching its "
        "audience, with a one-line summary, so the docs set stays reachable."
    )


def test_index_links_all_resolve() -> None:
    index = INDEX_PATH.read_text(encoding="utf-8")

    broken: list[str] = []
    for target in MARKDOWN_LINK.findall(index):
        target = target.strip()
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        path_part = target.split("#", 1)[0]
        if not path_part:
            continue
        if not (DOCS_DIR / path_part).resolve().exists():
            broken.append(target)

    assert not broken, (
        f"{INDEX_RELATIVE} links {len(broken)} path(s) that do not exist: "
        f"{', '.join(broken)}. Remove or repoint entries when a document moves."
    )


def test_tracked_docs_query_finds_the_docs_set() -> None:
    """Guard the git query itself, so the coverage checks cannot pass vacuously."""

    tracked = _tracked_docs()

    assert len(tracked) > 20
    assert "docs/METHODS.md" in tracked
    assert "docs/schemas/cohort-policy-v1.md" in tracked
