"""Package entrypoint for the repository architecture ratchet.

``python -m legalforecast.testing.architecture_rules`` runs the same CLI as
``legalforecast.testing.architecture_rules.reporting``; regenerate the reviewed
baseline with ``--write-baseline``.
"""

from __future__ import annotations

from legalforecast.testing.architecture_rules.reporting import main

if __name__ == "__main__":
    raise SystemExit(main())
