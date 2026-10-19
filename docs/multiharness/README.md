# Community Multi-Harness Comparisons

> **Status: non-official community track.** The code, adapter contracts, and no-network fixtures exist in this repository, and the checked-in registry includes historical provider smoke examples accepted through the community PR workflow. The workflow validates checked-in metadata and builds a separate community static-site artifact on `main`; that artifact is not the official LegalForecast-MTD result publication, and the published Cycle 1 results do not depend on it.

The multi-harness layer is meant to compare agent harnesses — LegalForecastBench fixture or subset tasks, Harvey LAB tasks, and contributor adapters — without weakening the official benchmark's boundaries. Its results would never rank alongside official results, and a LegalForecast-MTD Brier score is never combined with a Harvey LAB rubric score. See [publication governance](../publication-governance.md) for the track-separation rules.

## Evidence descriptions

These are ordinary descriptions of the evidence available for a community submission, not result tiers. They do not create official, verified-community, community-unverified, or alpha-non-canonical classifications, and they do not determine whether a submission is accepted or published. Acceptance and publication follow the reviewed metadata and workflow contract in [Submissions](submissions.md).

- **Preliminary — one task pair, operator-run, not independently reproducible**: describes a limited observation whose evidence is not independently reproducible.
- **Reproducible community result — contributor-grade, non-official**: describes a contributor-grade observation with reproducibility evidence while retaining its non-official status.

## Contributor path

Start with the CLI help:

```bash
uv run legalforecast multiharness --help
```

Then read, in order:

- [Contributor guide](contributor-guide.md): install, probe, select, run, interrupt, resume, validate, and package from a dedicated environment.
- [Adapter spec](adapter-spec.md): the community adapter contract.
- [Submissions](submissions.md): submission packaging, required contributor declarations, credits, funding policy, and PR intake.

Community submissions live under [`community/submissions/`](../../community/submissions/) and are rebuilt into a separate community registry and site. No-network fixture manifests for the adapter tracks live under [`examples/adapters/`](../../examples/adapters/).

## Reference

- [Contracts](contracts.md): sealed-deliverable, evaluation, scoring, identity, compatibility, and Harvey LAB source boundaries.
- [Harness efficiency observations](harness-efficiency-observations.md): receipt-backed duration, cost, and token accounting published as peer columns.
- [Native Harvey LAB bridge](harvey-lab-core.md): pinned lab-core 1.1.0 probing, native solver/judge execution, and public-safe results.
- [Evaluator receipt authority](receipt-authority.md): the Ed25519 evaluator-issuer seam (not yet provisioned) and the credential-free executable probe.
- [Claude Code terminal release run](terminal-release.md): running an outcome-blinded forecast release through the headless Claude Code CLI, with a provider-free fixture path. The protected benchmark workflow accepts this and the Hermes and OpenClaw harnesses as alternative execution modes, but the published Cycle 1 results use the native document-tool runner.
- [Local CLI adapter manifest](local-cli-adapter-manifest-v1.md): the generic manifest contract for local agentic CLI adapters.
- Adapter tracks: [provider baselines](adapters/provider-baselines.md) and the [Hermes Agent bridge](adapters/hermes-agent.md).

LegalForecastBench is an independent project. Harvey AI, Harvey LAB, and LegalQuants are not sponsors, partners, or endorsers of this work.
