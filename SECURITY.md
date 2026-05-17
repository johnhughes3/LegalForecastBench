# Security Policy

LegalForecast-MTD is local benchmark tooling. The default test and fixture
paths should not need live credentials, network access, PACER fees, Case.dev
fees, or model-provider calls.

## Supported Version

Security feedback currently targets `0.1.0a1` / `v0.1.0-alpha.1`.

## Report Privately When Needed

Use a private channel for issues involving:

- API keys, tokens, provider account IDs, or billing exposure;
- paid PACER or Case.dev paths that can run unexpectedly;
- path traversal or unsafe artifact writes;
- sealed, restricted, or sensitive filing material;
- model sandbox escapes or unintended network access;
- publication of private source-document text.

If a private channel is not available, file a minimal public issue that says a
private security report is needed and omit sensitive details.

## Safe Public Reports

Public reports are fine for fixture-only failures, stale docs, unclear
result-tier language, or reproducible offline test failures. Include the exact
command, expected behavior, observed behavior, and whether live credentials
were present.

## Cost and Credential Guardrails

Any change that makes live, paid, or credentialed paths run by default is a
security regression. Acquisition commands that can purchase material must
require explicit execution flags and fee acknowledgement.
