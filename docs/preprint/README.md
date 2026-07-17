# LegalForecast-MTD Cycle 1 preprint package

Status: pre-results repository package. This package does not authorize SSRN or arXiv submission.

The manuscript is complete as a methods draft and deliberately contains no Cycle 1 result. Its only remaining manuscript input is the audited official aggregate produced by the official publication gate. John J. Hughes III separately approves authorship, destination, final text, and any submission.

## Package contents

- `legalforecast-mtd-cycle-1.md` is the canonical manuscript source.
- `package-manifest.json` binds each pending result slot to a public aggregate path, field, and verification rule. Slots are required unless they explicitly set `required` to `false`; the paired-ablation slot is populated only when its artifact is indexed.
- `citation-audit.json` states what each reference supports and whether it is direct support, a design analogy, or context only.
- `../../output/pdf/legalforecast-mtd-cycle-1-draft.pdf` is the deterministic six-to-ten-page pre-results rendering.

No harness-comparison appendix is included. A future appendix is allowed only when validated evidence is ready, remains separately labeled with its community evidence status and limitations, and does not delay the official methods paper.

## Render

From the repository root:

```bash
uv run scripts/render_methods_preprint.py
```

The renderer rejects output outside the six-to-ten-page contract. The committed PDF must be byte-identical to a fresh render.

## Populate from audited results

1. Obtain the canonical audited official aggregate and verify every SHA-256 entry in `public/artifact-index.json`.
2. Reconstruct every unit loss in `public/unit-scores.jsonl` as `(probability_fully_dismissed - outcome)^2`, reject any supplied `brier` mismatch, aggregate only the recomputed losses into the leaderboard's micro-Brier rows, and verify the aggregate run card against the frozen manifest, model registry, ablations, and matrix counts.
3. Follow each binding in `package-manifest.json`; replace only the corresponding pending result cell and narrative. For an optional slot whose population condition is false, use its declared `absence_display` instead of requiring an artifact the aggregate does not emit. Preserve the exact **Official LegalForecast-MTD Cycle 1 result** label.
4. Run table reconstruction for every number, interval, ordering statement, baseline statement, and accounting total. A mismatch blocks the package.
5. Run the leakage and publication guardrails. Do not copy locked labels, raw provider responses, restricted source bytes, private withdrawal details, credentials, or `private-debug` material into the source or PDF.
6. Rerender, inspect every page visually, and obtain an independent methods review covering claims, citations, tables, leakage, limitations, and reproducibility.
7. Update the package status only after those checks pass. Repository completion still is not submission authority.

## Final review record

The pre-results draft requires an independent methods review before the Bead can close. After audited population, a second independent result-table and claims review is required because the current review cannot validate unseen numbers.

SSRN is the intended primary package. arXiv is optional and never blocks SSRN or the official report. Neither destination may receive this package without John's separate approval of the exact final artifact.
