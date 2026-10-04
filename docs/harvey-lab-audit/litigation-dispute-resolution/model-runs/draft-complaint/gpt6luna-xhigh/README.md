# GPT-6 Luna (xhigh): Draft Federal Complaint for Trade Secret Misappropriation and Breach of Employment Agreement

> [!NOTE]
> **Unedited model output and AI judge grades.** The deliverables are AI-generated drafts on Harvey LAB's fictional task records. Pass/fail verdicts are the native LAB judges' AI judgments, not human review or accepted corrections. See the [model-runs overview](../../README.md).

[Task audit page](../../../tasks/draft-complaint/README.md) · [Pinned task and rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json) · [Claude Opus 5.5 (low) run](../opus55-low/README.md) · [All runs](../../README.md)

**Model:** `gpt-6-luna`, reasoning effort `xhigh`. **Run:** `20260926-201603`.

**Native grades:** Sonnet 4.6 passed 64 of 71 criteria; GPT-5.5 passed 62 of 71 criteria. LAB all-pass score: 0 (mean of the judges' all-pass results; a task scores 1 with a judge only if every criterion passes).

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
| [C-018](#c-018) | ISSUE_002: Ex parte seizure option identified or addressed | **Fail** | **Fail** |
| [C-019](#c-019) | ISSUE_003: Missing DTSA whistleblower immunity notice identified | Pass | **Fail** |
| [C-020](#c-020) | ISSUE_003: Impact of missing whistleblower notice on remedies | Pass | Pass |
| [C-021](#c-021) | Garden leave notice shortfall alleged as breach | Pass | Pass |
| [C-022](#c-022) | Garden leave notice calculation: 53 days / 7 days short | Pass | Pass |
| [C-023](#c-023) | ISSUE_004: Harm from insufficient notice period alleged | **Fail** | **Fail** |
| [C-024](#c-024) | ISSUE_005: NC Trade Secrets Act statute of limitations addressed | Pass | Pass |
| [C-025](#c-025) | Specific protective measures for trade secrets alleged (at least 3 of 6) | Pass | Pass |
| [C-026](#c-026) | ISSUE_007: AgriNova's knowledge of misappropriation alleged with facts | Pass | Pass |
| [C-027](#c-027) | ISSUE_008: Preemption risk for common-law claims addressed | Pass | Pass |
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
| [C-045](#c-045) | Count VI: Tortious interference with prospective economic advantage against AgriNova | Pass | Pass |
| [C-046](#c-046) | Count VII: Unjust enrichment against both defendants | **Fail** | **Fail** |
| [C-047](#c-047) | Count VIII: Civil conspiracy against both defendants | Pass | Pass |
| [C-048](#c-048) | Factual allegation: October 27 mass download (3,814 files, 24.6 GB) | Pass | Pass |
| [C-049](#c-049) | Factual allegation: November 2 USB device transfer | Pass | **Fail** |
| [C-050](#c-050) | Factual allegation: November 8 encrypted email | **Fail** | **Fail** |
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

- **Sonnet 4.6: Pass.** The complaint caption clearly identifies 'IN THE UNITED STATES DISTRICT COURT FOR THE EASTERN DISTRICT OF NORTH CAROLINA NORTHERN DIVISION.' This satisfies the criterion of identifying the correct court (E.D.N.C.). The division listed is 'Northern Division' rather than 'Western Division or Raleigh,' but the criterion states 'Western Division or Raleigh' as examples, and the key requirement is that the Eastern District of North Carolina is named, which it is.
- **GPT-5.5: Pass.** The caption identifies the United States District Court for the Eastern District of North Carolina. Although it lists the Northern Division rather than Raleigh/Western Division, the specified federal court (E.D.N.C.) is named.

### C-002

Complaint names Verdant Biotech Solutions, Inc. as Plaintiff ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L25))

- **Sonnet 4.6: Pass.** The complaint clearly names 'VERDANT BIOTECH SOLUTIONS, INC.' as the Plaintiff in the caption and throughout the document.
- **GPT-5.5: Pass.** The complaint caption and opening paragraph name 'VERDANT BIOTECH SOLUTIONS, INC.' / 'Plaintiff Verdant Biotech Solutions, Inc.' as the Plaintiff.

### C-003

Plaintiff's state of incorporation: Delaware ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L33))

- **Sonnet 4.6: Pass.** Paragraph 6 explicitly states: 'Plaintiff Verdant is a Delaware corporation with its principal place of business at 4510 Meridian Research Drive, Suite 300, Research Triangle Park, North Carolina 27709.' This clearly identifies Verdant as incorporated in Delaware.
- **GPT-5.5: Pass.** The complaint identifies Plaintiff Verdant as “a Delaware corporation” in paragraph 6, satisfying the requirement to state Delaware as its incorporation state.

### C-004

Plaintiff's headquarters address: Research Triangle Park, NC ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L41))

- **Sonnet 4.6: Pass.** Paragraph 6 of the complaint states: 'Plaintiff Verdant is a Delaware corporation with its principal place of business at 4510 Meridian Research Drive, Suite 300, Research Triangle Park, North Carolina 27709.' This exactly matches the required address.
- **GPT-5.5: Pass.** The complaint identifies Verdant as a Delaware corporation with its principal place of business at 4510 Meridian Research Drive, Suite 300, Research Triangle Park, North Carolina 27709.

### C-005

Complaint names Dr. Marcus Ellison Tate as a Defendant ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L49))

- **Sonnet 4.6: Pass.** The complaint explicitly names 'DR. MARCUS ELLISON TATE' as a Defendant in the caption and throughout the document, including in the parties section (paragraph 7) and in multiple counts.
- **GPT-5.5: Pass.** The complaint caption names “DR. MARCUS ELLISON TATE” as a defendant, and the parties section identifies Defendant Tate by full name and describes his role.

### C-006

Defendant Tate's residence identified as Chapel Hill, NC ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L57))

- **Sonnet 4.6: Pass.** Paragraph 7 of the complaint states: 'Defendant Tate is an individual residing at 1822 Foxglove Lane, Chapel Hill, North Carolina 27517.' This exactly matches the criterion requiring Tate's residence to be identified as 1822 Foxglove Lane, Chapel Hill, NC 27517.
- **GPT-5.5: Pass.** The complaint identifies Defendant Tate as an individual residing at 1822 Foxglove Lane, Chapel Hill, North Carolina 27517.

### C-007

Complaint names AgriNova Crop Sciences, LLC as a Defendant ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L65))

- **Sonnet 4.6: Pass.** The complaint clearly names 'AGRINOVA CROP SCIENCES, LLC' as a Defendant in the caption and throughout the document, including in the parties section (paragraph 8) and in multiple counts.
- **GPT-5.5: Pass.** The complaint caption and party allegations name “AGRINOVA CROP SCIENCES, LLC” / “AgriNova” as a defendant, and claims are asserted against it.

### C-008

Defendant AgriNova identified as a North Carolina LLC ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L73))

- **Sonnet 4.6: Pass.** Paragraph 8 of the complaint explicitly states: 'Defendant AgriNova is a North Carolina limited liability company with its principal office at 780 Sycamore Innovation Parkway, Suite 1200, Raleigh, North Carolina 27601.' This correctly identifies AgriNova as a North Carolina LLC.
- **GPT-5.5: Pass.** The complaint expressly states that Defendant AgriNova is a North Carolina limited liability company with its principal office in Raleigh, North Carolina.

### C-009

Defendant AgriNova's principal office address: Raleigh, NC ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L81))

- **Sonnet 4.6: Pass.** Paragraph 8 of the complaint states: 'Defendant AgriNova is a North Carolina limited liability company with its principal office at 780 Sycamore Innovation Parkway, Suite 1200, Raleigh, North Carolina 27601.' This exactly matches the required address.
- **GPT-5.5: Pass.** The complaint identifies AgriNova as a North Carolina LLC with its principal office at 780 Sycamore Innovation Parkway, Suite 1200, Raleigh, North Carolina 27601.

### C-010

Complaint asserts federal question jurisdiction under DTSA ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L89))

- **Sonnet 4.6: Pass.** Paragraph 9 explicitly states: 'This Court has subject-matter jurisdiction over the DTSA claim under 18 U.S.C. § 1836(c) and 28 U.S.C. § 1331.' This directly asserts federal question jurisdiction under the DTSA.
- **GPT-5.5: Pass.** The complaint expressly alleges subject-matter jurisdiction over the DTSA claim under 18 U.S.C. § 1836(c) and 28 U.S.C. § 1331 in paragraph 9, thereby asserting federal question jurisdiction based on the Defend Trade Secrets Act.

### C-011

Complaint asserts supplemental jurisdiction under 28 U.S.C. § 1367 ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L97))

- **Sonnet 4.6: Pass.** Paragraph 9 of the complaint explicitly states: 'The Court has supplemental jurisdiction over the related state-law claims under 28 U.S.C. § 1367 because they form part of the same case or controversy.' This directly satisfies the criterion.
- **GPT-5.5: Pass.** The complaint expressly states that the Court has supplemental jurisdiction over the related state-law claims under 28 U.S.C. § 1367.

### C-012

Complaint asserts proper venue under 28 U.S.C. § 1391(b) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L105))

- **Sonnet 4.6: Pass.** Paragraph 11 explicitly states: 'Venue is proper in this District under 28 U.S.C. § 1391(b)(1) and (b)(2). Both Defendants reside in North Carolina for venue purposes, and a substantial part of the events or omissions giving rise to the claims occurred in this District, including conduct at Verdant's Research Triangle Park headquarters and AgriNova's Raleigh headquarters.' This directly cites 28 U.S.C. § 1391(b) and alleges both that defendants reside in the district and that a substantial part of the events occurred there.
- **GPT-5.5: Pass.** The complaint expressly alleges venue is proper under 28 U.S.C. § 1391(b)(1) and (b)(2), stating that both defendants reside in North Carolina for venue purposes and that a substantial part of the events occurred in the Eastern District of North Carolina, including at Verdant’s RTP headquarters and AgriNova’s Raleigh headquarters.

### C-013

Complaint references forum-selection clause in Employment Agreement ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L113))

- **Sonnet 4.6: Pass.** Paragraph 12 of the complaint explicitly references the forum-selection clause in Tate's Employment Agreement and Confidentiality and Invention Assignment Agreement, stating that those agreements 'select the federal or state courts located in Wake County, North Carolina, for covered disputes' and that 'The forum provisions bind Tate.'
- **GPT-5.5: Pass.** The complaint expressly references that Tate's Employment Agreement selects federal or state courts located in Wake County, North Carolina for covered disputes, providing a contractual basis for venue/forum.

### C-014

Complaint alleges personal jurisdiction over Tate ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L121))

- **Sonnet 4.6: Pass.** Paragraph 10 explicitly states: 'This Court has personal jurisdiction over Tate because he resides in North Carolina and the conduct at issue occurred in substantial part in this State.' This clearly alleges personal jurisdiction over Dr. Marcus Ellison Tate.
- **GPT-5.5: Pass.** The complaint expressly alleges personal jurisdiction over Tate in paragraph 10, stating that he resides in North Carolina and that substantial conduct occurred there. It also identifies his North Carolina residence in paragraph 7.

### C-015

Complaint alleges personal jurisdiction over AgriNova ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L129))

- **Sonnet 4.6: Pass.** Paragraph 10 explicitly alleges personal jurisdiction over AgriNova: 'The Court has personal jurisdiction over AgriNova because it is organized under North Carolina law, maintains its principal office in Raleigh, and conducts the challenged business activity in North Carolina.' This satisfies the criterion.
- **GPT-5.5: Pass.** The complaint expressly alleges personal jurisdiction over AgriNova in paragraph 10, stating that AgriNova is organized under North Carolina law, maintains its principal office in Raleigh, and conducts the challenged business activity in North Carolina.

### C-016

Interstate commerce nexus: statutory allegation present ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L137))

- **Sonnet 4.6: Pass.** The complaint explicitly alleges the interstate commerce nexus required by 18 U.S.C. § 1836(b)(1) in multiple places. Paragraph 43 states: 'The trade secrets at issue relate to products and services used in or intended for use in interstate and foreign commerce.' Paragraph 49 in Count I repeats this allegation: 'The secrets relate to products and services used in, or intended for use in, interstate and foreign commerce, including agricultural products distributed in 38 states and technology licensed internationally.' This satisfies the statutory requirement.
- **GPT-5.5: Pass.** The complaint expressly alleges the required DTSA interstate/foreign commerce nexus, including that TerraPrime products are sold in 38 states, licensed internationally, and that the trade secrets relate to products and services used in or intended for use in interstate and foreign commerce (paragraphs 43 and 49).

### C-017

Interstate commerce nexus: specific supporting facts alleged ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L145))

- **Sonnet 4.6: Pass.** The complaint contains multiple specific factual allegations supporting the interstate commerce nexus. Paragraph 43 states: 'Verdant's TerraPrime products are sold and distributed in 38 states, and Verdant licenses TerraPrime technology internationally in Brazil and Canada.' This is a concrete factual allegation, not merely a bare statutory recital. Additionally, paragraph 49 references these same facts in the context of the DTSA count. These specific facts (38 states of distribution, international licensing in Brazil and Canada) clearly satisfy the criterion.
- **GPT-5.5: Pass.** The complaint includes specific factual allegations supporting the interstate commerce nexus, including that TerraPrime products are sold and distributed in 38 states and that Verdant licenses TerraPrime technology internationally in Brazil and Canada. It also ties the trade secrets to products and services used or intended for use in interstate and foreign commerce.

### C-018

ISSUE_002: Ex parte seizure option identified or addressed ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L153))

- **Sonnet 4.6: Fail.** Neither the draft complaint nor the drafting notes mention the DTSA's ex parte seizure provision under 18 U.S.C. § 1836(b)(2). The complaint's prayer for relief requests injunctive relief but does not reference ex parte seizure. The drafting notes discuss injunctive relief strategy under Rule 65 and expedited discovery but never mention the ex parte seizure remedy or its applicability to facts like the laptop wipe or encrypted communications.
- **GPT-5.5: Fail.** Neither the complaint nor the drafting notes mention the DTSA ex parte seizure provision, 18 U.S.C. § 1836(b)(2), or discuss it as an extraordinary remedy potentially supported by facts like the laptop wipe or encrypted communications.

### C-019

ISSUE_003: Missing DTSA whistleblower immunity notice identified ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L162))

- **Sonnet 4.6: Pass.** Section 4 of the drafting notes explicitly addresses the DTSA whistleblower immunity notice issue: 'Federal exemplary damages and attorneys' fees against an employee under the DTSA depend on 18 U.S.C. § 1833(b) notice. Tate's 2018 CIAA text, as supplied, contains no immunity notice. If Verdant failed to provide the required notice in this or another applicable agreement/policy, the statute bars DTSA exemplary damages and attorneys' fees against Tate (not necessarily against AgriNova).' This directly identifies that the CIAA lacks the required notice and flags the consequence of being barred from recovering exemplary damages and attorneys' fees under the DTSA. The Employment Agreement is also implicitly covered by the instruction to 'Verify all signed agreements and incorporated policies.' The criterion is satisfied.
- **GPT-5.5: Fail.** The output flags the DTSA § 1833(b) whistleblower-immunity notice issue and states that the CIAA lacks the notice and that the omission may bar DTSA exemplary damages and attorneys’ fees. However, it does not identify that the Employment Agreement also lacks the required notice; it only says to verify other agreements/policies. The criterion requires identifying that neither the Employment Agreement nor the CIAA contains the notice.

### C-020

ISSUE_003: Impact of missing whistleblower notice on remedies ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L170))

- **Sonnet 4.6: Pass.** Section 4 of the drafting notes explicitly addresses the § 1833(b) whistleblower immunity notice issue. It states: 'Federal exemplary damages and attorneys' fees against an employee under the DTSA depend on 18 U.S.C. § 1833(b) notice. Tate's 2018 CIAA text, as supplied, contains no immunity notice. If Verdant failed to provide the required notice in this or another applicable agreement/policy, the statute bars DTSA exemplary damages and attorneys' fees against Tate (not necessarily against AgriNova).' This directly addresses the remedial impact of the missing notice, explaining that both exemplary damages (up to 2x) and attorney fees under the DTSA may be unavailable against Tate if the notice was not provided.
- **GPT-5.5: Pass.** The notes expressly discuss 18 U.S.C. § 1833(b), state that the supplied CIAA lacks the required immunity/whistleblower notice, and explain that failure to provide the notice bars DTSA exemplary damages and attorneys’ fees against Tate, subject to verification of other agreements or policies.

### C-021

Garden leave notice shortfall alleged as breach ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L178))

- **Sonnet 4.6: Pass.** Paragraph 67 explicitly alleges that Tate breached the 60-day notice provision by giving notice on November 18, 2024 for an effective departure on January 10, 2025, a 53-day interval (7 days short), and identifies this as a contractual breach under Count IV. This satisfies the criterion.
- **GPT-5.5: Pass.** The complaint expressly alleges the Employment Agreement required at least 60 calendar days' written notice, that Tate gave notice on November 18, 2024 for a January 10, 2025 departure (53 days, seven days short), and in Count IV specifically pleads this shortfall as a contractual breach separate from other conduct.

### C-022

Garden leave notice calculation: 53 days / 7 days short ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L186))

- **Sonnet 4.6: Pass.** Paragraph 32 states: 'The notice period was 53 calendar days, seven days short of the 60-day period required by the Employment Agreement.' Paragraph 67 also references the '53-day interval' and the '60-day notice provision.' Both the 53-day figure and the 7-days-short calculation are explicitly present in the complaint.
- **GPT-5.5: Pass.** The complaint expressly states that Tate gave notice on November 18, 2024 for a January 10, 2025 departure, which was 53 calendar days and seven days short of the required 60-day notice period.

### C-023

ISSUE_004: Harm from insufficient notice period alleged ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L194))

- **Sonnet 4.6: Fail.** The criterion requires that either the complaint or the drafting notes explain that the insufficient notice deprived Verdant of the opportunity to invoke the garden-leave provision, restrict Tate's systems access earlier, and potentially prevent some of the data exfiltration. Looking at both documents: The complaint (Count IV, paragraph 67) acknowledges the 7-day shortfall but explicitly states 'Verdant seeks nominal damages and any actual, non-speculative damages proved to have been caused by that breach; it does not contend that the seven-day shortfall caused the October--November exfiltration, which preceded notice.' The drafting notes (Section 2C) similarly state: 'The bulk exfiltration occurred before notice, so the missed seven days cannot have caused that conduct. Plead only the clear notice breach and nominal or proven actual damages; avoid asserting $85 million or prevention costs as causally attributable to the shortfall.' Neither document explains that the short notice deprived Verdant of the opportunity to invoke garden leave, restrict systems access earlier, or potentially prevent data exfiltration. In fact, both documents explicitly disclaim any causal connection between the notice shortfall and the exfiltration. The specific harm described in the criterion (opportunity to invoke garden leave, restrict access, prevent exfiltration) is not addressed anywhere in either document.
- **GPT-5.5: Fail.** The complaint mentions the 53-day notice and seeks nominal or proven damages, but expressly states the shortfall did not cause the October–November exfiltration. The drafting notes likewise state the missed seven days could not have caused the bulk exfiltration and only discuss garden leave to say it was discretionary. Neither document explains that insufficient notice deprived Verdant of an opportunity to invoke garden leave, restrict Tate’s access earlier, and potentially prevent exfiltration.

### C-024

ISSUE_005: NC Trade Secrets Act statute of limitations addressed ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L203))

- **Sonnet 4.6: Pass.** The drafting notes (complaint-drafting-notes.docx) in Section 5 under 'Limitations and remedial defenses' explicitly states: 'The supplied dates place discovery in February 2025, well within federal and state three-year periods, but document actual discovery dates and preserve the continuing-misappropriation timeline.' This references the 3-year statute of limitations and notes that the filing is timely given the February 2025 discovery date. This satisfies the criterion of addressing the NC TSPA statute of limitations and noting the filing is timely.
- **GPT-5.5: Pass.** The drafting notes expressly address limitations, stating that the supplied dates place discovery in February 2025, well within the federal and state three-year periods, and the complaint/NCUTSA count references N.C. Gen. Stat. §§ 66-152 to 66-157. This sufficiently notes timeliness under the NC Trade Secrets Act limitations period.

### C-025

Specific protective measures for trade secrets alleged (at least 3 of 6) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L212))

- **Sonnet 4.6: Pass.** The complaint in paragraph 20 alleges the following specific protective measures: (1) role-based access and download logs in VaultSci (electronic access controls), (2) restricted full MicroMap access to 12 designated employees (limited access), (3) restricted executive roadmap access to seven senior personnel (limited access/classification), (4) classification markings ('R&D-restricted' and 'executive-only'), (5) physical access controls including biometric access to cryogenic storage, (6) required employee confidentiality and invention-assignment agreements (mandatory NDA), (7) annual trade-secret training completed by Tate on September 12, 2024. This clearly satisfies at least three of the six listed measures — in fact all six are present.
- **GPT-5.5: Pass.** The complaint alleges multiple specific protective measures, including role-based access controls on VaultSci, confidentiality/invention-assignment agreements, annual trade-secret training, classification/restricted markings, limited access to MicroMap for 12 employees, and physical/biometric access controls. This exceeds the required minimum of three listed measures.

### C-026

ISSUE_007: AgriNova's knowledge of misappropriation alleged with facts ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L220))

- **Sonnet 4.6: Pass.** The complaint extensively alleges AgriNova's knowledge with specific circumstantial facts. Paragraph 38 states AgriNova 'knew or had reason to know that Tate's former position gave him access to highly valuable competitor information and that he owed continuing duties not to disclose or use it.' Paragraph 37 supports this with multiple specific facts: (a) timing — Tate's departure and AgriNova's February 3, 2025 announcement; (b) BioYield's suspicious similarity to TerraPrime — 'AI-driven strain selection, and synergy modeling,' 'proprietary library of characterized microbial strains,' same initial crop targets (soybeans, corn, wheat), described as 'consistent with material elements of TerraPrime'; (c) the recruiter's outreach expressly attributing the Okonkwo recommendation to Tate by name (paragraph 40); and (d) the 'accelerated announced launch schedule' and impossibly fast Q4 2025 timeline (paragraphs 36-37). All four supporting fact categories from the criterion are present, well exceeding the minimum of two required.
- **GPT-5.5: Pass.** The complaint expressly alleges that AgriNova knew or had reason to know the information was misappropriated and supports that allegation with multiple circumstantial facts: Tate joined/was announced by AgriNova shortly after departure, BioYield is described as highly similar to TerraPrime with AI-driven strain selection and synergy modeling, AgriNova announced an accelerated Q4 2025 launch timeline, and an AgriNova recruiter contacted a Verdant scientist stating Tate specifically recommended him.

### C-027

ISSUE_008: Preemption risk for common-law claims addressed ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L228))

- **Sonnet 4.6: Pass.** The drafting notes explicitly address NCUTSA preemption under section 2D (AgriNova tort claims): 'North Carolina Trade Secrets Protection Act displacement: Common-law claims premised solely on trade-secret misappropriation may be displaced. The complaint states contract-interference and conspiracy theories around independent contractual obligations and pleads unjust enrichment alternatively, but counsel should reassess preemption after identifying the precise factual basis for each.' The notes also warn against adding duplicate conversion, common-law misappropriation, or unfair-competition counts without a distinct nonsecret property interest or independent duty. Additionally, the unjust enrichment count in the complaint is expressly pleaded in the alternative and limited to the extent 'not displaced by statute or governed by an express contract.' The civil conspiracy count similarly notes it 'is not intended to evade any statutory displacement of common-law trade-secret claims.' The complaint frames the tortious interference and conspiracy claims around independent contractual obligations and solicitation conduct beyond pure trade secret misappropriation. Both the complaint and drafting notes address the preemption risk and recommend framing strategies, satisfying the criterion.
- **GPT-5.5: Pass.** The output expressly addresses NC Trade Secrets Protection Act displacement/preemption risk. The complaint pleads unjust enrichment in the alternative only to the extent not displaced by statute and frames civil conspiracy around independent conduct such as tortious interference/recruiting. The drafting notes also specifically flag NC TSPA displacement and recommend reassessing/framing common-law claims around independent duties and nonduplicative conduct.

### C-028

ISSUE_009: Tate's direct solicitation of Kowalski alleged ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L237))

- **Sonnet 4.6: Pass.** Paragraph 39 of the complaint alleges that on February 20, 2025, Tate texted Verdant Senior Research Scientist Dr. Anya Kowalski: 'Hey Anya, are you happy at Verdant? Things are moving fast here at AgriNova. We're building something incredible. I'd love to chat about what we're putting together---looking for top talent. Coffee sometime?' The complaint further states that Kowalski understood the text as an effort to recruit her to AgriNova. Count IV (paragraph 69) then explicitly alleges this as a breach of the employee nonsolicitation covenant. All required elements are present and accurate.
- **GPT-5.5: Pass.** The complaint specifically alleges that on February 20, 2025 Tate texted Dr. Anya Kowalski asking if she was happy at Verdant, stating AgriNova was building something incredible and looking for top talent, and later alleges this direct approach breached the employee nonsolicitation covenant.

### C-029

ISSUE_009: Tate's indirect solicitation of Okonkwo via recruiter alleged ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L245))

- **Sonnet 4.6: Pass.** The complaint explicitly alleges in paragraph 40 that an AgriNova recruiter sent Dr. James Okonkwo a LinkedIn message on February 28, 2025 stating 'Dr. Marcus Tate has specifically recommended you for a senior genomics role on our new BioYield team.' Paragraph 40 further alleges that 'on information and belief, Tate identified Okonkwo to AgriNova and thereby indirectly solicited or recruited him for the BioYield team.' Paragraph 69 in Count IV also references this indirect solicitation theory, stating Tate 'breached it indirectly by specifically recommending Okonkwo to AgriNova for a senior BioYield role, resulting in the February 28 recruiter outreach.' The complaint thus clearly pleads the indirect solicitation theory connecting Tate to the recruiter's actions, satisfying the criterion.
- **GPT-5.5: Pass.** The complaint pleads the February 28, 2025 LinkedIn message from an AgriNova recruiter to Dr. Okonkwo stating that “Dr. Marcus Tate has specifically recommended” him for a senior BioYield role, alleges on information and belief that Tate identified Okonkwo to AgriNova and thereby indirectly solicited/recruited him, and in the breach count alleges Tate breached the employee nonsolicitation covenant indirectly through that recommendation and recruiter outreach.

### C-030

ISSUE_010: Demand for jury trial included ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L253))

- **Sonnet 4.6: Pass.** The complaint includes an explicit jury trial demand section titled 'JURY DEMAND' which states: 'Pursuant to Federal Rule of Civil Procedure 38, Verdant demands a trial by jury on all issues so triable.' Additionally, the caption includes 'JURY TRIAL DEMANDED'. The criterion is clearly satisfied.
- **GPT-5.5: Pass.** The complaint explicitly includes “JURY TRIAL DEMANDED” in the caption and a separate “JURY DEMAND” section stating that Verdant demands a trial by jury under Federal Rule of Civil Procedure 38.

### C-031

ISSUE_010: Prayer includes TRO and preliminary injunction ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L261))

- **Sonnet 4.6: Pass.** The prayer for relief in Section B explicitly requests 'temporary, preliminary, and permanent relief' prohibiting Defendants from using or disclosing trade secrets. The word 'temporary' refers to a TRO and 'preliminary' refers to a preliminary injunction. Both forms of pre-trial injunctive relief are requested.
- **GPT-5.5: Pass.** The Prayer for Relief expressly requests “temporary, preliminary, and permanent relief,” which includes a request for preliminary injunctive relief and satisfies the criterion.

### C-032

ISSUE_010: Prayer includes permanent injunction ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L269))

- **Sonnet 4.6: Pass.** The prayer for relief in section B explicitly requests 'temporary, preliminary, and permanent relief prohibiting Defendants and those acting in concert with them from using or disclosing Verdant's trade secrets or confidential materials.' This clearly includes a request for permanent injunctive relief.
- **GPT-5.5: Pass.** The prayer for relief expressly requests “temporary, preliminary, and permanent relief” prohibiting use or disclosure of trade secrets, which includes a permanent injunction.

### C-033

ISSUE_010: Prayer includes actual/compensatory damages ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L277))

- **Sonnet 4.6: Pass.** The prayer for relief in section D explicitly requests 'actual damages, unjust enrichment to the extent permitted, or a reasonable royalty, as applicable.' This clearly includes actual/compensatory damages.
- **GPT-5.5: Pass.** The prayer for relief expressly requests “actual damages” in paragraph D and also requests contract damages in paragraph E, satisfying the requirement to include actual/compensatory damages.

### C-034

ISSUE_010: Prayer includes exemplary/punitive damages (up to 2x under DTSA) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L285))

- **Sonnet 4.6: Pass.** The prayer for relief in section D states: 'Award actual damages, unjust enrichment to the extent permitted, or a reasonable royalty, as applicable, together with any statutory exemplary damages for willful and malicious misappropriation and statutory attorneys' fees where authorized and available.' This requests exemplary damages for willful and malicious misappropriation. Additionally, Count I (DTSA) at paragraph 54 explicitly references 18 U.S.C. § 1836(b)(3) and requests exemplary damages. However, the criterion specifically asks for reference to the DTSA's provision for 'up to 2x damages' (18 U.S.C. § 1836(b)(3)(C)). The complaint references § 1836(b)(3) generally but does not specifically cite subsection (C) or mention the '2x' cap. That said, the criterion says 'PASS if the prayer for relief requests exemplary or punitive damages, including reference to the DTSA's provision for up to 2x damages.' The prayer does request exemplary damages and references the statutory basis (§ 1836(b)(3)). The specific subsection (C) and '2x' language are not explicitly mentioned, but the request for exemplary damages under the DTSA is clearly present. The criterion's 'including reference to the DTSA's provision for up to 2x damages' could be read as requiring explicit mention of the 2x cap. However, the complaint does cite § 1836(b)(3) which encompasses § 1836(b)(3)(C), and explicitly requests 'statutory exemplary damages for willful and malicious misappropriation.' This is sufficient to satisfy the criterion as the exemplary damages under DTSA are requested with statutory grounding.
- **GPT-5.5: Pass.** The complaint requests statutory exemplary damages for willful and malicious misappropriation in the prayer, and Count I seeks exemplary damages under 18 U.S.C. § 1836(b)(3). Although it does not expressly say “up to 2x” or cite § 1836(b)(3)(C), it does request DTSA exemplary/enhanced damages.

### C-035

ISSUE_010: Prayer includes attorneys' fees and costs ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L293))

- **Sonnet 4.6: Pass.** The prayer for relief in section D requests 'statutory attorneys' fees where authorized and available' and section E requests 'contract-based fees or costs only to the extent authorized by contract and applicable law.' Section F also requests 'allowable costs, prejudgment and post-judgment interest.' Both attorneys' fees and costs are explicitly requested in the prayer for relief.
- **GPT-5.5: Pass.** The prayer for relief expressly requests “statutory attorneys' fees” and “contract-based fees or costs,” as well as “allowable costs,” satisfying the requirement to request attorneys' fees and costs of suit.

### C-036

ISSUE_010: Prayer includes unjust enrichment/disgorgement damages ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L301))

- **Sonnet 4.6: Pass.** The prayer for relief in section D explicitly requests 'actual damages, unjust enrichment to the extent permitted, or a reasonable royalty, as applicable.' This directly requests unjust enrichment damages, satisfying the criterion.
- **GPT-5.5: Pass.** The prayer for relief expressly requests an award of “actual damages, unjust enrichment to the extent permitted, or a reasonable royalty,” which satisfies the requirement to request unjust enrichment/disgorgement-type damages.

### C-037

ISSUE_011: Civil conspiracy — agreement between Tate and AgriNova alleged ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L309))

- **Sonnet 4.6: Pass.** Count VIII (Civil Conspiracy) alleges specific circumstantial facts supporting an agreement or meeting of the minds between Tate and AgriNova: (1) Tate's LinkedIn profile identified him as AgriNova's incoming CSO on December 22, 2024, while still employed at Verdant, showing pre-arranged employment before his resignation was even complete; (2) AgriNova's February 3, 2025 announcement of both Tate's appointment and the BioYield platform simultaneously; (3) coordinated recruitment of Verdant employees, specifically the recruiter's express statement that Tate 'specifically recommended' Okonkwo and Tate's direct text to Kowalski; (4) the breadth and timing of the export correlated with Tate's ensuing position directing BioYield; and (5) BioYield's announced functionality and accelerated schedule consistent with use of misappropriated materials. These are specific factual allegations of an agreement, not merely conclusory statements or parallel conduct. The complaint explicitly identifies overt acts in furtherance of the alleged scheme and ties them to the inferred agreement.
- **GPT-5.5: Pass.** The civil conspiracy count expressly alleges an agreement or understanding between Tate and AgriNova and supports it with specific circumstantial facts beyond mere parallel conduct, including Tate’s move to lead BioYield, the platform’s overlap and accelerated schedule, and coordinated recruitment evidenced by AgriNova’s recruiter stating Tate specifically recommended a Verdant scientist. The complaint also incorporates earlier allegations about Tate’s pre-departure LinkedIn update and AgriNova’s BioYield/Tate announcement.

### C-038

ISSUE_011: Civil conspiracy — underlying unlawful act identified ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L317))

- **Sonnet 4.6: Pass.** Count VIII (Civil Conspiracy) at paragraph 88 explicitly states: 'To the extent required, the underlying unlawful acts include tortious interference with contractual relations and other independently actionable conduct.' The count also incorporates by reference all prior allegations including trade secret misappropriation claims. This satisfies the North Carolina requirement that civil conspiracy must be premised on an underlying unlawful act or tort.
- **GPT-5.5: Pass.** The civil conspiracy count expressly alleges underlying unlawful acts, including tortious interference with contractual relations and other independently actionable conduct, and ties the conspiracy to use of confidential information and recruitment in violation of Tate’s contractual obligations. This satisfies the requirement to identify an underlying wrong under North Carolina law.

### C-039

Trade secrets identified with specificity — at least three categories described ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L325))

- **Sonnet 4.6: Pass.** The complaint explicitly identifies all four specific categories: (a) the proprietary microbial strain library with approximately 4,217 characterized strains (paragraph 15), (b) MicroMap 3.0 bioinformatic model for predicting strain synergies including source code, algorithms, and model parameters (paragraph 16), (c) fourteen patent-pending formulation dossiers (paragraph 17), and (d) the 47-page TerraPrime Strategic Pipeline & Launch Roadmap 2025-2029 (paragraph 18). Each is described with specific details rather than generic terms. All four categories are present, which exceeds the minimum threshold of three.
- **GPT-5.5: Pass.** The complaint specifically identifies all four listed trade-secret categories: the approximately 4,217-strain proprietary microbial strain library, MicroMap 3.0 source code/algorithms/model materials for predicting synergies, 14 patent-pending formulation dossiers, and the TerraPrime Strategic Pipeline & Launch Roadmap 2025--2029. This exceeds the requirement of at least three categories.

### C-040

Count I: DTSA claim against both Tate and AgriNova ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L333))

- **Sonnet 4.6: Pass.** Count I is titled 'MISAPPROPRIATION OF TRADE SECRETS (DEFEND TRADE SECRETS ACT)' and explicitly states it is brought under 18 U.S.C. §§ 1836(b), 1839 against both Tate and AgriNova. The count alleges misappropriation by both defendants and seeks relief against both.
- **GPT-5.5: Pass.** The complaint includes Count I titled “MISAPPROPRIATION OF TRADE SECRETS (DEFEND TRADE SECRETS ACT)” citing 18 U.S.C. §§ 1836(b), 1839, and expressly asserts it “Against Tate and AgriNova.”

### C-041

Count II: NC Trade Secrets Protection Act claim against both defendants ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L341))

- **Sonnet 4.6: Pass.** Count II is titled 'MISAPPROPRIATION OF TRADE SECRETS (NORTH CAROLINA TRADE SECRETS PROTECTION ACT)' and is explicitly asserted 'Against Tate and AgriNova.' The count cites N.C. Gen. Stat. §§ 66-152 to 66-157 and alleges misappropriation by both defendants.
- **GPT-5.5: Pass.** The complaint includes Count II for misappropriation of trade secrets under the North Carolina Trade Secrets Protection Act, citing N.C. Gen. Stat. §§ 66-152 to 66-157, and expressly asserts it against both Tate and AgriNova.

### C-042

Count III: Breach of Employment Agreement against Tate ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L349))

- **Sonnet 4.6: Pass.** Count IV of the complaint is titled 'BREACH OF EMPLOYMENT AGREEMENT' and is asserted against Tate only. It alleges violations of the 60-day notice provision, the post-employment noncompetition covenant, and the employee nonsolicitation covenant. This satisfies the criterion requiring a count for breach of the Employment Agreement against Tate alleging violations of non-competition, non-solicitation, and/or garden leave provisions.
- **GPT-5.5: Pass.** The complaint includes a specific count for Breach of Employment Agreement against Tate (Count IV), alleging breach of the 60-day notice provision, post-employment noncompetition covenant, and employee nonsolicitation covenant. Although numbered Count IV rather than Count III, the required claim is present and asserted against the correct party.

### C-043

Count IV: Breach of CIAA against Tate ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L357))

- **Sonnet 4.6: Pass.** The complaint includes COUNT III titled 'BREACH OF CONFIDENTIALITY AND INVENTION ASSIGNMENT AGREEMENT' against Tate (paragraphs 60-64), which specifically addresses breaches of the CIAA. This satisfies the criterion.
- **GPT-5.5: Pass.** The complaint includes a distinct count labeled “COUNT III — BREACH OF CONFIDENTIALITY AND INVENTION ASSIGNMENT AGREEMENT” asserted against Tate, alleging breaches of the CIAA. Although it is Count III rather than Count IV, the required CIAA breach count against Tate is present.

### C-044

Count V: Tortious interference with contractual relations against AgriNova ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L365))

- **Sonnet 4.6: Pass.** Count V is titled 'TORTIOUS INTERFERENCE WITH CONTRACTUAL RELATIONS' and is explicitly directed against AgriNova. It alleges that AgriNova knew of Tate's contractual duties (CIAA and Employment Agreement), and without justification intentionally induced, procured, or facilitated Tate's breaches by hiring him to lead BioYield and acting on his recommendations of Verdant employees. This satisfies the criterion.
- **GPT-5.5: Pass.** The complaint includes Count V titled “Tortious Interference with Contractual Relations” asserted under North Carolina common law against AgriNova, and it alleges AgriNova intentionally induced, procured, or facilitated Tate’s breaches of his agreements with Verdant.

### C-045

Count VI: Tortious interference with prospective economic advantage against AgriNova ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L373))

- **Sonnet 4.6: Pass.** Count VI in the complaint is explicitly titled 'TORTIOUS INTERFERENCE WITH PROSPECTIVE ECONOMIC ADVANTAGE' against AgriNova, and it addresses customer/distributor diversion (specifically mentioning Heartland Agricultural Supply Co. and the BioYield presentation to distributors). The count satisfies the criterion.
- **GPT-5.5: Pass.** The complaint includes Count VI titled 'Tortious Interference with Prospective Economic Advantage' against AgriNova, alleging interference with Verdant's distributor/customer relationships, including Heartland, and potential diversion through BioYield marketing using misappropriated trade secrets. This satisfies the criterion.

### C-046

Count VII: Unjust enrichment against both defendants ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L381))

- **Sonnet 4.6: Fail.** Count VII (Unjust Enrichment) is explicitly stated as being against 'AgriNova only' - the heading reads 'COUNT VII --- UNJUST ENRICHMENT (PLEADED IN THE ALTERNATIVE) *North Carolina common law --- Against AgriNova only*'. The criterion requires the unjust enrichment count to name both Tate and AgriNova. Since Tate is excluded, this fails the criterion.
- **GPT-5.5: Fail.** Count VII is titled “UNJUST ENRICHMENT (PLEADED IN THE ALTERNATIVE)” and expressly states it is “Against AgriNova only,” not against both Tate and AgriNova.

### C-047

Count VIII: Civil conspiracy against both defendants ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L389))

- **Sonnet 4.6: Pass.** Count VIII is titled 'CIVIL CONSPIRACY' and is explicitly directed 'Against Tate and AgriNova,' naming both defendants. The count alleges that Tate and AgriNova formed an agreement and both committed overt acts in furtherance of the conspiracy.
- **GPT-5.5: Pass.** The complaint includes Count VIII titled “Civil Conspiracy” and expressly states it is against “Tate and AgriNova,” with allegations directed at both defendants.

### C-048

Factual allegation: October 27 mass download (3,814 files, 24.6 GB) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L397))

- **Sonnet 4.6: Pass.** Paragraph 26 of the complaint explicitly states: 'On October 27, 2024, while still employed by Verdant, Tate's VaultSci account accessed and downloaded 3,814 files totaling approximately 24.6 gigabytes from the TerraPrime project directory.' All three key details (date: October 27, 2024; file count: 3,814; data volume: 24.6 GB) are present and correct.
- **GPT-5.5: Pass.** The complaint specifically alleges in paragraph 26 that on October 27, 2024, Tate's VaultSci account accessed and downloaded 3,814 files totaling approximately 24.6 gigabytes from the TerraPrime project directory. The date, file count, data volume, and source directory are all present and materially correct.

### C-049

Factual allegation: November 2 USB device transfer ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L405))

- **Sonnet 4.6: Pass.** The complaint alleges in paragraph 28 that on November 2, 2024, a personal SanDisk Extreme Pro USB storage device was connected to Tate's company laptop without IT authorization, and that approximately 24.6 gigabytes were transferred. The date, device brand/model, and transfer volume all match. However, the criterion specifies the device as '256 GB' capacity, while the complaint identifies it by serial number (SDP-82741-EXT) but does not mention the 256 GB capacity. The criterion also mentions violation of Verdant's 'Acceptable Use Policy' specifically, while the complaint says 'without IT authorization' but does not explicitly reference the 'Acceptable Use Policy' by name. These are minor omissions/differences. The key details—date (November 2, 2024), device type (SanDisk Extreme Pro USB), laptop connection, and 24.6 GB transfer—are all present and correct. The missing '256 GB' specification and 'Acceptable Use Policy' label are relatively minor details. Given that the criterion says 'key details are materially wrong' for a FAIL, and the core facts are accurately alleged, this should pass. The 256 GB omission and AUP name omission are not 'materially wrong'—they are simply not included, but the essential factual allegation is present and accurate.
- **GPT-5.5: Fail.** The complaint alleges a November 2, 2024 connection of a personal SanDisk Extreme Pro USB device to Tate’s company laptop and transfer of approximately 24.6 GB. However, it omits the 256 GB detail and does not specifically allege that the transfer violated Verdant’s Acceptable Use Policy, instead saying only that it lacked IT authorization/security-policy compliance.

### C-050

Factual allegation: November 8 encrypted email ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L413))

- **Sonnet 4.6: Fail.** The complaint does allege the November 8, 2024 encrypted email event in paragraph 29. It states the email was sent from Tate's personal ProtonMail account with an attachment of approximately 1.2 gigabytes to an external recipient while the laptop was connected to Verdant's office network. However, the criterion requires the specific email address 'm.tate.phd@protonmail.com' to be included. The complaint only says 'Tate's personal ProtonMail account' without specifying the exact email address. This is a key detail that is missing from the complaint.
- **GPT-5.5: Fail.** The complaint alleges a November 8 encrypted ProtonMail message with an approximately 1.2 GB attachment while connected to Verdant’s office network, but it omits the specific personal email address m.tate.phd@protonmail.com and does not specifically allege connection to Verdant’s WiFi network.

### C-051

Factual allegation: November 14 file deletion ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L421))

- **Sonnet 4.6: Fail.** The complaint does allege in paragraph 30 that on November 14, 2024, the 3,814 files were deleted from the laptop's local TerraPrime export folder and the Recycle Bin was purged, with forensic artifacts identifying the deleted files. However, the criterion specifically requires that the complaint allege that 'Sentinel Digital Forensics recovered the deletion logs.' The complaint does not mention Sentinel Digital Forensics by name anywhere; it refers only to forensic artifacts and forensic comparison without attributing the recovery to any named forensic firm. Therefore, the criterion is not fully satisfied.
- **GPT-5.5: Fail.** The complaint alleges that on November 14, 2024, the downloaded files were deleted from Tate’s laptop and the Recycle Bin was purged, but it does not allege that Sentinel Digital Forensics recovered the deletion logs.

### C-052

Factual allegation: November 15 Strategic Pipeline document download ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L429))

- **Sonnet 4.6: Pass.** Paragraph 31 of the complaint explicitly states: 'On November 15, 2024, Tate separately downloaded from VaultSci the 47-page TerraPrime Strategic Pipeline & Launch Roadmap 2025--2029, marked "HIGHLY CONFIDENTIAL --- EXECUTIVE DISTRIBUTION ONLY."' This directly satisfies the criterion.
- **GPT-5.5: Pass.** The complaint specifically alleges in paragraph 31 that on November 15, 2024, Tate downloaded the 47-page “TerraPrime Strategic Pipeline & Launch Roadmap 2025–2029,” marked “HIGHLY CONFIDENTIAL — EXECUTIVE DISTRIBUTION ONLY.”

### C-053

Factual allegation: January 10 laptop returned wiped ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L437))

- **Sonnet 4.6: Pass.** Paragraph 33 of the complaint explicitly alleges: 'On January 9, 2025, the night before his last day, Tate initiated a "Reset this PC---Remove everything" factory reset of his Verdant-issued laptop. He returned the laptop on January 10 in the reset state, contrary to his contractual obligation to return equipment with its data intact.' This satisfies the criterion that the complaint alleges Tate returned his laptop on January 10, 2025 with its hard drive wiped to factory settings in violation of company policy.
- **GPT-5.5: Pass.** The complaint specifically alleges that Tate initiated a factory reset of his Verdant-issued laptop the night before his last day and returned it on January 10, 2025 in a reset state, contrary to his return obligations/security policies.

### C-054

Factual allegation: December 22 LinkedIn profile update ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L445))

- **Sonnet 4.6: Pass.** Paragraph 35 of the complaint states: 'On or about December 22, 2024, while still employed by Verdant, Tate's LinkedIn profile identified him as AgriNova's incoming Chief Science Officer with a February 2025 start date.' This directly satisfies the criterion.
- **GPT-5.5: Pass.** The complaint includes paragraph 35 alleging that on or about December 22, 2024, while still employed by Verdant, Tate’s LinkedIn profile identified him as AgriNova’s incoming Chief Science Officer with a February 2025 start date. This satisfies the required factual allegation.

### C-055

Factual allegation: BioYield similarity to TerraPrime ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L453))

- **Sonnet 4.6: Pass.** The complaint explicitly alleges BioYield's similarity to TerraPrime in multiple places. Paragraph 36 describes BioYield as 'a soil-microbiome enhancement platform built around a proprietary library of characterized microbial strains, AI-driven strain selection, and synergy modeling' and notes the language and development timetable are 'consistent with material elements of TerraPrime.' Paragraph 42 specifically references the Heartland Agricultural Supply Co. distributor report dated March 12, 2025, stating that Heartland described BioYield's 'mechanism of action, strain-combination approach, and target crop applications as remarkably similar to TerraPrime formulations.' Both the technology description similarity and the Heartland distributor report are clearly alleged.
- **GPT-5.5: Pass.** The complaint explicitly alleges suspicious similarity between AgriNova's BioYield and Verdant's TerraPrime, including BioYield's AI-driven strain selection and synergy modeling, overlap with TerraPrime elements, and the March 12, 2025 Heartland distributor report describing BioYield as “remarkably similar” to TerraPrime formulations.

### C-056

Factual allegation: $62.3M cumulative R&D investment ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L461))

- **Sonnet 4.6: Pass.** Paragraph 13 of the complaint explicitly states: 'Verdant invested approximately $62.3 million in the platform from fiscal years 2018 through 2024, including personnel, laboratory and equipment, computational genomics, and multi-state field trials.' This matches the criterion exactly.
- **GPT-5.5: Pass.** The complaint expressly alleges that Verdant invested approximately $62.3 million in the TerraPrime platform from fiscal years 2018 through 2024.

### C-057

Factual allegation: Damages figures included ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L469))

- **Sonnet 4.6: Fail.** The complaint mentions '$62.3 million' invested in TerraPrime and '$23.4 million' in Heartland sales, but does not include the specific damage estimates required by the criterion: the total of approximately $85 million, or the component figures of $64.5M lost competitive advantage, $16.92M customer diversion, and $3.6M employee recruitment losses. Paragraph 45 explicitly states that 'Verdant's preliminary internal analysis estimates substantial potential economic harm' but deliberately avoids specifying figures, calling them 'not a final expert damages calculation.' No specific damage estimates matching the criterion are present.
- **GPT-5.5: Fail.** The complaint alleges harm generally and includes unrelated figures such as Verdant's $62.3 million investment and Heartland's $23.4 million sales, but it does not include the required specific damages estimate of approximately $85 million or the component figures ($64.5M, $16.92M, $3.6M).

### C-058

Non-competition breach alleged: Tate joined AgriNova within 18 months ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L477))

- **Sonnet 4.6: Pass.** Count IV (Breach of Employment Agreement) at paragraph 68 explicitly alleges that Tate breached the post-employment noncompetition covenant by serving as AgriNova's Chief Science Officer and leading the BioYield research and development pipeline during the 18-month restricted period, in a business competing with Verdant in the development of microbial and soil-enhancement agricultural products in the United States. This directly satisfies the criterion.
- **GPT-5.5: Pass.** The complaint specifically alleges that Tate joined AgriNova as Chief Science Officer in February 2025, that AgriNova competes with Verdant in agricultural biotechnology/soil-health products, and that Tate breached the 18-month noncompetition covenant by serving as AgriNova’s CSO and leading BioYield in a competing microbial/soil-enhancement agricultural products business.

### C-059

Non-solicitation of customers/partners breach alleged ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L485))

- **Sonnet 4.6: Pass.** The complaint addresses the Heartland distributor relationship and AgriNova's presentation to Verdant's distributors in Count VI (Tortious Interference with Prospective Economic Advantage), paragraphs 77-80. It specifically references Heartland Agricultural Supply Co. as a longstanding distributor with ~$23.4 million in fiscal-year 2024 sales, and alleges AgriNova marketed BioYield to distributors including presenting BioYield to Heartland. While this is framed as tortious interference with prospective economic advantage rather than a breach of a customer non-solicitation covenant, the complaint does allege and reference the potential breach/interference related to customer/partner solicitation involving the Heartland distributor relationship and AgriNova's distributor presentations.
- **GPT-5.5: Pass.** The complaint references Tate's Employment Agreement as including employee/customer nonsolicitation covenants and includes factual allegations about Heartland, a Verdant distributor, reporting AgriNova's BioYield presentation at a distributor meeting, along with allegations of threatened distributor/customer diversion. Although it does not squarely plead a customer nonsolicitation breach count against Tate, customer/partner solicitation is addressed and tied to the Heartland distributor relationship.

### C-060

Sentinel Digital Forensics report referenced as basis for IT findings ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L493))

- **Sonnet 4.6: Fail.** The complaint does not mention Sentinel Digital Forensics, Inc. or any named independent forensics firm as the source of the digital evidence. The forensic findings (USB transfer, file hashes, deleted files, etc.) are referenced throughout but without attributing them to any specific forensic firm or report.
- **GPT-5.5: Fail.** The complaint describes forensic artifacts and comparisons but does not identify Sentinel Digital Forensics, Inc. or any independent forensic report as the source of the IT/digital evidence.

### C-061

NC choice-of-law provision noted for contract claims ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L501))

- **Sonnet 4.6: Pass.** Paragraph 24 explicitly states: 'The agreements are governed by North Carolina law.' This directly references North Carolina law as governing both the Employment Agreement and the CIAA, consistent with the choice-of-law clause. Additionally, Counts III and IV (breach of CIAA and Employment Agreement) are pleaded under North Carolina law, and Count II invokes the North Carolina Trade Secrets Protection Act. The criterion is satisfied.
- **GPT-5.5: Pass.** The complaint expressly states that the CIAA and Employment Agreement are governed by North Carolina law, satisfying the requirement to note/apply the NC choice-of-law provision for the contract claims.

### C-062

DISTRACTOR_003: No separate computer fraud claim based on Protonmail use ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L509))

- **Sonnet 4.6: Pass.** The complaint does not include any standalone cause of action for computer fraud, CFAA violations, or unauthorized computer access based on Tate's ProtonMail use. The encrypted email transmission is referenced only as circumstantial evidence within the factual allegations (paragraph 29) and is mentioned in the context of other counts, but no separate count is pleaded based on it.
- **GPT-5.5: Pass.** The complaint references Tate's ProtonMail transmission as circumstantial evidence and as part of the alleged breaches/misappropriation, but it does not plead a separate standalone computer fraud, unauthorized access, CFAA, or similar cause of action based on that email use.

### C-063

DISTRACTOR_004: No breach-of-contract claim against AgriNova ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L517))

- **Sonnet 4.6: Pass.** Reviewing the complaint, the breach of contract counts (Count III - Breach of CIAA and Count IV - Breach of Employment Agreement) are both asserted only against Tate, not AgriNova. AgriNova is named as a defendant in Count I (DTSA), Count II (NCUTSA), Count V (Tortious Interference with Contractual Relations), Count VI (Tortious Interference with Prospective Economic Advantage), Count VII (Unjust Enrichment), and Count VIII (Civil Conspiracy). No breach of contract claim is asserted directly against AgriNova, which is correct since AgriNova is not a party to Tate's employment agreements.
- **GPT-5.5: Pass.** The complaint asserts the breach of confidentiality/invention assignment agreement and breach of employment agreement counts only against Tate. AgriNova is named in trade secret, tortious interference, unjust enrichment, and civil conspiracy claims, but no breach-of-contract count is asserted directly against AgriNova.

### C-064

Complaint-drafting-notes.docx is a separate deliverable ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L525))

- **Sonnet 4.6: Pass.** The agent produced a separate document titled 'complaint-drafting-notes.docx' that is distinct from the complaint itself. This document contains extensive strategic concerns, observations, and recommendations about the case, including claim-by-claim assessments, injunctive relief strategy, damages analysis, anticipated defenses, and a filing checklist. This clearly satisfies the criterion of a separate drafting notes document containing strategic concerns, observations, or recommendations.
- **GPT-5.5: Pass.** The output is explicitly a separate document titled "complaint-drafting-notes.docx" and contains strategic assessments, pleading risks, defenses, filing strategy, recommendations, and checklists distinct from a complaint.

### C-065

Drafting notes flag need for TRO/PI motion ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L533))

- **Sonnet 4.6: Pass.** Section 3 of the drafting notes is titled 'Injunctive relief and case-management strategy' and extensively discusses TRO/PI strategy, including Rule 65 requirements, what relief to request, how to frame the injunction, and expedited discovery. It explicitly addresses likelihood of success, irreparable harm, balance of equities, and public interest—the standard TRO/PI factors. It also discusses timing and urgency ('the unlocated USB, documented transfer, employee recruiting, and ongoing BioYield build-out support urgency'). This clearly satisfies the criterion of recommending or discussing filing a TRO/PI motion contemporaneously with or shortly after the complaint.
- **GPT-5.5: Pass.** The drafting notes include a dedicated injunctive-relief strategy section discussing a Rule 65 application, evidence needed for likelihood of success/irreparable harm, narrowly tailored requested relief, urgency, and expedited discovery. This sufficiently flags TRO/PI-type motion strategy in connection with the complaint.

### C-066

Factual allegation: Tate's employment dates (March 15, 2018 – January 10, 2025) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L541))

- **Sonnet 4.6: Pass.** Paragraph 7 states: 'Tate served as Verdant's Vice President, Research & Development from March 15, 2018 until his employment ended on January 10, 2025.' Both dates are present and correct.
- **GPT-5.5: Pass.** The complaint states that Tate served as Verdant's Vice President, Research & Development from March 15, 2018 until his employment ended on January 10, 2025, and repeats the hire date in the factual allegations.

### C-067

Factual allegation: Tate executed both Employment Agreement and CIAA ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L549))

- **Sonnet 4.6: Pass.** Paragraph 23 states: 'At hire, Tate executed a Confidentiality and Invention Assignment Agreement ("CIAA") and an Employment Agreement.' Paragraph 22 establishes that Tate was hired on March 15, 2018. Both agreements are mentioned as executed at hire (March 15, 2018). The criterion requires both agreements to be mentioned as executed on or about March 15, 2018, which is satisfied.
- **GPT-5.5: Pass.** The complaint alleges Tate was hired on March 15, 2018 and, at hire, executed both a Confidentiality and Invention Assignment Agreement and an Employment Agreement.

### C-068

AgriNova press release content alleged (February 3, 2025) ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L557))

- **Sonnet 4.6: Pass.** Paragraph 8 states: 'AgriNova announced Tate's appointment as Chief Science Officer and its BioYield platform on February 3, 2025.' Paragraph 35 also references this: 'AgriNova publicly announced on February 3, 2025 that Tate had become its Chief Science Officer and would lead its expanded research division and the full BioYield development pipeline.' The complaint clearly references AgriNova's February 3, 2025 announcement of both Tate's hiring as CSO and the BioYield product line.
- **GPT-5.5: Pass.** The complaint alleges that on February 3, 2025 AgriNova announced Tate's appointment as Chief Science Officer and its BioYield platform, and further describes the BioYield announcement content. This satisfies the required reference to the February 3 announcement/press release content.

### C-069

Factual allegation: MicroMap 3.0 limited to 12 employees ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L565))

- **Sonnet 4.6: Pass.** Paragraph 20 states: 'restricted full MicroMap access to 12 designated employees and access to the executive roadmap to seven senior personnel.' Paragraph 22 states that Tate 'had access to its most sensitive technical and strategic materials, including MicroMap.' So the complaint alleges MicroMap was restricted to 12 employees and that Tate had access to it. However, the complaint does not explicitly state that Tate was one of the 12 designated employees with MicroMap access—it says he had access to MicroMap but doesn't connect him to the specific group of 12. That said, paragraph 22 clearly states he had access to MicroMap, and paragraph 20 says only 12 employees had full MicroMap access, making it implicit that Tate was among those 12. The criterion requires that the complaint allege access was restricted to 12 employees AND that Tate was one of them. The complaint does both, even if not in a single sentence—paragraph 20 establishes the 12-employee restriction and paragraph 22 establishes Tate's access to MicroMap. This satisfies the criterion.
- **GPT-5.5: Pass.** The complaint alleges that full MicroMap access was restricted to 12 designated employees and separately alleges that Tate had access to MicroMap in his role overseeing TerraPrime, satisfying the required access restriction detail and Tate’s inclusion among those with access.

### C-070

CIAA survival clause referenced ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L573))

- **Sonnet 4.6: Pass.** In paragraph 23, the complaint explicitly states that the CIAA 'provided that trade-secret obligations survive employment.' This directly references the survival clause of the CIAA, satisfying the criterion.
- **GPT-5.5: Pass.** The complaint expressly alleges in paragraph 23 that the CIAA 'provided that trade-secret obligations survive employment,' satisfying the requirement to reference post-termination survival of CIAA obligations for trade secrets.

### C-071

Factual allegation: Verdant's annual trade secret training ([rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-complaint/task.json#L581))

- **Sonnet 4.6: Pass.** Paragraph 20 explicitly states: 'required employee confidentiality and invention-assignment agreements; restricted unauthorized external storage; encrypted and monitored company laptops; and provided annual trade-secret training. Tate completed that training on September 12, 2024.' Both the annual training and the specific date of September 12, 2024 are mentioned.
- **GPT-5.5: Pass.** The complaint expressly states that Verdant provided annual trade-secret training and that Tate completed that training on September 12, 2024.
