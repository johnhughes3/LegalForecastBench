from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_docket_tool_container_is_documented_as_no_network_scaffold() -> None:
    compose = (ROOT / "docker" / "docket_tool" / "docker-compose.yaml").read_text(
        encoding="utf-8"
    )
    readme = (ROOT / "docker" / "docket_tool" / "README.md").read_text(encoding="utf-8")
    dockerfile = (ROOT / "docker" / "docket_tool" / "Dockerfile").read_text(
        encoding="utf-8"
    )

    assert 'network_mode: "none"' in compose
    assert "Status: placeholder." in readme
    assert "must not have network access" in readme
    assert "LegalForecast docket tool placeholder" in dockerfile
