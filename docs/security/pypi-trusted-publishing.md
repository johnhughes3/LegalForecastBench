# PyPI Trusted Publishing and Release Environment

This note is the single record of how `legalforecast-mtd` reaches PyPI: which identity is allowed to publish, which refs may run the publishing workflow, what the environment review does and does not buy, and how to revoke publication rights when something goes wrong.

The controlling property is that **no long-lived PyPI credential exists**. Publication is authorized by a short-lived OpenID Connect token that GitHub mints for one workflow run, and PyPI accepts it only when every registered claim matches. There is nothing in the repository, in Actions secrets, or on a maintainer's machine that could be stolen and replayed to publish a release.

## Registered trusted publisher

PyPI matches an incoming OIDC token against these exact values. All five must agree, and a mismatch in any one of them is a refusal, not a warning.

| Claim | Value |
| --- | --- |
| PyPI project | `legalforecast-mtd` |
| Repository owner | this repository's owner account, as GitHub's `repository_owner` claim reports it |
| Repository | `LegalForecastBench` |
| Workflow filename | `publish-package.yaml` |
| GitHub environment | `pypi` |

Registration happens on pypi.org, not in this repository. Until the project exists on PyPI it is registered as a *pending* publisher under the same five values; the pending registration converts to an ordinary trusted publisher on first successful upload.

Renaming the workflow file, renaming the environment, moving the repository, or transferring the project to a different owner all invalidate the registration. Any of those changes has to be paired with re-registration on PyPI, or the next release fails closed at upload.

## Ref restriction

Publication is restricted to release tags at three independent layers, so no single edit re-opens branch publication:

1. **Trigger.** `.github/workflows/publish-package.yaml` runs only on `push` of tags matching `v*`. There is no `workflow_dispatch` trigger and no manual publish input. Manual branch publication is not offered rather than being gated, because the release-check artifacts a publish consumes are only meaningful for a tagged commit; adding either is a change to this policy, not a convenience.
2. **Job guard.** The `publish` job additionally requires `startsWith(github.ref, 'refs/tags/v')`. This is defense against a future trigger being added without the ref implications being noticed: a non-tag ref reaches the job and the job declines to run.
3. **Environment rule.** The `pypi` environment must restrict deployments to protected tags matching `v*`. This is a repository setting, not a file in the tree, and it is the layer that survives a compromised workflow file, because the environment gate is evaluated by GitHub before any job step executes.

Layer 3 is the one an operator has to set by hand. Layers 1 and 2 are asserted mechanically by `tests/test_publish_package_workflow.py`.

## Self-review and administrator bypass

**Decision: self-review is permitted; the `pypi` environment review is a deliberation checkpoint, not a separation-of-duties control.**

The repository is maintained by a single owner, so requiring a distinct approver would mean either blocking releases or granting a second person publish authority for the sole purpose of clicking approve. Neither improves the outcome. What the required reviewer does buy is real: no `git push --tags` publishes on its own. A human has to look at the tag, at the release-check artifacts, and at the diff, and act at publish time.

**Administrator bypass is not treated as a security boundary.** A repository administrator can approve their own deployment and can edit environment protection rules; the environment gate therefore constrains automation and accidents, not a hostile administrator. The boundary that does hold is the trusted-publisher claim set above: even with full administrative control of this repository, publishing as `legalforecast-mtd` requires a run of *this* workflow file, in *this* environment, on *this* repository. Widening publish authority is an action on pypi.org, which is separately controlled.

The following are prohibited, and each one converts the design above into an ordinary secret-based pipeline:

- Adding a PyPI API token as a repository, environment, or organization secret.
- Adding `workflow_dispatch`, a branch trigger, or a "publish" input to the publishing workflow.
- Removing the `environment: pypi` binding, or pointing the publish job at an unprotected environment.
- Publishing from a fork, a mirror, or a second workflow file.

## Revocation and recovery

Publication rights are revoked on PyPI, not here. Deleting a workflow file or a branch does not revoke anything.

**If the repository, a maintainer account, or a release tag is compromised:**

1. **Revoke first.** Remove the trusted publisher for `legalforecast-mtd` in the PyPI project's publishing settings. That stops any further OIDC exchange immediately. It does not retract a short-lived upload token a run has already obtained, so cancel any in-flight run of the publishing workflow in the same step.
2. **Contain the release.** Yank affected versions on PyPI. Yanking leaves the files resolvable for existing pins while removing them from new resolution; deleting a release is irreversible and does *not* free the version number — PyPI refuses to accept a filename or a version identifier that has ever been uploaded, so a corrected build has to go out under a new version. Prefer yanking unless the artifact must not be retrievable at all.
3. **Assess the artifacts.** `package-artifact-hashes.json` from the corresponding `release-check` run records the hashes of what was built. Compare it against what is on PyPI to establish whether the published bytes are the reviewed bytes.
4. **Recover the repository side.** Rotate the compromised account's credentials, review the environment's protection rules and reviewer list for edits, and audit the workflow file's history for an added trigger, an added secret reference, or a changed action pin.
5. **Re-register deliberately.** Add the trusted publisher back only after the workflow file, environment settings, and action pins have been re-verified against this document. Re-registration is the last step, not the first.

**If only PyPI-side authority needs to move** — for example, transferring the project or changing the release workflow's name — remove the old trusted publisher before adding the new one, so there is never a window in which two distinct workflows can publish.

## Third-party action pinning

Every third-party action in the publishing workflow is pinned to a full 40-character commit SHA, never to a mutable tag. A tag can be repointed by its owner at any commit; a SHA cannot. `tests/test_publish_package_workflow.py` asserts this mechanically for every `uses:` line in the workflow, so an unpinned action cannot land without the test failing.

Because `.github/workflows/**` requires elevated permission to change, pin updates go through the same review path as any other workflow edit.
