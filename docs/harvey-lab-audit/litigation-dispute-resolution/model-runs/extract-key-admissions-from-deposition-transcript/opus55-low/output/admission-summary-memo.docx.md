<!-- Rendered from admission-summary-memo.docx for reading; the original file is the deliverable. -->

**PRIVILEGED & CONFIDENTIAL — ATTORNEY WORK PRODUCT**

*Prepared in Anticipation of Litigation / Subject to Protective Order*

**MEMORANDUM**

| **TO:**      | Victoria Pratt; Nathan Oshiro — Hargrove, Lennox & Pratt LLP (Counsel for Plaintiff CMS)                                                                                                                                                                                                                            |
|--------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **FROM:**    | Litigation Team                                                                                                                                                                                                                                                                                                     |
| **DATE:**    | \[Insert date\]                                                                                                                                                                                                                                                                                                     |
| **RE:**      | Corbin Machining Solutions, Inc. v. Derek Yoon and Pinnacle Automation Group, LLC, Kent County Circuit Court Case No. 24-CV-10583 — Deposition Admission Summary, Contradictions Analysis, and Recommended Next Steps (Deposition of Derek Yoon, Vols. I–II, Jan. 14–15, 2025)                                      |
| **SOURCES:** | Yoon Dep. Vol. I (Jan. 14, 2025); Yoon Dep. Vol. II (Jan. 15, 2025); Yoon Answers to First Interrogatories (served Nov. 1, 2024); Ridgepoint Forensic Report RDF-2024-0387 (Oct. 15, 2024); Employment Agreement (Mar. 4, 2019); Cease-and-Desist Letter (Aug. 22, 2024); Separation Acknowledgment (Aug. 28, 2024) |

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

*Citation conventions: “Vol. I at \_\_” cites the Volume I transcript page (Volume I is not line-numbered). “Vol. II \_\_:\_\_” cites Volume II page:line. “Rog \_\_” cites Yoon’s sworn interrogatory answers. “FR §\_\_” cites the Ridgepoint forensic report. “EA §\_\_” cites the Employment Agreement. “SA §\_\_” cites the Separation Acknowledgment. “C&D” cites the August 22, 2024 letter. The transcripts are unsigned; Yoon reserved read-and-sign (30 days), so all testimony below remains subject to errata.*

# I. Executive Summary

Across two days of testimony, Yoon made concessions that, combined with the forensic record and his own signed documents, substantially establish every core element of CMS’s claims: a binding 150-mile / 18-month non-compete he admits signing and understanding; employment with a direct competitor 142 miles away; unauthorized removal of source code and the Blue Book; a false return-of-property certification; materially inaccurate sworn interrogatory answers; hands-on work on the competing product; and the destruction of his phone data ten days after an express preservation demand. His explanations shifted repeatedly under examination and are contradicted by objective evidence.

**Most significant admissions and findings:**

- **Non-compete.** Signed and read the Employment Agreement without negotiating; understood it remained operative through August 2024; admits Troy is ~142 miles from CMS HQ (Vol. I at 19–28; Vol. II 295:21–296:1). His “100-mile” belief is refuted by the C&D (Aug. 22) and the Separation Acknowledgment (Aug. 28), both of which recite the 150-mile radius before he started at PAG.

- **Source code exfiltration.** Admits connecting his USB drive and copying files on August 10, 2024 without authorization; cannot name a single “personal” file; drive is still at his home and has not been returned (Vol. I at 102–110; Vol. II 332:15–19). The forensic report shows all 3,847 files were source code, headers, config, and markdown — including HarmonicPath and AdaptGrip firmware — copied from a full repository clone made the day before (FR §§5.1, 5.4.1).

- **Blue Book.** Admits the email went from his authenticated CMS account to his personal Gmail; admits the Blue Book is Proprietary Information under EA §8; moved from “don’t recall” to “may have forwarded it inadvertently” (Vol. I at 132–135). Forensics show a newly composed, blank-subject, blank-body message — the only such email in August (FR §5.2).

- **False certifications.** Admits he did not return the USB drive and did not disclose the Blue Book email when signing the Separation Acknowledgment; claims he “forgot” both (Vol. I at 176–180).

- **Interrogatories.** Concedes Rog 4 (first PAG contact) and Rog 12 (no involvement in CNC development) were not accurate (Vol. I at 63–64; Vol. II 302:14–303:16; 325:13–16). Rogs 3, 6, 7, 11, and 15 are also contradicted by his testimony or the forensic record.

- **Competing work.** Attended a MillEdge Pro architecture review on his second day, offered optimization-engine suggestions, made 11 commits (including “optimization engine refactor” and “engagement angle calculation — harmonic analysis integration”), helped with launch reviews, and described MillEdge Pro’s method using the verbatim HarmonicPath phrase “harmonic frequency matching for tool engagement angles,” for which he could identify no outside source (Vol. II 298–325; 318:20–321:24; 343:1–9).

- **PAG knowledge.** Told Adwell about the non-compete at the June 22 dinner; Adwell reported that PAG’s counsel (Mr. Kellner) had reviewed it and “thought they were fine,” apparently on distance grounds (Vol. II 310:8–311:24).

- **Spoliation.** Admits a factory reset of his iPhone 15 Pro on September 1, 2024 — ten days after a letter that expressly prohibited any factory reset — with no backup, wiping texts and call logs with Adwell (Vol. I at 191–195). He also may have deleted the Blue Book email post-notice (Vol. I at 136; Vol. II 332:20–333:2).

**Priority recommendations** (detailed in Part VI): (1) move to compel immediate turnover of USB drive SD256-7891-XKR and forensic imaging of the Gmail account and all personal devices by a neutral examiner; (2) file a spoliation/sanctions motion seeking an adverse-inference instruction; (3) demand corrected, supplemented interrogatory answers and serve targeted requests for admission locking in the deposition concessions; (4) renew/support the preliminary injunction on the non-compete and trade-secret claims using the admissions; (5) depose Adwell, Quinlan, Chandrasekaran, Marchetti, Parekh, and Matsuda, and subpoena Sycamore, Google, Apple, and Yoon’s carrier; (6) retain a software expert for a MillEdge Pro / OptiMill code comparison; and (7) fix the several errors in our own record (misquoted interrogatory, forensic-report inconsistencies, C&D timing statements) before they are used against us.

# II. Key Admissions by Topic

*The following table organizes the most useful admissions by claim element. “Strength” reflects our assessment of how firmly the admission is locked in (Strong = unequivocal; Moderate = qualified or hedged but corroborated; Qualified = hedged and requires corroboration).*

## A. Employment Agreement / Non-Compete (EA §7(a))

| **Admission**                                                                                                                                                   | **Cite**                                | **Strength** |
|-----------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------|--------------|
| Signed EA on 3/4/2019, read it, understood it, no attorney review, no negotiation of §§7–9; intended to be bound.                                               | Vol. I at 19–20, 27–28                  | Strong       |
| Understood non-compete barred work for a CNC-optimization / end-effector competitor within a set radius for a period after leaving.                             | Vol. I at 21                            | Strong       |
| No new agreement at CTO promotion; EA remained operative at resignation (consistent with EA §13(b)).                                                            | Vol. I at 28                            | Strong       |
| Only consideration was employment itself (relevant to enforceability arguments; note EA recites access to Proprietary Information as additional consideration). | Vol. I at 27                            | Strong       |
| Reading §7(a) aloud: “within a 150-mile radius.” Concedes he was “mistaken.”                                                                                    | Vol. I at 22                            | Strong       |
| Troy is ~142 miles from CMS HQ — “sounds approximately right” / “that sounds about right.”                                                                      | Vol. I at 23–24; Vol. II 295:21–296:1   | Strong       |
| Knew at resignation that PAG was developing CNC optimization; knew of overlap with CMS core business; “aware of the potential concerns.”                        | Vol. I at 196–197                       | Strong       |
| PAG competes with CMS; MillEdge Pro and OptiMill are both CNC toolpath optimization products targeting aerospace/automotive — “significant overlap.”            | Vol. I at 200–201; Vol. II 303:17–304:9 | Strong       |
| Resignation letter’s “different sector” statement: “I see your point.”                                                                                          | Vol. I at 83–85                         | Moderate     |

## B. Access to Trade Secrets / Proprietary Information

| **Admission**                                                                                                                                                                        | **Cite**                            | **Strength** |
|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------|--------------|
| Led OptiMill v3.0 development (1.4M LOC; \$6.2M cost); HarmonicPath is the core competitive advantage (22–28% cycle-time reduction); had full source-code access on internal GitLab. | Vol. I at 40–42; 221                | Strong       |
| Named inventor on all four AdaptGrip patents and both applications; assigned to CMS under EA §9; AdaptGrip ≈ \$18.7M / 25.3% of FY2023 revenue.                                      | Vol. I at 43–44                     | Strong       |
| Blue Book is the confidential customer pricing matrix (8%–31% discounts), restricted to senior management; it is “Proprietary Information” under EA §8.                              | Vol. I at 45, 131–132               | Strong       |
| Knew of IT Access Policy §3.4 (no transfers to personal devices/accounts without written authorization); never obtained authorization; knew access was logged.                       | Vol. I at 46–47, 110                | Strong       |
| Confidentiality obligation continues post-employment; is bound now at PAG.                                                                                                           | Vol. I at 26; Vol. II 328:21–329:14 | Strong       |

## C. USB Transfer (August 10, 2024)

| **Admission**                                                                                                                        | **Cite**                         | **Strength** |
|--------------------------------------------------------------------------------------------------------------------------------------|----------------------------------|--------------|
| “May have” connected a USB drive; if connected, “it was likely mine. No one else used my laptop.”                                    | Vol. I at 102–103                | Moderate     |
| Transferred files; did not review them individually; copied “a folder — or a set of folders”; cannot identify or name a single file. | Vol. I at 104–108                | Strong       |
| Concedes the forensic report traces the files to the OptiMill repository; “I recognize it looks bad.”                                | Vol. I at 105–110, 222           | Moderate     |
| Has no documentation that personal materials were stored in the repository.                                                          | Vol. I at 106                    | Strong       |
| Drive is at his home in Troy; not returned; counsel “in discussions.”                                                                | Vol. I at 108; Vol. II 332:15–19 | Strong       |
| Cannot rule out accessing the drive between Aug. 10 and Aug. 28.                                                                     | Vol. I at 178                    | Qualified    |

## D. Blue Book Email (August 12, 2024)

| **Admission**                                                                                            | **Cite**                                | **Strength** |
|----------------------------------------------------------------------------------------------------------|-----------------------------------------|--------------|
| Sender is his CMS address; recipient is his personal Gmail; file “looks like it could be the Blue Book.” | Vol. I at 132                           | Strong       |
| Evolving account: “don’t recall” → “may have forwarded it inadvertently” while “cleaning out my inbox.”  | Vol. I at 132–135                       | Moderate     |
| Filename “essentially tells you what the file is.”                                                       | Vol. I at 134                           | Strong       |
| Does not know whether it still exists; “may have deleted it”; later “I believe I deleted it.”            | Vol. I at 136–137; Vol. II 332:20–333:2 | Moderate     |

## E. Separation Acknowledgment (August 28, 2024)

| **Admission**                                                                                                                                        | **Cite**          | **Strength** |
|------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------|--------------|
| Signed SA certifying return of all property including USB drives; did not return the USB drive; did not disclose the Blue Book email; “forgot” both. | Vol. I at 176–179 | Strong       |
| Understood the SA was a “formal document.”                                                                                                           | Vol. I at 179     | Moderate     |

## F. Pre-Resignation Contacts with PAG

| **Admission**                                                                                                                                                                                                           | **Cite**                               | **Strength** |
|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------|--------------|
| Met Adwell at Michigan Automation Council event (~June 8–9) and dined with him June 22, while CMS CTO; Adwell said he was building something in CNC optimization.                                                       | Vol. I at 60–62; Vol. II 308:16–309:22 | Strong       |
| Told Adwell about his non-compete at the June 22 dinner; Adwell: “We should look into that”; considered it “manageable.”                                                                                                | Vol. II 310:8–311:4                    | Strong       |
| Adwell told him PAG’s lawyer (believed to be Mr. Kellner) reviewed the non-compete and “thought they were fine,” apparently based on distance/geography.                                                                | Vol. II 311:5–24                       | Moderate     |
| Mid-July coffee with Quinlan arranged by Adwell “to talk about the engineering team we’re building”; “normal interview-type questions.”                                                                                 | Vol. II 312:20–313:22                  | Strong       |
| July 28 email: “Very interested in continuing the conversation” about “the opportunity at PAG.” Aug. 5 email from Adwell: “Teresa and I want to talk about the VP role.” Aug. 14 email: “Wrapping things up on my end.” | Vol. II 314:18–315:22                  | Strong       |
| Agrees with full timeline: June 8–9 contact → June 22 dinner → further communications and at least one meeting → Aug. 16 resignation → Aug. 20 offer → Sept. 3 start.                                                   | Vol. II 296:5–13                       | Strong       |
| June dinner was “somewhere in between” social and job-related.                                                                                                                                                          | Vol. II 342:2–8                        | Moderate     |

## G. Work on MillEdge Pro

| **Admission**                                                                                                                                                                                                           | **Cite**                                       | **Strength** |
|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------|--------------|
| Attended “MillEdge Pro Technical Architecture Review” on Sept. 4 (day 2); offered suggestions on the optimization engine.                                                                                               | Vol. II 298:5–300:3                            | Strong       |
| Eleven commits under “dyoon-pag” in September 2024, including “optimization engine refactor,” “engagement angle parameters,” and “harmonic analysis integration.”                                                       | Vol. II 300:4–301:6; 322:1–323:10              | Strong       |
| Rog 12 answer was “not as precise as it should have been”; has involvement “in my supervisory capacity”; “should have worded that differently.”                                                                         | Vol. II 302:14–303:16; 325:13–16               | Strong       |
| Helped with final technical reviews before Oct. 21 launch; attends weekly engineering standups covering MillEdge Pro; has commit and admin access.                                                                      | Vol. II 306:10–17; 324:20–325:12; 330:11–331:5 | Strong       |
| Described MillEdge Pro as using “harmonic frequency matching for tool engagement angles” — verbatim HarmonicPath documentation language; cannot identify any outside source for the phrase (before and after redirect). | Vol. II 318:20–320:24; 343:1–12                | Strong       |
| Said he “tried” to keep CMS knowledge separate, then corrected to “did.”                                                                                                                                                | Vol. II 324:10–18                              | Moderate     |

## H. Phone Reset / Spoliation

| **Admission**                                                                                                                       | **Cite**             | **Strength** |
|-------------------------------------------------------------------------------------------------------------------------------------|----------------------|--------------|
| Received the C&D Aug. 22–24; understood it required preservation of communications and that litigation was possible.                | Vol. I at 87–88, 192 | Strong       |
| Factory-reset his iPhone 15 Pro on Sept. 1, 2024; no backup; texts, call logs, and data wiped, including any Adwell communications. | Vol. I at 192–194    | Strong       |
| Used the personal phone to call (and possibly text) Adwell.                                                                         | Vol. I at 191        | Moderate     |
| “In hindsight, I probably should have thought about that.”                                                                          | Vol. I at 195        | Moderate     |

# III. Contradictions and Inconsistencies

*This Part catalogs inconsistencies between (A) the deposition and Yoon’s sworn interrogatory answers; (B) Volume I and Volume II; (C) the testimony and the documentary/forensic record; and (D) biographical inconsistencies bearing on credibility. Items are ranked by impeachment value (High / Medium / Low).*

## A. Deposition vs. Sworn Interrogatory Answers

| **Rog** | **Sworn Answer (Nov. 1, 2024)**                                                                                                                                 | **Contrary Testimony / Evidence**                                                                                                                                                                                                           | **Value** |
|---------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------|
| 3       | First learned of PAG ~late August 2024.                                                                                                                         | Learned of PAG at June 22 dinner (Vol. I at 66, 196); met Adwell ~June 8–9 (Vol. II 309:6–10); Googled PAG and visited its careers page from CMS laptop Aug. 11 (FR §5.4.2).                                                                | High      |
| 4       | First spoke with Adwell “late August 2024 after submitting my resignation,” by phone; later phone calls with Adwell and Quinlan in late August.                 | June 8–9 event; June 22 dinner; 1–2 calls June–Aug; emails June 15, July 18, July 28, Aug. 5, Aug. 14; mid-July in-person coffee with Quinlan; conceded answer was inaccurate (Vol. I at 63–64; Vol. II 295:1–12, 308–315, 312:9–19).       | High      |
| 6       | Devices: CMS laptop and personal iPhone; no external storage identified.                                                                                        | Personal SanDisk USB drive used Aug. 10 (Vol. I at 102–103; FR §5.1). Also: says laptop returned Aug. 28 vs. Vol. I at 89 (“on my last day. August 30”).                                                                                    | High      |
| 7       | “I did not remove or copy any confidential or proprietary documents from CMS.”                                                                                  | 3,847 source-code files to USB; Blue Book to Gmail; concedes Blue Book is Proprietary Information (Vol. I at 102–108, 132–135; FR §§5.1–5.2).                                                                                               | High      |
| 10      | Returned all company property; complied with EA.                                                                                                                | USB drive never returned (Vol. I at 177; Vol. II 332:15–19; FR §4.2).                                                                                                                                                                       | High      |
| 11      | First spoke with Adwell late August; written offer “approximately late August.”                                                                                 | Offer letter dated Aug. 20 (Ex. 20); pre-resignation Quinlan meeting and Aug. 5 “VP role” email (Vol. II 291–292, 313–315).                                                                                                                 | High      |
| 12      | General management only; “not involved in the development of any CNC optimization products”; no hands-on development of features, architectures, or algorithms. | Architecture review day 2; 11 commits; launch reviews; weekly MillEdge standups; admits answer imprecise (Vol. II 298–306, 322–325).                                                                                                        | High      |
| 14      | Social contacts with CMS colleagues; no names, dates, or subjects recalled.                                                                                     | Names Kevin Matsuda, Jennifer Colegrove, Michael Roth; lunch with Matsuda Oct. 2024 (Vol. II 331:12–332:14).                                                                                                                                | Medium    |
| 15      | Has no CMS documents/ESI on any personal device, email account, or external storage.                                                                            | USB drive with the files is at his home (Vol. I at 108); Blue Book may still be in Gmail (Vol. I at 136–137). If he deleted it before Nov. 1, that deletion post-dates the Aug. 22 hold; if not, Rog 15 was false. Either answer helps CMS. | High      |
| 5       | Left to relocate near family and for a smaller environment; no outside influence.                                                                               | Moved to Troy because “closer to my new office” (Vol. I at 5); “the opportunity at PAG was attractive” (Vol. I at 85); ongoing PAG courtship since June.                                                                                    | Medium    |

## B. Volume I vs. Volume II (Internal Contradictions)

| **Topic**                        | **Volume I**                                                                                                | **Volume II**                                                                                                                                                                 | **Value**               |
|----------------------------------|-------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------|
| First contact with PAG           | June 22 dinner was the first communication with anyone at PAG (at 64).                                      | First contact ~June 8–9 at Michigan Automation Council event (309:6–10); June 15 invitation email (308:16–23).                                                                | High                    |
| Contacts June–Aug                | “Maybe one or two phone calls”; did not recall discussing a job; “things were still very informal” (at 65). | Emails and at least one follow-up meeting (295:1–9); Aug. 5 email re “the VP role” (315:3–12).                                                                                | High                    |
| Teresa Quinlan                   | No communications with Quinlan June–Aug (at 66); first met her after starting at PAG, Sept. 2024 (at 197).  | First met Quinlan mid-July 2024 at coffee arranged by Adwell to discuss the engineering team (312:23–313:18).                                                                 | High                    |
| When he learned of VP role       | Had “general discussions with Marcus about a role at PAG” before resigning (at 85–86).                      | Learned of the position only in August, after deciding to leave (290:14–291:16).                                                                                              | High                    |
| Non-compete disclosure to Adwell | “May have mentioned” a non-compete “at some point”; could not recall if at June 22 dinner (at 64–65).       | “I believe it came up during our dinner” on June 22 (310:12–16).                                                                                                              | Medium                  |
| Basis for joining PAG            | Believed he was within his rights based on his own understanding (100 miles) (at 89, 197).                  | Consulted an attorney and relied in good faith (328:9–14; 340:18–341:1); PAG counsel said “fine” (311:15–16).                                                                 | High (privilege waiver) |
| PhD year / topic                 | PhD 2010; dissertation on adaptive grip-force algorithms for robotic end-effectors (at 7).                  | PhD 2009; research on machining dynamics, chatter avoidance, vibration analysis (338:24–339:5).                                                                               | High                    |
| Code commits                     | —                                                                                                           | Commits were “minor,” “peripheral,” not to the core optimization engine (338:4–9) vs. commit messages “optimization engine refactor — initial pass / phase 2” (322:1–323:18). | High                    |
| Blue Book deletion               | Does not know; would need to check (at 136–137).                                                            | “I believe I deleted it” (332:20–333:2).                                                                                                                                      | Medium                  |

**Note on the PhD discrepancy:** Volume I aligned his dissertation with AdaptGrip (grip force); Volume II — on redirect, when counsel needed a pre-CMS source for harmonic analysis — recast it as chatter/vibration research. Both cannot be accurate. The dissertation is publicly available (Purdue/ProQuest) and should be obtained immediately. Also note EA Exhibit A lists **no** prior inventions, and EA §8(a)(B) excludes pre-existing knowledge only if shown by “contemporaneous written records predating such disclosure.”

## C. Testimony vs. Documentary and Forensic Record

| **Yoon’s Position**                                                                                                         | **Contrary Evidence**                                                                                                                                                                                                                                                                                           | **Value**  |
|-----------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------|
| Believed the radius was 100 miles until the deposition (Vol. I at 22–24; Vol. II 327:12–19).                                | C&D (Aug. 22) states 150 miles and that Troy (142 mi.) is “squarely within” it; SA §3(b) (signed Aug. 28) recites 150 miles and SA §3(e) represents he understands “the geographic reach.” Both pre-date his Sept. 3 PAG start. He also admits reviewing the EA around the time he accepted PAG (Vol. I at 23). | High       |
| USB files were “personal reference materials and publicly available papers” in a “working area” (Vol. I at 104–107).        | All 3,847 files are .cpp, .py, .h, .json, or .md — no PDFs or papers; sourced from OptiMill-v3\src, \algorithms\harmonicpath, \test, and AdaptGrip\firmware (FR §5.1, App. F).                                                                                                                                  | High       |
| Transfer not deliberate / copied a folder without reviewing (Vol. I at 107–108).                                            | Aug. 8 searches “how to transfer large files to USB”; Aug. 9 fresh full git clone of OptiMill-v3; Aug. 10 drive’s first-ever connection; 8 repo clones/pulls in final 60 days vs. ~1/month baseline (FR §§5.1, 5.4.1–5.4.2).                                                                                    | High       |
| Blue Book forwarded inadvertently while “cleaning out my inbox”; sometimes forwarded emails to himself (Vol. I at 133–134). | New standalone message (not a forward), no subject, no body; the only email to any personal account Aug. 1–28; byte-for-byte hash match to \\cms-fs01\Finance\Pricing (FR §5.2).                                                                                                                                | High       |
| Patent file access was “routine CTO oversight” (Vol. I at 157–159).                                                         | 47 accesses in 46 days vs. 3.0/month baseline (≈10.4x), accelerating toward departure; all six portfolio matters; no Jira tickets, filings, or deadlines (FR §5.3).                                                                                                                                             | High       |
| “Forgot” the USB drive and email at exit interview (Vol. I at 177–179).                                                     | SA §§1(d), 2(a)–(b), 4(c) specifically enumerate USB drives and personal email accounts; C&D (received six days earlier) specifically demanded return of USB drives and Gmail copies.                                                                                                                           | High       |
| Reset phone because it was slow; “wasn’t thinking about litigation” (Vol. I at 192–195).                                    | C&D §VI expressly: “You must not perform any factory reset, data wipe, or deletion … on any device.” He admits receiving and forwarding it to counsel (Vol. I at 87–89).                                                                                                                                        | High       |
| Did not know of PAG before June 22; MillEdge developed independently (Vol. I at 66; Vol. II 321:5–6).                       | Aug. 11 Google search for “Pinnacle Automation Group” and careers page visit (FR §5.4.2) — consistent with active pre-resignation job pursuit.                                                                                                                                                                  | Medium     |
| No Sycamore contact regarding PAG; coincidence (Vol. I at 66–67, 198).                                                      | No contrary evidence yet; prior paid Sycamore advisory role (2017). Unverified — requires third-party discovery.                                                                                                                                                                                                | Low (open) |

## D. Biographical Inconsistencies (Credibility)

Yoon’s sworn Rog 1–2 answers conflict with his sworn deposition testimony on basic facts. These may reflect drafting errors by counsel, but they were verified under oath and should be exploited (or at minimum clarified) because they cast doubt on the care taken in verifying the entire set of answers.

| **Item**                  | **Interrogatory Answers**                                                                                    | **Deposition**                                                                                                                                                         |
|---------------------------|--------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Full name                 | Derek Sung-Ho Yoon                                                                                           | Derek James Yoon (Vol. I at 5)                                                                                                                                         |
| Date of birth             | April 14, 1983                                                                                               | September 3, 1983 (Vol. I at 5)                                                                                                                                        |
| Current address           | 1482 Whitfield Lane, Troy, MI 48084                                                                          | 4712 Winthrop Lane, Troy, MI 48098 (Vol. I at 5)                                                                                                                       |
| Prior employment (10 yrs) | Strathmore Engineering Corp., Southfield — Director of Adv. Mfg. Systems, June 2014–Feb. 2019, ~12 engineers | Saxonbrook Precision (Dearborn) 2010–mid-2015; Meridian Robotics (Sterling Heights) Director of Advanced Automation mid-2015–early 2019, ~25 engineers (Vol. I at 7–8) |
| PhD                       | August 2010                                                                                                  | 2010 (Vol. I at 7); 2009 (Vol. II 338:24–25)                                                                                                                           |
| Hire-date bonus           | 35% (consistent with EA §3(b))                                                                               | “around 20 percent of base” (Vol. I at 9)                                                                                                                              |
| Prior address             | —                                                                                                            | 1518 Lakewood Blvd., East Grand Rapids (Vol. I at 5); C&D addressed to 1847 Lakeshore Drive, Grand Rapids                                                              |

Action: compare against his CV (Dep. Ex. 2), CMS HR file, and I-9/background check. If the employment history in Rog 2 is wrong, that bears on EA §4(c) (accuracy of hiring information).

# IV. Issues in Our Own Record Requiring Correction

Several inconsistencies originate in CMS’s own documents or examination. Defense counsel will use them to attack the forensic evidence and the examination; they should be corrected or explained before the injunction hearing, summary disposition, or expert disclosures.

- **Misquoted Interrogatory No. 4 (Vol. II 312:1–7).** Ms. Pratt read Rog 4 as asking about communications “regarding potential employment.” The actual interrogatory (and the Vol. I reading, at 59) asks for the first communication with any PAG representative on any subject. Defense counsel built the redirect on the narrower misquote (Vol. II 336:20–337:3). Correct the record via letter and in any motion; emphasize that Yoon conceded in Vol. I that the question “doesn’t limit” itself to employment (Vol. I at 63).

- **Blue Book mischaracterized (Vol. II 315:25–316:1; 332:24).** The examination twice called the Blue Book a “competitive analysis spreadsheet.” It is the customer pricing matrix (EA §8(a)(iii); FR §5.2). Avoid in future filings.

- **Email timestamp mismatch.** Vol. I at 133 put the Blue Book email at 11:47 a.m. ET; the forensic report and Exchange log show 14:22:17 EDT (FR §5.2, App. D). Reconcile Dep. Ex. 15 against the Exchange transport log (possible second log entry, time-zone, or exhibit error) before relying on either.

- **“Network” vs. local transfer.** Vol. I at 102 described the files as transferred “from the CMS internal network” and “from the OptiMill source code repository”; the report shows copying from a local clone on C:\\ (FR §5.1). The distinction is favorable (the Aug. 9 clone shows staging) but we should use the report’s precise description.

- **Forensic report internal inconsistencies.** (i) Baseline stated as “prior 12 months (July 2023–June 2024)” in examination vs. 13 months (June 2023–June 2024) in the report — harmless but should be consistent; (ii) FR §5.4.1 refers to “the twelve-month period from January through June 2024” (six months); (iii) the hash values in §4.3 and App. B–D appear to be sequential/placeholder-style strings and must be verified against the native EnCase output; (iv) the report is unsigned in the copy reviewed. Ask Ridgepoint to issue a corrected, signed report.

- **C&D timing statements.** The Aug. 22 C&D states that CMS’s “preliminary review” of the laptop had raised concerns and that CMS “has engaged” a forensic firm. The laptop was not returned until Aug. 28 and Ridgepoint was engaged Sept. 10 (FR §§2, 4.2). Confirm what review (e.g., server-side log review by IT Director Parekh) supported the letter; otherwise expect a credibility attack.

- **C&D mailing address.** Certified mail went to 1847 Lakeshore Drive, Grand Rapids; Yoon testified he lived at 1518 Lakewood Blvd., East Grand Rapids. Receipt is not in dispute (he admits receiving it Aug. 23–24 and it was also emailed to his Gmail), but pin down the Ex. 17 delivery confirmation and the email delivery record.

- **Scope of EA quotations.** Examination paraphrases of §7(a), §7(b), and §12 differ from the executed text (e.g., §7(b) actually includes a no-hire clause with a 12-month look-back and limits customer non-solicitation to customers with “material contact”; §12 also permits the W.D. Mich.). Quote the agreement verbatim going forward.

- **Transcript housekeeping.** Vol. I’s certificate states 230 pages; Vol. II states Vol. I comprised pages 1–287. Different reporters and videographers are listed for each day; Vol. II’s index page references (e.g., recross at 415, Kellner at 420) do not match the transcript. Counsel appearance blocks list inconsistent addresses and phone numbers for all three firms. Obtain certified corrected transcripts and an index before filing excerpts.

- **Separation Acknowledgment witness line** is blank, although Yoon says a second HR representative attended and the report says Parekh received the laptop and documented the return on the SA. Obtain the fully executed original and identify the second attendee.

# V. Significance for Claims and Defenses

## A. Breach of Non-Compete (EA §7(a))

Formation, knowledge, and competing employment within the territory are effectively conceded. The contest will be reasonableness under MCL 445.774a (as incorporated by EA §11). Helpful facts: his senior executive role, access to the full range of trade secrets, the direct product overlap, and the reformation clause (EA §7(c)). Expect defense arguments on the 150-mile radius and the absence of separate consideration (Vol. I at 27); EA’s recitals identify access to Proprietary Information and compensation as consideration. His “100-mile” belief is legally immaterial to breach and factually rebutted by the C&D and SA. Note the tolling provision (EA §10) extends the Restricted Period during any breach.

## B. Trade Secret Misappropriation (MUTSA / DTSA) and Breach of Confidentiality (EA §8)

Acquisition by improper means is strongly supported: unauthorized copying in violation of IT Policy §3.4 and EA §§6(d), 8(b), with premeditation evidence. Use/disclosure is the principal gap. Circumstantial support includes: the verbatim HarmonicPath phrasing; the Sept. 24 commit “harmonic analysis integration”; MillEdge Pro’s “up to 25%” claim within HarmonicPath’s 22–28% range; his inability to name any comparable product; the seven-week post-arrival launch; and the destruction of phone data (supporting an adverse inference). A code comparison is the most important missing piece.

## C. Claims Against PAG (Tortious Interference / Vicarious or Direct Misappropriation)

PAG had actual knowledge of the non-compete by June 22, 2024, its counsel reviewed it pre-hire, and it put Yoon to work on the competing product immediately with commit and admin access. The “fine” conclusion reportedly rested on distance — i.e., potentially the same erroneous 100-mile premise. Mr. Kellner’s role as the reviewing lawyer creates a potential advocate-witness issue under MRPC 3.7 if PAG asserts good faith/advice of counsel.

## D. Credibility and Sanctions

The pattern — false sworn interrogatory answers, a false exit certification, shifting explanations, and post-notice destruction of evidence — supports sanctions under MCR 2.313 and the court’s inherent authority, an adverse-inference instruction, and fee-shifting (also available under EA §10 and SA §5). It also materially strengthens the irreparable-harm and likelihood-of-success showing for injunctive relief.

# VI. Recommended Next Steps

## Immediate (0–14 days)

| **Action**                                                                                                                                                                                                                                                                                                                                    | **Owner**      |
|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------|
| Motion to compel turnover of USB drive SD256-7891-XKR to a neutral forensic examiner, with imaging of all Yoon personal devices, his Gmail account (derek.yoon.personal@gmail.com), and any cloud accounts; seek an order prohibiting further access or alteration. Birchfield twice took the request “under advisement” (Vol. I at 108–109). | Pratt / Oshiro |
| Serve a formal deficiency letter demanding supplementation/correction of Rogs 3, 4, 6, 7, 11, 12, 14, and 15 under MCR 2.302(E), with a short deadline; note Yoon’s own concessions and Birchfield’s statement that amendments will be handled “through the appropriate procedures” (Vol. II 303:8–11).                                       | Oshiro         |
| Correct the record on the Rog 4 misquotation by letter to all counsel.                                                                                                                                                                                                                                                                        | Pratt          |
| Calendar the 30-day read-and-sign window for both volumes; prepare to challenge substantive errata (e.g., attempts to recast USB, Blue Book, Quinlan, or commit testimony) and to seek reopening if material changes are made.                                                                                                                | Paralegal      |
| Send renewed preservation letters to Yoon, PAG, Adwell, and Quinlan covering personal phones, texts, iCloud/Google backups, and the MillEdge Pro repository history (including Yoon’s commit diffs).                                                                                                                                          | Oshiro         |

## Motions (15–45 days)

| **Action**                                                                                                                                                                                                                                                                                                                                                                   | **Owner**      |
|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------|
| Spoliation motion re: Sept. 1 factory reset (and any post-hold Blue Book deletion) seeking an adverse-inference instruction, fees, and forensic costs. Before filing, subpoena Apple (iCloud backup existence/dates) and Yoon’s wireless carrier (call/text metadata June–Sept. 2024) to quantify what was lost and whether it is recoverable.                               | Pratt          |
| Renew or supplement the preliminary-injunction motion with the admissions compendium in Part II: enforce §7(a) through ~Feb. 28, 2026 (subject to tolling), bar use of CMS information, and require return/sequestration of all CMS materials and certification under oath.                                                                                                  | Pratt / Oshiro |
| Motion to compel on privilege: Yoon has placed his attorney consultation and good-faith reliance at issue (Vol. II 340:18–341:1); seek disclosure or preclusion of any advice-of-counsel/good-faith defense. Also challenge the instruction not to answer factual questions about preservation steps and whether he consulted counsel before the reset (Vol. I at 137, 194). | Pratt          |
| Motion (or stipulation) to extend the protective order to PAG technical information on an attorneys’-eyes-only basis, to eliminate the objections that blocked MillEdge Pro testimony (Vol. I at 199–200; Vol. II 317–318).                                                                                                                                                  | Oshiro         |

## Written Discovery

| **Action**                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    | **Owner** |
|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------|
| Requests for Admission (MCR 2.312) locking in: the 150-mile term; the 142-mile distance; receipt of the C&D; execution and falsity of SA §§1(d), 2(b), 4(c); the Aug. 10 transfer; the Aug. 12 email; non-return of the drive; the Sept. 1 reset without backup; the June 22 non-compete disclosure; the 11 commits; Sept. 4 attendance.                                                                                                                                                                                      | Oshiro    |
| Document requests to PAG: full MillEdge Pro repository with git history and diffs for all “dyoon-pag” commits; pre-Sept. 2024 architecture documents and design history (to test “independent development”); benchmarking data behind the “25%” claim; Sept. 4 meeting notes/recordings; Yoon’s offer letter, option agreement, and vesting milestones; recruiting file; all Adwell/Quinlan communications (texts included) with Yoon; Series A materials referencing Yoon or CMS; any non-compete analysis provided to Yoon. | Oshiro    |
| Obtain Yoon’s Purdue dissertation and publications to test both versions of his research topic and whether the phrase “harmonic frequency matching for tool engagement angles” appears anywhere.                                                                                                                                                                                                                                                                                                                              | Paralegal |
| Request Yoon’s written certification demanded by the C&D (10 business days) — confirm whether one was ever provided; if so, it is another false statement.                                                                                                                                                                                                                                                                                                                                                                    | Oshiro    |

## Depositions / Third-Party Discovery

| **Action**                                                                                                                                                                                                                                        | **Owner** |
|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------|
| Marcus Adwell — June 8–9 event; June 22 dinner; non-compete discussion; what PAG counsel concluded and on what basis; texts/calls with Yoon; Aug. 5 “VP role” email; whether Yoon brought anything to PAG.                                        | Pratt     |
| Teresa Quinlan — mid-July coffee (interview), knowledge of non-compete, hiring decision timeline (offer drafted before Aug. 16?).                                                                                                                 | Pratt     |
| Ravi Chandrasekaran — MillEdge Pro architecture pre- and post-Yoon; substance of Yoon’s commits and Sept. 4 suggestions; origin of harmonic-frequency approach.                                                                                   | Pratt     |
| Lisa Marchetti, second HR attendee, and James Parekh — exit-interview checklist, questions about USB/personal accounts, laptop return date and documentation.                                                                                     | Oshiro    |
| Kevin Matsuda (and, as needed, Colegrove and Roth) — October 2024 lunch; any recruitment or CMS-information discussions (EA §7(b)).                                                                                                               | Oshiro    |
| Subpoenas: Sycamore Ventures (communications with or about Yoon in 2024; PAG diligence materials mentioning Yoon/CMS); Google (Gmail account metadata, deletion records, subject to privacy constraints); Apple and wireless carrier (see above). | Oshiro    |
| Karen Villalobos (Ridgepoint) — corrected, signed report; expand scope to the USB drive, Gmail, and PAG repository once produced; verify hashes and timestamps.                                                                                   | Pratt     |

## Experts and Case Development

| **Action**                                                                                                                                                                                                                                                                     | **Owner** |
|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------|
| Retain an independent software/source-code expert to compare MillEdge Pro (especially post-Sept. 2024 commits, engagement-angle and harmonic-analysis modules) against OptiMill v3.0/HarmonicPath.                                                                             | Pratt     |
| Develop damages model (lost profits / unjust enrichment / reasonable royalty); consider AdaptGrip firmware exposure — AdaptGrip firmware was in the USB transfer (FR §5.1) but was not addressed at deposition; also investigate whether PAG has any end-effector development. | Oshiro    |
| Reserve and, after production of the USB drive, PAG code, and Exhibit 22 follow-up, move to reconvene Yoon’s deposition on the AdaptGrip firmware, the commit diffs, Sycamore, and any new evidence (reservation made at Vol. II 344:5–8).                                     | Pratt     |
| Evaluate amending the complaint to add claims based on the false Separation Acknowledgment (SA §5 makes misrepresentation an independent basis for action) and, if supported, civil conspiracy/aiding-and-abetting against PAG.                                                | Pratt     |

# VII. Open Questions

- Where is the USB drive now, and has it been connected to any device (including PAG systems) since August 10? Yoon’s answers varied from “not sure” to “I did not” (Vol. I at 108–109).

- Does the Blue Book email still exist in Gmail, and if deleted, when (before or after Aug. 22; before or after the Nov. 1 interrogatory answers)?

- Was there an iCloud backup of the iPhone prior to Sept. 1? Did Yoon use any other device or messaging app with Adwell?

- What exactly did PAG’s counsel analyze, when, and was the analysis premised on a 100-mile radius?

- Did PAG’s offer letter (dated four days after resignation) exist in draft before Aug. 16?

- Was MillEdge Pro’s launch accelerated after Yoon joined, and when did “harmonic analysis” first appear in the MillEdge Pro codebase?

- Any role for Sycamore Ventures (Yoon’s former client) in connecting Yoon and PAG?

*This memorandum reflects the unsigned transcripts and documents listed above. Page and line citations should be conformed to the certified final transcripts once errata are returned.*
