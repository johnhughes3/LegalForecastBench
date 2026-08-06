from __future__ import annotations

import subprocess
import sys

from legalforecast.ingestion import COURTLISTENER_RECAP_FETCH_PROVIDER
from legalforecast.ingestion.courtlistener_provider_identity import (
    COURTLISTENER_RECAP_FETCH_PROVIDER as LIGHTWEIGHT_PROVIDER,
)
from legalforecast.ingestion.courtlistener_recap_fetch import (
    COURTLISTENER_RECAP_FETCH_PROVIDER as FETCH_PROVIDER,
)


def test_courtlistener_provider_identity_has_one_public_value() -> None:
    assert LIGHTWEIGHT_PROVIDER == "courtlistener.recap-fetch+pacer"
    assert FETCH_PROVIDER == LIGHTWEIGHT_PROVIDER
    assert COURTLISTENER_RECAP_FETCH_PROVIDER == LIGHTWEIGHT_PROVIDER


def test_disclosure_consumers_import_with_shared_provider_identity() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from legalforecast.ingestion.courtlistener_provider_identity "
                "import COURTLISTENER_RECAP_FETCH_PROVIDER as identity; "
                "from legalforecast.ingestion.provenance_clearance "
                "import COURTLISTENER_RECAP_FETCH_PROVIDER as clearance; "
                "from legalforecast.ingestion.disclosure_model_review "
                "import COURTLISTENER_RECAP_FETCH_PROVIDER as review; "
                "assert identity == clearance == review"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr
