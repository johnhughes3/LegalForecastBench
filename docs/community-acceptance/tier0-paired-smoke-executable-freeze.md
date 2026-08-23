# Tier-0 executable freeze (T0R2 operator-half successor packet)

Status: **NOT AN APPROVAL TARGET**. This packet supersedes the T0R successor packet for operator command shape, evaluator entrypoint identity, production evaluator seam, dated pricing, and per-call ceiling configuration. It does not authorize spend. The designated approver must not sign until `dm0g.4.5.16-reviewer` records acceptance against these bytes and the blocking inputs in "What is still missing" are resolved.

No provider call is authorized by this document.

## What this packet binds

| Field | Value |
| --- | --- |
| Packet | `docs/community-acceptance/tier0-paired-smoke-executable-freeze.md` |
| Supersedes | The T0R successor packet (`00d37b320cee3d937712b291748143cc816e0dad6813c2ccd71cad2e45c136bc`) in full, and `docs/community-acceptance/tier0-paired-smoke-structural-freeze.md` (`b8a3053f971c81e442fdb778ca7044ee92f24a78dc6eb899e86b05ab2bbdf919`) for operator command, binary identity, evaluator entrypoint, and spend-control shape |
| Reviewer | `dm0g.4.5.16-reviewer` |
| Regeneration | Recreate this file from the rows below, then `sha256sum` it. The companion `.sha256` and the readiness-pack executable-freeze table move together |

## Exact operator commands

Caller-supplied roots are mandatory. Private and archive roots must be fresh absent paths. There are no run-varying flags on the paid commands.

```bash
# 1. Install the pinned evaluator entrypoint (one time, provider-free).
uv run legalforecast multiharness tier0 install-evaluator-wrapper \
  --bin-dir "<operator bin directory on PATH>" \
  --scratch-root "<fresh absent probe scratch root>" \
  --output "<install record path>"

# 2. Mint the executable spec and its two sidecars (one time, provider-free,
#    inside the private boundary; the outputs carry evaluator-private
#    criterion IDs and must never enter git).
uv run legalforecast multiharness tier0 mint \
  --output-dir "<fresh private mint directory>" \
  --private-task-json "<pinned LAB checkout>/tasks/employment-labor/identify-issues-in-counterparty-motion-brief/task.json" \
  --native-thin-manifest "<native-thin arm identity JSON>"

# 3. Validate, then run.
export LFB_TIER0_SOURCE_ROOT="<existing LAB pin directory>"
export LFB_TIER0_PRIVATE_ROOT="<fresh absent private root>"
export LFB_TIER0_ARCHIVE_ROOT="<fresh absent archive root>"

uv run legalforecast multiharness tier0 validate \
  --spec "<mint dir>/tier0-executable-spec.json" \
  --spec-sha256 sha256:MINTED_SPEC_SHA256 \
  --approval TIER0_DETACHED_APPROVAL.json

uv run legalforecast multiharness tier0 run \
  --spec "<mint dir>/tier0-executable-spec.json" \
  --spec-sha256 sha256:MINTED_SPEC_SHA256 \
  --approval TIER0_DETACHED_APPROVAL.json
```

`tier0 run` installs the single supported production evaluator/provider factory at the CLI boundary when no embedding runtime has already installed a reviewed one. There is no adapter selector: an adapter chosen by flag or environment variable would be a run-varying input the frozen spec hash does not cover.

## Why the spec hash is not printed in this packet

The per-criterion judge ceilings must carry the 23 upstream criterion IDs verbatim, because the runner matches reservation *N* to the *N*th ceiling for its arm and refuses an identity mismatch. `docs/adapters/harvey-lab-pinned-evaluator-seam.md` classifies the criterion `id` field as evaluator-private, and this repository is public. The spec binds the policy digest, so the spec hash cannot be computed publicly either.

This packet therefore binds the **deterministic generator plus every public input**, and the operator mints the artifacts inside the private boundary. `tests/test_tier0_operator_half.py::test_mint_is_byte_reproducible_across_output_directories` proves the generator is byte-reproducible; a reviewer holding the same pin recomputes the same three hashes.

| Field | Value |
| --- | --- |
| Generator | `legalforecast/multiharness/tier0_mint.py` |
| Experiment ID | `tier0-paired-smoke-2026-08-17` |
| Emitted files | `tier0-executable-spec.json`, `tier0-executable-spec.pricing-snapshot.json`, `tier0-executable-spec.spend-policy.json` |
| Private inputs | pinned `task.json` (hash-verified against `c117cc3faf49b879f3c475b097bd67293ca79fa5b9e3d9cd91782b0f70f687e4` before parsing); native-thin arm identity manifest |

## Source pin and task

| Field | Value |
| --- | --- |
| Repository | `https://github.com/harveyai/harvey-labs` |
| Commit | `73feb91d63d53b1a44151d99329779c4defcdb72` |
| Tree | `944913ee8cdeaef4930a106e5e16d74aa93a29d7` |
| Task | `employment-labor/identify-issues-in-counterparty-motion-brief` |
| `task.json` SHA-256 | `c117cc3faf49b879f3c475b097bd67293ca79fa5b9e3d9cd91782b0f70f687e4` |

## Model identities

| Surface | Requested identity |
| --- | --- |
| Clean-native solver | `anthropic:claude-sonnet-4-6` |
| Native-thin solver | `anthropic:claude-sonnet-4-6` |
| Judge | `anthropic:claude-sonnet-4-6` with provider-default sampling (`temperature` and `top_p` omitted) |
| Criterion calls per complete arm | 23 |

## True binary identities

Provider-free interface re-characterization on 2026-08-17. Probe commands requested no model call.

| Binary | Version | SHA-256 | Fixture |
| --- | --- | --- | --- |
| `claude` | `2.1.233 (Claude Code)` | `55d281096f57d411ebbdd94dbf5e9ff3accb7c05713e37348c2c11d4b83bf9d9` | `tests/fixtures/claude_code_cli_characterization/claude-code-cli-interface-2.1.233.json` |
| `codex` | `codex-cli 0.147.0` | `cb0a15567e9a60a5820d54b0f6ae86d504dc3805c1eab21a47f70e3eb7b73a40` | `tests/fixtures/codex_cli_characterization/codex-cli-interface-0.147.0.json` |

`codex exec --help` on 0.147.0 advertises `--approve-for-me`. The adapter still refuses that flag. The earlier 4.4.27 digest `d6877199…` is not this pin.

## Evaluator entrypoint

The pinned entrypoint is now installed rather than assumed.

| Field | Value |
| --- | --- |
| Committed source | `scripts/harvey-lab-eval` |
| Installed name | `harvey-lab-eval` |
| Version | `1.1.0` (probe line: `harvey-lab-eval 1.1.0`) |
| SHA-256 | `sha256:3af0fdfa4af48cbc123fc599f65c9119b9fc832efd30c9c2acce341b51cdd820` |
| Installer | `uv run legalforecast multiharness tier0 install-evaluator-wrapper` |
| Install semantics | byte-identical copy; the committed digest is the installed digest |

The wrapper is provider-free and credential-free. Executed, it validates the frozen evaluation-input contract and then refuses with exit `3`: the upstream aggregate evaluator issues all 23 criterion judge calls inside one invocation, and no per-call ceiling can be checked before them. Paid scoring runs through the per-criterion production seam instead, which reserves budget immediately before every paid request. The wrapper's role on the paid path is identity — its bytes are pinned by the spec and bound into every evaluation receipt — plus making the unaccounted aggregate path unreachable rather than merely discouraged. It inherits the stripped containment environment and holds no credential logic; a credential-dependent failure surfaces upstream, by design. The accepted `schema_version` is `legalforecast.harvey_lab_evaluation_input.v1` — the identifier the in-tree producer actually emits. Version `1.0.0` pinned a different spelling, so every real `evaluation_input_record()` exited `4` (malformed) instead of reaching the intended exit-`3` refusal; the wrapper refused everything by accident rather than by design.

## Production evaluator and judge seam

| Field | Value |
| --- | --- |
| Module | `legalforecast/multiharness/tier0_production_factory.py` |
| Installed by | `tier0 run`, unconditionally, when no reviewed factory is already installed |
| Provider surface | Anthropic Messages API through the official SDK |
| Required SDK version | `0.116.0` (optional extra `tier0-judge-adapter`; a mismatch fails closed) |
| Judge credential | Infisical `dev`, `/agents/sandbox/legalforecastbench/harness-runtime/tier0-judge`, `TIER0_JUDGE_ANTHROPIC_API_KEY` |
| Credential resolution | injected callback at the process boundary; no host-environment fallback |
| Judge settings SHA-256 | `sha256:87863d48b22b4a1803605b0ae0a352fa06123a075b10ad96a3aa70d6789e57bf` |
| Judge prompt SHA-256 | `sha256:9aa7ce65e53bba6309b88d380f26ece8776fc3d63eb6eda36db9a287a79d8bac` |
| Judge output schema SHA-256 | `sha256:0543828cbd14f4f8d22312f89666cae2bdacfbfae6b5eabb2b8a4ea350bc5dc0` |
| Runtime policy SHA-256 | `sha256:81fdf9cdab802a9543cd6bc93b6eba7236be49f932c4449ea1843d6ea9352dda` |
| Egress policy SHA-256 | `sha256:e34d58b19f2ebe034e84ee59de0e02bebe194bfd72d9e6449a278f2720051f46` |
| Resource policy SHA-256 | `sha256:6302b8ece0d27180c098c9f5cc4c43516222d384732a461af27860b0b52b5b95` |
| Token accounting policy SHA-256 | `sha256:9ec98d3f7e68889f2414538099137ebc8ce88bcff2a84bc4cd5a5848452e7f88` |
| Judge input | criterion text **and** the candidate deliverable, extracted from the sealed `.docx` |
| Deliverable authentication | overlay bytes must reproduce the sealed `deliverable_tree_sha256` before any request |
| Deliverable bound | prompt bytes must not exceed the minted judge `max_input_tokens` less a 256-token framing reserve; an oversized prompt refuses rather than truncating |
| Judge identity enforcement | resolved model must equal the pinned `claude-sonnet-4-6`; a substitution refuses rather than being costed at the pinned rate |
| Cost basis | `estimated_from_pricing_snapshot` |

Every billed attempt, including retries, is written under `<private root>/evaluator/judge-attempts/<criterion>/` with exclusive-create semantics before settlement, so a retry can never erase the attempt it replaced. A response carrying subscription-unallocable or unknown usage is refused; `fixture/stub@local` is refused on this path. Each retained attempt also records the `deliverable_sha256` the verdict was formed against, so the bytes behind a verdict are auditable from the attempt alone.

## Dated pricing snapshot

| Field | Value |
| --- | --- |
| Snapshot ID | `tier0-anthropic-2026-08-17` |
| As-of date | `2026-08-17` |
| Source | `https://platform.claude.com/docs/en/about-claude/models/overview`, legacy-models table, checked 2026-08-17 |
| SHA-256 | `sha256:efbdc066693a3ef273c6a2738f47d1dbc3ca27383b37f5d8ea439f4e49eedc55` |

| Provider | Model | Input µUSD/token | Output µUSD/token | Request µUSD |
| --- | --- | --- | --- | --- |
| `anthropic` | `claude-sonnet-4-6` | 3 | 15 | 0 |

That is $3.00 per million input tokens and $15.00 per million output tokens. Only the model the spec actually uses is priced; an unused row would be a pricing claim nothing verifies.

## Per-call ceiling configuration

Every dollar figure is derived from the token caps and the rates above.

| Scope | Cap | Derivation |
| --- | --- | --- |
| Judge, per criterion | `$0.08`, 3 requests, 2 retries, parallelism 1 | worst case 24,000 in + 16 out = `$0.072240`, rounded up to the next cent |
| Solver, per arm | `$8.000000`, 1 request, 0 retries, parallelism 1 | worst case 400,000 in + 64,000 out = `$2.16` per request |
| Experiment-wide | `$27.040000`, 140 requests, parallelism 1 | 2 solver invocations plus 2 × 23 × 3 judge attempts |

The experiment stop sits inside the planning-only USD 25–100 administrative band the readiness pack records. The evaluator requests budget through `HarveyLabJudgeRequestBoundary.before_judge_call` immediately before every paid judge request, retries included; the provider-free proof of a mid-evaluator halt is `tests/test_tier0_mid_evaluator_spend_halt.py`.

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

The designated credential operator provisions the secret; agents never write or read it. Verification fails closed until the public key is committed and `status` is `configured`.

The Tier-0 **approval** authority is a distinct, human-only key. Its private half must never be stored under `/agents/sandbox/`: an agent-readable approval key would let an agent sign its own spend approval. Generate it offline and keep the private half in 1Password; only the public half is committed to `examples/adapters/harvey-lab/tier0-approval-authority.json`.

## What is still missing

These are blocking, in the order they gate the run.

1. **The native-thin arm has no enforceable dollar ceiling.** `SolverCeiling` requires an `adapter_argument` budget — a flag the invoked command genuinely honors — and the runner verifies the rendered command passes `<argument> <amount>`. The 2026-07-16 characterization of the pinned upstream harness records its complete option list as `--model`, `--task`, `--run-id`, `--max-turns`, `--temperature`, `--shell-timeout`, `--reasoning-effort`, `--skills`, `--sandbox-image`. None is a monetary cap, and a turn limit is not a dollar ceiling. `tier0 mint` therefore cannot produce a complete paired policy today, and refuses rather than emitting an advertised-but-unenforced budget. Two remediation paths exist, both needing review before use: land an approved metering boundary the native-thin invocation must egress through, or obtain an upstream budget flag and re-characterize. **Until one lands, paid Tier-0 is blocked regardless of every other input below.**
2. **Two public keys are unprovisioned** — the evaluator issuer and the distinct Tier-0 approval authority. Both committed config files still carry `public_key_base64: null`.
3. **The judge credential is unprovisioned** at the Infisical path named above.
4. **The `dm0g.4.2.2` privileged containment capture is absent**, and the documented procedure still targets Claude Code 2.1.220 rather than the installed 2.1.233.
5. **The solver credential handshake is unresolved.** Both arms pin `auth_profile: published-api-key`, and that path 404'd during the B2 close-out (`dm0g.4.2.13`, still open). The judge credential in item 3 is a separate secret at a separate path and does not cover the solver surface.
6. **The detached spend approval does not exist**, and must not be created before the reviewer records acceptance.

## Unminted paid artifacts

These hashes do not exist yet and must not be invented:

- executable spec SHA-256, spend-policy SHA-256 (minted per §"Why the spec hash is not printed", once item 1 is unblocked)
- native-thin solver executable digest and version
- detached spend-approval signature

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

The sibling published-api-key path 404'd and was not used. No Codex live task was retried after the 4.4.27 timeout. This lane performed no additional live probe.

## Designated operator's remaining exact actions

The batched sequence is in `docs/community-acceptance/tier0-operator-provisioning-card.md`. In summary: provision the two keypairs and the judge credential in one sitting, run the privileged no-spend capture from the exact block that card prints, and resolve the native-thin enforcement blocker. Only after those inputs exist may the spec be minted, the reviewer asked for fresh acceptance, and the detached approval created.
