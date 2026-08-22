"""Owner-signed flat corpus manifest and the manifest-mode forecast entry.

This package is the owner-directed parallel entry path for the Cycle 1 forecast
run.  It exists because the lineage issuance chain is slow to gate, and the
owner elected to authorize a run against one small signed manifest while the
custody chain reconciles afterwards.

It is **additive**.  Nothing here modifies the lineage issuance path, the Stage
A replay issuer, or any existing preflight gate; the integrity substance the
lineage path enforces is enforced here too, by reusing the same packet builder
and the same registry eligibility functions rather than restating them.
"""

from __future__ import annotations

from legalforecast.evals.corpus_manifest.deferred_bundle import (
    DeferredReceiptError,
    LabelAttachmentBuild,
    ManifestForecastBundleBuild,
    ManifestForecastBundleError,
    attach_labels,
    issue_bundle,
    verify_bundle,
    write_deferred_receipts,
)
from legalforecast.evals.corpus_manifest.execution_decisions import (
    ExecutionDecisionsBuild,
    ExecutionDecisionsError,
    issue_beads_observation,
    issue_execution_decisions,
    verify_execution_decisions,
)
from legalforecast.evals.corpus_manifest.schema import (
    AUDIT_ONLY_DOCUMENT_ROLES,
    MODEL_VISIBLE_DOCUMENT_ROLES,
    CorpusManifest,
    CorpusManifestError,
    ManifestCase,
    ManifestDocument,
    load_signed_manifest,
    manifest_digest,
)

__all__ = [
    "AUDIT_ONLY_DOCUMENT_ROLES",
    "MODEL_VISIBLE_DOCUMENT_ROLES",
    "CorpusManifest",
    "CorpusManifestError",
    "DeferredReceiptError",
    "ExecutionDecisionsBuild",
    "ExecutionDecisionsError",
    "LabelAttachmentBuild",
    "ManifestCase",
    "ManifestDocument",
    "ManifestForecastBundleBuild",
    "ManifestForecastBundleError",
    "attach_labels",
    "issue_beads_observation",
    "issue_bundle",
    "issue_execution_decisions",
    "load_signed_manifest",
    "manifest_digest",
    "verify_bundle",
    "verify_execution_decisions",
    "write_deferred_receipts",
]
