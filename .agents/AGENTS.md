# Agent Instructions

## What This Project Is

LegalForecastBench is an academic, open-source benchmark, released under the Apache License 2.0. It measures how well AI models handle one legal reasoning task: forecasting the outcome of a federal motion to dismiss from the written record the judge received. Each cycle scores models against a small, fixed corpus of public federal court records — 100 cases for Cycle 1. That corpus exists solely to evaluate models; it is not used to train, fine-tune, or build them.

## Standard of Rigor

This is academic research, not a financial institution or a crypto ledger. We want records that are rigorous, transparent, and reproducible — a reader can see what we did and redo it. They do not need to be cryptographically provable; readers may reasonably trust that we have not falsified our own data. Prefer a count, a census, or a test over a digest, a seal, or an attestation.

Before building any artifact that only humans and status reports read — a certificate, ledger, receipt, matrix, meta-report, readiness check, or approval chain — name its consumer, the capability it gates, the defect that actually happened to justify it, and when it gets deleted. If you cannot name all four, do not build it. Writing code just so that something "branches on it" does not change the answer.

After you finish planning and filing beads, check what you added against this section — and against the `just-say-no-to-process-porn-and-ceremony` skill if your harness provides it. Delete what fails. Nothing in this file authorizes machinery the plan did not need.

Where an older document in this tree still calls for attestations, sealed deliverables, receipt cards, hashed approval scopes, or evidence tiers, this section supersedes it.

## Priority: the new corpus path (2026-08-30 replan)

**Cycle 1 cannot publish until its corpus is complete** — the 2026-08-30 census found 61 filed oppositions missing from the 100 cases. The owner's replan finishes Cycle 1 *after* the cutover to the new corpus factory rather than on the legacy machinery: new pipeline and corpus repair (`ti2q`, `iot9`) → cutover and deletion of the old runtime (`v7zs`) → run and publish Cycle 1 through the new path. The deletion half of that cutover landed in #1034: the legacy corpus runtime, acquisition, and labeling surfaces are gone from this repository and now live in the companion private corpus repository. What remains open under `v7zs` is the semantic public-boundary fencing (`xvg1`). Prefer the smallest change that gets a correct result over new process, ceremony, or speculative hardening. Concretely:

- **Anything that spends money follows the Spending guardrails below** — a ceiling, an approval above the threshold, and a journal. That is the entire spend process; do not add authority chains or approval grammars on top of it.
- Everything else (code, validation, parsing, execution under an existing approval, evidence assembly): **do what needs to be done, promptly**. Halt-and-escalate is for genuine blockers (missing owner approval, failed validation), not for perfectible process.
- Before building anything, run the executability audit: name the command that produces every input your work requires and the path where it exists today. If one doesn't exist, building or escalating THAT is your first task.
- Integrity controls are not negotiable and are not the slowdown. They are exactly these: model contamination and release-anchor rules; outcome-leakage blinding; the Spending guardrails below; public-repo hygiene; and the one locked benchmark-run manifest. Anything not on this list is process, and the Standard of Rigor applies to it.

This project uses **bd** (beads) for issue tracking. Run `bd prime` for full workflow context.

> **Architecture in one line:** Issues live in a centrally configured beads-db Dolt SQL server. The server is the durable source of truth, so no `bd dolt push/pull` is needed. Connection details come from generated local metadata. `.beads/issues.jsonl` is a passive export, not the wire protocol.
>
> See [SYNC_CONCEPTS.md](https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md) for the one-screen overview and anti-patterns (don't treat JSONL as the source of truth; don't `bd import` during normal operation; don't reach for third-party Dolt hosting before trying the default).

## Corpus Spending Boundary

Provider purchases and budget consent for corpus construction belong to the private LegalForecastCorpus repository. LegalForecastBench does not ship purchase or budget commands; it consumes an issued immutable, outcome-blinded release and retains the public evaluation, scoring, reporting, publication, and withdrawal boundaries.

## Documentation placement

Keep public-facing documentation under `docs/`: explain the benchmark, reproduction, public contracts, and how outsiders can contribute. Save private/internal operating instructions, deployment procedures, credential setup, and corpus administration in the private LegalForecastCorpus repository. Delete obsolete plans rather than archiving them in this repository. Keep the root README concise; the CLAUDE.md symlink points to these contributor instructions.

## Public Repository Hygiene

This repository is public and open source. Do not commit machine- or user-specific operational details, including hostnames, private network names or addresses, Tailscale node identifiers, email addresses, local filesystem paths, account identifiers, or credentials. Use generic placeholders, environment variables, or generated local metadata instead.

## Infisical Paths

All LegalForecastBench Infisical paths are stage-specific subdirectories of `/agents/sandbox/legalforecastbench/`; do not add or use sibling aliases outside that namespace.

## AWS Accounts And Credentials

Two AWS accounts matter here, and confusing them wastes hours. Resolve the numeric ids locally from `~/.aws/config`; never commit them to this public repo.

- **Artifacts account** — owns everything this benchmark touches: the results and packet buckets, the artifacts KMS key, the `official-eval` OIDC roles, and the provider-authority operator role. The only configured human profile is `cos.benchmark.artifacts` (SSO role `CosBenchmarkArtifactOps`), and since the 2026-08-30 bootstrap lockdown it is **read-only, for verification**: the buckets and their KMS key carry resource policies naming only the OIDC roles, so every write — staging included — goes through an Actions workflow under OIDC, and **local staging is closed**. An identity policy cannot override a resource policy, so a `PutObject` denial here is not a missing grant to go find; it is the boundary working. There is no admin profile for this account.
- **Org management account** — `cos.admin.breakglass` is AdministratorAccess *there*, not here. It cannot read or write this project's buckets. **An `AccessDenied` under break-glass means wrong account, not a resource policy.** Admin in the artifacts account is reachable only by assuming its `OrganizationAccountAccessRole` cross-account from break-glass, and that is reserved for one-time bootstrap operations.

Use GitHub Actions for anything that writes official release storage; there is no local alternative. Paid provider cells run under OIDC through `run-benchmark.yaml`, and publication fan-in runs under `fan-in-publish.yaml`; the companion LegalForecastCorpus repository supplies immutable outcome-blinded release inputs. Creating or repolicying an IAM role is **not** something the routine OIDC operator can do — it holds read-only refresh verbs on exact role ARNs, so new roles are a one-time human-admin bootstrap apply per `infra/official-eval-bootstrap/README.md`.

GitHub auth goes through the secure-gate broker: ordinary `git push` and `gh workflow run` work with routine short-lived tokens. Secret and variable writes are human-approved server-side applies (`secure-gate-elevate set-variable --environment ...`); the machine never receives a write token.

## Scope Decisions

This benchmark is intentionally **not** adopting:

- Preregistration protocols
- Result-tier classification (official / verified-community / community-unverified / alpha-non-canonical)

Legacy references to those concepts have been removed from the supported tree; do not add new dependencies on them.

The owner selected training-cutoff eligibility before benchmark runs. Documentation aligned September 9, 2026: an eligible official comparison requires the documented training-data cutoff to strictly predate every scored decision; public release date is provenance, not the eligibility test. Unknown or overlapping cutoffs remain qualified. Preserve historical pre-/post-anchor fields and immutable artifacts; the existing release-arm reporting code needs alignment before automated publication claims this policy. Follow `docs/METHODS.md` and `docs/publication-governance.md`. Do not infer contamination from raw score differences across different cohorts or treat nonsignificance as proof of no contamination.

Report both micro-Brier and equal-case Brier, retaining the methods' micro headline and case-weighted sensitivity. Report actual/reconstructed costs and standard-rate repricing with coverage and missing usage disclosed.

Private corpus acquisition and unitization belong to the companion LegalForecastCorpus repository and are not shipped in this public package. This repository consumes locked outcome-blinded manifests and releases, retains public evaluation and publication paths, and keeps withdrawal handling for sealed or redacted cases.

## Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work atomically
bd close <id>         # Complete work
```

## Resuming benchmark runs

Use `uv run legalforecast run resume --github-run RUN_ID --ref main --max-parallel 8` to inspect a failed benchmark run. Add `--execute` to request protected recovery and dispatch. The command reconstructs the original inputs and budget identity from saved artifacts, preserves completed predictions, and uses current main for repaired execution code. Local planning needs only brokered GitHub access; AWS settlement and retry reservations run in the protected workflow. A ready local plan does not establish available provider credit or sufficient remaining AWS spend authority. Inspect the protected recovery result before claiming a resumed run has started; never release uncertain charges or increase the approved ceiling to force a retry.

Recovery preparation restores and validates completed cells before building the worker matrix, so only unfinished cases launch workers. The combined result includes carried and new receipts and available transcripts; the full original case census still determines completeness. Restored cell ledgers are retained for further recovery.

The native benchmark runner always uses the managed document-tool agent; it has no direct-prompt fallback. Unsupported provider/tool configurations fail before spend. Invalid or defaulted predictions fail the case and cannot be restored as completed results. When the execution setup itself was wrong, preserve the historical charges and use a corrected registry snapshot for a new experiment instead of resuming the old outputs.

## Testing

The supported full-suite command, locally and in CI, runs four pytest-xdist workers grouped by module:

```bash
uv run pytest -q -n 4 --dist=loadscope
```

For focused runs while iterating, plain serial `uv run pytest tests/<file> -q` is fine. Keep new tests parallel-safe: per-test `tmp_path` for all files and SQLite databases, `monkeypatch` for environment and cwd, ephemeral ports (`bind` to port 0), and no cross-test shared state. Do not call `os.fork()` in tests — xdist workers are multi-threaded; use a subprocess.

## Cycle 1 Change Control

Keep one active gate-changing integration lane, run focused tests before the full suite, and use the correctness/security emergency path when a gate is genuinely wrong. The old Cycle 1 change-control record and its frozen-byte-contract regime are retired; the new path has one locked run manifest and no per-document digests. Do not mint new schema versions, sidecars, or card variants to preserve byte-identical fields.

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
