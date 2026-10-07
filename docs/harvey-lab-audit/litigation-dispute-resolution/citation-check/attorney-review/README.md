# Attorney review of the AI citation check: protocol

This protocol was committed before any sampled finding was reviewed. It estimates how many of the citation check's problem findings are real errors.

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
- **Note**: what the authority actually says, with a locator, where useful.

Only "Confirmed error" counts as confirmed.

## What this estimates

The sample estimates the share of the 436 AI findings that are real errors. The exact one-sided 95% lower bounds (hypergeometric, population 436) are:

| Result | At least this many of 436 are real errors |
|---|---|
| 10 of 10 confirmed (stop) | 325 (74.5%) |
| 19 of 20 | 344 (78.9%) |
| 18 of 20 | 315 (72.2%) |
| 17 of 20 | 288 (66.1%) |
| 16 of 20 | 263 (60.3%) |
| 15 of 20 | 240 (55.0%) |

It does not estimate errors the AI missed among the citations it marked verified, and it does not re-check whether an error was planted.

`uv run python scripts/harvey_citation_sample.py tally` recomputes the draw, checks that the worksheet still lists it in order, applies the stopping rule, and prints the bound. `draw --text <dir>` regenerated the worksheet from the published results, quoting each citation's passage from the task text produced by `scripts/harvey_citation_check.py extract`.
