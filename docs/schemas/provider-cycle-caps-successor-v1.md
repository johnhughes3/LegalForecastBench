# Provider cycle caps successor receipt v1

`legalforecast.provider_cycle_caps_successor_receipt.v1` proves that authority-enabled Cycle 1 provider caps were deterministically derived from three exact immutable inputs: legacy `legalforecast.provider_cycle_caps.v1` bytes, the raw reviewed `legalforecast.official_labeling_authority_smoke.v1` receipt, and one canonical public alias/policy artifact.

Use the supported provider-free command; do not hand-edit provider caps or copy an identity digest out of the smoke receipt:

```bash
uv run legalforecast acquisition materialize-provider-cycle-caps-successor \
  --legacy-provider-cycle-caps /absolute/path/provider-cycle-caps-legacy.json \
  --expected-legacy-caps-sha256 <lowercase-sha256-of-exact-legacy-bytes> \
  --authority-smoke-receipt /absolute/path/authority-smoke.json \
  --expected-authority-smoke-sha256 <lowercase-sha256-of-exact-raw-smoke-bytes> \
  --expected-smoke-release-sha <full-lowercase-reviewed-main-commit> \
  --provider-caps-successor-policy /absolute/path/provider-caps-successor-policy.json \
  --expected-provider-policy-sha256 <lowercase-sha256-of-exact-policy-bytes> \
  --output-root /absolute/path/provider-caps-successor
```

The command makes no AWS, provider, PACER, evaluation, freeze, or dispatch call.
It requires absolute canonical paths and reads every input as one singly linked regular file without following final or parent symlinks.
All expected digests and the release SHA must already be canonical lowercase hexadecimal; normalization is forbidden.

## Authority-smoke input

The raw smoke receipt has this exact closed shape:

```json
{
  "allowed": {
    "condition_check_item": true,
    "describe_table": true,
    "describe_time_to_live": true,
    "get_item": true,
    "put_item": true,
    "transact_write_items": true,
    "update_item": true
  },
  "authority_resource_identity_sha256": "<lowercase-sha256>",
  "denied": {
    "delete_item": true,
    "list_tables": true,
    "outside_table_describe": true,
    "outside_table_get_item": true,
    "outside_table_put_item": true,
    "outside_table_transact_write_items": true,
    "outside_table_update_item": true,
    "scan": true
  },
  "provider_call_made": false,
  "release_sha": "<full-lowercase-reviewed-main-commit>",
  "schema_version": "legalforecast.official_labeling_authority_smoke.v1"
}
```

Every key is required, no extra key is accepted, every allowed and denied result must be the boolean `true`, and `provider_call_made` must be the boolean `false`.
The command hashes the raw downloaded bytes before parsing them and requires their release SHA to equal the separately supplied reviewed release.
An identity-only JSON object or a re-created receipt is not authority evidence.

## Canonical public policy input

`legalforecast.provider_cycle_caps_successor_policy.v1` has this exact shape and must use the repository canonical JSON encoding: UTF-8, sorted keys, two-space indentation, one trailing newline, no NaN, and unescaped Unicode.

```json
{
  "cycle_id": "cycle-1",
  "provider_accounts": [
    {
      "account": "cycle1-anthropic",
      "provider": "anthropic"
    },
    {
      "account": "cycle1-google",
      "provider": "google"
    },
    {
      "account": "cycle1-openai",
      "provider": "openai"
    }
  ],
  "schema_version": "legalforecast.provider_cycle_caps_successor_policy.v1",
  "spend_authority": {
    "backend": "dynamodb",
    "failure_threshold": 3,
    "failure_window_seconds": 300,
    "ledger_scope_fields": [
      "cycle_id",
      "provider",
      "account"
    ],
    "max_billable_attempts": 2
  }
}
```

Providers must be unique and sorted and must exactly equal the legacy caps provider set.
Accounts are public aliases validated by the runtime caps loader; AWS account IDs, ARNs, access-key forms, tokens, secrets, credentials, and other private identifiers are forbidden.
The policy cycle must equal the immutable source cycle.

## Outputs and resume

The output root owns exactly these paths:

- `provider-cycle-caps.json`
- `provider-cycle-caps-successor-receipt.json`
- `run-cards/materialize-provider-cycle-caps-successor.json`

The successor remains `legalforecast.provider_cycle_caps.v1` because that runtime schema already defines the closed authority-enabled form.
The public receipt commits the exact source, smoke, policy, and successor byte counts and SHA-256 digests, the reviewed release, public aliases, caps, and breaker policy.
The completed `legalforecast.acquisition_run_card.v1` additionally commits the canonical input and output paths and records provider, paid, and AWS activity as neither requested nor executed.

Each file is published exclusively and atomically inside its destination directory, with the completed run card last.
A retry may reuse or repair only the deterministic exact bytes.
Changed bytes, hard links, symlinks, special files, unsafe parent traversal, noncanonical paths, or any unexpected output residue fail closed without replacement.

Downstream paid stages continue to bind the exact successor caps bytes.
Neither the public receipt nor its run card substitutes for the caps artifact or for the live remote authority at execution time.
