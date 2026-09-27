# Harvey LAB litigation and dispute resolution audit: GPT-6 Sol and Claude Opus 5.5

> [!WARNING]
> **These audits are AI generated and have not been verified.** It reflects some human steering and guidance, but should not be treated as verified legal analysis, an authoritative assessment of Harvey LAB, or an accepted correction to any benchmark score. The reports may contain factual, legal, citation, arithmetic, and grading errors. Their labels “confirmed,” “definite,” and “verified” describe AI reviewer judgments; they do not establish human verification. **Portions of the findings that have been verified will be described separately on the public-facing LegalForecastBench site.** Inclusion here does not confer that status.

Two AI models audited the same 52 tasks. **GPT-6 Sol** did the first audit. **Claude Opus 5.5** then did its own audit: a blind pass that did not see GPT-6 Sol's work, followed by a reconciliation pass that ruled on every GPT-6 Sol finding. See [Models and human involvement](#models-and-human-involvement).

**Start here: [where the two audits agree and differ](comparison.md)** ([JSON](comparison.json)). It sorts every flagged criterion into five groups: both models call it problematic; both call it arguable; both flag it at different strengths; GPT-6 Sol only; Claude Opus 5.5 only.

In brief, across 2,858 criteria: GPT-6 Sol flagged 616 and Claude Opus 5.5 flagged 564. Both call 83 problematic and 135 arguable; 127 are flagged by both at different strengths; 271 are flagged only by GPT-6 Sol and 219 only by Claude Opus 5.5. Claude Opus 5.5 flagged 650 criteria in its blind pass. After reading GPT-6 Sol's work it added 41 and withdrew 127, so the final Opus position is not independent of GPT-6 Sol's. Six criteria count as flagged by both even though Opus rejected GPT-6 Sol's reason and flags them on its own ground. These are AI judgments, not a verified error rate.

### Layout

| Path | Contents |
| --- | --- |
| [`comparison.md`](comparison.md), [`comparison.json`](comparison.json) | Cross-task agreement totals and per-task counts, generated from the two models' structured results |
| [`comparison/`](comparison/) | One page per agreement group, listing each criterion with both models' findings (and, for GPT-6 Sol-only rows, Claude Opus 5.5's reason for rejecting them) |
| `tasks/<task>/README.md` | Task landing page: pinned sources and a criterion-by-criterion comparison table |
| `tasks/<task>/gpt-6-sol-audit.md` (`.json`) | GPT-6 Sol's report. Text unchanged from the original snapshot except for link targets; where its prose mentions `batch-N/` paths, those refer to the earlier layout |
| `tasks/<task>/claude-opus-5-5-audit.md` (`.json`) | Claude Opus 5.5's report, with its blind-pass findings and its verdict on each GPT-6 Sol finding |
| [`gpt-6-sol/`](gpt-6-sol/) | GPT-6 Sol's indexes, batch summaries, and follow-up output/grade reviews |

The Claude Opus 5.5 reports and the comparison are rendered by [`scripts/build_harvey_dual_audit.py`](../../../scripts/build_harvey_dual_audit.py) (with its `harvey_dual_audit_core.py` and `harvey_dual_audit_render.py` modules) from the JSON files, so the counts can be regenerated from this directory.

GitHub's rendered Markdown provides the intended reading interface: use the comparison or the task table below for individual reports, or GPT-6 Sol's detailed index for criterion-level navigation of its findings.

**Audited Harvey revision:** [`1dd81403b2fbb60596f7aea3fcecafad7bf73143`](https://github.com/harveyai/harvey-labs/tree/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution). Source links use this commit rather than a moving branch.

## Contents

- [Purpose and meaning of drift](#purpose-and-meaning-of-drift)
- [Models and human involvement](#models-and-human-involvement)
- [Scope, sources, and limitations](#scope-sources-and-limitations)
- [How to read the findings](#how-to-read-the-findings)
- [Task reports](#task-reports)
- [Initial reviews of model outputs and grades](#initial-reviews-of-model-outputs-and-grades)
- [Claude Opus 5.5 audit method](#claude-opus-55-audit-method)

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
| Second audit: one blind worker and one reconciliation worker per task (104 completed workers; two blind workers were restarted) | **Claude Opus 5.5** (`claude-opus-5-5`), **high** effort |
| Second audit: coordination, workflow design, extraction, comparison rendering, and pilot spot checks | **Claude Opus 5.5 in Claude Code**; the coordinating session's effort was not recorded |
| Tested solver condition | **GPT-6 Luna** (`gpt-6-luna`), **xhigh** reasoning |
| Tested solver condition | **Claude Opus 5.5** (`claude-opus-5-5`), **low** effort, with five-minute prompt caching |
| Native LAB judges | **Claude Sonnet 4.6** (`claude-sonnet-4-6`) and **GPT-5.5** (`gpt-5.5`) |

A human set the research question, raised initial concerns about selected criteria, selected the model conditions, and provided steering and guidance. AI workers generated the report text and findings. The human asked for the Claude Opus 5.5 audit after the GPT-6 Sol audit was published, and allowed Opus to consider GPT-6 Sol's findings in reaching its own. Their initial task audits were performed without seeing solver outputs, but the project was not fully blinded to the human's initial concerns. Later output/grade reviews are explicitly separate. Agreement among AI reviewers is not independent human or expert verification.

Both audits were produced on September 26, 2026 (EDT; some stored timestamps fall on September 27 UTC). This directory is a reference snapshot, not a live results dashboard. The full solver sweeps and grading were still underway when this collection was prepared; the selected follow-up reports do not cover every eventual result.

## Scope, sources, and limitations

The initial pass covers **52 tasks, 2,858 criteria, and 520 supplied-file occurrences** in Harvey LAB's litigation-dispute-resolution folder. File occurrences count attachments across tasks, not necessarily unique documents. Workers read the criteria and inspected relevant source passages. That does not imply exhaustive review of every source paragraph, spreadsheet formula, visual layout, privilege claim, or cited legal authority. Individual reports state their coverage and limitations.

The upstream snapshot is [Harvey LAB commit `1dd81403b2fbb60596f7aea3fcecafad7bf73143`](https://github.com/harveyai/harvey-labs/tree/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution). Each task page links to its original rubric and documents at that revision. This is an independent project reference; Harvey AI has not verified or endorsed these findings.

Exact filenames and criterion IDs have been linked programmatically where their task context resolves unambiguously. Criterion links point to the corresponding line in the pinned `task.json`; document links point to the original file. Each task page also lists every supplied source file. Narrative aliases such as “the complaint” are not guessed when ambiguous, and local extraction locators are not presented as GitHub document line numbers. These link checks validate navigation, not the legal analysis.

The public copy retains report text, structured findings where available, and source pointers. Navigation, warning banners, and Markdown renderings of JSON reports have been added; machine-local paths have been removed or made portable. Raw document extractions, solver transcripts, native grade files, credentials, and working scripts are not copied into this directory. Quoted passages and native-grade summaries in the follow-up reports remain AI-produced representations of those artifacts. Extraction line numbers and XML paragraph identifiers are local analysis locators, not stable page numbers in the original files; use the named source and quoted passage when checking a finding.

The original task inputs, audit artifacts, solver outputs, and native grades were preserved separately. No native scores were overwritten with audit recommendations. Upstream source material is attributed to Harvey AI; its [MIT license notice](UPSTREAM-LICENSE.txt) is retained for quoted source material.

## How to read the findings

Start with a task report and examine its cited sources before relying on a conclusion. Separate a defect in supplied documents from a defect in a rubric, and both from a judge's misapplication or a model's own mistake. A fictional court order can contain incorrect law while still giving the model an instruction it reasonably follows; contradictions in adversarial filings are not automatically dataset defects.

GPT-6 Sol's [detailed audit index](gpt-6-sol/index.md) and [structured index](gpt-6-sol/index.json) preserve its workers' classifications and counts, and the [comparison](comparison.md) sets them beside Claude Opus 5.5's. GPT-6 Sol uses “confirmed” and Claude Opus 5.5 uses “problematic” for its stronger label; the comparison treats the two as equivalent. **Those counts are not a verified error rate, an estimate of score inflation or deflation, or corrected benchmark results.** One finding may concern several criteria, several findings may concern the same criterion, and an “arguable” concern may ultimately be rejected. “No defect established” is not certification that a criterion is correct. The legal analysis itself may be wrong or incomplete.

## Task reports

| Task | Criteria |
| --- | ---: |
| [Analyze Counterparty Motion to Dismiss — Issue Identification Memorandum](tasks/analyze-counterparty-motion-to-dismiss/README.md) | 34 |
| [Analyze Counterparty Requests for Production for Objectionable and Overbroad Discovery Demands — Issue Identification Memorandum](tasks/analyze-counterparty-requests-for-production-for-objectionable-and-overbroad-discovery-demands/README.md) | 47 |
| [Analyze Counterparty's Motion for Summary Judgment — Issue Identification Memorandum](tasks/analyze-counterpartys-motion-for-summary-judgment/README.md) | 32 |
| [Assess Litigation Hold Scope for Custodian Identification — Custodian Recommendation Memorandum](tasks/assess-litigation-hold-scope-for-custodian-identification/README.md) | 50 |
| [Assess Reasonableness of Staffing Levels on Litigation Invoice](tasks/assess-reasonableness-of-staffing-levels-on-litigation-invoice/README.md) | 49 |
| [Assess Settlement Value Range for Product Liability Crush Injury Case — Litigation Settlement Memorandum](tasks/assess-settlement-value-range/README.md) | 52 |
| [Build Litigation Case Timeline — Chronological Event Summary for Breach of Contract and Fraud Defense](tasks/build-litigation-case-timeline/README.md) | 64 |
| [Categorize Document Production Set by Relevance and Privilege — Privilege Log and Relevance Classification Report](tasks/categorize-document-production-set-by-relevance-and-privilege/README.md) | 67 |
| [Compare Document Production Against Discovery Requests — Discovery Gap Analysis Memorandum](tasks/compare-document-production-against-discovery-requests/README.md) | 46 |
| [Draft Answer with Affirmative Defenses to Breach of Contract Complaint](tasks/draft-answer-to-breach-of-contract-complaint/README.md) | 40 |
| [Draft Case Assessment Memorandum — Litigation Risk Analysis for Distribution Agreement Dispute](tasks/draft-case-assessment-memorandum/README.md) | 55 |
| [Draft Federal Complaint for Trade Secret Misappropriation and Breach of Employment Agreement](tasks/draft-complaint/README.md) | 71 |
| [Draft Conflict Check Memorandum for Litigation Engagement Clearance](tasks/draft-conflict-check-memorandum/README.md) | 56 |
| [Draft Counterclaim Against Plaintiff for Breach of Joint Development Agreement](tasks/draft-counterclaim-against-plaintiff-for-breach-of-joint-development-agreement/README.md) | 73 |
| [Draft Case Assessment Memorandum for Defective Industrial Equipment Product Liability Claim](tasks/draft-defective-industrial-equipment-product-liability/README.md) | 79 |
| [Draft Deposition Outline for Supervisor in Employment Discrimination and Retaliation Case](tasks/draft-deposition-outline/README.md) | 59 |
| [Draft Discovery Plan Memorandum for Breach of Contract and Fraud Defense](tasks/draft-discovery-plan-memorandum/README.md) | 65 |
| [Draft Federal Complaint for Breach of Contract and Fiduciary Duty — Placement Agent Dispute](tasks/draft-federal-complaint-drafting/README.md) | 50 |
| [Draft First Set of Interrogatories to Defendant Veridian Health Systems in Trade Secret Misappropriation Case](tasks/draft-interrogatories/README.md) | 50 |
| [Draft Proposed Jury Instructions for Title VII Retaliation, Ohio Whistleblower, and Implied Contract Claims](tasks/draft-jury-instructions/README.md) | 57 |
| [Draft Discovery Responses and Objections to RFAs and RFPs in Breach of Supply Agreement Litigation](tasks/draft-litigation-discovery-responses/README.md) | 61 |
| [Draft Litigation Hold Notice for New Product Liability Class Action (Medical Device)](tasks/draft-litigation-hold-notice-for-new-product-liability-matter/README.md) | 61 |
| [Draft Memorandum of Law in Support of Motion for Preliminary Injunction — Trade Secret Misappropriation and Non-Compete Enforcement](tasks/draft-motion-for-preliminary-injunction/README.md) | 53 |
| [Draft Motion for Summary Judgment — Breach of Contract, Fraudulent Inducement, and Negligent Misrepresentation in Failed ERP Implementation](tasks/draft-motion-for-summary-judgment/README.md) | 69 |
| [Draft Motion in Limine to Exclude Expert Testimony and Prejudicial Evidence in Commercial Breach of Contract Case](tasks/draft-motion-in-limine-to-exclude-expert-testimony-and-prejudicial-evidence/README.md) | 49 |
| [Draft Federal Rule 37(a) Motion to Compel Discovery Responses in Commercial Litigation](tasks/draft-motion-to-compel-discovery-responses/README.md) | 59 |
| [Draft Rule 12(b)(6) Motion to Dismiss Brief — Commercial Software Licensing Dispute](tasks/draft-motion-to-dismiss-brief/README.md) | 89 |
| [Draft Opposition to Motion for Summary Judgment in BSA/AML Whistleblower Retaliation Case](tasks/draft-opposition-to-motion-for-summary-judgment/README.md) | 59 |
| [Draft Opposition to Motion to Dismiss — Memorandum of Law in Opposition (Restrictive Covenant, Trade Secrets, Tortious Interference)](tasks/draft-opposition-to-motion-to-dismiss/README.md) | 63 |
| [Draft Plaintiff's Portion of Joint Pretrial Statement in Breach of Contract and Fraudulent Inducement Action](tasks/draft-pretrial-statement/README.md) | 46 |
| [Draft Plaintiff's First Set of Requests for Production of Documents in Breach of Contract and Trade Secret Misappropriation Action](tasks/draft-requests-for-production/README.md) | 50 |
| [Draft Verified Responses and Objections to Plaintiff's First Set of Interrogatories in Commercial Breach of Contract and Fraud Action](tasks/draft-responses-to-interrogatories/README.md) | 48 |
| [Draft Responses and Objections to Requests for Production in Breach of Contract and Fraud Litigation](tasks/draft-responses-to-requests-for-production/README.md) | 45 |
| [Draft Direct and Cross-Examination Outlines for Key Fact Witness in Breach of Contract and Fraud Action](tasks/draft-witness-examination-outline/README.md) | 62 |
| [Extract Key Admissions from Deposition Transcript — Admission Summary Memorandum](tasks/extract-key-admissions-from-deposition-transcript/README.md) | 46 |
| [Extract Key Obligations from Litigation Hold and Document Preservation Notice — Obligation Summary Memorandum](tasks/extract-key-obligations-from-litigation-hold-and-document-preservation-notice/README.md) | 52 |
| [Extract Key Terms from Counterparty Complaint — Litigation Summary Memorandum](tasks/extract-key-terms-from-counterparty-complaint/README.md) | 75 |
| [Extract Privileged Communications from Production Set — Privilege Log and Clawback Memorandum](tasks/extract-privileged-communications-from-production-set/README.md) | 66 |
| [Extract Scope Terms from Matter Plan — Structured Extraction Report](tasks/extract-scope-terms-from-matter-plan/README.md) | 76 |
| [Identify Excessive or Duplicative Research Charges in Litigation Invoice](tasks/identify-excessive-or-duplicative-research-charges-in-litigation-invoice/README.md) | 46 |
| [Government Subpoena Issue Identification — Memorandum to Partner on Grand Jury Subpoena for Insider Trading Investigation](tasks/identify-government-subpoena-issues/README.md) | 52 |
| [Identify Issues in Counterparty Complaint — Issue Identification Memorandum](tasks/identify-issues-in-counterparty-complaint/README.md) | 25 |
| [Identify Issues in Counterparty Interrogatories — Objection and Strategy Memorandum](tasks/identify-issues-in-counterparty-interrogatories/README.md) | 47 |
| [Identify Issues in Litigation Matter Budget Proposal](tasks/identify-issues-in-matter-budget-proposal/README.md) | 39 |
| [Research Corporate Veil Piercing Standards Across Target Jurisdictions — In-House Legal Memorandum](tasks/research-corporate-veil-piercing-standards-across-target-jurisdictions/README.md) | 65 |
| [Research UCC Warranty Disclaimer Requirements for New Product Launch](tasks/research-ucc-warranty-disclaimer-requirements-for-new-product-launch/README.md) | 45 |
| [Review Counterparty's Proposed Jury Instructions — Issue Memorandum for Trade Secrets Trial](tasks/review-counterpartys-proposed-jury-instructions/README.md) | 33 |
| [Review Document Production Set for Attorney-Client Privilege Designations — Privilege Log and Recommendation Memo](tasks/review-document-production-set-for-attorney/README.md) | 48 |
| [Review Litigation Invoice Against Outside Counsel Billing Guidelines — Compliance Deviation Report](tasks/review-litigation-invoice-against-outside-counsel-billing-guidelines/README.md) | 49 |
| [Review Outside Counsel Engagement Letter for Problematic Terms — Issue Identification Memorandum](tasks/review-outside-counsel-engagement-letter-for-problematic-terms/README.md) | 45 |
| [Privilege Log Review and Clawback Analysis — Deficiency Memo and Clawback Candidate List](tasks/review-privilege-log-clawback-review/README.md) | 82 |
| [Verify Disbursement Charges Against Outside Counsel Billing Guidelines — Compliance Report](tasks/verify-disbursement-charges-against-billing-guidelines/README.md) | 57 |

## Initial reviews of model outputs and grades

These selected follow-up reports were prepared after the blind rubric pass. They discuss actual model errors as well as potential grading errors. Any proposed reversal or adjusted score remains an unverified AI recommendation.

- [Motion-to-dismiss output/grade audit: summary](gpt-6-sol/follow-up/motion-to-dismiss-grade-audit/summary.md), [detailed findings](gpt-6-sol/follow-up/motion-to-dismiss-grade-audit/findings.md), and [criterion coverage](gpt-6-sol/follow-up/motion-to-dismiss-grade-audit/coverage.md).
- [Luna litigation-hold output/grade audit](gpt-6-sol/follow-up/luna-litigation-hold-grade-audit.md).
- [Initial coordinating-assistant observations](gpt-6-sol/follow-up/initial-grade-observations.md).

Batch summaries: [1](gpt-6-sol/batch-summaries/batch-1-summary.md), [2](gpt-6-sol/batch-summaries/batch-2-summary.md), [3](gpt-6-sol/batch-summaries/batch-3-summary.md), [4](gpt-6-sol/batch-summaries/batch-4-summary.md), [5](gpt-6-sol/batch-summaries/batch-5-summary.md), [6](gpt-6-sol/batch-summaries/batch-6-summary.md).

## Claude Opus 5.5 audit method

The second audit ran as one workflow with two stages per task.

1. **Blind pass.** Each worker received only the task's instructions and rubric (`task.json`), text extractions of the supplied documents, and the LAB solver system prompt and judge prompt. It was told not to open any other audit of Harvey LAB, and it was not given GPT-6 Sol's files. DOCX files were extracted with pandoc to Markdown, the same method LAB's judge uses. XLSX files list each cell with any formula and its cached value.
2. **Reconciliation pass.** A second worker received the blind findings, GPT-6 Sol's report and structured index entry for the task, and the same sources. It gave a verdict on every GPT-6 Sol finding (problematic, arguable, not a defect, or mixed), rechecking the record and law itself, and then stated Claude Opus 5.5's final findings.

After the run, all 54 blind-pass transcripts (52 tasks; two workers were restarted) were checked. No tool call opened GPT-6 Sol's files or index entries, no tool result contained GPT-6 Sol's report text, and none of the 94 web requests concerned Harvey LAB.

Each task page shows the final status and the blind-pass status side by side, so readers can see where reading GPT-6 Sol changed Opus's view. Workers could check authorities through CourtListener and web search. A citation is marked ✓ only when the worker read the primary text in that session; everything else is unverified.

The extraction and workflow reproduced GPT-6 Sol's denominators independently: 52 tasks, 2,858 criteria, and 520 supplied files at the pinned commit. For two tasks (the motion-to-dismiss issue memo and the privilege-log clawback review), the reconciliation worker also received notes from an earlier Claude Opus 5.5 session that had examined those tasks in depth. Agreement between the two models is not independent verification: the reconciliation pass saw GPT-6 Sol's conclusions, and both are AI judgments.
