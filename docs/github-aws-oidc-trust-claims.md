# GitHub → AWS OIDC trust claims: verified condition surface

**Status:** verified against primary sources 2026-08-09. Applies to `infra/official-eval-bootstrap` and `infra/official-eval`.

This note settles a recurring review question: whether `token.actions.githubusercontent.com:repository`, `:ref`, and `:environment` are real, matchable IAM condition keys for this repository's protected-environment tokens.

**They are.** The trust policies in both Terraform roots are correct as written, and the `:repository` / `:ref` / `:environment` conditions must stay.

Two separate review claims asserted otherwise. Both are false, and both are recorded here so they are not relitigated.

## Claim 1 (false): "GitHub does not emit a `ref` claim on protected-environment tokens"

Raised as a CodeRabbit "Security & Privacy | Major" on PR #594. The assertion was that an environment-scoped token carries `sub`, `repository`, `repository_id`, `workflow_ref`, and `environment`, but not `ref`, so a `StringEquals` on `:ref` could never match.

GitHub's documented example token payload is for a job that *does* target an environment, and it carries the environment-qualified subject and a standalone `ref` claim at the same time:

```json
{
  "sub": "repo:octo-org/octo-repo:environment:prod",
  "environment": "prod",
  "ref": "refs/heads/main",
  "repository": "octo-org/octo-repo",
  "ref_type": "branch",
  "event_name": "workflow_dispatch"
}
```

The wording that misleads readers is in GitHub's *subject claim* reference, which says a segment is included "only if the job doesn't reference an environment". That sentence governs which segments are concatenated into the `sub` **string** — `repo:OWNER/REPO:environment:NAME` replaces `repo:OWNER/REPO:ref:refs/heads/BRANCH`. It does not remove the standalone top-level `ref` claim from the token payload.

Source: [GitHub — OpenID Connect](https://docs.github.com/en/actions/concepts/security/openid-connect) (example payload) and [OpenID Connect reference](https://docs.github.com/en/actions/reference/security/oidc) (subject claim composition).

## Claim 2 (false): "AWS maps only `amr`, `aud`, `email`, `oaud`, `sub`, so the other keys are never populated"

Raised in PR #597, which removed the three conditions on this basis. The five-key list is real but is the **Default** tab of AWS's condition-key reference, which states it applies when "your IdP is not listed in the tab options". GitHub *is* listed, with its own tab.

AWS's GitHub tab documents these condition keys: `actor`, `actor_id`, `job_workflow_ref`, `repository`, `repository_id`, `repository_owner_id`, `workflow`, `ref`, `environment`, `enterprise_id`.

Each is marked **Available in session: No**, which is not "unavailable". AWS defines it explicitly:

> When a claim is not available in session, the OIDC condition context key can only be used in a role trust policy for the initial `AssumeRoleWithWebIdentity` authentication.

A role trust policy for `sts:AssumeRoleWithWebIdentity` is exactly where these conditions live. "Available in session" governs whether a key can additionally be referenced from *permission* policies after the role is assumed — which these policies do not do. AWS's own GitHub example trust policy conditions on `:repository`, `:ref`, `:actor`, `:job_workflow_ref`, and `:enterprise_id`.

Source: [AWS — IAM and AWS STS condition context keys](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_iam-condition-keys.html#condition-keys-wif), GitHub tab.

## Why each condition is satisfiable here

The conditions are not merely legal — every one of them matches at runtime, because the workflow and environment configuration produce exactly the asserted values:

| Condition | Value | What guarantees it |
|---|---|---|
| `:aud` | `sts.amazonaws.com` | Default audience requested by `aws-actions/configure-aws-credentials`. |
| `:sub` | `repo:<owner>/<repo>:environment:<name>` | Every role-assuming job binds an `environment:`, which switches the subject to the environment-qualified form. |
| `:repository` | `<owner>/<repo>` | Always present in the token. |
| `:ref` | `refs/heads/main` | Each environment's deployment branch policy is `custom_branch_policies: ["main"]` in `infra/official-eval/github-environments.json`, so an environment-bound job cannot run from any other ref. The infra and validation workflows additionally guard `refs/heads/main` themselves. |
| `:environment` | the bound environment name | AWS notes that if the `environment` condition is used, "an environment must be configured and provided in the GitHub workflow". The bootstrap operator job binds `legalforecastbench-official-provider-authority-infra`. |

The failure mode of getting this wrong is fail-closed in one direction only: an unmatchable condition denies `AssumeRoleWithWebIdentity` (bootstrap cannot run), while a *removed* condition silently widens the trust surface. Removal is the dangerous direction, which is why the conditions are fenced by tests rather than left to review.

## Forward risk: immutable subject claims

GitHub changed the default subject format for repositories **created after 2026-07-15** to `repo:OWNER@OWNER-ID/REPO@REPO-ID:ref:refs/heads/BRANCH`.

This repository was created 2026-05-18, so it retains the legacy `repo:OWNER/REPO:...` subject that `local.github_subject` builds. The `ref`, `repository`, and `environment` claims are unaffected by that change in either format.

If this repository is ever migrated to immutable subject claims, or the official roots are pointed at a newer repository, `github_subject` is the value that must change — not the set of condition keys.

## Do not remove these conditions

`tests/test_official_eval_infra.py` and `tests/test_official_eval_bootstrap_infra.py` assert the exact rendered trust policies, and additionally assert satisfiability against the production inputs themselves: the `github_ref`/subject locals in `infra/official-eval/locals.tf` and `infra/official-eval-bootstrap/locals.tf`, the environment manifest, and the specific workflow jobs that assume each role (environment binding plus `id-token: write` on the assuming job, not merely somewhere in the workflow). A change that drops or loosens a condition, repoints a local at a branch the manifest forbids, or moves the environment binding off the role-assuming job fails those tests. Companion mutation tests in each file drift the real production bytes (via `tests/official_infra_trust_helpers.py`) and require the fences to redden, so the guards are proven to discriminate rather than validating copies of themselves. Re-read this note before proposing a change.
