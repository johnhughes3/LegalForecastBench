import analysis from "./significance/comparison.json" with { type: "json" };
import { parseSnapshot, type ResultsSnapshot } from "./snapshot.js";

export const comparison = analysis;
export const comparisonScope = `${analysis.available_models.length} of ${analysis.family_model_count} configurations have unit-level data for the updated analysis. The remaining ${analysis.missing_models.length} configurations were not tested. The correction retains all 120 pairs in the 16-model family across three metrics.`;

/** Replace the historical family, rather than mixing conclusions from two tests. */
export function applyComparison(snapshot: ResultsSnapshot): ResultsSnapshot {
	const slugs = new Set(snapshot.models.map((model) => model.slug));
	const covered = new Set(analysis.available_models);
	const family = [...analysis.available_models, ...analysis.missing_models];
	if (
		analysis.case_count !== snapshot.cohort.case_count ||
		analysis.unit_count !== snapshot.cohort.unit_count ||
		analysis.family_model_count !== slugs.size ||
		family.length !== slugs.size ||
		new Set(family).size !== slugs.size ||
		family.some((slug) => !slugs.has(slug))
	)
		throw new Error(
			"Significance analysis does not match the displayed cohort and model family",
		);
	for (const pair of analysis.significant_pairs)
		if (!covered.has(pair.better) || !covered.has(pair.worse))
			throw new Error("Significance result includes an untested model");
	return parseSnapshot({
		...snapshot,
		significant_pairs: analysis.significant_pairs,
		cohort: {
			...snapshot.cohort,
			bootstrap: {
				method: analysis.method,
				replicates: analysis.replicates,
				correction: analysis.correction,
				caveat: `${comparisonScope} ${analysis.caveat}`,
			},
		},
		provenance: {
			...snapshot.provenance,
			method: `${snapshot.provenance.method} Significance: ${comparisonScope}`,
		},
	});
}
