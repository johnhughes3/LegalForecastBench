# Commitment contracts

New commitment-bearing code imports named profiles and schema identifiers from `legalforecast.contracts`.

This Cycle 1 surface characterizes existing byte contracts; it does not migrate existing producers, verifiers, cards, fixtures, or persisted digests.

## Named byte profiles

| Name | Bytes | Intended use |
| --- | --- | --- |
| `ARTIFACT_CANONICAL_JSON_V1` | Key-sorted compact UTF-8 JSON with a trailing newline | Whole JSON artifacts |
| `ARTIFACT_JSON_VALUE_V1` | Key-sorted compact UTF-8 JSON without a trailing newline | JSON values embedded in another byte stream |
| `MANIFEST_CANONICAL_JSON_V1` | Key-sorted compact ASCII-escaped JSON without a trailing newline and with the historical `default=str` behavior | Manifest and freeze hashing |
| `RUN_CARD_INDENTED_JSON_V1` | Key-sorted, two-space-indented ASCII-escaped JSON with a trailing newline | Recovery-slice run cards and policy artifacts that already persist this form |

The blessed entry points reject non-finite numbers before serialization.

The artifact profiles delegate to `legalforecast.ingestion.canonical_json`; the manifest profile delegates to `legalforecast._canonical.canonical_json`, so valid Cycle 1 payloads retain their exact bytes.

## Digest representation and domain

Use `ARTIFACT_RAW_SHA256_V1`, `ARTIFACT_PREFIXED_SHA256_V1`, `MANIFEST_RAW_SHA256_V1`, or `RUN_CARD_RAW_SHA256_V1` rather than choosing a serializer and prefix ad hoc.

Each `commit` call requires a `SchemaIdentifier` domain and returns a `Commitment` that retains the profile name, schema domain, and a typed `RawSha256` or `PrefixedSha256` value.

Verification rejects a commitment from a different byte profile, schema domain, or persisted digest representation before comparing the digest.

The schema domain is an API-level binding and does not add new bytes to historical SHA-256 inputs; changing the digest input would be a versioned migration outside Cycle 1.

## Adding a distinct profile

A genuinely distinct persisted representation is allowed only when its byte behavior or digest representation differs and callers need that difference.

Give it a new versioned profile name, characterize Unicode, non-finite numbers, whitespace and newline behavior with literal golden vectors, and document why an existing profile is not correct.

Do not create a universal serializer or silently normalize raw and `sha256:`-prefixed fields.
