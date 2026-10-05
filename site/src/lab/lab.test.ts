import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { test } from "node:test";

import { repositoryRoot } from "../data/manuscript.js";
import {
	EMPTY_FILTER_STATE,
	matchesQuery,
	parseFilterState,
	serializeFilterState,
} from "./filter-state.js";
import { FILTERS, FLAG, flagsFor, maskFor, matchesMask } from "./flags.js";
import {
	buildDetail,
	buildIndex,
	type CriterionDetail,
	GRADE_SLOTS,
} from "./index-format.js";
import { loadLab } from "./load.js";
import { aiStatusHtml, criterionBodyHtml, reviewBadgeHtml } from "./markup.js";
import { AUDIT_PATH } from "./paths.js";
import { summarizeReview } from "./summary.js";
import type { Criterion } from "./types.js";
import { parseWorksheet } from "./worksheet.js";

const auditDir = resolve(repositoryRoot(), AUDIT_PATH);
const read = (relative: string): string =>
	readFileSync(resolve(auditDir, relative), "utf8");

test("the worksheet parses to exactly the seeded sample, in order", () => {
	const items = parseWorksheet(read("human-review/worksheet.md"));
	const sample = (
		JSON.parse(read("human-review/sample.json")) as {
			sample: { task: string; criterion: string }[];
		}
	).sample;
	assert.equal(items.length, 25);
	assert.deepEqual(
		items.map((item) => [item.task, item.criterion]),
		sample.map((row) => [row.task, row.criterion]),
	);
	assert.deepEqual(
		items.map((item) => item.number),
		Array.from({ length: 25 }, (_, i) => i + 1),
	);
	for (const item of items) {
		assert.ok(item.note.length > 0, `item ${item.number} has a note`);
	}
});

test("the worksheet parser matches the reviewer's recorded counts", () => {
	const items = parseWorksheet(read("human-review/worksheet.md"));
	const count = (pick: (item: (typeof items)[number]) => string) => {
		const out: Record<string, number> = {};
		for (const item of items) out[pick(item)] = (out[pick(item)] ?? 0) + 1;
		return out;
	};
	assert.deepEqual(
		count((i) => i.verdict),
		{
			Defective: 16,
			Arguable: 3,
			"Not defective": 6,
		},
	);
	assert.deepEqual(
		count((i) => i.aiReasoning),
		{
			Correct: 16,
			"Partly correct": 3,
			Wrong: 6,
		},
	);
	// Item 1 keeps its explanation after the environment verdict.
	const first = items[0];
	assert.equal(first?.environment, "Defective");
	assert.match(first?.environmentNote ?? "", /117 time entries/);
	assert.match(first?.category ?? "", /^unambiguous objective error/);
	// A note continues across "- " lines until the Category line.
	assert.ok((items[1]?.note.length ?? 0) > 1);
	assert.doesNotMatch((items[1]?.note ?? []).join(" "), /Category/);
});

test("the parser rejects an unknown verdict instead of guessing", () => {
	const broken = [
		"## 1. A task — C-001",
		"[Task audit page](../tasks/a-task/README.md)",
		"- **Verdict:** Maybe",
		"- **AI reasoning:** Correct",
		"- **Environment:** Correct",
		"- **Note and source locator:** text",
	].join("\n");
	assert.throws(() => parseWorksheet(broken), /verdict "Maybe"/);
});

test("every source joins: 52 tasks, 2,858 criteria, 835 final flags", () => {
	const lab = loadLab();
	assert.equal(lab.tasks.length, 52);
	assert.equal(
		lab.tasks.reduce((sum, task) => sum + task.criteria.length, 0),
		2858,
	);
	assert.equal(lab.flaggedTotal, 835);
	assert.equal(lab.review.length, 25);
	assert.equal(
		lab.tasks.flatMap((task) => task.criteria).filter((c) => c.review !== null)
			.length,
		25,
	);
});

test("grades in the explorer equal the comparison file's recorded run verdicts", () => {
	const lab = loadLab();
	const rows = (
		JSON.parse(read("comparison.json")) as {
			rows: {
				task: string;
				criterion: string;
				runs: Record<string, Record<string, string>>;
			}[];
		}
	).rows;
	for (const row of rows) {
		const criterion = lab.tasks
			.find((task) => task.slug === row.task)
			?.criteria.find((c) => c.id === row.criterion);
		assert.ok(criterion, `${row.task} ${row.criterion}`);
		assert.equal(
			criterion.grades.luna.sonnet.verdict,
			row.runs["gpt6luna-xhigh"]?.["claude-sonnet-4-6"],
		);
		assert.equal(
			criterion.grades.opus.gpt.verdict,
			row.runs["opus55-low"]?.["gpt-5.5"],
		);
	}
});

test("every task has instructions, documents, and rendered deliverables", () => {
	for (const task of loadLab().tasks) {
		assert.ok(task.instructions.length > 0, task.slug);
		assert.ok(task.documents.length > 0, `${task.slug} documents`);
		for (const run of ["luna", "opus"] as const) {
			assert.ok(task.runs[run].deliverables.length > 0, `${task.slug} ${run}`);
		}
		for (const document of task.documents) {
			assert.match(
				document.url,
				/^https:\/\/github\.com\/harveyai\/harvey-labs\//,
			);
		}
	}
});

type Letter = "p" | "f";

function criterionWith(
	grades: readonly [Letter, Letter, Letter, Letter],
	flagged: boolean,
): Criterion {
	const [ls, lg, os, og] = grades;
	const grade = (letter: Letter) => ({
		verdict: letter === "p" ? ("pass" as const) : ("fail" as const),
		reasoning: "",
	});
	return {
		id: "C-001",
		number: 1,
		title: "t",
		rubric: "r",
		line: null,
		deliverables: [],
		ai: {
			sol: flagged ? "arguable" : null,
			opus: null,
			opusBlind: null,
			bucket: flagged ? "sol_only" : null,
			solFindings: [],
			opusFindings: [],
			opusOnSol: [],
		},
		grades: {
			luna: { sonnet: grade(ls), gpt: grade(lg) },
			opus: { sonnet: grade(os), gpt: grade(og) },
		},
		review: null,
	};
}

test("filter flags mean what their labels say", () => {
	const allPass = flagsFor(
		criterionWith(["p", "p", "p", "p"], false),
		undefined,
	);
	assert.equal(allPass, 0);

	const split = flagsFor(criterionWith(["f", "p", "p", "p"], true), undefined);
	assert.ok(
		matchesMask(split, maskFor(["failedAny", "judgeDisagree", "flagged"])),
	);
	assert.equal(matchesMask(split, maskFor(["reviewed"])), false);

	// Both judges fail the same run: failed, but the judges agree.
	const agreed = flagsFor(
		criterionWith(["f", "f", "p", "p"], false),
		undefined,
	);
	assert.ok(agreed & FLAG.failedAny);
	assert.equal(agreed & FLAG.judgeDisagree, 0);

	// No active filter matches everything.
	assert.ok(matchesMask(0, 0));
	assert.equal(FILTERS.length, 5);
});

test("the compact index matches the data and carries the reviewed flags", () => {
	const lab = loadLab();
	const index = buildIndex(lab);
	assert.equal(index.rows.length, 2858);
	assert.equal(index.tasks.length, 52);
	assert.equal(index.rows.filter((row) => row[3] & FLAG.reviewed).length, 25);
	assert.equal(index.rows.filter((row) => row[3] & FLAG.flagged).length, 835);
	const defective = lab.review.filter((i) => i.verdict === "Defective").length;
	assert.equal(
		index.rows.filter((row) => row[3] & FLAG.humanDefective).length,
		defective,
	);
	// Fail bits agree with the grades they summarize.
	for (const row of index.rows.slice(0, 200)) {
		const criterion = lab.tasks[row[0]]?.criteria.find(
			(c) => c.number === row[1],
		);
		assert.ok(criterion);
		GRADE_SLOTS.forEach(({ run, judge }, bit) => {
			assert.equal(
				(row[6] >> bit) & 1,
				criterion.grades[run][judge].verdict === "fail" ? 1 : 0,
			);
		});
	}
});

test("per-task detail lines up with the criteria it describes", () => {
	const task = loadLab().tasks[0];
	assert.ok(task);
	const payload = buildDetail(task);
	assert.equal(payload.criteria.length, task.criteria.length);
	const first = payload.criteria[0];
	assert.equal(first?.reasoning.length, 4);
	assert.equal(
		first?.reasoning[0],
		task.criteria[0]?.grades.luna.sonnet.reasoning,
	);
	assert.equal(
		first?.reasoning[3],
		task.criteria[0]?.grades.opus.gpt.reasoning,
	);
	assert.equal(first?.rubric, task.criteria[0]?.rubric);
});

test("markup escapes judge text and renders the reviewer as human", () => {
	const hostile = '<img src=x onerror=alert(1)> & "quoted"';
	const task = loadLab().tasks[0];
	assert.ok(task);
	const detail = {
		...buildDetail(task).criteria[0],
		rubric: hostile,
		reasoning: [hostile, hostile, hostile, hostile],
	} as CriterionDetail;
	const html = criterionBodyHtml(task.slug, detail);
	assert.doesNotMatch(html, /<img/);
	assert.match(
		html,
		/&lt;img src=x onerror=alert\(1\)&gt; &amp; &quot;quoted&quot;/,
	);
	assert.match(reviewBadgeHtml("Defective", 7), /Reviewer #7:<\/b>Defective/);
	assert.doesNotMatch(reviewBadgeHtml("Defective", 7), /AI/);
	assert.match(aiStatusHtml("Sol", "arguable"), /AI Sol/);
	assert.equal(aiStatusHtml("Sol", null), "");
});

test("filter state round-trips through the URL and ignores unknown keys", () => {
	const state = parseFilterState(
		"?f=flagged,bogus,failedAny,flagged&q=rule+9&task=a-task",
	);
	assert.deepEqual(state, {
		filters: ["flagged", "failedAny"],
		query: "rule 9",
		task: "a-task",
	});
	assert.deepEqual(parseFilterState(`?${serializeFilterState(state)}`), state);
	assert.equal(serializeFilterState(EMPTY_FILTER_STATE), "");
	assert.ok(matchesQuery("C-012 Identifies Atlantic Marine", "atlantic c-012"));
	assert.equal(
		matchesQuery("C-012 Identifies Atlantic Marine", "twombly"),
		false,
	);
});

test("the review summary's cross-tab accounts for every item once", () => {
	const summary = summarizeReview(loadLab().review);
	let cells = 0;
	for (const row of Object.values(summary.crossTab))
		for (const cell of Object.values(row)) cells += cell.length;
	assert.equal(cells, 25);
	assert.equal(summary.verdicts.Defective.length, 16);
	assert.ok(summary.objectiveErrors.length > 0);
	assert.ok(summary.tasksWithDefectiveEnvironment <= summary.tasks);
});
