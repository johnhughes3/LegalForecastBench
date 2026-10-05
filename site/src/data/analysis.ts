import type { CollectionEntry } from "astro:content";
import { APPROACH_PUBLISHED } from "./approach";
import { publishedFindings } from "./findings";
import { snapshot } from "./results";

/**
 * The Analysis hub: every essay, report, experiment, and audit note in one
 * index. Articles keep their original URLs (/findings/…, /experiments/…,
 * /approach/) so links shared before the reorganization still resolve.
 */
export type AnalysisGroup =
	| "rationale"
	| "results"
	| "experiments"
	| "audits"
	| "ongoing";

export type EvidenceStatus =
	| "released"
	| "exploratory"
	| "essay"
	| "unverified"
	| "ongoing";

export interface AnalysisItem {
	href: string;
	title: string;
	summary: string;
	date: Date;
	group: AnalysisGroup;
	evidence: EvidenceStatus;
	/** The results release the item analyzes; null when it is not about a release. */
	release: string | null;
	external?: boolean;
	draft?: boolean;
}

export const GROUPS: { key: AnalysisGroup; title: string; blurb: string }[] = [
	{
		key: "rationale",
		title: "Why this task",
		blurb:
			"The conceptual case for scoring legal forecasts against court outcomes.",
	},
	{
		key: "results",
		title: "Results and error analysis",
		blurb:
			"The release report and closer looks at calibration and where models lost points.",
	},
	{
		key: "experiments",
		title: "Experiments",
		blurb:
			"Controlled comparisons that change one part of the task on the same cases.",
	},
	{
		key: "audits",
		title: "Benchmark audits",
		blurb:
			"Notes on how other legal AI benchmarks specify and grade their tasks.",
	},
	{
		key: "ongoing",
		title: "Ongoing research",
		blurb:
			"Work in progress, stated as hypotheses and designs rather than results.",
	},
];

export const EVIDENCE_LABELS: Record<EvidenceStatus, string> = {
	released: "Released results",
	exploratory: "Exploratory analysis",
	essay: "Essay",
	unverified: "Unverified AI audit",
	ongoing: "Ongoing, no results yet",
};

const fmt = (iso: string) =>
	new Date(`${iso}T00:00:00Z`).toLocaleDateString("en-US", {
		month: "long",
		day: "numeric",
		year: "numeric",
		timeZone: "UTC",
	});

/** The results release every Cycle 1 analysis is computed from. */
export const CURRENT_RELEASE = `Cycle 1 beta · ${fmt(snapshot.as_of)}`;

function fromFinding(entry: CollectionEntry<"findings">): AnalysisItem {
	const { kind, evidence } = entry.data;
	return {
		href: `/findings/${entry.id}/`,
		title: entry.data.title,
		summary: entry.data.summary,
		date: entry.data.date,
		group:
			evidence === "ongoing"
				? "ongoing"
				: kind === "critique"
					? "audits"
					: "results",
		evidence: evidence ?? (kind === "report" ? "released" : "exploratory"),
		release: evidence === "ongoing" ? null : CURRENT_RELEASE,
		draft: entry.data.draft,
	};
}

/** Pages that live outside the findings collection. */
const STATIC_ITEMS: AnalysisItem[] = [
	{
		href: "/approach/",
		title: "Law can be a verifiable domain",
		summary:
			"Why public litigation makes part of legal judgment checkable, and how outcome-based evaluation differs from rubric grading.",
		date: new Date(`${APPROACH_PUBLISHED}T00:00:00Z`),
		group: "rationale",
		evidence: "essay",
		release: null,
	},
	{
		href: "/experiments/summary-pipelines/",
		title:
			"On shared Luna summaries, Jev forecast worse than always guessing 50%",
		summary:
			"TypeSafe's Jev forecast from GPT-5.6 Luna summaries and scored below every naive baseline. Two OpenAI controls given the identical summaries beat the base rate.",
		date: new Date("2026-09-27T00:00:00Z"),
		group: "experiments",
		evidence: "released",
		release: CURRENT_RELEASE,
	},
	{
		href: "/lab/",
		title: "Harvey LAB litigation explorer: AI audits and a litigator's review",
		summary:
			"Browse 52 litigation tasks, every grading criterion, two graded model runs, and the AI audits. The audits are unverified AI judgments; a litigator hand-reviewed 25 sampled criteria.",
		date: new Date("2026-10-05T00:00:00Z"),
		group: "audits",
		evidence: "unverified",
		release: null,
	},
];

// Within a date, stronger evidence leads (the release report before its notes).
const EVIDENCE_ORDER: EvidenceStatus[] = [
	"released",
	"essay",
	"exploratory",
	"unverified",
	"ongoing",
];

export async function analysisItems(): Promise<AnalysisItem[]> {
	const findings = (await publishedFindings()).map(fromFinding);
	return [...findings, ...STATIC_ITEMS].sort(
		(a, b) =>
			b.date.valueOf() - a.date.valueOf() ||
			EVIDENCE_ORDER.indexOf(a.evidence) - EVIDENCE_ORDER.indexOf(b.evidence) ||
			a.title.localeCompare(b.title),
	);
}
