import { SITE_DESCRIPTION } from "./identity.js";

/**
 * Title and description for each static HTML page.
 * Titles stay short enough that `documentTitle` can append the site name.
 * Descriptions are the sentences already used on those pages.
 */
export const COPY = {
	home: {
		title: "Can AI forecast motions to dismiss?",
		description: SITE_DESCRIPTION,
	},
	results: {
		title: "Motion-to-dismiss forecast results",
		description:
			"Full-document leaderboard, cost frontier, and calibration for every model configuration in the current LegalForecastBench release.",
	},
	methods: {
		title: "How the forecasts are scored",
		description:
			"How LegalForecastBench builds its cases, runs models, and scores forecasts.",
	},
	paper: {
		title: "Legal forecasting working paper",
		description:
			"Working paper on forecasting federal judicial decisions as a test of legal reasoning.",
	},
	analysis: {
		title: "Forecast analysis and experiments",
		description:
			"Essays, reports, experiments, and audit notes on LegalForecastBench, each marked with its date, the release it analyzes, and how much evidence it carries.",
	},
	data: {
		title: "Download the forecast results",
		description:
			"Download the results LegalForecastBench displays, reproduce the scoring, and see where the evidence comes from.",
	},
	approach: {
		title: "Why score judicial outcomes",
		description:
			"Why public litigation makes parts of law a verifiable domain, and how outcome-based evaluation compares with rubric-based grading.",
	},
	experiment: {
		title: "Summary pipeline experiment",
		description:
			"On shared GPT-5.6 Luna summaries, Jev forecast motions to dismiss worse than always guessing 50%. OpenAI controls beat the base rate. A separate Grok-short condition uses different summaries.",
	},
	runNotes: {
		title: "Run notes and cost methods",
		description:
			"How results were produced, what the significance analysis covers, and how costs were estimated.",
	},
} as const;
