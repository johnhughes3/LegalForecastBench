# Consistency pass: Claude Opus 5.5

Scope: all 25 review blocks in `docs/legalreasonbench-audit/litigation/human-review/worksheet.md`, read against the protocol (`docs/legalreasonbench-audit/litigation/human-review/README.md`), the tally (`stress-test/tally-at-review-start.txt`), the task prompts and attachments under `docs/legalreasonbench-audit/litigation/tasks/`, and primary sources where a call depends on them. I read nothing else under `stress-test/`. Nothing in the worksheet was edited.

## Bottom line

John applies his principles consistently in most of the review. The four Not defective items (7, 8, 11, 12) and the seventeen items flagged problematic by at least one model rest on reasons that hold up against the record and the law. The headline result is robust: under the most aggressive reclassification I can defend (seven boundary items moved to Arguable), the count is 15 of 25 Defective, an estimate of 38 of 63 and an exact one-sided 95% lower bound of 29. That is still a large share of the flagged set.

The review has four real consistency problems, ranked by their effect on the reported figures:

1. **Item 10 is not an unambiguous objective error.** John's own note concedes the rubric's proposition is "perhaps narrowly correct". The prompt's stipulations (a) and (b) and its second question are built to support MPD's burden argument. *Douglas* says a prima facie showing normally suffices when no one challenges the penalty. The real D.C. Court of Appeals told MPD it "is correct about its burden under Douglas". This is professional judgment at most, and arguably Arguable. Recoding the basis alone reduces the objective-error count from 7 to 6, the estimate from 18 to 15 of 63, and the lower bound from 11 to 9.
2. **Items 10 and 23 have the same structure but are coded differently on environment.** In both, a proposition from the real case was carried onto task facts that differ from it. Item 10 is coded environment origin No and environment Correct. Item 23 is coded origin Yes and environment Defective, on the ground that `Facts.pdf` "differs from the real record". Item 9 reinforces the point: the rubric expects a record feature that the record lacks, and John coded it origin No. A supplied record that departs from the real case is not an objective error in the supplied record. Also, `Facts.pdf` is byte-identical in VICAR assignment 1, where items 21 and 22 record a Correct environment. Item 23's origin should be No. The VICAR assignment 2 environment stays Defective because of the supplement-instruction problem (items 24–25).
3. **Item 16 records a Correct environment, while the six other sampled items in its assignment (FNC assignment 2) record Defective.** The protocol makes the environment verdict a property of the assignment, "whether or not [the defects] touch the sampled criterion". This is a clerical fix. It moves the environment count from 9 to 10 and the Defective × Defective cell from 9 to 10.
4. **There are no Arguable verdicts, although John's own notes use Arguable language in places.** He calls item 3 "really a judgment call" and item 15 "a closer call". Item 10 is conceded to be narrowly correct, and the instruction ambiguity behind items 24–25 cuts both ways. The protocol's "rejects a correct approach" rule supports his Defective calls on these items. The protocol's own Arguable definition fits them equally well. Report this as a disclosed sensitivity analysis, not as an edit.

The 14 Professional judgment Defectives, the 7 objective errors (6 after item 10), and the "States/Mentions" penalty family are otherwise coherent. The missing-affidavit family needs a better explanation, not different fields.

## Per-item matrix

Abbreviations: D = Defective, ND = Not defective; AI C/W = AI reasoning Correct/Wrong; OE = Unambiguous objective error; PJ = Professional judgment; Orig = defect arises from environment; Env = environment verdict. "Open" and "closed" give the research universe.

| Item | Matter / assignment | Direction, points | Universe | Recorded fields | Principle John applied | Consistency concern |
|---|---|---|---|---|---|---|
| 1 | Certiorari a1 | Penalty −15 | Open | D / C / OE / No / Correct | The penalty punishes a statement the record supports (Petition p. 19; the Order's "remained an active case"). Its only stated basis, AC-2-6 § 4.1B, applies only when the applicant caused the missed deadline. | Sound. The note calls the real litigation "ground truth", but the county's real position (withdrawn March 2022) also contradicts September 2023. The objective error is the rubric's February 2020 basis, not the truth of the September 2023 date. The "Related items" line groups this item with the "Mentions" penalties, although its main defect is a wrong legal premise. |
| 2 | Certiorari a1 | Penalty −30 | Open | D / C / PJ / No / Correct | The penalty rejects a construction pause that careful counsel would recommend. *Parkway Towers*' prospective guidance supports a pause. | Sound. The note says the case "says the opposite", which overstates: the holding's outcome fits the rubric, and the dictum cuts against it. PJ, not OE, is the right basis. |
| 3 | Certiorari a1 | Reward +20 | Open | D / C / PJ / No / Correct | A mandated strategy (appeal) among permissible options. John: many careful lawyers would advise against an appeal. | Arguable boundary. The note itself says "that's really a judgment call", and the real county did appeal. With a 30-day jurisdictional clock, a protective petition is a reasonable side. |
| 4 | Certiorari a1 | Reward +20 | Open | D / C / PJ / No / Correct | The remand is right, but "while an appeal is pending" imports item 3's mandate. | Follows item 3 and has the same boundary concern. Coding 3 and 4 alike is consistent. |
| 5 | Certiorari a1 | Reward +10 | Open | D / C / OE / No / Correct | § 163.3167(10) protects unchallenged orders from later invalidation of the regulations behind them. Subsection (10)(b) preserves certiorari. | Sound. |
| 6 | Certiorari a1 | Reward +5 | Open | D / C / OE / No / Correct | Same ground as item 1. | Sound, and consistent with item 1. |
| 7 | Certiorari a2 | Reward +5 | Open | ND / W / – / – / Correct | Evidence the supplied record refers to but does not include can be cited in an open universe, and a competent lawyer would cite it. | Sound. It is distinguished explicitly from the missing-affidavit items. |
| 8 | Certiorari a2 | Reward +5 | Open | ND / W / – / – / Correct | Same as item 7 (the staff report). | Sound. |
| 9 | DCCA a1 | Reward +28 | Closed | D / C / OE / No / Correct | The rubric rewards finding a date conflict that does not exist. | Sound as OE. It is the template for item 23: the rubric expects a record feature the record lacks, and John coded origin No here. |
| 10 | DCCA a2 | Reward +26 | Closed | D / C / OE / No / Correct | A real-case proposition carried onto changed facts. MPD relied on comparators, so *Douglas* puts the penalty burden on MPD. | **Basis is not unambiguous** (see Inconsistency 1). Origin No is right, and it is the coding item 23 should follow. |
| 11 | DCCA a3 | Reward +6 | Closed | ND / W / – / – / Correct | A demanding but defensible standard: a competent memo would flag PERB's 40-versus-45-day error. | The result is sound, but the note rests on "desirable training signal", which is not the protocol's test. The protocol's "demanding but defensible standard" reaches the same result. |
| 12 | FNC a1 | Reward +5 | Closed | ND / W / – / – / Correct | *Langenhorst* requires the defendant to show the plaintiff's forum is inconvenient to it, not merely that its own forum is more convenient. | Sound (219 Ill. 2d at 444, in the supplied PDF). |
| 13 | FNC a1 | Penalty −30 | Closed | D / C / PJ / No / Correct | A "Mentions" penalty that reaches a response that reports the defendants' argument and rebuts it. | Sound. It is stronger than the note says: the assignment 1 prompt requires the memo to note "what's strong" about *each* of the defendants' arguments, so mentioning this one is required. The native judges did not misfire here. |
| 14 | FNC a2 | Reward +3 | Closed | D / C / PJ / Yes / Defective | The criterion rewards citing affidavits that do not exist and that the closed universe says do not exist. | The fields are defensible, but the environment explanation ("the prompt does not instruct the model to create one") describes a rubric-only defect. That undercuts origin Yes (see Inconsistency 4). |
| 15 | FNC a2 | Reward +5 | Closed | D / C / PJ / Yes / Defective | Same as item 14, for the client's affidavit. | The note says "a closer call". Drafting a client affidavit to accompany a response is routine, so this is an Arguable boundary item. The explanation has the same problem as item 14's. |
| 16 | FNC a2 | Penalty −30 | Closed | D / C / PJ / No / **Correct** | The penalty punishes stating a true figure that a competent opposition must rebut. | The verdict is sound. **The environment field is inconsistent** with items 14, 15 and 17–20, which are in the same assignment (see Field agreement). |
| 17 | FNC a2 | Reward +3 | Closed | D / C / PJ / Yes / Defective | Same as item 14 (Montgomery, "supported by"). | Same as item 14. |
| 18 | FNC a2 | Reward +3 | Closed | D / C / PJ / Yes / Defective | Same as item 14 (Vance, inconvenience). | Same as item 14. It also has a second, unrecorded ground: "as required under *Langenhorst*" misstates the case, which puts the inconvenience showing on the defendant. |
| 19 | FNC a2 | Reward +3 | Closed | D / C / PJ / Yes / Defective | Same as item 18 (Montgomery). | Same as item 18. |
| 20 | FNC a2 | Reward +3 | Closed | D / C / PJ / Yes / Defective | Same as item 18 (Linwood). | Same as item 18. |
| 21 | VICAR a1 | Reward +15 | Closed | D / C / OE / No / Correct | The § 704.6(1) forcible-felony bar does not apply when the claimed "felony" is the very act said to be justified. | Sound, though the note leans on Florida authority. The objective footing in the supplied materials is stronger: § 702.11 does not list conspiracy, and the rubric's own justification for criteria 28–29 rejects the same circular theory for intimidation. |
| 22 | VICAR a1 | Penalty −5 | Closed | D / C / PJ / No / Correct | A "Mentions" penalty fires on a drafting note that sets the fact aside. | Sound, and consistent with items 13 and 16. The Correct environment holds only if `Facts.pdf` is not defective, which conflicts with item 23's coding. |
| 23 | VICAR a2 | Reward +25 | Closed | D / C / OE / **Yes** / Defective | The rubric contradicts the supplied facts ("He opened fire as the Trailblazer approached"). | OE is right. **Origin and environment explanation are inconsistent** with items 9, 10, 21 and 22 (see Inconsistency 2). |
| 24 | VICAR a2 | Reward +10 | Closed | D / C / PJ / Yes / Defective | Assignment 1 criteria are re-graded on a "supplement", which fails a response that writes only the new section. | Arguable boundary: the preamble's "final complete legal deliverable" supports reading the task as a full brief. The environment verdict rests on an instruction/verifier ambiguity, which fits neither prong of the protocol's environment definition. The aside on "parked" versus "stopped" reads as a possible second ground but is not one. |
| 25 | VICAR a2 | Reward +15 | Closed | D / C / PJ / Yes / Defective | Same as item 24. | Same as item 24. |

## Genuine inconsistencies (prioritized)

### Inconsistency 1 (high): item 10's "Unambiguous objective error" basis

**Items:** 10, compared with the other objective-error items (1, 5, 6, 9, 21, 23).

**Evidence.** The criterion says "no uploaded authority requires MPD to prove the comparability of its comparator cases". John's note concedes that "the statement the rubric wants is perhaps narrowly correct as a general proposition of law" and that *Douglas* sets no bright-line requirement. His objective-error finding rests on context: MPD's Final Notice itself relied on comparators.

Three things in the task as given point the other way:

- **The prompt sets up MPD's argument.** It tells the solver to treat as true that "(b) at no point before the arbitration hearing did Braddock or his union allege that MPD treated similarly situated employees differently". Question 2 asks who "bore the burden of production and persuasion on the comparator evidence at each stage" and asks for "the strongest position MPD can take". Stipulation (b) is MPD's real-case argument, that its burden arose only after the officer made an initial showing. The task kept that argument available even as it added the comparators.
- **The supplied *Douglas* text gives the argument a footing.** It says that "[w]hen no issue has been raised concerning the penalty, such a prima facie case will normally suffice", and that when the penalty is challenged the agency "will be called upon to present such further evidence as it may choose" (`douglas_v_veterans_admin.pdf`, PDF p. 22, printed p. 333).
- **The real court accepted MPD's position.** John's own source quotes the D.C. Court of Appeals in No. 24-CV-0573 (May 21, 2026): "MPD is correct about its burden under Douglas."

None of this shows that the rubric is right. It shows that the rubric is not contradicted by the record, the law or the cited authority in the "unambiguous" sense the protocol reserves for this basis. The other six objective-error items all turn on a text that plainly negates the rubric: the § 4.1B(1) applicant-fault condition, § 163.3167(10)(b), the comparator memo's dates, § 702.11 together with the rubric's own circularity reasoning, and the line in `Facts.pdf` that Nelson "opened fire".

**Strongest defense of John's coding.** MPD's own Final Notice made comparability an aggravating factor. Under *Douglas*, the agency bears "the ultimate burden" of persuading the decision-maker that the penalty is appropriate. A memo that tells MPD it need not substantiate the very comparators it relied on is misleading in this posture, whatever the abstract rule. Read that way, the categorical criterion fails the qualified answer a careful lawyer would give.

**Recommendation.**

- *Substantive field change.* Recode the basis to Professional judgment. Report this as a disclosed post-tally reviewer disagreement or sensitivity line, not a silent edit. Effect: objective errors fall from 7 to 6 of 25, the estimate from 18 to 15 of 63, and the secondary lower bound from 11 to 9. The Defective count is unchanged.
- A second sensitivity line should show item 10 as Arguable. Defective falls from 21 to 20 of 25, the estimate from 53 to 50 of 63, and the lower bound from 45 to 42.

### Inconsistency 2 (high): environment origin for real-case carry-overs (items 23 versus 10, and 9)

**Items:** 23, 10, 9, 21 and 22.

**Evidence.**

- **Item 10.** John describes a task "modified from the real case" (MPD now relies on comparators), with a rubric that "fail[s] to take into account how this task environment was modified". He codes origin No and environment Correct.
- **Item 23.** The pattern is the same, and John says so himself: "item 10 is the other sampled criterion that carries a real-case rule onto changed task facts." But he codes origin Yes and environment Defective, explaining that "the supplied statement of facts differs from the real record".
- **The protocol.** The environment verdict turns on "objective errors in the supplied record". A closed-universe record that departs from the real case is not an error in the supplied record. The protocol's own example is a fictional record that a response "can reasonably follow, even where it misstates real-world law", and that counts as Not defective.
- **What `Facts.pdf` is.** It reads as the government's Eighth Circuit statement of the case, citing trial transcript pages (TT-III 561-65). The Eighth Circuit's "it is unclear who shot first" is a court's characterization of disputed evidence. It does not show that the government's statement of facts was altered.
- **The same document in assignment 1.** `Facts.pdf` is identical in VICAR assignment 1, apart from its source-URL line. If it were defective, items 21 and 22 would also need a Defective environment, and they record Correct.
- **Item 9.** The rubric expects a date conflict that the supplied memo does not contain, and John codes it origin No and environment Correct.

**Strongest defense.** The task preserves the real names and record citations, so the authors plausibly meant `Facts.pdf` to reproduce the real trial record. The rubric's justifications in assignment 1 ("at a minimum, it is unclear which side fired first") show that the authors believed the record was ambiguous. On that view, the supplied facts are an unplanted departure from the intended record, which would make them an environment error.

**Recommendation.** *Substantive field change* to item 23's origin, from Yes to No. Reported as a disclosed sensitivity, "arising from the environment" falls from 9 to 8.

Item 23's environment verdict should stay Defective, because it is an assignment-level property and items 24–25 make VICAR assignment 2 Defective. Its explanation should then name the supplement-instruction problem (*note-only*). If John keeps origin Yes instead, VICAR assignment 1 (items 21 and 22) should record Defective for the same `Facts.pdf`. That alternative changes the environment table further (11 or 12 Defective) and is harder to defend.

### Inconsistency 3 (medium-high): the Arguable boundary, with zero Arguable verdicts

**Items:** 3 and 4 (most plausible); 10; then 15, 24 and 25.

**Evidence.** The protocol defines Arguable as "reasonable litigators could disagree about whether the criterion would misgrade a competent response". It adds that "borderline or low-impact concerns are Arguable". John's notes contain language that fits this definition:

- **Item 3.** "So this case does not seem to require an appeal — that's really a judgment call". The real county did appeal, and a 30-day jurisdictional deadline makes a protective petition a reasonable choice.
- **Item 15.** "This one is a closer call because the affiant is the client".
- **Items 24–25.** The prompt says "supplement your brief", but the preamble says "[w]rite the final complete legal deliverable for this assignment to `response2.md`. The verifier reads only that file." Each reading is reasonable, and reasonable readers could disagree about which the task requires.

**Strongest defense.** The protocol's rule for multiple permissible approaches makes a criterion Defective when "it rejects an approach a careful litigator would adopt on this record". A reward criterion for a mutually exclusive choice necessarily fails the alternative. If the alternative is one careful counsel would adopt, the rule's text supports Defective, and John applied it the same way to items 2, 3 and 4. For items 24 and 25, a criterion that fails a reasonable reading of the instructions falls under basis (d), a conflict with the instructions.

**Recommendation.** *Reporting.* Add a disclosed sensitivity table rather than changing verdicts:

| Scenario | Defective | Estimate of 63 | 95% lower bound |
|---|---|---|---|
| As recorded | 21 | 53 | 45 |
| Item 10 to Arguable | 20 | 50 | 42 |
| Plus items 3 and 4 to Arguable | 18 | 45 | 37 |
| Plus items 15, 24 and 25 to Arguable | 15 | 38 | 29 |

Bounds use the protocol's exact hypergeometric method (N = 63, n = 25), which reproduces the tally's 45 and 11. Also state that the protocol's two rules overlap: "requiring one permissible option is not by itself a defect" and "rejects an approach a careful litigator would adopt". In practice the line runs through cases where the real-world client chose the option the rubric requires. This is where an independent second lawyer would add the most.

### Inconsistency 4 (medium): the missing-affidavit environment explanation contradicts the origin field

**Items:** 14, 15 and 17–20.

**Evidence.**

- **The fields.** Origin is Yes and the environment is Defective.
- **The explanation.** "No affidavit ... is provided in the environment, and the prompt does not instruct the model to create one." That describes a record that is complete and a criterion that demands something outside it, which is a rubric-only defect: protocol reason (a) or (c), origin No. The item 14 note also blames the rubric: "the practical effect of this rubric seems to be to nudge the model".
- **What actually supports a Defective environment.** The materials do contain a genuine defect that John's sources already quote. The assignment 2 prompt says "Please include all affidavits and information you referenced from Assignment #1", while the same prompt's closed-universe rule says "If a document is not uploaded, it does not exist." No physician or client affidavit was referenced in assignment 1; the only affidavit in the record is Dr. Smith's. The instruction therefore presupposes affidavits that cannot exist, and it pushes the solver toward a brief that cites unexecuted affidavits as sworn. That fits the protocol's second prong: "materials that direct work product a competent litigator should not put before a court."

**Recommendation.** *Note-only.* Rewrite the six environment explanations to name the conflicting instruction. That keeps the fields and makes them agree with the explanation.

If John concludes instead that the instruction does not direct affidavits, the coherent alternative is origin No and environment Correct for all seven FNC assignment 2 items. That would be a *substantive field change*, cutting the environment count to 3 and origin to 3. I do not recommend it.

### Inconsistency 5 (medium-low): items 24–25's environment verdict sits outside the protocol's definition

**Items:** 24 and 25, which also carry item 23's environment verdict, compared with the assignment-label issue in item 15.

**Evidence.** The environment explanation is an ambiguous instruction combined with a verifier that reads only `response2.md`. That is neither an objective error in the supplied record nor material that directs improper work product. It is a defect in how the task is built and graded. John treats the analogous grading problem in item 15 differently: criteria that name an assignment number the judge cannot see are "an overarching issue in the benchmark setup", recorded in neither the rubric nor the environment fields.

**Strongest defense.** "Defect arises from environment" is defined more broadly ("an error in the supplied task materials"), and the instruction is part of the task materials. An instruction that does not say what deliverable it wants is a fair candidate for an error in them.

**Recommendation.** *Note-only / reporting.* State in the environment table's caption that VICAR assignment 2's Defective environment rests on an instruction/verifier mismatch, a broader reading than the protocol's two prongs. Optionally show it as a sensitivity line: with item 16 corrected and VICAR assignment 2 moved to Correct, environment Defective would be 7 of 25 items, in 1 of 9 assignments. Do not change the fields.

### Inconsistency 6 (low): "Related items" groupings

Item 1 is listed with items 13, 16 and 22 as a penalty "worded 'States' or 'Mentions' that can reach a response rebutting ... the point". Item 1's penalty is defective because the penalized proposition is supported by the record, not because the verb reaches a rebuttal. Item 16 is a hybrid: a true statement that the response must address. *Note-only:* split the cross-reference into (i) penalties on true or record-supported statements (1, 16) and (ii) wording that reaches a rebuttal or a set-aside (13, 22, and 16 in part).

## The objective-error versus professional-judgment line

On the whole, John reserves "Unambiguous objective error" for cases where a text negates the rubric:

- the code's applicant-fault condition (items 1 and 6);
- the statute's own savings clause (item 5);
- the comparator memo's dates (item 9);
- the unlisted conspiracy offense together with the rubric's own circularity reasoning (item 21);
- the supplied facts (item 23).

He codes PJ where the criterion takes a contestable professional position that misgrades work careful counsel would produce: penalties on prudent or required content (2, 13, 16, 22), mandated strategy (3, 4), affidavits that do not exist (14, 15, 17–20), and deliverable scope (24, 25). That is the protocol's line, applied evenly.

Item 10 is the one exception (Inconsistency 1).

The missing-affidavit items could be argued the other way, as objective: the rubric expects a statement that the closed record says is false. John's PJ coding is the better reading, because the prompt's "include all affidavits" makes the propriety of drafting them, not the record, the real question. Item 2 is correctly PJ despite the note's strong language: the rubric quotes *Parkway Towers* accurately, and the dispute is over its weight.

Items 18–20 have an additional ground that would support OE if John wanted it. Each says the physician's affidavit shows DuPage is inconvenient "as required under *Langenhorst*". *Langenhorst* places the inconvenience showing on the defendant ("The defendant must show that the plaintiff's chosen forum is inconvenient to the defendant"; "the defendant cannot assert that the plaintiff's chosen forum is inconvenient to the plaintiff"; supplied PDF, 219 Ill. 2d at 444). Nothing in it requires the plaintiff's witnesses to swear that the alternative forum is inconvenient. *Note-only:* record it as a supporting ground. Changing the basis is not warranted, because the main defect is the missing affidavits.

## The Arguable boundary

The 21 / 0 / 4 distribution does not follow mechanically from the protocol, and it does not show misapplication either. It follows from two features:

- **John resolves the overlap between the protocol's rules toward Defective.** The rules are "requiring one permissible option is not a defect" and "rejecting a correct one is". Whenever the alternative the criterion forecloses is one careful counsel would adopt, he calls the criterion Defective. That reading of the text is reasonable. Applied consistently, it leaves Arguable almost no room in the cases where it would otherwise apply.
- **Descriptively, the verdicts track the strongest blind AI label.** All 17 items with a problematic flag are Defective. The 8 items whose strongest flag was arguable split 4 Defective (3, 4, 10, 13) and 4 Not defective (7, 8, 11, 12). This is not evidence of deference: John departs from the reconciliation on 8 items it did not retain (14, 15, 17–20, 24, 25) and gives independent sources throughout. But it is the pattern a reader will notice.

The four arguable-flag items he coded Defective show the boundary. Item 13 is sound as Defective: the prompt requires discussing every defense argument, so the "Mentions" penalty reaches required content. Items 3, 4 and 10 are the closest calls. Items 15, 24 and 25 are borderline for the reasons given above. The sensitivity table under Inconsistency 3 is the right way to report this.

## Rubric versus environment defects

The structure John uses is sound:

- **Environment-only defects.** The sample has none. No Not defective item has a Defective environment, and nothing was miscoded on that score.
- **Planted errors.** Item 11's PERB misstatement is treated as a planted error, environment Correct, as the protocol requires.
- **Referenced but unsupplied evidence.** Items 7 and 8 have a Correct environment. John distinguishes them from items 14–20 in item 14's note: there the evidence exists in the record, while the affidavits have not been signed. That distinction is principled.
- **The assignment-label wording problem** is recorded in neither field (see Inconsistency 5 for the contrast with items 24–25).

The problems are the ones above: item 23's origin (Inconsistency 2), item 16's environment field (Field agreement), the affidavit explanation (Inconsistency 4), and the definitional stretch for VICAR assignment 2 (Inconsistency 5).

Combined effect on the environment table if the recommended changes are disclosed:

| Version | Environment Defective (items) | Defective × Defective | Defective × Correct | Arising from environment | Assignments with a Defective environment |
|---|---|---|---|---|---|
| As recorded | 9 | 9 | 12 | 9 | 2 of 9 |
| Item 16 clerical fix | 10 | 10 | 11 | 9 | 2 of 9 |
| Plus item 23 origin to No | 10 | 10 | 11 | 8 | 2 of 9 |

## Field-agreement problems

- **Item 16, environment field (clerical).** It records Correct, while every other sampled item in FNC assignment 2 records Defective. The protocol makes the environment verdict a property of the assignment. Item 16 should read Defective, with origin left at No, because its defect (the 60.5% penalty) does not stem from the missing affidavits. It would then be the sample's only Defective-environment item whose own defect is independent of the environment, a useful illustration for readers. The tally script does not check environment consistency within an assignment (`scripts/legalreasonbench_review_sample.py`, environment counter at about lines 520–531). A one-line warning there would catch this in future reviews.
- **Item 23, environment explanation (note-only).** Under assignment-level coding it should match items 24 and 25 and name the supplement-instruction defect.
- **Items 14, 15 and 17–20, environment explanation (note-only).** See Inconsistency 4.
- **AI reasoning.** This field is consistent throughout. Every Not defective item is Wrong, as the protocol requires. Every Defective item is Correct, and in each case a flagging model's blind reason is the ground John relies on. I checked each: Sol F2/Opus O1 (items 1, 6), Sol F6/Opus O6 (2), Sol F7 (3, 4), Sol F5/Opus O2 (5), Sol F1/Opus O1 (9), Sol F2/Opus O2 (10), Opus O2 (13), Sol G1 (14, 17–20), Sol G2/Opus O2 (15), Sol G3/Opus O1 (16), Sol G1 (21), Sol G2 (22), Sol G1/Opus O1 (23), Sol G2/Opus O3 (24, 25). "Partly correct" is never used, and I found no item that needed it.
- **Names in the affidavit items.** Items 14 (Vance, "supported by"), 17 (Montgomery, "supported by"), 18 (Vance, inconvenience), 19 (Montgomery, inconvenience) and 20 (Linwood, inconvenience) all match their criteria. There is no clerical error.
- **Item 11's note** rests the Not defective verdict on training value ("a desirable training signal") rather than on whether a permissible competent response is misgraded. The verdict holds under the protocol's "demanding but defensible standard". *Note-only:* restate the reason in those terms.
- **Item 24's note** remarks that `Facts.pdf` says "parked" and that "stopped" tracks the real opinion. A reader could take this as a second ground. "Parked" supports "already stopped", so it is not one. *Note-only:* say that it is context only.

## Proposed clearer groupings and explanations, mapped to existing fields

These are reporting tables built from the recorded fields, not new fields or categories.

**1. A root-cause table** (rubric verdict and defect basis, grouped by the note's ground):

| Group | Items | Basis as recorded | Reporting language |
|---|---|---|---|
| Rubric relies on a wrong legal premise | 1, 5, 6, 21; 10 (contested) | OE (10 is contested) | "The rubric's stated rule is negated by the statute, code or cited authority." |
| Rubric contradicts the supplied record | 9, 23 | OE | "The expected answer is contradicted by the documents the solver was given." |
| Penalty reaches prudent, accurate or required content | 2, 13, 16, 22 | PJ | "The penalty would fall on work careful counsel would produce, including a rebuttal of the opponent's point." |
| Rubric mandates one of several permissible strategies | 3, 4 | PJ | "The rubric rewards one strategy and fails a strategy careful counsel would choose." |
| Rubric presupposes evidence that does not exist | 14, 15, 17–20 | PJ, origin Yes | "The rubric rewards citing affidavits that the closed record says do not exist." |
| Sequential re-grading of a supplement | 24, 25 | PJ, origin Yes | "Assignment 1 criteria are re-graded on an assignment 2 supplement whose required form is unclear." |
| Not defective | 7, 8, 11, 12 | – | "The flag fails: the criterion is demanding but defensible, or it applies the correct standard." |

**2. A count of independent underlying problems.** This adds to the README's caveat that criteria are not independent mistakes. The 21 Defective criteria rest on about 13 distinct problems: {1, 6}, 2, {3, 4}, 5, 9, 10, 13, {14, 15, 17–20}, 16, 21, 22, 23, {24, 25}. Reporting the count alongside 21 of 25 prevents the six-item affidavit cluster from reading as six separate failures.

**3. Explain the two environment columns separately.** "Defect arises from environment" (origin, Defective items only) answers whether the task materials caused this criterion's defect. "Environment" (all items, assignment-level) answers whether the assignment's materials are defective anywhere. Saying this in the table caption heads off the most likely misreading: that a Defective × Defective cell means the environment caused the defect. After the item 16 fix, item 16 illustrates the difference.

**4. Split the objective errors by source.** Law or authority covers items 1, 5, 6 and 21 (plus 10 if kept). The supplied record covers items 9 and 23. Readers care whether a rubric got the law wrong or misread its own documents.

## Points checked and found sound

- **Items 1 and 6.** They are coded identically on the same ground. The § 4.1B(1) applicant-fault condition is in both the 2015 and the 2022 archived text John cites. Neither the supplied record nor either party's real position supports a February 2020 withdrawal.
- **Item 5.** § 163.3167(10)(b) expressly preserves "a common law writ of certiorari proceeding", so OE is right.
- **Item 9.** The comparator memo's cases (August 2018 to October 2021) fall within its stated 2018–2021 window. This is a clean OE.
- **Item 21.** The supplied § 702.11 does not list conspiracy, and the rubric's own justification for criteria 28–29 calls the parallel intimidation theory circular. OE holds even without the Florida authority.
- **Item 23.** `Facts.pdf` (PDF p. 7) says Nelson "opened fire as the Trailblazer approached", and the assignment 2 prompt confines the solver to the attachments. The Defective verdict and the OE basis are right; only the origin is disputed.
- **Items 7 and 8 against items 14–20.** The distinction between evidence that already exists and is referenced in the record, and affidavits not yet signed, is principled and applied evenly.
- **Item 12.** *Langenhorst*'s inconvenience-to-the-defendant requirement appears in the supplied PDF, and Dr. Smith's affidavit says only "substantially more convenient". Not defective is correct.
- **Items 13, 16 and 22.** They are coded alike (Defective, PJ, origin No). Native runs misfired on 16 (3/3 against both models) and 22 (2/3 against Opus). Item 13's Defective verdict rests on the prompt's requirement to assess each defense argument.
- **Item 2.** PJ, not OE, is right. The rubric quotes *Parkway Towers* accurately, and the dispute is over what its prospective guidance means for a county that has already started building.
- **Items 3 and 4.** They are coded identically, which is right given that item 4's "while an appeal is pending" imports item 3's mandate.
- **The assignment-label issue.** Treating it as a global benchmark-setup issue rather than a rubric defect is applied uniformly. Coding it per criterion would make all 90 labeled criteria Defective, which would be over-inclusive. *Reporting:* disclose it once as a global grading-harness observation, with John's vote counts (Sonnet 5 cited the missing label in 10 of 1,074 votes and never changed a majority).
- **Clerical identity checks** passed: affidavit names, criterion directions and points, and research universes all match the worksheet entries and the task `input.json` files I checked.
