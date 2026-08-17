# Tier-0 executable freeze (T0R successor packet)

Status: **NOT AN APPROVAL TARGET**. This packet supersedes the structural freeze for command shape, binary identity, per-call spend enforcement, and receipt-authority coordinates. It does not authorize spend. The designated approver must not sign until `dm0g.4.5.16-reviewer` records acceptance against these bytes and the remaining fail-closed inputs below are provisioned.

No provider call is authorized by this document.

## What this packet binds

| Field | Value |
| --- | --- |
| Packet | `docs/community-acceptance/tier0-paired-smoke-executable-freeze.md` |
| Supersedes | `docs/community-acceptance/tier0-paired-smoke-structural-freeze.md` (`f87b916fb4eefd621e29093877dbd45b402486e20b51af876110907f880cd681`) for operator command, binary identity, and spend-control shape only |
| Reviewer | `dm0g.4.5.16-reviewer` |
| Regeneration | Recreate this file from the rows below, then `sha256sum` it. The companion `.sha256` and the readiness-pack executable-freeze table must move together |

## Exact operator commands

Caller-supplied roots are mandatory. Private and archive roots must be fresh absent paths. There are no run-varying flags.

```bash
export LFB_TIER0_SOURCE_ROOT="<existing LAB pin directory>"
export LFB_TIER0_PRIVATE_ROOT="<fresh absent private root>"
export LFB_TIER0_ARCHIVE_ROOT="<fresh absent archive root>"

uv run legalforecast multiharness tier0 validate \
  --spec TIER0_EXECUTABLE_SPEC.json \
  --spec-sha256 sha256:SPEC_SHA256 \
  --approval TIER0_DETACHED_APPROVAL.json

uv run legalforecast multiharness tier0 run \
  --spec TIER0_EXECUTABLE_SPEC.json \
  --spec-sha256 sha256:SPEC_SHA256 \
  --approval TIER0_DETACHED_APPROVAL.json
```

The CLI loads the evaluator issuer through `load_approved_issuer_authority(secret_loader=infisical_evaluator_issuer_secret_loader)`. The loader is not invoked while the public key remains `pending_human_provisioning`.

## Model identities

These are the frozen requested identities from the structural packet. Resolved identities must match or publication uses system-bundle language.

| Surface | Requested identity |
| --- | --- |
| Clean-native solver | `anthropic:claude-sonnet-4-6` |
| Native-thin solver | `anthropic:claude-sonnet-4-6` |
| Judge | `anthropic:claude-sonnet-4-6` at temperature `0.0` |
| Criterion calls per complete arm | 23 |

## True binary identities

Provider-free interface re-characterization on 2026-08-17. Probe commands requested no model call.

| Binary | Version | SHA-256 | Fixture |
| --- | --- | --- | --- |
| `claude` | `2.1.233 (Claude Code)` | `55d281096f57d411ebbdd94dbf5e9ff3accb7c05713e37348c2c11d4b83bf9d9` | `tests/fixtures/claude_code_cli_characterization/claude-code-cli-interface-2.1.233.json` |
| `codex` | `codex-cli 0.147.0` | `cb0a15567e9a60a5820d54b0f6ae86d504dc3805c1eab21a47f70e3eb7b73a40` | `tests/fixtures/codex_cli_characterization/codex-cli-interface-0.147.0.json` |

`codex exec --help` on 0.147.0 advertises `--approve-for-me`. The adapter still refuses that flag. The earlier 4.4.27 digest `d6877199…` is not this pin.

Privileged whole-process containment (`dm0g.4.2.2`) remains a designated-operator blocker and still names an older Claude identity.

## Per-call spend ceilings

The evaluator must request budget through `HarveyLabJudgeRequestBoundary.before_judge_call` immediately before every paid judge request, including retries. An experiment-wide request or dollar cap must halt the next judge call. The provider-free proof is `tests/test_tier0_mid_evaluator_spend_halt.py`: a fake provider with `experiment.max_requests=11` makes 11 paid calls and is denied on criterion 12 of 23 with terminal evidence.

Final dollar figures are not in this packet. A dated production pricing snapshot and the exact per-criterion / experiment maxima must still be committed and bound into the executable spec before spend.

## Receipt authority

| Field | Value |
| --- | --- |
| Public config | `examples/adapters/harvey-lab/evaluator-issuer-authority.json` |
| Status | `pending_human_provisioning` |
| Algorithm | Ed25519 |
| Issuer ID | `legalforecast.harvey-lab-evaluator-issuer.v1` |
| Key ID | `harvey-lab-evaluator-v1` |
| Infisical environment | `dev` |
| Infisical path | `/agents/sandbox/legalforecastbench/harness-runtime/evaluator-issuer` |
| Secret name | `HARVEY_LAB_EVALUATOR_ED25519_PRIVATE_KEY` |
| Secret format | Base64 of exactly 32 raw Ed25519 seed bytes (RFC 8032) |
| Public format | Base64 of exactly 32 raw Ed25519 public-key bytes in `public_key_base64` |

John provisions the secret. Agents never write or read it. The wrapper has no `secrets set` command. Verification fails closed until the public key is committed and `status` is `configured`. The approval authority is a distinct human-only key.

## Unminted paid artifacts

These hashes do not exist yet and must not be invented:

- executable spec SHA-256
- dated pricing-snapshot SHA-256
- spend-policy SHA-256
- evaluator wrapper SHA-256 (`harvey-lab-eval` is not installed on the characterized PATH)
- detached spend-approval signature

Paid `tier0 run` also requires a reviewed `install_tier0_production_evaluator_factory(...)` whose provider adapter returns allocable usage and cost. Fixture identity `fixture/stub@local` is refused on that path.

## Characterization live probe (not a Tier-0 run)

One cheapest-model probe was authorized for the 2.1.233 pin:

| Field | Value |
| --- | --- |
| Date | 2026-08-17 |
| Model | `claude-haiku-4-5` |
| Credential path | `/agents/sandbox/legalforecastbench/labeling` via `infisical-agent-sandbox` |
| Host provider env | unset |
| Cost | `0.00787875` USD |
| Tokens | 10 input / 41 output |

The sibling published-api-key path 404'd and was not used. No Codex live task was retried after the 4.4.27 timeout.

## John's remaining exact actions

1. Provision the evaluator Ed25519 seed at the Infisical coordinates above and approve committing the public key.
2. Provision the distinct Tier-0 approval public key.
3. Choose or authorize the production evaluator/provider adapter and install `harvey-lab-eval`.
4. Run the `dm0g.4.2.2` privileged no-spend capture after an independent reviewer approves the exact probe bytes and the 2.1.233 digest. Do not run the placeholder block that still says `INSERT_FRESH_INDEPENDENTLY_APPROVED_SHA256`.
5. After those inputs exist, mint the dated pricing snapshot, dollar-valued policy, executable spec, and detached approval; then request fresh `dm0g.4.5.16` acceptance against the resulting hashes.
