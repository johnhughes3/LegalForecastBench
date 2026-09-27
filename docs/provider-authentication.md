# Managed provider authentication

The managed document-tool runner separates authentication selection from model and endpoint selection. `LEGALFORECAST_OPENAI_AUTH_MODE` and `LEGALFORECAST_ANTHROPIC_AUTH_MODE` accept `api_key` or `workload_identity`. An omitted mode retains the currently accepted, bounded API-key path during migration. Selecting workload identity never falls back to a static key after a configuration or exchange failure. It also overrides ambient SDK API-key credentials.

Workload identity is implemented for the direct OpenAI Responses and Anthropic Messages transports. The installed provider SDK performs token exchange and refresh; the runner requests a fresh GitHub Actions OIDC assertion for the configured audience whenever the SDK needs one. Authentication does not change the agent loop, model, sampling settings, document tools, or spend reservation.

For either provider, set the following configuration with `PROVIDER` replaced by `OPENAI` or `ANTHROPIC`:

| Variable | Meaning |
| --- | --- |
| `LEGALFORECAST_PROVIDER_AUTH_MODE` | `workload_identity` |
| `LEGALFORECAST_PROVIDER_WIF_AUDIENCE` | Audience registered with the provider |
| `LEGALFORECAST_PROVIDER_WIF_PROVIDER_ID` | OpenAI identity provider ID or Anthropic federation rule ID |
| `LEGALFORECAST_PROVIDER_WIF_SERVICE_ACCOUNT_ID` | Dedicated benchmark service account |
| `LEGALFORECAST_ANTHROPIC_WIF_ORGANIZATION_ID` | Anthropic organization UUID |
| `LEGALFORECAST_ANTHROPIC_WIF_WORKSPACE_ID` | Anthropic benchmark workspace ID |

The Actions job must have `id-token: write` and expose its native `ACTIONS_ID_TOKEN_REQUEST_URL` and `ACTIONS_ID_TOKEN_REQUEST_TOKEN` to the runner process. The latter is a credential and must never be copied into artifacts, tool containers, logs, or configuration files. The runner refuses non-GitHub identity endpoints and redirects. OpenAI and Anthropic custom header overrides are rejected in workload-identity mode because they can inject static authentication independently of SDK credential selection. The check covers both the supplied environment and the process environment, and runs again immediately before SDK client construction.

Successful saved results and public receipts record the authentication mode, provider, endpoint family, and external issuer. A replay uses the saved record and requires no current credentials. Historical results without that record retain unknown authentication; they are not relabeled using the current environment. Exchange and identity-request errors returned by managed execution omit response bodies and exception chains that might expose tokens.

This source support is not a completed official migration. The official workflow continues its accepted static-key configuration until protected provider setup and bounded live verification are complete. Provider-side rules must bind the exact GitHub issuer, repository, main ref, protected environment, audience, and workflow identity; a local configuration file does not enforce those remote rules. Least-privilege inference scope, provider budgets, revocation, and removal or isolation of old keys remain rollout work. Administrative setup belongs in the private operations repository.

Google authentication remains API-key based. Workload-identity mode for Google is rejected until a distinct supported OAuth transport and its model, regional, usage, and pricing compatibility are verified. Jev summary preparation and one-shot experiments, legacy direct solvers, and community adapters are outside this managed document-tool integration. Issue #37 remains open for those official migration requirements, workflow activation, and live provider proof.

The implementation follows the [OpenAI GitHub Actions WIF contract](https://developers.openai.com/api/docs/guides/workload-identity-federation/github-actions) and [Anthropic WIF contract](https://platform.claude.com/docs/en/manage-claude/workload-identity-federation). Network-free tests exercise the installed SDKs with intercepted HTTP traffic; they do not prove provider-side claim enforcement or a live model response.
