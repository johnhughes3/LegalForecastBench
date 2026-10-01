/**
 * Homepage answers. Each sentence is already a claim the site makes.
 * FAQPage JSON-LD is built from this list, so the visible text and the
 * markup cannot drift. Link labels sit outside `answer` and are not schema.
 */
export interface Faq {
	question: string;
	answer: string;
	href?: string;
	hrefLabel?: string;
}

export const FAQS: readonly Faq[] = [
	{
		question: "What is LegalForecastBench?",
		answer:
			"LegalForecastBench is an open research benchmark that tests whether AI models can forecast federal motion-to-dismiss outcomes from the court record available before the decision. It measures predictive accuracy and the quality of the models' probabilities.",
		href: "/paper/",
		hrefLabel: "Working paper",
	},
	{
		question: "What does each forecast predict?",
		answer:
			"For each challenged claim against each defendant, the forecast is the probability that the claim is fully dismissed in the motion's first written disposition.",
		href: "/methods/",
		hrefLabel: "How the task is defined",
	},
	{
		question: "Are the published forecasts legal advice?",
		answer:
			"No. Published predictions are retrospective research artifacts about matters already decided. They are not legal advice.",
	},
	{
		question: "How are the forecasts scored?",
		answer:
			"The score is Brier score: the squared gap between the forecast and the outcome. It rewards calibration and discrimination, and it punishes confident errors.",
		href: "/methods/",
		hrefLabel: "Scoring and methods",
	},
	{
		question: "Where can I download the results and code?",
		answer:
			"The ranked results, downloads, and reproduction instructions are on the data and code page. The data is licensed under CC BY 4.0 and the code under the Apache License 2.0.",
		href: "/data/",
		hrefLabel: "Data and code",
	},
];
