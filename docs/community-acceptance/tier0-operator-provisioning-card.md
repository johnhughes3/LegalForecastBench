# Tier-0 operator provisioning card

Everything the designated operator must do, batched into one sitting. Agents never perform any step on this card: two of them create key material and one requires privileged approval.

Nothing here authorizes provider spend. The detached spend approval is deliberately **not** on this card — it is created only after `dm0g.4.5.16-reviewer` records acceptance.

Companion packet: `docs/community-acceptance/tier0-paired-smoke-executable-freeze.md`.

## Before you start: read the blocker

Paid Tier-0 cannot run today even with every credential below provisioned, because the native-thin arm has no enforceable dollar ceiling (freeze packet, "What is still missing", item 1). Provisioning is still worth doing in one sitting — it clears three of the five blockers and none of it expires — but do not schedule the paired run off the back of it.

## 1. Evaluator receipt-signing keypair

The evaluator boundary signs each evaluation receipt; verification refuses unsigned or unknown-issuer receipts and fails closed until this is provisioned.

Generate offline, on the operator machine, in a shell whose history is not persisted:

```bash
umask 077
seed_b64="$(uv run python -c '
import base64
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
key = Ed25519PrivateKey.generate()
print(base64.b64encode(key.private_bytes_raw()).decode("ascii"))
')"
public_b64="$(uv run python -c '
import base64, sys
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
seed = base64.b64decode(sys.argv[1], validate=True)
key = Ed25519PrivateKey.from_private_bytes(seed)
print(base64.b64encode(key.public_key().public_bytes_raw()).decode("ascii"))
' "${seed_b64}")"
printf 'public key (safe to commit): %s\n' "${public_b64}"
```

Store the **seed** at exactly these coordinates, using the Infisical wrapper (the bare CLI is unlinked and false-negatives):

| Field | Value |
| --- | --- |
| Environment | `dev` |
| Path | `/agents/sandbox/legalforecastbench/harness-runtime/evaluator-issuer` |
| Secret name | `HARVEY_LAB_EVALUATOR_ED25519_PRIVATE_KEY` |
| Value | `${seed_b64}` — base64 of exactly 32 raw seed bytes (RFC 8032) |

Then commit the public half only: set `public_key_base64` to `${public_b64}` and `status` to `configured` in `examples/adapters/harvey-lab/evaluator-issuer-authority.json`. Clear `seed_b64` from the shell (`unset seed_b64`) before leaving the session.

Rotation: mint a new seed, write it to the same path, commit the new public key in the same change. There is no dual-key window — verification matches exactly one `key_id`, so a receipt signed by the retired key stops verifying the moment the public key changes. Archive the retiring public key alongside any receipts already issued under it before rotating.

## 2. Tier-0 spend-approval keypair

This is the key that signs the detached approval authorizing a paid run.

**Its private half must never be stored under `/agents/sandbox/`.** Agents can read that namespace; an approval key there would let an agent sign its own spend authorization. Generate it offline with the same commands as step 1, keep the private half in **1Password** (this is routine human-touched credential custody, §8B), and commit only the public half to `examples/adapters/harvey-lab/tier0-approval-authority.json` with `status: configured`.

The two keys must remain distinct — the runner refuses an approval whose issuer matches the evaluator signer.

## 3. Judge provider credential

| Field | Value |
| --- | --- |
| Environment | `dev` |
| Path | `/agents/sandbox/legalforecastbench/harness-runtime/tier0-judge` |
| Secret name | `TIER0_JUDGE_ANTHROPIC_API_KEY` |
| Value | an Anthropic API key scoped to the Tier-0 workspace |

The production factory fetches this through the sanctioned wrapper at the moment of a paid call and refuses any other environment, path, or name before fetching. There is no host-environment fallback.

Also install the optional SDK extra the judge adapter pins, or the paid path fails closed:

```bash
uv sync --extra tier0-judge-adapter
```

## 4. Install the pinned evaluator entrypoint

Provider-free; safe to run now.

```bash
uv run legalforecast multiharness tier0 install-evaluator-wrapper \
  --bin-dir "<a directory on your PATH>" \
  --scratch-root "<fresh absent scratch path>" \
  --output "<install record path>"
```

Expected digest: `sha256:3af0fdfa4af48cbc123fc599f65c9119b9fc832efd30c9c2acce341b51cdd820`. The installer copies the committed bytes verbatim, then runs the credential-free capability probe against the installed path and refuses a mismatch.

## 5. `dm0g.4.2.2` privileged containment capture — DO NOT RUN YET

**The capture command in `docs/adapters/claude-code-native-containment.md` will fail again if run as written.** Its recorded failure on 2026-07-24 was HTTP 413: the reviewed probe (then 79,441 bytes) exceeded sudo-gate's configured per-file attachment cap, before approval or execution, producing no evidence. `scripts/probe_claude_code_native_containment.py` is now **81,433 bytes** — larger than the payload that was already rejected. Running it would burn an approval window on a known rejection.

Two things must happen before any capture attempt, in this order:

1. **Resolve the size rejection.** Either a separately reviewed sudo-gate per-file attachment-cap increase, or a source-transport refactor whose staged bytes, reconstruction, and final source hash get a fresh independent review. Confirm the effective cap against the current 81,433-byte probe before scheduling the sitting.
2. **Get the digests approved.** `dm0g.4.5.16-reviewer` approves, as part of the re-review, the probe source digest and the target executable identity:

   | Field | Value |
   | --- | --- |
   | Probe source | `scripts/probe_claude_code_native_containment.py` |
   | Probe SHA-256 | `264d4119363a2c824665dd53d4cbb73bc94f026db473b6062e77b402f9e51a47` |
   | Target executable | Claude Code `2.1.233` |
   | Target SHA-256 | `55d281096f57d411ebbdd94dbf5e9ff3accb7c05713e37348c2c11d4b83bf9d9` |

   The committed procedure still names 2.1.220 (`674f61f2…`), which matches neither the installed binary nor the freeze. That document's target table must be corrected to 2.1.233 in the same change that records the reviewer's approval — otherwise the capture cannot clear Tier-0 even if it succeeds.

Only once both hold: run the documented block from the repository root, cwd-bound, replacing `INSERT_FRESH_INDEPENDENTLY_APPROVED_SHA256` with `264d4119363a2c824665dd53d4cbb73bc94f026db473b6062e77b402f9e51a47`, and change the `mktemp` suffix and the `--reason` text from `2.1.220` to `2.1.233`. Approve the staged, hash-attested request out of band within its window. Keep the capture outside the repository until a different independent reviewer validates it.

## 6. Native-thin enforcement blocker (decision, not provisioning)

`tier0 mint` refuses to emit a paired spend policy until the native-thin arm can name a budget flag its command genuinely honors. The pinned upstream harness exposes none. Pick a path and assign it:

- land a reviewed metering boundary the native-thin invocation must egress through, so the controller can stop it; or
- obtain an upstream budget flag and re-characterize the pinned command.

Neither is an operator action tonight — it is a scoping decision that gates the paired run.

## Sequence summary

| Step | Blocking? | Who |
| --- | --- | --- |
| 1. Evaluator keypair → Infisical + public key commit | yes | operator |
| 2. Approval keypair → 1Password + public key commit | yes | operator |
| 3. Judge credential → Infisical, plus `uv sync --extra tier0-judge-adapter` | yes | operator |
| 4. Install `harvey-lab-eval` | yes | operator or agent |
| 5. Privileged capture | yes, and currently unrunnable | operator, after the size fix and reviewer digest approval |
| 6. Native-thin enforcement decision | yes | owner |
| Mint spec + sidecars | after 1–4 and 6 | operator, inside the private boundary |
| Detached spend approval | after reviewer acceptance | operator |
