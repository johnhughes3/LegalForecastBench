# Accepted-attempt map schema

`legalforecast.accepted_attempt_map.v1` is a committed post-execution selection amendment for an official evaluation freeze. It does not modify the freeze bundle: changing the bundle after shard execution would invalidate every receipt already bound to that bundle. Instead, the map names its parent freeze and records the operator's accepted immutable receipt for each shard that produced more than one receipt.

Singleton shards are always selected automatically and must not appear in the map. If any shard has multiple receipts, fan-in refuses until the map contains exactly one selection for every ambiguous shard and no selection for any singleton or undeclared shard.

The top-level JSON object contains exactly:

- `schema_version`: fixed to `legalforecast.accepted_attempt_map.v1`.
- `cycle_id`: the non-empty frozen cycle identifier.
- `parent_freeze_bundle_sha256`: the current freeze bundle's canonical commitment hash.
- `execution_policy_sha256`: the canonical hash of the frozen execution-policy content.
- `shard_schedule_sha256`: SHA-256 over canonical JSON shaped as `{"shards":[...]}`, where each entry contains `model_key` and `ablation` and the entries are sorted by that pair.
- `selections`: the sorted accepted receipt identities described below.
- `accepted_attempt_map_sha256`: SHA-256 over the canonical top-level object after removing this field.

Each `selections` entry contains exactly:

- `model_key` and `ablation`: the ambiguous frozen shard identity.
- `workflow_run_id` and `workflow_run_attempt`: the accepted immutable attempt.
- `receipt_key`: the receipt's derived `shard-receipts/<cycle>/.../<run>/<attempt>.json` key.
- `receipt_sha256`: the receipt's canonical self-commitment.

Publishing accepts this artifact only from a clean, tracked `manifests/` path in the trusted release checkout. Verification-only rehearsals may use an explicit local fixture path because they have no canonical publication code path. The final fan-in report records the complete accepted-attempt map, its hash and source path, the full discovered receipt-inventory hash, the current canonical URI-to-VersionId inventory hash, every accepted receipt identity, the verified union commitment, and the frozen cadence inputs. Publication recomputes both inventory hashes immediately before writing and refuses if either changed.
