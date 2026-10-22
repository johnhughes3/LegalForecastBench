# Audit prompt recovery and comparability

The [recovered task instructions](audit-prompts.md) preserve the common blind prompt, all four model/scope suffixes, and the separate reconciliation prompt. They were recovered on October 19, 2026 from saved worker messages and the coordinator's recorded dispatch. The four blind workers received an identical common instruction block; only the assigned matters, model identification, and output filename differed. Both models were instructed to use high reasoning or effort, review the same inputs, and avoid the other LegalReasonBench reviewers' findings.

This documents the initial task prompts, not identical complete runtime contexts. Workers read different assigned matters, made their own tool calls, and received source material as extraction and visual transcription proceeded. The blind instructions explicitly asked them to read the Harvey audit README, its human-review definitions, and a sample Harvey Opus finding schema: they were blind to the other LegalReasonBench pass, not to the prior Harvey audit. The [main method](../README.md#review-method) records actual reading limits and a source-quote exposure between the two Opus matter lanes. Reconciliation was not blind and did not overwrite either initial report.

The [Harvey recovery](../../../harvey-lab-audit/litigation-dispute-resolution/prompts/README.md) preserves the original Opus blind and reconciliation templates; its exact Sol task prompts remain unrecovered after checking both the original session files and separate raw backups on October 22. The checked backups also contain encrypted task bodies. We therefore cannot certify that the two audits used substantively identical prompts. The recovered instructions show these differences:

| Dimension | Harvey Opus template | LegalReasonBench initial instruction |
| --- | --- | --- |
| Status threshold | Problematic includes failing a correct answer or rewarding a wrong one; arguable also includes findings that “would misgrade only some competent answers.” | Explicitly applies the later human-review definitions: problematic includes rejecting a permissible careful-litigator response. |
| Record coverage instruction | Read key documents fully; search the remainder of large records for relevant facts. | Read all attachment text, earlier same-matter prompts, and accumulated attachments; actual selective reading is disclosed separately. |
| Dataset-specific checks | General legal, factual, instruction, and document defects. | Adds explicit sequential-dependency and penalty-misfire checks within the seven categories. |
| Category schema | Seven named categories plus `other` allowed by the supplied schema. | Seven named categories only. |
| Prior audit context | Blind worker prohibited from reading other Harvey audit or commentary. | Read the Harvey method, human-review definitions, and a sample Harvey Opus schema; avoid other LegalReasonBench findings. |
| Published comparison stage | Sol versus Opus's final position after reviewing Sol. | Both blind positions; subsequent reconciliation counted separately. |

The overlapping status language in the Harvey prompt does not prove a uniform historical classification rule. LegalReasonBench makes the later permissible-response standard explicit; this may affect individual buckets, but no causal effect on the observed rates has been measured. These are related audits using the same general taxonomy, not a controlled replication with identical instructions. Neither supplies a verified error rate.
