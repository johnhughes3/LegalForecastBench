"""Repository architecture and CLI-sprawl ratchets.

This module is the stable composition facade over
``legalforecast.testing.architecture_rules``.  It keeps the historical public
names used by pytest and ``python -m legalforecast.testing.architecture``.
"""

from __future__ import annotations

from legalforecast.testing.architecture_rules.baseline import (
    check_baseline,
    load_baseline,
    write_baseline,
)
from legalforecast.testing.architecture_rules.cli_compatibility import (
    CLI_PATH,
    UPWARD_IMPORT_ALLOWLIST,
    CliMetrics,
    CompatibilityInventory,
    imports_cli,
    is_console_adapter_source,
    scan_test_compatibility,
)
from legalforecast.testing.architecture_rules.inventory import (
    BASELINE_PATH,
    RepositoryInventory,
    scan_repository,
)
from legalforecast.testing.architecture_rules.reporting import main

ArchitectureSnapshot = RepositoryInventory
_imports_cli = imports_cli
_is_console_adapter_source = is_console_adapter_source
_scan_test_compatibility = scan_test_compatibility

__all__ = [
    "BASELINE_PATH",
    "CLI_PATH",
    "UPWARD_IMPORT_ALLOWLIST",
    "ArchitectureSnapshot",
    "CliMetrics",
    "CompatibilityInventory",
    "RepositoryInventory",
    "_imports_cli",
    "_is_console_adapter_source",
    "_scan_test_compatibility",
    "check_baseline",
    "load_baseline",
    "main",
    "scan_repository",
    "write_baseline",
]


if __name__ == "__main__":
    raise SystemExit(main())
