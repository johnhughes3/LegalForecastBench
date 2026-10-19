# Audit prompt recovery

These are the reviewer instructions used to critique Harvey LAB, distinct from the benchmark prompts given to solvers and judges. The recovery was performed on October 19, 2026 from saved local session history and workflow source. Machine-specific source locations are not published.

| Model and stage | Recovery | Saved evidence |
| --- | --- | --- |
| GPT-6 Sol, six initial audit workers | Exact task prompts not recovered | The coordinator's six dispatches and their worker records survive, but the delegated task bodies are encrypted in both copies. The records identify GPT-6 Sol at high reasoning. |
| Claude Opus 5.5, blind pass | Recovered workflow template | Common context, defect guide, blind instructions, and separately supplied output schema are preserved in [Opus audit prompts](opus-audit.md). |
| Claude Opus 5.5, reconciliation | Recovered workflow template | Same source preserves reconciliation instructions, schema, and optional earlier-notes wording for two tasks. |

The recovery checked the original Sol coordinator and six worker records, searched indexed session history, and inspected the surviving local audit source directory. No plaintext copy of the Sol task bodies was found. Their reports and batch summaries establish what they produced, but do not substitute for the instructions they received. We have not reconstructed a prompt from those outputs or inferred that its wording matched Opus's.

The Opus source was checked against the coordinator's initial two-task workflow definition and its subsequent 50-task invocation. The archived text uses portable placeholders for runtime values; those substitutions and the limits of the recovery are explained with the prompt. This is not a complete record of every runtime message, tool interaction, or earlier human steering. The [main audit method](../README.md#claude-opus-55-audit-method) describes those limits and the distinction between blind and reconciled findings.

The [LegalReasonBench prompt archive](../../../legalreasonbench-audit/litigation/prompts/README.md) preserves both models' initial task instructions and its separate reconciliation instructions. The audits share a general defect-audit framework, but substantive prompt identity across the two audits cannot be established. In particular, the recovered Harvey Opus guide describes arguable findings as including ones that “would misgrade only some competent answers,” while also defining problematic findings to include failing a correct answer. LegalReasonBench explicitly directs the workers to apply the later human-review standard to permissible careful-litigator responses. The original wording overlaps; the later instruction clarifies the treatment rather than proving that every such Harvey finding was put in a different bucket. No effect on flag rates has been measured.
