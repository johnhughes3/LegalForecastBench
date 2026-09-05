"""Public owner-signed corpus manifest schema compatibility surface.

The legacy corpus construction runtime was retired, but the public manifest
record remains an input contract for the private corpus builder and its export
readers.  Keep this package limited to the pure schema and digest helpers so
those readers do not regain a dependency on the retired runtime.
"""

from __future__ import annotations

from legalforecast.evals.corpus_manifest.schema import (
    AUDIT_ONLY_DOCUMENT_ROLES,
    MANIFEST_DIGEST_FIELD,
    MODEL_VISIBLE_DOCUMENT_ROLES,
    REQUIRED_CLAIM_BEARING_ROLES,
    REQUIRED_TARGET_MOTION_ROLES,
    BoundSource,
    CorpusManifest,
    CorpusManifestError,
    ManifestCase,
    ManifestDocument,
    load_signed_manifest,
    load_signed_manifest_bytes,
    manifest_digest,
)

__all__ = [
    "AUDIT_ONLY_DOCUMENT_ROLES",
    "MANIFEST_DIGEST_FIELD",
    "MODEL_VISIBLE_DOCUMENT_ROLES",
    "REQUIRED_CLAIM_BEARING_ROLES",
    "REQUIRED_TARGET_MOTION_ROLES",
    "BoundSource",
    "CorpusManifest",
    "CorpusManifestError",
    "ManifestCase",
    "ManifestDocument",
    "load_signed_manifest",
    "load_signed_manifest_bytes",
    "manifest_digest",
]
