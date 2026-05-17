# Official Evaluation Environment

Official LegalForecastBench runs use a protected GitHub environment and
short-lived AWS OIDC credentials. The benchmark repository does not store
long-lived AWS access keys and does not give pull requests, forks, or untrusted
branches access to private model packets.

## Protected Environments

`legalforecastbench-official-eval` is the read-only packet environment. Configure
it in GitHub with:

- secure-gate deployment protection enabled;
- required reviewers if the repository also uses human review;
- branch/ref restrictions limited to `main`;
- variable `LFB_AWS_REGION`;
- variable `LFB_PACKET_BUCKET`;
- variable `LFB_RESULTS_BUCKET`;
- variable `LFB_MODEL_PACKET_PREFIX` set to `model-packets/`;
- variable `LFB_RESULTS_MANIFEST_PREFIX` set to `manifests/`;
- secret `LFB_GITHUB_PACKET_READ_ROLE_ARN`.

`legalforecastbench-official-results` is reserved for the optional append-only
results-writer role. Configure it only if COS deploys that role with
`enableGithubResultsWriter=true`, and store the role ARN as
`LFB_GITHUB_RESULTS_WRITE_ROLE_ARN`.

## Read-Only Workflow

The consumer-side validation entrypoint is
`.github/workflows/official-s3-access-validation.yaml`.

It is intentionally `workflow_dispatch` only. It has no `pull_request` trigger,
checks `github.ref == 'refs/heads/main'`, resolves the requested `release_sha`
against `origin/main`, and grants `id-token: write` only to the protected AWS
job. AWS credentials are issued only after GitHub enters the
`legalforecastbench-official-eval` environment and secure-gate approves the
deployment protection rule.

The packet-read role may:

- list/read `model-packets/` in the private packet bucket;
- list/read public-safe `manifests/` in the results bucket;
- decrypt only approved S3 objects through the artifact KMS key.

The packet-read role must not:

- read `source-documents/`, `extracted-text/`, `audit-bundles/`, `withdrawn/`,
  or `quarantine/`;
- write or delete either bucket;
- administer IAM, KMS, bucket policies, budgets, or account settings;
- call acquisition services such as Case.dev, PACER, or CourtListener.

## Maintainer Roles

Maintainer upload, verification, and debug work uses the local
`cos.benchmark.data-operator` profile documented in the COS runbook. Sealed-case
withdrawal and destructive takedown work uses the separate
`cos.benchmark.data-steward` profile. Do not use those local profiles inside
GitHub Actions jobs.

COS owns the AWS account, buckets, KMS key, GitHub OIDC trust, and IAM roles.
LegalForecastBench owns the workflow contract and the public-safe documentation
for how official runs consume frozen packet manifests.

## Rotation And Revocation

If packet access must be rotated or revoked:

1. remove or replace `LFB_GITHUB_PACKET_READ_ROLE_ARN` in the
   `legalforecastbench-official-eval` environment;
2. update the COS artifact stack trust policy or deploy a replacement role;
3. re-run the protected COS deploy workflow and the LFB S3 access validation
   workflow from `main`;
4. update freeze manifests if bucket names, prefixes, KMS aliases, or packet
   object keys changed;
5. record the revocation reason, old role ARN, new role ARN, workflow run URL,
   and secure-gate approval ID in the private vault, not in this repository.

If a specific case or document is withdrawn, use the storage-layout takedown
process instead of broad role rotation unless the role itself was exposed.
