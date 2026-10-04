# Claude Opus 5.5 (low): Draft Plaintiff's Portion of Joint Pretrial Statement in Breach of Contract and Fraudulent Inducement Action

> [!NOTE]
> **Unedited model output and AI judge grades.** The deliverables are AI-generated drafts on Harvey LAB's fictional task records. Pass/fail verdicts are the native LAB judges' AI judgments, not human review or accepted corrections. See the [model-runs overview](../../README.md).

[Task audit page](../../../tasks/draft-pretrial-statement/README.md) · [Pinned task and rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json) · [GPT-6 Luna (xhigh) run](../gpt6luna-xhigh/README.md) · [All runs](../../README.md)

**Model:** `claude-opus-5-5`, reasoning effort `low`. **Run:** `20260926-202411`.

**Native grades:** Sonnet 4.6 passed 41 of 46 criteria; GPT-5.5 passed 42 of 46 criteria. LAB all-pass score: 0 (mean of the judges' all-pass results; a task scores 1 with a judge only if every criterion passes).

## Deliverables

- [plaintiff-pretrial-statement.docx](output/plaintiff-pretrial-statement.docx) ([read as Markdown](output/plaintiff-pretrial-statement.docx.md))
- [response.md](output/response.md)

## Grades

Failures are in bold. Each criterion links to both judges' reasoning below.

| Criterion | Title | Sonnet 4.6 | GPT-5.5 |
|---|---|---|---|
| [C-001](#c-001) | ISSUE_001: Identifies lease period discrepancy in reliance damages | Pass | Pass |
| [C-002](#c-002) | ISSUE_002: Addresses duplicative damages theory (expectation vs. reliance) | Pass | Pass |
| [C-003](#c-003) | ISSUE_003a: Addresses statute of limitations defense on fraud claim with 2-year period | Pass | Pass |
| [C-004](#c-004) | ISSUE_003b: Invokes discovery rule for fraud statute of limitations | Pass | Pass |
| [C-005](#c-005) | ISSUE_003: Explains why discovery rule saves fraud claim | Pass | Pass |
| [C-006](#c-006) | ISSUE_004: Motion in limine to exclude force majeure defense evidence | Pass | Pass |
| [C-007](#c-007) | ISSUE_005: Argues Findlay memo is not excludable under FRE 407 | **Fail** | **Fail** |
| [C-008](#c-008) | ISSUE_006: Acknowledges trade usage exception weakness in parol evidence motion | **Fail** | **Fail** |
| [C-009](#c-009) | ISSUE_007: Defends Dr. Prescott's future lost profits against Daubert challenge | Pass | Pass |
| [C-010](#c-010) | ISSUE_008: David Rinaldi included on witness list | Pass | Pass |
| [C-011](#c-011) | ISSUE_008: Rinaldi testimony summary covers key topics | Pass | Pass |
| [C-012](#c-012) | ISSUE_009: Addresses mitigation timing gap (6-month delay) | Pass | Pass |
| [C-013](#c-013) | ISSUE_010a: Connects Findlay memo to Ted Corbin III's knowledge | Pass | Pass |
| [C-014](#c-014) | ISSUE_010b: Articulates how Findlay memo supports scienter | Pass | Pass |
| [C-015](#c-015) | ISSUE_010: Identifies specific misrepresentations contradicted by internal documents | Pass | Pass |
| [C-016](#c-016) | Jurisdictional statement identifies diversity jurisdiction under 28 U.S.C. § 1332 | Pass | Pass |
| [C-017](#c-017) | Jurisdictional statement identifies citizenship of both parties | Pass | Pass |
| [C-018](#c-018) | Jurisdictional statement identifies amount in controversy | Pass | Pass |
| [C-019](#c-019) | Stipulated facts section includes key stipulations | Pass | Pass |
| [C-020](#c-020) | Contested factual issues section included | Pass | Pass |
| [C-021](#c-021) | Contested legal issues section included | Pass | Pass |
| [C-022](#c-022) | Witness list includes Peggy Hausman with testimony summary | Pass | Pass |
| [C-023](#c-023) | Witness list includes Ted Corbin III as adverse witness | Pass | Pass |
| [C-024](#c-024) | Witness list includes Marcus Findlay as adverse witness | Pass | Pass |
| [C-025](#c-025) | Witness list includes Dr. Elaine Prescott as expert witness | Pass | Pass |
| [C-026](#c-026) | Exhibit list includes key documents | Pass | Pass |
| [C-027](#c-027) | Motion in limine to exclude Gerald Voss's industry custom testimony included | **Fail** | **Fail** |
| [C-028](#c-028) | Estimated trial time section included | Pass | Pass |
| [C-029](#c-029) | Settlement status section included | Pass | Pass |
| [C-030](#c-030) | Correct case number and court identification | Pass | Pass |
| [C-031](#c-031) | Correct party identification in case caption | Pass | Pass |
| [C-032](#c-032) | Correct total damages figure stated | **Fail** | **Fail** |
| [C-033](#c-033) | Correct Year 1 MAPC shortfall figure | Pass | Pass |
| [C-034](#c-034) | Correct Year 2 MAPC shortfall figure | Pass | Pass |
| [C-035](#c-035) | Correct future lost profits calculation | Pass | Pass |
| [C-036](#c-036) | Identifies remaining claims as breach of contract and fraudulent inducement | Pass | Pass |
| [C-037](#c-037) | Does not include dismissed negligent misrepresentation claim | Pass | Pass |
| [C-038](#c-038) | References partial summary judgment on breach liability | Pass | Pass |
| [C-039](#c-039) | Motion in limine re materiality of MAPC breaches (law of the case) | **Fail** | Pass |
| [C-040](#c-040) | Correct identification of Judge Gresham | Pass | Pass |
| [C-041](#c-041) | Correct trial date stated | Pass | Pass |
| [C-042](#c-042) | Identifies EDA execution date correctly as March 1, 2021 | Pass | Pass |
| [C-043](#c-043) | Correctly characterizes the 12-state southeastern territory | Pass | Pass |
| [C-044](#c-044) | Mitigation credit correctly applied in damages | Pass | Pass |
| [C-045](#c-045) | Correctly identifies Ridgeline's gross margin as 34% | Pass | Pass |
| [C-046](#c-046) | Addresses Holt's challenge to future lost profits period | Pass | Pass |

## Judge reasoning

### C-001

ISSUE_001: Identifies lease period discrepancy in reliance damages ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L22))

- **Sonnet 4.6: Pass.** The agent's output explicitly addresses the lease period discrepancy. In Stipulated Fact 28, it states: 'Of the Total Rent, approximately $770,833.35 represents the fifteen months of rent from March 2023 through May 2024, the period remaining after termination of the EDA.' In Section 3, Issue 12, it distinguishes between the full $2,325,000 in reliance expenditures and the 'unrecouped post-termination portion' of $1,245,833.35 ($770,833.35 in post-termination rent plus $475,000 in equipment). In Section 5, Issue D, it again references both the full and post-termination figures. The output clearly distinguishes between the portion of the lease used during contract performance and the remaining unusable portion, satisfying the criterion.
- **GPT-5.5: Pass.** The output expressly identifies the lease term (June 1, 2021 to May 31, 2024), the March 2023 termination date, and distinguishes the full $1,850,000 rent from the approximately 15-month post-termination remainder of $770,833.35. It also frames the full lease amount versus post-termination unrecouped amount as an issue requiring proof/justification, rather than simply claiming the full lease cost without discussion.

### C-002

ISSUE_002: Addresses duplicative damages theory (expectation vs. reliance) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L30))

- **Sonnet 4.6: Pass.** The agent's output explicitly addresses the tension between expectation damages (lost profits) and reliance damages in multiple places. Section 5, Issue D is entirely devoted to 'Relationship between expectation damages (Count I) and reliance damages (Count II); prevention of double recovery.' The agent acknowledges that 'Ridgeline recognizes that it may not recover twice for the same loss' and proposes a special verdict form to allow the Court to mold the judgment. The agent also allocates reliance damages primarily to Count II (fraudulent inducement) rather than Count I (breach of contract), and notes that 'To the extent any reliance expenditure would have been recouped from the gross profit Ridgeline recovers on Count I, the Court should reduce the Count II award by the overlap only.' Additionally, Issue 13 in Section 3 addresses whether reliance losses would have been recouped from full performance, and the agent notes that Defendant's expert 'cannot identify any actual double-counting.' The output clearly recognizes the tension and reconciles the theories by allocating reliance damages to the fraud claim while preserving expectation damages for the contract claim, with a proposed mechanism to prevent duplicative recovery.
- **GPT-5.5: Pass.** The output expressly recognizes the potential overlap between expectation damages (lost profits under Count I) and reliance damages (Greenville lease and packaging equipment), allocates reliance damages primarily to the fraudulent inducement claim, proposes a special verdict and post-verdict molding to prevent double recovery, and states that contract reliance damages would be an alternative if Count II fails. This satisfies the criterion.

### C-003

ISSUE_003a: Addresses statute of limitations defense on fraud claim with 2-year period ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L38))

- **Sonnet 4.6: Pass.** The output extensively addresses the statute of limitations defense on the fraud claim. In Section 3, Issue 8, it discusses the two-year limitations period of 42 Pa. C.S. § 5524(7), the discovery rule, and when Ridgeline knew or should have known of the fraud. In Section 5, Issue H, it provides a full legal analysis of the limitations defense, citing 42 Pa. C.S. § 5524(7), Fine v. Checcio, and Cochran v. GAF Corp. The output also notes that the complaint was filed March 10, 2023, and addresses the timing of the misrepresentations (October 2020–February 2021), arguing that even on Corbin Supply's best theory (Year 1 shortfall February 28, 2022 or cure notice March 15, 2022), Count II was asserted within two years. The output clearly identifies the 2-year period, the relevant statute, and the timing issues.
- **GPT-5.5: Pass.** The output expressly addresses the fraud statute-of-limitations defense in Section 3 Issue 8 and Section 5 Issue H, cites Pennsylvania’s two-year fraud limitations period under 42 Pa. C.S. § 5524(7), discusses the discovery rule, and states the complaint was filed March 10, 2023. It also identifies the alleged misrepresentation period and specific communications from October 2020 through February 2021 elsewhere in the statement, making clear the limitations issue is being treated.

### C-004

ISSUE_003b: Invokes discovery rule for fraud statute of limitations ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L46))

- **Sonnet 4.6: Pass.** The output explicitly invokes the discovery rule in multiple places. In Section 3, Issue 8, it states: 'When Ridgeline knew or should have known of the fraud is a question of fact under the discovery rule. Fine v. Checcio, 870 A.2d 850, 858--59 (Pa. 2005).' In Section 5, Issue H, it states: 'The discovery rule tolls the limitations period until the plaintiff knows, or through reasonable diligence should know, that it has been injured and by whose conduct.' The output clearly and repeatedly invokes the discovery rule in connection with the statute of limitations defense on the fraud claim.
- **GPT-5.5: Pass.** The output expressly invokes the discovery rule in connection with Defendant’s statute-of-limitations defense to the fraudulent inducement claim, stating that the limitations period runs when Ridgeline knew or reasonably should have discovered the fraud, and cites Fine v. Checcio and 42 Pa. C.S. § 5524(7).

### C-005

ISSUE_003: Explains why discovery rule saves fraud claim ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L54))

- **Sonnet 4.6: Pass.** The output addresses the discovery rule in Section 3, Issue 8 and Section 5, Issue H. In Issue 8, it explains that Ridgeline did not know and could not have discovered the falsity of the representations until Corbin Supply produced its internal CRM data, warehouse records, sales roster, and the Findlay Memo in November and December 2023. It also explains that the Year 1 shortfall was consistent with ordinary start-up problems, that Corbin Supply's response to the cure notice cited general supply-chain challenges without disclosing the true infrastructure figures, and that the facts showing falsity were in Corbin Supply's exclusive possession. In Issue H, it further notes that even on Corbin Supply's best theory—that the Year 1 shortfall (February 28, 2022) or the cure notice (March 15, 2022) put Ridgeline on inquiry notice—Count II was asserted well within two years of either date (the complaint was filed March 10, 2023). The output thus explains both when Ridgeline actually discovered the fraud (late 2023 document production) and why it could not have discovered it earlier, satisfying the criterion's requirement to explain when Ridgeline actually discovered or should have discovered the fraud.
- **GPT-5.5: Pass.** The output specifically addresses the discovery rule in Section 3 Issue 8 and Section 5 Issue H, stating that Ridgeline did not know and could not reasonably have learned the falsity until Corbin produced internal CRM, warehouse, roster, and Findlay Memo documents in late 2023, and that the Year 1 shortfall did not put it on notice while the Year 2 decline was the first real concern. It further explains that the March 10, 2023 filing was timely even under Defendant’s earlier inquiry-notice theories.

### C-006

ISSUE_004: Motion in limine to exclude force majeure defense evidence ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L62))

- **Sonnet 4.6: Pass.** Section 10, Plaintiff's MIL No. 2 explicitly moves to preclude evidence and argument supporting a force majeure defense. It cites EDA § 12.1's requirement of written notice within 30 days of a force majeure event and the contractual provision that failure to give such notice 'shall constitute a waiver of the right to claim relief.' It also notes that Corbin Supply admits it gave no notice (Corbin Dep. 92:1--97:15) and that the Court found the record 'devoid of any evidence' of compliance. This satisfies the criterion.
- **GPT-5.5: Pass.** The output expressly includes Plaintiff's MIL No. 2 to preclude evidence and argument supporting a force majeure defense. It cites EDA § 12.1's requirement of written notice within 30 days and states that failure to provide notice waives the defense, and further states Corbin Supply admits it gave no notice.

### C-007

ISSUE_005: Argues Findlay memo is not excludable under FRE 407 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L70))

- **Sonnet 4.6: Fail.** The agent's output addresses the Findlay Memo's admissibility in Section 10 (Motions in Limine) and in Section 5 (Issue K), but only argues that it is admissible as a party-opponent statement and business record under FRE 801(d)(2)(D) and 803(6). The output does not address or oppose any FRE 407 (subsequent remedial measures) argument by Corbin Supply regarding the Findlay Memo. The criterion requires the output to specifically oppose a motion to exclude the Findlay Memo under FRE 407 by arguing that the memo predates the contract and any breach, making it outside FRE 407's scope. This argument is entirely absent from the output.
- **GPT-5.5: Fail.** The output discusses admissibility of the Findlay Memo as a party-opponent statement and business record, and it notes elsewhere that the memo was dated January 15, 2021 before the EDA. However, it does not address or oppose a Corbin Supply motion to exclude the memo under FRE 407, nor does it argue that FRE 407 applies only to subsequent remedial measures taken after an injury or harm and that the memo predates the contract and breach. Therefore it does not satisfy the specified criterion.

### C-008

ISSUE_006: Acknowledges trade usage exception weakness in parol evidence motion ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L78))

- **Sonnet 4.6: Fail.** The criterion requires that the output, in connection with a motion in limine to exclude Gerald Voss's industry custom testimony under the parol evidence rule, acknowledge the weakness that trade usage/industry custom evidence is generally admissible even with an integration clause. The agent's output contains no mention of Gerald Voss anywhere, and no motion in limine addressing trade usage or industry custom testimony under the parol evidence rule. The output's MIL No. 4 addresses the parol evidence rule only in the context of pre-contract representations being incorporated into the EDA itself, not in connection with any trade usage exception or a witness named Voss. Since the specific scenario described in the criterion (motion to exclude Voss's industry custom testimony with acknowledgment of the trade usage exception weakness) is entirely absent from the output, the criterion is not satisfied.
- **GPT-5.5: Fail.** The output does not mention Gerald Voss or any motion in limine to exclude industry custom/trade usage testimony. It also does not acknowledge that trade usage evidence may be admissible notwithstanding an integration clause under UCC § 1-303/common law, nor that the EDA’s integration clause does not expressly exclude trade usage. Therefore it fails the specified criterion.

### C-009

ISSUE_007: Defends Dr. Prescott's future lost profits against Daubert challenge ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L86))

- **Sonnet 4.6: Pass.** The output addresses the anticipated Daubert challenge to Dr. Prescott's future lost-profit opinions in Section 10.B (Plaintiff's Positions on Defendant's Anticipated Motions in Limine). It explicitly states: 'The methodology (contractual minimums, audited margin, mitigation credit) is generally accepted, and Defendant's own expert concedes it "is an accepted approach." Holt Dep. 18:3--38:22. Objections to the length of the damages period go to weight, not admissibility.' Additionally, Section 5, Issue B argues that the MAPCs are fixed contractual amounts providing a non-speculative foundation, citing the Court's own observation that 'contractual minimum-purchase obligations provide a non-speculative foundation for lost-profit calculations' (SJ Op. § IV.A.3), and that Defendant's expert concedes the MAPC methodology 'is an accepted approach.' The 34% gross margin derived from audited financials is also referenced throughout (Issues 9, 10, and the Prescott expert entry). The output thus both addresses the Daubert challenge and explains why the methodology is reliable based on contractual MAPCs and audited historical margins.
- **GPT-5.5: Pass.** The output expressly anticipates a defense Daubert motion to exclude or limit Dr. Prescott’s future lost-profit opinions and states Plaintiff will oppose it because her methodology uses contractual minimum purchase commitments, audited gross-margin data, and a mitigation credit. It also explains elsewhere that the Years 3–5 projections are based on fixed MAPCs totaling $31.5 million and Ridgeline’s historical 34% gross margin supported by audited financials, making the calculation non-speculative and reliable.

### C-010

ISSUE_008: David Rinaldi included on witness list ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L94))

- **Sonnet 4.6: Pass.** David Rinaldi is listed as Witness No. 2 in Section 6A (Fact Witnesses) of the plaintiff's witness list, designated as 'Will call' with a detailed summary of expected testimony.
- **GPT-5.5: Pass.** The plaintiff's witness list in Section 6 includes David Rinaldi as Fact Witness No. 2, with address, manner of testimony, expected testimony, and estimated direct examination time.

### C-011

ISSUE_008: Rinaldi testimony summary covers key topics ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L102))

- **Sonnet 4.6: Pass.** The witness list entry for David Rinaldi (Witness No. 2) includes a detailed summary of expected testimony that explicitly covers: 'drafting and negotiating the EDA and the MAPC schedule with Ms. Koppel' (negotiation of EDA/MAPC terms) and 'the March 15, 2022 cure notice, Ms. Koppel's March 28, 2022 letter, and his April 3 and April 28, 2022 calls requesting a written remediation plan' (communications about the cure notice). Both required topics are clearly addressed.
- **GPT-5.5: Pass.** The output lists David Rinaldi as a fact witness and provides a detailed expected testimony summary, including both his role in drafting and negotiating the EDA and MAPC schedule and his communications concerning the March 15, 2022 cure notice and follow-up with Corbin Supply.

### C-012

ISSUE_009: Addresses mitigation timing gap (6-month delay) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L110))

- **Sonnet 4.6: Pass.** The output extensively addresses the 6-month gap between EDA termination (March 10, 2023) and Allegheny engagement (September 1, 2023). In Section 3, Issue 11, it explicitly states Ridgeline began identifying replacement candidates within weeks of termination, began formal outreach in April 2023, contacted five candidates, ran due diligence on three including on-site visits and reference checks, selected Allegheny in July 2023, negotiated the agreement, integrated logistics, trained the sales force, and began distribution September 1, 2023. It justifies the timeline as commercially reasonable, noting that 'four to nine months is typical for replacing an exclusive distributor across twelve states' and that 'careful vetting was especially prudent after Corbin Supply's misrepresentations.' This is further supported in Section 5, Issue C and Section 6 witness list entries. The output clearly acknowledges the gap and provides detailed justification for why it was reasonable.
- **GPT-5.5: Pass.** The output expressly acknowledges the March 10, 2023 termination and September 1, 2023 replacement distributor start date, identifies the approximately six-month gap, and repeatedly states Ridgeline’s position that the timeline was commercially reasonable due to identifying candidates, due diligence, site visits, negotiations, logistics integration, and sales-force training across a twelve-state territory.

### C-013

ISSUE_010a: Connects Findlay memo to Ted Corbin III's knowledge ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L118))

- **Sonnet 4.6: Pass.** The output extensively connects the Findlay memo to Ted Corbin III's knowledge. In Section 3, Issue 3, it states: (a) the memo was addressed to 'Senior Leadership' and the distribution list included Mr. Corbin III; (b) Findlay reported directly to Mr. Corbin III (Stipulated Fact 4 and Issue 3 supporting evidence); and (c) Corbin Dep. 72:8–86:19 is cited where Corbin III states 'I don't deny that it was sent to me' and 'I may have seen it,' and Findlay's deposition testimony that Mr. Corbin III 'said he'd seen the memo' and discussed it with Findlay in late January 2021 before the contract was signed. All three connecting factors are present.
- **GPT-5.5: Pass.** The output explicitly connects the January 15, 2021 Findlay Memo to Ted Corbin III’s knowledge in multiple ways: it states the memo was addressed to Senior Leadership and that the distribution list included Corbin III; it notes Findlay reported directly to Corbin III; and it cites Corbin’s deposition testimony that he was on the Senior Leadership list, did not deny it was sent to him, and “may have seen it.”

### C-014

ISSUE_010b: Articulates how Findlay memo supports scienter ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L126))

- **Sonnet 4.6: Pass.** The output extensively discusses how the Findlay Memo supports scienter in Section 3, Issue 3. It explains that Mr. Corbin III personally ran negotiations, received the Findlay Memo (which documented the true, lower figures of 187 accounts, 7 warehouses, and 23 representatives), read it, and discussed it with Mr. Findlay in late January 2021 — before the EDA was signed. Despite this knowledge, he reaffirmed the inflated representations on February 12, 2021 and signed the EDA warranting those figures on March 1, 2021. The memo itself contains language acknowledging that 'external materials reference over 300' and directing that 'external negotiations should continue to reflect our full capabilities.' The output also notes the size of the discrepancies (60% overstatement of service centers, 4 of 11 warehouses false, 83% overstatement of dedicated sales force) as further evidence of knowing falsity. This directly articulates how the Findlay Memo supports the scienter element of fraudulent inducement.
- **GPT-5.5: Pass.** The output expressly discusses scienter in Section 3, Issue 3, explaining that the Findlay Memo documented the true lower figures, was distributed to senior leadership including Corbin, was allegedly read and discussed before signing, and was followed by reaffirmation of the false representations. It ties this to knowledge or reckless disregard for falsity in the fraudulent inducement claim.

### C-015

ISSUE_010: Identifies specific misrepresentations contradicted by internal documents ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L134))

- **Sonnet 4.6: Pass.** The output explicitly identifies all three misrepresentations with specific figures: (1) 300+ OEM service centers vs. actual 187 active accounts (Issues 1 and 2, PX-007 §3.1); (2) 11 operational warehouses vs. actual 7 operational (Issues 1 and 2, PX-007 §3.2); (3) 42 dedicated sales representatives vs. actual 23 (Issues 1 and 2, PX-007 §3.3). All three are clearly stated with both the represented and actual figures throughout the document.
- **GPT-5.5: Pass.** The output specifically identifies all three misrepresentations and contrasts the represented figures with internal-document actuals: 300+ OEM service centers vs. 187 active accounts, 11 operational warehouses vs. 7 operational warehouses, and 42 dedicated sales representatives vs. 23 hydraulic representatives.

### C-016

Jurisdictional statement identifies diversity jurisdiction under 28 U.S.C. § 1332 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L142))

- **Sonnet 4.6: Pass.** Section 1 of the output is explicitly titled 'JURISDICTIONAL STATEMENT (Proposed Joint)' and states: 'The Court has subject-matter jurisdiction under 28 U.S.C. § 1332(a)(1). Complete diversity exists between the parties, and the amount in controversy exceeds $75,000, exclusive of interest and costs.' It also cites 28 U.S.C. § 1332(c)(1) for citizenship rules and references the Court's prior ruling exercising 'diversity jurisdiction pursuant to 28 U.S.C. § 1332'. The criterion is clearly satisfied.
- **GPT-5.5: Pass.** The output includes a dedicated Section 1 titled “Jurisdictional Statement” and expressly states that the Court has subject-matter jurisdiction under 28 U.S.C. § 1332(a)(1) based on complete diversity and amount in controversy.

### C-017

Jurisdictional statement identifies citizenship of both parties ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L150))

- **Sonnet 4.6: Pass.** The jurisdictional statement in Section 1 clearly identifies Ridgeline as a Pennsylvania corporation with its principal place of business in Butler, Pennsylvania, and Corbin Supply as a Delaware limited liability company with principal offices in Charlotte, North Carolina. Both citizenships are stated, establishing complete diversity.
- **GPT-5.5: Pass.** The jurisdictional statement identifies Ridgeline as a Pennsylvania corporation with its principal place of business in Pennsylvania and Corbin Supply as a Delaware LLC with principal offices in Charlotte, North Carolina, and it addresses complete diversity by noting LLC member citizenship must be confirmed with no Pennsylvania members.

### C-018

Jurisdictional statement identifies amount in controversy ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L158))

- **Sonnet 4.6: Pass.** Section 1 of the jurisdictional statement explicitly states: 'the amount in controversy exceeds $75,000, exclusive of interest and costs.' This directly satisfies the criterion.
- **GPT-5.5: Pass.** The jurisdictional statement expressly states that “the amount in controversy exceeds $75,000, exclusive of interest and costs,” and further notes damages well above $75,000.

### C-019

Stipulated facts section includes key stipulations ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L166))

- **Sonnet 4.6: Pass.** The stipulated facts section (Section 2) includes all 7 required stipulations: (1) EDA validly executed March 1, 2021 (Stipulated Fact 11); (2) Year 1 purchases totaled $5,120,000 (Stipulated Fact 16); (3) Year 2 purchases totaled $4,370,000 (Stipulated Fact 18); (4) Ridgeline sent cure notice March 15, 2022 (Stipulated Fact 17); (5) Corbin Supply did not cure within 60 days (Stipulated Fact 17); (6) Ridgeline terminated the EDA on March 10, 2023 (Stipulated Fact 20); (7) court granted partial summary judgment finding breach of MAPC provisions (Stipulated Facts 22 and 25). All 7 are present, exceeding the threshold of 6.
- **GPT-5.5: Pass.** The output contains a clear Section 2 titled “Stipulated Facts.” It includes all seven required stipulations: valid execution of the EDA on March 1, 2021; Year 1 purchases of $5.12 million; Year 2 purchases of $4.37 million; the March 15, 2022 cure notice; Corbin Supply’s failure to cure within the 60-day period; Ridgeline’s March 10, 2023 termination; and the Court’s finding that Corbin Supply breached the MAPC provisions.

### C-020

Contested factual issues section included ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L174))

- **Sonnet 4.6: Pass.** Section 3 of the output is explicitly titled 'PLAINTIFF'S CONTESTED FACTUAL ISSUES' and contains 14 detailed issues. It covers all three required topics: (a) the nature and extent of Corbin Supply's pre-contract misrepresentations (Issues 1-2 address the specific representations made and their falsity); (b) damages amounts (Issues 9-13 address lost profits, future lost profits, reliance losses, and mitigation); and (c) whether Corbin Supply knew its representations were false (Issue 3 is specifically titled 'Corbin Supply made the representations knowingly or with reckless disregard for their truth'). All three criteria are thoroughly addressed.
- **GPT-5.5: Pass.** The output includes a dedicated Section 3 titled “Plaintiff's Contested Factual Issues.” It addresses the nature and extent of Corbin Supply’s alleged pre-contract misrepresentations, specific damages amounts including lost profits and reliance losses, and whether Corbin Supply knew or recklessly disregarded that its representations were false.

### C-021

Contested legal issues section included ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L182))

- **Sonnet 4.6: Pass.** Section 5 of the output is explicitly titled 'CONTESTED LEGAL ISSUES' and contains eleven sub-issues (A through K). It addresses: (a) the proper measure and recoverability of damages in Issues A, B, D, and E; (b) fraudulent inducement elements including scienter (Issue I, J) and statute of limitations (Issue H); (c) the force majeure defense (Issue F); and (d) the failure-to-mitigate defense (Issue C). This far exceeds the minimum requirement of addressing at least two of the four listed topics.
- **GPT-5.5: Pass.** The output includes a dedicated Section 5 titled “Contested Legal Issues.” It addresses multiple required topics, including damages measure/recoverability, failure to mitigate, force majeure, fraudulent inducement elements, scienter/attribution, and statute of limitations/discovery rule.

### C-022

Witness list includes Peggy Hausman with testimony summary ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L190))

- **Sonnet 4.6: Pass.** Section 6A of the witness list includes Margaret ('Peggy') Hausman as Witness No. 1, marked 'Will call,' with a detailed testimony summary covering Ridgeline's history, pre-EDA negotiations, her receipt of and reliance on the representations (PX-002, PX-003, PX-004, PX-006), materiality of the representations to the exclusivity grant and MAPCs, the Greenville lease and equipment, the effect of shortfalls, cure notice and termination decisions, when Ridgeline learned the true facts, and the replacement-distributor search. This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The witness list includes Margaret ("Peggy") Hausman as a will-call fact witness and provides a detailed summary of her expected testimony, including her reliance on Corbin Supply’s representations, the EDA negotiations, expenditures, breach impacts, and related issues.

### C-023

Witness list includes Ted Corbin III as adverse witness ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L198))

- **Sonnet 4.6: Pass.** Theodore 'Ted' Corbin III appears as witness #3 in Section 6A of the witness list. He is explicitly identified as a fact witness who is adverse (noted as 'adverse; Fed. R. Evid. 611(c)'). The entry includes a detailed summary of expected testimony covering his personal role in negotiations, sending pre-contract representations (PX-002, PX-003, PX-004, PX-006), the actual figures vs. represented figures, his receipt of the Findlay Memo and discussion with Findlay before signing, reaffirmation of representations on February 12, 2021, execution of EDA warranties, MAPC shortfalls, failure to submit remediation plan, absence of force majeure notice, and attribution of decline to 'market conditions.' He is designated as 'Will call.'
- **GPT-5.5: Pass.** The witness list in Section 6 includes Theodore (“Ted”) Corbin III as a fact witness, explicitly identified as adverse under Fed. R. Evid. 611(c). The summary of expected testimony includes his pre-contract representations, Corbin Supply’s actual capabilities, receipt/discussion of the Findlay Memo, reaffirmation of representations, and execution of EDA warranties.

### C-024

Witness list includes Marcus Findlay as adverse witness ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L206))

- **Sonnet 4.6: Pass.** Marcus Findlay is listed as witness #4 in Section 6A of the witness list. He is explicitly identified as an adverse witness under Fed. R. Evid. 611(c), with a detailed summary of expected testimony including his authorship of the January 15, 2021 Findlay Memo (PX-007), its contents regarding the actual figures (187 active accounts, 7 operational warehouses, 23 hydraulic representatives), the internal Year 1 forecast, and other relevant matters. This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The witness list includes Marcus Findlay as a fact/adverse witness and provides a detailed summary of his expected testimony, including authorship and contents of the January 15, 2021 Findlay Memo and actual figures for service centers, warehouses, and hydraulic representatives.

### C-025

Witness list includes Dr. Elaine Prescott as expert witness ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L214))

- **Sonnet 4.6: Pass.** Section 6B of the witness list includes Dr. Elaine Prescott, Ph.D., explicitly identified as an Expert (damages) witness, with a detailed summary of her qualifications and expected testimony covering damages calculations including Year 1-2 lost profits, gross margin analysis, Years 3-5 future lost profits, mitigation credits, reliance expenditures, and rebuttal of Holt's opinions.
- **GPT-5.5: Pass.** The witness list includes Dr. Elaine Prescott, Ph.D. under the Expert Witness section, identifies her as an expert in damages, and summarizes her expected testimony regarding lost profits, margins, mitigation credits, reliance expenditures, and damages calculations.

### C-026

Exhibit list includes key documents ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L222))

- **Sonnet 4.6: Pass.** The exhibit list in Section 8 includes: (1) PX-001 - Exclusive Distribution Agreement ✓; (2) PX-002 (Oct. 14, 2020 email) and PX-004 (Dec. 3, 2020 letter) - pre-contract correspondence ✓; (3) PX-007 - Findlay Memo ✓; (4) PX-018 - Greenville shipping hub lease ✓; (5) PX-033 - Expert Report of Dr. Elaine Prescott ✓. All 5 key documents are present, easily satisfying the requirement of at least 4 of 5.
- **GPT-5.5: Pass.** The plaintiff's exhibit list in Section 8 includes all five key documents: PX-001 Exclusive Distribution Agreement; PX-002 October 14 email and PX-004 December 3 letter; PX-007 Findlay Memo; PX-018 shipping hub lease; and PX-033 Dr. Prescott's expert report, plus damages summaries. This exceeds the requirement of at least 4 of 5.

### C-027

Motion in limine to exclude Gerald Voss's industry custom testimony included ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L230))

- **Sonnet 4.6: Fail.** The motions in limine section (Section 10) contains five plaintiff's motions in limine (MIL Nos. 1-5) and a table of anticipated defense motions. None of these motions mention Gerald Voss or any motion to exclude industry custom testimony regarding MAPC enforcement. Gerald Voss is not referenced anywhere in the document.
- **GPT-5.5: Fail.** The motions in limine section does not include any motion to exclude or limit Gerald Voss’s testimony, nor does it mention industry custom testimony regarding MAPC enforcement. The only witness-specific MIL concerns Warren Holt.

### C-028

Estimated trial time section included ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L238))

- **Sonnet 4.6: Pass.** Section 11 of the agent's output is explicitly titled 'ESTIMATED TRIAL TIME' and provides a detailed breakdown of trial phases, estimating a total of 6.25–7.5 days excluding deliberations, which is consistent with the 7-day jury trial estimate. The section notes that 'Ridgeline believes the case can be tried within the seven trial days the Court has allotted.'
- **GPT-5.5: Pass.** The output includes a dedicated Section 11 titled “Estimated Trial Time,” provides Plaintiff’s estimate, a proposed total trial schedule, and states the case can be tried within the seven trial days allotted by the Court, which is consistent with the criterion.

### C-029

Settlement status section included ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L246))

- **Sonnet 4.6: Pass.** The agent's output includes Section 12 titled 'SETTLEMENT STATUS' which addresses whether settlement discussions have occurred, whether further discussions would be productive, and consent to referral for a settlement conference.
- **GPT-5.5: Pass.** The output includes a clearly labeled Section 12 — Settlement Status, with subsections addressing prior discussions, productivity of further discussions, and consent to referral.

### C-030

Correct case number and court identification ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L254))

- **Sonnet 4.6: Pass.** The document clearly states 'Civil Action No. 2:23-cv-00417-KMG' in the caption and identifies the court as 'UNITED STATES DISTRICT COURT FOR THE WESTERN DISTRICT OF PENNSYLVANIA'. Both the case number and court identification are correct and present.
- **GPT-5.5: Pass.** The output identifies the court as the United States District Court for the Western District of Pennsylvania and includes Civil Action No. 2:23-cv-00417-KMG.

### C-031

Correct party identification in case caption ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L262))

- **Sonnet 4.6: Pass.** The case caption clearly identifies RIDGELINE MANUFACTURING, INC. as Plaintiff and CORBIN SUPPLY GROUP, LLC as Defendant. The parties are correctly identified and not swapped.
- **GPT-5.5: Pass.** The case caption correctly identifies Ridgeline Manufacturing, Inc. as Plaintiff and Corbin Supply Group, LLC as Defendant.

### C-032

Correct total damages figure stated ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L270))

- **Sonnet 4.6: Fail.** The agent's output provides the following damages breakdown: (1) Year 1-2 lost profits: $1,363,400 (34% margin on $4,010,000 shortfall); (2) Years 3-5 net future lost profits: $7,990,000 ($10,710,000 gross minus $2,720,000 Allegheny credit); (3) Reliance expenditures: $2,325,000 ($1,850,000 lease + $475,000 equipment). These three figures sum to $1,363,400 + $7,990,000 + $2,325,000 = $11,678,400, not $14,325,000. The criterion requires the total to be $14,325,000 (or equivalent breakdown: $4,010,000 + $7,990,000 + $2,325,000). The agent uses $1,363,400 (margin-adjusted lost profits) rather than $4,010,000 (gross shortfall) for the Count I damages component. The difference is $4,010,000 - $1,363,400 = $2,646,600, which is far more than $100,000. The agent explicitly states it is using the margin-adjusted figure and not the gross shortfall as a damages measure. This results in a total that is materially different from $14,325,000 without the output identifying a corrected figure that sums to $14,325,000. The criterion would pass if the breakdown summed to $14,325,000 using $4,010,000 as the breach component, but the agent uses $1,363,400 instead. The total of $11,678,400 is off by $2,646,600, well beyond the $100,000 threshold.
- **GPT-5.5: Fail.** The output does not state Ridgeline's total claimed damages as $14,325,000 or present the required damages breakdown of $4,010,000 + $7,990,000 + $2,325,000. Instead, it treats the $4,010,000 Year 1–2 MAPC shortfall as revenue and claims only $1,363,400 in lost profits for that component, yielding a materially different total without identifying it as a corrected lease-period adjustment.

### C-033

Correct Year 1 MAPC shortfall figure ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L278))

- **Sonnet 4.6: Pass.** The document states in Stipulated Fact 16: 'In Year 1, Corbin Supply purchased $5,120,000 of Ridgeline products, which was $880,000 below the $6,000,000 Year 1 MAPC.' This correctly identifies the Year 1 MAPC shortfall as $880,000. The figure is also referenced consistently elsewhere (e.g., Section 3, Issue 9: '$880,000 in Year 1').
- **GPT-5.5: Pass.** The output correctly states the Year 1 MAPC was $6,000,000, actual purchases were $5,120,000, and the Year 1 shortfall was $880,000 in multiple sections.

### C-034

Correct Year 2 MAPC shortfall figure ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L286))

- **Sonnet 4.6: Pass.** The document states in Stipulated Fact 18: 'In Year 2, Corbin Supply purchased $4,370,000 of Ridgeline products, which was $3,130,000 below the $7,500,000 Year 2 MAPC.' This correctly identifies the Year 2 MAPC shortfall as $3,130,000 ($7,500,000 - $4,370,000 = $3,130,000). The figure is also confirmed in Stipulated Fact 19 where the combined Year 1 and Year 2 shortfall is stated as $4,010,000 ($880,000 + $3,130,000 = $4,010,000), which is internally consistent.
- **GPT-5.5: Pass.** The output correctly states that in Year 2 Corbin Supply purchased $4,370,000 against a $7,500,000 MAPC, resulting in a $3,130,000 shortfall, and repeats that figure consistently.

### C-035

Correct future lost profits calculation ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L294))

- **Sonnet 4.6: Pass.** The output in Section 3, Issue 10 and Section 6 (Dr. Prescott's expert opinions) explicitly states: Years 3-5 MAPCs total $31,500,000 ($9M + $10.5M + $12M), multiplied by 34% gross margin = $10,710,000 gross lost profits, minus a $2,720,000 mitigation credit ($8,000,000 replacement sales × 34%), yielding net future lost profits of $7,990,000. This matches the criterion exactly.
- **GPT-5.5: Pass.** The output correctly states the future lost profits calculation: Years 3–5 MAPCs total $31.5 million, multiplied by a 34% gross margin equals $10,710,000, less a mitigation credit of $2,720,000 based on $8.0 million in replacement sales at 34%, yielding net future lost profits of $7,990,000.

### C-036

Identifies remaining claims as breach of contract and fraudulent inducement ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L302))

- **Sonnet 4.6: Pass.** The document clearly identifies both remaining claims throughout. Count I is explicitly identified as breach of contract (MAPC provisions) and Count II is explicitly identified as fraudulent inducement. This is stated in the preliminary note, in Section 3 (Issues 1-8 concern Count II fraudulent inducement; Issues 9-13 concern damages on Count I and Count II), in Section 5 (legal issues reference both counts), in Stipulated Facts 25-26 (liability on Count I established; Count II remains for jury on all elements), and throughout the contested factual and legal issues sections.
- **GPT-5.5: Pass.** The output expressly identifies Count I as breach of contract, with liability established and damages remaining, and Count II as fraudulent inducement remaining for jury determination on all elements.

### C-037

Does not include dismissed negligent misrepresentation claim ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L310))

- **Sonnet 4.6: Pass.** The agent's output only references Count I (breach of contract) and Count II (fraudulent inducement) as live claims going to trial. There is no mention of Count III or negligent misrepresentation as a remaining claim anywhere in the document. The output consistently treats the case as a two-count matter, with liability established on Count I and Count II going to the jury on all elements.
- **GPT-5.5: Pass.** The output identifies only Count I (breach of contract) and Count II (fraudulent inducement) as remaining issues for trial, and does not list Count III or negligent misrepresentation as a live claim.

### C-038

References partial summary judgment on breach liability ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L318))

- **Sonnet 4.6: Pass.** The output extensively references the partial summary judgment ruling. In the preliminary note, it references 'the Court granted partial summary judgment on November 15, 2024.' In Section 2 (Stipulated Facts), paragraphs 22-25 explicitly state that the Court determined as a matter of law that Corbin Supply breached the MAPC provisions, that Ridgeline properly issued its cure notice and terminated the EDA, that Ridgeline did not waive its rights, and that 'Liability on Count I is established. The jury will determine only the amount of Ridgeline's damages on Count I.' The document also references 'SJ Op.' (Summary Judgment Opinion) throughout, and Section 5 explicitly states 'Ridgeline does not ask the Court to revisit liability on Count I.' The criterion is clearly satisfied.
- **GPT-5.5: Pass.** The output repeatedly references the Court’s November 15, 2024 summary judgment ruling, states that Corbin Supply breached the MAPC provisions as a matter of law, that Ridgeline properly terminated, and that liability on Count I is established with only damages remaining, while fraudulent inducement remains for the jury.

### C-039

Motion in limine re materiality of MAPC breaches (law of the case) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L326))

- **Sonnet 4.6: Fail.** The criterion requires a motion in limine or argument to preclude Corbin Supply from arguing that the MAPC shortfalls were not material breaches, based on law of the case from the summary judgment ruling. Reviewing Section 10 (Motions in Limine), Plaintiff's MIL No. 3 addresses precluding relitigation of liability on Count I and the waiver/unclean-hands defenses. It states that the Court entered judgment on liability for breach of the MAPC provisions and moves to preclude Corbin Supply from suggesting it did not breach or that the breach was excused. However, this motion focuses on the existence of breach and the waiver/unclean-hands defenses, not specifically on the materiality of the MAPC breaches as a distinct issue. The criterion specifically asks for a motion/argument to preclude arguing the shortfalls were not 'material breaches.' While MIL No. 3 broadly covers relitigating liability, it does not specifically address the materiality element of the breach as a law-of-the-case argument. The document does not contain a specific motion or argument targeting Corbin Supply's ability to argue the MAPC shortfalls were not material breaches as a distinct law-of-the-case issue.
- **GPT-5.5: Pass.** The output includes Plaintiff's MIL No. 3, seeking to preclude Corbin Supply from relitigating Count I liability, including suggesting it did not breach or that the breach was excused, based on the Court's summary-judgment ruling. It also identifies that MAPC shortfalls were held breaches and that termination under the material-breach provision was proper. Although it does not use the exact phrase 'law of the case' or specifically say 'not material breaches,' it substantively seeks to bar relitigation of the already-decided MAPC breach/material termination issues at trial.

### C-040

Correct identification of Judge Gresham ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L334))

- **Sonnet 4.6: Pass.** The caption clearly identifies 'Hon. Katherine M. Gresham, United States District Judge' and the preliminary note references 'the Court's Pretrial Order dated February 10, 2025' with the judge's name appearing in the caption as required.
- **GPT-5.5: Pass.** The filing caption identifies the presiding judge as “Hon. Katherine M. Gresham” and also states “United States District Judge,” satisfying the criterion.

### C-041

Correct trial date stated ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L342))

- **Sonnet 4.6: Pass.** The document clearly states 'JURY TRIAL: SEPTEMBER 15, 2025' in the caption and references September 15, 2025 as the trial date in Section 11 (jury selection on morning of Sept. 15, 2025; opening statements on afternoon of Sept. 15, 2025) and Section 12 (before the September 15, 2025 trial date).
- **GPT-5.5: Pass.** The output states the trial date as "JURY TRIAL: SEPTEMBER 15, 2025" in the caption and also references the September 15, 2025 trial date elsewhere.

### C-042

Identifies EDA execution date correctly as March 1, 2021 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L350))

- **Sonnet 4.6: Pass.** The document repeatedly and consistently identifies the EDA execution date as March 1, 2021. For example, in the preliminary note: 'the Exclusive Distribution Agreement, Contract No. CSG-RM-2021-0301, dated and executed March 1, 2021'; in Stipulated Fact 11: 'On March 1, 2021, Ridgeline and Corbin Supply executed the Exclusive Distribution Agreement'; and in multiple other places throughout the document. The date is correctly stated as March 1, 2021.
- **GPT-5.5: Pass.** The output repeatedly identifies the Exclusive Distribution Agreement as dated and executed March 1, 2021, including in the preliminary note and stipulated fact 11.

### C-043

Correctly characterizes the 12-state southeastern territory ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L358))

- **Sonnet 4.6: Pass.** The document explicitly states in Stipulated Fact 12: 'The EDA appointed Corbin Supply as the exclusive distributor of Ridgeline's hydraulic product line in a twelve-state territory: Alabama, Arkansas, Florida, Georgia, Kentucky, Louisiana, Mississippi, North Carolina, South Carolina, Tennessee, Virginia, and West Virginia (EDA §§ 1.15, 2.1).' This correctly identifies all 12 states (AL, AR, FL, GA, KY, LA, MS, NC, SC, TN, VA, WV) in the southeastern region. The document also references 'twelve-state southeastern territory' in multiple other places throughout the document.
- **GPT-5.5: Pass.** The output correctly describes the exclusive distribution territory as a twelve-state southeastern territory and expressly lists the correct states: Alabama, Arkansas, Florida, Georgia, Kentucky, Louisiana, Mississippi, North Carolina, South Carolina, Tennessee, Virginia, and West Virginia.

### C-044

Mitigation credit correctly applied in damages ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L366))

- **Sonnet 4.6: Pass.** The output explicitly states in Section 3, Issue 10 and in Section 6 (Dr. Prescott's expert testimony): 'After a credit for the profit on replacement sales through Allegheny Industrial Partners ($3,200,000 per year for 2.5 years, or $8,000,000, at 34%, for a credit of $2,720,000), Ridgeline's net future lost profits are $7,990,000.' This exactly matches the criterion: 2.5 years × $3.2M/year × 34% margin = $2,720,000 mitigation credit applied against future lost profits.
- **GPT-5.5: Pass.** The output expressly applies a mitigation credit for replacement distributor Allegheny Industrial Partners: $3.2 million per year for 2.5 years equals $8 million, at a 34% margin, producing a $2,720,000 offset against future lost profits and net future lost profits of $7,990,000.

### C-045

Correctly identifies Ridgeline's gross margin as 34% ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L374))

- **Sonnet 4.6: Pass.** The agent's output consistently references Ridgeline's gross margin on distributor-channel sales as 34% throughout the document. This appears in Section 3 (Issues 9, 10), Section 5 (Issues A, B), Section 6 (Dr. Prescott's expert opinions), and elsewhere. The 34% figure is used as the basis for all lost-profit calculations without contradiction or alternative margin percentage being used.
- **GPT-5.5: Pass.** The output repeatedly identifies Ridgeline's gross margin on distributor-channel sales as 34%, including in damages Issues 9 and 10 and expert testimony summaries.

### C-046

Addresses Holt's challenge to future lost profits period ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L382))

- **Sonnet 4.6: Pass.** The agent's output explicitly addresses Holt's argument that future damages should be limited to twelve months. In Section 3, Issue 10(c), the output states: 'Corbin Supply's expert limits future damages to twelve months ($1,972,000) and uses Corbin Supply's declining performance as the baseline. Holt Rpt. § VII.B.' In Section 5, Issue B, the output directly frames the legal question as whether future damages must be 'limited to twelve months, or measured by Corbin Supply's pre-breach performance trend,' and argues that nothing in the EDA limits recovery to a twelve-month period and that measuring expectation damages against the breaching party's actual performance would reward the breach. The output also cites Holt's own deposition concession that the MAPC methodology 'is an accepted approach.' The criterion is clearly satisfied.
- **GPT-5.5: Pass.** The output expressly addresses Holt's alternative 12-month lost-profits period in multiple places, including Plaintiff's Contested Factual Issue 10, Legal Issue B, mitigation discussion, and the anticipated Daubert motion, and rebuts it by arguing damages should cover the remaining contract term using MAPCs with mitigation credit.
