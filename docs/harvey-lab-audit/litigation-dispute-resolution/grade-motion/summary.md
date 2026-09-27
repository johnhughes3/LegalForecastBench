# Motion actual-grade audit complete

> [!WARNING]
> **AI-generated, unverified analysis — for reference only.** This material reflects some human steering and guidance, but that does not constitute verification. It may contain factual, legal, citation, or grading errors. Labels such as “confirmed,” “definite,” or “verified” are AI reviewer claims, not human sign-off. See the [audit overview and model provenance](../README.md). Portions of the findings that have been verified will be described separately on the public-facing LegalForecastBench site.

Both actual DOCX outputs and all four native evaluations reviewed; 34 criteria × 2 outputs with saved coverage pointers. No raw artifact edits and no API reruns.

- Luna native: Sonnet31/34; GPT32/34. Both fail C001/C016; Sonnet alone also fails C025.
- Opus native: both30/34; both fail C015/C016/C025/C032.
- All four native task scores remain0 under all-pass aggregation.
- Strongest disputed false negative: Luna Sonnet C025 (equivalent severity language accepted by GPT, labels not requested). Opus C025 also shows risk-direction confusion in both judges.
- Faithful enforcement of defective/overprescriptive rubric: Luna C001 (no legal inconsistency in applying plausibility and9b), both models C016 (requires unconscionability despite statutory/other attacks).
- True omission: Opus C015 separate November2022 latency discovery.
- Mixed: Opus C032 lacks explicit filing date but does perform cutoff arithmetic; Sonnet overstates missing analysis, GPT adds all-four-date demand.
- Reviewed flagged passes are mostly supportable. C024 severity direction is ambiguous; no definite false-positive verdict established.
- Real output errors outside failed rows: both overstate absence of counsel evidence despite Whitford¶11; Opus P308 misstates UCC2.725's support for a one-year period; Opus blanket must-dismiss-without-prejudice recommendation is overbroad.

See findings.md for exact output quotations, native reasons, source pointers, primary-law URLs, and limits. See coverage.md for all34 criterion/native-verdict rows. This qualitative audit does not propose replacement grades or certify every legal theory/citation.
