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

Each role directory must contain only the vendor-created `.credentials.json` file, with no histories, settings, plugins, skills, commands, memory, or project instructions. The runner checks that census and owner-only permissions without reading credential bytes, rejects shared/nested role directories and overlap with benchmark paths, and runs vendor status under the same filesystem boundary. It accepts only a `claude.ai` login whose status names a subscription. It rejects CI and does not accept `ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN` as a fallback.

Record the exact executable identity without reading credentials:

```bash
claude --version
sha256sum "$(command -v claude)"
```

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

The solver and judge use distinct contained execution services, config roots, and working directories. The declared CLI version/digest and required suppression flags (`--setting-sources`, strict MCP configuration, no session persistence, and explicit tools) are checked before subscription status or model execution. The solver sees only the projected task, not the private rubric. Its output is discovered from the same working directory used by the native subprocess, quarantined when unexpected, and sealed before the judge receives the sealed deliverable plus one private criterion at a time. Each judge call receives only its current judge workspace plus its own auth-only config directory. Run output contains the sealed deliverables, private judge attempts, observed usage, and source-grounded evaluation records; it never contains a copied home directory or subscription credential.

No GitHub Actions workflow is supplied for this route because contributor subscription login is deliberately local and interactive. Do not move a durable CLI login into CI secrets or convert this community command into an API gateway workaround. Use the official API-backed benchmark workflows for official benchmark runs.

Any one-task result remains labeled `Preliminary — one task pair, operator-run, not independently reproducible.` until a real local solver and separate judge execution has completed and its artifacts have been inspected.
