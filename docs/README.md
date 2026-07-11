# Documentation Index

The technical documentation in this folder is drafted and maintained with substantial assistance from AI systems working under the direction of John J. Hughes, III, and is reviewed on a best-effort basis. Where possible, accuracy is enforced mechanically: the official-run runbook and reproduction guide are checked against the actual CLI by automated tests. Corrections are welcome as issues or pull requests.

## Official Benchmark

- [METHODS.md](METHODS.md): eval-card-grade methods — construct, frozen inputs, leakage controls, metrics, inference, related work, human-baseline status, limitations, and withdrawal policy.
- [labeling-protocol.md](labeling-protocol.md): the unit-resolution and edge-case codebook used to label frozen prediction units.
- [official-run-runbook.md](official-run-runbook.md): operator checklist for protected official cycles — freeze, dispatch, recovery, aggregation, and site rendering.
- [reproduce-or-audit.md](reproduce-or-audit.md): credential-free reproduction of public arithmetic and the deeper audit workflow.

## Community Multi-Harness (non-official)

- [multiharness-adapter-spec.md](multiharness-adapter-spec.md): the community adapter contract.
- [community-submissions.md](community-submissions.md): submission packaging, attestations, credits, funding policy, and PR intake.
- [adapters/](adapters/): notes for the first-class fixture adapter tracks (LQ.AI, Hermes Agent, OpenClaw, and provider/runtime baselines).

Historical planning and review documents have been removed from the working tree; they remain available in git history.
