# Attorney review of the AI citation check: protocol

The sampling and stopping rules below were committed before any sampled finding was reviewed. The confidence calculation was corrected after review to account for both possible analyses; the original fixed-sample calculation did not provide 95% coverage under this stopping rule. It estimates how many of the citation check's problem findings are real errors.

## Question

The [citation check](../README.md) reports 436 problem citations in the 52 LAB litigation task environments that no rubric criterion asks the model to catch (the "unintentional errors" in the paper's citation table). How many of those AI findings would an attorney confirm?

## Sample

- **Population.** The 436 entries in [`rubric-intent.json`](../rubric-intent.json) with `intentional: false`, sorted by task and citation number.
- **Draw.** A simple random sample of 20 without replacement, using seed `20261007` (this protocol's date) and Python's `random.Random(20261007).sample`. Review order is draw order. There is one draw: no redraws, replacements, or additions.
- **Stopping rule (fixed in advance).** Review entries 1 to 10. If all ten are confirmed errors, stop. Otherwise review entries 11 to 20 as well and report all twenty.
- **Files.** [`sample.json`](sample.json) records the draw; [`worksheet.md`](worksheet.md) has one entry per sampled citation.

## What the reviewer decides

For each entry, read the citation where it appears in the task document, the authority itself, and the AI's finding, then record:

- **Verdict**, one of:
  - **Confirmed error**: the citation is wrong in a way a careful lawyer would correct before filing. The authority does not exist, does not support the proposition it is cited for, does not contain the quoted language, or is cited so that a reader cannot find it or would find a different authority. This counts as confirmed even if the error is of a different kind than the AI said.
  - **Minor defect only**: the authority supports the proposition, but a pin cite, year, or similar detail is off.
  - **Not an error**: the citation is accurate.
- **Error type, if confirmed**: the AI's category if it is right, otherwise the correct one.
- **Rubric relevance (optional)**: whether the task's rubric tests the point the citation is used for, rewards relying on it, or ignores it. Each entry lists what an AI review of the rubric found and the text of any criterion that names the authority. This field does not affect the verdict or the count.
- **Note**: what the authority actually says, with a locator, where useful.

Only "Confirmed error" counts as confirmed.

## What this estimates

The sample estimates the share of the 436 AI findings that are real errors. The conservative one-sided 95% lower bounds below invert exact hypergeometric tails (population 436), using a 2.5% error allowance at each of the two possible analyses. By the Bonferroni inequality, the probability that either bound exceeds the true count is at most 5%, including when the first ten results determine whether review continues. This correction changes neither the draw nor the recorded verdicts.

| Result | At least this many of 436 are real errors |
|---|---|
| 10 of 10 confirmed (stop) | 303 (69.5%) |
| 19 of 20 | 330 (75.7%) |
| 18 of 20 | 300 (68.8%) |
| 17 of 20 | 273 (62.6%) |
| 16 of 20 | 248 (56.9%) |
| 15 of 20 | 225 (51.6%) |

It does not estimate errors the AI missed among the citations it marked verified, and it does not re-check whether an error was planted.

`uv run python scripts/harvey_citation_sample.py tally` recomputes the draw, checks that the worksheet still lists it in order, applies the stopping rule, and prints the bound. `draw --text <dir>` regenerated the worksheet from the published results, quoting each citation's passage from the task text produced by `scripts/harvey_citation_check.py extract`.
