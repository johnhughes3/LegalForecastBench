# Draft Federal Complaint for Trade Secret Misappropriation and Breach of Employment Agreement

> [!WARNING]
> **AI-generated, unverified analysis — for reference only.** This material reflects some human steering and guidance, but that does not constitute verification. It may contain factual, legal, citation, or grading errors. Labels such as “confirmed,” “definite,” or “verified” are AI reviewer claims, not human sign-off. See the [audit overview and model provenance](../../README.md). Portions of the findings that have been verified will be described separately on the public-facing LegalForecastBench site.

Rendered from [findings.json](findings.json); the original AI classifications and qualifications are retained.

**Id:** B6-DC-1

**Status:** confirmed

**Severity:** high

## Criteria

- C-027

**Issue:** Requires inventing North Carolina TSPA statutory preemption.

**Basis:** C-027 cites §66-157(a) as a preemption provision. Official Article 24 contains no such subsection; §66-157 is solely the three-year limitations provision. No displacement provision appears in this Act. A drafter correctly rejecting this assumed statutory preemption can fail.

## Source pointers

- task.json C-027; compare C-024 correctly describing §66-157

## Legal urls

- https://www.ncleg.gov/EnactedLegislation/Statutes/HTML/ByArticle/Chapter_66/Article_24.html

**Repair:** Remove mandatory preemption warning or require only supported independent overlap/duplicative-remedy analysis.


**Id:** B6-DC-2

**Status:** confirmed

**Severity:** medium

## Criteria

- C-023

**Issue:** Required causal story conflicts with the packet chronology and contract.

**Basis:** All identified exfiltration occurred October 27–November 15; notice was November 18. Showalter memo §IV itself describes compliance as moving departure to January 17, not earlier notice. Contract §7.3 permits access restrictions immediately on notice; seven additional January days cannot prevent pre-notice October/November transfers. The short notice breach is supportable; the required claim it deprived Verdant of an earlier opportunity to restrict access and prevent exfiltration is not.

## Source pointers

- sentinel-forensics-report.docx chronological context and timeline, sources.txt:285,411
- showalter-memo-to-counsel.docx §IV, sources.txt:513
- tate-employment-agreement.docx §7.3, sources.txt:779–790

## Legal urls



**Repair:** Credit breach analysis and explicit rejection of unsupported exfiltration causation; permit investigation/detection harm if supported.


**Id:** B6-DC-3

**Status:** arguable

**Severity:** medium

## Criteria

- C-045
- C-057

**Issue:** Mandates prospective-interference claim and quantified damages despite estimates rather than identified lost transactions.

**Basis:** Showalter memo requests these theories; Heartland reports a presentation, not a lost contract. Employee loss figure expressly assumes losing three scientists; the declarations describe recruitment without established departures. These are theories to investigate, not necessarily viable accrued damages. A companion memo qualifying allegations should receive credit.

## Source pointers

- showalter-memo-to-counsel.docx §§VII–IX, sources.txt:542–562
- damages-analysis-summary.xlsx damages assumptions
- kowalski-declaration.docx; okonkwo-declaration.docx

## Legal urls



**Repair:** Allow well-reasoned omission of premature claim and qualification of projected losses; do not compel unsupported actual-loss allegations.
