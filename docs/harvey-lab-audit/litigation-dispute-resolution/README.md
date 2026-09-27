# Harvey LAB litigation and dispute resolution audit

> [!WARNING]
> **This audit is AI generated and has not been verified.** It reflects some human steering and guidance, but should not be treated as verified legal analysis, an authoritative assessment of Harvey LAB, or an accepted correction to any benchmark score. The reports may contain factual, legal, citation, arithmetic, and grading errors. Their labels “confirmed,” “definite,” and “verified” describe AI reviewer judgments; they do not establish human verification. **Portions of the findings that have been verified will be described separately on the public-facing LegalForecastBench site.** Inclusion here does not confer that status.

This audit is included for reference. GitHub's rendered Markdown provides the intended reading interface: use the task table below for individual reports, or the detailed index for criterion-level navigation.

## Contents

- [Purpose and meaning of drift](#purpose-and-meaning-of-drift)
- [Models and human involvement](#models-and-human-involvement)
- [Scope, sources, and limitations](#scope-sources-and-limitations)
- [How to read the findings](#how-to-read-the-findings)
- [Task reports](#task-reports)
- [Initial reviews of model outputs and grades](#initial-reviews-of-model-outputs-and-grades)

## Purpose and meaning of drift

The purpose was to assess how much “drift” a rubric-based approach using fictitious litigation data, such as Harvey LAB, may introduce compared with a framework based on real litigation data, such as LegalForecastBench. Here, “drift” means a possible gap between the supplied record, the requested legal work, the rubric's expected answer, and the judge's application of that rubric. It is not a measure of model changes over time or the contamination-related drift metric used elsewhere in LegalForecastBench.

The audit looks for unsupported facts, inconsistent documents, potentially incorrect legal propositions, requirements not communicated in the task prompt, and grading that may reward or penalize answers for the wrong reasons. It also distinguishes those concerns from real model mistakes and ordinary disagreement about legal judgment.

This reference collection does **not** quantify a comparative drift rate or establish that fictitious data causes more error than real litigation data. The two frameworks measure different tasks, and no matched causal comparison was performed here. Real court records, outcome labels, selection decisions, and forecasting evaluations can also contain ambiguity or error. The reports are leads for further verification, not evidence that LegalForecastBench is free from those risks. See [LegalForecastBench's methods](../../METHODS.md).

## Models and human involvement

| Role | Model and setting |
| --- | --- |
| Six workers conducting the initial rubric/document audit | **GPT-6 Sol** (`gpt-6-sol`), **high** reasoning |
| Follow-up reviews of selected outputs and native grades | **GPT-6 Sol**, **high** reasoning |
| Coordination, consolidation, selected spot checks, and reference packaging | **GPT-6 in Codex**; the coordinating session's specific variant and effort were not recorded in the audit provenance |
| Tested solver condition | **GPT-6 Luna** (`gpt-6-luna`), **xhigh** reasoning |
| Tested solver condition | **Claude Opus 5.5** (`claude-opus-5-5`), **low** effort, with five-minute prompt caching |
| Native LAB judges | **Claude Sonnet 4.6** (`claude-sonnet-4-6`) and **GPT-5.5** (`gpt-5.5`) |

A human set the research question, raised initial concerns about selected criteria, selected the model conditions, and provided steering and guidance. AI workers generated the report text and findings. Their initial task audits were performed without seeing solver outputs, but the project was not fully blinded to the human's initial concerns. Later output/grade reviews are explicitly separate. Agreement among AI reviewers is not independent human or expert verification.

The audit reports were produced on September 26, 2026 (EDT; some stored timestamps fall on September 27 UTC). This directory is a reference snapshot, not a live results dashboard. The full solver sweeps and grading were still underway when this collection was prepared; the selected follow-up reports do not cover every eventual result.

## Scope, sources, and limitations

The initial pass covers **52 tasks, 2,858 criteria, and 520 supplied-file occurrences** in Harvey LAB's litigation-dispute-resolution folder. File occurrences count attachments across tasks, not necessarily unique documents. Workers read the criteria and inspected relevant source passages. That does not imply exhaustive review of every source paragraph, spreadsheet formula, visual layout, privilege claim, or cited legal authority. Individual reports state their coverage and limitations.

The upstream snapshot is [Harvey LAB commit `1dd81403b2fbb60596f7aea3fcecafad7bf73143`](https://github.com/harveyai/harvey-labs/tree/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution). Each task page links to its original rubric and documents at that revision. This is an independent project reference; Harvey AI has not verified or endorsed these findings.

The public copy retains report text, structured findings where available, and source pointers. Navigation, warning banners, and Markdown renderings of JSON reports have been added; machine-local paths have been removed or made portable. Raw document extractions, solver transcripts, native grade files, credentials, and working scripts are not copied into this directory. Quoted passages and native-grade summaries in the follow-up reports remain AI-produced representations of those artifacts. Extraction line numbers and XML paragraph identifiers are local analysis locators, not stable page numbers in the original files; use the named source and quoted passage when checking a finding.

The original task inputs, audit artifacts, solver outputs, and native grades were preserved separately. No native scores were overwritten with audit recommendations. Upstream source material is attributed to Harvey AI; its [MIT license notice](UPSTREAM-LICENSE.txt) is retained for quoted source material.

## How to read the findings

Start with a task report and examine its cited sources before relying on a conclusion. Separate a defect in supplied documents from a defect in a rubric, and both from a judge's misapplication or a model's own mistake. A fictional court order can contain incorrect law while still giving the model an instruction it reasonably follows; contradictions in adversarial filings are not automatically dataset defects.

The [detailed audit index](index.md) and [structured index](index.json) preserve the workers' classifications and counts. **Those counts are not a verified error rate, an estimate of score inflation or deflation, or corrected benchmark results.** One finding may concern several criteria, several findings may concern the same criterion, and an “arguable” concern may ultimately be rejected. “No defect established” is not certification that a criterion is correct. The legal analysis itself may be wrong or incomplete.

## Task reports

| Task | Criteria |
| --- | ---: |
| [Analyze Counterparty Motion to Dismiss — Issue Identification Memorandum](batch-1/analyze-counterparty-motion-to-dismiss/README.md) | 34 |
| [Analyze Counterparty Requests for Production for Objectionable and Overbroad Discovery Demands — Issue Identification Memorandum](batch-2/analyze-counterparty-requests-for-production-for-objectionable-and-overbroad-discovery-demands/README.md) | 47 |
| [Analyze Counterparty's Motion for Summary Judgment — Issue Identification Memorandum](batch-3/analyze-counterpartys-motion-for-summary-judgment/README.md) | 32 |
| [Assess Litigation Hold Scope for Custodian Identification — Custodian Recommendation Memorandum](batch-4/assess-litigation-hold-scope-for-custodian-identification/README.md) | 50 |
| [Assess Reasonableness of Staffing Levels on Litigation Invoice](batch-5/assess-reasonableness-of-staffing-levels-on-litigation-invoice/README.md) | 49 |
| [Assess Settlement Value Range for Product Liability Crush Injury Case — Litigation Settlement Memorandum](batch-6/assess-settlement-value-range/README.md) | 52 |
| [Build Litigation Case Timeline — Chronological Event Summary for Breach of Contract and Fraud Defense](batch-1/build-litigation-case-timeline/README.md) | 64 |
| [Categorize Document Production Set by Relevance and Privilege — Privilege Log and Relevance Classification Report](batch-2/categorize-document-production-set-by-relevance-and-privilege/README.md) | 67 |
| [Compare Document Production Against Discovery Requests — Discovery Gap Analysis Memorandum](batch-3/compare-document-production-against-discovery-requests/README.md) | 46 |
| [Draft Answer with Affirmative Defenses to Breach of Contract Complaint](batch-4/draft-answer-to-breach-of-contract-complaint/README.md) | 40 |
| [Draft Case Assessment Memorandum — Litigation Risk Analysis for Distribution Agreement Dispute](batch-5/draft-case-assessment-memorandum/README.md) | 55 |
| [Draft Federal Complaint for Trade Secret Misappropriation and Breach of Employment Agreement](batch-6/draft-complaint/README.md) | 71 |
| [Draft Conflict Check Memorandum for Litigation Engagement Clearance](batch-1/draft-conflict-check-memorandum/README.md) | 56 |
| [Draft Counterclaim Against Plaintiff for Breach of Joint Development Agreement](batch-2/draft-counterclaim-against-plaintiff-for-breach-of-joint-development-agreement/README.md) | 73 |
| [Draft Case Assessment Memorandum for Defective Industrial Equipment Product Liability Claim](batch-3/draft-defective-industrial-equipment-product-liability/README.md) | 79 |
| [Draft Deposition Outline for Supervisor in Employment Discrimination and Retaliation Case](batch-4/draft-deposition-outline/README.md) | 59 |
| [Draft Discovery Plan Memorandum for Breach of Contract and Fraud Defense](batch-5/draft-discovery-plan-memorandum/README.md) | 65 |
| [Draft Federal Complaint for Breach of Contract and Fiduciary Duty — Placement Agent Dispute](batch-6/draft-federal-complaint-drafting/README.md) | 50 |
| [Draft First Set of Interrogatories to Defendant Veridian Health Systems in Trade Secret Misappropriation Case](batch-1/draft-interrogatories/README.md) | 50 |
| [Draft Proposed Jury Instructions for Title VII Retaliation, Ohio Whistleblower, and Implied Contract Claims](batch-2/draft-jury-instructions/README.md) | 57 |
| [Draft Discovery Responses and Objections to RFAs and RFPs in Breach of Supply Agreement Litigation](batch-3/draft-litigation-discovery-responses/README.md) | 61 |
| [Draft Litigation Hold Notice for New Product Liability Class Action (Medical Device)](batch-4/draft-litigation-hold-notice-for-new-product-liability-matter/README.md) | 61 |
| [Draft Memorandum of Law in Support of Motion for Preliminary Injunction — Trade Secret Misappropriation and Non-Compete Enforcement](batch-5/draft-motion-for-preliminary-injunction/README.md) | 53 |
| [Draft Motion for Summary Judgment — Breach of Contract, Fraudulent Inducement, and Negligent Misrepresentation in Failed ERP Implementation](batch-6/draft-motion-for-summary-judgment/README.md) | 69 |
| [Draft Motion in Limine to Exclude Expert Testimony and Prejudicial Evidence in Commercial Breach of Contract Case](batch-1/draft-motion-in-limine-to-exclude-expert-testimony-and-prejudicial-evidence/README.md) | 49 |
| [Draft Federal Rule 37(a) Motion to Compel Discovery Responses in Commercial Litigation](batch-2/draft-motion-to-compel-discovery-responses/README.md) | 59 |
| [Draft Rule 12(b)(6) Motion to Dismiss Brief — Commercial Software Licensing Dispute](batch-3/draft-motion-to-dismiss-brief/README.md) | 89 |
| [Draft Opposition to Motion for Summary Judgment in BSA/AML Whistleblower Retaliation Case](batch-4/draft-opposition-to-motion-for-summary-judgment/README.md) | 59 |
| [Draft Opposition to Motion to Dismiss — Memorandum of Law in Opposition (Restrictive Covenant, Trade Secrets, Tortious Interference)](batch-5/draft-opposition-to-motion-to-dismiss/README.md) | 63 |
| [Draft Plaintiff's Portion of Joint Pretrial Statement in Breach of Contract and Fraudulent Inducement Action](batch-6/draft-pretrial-statement/README.md) | 46 |
| [Draft Plaintiff's First Set of Requests for Production of Documents in Breach of Contract and Trade Secret Misappropriation Action](batch-1/draft-requests-for-production/README.md) | 50 |
| [Draft Verified Responses and Objections to Plaintiff's First Set of Interrogatories in Commercial Breach of Contract and Fraud Action](batch-2/draft-responses-to-interrogatories/README.md) | 48 |
| [Draft Responses and Objections to Requests for Production in Breach of Contract and Fraud Litigation](batch-3/draft-responses-to-requests-for-production/README.md) | 45 |
| [Draft Direct and Cross-Examination Outlines for Key Fact Witness in Breach of Contract and Fraud Action](batch-4/draft-witness-examination-outline/README.md) | 62 |
| [Extract Key Admissions from Deposition Transcript — Admission Summary Memorandum](batch-5/extract-key-admissions-from-deposition-transcript/README.md) | 46 |
| [Extract Key Obligations from Litigation Hold and Document Preservation Notice — Obligation Summary Memorandum](batch-6/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/README.md) | 52 |
| [Extract Key Terms from Counterparty Complaint — Litigation Summary Memorandum](batch-1/extract-key-terms-from-counterparty-complaint/README.md) | 75 |
| [Extract Privileged Communications from Production Set — Privilege Log and Clawback Memorandum](batch-2/extract-privileged-communications-from-production-set/README.md) | 66 |
| [Extract Scope Terms from Matter Plan — Structured Extraction Report](batch-3/extract-scope-terms-from-matter-plan/README.md) | 76 |
| [Identify Excessive or Duplicative Research Charges in Litigation Invoice](batch-4/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/README.md) | 46 |
| [Government Subpoena Issue Identification — Memorandum to Partner on Grand Jury Subpoena for Insider Trading Investigation](batch-5/identify-government-subpoena-issues/README.md) | 52 |
| [Identify Issues in Counterparty Complaint — Issue Identification Memorandum](batch-6/identify-issues-in-counterparty-complaint/README.md) | 25 |
| [Identify Issues in Counterparty Interrogatories — Objection and Strategy Memorandum](batch-1/identify-issues-in-counterparty-interrogatories/README.md) | 47 |
| [Identify Issues in Litigation Matter Budget Proposal](batch-2/identify-issues-in-matter-budget-proposal/README.md) | 39 |
| [Research Corporate Veil Piercing Standards Across Target Jurisdictions — In-House Legal Memorandum](batch-3/research-corporate-veil-piercing-standards-across-target-jurisdictions/README.md) | 65 |
| [Research UCC Warranty Disclaimer Requirements for New Product Launch](batch-4/research-ucc-warranty-disclaimer-requirements-for-new-product-launch/README.md) | 45 |
| [Review Counterparty's Proposed Jury Instructions — Issue Memorandum for Trade Secrets Trial](batch-5/review-counterpartys-proposed-jury-instructions/README.md) | 33 |
| [Review Document Production Set for Attorney-Client Privilege Designations — Privilege Log and Recommendation Memo](batch-6/review-document-production-set-for-attorney/README.md) | 48 |
| [Review Litigation Invoice Against Outside Counsel Billing Guidelines — Compliance Deviation Report](batch-1/review-litigation-invoice-against-outside-counsel-billing-guidelines/README.md) | 49 |
| [Review Outside Counsel Engagement Letter for Problematic Terms — Issue Identification Memorandum](batch-2/review-outside-counsel-engagement-letter-for-problematic-terms/README.md) | 45 |
| [Privilege Log Review and Clawback Analysis — Deficiency Memo and Clawback Candidate List](batch-3/review-privilege-log-clawback-review/README.md) | 82 |
| [Verify Disbursement Charges Against Outside Counsel Billing Guidelines — Compliance Report](batch-4/verify-disbursement-charges-against-billing-guidelines/README.md) | 57 |

## Initial reviews of model outputs and grades

These selected follow-up reports were prepared after the blind rubric pass. They discuss actual model errors as well as potential grading errors. Any proposed reversal or adjusted score remains an unverified AI recommendation.

- [Motion-to-dismiss output/grade audit: summary](grade-motion/summary.md), [detailed findings](grade-motion/findings.md), and [criterion coverage](grade-motion/coverage.md).
- [Luna litigation-hold output/grade audit](batch-4/grade-audit.md).
- [Initial coordinating-assistant observations](initial-grade-observations.md).

Batch summaries: [1](batch-1/summary.md), [2](batch-2/summary.md), [3](batch-3/summary.md), [4](batch-4/summary.md), [5](batch-5/summary.md), [6](batch-6/summary.md).
