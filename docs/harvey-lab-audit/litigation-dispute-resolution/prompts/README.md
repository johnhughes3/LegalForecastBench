# Auditor instructions and provenance

These are the reviewer instructions used to critique Harvey LAB, distinct from the benchmark prompts given to solvers and judges. The archive preserves the human request for the Sol audit and the saved Opus workflow templates. Sol generated its own delegated worker prompts; their exact wording was not controlled by the human investigator and is unavailable in our records.

## Human instruction for the Sol audit

The coordinator's saved human-input history records the following request at September 27, 2026, 00:08:20 UTC. Spelling, capitalization, and spacing are preserved; no substitutions were made:

> OK can you delegate the rubric audit to SOl workers and  kick off the Luna full run -- (GPT -6 Luna xhigh) and can we try Opus 5.5 low as well (make sure cache is on) -- both only on litigation tasks. Let's then grade both and cpature any instances where they were graded wrong and audit those. Make sure we keep the data in pristine condition.

The Sol coordinator then generated and dispatched task instructions to six GPT-6 Sol workers, each with high reasoning and no inherited conversation history (`fork_turns: none`). We did not prescribe or control the exact wording of those model-generated worker instructions. The human request above is the documented human input, not a transcription of the worker prompts. It also requested separate solver runs; its reference to Opus low effort does not describe the later Opus audit, which requested high effort.

## Availability of the generated worker instructions

OpenAI's merged [Codex change #26210, “Encrypt multi-agent v2 message payloads”](https://github.com/openai/codex/pull/26210) explains that the Responses service encrypts the model-generated collaboration `message` before returning it to the client. Codex stores and forwards the ciphertext, and Responses decrypts it internally for the recipient model. The change deliberately leaves the local plaintext field empty. These are agent-to-agent task instructions, distinct from private reasoning items.

The surviving coordinator and worker records match that delivery path: the dispatches contain encrypted message strings, and the workers' initial records contain readable task-routing headers followed by `encrypted_content`. The exact instructions are therefore unavailable to us from these records; they need not ever have existed as plaintext on the local computer. This encryption comes from OpenAI's agent communication mechanism, separately from any encryption protecting local backups. We have not reconstructed the worker prompts from their reports or treated the human request as their exact wording.

## Saved Opus instructions

The [Opus audit prompts](opus-audit.md) preserve the common context, defect guide, blind and reconciliation templates, and separately supplied output schemas. These were recovered on October 19, 2026 from saved workflow source and coordinator dispatches. The source was checked against the initial two-task workflow definition and its subsequent 50-task invocation. Portable placeholders replace runtime paths and template values; the substitutions are disclosed with the prompts.

This archive is not a complete record of every runtime message, tool interaction, or earlier human steering. The [main audit method](../README.md#claude-opus-55-audit-method) describes those limits and distinguishes blind from reconciled findings.

## Comparability

The [LegalReasonBench prompt archive](../../../legalreasonbench-audit/litigation/prompts/README.md) preserves both models' initial task instructions and its separate reconciliation instructions. The audits share a general defect-audit framework, but substantive prompt identity across the two audits cannot be established. In particular, the recovered Harvey Opus guide describes arguable findings as including ones that “would misgrade only some competent answers,” while also defining problematic findings to include failing a correct answer. LegalReasonBench explicitly directs the workers to apply the later human-review standard to permissible careful-litigator responses. The original wording overlaps; the later instruction clarifies the treatment rather than proving that every such Harvey finding was put in a different bucket. No effect on flag rates has been measured.
