/** Shapes shared by the LAB explorer's build-time loader, pages, and client scripts. */

/** The two published model runs that were graded. */
export type RunKey = "luna" | "opus";
/** The two native LAB judges. */
export type JudgeKey = "sonnet" | "gpt";
export type Verdict = "pass" | "fail";

/** An audit model's final position on one criterion. */
export type AiStatus =
	| "problematic"
	| "arguable"
	| "unverified"
	| "qualified_check";

export type Bucket =
	| "both_problematic"
	| "both_arguable"
	| "split"
	| "sol_only"
	| "opus_only";

export type Grade = {
	verdict: Verdict;
	reasoning: string;
};

/** Grades for one criterion: a verdict and reasoning from each judge on each run. */
export type Grades = Record<RunKey, Record<JudgeKey, Grade>>;

/** The AI audit record for one criterion. Every field is AI generated and unverified. */
export type AiAudit = {
	/** GPT-6 Sol's final status; null when it did not flag the criterion. */
	sol: AiStatus | null;
	/** Claude Opus 5.5's final (post-reconciliation) status. */
	opus: AiStatus | null;
	/** Claude Opus 5.5's blind-pass status, before it saw GPT-6 Sol's work. */
	opusBlind: AiStatus | null;
	/** Agreement group for a final flag; null when neither model finally flagged it. */
	bucket: Bucket | null;
	solFindings: readonly string[];
	opusFindings: readonly string[];
	opusOnSol: readonly string[];
};

export type RubricVerdict =
	| "Defective"
	| "Arguable"
	| "Not defective"
	| "Unresolved";
export type EnvironmentVerdict = "Defective" | "Arguable" | "Correct";
export type AiReasoning = "Correct" | "Partly correct" | "Wrong";

/** One of the 25 criteria the reviewer judged himself. These are the reviewer's own words. */
export type ReviewItem = {
	/** 1-based position in the worksheet, which is also the walk-through order. */
	number: number;
	task: string;
	criterion: string;
	verdict: RubricVerdict;
	aiReasoning: AiReasoning;
	environment: EnvironmentVerdict;
	/** The reviewer's explanation of the environment verdict, when he gave one. */
	environmentNote: string;
	/** The note and source locator, one string per paragraph, verbatim. */
	note: readonly string[];
	/** The reviewer's category line, verbatim; empty when he gave none. */
	category: string;
};

export type Criterion = {
	id: string;
	/** Numeric part of the id, for sorting and compact encoding. */
	number: number;
	title: string;
	/** Rubric text (`match_criteria`) as published upstream. */
	rubric: string;
	/** Line of this criterion in the pinned upstream task.json, for deep links. */
	line: number | null;
	deliverables: readonly string[];
	ai: AiAudit;
	grades: Grades;
	/** Worksheet number when the reviewer judged this criterion. */
	review: number | null;
};

export type RunSummary = {
	/** Criteria each judge passed, and whether the judge's all-pass score is 1. */
	judges: Record<JudgeKey, { passed: number; total: number; allPass: boolean }>;
	/** Deliverable file names, matching the content collection ids. */
	deliverables: readonly string[];
};

export type TaskDocument = { name: string; url: string };

export type Task = {
	slug: string;
	title: string;
	workType: string;
	tags: readonly string[];
	instructions: string;
	documents: readonly TaskDocument[];
	criteria: readonly Criterion[];
	runs: Record<RunKey, RunSummary>;
};

export type LabData = {
	tasks: readonly Task[];
	review: readonly ReviewItem[];
	/** Number of criteria finally flagged by either model. */
	flaggedTotal: number;
};
