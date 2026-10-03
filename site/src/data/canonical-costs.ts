import type { SiteCosts } from "../generated/site-export.js";
import type { SnapshotModel } from "./snapshot.js";

/** The scoring export owns its cost evidence; saved enrichments are legacy fallbacks. */
export function hasCanonicalCosts(costs: SiteCosts): boolean {
	return (
		costs.basis !== "unavailable" && costs.basis !== "estimated_accounting"
	);
}

/** Only a complete standard-rate estimate belongs in comparative cost charts. */
export function canonicalCost(
	costs: SiteCosts,
	caseCount: number,
): SnapshotModel["cost"] {
	const complete =
		costs.standard_rate_status === "complete" &&
		costs.standard_rate_covered_case_count === caseCount &&
		costs.missing_case_count === 0 &&
		costs.covered_case_count === caseCount &&
		costs.standard_rate_total_cost != null;
	const amount = complete ? (costs.standard_rate_total_cost ?? null) : null;
	const workloadBasis =
		costs.basis === "provider_reported"
			? "reported charge"
			: costs.basis === "mixed_receipt_evidence"
				? "mixed reported charges and usage estimates"
				: "usage estimate";
	const workload =
		costs.total_cost === null
			? "Workload cost unavailable."
			: `Successful workload ${workloadBasis}: $${costs.total_cost.toFixed(4)}; accounting covers ${costs.covered_case_count} of ${caseCount} cases.`;
	const standard = complete
		? `Standard-rate estimate covers all ${caseCount} cases.`
		: `Standard-rate estimate ${costs.standard_rate_status ?? "unavailable"}; covers ${costs.standard_rate_covered_case_count ?? 0} of ${caseCount} cases. Excluded from comparative cost charts.`;
	const cache = `Missing cache read/write dimensions: ${costs.missing_cache_read_response_count ?? 0}/${costs.missing_cache_write_response_count ?? 0} responses; missing cache prices: ${costs.missing_cache_rate_response_count ?? 0} responses; missing response usage: ${costs.missing_response_usage_case_count ?? 0} cases.`;
	return {
		usd: amount,
		basis: amount === null ? "unavailable" : "standard_rate",
		note: [workload, standard, cache, ...(costs.caveats ?? [])].join(" "),
	};
}
