# Provider Runtime Baseline Adapters

These are community comparison adapters. They are not official LegalForecastBench evaluation paths, and their results never rank with official results.

The maintained examples are [`openai-responses`](../../examples/adapters/openai-responses/adapter-manifest.json) and [`claude-agent-sdk`](../../examples/adapters/claude-agent-sdk/adapter-manifest.json). Their ordinary `run` commands are credential-free conformance paths; live provider execution is an explicit `run-with-tools` path using the adapter's allowlisted provider environment and host-owned tool channel. Both are source-checkout adapters whose manifest, code, lockfile, and runtime pins must be used together. Through 2026-09-18 UTC, live `gpt-5.6-sol` `run-with-tools` requests use Vercel AI Gateway; the `OPENAI_API_KEY` grant must be that gateway credential for Sol runs and the direct OpenAI credential for other models. Direct OpenAI routing resumes on 2026-09-19 UTC.

The historical provider smoke submissions under [`community/submissions/2026/`](../../community/submissions/2026/) remain examples only. The no-network packages under [`tests/fixtures/community_submissions/2026/`](../../tests/fixtures/community_submissions/2026/) are test inputs and never publication evidence.

Before any paid or public run, recheck the provider's current authentication, automation, billing, and publication terms for the exact surface being used. Use an explicitly supported API-key or equivalent automation profile; a consumer subscription login is not a general third-party API entitlement. Public repository CI must not install cached interactive or subscription credentials.

Keep provider account, workspace, organization, billing, credential, raw transcript, private matter, and infrastructure details out of public artifacts. Do not report subscription usage as API spend or imply provider sponsorship. Record only public-safe route, requested and served model, runtime, auth category, usage dimensions, and the applicable terms assumption.

The adapter protocol, sandbox and tool-channel rules, source-checkout requirements, and conformance commands live in [the multiharness adapter specification](../multiharness/adapter-spec.md). The typed code and executable fixtures remain the behavior authority.
