"""Static result site renderers for official and community outputs."""

from __future__ import annotations

import hashlib
import html
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from legalforecast._json_io import read_json_object, write_json_object
from legalforecast.multiharness.spec import ArtifactRecord
from legalforecast.publication.publication_guardrails import (
    PublicationGuardrailConfig,
    enforce_publication_guardrails,
)

OFFICIAL_RESULTS_SITE_SCHEMA_VERSION = "legalforecast.official_results_site.v1"
COMMUNITY_RESULTS_SITE_SCHEMA_VERSION = "legalforecast.community_results_site.v1"
_CSS = """
:root {
  color-scheme: light;
  --ink: #17202a;
  --muted: #5d6975;
  --line: #d8dde3;
  --panel: #f6f8fa;
  --accent: #0f766e;
}
body {
  font-family: Inter, ui-sans-serif, system-ui, -apple-system,
    BlinkMacSystemFont, "Segoe UI", sans-serif;
  margin: 0;
  color: var(--ink);
  background: white;
}
main {
  max-width: 1120px;
  margin: 0 auto;
  padding: 32px 24px 48px;
}
h1, h2, h3 {
  letter-spacing: 0;
}
.lede {
  color: var(--muted);
  max-width: 780px;
}
.notice {
  border-left: 4px solid var(--accent);
  background: var(--panel);
  padding: 12px 16px;
  margin: 20px 0;
}
table {
  border-collapse: collapse;
  width: 100%;
  margin: 16px 0 28px;
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
    rows = _official_rows(official_artifacts_dir)
    artifact_links = _artifact_links(official_artifacts_dir)
    body = [
        "<main>",
        "<h1>LegalForecastBench Official Results</h1>",
        (
            "<p class='lede'>Official benchmark results are produced only by the "
            "protected LegalForecastBench evaluation workflow and official "
            "aggregation artifacts.</p>"
        ),
        "<section><h2>Score Table</h2>",
        _official_table(rows),
        "</section>",
        "<section><h2>Methodology and Run Cards</h2>",
        "<p>Use the linked run cards and methodology artifacts to inspect the "
        "frozen cycle, model registry, scoring configuration, and release bundle.</p>",
        _link_list(artifact_links),
        "</section>",
        "</main>",
    ]
    _write_site(output_dir, "\n".join(body), OFFICIAL_RESULTS_SITE_SCHEMA_VERSION)
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
    artifact_links = _artifact_links(community_aggregate_dir)
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
    _write_site(output_dir, "\n".join(body), COMMUNITY_RESULTS_SITE_SCHEMA_VERSION)
    return _site_result(output_dir)


def _write_site(output_dir: Path, body: str, schema_version: str) -> None:
    assets_dir = output_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    (assets_dir / "site.css").write_text(_CSS + "\n", encoding="utf-8")
    (output_dir / "index.html").write_text(
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
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


def _official_rows(root: Path) -> tuple[Mapping[str, Any], ...]:
    for name in ("leaderboard.json", "scores.json", "score-summary.json"):
        path = root / name
        if not path.is_file():
            continue
        record = _read_json(path, name)
        rows = record.get("rows", record.get("scores", ()))
        parsed = _mapping_rows(rows)
        if parsed:
            return parsed
    return ()


def _official_table(rows: Sequence[Mapping[str, Any]]) -> str:
    if not rows:
        return "<p>No official score rows were found in the supplied artifacts.</p>"
    table_rows: list[str] = []
    for row in rows:
        model = _first_str(row, ("model_id", "model_key", "solver_id"))
        score = _first_value(row, ("micro_brier", "score", "mean_score"))
        table_rows.append(
            f"<tr><td>{html.escape(model)}</td><td>{html.escape(str(score))}</td></tr>"
        )
    return (
        "<table><thead><tr><th>Model</th><th>Primary score</th></tr></thead>"
        f"<tbody>{''.join(table_rows)}</tbody></table>"
    )


def _community_cards(rows: Sequence[Mapping[str, Any]]) -> str:
    adapters = sorted({_first_str(row, ("adapter_id",)) for row in rows})
    models = sorted({_first_str(row, ("model_key",)) for row in rows})
    conformance = sorted({_first_str(row, ("conformance_status",)) for row in rows})
    cards = (
        ("Adapters", ", ".join(adapters) or "none"),
        ("Models", ", ".join(models) or "none"),
        ("Conformance", ", ".join(conformance) or "unknown"),
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
            section_rows.append(
                "<tr>"
                f"<td>{html.escape(_first_str(row, ('row_id',)))}</td>"
                f"<td>{html.escape(_first_str(row, ('row_type',)))}</td>"
                f"<td>{html.escape(_first_str(row, ('model_key',)))}</td>"
                f"<td>{html.escape(_first_str(row, ('adapter_id',)))}</td>"
                f"<td>{html.escape(str(row.get('task_count', '')))}</td>"
                f"<td>{html.escape(str(row.get('coverage_percentage', '')))}%</td>"
                "</tr>"
            )
        sections.append(
            "<section>"
            f"<h2>{html.escape(title)} ({html.escape(scoring_mode)})</h2>"
            "<p>Coverage matrices and shard/composite views are grouped within "
            "this compatible family and scoring mode.</p>"
            "<table><thead><tr><th>Row</th><th>Type</th><th>Model</th>"
            "<th>Adapter</th><th>Tasks</th><th>Coverage</th></tr></thead>"
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


def _artifact_links(root: Path) -> tuple[tuple[str, str], ...]:
    links: list[tuple[str, str]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if any(part.startswith(".") for part in relative.split("/")):
            continue
        links.append((relative, relative))
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


def _first_value(record: Mapping[str, Any], keys: Sequence[str]) -> object:
    for key in keys:
        value = record.get(key)
        if value is not None:
            return value
    return ""


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
