import type { ResultSource } from "./extend-snapshot.js";
import records from "./receipt-costs.json" with { type: "json" };
import { parseSnapshot, type ResultsSnapshot } from "./snapshot.js";

export interface ReceiptCost {
	slug: string;
	forecast_run_id: string;
	score_run_id: string;
	model_key: string;
	covered_case_count: number;
	missing_case_count: number;
	workload_cost_usd: number;
	workload_cost_basis: string;
	standard_rate_estimate_usd: number | null;
	standard_rate_multiplier: number;
	standard_rate_method: string;
	caveats: string[];
}

export const receiptCosts: ReceiptCost[] = records;

/** Enrich chart costs from matching saved runs without changing scored exports. */
export function applyReceiptCosts(
	snapshot: ResultsSnapshot,
	sources: ResultSource[],
	costs: ReceiptCost[] = receiptCosts,
): ResultsSnapshot {
	const models = new Map(snapshot.models.map((model) => [model.slug, model]));
	const seen = new Set<string>();
	for (const cost of costs) {
		const model = models.get(cost.slug);
		const source = sources.find((item) => item.slug === cost.slug);
		if (
			seen.has(cost.slug) ||
			!model ||
			!source ||
			model.model_key !== cost.model_key ||
			source.forecast_run !== cost.forecast_run_id ||
			source.scoring_run !== cost.score_run_id ||
			cost.covered_case_count !== snapshot.cohort.case_count ||
			cost.missing_case_count !== 0
		)
			throw new Error("Cost evidence does not match the complete selected run");
		seen.add(cost.slug);
		const estimate = cost.standard_rate_estimate_usd;
		if (estimate === null) continue;
		if (!Number.isFinite(estimate) || estimate <= 0)
			throw new Error("Chart cost must be a positive finite estimate");
		const cacheNote = cost.standard_rate_method.includes("conservative")
			? "Incomplete cache usage or prices use ordinary-input estimates, which may overstate or understate cache-adjusted costs."
			: "Retains reported cache usage and cache prices.";
		models.set(cost.slug, {
			...model,
			cost: {
				usd: estimate,
				basis: "estimated",
				note: `Standard-rate estimate for ${cost.covered_case_count} successful cases. ${cacheNote} Successful workload ${cost.workload_cost_basis === "provider_reported" ? "charge" : "estimate"}: $${cost.workload_cost_usd.toFixed(4)}${cost.standard_rate_multiplier === 2 ? " at Flex rates" : ""}. Excludes failed attempts and unresolved charges.`,
			},
		});
	}
	return parseSnapshot({ ...snapshot, models: [...models.values()] });
}
