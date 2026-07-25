# Acquisition systemd launcher

Acquisition units that inject Infisical secrets must invoke `legalforecast-acquisition-systemd-run`; they must not put `infisical-agent-sandbox run` directly in `ExecStart`.

Some Infisical CLI versions can return zero after a wrapped child failed.
The repository launcher runs the acquisition child behind a private nonce-bound status receipt, records a secret-free launch receipt, and exits with the authenticated child status.
If the sandbox reports success but no valid child receipt exists, the launcher fails closed with status 70.
The launch receipt contains a SHA-256 commitment to the command argument vector, never the arguments or environment themselves, and the private status directory is removed before the launcher exits.

An acquisition transient unit should have this shape:

```bash
systemd-run --user --unit=<unique-unit-name> --property=Type=exec \
  --working-directory="$PWD" \
  uv run legalforecast-acquisition-systemd-run \
  --sandbox-path /agents/sandbox/legalforecastbench-acquisition \
  --receipt-output <durable-launch-receipt.json> \
  -- uv run legalforecast acquisition <subcommand> <frozen-arguments>
```

Use the dedicated `/agents/sandbox/legalforecastbench/parser` or `/agents/sandbox/legalforecastbench/labeling` path for those stages.
These and `/agents/sandbox/legalforecastbench-acquisition` are the launcher's exact dedicated sandbox paths; every root, alias, parent, and unrelated path is rejected before the sandbox helper can run.
The parser stage view must resolve exactly `MISTRAL_API_KEY`; the labeling stage view must resolve exactly `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, and `GEMINI_API_KEY`.
Configure those names as Infisical dependent secret references to the canonical values under `/agents/sandbox/legalforecastbench-acquisition` so credential rotation propagates without creating another stored value.
Reference resolution requires the sandbox identity to read both the stage view and the referenced canonical secret; the reviewed `/agents/sandbox/**` read grant covers both, and must not be broadened to compensate for a broken reference.
Do not copy credential values.
Do not enable folder imports: an import would expose acquisition and unrelated provider credentials to the stage process.
The masked Infisical UI inventory is the authoritative exact-inventory check and must match the stage allowlist before the stage starts.
Then run the defense-in-depth sentinels below from an allowlisted empty caller environment; they inspect zsh parameter-name metadata only and reject every known cross-stage credential without expanding or printing a value:

```bash
env -i PATH="$PATH" HOME="$HOME" USER="$USER" LOGNAME="$LOGNAME" SHELL="$SHELL" TERM="${TERM:-dumb}" \
  infisical-agent-sandbox run --env dev \
  --path /agents/sandbox/legalforecastbench/parser \
  -- zsh -dfc '
    required=(MISTRAL_API_KEY)
    forbidden=(OPENAI_API_KEY ANTHROPIC_API_KEY GEMINI_API_KEY CASE_DEV_API_KEY COURTLISTENER_API_TOKEN RECAP_API_TOKEN FIRECRAWL_API_KEY PACER_USERNAME PACER_PASSWORD)
    for name in $required; do (( ${+parameters[$name]} )) || { print -u2 -- "$name=missing"; exit 1; }; done
    for name in $forbidden; do (( ! ${+parameters[$name]} )) || { print -u2 -- "$name=unexpected"; exit 1; }; done'

env -i PATH="$PATH" HOME="$HOME" USER="$USER" LOGNAME="$LOGNAME" SHELL="$SHELL" TERM="${TERM:-dumb}" \
  infisical-agent-sandbox run --env dev \
  --path /agents/sandbox/legalforecastbench/labeling \
  -- zsh -dfc '
    required=(OPENAI_API_KEY ANTHROPIC_API_KEY GEMINI_API_KEY)
    forbidden=(MISTRAL_API_KEY CASE_DEV_API_KEY COURTLISTENER_API_TOKEN RECAP_API_TOKEN FIRECRAWL_API_KEY PACER_USERNAME PACER_PASSWORD)
    for name in $required; do (( ${+parameters[$name]} )) || { print -u2 -- "$name=missing"; exit 1; }; done
    for name in $forbidden; do (( ! ${+parameters[$name]} )) || { print -u2 -- "$name=unexpected"; exit 1; }; done'
```

The sentinels are not a substitute for the complete masked UI inventory because their forbidden lists are intentionally finite.
Do not broaden an Infisical path to make a unit start.

Downstream launchers must require all of the following before consuming an acquisition output:

- systemd `Result=success` and `ExecMainStatus=0`;
- a `legalforecast.infisical_systemd_launch.v1` receipt with `child_receipt_observed=true`, `sandbox_exit_status=0`, and `effective_exit_status=0`;
- the acquisition command's own completed run card and ordinary artifact reconciliation.

Neither systemd status nor the Infisical wrapper status is sufficient by itself.
Never use `|| true`, `SuccessExitStatus=`, or a follow-up command that overwrites the launcher's status.

The provider-free operational smoke deliberately uses a fake Infisical executable that masks the child status.
It starts one successful user unit and one child that exits 23, verifies `Result=success`/status 0 and `Result=exit-code`/status 23 respectively, emits no secret names or command arguments, and removes the transient unit state:

```bash
uv run scripts/smoke_infisical_systemd_exit_status.py \
  --output tmp/infisical-systemd-smoke-receipt.json
```

This smoke makes zero provider calls and performs no acquisition, purchase, evaluation, freeze, or dispatch action.
