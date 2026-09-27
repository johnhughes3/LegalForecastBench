# Blind rubric audit

> [!WARNING]
> **AI-generated, unverified analysis — for reference only.** This material reflects some human steering and guidance, but that does not constitute verification. It may contain factual, legal, citation, or grading errors. Labels such as “confirmed,” “definite,” or “verified” are AI reviewer claims, not human sign-off. See the [audit overview and model provenance](../../README.md). Portions of the findings that have been verified will be described separately on the public-facing LegalForecastBench site.

[Pinned task instructions and rubric](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-to-dismiss/task.json) · [Source documents](https://github.com/harveyai/harvey-labs/tree/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-to-dismiss/documents) · Commit `1dd81403b2fbb60596f7aea3fcecafad7bf73143`.

**F1 — confirmed — [C-007](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-to-dismiss/task.json#L70)**

PASS/FAIL conditions do not cover the same threshold.

Evidence: PASS requires both Twombly and Iqbal (or their standard); FAIL says neither mentioned. A brief naming one case leaves grader inconsistent instructions.

Repair: Use one unambiguous requirement, preferably correct plausibility standard rather than case-name count.

**F2 — arguable — [C-009](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-to-dismiss/task.json#L86), [C-011](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-to-dismiss/task.json#L102)**

Mandatory routine reformation formulation overstates Connecticut doctrine and is encouraged by misleading source memo.

Evidence: litigation-strategy-memo paragraphs 25–26 attributes flexible reasonable modification to Deming. D. Conn. Sunbelt Rentals opinion at pp.5–7 quotes Deming 279 Conn.745,769 n.21 as narrow severable-undertakings rule; broader rewriting appears in some trial decisions with express modification language. RCA section 8.5 supports a reformation argument here, but not an unqualified assertion that courts routinely reform overbroad covenants.

Repair: Credit accurate limited doctrine and express-clause argument without requiring overstated routine practice.

**F3 — arguable — [C-029](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-to-dismiss/task.json#L246), [C-031](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-to-dismiss/task.json#L262)**

Compulsory constructive-knowledge and 24-day-gap theories can penalize stronger, more careful advocacy.

Evidence: Strategy memo paragraphs 81–85 infers restrictive-covenant knowledge from industry practice and hiring timing. Complaint supplies those allegations, so these are not invented facts, but hiring 24 days later does not itself show contract knowledge. Connecticut interference law requires knowledge of the relevant relationship; constructive knowledge as stand-alone substitute has not been established by sources reviewed.

Repair: Accept reasonable actual-knowledge inference, knowledge of client relationships, or qualified argument; do not compel assertion that due-diligence omission proves knowledge.

**F4 — arguable — [C-038](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-to-dismiss/task.json#L318), [C-039](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-to-dismiss/task.json#L326)**

Requires characterizing promotional proprietary-insights language as quasi-admission of misuse.

Evidence: Lodestar press release paragraph 9 promotes operational expertise and proprietary insights. This is circumstantial material, not an express admission that information was taken or improperly used. Litigation strategy memo expressly requests recurring use, but court briefing can reasonably avoid overstating it.

Repair: Credit cautious circumstantial inference in either relevant claim section.

**F5 — arguable — [C-041](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-to-dismiss/task.json#L342), [C-042](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-to-dismiss/task.json#L350), [C-043](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-to-dismiss/task.json#L358), [C-044](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-to-dismiss/task.json#L366), [C-045](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-to-dismiss/task.json#L374), [C-046](https://github.com/harveyai/harvey-labs/blob/1dd81403b2fbb60596f7aea3fcecafad7bf73143/tasks/litigation-dispute-resolution/draft-opposition-to-motion-to-dismiss/task.json#L382)**

Exact section/heading and citation-placement rules go beyond requested opposition.

Evidence: Prompt specifies opposition memorandum, not five separately headed argument sections or complaint citations in three sections. A coherent issue-based combined section can answer every dismissal argument.

Repair: Score substantive responsiveness and source support without fixed heading/citation distribution.

Coverage: 63/63 criteria, 7/7 documents, criterion-directed source inspection. 63 criteria examined, all seven documents searched/read in relevant sections. Statutory DTSA nonpreemption and misappropriation definitions confirmed from chapter 90 primary text accessed during this batch. No conclusion that covenant reformation, fiduciary duty, standing, or plaintiff advocacy is categorically unavailable. Standalone constructive-knowledge sufficiency remains unresolved.

Legal sources:
- https://ecf.ctd.uscourts.gov/cgi-bin/show_public_doc?2021cv0774-34=
- https://www.jud.ct.gov/lawjournal/Docs/Misc/2023/41/CLJ10102023.pdf
- https://www.supremecourt.gov/opinions/20pdf/20-297_4g25.pdf
- https://uscode.house.gov/view.xhtml?edition=prelim&hl=false&num=0&path=%2Fprelim%40title18%2Fpart1%2Fchapter90&req=granuleid%3AUSC-prelim-title18-chapter90
