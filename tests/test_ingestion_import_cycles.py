from __future__ import annotations

import subprocess
import sys


def test_console_import_order_does_not_create_ingestion_selection_cycle() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import legalforecast.selection.motion_linkage; "
                "import legalforecast.ingestion.case_dev_firecrawl; "
                "import legalforecast.cli"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr
