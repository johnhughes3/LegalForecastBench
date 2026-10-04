# Claude Opus 5.5 (low): Review Counterparty's Proposed Jury Instructions — Issue Memorandum for Trade Secrets Trial

> [!NOTE]
> **Unedited model output and AI judge grades.** The deliverables are AI-generated drafts on Harvey LAB's fictional task records. Pass/fail verdicts are the native LAB judges' AI judgments, not human review or accepted corrections. See the [model-runs overview](../../README.md).

[Task audit page](../../../tasks/review-counterpartys-proposed-jury-instructions/README.md) · [Pinned task and rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json) · [GPT-6 Luna (xhigh) run](../gpt6luna-xhigh/README.md) · [All runs](../../README.md)

**Model:** `claude-opus-5-5`, reasoning effort `low`. **Run:** `20260926-202411`.

**Native grades:** Sonnet 4.6 passed 31 of 33 criteria; GPT-5.5 passed 31 of 33 criteria. LAB all-pass score: 0 (mean of the judges' all-pass results; a task scores 1 with a judge only if every criterion passes).

## Deliverables

- [jury-instruction-issues-memo.docx](output/jury-instruction-issues-memo.docx) ([read as Markdown](output/jury-instruction-issues-memo.docx.md))

## Grades

Failures are in bold. Each criterion links to both judges' reasoning below.

| Criterion | Title | Sonnet 4.6 | GPT-5.5 |
|---|---|---|---|
| [C-001](#c-001) | Identifies Issue with Instruction No. 14 including dismissed SignalSift category | Pass | Pass |
| [C-002](#c-002) | Cites summary judgment order as source for SignalSift dismissal | Pass | Pass |
| [C-003](#c-003) | Explains prejudice from including dismissed SignalSift category | Pass | Pass |
| [C-004](#c-004) | Identifies improper 'novelty' requirement in Instruction No. 12 | Pass | Pass |
| [C-005](#c-005) | Explains that Georgia Trade Secrets Act does not require novelty | Pass | Pass |
| [C-006](#c-006) | Identifies omission of disclosure/use prong in Instruction No. 16 | Pass | Pass |
| [C-007](#c-007) | Explains that omission of disclosure/use prong removes Oakvale's theory against Axial | Pass | Pass |
| [C-008](#c-008) | Identifies argumentative second sentence in Instruction No. 23 (inevitable disclosure) | Pass | Pass |
| [C-009](#c-009) | Cites court's ruling on inevitable disclosure as limited to standalone theory | Pass | Pass |
| [C-010](#c-010) | Identifies 'adequacy' vs. 'reasonableness' error in Instruction No. 13 | Pass | Pass |
| [C-011](#c-011) | Notes Instruction No. 13 omits totality-of-circumstances standard | Pass | Pass |
| [C-012](#c-012) | Identifies improper unanimity requirement on damages theories in Instruction No. 30 | Pass | Pass |
| [C-013](#c-013) | Explains that O.C.G.A. § 10-1-763(a) permits both lost profits and unjust enrichment | Pass | Pass |
| [C-014](#c-014) | Notes no federal civil procedure requirement for unanimity on damages theories | Pass | Pass |
| [C-015](#c-015) | Identifies misstated punitive damages standard in Instruction No. 32 | Pass | Pass |
| [C-016](#c-016) | Explains correct punitive damages standard under O.C.G.A. § 10-1-763(b) | Pass | Pass |
| [C-017](#c-017) | Identifies narrowing of breach of contract claim in Instruction No. 25 | Pass | Pass |
| [C-018](#c-018) | References Employment Agreement's broad definition of Confidential Information | Pass | Pass |
| [C-019](#c-019) | Identifies improper 'independently wrongful act' element in Instruction No. 27 | Pass | Pass |
| [C-020](#c-020) | Explains distinction between tortious interference with contract vs. business relations | **Fail** | **Fail** |
| [C-021](#c-021) | Identifies improper fault apportionment instruction in No. 29 | Pass | Pass |
| [C-022](#c-022) | Notes failure to mitigate defense was withdrawn at pretrial conference | Pass | Pass |
| [C-023](#c-023) | Notes comparative fault does not apply to intentional tort claims | **Fail** | **Fail** |
| [C-024](#c-024) | Identifies conflict between Instruction No. 21 and the discovery sanctions order | Pass | Pass |
| [C-025](#c-025) | References the September 5, 2024 sanctions order as authority | Pass | Pass |
| [C-026](#c-026) | Identifies argumentative 'particular skepticism' language in Instruction No. 31 | Pass | Pass |
| [C-027](#c-027) | References Eleventh Circuit Pattern Instruction 3.5 as proper standard | Pass | Pass |
| [C-028](#c-028) | Provides recommendation for each identified issue | Pass | Pass |
| [C-029](#c-029) | Identifies at least some unobjectionable instructions | Pass | Pass |
| [C-030](#c-030) | Memo identifies correct case name and parties | Pass | Pass |
| [C-031](#c-031) | Memo identifies correct case number and court | Pass | Pass |
| [C-032](#c-032) | Describes potential prejudice to Oakvale for each flagged issue | Pass | Pass |
| [C-033](#c-033) | Distinguishes flatly wrong instructions from subtly misleading ones | Pass | Pass |

## Judge reasoning

### C-001

Identifies Issue with Instruction No. 14 including dismissed SignalSift category ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L18))

- **Sonnet 4.6: Pass.** The memo explicitly addresses Instruction No. 14 in Section III.C, identifying that it lists seven categories including '(7) a machine-learning feature selection methodology known as SignalSift' and that this is improper because the SJ Order dismissed category 7 with prejudice. The memo cites the controlling authority (SJ Order §IV.B.3 and Order ¶1) and recommends deleting item (7) and changing the lead-in to 'the following six categories.' This is also flagged as CRITICAL in the Priority Summary Table.
- **GPT-5.5: Pass.** The memo explicitly flags Defense Proposed Instruction No. 14 as critical because it lists seven trade-secret categories including category 7, SignalSift, and states that the SJ Order dismissed SignalSift with prejudice and the jury should not consider it. It recommends deleting item (7).

### C-002

Cites summary judgment order as source for SignalSift dismissal ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L26))

- **Sonnet 4.6: Pass.** The memo explicitly references the SJ Order (January 12, 2025 Summary Judgment Order) as the controlling authority for the SignalSift/category 7 dismissal. In Section II (Priority Summary Table), it cites 'SJ Order §IV.B.3, ¶1; Minutes §III' for Instruction No. 14. In Section III.C, it states: 'Controlling authority. SJ Order §IV.B.3 and Order ¶1: SignalSift is "DISMISSED WITH PREJUDICE. . . . The jury will not be asked to consider whether SignalSift is a protectable trade secret, as that question has been resolved as a matter of law."' This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The memo explicitly identifies the January 12, 2025 Summary Judgment Order as the basis for excluding SignalSift/category 7, stating that the SJ Order dismissed category 7 with prejudice and that the jury will not be asked to consider it. It also cites SJ Order §IV.B.3 and Order ¶1 in the dedicated discussion of Instruction No. 14.

### C-003

Explains prejudice from including dismissed SignalSift category ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L34))

- **Sonnet 4.6: Pass.** In Section III.C (Instruction No. 14), the memo states: 'Leaving SignalSift in front of the jury invites an argument that one "lost" category undermines the others.' This explains the potential prejudice to Oakvale — specifically that including the dismissed SignalSift category could suggest to the jury that Oakvale is over-claiming or that its trade secret case is weaker, as defendants could argue that losing one category casts doubt on the remaining six. This constitutes an explanation of prejudice (jury confusion / suggestion that Oakvale is over-claiming / undermining the other categories).
- **GPT-5.5: Pass.** The memo specifically addresses prejudice from including the dismissed SignalSift category, noting that leaving it before the jury could invite an argument that Oakvale’s loss on one category undermines the others, and it also emphasizes that the jury should not be asked to consider the resolved category.

### C-004

Identifies improper 'novelty' requirement in Instruction No. 12 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L42))

- **Sonnet 4.6: Pass.** Section III.J of the memo explicitly addresses Instruction No. 12 and states: 'The first sentence defines a trade secret as information that is "novel."' It then cites the SJ Order: '"The GTSA does not require that the information claimed as a trade secret be novel or represent an advance over the prior art."' The recommended objection says 'Delete "novel."' This clearly identifies the improper novelty requirement as an error.
- **GPT-5.5: Pass.** The memo explicitly flags Instruction No. 12 as adding a novelty requirement: the summary lists 'No. 12: adds a "novel" requirement,' and Section III.J states that the instruction defines a trade secret as information that is 'novel' and recommends deleting 'novel.'

### C-005

Explains that Georgia Trade Secrets Act does not require novelty ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L50))

- **Sonnet 4.6: Pass.** Section III.J of the memo explicitly addresses Instruction No. 12 and states: 'The SJ Order §IV.B.1: "The GTSA does not require that the information claimed as a trade secret be novel or represent an advance over the prior art."' The memo recommends deleting 'novel' from the instruction and using the statutory text of §10-1-761(4) verbatim. It also references the statutory elements (independent economic value from not being generally known, reasonable measures to maintain secrecy) throughout the document. This clearly articulates that novelty is not a statutory element under the Georgia Trade Secrets Act.
- **GPT-5.5: Pass.** The memo expressly flags Instruction No. 12 for improperly adding a “novel” requirement and states that the GTSA “does not require that the information claimed as a trade secret be novel or represent an advance over the prior art.” It also discusses the statutory trade-secret elements, including economic value from not being generally known and reasonable secrecy measures under O.C.G.A. § 10-1-761(4).

### C-006

Identifies omission of disclosure/use prong in Instruction No. 16 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L58))

- **Sonnet 4.6: Pass.** Section III.E of the memo explicitly identifies that Instruction No. 16 'defines misappropriation only as acquisition . . . by a person who knows or has reason to know that the trade secret was acquired by improper means' and 'leaves out the statutory disclosure or use prong entirely, including use by someone who acquired the information under a duty to keep it secret.' It cites O.C.G.A. §10-1-761(2)(A)--(B) and the SJ Order, and recommends replacing No. 16 with the full statutory definition covering both acquisition and disclosure/use. This directly satisfies the criterion.
- **GPT-5.5: Pass.** The memo expressly flags Instruction No. 16 as defining misappropriation only by acquisition through improper means and states that it omits the statutory disclosure/use prong, including use or disclosure by someone under a duty to maintain secrecy. It cites O.C.G.A. § 10-1-761(2)(A)--(B) and recommends replacing No. 16 with the full statutory definition.

### C-007

Explains that omission of disclosure/use prong removes Oakvale's theory against Axial ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L66))

- **Sonnet 4.6: Pass.** In Section E (Instructions No. 16, 17 and 22), the memo explicitly states: 'Dr. Voss obtained Oakvale's information lawfully while employed, so an acquisition-only definition would effectively take the core use/disclosure theory away from the jury.' This directly connects the omission of the disclosure/use prong to the impact on Oakvale's case theory. However, the criterion specifically asks whether the memo explains the impact on Oakvale's theory against Axial (the corporate defendant), not just Dr. Voss. The memo does mention Axial in the context of No. 22 ('Use in New Employment') and the recommended alternative for No. 22 references 'the defendant actually misappropriated,' but the specific connection to Axial's liability for using or disclosing trade secrets (as opposed to Dr. Voss's) is not explicitly drawn out. The memo focuses on Dr. Voss's lawful acquisition and the use/disclosure theory generally, but does not separately articulate that omitting the use/disclosure prong eliminates the theory that Axial (as a corporate entity) is liable for using or disclosing the secrets. That said, the memo does discuss Axial throughout and the use/disclosure prong analysis implicitly covers both defendants. The language 'effectively take the core use/disclosure theory away from the jury' is broad enough to encompass the theory against Axial, and the instruction numbers 16/22 are titled to include 'Use in New Employment' which relates to Axial's context. The connection is present but not explicitly stated as 'Axial's liability for use/disclosure.' Given the criterion asks whether the memo 'connects the omission to the impact on Oakvale's case theory against Axial,' and the memo does not explicitly name Axial in this context (only Dr. Voss), this is a borderline case. However, reading the memo holistically, the analysis of No. 22 ('Use in New Employment') is clearly about Axial's use of the secrets in the new employment context, and the recommended revision addresses 'the defendant' broadly. The memo does make the connection sufficiently to satisfy the criterion.
- **GPT-5.5: Pass.** The memo identifies that Instruction No. 16 omits the statutory disclosure/use prong and states that an acquisition-only definition would “effectively take the core use/disclosure theory away from the jury.” It also frames the corrected instruction to cover whether “Dr. Voss or Axial actually acquired, used, or disclosed Oakvale’s trade secrets.” This connects the omission to the loss of Oakvale’s use/disclosure theory against Axial, not merely acquisition.

### C-008

Identifies argumentative second sentence in Instruction No. 23 (inevitable disclosure) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L74))

- **Sonnet 4.6: Pass.** The memo explicitly addresses Instruction No. 23 in Section D, distinguishing between the first paragraph (which it acknowledges is consistent with the SJ Order regarding inevitable disclosure as an independent basis for liability) and the second paragraph (which it identifies as improper because it states that job similarity 'is not evidence of misappropriation'). The memo cites the SJ Order §IV.C, which holds that job similarity 'is one piece of circumstantial evidence the jury may consider as part of the totality of the evidence.' The memo proposes alternative language that preserves the bar on finding misappropriation solely from competitive employment while allowing job similarity to be considered as circumstantial evidence. This directly satisfies the criterion.
- **GPT-5.5: Pass.** The memo expressly distinguishes Instruction No. 23's first paragraph as consistent with the SJ Order because Georgia does not recognize inevitable disclosure as an independent basis for liability, while identifying the second paragraph/sentence stating that Dr. Voss's similar position at Axial “is not evidence of misappropriation” as improper. It explains that the SJ Order permits job similarity as circumstantial evidence the jury may consider with the totality of the evidence and proposes alternative language reflecting that distinction.

### C-009

Cites court's ruling on inevitable disclosure as limited to standalone theory ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L82))

- **Sonnet 4.6: Pass.** Section D of the memo (Instruction No. 23 — Inevitable Disclosure Doctrine) explicitly addresses the scope of the court's ruling. It states that the first paragraph of the instruction, which says Georgia does not recognize inevitable disclosure as an independent basis for liability, is consistent with the SJ Order, while the second paragraph is not. It then cites SJ Order §IV.C for the proposition that job similarity 'is one piece of circumstantial evidence the jury may consider as part of the totality of the evidence,' and notes the Court's distinction 'between a legal presumption (which is impermissible) and an evidentiary inference drawn from the totality of the evidence (which is permissible).' The memo also notes the Court prohibited only an instruction that misappropriation 'may be inferred solely from Dr. Voss's competitive employment.' This clearly explains that the ruling rejected inevitable disclosure only as a standalone/independent basis for liability, not as a bar on circumstantial evidence of job similarity, satisfying the criterion.
- **GPT-5.5: Pass.** The memo expressly explains that the court's inevitable-disclosure ruling only bars using inevitable disclosure/competitive employment as an independent or standalone basis for liability, while allowing job similarity as circumstantial evidence of actual misappropriation under the totality of the evidence. It cites the SJ Order §IV.C and distinguishes impermissible legal presumption from permissible evidentiary inference.

### C-010

Identifies 'adequacy' vs. 'reasonableness' error in Instruction No. 13 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L90))

- **Sonnet 4.6: Pass.** In Section III.L, the memo explicitly states that Instruction No. 13 'asks whether security was "inadequate" as to any category' and recommends replacing '"inadequate" with "not reasonable under the circumstances."' This directly identifies the substitution of 'adequate/inadequate' for the statutory 'reasonable' standard as a legal error.
- **GPT-5.5: Pass.** The memo expressly flags Instruction No. 13 for using an “inadequate” security standard and states that the correct standard is whether measures were “reasonable under the circumstances,” recommending replacement language. This satisfies the criterion.

### C-011

Notes Instruction No. 13 omits totality-of-circumstances standard ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L98))

- **Sonnet 4.6: Pass.** In Section III.L, the memo explicitly states that Instruction No. 13 'never says the measures need only be "reasonable under the circumstances" and not perfect' and 'leaves out the size and sophistication of the business and the totality of the circumstances.' The recommended alternative also says to 'replace "inadequate" with "not reasonable under the circumstances"' and 'Add that reasonable measures do not require perfect or absolute secrecy and that the jury may consider the nature of the information and the size and circumstances of the business.' This directly addresses both the missing totality-of-circumstances standard and the principle that perfect security is not required.
- **GPT-5.5: Pass.** The memo specifically states that Instruction No. 13 fails to say security measures need only be “reasonable under the circumstances,” “not perfect,” and that it leaves out the “totality of the circumstances.”

### C-012

Identifies improper unanimity requirement on damages theories in Instruction No. 30 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L106))

- **Sonnet 4.6: Pass.** Section III.G of the memo explicitly addresses Instruction No. 30 and identifies that it 'tells the jury it must unanimously agree on which category of damages --- lost profits or unjust enrichment --- to award. You may not award both.' The memo flags this as improper, citing O.C.G.A. §10-1-763(a) and the SJ Order, and proposes alternative language that allows both measures subject to a non-duplication requirement. This directly satisfies the criterion.
- **GPT-5.5: Pass.** The memo expressly flags Instruction No. 30 as problematic because it tells the jury it “must unanimously agree on which category of damages — lost profits or unjust enrichment — to award” and that the jury “may not award both.” It further explains this improperly makes the measures mutually exclusive and imposes a unanimity requirement on the choice of damages measure.

### C-013

Explains that O.C.G.A. § 10-1-763(a) permits both lost profits and unjust enrichment ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L114))

- **Sonnet 4.6: Pass.** Section III.G of the memo explicitly addresses Instruction No. 30 and cites O.C.G.A. §10-1-763(a), quoting that a complainant 'may recover damages for the actual loss' and 'also may recover for the unjust enrichment . . . that is not taken into account in computing damages for actual loss.' The memo further references the SJ Order stating the jury 'may not award both lost profits and unjust enrichment to the extent they compensate for the same injury,' and proposes substitute language allowing both measures subject to a non-duplication requirement. This clearly explains that the two damages measures are complementary, not mutually exclusive, under the statute.
- **GPT-5.5: Pass.** The memo expressly states that O.C.G.A. § 10-1-763(a) allows recovery for actual loss/lost profits and also unjust enrichment to the extent not already accounted for, objects to treating them as mutually exclusive, and proposes a non-duplication instruction. This satisfies the criterion.

### C-014

Notes no federal civil procedure requirement for unanimity on damages theories ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L122))

- **Sonnet 4.6: Pass.** In Section III.G (Instruction No. 30), the memo explicitly states: 'Fed. R. Civ. P. 48(b) requires unanimity on the verdict, not on each underlying theory (Trial Brief §II.A).' This directly addresses the criterion that federal civil procedure does not require the jury to unanimously agree on which specific damages theory supports the award, only on the ultimate verdict.
- **GPT-5.5: Pass.** The memo expressly states in the discussion of Instruction No. 30 that “Fed. R. Civ. P. 48(b) requires unanimity on the verdict, not on each underlying theory,” directly noting that federal civil procedure does not require unanimity on the specific damages theory supporting the award.

### C-015

Identifies misstated punitive damages standard in Instruction No. 32 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L130))

- **Sonnet 4.6: Pass.** The memo explicitly addresses Instruction No. 32 in Section H, identifying that it requires 'actual fraud and specific intent to injure' rather than the correct GTSA standard of 'willful and malicious misappropriation' under O.C.G.A. §10-1-763(b). The memo notes that the 'specific intent' language comes from the cap-exception provisions of the general punitive statute and that 'actual fraud' is not an element under the GTSA. It recommends substituting the 'willful and malicious' standard.
- **GPT-5.5: Pass.** The memo explicitly identifies Instruction No. 32 as misstating the punitive damages standard by requiring “actual fraud and specific intent to injure,” and contrasts that with the Georgia Trade Secrets Act standard of “willful and malicious misappropriation” under O.C.G.A. §10-1-763(b).

### C-016

Explains correct punitive damages standard under O.C.G.A. § 10-1-763(b) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L138))

- **Sonnet 4.6: Pass.** Section H of the memo (Instruction No. 32 — Punitive Damages) explicitly identifies that O.C.G.A. §10-1-763(b) authorizes exemplary damages for 'willful and malicious misappropriation' and distinguishes this from the 'actual fraud and specific intent to injure' language in the general punitive damages statute (O.C.G.A. §51-12-5.1(f)-(g)). The memo notes that the defense instruction incorrectly imported the higher standard from the general statute and recommends substituting the correct 'willful and malicious' standard from the GTSA. This satisfies the criterion.
- **GPT-5.5: Pass.** The memo correctly states that O.C.G.A. § 10-1-763(b) authorizes exemplary damages for “willful and malicious misappropriation,” and it expressly distinguishes that standard from the “actual fraud and specific intent to injure” language associated with Georgia’s general punitive damages statute, O.C.G.A. § 51-12-5.1. It recommends substituting the willful-and-malicious standard and reserving cap issues for the court.

### C-017

Identifies narrowing of breach of contract claim in Instruction No. 25 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L146))

- **Sonnet 4.6: Pass.** Section III.F of the memo explicitly addresses Instruction No. 25, identifying that it improperly requires proof that Dr. Voss 'disclosed specific documents belonging to Oakvale,' which narrows the contract claim by leaving out the non-use obligation, intangible and memorized information, and indirect use. The memo cites Agreement §4.2, which covers both use and disclosure including 'intangible knowledge, methods, processes, or know-how,' and §4.1, which includes 'information retained in Employee's memory or recollection.' This directly satisfies the criterion.
- **GPT-5.5: Pass.** The memo expressly flags Instruction No. 25 as improperly narrowing the breach/confidentiality claim by requiring disclosure of “specific documents,” and explains that the Employment Agreement covers use or disclosure of broadly defined Confidential Information, including intangible and memorized knowledge, methods, processes, and know-how regardless of physical document transfer.

### C-018

References Employment Agreement's broad definition of Confidential Information ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L154))

- **Sonnet 4.6: Pass.** In Section III.F (Instruction No. 25), the memo explicitly cites Agreement §4.1 and §4.2. It quotes §4.2's prohibition on both use and disclosure, including 'the application of intangible knowledge, methods, processes, or know-how,' and notes that §4.1 defines Confidential Information to include 'information retained in Employee's memory or recollection' in any form. This directly references the Employment Agreement's broad definition of Confidential Information as the basis for objecting to Instruction No. 25's narrow 'specific documents' requirement.
- **GPT-5.5: Pass.** The memo discusses Instruction No. 25 and expressly cites the Employment Agreement’s confidentiality provisions, including §4.1’s definition of Confidential Information and §4.2’s prohibition on use/disclosure. It explains that the Agreement is broader than specific document disclosure because it covers memorized/intangible knowledge, methods, processes, and know-how, and uses that as the basis for why Instruction No. 25 is too narrow.

### C-019

Identifies improper 'independently wrongful act' element in Instruction No. 27 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L162))

- **Sonnet 4.6: Pass.** Section K of the memo explicitly addresses Instruction No. 27 and states: 'It adds (3) "an independently wrongful act, separate from the interference itself" and (4) "purpose of inducing the breach." Both go beyond the elements the Court identified.' This directly identifies the improper 'independently wrongful act' element as a problem with Instruction No. 27.
- **GPT-5.5: Pass.** The memo expressly flags Instruction No. 27 as problematic because it adds an 'independently wrongful act, separate from the interference itself' element to the tortious interference claim, and recommends substituting the four elements from the summary judgment order.

### C-020

Explains distinction between tortious interference with contract vs. business relations ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L170))

- **Sonnet 4.6: Fail.** The memo's Section K (Instruction No. 27) objects to the 'independently wrongful act' element and cites the SJ Order's four-element formulation, but it does not explain that the 'independently wrongful act' requirement belongs to the distinct tort of tortious interference with business relations (as opposed to interference with an existing contract). The memo simply says the added elements 'go beyond the elements the Court identified' without articulating the legal distinction between the two torts under Georgia law. The criterion requires the memo to explain that for tortious interference with an existing contract, knowing inducement of breach is sufficient and the independently wrongful act element applies only to the separate tort of interference with business relations. This distinction is not articulated in the memo.
- **GPT-5.5: Fail.** The memo correctly objects that the proposed tortious-interference-with-contract instruction improperly adds an “independently wrongful act” element and states that the Court identified only the four existing-contract elements, including knowing inducement of breach. However, it does not articulate the requested distinction that the independently wrongful act requirement belongs to the separate tort of tortious interference with business relations, not interference with an existing contract.

### C-021

Identifies improper fault apportionment instruction in No. 29 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L178))

- **Sonnet 4.6: Pass.** The memo explicitly addresses Instruction No. 29 in Section III.B, identifying that it tells the jury to 'reduce any damages award proportionally' for Oakvale's 'delay or inaction' and failure to 'exercise reasonable diligence in protecting its own interests.' The memo characterizes this as a failure-to-mitigate/avoidable-consequences doctrine (comparative apportionment) that was withdrawn and barred by the court. This directly satisfies the criterion of identifying that No. 29 improperly instructs the jury to reduce damages based on Oakvale's alleged failure to enforce contractual rights.
- **GPT-5.5: Pass.** The memo expressly flags Instruction No. 29 as improper, stating that it tells the jury to reduce damages proportionally based on Oakvale’s delay or inaction/failure to protect its interests, characterizes it as a revived mitigation defense, and notes that it adds comparative apportionment with no pleaded basis.

### C-022

Notes failure to mitigate defense was withdrawn at pretrial conference ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L186))

- **Sonnet 4.6: Pass.** The memo explicitly addresses Instruction No. 29 in Section III.B, stating that at the February 10 pretrial conference (Minutes §IV), Defendants 'formally withdraw their Fifteenth Affirmative Defense, which asserted failure to mitigate damages,' and that the withdrawal was 'unconditional and without reservation.' The Court ruled that 'Defendants may not raise failure to mitigate at any stage of the trial proceedings, including in proposed jury instructions or closing arguments.' This directly connects the withdrawal of the failure to mitigate defense at the February 10 pretrial conference to the objection against Instruction No. 29's apportionment language.
- **GPT-5.5: Pass.** The memo explicitly states that Defendants withdrew their Fifteenth Affirmative Defense for failure to mitigate at the February 10 pretrial conference and that the Court barred raising it in proposed jury instructions. It connects this withdrawal directly to Instruction No. 29, describing the apportionment instruction as an improper revival of the withdrawn mitigation defense.

### C-023

Notes comparative fault does not apply to intentional tort claims ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L194))

- **Sonnet 4.6: Fail.** The memo's analysis of Instruction No. 29 focuses on the withdrawal of the mitigation defense and the court's bar on raising it, and notes that comparative apportionment 'has no pleaded basis in an intentional-misappropriation and contract case.' However, it does not explicitly state that comparative fault does not apply to intentional tort claims under Georgia law as a distinct legal reason why the instruction is improper. The criterion requires the memo to note that comparative fault does not apply to intentional tort claims (such as misappropriation or tortious interference) under Georgia law. This specific legal point is absent from the memo.
- **GPT-5.5: Fail.** The memo criticizes Instruction No. 29 as reviving a withdrawn mitigation defense and says the proposed comparative apportionment has “no pleaded basis in an intentional-misappropriation and contract case.” But it does not state the required point that comparative fault does not apply to intentional tort claims under Georgia law, such as misappropriation or tortious interference, as an additional reason the instruction is improper.

### C-024

Identifies conflict between Instruction No. 21 and the discovery sanctions order ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L202))

- **Sonnet 4.6: Pass.** The memo clearly identifies the conflict between Instruction No. 21 and the Sanctions Order (September 5, 2024). Section III.A is entirely dedicated to this issue, noting that the instruction says the jury 'may not draw any adverse inference from either party's handling of electronic data,' while the Sanctions Order paragraph 4 expressly authorized an adverse inference instruction against Dr. Voss for deleting 347 files after receiving the litigation hold notice. The memo quotes the controlling authority directly and flags it as a Critical priority issue.
- **GPT-5.5: Pass.** The memo explicitly identifies Instruction No. 21 as critical, states that it says the jury may not draw any adverse inference, and explains this directly contradicts the September 5 sanctions order authorizing an adverse inference against Dr. Voss for deleting 347 files after a litigation hold.

### C-025

References the September 5, 2024 sanctions order as authority ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L210))

- **Sonnet 4.6: Pass.** The memo explicitly references the 'Sanctions Order' dated September 5, 2024 multiple times in connection with Instruction No. 21. In the Summary (Part I), it states 'Paragraph 4 of the Sanctions Order expressly forbids any party from proposing that kind of instruction.' In Section III.A, it quotes the Sanctions Order ¶4 directly, references the Court's finding of intent to deprive under Rule 37(e)(2) (¶3), and notes the SJ Order confirms the sanctions ruling 'remains in full force and effect.' The memo also references the substance of the sanctions order — Dr. Voss deleting 347 files, the litigation hold violation, and the authorized adverse inference — throughout the analysis. The date 'September 5, 2024' is stated in the memo header under 'RE' as the 'Order on Motion for Sanctions for Spoliation (Sept. 5, 2024).'
- **GPT-5.5: Pass.** The memo specifically identifies the September 5, 2024 Sanctions Order and cites it as the controlling authority contradicting Instruction No. 21, including its adverse-inference authorization regarding Dr. Voss’s deletion of 347 files and the prohibition on proposing an instruction barring adverse inferences.

### C-026

Identifies argumentative 'particular skepticism' language in Instruction No. 31 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L218))

- **Sonnet 4.6: Pass.** The memo explicitly addresses Instruction No. 31 in Section I (Instruction No. 31 — Expert Testimony) and flags the 'particular skepticism' language as problematic. It states: 'The instruction tells jurors to view Dr. Marchetti's testimony "with particular skepticism given her financial relationship with the plaintiff." It then treats Dr. Webley, who was also retained and paid, neutrally. This is one-sided comment on the evidence.' The memo recommends striking the 'particular skepticism' sentence and replacing it with a neutral statement about expert compensation. This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The memo explicitly flags Instruction No. 31 for telling jurors to view Dr. Marchetti's testimony “with particular skepticism,” describes it as one-sided/commenting on the evidence, and recommends replacing it with a neutral expert-compensation instruction. This satisfies the criterion.

### C-027

References Eleventh Circuit Pattern Instruction 3.5 as proper standard ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L226))

- **Sonnet 4.6: Pass.** In Section I (Instruction No. 31), the memo states: 'The Eleventh Circuit pattern instruction it cites contains no such language.' This references the Eleventh Circuit pattern instruction as the proper neutral standard for expert witness credibility, noting it does not include 'particular skepticism' language. In Section III.I, the memo again states: 'The pattern instruction treats expert testimony like any other testimony.' The recommended objection says to 'Keep a neutral statement that the jury may consider compensation "of any expert witness" in weighing credibility.' The memo does reference the Eleventh Circuit pattern instruction as the proper neutral standard. However, the criterion specifically asks for a reference to 'Eleventh Circuit Pattern Jury Instruction 3.5 or equivalent.' The memo references 'the Eleventh Circuit pattern instruction' without specifying the number 3.5. The criterion says '3.5 or equivalent,' and the memo does reference the pattern instruction as the proper neutral standard allowing consideration of compensation as one factor. The reference is to the pattern instruction generally without the specific number 3.5, but the criterion allows for 'equivalent' references. The memo does satisfy the spirit of the criterion by referencing the Eleventh Circuit pattern instruction as the proper neutral standard.
- **GPT-5.5: Pass.** The memo addresses expert witness credibility in Instruction No. 31, cites the Eleventh Circuit pattern instruction as the proper neutral approach, states that it contains no 'particular skepticism' language, and recommends a neutral instruction allowing the jury to consider compensation of any expert witness as one factor. Although it does not identify the pattern instruction by number 3.5, it provides the equivalent required reference and standard.

### C-028

Provides recommendation for each identified issue ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L234))

- **Sonnet 4.6: Pass.** Every identified problematic instruction in the memo includes at least a 'Recommended objection / alternative' subsection with specific guidance. Instructions 21, 29, 14, 23 (critical) each have detailed recommendations. Instructions 16/22, 25, 30, 32, 31, 12, 27 (high priority) each have recommendations. Instructions 13, 20, 18, 19, 15 (medium) have recommendations. Instructions 11, 24, 28, 35 (low) have targeted correction recommendations. The priority table also summarizes issues. No identified issue lacks a recommendation.
- **GPT-5.5: Pass.** The memo identifies problematic instructions and, for each, provides a recommended response—typically to object, strike, revise, or substitute specific alternative language. It also includes recommendations/actions for cross-document inconsistencies and low-priority issues. There are no multiple identified problematic instructions left without guidance on how to address them.

### C-029

Identifies at least some unobjectionable instructions ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L242))

- **Sonnet 4.6: Pass.** The memo explicitly identifies several instructions as unobjectionable. In Section III.N, it states: 'No. 34 (injunctive relief for the Court) is consistent with the Minutes, and we do not object. Nos. 1--9, 26 and 33 appear to be standard and unobjectionable, subject to the party-name correction below.' This identifies at least two (indeed many more than two) defense proposed instructions as proper or unobjectionable, satisfying the criterion.
- **GPT-5.5: Pass.** The memo affirmatively identifies multiple defense instructions as unobjectionable or not warranting objection, including No. 34, Nos. 1–9, 26, and 33, and notes No. 28 is generally acceptable. This satisfies the requirement to identify at least two unobjectionable instructions.

### C-030

Memo identifies correct case name and parties ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L250))

- **Sonnet 4.6: Pass.** The memo identifies the case as 'Oakvale/Ridgemont Technologies, Inc. v. Voss & Axial Systems Corp.' and throughout the document refers to Oakvale Technologies, Inc. as the plaintiff, Dr. Nolan Voss as a defendant, and Axial Systems Corp. as a defendant. The parties are correctly identified, even though the memo also notes an inconsistency between 'Oakvale' and 'Ridgemont' as the plaintiff's name (flagged as a cross-document inconsistency to resolve). The core identification of the parties matches the criterion.
- **GPT-5.5: Pass.** The memo identifies the matter as involving Oakvale Technologies, Inc. as plaintiff and Voss/Axial Systems Corp. as defendants, and repeatedly refers to Dr. Nolan Voss and Axial Systems Corp. Although it notes a possible Oakvale/Ridgemont naming inconsistency, the required parties are present and not materially absent.

### C-031

Memo identifies correct case number and court ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L258))

- **Sonnet 4.6: Pass.** The memo header clearly states 'Oakvale/Ridgemont Technologies, Inc. v. Voss & Axial Systems Corp., No. 1:23-cv-01847-CME (N.D. Ga.)' which correctly identifies both the case number (1:23-cv-01847-CME) and the court (U.S. District Court for the Northern District of Georgia).
- **GPT-5.5: Pass.** The memo’s RE line identifies the matter as No. 1:23-cv-01847-CME and specifies “(N.D. Ga.),” which denotes the U.S. District Court for the Northern District of Georgia.

### C-032

Describes potential prejudice to Oakvale for each flagged issue ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L266))

- **Sonnet 4.6: Pass.** I need to evaluate whether the memo describes potential prejudice to Oakvale for at least 8 of the 12 planted issues identified. Let me go through each flagged issue and check for prejudice descriptions: 1. **No. 21 (Spoliation/Adverse Inference)** - The memo explains the instruction says jury 'may not draw any adverse inference,' which is the opposite of what the Court ordered. Prejudice: Oakvale loses the benefit of the adverse inference the Court already granted, which was a significant litigation win. Prejudice is implicit but described through the contrast with the Sanctions Order. 2. **No. 29 (Failure to Enforce/Apportionment)** - The memo explains this revives a withdrawn defense that would reduce damages proportionally. Prejudice: damages would be reduced for Oakvale's 'delay or inaction.' This is clearly described. 3. **No. 14 (Identification of Trade Secrets - SignalSift)** - The memo notes that leaving SignalSift in front of the jury 'invites an argument that one lost category undermines the others.' Prejudice is explicitly described. 4. **No. 23 (Inevitable Disclosure)** - The memo explains the second paragraph says job similarity 'is not evidence of misappropriation,' contrary to the SJ Order. Prejudice: Oakvale loses a key piece of circumstantial evidence the Court said the jury may consider. 5. **No. 16/22 (Misappropriation - acquisition only)** - The memo states 'an acquisition-only definition would effectively take the core use/disclosure theory away from the jury.' Prejudice is explicitly described. 6. **No. 25 (Breach of Confidentiality)** - The memo explains this narrows the contract to document disclosure, leaving out non-use obligation, intangible/memorized information, and indirect use. Prejudice: Oakvale's contract claim is significantly narrowed. 7. **No. 30 (Lost Profits/Unjust Enrichment)** - The memo explains the instruction forces a mandatory election and leaves out the reasonable-royalty alternative. Prejudice: Oakvale cannot recover both measures even where they don't overlap, and loses the royalty option. 8. **No. 32 (Punitive Damages)** - The memo explains the instruction uses a higher standard ('actual fraud + specific intent') than the statutory 'willful and malicious' standard. Prejudice: harder for Oakvale to obtain punitive damages. 9. **No. 31 (Expert Testimony - 'particular skepticism')** - The memo explains this is one-sided and effectively revisits the Daubert denial. Prejudice: Dr. Marchetti's testimony is unfairly discredited while Defendants' expert is treated neutrally. 10. **No. 12 (Trade Secret Definition - 'novel')** - The memo explains the 'novel' requirement is not in the statute and the SJ Order expressly said novelty is not required. Prejudice: Oakvale must meet a higher standard not required by law, potentially losing trade secret protection for some categories. 11. **No. 27 (Tortious Interference)** - The memo explains two extra elements are added beyond what the Court identified. Prejudice: Oakvale must prove additional elements not required by law, making the claim harder to win. 12. **No. 13/20 (Reasonable Measures; Combination)** - The memo explains 'inadequate' standard is wrong and 'sufficient added value' test doesn't appear in statute. Prejudice: higher bar for Oakvale to establish trade secret status. Now let me assess which ones have explicit or clear prejudice descriptions: 1. No. 21 - Prejudice described (loses adverse inference benefit) - somewhat implicit but clear 2. No. 29 - Prejudice described (damages reduced) - explicit 3. No. 14 - Prejudice described (undermines other categories) - explicit 4. No. 23 - Prejudice described (loses circumstantial evidence) - clear 5. No. 16/22 - Prejudice described (core theory taken from jury) - explicit 6. No. 25 - Prejudice described (contract claim narrowed) - clear 7. No. 30 - Prejudice described (can't recover both, loses royalty option) - explicit 8. No. 32 - Prejudice described (harder to get punitive damages) - clear 9. No. 31 - Prejudice described (expert unfairly discredited) - explicit 10. No. 12 - Prejudice described (higher standard not required by law) - clear 11. No. 27 - Prejudice described (extra elements to prove) - clear 12. No. 13/20 - Prejudice described (higher bar for trade secret status) - clear All 12 identified issues have some description of prejudice to Oakvale. This clearly exceeds the threshold of 8. The verdict should be PASS.
- **GPT-5.5: Pass.** The memo identifies the relevant planted instruction issues and, for well over 8 of the 12, explains how the challenged language would harm Oakvale: e.g., eliminating the adverse inference, reviving a withdrawn mitigation defense to reduce damages, putting dismissed SignalSift issues before the jury, excluding job-similarity circumstantial evidence, removing the use/disclosure misappropriation theory, narrowing the contract claim to documents, forcing an improper damages election, heightening the punitive-damages standard, singling out Oakvale’s expert for skepticism, and adding extra elements or requirements to trade secret and tortious-interference claims. The prejudice discussion is often embedded in the “Problem” sections rather than separately labeled, but it is sufficient.

### C-033

Distinguishes flatly wrong instructions from subtly misleading ones ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/review-counterpartys-proposed-jury-instructions/task.json#L274))

- **Sonnet 4.6: Pass.** The memo clearly distinguishes between different severity levels of instruction problems. It explicitly labels four instructions as 'CRITICAL' (Nos. 21, 29, 14, 23) because they 'directly violate express court rulings.' It labels another group as 'HIGH' priority (Nos. 16/22, 25, 30, 32, 31, 12, 27) for misstatements of substantive law. A third group is labeled 'MEDIUM' (Nos. 13, 20, 18, 19) for less severe issues, and a fourth group 'LOW' (Nos. 11, 15, 28, 35) for minor citation or framing issues. The memo also uses qualitative language to distinguish: 'flatly wrong' vs. instructions that are 'subtly misleading' or 'slanted.' For example, it notes that No. 23's first paragraph 'is consistent with the SJ Order' while only the second paragraph is problematic. It notes that No. 28 is 'generally acceptable' but has one sentence that needs adjustment. It notes that Nos. 1-9, 26, and 33 'appear to be standard and unobjectionable.' This clearly satisfies the criterion of distinguishing flatly wrong instructions from subtly misleading ones.
- **GPT-5.5: Pass.** The memo explicitly differentiates severity: it labels some instructions as “directly violate express court rulings” and “Critical,” others as substantive misstatements marked “High,” and still others as “Medium” or “Low” issues involving framing, citation, or targeted corrections. It also distinguishes instructions to strike in full from those needing revisions or limiting language.
