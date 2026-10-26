# Claude Code clean-native Harvey LAB community baseline

This is a community baseline, not an official LegalForecastBench run. Official benchmark models use the API-backed benchmark workflows. This route instead uses a contributor's existing Claude subscription through the vendor-supported native Claude Code CLI for both the solver and the separate judge. It does not use an API key, paid gateway descriptor, hosted spend authority, or DynamoDB journal.

Subscription charges cannot be allocated per call. Results therefore record cost as `subscription_unallocable` with a null amount, never as `$0`. They retain token counts only when the CLI reports them.

## Prepare the outcome-blinded inputs

Clone the public upstream source and check out the recorded v1.1.0 commit:

```bash
git clone https://github.com/harveyai/harvey-labs.git harvey-labs
git -C harvey-labs checkout --detach 1dd81403b2fbb60596f7aea3fcecafad7bf73143
uv run legalforecast harvey-lab prepare-clean-native \
  --source-root harvey-labs \
  --output-dir run-input/projected \
  --evaluator-private-dir run-input/evaluator-private
mkdir -p run-input/bin
uv run legalforecast multiharness tier0 install-evaluator-wrapper \
  --bin-dir run-input/bin \
  --scratch-root run-input/wrapper-scratch \
  --output run-input/wrapper-install.json
```

The prepare command verifies the clean upstream commit and tree, selects only `employment-labor/identify-issues-in-counterparty-motion-brief`, and separates solver-visible files from the private rubric. It performs no model or evaluator request. Keep both prepared directories private until evaluation finishes.

## Log in with the vendor CLI

Install Claude Code through a supported vendor distribution, then prepare two fresh, owner-only config directories and use the vendor's normal interactive login once for each role. Do not copy an existing `~/.claude` directory or credential file:

```bash
install -d -m 700 "$PWD/run-auth/solver" "$PWD/run-auth/judge"
CLAUDE_CONFIG_DIR="$PWD/run-auth/solver" claude auth login
CLAUDE_CONFIG_DIR="$PWD/run-auth/judge" claude auth login
```

Each role directory must contain the vendor-created `.credentials.json` file. The CLI also creates `.claude.json`, its empty lock directory, and timestamped state files under `backups/`; these vendor state files are allowed. Histories, settings, plugins, skills, commands, memory, and project instructions remain excluded. The runner checks that census and owner-only permissions without reading credential bytes, rejects shared/nested role directories and overlap with benchmark paths, and runs vendor status under the same filesystem boundary. It accepts only a `claude.ai` login whose status names a subscription. It rejects CI and does not accept `ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN` as a fallback.

Record the exact executable identity without reading credentials:

```bash
claude --version
sha256sum "$(command -v claude)"
```

The same isolated role roots can be reused after a run. The validator permits native `.last-cleanup`, failed-event JSON files in `telemetry/`, empty `sessions/` and `shell-snapshots/` directories, empty UUID-named directories under `session-env/`, and model catalog JSON caches named `UUID-12hex-cc.json` under `cache/model-catalog/`, alongside login state. Keep this vendor bookkeeping; settings, histories, plugins, extra cache directories, and symlinks remain rejected.

## Run the local community baseline

Use the exact version string and unprefixed digest observed above. Model family aliases such as `sonnet` are allowed because the native CLI supports them; requested aliases and observed model identities are reported separately. If the CLI does not report an actual model identity, the result says it was unreported rather than asserting an exact judge model.

```bash
uv run legalforecast harvey-lab run-community-subscription \
  --source-root harvey-labs \
  --projection-dir run-input/projected \
  --evaluator-private-dir run-input/evaluator-private \
  --run-dir run-output/claude-code-harvey-lab \
  --evaluator-bin-dir run-input/bin \
  --solver-config-dir "$PWD/run-auth/solver" \
  --judge-config-dir "$PWD/run-auth/judge" \
  --claude-version '2.x.y (Claude Code)' \
  --claude-sha256 '<sha256>' \
  --solver-model sonnet \
  --judge-model sonnet
```

The solver and judge use distinct contained execution services, config roots, and working directories. The declared CLI version/digest and required suppression flags (`--safe-mode`, `--setting-sources`, strict MCP configuration, no session persistence, explicit tools, and the owned inline `--settings` object) are checked before subscription status or model execution. The Claude solver currently requires exact `claude --version` output `2.1.310 (Claude Code)`, the reviewed version for the `claude_native_sandbox.v1` policy; advertising `--settings` in help is not treated as proof that nested sandbox keys are enforced. Safe mode disables host instructions, skills, plugins, hooks, output styles, workflows, and auto-memory while preserving the selected role's subscription login and the explicitly declared built-in tools and permissions. The solver settings require Claude's native Bash sandbox, fail when that sandbox is unavailable, disable unsandboxed retries, declare no excluded commands, and deny both reads and writes to the solver authentication root. Matching `Read` and `Edit` deny rules cover Claude's built-in file tools, which run outside the Bash sandbox; because those rules use vendor gitignore-pattern syntax, authentication-root paths containing pattern or rule-delimiter characters are rejected before a run specification is built. The parent Claude process still retains the role root it needs for authentication. The solver sees only the projected task, not the private rubric. Its output is discovered from the same working directory used by the native subprocess, quarantined when unexpected, and sealed before the judge receives the sealed deliverable plus one private criterion at a time. Each judge call receives only its current judge workspace plus its own isolated vendor config directory. Run output contains the sealed deliverables, private judge attempts, observed usage, and source-grounded evaluation records; it never contains a copied home directory or subscription credential.

No GitHub Actions workflow is supplied for this route because contributor subscription login is deliberately local and interactive. Do not move a durable CLI login into CI secrets or convert this community command into an API gateway workaround. Use the official API-backed benchmark workflows for official benchmark runs.

Any one-task result remains labeled `Preliminary — one task pair, operator-run, not independently reproducible.` until a real local solver and separate judge execution has completed and its artifacts have been inspected.

The matching [Codex subscription baseline](codex-cli-harvey-lab-baseline.md) selects `--harness codex` on the same community command and uses the same separate Claude subscription judge. Keep the prepared task and requested judge family identical when comparing these two native solvers.

`--timeout-seconds` sets the time limit for the solver and for each judge invocation (default: 900 seconds). The community operator applies this value to its runtime manifest; the example adapter’s 120-second default does not shorten it.
