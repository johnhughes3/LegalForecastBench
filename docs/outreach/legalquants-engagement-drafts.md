# LegalQuants engagement drafts

Status: draft only — DO NOT SEND.

Authority: `LegalForecastBench-dm0g.7.5` prepares text; only John may approve, send, decline, or defer an external message under `LegalForecastBench-dm0g.7.6`.

Feedback-window close date: August 12, 2026.

These drafts contain no unpublished result, confidential artifact, private account information, or representation that LegalQuants reviewed or approved the design.

## Draft 1: immediate reply

Suggested subject: Claude Code and Harvey LAB comparison design

Jamie — yes, this is the comparison we are preparing to test.

Our intended primary design would preserve Claude Code's native tools and agent loop inside an outer containment boundary. It would not replace them with the thinner task tool interface. The design remains subject to feasibility and methods review, so we are not presenting it as final.

We have not finalized the stratified-pilot task or arm selection, and we have not observed any stratified-pilot score.

Before we freeze the task and arm selection, we would welcome public input from you and LegalQuants. We are especially interested in the most informative task strata, the matched comparisons that matter to practitioners, and useful coverage or failure summaries.

The input window closes on August 12, 2026, before any stratified-pilot score is observed. A response is not required for the work to continue: we will close the window on that date as feedback received, no response, or a decision not to send, then commit the final pilot specification before scoring.

LegalForecastBench is an independent project. Harvey AI, Harvey LAB, and LegalQuants are not sponsors, partners, or endorsers of this work.

If useful, we can share the public proposed-shard record once it is populated and ready for pre-freeze review.

— John

## Draft 2: preliminary-result follow-up

Send only after the linked artifact has passed its required validation, privacy, claims, and release approvals and while the input window remains open.

Suggested subject: Preliminary Claude Code and Harvey LAB artifact

Jamie — following up with the validated public artifact we discussed: [VALIDATED_PUBLICATION_URL]

Its exact evidence label is: **Preliminary — one task pair, operator-run, not independently reproducible**.

This artifact covers one pinned task pair. It reports only the task, treatment identities, compatibility facts, score and coverage, cost basis, token dimensions, wall-clock time, attempts, retries, failures, and limitations supported by the artifact: [OBSERVED_FACTS_COPIED_VERBATIM_FROM_VALIDATED_PUBLICATION].

If the input window is still open, we would welcome public comments on the proposed stratified-pilot shard before its task and arm selection is frozen and before any stratified-pilot score is observed. The window closes on August 12, 2026; the work does not wait indefinitely for a response.

LegalForecastBench is an independent project. Harvey AI, Harvey LAB, and LegalQuants are not sponsors, partners, or endorsers of this work.

— John

## Review gates

### Send authority

- Repository drafting is not send authority.
- John must approve the exact rendered message and either send it himself or record a decline/defer decision in `LegalForecastBench-dm0g.7.6`.
- Do not send a message containing an unresolved bracketed placeholder.
- Do not collect or archive private account information; retain only a public permalink if a public message is sent.

### Methods review

- Confirm the immediate draft describes native-tools preservation as intended and subject to feasibility, not as a completed treatment.
- Confirm pilot task and arm selection remain unfrozen and no stratified-pilot score has been observed.
- Confirm feedback can affect the pilot only before selection, freeze, and score observation.
- Confirm the window closes on August 12, 2026 as feedback received, no response, or John declining to send, and no response is required for engineering to continue.
- Confirm the proposed-shard record captures task strata, exact task IDs, selection hash, arms, model matching, randomized order, repeats, failure policy, coverage floor, uncertainty, budget, stopping rule, deterministic-selection evidence, balance diagnostics, order-generation golden evidence, and budget simulation before its immutable proposal commit.

Methods reviewer: `[NAME / DATE / APPROVED OR FINDINGS]`

### Claims, confidentiality, and non-affiliation review

- Confirm the immediate draft contains no score, result, private artifact, confidential detail, causal claim, or superiority claim.
- Confirm the follow-up links only a validated public artifact, reproduces its exact evidence label, and copies only supported facts from that artifact.
- Confirm both drafts use the frozen non-affiliation text verbatim and do not imply review, approval, sponsorship, endorsement, or partnership.
- Confirm no unpublished URL, credential, local path, private account identifier, or non-public feedback is present.

Claims/non-affiliation reviewer: `[NAME / DATE / APPROVED OR FINDINGS]`

## Recording workflow

1. Copy `legalquants-proposed-shard.template.json` to the pilot's public pre-freeze evidence directory, populate every `TBD_BEFORE_PROPOSAL_COMMIT` value, and commit that proposal before selection freezes or any stratified-pilot score is observed.
2. Treat the committed proposed-shard record as immutable. Record its path and hash in the separate feedback record; never backfill the proposal with the later final-spec hash or diff.
3. Copy `legalquants-feedback-record.template.json` into the same evidence directory and record John's send, decline, or defer decision. If sent, record the approved-text hash, sent-text hash, exact-text match, timestamp, and public outbound permalink without private contact data.
4. Record each public suggestion, receipt time, accepted, partially accepted, rejected, or not-applicable disposition, methods rationale, disposition time, and whether disposition preceded selection freeze.
5. Close the window on August 12, 2026 as feedback received, no response, or John declined send; never wait for a response to exist.
6. After the window closes and every feedback item is dispositioned, commit the final frozen specification before score observation. Record whether a separate Tier-0 result informed any change, the final frozen-spec path and hash, the diff from the immutable proposed shard, the freeze time, and the pre-score commitment state in the feedback record.
