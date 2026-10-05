/** Counts shown on the explorer landing pages, computed from the loaded data. */
import { JUDGES, RUNS } from "./flags.js";
import type {
	AiReasoning,
	EnvironmentVerdict,
	JudgeKey,
	LabData,
	ReviewItem,
	RubricVerdict,
	RunKey,
} from "./types.js";
import {
	AI_REASONING,
	ENVIRONMENT_VERDICTS,
	RUBRIC_VERDICTS,
} from "./worksheet.js";

/** Worksheet numbers per cell, so every count can link to its items. */
type Cells<K extends string> = Record<K, number[]>;

export type ReviewSummary = {
	total: number;
	verdicts: Cells<RubricVerdict>;
	aiReasoning: Cells<AiReasoning>;
	environment: Cells<EnvironmentVerdict>;
	crossTab: Record<RubricVerdict, Cells<EnvironmentVerdict>>;
	/** Defective items the reviewer categorized as an unambiguous objective error. */
	objectiveErrors: number[];
	/** Distinct tasks in the sample, and how many have a defective environment. */
	tasks: number;
	tasksWithDefectiveEnvironment: number;
};

function cells<K extends string>(keys: readonly K[]): Cells<K> {
	return Object.fromEntries(
		keys.map((key) => [key, [] as number[]]),
	) as Cells<K>;
}

export function summarizeReview(items: readonly ReviewItem[]): ReviewSummary {
	const verdicts = cells(RUBRIC_VERDICTS);
	const aiReasoning = cells(AI_REASONING);
	const environment = cells(ENVIRONMENT_VERDICTS);
	const crossTab = Object.fromEntries(
		RUBRIC_VERDICTS.map((verdict) => [verdict, cells(ENVIRONMENT_VERDICTS)]),
	) as Record<RubricVerdict, Cells<EnvironmentVerdict>>;
	const objectiveErrors: number[] = [];
	for (const item of items) {
		verdicts[item.verdict].push(item.number);
		aiReasoning[item.aiReasoning].push(item.number);
		environment[item.environment].push(item.number);
		crossTab[item.verdict][item.environment].push(item.number);
		if (
			item.verdict === "Defective" &&
			/^unambiguous objective error/i.test(item.category)
		)
			objectiveErrors.push(item.number);
	}
	const tasks = new Set(items.map((item) => item.task));
	const badEnvironments = new Set(
		items.filter((item) => item.environment === "Defective").map((i) => i.task),
	);
	return {
		total: items.length,
		verdicts,
		aiReasoning,
		environment,
		crossTab,
		objectiveErrors,
		tasks: tasks.size,
		tasksWithDefectiveEnvironment: badEnvironments.size,
	};
}

export type RunTotals = Record<
	RunKey,
	Record<
		JudgeKey,
		{ passed: number; total: number; tasksAllPass: number; tasks: number }
	>
>;

/** Criterion-level pass counts and all-pass task counts per run and judge. */
export function summarizeRuns(lab: LabData): RunTotals {
	const totals = {} as RunTotals;
	for (const run of RUNS) {
		const byJudge = {} as RunTotals[RunKey];
		for (const judge of JUDGES) {
			let passed = 0;
			let total = 0;
			let tasksAllPass = 0;
			for (const task of lab.tasks) {
				total += task.criteria.length;
				passed += task.criteria.filter(
					(criterion) => criterion.grades[run][judge].verdict === "pass",
				).length;
				if (task.runs[run].judges[judge].allPass) tasksAllPass += 1;
			}
			byJudge[judge] = { passed, total, tasksAllPass, tasks: lab.tasks.length };
		}
		totals[run] = byJudge;
	}
	return totals;
}
