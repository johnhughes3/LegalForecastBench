# LegalReasonBench sample: litigation rubric audit

> [!WARNING]
> **These audits are AI generated and have not been verified.** It reflects some human steering and guidance, but should not be treated as verified legal analysis, an authoritative assessment of Harvey LAB, or an accepted correction to any benchmark score. The reports may contain factual, legal, citation, arithmetic, and grading errors. Their labels “confirmed,” “definite,” and “verified” describe AI reviewer judgments; they do not establish human verification. **Portions of the findings that have been verified will be described separately on the public-facing LegalForecastBench site.** Inclusion here does not confer that status.

The warning above is copied from the Harvey audit. Here it applies to the LegalReasonBench audit as well. No findings in this directory have been verified by a human.

The [human-review protocol](human-review/README.md) draws a simple random sample of 25 of the 63 criteria that either blind report flagged, with a blank [worksheet](human-review/worksheet.md) for the project author's review. Until its verdicts are recorded and tallied there, no human verdict exists.

This audit asks whether litigation assignments in micro1's public sample show the rubric defect classes examined in the [Harvey LAB audit](../../harvey-lab-audit/litigation-dispute-resolution/README.md). It does not correct scores or estimate an error rate for the withheld full benchmark.

The source is [LegalReasonBench (micro1)](https://www.micro1.ai/benchmark/legal-reason-bench), pinned to [dataset revision `1bfa904c8f255925baf2610c0f86aa7c05d94ed9`](https://huggingface.co/datasets/micro1-inc/LegalReasonBench/tree/1bfa904c8f255925baf2610c0f86aa7c05d94ed9). The revision was read from the Hugging Face dataset API on October 17, 2026 UTC. The [pinned dataset card](https://huggingface.co/datasets/micro1-inc/LegalReasonBench/blob/1bfa904c8f255925baf2610c0f86aa7c05d94ed9/README.md) declares CC BY 4.0; see the [upstream license and attribution](UPSTREAM-LICENSE.txt).

The sample has 15 assignments and 221 criteria. The litigation subset has **11 assignments, 179 criteria**, across four matters. Four governance and regulatory compliance assignments (42 criteria) are excluded because their requested deliverables concern no adversarial proceeding. The criminal appeal and forum non conveniens assignments are included because they request briefs and analysis of an adversary's filing. See the [assignment census](in-scope.md). Criterion counts include reward and penalty criteria; one criterion can carry several findings.

The [comparison](comparison.md) reports blind agreement, category counts, and separate final reconciliation, with [criterion-level JSON](comparison.json). The [citation check](citation-check/README.md) records source access, first and second judgments, and rubric intent. The [Harvey comparison](comparison-to-harvey.md) places the flag and citation-problem rates alongside the earlier audit, retaining the differences in method and denominators. Each task directory contains the prompt, accumulated source packet, both model reports, and reconciliation.

The litigation source packet consists of 29 PDFs (526 pages) and four DOCX documents. Every PDF page produced some text, but the six-page Patton state plea and five-page LCU project printout contain scanned body text with only electronic stamps or browser headers in the text layer. The six-page land-use Order DOCX consists of embedded page images. Separate AI visual transcriptions supplement those extractor outputs, and visual descriptions preserve meaningful figures embedded in the Petition and Resolution DOCX files. A check of other pages with fewer than 100 extracted characters found report covers, dividers, blank report pages, and an arbitration signature page. Neither this check nor the transcriptions establish complete capture of small text, maps, or tables; uncertainty is recorded with the affected image.

The 40 distinct documents in the full sample occupy 47 attachment paths because seven are repeated in later assignments. The litigation subset contains 33 distinct documents across 40 paths. Direct comparison of the downloaded bytes established those repetitions. Assignment packets retain the accumulated attachments and earlier prompts; no prior model deliverables were invented. Duplicate copies do not constitute new evidence.

The audit uses the Harvey finding schema without adding categories: `legal_error`, `source_conflict`, `unsupported_fact`, `unrequested_requirement`, `ambiguous_or_unjudgeable`, `document_defect`, and `internal_inconsistency`. A finding may cover several criteria; a criterion may have several findings. Category counts deduplicate within each category and may overlap across categories.

The stronger label, `problematic`, follows the Harvey human-review definition of Defective: applied as written to the task, the criterion would fail a response a careful litigator could consider correct or pass one that is wrong. `arguable` covers reasonable disagreement and concerns affecting unusual responses. A demanding but defensible criterion, a permissible professional judgment, and an error in the environment that does not change grading are not automatically rubric defects. Sequential dependencies and penalty misfires are identified in explanations within the existing seven categories. A preferred prior answer alone does not establish a defect; the finding must explain how it excludes a permissible response.

Source conversion uses pandoc for DOCX, displaying tracked changes, and a PDF text extractor with page boundaries. Extraction is run in isolated Python mode from outside the directory holding downloaded, untrusted data; no upstream code is executed. PDF pages lacking text are marked as possibly blank or scanned. Extraction does not establish visual completeness, and DOCX extraction locators are not original pagination. The native instruction files are also retained, with public benchmark sandbox paths made relative. Email addresses are redacted in source quotations. The pinned upstream files remain the reference for checking any passage.

This is an independent critique, not an assessment endorsed by micro1. The sample includes public court records and adapted matter documents; opposing advocacy, hypothetical scenario instructions, planted mistakes the rubric asks a solver to identify, and genuine grading defects must be distinguished. Neither this audit nor the Harvey audit supplies a verified error rate. The full LegalReasonBench sample has only 221 criteria, fewer in litigation scope, clustered in a few sequential matters. No full-benchmark extrapolation, causal comparison, score correction, or claim of human verification is warranted.

The [instruction archive and comparison](prompts/README.md) explains which instructions are available and how they differ from Harvey. The [saved blind and reconciliation task prompts](prompts/audit-prompts.md) retain both models' common instruction, all four scope suffixes, and the later reconciliation instruction, with machine-specific paths replaced by portable placeholders.

## Review method

Claude Opus 5.5 at high effort and GPT-6 Sol at high reasoning independently read the assignment packets and produced separate reports. Each model's work was divided into two matter groups, with separate output files and instructions not to read the other model's LegalReasonBench findings. The saved reports state their actual document and legal-source coverage. External research for the audit checks the accuracy of supplied law; it does not expand the universe a solver was permitted to use in a closed-research assignment.

Both models reviewed all rubric criteria, but some long attachments were read selectively: the forum statistics volume and portions of several judicial opinions were searched and read around relevant passages. The reports identify those limits. One Opus worker's post-draft quote-checking script printed source-quote fragments from the sibling Opus worker's land-use reports, outside its assigned matters; it reports seeing no statuses or explanations and no Sol findings. This limits any claim that the two Opus matter lanes were wholly isolated, although they comprise the same model pass.

The comparison counts the two blind reports. A subsequent reconciliation reviews both sets of findings against the source record and the Harvey human-review definitions, recording a ruling on every proposed finding and a separate final set. Reconciliation does not overwrite either blind report. This differs from the published Harvey comparison, whose Opus column incorporates reconciliation after seeing Sol's findings. The two agreement tables therefore describe related but different stages of review.

The completed reconciliation rules on all 64 blind findings: 21 problematic, 29 arguable, 10 not a defect, and four mixed rulings with criterion-specific outcomes. Its 31 final findings cover 36 distinct criteria (13 problematic and 23 arguable). These are AI judgments under the stated standard. The saved reconciliation reports identify additional source limits, including unread historical local provisions and an unresolved Iowa self-defense question; the separate citation review does not turn those judgments into human verification.

Citation checking has a separate census of legal-authority occurrences in each unique matter document, with prompt and rubric occurrences counted separately. Repeated attachment copies in later assignment packets are not counted again. Each first-check problem receives a second review, and the records distinguish a defective authority from an instruction or criterion that asks the solver to catch it. Source-access failures and incomplete checks remain visible; they do not count as verified authorities.

Opus prepared the initial citation censuses; Sol reviewed their proposed problems and supplemented omitted references. Further Sol workers attempted sources that the first pass had not read. Those reads are recorded as first substantive checks, with the original judgments retained, and new problem claims receive a fresh Opus review. A rejected claim based on an auditor's misreading of citation-summary metadata remains visible without counting as an upstream problem. High effort was requested for these workers; one supplemental Opus reviewer reported low effort and the final image reviewer reported no visible named effort setting. Their JSON retains the requested and reported settings rather than asserting a confirmed runtime setting.

The saved citation review records 2,312 real-authority occurrences: 1,957 verified, 118 with minor defects, 73 problem occurrences (47 mischaracterized, five misquoted, and 21 wrong citations to real cases), and 164 unable to verify. Seventy fictional scenario-authority references are excluded. All 83 first-stage problem claims have independent second judgments, including overturned claims, and none lacks a rubric-intent record. The observed problem rate is 73/2,312 (3.2%), with 164/2,312 (7.1%) unable to verify; these are occurrence counts, not distinct underlying mistakes.

The completed occurrence censuses cover readable source text and original embedded media under the saved counting conventions. Full-resolution image inspection resolved the initial land-use fine-print gap and recovered one rule citation in a rotated survey notice; a final D.C. rescan recovered 15 omitted occurrences. Residual illegible image text is identified as geographic labels, map credits or drafting metadata. These are AI coverage judgments, not a guarantee of exhaustive capture. All assigned source-access gaps received retrieval attempts, but 164 occurrences remain unable to verify: historical local compilations, some agency decisions and secondary works, exact editions, and reporter pages remain unavailable or unread. Their per-reference records retain the attempts and precise limits. No not-found citation was labelled fabricated merely because retrieval failed. The summary's completion flag concerns enumeration and completion of required second checks; it does not mean every authority was verified.

The rendering code reuses the Harvey status aggregation and agreement buckets. It assigns each criterion the strongest status in a model's findings, deduplicates criteria within a category, and preserves overlaps between categories. It counts reconciliation separately. The rubric audit itself submitted no model responses to benchmark judges and adjusted no scores. The subsequent [paired solver experiment](model-runs/README.md) preserves actual answers and native benchmark grades separately; its available criterion grades also appear in the human-review worksheet.

## Reproduction

From the repository root, render the saved audit and citation judgments without making model calls:

```bash
uv run python -I scripts/build_legalreasonbench_audit.py render
```

To repeat the source extraction, install pandoc and save the pinned dataset API metadata outside the untrusted download directory:

```bash
mkdir -p tmp/legalreasonbench-audit
curl -fL https://huggingface.co/api/datasets/micro1-inc/LegalReasonBench/revision/1bfa904c8f255925baf2610c0f86aa7c05d94ed9 -o tmp/legalreasonbench-audit/api.json
uv run --with pypdf==6.21.0 --with fonttools==4.67.0 python -I scripts/build_legalreasonbench_audit.py extract --rows docs/legalreasonbench-audit/litigation/source-index.json --api tmp/legalreasonbench-audit/api.json
```

The extraction used pandoc 3.1.3, pypdf 6.21.0, and fonttools 4.67.0. Replaying from the saved source index reproduced all 112 task inputs, native instructions, and attachment extractions byte for byte. This comparison excludes generated review pages and the separate visual transcription. Existing classification decisions are preserved on extraction. Model judgments and visual transcription remain AI work products; rendering reproduces their saved counts rather than independently verifying their substance.

<!-- file-index:start -->
<details>
<summary>Audit document index</summary>

- [README.md](README.md)
- [citation-check/README.md](citation-check/README.md)
- [citation-check/problems.md](citation-check/problems.md)
- [citation-check/results/lrb-certiorari-quasi-judicial-land-use.md](citation-check/results/lrb-certiorari-quasi-judicial-land-use.md)
- [citation-check/results/lrb-dcca-challenge-police-discipline.md](citation-check/results/lrb-dcca-challenge-police-discipline.md)
- [citation-check/results/lrb-forum-non-conveniens-response.md](citation-check/results/lrb-forum-non-conveniens-response.md)
- [citation-check/results/lrb-vicar-trial-jury-instructions.md](citation-check/results/lrb-vicar-trial-jury-instructions.md)
- [comparison-to-harvey.md](comparison-to-harvey.md)
- [comparison.md](comparison.md)
- [human-review/README.md](human-review/README.md)
- [human-review/worksheet.md](human-review/worksheet.md)
- [in-scope.md](in-scope.md)
- [model-runs/README.md](model-runs/README.md)
- [model-runs/experiment.md](model-runs/experiment.md)
- [model-runs/lrb-certiorari-quasi-judicial-land-use-assignment-1/gpt6luna-xhigh/README.md](model-runs/lrb-certiorari-quasi-judicial-land-use-assignment-1/gpt6luna-xhigh/README.md)
- [model-runs/lrb-certiorari-quasi-judicial-land-use-assignment-1/gpt6luna-xhigh/response.md](model-runs/lrb-certiorari-quasi-judicial-land-use-assignment-1/gpt6luna-xhigh/response.md)
- [model-runs/lrb-certiorari-quasi-judicial-land-use-assignment-1/opus55-low/README.md](model-runs/lrb-certiorari-quasi-judicial-land-use-assignment-1/opus55-low/README.md)
- [model-runs/lrb-certiorari-quasi-judicial-land-use-assignment-1/opus55-low/response.md](model-runs/lrb-certiorari-quasi-judicial-land-use-assignment-1/opus55-low/response.md)
- [model-runs/lrb-certiorari-quasi-judicial-land-use-assignment-2/gpt6luna-xhigh/README.md](model-runs/lrb-certiorari-quasi-judicial-land-use-assignment-2/gpt6luna-xhigh/README.md)
- [model-runs/lrb-certiorari-quasi-judicial-land-use-assignment-2/gpt6luna-xhigh/response.md](model-runs/lrb-certiorari-quasi-judicial-land-use-assignment-2/gpt6luna-xhigh/response.md)
- [model-runs/lrb-certiorari-quasi-judicial-land-use-assignment-2/opus55-low/README.md](model-runs/lrb-certiorari-quasi-judicial-land-use-assignment-2/opus55-low/README.md)
- [model-runs/lrb-certiorari-quasi-judicial-land-use-assignment-2/opus55-low/response.md](model-runs/lrb-certiorari-quasi-judicial-land-use-assignment-2/opus55-low/response.md)
- [model-runs/lrb-forum-non-conveniens-response-assignment-1/gpt6luna-xhigh/README.md](model-runs/lrb-forum-non-conveniens-response-assignment-1/gpt6luna-xhigh/README.md)
- [model-runs/lrb-forum-non-conveniens-response-assignment-1/gpt6luna-xhigh/response.md](model-runs/lrb-forum-non-conveniens-response-assignment-1/gpt6luna-xhigh/response.md)
- [model-runs/lrb-forum-non-conveniens-response-assignment-1/opus55-low/README.md](model-runs/lrb-forum-non-conveniens-response-assignment-1/opus55-low/README.md)
- [model-runs/lrb-forum-non-conveniens-response-assignment-1/opus55-low/response.md](model-runs/lrb-forum-non-conveniens-response-assignment-1/opus55-low/response.md)
- [model-runs/lrb-forum-non-conveniens-response-assignment-2/gpt6luna-xhigh/README.md](model-runs/lrb-forum-non-conveniens-response-assignment-2/gpt6luna-xhigh/README.md)
- [model-runs/lrb-forum-non-conveniens-response-assignment-2/gpt6luna-xhigh/response.md](model-runs/lrb-forum-non-conveniens-response-assignment-2/gpt6luna-xhigh/response.md)
- [model-runs/lrb-forum-non-conveniens-response-assignment-2/opus55-low/README.md](model-runs/lrb-forum-non-conveniens-response-assignment-2/opus55-low/README.md)
- [model-runs/lrb-forum-non-conveniens-response-assignment-2/opus55-low/response.md](model-runs/lrb-forum-non-conveniens-response-assignment-2/opus55-low/response.md)
- [prompts/README.md](prompts/README.md)
- [prompts/audit-prompts.md](prompts/audit-prompts.md)
- [tasks/lrb-certiorari-quasi-judicial-land-use-assignment-1/README.md](tasks/lrb-certiorari-quasi-judicial-land-use-assignment-1/README.md)
- [tasks/lrb-certiorari-quasi-judicial-land-use-assignment-1/attachments/assignment-1/1774361815-lcu-project.pdf.md](tasks/lrb-certiorari-quasi-judicial-land-use-assignment-1/attachments/assignment-1/1774361815-lcu-project.pdf.md)
- [tasks/lrb-certiorari-quasi-judicial-land-use-assignment-1/attachments/assignment-1/1774361815-lcu-project.pdf.transcription.md](tasks/lrb-certiorari-quasi-judicial-land-use-assignment-1/attachments/assignment-1/1774361815-lcu-project.pdf.transcription.md)
- [tasks/lrb-certiorari-quasi-judicial-land-use-assignment-1/attachments/assignment-1/1774361815-orderpdf.docx.md](tasks/lrb-certiorari-quasi-judicial-land-use-assignment-1/attachments/assignment-1/1774361815-orderpdf.docx.md)
- [tasks/lrb-certiorari-quasi-judicial-land-use-assignment-1/attachments/assignment-1/1774361815-orderpdf.docx.transcription.md](tasks/lrb-certiorari-quasi-judicial-land-use-assignment-1/attachments/assignment-1/1774361815-orderpdf.docx.transcription.md)
- [tasks/lrb-certiorari-quasi-judicial-land-use-assignment-1/attachments/assignment-1/1774361815-petition.docx.figures.md](tasks/lrb-certiorari-quasi-judicial-land-use-assignment-1/attachments/assignment-1/1774361815-petition.docx.figures.md)
- [tasks/lrb-certiorari-quasi-judicial-land-use-assignment-1/attachments/assignment-1/1774361815-petition.docx.md](tasks/lrb-certiorari-quasi-judicial-land-use-assignment-1/attachments/assignment-1/1774361815-petition.docx.md)
- [tasks/lrb-certiorari-quasi-judicial-land-use-assignment-1/attachments/assignment-1/1774361815-resolution.docx.figures.md](tasks/lrb-certiorari-quasi-judicial-land-use-assignment-1/attachments/assignment-1/1774361815-resolution.docx.figures.md)
- [tasks/lrb-certiorari-quasi-judicial-land-use-assignment-1/attachments/assignment-1/1774361815-resolution.docx.md](tasks/lrb-certiorari-quasi-judicial-land-use-assignment-1/attachments/assignment-1/1774361815-resolution.docx.md)
- [tasks/lrb-certiorari-quasi-judicial-land-use-assignment-1/claude-opus-5-5-audit.md](tasks/lrb-certiorari-quasi-judicial-land-use-assignment-1/claude-opus-5-5-audit.md)
- [tasks/lrb-certiorari-quasi-judicial-land-use-assignment-1/gpt-6-sol-audit.md](tasks/lrb-certiorari-quasi-judicial-land-use-assignment-1/gpt-6-sol-audit.md)
- [tasks/lrb-certiorari-quasi-judicial-land-use-assignment-1/instruction.md](tasks/lrb-certiorari-quasi-judicial-land-use-assignment-1/instruction.md)
- [tasks/lrb-certiorari-quasi-judicial-land-use-assignment-1/reconciliation.md](tasks/lrb-certiorari-quasi-judicial-land-use-assignment-1/reconciliation.md)
- [tasks/lrb-certiorari-quasi-judicial-land-use-assignment-1/upstream-instruction.md](tasks/lrb-certiorari-quasi-judicial-land-use-assignment-1/upstream-instruction.md)
- [tasks/lrb-certiorari-quasi-judicial-land-use-assignment-2/README.md](tasks/lrb-certiorari-quasi-judicial-land-use-assignment-2/README.md)
- [tasks/lrb-certiorari-quasi-judicial-land-use-assignment-2/attachments/assignment-1/1774361815-lcu-project.pdf.md](tasks/lrb-certiorari-quasi-judicial-land-use-assignment-2/attachments/assignment-1/1774361815-lcu-project.pdf.md)
- [tasks/lrb-certiorari-quasi-judicial-land-use-assignment-2/attachments/assignment-1/1774361815-lcu-project.pdf.transcription.md](tasks/lrb-certiorari-quasi-judicial-land-use-assignment-2/attachments/assignment-1/1774361815-lcu-project.pdf.transcription.md)
- [tasks/lrb-certiorari-quasi-judicial-land-use-assignment-2/attachments/assignment-1/1774361815-orderpdf.docx.md](tasks/lrb-certiorari-quasi-judicial-land-use-assignment-2/attachments/assignment-1/1774361815-orderpdf.docx.md)
- [tasks/lrb-certiorari-quasi-judicial-land-use-assignment-2/attachments/assignment-1/1774361815-orderpdf.docx.transcription.md](tasks/lrb-certiorari-quasi-judicial-land-use-assignment-2/attachments/assignment-1/1774361815-orderpdf.docx.transcription.md)
- [tasks/lrb-certiorari-quasi-judicial-land-use-assignment-2/attachments/assignment-1/1774361815-petition.docx.figures.md](tasks/lrb-certiorari-quasi-judicial-land-use-assignment-2/attachments/assignment-1/1774361815-petition.docx.figures.md)
- [tasks/lrb-certiorari-quasi-judicial-land-use-assignment-2/attachments/assignment-1/1774361815-petition.docx.md](tasks/lrb-certiorari-quasi-judicial-land-use-assignment-2/attachments/assignment-1/1774361815-petition.docx.md)
- [tasks/lrb-certiorari-quasi-judicial-land-use-assignment-2/attachments/assignment-1/1774361815-resolution.docx.figures.md](tasks/lrb-certiorari-quasi-judicial-land-use-assignment-2/attachments/assignment-1/1774361815-resolution.docx.figures.md)
- [tasks/lrb-certiorari-quasi-judicial-land-use-assignment-2/attachments/assignment-1/1774361815-resolution.docx.md](tasks/lrb-certiorari-quasi-judicial-land-use-assignment-2/attachments/assignment-1/1774361815-resolution.docx.md)
- [tasks/lrb-certiorari-quasi-judicial-land-use-assignment-2/claude-opus-5-5-audit.md](tasks/lrb-certiorari-quasi-judicial-land-use-assignment-2/claude-opus-5-5-audit.md)
- [tasks/lrb-certiorari-quasi-judicial-land-use-assignment-2/gpt-6-sol-audit.md](tasks/lrb-certiorari-quasi-judicial-land-use-assignment-2/gpt-6-sol-audit.md)
- [tasks/lrb-certiorari-quasi-judicial-land-use-assignment-2/instruction.md](tasks/lrb-certiorari-quasi-judicial-land-use-assignment-2/instruction.md)
- [tasks/lrb-certiorari-quasi-judicial-land-use-assignment-2/reconciliation.md](tasks/lrb-certiorari-quasi-judicial-land-use-assignment-2/reconciliation.md)
- [tasks/lrb-certiorari-quasi-judicial-land-use-assignment-2/upstream-instruction.md](tasks/lrb-certiorari-quasi-judicial-land-use-assignment-2/upstream-instruction.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-1/README.md](tasks/lrb-dcca-challenge-police-discipline-assignment-1/README.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-1/attachments/assignment-1/braddock_arbitration_award.pdf.md](tasks/lrb-dcca-challenge-police-discipline-assignment-1/attachments/assignment-1/braddock_arbitration_award.pdf.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-1/attachments/assignment-1/comparator_discipline_cases.pdf.md](tasks/lrb-dcca-challenge-police-discipline-assignment-1/attachments/assignment-1/comparator_discipline_cases.pdf.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-1/attachments/assignment-1/final_notice_adverse_action_braddock.pdf.md](tasks/lrb-dcca-challenge-police-discipline-assignment-1/attachments/assignment-1/final_notice_adverse_action_braddock.pdf.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-1/claude-opus-5-5-audit.md](tasks/lrb-dcca-challenge-police-discipline-assignment-1/claude-opus-5-5-audit.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-1/gpt-6-sol-audit.md](tasks/lrb-dcca-challenge-police-discipline-assignment-1/gpt-6-sol-audit.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-1/instruction.md](tasks/lrb-dcca-challenge-police-discipline-assignment-1/instruction.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-1/reconciliation.md](tasks/lrb-dcca-challenge-police-discipline-assignment-1/reconciliation.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-1/upstream-instruction.md](tasks/lrb-dcca-challenge-police-discipline-assignment-1/upstream-instruction.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-2/README.md](tasks/lrb-dcca-challenge-police-discipline-assignment-2/README.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-2/attachments/assignment-1/braddock_arbitration_award.pdf.md](tasks/lrb-dcca-challenge-police-discipline-assignment-2/attachments/assignment-1/braddock_arbitration_award.pdf.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-2/attachments/assignment-1/comparator_discipline_cases.pdf.md](tasks/lrb-dcca-challenge-police-discipline-assignment-2/attachments/assignment-1/comparator_discipline_cases.pdf.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-2/attachments/assignment-1/final_notice_adverse_action_braddock.pdf.md](tasks/lrb-dcca-challenge-police-discipline-assignment-2/attachments/assignment-1/final_notice_adverse_action_braddock.pdf.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-2/attachments/assignment-2/dcmr_title6b_1606.pdf.md](tasks/lrb-dcca-challenge-police-discipline-assignment-2/attachments/assignment-2/dcmr_title6b_1606.pdf.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-2/attachments/assignment-2/douglas_v_veterans_admin.pdf.md](tasks/lrb-dcca-challenge-police-discipline-assignment-2/attachments/assignment-2/douglas_v_veterans_admin.pdf.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-2/claude-opus-5-5-audit.md](tasks/lrb-dcca-challenge-police-discipline-assignment-2/claude-opus-5-5-audit.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-2/gpt-6-sol-audit.md](tasks/lrb-dcca-challenge-police-discipline-assignment-2/gpt-6-sol-audit.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-2/instruction.md](tasks/lrb-dcca-challenge-police-discipline-assignment-2/instruction.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-2/reconciliation.md](tasks/lrb-dcca-challenge-police-discipline-assignment-2/reconciliation.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-2/upstream-instruction.md](tasks/lrb-dcca-challenge-police-discipline-assignment-2/upstream-instruction.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-3/README.md](tasks/lrb-dcca-challenge-police-discipline-assignment-3/README.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-3/attachments/assignment-1/braddock_arbitration_award.pdf.md](tasks/lrb-dcca-challenge-police-discipline-assignment-3/attachments/assignment-1/braddock_arbitration_award.pdf.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-3/attachments/assignment-1/comparator_discipline_cases.pdf.md](tasks/lrb-dcca-challenge-police-discipline-assignment-3/attachments/assignment-1/comparator_discipline_cases.pdf.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-3/attachments/assignment-1/final_notice_adverse_action_braddock.pdf.md](tasks/lrb-dcca-challenge-police-discipline-assignment-3/attachments/assignment-1/final_notice_adverse_action_braddock.pdf.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-3/attachments/assignment-2/dcmr_title6b_1606.pdf.md](tasks/lrb-dcca-challenge-police-discipline-assignment-3/attachments/assignment-2/dcmr_title6b_1606.pdf.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-3/attachments/assignment-2/douglas_v_veterans_admin.pdf.md](tasks/lrb-dcca-challenge-police-discipline-assignment-3/attachments/assignment-2/douglas_v_veterans_admin.pdf.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-3/attachments/assignment-3/dc_code_1-605.02.pdf.md](tasks/lrb-dcca-challenge-police-discipline-assignment-3/attachments/assignment-3/dc_code_1-605.02.pdf.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-3/attachments/assignment-3/fop_doc_labor_comm_v_perb_2009.pdf.md](tasks/lrb-dcca-challenge-police-discipline-assignment-3/attachments/assignment-3/fop_doc_labor_comm_v_perb_2009.pdf.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-3/attachments/assignment-3/paperworkers_v_misco.pdf.md](tasks/lrb-dcca-challenge-police-discipline-assignment-3/attachments/assignment-3/paperworkers_v_misco.pdf.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-3/attachments/assignment-3/perb_decision_braddock.pdf.md](tasks/lrb-dcca-challenge-police-discipline-assignment-3/attachments/assignment-3/perb_decision_braddock.pdf.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-3/attachments/assignment-3/wr_grace_v_rubber_workers.pdf.md](tasks/lrb-dcca-challenge-police-discipline-assignment-3/attachments/assignment-3/wr_grace_v_rubber_workers.pdf.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-3/claude-opus-5-5-audit.md](tasks/lrb-dcca-challenge-police-discipline-assignment-3/claude-opus-5-5-audit.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-3/gpt-6-sol-audit.md](tasks/lrb-dcca-challenge-police-discipline-assignment-3/gpt-6-sol-audit.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-3/instruction.md](tasks/lrb-dcca-challenge-police-discipline-assignment-3/instruction.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-3/reconciliation.md](tasks/lrb-dcca-challenge-police-discipline-assignment-3/reconciliation.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-3/upstream-instruction.md](tasks/lrb-dcca-challenge-police-discipline-assignment-3/upstream-instruction.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-4/README.md](tasks/lrb-dcca-challenge-police-discipline-assignment-4/README.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-4/attachments/assignment-1/braddock_arbitration_award.pdf.md](tasks/lrb-dcca-challenge-police-discipline-assignment-4/attachments/assignment-1/braddock_arbitration_award.pdf.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-4/attachments/assignment-1/comparator_discipline_cases.pdf.md](tasks/lrb-dcca-challenge-police-discipline-assignment-4/attachments/assignment-1/comparator_discipline_cases.pdf.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-4/attachments/assignment-1/final_notice_adverse_action_braddock.pdf.md](tasks/lrb-dcca-challenge-police-discipline-assignment-4/attachments/assignment-1/final_notice_adverse_action_braddock.pdf.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-4/attachments/assignment-2/dcmr_title6b_1606.pdf.md](tasks/lrb-dcca-challenge-police-discipline-assignment-4/attachments/assignment-2/dcmr_title6b_1606.pdf.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-4/attachments/assignment-2/douglas_v_veterans_admin.pdf.md](tasks/lrb-dcca-challenge-police-discipline-assignment-4/attachments/assignment-2/douglas_v_veterans_admin.pdf.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-4/attachments/assignment-3/dc_code_1-605.02.pdf.md](tasks/lrb-dcca-challenge-police-discipline-assignment-4/attachments/assignment-3/dc_code_1-605.02.pdf.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-4/attachments/assignment-3/fop_doc_labor_comm_v_perb_2009.pdf.md](tasks/lrb-dcca-challenge-police-discipline-assignment-4/attachments/assignment-3/fop_doc_labor_comm_v_perb_2009.pdf.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-4/attachments/assignment-3/paperworkers_v_misco.pdf.md](tasks/lrb-dcca-challenge-police-discipline-assignment-4/attachments/assignment-3/paperworkers_v_misco.pdf.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-4/attachments/assignment-3/perb_decision_braddock.pdf.md](tasks/lrb-dcca-challenge-police-discipline-assignment-4/attachments/assignment-3/perb_decision_braddock.pdf.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-4/attachments/assignment-3/wr_grace_v_rubber_workers.pdf.md](tasks/lrb-dcca-challenge-police-discipline-assignment-4/attachments/assignment-3/wr_grace_v_rubber_workers.pdf.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-4/attachments/assignment-4/supplemental_comparator_disclosure.pdf.md](tasks/lrb-dcca-challenge-police-discipline-assignment-4/attachments/assignment-4/supplemental_comparator_disclosure.pdf.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-4/claude-opus-5-5-audit.md](tasks/lrb-dcca-challenge-police-discipline-assignment-4/claude-opus-5-5-audit.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-4/gpt-6-sol-audit.md](tasks/lrb-dcca-challenge-police-discipline-assignment-4/gpt-6-sol-audit.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-4/instruction.md](tasks/lrb-dcca-challenge-police-discipline-assignment-4/instruction.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-4/reconciliation.md](tasks/lrb-dcca-challenge-police-discipline-assignment-4/reconciliation.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-4/upstream-instruction.md](tasks/lrb-dcca-challenge-police-discipline-assignment-4/upstream-instruction.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-5/README.md](tasks/lrb-dcca-challenge-police-discipline-assignment-5/README.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-5/attachments/assignment-1/braddock_arbitration_award.pdf.md](tasks/lrb-dcca-challenge-police-discipline-assignment-5/attachments/assignment-1/braddock_arbitration_award.pdf.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-5/attachments/assignment-1/comparator_discipline_cases.pdf.md](tasks/lrb-dcca-challenge-police-discipline-assignment-5/attachments/assignment-1/comparator_discipline_cases.pdf.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-5/attachments/assignment-1/final_notice_adverse_action_braddock.pdf.md](tasks/lrb-dcca-challenge-police-discipline-assignment-5/attachments/assignment-1/final_notice_adverse_action_braddock.pdf.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-5/attachments/assignment-2/dcmr_title6b_1606.pdf.md](tasks/lrb-dcca-challenge-police-discipline-assignment-5/attachments/assignment-2/dcmr_title6b_1606.pdf.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-5/attachments/assignment-2/douglas_v_veterans_admin.pdf.md](tasks/lrb-dcca-challenge-police-discipline-assignment-5/attachments/assignment-2/douglas_v_veterans_admin.pdf.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-5/attachments/assignment-3/dc_code_1-605.02.pdf.md](tasks/lrb-dcca-challenge-police-discipline-assignment-5/attachments/assignment-3/dc_code_1-605.02.pdf.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-5/attachments/assignment-3/fop_doc_labor_comm_v_perb_2009.pdf.md](tasks/lrb-dcca-challenge-police-discipline-assignment-5/attachments/assignment-3/fop_doc_labor_comm_v_perb_2009.pdf.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-5/attachments/assignment-3/paperworkers_v_misco.pdf.md](tasks/lrb-dcca-challenge-police-discipline-assignment-5/attachments/assignment-3/paperworkers_v_misco.pdf.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-5/attachments/assignment-3/perb_decision_braddock.pdf.md](tasks/lrb-dcca-challenge-police-discipline-assignment-5/attachments/assignment-3/perb_decision_braddock.pdf.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-5/attachments/assignment-3/wr_grace_v_rubber_workers.pdf.md](tasks/lrb-dcca-challenge-police-discipline-assignment-5/attachments/assignment-3/wr_grace_v_rubber_workers.pdf.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-5/attachments/assignment-4/supplemental_comparator_disclosure.pdf.md](tasks/lrb-dcca-challenge-police-discipline-assignment-5/attachments/assignment-4/supplemental_comparator_disclosure.pdf.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-5/claude-opus-5-5-audit.md](tasks/lrb-dcca-challenge-police-discipline-assignment-5/claude-opus-5-5-audit.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-5/gpt-6-sol-audit.md](tasks/lrb-dcca-challenge-police-discipline-assignment-5/gpt-6-sol-audit.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-5/instruction.md](tasks/lrb-dcca-challenge-police-discipline-assignment-5/instruction.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-5/reconciliation.md](tasks/lrb-dcca-challenge-police-discipline-assignment-5/reconciliation.md)
- [tasks/lrb-dcca-challenge-police-discipline-assignment-5/upstream-instruction.md](tasks/lrb-dcca-challenge-police-discipline-assignment-5/upstream-instruction.md)
- [tasks/lrb-forum-non-conveniens-response-assignment-1/README.md](tasks/lrb-forum-non-conveniens-response-assignment-1/README.md)
- [tasks/lrb-forum-non-conveniens-response-assignment-1/attachments/assignment-1/2023 Annual Report Statistical Summary.pdf.md](tasks/lrb-forum-non-conveniens-response-assignment-1/attachments/assignment-1/2023%20Annual%20Report%20Statistical%20Summary.pdf.md)
- [tasks/lrb-forum-non-conveniens-response-assignment-1/attachments/assignment-1/Bradbury v. St. Mary's Hospital.pdf.md](tasks/lrb-forum-non-conveniens-response-assignment-1/attachments/assignment-1/Bradbury%20v.%20St.%20Mary%27s%20Hospital.pdf.md)
- [tasks/lrb-forum-non-conveniens-response-assignment-1/attachments/assignment-1/Davis Complaint.docx.md](tasks/lrb-forum-non-conveniens-response-assignment-1/attachments/assignment-1/Davis%20Complaint.docx.md)
- [tasks/lrb-forum-non-conveniens-response-assignment-1/attachments/assignment-1/Defendants Motion to Transfer.pdf.md](tasks/lrb-forum-non-conveniens-response-assignment-1/attachments/assignment-1/Defendants%20Motion%20to%20Transfer.pdf.md)
- [tasks/lrb-forum-non-conveniens-response-assignment-1/attachments/assignment-1/First Am Bank v. Guerine.pdf.md](tasks/lrb-forum-non-conveniens-response-assignment-1/attachments/assignment-1/First%20Am%20Bank%20v.%20Guerine.pdf.md)
- [tasks/lrb-forum-non-conveniens-response-assignment-1/attachments/assignment-1/Langenhorst v. Norfolk Southern.pdf.md](tasks/lrb-forum-non-conveniens-response-assignment-1/attachments/assignment-1/Langenhorst%20v.%20Norfolk%20Southern.pdf.md)
- [tasks/lrb-forum-non-conveniens-response-assignment-1/claude-opus-5-5-audit.md](tasks/lrb-forum-non-conveniens-response-assignment-1/claude-opus-5-5-audit.md)
- [tasks/lrb-forum-non-conveniens-response-assignment-1/gpt-6-sol-audit.md](tasks/lrb-forum-non-conveniens-response-assignment-1/gpt-6-sol-audit.md)
- [tasks/lrb-forum-non-conveniens-response-assignment-1/instruction.md](tasks/lrb-forum-non-conveniens-response-assignment-1/instruction.md)
- [tasks/lrb-forum-non-conveniens-response-assignment-1/reconciliation.md](tasks/lrb-forum-non-conveniens-response-assignment-1/reconciliation.md)
- [tasks/lrb-forum-non-conveniens-response-assignment-1/upstream-instruction.md](tasks/lrb-forum-non-conveniens-response-assignment-1/upstream-instruction.md)
- [tasks/lrb-forum-non-conveniens-response-assignment-2/README.md](tasks/lrb-forum-non-conveniens-response-assignment-2/README.md)
- [tasks/lrb-forum-non-conveniens-response-assignment-2/attachments/assignment-1/2023 Annual Report Statistical Summary.pdf.md](tasks/lrb-forum-non-conveniens-response-assignment-2/attachments/assignment-1/2023%20Annual%20Report%20Statistical%20Summary.pdf.md)
- [tasks/lrb-forum-non-conveniens-response-assignment-2/attachments/assignment-1/Bradbury v. St. Mary's Hospital.pdf.md](tasks/lrb-forum-non-conveniens-response-assignment-2/attachments/assignment-1/Bradbury%20v.%20St.%20Mary%27s%20Hospital.pdf.md)
- [tasks/lrb-forum-non-conveniens-response-assignment-2/attachments/assignment-1/Davis Complaint.docx.md](tasks/lrb-forum-non-conveniens-response-assignment-2/attachments/assignment-1/Davis%20Complaint.docx.md)
- [tasks/lrb-forum-non-conveniens-response-assignment-2/attachments/assignment-1/Defendants Motion to Transfer.pdf.md](tasks/lrb-forum-non-conveniens-response-assignment-2/attachments/assignment-1/Defendants%20Motion%20to%20Transfer.pdf.md)
- [tasks/lrb-forum-non-conveniens-response-assignment-2/attachments/assignment-1/First Am Bank v. Guerine.pdf.md](tasks/lrb-forum-non-conveniens-response-assignment-2/attachments/assignment-1/First%20Am%20Bank%20v.%20Guerine.pdf.md)
- [tasks/lrb-forum-non-conveniens-response-assignment-2/attachments/assignment-1/Langenhorst v. Norfolk Southern.pdf.md](tasks/lrb-forum-non-conveniens-response-assignment-2/attachments/assignment-1/Langenhorst%20v.%20Norfolk%20Southern.pdf.md)
- [tasks/lrb-forum-non-conveniens-response-assignment-2/attachments/assignment-2/2023 Annual Report Statistical Summary.pdf.md](tasks/lrb-forum-non-conveniens-response-assignment-2/attachments/assignment-2/2023%20Annual%20Report%20Statistical%20Summary.pdf.md)
- [tasks/lrb-forum-non-conveniens-response-assignment-2/attachments/assignment-2/Bradbury v. St. Mary's Hospital.pdf.md](tasks/lrb-forum-non-conveniens-response-assignment-2/attachments/assignment-2/Bradbury%20v.%20St.%20Mary%27s%20Hospital.pdf.md)
- [tasks/lrb-forum-non-conveniens-response-assignment-2/attachments/assignment-2/Davis Complaint.docx.md](tasks/lrb-forum-non-conveniens-response-assignment-2/attachments/assignment-2/Davis%20Complaint.docx.md)
- [tasks/lrb-forum-non-conveniens-response-assignment-2/attachments/assignment-2/Defendants Motion to Transfer.pdf.md](tasks/lrb-forum-non-conveniens-response-assignment-2/attachments/assignment-2/Defendants%20Motion%20to%20Transfer.pdf.md)
- [tasks/lrb-forum-non-conveniens-response-assignment-2/attachments/assignment-2/First Am Bank v. Guerine.pdf.md](tasks/lrb-forum-non-conveniens-response-assignment-2/attachments/assignment-2/First%20Am%20Bank%20v.%20Guerine.pdf.md)
- [tasks/lrb-forum-non-conveniens-response-assignment-2/attachments/assignment-2/Langenhorst v. Norfolk Southern.pdf.md](tasks/lrb-forum-non-conveniens-response-assignment-2/attachments/assignment-2/Langenhorst%20v.%20Norfolk%20Southern.pdf.md)
- [tasks/lrb-forum-non-conveniens-response-assignment-2/claude-opus-5-5-audit.md](tasks/lrb-forum-non-conveniens-response-assignment-2/claude-opus-5-5-audit.md)
- [tasks/lrb-forum-non-conveniens-response-assignment-2/gpt-6-sol-audit.md](tasks/lrb-forum-non-conveniens-response-assignment-2/gpt-6-sol-audit.md)
- [tasks/lrb-forum-non-conveniens-response-assignment-2/instruction.md](tasks/lrb-forum-non-conveniens-response-assignment-2/instruction.md)
- [tasks/lrb-forum-non-conveniens-response-assignment-2/reconciliation.md](tasks/lrb-forum-non-conveniens-response-assignment-2/reconciliation.md)
- [tasks/lrb-forum-non-conveniens-response-assignment-2/upstream-instruction.md](tasks/lrb-forum-non-conveniens-response-assignment-2/upstream-instruction.md)
- [tasks/lrb-vicar-trial-jury-instructions-assignment-1/README.md](tasks/lrb-vicar-trial-jury-instructions-assignment-1/README.md)
- [tasks/lrb-vicar-trial-jury-instructions-assignment-1/attachments/assignment-1/702.11.pdf.md](tasks/lrb-vicar-trial-jury-instructions-assignment-1/attachments/assignment-1/702.11.pdf.md)
- [tasks/lrb-vicar-trial-jury-instructions-assignment-1/attachments/assignment-1/704.pdf.md](tasks/lrb-vicar-trial-jury-instructions-assignment-1/attachments/assignment-1/704.pdf.md)
- [tasks/lrb-vicar-trial-jury-instructions-assignment-1/attachments/assignment-1/706.1.pdf.md](tasks/lrb-vicar-trial-jury-instructions-assignment-1/attachments/assignment-1/706.1.pdf.md)
- [tasks/lrb-vicar-trial-jury-instructions-assignment-1/attachments/assignment-1/707.11.pdf.md](tasks/lrb-vicar-trial-jury-instructions-assignment-1/attachments/assignment-1/707.11.pdf.md)
- [tasks/lrb-vicar-trial-jury-instructions-assignment-1/attachments/assignment-1/708.6.pdf.md](tasks/lrb-vicar-trial-jury-instructions-assignment-1/attachments/assignment-1/708.6.pdf.md)
- [tasks/lrb-vicar-trial-jury-instructions-assignment-1/attachments/assignment-1/Ellison.pdf.md](tasks/lrb-vicar-trial-jury-instructions-assignment-1/attachments/assignment-1/Ellison.pdf.md)
- [tasks/lrb-vicar-trial-jury-instructions-assignment-1/attachments/assignment-1/Facts.pdf.md](tasks/lrb-vicar-trial-jury-instructions-assignment-1/attachments/assignment-1/Facts.pdf.md)
- [tasks/lrb-vicar-trial-jury-instructions-assignment-1/attachments/assignment-1/Kehoe.pdf.md](tasks/lrb-vicar-trial-jury-instructions-assignment-1/attachments/assignment-1/Kehoe.pdf.md)
- [tasks/lrb-vicar-trial-jury-instructions-assignment-1/attachments/assignment-1/Patton State Plea.pdf.md](tasks/lrb-vicar-trial-jury-instructions-assignment-1/attachments/assignment-1/Patton%20State%20Plea.pdf.md)
- [tasks/lrb-vicar-trial-jury-instructions-assignment-1/attachments/assignment-1/Patton State Plea.pdf.transcription.md](tasks/lrb-vicar-trial-jury-instructions-assignment-1/attachments/assignment-1/Patton%20State%20Plea.pdf.transcription.md)
- [tasks/lrb-vicar-trial-jury-instructions-assignment-1/attachments/assignment-1/Poe.pdf.md](tasks/lrb-vicar-trial-jury-instructions-assignment-1/attachments/assignment-1/Poe.pdf.md)
- [tasks/lrb-vicar-trial-jury-instructions-assignment-1/attachments/assignment-1/White Horse.pdf.md](tasks/lrb-vicar-trial-jury-instructions-assignment-1/attachments/assignment-1/White%20Horse.pdf.md)
- [tasks/lrb-vicar-trial-jury-instructions-assignment-1/claude-opus-5-5-audit.md](tasks/lrb-vicar-trial-jury-instructions-assignment-1/claude-opus-5-5-audit.md)
- [tasks/lrb-vicar-trial-jury-instructions-assignment-1/gpt-6-sol-audit.md](tasks/lrb-vicar-trial-jury-instructions-assignment-1/gpt-6-sol-audit.md)
- [tasks/lrb-vicar-trial-jury-instructions-assignment-1/instruction.md](tasks/lrb-vicar-trial-jury-instructions-assignment-1/instruction.md)
- [tasks/lrb-vicar-trial-jury-instructions-assignment-1/reconciliation.md](tasks/lrb-vicar-trial-jury-instructions-assignment-1/reconciliation.md)
- [tasks/lrb-vicar-trial-jury-instructions-assignment-1/upstream-instruction.md](tasks/lrb-vicar-trial-jury-instructions-assignment-1/upstream-instruction.md)
- [tasks/lrb-vicar-trial-jury-instructions-assignment-2/README.md](tasks/lrb-vicar-trial-jury-instructions-assignment-2/README.md)
- [tasks/lrb-vicar-trial-jury-instructions-assignment-2/attachments/assignment-1/702.11.pdf.md](tasks/lrb-vicar-trial-jury-instructions-assignment-2/attachments/assignment-1/702.11.pdf.md)
- [tasks/lrb-vicar-trial-jury-instructions-assignment-2/attachments/assignment-1/704.pdf.md](tasks/lrb-vicar-trial-jury-instructions-assignment-2/attachments/assignment-1/704.pdf.md)
- [tasks/lrb-vicar-trial-jury-instructions-assignment-2/attachments/assignment-1/706.1.pdf.md](tasks/lrb-vicar-trial-jury-instructions-assignment-2/attachments/assignment-1/706.1.pdf.md)
- [tasks/lrb-vicar-trial-jury-instructions-assignment-2/attachments/assignment-1/707.11.pdf.md](tasks/lrb-vicar-trial-jury-instructions-assignment-2/attachments/assignment-1/707.11.pdf.md)
- [tasks/lrb-vicar-trial-jury-instructions-assignment-2/attachments/assignment-1/708.6.pdf.md](tasks/lrb-vicar-trial-jury-instructions-assignment-2/attachments/assignment-1/708.6.pdf.md)
- [tasks/lrb-vicar-trial-jury-instructions-assignment-2/attachments/assignment-1/Ellison.pdf.md](tasks/lrb-vicar-trial-jury-instructions-assignment-2/attachments/assignment-1/Ellison.pdf.md)
- [tasks/lrb-vicar-trial-jury-instructions-assignment-2/attachments/assignment-1/Facts.pdf.md](tasks/lrb-vicar-trial-jury-instructions-assignment-2/attachments/assignment-1/Facts.pdf.md)
- [tasks/lrb-vicar-trial-jury-instructions-assignment-2/attachments/assignment-1/Kehoe.pdf.md](tasks/lrb-vicar-trial-jury-instructions-assignment-2/attachments/assignment-1/Kehoe.pdf.md)
- [tasks/lrb-vicar-trial-jury-instructions-assignment-2/attachments/assignment-1/Patton State Plea.pdf.md](tasks/lrb-vicar-trial-jury-instructions-assignment-2/attachments/assignment-1/Patton%20State%20Plea.pdf.md)
- [tasks/lrb-vicar-trial-jury-instructions-assignment-2/attachments/assignment-1/Patton State Plea.pdf.transcription.md](tasks/lrb-vicar-trial-jury-instructions-assignment-2/attachments/assignment-1/Patton%20State%20Plea.pdf.transcription.md)
- [tasks/lrb-vicar-trial-jury-instructions-assignment-2/attachments/assignment-1/Poe.pdf.md](tasks/lrb-vicar-trial-jury-instructions-assignment-2/attachments/assignment-1/Poe.pdf.md)
- [tasks/lrb-vicar-trial-jury-instructions-assignment-2/attachments/assignment-1/White Horse.pdf.md](tasks/lrb-vicar-trial-jury-instructions-assignment-2/attachments/assignment-1/White%20Horse.pdf.md)
- [tasks/lrb-vicar-trial-jury-instructions-assignment-2/attachments/assignment-2/Facts.pdf.md](tasks/lrb-vicar-trial-jury-instructions-assignment-2/attachments/assignment-2/Facts.pdf.md)
- [tasks/lrb-vicar-trial-jury-instructions-assignment-2/attachments/assignment-2/Kuhse.pdf.md](tasks/lrb-vicar-trial-jury-instructions-assignment-2/attachments/assignment-2/Kuhse.pdf.md)
- [tasks/lrb-vicar-trial-jury-instructions-assignment-2/claude-opus-5-5-audit.md](tasks/lrb-vicar-trial-jury-instructions-assignment-2/claude-opus-5-5-audit.md)
- [tasks/lrb-vicar-trial-jury-instructions-assignment-2/gpt-6-sol-audit.md](tasks/lrb-vicar-trial-jury-instructions-assignment-2/gpt-6-sol-audit.md)
- [tasks/lrb-vicar-trial-jury-instructions-assignment-2/instruction.md](tasks/lrb-vicar-trial-jury-instructions-assignment-2/instruction.md)
- [tasks/lrb-vicar-trial-jury-instructions-assignment-2/reconciliation.md](tasks/lrb-vicar-trial-jury-instructions-assignment-2/reconciliation.md)
- [tasks/lrb-vicar-trial-jury-instructions-assignment-2/upstream-instruction.md](tasks/lrb-vicar-trial-jury-instructions-assignment-2/upstream-instruction.md)

</details>
<!-- file-index:end -->
