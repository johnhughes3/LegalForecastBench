<!-- AI-generated research artifact. An AI classification agent prepared this report for the author of the LAB audit paper on November 8, 2026 (random seed 20261108); the author verified the C-051 quotation against the pinned task file. It is one reader's classification and is cited by the paper for the counts in Section 4.3. -->

# Fact-check: "rubrics almost all customized to a specific task; few test general principles" (agent report, 2026-11-08)

Question from the draft (Section 4.3, bracketed author note): are LAB and LegalReasonBench litigation rubrics almost all task-specific, with few testing general principles of writing and argumentation?

**Bottom line: confirmed for both benchmarks, with one quantifier nuance for LAB.** LRB is near-absolute (1 of 179 criteria is a general principle). LAB is "almost all" by any reasonable reading (87–96% task-specific depending on how doctrinal-knowledge checks are counted), but it contains a small stratum of general craft criteria (roughly 4–8%, about 1–3 per task), so "few" is accurate while "none" would not be.

## 1. Data and totals (reconcile exactly)

| | Source | Tasks | Criteria | Paper |
|---|---|---|---|---|
| LAB litigation | 52 task.json files fetched from harveyai/harvey-labs at commit 1dd81403 (local audit dirs hold only line pointers, not criterion text) | 52 | 2,858 | 2,858 |
| LRB litigation | local docs/legalreasonbench-audit/litigation/tasks/*/input.json (revision 1bfa904c) | 11 assignments / 4 matters | 179 (151 required, 28 penalty) | 179 |

LAB per-task criterion counts: min 25, median 52, max 89. LRB per assignment: 8–29.

## 2. Structural findings

- 2,858 of 2,858 LAB criteria (100%) are phrased "PASS if ... FAIL if ..." and every one begins with "PASS if."
- No task-level or global criteria in LAB. Top-level task.json keys are title, work_type, tags, instructions, deliverables, criteria; criterion keys are id, title, deliverables, match_criteria. The pinned judge prompt (lab_core/evaluation/prompts/rubric_criterion.txt) is purely per-criterion and layers no general quality instruction (accuracy, no fabrication, tone). The pinned docs/eval-strategies.md says: "Every task defines its rubric inline in task.json ... There is no separate gold standard file."
- LRB rubric items carry polarity, points, an optional irac_section (97 blank, 45 Application, 20 Rule, 11 Conclusion, 6 Issue), a source quote, and a justification. No global rubric field either.
- LAB title prefixes: 962 "ISSUE_nnn" (planted-issue spotting), 16 "DISTRACTOR", 10 "DOC", remainder untagged.

## 3. Keyword screen over the full population

LAB (N = 2,858): cite/citation 237 hits (8.3%), nearly all task-specific ("cites Section 4.2 for the Sengupta issue"); flag/caveat/limitation 282 (9.9%), near-zero precision; recommend 234 (8.2%), near zero; clear 40; structur/organiz 39/14; accura 34; authority 32; professional 12 (zero true hits); assum 9; invent/nonexistent/fictitious 10 (zero true hits: "inventor", "inventory"); fabricat 8 (zero hits about the model fabricating; all refer to fabricated facts in the record or "Irongate Fabrication Co."); hallucinat, tone, concise, plain language, every assertion, standard of review, bluebook/pincite: 0. A tight high-precision screen (minimum-N citations, record citations, non-leading form, priority tiers, recommendation coverage, chronological order, acknowledges ambiguity, internal consistency, TOC/TOA, executive summary, signature block, low/mid/high range) hits 67 criteria (2.3%), about 20 of them format checks.

LRB (N = 179): any-pattern union 22 (12.3%), nearly all false positives ("burden" = burden-of-proof statements of law). Tight screen: 0 hits.

Specificity markers: LAB criteria contain a dollar figure 14.8%, explicit date 19.3%, DOC/Bates/Exhibit/Line id 6.5%, section/statute cite 15.4%, numbered RFP/Count/Para 7.8%, named case 1.8%; any marker 56.5%. LRB names parties and events in prose rather than figures, so its marker rate (28.5%) understates its specificity.

## 4. Hand classification

Method: seed 20261108, random sample of 120 LAB criteria without replacement (44 of 52 tasks represented); all 179 LRB criteria read. Categories: (1) task-specific, split into (1a) record-specific content and (1b) doctrinal knowledge triggered by this record's issue; (2) general principle, split into (2a) cross-task craft/argumentation and (2b) standard practice component for the task type; (3) format/mechanics; (4) other.

LAB sample (n = 120):

| Category | Count | Share |
|---|---|---|
| (1a) record-specific substance | 94 | 78.3% |
| (1b) doctrinal knowledge tied to the record | 10 | 8.3% |
| (1) total task-specific | 104 | 86.7% |
| (2a) cross-task craft principle | 5 | 4.2% |
| (2b) general practice component for task type | 5 | 4.2% |
| (2) total general | 10 | 8.3% (approx. 95% CI 4.6–14.7%) |
| (3) format/mechanics | 6 | 5.0% |
| (4) other | 0 | 0% |

All ten LAB category-(2) criteria, verbatim:

(2a) cross-task craft:
1. draft-case-assessment-memorandum / C-043: "PASS if the damages section provides a damages range (low/mid/high or equivalent with dollar figures) for either individual categories or the total exposure. FAIL if no range estimate is provided."
2. draft-witness-examination-outline / C-031: "PASS if the direct examination questions are drafted in proper non-leading form ... FAIL if the direct examination questions are predominantly in leading form ..."
3. draft-witness-examination-outline / C-038: "PASS if the cross-examination preparation proposes specific redirect examination questions (not just general strategies) to rehabilitate Elliston for at least some of the anticipated attack vectors. FAIL if no specific redirect questions are proposed."
4. extract-key-obligations-from-litigation-hold-and-document-preservation-notice / C-048: "PASS if the memo cites specific paragraph numbers from the DOJ Preservation Notice ... At least 4 distinct paragraph number references must appear. FAIL if fewer than 4 paragraph references are cited." (boundary with format)
5. review-outside-counsel-engagement-letter-for-problematic-terms / C-033: "PASS if the memo provides a recommended course of action for at least 75% of identified issues, and at least three distinct recommendation types are used ... FAIL if recommendations are absent for the majority of issues, or if fewer than three distinct recommendation types appear across the memo."

(2b) standard practice components (boundary cases; a stricter reader would put these in (1)):
6. analyze-counterparty-requests-for-production / C-005: privilege log recommendation and/or warning against blanket waiver.
7. analyze-counterparty-requests-for-production / C-027: identifies that a FRE 502(d) order should be sought before production.
8. draft-deposition-outline / C-059: includes questions addressing the foundation for emotional distress or compensatory damages.
9. draft-discovery-plan-memorandum / C-063: discusses Rule 26(b)(1) proportionality.
10. draft-responses-to-interrogatories / C-016: statement that withheld privileged material will be identified on a privilege log per Rule 26(b)(5)(A).

The six format items: PI brief has a conclusion with prayer for relief (C-004); MIL has a distinct FRE 407 section (C-036); Opp-MTD has a separate DTSA/CUTSA section (C-043); Rog responses cover all 25 (C-002); witness outline contains Part 1 (C-057) and Part 3 (C-059).

LRB (all 179):

| Category | Count | Share |
|---|---|---|
| (1a) record-specific substance | 141 | 78.8% |
| (1b) statement of a legal rule from the closed research universe | 37 | 20.7% |
| (1) total task-specific | 178 | 99.4% |
| (2) general principle | 1 | 0.6% |
| (3) format | 0 | 0% |

The single LRB category-(2) criterion: lrb-dcca-challenge-police-discipline assignment-2 / criterion_8 (penalty, −22): "Mentions authority absent from the uploaded materials in support of the burden allocation." Four other LRB items reward specific instances of citation verification but are framed as record-specific findings (e.g., assignment-2 criterion_9, +30: the Award's citation to Douglas does not correspond to any page of the uploaded opinion). All 28 penalty items penalize a specific wrong fact or legal conclusion.

## 5. Footnote-ready numbers

Long form: "Of the 2,858 LAB litigation criteria at commit 1dd8140, every one is a 'PASS if ... FAIL if ...' check applied by a per-criterion judge prompt with no task-level or general quality rubric. In a seeded random sample of 120 criteria (one reader's classification), 104 (87%) required a particular fact, figure, party, document, argument or authority from the task's own record; 10 (8%; 95% CI roughly 5–15%) tested a general professional or drafting principle that would apply across tasks of that type (e.g., non-leading direct-examination questions, a low/mid/high damages range, recommendations for at least 75% of identified issues), of which only 5 (4%) were cross-task writing or argumentation principles; 6 (5%) checked format. Across the full population, no criterion mentions hallucination, tone, concision or plain language, and the only criterion addressing citation authenticity (draft-motion-for-preliminary-injunction C-051) requires 'at least three case law authorities (whether real or plausibly cited).' Of LegalReasonBench's 179 litigation criteria (revision 1bfa904), 178 require a specific fact, holding or legal rule from the matter's closed research universe; the sole exception is a penalty for citing 'authority absent from the uploaded materials.'"

Short form: "In a random sample of 120 LAB litigation criteria, 10 (8%) tested a general principle applicable across tasks of the same type, and only 5 (4%) a cross-task writing or argumentation principle; 1 of 179 LegalReasonBench litigation criteria did."

## 6. Side findings

- No anti-hallucination criterion exists in either benchmark. Zero LAB criteria mention hallucination; the 8 "fabricat" hits concern fabricated facts inside the record.
- LAB C-051 (draft-motion-for-preliminary-injunction) expressly credits "plausibly cited" authorities, so a fabricated case counts toward PASS. [Verified by the orchestrator against the task.json at commit 1dd81403: "PASS if the memorandum cites at least three case law authorities (whether real or plausibly cited) in support of its legal arguments across the various PI factors. FAIL if fewer than three cases are cited in the entire memorandum."]
- LAB's general-craft stratum is formulaic and recurs across tasks: recommendation-coverage thresholds (5), priority tiers / high-medium-low ratings (13), chronological ordering (4), record-citation requirements (3), "acknowledges ambiguity" (3), internal arithmetic consistency (1), non-leading form (1). Roughly 1–3 per task.
- LRB's "general" content is doctrinal (37 statements of law from the uploaded authorities) rather than craft; it has no format criteria.

## 7. Caveats

One reader's classification; the (1b)/(2b) boundary is the soft spot (strict reading 4% general; loose reading 12–15%; the claim survives either way). Litigation vertical only. Keyword screens over-count badly and were used only to surface candidates. The two benchmarks differ in grain (binary PASS/FAIL with all-pass scoring vs weighted reward/penalty), so the percentages are comparable in spirit, not as a like-for-like metric.
