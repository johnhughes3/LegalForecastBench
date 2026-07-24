# Claude Code 2.1.218 Host-Specific Native Containment Feasibility

Status: the probe source and tests are branch-local work in progress. No evidence receipt or fixture is present in this branch, and this revision claims no successful capture. The probe must receive independent source review and sudo-gate approval before capture. GitHub issue `#196` remains open.

## Purpose and claim boundary

This work investigates the preliminary community path in issue `#196`: preserve Claude Code's own agent loop, context management, and enumerated local tools inside a disposable whole-process boundary, without substituting a task MCP server and without using `claude --bare`.

The candidate profile is `claude-code-clean-native`. The label means that the probe starts from an isolated configuration and deliberately disables specified stock surfaces; it does not mean literal out-of-the-box behavior.

If the pending capture passes, it will establish only host-specific feasibility on the reviewed machine and systemd configuration. It will not establish contributor portability, a generally safe installation recipe, a benchmark result, a harness effect, satisfaction of issue `#49`, or closure of issue `#196`.

The capture contract uses no benchmark task bytes and makes no provider request. It exercises a synthetic prompt against a loopback-only deterministic stub; it performs no scored solver or evaluator call.

## Exact candidate pin

Issue `#196` records earlier Claude Code observations, but the pending capture targets the exact executable currently selected for review:

| Field | Pinned value |
| --- | --- |
| Executable | `/work/.local/share/claude/versions/2.1.218` |
| Version | `2.1.218 (Claude Code)` |
| Executable SHA-256 | `e12071751a9336b8af1012c103358ff04ac18f9aaff4a738cff7ba5cdfaf63f2` |
| Probe source SHA-256 approved for capture | `69d0ff468995e6efacba3fd1072462572093316a0fa4610eae057241365439d7` |
| Future fixture | `tests/fixtures/claude_native_containment/claude-code-native-containment-2.1.218.json` |
| Model label used by the local stub | `claude-sonnet-4-6` |
| Required provider requests | `0` |
| Required benchmark task bytes | `0` |

There is no fixture directory or fixture at the future path yet. The probe-source row above records the exact independently approved committed source. Version, executable hash, or approved probe-source drift must stop capture before Claude enters the native loop.

## Proposed zero-spend native-loop method

The reviewed Claude Code executable will run in noninteractive `--print` mode against a deterministic Anthropic-compatible server bound only to loopback inside the same private network namespace. The stub scripts native calls for the required capability checks, accepts only the expected structured tool results, and returns a terminal assistant response.

The pending probe is intended to exercise these native tools against synthetic inputs:

| Native tool | Synthetic check |
| --- | --- |
| `Read` | Read the required input. |
| `Glob` | Discover the input by pattern. |
| `Grep` | Find a sentinel in the input. |
| `Bash` | Exercise visibility and network canaries and create a receipt. |
| `Write` | Create a draft deliverable. |
| `Edit` | Replace the draft with the sealed deliverable. |

The first request records Claude Code's advertised native-tool inventory. Any native `Agent` or `Task` entry is recorded as present or absent; this characterization does not launch a subagent.

The synthetic deliverable contract is `/workspace/deliverable.txt`, with exact bytes `FINAL NATIVE_BOUNDARY_OK\n` and SHA-256 `85d05425d3c82e24da44a918148bec75a776609c56f3a2fa0484a0984ee1a100`.

## Whole-process systemd boundary

This host cannot currently establish the intended boundary with its available rootless user-namespace mechanisms. The proposed capture therefore asks the audited sudo-gate service to run the reviewed probe, which in turn asks the system service manager to launch the entire Claude process in one transient unit with a disposable `RootDirectory`.

The outer probe runs through sudo-gate as root only to assemble and attest the boundary. The transient unit runs Claude with systemd `DynamicUser=yes`, assigning a non-root UID and GID distinct from the host `johnhughes` identity. A separate short-lived `johnhughes` process remains outside the unit solely as a `/proc` isolation canary. The requested unit uses a private network namespace, removes capabilities, denies privilege gain, restricts kernel and namespace surfaces, and exposes only the operating-system paths needed by the executable plus writable disposable home, temporary, and workspace paths. Requested systemd properties are not accepted as proof by themselves: the emitted receipt must verify the dynamic process identity, `NoNewPrivileges`, zero capability masks, service cgroup, read-only operating-system binds, root and network boundary facts, and absence of namespace fallback in the unit journal.

The proposed canaries cover projected evaluator-private bytes, host home and repository visibility, external network reachability, ambient agents, project instructions, settings, hooks, MCP configuration, and skills. A separate exact-content and SHA-256 assertion seals the output. The private-sentinel receipt records that the exact outer host path was checked and was not visible from the inner process without disclosing that path. A missing, unexpected, or positive canary result must fail closed.

This is a whole-process boundary, not a claim that Claude Code's application-level settings alone provide containment.

Claude runs with the single permission mechanism `--dangerously-skip-permissions` so the deterministic native-tool sequence can proceed noninteractively. The probe does not also pass `--permission-mode bypassPermissions`. The permission flag provides no containment: the reviewed transient systemd unit and disposable root are the outer safety boundary.

## Administrative-settings caveat

Claude Code may support administrator-managed or enterprise policy settings that ordinary project and user configuration cannot override. The proposed probe plants synthetic project and user customizations inside its disposable root and checks that they remain inactive. It does not characterize every administrator-managed settings mechanism on every installation.

The host-specific feasibility claim therefore depends on the reviewed `RootDirectory` projection excluding unreviewed host policy files. A contributor installation with different managed settings, service-manager behavior, filesystem projections, or namespace permissions requires a new review and capture; this receipt cannot be treated as portable authority.

## Deliberately disabled surfaces

The candidate treatment disables and records selected stock surfaces, including Chrome integration, web tools, ambient agents, hooks, MCP servers, project instructions, settings, skills, and slash commands. These controls are part of the treatment identity.

Ambient plugins remain an explicitly unverified safe-mode surface. The earlier draft plugin layout was not a valid installed-plugin negative control, so a successful capture must record `unverified_safe_mode_surfaces: ["ambient plugins"]` rather than claim that plugins were disabled or contained.

The profile uses no task MCP server and does not use `--bare`. Replacing Claude's native tools with task MCP tools, enabling a disabled surface, or changing the whole-process boundary defines a different treatment and requires separate evidence.

## Pre-capture review

An independent reviewer must inspect committed, clean probe and test bytes, verify the executable independently, and record the final probe-source SHA-256 before anyone requests privileged capture:

```bash
test -z "$(git status --porcelain=v1 -- \
  scripts/probe_claude_code_native_containment.py \
  tests/test_claude_code_native_containment.py)" || {
  echo "probe and test paths must be committed and clean before review" >&2
  exit 1
}
git diff origin/main...HEAD -- \
  scripts/probe_claude_code_native_containment.py \
  tests/test_claude_code_native_containment.py
sha256sum scripts/probe_claude_code_native_containment.py
sha256sum /work/.local/share/claude/versions/2.1.218
/work/.local/share/claude/versions/2.1.218 --version
```

The expected executable observations are the version and hash in the pin table above. The source hash was recorded only after the implementation bytes were committed, frozen, and independently approved. The operator preflight, sudo-gate staged-file attestation, inner staged/copy equality check, and post-capture `probe.source_sha256` must all match the approved digest.

After that review and table update, request the exact whole-process capture from the repository root. The command relies on the reviewed probe's pinned default executable path, so the 273 MB Claude binary is not an argv file token that sudo-gate would stage. Outer mode has no `--output` option: it emits one JSON document on stdout. `sudo-request` relays command stdout separately while approval status, URLs, command stderr, and client errors remain on stderr, so redirect stdout only and never use `2>&1`.

The first request attempt on 2026-07-24 was rejected before approval or execution with HTTP 413 because the reviewed 79,441-byte probe exceeded sudo-gate's configured per-file attachment cap. It produced no evidence. Do not bypass staged-file attestation with ordinary sudo or an unreviewed loader. A future capture requires either a separately reviewed sudo-gate capacity change or a source-transport refactor whose complete staged bytes, reconstruction, and final source hash receive a new independent review.

```bash
set -euo pipefail
umask 077

probe_path="$(realpath scripts/probe_claude_code_native_containment.py)"
approved_probe_sha256="69d0ff468995e6efacba3fd1072462572093316a0fa4610eae057241365439d7"
[[ "${approved_probe_sha256}" =~ ^[0-9a-f]{64}$ ]] || {
  echo "capture forbidden: insert the independently approved probe SHA-256" >&2
  exit 1
}
observed_probe_sha256="$(sha256sum -- "${probe_path}" | cut -d' ' -f1)"
[[ "${observed_probe_sha256}" == "${approved_probe_sha256}" ]] || {
  echo "capture forbidden: probe source hash drift" >&2
  exit 1
}

capture_path="$(
  mktemp --tmpdir=/tmp --suffix=.json \
    claude-code-native-containment-2.1.218.XXXXXX
)"
chmod 0600 "${capture_path}"
if ! sudo-request \
  --reason "LegalForecastBench issue #196: capture reviewed zero-provider-spend Claude 2.1.218 whole-process containment evidence" \
  -- /usr/bin/python3 "${probe_path}" >"${capture_path}"; then
  rm -f -- "${capture_path}"
  exit 1
fi

uv run python -m json.tool "${capture_path}" >/dev/null
uv run python - "${capture_path}" "${approved_probe_sha256}" <<'PY'
import json
import sys
from pathlib import Path

evidence = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
probe = evidence.get("probe")
if not isinstance(probe, dict) or probe.get("source_sha256") != sys.argv[2]:
    raise SystemExit("captured probe source hash differs from approved digest")
PY
printf 'Unreviewed capture: %s\n' "${capture_path}"
```

Do not run this command before approval, do not substitute ordinary `sudo`, do not add `--claude-binary` to the sudo-gate argv, and do not replace the fresh `mktemp` path with a predictable filename. Sudo-gate will attest and stage the reviewed probe source; the probe must independently verify its pinned default executable before copying it into the disposable root. The printed path still contains unreviewed evidence and is not a passing fixture.

## Post-capture review

The first capture remains outside the repository until an independent reviewer verifies the exact binary identity, approved probe-source identity, whole-process boundary attestation, dynamic process identity and cgroup facts, native-tool receipt, canary set, sealed deliverable, zero provider requests, and zero benchmark task bytes. Review happens before creating the future fixture directory or copying any receipt into the repository.

Only after that independent approval may the reviewer create `tests/fixtures/claude_native_containment/`, copy the exact approved receipt to the future fixture path, and run the fixture-backed test suite. Until the approved receipt exists at that path, fixture-required tests correctly skip and no passing evidence is claimed.

```bash
uv run pytest -q tests/test_claude_code_native_containment.py
```

A later cross-capture replay is a separate gate. It is allowed only after an approved fixture exists and only after the probe and tests define an explicitly reviewed stable projection for every intentionally run-specific field. Do not use the environment-variable replay or claim semantic equivalence while that projection is absent or incomplete. Any eventual projection must enumerate the permitted differences; it is not permission to ignore other drift.

Only an independently reviewed receipt that satisfies the full contract may be copied to `tests/fixtures/claude_native_containment/claude-code-native-containment-2.1.218.json`. Until then, the fixture is absent, the candidate is not passing evidence, and issue `#196` remains open.
