# Official provider identity decision for Cycle 1

Date: 2026-07-16

Status: implementation required before the one-provider live smoke

Authority: `LegalForecastBench-dm0g.5.3`

Successor: `LegalForecastBench-5qd6.100`

Independent workflow-integrity gate: `LegalForecastBench-5qd6.101`

External issue: [GitHub #37](https://github.com/johnhughes3/LegalForecastBench/issues/37)

## Decision

Cycle 1 may not use a replayable static model-provider credential for its selected live provider.

The selected Cycle 1 provider is OpenAI for purposes of the one-provider smoke, and `LegalForecastBench-5qd6.35` depends on `LegalForecastBench-5qd6.100`, which implements fail-closed GitHub Actions workload identity federation for that OpenAI cell.

`LegalForecastBench-5qd6.35` also depends on `LegalForecastBench-5qd6.101`, which pins every third-party action in the official credential-bearing workflows to a reviewed full commit SHA before any short-lived subject or access token is exposed to those jobs.

No static-key waiver is authorized by this decision.

GitHub issue #37 remains open after the OpenAI slice because Anthropic and Gemini still require their own terminal migration decisions before either provider enters an official dispatch.

## Evidence reviewed

At the decision commit, this W3 worktree matches `origin/main` and `.github/workflows/run-benchmark.yaml` still preflights and injects `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, and `GEMINI_API_KEY` into provider-selected matrix cells.

The current custom transport in `legalforecast/evals/live_model_solver.py` reads the same environment variables and sends them directly in provider authorization headers.

The repository treats those values as opaque API keys: it records no provider-enforced expiry, rotation deadline, allowed-model scope, source restriction, or hard spending cap for the credential itself.

`LegalForecastBench-5qd6.32` records a verified but not yet published W1 checkpoint for `.github/workflows/official-provider-cell.yaml` that narrows each job to one protected provider environment and a step-scoped generic `PROVIDER_API_KEY`.

That provider isolation is necessary but does not bound credential replay outside the job if the provider credential is long-lived and copied.

`docs/security/model-provider-budget-caps.md` does not exist, and the repository therefore contains no accepted evidence that a static model-provider key has a provider-enforced hard cap sufficient to satisfy the development threat model.

The provider documentation now gives a materially narrower path: OpenAI and Anthropic document direct GitHub Actions federation to short-lived service-account tokens, and Google Cloud documents workload identity federation for deployment pipelines.

## Threat-model conclusion

The official workflow already limits when a paid-model job can start, and W1's provider-cell design limits which provider secret and AWS role a job receives.

Those controls reduce accidental cross-provider exposure, but they do not prevent a copied long-lived provider key from being replayed from another process or host until revocation.

Workload identity binds the credential exchange to the protected GitHub workflow identity and returns a short-lived token, so compromise is constrained by both claim matching and token lifetime.

The remaining implementation risk is moderate and bounded: approximately four agent-hours for the explicit auth mode, token exchange, workflow integration, provenance redaction, and network-free tests, plus John-controlled provider-side identity-provider and service-account setup during `LegalForecastBench-5qd6.35`.

## Provider disposition

| Provider | Gate status | Exact route |
| --- | --- | --- |
| OpenAI | Cycle 1 gate | Implement `LegalForecastBench-5qd6.100` before `LegalForecastBench-5qd6.35`; the smoke uses the protected GitHub OIDC identity and a short-lived OpenAI service-account token. |
| Anthropic | Residual issue #37 work | Reactivate before an Anthropic registry row is approved for official dispatch; create a blocking implementation bead, configure Anthropic WIF rules and a service account, and prove `ANTHROPIC_API_KEY` must be unset so it cannot take precedence over federation. |
| Gemini | Residual issue #37 work | Reactivate before a Gemini registry row is approved for official dispatch; first decide direct Gemini OAuth versus Vertex AI through Google Cloud WIF using transport and model-equivalence evidence, then create the corresponding blocking implementation bead. |

If the smoke operator proposes a provider other than OpenAI, that proposal changes this decision's implementation premise and requires a new explicit decision plus a provider-specific blocking bead before dispatch.

## OpenAI implementation contract

The provider-side trust rule must pin issuer, audience, repository, ref, workflow_ref, and environment rather than accepting a repository-wide subject.

The exact production mapping is GitHub issuer `https://token.actions.githubusercontent.com`, the configured OpenAI audience, repository `johnhughes3/LegalForecastBench`, ref `refs/heads/main`, the exact reusable-workflow `workflow_ref` at a reviewed immutable revision, and the protected official provider environment.

The workflow requests `id-token: write`, obtains a GitHub subject token only inside the selected protected provider job, and exchanges it for an OpenAI access token using non-secret identity-provider and service-account identifiers.

The OpenAI service account is limited to the smallest model-request permission set needed by the frozen registry, beginning with `api.model.request`; provider-side provisioning and the first live token exchange are recorded by the John-owned smoke bead.

The runtime auth mode is explicit and fail-closed: missing or invalid workload identity input is an error, `OPENAI_API_KEY` and `PROVIDER_API_KEY` are absent from the OpenAI cell, and no code path silently retries with a static key.

Private provenance records the auth mode and non-secret identity-provider, service-account, issuer, audience, repository, ref, workflow, and environment identifiers.

Subject assertions, exchanged access tokens, authorization headers, and raw provider responses are excluded from logs, Actions artifacts, receipts, and public run cards.

Network-free tests must cover successful wiring, missing identity material, claim mismatch, malformed or expired exchange responses, rejection of static-key fallback or shadowing, and redaction.

## Residual reactivation and exceptions

The Anthropic residual reactivates before an Anthropic registry row is approved for official dispatch, not after a dispatch is queued.

The Gemini residual reactivates before a Gemini registry row is approved for official dispatch, with the transport choice resolved before credential implementation begins.

Closing `LegalForecastBench-5qd6.100` does not close GitHub issue #37; issue closure requires terminal evidence for every provider allowed by the official registry or an explicit decision removing that provider from official scope.

Any future request to use a static credential requires a new John-approved security decision that records actual provider-enforced hard-cap evidence, scope, isolated environment, expiry, revocation owner, and the successor migration gate; neither this document nor an isolated provider environment supplies that exception.

## Primary guidance

- [OpenAI workload identity federation for GitHub Actions](https://developers.openai.com/api/docs/guides/workload-identity-federation/github-actions)
- [OpenAI workload identity federation overview](https://developers.openai.com/api/docs/guides/workload-identity-federation)
- [Anthropic workload identity federation](https://platform.claude.com/docs/en/manage-claude/workload-identity-federation)
- [Anthropic GitHub Actions WIF setup](https://platform.claude.com/docs/en/manage-claude/wif-providers/github-actions)
- [Google Cloud workload identity federation](https://docs.cloud.google.com/iam/docs/workload-identity-federation)
- [GitHub Actions OpenID Connect reference](https://docs.github.com/en/actions/reference/security/oidc)
