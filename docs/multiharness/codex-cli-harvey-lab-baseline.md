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

The Codex community solver additionally requires a working rootless Podman installation. Verify the prerequisite before preparing a run:

```sh
podman info --format '{{.Host.Security.Rootless}}'
```

The result must be `true`. The operator fails closed when Podman is absent or rootful. It creates an image-free transient root filesystem for each launch, makes that root read-only, uses `--userns=keep-id --cap-drop=ALL`, and checks inside the container that the invoking non-root UID is preserved and the effective, permitted, and bounding capability sets are zero. It binds only `/usr`, `/bin`, `/lib`, and `/lib64` read-only; the exact digest-pinned Codex executable and system CA bundle read-only; the exact prepared solver projection read-only; and the exact solver workspace and Codex authentication root read-write for the trusted parent process. It does not mount the source root, evaluator-private root, run root, judge root, host `/proc`, host `/tmp`, a home directory or authentication-root ancestor, a container socket, or `/dev/fuse`. Mount sources and targets must be absolute, existing, non-symlink paths and are revalidated immediately before process spawn. Podman supplies a distinct procfs, private scratch tmpfs, generated resolver files, and its ordinary rootless network so the trusted parent can reach the subscription service. The nested native Codex permission profile still denies network to model-generated tools unless that profile explicitly grants it; this route does not grant it.

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

The run directory must be fresh. Capability preflight for both binaries runs before any model execution. For Codex, preflight also launches `/bin/true` through the actual shared executor, rootless Podman boundary, and native Codex `sandbox` command using the named workspace-write/auth-deny profile. A missing rootless backend, failed keep-id or zero-capability check, executable identity change, or failed native sandbox launch stops before model use; there is no host-execution fallback. This canary proves that the production launch seam can start, while the synthetic boundary E2E proves the authentication and evaluator-private denials without reading real credentials. Solver deliverables are captured before the judge evaluates them, and a failed or cancelled native turn cannot produce a score. The command prints the harness, task, requested and observed model identities, criterion counts, score, and reported judge token usage. Subscription costs remain null with basis `subscription_unallocable`; a subscription result does not establish zero economic cost or a per-call API price.

Keep raw runtime transcripts, authentication files, and evaluator-private material private. A one-task comparison remains preliminary, and offline tests or successful capability preflight do not establish a live subscription baseline. Publication requires actual solver and judge completion on the pinned task and an inspection of the resulting outputs.

`--timeout-seconds` sets the time limit for the solver and for each judge invocation (default: 900 seconds). The community operator applies this value to its runtime manifest; the example adapter’s 120-second default does not shorten it.
