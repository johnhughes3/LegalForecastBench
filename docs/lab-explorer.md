# Harvey LAB explorer: design

The explorer is offline until the LAB audit paper is published: its pages sit in `site/src/pages/_lab/`, which Astro does not route, and `/lab/*` redirects to the paper. Rename the directory to `lab/` (and remove the redirect in `site/vercel.json`) to relaunch it at `/lab/`. It lets a reader browse Harvey LAB's 52 litigation tasks, read every rubric criterion next to the AI audit findings and two graded model runs, and go one by one through the 25 criteria a litigator hand-reviewed. The source data is the audit in [`harvey-lab-audit/litigation-dispute-resolution/`](harvey-lab-audit/litigation-dispute-resolution/README.md). The explorer adds no data of its own and never edits that directory.

## Two entry points

A two-tab bar sits at the top of every explorer page. The tabs are plain links, so each view is its own cacheable static page and works without JavaScript.

| Tab | URL | For | Content |
| --- | --- | --- | --- |
| Hand-audited | `/lab/` | Reading the reviewer's work | Counts, the rubric-verdict by environment-verdict table (each cell links to its items), a 25-row table, and a walk-through that starts at item 1. |
| Full runs | `/lab/runs/` | Scanning everything | Run totals, a 52-task directory, and a filterable scanner over all 2,858 criteria. |

Other pages: `/lab/review/<1..25>/` (one hand-audited criterion each, with previous and next links, a position indicator and a 25-square pager), `/lab/tasks/<task>/` (instructions, documents, runs, every criterion), and `/lab/deliverables/<task>/<run>/<file>/` (a model deliverable rendered for reading).

## What is human and what is AI

Only the reviewer's verdicts are human judgments. Every page carries an AI notice, every chip for an audit status reads "AI Sol" or "AI Opus", every judge grade is labeled "AI judge", and the reviewer's determination is shown in a bordered block titled "Reviewer's verdicts and analysis (John Hughes)" using the "Reviewer:" badge. Nothing from the AI audits is labeled "verified" or "confirmed" except where an audit's own text says so. Task instructions and rubric text are Harvey's (MIT licensed); the license is vendored with them.

## Data model and build-time pipeline

Everything is read at build time from files in the repository. Nothing is fetched over the network during a build.

| Input | Source | Used for |
| --- | --- | --- |
| Task instructions and full rubric | `site/src/data/lab/upstream/<task>.json`, vendored from Harvey at the pinned commit | Instructions, every criterion's text and deliverable names |
| Criterion line numbers | `tasks/<task>/claude-opus-5-5-audit.json` | Deep links to `task.json#L<n>` |
| Both AI auditors' final and blind statuses, findings, agreement group | `comparison.json` | Flags and findings |
| Pass or fail plus reasoning, per run and judge | `model-runs/<task>/<run>/scores_<judge>.json` | Grades and reasoning |
| Source document names | `tasks/<task>/README.md` | Links to the pinned upstream documents |
| The reviewer's verdicts | `human-review/worksheet.md` | The 25 hand-audited criteria |
| Deliverable renderings | `model-runs/<task>/<run>/output/*.md` | An Astro content collection, one page each |

`site/src/lab/load.ts` joins these into one `LabData` value. The joins are checked, not trusted: a task whose criteria differ in count or order across the upstream file, the audit and any of the four score files fails the build. `site/src/lab/worksheet.ts` parses the worksheet with the same patterns as `scripts/harvey_review_sample.py`, and throws on an unknown verdict value.

The compact wire formats are in `index-format.ts`: `LabIndex` (one array row per criterion for the scanner) and `TaskDetail` (one task's rubric text, findings and judge reasoning). They are emitted as static JSON by two Astro endpoints.

### Vendoring decision

- **`task.json` files are vendored** (52 files, 1.5 MB). They are the only source of the instructions and the full rubric, and without them the build would depend on the network and on an upstream that can change. They are written byte for byte by `site/scripts/fetch-lab-upstream.ts` and pinned to commit `1dd81403b2fbb60596f7aea3fcecafad7bf73143`. A unit test confirms their criteria line up with every other source. Biome ignores the directory.
- **Source documents are linked, not copied or rendered.** They are binary `.docx`, `.xlsx`, `.pdf` and `.eml` files of fictional records. Copying them would add repository weight, rendering them would add a conversion step with its own fidelity questions, and each page already links to Harvey's pinned copy, which is the authoritative one.
- **Model deliverables are rendered** from the existing Markdown renderings into pages (about 9 MB of HTML in total, never loaded unless a reader opens one). The original `.docx` is linked from the repository.
- The attribution notice and MIT text are in `site/src/data/lab/upstream/LICENSE.txt`.

## Lazy loading

| Content | How it loads |
| --- | --- |
| Landing page, task directory, task rows | In the page HTML |
| Rubric text, AI findings and judge reasoning for a task | One JSON file per task, fetched the first time a row is hovered, focused or opened |
| The all-criteria scanner's index | One JSON file, fetched when the scanner nears the viewport, when a filter is touched, or at once if the URL already carries a filter |
| Deliverable renderings | Separate pages, reached by link |
| Reviewer's determination | In the page HTML (it is the point of the page) |

The scanner draws 100 rows at a time. Rows are built from escaped strings by the same functions that draw chips on the server (`markup.ts`), so there is one definition of how a grade or status looks. Judge text and rubric text are escaped on every path. A test pushes hostile HTML through the renderer.

## Filters

The five filters are bits in a per-criterion mask (`flags.ts`), shared by the build and the browser: Hand-audited, Defective per reviewer, AI-flagged (final position of either auditor), Failed by any run (any of the four grades), and Judges disagree (Sonnet 4.6 and GPT-5.5 differ on at least one run). Active filters combine with AND. A free-text search matches criterion ids and titles, and the scanner has a task selector. State is kept in the URL (`?f=...&q=...&task=...`) so a view can be shared. A link to `#c-049` opens that row and clears any filter hiding it.

## Page structure and accessibility

- The task page and the scanner share the same row design: id, title, status chips, then `S` and `G` marks (Sonnet 4.6, GPT-5.5) for Luna and Opus. Rows are native `<details>` elements, so keyboard and screen-reader behavior comes from the browser.
- Status is a glyph plus a word, never color alone (`✓ pass`, `✗ fail`, "AI Sol problematic"). Each grade mark has an accessible name such as "Sonnet 4.6 fail". Contrast uses the site's existing tokens.
- Filter buttons are toggle buttons (`aria-pressed`) in a labeled `fieldset`; the match count is a polite live region.
- The tab bar is a `nav` with `aria-current`; the pager is a labeled `nav` with an ordered list; previous and next carry `rel` attributes.
- Tables have captions and scoped headers and scroll inside their own container on narrow screens. A browser test checks that no explorer page scrolls sideways at 390 px.
- Without JavaScript the landing page, review pages, task directory, task pages' summary rows and deliverables all work; filtering, row detail and the scanner need JavaScript and say so.

## Size and performance budget

Measured on the cold build of this branch (gzip level 9):

| Item | Raw | Gzip |
| --- | ---: | ---: |
| `/lab/` (landing) | 62 KB | 10 KB |
| `/lab/runs/` | 68 KB | 12 KB |
| `/lab/review/1/` | 36 KB | 9 KB |
| Largest task page | 133 KB | 13 KB |
| Median task page | 86 KB | not measured |
| Scanner index, fetched on demand | 254 KB | 70 KB |
| Largest per-task detail file, fetched on demand | 244 KB | 48 KB |
| Explorer JavaScript (shared filter controls and renderers, plus a small script per page) | under 12 KB | about 5 KB |

No React runtime is loaded on `/lab/*`. The explorer adds 212 pages and 53 JSON files (about 23 MB in `dist/lab`, nearly all of it task pages, deliverable pages and detail files that no one downloads unless they ask), and the full site build still takes about 3.5 seconds. The budget: no landing, scanner or task page over about 150 KB raw (deliverable renderings are the content itself and can be larger), no React on these pages, and nothing over 100 KB gzip fetched without a reader action.

## Where it is linked

- **Analysis index** (`/analysis/`): the existing "Harvey LAB litigation tasks" audit entry now points to `/lab/` instead of the GitHub folder, and the header's Analysis tab stays highlighted on explorer pages.
- **Paper page** (`/paper/`): a "LAB audit explorer" button beside Results, Methods and Data. The manuscript cites the audit, so readers of the paper are the natural audience. The `.tex` source is untouched.
- **Approach essay** (`/approach/`): a one-sentence pointer at the end of the paragraph that introduces the LAB case study.
- The explorer is **not** in the primary navigation (it has five items and a layout test counts them) and **not** in the agent-markdown negotiation table, which covers prose pages. Explorer pages appear in the sitemap except deliverable renderings, which are `noindex`.

## Not done

- The statistical lower bound from the review protocol's decision table is not shown. The landing page gives the counts and links to the protocol; the bound is the reviewer's to publish.
- Search covers ids and titles, not rubric text, because rubric text is loaded per task on demand.
- The 25 hand-audited criteria are not cross-linked to the audit's own long reports beyond the per-task links.
