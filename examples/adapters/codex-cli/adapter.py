#!/usr/bin/env python3
"""Offline Codex CLI community adapter."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

# The documented `uv run legalforecast ...` invocation supplies project dependencies.
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_PROJECT_ROOT))

main = importlib.import_module("legalforecast.multiharness.codex_cli_cli").main


if __name__ == "__main__":
    raise SystemExit(main())
