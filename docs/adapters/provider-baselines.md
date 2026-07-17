# Provider Runtime Baseline Adapters

The provider/runtime baseline tracks give community users reference points for interpreting LQ.AI, Hermes Agent, OpenClaw, and other harness comparisons. They are not official LegalForecastBench evaluation paths, and their results publish only to community comparison surfaces.

Decision reviewed: 2026-07-17.

This is a provider-surface and project-publication decision, not legal advice. It applies only to the named authentication and execution surfaces below. No provider statement is generalized beyond its documented product surface. Provider documentation and terms can change, so every paid or public run must recheck the linked sources and record the effective auth profile. Ambiguity is a blocking result: an undocumented auth, automation, billing, or publication combination must not run or publish until the provider documents it or gives written permission.

The checked-in fixture manifests are:

- `examples/adapters/openai-responses/adapter-manifest.json`
- `examples/adapters/claude-agent-sdk/adapter-manifest.json`

Both manifests use `examples/adapters/fixture_bridge.py`, run with no network, and prove the adapter contract before a contributor points a manifest at a real provider runtime.

Run the fixture bridge conformance checks:

```bash
uv run legalforecast multiharness conformance \
  --adapter-manifest examples/adapters/openai-responses/adapter-manifest.json \
  --output-dir tmp/openai-responses-conformance

uv run legalforecast multiharness conformance \
  --adapter-manifest examples/adapters/claude-agent-sdk/adapter-manifest.json \
  --output-dir tmp/claude-agent-sdk-conformance
```

Production provider baseline bridges should use API-key auth or another explicit provider-supported API auth mechanism. Do not claim that a ChatGPT, Claude, or similar subscription login is a general third-party API entitlement.

Each result should record public-safe provenance: provider route, model route, runtime style, agent-loop style, auth mode, provider terms assumption, and whether any subscription-login claim was made. Public artifacts must not include provider account identifiers, API keys, raw transcripts, private matter materials, sealed materials, or official LegalForecastBench infrastructure details.

## Installed distribution evidence

The capability check was credential-free and made no model request. It inspected version output, binary hashes, and help text only; it did not call an auth-status command because those surfaces can reveal account identifiers.

| Distribution | Observed binary identity | Supported surface observed without spend |
| --- | --- | --- |
| Codex CLI 0.144.5 | SHA-256 `058d616bde049c0648b72d53a22a54bf428eeb3f10e76cb4d6d4d4f81b764600` | `codex exec` is explicitly non-interactive; it supports JSONL, ephemeral sessions, output schemas, explicit sandboxes, API-key login, access-token login, and saved ChatGPT auth. |
| Claude Code 2.1.212 | SHA-256 `044a88cf3a5180776617fd3da1238dcbf9141ddec449a39cf7d2af1ac78e684e` | `claude -p` is explicitly non-interactive; it supports JSON and streaming output, JSON Schema, tool allow/deny lists, permission modes, no-session-persistence, and `--max-budget-usd` for print-mode API calls. That option is not a subscription billing limit. `claude setup-token` is documented as requiring a Claude subscription. |

The installed Claude Code version is newer than the earlier 2.1.210 and 2.1.211 observations. Any experiment specification must pin the 2.1.212 hash above or deliberately re-run this capability and terms check for a different binary. The clean-native Claude treatment does not use `--bare`: Anthropic documents that `--bare` changes startup behavior and ignores subscription OAuth tokens, while the experiment is intended to preserve the native installed loop and explicitly control its outer boundary.

## Primary-source record

The OpenAI product sources are [Codex authentication](https://learn.chatgpt.com/docs/auth), [non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode), and [Codex pricing and feature availability](https://learn.chatgpt.com/docs/pricing). The authentication page distinguishes ChatGPT subscription access from usage-based API-key access, assigns API billing to the Platform account, and recommends API-key auth for programmatic workflows. The non-interactive page documents `codex exec`, per-invocation `CODEX_API_KEY`, the official GitHub Action, and the advanced ChatGPT-managed CI path; it says not to use the latter for public or open-source repositories.

The OpenAI publication sources are the [Terms of Use](https://openai.com/policies/terms-of-use/) effective 2026-01-01, the [Services Agreement](https://openai.com/policies/services-agreement/) effective 2026-01-01, the [Sharing & Publication Policy](https://openai.com/policies/sharing-publication-policy/), and the [Brand Guidelines](https://openai.com/brand/). The consumer Terms of Use assign output rights to the user and require evaluation before using or sharing output, with human review as appropriate. The Services Agreement assigns output rights to the customer and makes the customer responsible for evaluating output accuracy and appropriateness; it is not represented here as imposing the consumer terms' human-review-before-sharing formulation. The sharing policy generally permits sharing a user's own prompts and completions with conspicuous AI disclosure and welcomes research publications related to the API. The Brand Guidelines govern use of OpenAI names and marks and prohibit suggesting sponsorship or endorsement.

The Anthropic product sources are [programmatic Claude Code](https://code.claude.com/docs/en/headless), [Claude Code authentication](https://code.claude.com/docs/en/iam), [Claude Code costs](https://code.claude.com/docs/en/costs), and [Claude Code GitHub Actions](https://code.claude.com/docs/en/github-actions). They document `claude -p`, API-key auth, subscription login for Pro, Max, Team, and Enterprise, one-year `CLAUDE_CODE_OAUTH_TOKEN` credentials for scripts and CI, API-key precedence, and API-key-based GitHub Actions. They also distinguish API billing from subscription-included usage and warn that local cost figures are estimates rather than authoritative subscription billing.

The Anthropic publication sources are the [Consumer Terms](https://www.anthropic.com/legal/consumer-terms) effective 2025-10-08 and [Commercial Terms](https://www.anthropic.com/legal/commercial-terms) effective 2025-06-17. Both assign the applicable output rights to the user or customer. The Consumer Terms require independently confirming accuracy before relying on output; the Commercial Terms require evaluating output appropriateness, including human review where appropriate, before using or sharing output. The Consumer Terms prohibit automated access unless it uses an Anthropic API key or Anthropic explicitly permits the surface; the Claude Code programmatic and authentication documentation is the explicit permission relied on here, and only for the documented Claude Code CLI paths. Neither terms page is treated as permission to share credentials, account records, provider confidential information, or provider branding that implies affiliation.

## Supported profile matrix

| Profile | Auth and billing category | Non-interactive and CI decision | Result-publication decision |
| --- | --- | --- | --- |
| `codex-chatgpt-local` | A contributor's own ChatGPT sign-in; usage follows that ChatGPT plan or workspace limits and credits, not API billing. | Supported for local `codex exec`. Public-repository CI is blocked. ChatGPT-managed CI is an advanced path only for trusted private runners or documented Enterprise access-token automation; never copy a browser session or a contributor's cached auth store into a runner. | An operator-run community score, public-safe token dimensions, resolved model/configuration, and reviewed output excerpts may publish under the applicable preliminary label and OpenAI sharing rules. Do not report subscription usage as API spend or disclose account, workspace, credit, or billing identifiers. |
| `codex-api-automation` | A project- or contributor-owned Platform API key; usage-based Platform billing and API data controls apply. | Supported for `codex exec`, scripts, private runners, and isolated CI. Prefer the official Codex GitHub Action; otherwise scope `CODEX_API_KEY` to the single invocation and do not expose it to repository-controlled setup code. | Project-derived scores, API-billed cost totals, public-safe token dimensions, resolved model/configuration, and reviewed excerpts may publish under the applicable community label and OpenAI sharing rules. Keep keys, raw invoices, organization/project identifiers, and raw transcripts private. |
| `claude-subscription-local` | A contributor's own Pro, Max, Team, or Enterprise Claude Code entitlement. Pro/Max usage is included in the subscription; applicable Team/Enterprise order terms and controls must be checked separately. | Supported for local `claude -p` and the documented `CLAUDE_CODE_OAUTH_TOKEN` script/CI surface. This project permits the Tier-0 operator-run local path. Public-repository CI is blocked because the token is a durable personal or seat credential; a future contributor profile must prove a contributor-owned boundary and must not use `--bare` for the clean-native treatment. | An operator-run community score, public-safe token dimensions, plan-category provenance, resolved model/configuration, and reviewed excerpts may publish under the applicable preliminary label. Do not report subscription usage as API spend, publish account or plan-limit records, or imply that the result is independently reproducible. |
| `claude-api-automation` | A project- or contributor-owned Anthropic API key under the Commercial Terms; usage-based API billing applies. | Supported for `claude -p`, scripts, and isolated CI. The official Claude Code GitHub Action documents `ANTHROPIC_API_KEY`; secrets must remain outside repository-controlled code and task workspaces. | Project-derived scores, API-billed cost totals, public-safe token dimensions, resolved model/configuration, and reviewed excerpts may publish under the applicable community label. Keep keys, raw invoices, organization identifiers, provider confidential information, and raw transcripts private. |

## Cross-profile publication and credential boundary

Do not publish provider account identifiers, workspace or organization identifiers, credential paths, auth tokens, API keys, raw invoices, raw usage dashboards, or private billing records. Do not copy or share a contributor's subscription credential. Credentials stay outside solver-visible input, output, scratch, evaluator material, and public artifacts.

The public-repository CI boundary is fail-closed: neither a cached interactive login nor a contributor subscription credential may be installed in a public runner. Only a separately approved API-automation profile with runner isolation and repository-safe secret handling may be considered for that surface.

Do not report subscription usage as API spend. For subscription rows, report the plan category and public-safe token or usage dimensions that the CLI itself emits, and label monetary cost as unavailable or subscription-included unless an authoritative attributable charge exists. For API rows, report the provider-billed amount separately from evaluator and experiment costs and retain the private billing receipt only in the trusted evidence boundary.

Scores and aggregates are project-authored research data. Published output excerpts must be human-reviewed, attributed to the project, and conspicuously identified as AI-generated where the provider policy requires it. The project must use the exact evidence-tier label and non-affiliation statement from `docs/publication-governance.json`; provider names identify the measured product surface and never imply provider endorsement.

Only allowlisted aggregate fields and deliberately reviewed excerpts may leave the trusted boundary; raw transcripts remain private. If current provider sources no longer support a profile, if applicable organization-specific terms differ, or if a publication would require material whose rights or confidentiality are unclear, the run or publication remains blocked under that profile.
