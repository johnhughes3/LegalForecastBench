/** Reader-facing explanations shared by tooltips across the site. */
export const EXPLAIN = {
	eligible:
		"Eligible: the provider documents a training-data cutoff before every decision in this cohort, so the outcomes should postdate the model's training data. A stated cutoff is evidence, not proof.",
	qualified:
		"Qualified: we cannot confirm that the model's training data predates every decision. The cutoff may be unpublished, reported only as a knowledge cutoff, or overlap the decision window. The score is shown, but read it with that caveat.",
	unknown:
		"Unknown: the export does not record enough information to assess whether the model's training data predates the decisions.",
	frontier:
		"On the observed cost/quality frontier: no other model is both cheaper and at least as good, with a strict improvement in one. Descriptive only; it is not a significance test.",
	significance:
		"From a paired case-cluster bootstrap with a Bonferroni correction for multiple comparisons. Differences not listed may still be real; the sample is small.",
	headline:
		"Micro Brier is the headline metric: squared error of each dismissal forecast, averaged over all claim-defendant units. Lower is better; always answering 50% scores 0.25.",
	rank: "Rank by micro Brier, the headline metric. Tied scores share a rank.",
	auc: "AUC: the chance that a randomly chosen dismissed unit got a higher forecast than a randomly chosen surviving one. 0.5 is no ranking ability; 1.0 is perfect. It ignores calibration.",
	meanForecast:
		"Average forecast probability of dismissal across all units. A calibrated model's average is close to the actual dismissal rate.",
} as const;
