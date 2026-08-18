"""Load a CourtListener parser model from its authenticated source bytes.

The preserved sources live beside this module under ``sources/<version>/`` with
a ``.pysource`` suffix rather than ``.py``, for two reasons that both protect
the digest:

* ``ruff format`` and ``ruff check --fix`` rewrite Python files in place.  One
  reformat would change the bytes and break the pin, and the pin cannot simply
  be recomputed -- it is the digest the identity allowlist already authenticates.
* A non-importable suffix makes this digest-verified loader the only way to
  reach those bytes.  A preserved screen imported as an ordinary module would
  bind to the *current* parser and silently compose a model that never existed.

Every model, current or preserved, is handed to callers through one small
facade, so the replay path has a single shape and the preserved branch is not a
special case that only runs on one snapshot.
"""

from __future__ import annotations

import builtins
import hashlib
import sys
import threading
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from types import ModuleType
from typing import Any, Final, Protocol, cast

from legalforecast.ingestion.frozen_parser_model.registry import (
    CURRENT_PARSER_MODEL,
    FrozenParserModelError,
    FrozenParserModelIdentity,
    frozen_parser_model_identity,
)

_SOURCES_ROOT: Final = Path(__file__).resolve().parent / "sources"
_SOURCE_SUFFIX: Final = ".pysource"
_PACKAGE_PREFIX: Final = "legalforecast.ingestion."


class ParsedDocument(Protocol):
    """The document surface the docket-decision replay reads."""

    @property
    def href(self) -> str | None: ...

    @property
    def freely_available(self) -> bool: ...

    def to_record(self) -> dict[str, object]: ...


class ParsedEntry(Protocol):
    """The docket-entry surface the docket-decision replay reads."""

    @property
    def row_id(self) -> str: ...

    @property
    def entry_number(self) -> str | None: ...

    @property
    def filed_at(self) -> str | None: ...

    @property
    def text(self) -> str: ...

    @property
    def role(self) -> str: ...

    @property
    def documents(self) -> tuple[ParsedDocument, ...]: ...

    def to_record(self) -> dict[str, object]: ...


class ParsedPage(Protocol):
    """The docket-page surface the docket-decision replay reads."""

    @property
    def source_url(self) -> str | None: ...

    @property
    def entries(self) -> tuple[ParsedEntry, ...]: ...

    def to_record(self) -> dict[str, object]: ...


@dataclass(frozen=True, slots=True)
class ParserModel:
    """One authenticated CourtListener parser model, current or preserved."""

    version: str
    parse_error: type[Exception]
    accepts_screen_court_id: bool
    _web: Any
    _screen: Any

    def document(
        self,
        *,
        kind: str,
        description: str,
        href: str | None,
        action_label: str | None,
        pacer_only: bool,
        restriction_markers: tuple[str, ...],
    ) -> ParsedDocument:
        """Build one docket document under this model."""

        return cast(
            ParsedDocument,
            self._web.CourtListenerWebDocument(
                kind=kind,
                description=description,
                href=href,
                action_label=action_label,
                pacer_only=pacer_only,
                restriction_markers=restriction_markers,
            ),
        )

    def entry(
        self,
        *,
        row_id: str,
        entry_number: str | None,
        filed_at: str | None,
        text: str,
        documents: tuple[ParsedDocument, ...],
        restriction_markers: tuple[str, ...],
    ) -> ParsedEntry:
        """Build one docket entry under this model."""

        return cast(
            ParsedEntry,
            self._web.CourtListenerWebDocketEntry(
                row_id=row_id,
                entry_number=entry_number,
                filed_at=filed_at,
                text=text,
                documents=documents,
                restriction_markers=restriction_markers,
            ),
        )

    def page(
        self,
        *,
        docket_id: str | None,
        source_url: str | None,
        title: str | None,
        entries: tuple[ParsedEntry, ...],
        has_next_page: bool,
    ) -> ParsedPage:
        """Build one docket page under this model."""

        return cast(
            ParsedPage,
            self._web.CourtListenerWebDocketPage(
                docket_id=docket_id,
                source_url=source_url,
                title=title,
                entries=entries,
                has_next_page=has_next_page,
            ),
        )

    def parse_docket_html(
        self,
        raw_html: str,
        *,
        source_url: str | None,
        docket_id: str | None,
    ) -> ParsedPage:
        """Parse raw CourtListener HTML under this model."""

        return cast(
            ParsedPage,
            self._web.parse_courtlistener_docket_html(
                raw_html,
                source_url=source_url,
                docket_id=docket_id,
            ),
        )

    def screen_record(
        self,
        page: ParsedPage,
        *,
        candidate_text: str,
        court_id: str,
        decision_filed_on_or_after: date,
        decision_filed_on_or_before: date | None,
    ) -> dict[str, object]:
        """Replay the strict MTD decision screen under this model.

        ``court_id`` is dropped for a model frozen before the screen accepted
        it.  That is the honest replay: the preserved implementation derived
        bankruptcy context from docket text alone, and feeding it an argument it
        never had would be a different model again.
        """

        arguments: dict[str, object] = {
            "candidate_text": candidate_text,
            "decision_filed_on_or_after": decision_filed_on_or_after,
            "decision_filed_on_or_before": decision_filed_on_or_before,
        }
        if self.accepts_screen_court_id:
            arguments["court_id"] = court_id
        screen = self._screen.screen_courtlistener_docket_for_mtd_decision(
            page, **arguments
        )
        return cast(dict[str, object], screen.to_record())


_CACHE: Final[dict[str, ParserModel]] = {}
_CACHE_LOCK: Final = threading.Lock()


def load_parser_model(version: str) -> ParserModel:
    """Return one authenticated parser model, or fail closed on an unknown one."""

    with _CACHE_LOCK:
        cached = _CACHE.get(version)
        if cached is not None:
            return cached
        model = (
            _current_parser_model()
            if version == CURRENT_PARSER_MODEL
            else _frozen_parser_model(frozen_parser_model_identity(version))
        )
        _CACHE[version] = model
        return model


def _current_parser_model() -> ParserModel:
    from legalforecast.ingestion import courtlistener_web, mtd_acquisition_screen

    return ParserModel(
        version=CURRENT_PARSER_MODEL,
        parse_error=courtlistener_web.CourtListenerWebParseError,
        accepts_screen_court_id=True,
        _web=courtlistener_web,
        _screen=mtd_acquisition_screen,
    )


def _frozen_parser_model(identity: FrozenParserModelIdentity) -> ParserModel:
    web = _execute_preserved_source(identity, name="courtlistener_web", siblings={})
    screen = _execute_preserved_source(
        identity,
        name="mtd_acquisition_screen",
        siblings={"courtlistener_web": web},
    )
    return ParserModel(
        version=identity.version,
        parse_error=cast(type[Exception], web.__dict__["CourtListenerWebParseError"]),
        accepts_screen_court_id=identity.accepts_screen_court_id,
        _web=web,
        _screen=screen,
    )


def _execute_preserved_source(
    identity: FrozenParserModelIdentity,
    *,
    name: str,
    siblings: Mapping[str, ModuleType],
) -> ModuleType:
    expected = identity.source_sha256.get(name)
    if expected is None:
        raise FrozenParserModelError(
            f"preserved parser source is not pinned: {identity.version}/{name}"
        )
    path = _SOURCES_ROOT / identity.version / f"{name}{_SOURCE_SUFFIX}"
    if path.is_symlink() or not path.is_file():
        raise FrozenParserModelError(
            f"preserved parser source is not a regular file: {path}"
        )
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != expected:
        raise FrozenParserModelError(
            "preserved parser source differs from its authenticated digest: "
            f"{identity.version}/{name}"
        )
    module = ModuleType(f"{__name__}.{identity.version}.{name}")
    module.__dict__["__file__"] = str(path)
    module.__dict__["__builtins__"] = _preserved_builtins(siblings)
    # ``dataclasses`` resolves ``sys.modules[cls.__module__]`` while building a
    # ``slots=True`` class, so the preserved module must be registered before it
    # executes.  The key is this loader's own dotted path plus the version, which
    # cannot collide with the production module it preserves.
    sys.modules[module.__name__] = module
    try:
        exec(compile(payload, str(path), "exec"), module.__dict__)
    except BaseException:
        del sys.modules[module.__name__]
        raise
    return module


def _preserved_builtins(siblings: Mapping[str, ModuleType]) -> dict[str, Any]:
    """Resolve intra-package imports to preserved siblings, not the live tree.

    The preserved sources are byte-identical to their originals, so the
    preserved screen still reads ``from legalforecast.ingestion.courtlistener_web
    import ...``.  Executing that against ``sys.modules`` would compose a
    preserved screen with the *current* parser -- a model that never produced
    any evidence.  Overriding ``__import__`` in the executed module's own
    builtins rebinds exactly those names for exactly that execution, so
    ``sys.modules`` is never mutated and concurrent importers of the production
    modules are unaffected.
    """

    aliases = {f"{_PACKAGE_PREFIX}{name}": module for name, module in siblings.items()}
    real_import = builtins.__import__

    def preserved_import(
        name: str,
        globals: Mapping[str, object] | None = None,
        locals: Mapping[str, object] | None = None,
        fromlist: Sequence[str] = (),
        level: int = 0,
    ) -> ModuleType:
        if level == 0 and fromlist and name in aliases:
            return aliases[name]
        return real_import(name, globals, locals, fromlist, level)

    return {**vars(builtins), "__import__": preserved_import}
