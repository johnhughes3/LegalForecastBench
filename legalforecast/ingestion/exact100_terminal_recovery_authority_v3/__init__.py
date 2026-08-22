"""v3 fresh-terminal recovery authority for exact-100 successor replay.

The v1/v2 persisted recovery bundle still commits the exact 404 body. That
complete-map bound remains in
``authorize_persisted_terminal_recovery_evidence``. This subpackage versions
the successor-facing proof that a fresh CourtListener observation was a
terminal 404 for the same selection/candidate/document/docket/entry tuple
without requiring those raw 404 bytes to equal the saved sidecar.

Read :mod:`.authority` for the in-process capability and the authorize
adapter that remints exclusion evidence from the persisted bundle.
"""
