# GPT-6 Sol and Claude Opus 5.5: where the two audits agree and differ

> [!WARNING]
> **AI-generated, unverified analysis — for reference only.** Labels such as “problematic” or “verified” are AI reviewer judgments, not human sign-off or accepted score corrections. Agreement between two AI models is not independent verification. See the [audit overview](README.md).

Each row is one rubric criterion that at least one model flagged. A model's status for a criterion is the strongest status among its findings that cite it. GPT-6 Sol's statuses come from its [structured index](gpt-6-sol/index.json) (“confirmed” is shown as problematic); its `unverified` and `qualified_check` entries are not counted as flags. Claude Opus 5.5's statuses are its final position after a blind pass and a reconciliation pass that reviewed every GPT-6 Sol finding. Because Opus saw Sol's findings before finalizing, agreement is not independent confirmation; the blind-pass column on each task page shows what Opus found before reading Sol. Agreement on a criterion does not always mean agreement on the reason; each row lists both models' findings, and the last section lists criteria flagged on different grounds.

## Totals

| Agreement | Criteria | Tasks |
|---|---:|---:|
| [Both models: problematic](comparison/both-problematic.md) | 83 | 43 |
| [Both models: arguable](comparison/both-arguable.md) | 135 | 44 |
| [Both flagged, different strength (one problematic, one arguable)](comparison/split.md) | 127 | 45 |
| [Flagged by GPT-6 Sol only](comparison/sol-only.md) | 271 | 48 |
| [Flagged by Claude Opus 5.5 only](comparison/opus-only.md) | 219 | 48 |

Denominator: 2858 criteria across 52 tasks. Counts are criterion-level flags, not a verified error rate or a score correction. Claude Opus 5.5 flagged 650 criteria in its blind pass; after reading GPT-6 Sol it added 41 and withdrew 127.

## Model-run outcomes

How often each group of criteria was failed by LAB's native judges in the two [published model runs](model-runs/README.md) (GPT-6 Luna xhigh and Claude Opus 5.5 low, each graded by Sonnet 4.6 and GPT-5.5: 4 verdicts per criterion). A failure is not evidence that a criterion is defective, nor a pass that it is sound; these counts show where flagged criteria actually decided grades.

| Group | Criteria | Failed in any verdict | Failed in all verdicts |
|---|---:|---:|---:|
| [Both models: problematic](comparison/both-problematic.md) | 83 | 45 | 25 |
| [Both models: arguable](comparison/both-arguable.md) | 135 | 77 | 18 |
| [Both flagged, different strength (one problematic, one arguable)](comparison/split.md) | 127 | 52 | 16 |
| [Flagged by GPT-6 Sol only](comparison/sol-only.md) | 271 | 74 | 6 |
| [Flagged by Claude Opus 5.5 only](comparison/opus-only.md) | 219 | 86 | 32 |
| Not flagged by either model | 2023 | 339 | 50 |

## By task

| Task | Criteria | Both problematic | Both arguable | Split | Sol only | Opus only |
|---|---:|---:|---:|---:|---:|---:|
| [Analyze Counterparty Motion to Dismiss — Issue Identification Memorandum](tasks/analyze-counterparty-motion-to-dismiss/README.md) | 34 | 1 | 4 | 6 | 4 | 1 |
| [Analyze Counterparty Requests for Production for Objectionable and Overbroad Discovery Demands — Issue Identification Memorandum](tasks/analyze-counterparty-requests-for-production-for-objectionable-and-overbroad-discovery-demands/README.md) | 47 | 0 | 3 | 2 | 4 | 4 |
| [Analyze Counterparty's Motion for Summary Judgment — Issue Identification Memorandum](tasks/analyze-counterpartys-motion-for-summary-judgment/README.md) | 32 | 0 | 0 | 2 | 3 | 1 |
| [Assess Litigation Hold Scope for Custodian Identification — Custodian Recommendation Memorandum](tasks/assess-litigation-hold-scope-for-custodian-identification/README.md) | 50 | 0 | 1 | 1 | 0 | 1 |
| [Assess Reasonableness of Staffing Levels on Litigation Invoice](tasks/assess-reasonableness-of-staffing-levels-on-litigation-invoice/README.md) | 49 | 3 | 4 | 7 | 4 | 0 |
| [Assess Settlement Value Range for Product Liability Crush Injury Case — Litigation Settlement Memorandum](tasks/assess-settlement-value-range/README.md) | 52 | 0 | 2 | 3 | 0 | 8 |
| [Build Litigation Case Timeline — Chronological Event Summary for Breach of Contract and Fraud Defense](tasks/build-litigation-case-timeline/README.md) | 64 | 4 | 0 | 5 | 10 | 1 |
| [Categorize Document Production Set by Relevance and Privilege — Privilege Log and Relevance Classification Report](tasks/categorize-document-production-set-by-relevance-and-privilege/README.md) | 67 | 3 | 5 | 2 | 6 | 17 |
| [Compare Document Production Against Discovery Requests — Discovery Gap Analysis Memorandum](tasks/compare-document-production-against-discovery-requests/README.md) | 46 | 2 | 2 | 4 | 2 | 1 |
| [Draft Answer with Affirmative Defenses to Breach of Contract Complaint](tasks/draft-answer-to-breach-of-contract-complaint/README.md) | 40 | 2 | 3 | 1 | 2 | 5 |
| [Draft Case Assessment Memorandum — Litigation Risk Analysis for Distribution Agreement Dispute](tasks/draft-case-assessment-memorandum/README.md) | 55 | 1 | 7 | 0 | 5 | 4 |
| [Draft Federal Complaint for Trade Secret Misappropriation and Breach of Employment Agreement](tasks/draft-complaint/README.md) | 71 | 1 | 2 | 1 | 0 | 6 |
| [Draft Conflict Check Memorandum for Litigation Engagement Clearance](tasks/draft-conflict-check-memorandum/README.md) | 56 | 2 | 2 | 3 | 4 | 4 |
| [Draft Counterclaim Against Plaintiff for Breach of Joint Development Agreement](tasks/draft-counterclaim-against-plaintiff-for-breach-of-joint-development-agreement/README.md) | 73 | 1 | 1 | 3 | 15 | 3 |
| [Draft Case Assessment Memorandum for Defective Industrial Equipment Product Liability Claim](tasks/draft-defective-industrial-equipment-product-liability/README.md) | 79 | 3 | 4 | 0 | 8 | 7 |
| [Draft Deposition Outline for Supervisor in Employment Discrimination and Retaliation Case](tasks/draft-deposition-outline/README.md) | 59 | 1 | 4 | 2 | 1 | 3 |
| [Draft Discovery Plan Memorandum for Breach of Contract and Fraud Defense](tasks/draft-discovery-plan-memorandum/README.md) | 65 | 1 | 5 | 0 | 2 | 6 |
| [Draft Federal Complaint for Breach of Contract and Fiduciary Duty — Placement Agent Dispute](tasks/draft-federal-complaint-drafting/README.md) | 50 | 2 | 0 | 1 | 2 | 9 |
| [Draft First Set of Interrogatories to Defendant Veridian Health Systems in Trade Secret Misappropriation Case](tasks/draft-interrogatories/README.md) | 50 | 1 | 2 | 0 | 7 | 7 |
| [Draft Proposed Jury Instructions for Title VII Retaliation, Ohio Whistleblower, and Implied Contract Claims](tasks/draft-jury-instructions/README.md) | 57 | 2 | 3 | 5 | 2 | 3 |
| [Draft Discovery Responses and Objections to RFAs and RFPs in Breach of Supply Agreement Litigation](tasks/draft-litigation-discovery-responses/README.md) | 61 | 1 | 3 | 6 | 3 | 1 |
| [Draft Litigation Hold Notice for New Product Liability Class Action (Medical Device)](tasks/draft-litigation-hold-notice-for-new-product-liability-matter/README.md) | 61 | 0 | 1 | 1 | 1 | 10 |
| [Draft Memorandum of Law in Support of Motion for Preliminary Injunction — Trade Secret Misappropriation and Non-Compete Enforcement](tasks/draft-motion-for-preliminary-injunction/README.md) | 53 | 2 | 1 | 1 | 2 | 5 |
| [Draft Motion for Summary Judgment — Breach of Contract, Fraudulent Inducement, and Negligent Misrepresentation in Failed ERP Implementation](tasks/draft-motion-for-summary-judgment/README.md) | 69 | 2 | 2 | 1 | 6 | 13 |
| [Draft Motion in Limine to Exclude Expert Testimony and Prejudicial Evidence in Commercial Breach of Contract Case](tasks/draft-motion-in-limine-to-exclude-expert-testimony-and-prejudicial-evidence/README.md) | 49 | 0 | 3 | 0 | 6 | 2 |
| [Draft Federal Rule 37(a) Motion to Compel Discovery Responses in Commercial Litigation](tasks/draft-motion-to-compel-discovery-responses/README.md) | 59 | 0 | 0 | 3 | 4 | 2 |
| [Draft Rule 12(b)(6) Motion to Dismiss Brief — Commercial Software Licensing Dispute](tasks/draft-motion-to-dismiss-brief/README.md) | 89 | 5 | 9 | 4 | 13 | 6 |
| [Draft Opposition to Motion for Summary Judgment in BSA/AML Whistleblower Retaliation Case](tasks/draft-opposition-to-motion-for-summary-judgment/README.md) | 59 | 1 | 3 | 1 | 6 | 2 |
| [Draft Opposition to Motion to Dismiss — Memorandum of Law in Opposition (Restrictive Covenant, Trade Secrets, Tortious Interference)](tasks/draft-opposition-to-motion-to-dismiss/README.md) | 63 | 0 | 2 | 1 | 10 | 1 |
| [Draft Plaintiff's Portion of Joint Pretrial Statement in Breach of Contract and Fraudulent Inducement Action](tasks/draft-pretrial-statement/README.md) | 46 | 1 | 2 | 1 | 2 | 5 |
| [Draft Plaintiff's First Set of Requests for Production of Documents in Breach of Contract and Trade Secret Misappropriation Action](tasks/draft-requests-for-production/README.md) | 50 | 1 | 0 | 2 | 2 | 4 |
| [Draft Verified Responses and Objections to Plaintiff's First Set of Interrogatories in Commercial Breach of Contract and Fraud Action](tasks/draft-responses-to-interrogatories/README.md) | 48 | 2 | 0 | 2 | 12 | 4 |
| [Draft Responses and Objections to Requests for Production in Breach of Contract and Fraud Litigation](tasks/draft-responses-to-requests-for-production/README.md) | 45 | 1 | 3 | 1 | 3 | 5 |
| [Draft Direct and Cross-Examination Outlines for Key Fact Witness in Breach of Contract and Fraud Action](tasks/draft-witness-examination-outline/README.md) | 62 | 1 | 0 | 3 | 6 | 8 |
| [Extract Key Admissions from Deposition Transcript — Admission Summary Memorandum](tasks/extract-key-admissions-from-deposition-transcript/README.md) | 46 | 0 | 1 | 3 | 2 | 7 |
| [Extract Key Obligations from Litigation Hold and Document Preservation Notice — Obligation Summary Memorandum](tasks/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/README.md) | 52 | 3 | 1 | 3 | 1 | 10 |
| [Extract Key Terms from Counterparty Complaint — Litigation Summary Memorandum](tasks/extract-key-terms-from-counterparty-complaint/README.md) | 75 | 1 | 2 | 4 | 1 | 5 |
| [Extract Privileged Communications from Production Set — Privilege Log and Clawback Memorandum](tasks/extract-privileged-communications-from-production-set/README.md) | 66 | 3 | 11 | 4 | 12 | 4 |
| [Extract Scope Terms from Matter Plan — Structured Extraction Report](tasks/extract-scope-terms-from-matter-plan/README.md) | 76 | 1 | 0 | 0 | 4 | 4 |
| [Identify Excessive or Duplicative Research Charges in Litigation Invoice](tasks/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/README.md) | 46 | 4 | 5 | 3 | 9 | 1 |
| [Government Subpoena Issue Identification — Memorandum to Partner on Grand Jury Subpoena for Insider Trading Investigation](tasks/identify-government-subpoena-issues/README.md) | 52 | 1 | 5 | 0 | 11 | 4 |
| [Identify Issues in Counterparty Complaint — Issue Identification Memorandum](tasks/identify-issues-in-counterparty-complaint/README.md) | 25 | 2 | 2 | 2 | 3 | 0 |
| [Identify Issues in Counterparty Interrogatories — Objection and Strategy Memorandum](tasks/identify-issues-in-counterparty-interrogatories/README.md) | 47 | 1 | 2 | 2 | 12 | 2 |
| [Identify Issues in Litigation Matter Budget Proposal](tasks/identify-issues-in-matter-budget-proposal/README.md) | 39 | 1 | 1 | 7 | 3 | 2 |
| [Research Corporate Veil Piercing Standards Across Target Jurisdictions — In-House Legal Memorandum](tasks/research-corporate-veil-piercing-standards-across-target-jurisdictions/README.md) | 65 | 2 | 4 | 4 | 6 | 0 |
| [Research UCC Warranty Disclaimer Requirements for New Product Launch](tasks/research-ucc-warranty-disclaimer-requirements-for-new-product-launch/README.md) | 45 | 1 | 1 | 1 | 2 | 3 |
| [Review Counterparty's Proposed Jury Instructions — Issue Memorandum for Trade Secrets Trial](tasks/review-counterpartys-proposed-jury-instructions/README.md) | 33 | 2 | 2 | 5 | 2 | 1 |
| [Review Document Production Set for Attorney-Client Privilege Designations — Privilege Log and Recommendation Memo](tasks/review-document-production-set-for-attorney/README.md) | 48 | 1 | 1 | 2 | 10 | 9 |
| [Review Litigation Invoice Against Outside Counsel Billing Guidelines — Compliance Deviation Report](tasks/review-litigation-invoice-against-outside-counsel-billing-guidelines/README.md) | 49 | 5 | 1 | 3 | 9 | 5 |
| [Review Outside Counsel Engagement Letter for Problematic Terms — Issue Identification Memorandum](tasks/review-outside-counsel-engagement-letter-for-problematic-terms/README.md) | 45 | 2 | 2 | 2 | 6 | 1 |
| [Privilege Log Review and Clawback Analysis — Deficiency Memo and Clawback Candidate List](tasks/review-privilege-log-clawback-review/README.md) | 82 | 2 | 9 | 6 | 21 | 0 |
| [Verify Disbursement Charges Against Outside Counsel Billing Guidelines — Compliance Report](tasks/verify-disbursement-charges-against-billing-guidelines/README.md) | 57 | 4 | 2 | 1 | 0 | 2 |

## Same criterion, different grounds

These criteria count as flagged by both models, but Claude Opus 5.5 rejected GPT-6 Sol's reason and flags them for a reason of its own.

- [draft-deposition-outline](tasks/draft-deposition-outline/README.md) C-038: Opus rejects GPT-6 Sol's arguable/0 as not_a_defect, but flags the criterion as arguable on a different ground
- [draft-deposition-outline](tasks/draft-deposition-outline/README.md) C-006: Opus rejects GPT-6 Sol's arguable/1 as not_a_defect, but flags the criterion as arguable on a different ground
- [draft-deposition-outline](tasks/draft-deposition-outline/README.md) C-050: Opus rejects GPT-6 Sol's arguable/1 as not_a_defect, but flags the criterion as arguable on a different ground
- [draft-responses-to-requests-for-production](tasks/draft-responses-to-requests-for-production/README.md) C-014: Opus rejects GPT-6 Sol's F3 as not_a_defect, but flags the criterion as arguable on a different ground
- [identify-issues-in-matter-budget-proposal](tasks/identify-issues-in-matter-budget-proposal/README.md) C-012: Opus rejects GPT-6 Sol's Arguable / minor source issues: item 1 as not_a_defect, but flags the criterion as arguable on a different ground
- [identify-issues-in-matter-budget-proposal](tasks/identify-issues-in-matter-budget-proposal/README.md) C-035: Opus rejects GPT-6 Sol's Arguable / minor source issues: item 1 as not_a_defect, but flags the criterion as arguable on a different ground
