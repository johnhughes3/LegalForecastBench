# Tier-0 readiness pack for the designated approver

Status: **NOT READY FOR SPEND SIGNATURE**

No provider spend is authorized by this document. The production runner, native-thin arm, receipt binding, and mechanical spend-control implementation are on `main` through `9a78302075b2a0840f25f03f59242743bc283abb`, but the remaining work is still not limited to the designated approver's signature: two public authorities are unprovisioned, no production evaluator/provider factory is installed, the evaluator wrapper is not pinned, the privileged containment capture is absent, and no final executable spec, pricing snapshot, spend policy, or superseding freeze exists.

## Current specification artifact

| Field | Value |
| --- | --- |
| Structural specification | `docs/community-acceptance/tier0-paired-smoke-structural-freeze.md` |
| SHA-256 | `f87b916fb4eefd621e29093877dbd45b402486e20b51af876110907f880cd681` |
| Status | Structural pre-spend freeze only; blocked and not an approval target |
| Required next artifact | A newly hashed executable freeze that explicitly supersedes this one and predates every paid call |

The companion `.sha256` file permits a reviewer to verify the exact bytes. The designated approver should not approve spend against this hash.

Regenerating the structural specification means updating three things together: the freeze document, its `.sha256` companion, and the SHA-256 row above. `tests/test_community_acceptance_freeze_digest.py` fails if any of the three drifts from the others, so the table above cannot silently outlive the bytes it names. That gate reads the rendered table in this section only, and requires exactly one such table — under a level-two heading — carrying exactly one `Structural specification` row and one `SHA-256` row: a row moved into a code fence, an HTML comment, or an indented block, or into a historical table or a second table here, is not a declaration a reviewer can see, and the gate reports it missing rather than accepting it.

## Cost state

The known complete pair requires two solver executions and 46 criterion-level judge calls before any internal retry. A planning-only administrative reserve of **USD 25–100** is proposed so budgeting work has a bounded discussion range.

That band is not an estimate, cap, or authorization. The landed controller can enforce per-arm solver caps, per-criterion judge caps, retry and parallelism limits, and one experiment-wide hard stop, but no dated production pricing snapshot or final dollar-valued policy has been committed. The final inputs must choose the token/request/retry limits, prove every worst-case request fits its scoped ceiling, and bind the policy and pricing hashes into the executable spec. Subscription-unallocable usage must never be reported as `$0`.

## Exact `dm0g.4.5.15` commands

**BLOCKED — the supported command shape has landed, but there is no executable approval packet. Do not run these templates or substitute an ad hoc invocation.**

```bash
uv run legalforecast multiharness tier0 validate \
  --spec TIER0_EXECUTABLE_SPEC.json \
  --spec-sha256 sha256:SPEC_SHA256 \
  --approval TIER0_DETACHED_APPROVAL.json

uv run legalforecast multiharness tier0 run \
  --spec TIER0_EXECUTABLE_SPEC.json \
  --spec-sha256 sha256:SPEC_SHA256 \
  --approval TIER0_DETACHED_APPROVAL.json
```

The entrypoint derives fresh private and archive roots from the spec directory and hash, executes the frozen opaque arm order, and accepts no run-varying flags beyond the spec/hash/approval triplet. Its provider-free fake-binary acceptance path covers projection, registry lookup, contained clean-native and native-thin execution, discovery, authorized scoring, receipts, and archive output.

The paid command is nevertheless non-executable today. Both committed public-authority files have `public_key_base64: null` and `status: pending_human_provisioning`. In addition, `legalforecast.multiharness.cli` requires an embedding runtime to call `install_tier0_production_evaluator_factory(...)`, but the supported repository has no production installer; without one, `tier0 run` refuses paid execution before evaluation. The required `harvey-lab-eval` wrapper is also not installed on the characterized PATH, so no final wrapper digest can be placed in the executable spec. These are fail-closed blockers, not operator choices that may be supplied as extra flags.

## What `dm0g.4.5.16` will review

The independent `dm0g.4.5.16-reviewer` registered and recorded a Phase-1 `BLOCKED / NOT ACCEPTED` verdict against the earlier structural-only state. That verdict remains controlling; it is not acceptance of the landed implementation. A fresh review must receive the final executable freeze, its hash, exact commands, dated pricing and spend sidecars, configured public authorities, wrapper and binary identities, and byte-identical regeneration evidence. The reviewer must not be any `dm0g.4.5.15` or `dm0g.4.5.18` executor, and the final private archive must prove that separation.

The reviewer will verify the executable spec predates spend; byte-identical inputs; requested/resolved model and configuration identity; containment and canaries; complete attempt/retry/failure/cost retention; pre-evaluation sealing; evaluator, judge, rubric, issuer, signature, and accounting bindings; recomputed criterion and paired scores; recomputed coverage/cost/token/time fields; public allowlist and secret/private-shape scans; durable archive hashes; and the permanent preliminary claim label. The full twelve-point protocol is frozen in the structural specification.

## `dm0g.4.2.2` privileged no-spend capture

This remains a designated-credential-operator blocker. No approved privileged Claude whole-process containment fixture exists.

The operator procedure is in `docs/adapters/claude-code-native-containment.md`, but its command block intentionally contains `INSERT_FRESH_INDEPENDENTLY_APPROVED_SHA256` and must not be run as written. The currently documented target is Claude Code 2.1.220 with SHA-256 `674f61f20ff306f3100cf9200e4c36c4b70278b5bef2884549819b942a89c863`; that identity does not match either the landed adapter manifest or the latest credential-free probe, Claude Code 2.1.233 with SHA-256 `55d281096f57d411ebbdd94dbf5e9ff3accb7c05713e37348c2c11d4b83bf9d9`. It therefore cannot by itself clear Tier-0.

The designated credential operator's exact action sequence is:

1. Assign an independent reviewer to approve the exact current probe and test bytes plus the intended target executable hash.
2. Resolve or identify the supported cwd-bound V2 `sudo-request` client/daemon invocation; the unchanged clients from the recorded HTTP 422 failures must not be retried.
3. From the repository root, run the documented capture block only after replacing `INSERT_FRESH_INDEPENDENTLY_APPROVED_SHA256` with the reviewer's exact approved digest.
4. Approve that fresh staged and hash-attested request out of band within its approval window.
5. Keep the capture outside the repository until a different independent reviewer validates it and authorizes the fixture.
6. Reconcile the approved containment binary with the final executable Tier-0 binary identity before treating the capture as a Tier-0 prerequisite.

There is no safe copy-paste command before steps 1 and 2 are satisfied. Printing the placeholder block as runnable would defeat the independent-review boundary.

## Other blocking seams

| Blocker | Required result |
| --- | --- |
| `dm0g.4.5.13` | Narrow issue-196 selection, byte inventory, private split, seal, and provider-free dry run land; its privileged-containment dependency remains explicit |
| `legalforecastbench-lrc3` | Install the reviewed production evaluator/provider factory, pin an installed evaluator wrapper, and configure the approved evaluator public key; the CLI, per-arm receipts, and archive surface are landed |
| `legalforecastbench-e5er` | Commit the dated pricing snapshot and exact dollar-valued policy, bind both hashes into the executable spec, and retain the final mutation evidence; the enforcement mechanism is landed |
| Approval authority | John supplies and reviews the public Ed25519 key for `legalforecast.tier0-spend-approval-issuer.v1`; it must remain distinct from the evaluator signer |
| Evaluator authority | John provisions the RFC 8032 seed only at `/agents/sandbox/legalforecastbench/harness-runtime/evaluator-issuer` in `dev` and approves committing the corresponding public key; agents never create or read the secret |
| Binary identities | Reconcile the privileged containment target with observed Claude Code 2.1.233, then bind the exact approved solver and evaluator-wrapper identities through generated private run metadata |
| Credentials | Complete the designated credential operator's solver/judge credential handshakes without host-store fallback |
| Order and mapping | Commit opaque arm IDs, solver/evaluator order, private mapping custody, and terminal retry policy |
| Pricing and caps | Bind a dated pricing snapshot and reproducible estimate to enforced maxima |

## Tier-1 and quickstart status

`dm0g.4.3.8` has a blocked structural draft, not a final freeze. It requires the real Tier-0 observations and independent `dm0g.4.5.16` review, plus the still-open `dm0g.4.1.15` checkpoint.

The `dm0g.4.6.6` friction list was already fixed and landed in PR #730, and its fixture quickstart passed. The remaining Harvey LAB projected-category rerun is not recorded after the bridge landed, so no new documentation fix is inferred here and the bead remains open. The separately authorized one-call published-key check was already recorded; this lane performed no additional live smoke.

## Signature decision

The designated approver's safe action today is **do not sign**. First provide the two reviewed public keys and choose or authorize the production evaluator/provider adapter and wrapper. Then the owning lane can commit the dated pricing snapshot, dollar-valued policy, executable spec, deterministic superseding freeze, and companion hash; only after the independent reviewer records fresh acceptance should the detached spend signature be created.
