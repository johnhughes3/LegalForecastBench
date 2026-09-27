# Review saved forecast rationales

Outcome accuracy alone does not establish legal reasoning quality. The rationale export prepares saved per-unit explanations for qualitative lawyer review without changing the scoring protocol or making new provider calls.

```bash
uv run python -m legalforecast.evals.rationale_audit \
  --runs private-runs.jsonl \
  --output-dir private-rationale-review
```

Input is JSONL in the existing case-run record shape: `case_id`, `solver_id`, `run_label`, `ablation`, `required_unit_ids`, and `raw_output`. Native receipt identity fields `model_key` and `run_identity_sha256` are accepted in place of `solver_id` and `run_label`. An optional positive `repeat_index` distinguishes repeated predictions (default 1). The raw model response is parsed by the same parser used for scoring. Public records with `parser_output` are also accepted, but those deliberately contain no prose: their units appear as missing rationales. The command cannot reconstruct text stripped from public receipts. Supply saved private responses when available; never manufacture an explanation after scoring.

For a locally available native runner ledger, replace `--runs private-runs.jsonl` with `--ledger run-ledger.sqlite3`. The database is opened read-only; completed cells supply their receipt identities and saved managed response `raw_output`. The raw response must reproduce the receipt's parser projection. Non-managed provider payloads without normalized `raw_output` remain missing-rationale rows. Ledger mode covers only completed cells, not failed or unstarted cells, so its denominator is not the planned run census. Obtain any protected private artifact through its existing authorized path; this command neither downloads it nor grants access.

The new output directory contains:

- `review.jsonl`: random review IDs, case/unit IDs for matching the supplied packet, original rationale text, and whether the prediction defaulted. Model identity, probabilities, provider metadata, case assessments, and outcomes are omitted. Row order is randomized.
- `private-key.jsonl`: the coordinator's mapping to source row, model, condition, repeat, probability, and parser status. Do not give this file to blinded reviewers.
- `coverage.json`: counts of all required predictions, present and missing rationales, and defaulted predictions. Missing explanations and invalid outputs stay in the denominator.

The export hides structured model identity, not identity embedded in prose. Before distribution, the coordinator must inspect rationales for self-identification or outcome leakage and provide only the pre-decision packet. Both files remain private research material, not public website artifacts. Keep the original export so completed reviews can be joined by `review_id`; regenerating creates new IDs. Existing output directories are refused to avoid breaking those joins.

This prepares review material; it does not supply lawyer ratings, dispositive-ground annotations, or a new reasoning score. Per-ground scoring requires distinguishing accepted grounds from rejected and expressly unreached grounds; an unreached argument is not a negative label. A qualitative audit can assess whether explanations engage the actual arguments before deciding whether additional annotation is worth its cost.

External CourtListener/MCP retrieval is a separate unresolved research condition. Local tools over a frozen packet do not establish cutoff-safe external search. Such a comparison needs a fixed eligible source collection, exclusion of target and related-case outcomes and tentative rulings, cutoff filtering of returned text and metadata, and the same model/packets with a no-external-retrieval control. No external retrieval is enabled by this command.

The existing metadata-only versus full-packet comparison estimates the incremental predictive value of the supplied record; it does not isolate reasoning from memorization, case mix, or missing primary sources. A rationale audit is complementary evidence, not a causal identification strategy. Issue #6 remains open for these research questions.
