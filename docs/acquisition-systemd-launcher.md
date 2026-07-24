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
