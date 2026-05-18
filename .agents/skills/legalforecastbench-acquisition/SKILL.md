---
name: legalforecastbench-acquisition
description: Use when working on LegalForecastBench MTD acquisition, case.dev smoke runs, CourtListener/RECAP packet recovery, or live-pilot sample selection.
---

# LegalForecastBench Acquisition

## Source of truth

- Check `legalforecast/ingestion/mtd_acquisition_screen.py` before proposing live MTD search terms.
- `OPTIMIZED_MTD_DECISION_SEARCH_TERMS` and `SECONDARY_MTD_DECISION_SEARCH_TERMS` are the live smoke defaults.
- `LOW_YIELD_MTD_DISCOVERY_TERMS` and `legalforecast.selection.candidate_discovery.mtd_discovery_search_terms()` are broad recall tools, not the default for live smoke collection.
- Do not invent ad hoc query lists when these constants cover the task.

## Empirical basis

The May 17, 2026 full acquisition screen in `/tmp/lfb-acq-validation/mtd-gemini-full-150-20260517-014900/combined_report.md` found:

- 3,668 unique processed dockets.
- 199 deterministic actual MTD decisions.
- 151 Gemini-good cases.
- 150 cheapest selected cases for the target.
- Best single term: `order on motion to dismiss`, with 1,156 scraped dockets, 114 deterministic MTD decisions, and 94 good cases.

If this `/tmp` artifact is gone, search `~/.codex/sessions/2026/05/17/rollout-2026-05-17T08-19-11-019e35e0-47cd-7a72-ba09-1a7657cd2e9d.jsonl` for `151` or `Gemini-good` to recover the provenance.

## Smoke runs

Use `legalforecast case-dev-smoke` for bounded Phase 0 acquisition checks. By default it should use the optimized decision-oriented terms:

```text
order on motion to dismiss
order granting motion to dismiss
order denying motion to dismiss
order granting in part and denying in part motion to dismiss
opinion and order motion to dismiss
memorandum opinion and order motion to dismiss
decision and order motion to dismiss
order on motion for judgment on the pleadings
order granting motion for judgment on the pleadings
order denying motion for judgment on the pleadings
```

Only pass `--query-term` when intentionally overriding the optimized defaults. If overriding, say why in the report or handoff.

For a 25-candidate post-release pilot from April 24, 2026 through the current collection date:

```bash
uv run legalforecast case-dev-smoke \
  --output tmp/case-dev-smoke-2026-04-24_to_YYYY-MM-DD_25.md \
  --dry-run \
  --date-window-start 2026-04-24 \
  --date-window-end YYYY-MM-DD \
  --per-query-limit 100 \
  --candidate-retrieval-limit 25
```

Replace `--dry-run` with `--live` only after explicit user approval for live case.dev API usage.

## Live and paid data guardrails

- Do not run live case.dev, RECAP, CourtListener, PACER, or purchase/recovery commands unless the user has approved the live operation for this turn.
- Do not trigger paid PACER or Case.dev purchase paths without explicit fee acknowledgement.
- Prefer public/free CourtListener or RECAP artifacts first; keep paid acquisition separate from model-execution cost.
- Write generated reports under `tmp/` unless the user asks for a stable doc path.

`acquisition download-free --execute` has two explicit modes:

```bash
uv run legalforecast acquisition download-free \
  --requests tmp/acquisition/free-document-requests.jsonl \
  --output-root tmp/acquisition \
  --execute \
  --live-public-download
```

Use `--live-public-download` only for already-free HTTPS CourtListener/RECAP PDF
URLs. Use `--fixture-documents` for offline tests and fixtures. This stage must
not purchase PACER documents.

When starting from a screened Case.dev/CourtListener JSONL plus saved raw docket
HTML, use the planner first:

```bash
uv run legalforecast acquisition plan-public-downloads \
  --screened-cases tmp/acquisition/selected-cases.jsonl \
  --raw-html-dir tmp/acquisition/raw_html \
  --output-root tmp/acquisition \
  --target-clean-cases 25 \
  --execute
```

The strict planner selects only candidates with free public links for an
operative complaint, the target MTD entry, and the decision. If target entry
numbers are stale, `--allow-inferred-target-mtd` can be used for pilot triage,
but the run should be described as inferred-linkage rather than official.

After `download-free`, derive parser requests through the CLI rather than
hand-building JSONL:

```bash
uv run legalforecast acquisition plan-parse-documents \
  --download-manifest tmp/acquisition/free-document-downloads.jsonl \
  --output-root tmp/acquisition \
  --execute
```

## Sample selection

For small real pilots, select clean cases, not raw hits:

- Use the decision/order docket-entry date for the date window.
- Deduplicate by case.
- Sort deterministically by decision entry date, court, and docket number.
- Screen for federal civil MTD or MTD-adjacent written dispositions.
- Exclude sealed/restricted records, non-civil matters, habeas/immigration detention, bankruptcy, criminal, standing orders, extensions, voluntary dismissals, and cases without reconstructable pre-decision packets.
- Log every exclusion reason so the acquisition yield is auditable.

## Registry-backed pilot execution

Live pilot runs should use frozen registry keys, not ad hoc solver IDs. The
current 25-case pilot registry is:

```text
model_registries/pilot-2026-04-24_to_2026-05-18.json
```

Default pilot model keys:

```text
google:gemini-3-flash-preview
openai:gpt-5.4-mini
anthropic:claude-sonnet-4-6
```

Use `legalforecast eval run-case --backend live --model-registry ... --model-key
...` for one isolated case/model job. The GitHub matrix workflow
`.github/workflows/official-eval-matrix.yaml` takes `model_registry_uri` and
comma-separated `model_keys`, verifies that the requested keys exist in the
frozen registry, and dispatches one job per case/model row.

After downloading workflow artifacts, aggregate a multi-model pilot with one
`--model-key` per expected registry entry:

```bash
uv run python -m legalforecast.publication.official_aggregate \
  --per-case-dir tmp/official-eval-artifacts \
  --run-input-manifest tmp/private-store-export/objects/results/manifests/cycle-id.run-inputs.json \
  --labels tmp/locked-labels/cycle-id.labels.jsonl \
  --output-dir tmp/official-results/cycle-id \
  --cycle-id cycle-id \
  --cycle-series pilot \
  --clean-motion-count 25 \
  --prediction-unit-count <locked-unit-count> \
  --model-key google:gemini-3-flash-preview \
  --model-key openai:gpt-5.4-mini \
  --model-key anthropic:claude-sonnet-4-6 \
  --ablation full_packet
```

For a 25-case, 3-model pilot, aggregation should expect 75 case/model outputs
but still report 25 distinct cases. `cycle-power.json` should classify the
result as a pilot/feasibility output, not a strong-ranking claim.
