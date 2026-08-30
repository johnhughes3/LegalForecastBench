# Agent Instructions

## What This Project Is

LegalForecastBench is an academic, open-source benchmark, released under the Apache License 2.0. It measures how well AI models handle one legal reasoning task: forecasting the outcome of a federal motion to dismiss from the written record the judge received. Each cycle scores models against a small, fixed corpus of public federal court records — 100 cases for Cycle 1. That corpus exists solely to evaluate models; it is not used to train, fine-tune, or build them.

## Standard of Rigor

This is academic research, not a financial institution or a crypto ledger. We want records that are rigorous, transparent, and reproducible — a reader can see what we did and redo it. They do not need to be cryptographically provable; readers may reasonably trust that we have not falsified our own data. Prefer a count, a census, or a test over a digest, a seal, or an attestation.

Before building any artifact that only humans and status reports read — a certificate, ledger, receipt, matrix, meta-report, readiness check, or approval chain — name its consumer, the capability it gates, the defect that actually happened to justify it, and when it gets deleted. If you cannot name all four, do not build it. Writing code just so that something "branches on it" does not change the answer.

After you finish planning and filing beads, re-read `/just-say-no-to-process-porn-and-ceremony` and check what you added against it. Delete what fails. Nothing in this file authorizes machinery the plan did not need.

## Priority: the new corpus path (2026-08-30 replan)

**Cycle 1 cannot publish until its corpus is complete** — the 2026-08-30 census found 61 filed oppositions missing from the 100 cases. The owner's replan finishes Cycle 1 *after* the cutover to the new corpus factory rather than on the legacy machinery: new pipeline and corpus repair (`ti2q`, `iot9`) → cutover and deletion of the old runtime (`v7zs`) → run and publish Cycle 1 through the new path. Prefer the smallest change that gets a correct result over new process, ceremony, or speculative hardening. Concretely:

- **PACER/document purchases require the owner's approval with the approximate dollar amount** — state the amount, get the approval, journal the spend, respect the stated ceiling. That is the entire required purchase process; do not add authority chains or approval machinery beyond it.
- Everything else (code, validation, parsing, execution under an existing approval, evidence assembly): **do what needs to be done, promptly**. Halt-and-escalate is for genuine blockers (missing owner approval, failed validation), not for perfectible process.
- Before building anything, run the executability audit: name the command that produces every input your work requires and the path where it exists today. If one doesn't exist, building or escalating THAT is your first task.
- Integrity controls are not negotiable and are not the slowdown. They are exactly these: model contamination and release-anchor rules; outcome-leakage blinding; owner approval with the dollar amount before any purchase or paid run; public-repo hygiene; and the one locked benchmark-run manifest. Anything not on this list is process, and the Standard of Rigor applies to it.

This project uses **bd** (beads) for issue tracking. Run `bd prime` for full workflow context.

> **Architecture in one line:** Issues live in a centrally configured beads-db Dolt SQL server. The server is the durable source of truth, so no `bd dolt push/pull` is needed. Connection details come from generated local metadata. `.beads/issues.jsonl` is a passive export, not the wire protocol.
>
> See [SYNC_CONCEPTS.md](https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md) for the one-screen overview and anti-patterns (don't treat JSONL as the source of truth; don't `bd import` during normal operation; don't reach for third-party Dolt hosting before trying the default).

## Public Repository Hygiene

This repository is public and open source. Do not commit machine- or user-specific operational details, including hostnames, private network names or addresses, Tailscale node identifiers, email addresses, local filesystem paths, account identifiers, or credentials. Use generic placeholders, environment variables, or generated local metadata instead.

## Infisical Paths

All LegalForecastBench Infisical paths are stage-specific subdirectories of `/agents/sandbox/legalforecastbench/`; do not add or use sibling aliases outside that namespace.

## AWS Accounts And Credentials

Two AWS accounts matter here, and confusing them wastes hours. Resolve the numeric ids locally from `~/.aws/config`; never commit them to this public repo.

- **Artifacts account** — owns everything this benchmark touches: the results and packet buckets, the artifacts KMS key, the `official-eval` OIDC roles, and the provider-authority operator role. The only configured human profile is `cos.benchmark.artifacts` (SSO role `CosBenchmarkArtifactOps`). It can read and write the manifest-run and model-packet prefixes, which is what local staging and scope upload use. There is no admin profile for this account.
- **Org management account** — `cos.admin.breakglass` is AdministratorAccess *there*, not here. It cannot read or write this project's buckets. **An `AccessDenied` under break-glass means wrong account, not a resource policy.** Admin in the artifacts account is reachable only by assuming its `OrganizationAccountAccessRole` cross-account from break-glass, and that is reserved for one-time bootstrap operations.

Prefer GitHub Actions over local credentials for anything that writes S3. Paid provider cells and fan-in already run under OIDC; manifest-run staging has its own OIDC role and workflow (`stage-manifest-run.yaml`). Creating or repolicying an IAM role is **not** something the routine OIDC operator can do — it holds read-only refresh verbs on exact role ARNs, so new roles are a one-time human-admin bootstrap apply per `infra/official-eval-bootstrap/README.md`.

GitHub auth goes through the secure-gate broker: ordinary `git push` and `gh workflow run` work with routine short-lived tokens. Secret and variable writes are human-approved server-side applies (`secure-gate-elevate set-variable --environment ...`); the machine never receives a write token.

## Scope Decisions

This benchmark is intentionally **not** adopting:

- Preregistration protocols
- Result-tier classification (official / verified-community / community-unverified / alpha-non-canonical)

Legacy references to those concepts have been removed from the supported tree; do not add new dependencies on them.

One narrow carve-out, per the owner directive of 2026-08-29 (bead `legalforecastbench-38gh`): results carry a two-value classification, `official` or `supplementary_post_anchor`, derived mechanically from a model's `release_timestamp` against the cycle's corpus anchor. It exists so a model released after the corpus decision window can run through the same pipeline and publish beside the official four with a dagger marker and a caveat, without ever entering the official set. The dagger is distinct from the contamination-tier asterisk, which marks official models whose training cutoff is undisclosed. It is a presentation flag plus one fail-closed gate (`legalforecast/reporting/result_class.py`), not the four-tier scheme above, which stays unadopted.

The **acquisition** and **withdrawal** code paths are kept — acquisition is core pipeline, withdrawal handles sealed/redacted cases.

## Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work atomically
bd close <id>         # Complete work
```

## Testing

The supported full-suite command, locally and in CI, runs four pytest-xdist workers grouped by module:

```bash
uv run pytest -q -n 4 --dist=loadscope
```

For focused runs while iterating, plain serial `uv run pytest tests/<file> -q` is fine. Keep new tests parallel-safe: per-test `tmp_path` for all files and SQLite databases, `monkeypatch` for environment and cwd, ephemeral ports (`bind` to port 0), and no cross-test shared state. Do not call `os.fork()` in tests — xdist workers are multi-threaded; use a subprocess.

## Cycle 1 Change Control

[docs/cycle-1-change-control.md](/docs/cycle-1-change-control.md) still governs the *cadence* of gate-changing work on the legacy chain: one active gate-changing integration lane, focused-before-full test ordering, and the correctness/security emergency path. Its frozen-byte-contract regime is superseded by the 2026-08-30 replan — the new path has one locked run manifest and no per-document digests, so do not mint new schema versions, sidecars, or card variants to preserve byte-identical fields in code that `v7zs` is chartered to delete.

## Non-Interactive Shell Commands

**ALWAYS use non-interactive flags** with file operations to avoid hanging on confirmation prompts.

Shell commands like `cp`, `mv`, and `rm` may be aliased to include `-i` (interactive) mode on some systems, causing the agent to hang indefinitely waiting for y/n input.

**Use these forms instead:**
```bash
# Force overwrite without prompting
cp -f source dest           # NOT: cp source dest
mv -f source dest           # NOT: mv source dest
rm -f file                  # NOT: rm file

# For recursive operations
rm -rf directory            # NOT: rm -r directory
cp -rf source dest          # NOT: cp -r source dest
```

**Other commands that may prompt:**
- `scp` - use `-o BatchMode=yes` for non-interactive
- `ssh` - use `-o BatchMode=yes` to fail instead of prompting
- `apt-get` - use `-y` flag
- `brew` - use `HOMEBREW_NO_AUTO_UPDATE=1` env var

<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:7510c1e2 -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

**Architecture in one line:** issues live in a centrally configured beads-db Dolt SQL server (server mode; no Dolt push remote); connection details come from generated local metadata, and `.beads/issues.jsonl` is a passive export. See https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md for details and anti-patterns.

## Session Completion

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds
<!-- END BEADS INTEGRATION -->
