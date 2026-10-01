/** Essay date shown on the analysis hub and used as the page's lastmod. */
export const APPROACH_PUBLISHED = "2026-09-27";

export const APPROACH_HEADING = "Law can be a verifiable domain";

export const APPROACH_LEAD =
	"AI has improved fastest where answers can be checked: code that compiles and passes tests, math with a known result. Law has seemed different, because good legal work is judged by other lawyers and much of it is confidential. Public litigation changes that for an important slice of legal reasoning.";

export const APPROACH_PIPELINE: readonly { step: string; body: string }[] = [
	{
		step: "Public record",
		body: "Complaints, motions, oppositions, replies, and the docket, filed publicly in federal court.",
	},
	{
		step: "Curation",
		body: "Select usable motions, repair mislabeled dockets, confirm the record the judge saw, and define each claim-defendant unit.",
	},
	{
		step: "Two signals",
		body: "The outcome of each unit, which can be checked, and the judge's written reasoning, which explains why.",
	},
	{
		step: "Uses",
		body: "Evaluation designed to limit contamination today. Possibly verifiable training signal for legal judgment tomorrow.",
	},
];

/** Dimension, outcome grading, rubric grading. */
export const APPROACH_COMPARISON: readonly [string, string, string][] = [
	[
		"What is graded",
		"Whether the forecast matched what the court actually did",
		"Whether a deliverable satisfies criteria an expert wrote in advance",
	],
	[
		"Who writes the answer key",
		"The court, in its written ruling",
		"The benchmark's authors",
	],
	[
		"How it is scored",
		"A proper scoring rule (Brier) over probabilities",
		"Model judges applying pass/fail criteria",
	],
	[
		"Main failure mode",
		"Noisy or mislabeled outcomes; a narrow task",
		"Criteria that are wrong, inconsistent, or unrequested",
	],
	[
		"What it measures best",
		"Calibrated judgment about how a real decision-maker will act",
		"Quality and completeness of legal work product",
	],
	[
		"Contamination",
		"Decisions must postdate the reported training or knowledge cutoff; limited contamination remains an assumption",
		"Tasks can be held out, but grow stale once public",
	],
];
