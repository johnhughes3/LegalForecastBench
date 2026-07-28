# Official paid-labeling authority

This module creates the distinct GitHub Actions OIDC role used by the protected paid-labeling workflow.

It does not create or replace the shared provider spend authority table.
The exact existing table ARN and its SHA-256 identity must match the frozen `legalforecast.provider_cycle_caps.v1` artifact before Terraform can apply.
The role policy permits only `ConditionCheckItem`, `DescribeTable`, `DescribeTimeToLive`, `GetItem`, `PutItem`, and `UpdateItem` against that one table.
`TransactWriteItems` authorizes each item operation separately, so the durable poison transaction needs both `ConditionCheckItem` and `UpdateItem`; there is no standalone `dynamodb:TransactWriteItems` IAM action.
It grants no S3, `Scan`, `DeleteItem`, table administration, or wildcard resource authority.
The paid workflow runs only on a GitHub-hosted runner and requests a 7,200-second role session, matching its 120-minute job timeout.

The trust policy admits only these exact protected GitHub environments:

- `legalforecastbench-official-labeling-authority-smoke`
- `legalforecastbench-official-labeling-anthropic-unitize`
- `legalforecastbench-official-labeling-google-review`
- `legalforecastbench-official-labeling-openai-label`
- `legalforecastbench-official-labeling-google-label`

Each provider-bearing environment must contain only its provider's `PROVIDER_API_KEY`, the transport-only `BATON_AGE_IDENTITY`, and the protected non-secret variables required by `.github/workflows/official-paid-labeling.yaml`.
The age identity decrypts closed acquisition batons but grants no provider, AWS, evaluation, freeze, or dispatch authority; the matching `LFB_BATON_AGE_RECIPIENT` is non-secret configuration.
The authority-smoke environment contains no provider key.
Every environment must require a human reviewer and use a deployment branch policy that admits only `main`; the OIDC environment subject does not independently bind the Git ref.
The workflow maps that one generic secret to the provider-specific process variable only for the provider-call step.
The raw role ARN, table ARN, and AWS account identifier remain protected configuration and must not appear in provider-cycle-caps, run cards, or published artifacts.
The public SHA-256 table-identity commitment is an equality check, not a secrecy boundary: a party that can enumerate likely ARNs can recover the account identifier by testing candidates.

Run Terraform from a protected operator context.
Use a disposable `TF_DATA_DIR` and `terraform init -backend=false` for local validation.
Provisioning and the live provider-free permission smoke are separate operator checkpoints; committing this module does not claim that either has occurred.
