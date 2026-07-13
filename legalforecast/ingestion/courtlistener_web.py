"""CourtListener public docket-page parsing helpers.

The scraper layer is responsible for retrieving raw HTML. This module keeps the
benchmark core dependency-light by parsing the stable docket-entry markup from
that raw HTML and producing auditable acquisition diagnostics.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from html.parser import HTMLParser
from urllib.parse import urlparse

from legalforecast.ingestion.restricted_material import restricted_material_markers


class CourtListenerWebParseError(ValueError):
    """Raised when raw CourtListener HTML cannot be parsed as a docket page."""


class CourtListenerEntryRole(StrEnum):
    """Acquisition-oriented docket-entry roles for MTD packet screening."""

    MTD_NOTICE = "mtd_notice"
    MTD_MEMORANDUM = "mtd_memorandum"
    OPPOSITION = "opposition"
    REPLY = "reply"
    EXHIBIT = "exhibit"
    DECISION = "decision"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class CourtListenerWebDocument:
    kind: str
    description: str
    href: str | None
    action_label: str | None
    pacer_only: bool
    restriction_markers: tuple[str, ...] = ()

    @property
    def restricted(self) -> bool:
        return bool(self.restriction_markers)

    @property
    def freely_available(self) -> bool:
        return self.href is not None and not self.pacer_only and not self.restricted

    def to_record(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "description": self.description,
            "href": self.href,
            "action_label": self.action_label,
            "pacer_only": self.pacer_only,
            "freely_available": self.freely_available,
            "restriction_markers": list(self.restriction_markers),
        }


@dataclass(frozen=True, slots=True)
class CourtListenerWebDocketEntry:
    row_id: str
    entry_number: str | None
    filed_at: str | None
    text: str
    documents: tuple[CourtListenerWebDocument, ...] = ()
    restriction_markers: tuple[str, ...] = ()

    @property
    def restricted(self) -> bool:
        return bool(self.restriction_markers) or any(
            document.restricted for document in self.documents
        )

    @property
    def role(self) -> CourtListenerEntryRole:
        return classify_courtlistener_entry_role(self)

    @property
    def relevant_to_mtd_packet(self) -> bool:
        return self.role is not CourtListenerEntryRole.OTHER

    @property
    def pacer_only_document_count(self) -> int:
        return sum(1 for document in self.documents if document.pacer_only)

    @property
    def freely_available_document_count(self) -> int:
        return sum(1 for document in self.documents if document.freely_available)

    def to_record(self) -> dict[str, object]:
        return {
            "row_id": self.row_id,
            "entry_number": self.entry_number,
            "filed_at": self.filed_at,
            "text": self.text,
            "role": self.role.value,
            "restriction_markers": list(self.restriction_markers),
            "documents": [document.to_record() for document in self.documents],
        }


@dataclass(frozen=True, slots=True)
class CourtListenerWebDocketPage:
    docket_id: str | None
    source_url: str | None
    title: str | None
    entries: tuple[CourtListenerWebDocketEntry, ...]
    has_next_page: bool

    @property
    def is_single_page(self) -> bool:
        return not self.has_next_page

    @property
    def exclusion_reason(self) -> str | None:
        return "courtlistener_docket_more_than_one_page" if self.has_next_page else None

    @property
    def mtd_decision_entries(self) -> tuple[CourtListenerWebDocketEntry, ...]:
        return tuple(
            entry
            for entry in self.entries
            if entry.role is CourtListenerEntryRole.DECISION
        )

    def to_record(self) -> dict[str, object]:
        return {
            "docket_id": self.docket_id,
            "source_url": self.source_url,
            "title": self.title,
            "entry_count": len(self.entries),
            "has_next_page": self.has_next_page,
            "exclusion_reason": self.exclusion_reason,
            "entries": [entry.to_record() for entry in self.entries],
        }


@dataclass(frozen=True, slots=True)
class CourtListenerBriefingCompleteness:
    docket_id: str | None
    single_page: bool
    role_counts: Mapping[str, int]
    pacer_only_document_count: int
    freely_available_document_count: int
    missing_core_roles: tuple[str, ...]

    @property
    def estimated_purchase_count(self) -> int:
        return self.pacer_only_document_count

    @property
    def has_mtd_decision(self) -> bool:
        return self.role_counts.get(CourtListenerEntryRole.DECISION.value, 0) > 0

    @property
    def ranking_key(self) -> tuple[int, int, int]:
        return (
            self.estimated_purchase_count,
            len(self.missing_core_roles),
            0 if self.single_page else 1,
        )

    def to_record(self) -> dict[str, object]:
        return {
            "docket_id": self.docket_id,
            "single_page": self.single_page,
            "role_counts": dict(self.role_counts),
            "pacer_only_document_count": self.pacer_only_document_count,
            "freely_available_document_count": self.freely_available_document_count,
            "missing_core_roles": list(self.missing_core_roles),
            "estimated_purchase_count": self.estimated_purchase_count,
            "has_mtd_decision": self.has_mtd_decision,
            "ranking_key": list(self.ranking_key),
        }


def parse_courtlistener_docket_html(
    raw_html: str,
    *,
    source_url: str | None = None,
    docket_id: str | None = None,
) -> CourtListenerWebDocketPage:
    """Parse a public CourtListener docket page from raw HTML."""

    if not raw_html.strip():
        raise CourtListenerWebParseError("raw HTML is empty")
    root = _CourtListenerHTMLTreeParser.parse(raw_html)
    docket_table = _first_descendant(root, id_value="docket-entry-table")
    if docket_table is None:
        raise CourtListenerWebParseError("CourtListener docket-entry table not found")

    parsed_docket_id = docket_id or _docket_id_from_url(source_url)
    entries = tuple(_parse_entry_row(row) for row in _entry_rows(docket_table))
    return CourtListenerWebDocketPage(
        docket_id=parsed_docket_id,
        source_url=source_url,
        title=_page_title(root),
        entries=entries,
        has_next_page=_has_enabled_next_link(root),
    )


def classify_courtlistener_entry_role(
    entry: CourtListenerWebDocketEntry,
) -> CourtListenerEntryRole:
    """Classify a docket row for MTD briefing acquisition."""

    text = _normalized_text(
        " ".join(
            (
                entry.text,
                " ".join(document.description for document in entry.documents),
                " ".join(document.kind for document in entry.documents),
            )
        )
    ).lower()
    references_mtd = _references_mtd(text)
    if references_mtd and starts_with_dispositive_motion(text):
        return CourtListenerEntryRole.MTD_NOTICE
    if references_mtd and _looks_like_decision(text):
        return CourtListenerEntryRole.DECISION
    if "reply" in text and references_mtd:
        return CourtListenerEntryRole.REPLY
    if _looks_like_substantive_mtd_opposition(text):
        return CourtListenerEntryRole.OPPOSITION
    if "memorandum" in text and references_mtd:
        return CourtListenerEntryRole.MTD_MEMORANDUM
    if "exhibit" in text and references_mtd:
        return CourtListenerEntryRole.EXHIBIT
    if references_mtd:
        return CourtListenerEntryRole.MTD_NOTICE
    return CourtListenerEntryRole.OTHER


def is_substantive_mtd_opposition_entry(
    entry: CourtListenerWebDocketEntry,
) -> bool:
    """Return whether a docket row is an actual MTD opposition brief.

    CourtListener docket text often contains ``response`` or ``opposition`` in
    deadline motions and extension orders. Those procedural rows are not model
    inputs and must not create required opposition slots.
    """

    text = _normalized_text(
        " ".join(
            (
                entry.text,
                " ".join(document.description for document in entry.documents),
                " ".join(document.kind for document in entry.documents),
            )
        )
    ).lower()
    return _looks_like_substantive_mtd_opposition(text)


def _looks_like_substantive_mtd_opposition(text: str) -> bool:
    if not _references_mtd(text):
        return False
    if re.search(
        r"\bmotions?\s+(?:for\s+(?:an?\s+)?)?"
        r"(?:extension|enlargement)\s+of\s+time\b"
        r"|\bmotions?\s+to\s+(?:extend|enlarge)\b"
        r"|\b(?:request|application|letter|order)\b[^.;]{0,100}"
        r"(?:\b(?:extension|enlargement)\s+of\s+time\b"
        r"|\b(?:extend|extending|additional)\s+(?:the\s+)?time\b"
        r"|\btime\s+to\s+(?:file|respond|oppose)\b"
        r"|\bdeadline\b|\bdue\s+date\b|\bleave\s+to\s+file\b)",
        text,
    ):
        return False
    return bool(re.search(r"\bopposition\b|\bresponse\b", text))


def estimate_briefing_completeness(
    page: CourtListenerWebDocketPage,
) -> CourtListenerBriefingCompleteness:
    """Estimate completeness and purchase pressure from docket text alone."""

    relevant_entries = tuple(
        entry for entry in page.entries if entry.relevant_to_mtd_packet
    )
    role_counts = Counter(entry.role.value for entry in relevant_entries)
    missing_core_roles = tuple(
        role.value
        for role in (
            CourtListenerEntryRole.MTD_NOTICE,
            CourtListenerEntryRole.OPPOSITION,
            CourtListenerEntryRole.DECISION,
        )
        if role_counts.get(role.value, 0) == 0
    )
    return CourtListenerBriefingCompleteness(
        docket_id=page.docket_id,
        single_page=page.is_single_page,
        role_counts=dict(sorted(role_counts.items())),
        pacer_only_document_count=sum(
            entry.pacer_only_document_count for entry in relevant_entries
        ),
        freely_available_document_count=sum(
            entry.freely_available_document_count for entry in relevant_entries
        ),
        missing_core_roles=missing_core_roles,
    )


def rank_cheapest_complete_candidates(
    pages: Iterable[CourtListenerWebDocketPage],
) -> tuple[CourtListenerBriefingCompleteness, ...]:
    """Rank candidate dockets by missing purchase burden, then completeness."""

    estimates = tuple(estimate_briefing_completeness(page) for page in pages)
    return tuple(sorted(estimates, key=lambda estimate: estimate.ranking_key))


def _empty_node_list() -> list[_Node]:
    return []


def _empty_text_list() -> list[str]:
    return []


@dataclass(slots=True)
class _Node:
    tag: str
    attrs: dict[str, str]
    children: list[_Node] = field(default_factory=_empty_node_list)
    text_parts: list[str] = field(default_factory=_empty_text_list)
    parent: _Node | None = None

    def text(self) -> str:
        parts = [*self.text_parts]
        for child in self.children:
            parts.append(child.text())
        return _normalized_text(" ".join(parts))


class _CourtListenerHTMLTreeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _Node(tag="document", attrs={})
        self._stack = [self.root]

    @classmethod
    def parse(cls, raw_html: str) -> _Node:
        parser = cls()
        parser.feed(raw_html)
        parser.close()
        return parser.root

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = _Node(
            tag=tag.lower(),
            attrs={name.lower(): value or "" for name, value in attrs},
            parent=self._stack[-1],
        )
        self._stack[-1].children.append(node)
        if tag.lower() not in _VOID_TAGS:
            self._stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        normalized_tag = tag.lower()
        for index in range(len(self._stack) - 1, 0, -1):
            if self._stack[index].tag == normalized_tag:
                del self._stack[index:]
                return

    def handle_data(self, data: str) -> None:
        if data.strip():
            self._stack[-1].text_parts.append(data)


def _entry_rows(docket_table: _Node) -> tuple[_Node, ...]:
    return tuple(
        child
        for child in docket_table.children
        if child.tag == "div"
        and _has_class(child, "row")
        and child.attrs.get("id", "").startswith(("entry-", "minute-entry-"))
    )


def _parse_entry_row(row: _Node) -> CourtListenerWebDocketEntry:
    row_id = row.attrs.get("id", "")
    direct_divs = [child for child in row.children if child.tag == "div"]
    entry_number = None
    date_filed = None
    for child in direct_divs:
        if entry_number is None and _has_class(child, "col-xs-1"):
            entry_number = child.text() or None
        if date_filed is None and (
            _has_class(child, "col-xs-3") or _has_class(child, "col-sm-2")
        ):
            span = _first_descendant(child, tag="span")
            date_filed = span.attrs.get("title") if span is not None else child.text()
            date_filed = date_filed or None
    row_text = row.text()
    return CourtListenerWebDocketEntry(
        row_id=row_id,
        entry_number=entry_number,
        filed_at=date_filed,
        text=row_text,
        documents=tuple(
            _parse_recap_document(document) for document in _documents(row)
        ),
        restriction_markers=restricted_material_markers(text_fields=(row_text,)),
    )


def _parse_recap_document(document: _Node) -> CourtListenerWebDocument:
    columns = [child for child in document.children if child.tag == "div"]
    kind = columns[0].text() if columns else ""
    description = columns[1].text() if len(columns) > 1 else ""
    link = _best_document_link(document)
    action_label = None
    href = None
    pacer_only = False
    if link is not None:
        href = link.attrs.get("href") or None
        action_label = link.text() or link.attrs.get("title") or None
        classes = link.attrs.get("class", "")
        action_text = _normalized_text(action_label or "")
        pacer_only = (
            "open_buy_pacer_modal" in classes
            or "buy on pacer" in action_text.lower()
            or (href or "").startswith("https://ecf.")
        )
    return CourtListenerWebDocument(
        kind=kind,
        description=description,
        href=href,
        action_label=action_label,
        pacer_only=pacer_only,
        restriction_markers=restricted_material_markers(
            records=(document.attrs, *((link.attrs,) if link is not None else ())),
            text_fields=(kind, description),
            access_label_fields=(action_label or "",),
        ),
    )


def _documents(row: _Node) -> tuple[_Node, ...]:
    return tuple(
        node
        for node in _descendants(row)
        if node.tag == "div" and _has_class(node, "recap-documents")
    )


def _best_document_link(node: _Node) -> _Node | None:
    links = [
        child
        for child in _descendants(node)
        if child.tag == "a" and child.attrs.get("href")
    ]
    if not links:
        return None
    for link in links:
        if _is_preferred_free_download_link(link):
            return link
    for link in links:
        text = _normalized_text(f"{link.text()} {link.attrs.get('title', '')}")
        classes = link.attrs.get("class", "")
        href = link.attrs.get("href", "")
        if (
            "open_buy_pacer_modal" not in classes
            and "buy on pacer" not in text.lower()
            and not href.startswith("https://ecf.")
        ):
            return link
    return links[0]


def _is_preferred_free_download_link(link: _Node) -> bool:
    text = _normalized_text(f"{link.text()} {link.attrs.get('title', '')}").lower()
    classes = link.attrs.get("class", "")
    href = link.attrs.get("href", "")
    parsed = urlparse(href)
    if (
        "open_buy_pacer_modal" in classes
        or "buy on pacer" in text
        or href.startswith("https://ecf.")
    ):
        return False
    return (
        "download pdf" in text
        or parsed.hostname == "storage.courtlistener.com"
        or parsed.path.lower().endswith(".pdf")
    )


def _has_enabled_next_link(root: _Node) -> bool:
    for link in _descendants(root):
        if link.tag != "a" or link.attrs.get("rel") != "next":
            continue
        classes = link.attrs.get("class", "")
        href = link.attrs.get("href", "")
        return "disabled" not in classes and not href.endswith("#")
    return False


def _page_title(root: _Node) -> str | None:
    title_node = _first_descendant(root, tag="h1") or _first_descendant(
        root, tag="title"
    )
    if title_node is None:
        return None
    title = title_node.text()
    return title or None


def _first_descendant(
    node: _Node,
    *,
    tag: str | None = None,
    id_value: str | None = None,
) -> _Node | None:
    for child in _descendants(node):
        if tag is not None and child.tag != tag:
            continue
        if id_value is not None and child.attrs.get("id") != id_value:
            continue
        return child
    return None


def _descendants(node: _Node) -> Iterable[_Node]:
    for child in node.children:
        yield child
        yield from _descendants(child)


def _has_class(node: _Node, class_name: str) -> bool:
    return class_name in node.attrs.get("class", "").split()


def _docket_id_from_url(source_url: str | None) -> str | None:
    if source_url is None:
        return None
    match = re.search(r"/docket/(\d+)/", urlparse(source_url).path)
    return match.group(1) if match else None


def _references_mtd(text: str) -> bool:
    return bool(
        re.search(r"\bmotions?\s+to\s+dismiss\b", text, re.I)
        or re.search(
            r"\bmotions?\s+by\b[^\n]{0,240}?\bto\s+dismiss\b",
            text,
            re.I,
        )
        or re.search(r"\b12\s*\(\s*b\s*\)\s*\(\s*[126]\s*\)", text, re.I)
        or re.search(r"\b12\s*\(\s*c\s*\)", text, re.I)
        or re.search(r"\brule\s+12\b", text, re.I)
        or re.search(r"\bmtd\b", text, re.I)
        or re.search(r"\bjudgment\s+on\s+the\s+pleadings\b", text, re.I)
    )


def _looks_like_decision(text: str) -> bool:
    return bool(
        re.search(r"\border\b", text, re.I)
        or re.search(r"\bopinion\b", text, re.I)
        or re.search(r"\bdecision\b", text, re.I)
        or re.search(r"\bmemorandum\s+(?:and\s+)?opinion\b", text, re.I)
    )


def starts_with_dispositive_motion(text: str) -> bool:
    """Return whether a docket row begins with an MTD after row metadata."""
    return bool(
        re.match(
            r"^\s*"
            r"(?:(?:\d+\s+)|(?:[a-z]{3,9}\s+\d{1,2},\s+\d{4}"
            r"(?:,\s+\d{1,2}:\d{2}\s*(?:a\.?m\.?|p\.?m\.?))?\s+))*"
            r"(?:(?:amended|corrected|defendant(?:s'?|'s)?|first|joint|partial|"
            r"renewed|second|third)\s+)*"
            r"motions?\s+(?:to\s+dismiss|for\s+judgment\s+on\s+the\s+pleadings)\b",
            text,
            re.I,
        )
    )


def _normalized_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


_VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}
