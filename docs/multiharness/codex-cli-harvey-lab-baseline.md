# Codex CLI community baseline on Harvey LAB

The community route runs the native Codex CLI solver through the contributor's ChatGPT subscription and a separate native Claude Code judge through a Claude subscription. It reuses the same pinned task projection, deliverable capture, per-criterion evaluation, and judge implementation as the [Claude Code community baseline](claude-code-harvey-lab-baseline.md). This is a local community measurement; the official API benchmark and the upstream `harvey-lab run` API experiment are separate commands.

Prepare the pinned Harvey LAB v1.1.0 source, solver projection, evaluator-private material, and evaluator wrapper using the commands in the Claude baseline guide. Use the identical prepared task and requested Claude judge family for a comparison. When the solvers use different foundation models, their scores compare complete model-and-harness systems and cannot isolate the effect of the harness. A native model family alias may resolve to a newer deployment; record both the requested identity and the actual model when the runtime reports it, and leave an unreported actual identity unknown.

Create separate, owner-only role configuration roots outside every source, projection, evaluator-private, run, and executable directory. Authenticate each role with the vendor's supported login command; do not copy existing credentials, settings, histories, or plugin state:

```sh
install -d -m 700 "$PWD/community-auth/codex-solver" "$PWD/community-auth/claude-judge"
CODEX_HOME="$PWD/community-auth/codex-solver" codex login
CLAUDE_CONFIG_DIR="$PWD/community-auth/claude-judge" claude auth login
```

The Codex solver root contains its owner-only `auth.json` and may retain the native login state `log/codex-login.log` and `tmp/arg0-linux` helper state. Native `codex-arg0XXXXXX` directories may contain a regular `.lock` and the three vendor helper aliases (`applypatch`, `apply_patch`, and `codex-linux-sandbox`) only when each links directly to the explicitly pinned, digest-verified Codex executable. Other settings, history, plugins, temporary contents, and symlinks are rejected. The Claude judge root contains its owner-only `.credentials.json` and may retain the vendor-generated state described in the [Claude baseline guide](claude-code-harvey-lab-baseline.md); do not delete supported vendor state created by login or status. Both vendor status commands must confirm subscription authentication. The runtime launches each role with an isolated home and only its own authentication root. API keys are not projected. Codex uses an inline named native filesystem-permission profile: the role workspace is writable, the minimal runtime paths are readable, and the absolute `CODEX_HOME` is denied to model-generated tools. The parent Codex process retains `CODEX_HOME` for authentication. User configuration and execution rules remain suppressed, approval is noninteractive, and session persistence is disabled; the route never selects `danger-full-access`. The Claude judge has no tools and cannot read the solver login.

Choose and record the exact installed binary versions and SHA-256 values. Both are required explicitly; the command does not silently update the checked-in example pins. Inspect compatibility without login or model calls:

```sh
codex --version
sha256sum "$(command -v codex)"
claude --version
sha256sum "$(command -v claude)"
uv run python -m legalforecast.multiharness.native_cli_preflight \
  --cli codex --version 'EXACT CODEX VERSION' --sha256 CODEX_SHA256
uv run python -m legalforecast.multiharness.native_cli_preflight \
  --cli claude --version 'EXACT CLAUDE VERSION' --sha256 CLAUDE_SHA256
```

Run the prepared task with an explicit Codex model, reasoning effort, and Claude judge family:

```sh
uv run legalforecast harvey-lab run-community-subscription \
  --harness codex \
  --source-root harvey-labs \
  --projection-dir run-input/projected \
  --evaluator-private-dir run-input/evaluator-private \
  --run-dir run-output/codex-harvey-lab \
  --evaluator-bin-dir run-input/bin \
  --solver-config-dir "$PWD/community-auth/codex-solver" \
  --judge-config-dir "$PWD/community-auth/claude-judge" \
  --codex-version 'EXACT CODEX VERSION' --codex-sha256 CODEX_SHA256 \
  --claude-version 'EXACT CLAUDE VERSION' --claude-sha256 CLAUDE_SHA256 \
  --solver-model CODEX_MODEL --reasoning-effort medium --judge-model sonnet
```

The run directory must be fresh. Capability preflight for both binaries runs before any model execution. Codex's native filesystem sandbox must also be usable on the contributor host; a configuration preflight or passing offline test does not prove that native tool commands can start or that the authentication-root denial is enforced on that host. Solver deliverables are captured before the judge evaluates them, and a failed or cancelled native turn cannot produce a score. The command prints the harness, task, requested and observed model identities, criterion counts, score, and reported judge token usage. Subscription costs remain null with basis `subscription_unallocable`; a subscription result does not establish zero economic cost or a per-call API price.

Keep raw runtime transcripts, authentication files, and evaluator-private material private. A one-task comparison remains preliminary, and offline tests or successful capability preflight do not establish a live subscription baseline. Publication requires actual solver and judge completion on the pinned task and an inspection of the resulting outputs.

`--timeout-seconds` sets the time limit for the solver and for each judge invocation (default: 900 seconds). The community operator applies this value to its runtime manifest; the example adapter’s 120-second default does not shorten it.
