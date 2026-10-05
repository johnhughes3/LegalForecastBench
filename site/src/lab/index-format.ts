/**
 * Compact wire formats fetched by the browser.
 *
 * `LabIndex` is one array row per criterion (2,858 of them) so the
 * all-criteria scanner can filter without downloading any prose beyond titles.
 * `TaskDetail` carries one task's rubric text, audit findings and judge
 * reasoning, and is fetched the first time a reader opens a criterion there.
 */
import { flagsFor, JUDGES, RUNS } from "./flags.js";
import type {
	AiAudit,
	AiStatus,
	Criterion,
	LabData,
	ReviewItem,
	RubricVerdict,
	RunKey,
	Task,
	Verdict,
} from "./types.js";
import { RUBRIC_VERDICTS } from "./worksheet.js";

/** Display order of the four native grades; the same order everywhere. */
export const GRADE_SLOTS = RUNS.flatMap((run) =>
	JUDGES.map((judge) => ({ run, judge })),
);

/** 0 = not flagged, 1 = arguable, 2 = problematic. */
export type StatusCode = 0 | 1 | 2;

export function statusCode(status: AiStatus | null): StatusCode {
	if (status === "problematic") return 2;
	if (status === "arguable") return 1;
	return 0;
}

/**
 * [task index, criterion number, title, flag mask, GPT-6 Sol status,
 *  Claude Opus 5.5 status, fail bits (bit i = GRADE_SLOTS[i] failed),
 *  worksheet number or 0, reviewer verdict as 1 + index into RUBRIC_VERDICTS
 *  or 0]
 */
export type IndexRow = readonly [
	task: number,
	number: number,
	title: string,
	flags: number,
	sol: StatusCode,
	opus: StatusCode,
	fails: number,
	review: number,
	reviewVerdict: number,
];

export type LabIndex = {
	tasks: readonly { slug: string; title: string }[];
	rows: readonly IndexRow[];
};

/** What an opened criterion needs beyond its summary row. */
export type CriterionDetail = {
	rubric: string;
	line: number | null;
	ai: AiAudit;
	/** Verdicts in GRADE_SLOTS order. */
	verdicts: readonly Verdict[];
	/** Judge reasoning in GRADE_SLOTS order. */
	reasoning: readonly string[];
	/** Deliverable names this criterion is graded against, per run. */
	deliverables: Record<RunKey, readonly string[]>;
};

export type TaskDetail = {
	task: string;
	/** In task order, aligned with the rows on the task page. */
	criteria: readonly CriterionDetail[];
};

export function buildIndex(lab: LabData): LabIndex {
	const reviewByNumber = new Map<number, ReviewItem>(
		lab.review.map((item) => [item.number, item]),
	);
	const rows: IndexRow[] = [];
	lab.tasks.forEach((task, taskIndex) => {
		for (const criterion of task.criteria) {
			const review =
				criterion.review === null
					? undefined
					: reviewByNumber.get(criterion.review);
			let fails = 0;
			GRADE_SLOTS.forEach(({ run, judge }, bit) => {
				if (criterion.grades[run][judge].verdict === "fail") fails |= 1 << bit;
			});
			rows.push([
				taskIndex,
				criterion.number,
				criterion.title,
				flagsFor(criterion, review),
				statusCode(criterion.ai.sol),
				statusCode(criterion.ai.opus),
				fails,
				criterion.review ?? 0,
				review ? 1 + RUBRIC_VERDICTS.indexOf(review.verdict) : 0,
			]);
		}
	});
	return {
		tasks: lab.tasks.map(({ slug, title }) => ({ slug, title })),
		rows,
	};
}

export function criterionDetail(
	task: Task,
	criterion: Criterion,
): CriterionDetail {
	const named = (run: RunKey): readonly string[] => {
		const own = task.runs[run].deliverables.filter((name) =>
			criterion.deliverables.includes(name),
		);
		return own.length > 0 ? own : task.runs[run].deliverables;
	};
	return {
		rubric: criterion.rubric,
		line: criterion.line,
		ai: criterion.ai,
		verdicts: GRADE_SLOTS.map(
			({ run, judge }) => criterion.grades[run][judge].verdict,
		),
		reasoning: GRADE_SLOTS.map(
			({ run, judge }) => criterion.grades[run][judge].reasoning,
		),
		deliverables: { luna: named("luna"), opus: named("opus") },
	};
}

export function buildDetail(task: Task): TaskDetail {
	return {
		task: task.slug,
		criteria: task.criteria.map((criterion) =>
			criterionDetail(task, criterion),
		),
	};
}

export const criterionId = (number: number): string =>
	`C-${String(number).padStart(3, "0")}`;

/** The reviewer's verdict for an index row, or null when the criterion was not hand-audited. */
export function reviewVerdictOf(row: IndexRow): RubricVerdict | null {
	return RUBRIC_VERDICTS[row[8] - 1] ?? null;
}
