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
    ManifestForecastBundleBuild,
    ManifestForecastBundleError,
    issue_bundle,
    verify_bundle,
)
from legalforecast.evals.corpus_manifest.execution_decisions import (
    ExecutionDecisionsBuild,
    ExecutionDecisionsError,
    issue_beads_observation,
    issue_execution_decisions,
    verify_execution_decisions,
)
from legalforecast.evals.corpus_manifest.execution_scope import (
    ExecutionScopeError,
    compose_model_scopes,
    generate_execution_policy_v3,
    generate_execution_policy_v4,
    issue_execution_plan,
    issue_execution_plan_v4,
    issue_model_execution_scope,
    select_model_scope,
    verify_execution_policy_v3,
    verify_execution_policy_v4,
    verify_execution_scope,
    verify_execution_scope_runtime,
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
    "ExecutionDecisionsBuild",
    "ExecutionDecisionsError",
    "ExecutionScopeError",
    "ManifestCase",
    "ManifestDocument",
    "ManifestForecastBundleBuild",
    "ManifestForecastBundleError",
    "compose_model_scopes",
    "generate_execution_policy_v3",
    "generate_execution_policy_v4",
    "issue_beads_observation",
    "issue_bundle",
    "issue_execution_decisions",
    "issue_execution_plan",
    "issue_execution_plan_v4",
    "issue_model_execution_scope",
    "load_signed_manifest",
    "manifest_digest",
    "select_model_scope",
    "verify_bundle",
    "verify_execution_decisions",
    "verify_execution_policy_v3",
    "verify_execution_policy_v4",
    "verify_execution_scope",
    "verify_execution_scope_runtime",
]
