# Provider cycle caps v1

`legalforecast.provider_cycle_caps.v1` is the immutable pre-labeling commitment for provider/account spend. It records each provider cap and the shared remote authority that every paid labeling and official-evaluation call must consult.

The artifact has this shape:

```json
{
  "schema_version": "legalforecast.provider_cycle_caps.v1",
  "cycle_id": "cycle-1",
  "spend_authority": {
    "backend": "dynamodb",
    "resource_identity_sha256": "<sha256-of-actual-table-arn>",
    "ledger_scope_fields": ["cycle_id", "provider", "account"],
    "max_billable_attempts": 2,
    "failure_threshold": 3,
    "failure_window_seconds": 300
  },
  "providers": [
    {
      "provider": "openai",
      "account": "primary",
      "cycle_reservation_cap_usd": "1000.00",
      "external_spend_limit_usd": "1000.00",
      "external_limit_scope": "operator-verified account limit",
      "external_limit_source": "operator evidence",
      "verified_at": "2026-07-16T00:00:00Z"
    }
  ]
}
```

The schema is closed: the artifact, `spend_authority` object, and provider entries accept exactly the keys shown above, except that historical artifacts may omit `spend_authority` and provider `account`. Unknown keys are rejected so that misspelled or accidentally disclosed fields cannot be ignored.

The public `account` value is a lowercase kebab-case alias of 1–32 characters, never an account ID, ARN, or credential. Validation rejects whitespace, any 12-digit account-ID sequence, ARN syntax, credential-like prefixes or words, and all characters outside lowercase ASCII letters, digits, and hyphens. Validation errors do not echo the rejected value. `resource_identity_sha256` is the lowercase SHA-256 digest of the actual DynamoDB table ARN; the runtime obtains the ARN through `DescribeTable` and refuses a mismatch without publishing the ARN itself. The table must use string partition key `authority_key` and string sort key `record_key`.

The exact artifact bytes are hashed before the first paid labeling call. That pre-labeling artifact fixes the authority, caps, aliases, attempt budget, and breaker policy used by labeling. Its digest is the remote ledger's `reservation_ledger_sha256`; the later at-freeze execution policy must reproduce those commitments and the artifact digest exactly, and cannot originate or raise them. Consequently, labeling and evaluation address the same `(authority, cycle_id, provider, account, reservation_ledger_sha256)` ledger even though their attempt records have different stage names.

Legacy artifacts without `spend_authority` and provider account aliases remain readable for historical inspection, but paid labeling refuses to use them. Every paid acquisition command also requires `--provider-authority-table`; the optional `--provider-authority-region` defaults to `us-east-1`.

Reservations use exact integer micro-USD values. A cap with precision finer than one micro-USD is invalid for remote execution. Ambiguous attempts retain their full reservation until immutable provider-usage evidence reconciles them.
