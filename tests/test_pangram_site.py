"""The site Pangram check sends only the website's own visible prose."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load() -> ModuleType:
    path = ROOT / "scripts/pangram_site.py"
    spec = importlib.util.spec_from_file_location("pangram_site", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pangram_site = _load()

PAGE = """<!doctype html><html><head><title>Results page · LegalForecastBench</title>
<script>var tracking = "do not send";</script></head>
<body><header><nav><a href="/">Home navigation link text here</a></nav></header>
<main>
<h1>Results</h1>
<p>Models forecast whether judges dismissed each claim in the cohort.</p>
<svg><title>Chart label inside an svg graphic</title><text>axis text</text></svg>
<table><tr><td>Secret table cell with several words in it</td></tr></table>
<div aria-hidden="true">Hidden decoration text that nobody reads aloud</div>
<p>0.1176</p>
<p>17 of 387 predictions were made with high confidence overall.</p>
<pre><code>uv run python secret_code_example.py --flag value</code></pre>
</main>
<footer>Footer text that repeats on every page of the site</footer>
</body></html>"""


def test_page_text_keeps_main_prose_only() -> None:
    title, paragraphs = pangram_site.page_text(PAGE)
    assert title == "Results page"
    assert "Models forecast whether judges dismissed each claim in the cohort." in (
        paragraphs
    )
    joined = " ".join(paragraphs)
    for hidden in (
        "navigation",
        "tracking",
        "Chart label",
        "axis text",
        "Secret table",
        "Hidden decoration",
        "secret_code",
        "Footer",
    ):
        assert hidden not in joined


def _site(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    pages = {
        "index.html": PAGE,
        "methods/index.html": PAGE.replace("17 of 387", "12 of 91").replace(
            "Models forecast", "Methods explain"
        ),
        "paper/index.html": PAGE.replace("Models forecast", "Paper abstract"),
        "lab/tasks/x/index.html": PAGE.replace("Models forecast", "Harvey task"),
    }
    for name, html in pages.items():
        path = dist / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
    return dist


def test_site_units_exclude_routes_fragments_and_repeats(tmp_path: Path) -> None:
    units, stats = pangram_site.site_units(
        _site(tmp_path), list(pangram_site.DEFAULT_EXCLUDE), []
    )
    assert [u.key for u in units] == ["/", "/methods/"]
    assert stats["excluded_pages"] == 2
    assert "0.1176" not in units[0].text and stats["fragments"] >= 2
    # The methods page repeats the confidence sentence with other numbers.
    assert "12 of 91" not in units[1].text
    assert "Methods explain" in units[1].text
    assert stats["repeated_paragraphs"] == 1


def test_only_and_extra_exclusions(tmp_path: Path) -> None:
    dist = _site(tmp_path)
    default = list(pangram_site.DEFAULT_EXCLUDE)
    units, _ = pangram_site.site_units(dist, [*default, "/methods/"], [])
    assert [u.key for u in units] == ["/"]
    units, _ = pangram_site.site_units(dist, default, ["/methods/"])
    assert [u.key for u in units] == ["/methods/"]


def test_parts_split_at_page_boundaries() -> None:
    unit = pangram_site.pangram.Unit
    units = [unit(f"/{n}/", f"Page {n}", "word " * 40) for n in range(5)]
    split = pangram_site.parts(units, 100)
    assert [len(p) for p in split] == [2, 2, 1]
    with pytest.raises(SystemExit, match="over Pangram's ceiling"):
        pangram_site.parts([unit("/big/", "Big", "word " * 101)], 100)


def test_extract_only_needs_no_key_and_writes_the_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(pangram_site.pangram.KEY_VARIABLE, raising=False)
    dist = _site(tmp_path)
    out = tmp_path / "out"
    code = pangram_site.main(["--dist", str(dist), "--out", str(out), "--extract-only"])
    assert code == 0
    printed = capsys.readouterr().out
    assert "not a check of the whole site" in printed
    sent = (out / "site-1.txt").read_text(encoding="utf-8")
    assert "Models forecast" in sent and "Paper abstract" not in sent
    with pytest.raises(SystemExit, match=pangram_site.pangram.KEY_VARIABLE):
        pangram_site.main(["--dist", str(dist), "--out", str(out)])


def test_a_window_counts_for_every_page_it_overlaps() -> None:
    unit = pangram_site.pangram.Unit
    units = [
        unit("/a/", "A", "Alpha prose sentence one.\n\nAlpha prose sentence two."),
        unit("/b/", "B", "Bravo prose sentence one."),
        unit("/c/", "C", "Charlie prose sentence one."),
    ]
    text, spans = pangram_site.pangram.document(units)
    windows = [
        {"text": "Alpha prose sentence two.\nB\nBravo prose sentence one."},
        {"text": "Charlie prose sentence one."},
        {"text": "Text that is not in the document anywhere."},
    ]
    owners = pangram_site.pangram.window_owners(text, spans, windows)
    assert owners == [[0, 1], [2], []]


def test_a_document_under_pangrams_minimum_is_refused_before_sending(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(pangram_site.pangram.KEY_VARIABLE, "placeholder")

    def refuse() -> None:
        raise AssertionError("no request may be sent")

    monkeypatch.setattr(pangram_site.pangram, "_client", refuse)
    dist = _site(tmp_path)
    with pytest.raises(SystemExit, match="Pangram's minimum"):
        pangram_site.main(["--dist", str(dist), "--out", str(tmp_path / "o")])
