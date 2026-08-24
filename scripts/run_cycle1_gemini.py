"""Resumable supplementary Cycle 1 Gemini 3.7 Flash runner.

This thin entry point reuses the authenticated local runner and selects only
the supplementary Gemini configuration.  Run it through
``legalforecast.labeling.provider_environment --provider google`` for paid
execution so the child receives only ``GEMINI_API_KEY``.
"""

from __future__ import annotations

from collections.abc import Sequence

if __package__:
    from scripts.run_cycle1_luna import GEMINI_CONFIG
    from scripts.run_cycle1_luna import main as _run_main
else:  # pragma: no cover - direct script execution import path
    from run_cycle1_luna import GEMINI_CONFIG
    from run_cycle1_luna import main as _run_main


def main(argv: Sequence[str] | None = None) -> int:
    """Run the generic local runner with the Gemini supplementary policy."""

    return _run_main(argv, config=GEMINI_CONFIG)


if __name__ == "__main__":
    raise SystemExit(main())
