import { SITE_DESCRIPTION } from "./identity.js";

/**
 * Title and description for each static HTML page.
 * Titles stay short enough that `documentTitle` can append the site name.
 * Descriptions are the sentences already used on those pages.
 */
/** The home page introduction, written by the author for the site. */
export const HOME_INTRO =
	"LegalForecastBench is an effort to develop a new, challenging benchmark that uses the signal from judicial decisions to evaluate frontier models on high-level legal tasks against an objective real-world ground truth. Models receive the same briefs a federal judge received when ruling on a motion to dismiss, and are asked to estimate the probability that the judge dismissed each claim challenged by a defendant.";

/** The home page's "Why judicial outcomes" section, written by the author. */
export const WHY_OUTCOMES = {
	quote:
		"“It is emphatically the province and duty of the Judicial Department to say what the law is.”",
	/** Background and full text of the opinion (National Archives). */
	marburyUrl: "https://www.archives.gov/milestone-documents/marbury-v-madison",
	afterCase:
		" 5 U.S. 137, 177 (1803). Every litigated judgment has the force of law as between the parties, and definitively resolves any disputes between the parties on the interpretation of the law or its application to a specific fact pattern. Moreover, one of the important, foundational principles of our common law heritage is that these judicial dispositions are public. Judges interpret, and make, law so their reasoned opinions are a public asset.",
	motions:
		"LegalForecastBench is an illustration of one specific use of the signal that lies in this data, using judges' rulings on motions to dismiss to evaluate the predictive abilities of frontier models. The benchmark focuses on district court level motions because lower courts are heavily constrained by precedent and largely decide garden-variety disputes in which the ability to correctly analyze and apply the law to the alleged facts will be the primary way to predict the outcome. Obviously, not every judicial disposition is accurate. But unless and until overturned on appeal, these dispositions have the force of law and are the main source of signal that real lawyers rely on to understand how the law will be applied to concrete fact patterns.",
} as const;

export const COPY = {
	home: {
		title: "Can AI forecast motions to dismiss?",
		description: SITE_DESCRIPTION,
	},
	paper: {
		title: "Legal forecasting working paper",
		description:
			"Working paper on using real-world judicial outcomes to evaluate AI legal reasoning.",
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
