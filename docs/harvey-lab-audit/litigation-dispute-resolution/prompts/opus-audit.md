# Recovered Harvey Opus audit prompts

Recovered on October 19, 2026 from the saved Claude Opus 5.5 workflow source and its coordinator's workflow dispatches. The same prompt functions were used for the initial two tasks and the remaining 50 tasks. This preserves the reviewer task instructions and structured-output schemas, not the provider's system instructions, complete conversation, tool results, task inputs, or later messages. It is an archival transcription, not a new recommended prompt.

The original JavaScript interpolations are replaced with named `{{PLACEHOLDERS}}`; machine-specific input and output roots are omitted. These substitutions change source locations and template notation, not the substantive audit instructions. Insert the common context and defect guide into each pass at their marked positions. The task input directory held `task.json` and extracted documents; the upstream checkout supplied the solver and judge prompts. Those benchmark prompts are distinct from the auditor instructions below.

## Common context

```text
Harvey LAB is a public legal-AI benchmark. You are auditing ONE task, "{{TASK}}", for defects in its rubric and supplied record.

Inputs (read-only):
- {{TASK_INPUT_DIR}}/task.json: the instructions given to the solver and the {{CRITERIA_COUNT}} grading criteria (match_criteria text).
- {{TASK_INPUT_DIR}}/documents/*.txt: text extractions of the {{DOCUMENT_COUNT}} supplied documents. DOCX was extracted with pandoc to markdown (the same text the LAB judge sees); XLSX lists cells as COORD=value, with formulas shown as =FORMULA -> cached value.
- {{UPSTREAM_CHECKOUT}}/lab_core/harness/system_prompt.md (generic solver system prompt; it tells the solver not to read task.json) and {{UPSTREAM_CHECKOUT}}/lab_core/evaluation/prompts/rubric_criterion.txt (judge prompt).

How grading works: the solver sees only the instructions, the system prompt, and the documents. Each criterion is graded pass/fail independently by two LLM judges (Claude Sonnet 4.6 and GPT-5.5). Each judge sees the instructions, the deliverable, and that one criterion's match_criteria; there is no reference answer. The headline metric is all-pass: a run scores only if every criterion passes for both judges. So one defective criterion can zero out a correct answer.
```

## Defect guide

```text
What counts as a defect (be calibrated, not maximal):
- legal_error: the criterion requires or rewards an incorrect or materially incomplete legal proposition for the governing jurisdiction and facts.
- source_conflict / unsupported_fact: the criterion depends on facts the record contradicts or does not contain.
- unrequested_requirement: the criterion demands format, labels, counts, ratings, sections, citations, or dates the instructions never asked for AND that a competent practitioner would not treat as implicit in the requested work product. Explain why it is hidden rather than implicit. Standard components of the named document type are implicit, not hidden.
- internal_inconsistency: criteria conflict with each other or with the instructions.
- ambiguous_or_unjudgeable: the judge cannot reliably apply it, or a correct answer falls between its PASS and FAIL conditions.
- document_defect: an error or inconsistency in the supplied documents that affects what a correct answer is (contradictions inside adversarial filings are not automatically defects).
Do NOT flag ordinary disagreement about legal judgment where the criterion's position is reasonable, or a criterion that is merely demanding.
Status: "problematic" means you are confident the criterion as written would misgrade competent work (fail a correct answer or reward a wrong one) or states wrong law or facts. "arguable" means it is defensible but debatable, depends on judgment or unstated assumptions, or would misgrade only some competent answers.
Method: read every criterion and the instructions. Read the key documents in full. For large records, search the rest for the facts each criterion relies on (use grep/rg on the .txt files). Check legal propositions where they matter: CourtListener MCP tools are available via ToolSearch (e.g. "select:mcp__claude_ai_CourtListener__search,mcp__claude_ai_CourtListener__read_document"), and so is WebSearch for statutes. Never fabricate a citation; set verified=true only if you read the primary text in this session. Quote evidence verbatim with its filename. Keep each explanation tight. The finding list should reflect your honest assessment: an empty list is acceptable if the rubric is sound.
```

## Blind pass

```text
{{COMMON_CONTEXT}}

{{DEFECT_GUIDE}}

Independence rule: this is a blind, independent audit. Do NOT open, search for, or read any other audit or commentary about Harvey LAB, including anything under a docs/harvey-lab-audit directory in any repository on this machine, and do not search the web for reviews of Harvey LAB rubrics. Work only from the inputs above and legal sources.

Return the structured result. criteria_reviewed must equal the number of criteria you actually reviewed.
```

## Reconciliation pass

```text
{{COMMON_CONTEXT}}

{{DEFECT_GUIDE}}

This is the SECOND pass. In a blind first pass (you, Claude Opus 5.5, without seeing any other audit), you produced these findings:
<blind_findings>
{{BLIND_FINDINGS_JSON}}
</blind_findings>

Now review the independent audit of the same task by another model, GPT-6 Sol:
- Structured index entry (the list of Sol findings with locator, status, criteria): {{SOL_INDEX_ENTRY_FILE}}
- Sol's report files: {{SOL_REPORT_FILES}}{{OPTIONAL_PRIOR_NOTES_LINE}}

Do three things:
1. For EVERY finding in the Sol index entry's findings[] (use its locator verbatim), check the record and law yourself and give your verdict: problematic, arguable, not_a_defect, or mixed (with per_criterion verdicts for every criterion in sol_criteria). Give a concrete reason. Do not defer to Sol, and do not anchor on your blind pass. Update either way based on evidence.
2. Produce your FINAL findings: the complete Claude Opus 5.5 position for this task. Every criterion you consider problematic or arguable must appear in some finding, including ones you now accept from Sol (origin "adopted_after_reading_sol") and blind findings you changed (origin "revised"). Drop blind findings you no longer support, and say so in changes_from_blind. Link sol_locators and blind_ids where relevant. Keep ids O1, O2, ... (renumber as needed).
3. Your per-criterion verdicts in sol_verdicts must be consistent with your final findings: a criterion you call problematic or arguable there must appear at that status in findings.
```

`{{BLIND_FINDINGS_JSON}}` was the corresponding blind result serialized as JSON. `{{SOL_INDEX_ENTRY_FILE}}` and `{{SOL_REPORT_FILES}}` pointed to that task's Sol findings. `{{OPTIONAL_PRIOR_NOTES_LINE}}` was empty except for the motion-to-dismiss issue memo and privilege-log clawback review. For those two tasks it expanded as follows, with the original source path replaced:

```text
- An earlier Claude Opus 5.5 session analyzed this task in depth; its verified notes are at {{PRIOR_NOTES_FILE}}. Treat them as your own prior work, subject to the same evidence standard.
```

The word “verified” above is retained from the historical prompt; it does not establish human verification. The reconciliation instructions address the second worker as though it were the blind worker, but the workflow created a separate worker for each stage and passed the blind result to the second worker. Both stages requested `effort: 'high'`.

## Structured-output schemas

The workflow supplied these schemas separately from the prompt string. They are retained as JavaScript declarations to preserve the original required fields and descriptions. The historical category enum allowed `other` in addition to the seven named categories; this differs from LegalReasonBench's explicit seven-category restriction.

```javascript
const EVIDENCE = { type: 'array', items: { type: 'object', required: ['source', 'quote'], properties: {
  source: { type: 'string', description: 'task.json criterion id / instructions, or supplied document filename' },
  quote: { type: 'string', description: 'verbatim excerpt, short' } } } }
const AUTH = { type: 'array', items: { type: 'object', required: ['citation', 'proposition', 'verified'], properties: {
  citation: { type: 'string' }, proposition: { type: 'string' },
  verified: { type: 'boolean', description: 'true only if you read the primary text in this session' } } } }
const FINDING_PROPS = {
  id: { type: 'string', description: 'O1, O2, ...' },
  status: { type: 'string', enum: ['problematic', 'arguable'] },
  category: { type: 'string', enum: ['legal_error', 'source_conflict', 'unsupported_fact', 'unrequested_requirement', 'internal_inconsistency', 'ambiguous_or_unjudgeable', 'document_defect', 'other'] },
  criteria: { type: 'array', items: { type: 'string' }, description: 'criterion ids like C-012; empty only for document defects not tied to a criterion' },
  title: { type: 'string', description: 'one line, <=120 chars' },
  explanation: { type: 'string', description: '<=180 words: what is wrong and how it would misgrade competent work' },
  evidence: EVIDENCE,
  authorities: AUTH,
  suggested_fix: { type: 'string' },
}
const FINDING_REQ = ['id', 'status', 'category', 'criteria', 'title', 'explanation', 'evidence', 'authorities', 'suggested_fix']

const BLIND_SCHEMA = { type: 'object', required: ['task', 'criteria_reviewed', 'coverage', 'findings', 'overall'], properties: {
  task: { type: 'string' },
  criteria_reviewed: { type: 'integer' },
  coverage: { type: 'string', description: 'which documents read fully vs searched; limitations; what was not verified' },
  findings: { type: 'array', items: { type: 'object', required: FINDING_REQ, properties: FINDING_PROPS } },
  overall: { type: 'string', description: '3-6 sentences: overall soundness of this task rubric' } } }

const FINAL_SCHEMA = { type: 'object', required: ['task', 'sol_verdicts', 'findings', 'changes_from_blind', 'overall', 'coverage'], properties: {
  task: { type: 'string' },
  sol_verdicts: { type: 'array', items: { type: 'object', required: ['sol_locator', 'sol_status', 'sol_criteria', 'verdict', 'per_criterion', 'reason'], properties: {
    sol_locator: { type: 'string', description: 'exactly as in the GPT-6 Sol index entry findings[].locator' },
    sol_status: { type: 'string' },
    sol_criteria: { type: 'array', items: { type: 'string' } },
    verdict: { type: 'string', enum: ['problematic', 'arguable', 'not_a_defect', 'mixed'] },
    per_criterion: { type: 'array', items: { type: 'object', required: ['criterion', 'verdict'], properties: {
      criterion: { type: 'string' }, verdict: { type: 'string', enum: ['problematic', 'arguable', 'not_a_defect'] } } } },
    reason: { type: 'string', description: '<=90 words, grounded in the record or law you checked' } } } },
  findings: { type: 'array', items: { type: 'object', required: FINDING_REQ.concat(['origin', 'sol_locators', 'blind_ids']), properties: Object.assign({}, FINDING_PROPS, {
    origin: { type: 'string', enum: ['blind', 'revised', 'adopted_after_reading_sol'] },
    sol_locators: { type: 'array', items: { type: 'string' } },
    blind_ids: { type: 'array', items: { type: 'string' } } }) } },
  changes_from_blind: { type: 'string', description: 'what changed after reading GPT-6 Sol and why; "none" if nothing' },
  overall: { type: 'string', description: '3-6 sentences' },
  coverage: { type: 'string' } } }
```
