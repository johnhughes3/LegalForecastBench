# First Luna hold memo: grade audit

> [!WARNING]
> **AI-generated, unverified analysis — for reference only.** This material reflects some human steering and guidance, but that does not constitute verification. It may contain factual, legal, citation, or grading errors. Labels such as “confirmed,” “definite,” or “verified” are AI reviewer claims, not human sign-off. See the [audit overview and model provenance](../README.md). Portions of the findings that have been verified will be described separately on the public-facing LegalForecastBench site.

Blind batch findings were completed and saved before reading this solver output or judge results. This follow-up reads the actual output DOCX as paragraph text and both native judge result files. It does not change raw output, grades, tasks or runtime files.

Run: `repo/results/litigation-dispute-resolution/assess-litigation-hold-scope-for-custodian-identification/gpt6luna-xhigh/20260926-201603`. Actual artifact: `output/litigation-hold-memo.docx`. Text evidence with paragraph numbers: luna-hold-output.txt (local extraction; not included). Paragraph numbers include table-cell paragraphs and are XML extraction pointers, not document page numbers.

Native GPT-5.5 result is 48/50; Sonnet4.6 is47/50. Native mean is95%, and both all-pass task scores are0. I recommend sustaining two substantive failures and reversing Sonnet C-034. This would make an audit-adjusted criterion mean96% (48/50 for each judge), while the all-pass task result remains0. These are review recommendations, not overwritten native scores.

## Failed criteria adjudication

| Criterion | Native results | Audit recommendation | Classification |
|---|---|---|---|
| C-028 engagement scope gap | Both fail | Sustain | True model omission |
| C-041 General Counsel custodian | Both fail | Sustain | True model omission |
| C-034 SOX scope connection | GPT pass / Sonnet fail | Pass; reverse Sonnet | Judge overreading, aided by ambiguous rubric |

**C-028:** The engagement letter §1 expressly excludes matters beyond defense of the Kovach claims absent separate written agreement; its date is October18, preceding the October28 SEC letter. The memo distinguishes the Audit Committee investigation from the employment-defense engagement (paragraph214) and tracks SEC versus employment evidence separately (16,46). Neither distinction identifies the missing SEC engagement authorization. Paragraph223 assigns SEC strategy coordination to outside counsel without flagging the scope gap. Both judge failures are supported; treating this as satisfied by general separate-matter administration would conflate different issues.

**C-041:** Monica Tran-Nguyen is an addressee (paragraph5) and owner of legal/response decisions (220–221), but the custodian table (52–106) omits her. Instructions to preserve general governance/counsel repositories do not distinctly preserve the General Counsel's own demand-letter, SEC-response and coordination records. Because this is a custodian-identification memo and source correspondence establishes her relevant possession, both failures identify a real omission, even though broad organizational preservation may incidentally capture copies.

**C-034:** Sonnet says an explicit connection to “broader or more protective” obligations is required. The criterion is disjunctive: it accepts a connection between the SOX theory and preservation of complaint/retaliation communications, **or** the broader-obligations proposition. Paragraph21 identifies the accounting-complaint retaliation matter as including SOX806, and in the same paragraph states that the Kovach matter additionally requires employment, complaint, investigation and termination evidence. Paragraph47 implements that scope;74–76 and211–214 preserve the Audit Committee report and response. This is an intelligible contextual connection. Sonnet even acknowledges the specified substantive records are preserved, then demands greater express legal phrasing. I would credit it, as GPT did. A strict reader could find the SOX-specific causal explanation thin, so this is a reasoned adjudication rather than proof that any fail is impossible. Do not repair the response by insisting on a special SOX preservation standard: ordinary preservation relevance to the claim is the sound explanation. The blind audit already classified the rubric's broader-obligations alternative as imprecise. [18USC1514A primary text](https://www.govinfo.gov/content/pkg/USCODE-2020-title18/pdf/USCODE-2020-title18-partI-chap73-sec1514A.pdf).

## Passed-criterion checks and limits

I checked all50 criteria against the actual memo and read all100 native criterion reasons. No additional confirmed false-positive pass emerged. The following apparent mismatches deserve explicit treatment:

- C-013: memo uses November6/August8 cutoff, matching an earlier source update, rather than updating to November8/August10. That is a minor stale-date issue. It nevertheless specifically assesses June/July chats as outside90days and likely lost, satisfying the criterion's substantive alternative. Sonnet's reasoning inaccurately calls November6 “the current date”; correct that reason, not necessarily the verdict.
- C-046: migration date is conveyed indirectly by complementary pre-April1 archive and April1-onward M365 descriptions, adjacent to migration discussion. Passing this is reasonable.
- C-047:421/~2800 is15.04%, so numeric equivalence supports pass despite not printing15%.
- C-029/C-030: thirteen-day proximity and targeted July2–15 decision-maker records are expressly present. No need to require the magic word “causation.”
- C-009: the blind rubric defect leaves one/two of three regional managers undefined. Here all three are expressly included, so the defect does not affect this grade.
- C-049: the memo appropriately preserves investigation materials while reserving document-specific privilege review. It should not be failed for declining to pronounce every underlying record privileged.

This is a text/substance audit. I did not render the DOCX to validate pagination, table overflow or visual quality, and did not rerun a judge. The audit-adjusted96% remains an all-pass failure because C-028 and C-041 remain genuine omissions.

## Complete criterion evidence map

| Criterion | GPT | Sonnet | Audit | Output paragraphs |
|---|---|---|---|---|
| C-001 | pass | pass | pass | 56–58 |
| C-002 | pass | pass | pass | 59–61 |
| C-003 | pass | pass | pass | 65–67 |
| C-004 | pass | pass | pass | 68–70 |
| C-005 | pass | pass | pass | 71–73 |
| C-006 | pass | pass | pass | 62–64 |
| C-007 | pass | pass | pass | 74–76,211–214 |
| C-008 | pass | pass | pass | 211–214 |
| C-009 | pass | pass | pass | 77–85 |
| C-010 | pass | pass | pass | 86–88 |
| C-011 | pass | pass | pass | 52,77–94 |
| C-012 | pass | pass | pass | 123–125,168–171 |
| C-013 | pass | pass | pass | 124,170 |
| C-014 | pass | pass | pass | 125,204 |
| C-015 | pass | pass | pass | 171 |
| C-016 | pass | pass | pass | 118–121,176–179 |
| C-017 | pass | pass | pass | 118–121 |
| C-018 | pass | pass | pass | 121,178–179 |
| C-019 | pass | pass | pass | 138–141,180–183 |
| C-020 | pass | pass | pass | 141,183 |
| C-021 | pass | pass | pass | 146–149 |
| C-022 | pass | pass | pass | 149,206 |
| C-023 | pass | pass | pass | 186–187 |
| C-024 | pass | pass | pass | 130–133,172–175 |
| C-025 | pass | pass | pass | 133,175 |
| C-026 | pass | pass | pass | 16,45–48 |
| C-027 | pass | pass | pass | 89–103 |
| C-028 | fail | fail | fail | 38,104–106,214,223 (gap omitted) |
| C-029 | pass | pass | pass | 25–28 |
| C-030 | pass | pass | pass | 28,67 |
| C-031 | pass | pass | pass | 18,22,29–36 |
| C-032 | pass | pass | pass | 17–18,38–44,201 |
| C-033 | pass | pass | pass | 21 |
| C-034 | pass | fail | pass | 21,47,74–76,211–214 |
| C-035 | pass | pass | pass | 114–117 |
| C-036 | pass | pass | pass | 122–125 |
| C-037 | pass | pass | pass | 130–133 |
| C-038 | pass | pass | pass | 134–137 |
| C-039 | pass | pass | pass | 138–141 |
| C-040 | pass | pass | pass | 142–145 |
| C-041 | fail | fail | fail | 5,220–221 (administrative role only) |
| C-042 | pass | pass | pass | 19,168–199,235–239 |
| C-043 | pass | pass | pass | 123–125 |
| C-044 | pass | pass | pass | 132 |
| C-045 | pass | pass | pass | 140–141 |
| C-046 | pass | pass | pass | 115,119–120 |
| C-047 | pass | pass | pass | 120 |
| C-048 | pass | pass | pass | 38,226–227 |
| C-049 | pass | pass | pass | 32,104–106,211–214 |
| C-050 | pass | pass | pass | 123 |
