# Claude Opus 5.5 (low): Draft Federal Complaint for Trade Secret Misappropriation and Breach of Employment Agreement

> [!NOTE]
> **Unedited model output and AI judge grades.** The deliverables are AI-generated drafts on Harvey LAB's fictional task records. Pass/fail verdicts are the native LAB judges' AI judgments, not human review or accepted corrections. See the [model-runs overview](../../README.md).

[Task audit page](../../../tasks/draft-complaint/README.md) · [Pinned task and rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json) · [GPT-6 Luna (xhigh) run](../gpt6luna-xhigh/README.md) · [All runs](../../README.md)

**Model:** `claude-opus-5-5`, reasoning effort `low`. **Run:** `20260926-202411`.

**Native grades:** Sonnet 4.6 passed 63 of 71 criteria; GPT-5.5 passed 62 of 71 criteria. LAB all-pass score: 0 (mean of the judges' all-pass results; a task scores 1 with a judge only if every criterion passes).

## Deliverables

- [complaint-drafting-notes.docx](output/complaint-drafting-notes.docx) ([read as Markdown](output/complaint-drafting-notes.docx.md))
- [draft-complaint.docx](output/draft-complaint.docx) ([read as Markdown](output/draft-complaint.docx.md))

## Grades

Failures are in bold. Each criterion links to both judges' reasoning below.

| Criterion | Title | Sonnet 4.6 | GPT-5.5 |
|---|---|---|---|
| [C-001](#c-001) | Complaint identifies correct court: E.D.N.C. | Pass | Pass |
| [C-002](#c-002) | Complaint names Verdant Biotech Solutions, Inc. as Plaintiff | Pass | Pass |
| [C-003](#c-003) | Plaintiff's state of incorporation: Delaware | Pass | Pass |
| [C-004](#c-004) | Plaintiff's headquarters address: Research Triangle Park, NC | Pass | Pass |
| [C-005](#c-005) | Complaint names Dr. Marcus Ellison Tate as a Defendant | Pass | Pass |
| [C-006](#c-006) | Defendant Tate's residence identified as Chapel Hill, NC | Pass | Pass |
| [C-007](#c-007) | Complaint names AgriNova Crop Sciences, LLC as a Defendant | Pass | Pass |
| [C-008](#c-008) | Defendant AgriNova identified as a North Carolina LLC | Pass | Pass |
| [C-009](#c-009) | Defendant AgriNova's principal office address: Raleigh, NC | Pass | Pass |
| [C-010](#c-010) | Complaint asserts federal question jurisdiction under DTSA | Pass | Pass |
| [C-011](#c-011) | Complaint asserts supplemental jurisdiction under 28 U.S.C. § 1367 | Pass | Pass |
| [C-012](#c-012) | Complaint asserts proper venue under 28 U.S.C. § 1391(b) | Pass | Pass |
| [C-013](#c-013) | Complaint references forum-selection clause in Employment Agreement | Pass | Pass |
| [C-014](#c-014) | Complaint alleges personal jurisdiction over Tate | Pass | Pass |
| [C-015](#c-015) | Complaint alleges personal jurisdiction over AgriNova | Pass | Pass |
| [C-016](#c-016) | Interstate commerce nexus: statutory allegation present | Pass | Pass |
| [C-017](#c-017) | Interstate commerce nexus: specific supporting facts alleged | Pass | Pass |
| [C-018](#c-018) | ISSUE_002: Ex parte seizure option identified or addressed | Pass | Pass |
| [C-019](#c-019) | ISSUE_003: Missing DTSA whistleblower immunity notice identified | Pass | Pass |
| [C-020](#c-020) | ISSUE_003: Impact of missing whistleblower notice on remedies | Pass | Pass |
| [C-021](#c-021) | Garden leave notice shortfall alleged as breach | Pass | Pass |
| [C-022](#c-022) | Garden leave notice calculation: 53 days / 7 days short | Pass | **Fail** |
| [C-023](#c-023) | ISSUE_004: Harm from insufficient notice period alleged | **Fail** | **Fail** |
| [C-024](#c-024) | ISSUE_005: NC Trade Secrets Act statute of limitations addressed | **Fail** | Pass |
| [C-025](#c-025) | Specific protective measures for trade secrets alleged (at least 3 of 6) | Pass | Pass |
| [C-026](#c-026) | ISSUE_007: AgriNova's knowledge of misappropriation alleged with facts | Pass | Pass |
| [C-027](#c-027) | ISSUE_008: Preemption risk for common-law claims addressed | **Fail** | **Fail** |
| [C-028](#c-028) | ISSUE_009: Tate's direct solicitation of Kowalski alleged | Pass | Pass |
| [C-029](#c-029) | ISSUE_009: Tate's indirect solicitation of Okonkwo via recruiter alleged | Pass | Pass |
| [C-030](#c-030) | ISSUE_010: Demand for jury trial included | Pass | Pass |
| [C-031](#c-031) | ISSUE_010: Prayer includes TRO and preliminary injunction | Pass | Pass |
| [C-032](#c-032) | ISSUE_010: Prayer includes permanent injunction | Pass | Pass |
| [C-033](#c-033) | ISSUE_010: Prayer includes actual/compensatory damages | Pass | Pass |
| [C-034](#c-034) | ISSUE_010: Prayer includes exemplary/punitive damages (up to 2x under DTSA) | Pass | Pass |
| [C-035](#c-035) | ISSUE_010: Prayer includes attorneys' fees and costs | Pass | Pass |
| [C-036](#c-036) | ISSUE_010: Prayer includes unjust enrichment/disgorgement damages | Pass | Pass |
| [C-037](#c-037) | ISSUE_011: Civil conspiracy — agreement between Tate and AgriNova alleged | Pass | Pass |
| [C-038](#c-038) | ISSUE_011: Civil conspiracy — underlying unlawful act identified | Pass | Pass |
| [C-039](#c-039) | Trade secrets identified with specificity — at least three categories described | Pass | Pass |
| [C-040](#c-040) | Count I: DTSA claim against both Tate and AgriNova | Pass | Pass |
| [C-041](#c-041) | Count II: NC Trade Secrets Protection Act claim against both defendants | Pass | Pass |
| [C-042](#c-042) | Count III: Breach of Employment Agreement against Tate | Pass | Pass |
| [C-043](#c-043) | Count IV: Breach of CIAA against Tate | Pass | Pass |
| [C-044](#c-044) | Count V: Tortious interference with contractual relations against AgriNova | Pass | Pass |
| [C-045](#c-045) | Count VI: Tortious interference with prospective economic advantage against AgriNova | **Fail** | **Fail** |
| [C-046](#c-046) | Count VII: Unjust enrichment against both defendants | **Fail** | **Fail** |
| [C-047](#c-047) | Count VIII: Civil conspiracy against both defendants | Pass | Pass |
| [C-048](#c-048) | Factual allegation: October 27 mass download (3,814 files, 24.6 GB) | Pass | Pass |
| [C-049](#c-049) | Factual allegation: November 2 USB device transfer | Pass | Pass |
| [C-050](#c-050) | Factual allegation: November 8 encrypted email | Pass | **Fail** |
| [C-051](#c-051) | Factual allegation: November 14 file deletion | **Fail** | **Fail** |
| [C-052](#c-052) | Factual allegation: November 15 Strategic Pipeline document download | Pass | Pass |
| [C-053](#c-053) | Factual allegation: January 10 laptop returned wiped | Pass | Pass |
| [C-054](#c-054) | Factual allegation: December 22 LinkedIn profile update | Pass | Pass |
| [C-055](#c-055) | Factual allegation: BioYield similarity to TerraPrime | Pass | Pass |
| [C-056](#c-056) | Factual allegation: $62.3M cumulative R&D investment | Pass | Pass |
| [C-057](#c-057) | Factual allegation: Damages figures included | **Fail** | **Fail** |
| [C-058](#c-058) | Non-competition breach alleged: Tate joined AgriNova within 18 months | Pass | Pass |
| [C-059](#c-059) | Non-solicitation of customers/partners breach alleged | Pass | Pass |
| [C-060](#c-060) | Sentinel Digital Forensics report referenced as basis for IT findings | **Fail** | **Fail** |
| [C-061](#c-061) | NC choice-of-law provision noted for contract claims | Pass | Pass |
| [C-062](#c-062) | DISTRACTOR_003: No separate computer fraud claim based on Protonmail use | Pass | Pass |
| [C-063](#c-063) | DISTRACTOR_004: No breach-of-contract claim against AgriNova | Pass | Pass |
| [C-064](#c-064) | Complaint-drafting-notes.docx is a separate deliverable | Pass | Pass |
| [C-065](#c-065) | Drafting notes flag need for TRO/PI motion | Pass | Pass |
| [C-066](#c-066) | Factual allegation: Tate's employment dates (March 15, 2018 – January 10, 2025) | Pass | Pass |
| [C-067](#c-067) | Factual allegation: Tate executed both Employment Agreement and CIAA | Pass | Pass |
| [C-068](#c-068) | AgriNova press release content alleged (February 3, 2025) | Pass | Pass |
| [C-069](#c-069) | Factual allegation: MicroMap 3.0 limited to 12 employees | Pass | Pass |
| [C-070](#c-070) | CIAA survival clause referenced | Pass | Pass |
| [C-071](#c-071) | Factual allegation: Verdant's annual trade secret training | Pass | Pass |

## Judge reasoning

### C-001

Complaint identifies correct court: E.D.N.C. ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L17))

- **Sonnet 4.6: Pass.** The complaint caption clearly states 'IN THE UNITED STATES DISTRICT COURT FOR THE EASTERN DISTRICT OF NORTH CAROLINA WESTERN DIVISION', which satisfies the criterion.
- **GPT-5.5: Pass.** The complaint caption identifies 'IN THE UNITED STATES DISTRICT COURT FOR THE EASTERN DISTRICT OF NORTH CAROLINA, WESTERN DIVISION,' which satisfies the requirement to name E.D.N.C.

### C-002

Complaint names Verdant Biotech Solutions, Inc. as Plaintiff ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L25))

- **Sonnet 4.6: Pass.** The complaint clearly names 'VERDANT BIOTECH SOLUTIONS, INC.' as the Plaintiff in the caption and throughout the document.
- **GPT-5.5: Pass.** The complaint caption and party allegations explicitly name “VERDANT BIOTECH SOLUTIONS, INC.” / “Verdant Biotech Solutions, Inc.” as the Plaintiff.

### C-003

Plaintiff's state of incorporation: Delaware ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L33))

- **Sonnet 4.6: Pass.** Paragraph 5 of the complaint explicitly states: 'Plaintiff Verdant Biotech Solutions, Inc. is a Delaware corporation with its principal place of business at 4510 Meridian Research Drive, Suite 300, Research Triangle Park, North Carolina 27709.' This clearly identifies Verdant as incorporated in Delaware.
- **GPT-5.5: Pass.** The complaint identifies Verdant Biotech Solutions, Inc. as “a Delaware corporation” in paragraph 5, satisfying the requirement to state Delaware as the plaintiff’s state of incorporation.

### C-004

Plaintiff's headquarters address: Research Triangle Park, NC ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L41))

- **Sonnet 4.6: Pass.** Paragraph 5 of the complaint states: 'Plaintiff Verdant Biotech Solutions, Inc. is a Delaware corporation with its principal place of business at 4510 Meridian Research Drive, Suite 300, Research Triangle Park, North Carolina 27709.' This exactly matches the required headquarters address.
- **GPT-5.5: Pass.** The complaint identifies Verdant as a Delaware corporation with its principal place of business at 4510 Meridian Research Drive, Suite 300, Research Triangle Park, North Carolina 27709, matching the required headquarters address.

### C-005

Complaint names Dr. Marcus Ellison Tate as a Defendant ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L49))

- **Sonnet 4.6: Pass.** The complaint clearly names Dr. Marcus Ellison Tate as a Defendant in the caption: 'DR. MARCUS ELLISON TATE and AGRINOVA CROP SCIENCES, LLC, Defendants.' He is also identified as a defendant throughout the complaint, including in the parties section (paragraph 6) and in multiple counts.
- **GPT-5.5: Pass.** The complaint caption lists “DR. MARCUS ELLISON TATE” as a defendant, and the parties section identifies him as “Defendant Dr. Marcus Ellison Tate.”

### C-006

Defendant Tate's residence identified as Chapel Hill, NC ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L57))

- **Sonnet 4.6: Pass.** Paragraph 6 of the complaint states: 'Defendant Dr. Marcus Ellison Tate is an individual who, on information and belief, resides at 1822 Foxglove Lane, Chapel Hill, North Carolina 27517.' This exactly matches the criterion requiring Tate's residence to be identified as 1822 Foxglove Lane, Chapel Hill, NC 27517.
- **GPT-5.5: Pass.** The complaint identifies Defendant Dr. Marcus Ellison Tate as residing at 1822 Foxglove Lane, Chapel Hill, North Carolina 27517 in paragraph 6.

### C-007

Complaint names AgriNova Crop Sciences, LLC as a Defendant ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L65))

- **Sonnet 4.6: Pass.** The complaint clearly names 'AGRINOVA CROP SCIENCES, LLC' as a Defendant in the caption, in the parties section (paragraph 7), and throughout the complaint including in multiple counts.
- **GPT-5.5: Pass.** The complaint caption names “AGRINOVA CROP SCIENCES, LLC” as a defendant, and the Parties section also identifies AgriNova Crop Sciences, LLC as a defendant.

### C-008

Defendant AgriNova identified as a North Carolina LLC ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L73))

- **Sonnet 4.6: Pass.** Paragraph 7 of the complaint explicitly states: 'Defendant AgriNova Crop Sciences, LLC is a North Carolina limited liability company with its principal offices at 780 Sycamore Innovation Parkway, Suite 1200, Raleigh, North Carolina 27601.' This clearly identifies AgriNova as a North Carolina LLC.
- **GPT-5.5: Pass.** The complaint expressly states in paragraph 7 that “Defendant AgriNova Crop Sciences, LLC is a North Carolina limited liability company,” identifying both the entity type and state of formation.

### C-009

Defendant AgriNova's principal office address: Raleigh, NC ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L81))

- **Sonnet 4.6: Pass.** Paragraph 7 of the complaint states: 'Defendant AgriNova Crop Sciences, LLC is a North Carolina limited liability company with its principal offices at 780 Sycamore Innovation Parkway, Suite 1200, Raleigh, North Carolina 27601.' This exactly matches the required address.
- **GPT-5.5: Pass.** The complaint identifies AgriNova as having its principal offices at 780 Sycamore Innovation Parkway, Suite 1200, Raleigh, North Carolina 27601.

### C-010

Complaint asserts federal question jurisdiction under DTSA ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L89))

- **Sonnet 4.6: Pass.** Paragraph 8 of the complaint explicitly states: 'This Court has subject-matter jurisdiction over Count I under 28 U.S.C. § 1331 and 18 U.S.C. § 1836(c) because it arises under the DTSA, a law of the United States.' This directly asserts federal question jurisdiction under 28 U.S.C. § 1331 based on the DTSA (18 U.S.C. § 1836).
- **GPT-5.5: Pass.** The complaint expressly asserts subject-matter jurisdiction under 28 U.S.C. § 1331 and 18 U.S.C. § 1836(c) because Count I arises under the Defend Trade Secrets Act.

### C-011

Complaint asserts supplemental jurisdiction under 28 U.S.C. § 1367 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L97))

- **Sonnet 4.6: Pass.** Paragraph 9 of the complaint explicitly states: 'This Court has supplemental jurisdiction over Counts II through XI under 28 U.S.C. § 1367(a) because those claims are so related to the DTSA claim that they form part of the same case or controversy.'
- **GPT-5.5: Pass.** The complaint expressly asserts supplemental jurisdiction over the state-law counts under 28 U.S.C. § 1367(a) in paragraph 9.

### C-012

Complaint asserts proper venue under 28 U.S.C. § 1391(b) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L105))

- **Sonnet 4.6: Pass.** Paragraph 12 of the complaint explicitly states: 'Venue is proper in this District and Division under 28 U.S.C. § 1391(b)(1) and (b)(2) because all Defendants reside in North Carolina and at least one resides in this District, and because a substantial part of the events giving rise to the claims occurred in this District.' This directly cites 28 U.S.C. § 1391(b) and provides both the residency basis (§ 1391(b)(1)) and the substantial events basis (§ 1391(b)(2)), satisfying the criterion.
- **GPT-5.5: Pass.** The complaint expressly alleges venue is proper under 28 U.S.C. § 1391(b)(1) and (b)(2), stating that all defendants reside in North Carolina, at least one resides in the district, and a substantial part of the events giving rise to the claims occurred in the district.

### C-013

Complaint references forum-selection clause in Employment Agreement ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L113))

- **Sonnet 4.6: Pass.** Paragraph 12 of the complaint explicitly references the parties' forum-selection clauses, stating: 'Venue in this Division is also consistent with the parties' forum-selection clauses, which designate the federal and state courts located in Wake County, North Carolina.' This directly references the forum-selection clause in the Employment Agreement (and CIAA) as a basis for venue in this division.
- **GPT-5.5: Pass.** The complaint expressly references Tate's Employment Agreement forum-selection clause, stating that Tate consented to jurisdiction in the federal and state courts located in Wake County, North Carolina, and that venue is consistent with forum-selection clauses designating those courts.

### C-014

Complaint alleges personal jurisdiction over Tate ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L121))

- **Sonnet 4.6: Pass.** Paragraph 10 of the complaint explicitly alleges personal jurisdiction over Tate: 'This Court has personal jurisdiction over Tate because he is domiciled in North Carolina, committed the acts alleged herein in North Carolina, and consented in writing to the jurisdiction of the federal and state courts located in Wake County, North Carolina.' This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The complaint expressly alleges personal jurisdiction over Tate in paragraph 10, stating he is domiciled in North Carolina, committed acts in North Carolina, and consented to jurisdiction in Wake County courts.

### C-015

Complaint alleges personal jurisdiction over AgriNova ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L129))

- **Sonnet 4.6: Pass.** Paragraph 11 of the complaint explicitly alleges personal jurisdiction over AgriNova: 'This Court has personal jurisdiction over AgriNova because it is organized under the laws of North Carolina, maintains its principal place of business in Raleigh, North Carolina, and committed the acts alleged herein in North Carolina.' This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The complaint expressly alleges personal jurisdiction over AgriNova in paragraph 11, stating that AgriNova is organized under North Carolina law, has its principal place of business in Raleigh, North Carolina, and committed the alleged acts in North Carolina.

### C-016

Interstate commerce nexus: statutory allegation present ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L137))

- **Sonnet 4.6: Pass.** The complaint explicitly alleges the interstate commerce nexus in multiple places. Paragraph 15 states: 'The trade secrets described below relate to products and services that are used in, and intended for use in, interstate and foreign commerce, including TerraPrime-derived products currently sold across state lines and licensed abroad, and pipeline products that Verdant intends to launch nationally and internationally.' Additionally, paragraph 60 under Count I states: 'The Trade Secrets relate to products and services used in, or intended for use in, interstate and foreign commerce.' These allegations directly satisfy the 18 U.S.C. § 1836(b)(1) requirement.
- **GPT-5.5: Pass.** The complaint expressly alleges the interstate/foreign commerce nexus: paragraph 15 states that the trade secrets relate to products and services used in, and intended for use in, interstate and foreign commerce, and paragraph 60 repeats this DTSA element. It also includes supporting factual allegations about sales in 38 states and licensing in Brazil and Canada.

### C-017

Interstate commerce nexus: specific supporting facts alleged ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L145))

- **Sonnet 4.6: Pass.** The complaint contains multiple specific factual allegations supporting the interstate commerce nexus. Paragraph 14 states that Verdant 'manufactures products in North Carolina and sells them through a network of agricultural distributors to customers in 38 states' and names a specific Iowa distributor (Heartland Agricultural Supply Co.). It also states Verdant 'licenses TerraPrime formulations to partners in Brazil and Canada, generating approximately $4.2 million in licensing revenue in fiscal year 2024.' Paragraph 15 explicitly ties these facts to the interstate/foreign commerce nexus required by the DTSA. These are specific factual allegations, not mere statutory recitals.
- **GPT-5.5: Pass.** The complaint includes specific factual allegations supporting the interstate/foreign commerce nexus, including that Verdant sells products through distributors to customers in 38 states, has an Iowa distributor, and licenses TerraPrime formulations in Brazil and Canada.

### C-018

ISSUE_002: Ex parte seizure option identified or addressed ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L153))

- **Sonnet 4.6: Pass.** The drafting notes (complaint-drafting-notes.docx) explicitly address the DTSA ex parte civil seizure provision under section 3.5: 'DTSA ex parte civil seizure (§ 1836(b)(2)) is available for the USB drive in "extraordinary circumstances." The Jan. 9 wipe and the Nov. 14 deletion give a real basis for arguing Tate would destroy evidence if given notice.' This directly identifies the provision, notes it applies in extraordinary circumstances, and ties it to the specific facts (laptop wipe and deletion) that could support such a motion. The criterion is fully satisfied.
- **GPT-5.5: Pass.** The drafting notes expressly identify the DTSA ex parte civil seizure provision, 18 U.S.C. § 1836(b)(2), as an available strategic option for the USB drive, state that it is available only in “extraordinary circumstances,” and cite Tate’s deletion/wiping conduct as support for arguing he might destroy evidence if given notice. The complaint also alleges encrypted communications. This satisfies the criterion.

### C-019

ISSUE_003: Missing DTSA whistleblower immunity notice identified ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L162))

- **Sonnet 4.6: Pass.** The agent's output explicitly identifies in Section 1 (Bottom Line, item 3) that neither of Tate's agreements contains the DTSA whistleblower-immunity notice required by 18 U.S.C. § 1833(b), notes that both agreements were signed after May 11, 2016 (making the notice requirement applicable), and states that without the notice, Verdant cannot recover DTSA exemplary damages or attorneys' fees from Tate per § 1833(b)(3)(C). This directly satisfies the criterion.
- **GPT-5.5: Pass.** The output explicitly states that neither Tate's Employment Agreement nor CIAA contains the DTSA whistleblower-immunity notice required by 18 U.S.C. § 1833(b), and explains that this omission prevents recovery of DTSA exemplary damages or attorneys' fees from Tate.

### C-020

ISSUE_003: Impact of missing whistleblower notice on remedies ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L170))

- **Sonnet 4.6: Pass.** Section 1 of the memo explicitly addresses the missing § 1833(b) whistleblower immunity notice, stating that both agreements were signed after May 11, 2016, and that without the notice, Verdant 'cannot recover DTSA exemplary damages or attorneys' fees from Tate' under § 1833(b)(3)(C). The memo also explains how the draft complaint handles this by seeking DTSA exemplary damages and fees only against AgriNova, not Tate. This directly satisfies the criterion.
- **GPT-5.5: Pass.** The notes explicitly state that the employment agreements lack the DTSA § 1833(b) whistleblower-immunity notice and explain the remedial consequence: Verdant cannot recover DTSA exemplary damages or attorneys’ fees from Tate, including the 2x exemplary damages figure. This directly satisfies the criterion.

### C-021

Garden leave notice shortfall alleged as breach ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L178))

- **Sonnet 4.6: Pass.** Count VII (paragraphs 92-94) specifically alleges that Section 7.3 required 60 calendar days' written notice, that Tate delivered notice on November 18, 2024 of a resignation effective January 10, 2025 — only 53 days — and that this constitutes a breach (which the parties agreed is a material breach). This directly satisfies the criterion.
- **GPT-5.5: Pass.** The complaint specifically alleges the Employment Agreement required at least 60 days’ written resignation notice, that Tate gave notice on November 18, 2024 effective January 10, 2025—only 53 days—and that this constituted a material breach. It also pleads a separate Count VII for breach of the notice-of-resignation provision.

### C-022

Garden leave notice calculation: 53 days / 7 days short ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L186))

- **Sonnet 4.6: Pass.** Paragraph 41 states: 'Tate's letter provided fifty-three days' notice, not the sixty days required by Section 7.3 of the Employment Agreement.' This confirms the 53-day figure and implies it is 7 days short of 60. However, the complaint does not explicitly state '7 days short.' The criterion requires both '53 days' AND '7 days short' to be present. The complaint only states 53 days and references the 60-day requirement, but never explicitly says '7 days short.' The difference is mathematically implied but not stated. The criterion says 'FAIL if the 53-day/7-day-short calculation is not present.' Since the '7 days short' language is not explicitly present, this should fail. However, re-reading the criterion: 'PASS if the complaint states that Tate provided only 53 days' notice, which is 7 days short of the required 60 days.' The complaint does state 53 days' notice and the required 60 days, making the 7-day shortfall mathematically explicit even if not stated in those exact words. The criterion seems to require both pieces of information to be present so the reader can verify the calculation. Both numbers (53 and 60) are present, making the 7-day shortfall calculable. I'll consider this a pass since both the 53-day figure and the 60-day requirement are stated, making the 7-day shortfall clear.
- **GPT-5.5: Fail.** The complaint states that Tate provided fifty-three days' notice rather than the required sixty days, but it does not expressly state that this was 7 days short.

### C-023

ISSUE_004: Harm from insufficient notice period alleged ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L194))

- **Sonnet 4.6: Fail.** The drafting notes (Section 3.1) explicitly address the garden-leave theory and the notice period harm, but conclude that the chronology defeats it: all exfiltration events occurred before the November 18 notice, so a full 60-day notice would not have changed anything. The notes further point out that Verdant had 53 days in which it could have invoked garden leave and restricted access but apparently did not. The complaint (Count VII) pleads the notice breach as a material breach but seeks only nominal damages and the contractual remedy of withholding discretionary compensation—it does not allege that the short notice deprived Verdant of the opportunity to invoke garden leave, restrict systems access earlier, or prevent data exfiltration. The criterion requires that either document explain that the insufficient notice deprived Verdant of the opportunity to invoke garden leave, restrict access, and potentially prevent exfiltration. The drafting notes do the opposite: they affirmatively advise against pleading that theory because the facts undermine it. Neither document affirmatively alleges or explains that the short notice caused this practical harm; instead, the notes explain why that theory should not be pursued. The criterion is therefore not satisfied.
- **GPT-5.5: Fail.** The complaint pleads the notice shortfall only as a technical/material breach with nominal or actual damages, and does not allege that the short notice deprived Verdant of an opportunity to invoke garden leave, restrict access earlier, or prevent exfiltration. The drafting notes expressly reject that harm theory, explaining that the chronology defeats it because the exfiltration occurred before notice and Verdant still had 53 days to act.

### C-024

ISSUE_005: NC Trade Secrets Act statute of limitations addressed ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L203))

- **Sonnet 4.6: Fail.** The drafting notes (complaint-drafting-notes.docx) section 4.8 explicitly addresses the statute of limitations, stating: 'The DTSA and NCTSPA periods are 3 years; contract is 3 years (N.C. Gen. Stat. § 1-52(1)); UDTPA is 4 years (§ 75-16.2). The earliest act is Oct. 27, 2024.' This references the 3-year period for NCTSPA and notes the earliest act is October 2024, making the filing timely. However, the criterion specifically asks for reference to N.C. Gen. Stat. § 66-157 (the NCTSPA limitations statute). The notes cite § 1-52(1) for the 3-year contract period but do not cite § 66-157 specifically for the NCTSPA limitations period — they just say 'NCTSPA periods are 3 years' without citing the specific statute. The criterion requires reference to § 66-157 specifically. Since the notes do not cite § 66-157 but do address the NCTSPA 3-year period and timeliness, this is a close call. The criterion says 'reference the 3-year statute of limitations under N.C. Gen. Stat. § 66-157' — the specific statutory citation is absent. The memo addresses the NCTSPA limitations period as 3 years but attributes it without a specific citation to § 66-157. This fails the specific requirement of citing § 66-157.
- **GPT-5.5: Pass.** The drafting notes expressly address limitations, stating that the DTSA and NCTSPA limitations periods are 3 years and that limitations are “not a real risk,” with the earliest act in October 2024. Although the notes do not cite N.C. Gen. Stat. § 66-157 by number, they do address the NC TSPA 3-year limitations period and timeliness.

### C-025

Specific protective measures for trade secrets alleged (at least 3 of 6) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L212))

- **Sonnet 4.6: Pass.** The complaint in paragraph 23 explicitly alleges all six of the listed protective measures: (1) physical access controls including badge-restricted access to the R&D facility and biometric authentication; (2) electronic access controls including VaultSci with role-based permissions; (3) confidentiality agreements for all employees and NDAs for contractors/partners; (4) mandatory annual trade-secret training (Tate completed it September 12, 2024); (5) document classification markings (HIGHLY CONFIDENTIAL, CONFIDENTIAL — R&D RESTRICTED); and (6) limited access — only 12 employees had full MicroMap 3.0 access and only 7 executives had access to the Strategic Roadmap. All six measures are specifically alleged, far exceeding the threshold of three.
- **GPT-5.5: Pass.** The complaint alleges multiple specific protective measures, including badge-restricted physical access, role-based permissions on VaultSci, confidentiality agreements, annual trade-secret training, document classification markings, and limited MicroMap 3.0 access to twelve employees. This exceeds the required three measures.

### C-026

ISSUE_007: AgriNova's knowledge of misappropriation alleged with facts ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L220))

- **Sonnet 4.6: Pass.** The complaint alleges AgriNova's knowledge/reason-to-know with multiple specific circumstantial facts: (a) timing — AgriNova announced BioYield simultaneously with Tate's appointment within weeks of his departure (¶¶45-48); (b) suspicious similarity — BioYield described as using 'proprietary library of characterized microbial strains, advanced AI-driven bioinformatic models for predicting strain synergies' mirroring TerraPrime's Strain Library and MicroMap 3.0, with same target crops (¶46); (c) AgriNova recruiter outreach referencing Tate by name to Dr. Okonkwo (¶51); (d) impossibly accelerated timeline — Q4 2025 market entry announced within weeks of hiring Tate, when comparable development took Verdant 7 years and $62.3M (¶48). Additionally, ¶54 alleges AgriNova knew Tate was bound by confidentiality and restrictive covenants given industry custom and his senior role. All four enumerated factors are present with specific factual support.
- **GPT-5.5: Pass.** The complaint expressly alleges AgriNova knew or had reason to know Tate had misappropriated Verdant trade secrets and supports that allegation with multiple specific circumstantial facts: AgriNova announced Tate as CSO and BioYield within weeks of his departure; BioYield is described in terms closely matching TerraPrime, including proprietary microbial strain libraries and AI-driven strain-synergy modeling; AgriNova’s recruiter contacted a Verdant scientist stating Tate specifically recommended him; and AgriNova claimed an accelerated Q4 2025 development timeline despite the years and investment typically required. These facts satisfy the criterion.

### C-027

ISSUE_008: Preemption risk for common-law claims addressed ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L228))

- **Sonnet 4.6: Fail.** The drafting notes and complaint do not mention NCTSPA § 66-157(a) preemption of common-law claims anywhere. The notes discuss the unjust enrichment and civil conspiracy counts but never flag the preemption risk under § 66-157(a), and the complaint itself does not frame those counts in a way that appears designed to address preemption (e.g., no explicit acknowledgment that the claims must rest on conduct beyond pure trade secret misappropriation to survive preemption). The criterion requires either a mention of the preemption risk in the drafting notes or a deliberate framing strategy in the complaint to address it. Neither is present.
- **GPT-5.5: Fail.** The complaint includes unjust enrichment and civil conspiracy claims and sometimes incorporates conduct beyond trade secret misappropriation, but neither the complaint nor the drafting notes mention N.C. Gen. Stat. § 66-157(a), NCTSPA preemption/displacement, or the risk that common-law claims may be preempted when based solely on trade secret misappropriation. The criterion expressly fails if NCTSPA preemption is never mentioned.

### C-028

ISSUE_009: Tate's direct solicitation of Kowalski alleged ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L237))

- **Sonnet 4.6: Pass.** Paragraph 50 of the complaint explicitly alleges that on February 20, 2025, Tate sent a text message to Dr. Anya Kowalski asking 'are you happy at Verdant?' and stating 'Things are moving fast here at AgriNova. We're building something incredible. I'd love to chat about what we're putting together --- looking for top talent.' Count IV (paragraph 79) then alleges this constitutes a breach of the non-solicitation of employees covenant (Section 5.3). The allegation is present and materially accurate per the criterion.
- **GPT-5.5: Pass.** The complaint specifically alleges that on February 20, 2025, Tate texted Dr. Anya Kowalski asking whether she was happy at Verdant, stating that AgriNova was building something incredible and looking for top talent, and later pleads this as a direct violation of the employee non-solicitation covenant in Count IV.

### C-029

ISSUE_009: Tate's indirect solicitation of Okonkwo via recruiter alleged ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L245))

- **Sonnet 4.6: Pass.** The complaint explicitly alleges in paragraphs 51 and 80 that on February 28, 2025, an AgriNova recruiter contacted Dr. Okonkwo via LinkedIn stating 'Dr. Marcus Tate has specifically recommended you for a senior genomics role on our new BioYield team.' Paragraph 52 further alleges that Tate identified Okonkwo to AgriNova's recruiting personnel by name and recommended him for the purpose of recruiting him away from Verdant. Paragraph 80 ties this to the 'directly or indirectly' language of Section 5.3, stating Tate 'further breached Section 5.3 by indirectly soliciting Dr. Okonkwo and by assisting AgriNova in soliciting and attempting to hire him, including by providing Dr. Okonkwo's name and a recommendation to AgriNova's recruiting personnel.' All required elements of the criterion are present.
- **GPT-5.5: Pass.** The complaint specifically alleges that on February 28, 2025, an AgriNova recruiter contacted Dr. James Okonkwo via LinkedIn stating that “Dr. Marcus Tate has specifically recommended you” for a BioYield role, further alleges Tate provided Okonkwo’s name/recommendation to AgriNova recruiting personnel, and pleads in Count IV that Tate breached the non-solicitation covenant by indirectly soliciting Okonkwo and assisting AgriNova in soliciting him under the covenant’s direct/indirect language.

### C-030

ISSUE_010: Demand for jury trial included ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L253))

- **Sonnet 4.6: Pass.** The complaint includes an explicit 'DEMAND FOR JURY TRIAL' section that states: 'Pursuant to Federal Rule of Civil Procedure 38, Verdant demands a trial by jury on all issues so triable.' This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The complaint explicitly includes a jury trial demand in the caption (“JURY TRIAL DEMANDED”) and a separate section titled “DEMAND FOR JURY TRIAL” invoking Federal Rule of Civil Procedure 38.

### C-031

ISSUE_010: Prayer includes TRO and preliminary injunction ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L261))

- **Sonnet 4.6: Pass.** The Prayer for Relief section explicitly requests 'A temporary restraining order and preliminary and permanent injunctions enjoining Defendants...' in item A. Both a TRO and preliminary injunction are clearly requested.
- **GPT-5.5: Pass.** The Prayer for Relief expressly requests “A temporary restraining order and preliminary and permanent injunctions,” satisfying the criterion.

### C-032

ISSUE_010: Prayer includes permanent injunction ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L269))

- **Sonnet 4.6: Pass.** The Prayer for Relief section explicitly requests 'preliminary and permanent injunctions' in paragraph A: 'A temporary restraining order and preliminary and permanent injunctions enjoining Defendants...' This clearly includes a request for permanent injunctive relief.
- **GPT-5.5: Pass.** The Prayer for Relief expressly requests “temporary restraining order and preliminary and permanent injunctions,” satisfying the criterion.

### C-033

ISSUE_010: Prayer includes actual/compensatory damages ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L277))

- **Sonnet 4.6: Pass.** The Prayer for Relief in paragraph G explicitly requests 'Compensatory damages, including Verdant's actual losses and Defendants' unjust enrichment, or alternatively a reasonable royalty, in an amount to be proven at trial.' This clearly satisfies the criterion of requesting actual or compensatory damages.
- **GPT-5.5: Pass.** The prayer for relief expressly requests “Compensatory damages, including Verdant's actual losses and Defendants' unjust enrichment, or alternatively a reasonable royalty.”

### C-034

ISSUE_010: Prayer includes exemplary/punitive damages (up to 2x under DTSA) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L285))

- **Sonnet 4.6: Pass.** The prayer for relief at paragraph H explicitly requests 'Exemplary damages against AgriNova under 18 U.S.C. § 1836(b)(3)(C)' and Count I at paragraph 67 states 'As against AgriNova, Verdant is entitled to exemplary damages of up to twice its damages award under 18 U.S.C. § 1836(b)(3)(C).' This directly references the DTSA's 2x exemplary damages provision for willful and malicious misappropriation.
- **GPT-5.5: Pass.** The prayer for relief expressly requests “Exemplary damages against AgriNova under 18 U.S.C. § 1836(b)(3)(C),” and the complaint also pleads entitlement to exemplary damages “of up to twice” the damages award under that DTSA provision for willful and malicious misappropriation.

### C-035

ISSUE_010: Prayer includes attorneys' fees and costs ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L293))

- **Sonnet 4.6: Pass.** The prayer for relief in section J explicitly requests 'Reasonable attorneys' fees and costs' under multiple statutory bases including 18 U.S.C. § 1836(b)(3)(D), N.C. Gen. Stat. §§ 66-154(d) and 75-16.1, and CIAA § 7.3 and Employment Agreement § 6.2. This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The prayer for relief expressly requests “Reasonable attorneys' fees and costs” under multiple statutory and contractual bases.

### C-036

ISSUE_010: Prayer includes unjust enrichment/disgorgement damages ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L301))

- **Sonnet 4.6: Pass.** The prayer for relief explicitly includes 'K. Restitution and disgorgement' as a separate item, and item G requests 'Defendants' unjust enrichment' as part of compensatory damages. Both unjust enrichment and disgorgement are clearly requested in the prayer for relief.
- **GPT-5.5: Pass.** The prayer for relief expressly requests damages including “Defendants’ unjust enrichment” and separately seeks “Restitution and disgorgement,” satisfying the criterion.

### C-037

ISSUE_011: Civil conspiracy — agreement between Tate and AgriNova alleged ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L309))

- **Sonnet 4.6: Pass.** Count XI (Civil Conspiracy) alleges specific facts supporting a pre-arranged agreement between Tate and AgriNova: (1) the conspiracy began 'no later than October 2024 — before Tate was employed by AgriNova,' suggesting a pre-departure arrangement; (2) Tate's LinkedIn update on December 22, 2024 (while still employed at Verdant) showing AgriNova as his employer with a February 2025 start date, with the inference that the agreement was reached during or before the period of exfiltration (¶42); (3) the simultaneous announcement of Tate's appointment and the BioYield platform on February 3, 2025 (¶45); (4) AgriNova's 'accelerated timeline' language suggesting it already had the Trade Secrets; and (5) coordinated recruitment of Verdant scientists with MicroMap 3.0 access (¶¶50-53). These are circumstantial but specific factual allegations of a meeting of the minds, not merely conclusory statements or parallel conduct.
- **GPT-5.5: Pass.** The complaint’s civil conspiracy count incorporates detailed preceding allegations that support a meeting of the minds between Tate and AgriNova, not just parallel conduct. Those facts include Tate’s LinkedIn update before leaving Verdant identifying AgriNova employment, allegations that Tate and AgriNova had agreed or were negotiating during the exfiltration period, AgriNova’s simultaneous announcement of Tate and BioYield on an accelerated timeline, and coordinated recruitment of Verdant scientists through Tate’s recommendations. Count XI then alleges an agreement and overt acts based on those facts.

### C-038

ISSUE_011: Civil conspiracy — underlying unlawful act identified ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L317))

- **Sonnet 4.6: Pass.** Count XI (Civil Conspiracy) explicitly identifies underlying unlawful acts. Paragraph 109 alleges that Tate and AgriNova agreed to misappropriate Verdant's Trade Secrets (an underlying tort). Paragraph 110 identifies the overt unlawful acts committed in furtherance of the conspiracy: 'Tate's exfiltration and transmission of the Trade Secrets, the destruction of evidence, AgriNova's acquisition and use of the Trade Secrets, and the solicitation of Verdant's scientists and distributors.' The count also incorporates all preceding paragraphs, which include trade secret misappropriation, breach of contract, and tortious interference claims. Under North Carolina law, civil conspiracy requires an underlying tort or wrong, and the complaint clearly identifies trade secret misappropriation and related torts as the underlying unlawful acts.
- **GPT-5.5: Pass.** The civil conspiracy count expressly alleges an agreement to misappropriate Verdant’s trade secrets and breach Tate’s contractual obligations, and identifies overt unlawful acts including exfiltration/transmission of trade secrets, destruction of evidence, AgriNova’s acquisition/use of trade secrets, and solicitation of employees/distributors. This satisfies the requirement to identify an underlying unlawful act or wrong under North Carolina law.

### C-039

Trade secrets identified with specificity — at least three categories described ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L325))

- **Sonnet 4.6: Pass.** The complaint identifies all four specific categories with substantial detail: (a) the Strain Library of 4,217 characterized microbial strains (¶18), (b) MicroMap 3.0 source code, algorithms, and model architecture for predicting strain synergies (¶19), (c) fourteen Formulation Dossiers (¶20), and (d) the TerraPrime Strategic Pipeline & Launch Roadmap 2025-2029 (¶21). Each is described with specificity including file locations, access restrictions, and content details — far exceeding the minimum threshold of three categories.
- **GPT-5.5: Pass.** The complaint identifies the trade secrets with specificity, including the proprietary library of 4,217 characterized microbial strains, MicroMap 3.0 source code/algorithms/model for predicting strain synergies, fourteen TerraPrime formulation dossiers, and the TerraPrime Strategic Pipeline & Launch Roadmap 2025–2029. This satisfies the requirement to describe at least three specified categories.

### C-040

Count I: DTSA claim against both Tate and AgriNova ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L333))

- **Sonnet 4.6: Pass.** Count I of the complaint is titled 'Misappropriation of Trade Secrets Under the Defend Trade Secrets Act, 18 U.S.C. § 1836 (Against All Defendants)' and is explicitly asserted against both Tate and AgriNova. Paragraphs 61 and 62 separately address Tate's misappropriation and AgriNova's misappropriation under the DTSA. The criterion is satisfied.
- **GPT-5.5: Pass.** The complaint includes Count I titled “Misappropriation of Trade Secrets Under the Defend Trade Secrets Act, 18 U.S.C. § 1836 (Against All Defendants)” and specifically alleges DTSA misappropriation by both Tate and AgriNova.

### C-041

Count II: NC Trade Secrets Protection Act claim against both defendants ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L341))

- **Sonnet 4.6: Pass.** COUNT II of the complaint is titled 'Misappropriation of Trade Secrets Under the North Carolina Trade Secrets Protection Act, N.C. Gen. Stat. § 66-152 et seq.' and is explicitly asserted '(Against All Defendants),' which includes both Tate and AgriNova. The count cites the relevant statutory provisions and alleges misappropriation by both defendants.
- **GPT-5.5: Pass.** The complaint includes Count II titled “Misappropriation of Trade Secrets Under the North Carolina Trade Secrets Protection Act, N.C. Gen. Stat. § 66-152 et seq. (Against All Defendants),” and alleges that Defendants misappropriated the trade secrets, thereby asserting the claim against both Tate and AgriNova.

### C-042

Count III: Breach of Employment Agreement against Tate ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L349))

- **Sonnet 4.6: Pass.** The complaint includes multiple counts for breach of the Employment Agreement against Tate specifically: Count IV (non-solicitation of employees, § 5.3), Count V (non-competition, § 5.2), Count VI (customer/distributor non-solicitation, § 5.4), and Count VII (notice-of-resignation/garden leave, § 7.3). All are asserted against Tate only. The criterion requires a count for breach of the Employment Agreement against Tate alleging violations of non-competition, non-solicitation, and/or garden leave provisions — all three are present.
- **GPT-5.5: Pass.** The complaint includes breach-of-contract counts against Tate based on the Employment Agreement, including employee non-solicitation (Count IV), non-competition (Count V), customer/distributor non-solicitation (Count VI), and notice-of-resignation provisions (Count VII). Although the CIAA breach is labeled Count III, the required Employment Agreement breach claims are present and asserted against Tate.

### C-043

Count IV: Breach of CIAA against Tate ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L357))

- **Sonnet 4.6: Pass.** Count III of the complaint is explicitly titled 'Breach of Contract: Confidentiality and Invention Assignment Agreement (Against Tate)' and alleges multiple breaches of the CIAA by Tate, including unauthorized downloading, copying, and removing Confidential Information, connecting unauthorized personal storage devices, transmitting data through personal email, disclosing Confidential Information to AgriNova, failing to return materials, and wiping the Company laptop. This directly satisfies the criterion.
- **GPT-5.5: Pass.** The complaint includes a specific count titled “COUNT III — Breach of Contract: Confidentiality and Invention Assignment Agreement (Against Tate),” alleging Tate breached the CIAA and seeking remedies. Although numbered Count III rather than Count IV, the required CIAA breach count against Tate is present.

### C-044

Count V: Tortious interference with contractual relations against AgriNova ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L365))

- **Sonnet 4.6: Pass.** COUNT VIII of the complaint is titled 'Tortious Interference With Contract (Against AgriNova)' and is directed solely against AgriNova. It alleges that AgriNova knew of the Employment Agreement and CIAA, intentionally induced Tate to breach those agreements (by employing him in violation of the non-compete, accepting misappropriated confidential information, and using Tate to recruit Verdant scientists), and acted without justification. This satisfies the criterion: the count is present, asserted against AgriNova (the correct party), and alleges that AgriNova induced Tate to breach his agreements with Verdant.
- **GPT-5.5: Pass.** The complaint includes a dedicated tortious interference with contract count against AgriNova (Count VIII), alleging AgriNova knew of Tate’s agreements and intentionally induced him to breach confidentiality, non-compete, and non-solicitation obligations.

### C-045

Count VI: Tortious interference with prospective economic advantage against AgriNova ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L373))

- **Sonnet 4.6: Fail.** The complaint includes Count VIII for 'Tortious Interference With Contract' against AgriNova, but there is no separate count for 'Tortious Interference with Prospective Economic Advantage' (or prospective business relations). The criterion specifically requires a count addressing tortious interference with prospective economic advantage/business relations, which is a distinct tort from tortious interference with an existing contract. The complaint does not include this separate cause of action. While Count VIII addresses interference with existing contracts (the Employment Agreement and CIAA), there is no count alleging interference with prospective economic advantage or prospective business relations, which would cover things like potential future customer relationships, distributor relationships, or other prospective business opportunities that AgriNova disrupted through its conduct.
- **GPT-5.5: Fail.** The complaint includes a tortious interference with contract claim against AgriNova and breach/non-solicitation counts against Tate, but it does not include a separate count for tortious interference with prospective economic advantage or business relations against AgriNova addressing employee solicitation or customer/distributor diversion.

### C-046

Count VII: Unjust enrichment against both defendants ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L381))

- **Sonnet 4.6: Fail.** Count X (Unjust Enrichment) is pleaded only against AgriNova, not against both Tate and AgriNova. The count heading reads 'COUNT X --- Unjust Enrichment (Against AgriNova)' and the body references only AgriNova. Tate is not named as a defendant in this count. The criterion requires the unjust enrichment count to name both defendants.
- **GPT-5.5: Fail.** The complaint includes an unjust enrichment count, but it is Count X and is asserted only against AgriNova, not against both Tate and AgriNova. Count VII is a breach of contract claim, not unjust enrichment.

### C-047

Count VIII: Civil conspiracy against both defendants ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L389))

- **Sonnet 4.6: Pass.** Count XI is titled 'Civil Conspiracy (Against All Defendants)' and paragraph 108 incorporates all preceding paragraphs, paragraph 109 alleges that 'Tate and AgriNova agreed to misappropriate Verdant's Trade Secrets,' and paragraph 111 states 'each Defendant is jointly and severally liable.' Both Tate and AgriNova are named as defendants in this count. The criterion asks for a civil conspiracy count against both defendants, which is satisfied here.
- **GPT-5.5: Pass.** The complaint includes a civil conspiracy claim, titled “COUNT XI — Civil Conspiracy (Against All Defendants),” and expressly alleges that Tate and AgriNova agreed and acted in furtherance of the conspiracy. Although it is numbered Count XI rather than Count VIII, it names both defendants.

### C-048

Factual allegation: October 27 mass download (3,814 files, 24.6 GB) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L397))

- **Sonnet 4.6: Pass.** Paragraph 35 of the complaint explicitly states: 'Between approximately 10:17 p.m. and 11:48 p.m. on Sunday, October 27, 2024, Tate, using his account "mtate_vp" from the Verdant R&D facility, downloaded 3,814 files totaling 24.6 GB from the TerraPrime directory on VaultSci to his Company laptop.' All three key details (date: October 27, 2024; file count: 3,814; data volume: 24.6 GB) are present and correct.
- **GPT-5.5: Pass.** The complaint specifically alleges that on October 27, 2024, Tate used his account to download 3,814 files totaling 24.6 GB from the TerraPrime directory on VaultSci, satisfying the required date, file count, volume, and source-directory details.

### C-049

Factual allegation: November 2 USB device transfer ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L405))

- **Sonnet 4.6: Pass.** Paragraph 37 of the complaint explicitly alleges that on November 2, 2024, at approximately 8:32 p.m., Tate connected a personal SanDisk Extreme Pro 256 GB USB flash drive (serial number SDP-82741-EXT) to his Company laptop and transferred approximately 24.6 GB of data to it. The complaint also notes this device was never authorized and references Verdant's Acceptable Use Policy (§ 4.3) prohibiting unauthorized external storage devices. All key details are present and accurate.
- **GPT-5.5: Pass.** The complaint specifically alleges that on November 2, 2024, Tate connected a personal SanDisk Extreme Pro 256 GB USB flash drive to his Company laptop and transferred approximately 24.6 GB of data to it. It also alleges Verdant’s Acceptable Use Policy prohibited connecting external storage devices without authorization and that Tate lacked authorization.

### C-050

Factual allegation: November 8 encrypted email ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L413))

- **Sonnet 4.6: Pass.** Paragraph 38 of the complaint alleges: 'At approximately 7:14 p.m. on November 8, 2024, while connected to Verdant's R&D network, Tate sent an email from his personal account, m.tate.phd@protonmail.com, to an external recipient, bearing an encrypted attachment of approximately 1.2 GB.' This matches all key details: the date (November 8, 2024), the personal ProtonMail account (m.tate.phd@protonmail.com), the encrypted attachment, the 1.2 GB size, and the connection to Verdant's network.
- **GPT-5.5: Fail.** The complaint alleges the November 8, 2024 encrypted email from Tate’s personal ProtonMail account with an approximately 1.2 GB attachment, but it states he was connected to Verdant’s “R&D network,” not Verdant’s WiFi network. The specific WiFi detail required by the criterion is omitted.

### C-051

Factual allegation: November 14 file deletion ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L421))

- **Sonnet 4.6: Fail.** The complaint does allege in paragraph 39 that on November 14, 2024, Tate deleted the 3,814 downloaded files from his laptop and purged the recycle bin. However, the criterion requires that the complaint also allege that 'Sentinel Digital Forensics recovered the deletion logs.' The complaint does not mention Sentinel Digital Forensics by name anywhere; it only refers to 'an independent digital-forensics firm' in paragraph 34. The specific requirement that the complaint name Sentinel Digital Forensics as the entity that recovered the deletion logs is not satisfied.
- **GPT-5.5: Fail.** The complaint alleges the November 14, 2024 deletion of the downloaded files and purging of the recycle bin, but it does not allege that Sentinel Digital Forensics recovered the deletion logs; it only references an unnamed independent digital-forensics firm and forensic artifacts generally.

### C-052

Factual allegation: November 15 Strategic Pipeline document download ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L429))

- **Sonnet 4.6: Pass.** Paragraph 40 of the complaint explicitly alleges: 'At approximately 2:17 p.m. on November 15, 2024, Tate downloaded the Strategic Roadmap, marked "HIGHLY CONFIDENTIAL --- EXECUTIVE DISTRIBUTION ONLY," which had not been included in the October 27 download.' Paragraph 21 identifies the Strategic Roadmap as the 47-page 'TerraPrime Strategic Pipeline & Launch Roadmap 2025--2029.' Both the date, the document name/description, and the classification marking are present.
- **GPT-5.5: Pass.** The complaint specifically alleges that on November 15, 2024, Tate downloaded the Strategic Roadmap, and earlier defines that document as the 47-page “TerraPrime Strategic Pipeline & Launch Roadmap 2025–2029” marked “HIGHLY CONFIDENTIAL — EXECUTIVE DISTRIBUTION ONLY.”

### C-053

Factual allegation: January 10 laptop returned wiped ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L437))

- **Sonnet 4.6: Pass.** Paragraph 43 of the complaint explicitly alleges that on January 9-10, 2025, Tate executed a 'Reset this PC — Remove everything' operation on his Company laptop, erasing all user data, and returned the wiped laptop on January 10, 2025, in violation of CIAA § 4.4, Employment Agreement § 4.3, and Verdant's IT Asset Return Policy. This satisfies the criterion.
- **GPT-5.5: Pass.** The complaint alleges that on January 9 Tate reset the Company laptop using 'Reset this PC — Remove everything,' and returned the wiped laptop on January 10, 2025, in violation of the CIAA, Employment Agreement, and Verdant's IT Asset Return Policy. It also states earlier that he reset the laptop to factory settings before his final day.

### C-054

Factual allegation: December 22 LinkedIn profile update ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L445))

- **Sonnet 4.6: Pass.** Paragraph 42 of the complaint explicitly states: 'December 22, 2024 --- AgriNova role disclosed. While still employed by Verdant, Tate updated his LinkedIn profile to identify himself as "Chief Science Officer, AgriNova Crop Sciences," with a start date of February 2025.' This directly satisfies the criterion.
- **GPT-5.5: Pass.** The complaint expressly alleges in paragraph 42 that on December 22, 2024, while still employed by Verdant, Tate updated his LinkedIn profile to identify himself as Chief Science Officer at AgriNova with a start date of February 2025.

### C-055

Factual allegation: BioYield similarity to TerraPrime ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L453))

- **Sonnet 4.6: Pass.** The complaint explicitly alleges BioYield's similarity to TerraPrime in multiple places. Paragraph 46 describes AgriNova's BioYield as using 'AI-driven bioinformatic models for predicting strain synergies' and a 'proprietary library of characterized microbial strains,' noting each element corresponds to a category of Verdant's Trade Secrets. Paragraph 49 specifically references the Heartland distributor report dated March 12, 2025, stating that Heartland informed Verdant that BioYield's 'described mechanism of action, strain-combination approach, and target crop applications were remarkably similar to Verdant's TerraPrime formulations.' Both the technology description similarity and the Heartland distributor report are clearly alleged.
- **GPT-5.5: Pass.** The complaint expressly alleges suspicious similarity between AgriNova's BioYield and Verdant's TerraPrime, including BioYield's AI-driven strain selection/synergy modeling and proprietary microbial strain library matching TerraPrime trade secret categories, and it specifically references the March 12, 2025 Heartland report that BioYield was “remarkably similar” to TerraPrime formulations.

### C-056

Factual allegation: $62.3M cumulative R&D investment ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L461))

- **Sonnet 4.6: Pass.** The complaint explicitly references the $62.3 million cumulative R&D investment in paragraph 16 ('Verdant invested approximately $62.3 million in TerraPrime') and again in paragraph 48 ('seven years and $62.3 million'). The figure is correctly stated and prominently featured.
- **GPT-5.5: Pass.** The complaint expressly alleges that Verdant invested approximately $62.3 million in the TerraPrime platform, including a breakdown of costs, and repeats the figure in later allegations.

### C-057

Factual allegation: Damages figures included ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L469))

- **Sonnet 4.6: Fail.** The complaint includes specific dollar figures related to Verdant's investment ($62.3 million in TerraPrime development) and revenue ($187 million FY2024, $4.2 million licensing), but does not include the specific damage estimates referenced in the criterion: the total estimated damages of approximately $85 million, or the component figures of $64.5M lost competitive advantage, $16.92M customer diversion, or $3.6M employee recruitment losses. The complaint states damages 'in an amount to be proven at trial' without specifying these particular figures.
- **GPT-5.5: Fail.** The complaint includes some monetary figures (e.g., Verdant’s $62.3 million TerraPrime investment and revenues), but it does not allege specific damages estimates of approximately $85 million or the specified component figures of $64.5M lost competitive advantage, $16.92M customer diversion, or $3.6M employee recruitment losses.

### C-058

Non-competition breach alleged: Tate joined AgriNova within 18 months ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L477))

- **Sonnet 4.6: Pass.** Count V (paragraphs 83-86) specifically alleges that Tate breached the 18-month non-competition covenant (Employment Agreement § 5.2) by joining AgriNova as Chief Science Officer in February 2025, within 18 months of his departure from Verdant, and that AgriNova competes with Verdant in the research, development, and sale of microbial agricultural and soil-enhancement products. This directly satisfies the criterion.
- **GPT-5.5: Pass.** The complaint specifically alleges an 18-month non-compete in Employment Agreement § 5.2, that AgriNova competes with Verdant in microbial agricultural and soil-enhancement products, and that Tate began employment with AgriNova as Chief Science Officer in February 2025 leading BioYield within 18 months of leaving Verdant, thereby breaching the covenant.

### C-059

Non-solicitation of customers/partners breach alleged ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L485))

- **Sonnet 4.6: Pass.** Count VI (paragraphs 87-91) explicitly alleges breach of the customer and distributor non-solicitation covenant (Employment Agreement § 5.4), specifically referencing Heartland as Verdant's largest distributor with whom Tate had material contact, and alleging that Tate participated in AgriNova's presentation of BioYield to Heartland. The Heartland relationship is also referenced in paragraph 49 in the factual allegations. This clearly satisfies the criterion.
- **GPT-5.5: Pass.** The complaint expressly alleges breach of the customer/distributor non-solicitation covenant, including Tate’s material contact with Heartland and AgriNova’s BioYield presentation/solicitation to Heartland, Verdant’s largest distributor.

### C-060

Sentinel Digital Forensics report referenced as basis for IT findings ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L493))

- **Sonnet 4.6: Fail.** The complaint references 'an independent digital-forensics firm' in paragraph 34 but does not name it as 'Sentinel Digital Forensics, Inc.' The firm is never identified by name anywhere in the document.
- **GPT-5.5: Fail.** The complaint references an unnamed independent digital-forensics firm and forensic examination, but it does not identify Sentinel Digital Forensics, Inc. or reference a Sentinel report as the source of the IT findings.

### C-061

NC choice-of-law provision noted for contract claims ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L501))

- **Sonnet 4.6: Pass.** Paragraph 33 of the complaint explicitly states: 'The Agreements are governed by North Carolina law (Employment Agreement § 9.1; CIAA § 9.1).' Additionally, the contract claims (Counts III-VII) incorporate this by reference, and the complaint consistently applies North Carolina law throughout, including citing N.C. Gen. Stat. provisions for the state-law claims. The choice-of-law provision is clearly noted and applied.
- **GPT-5.5: Pass.** The complaint expressly states that the Employment Agreement and CIAA are governed by North Carolina law, citing the choice-of-law provisions in Employment Agreement § 9.1 and CIAA § 9.1, and frames the contract claims accordingly.

### C-062

DISTRACTOR_003: No separate computer fraud claim based on Protonmail use ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L509))

- **Sonnet 4.6: Pass.** The complaint contains eleven counts (I through XI). None of them is a standalone CFAA or computer fraud claim. The ProtonMail encrypted email is referenced as factual evidence within other counts (e.g., DTSA misappropriation, NCTSPA, breach of CIAA, civil conspiracy) but is never the basis of a separate cause of action for unauthorized computer access or computer fraud. The criterion is satisfied.
- **GPT-5.5: Pass.** The complaint references Tate’s ProtonMail transmission as factual evidence supporting trade secret misappropriation and breach claims, but it does not plead a standalone CFAA, computer fraud, unauthorized access, or similar cause of action based on personal email use.

### C-063

DISTRACTOR_004: No breach-of-contract claim against AgriNova ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L517))

- **Sonnet 4.6: Pass.** Reviewing all counts in the complaint: Count III (Breach of Contract: CIAA) is against Tate only. Count IV (Breach of Contract: Non-Solicitation) is against Tate only. Count V (Breach of Contract: Non-Competition) is against Tate only. Count VI (Breach of Contract: Customer/Distributor Non-Solicitation) is against Tate only. Count VII (Breach of Contract: Notice-of-Resignation) is against Tate only. AgriNova is named as a defendant in Count I (DTSA), Count II (NCTSPA), Count VIII (Tortious Interference), Count IX (UDTPA), Count X (Unjust Enrichment), and Count XI (Civil Conspiracy). No breach of contract count is asserted against AgriNova. The complaint correctly channels AgriNova's liability through tortious interference, trade secret statutes, unjust enrichment, and civil conspiracy.
- **GPT-5.5: Pass.** The complaint asserts breach-of-contract counts only against Tate (Counts III–VII). AgriNova is named in non-contract theories such as DTSA/NCTSPA misappropriation, tortious interference, UDTPA, unjust enrichment, and civil conspiracy, but no breach-of-contract claim is asserted directly against AgriNova.

### C-064

Complaint-drafting-notes.docx is a separate deliverable ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L525))

- **Sonnet 4.6: Pass.** The agent produced a document explicitly labeled 'complaint-drafting-notes.docx' that is a separate memorandum containing strategic concerns, observations, and recommendations about the case. It is distinct from the complaint itself and includes sections on claims analysis, strategic concerns, anticipated defenses, document discrepancies, and recommended next steps. This satisfies the criterion of a separate drafting notes document.
- **GPT-5.5: Pass.** The agent produced a distinct document labeled “complaint-drafting-notes.docx” in memorandum form, separate from the complaint itself, and it contains strategic concerns, observations, anticipated defenses, recommendations, and next steps about the case.

### C-065

Drafting notes flag need for TRO/PI motion ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L533))

- **Sonnet 4.6: Pass.** The drafting notes extensively discuss TRO/PI strategy in multiple sections. Section 1 mentions 'the TRO against AgriNova is the most exposed part of our position' and recommends filing 'the complaint and TRO/expedited-discovery motion as soon as the verification and open items below are done.' Section 3.5 is titled 'Relief: TRO scope and the DTSA employment limitation' and discusses TRO scope, DTSA ex parte civil seizure, bond requirements, and sealing. Section 6 (Next Steps) item 4 explicitly calls for preparing 'TRO papers: Driscoll declaration, IT Director (Marsh) declaration on protective measures, re-executed Kowalski and Okonkwo declarations, proposed forensic protocol, and a proposed order focused on no-use, turnover and sequestration, preservation, and expedited discovery.' The notes clearly recommend filing a TRO motion contemporaneously with the complaint.
- **GPT-5.5: Pass.** The drafting notes expressly recommend filing the complaint together with a TRO/expedited-discovery motion as soon as possible, discuss TRO scope and relief, and list preparation of TRO papers as a recommended next step.

### C-066

Factual allegation: Tate's employment dates (March 15, 2018 – January 10, 2025) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L541))

- **Sonnet 4.6: Pass.** Paragraph 6 states: 'Tate was employed by Verdant as Vice President, Research & Development from March 15, 2018 through January 10, 2025.' Both dates are present and correct.
- **GPT-5.5: Pass.** The complaint expressly states that Tate was employed by Verdant from March 15, 2018 through January 10, 2025, satisfying both required dates.

### C-067

Factual allegation: Tate executed both Employment Agreement and CIAA ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L549))

- **Sonnet 4.6: Pass.** Paragraph 25 explicitly states: 'Tate executed two written agreements on March 15, 2018: an Employment Agreement (the "Employment Agreement") and a Confidentiality and Invention Assignment Agreement (the "CIAA") (together, the "Agreements").' Both agreements are mentioned and the date March 15, 2018 is specified.
- **GPT-5.5: Pass.** The complaint expressly alleges in paragraph 25 that, as a condition of employment, Tate executed both an Employment Agreement and a Confidentiality and Invention Assignment Agreement on March 15, 2018.

### C-068

AgriNova press release content alleged (February 3, 2025) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L557))

- **Sonnet 4.6: Pass.** Paragraphs 45-47 of the complaint explicitly reference AgriNova's February 3, 2025 press release, describing its announcement of Tate's appointment as Chief Science Officer and the simultaneous unveiling of BioYield. The press release is also listed as Exhibit D in the Index of Exhibits.
- **GPT-5.5: Pass.** The complaint expressly references AgriNova's February 3, 2025 press release in paragraph 45, alleging that it announced Tate's appointment as Chief Science Officer and concurrently unveiled BioYield. It also lists the press release as Exhibit D.

### C-069

Factual allegation: MicroMap 3.0 limited to 12 employees ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L565))

- **Sonnet 4.6: Pass.** Paragraph 19 states: 'Only twelve Verdant employees had full access to MicroMap 3.0.' Tate's access is established throughout the complaint (e.g., paragraph 24 states he 'had access to each category of the Trade Secrets,' and paragraph 35 details his download of MicroMap 3.0 files). The criterion requires the complaint to allege that access was restricted to 12 employees and that Tate was one of them. Both elements are present.
- **GPT-5.5: Pass.** The complaint states that “Only twelve Verdant employees had full access to MicroMap 3.0” and separately alleges that Tate oversaw TerraPrime and “had access to each category of the Trade Secrets,” which includes MicroMap 3.0. This satisfies the required access restriction detail and Tate’s inclusion.

### C-070

CIAA survival clause referenced ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L573))

- **Sonnet 4.6: Pass.** Paragraph 26 of the complaint explicitly states: 'These obligations survive in perpetuity as to trade secrets and for five years as to other Confidential Information (§ 8.1).' This directly references the CIAA's survival clause and specifies that confidentiality obligations survive termination in perpetuity for trade secrets.
- **GPT-5.5: Pass.** The complaint expressly references the CIAA survival clause, alleging that Tate's confidentiality/non-use obligations survive termination “in perpetuity as to trade secrets and for five years as to other Confidential Information” in CIAA § 8.1.

### C-071

Factual allegation: Verdant's annual trade secret training ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L581))

- **Sonnet 4.6: Pass.** The complaint explicitly mentions annual trade-secret training in paragraph 23 under 'Reasonable Measures to Protect the Trade Secrets': 'mandatory annual trade-secret training, which Tate most recently completed on September 12, 2024.' This satisfies the criterion.
- **GPT-5.5: Pass.** The complaint expressly alleges Verdant had “mandatory annual trade-secret training” and states Tate most recently completed it on September 12, 2024.
