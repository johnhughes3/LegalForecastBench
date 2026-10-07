"""Score the website's own prose, other than the paper, with Pangram's AI-text detector.

Reads the built site (``site/dist``, from ``pnpm --dir site build``), keeps the text a
visitor sees in each page's main content, and sends it to Pangram. It reuses the
paper check's client and report (``docs/papers/pangram_check.py``).

Left out by default, because they are not the site's own prose:

* ``/paper/``: the paper, which has its own check;
* ``/lab/deliverables/``, ``/lab/tasks/``, ``/lab/review/``: AI model outputs, Harvey
  LAB task material and AI audit findings, and the human-review pages generated from
  the worksheet;
* navigation, headers, footers, tables, code, scripts, and hidden elements.

A paragraph that repeats on several pages (model-page boilerplate, for example) is
scored once, on the first page where it appears. If the text is longer than one
Pangram request allows, it is split at page boundaries into several documents.

Scoring is opt-in and spends Pangram credits; the script prints its estimate and
refuses to send above ``--max-usd``. Run from the repository root::

    pnpm --dir site build
    uv run --frozen python scripts/pangram_site.py --extract-only
    uv run --frozen --with pangram-sdk==1.0.0 python scripts/pangram_site.py --verbose
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIST = ROOT / "site" / "dist"
# Fragments shorter than this are labels, dates, and statistic tiles, not prose.
MIN_PARAGRAPH_WORDS = 5
NUMBER = re.compile(r"\d+(?:[.,:]\d+)*")
DEFAULT_EXCLUDE = (
    "/paper/",
    "/lab/deliverables/",
    "/lab/tasks/",
    "/lab/review/",
    "/og/",
    "/404",
)
# Elements whose text is not prose a visitor reads as the site's writing.
SKIP = {
    "script",
    "style",
    "noscript",
    "template",
    "svg",
    "nav",
    "header",
    "footer",
    "table",
    "pre",
    "code",
    "button",
    "select",
    "form",
}
BLOCKS = {
    "p",
    "li",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "dd",
    "dt",
    "blockquote",
    "figcaption",
    "summary",
    "div",
    "section",
    "article",
}
VOID = {"br", "img", "hr", "input", "meta", "link", "source", "wbr", "col", "area"}


def _paper_check() -> Any:
    path = ROOT / "docs" / "papers" / "pangram_check.py"
    spec = importlib.util.spec_from_file_location("pangram_check", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pangram = _paper_check()


class _Visible(HTMLParser):
    """Collect paragraphs of visible text, noting which sit inside <main>."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.paragraphs: list[tuple[bool, str]] = []
        self.has_main = False
        self._main_depth = 0
        self._in_title = False
        self._muted = 0  # open elements since entering a skipped or hidden one
        self._buffer: list[str] = []
        self._buffer_in_main = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "title" and not self._muted and not self.title:
            self._in_title = True
        if tag == "br":
            self._flush()
        if tag in VOID:
            return
        if self._muted:
            self._muted += 1
            return
        values = dict(attrs)
        if tag in SKIP or "hidden" in values or values.get("aria-hidden") == "true":
            self._flush()
            self._muted = 1
            return
        if tag == "main":
            self.has_main = True
            self._main_depth += 1
        if tag in BLOCKS:
            self._flush()

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if tag in VOID:
            return
        if self._muted:
            self._muted -= 1
            return
        if tag in BLOCKS or tag == "main":
            self._flush()
        if tag == "main" and self._main_depth:
            self._main_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        elif not self._muted:
            if not self._buffer:
                self._buffer_in_main = self._main_depth > 0
            self._buffer.append(data)

    def _flush(self) -> None:
        text = " ".join("".join(self._buffer).split())
        if text:
            self.paragraphs.append((self._buffer_in_main, text))
        self._buffer = []

    def close(self) -> None:
        super().close()
        self._flush()


def page_text(html: str) -> tuple[str, list[str]]:
    """The page title and its visible paragraphs, from <main> when there is one."""
    parser = _Visible()
    parser.feed(html)
    parser.close()
    paragraphs = [
        text for in_main, text in parser.paragraphs if in_main or not parser.has_main
    ]
    title = " ".join(parser.title.split()).split(" · ")[0]
    return title, paragraphs


def route_of(path: Path, dist: Path) -> str:
    relative = path.relative_to(dist).as_posix()
    route = "/" + re.sub(r"(^|/)index\.html$", r"\1", relative)
    return route.removesuffix(".html") if route.endswith(".html") else route


def site_units(
    dist: Path, exclude: list[str], include: list[str]
) -> tuple[list[Any], dict[str, int]]:
    """One unit per page, each repeated paragraph kept only on its first page."""
    if not dist.is_dir():
        raise SystemExit(
            f"{dist} not found; build the site first (pnpm --dir site build)"
        )
    seen: set[str] = set()
    units: list[Any] = []
    stats = {"pages": 0, "excluded_pages": 0, "repeated_paragraphs": 0, "fragments": 0}
    for path in sorted(dist.rglob("*.html")):
        route = route_of(path, dist)
        stats["pages"] += 1
        wanted = any(route.startswith(p) for p in include) if include else True
        if not wanted or any(route.startswith(p) for p in exclude):
            stats["excluded_pages"] += 1
            continue
        title, paragraphs = page_text(
            path.read_text(encoding="utf-8", errors="replace")
        )
        kept: list[str] = []
        for paragraph in paragraphs:
            if len(paragraph.split()) < MIN_PARAGRAPH_WORDS:
                stats["fragments"] += 1
                continue
            # Template sentences that differ only in their numbers count as repeats.
            key = NUMBER.sub("#", paragraph)
            if key in seen:
                stats["repeated_paragraphs"] += 1
                continue
            seen.add(key)
            kept.append(paragraph)
        if kept:
            units.append(pangram.Unit(route, title or route, "\n\n".join(kept)))
    return units, stats


def parts(units: list[Any], max_words: int) -> list[list[Any]]:
    """Split units into documents under Pangram's word ceiling, at page boundaries."""
    out: list[list[Any]] = [[]]
    size = 0
    for unit in units:
        if unit.words > max_words:
            raise SystemExit(
                f"{unit.key} alone has {unit.words:,} words, over Pangram's ceiling"
            )
        if out[-1] and size + unit.words > max_words:
            out.append([])
            size = 0
        out[-1].append(unit)
        size += unit.words
    return out


def _arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(__doc__ or "").split("\n\n")[0],
        epilog=(
            "Route prefixes left out by default: "
            + ", ".join(DEFAULT_EXCLUDE)
            + f". Scoring reads the key from {pangram.KEY_VARIABLE} and spends credits."
        ),
    )
    parser.add_argument("--dist", type=Path, default=DEFAULT_DIST)
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="directory for the text sent and Pangram's responses "
        "(default: DIST/.pangram)",
    )
    parser.add_argument(
        "--extract-only",
        action="store_true",
        help="write the text and print the page table without calling Pangram",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="PREFIX",
        help="also leave out routes starting with PREFIX (repeatable)",
    )
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        metavar="PREFIX",
        help="score only routes starting with PREFIX (repeatable)",
    )
    parser.add_argument(
        "--max-usd",
        type=float,
        default=15.0,
        help="refuse to send if the estimated total exceeds this (default: 15)",
    )
    parser.add_argument(
        "--fail-above",
        type=float,
        metavar="FRACTION",
        help="exit 1 if any document's AI plus AI-assisted fraction exceeds this",
    )
    parser.add_argument("--model", default="default")
    parser.add_argument(
        "--verbose", action="store_true", help="print an excerpt of each flagged window"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _arguments(argv)
    out = args.out or args.dist / ".pangram"
    units, stats = site_units(args.dist, [*DEFAULT_EXCLUDE, *args.exclude], args.only)
    if not units:
        raise SystemExit("no pages left to score")
    documents = parts(units, pangram.MAX_WORDS)
    words = sum(u.words for u in units)
    dollars = sum(pangram.estimate(pangram.document(d)[0])[1] for d in documents)
    print(
        f"{len(units)} pages, {words:,} words of site prose in {len(documents)} "
        f"document(s): about ${dollars:.2f} at Pangram's published rate.\n"
        f"Left out: {stats['excluded_pages']} of {stats['pages']} pages by route, "
        f"{stats['repeated_paragraphs']} paragraphs repeated from earlier pages "
        "(ignoring numbers), and "
        f"{stats['fragments']} fragments under {MIN_PARAGRAPH_WORDS} words.\n"
    )
    sending = not args.extract_only
    if sending and not os.environ.get(pangram.KEY_VARIABLE):
        raise SystemExit(
            f"{pangram.KEY_VARIABLE} is not set; set it or pass --extract-only"
        )
    if sending and dollars > args.max_usd:
        raise SystemExit(
            f"estimated ${dollars:.2f} exceeds --max-usd {args.max_usd:.2f}; "
            "raise it to send"
        )
    short = [
        n
        for n, d in enumerate(documents, 1)
        if sum(u.words for u in d) < pangram.MIN_WORDS
    ]
    if short and sending:
        raise SystemExit(
            f"document(s) {', '.join(map(str, short))} have fewer than "
            f"{pangram.MIN_WORDS} words, Pangram's minimum; widen --only"
        )
    client = pangram._client() if sending else None
    status = 0
    for number, document in enumerate(documents, 1):
        if len(documents) > 1:
            print(f"=== Document {number} of {len(documents)} ===\n")
        status |= pangram.score(
            document,
            out=out,
            client=client,
            model=args.model,
            fail_above=args.fail_above,
            verbose=args.verbose,
            text_name=f"site-{number}.txt",
            response_name=f"site-{number}.json",
        )
        print()
    print(
        "This is not a check of the whole site. Left out: routes starting with "
        + ", ".join([*DEFAULT_EXCLUDE, *args.exclude])
        + "; navigation, headers, footers, tables, code, and hidden elements; "
        f"fragments under {MIN_PARAGRAPH_WORDS} words; and paragraphs already scored "
        "on an earlier page, ignoring numbers."
    )
    return status


if __name__ == "__main__":
    raise SystemExit(main())
