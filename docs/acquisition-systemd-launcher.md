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
  /usr/bin/env -i PATH="$PATH" HOME="$HOME" USER="$USER" LOGNAME="$LOGNAME" SHELL="$SHELL" TERM="${TERM:-dumb}" \
  uv run legalforecast-acquisition-systemd-run \
  --sandbox-path /agents/sandbox/legalforecastbench-acquisition \
  --receipt-output <durable-launch-receipt.json> \
  -- uv run legalforecast acquisition <subcommand> <frozen-arguments>
```

The `/usr/bin/env -i` boundary is part of the transient unit's command, not merely a caller-side preflight.
User service managers can retain imported environment variables, so every secret-bearing unit must clear that inherited environment before the launcher starts and restore only the explicit nonsecret allowlist shown above.
The launcher and its sandbox child then inherit only that allowlist plus the stage settings injected by `infisical-agent-sandbox`.

Use the dedicated `/agents/sandbox/legalforecastbench/parser` or `/agents/sandbox/legalforecastbench/labeling` path for those stages.
Paid RECAP Fetch uses only `/agents/sandbox/legalforecastbench/recap-fetch-broker-client`.
These and `/agents/sandbox/legalforecastbench-acquisition` are the launcher's exact dedicated sandbox paths; every root, alias, parent, and unrelated path is rejected before the sandbox helper can run.
The parser stage view must resolve exactly `MISTRAL_API_KEY`; the labeling stage view must resolve exactly `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, and `GEMINI_API_KEY`.
Configure those names as Infisical dependent secret references to the canonical values under `/agents/sandbox/legalforecastbench-acquisition` so credential rotation propagates without creating another stored value.
Reference resolution requires the sandbox identity to read both the stage view and the referenced canonical secret; the reviewed `/agents/sandbox/**` read grant covers both, and must not be broadened to compensate for a broken reference.
Do not copy credential values.
Do not enable folder imports: an import would expose acquisition and unrelated provider credentials to the stage process.
The masked Infisical UI inventory is the authoritative exact-inventory check and must match the stage allowlist before the stage starts.
Then run the defense-in-depth sentinels below from an allowlisted empty caller environment; they inspect zsh parameter-name metadata, expand required values only to confirm they are nonempty, and reject every known cross-stage credential without printing or exporting a value:

```bash
env -i PATH="$PATH" HOME="$HOME" USER="$USER" LOGNAME="$LOGNAME" SHELL="$SHELL" TERM="${TERM:-dumb}" \
  infisical-agent-sandbox run --env dev \
  --path /agents/sandbox/legalforecastbench/parser \
  -- zsh -dfc '
    required=(MISTRAL_API_KEY)
    forbidden=(OPENAI_API_KEY ANTHROPIC_API_KEY GEMINI_API_KEY CASE_DEV_API_KEY COURTLISTENER_API_TOKEN RECAP_API_TOKEN FIRECRAWL_API_KEY PACER_USERNAME PACER_PASSWORD)
    for name in $required; do (( ${+parameters[$name]} )) && [[ -n ${(P)name} ]] || { print -u2 -- "$name=missing"; exit 1; }; done
    for name in $forbidden; do (( ! ${+parameters[$name]} )) || { print -u2 -- "$name=unexpected"; exit 1; }; done'

env -i PATH="$PATH" HOME="$HOME" USER="$USER" LOGNAME="$LOGNAME" SHELL="$SHELL" TERM="${TERM:-dumb}" \
  infisical-agent-sandbox run --env dev \
  --path /agents/sandbox/legalforecastbench/labeling \
  -- zsh -dfc '
    required=(OPENAI_API_KEY ANTHROPIC_API_KEY GEMINI_API_KEY)
    forbidden=(MISTRAL_API_KEY CASE_DEV_API_KEY COURTLISTENER_API_TOKEN RECAP_API_TOKEN FIRECRAWL_API_KEY PACER_USERNAME PACER_PASSWORD)
    for name in $required; do (( ${+parameters[$name]} )) && [[ -n ${(P)name} ]] || { print -u2 -- "$name=missing"; exit 1; }; done
    for name in $forbidden; do (( ! ${+parameters[$name]} )) || { print -u2 -- "$name=unexpected"; exit 1; }; done'
```

The sentinels are not a substitute for the complete masked UI inventory because their forbidden lists are intentionally finite.
Do not broaden an Infisical path to make a unit start.

The broker-client view is deliberately different from the dependent parser and labeling views.
It contains exactly `RECAP_FETCH_BROKER_URL`, `RECAP_FETCH_BROKER_MACHINE_ID`, `RECAP_FETCH_BROKER_PRIVATE_KEY_JWK`, `RECAP_FETCH_BROKER_IDENTITY_POLICY_JSON`, and `RECAP_FETCH_BROKER_IDENTITY_POLICY_SHA256` as ordinary secret values written only after the reviewed broker activation has produced and bound them.
They are never dependent references and never folder imports.
The private JWK authenticates only the bounded broker client; it is not a PACER credential.
Raw `PACER_USERNAME`, `PACER_PASSWORD`, and `COURTLISTENER_API_TOKEN` remain broker-custodied and must never appear in this agent-readable view.
Terraform owns only the empty folder; the activation-derived values must stay out of Git, Terraform state, command arguments, logs, and receipts.

Before every paid RECAP Fetch launch, require an immutable successful activation/routing receipt and a complete masked Infisical UI inventory showing exactly those five ordinary-value names, imports disabled, and no other row.
Close the write-capable provisioning session, then run this defense-in-depth name-only sentinel from an allowlisted empty caller environment.
It prints only the five expected names with `present`, never a value:

```bash
env -i PATH="$PATH" HOME="$HOME" USER="$USER" LOGNAME="$LOGNAME" SHELL="$SHELL" TERM="${TERM:-dumb}" \
  infisical-agent-sandbox run --env dev \
  --path /agents/sandbox/legalforecastbench/recap-fetch-broker-client \
  -- zsh -dfc '
    required=(RECAP_FETCH_BROKER_URL RECAP_FETCH_BROKER_MACHINE_ID RECAP_FETCH_BROKER_PRIVATE_KEY_JWK RECAP_FETCH_BROKER_IDENTITY_POLICY_JSON RECAP_FETCH_BROKER_IDENTITY_POLICY_SHA256)
    forbidden=(PACER_USERNAME PACER_PASSWORD COURTLISTENER_API_TOKEN RECAP_API_TOKEN CASE_DEV_API_KEY FIRECRAWL_API_KEY MISTRAL_API_KEY OPENAI_API_KEY ANTHROPIC_API_KEY GEMINI_API_KEY)
    typeset -A required_set
    for name in $required; do
      required_set[$name]=1
      (( ${+parameters[$name]} )) && [[ -n ${(P)name} ]] || { print -u2 -- "$name=missing"; exit 1; }
    done
    for name in ${(k)parameters}; do
      if [[ $name == RECAP_FETCH_BROKER_* ]] && (( ! ${+required_set[$name]} )); then
        print -u2 -- "$name=unexpected"
        exit 1
      fi
    done
    for name in $forbidden; do (( ! ${+parameters[$name]} )) || { print -u2 -- "$name=unexpected"; exit 1; }; done
    for name in $required; do print -- "$name=present"; done'
```

The masked inventory remains authoritative for every name, while the sentinel proves that the launch-time environment contains the five nonempty client settings, no extra `RECAP_FETCH_BROKER_*` setting, and none of the known raw provider or cross-stage credentials.
Folder creation, a passing sentinel, or possession of a client JWK is not purchase authority; the frozen purchase, attempt, broker, ledger, budget, and explicit fee-acknowledgement gates still apply.

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
