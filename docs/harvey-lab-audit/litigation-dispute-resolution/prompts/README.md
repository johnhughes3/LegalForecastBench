# Audit prompt recovery

These are the reviewer instructions used to critique Harvey LAB, distinct from the benchmark prompts given to solvers and judges. The initial recovery was performed on October 19, 2026 from saved local session history and workflow source; a further session and backup search was performed on October 22. Machine-specific source locations are not published.

| Model and stage | Recovery | Saved evidence |
| --- | --- | --- |
| GPT-6 Sol, six initial audit workers | Exact task prompts not recovered | The coordinator's six dispatches and their worker records survive, but the delegated task bodies are encrypted in both copies. The records identify GPT-6 Sol at high reasoning. |
| Claude Opus 5.5, blind pass | Recovered workflow template | Common context, defect guide, blind instructions, and separately supplied output schema are preserved in [Opus audit prompts](opus-audit.md). |
| Claude Opus 5.5, reconciliation | Recovered workflow template | Same source preserves reconciliation instructions, schema, and optional earlier-notes wording for two tasks. |

The recovery checked the original Sol coordinator and six worker records, searched indexed session history, and inspected the surviving local audit source directory. No plaintext copy of the Sol task bodies was found. Their reports and batch summaries establish what they produced, but do not substitute for the instructions they received. We have not reconstructed a prompt from those outputs or inferred that its wording matched Opus's.

The October 22 search checked the original Codex session files, now compressed, and separate raw session backups captured on September 27, 2026 at approximately 07:05 UTC. Backups exist for the coordinator and all six initial Sol workers. These backups have no outer encryption, so their contents could be read directly: the coordinator's six dispatches still contain encrypted task bodies, and each worker's initial task contains a readable routing header followed by an `encrypted_content` field. The searchable session archive preserves only those routing headers; the six local thread metadata records contain no separate task text. This establishes that the checked backups preserve the same recovery gap, not that every possible historical copy has been exhausted.

### Why the task messages are encrypted

The observed record shape matches Codex's upstream Multi-Agent V2 encrypted delivery path. OpenAI's merged [change #26210](https://github.com/openai/codex/pull/26210), dated June 5, 2026, explicitly describes the mechanism: the Responses service encrypts the model-generated `message` argument before returning it to the client; Codex forwards and stores the ciphertext; Responses decrypts it internally for the recipient model. The change marks collaboration message parameters as encrypted and leaves the local inter-agent plaintext field empty. This is task-message encryption, distinct from private reasoning items.

Consequently, the exact worker instructions may never have existed as plaintext on the local computer. The human's request to delegate an audit is ordinary readable input; the coordinator model's subsequently generated worker instructions take this encrypted delivery path. A worker can receive and act on those instructions while the local client retains only ciphertext. The matching coordinator/worker records are consistent with that design, rather than showing that a local backup service encrypted previously readable task fields.

The separately configured age encryption protects entire offsite bundles. Its recovery identity decrypts those bundles, not OpenAI's encrypted collaboration messages. Restoring another copy of the same rollout cannot by itself reveal the task text. Further local recovery would require an independently saved plaintext instruction, such as a prompt file or explicit transcription. No such copy has been found. An upstream [auditability issue](https://github.com/openai/codex/issues/28058) reports this same loss of readable task history; a user-accessible plaintext export or decryption facility has not been established here.

### October 22 offsite and session-store investigation

The offsite inventory contained 293 Borg archives, including 264 session archives. Forty session archives postdated the six dispatches. Three candidate bundles were restored to private temporary storage, decrypted with the separately held age identity, decompressed, and scanned for the seven exact session IDs in member names and readable contents, and for separately named Harvey audit prompt, workflow, or request files. No original session store or remote backup was changed. The table identifies bundles by their decrypted manifest's UTC creation time; Borg's displayed archive times used a different timezone.

| Bundle manifest creation time (UTC) | Regular files scanned | Session-file dates present | Relevant surviving material |
| --- | ---: | --- | --- |
| 2026-09-27 09:13:24 | 1,228 | August 21–27 | Human command history and a coordinator index entry; no named coordinator or worker rollout. |
| 2026-10-21 04:45:11 | 43 | September 7–18 | No match for any of the seven session IDs. |
| 2026-10-22 09:12:16 | 58 | September 20 | Human command history; no named coordinator or worker rollout. |

The two matching command histories each retain 13 coordinator entries and no entries for the six worker IDs. Neither bundle contains a separately named Harvey prompt/workflow/request file. Decrypting the outer age bundles succeeded; this did not recover the missing inner task messages. The session-file date ranges describe actual contents, rather than an inference from the nominal 30-day local retention policy.

The remaining 37 candidate bundles were not restored. Payload listings succeeded for 33 of the 40 candidates before repeated remote DNS-resolution failures interrupted further archive access. This is an incomplete offsite search, not evidence that those uninspected bundles lack the prompts. Private inventory and scan results retain the exact archive locators; hostnames, account details, credentials, and machine-specific paths are excluded here.

The source machine's compressed coordinator and all six exact worker rollouts were also rechecked. The six initial `spawn_agent` messages are encrypted strings, and each worker's initial `agent_message` contains the readable `NEW_TASK` routing header followed by the same encrypted body as its dispatch. The nearby worker with the 20:12:35 filename was excluded. The source session-history database retains worker activity and coordinator subagent-start events, but those events contain identifiers rather than separate task text. Read-only `thread/items/list` requests against the source session service returned the first 20 stored items for each worker; these begin with reasoning and activity, without the initial task message. Checking the installed session API and its documented read methods did not identify a documented plaintext-decryption/export operation for these encrypted agent messages. This does not establish that provider-side recovery is impossible.

### Dispatch and Git chronology

The rollout filenames use September 26 local dates, while the records place the initial dispatches on September 27 UTC. All six identify `gpt-6-sol`, `high` reasoning, and `fork_turns: none`. Physical record numbers below refer to the rechecked coordinator copy and are locators, not stable identifiers across every historical copy.

| Worker | Dispatch time, September 27 UTC | Coordinator physical record |
| --- | --- | ---: |
| `audit_1` | 00:11:53.170 | 887 |
| `audit_2` | 00:12:02.670 | 893 |
| `audit_3` | 00:12:12.026 | 899 |
| `audit_4` | 00:12:21.462 | 905 |
| `audit_5` | 00:12:30.959 | 911 |
| `audit_6` | 00:12:42.651 | 917 |

Git history places the first original audit tree, including all six batches' task reports, at [d7815ea](https://github.com/johnhughes3/LegalForecastBench/commit/d7815ea13e02afcfe1b0a537d9b2fc15ddf96c9a), September 27 at 01:54:26 UTC. The normalized Sol reports and Opus comparison were added at [767de0c](https://github.com/johnhughes3/LegalForecastBench/commit/767de0c725a77bc2ea777ee32eb5e772a433407a), 04:36:43 UTC, and restored after a temporary removal at [2415d16](https://github.com/johnhughes3/LegalForecastBench/commit/2415d1637e780d255e991c6905a4dffd650194c7), 06:19:10 UTC. The committed audit builders ingest and render results; no original Sol dispatch prompt was found in the inspected Git refs. Commit times bound publication, not prompt creation or execution.

### Surviving human steering

Both restored command histories preserve this coordinator request at September 27, 00:08:20 UTC. The text below preserves spelling, capitalization, and spacing; no substitutions were made:

> OK can you delegate the rubric audit to SOl workers and  kick off the Luna full run -- (GPT -6 Luna xhigh) and can we try Opus 5.5 low as well (make sure cache is on) -- both only on litigation tasks. Let's then grade both and cpature any instances where they were graded wrong and audit those. Make sure we keep the data in pristine condition.

This is human steering before the initial Sol dispatches, not the task instructions delivered to the workers. It also requests separate benchmark runs; its reference to Opus low effort is not evidence about the later Opus audit's effort. It cannot establish the Sol workers' defect thresholds, required coverage, blinding rules, or output instructions. Any further historical search should target independently saved plaintext from between this request and 00:12:43 UTC, rather than assume that more rollout copies will decrypt the messages. The 37 unrestored bundles could contain a separate saved artifact, but identical rollout backups would preserve the ciphertext. Whether OpenAI offers recovery of these particular agent messages remains unverified; a provider export must not be presumed available. Their wording remains unrecovered and has not been inferred from reports or this human request.

The Opus source was checked against the coordinator's initial two-task workflow definition and its subsequent 50-task invocation. The archived text uses portable placeholders for runtime values; those substitutions and the limits of the recovery are explained with the prompt. This is not a complete record of every runtime message, tool interaction, or earlier human steering. The [main audit method](../README.md#claude-opus-55-audit-method) describes those limits and the distinction between blind and reconciled findings.

The [LegalReasonBench prompt archive](../../../legalreasonbench-audit/litigation/prompts/README.md) preserves both models' initial task instructions and its separate reconciliation instructions. The audits share a general defect-audit framework, but substantive prompt identity across the two audits cannot be established. In particular, the recovered Harvey Opus guide describes arguable findings as including ones that “would misgrade only some competent answers,” while also defining problematic findings to include failing a correct answer. LegalReasonBench explicitly directs the workers to apply the later human-review standard to permissible careful-litigator responses. The original wording overlaps; the later instruction clarifies the treatment rather than proving that every such Harvey finding was put in a different bucket. No effect on flag rates has been measured.
