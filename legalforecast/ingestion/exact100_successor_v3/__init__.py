"""The v3 exact-100 successor lane: N paired swaps from the current cohort head.

Grouped as a subpackage rather than four more modules in ``ingestion`` for two
reasons.  The lane's four files only make sense together -- an evidence
capability, its issuance adapter, the projector, and the console entry point
that binds them -- and ``legalforecast/ingestion`` is already at its reviewed
file ceiling, which this keeps intact.

Read :mod:`.projector` first for what the successor guarantees, then
:mod:`.replacement_evidence` for what an owner-adjudicated promotion must
prove.  :mod:`.cli` is the operator surface and explains why the lane ships as
a console script instead of a ``legalforecast`` subcommand.
"""

from __future__ import annotations
