"""Static result site renderers for official and community outputs."""

from __future__ import annotations

import hashlib
import html
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from legalforecast._json_io import read_json_object, write_json_object
from legalforecast.multiharness.spec import ArtifactRecord
from legalforecast.publication.official_report_site import build_official_report_page
from legalforecast.publication.official_report_validation import load_official_bundle
from legalforecast.publication.publication_guardrails import (
    PublicationGuardrailConfig,
    enforce_publication_guardrails,
)

OFFICIAL_RESULTS_SITE_SCHEMA_VERSION = "legalforecast.official_results_site.v1"
COMMUNITY_RESULTS_SITE_SCHEMA_VERSION = "legalforecast.community_results_site.v1"
CONFORMANCE_SELF_REPORTED_LABEL = "Conformance (self-reported)"
_CSS = """
:root {
  color-scheme: light;
  --ink: #17202a;
  --muted: #5d6975;
  --line: #d8dde3;
  --panel: #f6f8fa;
  --accent: #0f766e;
  --accent-soft: #e7f5f2;
  --baseline: #735c0f;
  --baseline-soft: #fff8c5;
}
* {
  box-sizing: border-box;
}
body {
  font-family: "Avenir Next", Avenir, "Segoe UI", ui-sans-serif, sans-serif;
  margin: 0;
  color: var(--ink);
  background: white;
  line-height: 1.55;
}
main {
  max-width: 1120px;
  margin: 0 auto;
  padding: 32px 24px 48px;
}
h1, h2, h3 {
  font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua",
    Palatino, Georgia, serif;
  letter-spacing: 0;
  line-height: 1.2;
}
a {
  color: #075f57;
}
a:focus-visible,
summary:focus-visible {
  outline: 3px solid #2dd4bf;
  outline-offset: 3px;
}
.skip-link {
  background: white;
  left: 12px;
  padding: 8px 12px;
  position: absolute;
  top: -80px;
  z-index: 10;
}
.skip-link:focus {
  top: 12px;
}
.eyebrow {
  color: var(--accent);
  font-size: 0.82rem;
  font-weight: 750;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.lede {
  color: var(--muted);
  max-width: 780px;
  font-size: 1.08rem;
}
.notice {
  border-left: 4px solid var(--accent);
  background: var(--panel);
  padding: 12px 16px;
  margin: 20px 0;
}
.official-notice {
  background: var(--accent-soft);
}
.baseline-notice {
  border-left-color: var(--baseline);
  background: var(--baseline-soft);
}
.report-nav ul {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 18px;
  list-style: none;
  padding: 0;
}
table {
  border-collapse: collapse;
  width: 100%;
}
th, td {
  border: 1px solid var(--line);
  padding: 8px 10px;
  text-align: left;
  vertical-align: top;
}
th {
  background: var(--panel);
}
.table-scroll {
  margin: 16px 0 28px;
  overflow-x: auto;
}
.table-scroll:focus-visible {
  outline: 3px solid #2dd4bf;
  outline-offset: 3px;
}
.table-hint {
  color: var(--muted);
  display: none;
  font-size: 0.9rem;
}
caption {
  font-weight: 700;
  padding: 0 0 8px;
  text-align: left;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}
.card {
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 12px;
  background: white;
}
.metric {
  font-size: 1.45rem;
  font-variant-numeric: tabular-nums;
  font-weight: 750;
  margin: 4px 0;
}
.tier-badge {
  background: var(--accent-soft);
  border: 1px solid var(--accent);
  border-radius: 999px;
  color: #075f57;
  display: inline-block;
  font-size: 0.78rem;
  font-weight: 750;
  padding: 2px 8px;
}
.muted {
  color: var(--muted);
}
.audit-panel {
  border: 1px solid var(--line);
  border-radius: 6px;
  margin: 24px 0;
  padding: 12px 16px;
}
@media (max-width: 720px) {
  main {
    padding: 24px 16px 40px;
  }
  .report-nav ul {
    display: block;
  }
  .report-nav li {
    margin: 8px 0;
  }
  th, td {
    min-width: 120px;
  }
  .table-hint {
    display: block;
  }
}
""".strip()


@dataclass(frozen=True, slots=True)
class StaticSiteResult:
    """Generated static site files."""

    output_dir: Path
    index_path: Path
    artifact_index_path: Path


def render_official_results_site(
    *,
    official_artifacts_dir: Path,
    output_dir: Path,
) -> StaticSiteResult:
    """Render an official-only static site from official aggregate artifacts."""

    output_dir.mkdir(parents=True, exist_ok=True)
    bundle = load_official_bundle(official_artifacts_dir)
    artifact_links = _artifact_links(
        official_artifacts_dir,
        href_base=output_dir,
        allowed_paths=bundle.artifact_paths,
    )
    page = build_official_report_page(
        official_artifacts_dir=official_artifacts_dir,
        artifact_links=artifact_links,
        bundle=bundle,
    )
    _write_site(
        output_dir,
        page.body,
        OFFICIAL_RESULTS_SITE_SCHEMA_VERSION,
        title=f"{page.title} | LegalForecastBench",
    )
    return _site_result(output_dir)


def render_community_results_site(
    *,
    community_aggregate_dir: Path,
    output_dir: Path,
) -> StaticSiteResult:
    """Render the non-official community comparison static site."""

    output_dir.mkdir(parents=True, exist_ok=True)
    summary = _read_json(
        community_aggregate_dir / "registry" / "site-summary.json",
        "community site summary",
    )
    rows = _rows(summary)
    artifact_links = _artifact_links(community_aggregate_dir, href_base=output_dir)
    body = [
        "<main>",
        "<h1>LegalForecastBench Community Harness Comparisons</h1>",
        (
            "<p class='notice'>These are non-official community results. They are "
            "reviewed for public-safety and compatibility metadata, but they are "
            "not official LegalForecastBench results.</p>"
        ),
        _community_cards(rows),
        _community_sections(rows),
        "<section><h2>Artifacts</h2>",
        _link_list(artifact_links),
        "</section>",
        "</main>",
    ]
    _write_site(
        output_dir,
        "\n".join(body),
        COMMUNITY_RESULTS_SITE_SCHEMA_VERSION,
        title="Community Harness Comparisons | LegalForecastBench",
    )
    return _site_result(output_dir)


def _write_site(
    output_dir: Path,
    body: str,
    schema_version: str,
    *,
    title: str,
) -> None:
    assets_dir = output_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    (assets_dir / "site.css").write_text(_CSS + "\n", encoding="utf-8")
    (output_dir / "index.html").write_text(
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>{html.escape(title)}</title>"
        "<link rel='stylesheet' href='assets/site.css'>"
        "</head><body>"
        f"{body}"
        "</body></html>",
        encoding="utf-8",
    )
    write_json_object(
        output_dir / "site-manifest.json",
        {
            "schema_version": schema_version,
            "index": "index.html",
            "stylesheet": "assets/site.css",
        },
    )
    _write_artifact_index(output_dir)
    enforce_publication_guardrails(
        PublicationGuardrailConfig(public_paths=(output_dir,))
    )


def _site_result(output_dir: Path) -> StaticSiteResult:
    return StaticSiteResult(
        output_dir=output_dir,
        index_path=output_dir / "index.html",
        artifact_index_path=output_dir / "artifact-index.json",
    )


def _community_cards(rows: Sequence[Mapping[str, Any]]) -> str:
    adapters = sorted({_first_str(row, ("adapter_id",)) for row in rows})
    models = sorted({_first_str(row, ("model_key",)) for row in rows})
    conformance = sorted(
        {
            _self_reported_conformance_status(_first_str(row, ("conformance_status",)))
            for row in rows
        }
    )
    cards = (
        ("Adapters", ", ".join(adapters) or "none"),
        ("Models", ", ".join(models) or "none"),
        (CONFORMANCE_SELF_REPORTED_LABEL, ", ".join(conformance) or "unknown"),
    )
    return (
        "<section><h2>Adapter and Conformance Cards</h2><div class='grid'>"
        + "".join(
            "<div class='card'>"
            f"<h3>{html.escape(title)}</h3>"
            f"<p>{html.escape(value)}</p>"
            "</div>"
            for title, value in cards
        )
        + "</div></section>"
    )


def _self_reported_conformance_status(status: str) -> str:
    normalized = status.strip() or "unknown"
    if "self-reported" in normalized.lower():
        return normalized
    return f"{normalized} (self-reported)"


def _community_sections(rows: Sequence[Mapping[str, Any]]) -> str:
    sections: list[str] = []
    for family, scoring_mode in sorted(
        {
            (_first_str(row, ("family",)), _first_str(row, ("scoring_mode",)))
            for row in rows
        }
    ):
        title = (
            "Harvey LAB"
            if family == "harvey_lab"
            else "LegalForecastBench/LFB"
            if family == "legalforecast_mtd"
            else family
        )
        section_rows: list[str] = []
        for row in rows:
            if (
                _first_str(row, ("family",)) != family
                or _first_str(row, ("scoring_mode",)) != scoring_mode
            ):
                continue
            conformance_status = _self_reported_conformance_status(
                _first_str(row, ("conformance_status",))
            )
            section_rows.append(
                "<tr>"
                f"<td>{html.escape(_first_str(row, ('row_id',)))}</td>"
                f"<td>{html.escape(_first_str(row, ('row_type',)))}</td>"
                f"<td>{html.escape(_first_str(row, ('model_key',)))}</td>"
                f"<td>{html.escape(_first_str(row, ('adapter_id',)))}</td>"
                f"<td>{html.escape(str(row.get('task_count', '')))}</td>"
                f"<td>{html.escape(str(row.get('coverage_percentage', '')))}%</td>"
                f"<td>{html.escape(conformance_status)}</td>"
                "</tr>"
            )
        sections.append(
            "<section>"
            f"<h2>{html.escape(title)} ({html.escape(scoring_mode)})</h2>"
            "<p>Coverage matrices and shard/composite views are grouped within "
            "this compatible family and scoring mode.</p>"
            "<table><thead><tr><th>Row</th><th>Type</th><th>Model</th>"
            "<th>Adapter</th><th>Tasks</th><th>Coverage</th>"
            f"<th>{html.escape(CONFORMANCE_SELF_REPORTED_LABEL)}</th></tr></thead>"
            f"<tbody>{''.join(section_rows)}</tbody></table>"
            "</section>"
        )
    return "\n".join(sections)


def _rows(summary: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    return _mapping_rows(summary.get("rows", ()))


def _mapping_rows(value: object) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        return ()
    records: list[Mapping[str, Any]] = []
    for item in cast(Sequence[object], value):
        if isinstance(item, Mapping):
            records.append(cast(Mapping[str, Any], item))
    return tuple(records)


def _artifact_links(
    root: Path,
    *,
    href_base: Path,
    allowed_paths: Sequence[str] | None = None,
) -> tuple[tuple[str, str], ...]:
    links: list[tuple[str, str]] = []
    allowed = set(allowed_paths) if allowed_paths is not None else None
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if allowed is not None and relative not in allowed:
            continue
        if any(part.startswith(".") for part in relative.split("/")):
            continue
        href = os.path.relpath(path, start=href_base).replace(os.sep, "/")
        links.append((href, relative))
    return tuple(links)


def _link_list(links: Sequence[tuple[str, str]]) -> str:
    if not links:
        return "<p>No downloadable public artifacts were found.</p>"
    return (
        "<ul>"
        + "".join(
            f"<li><a href='{html.escape(href)}'>{html.escape(label)}</a></li>"
            for href, label in links
        )
        + "</ul>"
    )


def _write_artifact_index(output_dir: Path) -> None:
    artifacts = [
        _artifact_for(output_dir, path)
        for path in sorted(output_dir.rglob("*"))
        if path.is_file() and path.name != "artifact-index.json"
    ]
    write_json_object(
        output_dir / "artifact-index.json",
        {"artifacts": [artifact.to_record() for artifact in artifacts]},
    )


def _artifact_for(root: Path, path: Path) -> ArtifactRecord:
    return ArtifactRecord(
        artifact_id=path.relative_to(root).as_posix().replace("/", ":"),
        path=path.relative_to(root).as_posix(),
        sha256=_file_sha256(path),
        media_type=_media_type(path),
        public=True,
        size_bytes=path.stat().st_size,
    )


def _read_json(path: Path, label: str) -> Mapping[str, Any]:
    return read_json_object(
        path,
        error_factory=ValueError,
        missing_message=lambda item: f"{label} does not exist: {item}",
        non_object_message=lambda item: f"{label} must be a JSON object: {item}",
    )


def _first_str(record: Mapping[str, Any], keys: Sequence[str]) -> str:
    for key in keys:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return "unknown"


def _file_sha256(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _media_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".html":
        return "text/html"
    if suffix == ".css":
        return "text/css"
    if suffix == ".json":
        return "application/json"
    return "application/octet-stream"
