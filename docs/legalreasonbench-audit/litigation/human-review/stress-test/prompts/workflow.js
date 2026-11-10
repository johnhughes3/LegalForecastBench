export const meta = {
  name: 'lrb-human-review-stress-test',
  description: 'Stress-test 25 LegalReasonBench human-review calls, two consistency passes, then an independent Codex review',
  phases: [
    { title: 'Per-item', detail: 'one Opus agent per sampled criterion', model: 'opus' },
    { title: 'Consistency', detail: 'Opus and Fable consistency passes in parallel' },
    { title: 'Codex', detail: 'Opus agent obtains and assesses an independent Codex review', model: 'opus' },
  ],
}

const ROOT = 'docs/legalreasonbench-audit/litigation/human-review/stress-test'
const pad = n => String(n).padStart(2, '0')

const ITEM_SCHEMA = {
  type: 'object',
  properties: {
    item: { type: 'integer' },
    recorded: { type: 'object', properties: { verdict: { type: 'string' }, ai_reasoning: { type: 'string' }, basis: { type: 'string' }, env_origin: { type: 'string' }, environment: { type: 'string' } }, required: ['verdict', 'ai_reasoning', 'environment'] },
    recommended: { type: 'object', properties: { verdict: { type: 'string' }, ai_reasoning: { type: 'string' }, basis: { type: 'string' }, env_origin: { type: 'string' }, environment: { type: 'string' } }, required: ['verdict', 'ai_reasoning', 'environment'] },
    change_type: { type: 'string', enum: ['none', 'note_only', 'clerical', 'substantive_field_change'] },
    changed_fields: { type: 'array', items: { type: 'string' } },
    strongest_objection: { type: 'string' },
    objection_answered_by_note: { type: 'string', enum: ['yes', 'partly', 'no', 'n/a'] },
    stronger_arguments: { type: 'string' },
    errors_in_note: { type: 'array', items: { type: 'string' } },
    headline: { type: 'string' },
    confidence: { type: 'string', enum: ['low', 'medium', 'high'] },
    report_path: { type: 'string' },
  },
  required: ['item', 'recorded', 'recommended', 'change_type', 'strongest_objection', 'objection_answered_by_note', 'errors_in_note', 'headline', 'confidence', 'report_path'],
}

const CONSISTENCY_SCHEMA = {
  type: 'object',
  properties: {
    model: { type: 'string' },
    bottom_line: { type: 'string' },
    findings: { type: 'array', items: { type: 'object', properties: {
      title: { type: 'string' }, items: { type: 'array', items: { type: 'integer' } },
      importance: { type: 'string', enum: ['high', 'medium', 'low'] },
      recommendation: { type: 'string' },
      change_type: { type: 'string', enum: ['note_only', 'clerical', 'substantive_field_change', 'reporting'] },
    }, required: ['title', 'items', 'importance', 'recommendation', 'change_type'] } },
    arguable_boundary_view: { type: 'string' },
    report_path: { type: 'string' },
  },
  required: ['model', 'bottom_line', 'findings', 'arguable_boundary_view', 'report_path'],
}

const CODEX_SCHEMA = {
  type: 'object',
  properties: {
    codex_cli_version: { type: 'string' },
    model_used: { type: 'string' },
    reasoning_effort: { type: 'string' },
    web_search_enabled: { type: 'string' },
    exit_status: { type: 'string' },
    findings: { type: 'array', items: { type: 'object', properties: {
      title: { type: 'string' }, items: { type: 'array', items: { type: 'integer' } },
      codex_position: { type: 'string' },
      assessment: { type: 'string', enum: ['holds', 'partly_holds', 'misunderstood', 'unverifiable'] },
      note: { type: 'string' },
      change_type: { type: 'string', enum: ['none', 'note_only', 'clerical', 'substantive_field_change', 'reporting'] },
    }, required: ['title', 'items', 'codex_position', 'assessment', 'note'] } },
    codex_misunderstandings: { type: 'array', items: { type: 'string' } },
    bottom_line: { type: 'string' },
  },
  required: ['codex_cli_version', 'model_used', 'reasoning_effort', 'exit_status', 'findings', 'bottom_line'],
}

const ITEMS = Array.from({ length: 25 }, (_, i) => i + 1)

const perItem = pipeline(ITEMS, n => agent(
  `Read and follow the instructions in ${ROOT}/prompts/01-per-item-stress-test.md exactly, with {{N}} = ${n} and {{NN}} = ${pad(n)}. ` +
  `Write your report to ${ROOT}/items/item-${pad(n)}.md, then return the structured summary.`,
  { label: `item-${pad(n)}`, phase: 'Per-item', schema: ITEM_SCHEMA, model: 'opus', effort: 'high' },
))

const consistency = parallel(['opus', 'fable'].map(m => () => agent(
  `Read and follow the instructions in ${ROOT}/prompts/02-consistency-pass.md exactly, with {{MODEL}} = ${m}. ` +
  `Write your report to ${ROOT}/consistency/${m}.md, then return the structured summary.`,
  { label: `consistency-${m}`, phase: 'Consistency', schema: CONSISTENCY_SCHEMA, model: m, effort: 'high' },
)))

const [items, cons] = await Promise.all([perItem, consistency])
const doneItems = items.filter(Boolean)
log(`Per-item reports: ${doneItems.length}/25; consistency passes: ${cons.filter(Boolean).length}/2`)
const missing = ITEMS.filter(n => !doneItems.some(r => r.item === n))
if (missing.length) log(`Missing per-item results: ${missing.join(', ')}`)

phase('Codex')
const codex = await agent(
  `Read and follow the instructions in ${ROOT}/prompts/03-codex-orchestrator.md exactly. ` +
  (missing.length ? `Note: per-item reports for items ${missing.join(', ')} did not complete; tell Codex so. ` : '') +
  `Then return the structured summary.`,
  { label: 'codex-review', phase: 'Codex', schema: CODEX_SCHEMA, model: 'opus', effort: 'high' },
)

return { items: doneItems, missing, consistency: cons.filter(Boolean), codex }
