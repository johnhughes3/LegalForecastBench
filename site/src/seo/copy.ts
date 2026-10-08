import { SITE_DESCRIPTION } from "./identity.js";

/**
 * Title and description for each static HTML page.
 * Titles stay short enough that `documentTitle` can append the site name.
 * Descriptions are the sentences already used on those pages.
 */
/** The home page introduction, written by the author for the site. */
export const HOME_INTRO =
	"LegalForecastBench is an effort to develop a new, challenging benchmark that uses the signal from judicial decisions to evaluate frontier models on high-level legal tasks against an objective real-world ground truth. Models receive the same briefs a federal judge received when ruling on a motion to dismiss, and are asked to estimate the probability that the judge dismissed each claim challenged by a defendant.";

export const COPY = {
	home: {
		title: "Can AI forecast motions to dismiss?",
		description: SITE_DESCRIPTION,
	},
	paper: {
		title: "Legal forecasting working paper",
		description:
			"Working paper on forecasting federal judicial decisions as a test of legal reasoning.",
	},
	data: {
		title: "Download the forecast results",
		description:
			"Download the results LegalForecastBench displays, reproduce the scoring, and see where the evidence comes from.",
	},
	/** The LAB explorer is offline until the audit paper is published. */
	lab: {
		title: "Harvey LAB litigation explorer",
		description:
			"Explore Harvey LAB's 52 litigation tasks: rubric criteria, AI audit findings, two graded model runs, and a litigator's review of 25 sampled criteria.",
	},
} as const;
