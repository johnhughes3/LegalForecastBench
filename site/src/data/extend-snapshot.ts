import type { SiteExport, SiteUnit } from "../generated/site-export.js";
import { canonicalCost } from "./canonical-costs.js";
import {
	parseSnapshot,
	type ResultsSnapshot,
	type SnapshotModel,
} from "./snapshot.js";

export interface ResultSource {
	slug: string;
	release_date: string;
	forecast_run: string;
	scoring_run: string;
	access: string;
	provider: string;
	release: string;
	release_digest: string;
	/** Reader-facing name; run settings belong in `reasoning` and `access`. */
	display_name: string;
	reasoning: string;
}
export interface PublishedResult {
	source: ResultSource;
	data: SiteExport;
}

export const publicUnitCensus = (units: SiteUnit[]) =>
	JSON.stringify(
		units
			.map((u) => [u.case_id, u.unit_id, u.outcome])
			.sort((a, b) => JSON.stringify(a).localeCompare(JSON.stringify(b))),
	);

/** Keep scored metrics authoritative and reject incompatible experiment rows. */
export function extendSnapshot(
	original: ResultsSnapshot,
	additions: PublishedResult[],
): ResultsSnapshot {
	let reference: string | undefined;
	const models = additions.map(({ source, data }): SnapshotModel => {
		if (
			source.release !== original.provenance.release ||
			source.release_digest !== original.provenance.release_digest ||
			data.contamination_boundary !== original.cohort.decision_window.start ||
			data.excluded_case_count !== 0 ||
			data.results.length !== 1
		)
			throw new Error("Incompatible cohort provenance");
		const row = data.results[0];
		if (row?.metadata.condition !== "agentic" || row.metadata.ablation !== null)
			throw new Error("Only agentic results belong in this snapshot");
		const units = row.units;
		const unique = new Set(
			units.map((u) => JSON.stringify([u.case_id, u.unit_id])),
		);
		if (
			row.case_count !== original.cohort.case_count ||
			row.unit_count !== original.cohort.unit_count ||
			units.length !== row.unit_count ||
			unique.size !== units.length ||
			new Set(units.map((u) => u.case_id)).size !== row.case_count ||
			units.filter((u) => u.outcome === 1).length !==
				original.cohort.dismissed_unit_count
		)
			throw new Error("Incompatible cohort counts");
		const current = publicUnitCensus(units);
		if (reference !== undefined && current !== reference)
			throw new Error("Incompatible cohort unit identities or outcomes");
		reference = current;
		const correct = (u: SiteUnit) =>
			Number(u.probability_fully_dismissed >= 0.5) === u.outcome;
		const high = units.filter(
			(u) =>
				u.probability_fully_dismissed >= 0.9 ||
				u.probability_fully_dismissed <= 0.1,
		);
		return {
			slug: source.slug,
			display_name: source.display_name,
			provider: source.provider,
			model_key: row.model_id,
			access: source.access,
			reasoning: source.reasoning,
			release_date: source.release_date,
			training_cutoff: row.metadata.training_cutoff,
			eligibility: row.metadata.comparison_eligibility,
			eligibility_reason: row.metadata.eligibility_reason,
			github_run_id: source.forecast_run,
			micro_brier: row.micro_brier,
			equal_case_brier: row.equal_case_brier,
			correct: units.filter(correct).length,
			high_confidence: {
				count: high.length,
				wrong: high.filter((u) => !correct(u)).length,
				mean_confidence: high.length
					? high.reduce(
							(sum, u) =>
								sum +
								Math.max(
									u.probability_fully_dismissed,
									1 - u.probability_fully_dismissed,
								),
							0,
						) / high.length
					: null,
			},
			cost: canonicalCost(row.costs, row.case_count),
		};
	});
	return parseSnapshot({
		...structuredClone(original),
		snapshot_id: "beta-2026-09-27",
		as_of: "2026-09-27",
		provenance: {
			...original.provenance,
			method: `${original.provenance.method} Six later full-document agentic configurations use native scored exports. Accuracy and confidence counts derive from their public prediction units.`,
		},
		models: [...original.models, ...models],
	});
}
