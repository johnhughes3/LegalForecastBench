---
name: execution-lane-discipline
description: "How to run a scoped work lane in this repo without burning hours on unlandable work: the mandatory executability audit before building, enforcement-ships-with-issuance for fail-closed contracts, the review-loop cap, cheap-gates-first test ordering, single-writer branch ownership, checkpoint cadence against the lane's payoff, structural halts as a valid outcome, and right-sized process for bounded-cost operations. Use when claiming a bead or lane, planning a validator/executor/gate that will refuse unsigned or unhashed input, iterating on a PR under review, or deciding whether to halt and escalate."
---

# Execution-Lane Discipline

These rules come from a session autopsy of a lane that ran roughly eleven hours and landed nothing: it built enforcement for an artifact no supported tool could produce, then polished the prerequisite instead of reporting that the payoff was unreachable. Each rule below is the cheap check that would have caught it.

They apply to any scoped work lane here, alongside the standing priorities in [AGENTS.md](/.agents/AGENTS.md) and the frozen-contract rules in [docs/cycle-1-change-control.md](/docs/cycle-1-change-control.md).

## 0. Executability audit — before you build anything

For every artifact your planned entrypoint will require as input, name two things:

1. the exact command that produces it, and
2. the exact in-repo path or store where it exists today.

Unknown on either axis means you do not yet have a buildable lane. Producing that command **is** your first deliverable, or the missing capability **is** your first escalation — before any implementation work.

This audit is a handful of commands and about ninety seconds. Skipping it is what cost nine hours in the autopsied session. Write the audit into the bead so the next agent inherits it instead of repeating it.

## 1. Enforcement ships with issuance

Any fail-closed contract you build — an executor that accepts only a hashed spec, a validator that demands a signed artifact, a recorder that requires a bound authorization — must ship **with** the supported production tool that issues that artifact: same PR, or an explicitly sequenced sibling PR named in the bead. Ship the operator flow with it: issue the request, the owner signs against the hash, the operator executes.

Enforcement without issuance is an unfinished feature, and it fails expensively: it consumes a scarce owner-authorization window and returns a structural halt instead of a result. This has happened repeatedly here (a runner with no spec issuer, a gate pack whose release-hash sequencing had no producer, a replay contract with no way to mint the spec it demanded).

Acceptance criteria for a fail-closed bead must name the issuance path explicitly.

## 2. Review-loop cap: three rounds, then escalate

Cap review iterations at **three rounds on the same PR**. If a fourth round is starting, stop and escalate to the owner with the full finding history — round, finding, severity, whether it was in code the previous round approved.

Many sequential rounds each surfacing new blockers in previously approved code is a reviewer-process failure, not a code-quality failure, and another round will not converge it.

## 3. Cheap gates first; full suite exactly once

Per iteration, run gates in ascending cost and stop at the first failure:

1. **Structural gates (seconds to ~30s)** — architecture, module map, and contract ratchet. Currently:
   ```bash
   uv run pytest tests/test_architecture.py tests/test_architecture_rules.py \
     tests/test_architecture_inventory.py tests/test_ingestion_module_map.py \
     tests/test_contract_ratchet.py -q
   ```
2. **Focused tests** for the modules you touched, serial.
3. **Static gates** — `ruff format && ruff check --fix && uv run pyright`.

The full suite (`uv run pytest -q -n 4 --dist=loadscope`) is a ten-minute gate: run it **exactly once, on the final pre-merge head**. Never once per review round. Note that the contract-ratchet baseline is whole-tree, so every merge into the trunk can redden an open ratchet-touching PR — rebase promptly rather than re-running the full suite to investigate.

## 4. Single writer per branch

One writer per branch, always. Announce branch ownership when you claim the lane, in the bead and wherever the team coordinates, so siblings can see it.

If any other actor — a human, a sibling agent, or an automated merge/fix bot — pushes to your branch, stop before your next commit and resolve ownership. Two writers on one branch produce force-push races, lost review fixes, and CI runs against a head nobody owns.

## 5. Checkpoint cadence: T+3h, then every 2h

At three hours into a lane, and every two hours after, write a short checkpoint into the bead that answers:

- What is this lane's actual **payoff** — the landed result it exists to produce, not the prerequisite currently in front of you?
- What is the critical path from here to that payoff?
- Is every remaining prerequisite on that path **obtainable** — tool exists, artifact producible, approval available?

If the payoff is unreachable, halt and escalate now. Do not keep improving the prerequisite. Time already spent is not a reason to spend more; the checkpoint exists precisely to interrupt that reflex.

## 6. A correct structural halt satisfies the goal

Discovering that the work cannot proceed — a missing issuance path, an absent approval, a frozen-contract conflict, an input nothing can produce — and reporting it plainly **is** a successful outcome. Say so in those words, with the evidence.

Do not dress a halt as progress, and never redefine hours of prerequisite polish as success. A clear halt at hour one is worth more to the project than a busy hour eleven.

## 7. Proportionality — right-sized process, non-negotiable integrity

The critical path is finishing the cycle and publishing results. Prefer the smallest change that produces a correct result over new process, ceremony, or speculative hardening.

For a **bounded-cost operation** (a document purchase, a metered API probe, any spend with a stated ceiling), the entire required process is:

1. a **ceiling** — the approximate amount, stated up front,
2. a **journal** — what was spent, on what, recorded in the bead, and
3. the **owner's one-line approval** against that approximate amount.

Nothing more. Do not build authority chains, multi-party sign-off, or approval machinery on top of that.

What proportionality never touches: **integrity controls are not the slowdown and are not negotiable.** Contamination and model-eligibility rules, outcome-leakage blinding, byte-role validation of authenticated artifacts, and frozen-contract change control stay exactly as documented. Trim process, never integrity.

## Lane checklist

At claim time:

- [ ] Executability audit written into the bead (rule 0).
- [ ] Branch ownership announced (rule 4).
- [ ] If the lane builds a fail-closed contract: issuance path identified and in scope (rule 1).

While working:

- [ ] Cheap gates each iteration; full suite once at the end (rule 3).
- [ ] Checkpoint at T+3h and every 2h, restating the path to the payoff (rule 5).
- [ ] Review rounds counted; escalate at four (rule 2).

At close:

- [ ] Result **or** an explicit structural halt, reported plainly with evidence (rule 6).
- [ ] Any spend journaled against its approved ceiling (rule 7).
