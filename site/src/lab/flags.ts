/**
 * Criterion filters, shared by the build (which stamps each criterion with a
 * bitmask) and the browser (which tests the mask). Keeping the predicate here
 * means a task page, the all-criteria scanner and the tests agree on what
 * "failed by any run" or "judge disagreement" means.
 */
import type { Criterion, JudgeKey, ReviewItem, RunKey } from "./types.js";

export const RUNS: readonly RunKey[] = ["luna", "opus"];
export const JUDGES: readonly JudgeKey[] = ["sonnet", "gpt"];

export const FLAG = {
	/** Finally flagged problematic or arguable by at least one audit model. */
	flagged: 1,
	/** One of the 25 criteria the reviewer judged himself. */
	reviewed: 2,
	/** At least one of the four native grades is a fail. */
	failedAny: 4,
	/** On at least one run, the two judges disagree. */
	judgeDisagree: 8,
	/** The reviewer found the criterion defective. */
	humanDefective: 16,
} as const;

export type FilterKey = keyof typeof FLAG;

export const FILTERS: readonly {
	key: FilterKey;
	label: string;
	hint: string;
}[] = [
	{ key: "reviewed", label: "Hand-audited", hint: "judged by the reviewer" },
	{
		key: "humanDefective",
		label: "Defective per reviewer",
		hint: "the reviewer's own verdict",
	},
	{ key: "flagged", label: "AI-flagged", hint: "AI audit, unverified" },
	{ key: "failedAny", label: "Failed by any run", hint: "native AI grades" },
	{
		key: "judgeDisagree",
		label: "Judges disagree",
		hint: "Sonnet 4.6 and GPT-5.5 differ",
	},
];

export function flagsFor(
	criterion: Criterion,
	review: ReviewItem | undefined,
): number {
	let flags = 0;
	if (criterion.ai.bucket !== null) flags |= FLAG.flagged;
	if (review) {
		flags |= FLAG.reviewed;
		if (review.verdict === "Defective") flags |= FLAG.humanDefective;
	}
	for (const run of RUNS) {
		const sonnet = criterion.grades[run].sonnet.verdict;
		const gpt = criterion.grades[run].gpt.verdict;
		if (sonnet === "fail" || gpt === "fail") flags |= FLAG.failedAny;
		if (sonnet !== gpt) flags |= FLAG.judgeDisagree;
	}
	return flags;
}

export function maskFor(active: readonly FilterKey[]): number {
	return active.reduce((mask, key) => mask | FLAG[key], 0);
}

/** A criterion matches when it carries every active filter's flag. */
export function matchesMask(flags: number, mask: number): boolean {
	return (flags & mask) === mask;
}

const FILTER_KEYS: ReadonlySet<string> = new Set(FILTERS.map((f) => f.key));

export function isFilterKey(value: string): value is FilterKey {
	return FILTER_KEYS.has(value);
}
