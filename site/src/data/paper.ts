/**
 * The working paper, as listed on /paper/ and linked from every page.
 *
 * One record, so the landing page, header action, and homepage cannot drift.
 * To publish a version: add the immutable PDF under public/papers/, append a
 * row to `versions`, and point `current` at it. Never overwrite a released
 * PDF; a correction is a new version with a note.
 */
export interface PaperVersion {
	version: string;
	/** ISO date the version was posted. */
	date: string;
	/** Site path of the immutable PDF, e.g. /papers/legalforecastbench-v0.1.pdf. */
	pdf: string;
	/** The results release the version analyzes. */
	release: string;
	/** What changed from the prior version; omit for the first. */
	changes?: string;
}

export const PAPER = {
	title:
		"LegalForecastBench: Evaluating Probabilistic Legal Judgment from Pre-Decision Court Records",
	author: "John J. Hughes, III",
	status: "Working paper",
	// Draft abstract assembled from the released results. Replace with the
	// paper's own abstract when the PDF is posted.
	abstract: [
		"LegalForecastBench asks whether AI models can forecast federal motion-to-dismiss outcomes from the court record available before the decision. Each model receives the pre-decision docket and filings through a controlled document-tool harness and gives the probability that each challenged claim against each defendant is fully dismissed in the motion's first written disposition. Forecasts are scored with the Brier score against the court's actual ruling.",
		"The first release covers 91 cases and 387 claim-defendant units decided between June 30 and August 7, 2026. We report observed ordering, paired case-level uncertainty where unit-level predictions are available, calibration, and cost, together with a controlled experiment on summary-based forecasting and an error analysis of confident misses and procedural outcomes.",
	],
	versions: [] as PaperVersion[],
} as const;

/** The newest posted version, or null before the first PDF is released. */
export const currentPaper: PaperVersion | null = PAPER.versions.at(-1) ?? null;
