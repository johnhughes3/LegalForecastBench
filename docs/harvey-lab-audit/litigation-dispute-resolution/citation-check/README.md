# Citation check of the 52 LAB litigation task environments

> [!WARNING]
> **AI-generated analysis, not yet spot-checked by a person.** Claude agents extracted and checked every citation below; a separate agent then tried to overturn each problem finding. No lawyer has re-checked these results. Characterizations of what an authority holds are AI judgments. "Not found" means not found after a thorough search, not proof of fabrication.

This check covers every citation to legal authority in Harvey LAB's `litigation-dispute-resolution` practice area at commit [`1dd81403`](https://github.com/harveyai/harvey-labs/tree/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution): all 52 tasks, both the supplied documents and each `task.json` (the instructions and rubric). It extends the earlier [check of the 19 sampled tasks](../human-review/citation-sweep.md), which covered case law only.

| File | Contents |
|---|---|
| [`problems.md`](problems.md) | Every citation whose final status is a problem, by task, with the finding |
| [`summary.json`](summary.json) | The counts in this README, by status, authority type, location, and task |
| `results/<task>.json` | Every citation in the task: where it appears, what it is cited for, quotations attributed to it, the first check (status, explanation, source URLs, excerpt read), and the second check where one was made |

## Results

The check found 3,821 citation instances. 203 are fictional by design (the scenario's own case captions, docket entries, and orders) and were not checked. Of the 3,618 cited as real law:

| Final status | Instances |
|---|---:|
| Verified | 2,754 |
| Verified, minor defect (pin cite, loose paraphrase, wrong year) | 346 |
| **Mischaracterized**: real authority cited for something it does not say or contradicts | **277** |
| **Not found, likely fabricated** | **76** |
| **Wrong citation to a real authority** (reporter, court, year, or party garbled) | **58** |
| **Misquoted**: quoted language not in the authority | **40** |
| **Citation points to a different case** than the one named | **16** |
| Unable to verify (source text not accessible) | 51 |
| **Problems, total** | **467** |

Problems appear in 41 of the 52 tasks and are concentrated: four tasks account for 239 of them (`draft-motion-to-dismiss-brief` 98, `draft-opposition-to-motion-to-dismiss` 54, `assess-settlement-value-range` 49, `review-counterpartys-proposed-jury-instructions` 38).

By authority type:

| Type | Checked | Problems | Not found |
|---|---:|---:|---:|
| Case | 590 | 224 | 60 |
| Statute | 1,341 | 104 | 3 |
| Court rule | 1,120 | 63 | 5 |
| Regulation | 189 | 20 | 0 |
| Restatement or treatise | 38 | 4 | 2 |
| Other (agency guidance, model instructions, contract provisions cited as authority) | 340 | 52 | 6 |

Thirty-five problems sit in a `task.json`, that is, in the task instructions or the rubric the grader applies; the other 432 are in the supplied documents.

**Second check.** Every first-check problem (481) went to a separate agent instructed to search for evidence that the citation is in fact accurate. It overturned 14: 10 mischaracterizations, 3 wrong citations, and 1 misquotation, mostly to "verified, minor defect." It overturned none of the 76 not-found findings.

**Comparison with the 19-task check.** For the 19 tasks both checks cover, this check finds 102 problems among 224 case-citation instances; the earlier check found 45 among 102. The units differ: this check counts short forms, *Id.* references, names given without a citation, and rubric references separately, which the earlier check folded together.

## How to read these numbers

- **A problem in a document is not necessarily a defect in the task.** Some tasks hand the model an opposing party's brief or proposed jury instructions to critique, and a miscited authority there may be planted for the model to catch. This check records whether a citation is accurate, not whether the error was intended or whether the rubric rewards spotting it. The two largest counts come from tasks of exactly this kind (an opposing motion to dismiss, a counterparty's jury instructions), alongside tasks where the flawed authority sits in the client's own research memo or in the rubric. Classifying each problem as planted or unplanted, and as affecting a graded criterion or not, has not been done.
- **The second check is not independent.** It used the same model family, saw the first finding and its sources, and overturned 3%. It removes clear mistakes; it is not a substitute for a person reading the authorities.
- **Extraction varies between runs.** An interrupted rerun of the extraction step listed 3,872 instances, against 3,821 in the run reported here, with different instances in every task. Totals are therefore approximate at the level of a few percent; the problem findings themselves each rest on their own recorded source.
- **"Other" is a mixed category.** It includes agency guidance and pattern jury instructions, but also some contract provisions the extraction treated as authority; problems in it are less informative than those for cases and statutes.

## Method

1. **Text.** Each supplied document and `task.json` was converted to plain text: DOCX through pandoc with tracked changes shown, XLSX cell by cell including comments, EML through Python's `email` module, PPTX slide text, and `task.json` as formatted JSON. [`scripts/harvey_citation_check.py`](../../../../scripts/harvey_citation_check.py) `extract` reproduces these files byte for byte from the pinned commit.
2. **Extraction.** For each task, Claude Sonnet read every file in full, in batches of at most 200 KB, and listed every citation instance: authority, citation as written, pin cite, location, the proposition it is cited for, every quotation attributed to it, and whether the document makes it part of the fictional scenario. A second Sonnet pass reread the same files and added instances the first missed (422 of the 3,618) and reversed fictional labels on authorities cited as real law (14).
3. **First check.** Claude Opus 5.5 (high effort) checked each real-law citation, in groups of eight, against CourtListener first and otherwise against official court sites, Justia, Google Scholar case pages, Casetext, Cornell LII, GovInfo, the U.S. Code and eCFR sites, and official state legislature and court-rule sites. The agents were told not to rely on model memory: every status, including "verified," had to rest on text they read, with the URL and an excerpt recorded.
4. **Second check.** Each problem finding went to a separate Opus agent with the first finding and its sources, instructed to look for alternative spellings, parallel reporters, unpublished or related opinions, the quotation at another page, and fair readings that support the proposition, and to overturn the finding if it was wrong or overstated.

The checking runs were interrupted twice by usage limits. Completed checks were kept and only unfinished batches were rerun; no citation was checked twice. The extraction from the first run is the one reported. CourtListener was reached through its connector for most checks and through its website for some.

The status definitions given to the checking agents:

- **VERIFIED**: authority exists, citation correct, supports the proposition, quotes appear.
- **VERIFIED_MINOR_DEFECT**: supports the proposition but with a small defect (wrong pin page, quote with minor wording differences, loose parenthetical, wrong year).
- **MISCHARACTERIZED**: real authority, cited for a holding, rule, or facts it does not contain or contradicts.
- **MISQUOTED**: real authority, but quoted language does not appear in it (and the proposition is otherwise not clearly wrong).
- **WRONG_CITATION_REAL_CASE**: a real authority exists but the reporter, volume, page, court, year or party name is garbled.
- **CITATION_POINTS_TO_DIFFERENT_CASE**: the reporter cite is real but belongs to a different case than the one named.
- **NOT_FOUND_LIKELY_FABRICATED**: no such authority located after a thorough search (multiple name variants, reporters, courts, and web).
- **UNABLE_TO_VERIFY**: exists (or may exist) but the agent could not access text sufficient to check the proposition or quote.

`problems.md`, `summary.json`, and `results/` are written by `scripts/harvey_citation_check.py publish` from the combined output of the checking runs.
