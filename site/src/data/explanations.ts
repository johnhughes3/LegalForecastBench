/** Reader-facing explanations shared by tooltips across the site. */
export const EXPLAIN = {
	eligible:
		"Eligible: training data/knowledge cutoff is before the decisions we used to test.",
	qualified:
		"Qualified: no published training data/knowledge cutoff, or the cutoff is not before the decisions we used to test.",
	unknown: "Unknown: no cutoff information recorded.",
	frontier:
		"On the observed cost/quality frontier: no other model is both cheaper and at least as good, and this model strictly improves over others on at least one dimension. (Note that the improvement does not have to be statistically significant.)",
	significance:
		"From a paired case-cluster bootstrap with a Bonferroni correction for multiple comparisons. Differences not listed may still be real; the sample is small.",
	headline:
		"Micro Brier is the headline metric: squared error of each dismissal forecast, averaged over all claim-defendant units. Lower is better; always answering 50% scores 0.25.",
	rank: "Rank by micro Brier, the headline metric. Tied scores share a rank.",
	auc: "AUC: the chance that a randomly chosen dismissed unit got a higher forecast than a randomly chosen surviving one. 0.5 is no ranking ability; 1.0 is perfect. It ignores calibration.",
	meanForecast:
		"Average forecast probability of dismissal across all units. A calibrated model's average is close to the actual dismissal rate.",
} as const;
