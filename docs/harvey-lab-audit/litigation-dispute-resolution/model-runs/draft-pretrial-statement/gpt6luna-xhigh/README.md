# GPT-6 Luna (xhigh): Draft Plaintiff's Portion of Joint Pretrial Statement in Breach of Contract and Fraudulent Inducement Action

> [!NOTE]
> **Unedited model output and AI judge grades.** The deliverables are AI-generated drafts on Harvey LAB's fictional task records. Pass/fail verdicts are the native LAB judges' AI judgments, not human review or accepted corrections. See the [model-runs overview](../../README.md).

[Task audit page](../../../tasks/draft-pretrial-statement/README.md) · [Pinned task and rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json) · [Claude Opus 5.5 (low) run](../opus55-low/README.md) · [All runs](../../README.md)

**Model:** `gpt-6-luna`, reasoning effort `xhigh`. **Run:** `20260926-201603`.

**Native grades:** Sonnet 4.6 passed 41 of 46 criteria; GPT-5.5 passed 43 of 46 criteria. LAB all-pass score: 0 (mean of the judges' all-pass results; a task scores 1 with a judge only if every criterion passes).

## Deliverables

- [plaintiff-pretrial-statement.docx](output/plaintiff-pretrial-statement.docx) ([read as Markdown](output/plaintiff-pretrial-statement.docx.md))

## Grades

Failures are in bold. Each criterion links to both judges' reasoning below.

| Criterion | Title | Sonnet 4.6 | GPT-5.5 |
|---|---|---|---|
| [C-001](#c-001) | ISSUE_001: Identifies lease period discrepancy in reliance damages | Pass | Pass |
| [C-002](#c-002) | ISSUE_002: Addresses duplicative damages theory (expectation vs. reliance) | Pass | Pass |
| [C-003](#c-003) | ISSUE_003a: Addresses statute of limitations defense on fraud claim with 2-year period | Pass | Pass |
| [C-004](#c-004) | ISSUE_003b: Invokes discovery rule for fraud statute of limitations | Pass | Pass |
| [C-005](#c-005) | ISSUE_003: Explains why discovery rule saves fraud claim | **Fail** | Pass |
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
| [C-032](#c-032) | Correct total damages figure stated | Pass | Pass |
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

- **Sonnet 4.6: Pass.** The agent's output explicitly addresses the lease period discrepancy in Section 3, Issue 6 (Reliance Expenditures). It notes that Prescott calculated $2,325,000 but 'acknowledged that limiting lease loss to the post-termination period would reduce the lease portion to approximately $770,833.35 and the total reliance amount to approximately $1,245,833.35.' This directly identifies the distinction between the full lease cost and the recoverable post-termination portion (~15 months at ~$51,388.89/month). The output does not simply claim the full $1,850,000 without discussion; it explicitly flags the timing issue and the alternative calculation. This satisfies the criterion.
- **GPT-5.5: Pass.** The output explicitly identifies the timing issue: the lease ran June 1, 2021 to May 31, 2024, while termination occurred March 10, 2023, and it notes that limiting lease loss to the post-termination period reduces the lease portion to approximately $770,833.35. It also acknowledges that claiming the full lease/equipment amount requires allocation, consideration of value received, and avoidance of double recovery.

### C-002

ISSUE_002: Addresses duplicative damages theory (expectation vs. reliance) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L30))

- **Sonnet 4.6: Pass.** The agent's output extensively addresses the tension between expectation and reliance damages. In Section 3 (Contested Factual Issue 6), it explicitly notes that 'the amount of any recoverable fraud reliance loss must account for value received, residual/redeployment value, and any overlap with expectation damages without a double recovery.' In Section 5C, it frames the legal issue as 'Availability and allocation of reliance damages on Count II; no double recovery' and states 'the verdict should allocate any award and exclude any proven overlap.' The output also allocates reliance damages to the fraud claim (Count II) rather than the breach of contract claim (Count I), explicitly treating them as 'distinct theories and categories if the evidence establishes separate loss.' Section 5H addresses the contractual exclusion and notes Plaintiff does not seek consequential damages. The Prescott report discussion acknowledges the alternative calculation reducing reliance damages if limited to post-termination period. Throughout, the output flags the non-duplication requirement and proposes the reconciliation approach of allocating reliance damages to the fraud count while keeping expectation damages on the contract count. This satisfies the criterion.
- **GPT-5.5: Pass.** The output expressly recognizes the potential overlap between contract expectation/lost-profit damages and reliance expenditures for the Greenville hub and packaging equipment. It allocates reliance damages to the fraudulent inducement claim, discusses value received/residual value and overlap, includes a contested legal issue on avoiding double recovery, and states Plaintiff does not seek duplicate recovery. This satisfies the criterion.

### C-003

ISSUE_003a: Addresses statute of limitations defense on fraud claim with 2-year period ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L38))

- **Sonnet 4.6: Pass.** The output extensively addresses the statute of limitations defense on the fraud claim. In Section 3 (Contested Factual Issue 7), it discusses the discovery rule and the two-year fraud limitations period, citing 42 Pa. C.S. § 5524(7) and Fine v. Checcio. In Section 4 (Defendant's Contested Issue 7), it notes that the alleged communications began October 14, 2020 and the Complaint was filed March 10, 2023, explicitly identifying that this is more than two years after the earliest misrepresentation. In Section 5(E), it addresses the statute of limitations as a contested legal issue, again citing 42 Pa. C.S. § 5524(7) and the discovery rule. The output clearly addresses the 2-year period, the timing of the misrepresentations (Oct 2020–Feb 2021), and the March 10, 2023 filing date.
- **GPT-5.5: Pass.** The output addresses the fraudulent inducement statute-of-limitations defense multiple times. It cites Pennsylvania’s two-year fraud limitations period under 42 Pa. C.S. § 5524(7), discusses the discovery rule, states that the alleged communications/statements occurred from October 2020 to February 2021, and notes the Complaint was filed March 10, 2023, more than two years after the earliest alleged misrepresentation.

### C-004

ISSUE_003b: Invokes discovery rule for fraud statute of limitations ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L46))

- **Sonnet 4.6: Pass.** The output explicitly invokes the discovery rule multiple times in connection with the fraud statute of limitations. In Section 3 (Contested Factual Issue 7), it argues that Ridgeline 'did not know, and through reasonable diligence could not reasonably have known, the specific falsity' and cites Fine v. Checcio for the discovery rule. In Section 5.E, it frames the legal issue as whether the claim 'is time-barred under Pennsylvania's two-year period or tolled until Ridgeline knew or reasonably should have known of the alleged fraud,' explicitly stating 'the discovery-rule trigger is a jury issue on this record' and citing 42 Pa. C.S. § 5524(7) and Fine v. Checcio, 582 Pa. 253, 266-67 (2005). The output clearly invokes the discovery rule throughout.
- **GPT-5.5: Pass.** The output explicitly invokes the discovery rule in connection with the fraud statute of limitations, stating that the fraud limitations period is tolled until Ridgeline knew or reasonably should have known of the fraud, and citing Fine v. Checcio and 42 Pa. C.S. § 5524(7).

### C-005

ISSUE_003: Explains why discovery rule saves fraud claim ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L54))

- **Sonnet 4.6: Fail.** Section 3, Issue 7 (Discovery and reasonable diligence for statute-of-limitations purposes) and Section 5E both explain the discovery rule argument. The output states that Hausman testified the Year 1 shortfall could reflect ordinary onboarding or market factors, that concerns about the worsening Year 2 trend arose in fall 2022, and that Ridgeline did not learn the actual 187/7/23 figures and the Findlay memo until Corbin's document productions in November–December 2023. It also notes the Complaint was filed March 10, 2023, and that Corbin has not shown reasonable diligence would have revealed those facts more than two years before suit. However, there is a tension: the filing date is March 10, 2023, but the output says the specific falsity was learned from discovery productions in November–December 2023 (after filing). The output does not clearly reconcile this—it does not explain how the March 10, 2023 filing was timely if the specific falsity wasn't discovered until late 2023. It mentions fall 2022 concerns about Year 2 trends but does not squarely argue that this (or some earlier date within two years of filing) is when discovery occurred or should have occurred, making the filing timely. The criterion requires explaining when Ridgeline actually discovered or should have discovered the fraud in a way that makes the March 10, 2023 filing timely. The output gestures at this but does not clearly articulate the timeline that saves the claim—it actually undermines it by saying specific falsity wasn't known until late 2023 (post-filing). The discovery rule explanation is incomplete and internally inconsistent regarding the filing date.
- **GPT-5.5: Pass.** The output discusses the discovery rule in Sections 3.7 and 5.E, explaining that Ridgeline did not learn the specific falsity of Corbin’s representations until Corbin’s document productions in late 2023, and that earlier shortfalls or concerns did not reveal the concealed facts. It also frames the limitations issue around whether Ridgeline knew or should have known more than two years before filing and notes the March 10, 2023 complaint date. This sufficiently explains when the fraud was actually or reasonably discoverable and why the claim is timely under the discovery rule.

### C-006

ISSUE_004: Motion in limine to exclude force majeure defense evidence ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L62))

- **Sonnet 4.6: Pass.** Section 10.E of the output explicitly anticipates a motion in limine to 'Preclude unsupported force-majeure defense absent notice or proof of excuse.' It cites EDA § 12.1(b) as requiring written notice, notes that Corbin III could identify no notice and Rinaldi's records search found none, and argues that general pandemic conditions alone do not establish contractual notice. This directly satisfies the criterion requiring a motion in limine citing the Section 12.1 notice requirement and the absence of any notice as the basis for exclusion.
- **GPT-5.5: Pass.** The output includes a specific anticipated motion in limine titled “Preclude unsupported force-majeure defense absent notice or proof of excuse,” arguing that EDA § 12.1(b) required written notice, that Corbin III could identify no notice and Ridgeline found none, and that the defense should be precluded absent compliance or excuse. It also elsewhere states the 30-day written notice requirement and absence of notice.

### C-007

ISSUE_005: Argues Findlay memo is not excludable under FRE 407 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L70))

- **Sonnet 4.6: Fail.** The agent's output is a comprehensive pretrial statement covering 12 sections. The motions in limine section (Section 10) addresses several anticipated motions but does not include any motion or argument opposing a Corbin Supply motion to exclude the Findlay memo under FRE 407 (subsequent remedial measures). The Findlay memo is referenced extensively throughout the document as substantive evidence, but nowhere does the agent argue that FRE 407 is inapplicable because the memo predates the contract execution (January 15, 2021 memo vs. March 1, 2021 EDA execution) and therefore cannot be a 'subsequent remedial measure.' The criterion requires the output to specifically oppose a Corbin FRE 407 motion by arguing the memo predates the contract/breach and falls outside FRE 407's scope. This argument is entirely absent from the output.
- **GPT-5.5: Fail.** The output identifies and relies on the January 15, 2021 Findlay memo, but it does not address any Corbin Supply motion in limine under FRE 407, nor does it argue that Rule 407 applies only to post-injury remedial measures and that the memo predates the March 1, 2021 EDA and any breach. Therefore it does not satisfy the specified criterion.

### C-008

ISSUE_006: Acknowledges trade usage exception weakness in parol evidence motion ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L78))

- **Sonnet 4.6: Fail.** The agent's output contains five motions in limine (Sections A through E), none of which involve Gerald Voss or a parol evidence motion to exclude industry custom/trade usage testimony. The criterion specifically requires that the output, in connection with a motion to exclude Gerald Voss's industry custom testimony under the parol evidence rule, acknowledge the weakness that trade usage evidence is generally admissible even with an integration clause. Since the output does not include any such motion or any mention of Gerald Voss, it cannot satisfy this criterion.
- **GPT-5.5: Fail.** The output does not include any motion in limine concerning Gerald Voss's industry custom testimony or a parol-evidence argument, and it does not acknowledge that trade usage/industry custom evidence is generally admissible despite an integration clause under UCC § 1-303/common law or that the EDA's integration clause does not expressly exclude trade usage. Thus it does not satisfy the required acknowledgement.

### C-009

ISSUE_007: Defends Dr. Prescott's future lost profits against Daubert challenge ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L86))

- **Sonnet 4.6: Pass.** Section 5.G (Expert admissibility and scope) addresses the Daubert issue for both experts. It states that 'Prescott's disclosed opinions use contract MAPCs, audited financial data, a disclosed 34% gross margin, and an express mitigation credit; her opinions are within the disclosed report.' This directly argues that the methodology is reliable because it is grounded in contractual MAPCs (fixed, agreed-upon numbers) and a 34% gross margin supported by audited financials. The section also notes the Court deferred Daubert issues for pretrial motions. Additionally, Section 4.4 (Defendant's contested issue on future lost profits) and Section 5.A (measure of Count I damages) further discuss the MAPC-based methodology and Prescott's projections. The output thus addresses the anticipated Daubert challenge to future lost profits and explains why the methodology is reliable, satisfying the criterion.
- **GPT-5.5: Pass.** The output expressly anticipates Corbin's Daubert/Rule 702 challenge to Dr. Prescott's future-loss methodology and defends it by stating that her Years 3–5 projections use the contractual MAPCs, audited financial data, a disclosed 34% gross margin, and a mitigation credit. It also argues in the contested legal issues section that the MAPCs are bargained-for minimums and that future lost profits are supported by purchase records, audited historical margins, and expert opinions, rather than speculation.

### C-010

ISSUE_008: David Rinaldi included on witness list ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L94))

- **Sonnet 4.6: Pass.** David Rinaldi is listed as witness #4 in Section 6 (Plaintiff's Witness List), described as a fact witness who will testify live about EDA negotiations, MAPC derivation, cure notice, termination, mitigation search, force-majeure notice search, Greenville lease, and related matters.
- **GPT-5.5: Pass.** The plaintiff's witness list in Section 6 includes David Rinaldi as witness number 4, with address, expected testimony, and estimated direct examination time.

### C-011

ISSUE_008: Rinaldi testimony summary covers key topics ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L102))

- **Sonnet 4.6: Pass.** The witness list entry for David Rinaldi explicitly states he will testify about 'EDA negotiations and MAPC derivation; cure notice and failure to receive a formal remediation plan; termination...' This covers both his role in negotiating the EDA's MAPC terms and his communications regarding the cure notice, satisfying the criterion.
- **GPT-5.5: Pass.** The output lists David Rinaldi as a fact witness and summarizes his expected testimony as including “EDA negotiations and MAPC derivation” and “cure notice and failure to receive a formal remediation plan,” satisfying both alternative topics in the criterion.

### C-012

ISSUE_009: Addresses mitigation timing gap (6-month delay) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L110))

- **Sonnet 4.6: Pass.** The output extensively addresses the 6-month mitigation gap in multiple sections. In Section 3 (Contested Factual Issue #5), it explicitly states the approximately six-month period from termination to Allegheny's effective date was commercially reasonable, and details the steps taken: identifying candidates, contacting five, two declining, vetting three, visiting facilities, checking finances and references, selecting Allegheny in July, and completing negotiations, systems integration, and training before September 1, 2023. In Section 5.B, it argues the six-month replacement process was commercially reasonable for a vetted exclusive partner across 12 states, especially given Corbin's inaccurate capability claims. The output also notes Prescott's opinion that four to nine months is typical and six months is on the faster end. The justification is thorough and directly addresses why the delay was reasonable.
- **GPT-5.5: Pass.** The output expressly acknowledges the approximately six-month period from Ridgeline’s March 10, 2023 termination to Allegheny’s September 1, 2023 effective date and states Ridgeline’s position that the period was commercially reasonable. It justifies the timing with evidence of identifying candidates, vetting, site visits, financial/reference checks, negotiations, systems integration, and training for a multi-state distributor replacement.

### C-013

ISSUE_010a: Connects Findlay memo to Ted Corbin III's knowledge ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L118))

- **Sonnet 4.6: Pass.** The agent's output connects the Findlay memo to Ted Corbin III's knowledge in multiple places. In Section 3.2 (Corbin's knowledge, recklessness, and intent), it states: 'Findlay testified that Corbin III was on the distribution list, reported directly to him, and discussed the memo with him before execution; Findlay recalled Corbin III saying he had seen it and that Corbin would "grow into the numbers." (Findlay Dep. Tr. 8:12--16:5, 22:3--44:18.) Corbin testified he "may have seen" the memo and could not specifically recall reading it.' This satisfies criteria (a) by noting the memo was addressed to Senior Leadership, (b) by noting Findlay reported directly to Corbin III, and (c) by noting Corbin III's 'may have seen' admission from his deposition.
- **GPT-5.5: Pass.** The output explicitly connects the January 15, 2021 Findlay memo to Ted Corbin III’s knowledge by stating that the memo was addressed to Senior Leadership, that Findlay testified Corbin III was on the distribution list and reported directly to him, that Findlay discussed the memo with him before execution, and that Corbin III testified he “may have seen” the memo.

### C-014

ISSUE_010b: Articulates how Findlay memo supports scienter ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L126))

- **Sonnet 4.6: Pass.** The output extensively discusses how the Findlay memo supports scienter in Section 3, Issue 2 ('Corbin's knowledge, recklessness, and intent to induce the EDA'). It explains that the January 15, 2021 internal memo to 'Senior Leadership' described the MAPCs as 'aggressive,' outlined a plan to 'renegotiate or exit after year one,' and recorded the actual figures (187 active centers, 7 warehouses, 23 hydraulic reps) — all contradicting the representations made to Ridgeline. The output further articulates that Findlay testified Corbin III was on the distribution list, discussed the memo with him before execution, and that Corbin III said he had seen it and that Corbin would 'grow into the numbers.' This is directly tied to scienter: Corbin's leadership knew or recklessly disregarded that their representations were materially overstated. The memo is also referenced in Section 4 (Defendant's contested facts on scienter), Section 5.D (legal elements of fraudulent inducement), and the witness list. The output clearly articulates how the Findlay memo supports scienter for the fraudulent inducement claim.
- **GPT-5.5: Pass.** The output expressly explains that the January 15, 2021 Findlay memo was sent to senior leadership, identified the MAPCs as aggressive, recorded actual capabilities of 187 service centers, seven warehouses, and 23 hydraulic representatives, and discussed a plan to renegotiate or exit. It further ties the memo to Ted Corbin III’s knowledge through distribution and discussions before execution, thereby articulating how Corbin leadership knew or recklessly disregarded that the representations were false when made.

### C-015

ISSUE_010: Identifies specific misrepresentations contradicted by internal documents ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L134))

- **Sonnet 4.6: Pass.** The output explicitly identifies all three misrepresentations with both the represented and actual figures: (1) 300+ OEM service centers vs. actual 187 (CRM reflected 187 active accounts); (2) 11 operational warehouses vs. actual 7 operational (seven operational warehouses at signing, not eleven); (3) 42 dedicated sales representatives vs. actual 23 (hydraulic roster listed 23 representatives). These appear in Section 3, Contested Factual Issue 1, with specific citations to supporting evidence.
- **GPT-5.5: Pass.** The output specifically identifies all three misrepresentations with represented versus actual figures: 300+ service centers versus 187 active accounts, 11 warehouses versus 7 operational warehouses, and 42 dedicated hydraulic representatives versus 23 representatives, citing internal records and the Findlay memo.

### C-016

Jurisdictional statement identifies diversity jurisdiction under 28 U.S.C. § 1332 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L142))

- **Sonnet 4.6: Pass.** Section 1 of the output explicitly states: 'Subject-matter jurisdiction is based on diversity of citizenship under 28 U.S.C. § 1332(a)(1).' This clearly identifies diversity jurisdiction under 28 U.S.C. § 1332 as the basis for federal jurisdiction.
- **GPT-5.5: Pass.** The output includes a dedicated “SECTION 1. JURISDICTIONAL STATEMENT” and expressly states that subject-matter jurisdiction is based on diversity of citizenship under 28 U.S.C. § 1332(a)(1).

### C-017

Jurisdictional statement identifies citizenship of both parties ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L150))

- **Sonnet 4.6: Pass.** Section 1 of the jurisdictional statement identifies Ridgeline Manufacturing, Inc. as a Pennsylvania corporation with its principal place of business in Butler, Pennsylvania, and identifies Corbin Supply Group, LLC as organized under Delaware law with principal offices in Charlotte, North Carolina. Both parties' citizenship information is present and correct, satisfying the criterion.
- **GPT-5.5: Pass.** The jurisdictional statement identifies Ridgeline as a Pennsylvania corporation with its principal place of business in Pennsylvania, and Corbin Supply as a Delaware LLC with principal offices in Charlotte, North Carolina. Although it notes LLC member citizenship must be confirmed, the criterion is satisfied by identifying these party citizenship-related facts.

### C-018

Jurisdictional statement identifies amount in controversy ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L158))

- **Sonnet 4.6: Pass.** The jurisdictional statement in Section 1 explicitly states: 'The amount in controversy exceeds $75,000, exclusive of interest and costs.' This directly satisfies the criterion.
- **GPT-5.5: Pass.** The jurisdictional statement expressly states that the amount in controversy exceeds $75,000, exclusive of interest and costs.

### C-019

Stipulated facts section includes key stipulations ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L166))

- **Sonnet 4.6: Pass.** Section 2 (Stipulated Facts) contains all 7 stipulations: (1) EDA executed March 1, 2021 (¶3); (2) Year 1 purchases $5.12M (¶5); (3) Year 2 purchases $4.37M (¶5); (4) cure notice sent March 15, 2022 (¶6); (5) Corbin did not cure within 60 days (¶6); (6) EDA terminated March 10, 2023 (¶7); (7) Court granted partial summary judgment on MAPC breach liability (¶8). All 7 are present, exceeding the threshold of 6.
- **GPT-5.5: Pass.** The output includes a Section 2 titled “Stipulated Facts” and lists all seven required stipulations: execution of the EDA on March 1, 2021; Year 1 purchases of $5.12 million; Year 2 purchases of $4.37 million; March 15, 2022 cure notice; failure to cure within 60 days; March 10, 2023 termination; and partial summary judgment finding breach of the MAPC provisions.

### C-020

Contested factual issues section included ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L174))

- **Sonnet 4.6: Pass.** Section 3 of the output is explicitly titled 'PLAINTIFF'S CONTESTED FACTUAL ISSUES' and addresses all three required topics: (a) the nature and extent of pre-contract misrepresentations (Issues 1 and 3 cover the falsity and scope of capability representations and reliance/inducement); (b) damages amounts (Issues 4, 5, and 6 cover MAPC shortfall damages, lost profits, mitigation, and reliance expenditures); and (c) whether Corbin knew its representations were false (Issue 2 directly addresses Corbin's knowledge, recklessness, and intent). All three criteria are clearly addressed.
- **GPT-5.5: Pass.** The output includes a dedicated Section 3 titled "Plaintiff's Contested Factual Issues." It addresses the nature and extent of Corbin Supply's alleged pre-contract misrepresentations, damages amounts including MAPC shortfalls, future lost profits, and reliance expenditures, and whether Corbin knew or recklessly disregarded that its representations were false.

### C-021

Contested legal issues section included ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L182))

- **Sonnet 4.6: Pass.** Section 5 (Contested Legal Issues) addresses: (A) measure of Count I damages including MAPC shortfalls and future lost profits; (B) failure to mitigate/replacement-distributor period; (C) availability and allocation of reliance damages; (D) elements and proof standard for fraudulent inducement including scienter; (E) statute of limitations and discovery rule on Count II; (F) force majeure under EDA § 12.1; and more. This clearly covers all four specified topics: damages measure, fraudulent inducement elements (including scienter and statute of limitations), force majeure defense, and failure-to-mitigate defense.
- **GPT-5.5: Pass.** The output includes a dedicated SECTION 5 titled “CONTESTED LEGAL ISSUES.” It addresses multiple required topics, including damages measure/recoverability, fraudulent inducement elements and statute of limitations, force majeure, and failure to mitigate.

### C-022

Witness list includes Peggy Hausman with testimony summary ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L190))

- **Sonnet 4.6: Pass.** The witness list in Section 6 includes Margaret 'Peggy' Hausman as Witness #1 with a detailed testimony summary covering Ridgeline's business, negotiations, Corbin's representations, MAPC formation, decision to enter the EDA, reliance and capital expenditures, Corbin's performance and termination, discovery of actual capabilities, and mitigation/search for Allegheny. This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The witness list includes Margaret “Peggy” Hausman as a fact witness and provides a detailed summary of her expected testimony, including Corbin’s representations, Ridgeline’s decision to enter the EDA, reliance, capital expenditures, performance/termination, and mitigation.

### C-023

Witness list includes Ted Corbin III as adverse witness ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L198))

- **Sonnet 4.6: Pass.** The witness list in Section 6 explicitly includes Theodore 'Ted' Corbin III as witness #2, identified as a 'Fact/adverse witness; live, called by Plaintiff under Fed. R. Evid. 611(c).' The summary of expected testimony covers his negotiations, authorship of pre-contract representations, actual service-center/warehouse/sales-force figures, receipt/knowledge of the Findlay memo, performance, cure, COVID/force-majeure position, and purchase shortfalls. This satisfies all elements of the criterion.
- **GPT-5.5: Pass.** The witness list includes Theodore “Ted” Corbin III as a fact/adverse witness called under Fed. R. Evid. 611(c), with expected testimony covering pre-contract representations, actual capabilities, knowledge of the Findlay memo, performance, and related issues.

### C-024

Witness list includes Marcus Findlay as adverse witness ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L206))

- **Sonnet 4.6: Pass.** Marcus Findlay is listed as witness #3 in Section 6 (Plaintiff's Witness List), identified as a 'Fact/adverse witness; live, called by Plaintiff under Fed. R. Evid. 611(c),' with a detailed summary of expected testimony covering authorship of the January 15, 2021 memo, actual operating capabilities, the 23-person hydraulic sales force, seven operational warehouses, and pre-signing conversations with Corbin III.
- **GPT-5.5: Pass.** The witness list includes Marcus Findlay as a fact/adverse witness and summarizes his expected testimony regarding the January 15, 2021 memo, actual operating capabilities, the 23-person hydraulic sales force, and seven operational warehouses.

### C-025

Witness list includes Dr. Elaine Prescott as expert witness ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L214))

- **Sonnet 4.6: Pass.** Dr. Elaine Prescott is listed as witness #5 in Section 6 (Plaintiff's Witness List), explicitly identified as an 'Expert witness; live,' with her business address, qualifications (Ph.D. in Economics, Carnegie Mellon University, 20+ years forensic economics experience), and a detailed summary of her expected testimony covering the $4.01 million MAPC shortfalls, $7.99 million net future lost profits, and $2.325 million reliance expenditures damages calculations.
- **GPT-5.5: Pass.** The plaintiff's witness list includes Dr. Elaine Prescott as an expert witness and summarizes her expected testimony regarding damages calculations, including MAPC shortfalls, future lost profits, mitigation credit, and reliance expenditures.

### C-026

Exhibit list includes key documents ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L222))

- **Sonnet 4.6: Pass.** The exhibit list in Section 8 includes: (1) PX-001: Executed Exclusive Distribution Agreement; (2) PX-004: October 14, 2020 email and PX-006: December 3, 2020 letter (pre-contract correspondence); (3) PX-007: Findlay internal strategy memo; (4) PX-016: Hargrove Logistics lease (shipping hub lease); (5) PX-025: Expert Report of Dr. Elaine Prescott. All 5 key documents are present, satisfying the criterion of at least 4 of 5.
- **GPT-5.5: Pass.** The plaintiff's exhibit list includes all five key documents: the Exclusive Distribution Agreement (PX-001), pre-contract correspondence including the October 14 email and December 3 letter (PX-004, PX-006), the Findlay strategy memo (PX-007), the shipping hub lease (PX-016), and Dr. Prescott's expert report (PX-025).

### C-027

Motion in limine to exclude Gerald Voss's industry custom testimony included ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L230))

- **Sonnet 4.6: Fail.** The motions in limine section (Section 10) contains five anticipated motions: (A) preclude relitigation of Count I liability, (B) limit Holt's opinions on distributor-transition timing, (C) exclude Holt's equipment residual-value opinion, (D) limit Holt from giving legal conclusions on duplicative damages, and (E) preclude unsupported force-majeure defense. There is no mention of Gerald Voss or any motion to exclude or limit testimony on industry custom regarding MAPC enforcement. The criterion requires such a motion to be present for a PASS.
- **GPT-5.5: Fail.** The motions in limine section lists motions regarding relitigation of liability, Holt's opinions, duplicative damages, and force majeure, but it does not include any motion to exclude or limit Gerald Voss's industry custom testimony regarding MAPC enforcement. Gerald Voss is not mentioned.

### C-028

Estimated trial time section included ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L238))

- **Sonnet 4.6: Pass.** Section 11 of the agent's output is explicitly titled 'ESTIMATED TRIAL TIME' and states that Plaintiff's good-faith estimate for its case-in-chief is approximately three trial days, and references the Court's seven-day total trial estimate, consistent with the 7-day jury trial.
- **GPT-5.5: Pass.** The output includes a dedicated SECTION 11 titled 'ESTIMATED TRIAL TIME' and explicitly references the Court's seven-day trial estimate, stating Plaintiff does not request additional time beyond the seven days allotted and proposing a seven-day total planning estimate.

### C-029

Settlement status section included ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L246))

- **Sonnet 4.6: Pass.** The output includes Section 12 titled 'SETTLEMENT STATUS' which addresses settlement discussions, referral to mediator, and related matters, even though it contains bracketed placeholders requiring counsel completion.
- **GPT-5.5: Pass.** The output includes a clearly labeled 'SECTION 12. SETTLEMENT STATUS' with placeholders for counsel to complete regarding settlement discussions and mediation referral.

### C-030

Correct case number and court identification ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L254))

- **Sonnet 4.6: Pass.** The document header clearly states 'Case No. 2:23-cv-00417-KMG' and identifies the court as 'UNITED STATES DISTRICT COURT FOR THE WESTERN DISTRICT OF PENNSYLVANIA'. Both the case number and court identification are correct and present.
- **GPT-5.5: Pass.** The output correctly identifies the United States District Court for the Western District of Pennsylvania and includes the case number 2:23-cv-00417-KMG.

### C-031

Correct party identification in case caption ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L262))

- **Sonnet 4.6: Pass.** The case caption clearly identifies RIDGELINE MANUFACTURING, INC. as Plaintiff and CORBIN SUPPLY GROUP, LLC as Defendant. The parties are correctly identified and not swapped.
- **GPT-5.5: Pass.** The case caption identifies RIDGELINE MANUFACTURING, INC. as Plaintiff and CORBIN SUPPLY GROUP, LLC as Defendant, matching the criterion.

### C-032

Correct total damages figure stated ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L270))

- **Sonnet 4.6: Pass.** The agent's output states in Section 1 that 'Ridgeline's expert has calculated economic damages of $14,325,000 before any allocation or adjustment to avoid duplicative recovery.' In Section 4 (Count I damages), it breaks down the components: $4,010,000 in shortfall amounts (Year 1: $880,000 + Year 2: $3,130,000) and $7,990,000 in net future lost profits, plus in Section 6 (reliance damages) $2,325,000 in reliance expenditures. These sum to $14,325,000, matching the stated total. The agent also notes the lease period issue (ISSUE_001) by acknowledging that limiting lease loss to the post-termination period would reduce the lease portion to approximately $770,833.35 and the total reliance amount to approximately $1,245,833.35, which constitutes an explanation of the adjustment. The damages figure is correctly stated and the adjustment is explained.
- **GPT-5.5: Pass.** The output expressly states that Ridgeline's expert calculated economic damages of $14,325,000 and also provides the component breakdown of $4,010,000 in shortfalls, $7,990,000 in future lost profits, and $2,325,000 in reliance expenditures, which sums to the required figure. It also notes a possible adjusted reliance amount for the lease-period issue.

### C-033

Correct Year 1 MAPC shortfall figure ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L278))

- **Sonnet 4.6: Pass.** The document states in Stipulated Fact #5: 'Corbin purchased $5,120,000 in Year 1, $880,000 below the Year 1 MAPC' and in Section 3 Contested Factual Issue #4: 'Actual Year 1 and Year 2 purchase shortfalls are $880,000 and $3,130,000, respectively.' The Year 1 MAPC shortfall is correctly stated as $880,000 throughout the document.
- **GPT-5.5: Pass.** The output correctly states that Corbin purchased $5,120,000 in Year 1, which was $880,000 below the Year 1 MAPC, and repeats the $880,000 Year 1 shortfall elsewhere.

### C-034

Correct Year 2 MAPC shortfall figure ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L286))

- **Sonnet 4.6: Pass.** The document states in Stipulated Fact #5: 'Corbin purchased $5,120,000 in Year 1, $880,000 below the Year 1 MAPC, and $4,370,000 in Year 2, $3,130,000 below the Year 2 MAPC.' The Year 2 MAPC shortfall is correctly stated as $3,130,000.
- **GPT-5.5: Pass.** The output correctly states that Corbin purchased $4,370,000 in Year 2, which was $3,130,000 below the Year 2 MAPC, and repeats the correct $3.13M shortfall elsewhere.

### C-035

Correct future lost profits calculation ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L294))

- **Sonnet 4.6: Pass.** The agent's output states in Section 4 (Defendant's contested factual issues, item 4) that Prescott calculates '$7.99 million net future lost profits using Years 3–5 MAPCs and an Allegheny mitigation credit.' In Section 3 (item 4), the output states: 'Prescott calculates $4,010,000 in shortfall amounts and $7,990,000 in net future lost profits for Years 3--5, using MAPCs and a 34% margin, less a $2,720,000 mitigation credit.' The criterion requires: Years 3-5 MAPCs = $31.5M × 34% = $10,710,000, minus mitigation credit of $2,720,000 ($8.0M × 34%) = $7,990,000. The agent's output correctly states the net future lost profits figure of $7,990,000 and correctly identifies the components: Years 3-5 MAPCs, 34% margin, and $2,720,000 mitigation credit. The math is consistent: $10,710,000 - $2,720,000 = $7,990,000. The output does not explicitly state the intermediate $10,710,000 figure, but it correctly identifies all the inputs and the final result of $7,990,000, which matches the criterion's required calculation.
- **GPT-5.5: Pass.** The output states that Prescott calculates net future lost profits of $7,990,000 for Years 3–5 using the MAPCs and a 34% margin, less a $2,720,000 mitigation credit. Although it does not spell out every intermediate number in one place, the stated net figure and methodology match the required calculation.

### C-036

Identifies remaining claims as breach of contract and fraudulent inducement ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L302))

- **Sonnet 4.6: Pass.** The document clearly identifies both remaining claims. In the introduction, it states 'Count I proceeds for damages only' (breach of contract/MAPC provisions) and 'Count II (fraudulent inducement)...remain for trial.' Throughout the document, both counts are repeatedly referenced and addressed in detail, including in the contested factual issues, contested legal issues, and motions in limine sections.
- **GPT-5.5: Pass.** The output expressly identifies Count I as the breach of contract claim proceeding for damages only and Count II as the fraudulent inducement claim remaining for trial, while noting Count III was dismissed.

### C-037

Does not include dismissed negligent misrepresentation claim ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L310))

- **Sonnet 4.6: Pass.** The document explicitly states in the introduction that 'Count III (negligent misrepresentation) was dismissed' and lists it as a stipulated fact (Stipulation #9: 'Count III (negligent misrepresentation) was dismissed by Order dated July 7, 2023.'). The document does not list negligent misrepresentation as a live claim going to trial. Only Count I (breach of contract, damages only) and Count II (fraudulent inducement) are identified as remaining for trial.
- **GPT-5.5: Pass.** The output states that Count III (negligent misrepresentation) was dismissed and does not list it as a live claim going to trial.

### C-038

References partial summary judgment on breach liability ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L318))

- **Sonnet 4.6: Pass.** The output explicitly and repeatedly references the partial summary judgment on breach liability. In the introduction it states: 'The November 15, 2024 Memorandum Opinion and Order granted Ridgeline partial summary judgment on liability for Corbin Supply's breach of the Minimum Annual Purchase Commitment ("MAPC") provisions of the parties' Exclusive Distribution Agreement ("EDA"). Count I proceeds for damages only.' Stipulated Fact #8 also states: 'On November 15, 2024, the Court held Corbin liable as a matter of law for breach of the MAPC provisions. Count I liability is not for trial.' Multiple other sections reference this ruling as well.
- **GPT-5.5: Pass.** The output repeatedly states that the November 15, 2024 order granted Ridgeline partial summary judgment on liability for Corbin's breach of the MAPC provisions, that Count I proceeds for damages only, and that breach liability is not for trial while fraudulent inducement remains for trial.

### C-039

Motion in limine re materiality of MAPC breaches (law of the case) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L326))

- **Sonnet 4.6: Fail.** The agent's output includes a motion in limine (Section 10.A) to preclude relitigation of Count I liability and resolved defenses, specifically stating that the Court conclusively decided Count I liability for Ridgeline and that only damages remain. However, this motion focuses on precluding argument that Corbin did not breach the MAPC provisions at all (i.e., liability), not specifically on precluding Corbin from arguing that the MAPC shortfalls were not 'material breaches.' The criterion specifically asks for a motion or argument to preclude Corbin from arguing the MAPC shortfalls were not material breaches on law-of-the-case grounds. While Section 10.A addresses liability generally, it does not specifically address the materiality-of-breach issue as a distinct argument. The document does not contain a specific motion in limine or argument targeting Corbin's ability to argue that the breaches were not 'material' — a distinct legal argument that could affect remedies even after liability is established. The output lacks this specific motion/argument.
- **GPT-5.5: Pass.** The output includes a motion in limine titled “Preclude relitigation of Count I liability and resolved defenses,” seeking to bar evidence or argument that would invite the jury to reconsider Corbin’s MAPC-breach liability because the Court already decided liability on summary judgment and only damages remain. Although it does not use the exact phrase “material breaches” or “law of the case,” the requested preclusion encompasses any argument that the MAPC shortfalls were not material breaches.

### C-040

Correct identification of Judge Gresham ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L334))

- **Sonnet 4.6: Pass.** The caption of the document clearly identifies 'Hon. Katherine M. Gresham, United States District Judge,' which matches the criterion requiring identification of the presiding judge as the Honorable Katherine M. Gresham, U.S. District Judge.
- **GPT-5.5: Pass.** The caption identifies the presiding judge as 'Hon. Katherine M. Gresham' and 'United States District Judge,' satisfying the criterion.

### C-041

Correct trial date stated ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L342))

- **Sonnet 4.6: Pass.** The document states 'The Court has set jury trial to commence September 15, 2025' in the introductory paragraph, and also references 'jury selection on the morning of September 15, 2025' in Section 11. The trial date is correctly stated as September 15, 2025.
- **GPT-5.5: Pass.** The output explicitly states that jury trial is set to commence September 15, 2025, and later repeats jury selection on September 15, 2025.

### C-042

Identifies EDA execution date correctly as March 1, 2021 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L350))

- **Sonnet 4.6: Pass.** The document clearly states in Stipulated Fact #3: 'The parties executed the EDA, Contract No. CSG-RM-2021-0301, on March 1, 2021.' This is also referenced in PX-001 as 'dated March 1, 2021' and in the EDA section references throughout. The date is correctly identified as March 1, 2021.
- **GPT-5.5: Pass.** The output explicitly states that the parties executed the EDA on March 1, 2021, including in Section 2, stipulated fact 3.

### C-043

Correctly characterizes the 12-state southeastern territory ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L358))

- **Sonnet 4.6: Pass.** The output explicitly lists the 12-state territory in PX-003: '(AL, AR, FL, GA, KY, LA, MS, NC, SC, TN, VA, WV)' and also references it as a 'twelve-state territory' in Section 2 Stipulated Fact #3. The states listed are southeastern states, satisfying the criterion.
- **GPT-5.5: Pass.** The output repeatedly describes the EDA as covering a 12-state territory and specifically lists the states as AL, AR, FL, GA, KY, LA, MS, NC, SC, TN, VA, and WV in the exhibit list, satisfying the criterion.

### C-044

Mitigation credit correctly applied in damages ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L366))

- **Sonnet 4.6: Pass.** The agent's output explicitly mentions the mitigation credit in Section 3 (Contested Factual Issues, Issue 4) and in the witness list for Dr. Prescott. Specifically, Prescott's report calculates '$7,990,000 in net future lost profits for Years 3--5, using MAPCs and a 34% margin, less a $2,720,000 mitigation credit.' The $2,720,000 figure matches the criterion (2.5 years × $3.2M/year × 34% margin = $2,720,000). The mitigation credit is correctly identified and applied against future lost profits, satisfying the criterion.
- **GPT-5.5: Pass.** The output expressly states that Prescott calculated $7,990,000 in net future lost profits for Years 3–5 using MAPCs and a 34% margin, less a $2,720,000 mitigation credit, and identifies Allegheny’s projected $3.2 million annual volume as mitigation evidence. This matches the required offset calculation.

### C-045

Correctly identifies Ridgeline's gross margin as 34% ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L374))

- **Sonnet 4.6: Pass.** The agent's output references the 34% gross margin multiple times throughout the document. In Section 3 (Contested Factual Issues), it states Prescott calculates damages 'using MAPCs and a 34% margin.' In Section 4, it notes Holt 'calculates $1,972,000 for Year 3 using $9 million less $3.2 million projected Allegheny revenue, times a 34% margin.' In Section 5A, it references 'a disclosed 34% gross margin' in Prescott's opinions. The 34% gross margin figure is consistently and correctly identified throughout the document.
- **GPT-5.5: Pass.** The output repeatedly identifies Ridgeline’s distributor-channel/gross margin as 34%, including in the damages discussion, expert testimony summaries, and contested legal issues. No materially different margin percentage is used.

### C-046

Addresses Holt's challenge to future lost profits period ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-pretrial-statement/task.json#L382))

- **Sonnet 4.6: Pass.** The agent's output explicitly addresses Holt's argument that the future lost-profit period should be limited to 12 months rather than the full remaining contract term. In Section 3 (Contested Factual Issues), subsection 4, the output states Holt 'proposes limiting the period to 12 months and disputes Prescott's $7.99 million net projection.' In Section 4 (Defendant's Contested Factual Issues), subsection 4, it again describes Holt's position: 'he proposes limiting the period to 12 months and disputes Prescott's $7.99 million net projection.' In Section 5 (Contested Legal Issues), subsection A, the output contrasts Prescott's Years 3-5 projection against Holt's 12-month/$1.972 million alternative, and states Plaintiff's position that the contractual language and disclosed evidence support the MAPC-based measure. The criterion is clearly satisfied.
- **GPT-5.5: Pass.** The output expressly addresses Holt's challenge several times, including noting that Holt proposes limiting future lost profits to a 12-month period, disputes Prescott's Years 3–5 / remainder-of-contract projection, and frames this as a contested factual and legal issue for trial.
